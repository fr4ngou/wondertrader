import { afterEach, expect, test, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import LiveStrategyPerformance from './LiveStrategyPerformance'
import { validateLivePerformance } from './liveStrategyApi'
import type { LivePerformance } from './liveStrategyApi'

const chart = vi.hoisted(() => ({
  formatter: undefined as undefined | ((input: unknown) => string),
  events: new Map<string, (event: { offsetX: number; offsetY: number }) => void>(),
}))
vi.mock('echarts/core', () => ({
  use: vi.fn(),
  init: () => ({
    setOption: (option: { tooltip: { formatter: (input: unknown) => string } }) => {
      chart.formatter = option.tooltip.formatter
    },
    getZr: () => ({
      on: (name: string, handler: (event: { offsetX: number; offsetY: number }) => void) => chart.events.set(name, handler),
    }),
    containPixel: () => true,
    convertFromPixel: () => 0,
    resize: vi.fn(),
    dispose: vi.fn(),
  }),
}))
afterEach(cleanup)
const data = { schema_version: 'guanheng.live-strategy-performance.v1', read_only: true, observed_at: '2026-01-05T08:00:00Z', state: 'available', reason: '实际发布观察。',
  requested: { strategy_id: 'sample', strategy_version: '1' }, current: { strategy_id: 'sample', strategy_version: '1', key_matches: true, is_current: true, scope_id: 'a'.repeat(64), runtime_state: 'ready', process_state: 'alive' },
  coverage: { from: '2026-01-05', to: '2026-01-05', point_count: 1, basis: 'actual-published-observations', history_state: 'app-published-observation-history', reason: '仅真实观察，不补历史。', deals_truncated: false },
  baseline: { total_cny: '1000000', baseline_at: '2026-01-05T00:00:00Z', scope_id: 'b'.repeat(64) },
  summary: { nav_cny: '1000100', pnl_cny: '100', return_pct: null, observed_at: '2026-01-05T08:00:00Z', price_observed_at: null, pnl_source: 'broker-cash-delta', return_reason: '资金流归因未齐。' },
  daily: [{ date: '2026-01-02', observed_at: null, nav_cny: null, cash_cny: null, market_value_cny: null, pnl_cny: null, return_pct: null, positions: [], deals: [], positions_state: 'unavailable', deals_state: 'empty' },
    { date: '2026-01-05', observed_at: '2026-01-05T08:00:00Z', nav_cny: '1000100', cash_cny: '999100', market_value_cny: '1000', pnl_cny: '100', return_pct: null,
      positions: [{ symbol: '510300.SH', quantity: 100, sellable: 0, observed_at: '2026-01-05T08:00:00Z' }],
      deals: [{ id: 'synthetic', date: '2026-01-05', time: '10:00:00', symbol: '510300.SH', side: 'BUY', price_cny: '10', quantity: 100, amount_cny: '1000', attribution: 'account-universe-only' }], positions_state: 'available', deals_state: 'available' }], markers: [] } as LivePerformance

test('默认直接展示当日持仓成交，未合格收益率与单点历史不伪造为零', () => {
  render(<LiveStrategyPerformance data={data} />)
  expect(screen.getByRole('region', { name: '2026-01-05每日持仓和成交' })).toBeVisible()
  expect(screen.getByText('10:00:00')).toBeVisible()
  expect(screen.getByText('投资收益率').parentElement).toHaveTextContent('口径待核实')
  expect(screen.getByText(/当前只有 1 个实际净值点/)).toBeVisible()
  expect(screen.getByText(/策略归属尚未确认/)).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '展开详细信息' }))
  expect(screen.getByRole('columnheader', { name: '金额（元）' })).toBeVisible()
})

test('摘要按同日证券及方向合计，左侧仍保留各笔原明细', () => {
  const original = data.daily[1].deals[0]
  const observation: LivePerformance = { ...data, daily: [data.daily[0], {
    ...data.daily[1], deals_state: 'partial', deals: [
      original, { ...original, id: 'buy2', quantity: 250, time: '10:00:01' },
      { ...original, id: 'sell', side: 'SELL', quantity: 50, time: '10:00:02' },
      { ...original, id: 'unknown', side: 'UNKNOWN', quantity: 10, time: '10:00:03' },
    ],
  }] }
  render(<LiveStrategyPerformance data={observation} />)
  const summary = within(screen.getByRole('region', { name: '当日汇总' }))
  expect(summary.getByText('账户范围成交')).toBeVisible()
  expect(summary.getByText('4 笔')).toBeVisible()
  expect(summary.getByText('350 份 · 2 笔').parentElement).toHaveTextContent('买入')
  expect(summary.getByText('50 份 · 1 笔').parentElement).toHaveTextContent('卖出')
  expect(summary.getByText('10 份 · 1 笔').parentElement).toHaveTextContent('方向未确认')
  expect(summary.getByText('汇总仅含已取得的成交。')).toBeVisible()
  expect(summary.queryByText('10:00:01')).toBeNull()
  const details = within(screen.getByRole('region', { name: '2026-01-05每日持仓和成交' }))
  expect(details.getByText('10:00:01')).toBeVisible()
  expect(details.getByText('归属未确认')).toBeVisible()
})

