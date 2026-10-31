import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import BacktestWorkspace from './BacktestWorkspace'
import * as api from './backtestApi'
import day from './backtest-day.fixture.json'

vi.mock('./backtestApi', () => ({ fetchBacktestWorkspace: vi.fn(), commandBacktest: vi.fn(), fetchBacktestRecords: vi.fn(), fetchBacktestDay: vi.fn(), fetchBacktestArchive: vi.fn(), fetchArchiveConfiguration: vi.fn() }))
afterEach(() => { cleanup(); vi.resetAllMocks() })
beforeEach(() => { vi.mocked(api.fetchBacktestArchive).mockResolvedValue({ schema: 'nbw-archive-index-v1', runs: [], invalid_receipts: 0, unarchived_runs: 0, scope: 'isolated-raw-BT' }) })
const base = { schema: 'nbw-workspace-v1' as const, owner_id: 'a'.repeat(32), available: true, reason: null,
  configuration: { label: '合成验证样本', start: 202401030930, end: 202401091500, session_sha256: 'c'.repeat(64), max_seconds: 30 }, runs: [] as api.BacktestRun[], scope: 'isolated-raw-BT' }
const run: api.BacktestRun = { owner_id: base.owner_id, request_id: '1'.repeat(32), run_id: 'b'.repeat(32), status: 'completed', reason: '原生回测完成',
  elapsed_ms: 500, pid: 123, exit_code: 0, forced: false, pid_reaped: true, pipes_joined: true, record_count: 5, scope: 'isolated-raw-BT' }
function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/strategies?tab=backtests']}><BacktestWorkspace /></MemoryRouter></QueryClientProvider>)
}

it('只读历史报告页面没有启动取消保存入口，也不读取Web运行工作区', async () => {
  show()
  expect(await screen.findByText('尚无已保存的回测报告。')).toBeVisible()
  expect(screen.queryByRole('button', {name:/启动回测|取消当前回测|保存报告/})).not.toBeInTheDocument()
  expect(api.fetchBacktestWorkspace).not.toHaveBeenCalled()
  expect(api.commandBacktest).not.toHaveBeenCalled()
})

it('新进程无本轮运行也能只读历史冻结配置与原报告', async () => {
  const entry: api.ArchiveEntry = { run_id: 'b'.repeat(32), owner_id: 'f'.repeat(32), request_id: '2'.repeat(32), record_count: 5,
    report_sha256: 'c'.repeat(64), receipt_sha256: 'd'.repeat(64), scope: run.scope, configuration: { ...base.configuration, name: 'configured' } }
  vi.mocked(api.fetchBacktestArchive).mockResolvedValue({ schema: 'nbw-archive-index-v1', runs: [entry], invalid_receipts: 0, unarchived_runs: 1, scope: run.scope })
  vi.mocked(api.fetchArchiveConfiguration).mockResolvedValue({ schema: 'nbw-archive-configuration-v1', run_id: entry.run_id, request_id: entry.request_id,
    receipt_sha256: entry.receipt_sha256, report_sha256: entry.report_sha256, installation_sha256: 'e'.repeat(64), configuration: entry.configuration,
    session_configuration: { strategy: 'synthetic' }, policy: {}, fee_reserve_cny: '0', fee_source: 'synthetic', scope: run.scope })
  vi.mocked(api.fetchBacktestRecords).mockResolvedValue({ request_id: entry.request_id, report_sha256: entry.report_sha256, total: 5, offset: 0,
    records: [{ trading_date: 20240109, minute: 1500, status: 'ready', reason: '完成' }], scope: run.scope })
  vi.mocked(api.fetchBacktestDay).mockResolvedValue({ ...day, request_id: entry.request_id, index: 0 } as api.BacktestDay)
  show()
  await fireEvent.click(await screen.findByRole('button', { name: '查看历史 2024-01-09' }))
  expect(await screen.findByRole('heading', { name: '2024-01-09 · 当日结果' })).toBeVisible()
  expect(api.commandBacktest).not.toHaveBeenCalled()
  expect(api.fetchBacktestDay).toHaveBeenCalledWith(entry.owner_id, entry.request_id, 0, expect.any(AbortSignal), entry.report_sha256, 20240109,
    { runId: entry.run_id, receiptSha: entry.receipt_sha256, reportSha: entry.report_sha256 })
})
