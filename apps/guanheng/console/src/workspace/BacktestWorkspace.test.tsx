import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import BacktestWorkspace from './BacktestWorkspace'
import * as api from './backtestApi'
import fixture from './backtest-performance.fixture.json'

vi.mock('./backtestApi', async original => ({ ...await original<typeof api>(), fetchBacktestArchive: vi.fn() }))
vi.mock('./BacktestPerformance', () => ({ reportLabel: (entry: api.ArchiveEntry) => entry.configuration.label, reportKey:(entry: api.ArchiveEntry)=>entry.run_id+entry.receipt_sha256,
  default: ({ entry, mainSelector, onRefreshArchive }: { entry: api.ArchiveEntry; mainSelector: import('react').ReactNode; onRefreshArchive:()=>void }) => <div><h1>回测分析</h1>{mainSelector}<span>{entry.record_count}期</span><button onClick={onRefreshArchive}>刷新目录</button></div> }))
const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(c => c.clear()); vi.resetAllMocks() })
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client)
  render(<QueryClientProvider client={client}><BacktestWorkspace /></QueryClientProvider>)
}
test('独立入口空归档明确提示并提供刷新，保持只读', async () => {
  vi.mocked(api.fetchBacktestArchive).mockResolvedValue({ schema: 'nbw-archive-index-v1', runs: [], invalid_receipts: 0, unarchived_runs: 0, scope: 'isolated-raw-BT' })
  mount(); expect(await screen.findByText('尚无已保存的回测报告。')).toBeVisible()
  expect(screen.getByRole('button', { name: '刷新历史报告' })).toBeVisible()
  expect(screen.queryByRole('button', { name: /启动|取消|保存/ })).toBeNull()
})
test('目录默认选择截止日期最新报告，并保留真实归档选择器', async () => {
  const newer = { ...fixture.right_entry, configuration: { ...fixture.right_entry.configuration, end: 202611021500 } }
  vi.mocked(api.fetchBacktestArchive).mockResolvedValue({ schema: 'nbw-archive-index-v1', runs: [fixture.left_entry, newer], invalid_receipts: 0, unarchived_runs: 0, scope: 'isolated-raw-BT' })
  mount(); await screen.findByRole('heading', { name: '回测分析' })
  expect(screen.getByLabelText('选择历史回测')).toHaveValue(newer.run_id)
})

test('已有报告页面可刷新发现后续保存的报告，无需重新打开页面', async () => {
  const index = { schema:'nbw-archive-index-v1' as const,runs:[fixture.left_entry],invalid_receipts:0,unarchived_runs:0,scope:'isolated-raw-BT' }
  vi.mocked(api.fetchBacktestArchive).mockResolvedValueOnce(index).mockResolvedValueOnce({...index,runs:[fixture.left_entry,fixture.right_entry]})
  mount(); await screen.findByRole('heading',{name:'回测分析'})
  expect(screen.getAllByRole('option')).toHaveLength(1)
  fireEvent.click(screen.getByRole('button',{name:'刷新目录'}))
  await screen.findByRole('option',{name:fixture.right_entry.configuration.label})
  expect(screen.getAllByRole('option')).toHaveLength(2)
})
