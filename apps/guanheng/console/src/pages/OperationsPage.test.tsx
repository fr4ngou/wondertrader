import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'

import { fetchOperationsWorkbench } from '../api'
import type { ConsoleBootstrap, OperationsWorkbenchProjection } from '../types'
import { OperationsPage } from './OperationsPage'

vi.mock('../api', () => ({
  fetchOperationsWorkbench: vi.fn(),
  fetchOperationalErrorLogs: vi.fn(),
}))

const bootstrap = { overview: { operations: null, trading_operations: null } } as ConsoleBootstrap

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter><OperationsPage bootstrap={bootstrap} /></MemoryRouter>
    </QueryClientProvider>,
  )
  return client
}

function emptyWorkbench(observationAvailable: boolean): OperationsWorkbenchProjection {
  const generatedAt = new Date().toISOString()
  return {
    schema_version: '1.3', generated_at: generatedAt,
    database_migrations: {
      schema_version: '1.0', generated_at: generatedAt, observation_available: false,
      source_versions: [], applied_versions: [], missing_versions: [],
      unknown_applied_versions: [], checksum_mismatch_versions: [],
      contiguous: false, up_to_date: false, read_only: true, executable: false,
    },
    history_jobs: [], operation_policies: [], thresholds: [],
    conversation_receipts: [], conversation_receipt_invalid_count: 0,
    conversation_receipt_observation_available: observationAvailable,
    read_only: true,
  }
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

test('shows a pending state then only eight verified receipts', async () => {
  let complete!: (value: OperationsWorkbenchProjection) => void
  vi.mocked(fetchOperationsWorkbench).mockImplementation(() => new Promise((resolve) => { complete = resolve }))
  mount()

  expect(screen.getByText('正在读取对话任务回执')).toBeInTheDocument()
  expect(fetchOperationsWorkbench).toHaveBeenCalledWith(expect.any(AbortSignal), 8)

  complete({
    conversation_receipt_invalid_count: 0,
    conversation_receipts: Array.from({ length: 9 }, (_, index) => ({
      receipt_sha256: String(index).padStart(64, '0'), operation_id: 'diagnostic.read',
      summary_lines: [`任务 ${index}`], strategy: null, status: 'succeeded',
      completed_at: '2026-09-25T08:00:00Z', duration_ms: 100,
      total_return: null, maximum_drawdown: null, trade_count: null,
      content_verified: true, artifacts_verified: true,
    })),
  } as OperationsWorkbenchProjection)

  await waitFor(() => expect(document.querySelectorAll('.conversation-receipt-row')).toHaveLength(8))
  expect(screen.queryByText('正在读取对话任务回执')).not.toBeInTheDocument()
})

test.each(['request_failed', 'source_unavailable'] as const)('shows receipt source failure for %s', async (reason) => {
  if (reason === 'request_failed') {
    vi.mocked(fetchOperationsWorkbench).mockRejectedValue(new Error('运维权威投影读取超时'))
  } else {
    vi.mocked(fetchOperationsWorkbench).mockResolvedValue(emptyWorkbench(false))
  }
  mount()

  const card = screen.getByRole('heading', { name: '最近对话任务' }).closest('article')
  expect(card).not.toBeNull()
  const receipts = within(card!)
  expect(await receipts.findByText('对话任务回执不可用', {}, { timeout: 3_000 })).toBeInTheDocument()
  expect(receipts.getByText('回执目录或摘要索引当前不可读，请查看运行状态与错误日志。')).toBeInTheDocument()
  expect(receipts.queryByText('暂无对话任务回执')).not.toBeInTheDocument()
  expect(receipts.queryByText('正在读取对话任务回执')).not.toBeInTheDocument()
})

test('shows an empty receipt list only after an available observation', async () => {
  vi.mocked(fetchOperationsWorkbench).mockResolvedValue(emptyWorkbench(true))
  mount()

  const card = screen.getByRole('heading', { name: '最近对话任务' }).closest('article')
  expect(card).not.toBeNull()
  const receipts = within(card!)
  expect(await receipts.findByText('暂无对话任务回执')).toBeInTheDocument()
  expect(receipts.getByText('完成对话式回测或诊断后会显示在这里。')).toBeInTheDocument()
  expect(receipts.queryByText('对话任务回执不可用')).not.toBeInTheDocument()
  expect(receipts.queryByText('正在读取对话任务回执')).not.toBeInTheDocument()
})
