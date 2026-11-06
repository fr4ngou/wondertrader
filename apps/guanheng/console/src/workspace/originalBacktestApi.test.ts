import { afterEach, expect, it, vi } from 'vitest'
import { fetchReadJson } from '../api'
import { fetchBacktestArchiveSummaries } from './backtestApi'
import { fetchOriginalLedger, fetchOriginalPerformance, fetchOriginalSignals, ORIGINAL_STRATEGY, validateOriginalEntry, type OriginalArchiveEntry } from './originalBacktestApi'

vi.mock('../api', () => ({ fetchReadJson: vi.fn() }))
afterEach(() => vi.resetAllMocks())
// 合成三日期原件形态：归一化初值1，与人民币/WT命令身份保持明确边界。
const entry: OriginalArchiveEntry = { report_family: 'resonance-original', run_id: 'a'.repeat(32), record_count: 3,
  report_sha256: 'b'.repeat(64), receipt_sha256: 'c'.repeat(64), scope: 'original-stable-research',
  configuration: { label: '合成原版样本', name: 'original', start: 202401020000, end: 202401042359, session_sha256: 'd'.repeat(64), max_seconds: 30 },
  summary: { report_family: 'resonance-original', strategy: { id: ORIGINAL_STRATEGY, version: '0.1.0a1' }, unit: 'normalized-equity', initial_equity: 1 } }
const identity = { run_id: entry.run_id, receipt_sha256: entry.receipt_sha256, report_sha256: entry.report_sha256 }
const performance = { ...identity, schema: 'orr-performance-v1', strategy: { id: ORIGINAL_STRATEGY, version: '0.1.0a1', algorithm_id: ORIGINAL_STRATEGY },
  configuration: entry.configuration, unit: 'normalized-equity', metrics: { initial_equity: 1, last_equity: 1.05, total_return_pct: 5, observed_max_drawdown_pct: 5, fees: 0 },
  observations: { total: 3, available: 3, missing: 0, last_trading_date: 20240104 }, points: [[20240102, 1], [20240103, 0.95], [20240104, 1.05]],
  model: { execution: 'next-trading-day-close' }, source: {}, data_kind: 'synthetic-test', input_sha256: 'd'.repeat(64), source_manifest_sha256: 'e'.repeat(64),
  execution_qualified: false, point_in_time_qualified: false, scope: entry.scope }

it('轻量目录按独立family读取原版权益，不要求虚构WT owner/request', async () => {
  vi.mocked(fetchReadJson).mockResolvedValue({ schema: 'nbw-archive-summary-index-v1', runs: [entry], invalid_receipts: 0, unarchived_runs: 0, scope: entry.scope })
  expect((await fetchBacktestArchiveSummaries()).runs).toEqual([entry])
  expect(validateOriginalEntry(entry as unknown as Record<string, unknown>, true)).toBe(entry)
  expect(() => validateOriginalEntry({ ...entry, owner_id: 'f'.repeat(32) }, true)).toThrow()
  expect(() => validateOriginalEntry({ ...entry, summary: { ...entry.summary, initial_capital_cny: '1' } }, true)).toThrow()
})

it('绩效保持归一化小数，拒绝报告切换串值和数量覆盖失真', async () => {
  vi.mocked(fetchReadJson).mockResolvedValue(performance)
  expect((await fetchOriginalPerformance(entry)).metrics.last_equity).toBe(1.05)
  for (const change of [{ receipt_sha256: 'f'.repeat(64) }, { unit: 'CNY' }, { points: [[20240102, 1], [20240102, 0.95], [20240104, 1.05]] },
    { observations: { ...performance.observations, available: 2 } }, { execution_qualified: true }]) {
    vi.mocked(fetchReadJson).mockResolvedValue({ ...performance, ...change })
    await expect(fetchOriginalPerformance(entry)).rejects.toThrow()
  }
})

it('原信号与次日模拟调仓独立分页，保留原因和模型量', async () => {
  const ledger = { ...identity, schema: 'orr-ledger-v1', unit: 'normalized-equity', date: 20240103, offset: 0, total: 1,
    positions_available: false, positions: [], trades_available: true,
    trades: [{ index: 0, date: 20240103, signal_date: 20240102, symbol: '510300', side: 'buy', action: 'BUY', price: 2, amount: 1, quantity: 0.5, fee: 0, weight_pct: 100, reason: '' }] }
  vi.mocked(fetchReadJson).mockResolvedValue(ledger)
  expect((await fetchOriginalLedger(entry, 20240103, 0)).trades[0].quantity).toBe(0.5)
  const signals = { ...identity, schema: 'orr-signals-v1', date: 20240102, offset: 0, total: 1, scope: entry.scope,
    signals: [{ index: 0, date: 20240102, symbol: '510300', action: 'BUY', price: 1.9, reason: '合成低位信号' }] }
  vi.mocked(fetchReadJson).mockResolvedValue(signals)
  expect((await fetchOriginalSignals(entry, 20240102, 0)).signals[0].price).toBe(1.9)
  const longReason = '合成原算法理由'.repeat(180)
  vi.mocked(fetchReadJson).mockResolvedValue({ ...signals, signals: [{ ...signals.signals[0], reason: longReason }] })
  expect((await fetchOriginalSignals(entry, 20240102, 0)).signals[0].reason).toBe(longReason)
  vi.mocked(fetchReadJson).mockResolvedValue({ ...signals, signals: [{ ...signals.signals[0], reason: '长'.repeat(2049) }] })
  await expect(fetchOriginalSignals(entry, 20240102, 0)).rejects.toThrow()
  vi.mocked(fetchReadJson).mockResolvedValue({ ...signals, signals: [{ ...signals.signals[0], action: 'REFILL' }] })
  await expect(fetchOriginalSignals(entry, 20240102, 0)).rejects.toThrow()
  vi.mocked(fetchReadJson).mockResolvedValue({ ...ledger, trades: [{ ...ledger.trades[0], signal_date: 20240103 }] })
  await expect(fetchOriginalLedger(entry, 20240103, 0)).rejects.toThrow()
})