test('悬停只换摘要，点击才固定当日明细', () => {
  render(<LiveStrategyPerformance data={data} />)
  const summary = within(screen.getByRole('region', { name: '当日汇总' }))
  const event = { offsetX: 10, offsetY: 10 }
  act(() => chart.events.get('mousemove')?.(event))
  expect(summary.getByText('2026-01-02')).toBeVisible()
  expect(summary.getByText('悬停预览')).toBeVisible()
  expect(screen.getByRole('region', { name: '2026-01-05每日持仓和成交' })).toBeVisible()
  act(() => chart.events.get('click')?.(event))
  expect(summary.getByText('所选日期')).toBeVisible()
  expect(screen.getByRole('region', { name: '2026-01-02每日持仓和成交' })).toBeVisible()
})

test('历史成交日缺持仓不沿用今天持仓，完整无成交与未知分别说明', () => {
  render(<LiveStrategyPerformance data={data} />)
  fireEvent.change(screen.getByLabelText('观察日期'), { target: { value: '2026-01-02' } })
  expect(screen.queryByText('10:00:00')).toBeNull()
  expect(screen.getAllByText('该日没有持仓观测。').length).toBeGreaterThan(0)
  expect(screen.getAllByText('当日完整查询无成交。').length).toBeGreaterThan(0)
})

test('展示已核收益率、追加和提取，并拒绝过期覆盖', () => {
  const end = '2026-01-05T08:00:00Z'
  const observation = { ...data, summary: {
    ...data.summary!, valuation_state: 'actual' as const, pnl_cny: null,
    pnl_source: 'previous-verified-valuation', return_pct: '21', capital_return: {
    baseline_at: data.baseline!.baseline_at, valued_at: end, valuation_nav_cny: '1000100',
    cash_observed_at: end, coverage_required_at: end,
    inflow_through: end, outflow_through: end, flow_count: 2, state: 'available', return_pct: '21', reason: '已核对资金进出。',
    flows: [
      { id: '1'.repeat(64), direction: 'inflow' as const, amount_cny: '500000', effective_at: '2026-01-05T04:00:00Z' },
      { id: '2'.repeat(64), direction: 'outflow' as const, amount_cny: '200000', effective_at: '2026-01-05T06:00:00Z' },
    ],
  } } }
  render(<LiveStrategyPerformance data={validateLivePerformance(observation, 'sample', '1')} />)
  expect(screen.getByText('投资收益率').parentElement).toHaveTextContent('21%')
  expect(screen.getByText(/上次已核净值时间.*收益估值截止/)).toBeVisible()
  const details = screen.getByText('策略资金进出（2 笔）').parentElement as HTMLDetailsElement
  details.open = true
  expect(within(details).getByText('追加', { exact: true })).toBeVisible()
  expect(within(details).getByText('提取', { exact: true })).toBeVisible()
  observation.summary.capital_return.coverage_required_at = '2026-01-05T08:01:00Z'
  expect(() => validateLivePerformance(observation, 'sample', '1')).toThrow('线上策略观察格式无效')
})

test('持仓只数正仓位，持仓和成交使用目录名称及原持仓时间', () => {
  const observation = { ...data, security_names: { '510300.SH': '华泰柏瑞沪深300ETF', '510050.SH': '华夏上证50ETF' },
    daily: data.daily.map(day => day.date === '2026-01-05' ? { ...day,
      positions_observed_at: '2026-01-05T07:59:12Z',
      positions: [...day.positions, { ...day.positions[0], symbol: '510050.SH', quantity: 0 }],
    } : day),
  }
  render(<LiveStrategyPerformance data={observation} />)
  const details = within(screen.getByRole('region', { name: '2026-01-05每日持仓和成交' }))
  expect(details.getAllByText(/华泰柏瑞沪深300ETF/)).toHaveLength(2)
  expect(details.getAllByText('510300.SH')).toHaveLength(2)
  expect(details.getByText(/持仓观察时间.*15:59:12/)).toBeVisible()
  expect(details.getByText('策略证券范围内的账户持仓')).toBeVisible()
  expect(screen.queryByText('510050.SH')).toBeNull()
  expect(screen.getByText('持仓 1 项')).toBeVisible()
})

test('净值和成交笔数相同时新持仓观察仍及时进入悬停摘要', () => {
  const prior = { ...data, daily: data.daily.map((d, i) => i === 1 ? { ...d, positions: [], positions_state: 'unavailable' as const } : d) }
  const view = render(<LiveStrategyPerformance data={prior} />)
  const formatter = chart.formatter!
  expect(formatter([{dataIndex:1}])).toContain('持仓尚无观测')
  view.rerender(<LiveStrategyPerformance data={data} />)
  expect(chart.formatter).toBe(formatter)
  expect(formatter([{dataIndex:1}])).toContain('持仓 1 项')
})
