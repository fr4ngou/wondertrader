import { afterEach, expect, it, vi } from 'vitest'
import { fetchReadJson } from '../api'
import { fetchBacktestDay } from './backtestApi'
import { validatePerformance } from './backtestPerformanceApi'
import { PER_DATE_REPORT_SCHEMA, PER_DATE_SCOPE } from './backtestRetained'
import fixture from './backtest-per-date.fixture.json'

vi.mock('../api', () => ({ fetchReadJson: vi.fn() }))
afterEach(() => vi.resetAllMocks())

// 身份为传输测试上下文；资金/持仓/逐日窗口来自B冻结原生报告，不授归档资格。
const read = (value: typeof fixture.days[number]) => fetchBacktestDay('a'.repeat(32), value.request_id,
  value.index, undefined, value.report_sha256, value.record.trading_date)

it('逐日复权原报告的五种实际阶段保留资金、持仓、目标及当日模型', async () => {
  expect(new Set(fixture.days.map(day => day.record.status)).size).toBe(5)
  for (const day of fixture.days) {
    vi.mocked(fetchReadJson).mockResolvedValue(day)
    const parsed = await read(day)
    expect(parsed.report_schema).toBe(PER_DATE_REPORT_SCHEMA)
    expect(parsed.record.capture).toEqual(day.record.capture)
    expect(parsed.evaluation_summary).toEqual(day.evaluation_summary)
  }
  const performance = validatePerformance(fixture.performance, fixture.entry)
  expect(performance.scope).toBe(PER_DATE_SCOPE)
  expect(performance.points).toHaveLength(400)
})

it.each(['date', 'factor', 'received', 'known', 'manifest', 'missing-window', 'wrong-family'])('拒绝逐日来源%s错配', async kind => {
  const value = structuredClone(fixture.days.find(day => day.evaluation_summary !== null)!)
  const window = value.record.market_window
  if (kind === 'date') window.basis_date = '2099-01-01'
  if (kind === 'factor') window.factor_revision = '0'.repeat(64)
  if (kind === 'received') window.received_at = '2027-01-01T00:00:00Z'
  if (kind === 'known') window.known_at = '2027-01-01T00:00:00Z'
  if (kind === 'manifest') window.manifest_sha256 = 'bad-hash'
  if (kind === 'missing-window') Reflect.deleteProperty(value.record, 'market_window')
  if (kind === 'wrong-family') value.report_schema = 'guanheng.retained-replay-report.v1'
  vi.mocked(fetchReadJson).mockResolvedValue(value)
  await expect(read(value)).rejects.toThrow('格式或身份无效')
})

it('报告族与模型范围绑定，缺失逐日身份保持不可读取', () => {
  expect(() => validatePerformance({ ...fixture.performance, scope: 'RT-qualified' }, fixture.entry)).toThrow()
  expect(() => validatePerformance({ ...fixture.performance, report_schema: 'guanheng.retained-replay-report.v1' }, fixture.entry)).toThrow()
})

it.each(['missing-positive', 'foreign', 'wrong-zero'])('原生稀疏目标仍拒绝%s读回', async kind => {
  const value = structuredClone(fixture.days.find(day => day.record.status === 'buying')!) as typeof fixture.days[number] & {
    record: { readback: (string | number)[][] }
  }
  if (kind === 'missing-positive') value.record.readback = []
  if (kind === 'foreign') value.record.readback.push(['SSE.ETF.999999', 0])
  if (kind === 'wrong-zero') value.record.readback.push(['SSE.ETF.510300', 100])
  vi.mocked(fetchReadJson).mockResolvedValue(value)
  await expect(read(value)).rejects.toThrow('格式或身份无效')
})
