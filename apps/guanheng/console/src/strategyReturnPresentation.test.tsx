import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import type { StrategyCapitalHistory, StrategyCapitalSleeve } from './types'
import { capitalDisplayNumber, capitalHistorySamples, capitalHistoryTooltip, capitalReturnMetrics, zeroObservationRange } from './strategyReturnPresentation'
import { StrategyCapitalPanel } from './components/StrategyCapitalPanel'

afterEach(cleanup)

const sleeve: StrategyCapitalSleeve = { schema_version: '1.1', strategy_lineage_id: 'synthetic-lineage',
  virtual_cash: 120, daily_return_available: false, valuation_source: 'strategy_capital_snapshot',
  reconciliation_issue_codes: [], account_boundary_captured_at: '2031-03-12T01:00:00Z',
  reconciliation_status: 'reconciled', net_asset_value: 120,
  market_value: 0, positions: [], pnl_metrics_available: true, total_return_available: false,
  capital_contributions_total: 100, total_return: 99, contributed_principal: '200.00',
  investment_pnl: '-80.00', return_on_principal: '-0.4' }

test.each([
  { contributed_principal: 100, investment_pnl: 20, return_on_principal: .2 },
  { contributed_principal: '200.00', investment_pnl: '-80.00', return_on_principal: '-0.4' },
])('uses the supplied same-boundary metrics including added principal', values => {
  const result = capitalReturnMetrics({ ...sleeve, ...values })
  expect(result).toMatchObject({ available: true, principal: Number(values.contributed_principal),
    pnl: Number(values.investment_pnl), ratio: Number(values.return_on_principal) })
})

test.each([
  undefined, { ...sleeve, contributed_principal: undefined }, { ...sleeve, return_on_principal: null },
  { ...sleeve, contributed_principal: 0 }, { ...sleeve, investment_pnl: 'NaN' },
  { ...sleeve, reconciliation_status: 'blocked' as const },
  { ...sleeve, pnl_metrics_available: false },
])('keeps missing, malformed and blocked facts unavailable', value => {
  expect(capitalReturnMetrics(value)).toMatchObject({ available: false, principal: null, pnl: null, ratio: null })
})

test('formats supplied Decimal metrics while preserving the original total-return protection', () => {
  render(<StrategyCapitalPanel sleeve={sleeve} metricsOnly />)
  expect(screen.getByText('投入本金收益率')).toBeInTheDocument()
  expect(screen.getByText('-40.00%')).toBeInTheDocument()
  expect(screen.getByText('投资盈亏 ¥ -80')).toBeInTheDocument()
  expect(screen.getByText(/投入本金 ¥ 200，包含初始与追加本金/)).toBeInTheDocument()
  expect(screen.getByText(/缺少划转时点估值/)).toBeInTheDocument()
  expect(screen.queryByText('9900.00%')).not.toBeInTheDocument()
})

test('an older backend gives an explicit missing-fields reason with no frontend estimate', () => {
  render(<StrategyCapitalPanel sleeve={{ ...sleeve, contributed_principal: undefined, investment_pnl: undefined, return_on_principal: undefined }} metricsOnly />)
  expect(screen.getByText(/当前快照尚未提供完整/)).toBeInTheDocument()
  expect(screen.getByText('投资盈亏 ¥ 不可用')).toBeInTheDocument()
})

test.each(['', ' ', 'Infinity', 'NaN', '1,000', '1oops', '1e999'])('refuses malformed decimal %j', value => {
  expect(capitalDisplayNumber(value)).toBeNull()
})

const point = (captured_at: string, status: 'ready' | 'blocked' = 'ready') => ({ captured_at,
  valuation_at: '2031-03-11T06:30:00Z', status, return_on_principal: .1, drawdown: 0 }) as StrategyCapitalHistory['points'][number]

test('daily X is the captured Beijing day; missing and blocked observations remain gaps', () => {
  const history = { sampling: 'daily', window_start: '2031-03-12T00:00:00+08:00',
    window_end: '2031-03-16T00:00:00+08:00', points: [
      point('2031-03-11T16:05:00Z'), point('2031-03-14T01:00:00Z', 'blocked'), point('2031-03-15T01:00:00Z'),
    ] } as StrategyCapitalHistory
  const samples = capitalHistorySamples(history)
  expect(samples.map(value => value.label)).toEqual(['2031-03-12', '2031-03-13', '2031-03-14', '2031-03-15'])
  expect(samples.map(value => value.returnValue)).toEqual([.1, null, null, .1])
  expect(samples.map(value => value.drawdown)).toEqual([0, null, null, 0])
  expect(samples[1].point).toBeNull()
  expect(capitalHistoryTooltip(samples[0])).toContain('2031-03-11')
  expect(capitalHistoryTooltip(samples[0])).toContain('2031-03-12')
  expect(capitalHistoryTooltip(samples[0])).toContain('实际估值')
  expect(capitalHistoryTooltip(samples[0])).toContain('保存观察')
  expect(capitalHistoryTooltip(samples[1])).toContain('当日没有保存观察')
})

test('a daily window with no capital facts contains only presentation gaps', () => {
  const values = capitalHistorySamples({ sampling: 'daily', window_start: '2031-03-12T00:00:00+08:00', window_end: '2031-03-13T08:00:00+08:00', points: [] } as unknown as StrategyCapitalHistory)
  expect(values).toHaveLength(2)
  expect(values.every(value => value.point === null && value.returnValue === null && value.drawdown === null)).toBe(true)
})

test('snapshot labels retain intraday times and add dates when valuations cross days', () => {
  const first = { ...point('2031-03-12T02:00:00Z'), valuation_at: '2031-03-12T01:30:00Z' }
  const second = { ...first, valuation_at: '2031-03-12T01:45:00Z' }
  const values = capitalHistorySamples({ points: [first, second] } as StrategyCapitalHistory)
  expect(values.map(value => value.label)).toEqual(['09:30', '09:45'])
  const crossDay = capitalHistorySamples({ points: [first, { ...second, valuation_at: '2031-03-13T01:45:00Z' }] } as StrategyCapitalHistory)
  expect(crossDay[0].label).toContain('2031-03-12')
  expect(crossDay[1].label).toContain('2031-03-13')
})

test('zero-only and single observations use display bounds without altering values', () => {
  expect(zeroObservationRange([null, 0], true)).toEqual({ min: -.001, max: 0 })
  expect(zeroObservationRange([0])).toEqual({ min: -.001, max: .001 })
  expect(zeroObservationRange([null, -.02], true)).toEqual({})
  expect(zeroObservationRange([null], true)).toEqual({})
})
