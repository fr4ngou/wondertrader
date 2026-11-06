import { expect, test } from 'vitest'
import { validateLivePerformance } from './liveStrategyApi'

const empty = () => ({ schema_version: 'guanheng.live-strategy-performance.v1', read_only: true,
  observed_at: '2026-01-05T08:00:00Z', state: 'not_current', reason: '所选身份与运行身份不符。',
  requested: { strategy_id: 'sample', strategy_version: '1' },
  current: { strategy_id: 'sample', strategy_version: '1', key_matches: false, is_current: false, runtime_state: null, scope_id: null, process_state: 'unknown' },
  coverage: { from: null, to: null, point_count: 0, basis: 'actual-published-observations', history_state: 'unavailable', reason: '尚无实际观察。', deals_truncated: false },
  baseline: null, summary: null, daily: [], markers: [] })

test('非当前选择保持无资金、无明细，切换身份不复用上一选择', () => {
  expect(validateLivePerformance(empty(), 'sample', '1').daily).toEqual([])
  expect(() => validateLivePerformance(empty(), 'other', '1')).toThrow('格式无效')
  expect(() => validateLivePerformance({ ...empty(), summary: { nav_cny: '1000000', pnl_cny: '0', return_pct: null, return_reason: '未知' } }, 'sample', '1')).toThrow()
})

test('在线标记需要同一版本和实际活进程，失败不冒充在线', () => {
  const value = empty()
  value.state = 'available'
  value.current.key_matches = true; value.current.is_current = true
  expect(() => validateLivePerformance(value, 'sample', '1')).toThrow()
  value.current.process_state = 'alive'
  expect(validateLivePerformance(value, 'sample', '1').current.is_current).toBe(true)
  value.current.strategy_version = '2'
  expect(() => validateLivePerformance(value, 'sample', '1')).toThrow()
})

test('未知净值和收益率保留空值；不同来源日期不得倒序或重复', () => {
  const day = { date: '2026-01-05', observed_at: null, nav_cny: null, cash_cny: null, market_value_cny: null, pnl_cny: null, return_pct: null,
    positions: [], deals: [], positions_state: 'unavailable', deals_state: 'unavailable' }
  const value = { ...empty(), state: 'available', daily: [day] }
  expect(validateLivePerformance(value, 'sample', '1').daily[0].nav_cny).toBeNull()
  expect(() => validateLivePerformance({ ...value, daily: [day, day] }, 'sample', '1')).toThrow()
  expect(() => validateLivePerformance({ ...value, daily: [{ ...day, return_pct: 0 }] }, 'sample', '1')).toThrow()
})
