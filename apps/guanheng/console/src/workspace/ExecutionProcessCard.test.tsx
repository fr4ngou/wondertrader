import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import OperationsWorkspace from './OperationsWorkspace'
import { executionProcessFixture, historyPreparationFixture, operationsFixture, sourceMarketFixture } from './operations.fixture'
const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.unstubAllGlobals() })
test('执行进程只读展示、失败隐藏旧观察及恢复；状态不授执行或恢复资格', async () => {
  let failed = false; const requests: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    expect(init?.method ?? 'GET').toBe('GET'); requests.push(String(input))
    if(String(input) === '/v1/ui/qmt-history-preparation') return Response.json(historyPreparationFixture)
    if(String(input) === '/v1/ui/execution-process') return failed ? Response.json({}, { status: 503 }) : Response.json({ ...executionProcessFixture,
      process: { ...executionProcessFixture.process, state: 'ready', label: '已启动', ready: true, pid: 123, pending: true } })
    return Response.json(String(input) === '/v1/ui/source-market' ? sourceMarketFixture : operationsFixture)
  }))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client)
  render(<QueryClientProvider client={client}><OperationsWorkspace /></QueryClientProvider>)
  expect(await screen.findByRole('region', { name: '策略执行进程' })).toHaveTextContent('已启动')
  expect(screen.getByRole('region', { name: '策略执行进程' })).toHaveTextContent('自动恢复尚未准入')
  failed = true; fireEvent.click(screen.getByRole('button', { name: '重新读取状态' }))
  expect(await screen.findByText(/策略执行进程状态读取失败/)).toBeVisible()
  expect(screen.getByRole('region', { name: '策略执行进程' })).not.toHaveTextContent('已启动')
  failed = false; fireEvent.click(screen.getByRole('button', { name: '重新读取状态' }))
  expect(await screen.findByText('已启动')).toBeVisible()
  expect(requests.filter(value => value === '/v1/ui/execution-process')).toHaveLength(3)
})
