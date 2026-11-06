import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import LiveStrategyPerformance from './LiveStrategyPerformance'
import type { LivePerformance } from './liveStrategyApi'

const chart = vi.hoisted(() => ({ formatter: undefined as undefined | ((input: unknown) => string) }))
vi.mock('echarts/core', () => ({ use: vi.fn(), init: () => ({ setOption: (option: {tooltip:{formatter:(input:unknown)=>string}}) => {chart.formatter=option.tooltip.formatter}, getZr: () => ({ on: vi.fn() }), resize: vi.fn(), dispose: vi.fn() }) }))
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

test('历史成交日缺持仓不沿用今天持仓，完整无成交与未知分别说明', () => {
  render(<LiveStrategyPerformance data={data} />)
  fireEvent.change(screen.getByLabelText('观察日期'), { target: { value: '2026-01-02' } })
  expect(screen.queryByText('10:00:00')).toBeNull()
  expect(screen.getAllByText('该日没有持仓观测。').length).toBeGreaterThan(0)
  expect(screen.getAllByText('当日完整查询无成交。').length).toBeGreaterThan(0)
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
