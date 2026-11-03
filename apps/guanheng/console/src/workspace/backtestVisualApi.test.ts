import { afterEach, expect, test, vi } from 'vitest'
import { fetchBacktestReadJson } from './backtestApi'
import { fetchLedger, fetchVisuals } from './backtestVisualApi'
import fixture from './backtest-performance.fixture.json'

vi.mock('./backtestApi', async original => ({ ...await original<typeof import('./backtestApi')>(), fetchBacktestReadJson:vi.fn() }))
afterEach(() => vi.resetAllMocks())
const entry = fixture.left_entry
function visual() { return { schema:'nbw-visuals-v1', run_id:entry.run_id, receipt_sha256:entry.receipt_sha256, report_sha256:entry.report_sha256,
  trades_available:false, points:Array.from({length:entry.record_count},(_,i)=>[20240102+i,null,null,0,0,0]) } }
test('未知成交与未知日收益正常保留，不要求填零', async () => {
  vi.mocked(fetchBacktestReadJson).mockResolvedValueOnce(visual())
  const result = await fetchVisuals(entry)
  expect(result.trades_available).toBe(false); expect(result.points[0][1]).toBeNull()
})
test.each(['identity','duplicate-day','extra-field'])('图表拒绝%s损坏的响应', async fault => {
  const value = visual()
  if (fault === 'identity') value.receipt_sha256 = 'f'.repeat(64)
  if (fault === 'duplicate-day') value.points[1][0] = value.points[0][0]
  if (fault === 'extra-field') Object.assign(value,{unexpected:true})
  vi.mocked(fetchBacktestReadJson).mockResolvedValueOnce(value)
  await expect(fetchVisuals(entry)).rejects.toThrow()
})
test('日期明细绑定查询日期与报告，错日拒绝', async () => {
  const value = { schema:'nbw-ledger-v1', run_id:entry.run_id, receipt_sha256:entry.receipt_sha256, report_sha256:entry.report_sha256,
    date:20240104, positions_available:false,positions:[],trades_available:true,total:0,offset:0,trades:[] }
  vi.mocked(fetchBacktestReadJson).mockResolvedValueOnce(value)
  await expect(fetchLedger(entry,20240103,0)).rejects.toThrow()
})
