import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import OriginalBacktests from './OriginalBacktests'
import * as api from './originalBacktestApi'

vi.mock('./originalBacktestApi', async original => ({ ...await original<typeof import('./originalBacktestApi')>(),
  fetchOriginalPerformance: vi.fn(), fetchOriginalVisuals: vi.fn(), fetchOriginalLedger: vi.fn(), fetchOriginalSignals: vi.fn() }))
vi.mock('./BacktestVisualChart', () => ({ reportDate: (n: number) => String(n), reportPct: (n: number) => n + '%',
  default: ({ onDay }: { onDay: (n: number) => void }) => <button onClick={() => onDay(20230103)}>点选仅对比日期</button> }))
const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(c => c.clear()); vi.resetAllMocks() })
const entry: api.OriginalArchiveEntry = { report_family: 'resonance-original', run_id: 'a'.repeat(32), record_count: 2, report_sha256: 'b'.repeat(64), receipt_sha256: 'c'.repeat(64), scope: 'synthetic-original',
  configuration: { name: 'original', label: '合成主报告', start: 202401020000, end: 202401032359, session_sha256: 'd'.repeat(64), max_seconds: 30 } }
const other = { ...entry, run_id: 'f'.repeat(32), configuration: { ...entry.configuration, label: '合成对比报告', start: 202301020000, end: 202301032359 } }
const report = { schema: 'orr-performance-v1', strategy: { id: api.ORIGINAL_STRATEGY, version: '0.1.0a1', algorithm_id: api.ORIGINAL_STRATEGY }, unit: 'normalized-equity',
  configuration: entry.configuration, metrics: { initial_equity: 1, last_equity: 1.01, total_return_pct: 1, observed_max_drawdown_pct: 0, fees: 0 },
  observations: { total: 2, available: 2, missing: 0, last_trading_date: 20240103 }, points: [[20240102, 1], [20240103, 1.01]],
  data_kind: 'synthetic-test', source: {}, model: {}, input_sha256: 'd'.repeat(64), source_manifest_sha256: 'e'.repeat(64), scope: 'synthetic-original', execution_qualified: false, point_in_time_qualified: false }

test('仅对比报告覆盖的日期保持主明细选择，不向主报告发送越界日期', async () => {
  vi.mocked(api.fetchOriginalPerformance).mockImplementation(async e => ({ ...report, run_id: e.run_id, receipt_sha256: e.receipt_sha256, report_sha256: e.report_sha256,
    points: e === entry ? report.points : [[20230102, 1], [20230103, 1.01]], configuration: e.configuration } as api.OriginalPerformance))
  vi.mocked(api.fetchOriginalVisuals).mockResolvedValue({ schema: 'orr-visuals-v1', points: [], trades_available: true } as unknown as api.OriginalVisuals)
  vi.mocked(api.fetchOriginalLedger).mockResolvedValue({ schema: 'orr-ledger-v1', date: null, offset: 0, total: 0, trades: [], trades_available: true } as unknown as api.OriginalLedger)
  vi.mocked(api.fetchOriginalSignals).mockResolvedValue({ schema: 'orr-signals-v1', date: null, offset: 0, total: 0, signals: [] } as unknown as api.OriginalSignals)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client)
  render(<QueryClientProvider client={client}><OriginalBacktests entries={[entry, other]} runId={entry.run_id} compareId={other.run_id} onOpen={vi.fn()} /></QueryClientProvider>)
  await screen.findByRole('heading', { name: '组合模拟调仓' })
  await waitFor(() => expect(api.fetchOriginalLedger).toHaveBeenCalledTimes(1))
  fireEvent.click(screen.getByRole('button', { name: '点选仅对比日期' }))
  expect(await screen.findByText(/仅在对比报告中，当前仍显示主报告明细/)).toBeVisible()
  expect(api.fetchOriginalLedger).toHaveBeenCalledTimes(1)
  expect(api.fetchOriginalSignals).toHaveBeenCalledTimes(1)
  expect(vi.mocked(api.fetchOriginalLedger).mock.calls.every(call => call[1] === null)).toBe(true)
})
