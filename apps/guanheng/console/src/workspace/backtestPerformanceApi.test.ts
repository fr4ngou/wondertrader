import { afterEach, expect, test, vi } from 'vitest'
import { fetchBacktestComparison, fetchBacktestPerformance, validatePerformance } from './backtestPerformanceApi'
import fixture from './backtest-performance.fixture.json'

afterEach(() => vi.unstubAllGlobals())
test.each(['0.1.0a1','0.1.0a2'])('同族原版WT绩效按已验版本读取：%s', version => {
  const value={...structuredClone(fixture.left),report_schema:'guanheng.original-native-replay-report.v1',
    strategy:{id:'resonance-original-wt-351f9d5-stable',version,algorithm_id:'resonance-original-351f9d5-stable'},
    metrics:{...fixture.left.metrics,initial_capital_cny:'1000000'}}
  const entry={...fixture.left_entry,summary:{strategy:{id:value.strategy.id,version},initial_capital_cny:'1000000'}}
  expect(validatePerformance(value,entry).strategy.version).toBe(version)
  expect(()=>validatePerformance({...value,strategy:{...value.strategy,version:'0.1.0a999'}},entry)).toThrow()
})
test('完整绩效继续匹配轻量目录的原策略版本及本金',()=>{
  const summary={strategy:{id:fixture.left.strategy.id,version:fixture.left.strategy.version},initial_capital_cny:fixture.left.metrics.initial_capital_cny}
  expect(validatePerformance(fixture.left,{...fixture.left_entry,summary})).toEqual(fixture.left)
  expect(()=>validatePerformance(fixture.left,{...fixture.left_entry,summary:{...summary,strategy:{...summary.strategy,version:'wrong'}}})).toThrow('格式或身份无效')
  expect(()=>validatePerformance(fixture.left,{...fixture.left_entry,summary:{...summary,initial_capital_cny:'2'}})).toThrow('格式或身份无效')
})
test('原生两族投影及原文件/规范会话不同摘要均保留，比较请求只读绑定双方receipt', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(Response.json(fixture.left)).mockResolvedValueOnce(Response.json(fixture.comparison))
  vi.stubGlobal('fetch', fetch)
  expect(await fetchBacktestPerformance(fixture.left_entry)).toEqual(fixture.left)
  expect(await fetchBacktestComparison(fixture.left_entry, fixture.right_entry)).toEqual(fixture.comparison)
  expect(String(fetch.mock.calls[0][0])).toContain(fixture.left_entry.receipt_sha256)
  expect(String(fetch.mock.calls[1][0])).toContain(fixture.right_entry.receipt_sha256)
  expect(fetch.mock.calls.every(call => (call[1]?.method ?? 'GET') === 'GET')).toBe(true)
})
test.each(['identity', 'extra', 'date', 'duplicate', 'count', 'fees', 'infinite', 'unavailable', 'last'])('拒绝无效绩效：%s', mutation => {
  const value = structuredClone(fixture.left) as Record<string, any>
  if (mutation === 'identity') value.report_sha256 = 'f'.repeat(64)
  if (mutation === 'extra') value.runtime_ready = true
  if (mutation === 'date') value.points[0][0] = 20240230
  if (mutation === 'duplicate') value.points[1][0] = value.points[0][0]
  if (mutation === 'count') value.observations.available++
  if (mutation === 'fees') value.metrics.native_cumulative_fees_cny = '-1'
  if (mutation === 'infinite') value.metrics.total_return_pct = Infinity
  if (mutation === 'unavailable') { value.points = value.points.map(([day]: [number]) => [day, null]); value.observations = {total: 5, available: 0, missing: 5, last_trading_date: null}; value.metrics.last_nav_cny = null }
  if (mutation === 'last') value.metrics.last_nav_cny = '12'
  expect(() => validatePerformance(value, fixture.left_entry)).toThrow('回测数据格式或身份无效')
})
test.each([['unknown'], ['strategy', 'window'], ['window', 'window']])('拒绝未知、重复或无序差异', async (...differences) => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({...fixture.comparison, differences})))
  await expect(fetchBacktestComparison(fixture.left_entry, fixture.right_entry)).rejects.toThrow('回测数据格式或身份无效')
})
test('拒绝选择相同运行，失败期间沿HTTP错误退出', async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json({}, {status: 503})); vi.stubGlobal('fetch', fetch)
  await expect(fetchBacktestComparison(fixture.left_entry, fixture.left_entry)).rejects.toThrow()
  expect(fetch).not.toHaveBeenCalled()
  await expect(fetchBacktestPerformance(fixture.left_entry)).rejects.toThrow('回测绩效读取失败')
})
