import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { HistoryPreparationOverview, HistoryPreparationStatus, useHistoryPreparationStatus } from './HistoryPreparationStatus'
import { fetchHistoryPreparation } from './historyPreparationApi'
import { historyPreparationFixture } from './operations.fixture'

const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(c => c.clear()); vi.unstubAllGlobals() })
const ready = { ...historyPreparationFixture, process: { ...historyPreparationFixture.process,
  state: 'ready', label: '监听就绪', ready: true, pid: 12345 } }

test('总览补齐状态保持简短，刷新失败保留原结果和时间，手动恢复', async () => {
  let release: ((response: Response) => void) | undefined
  const fetch = vi.fn().mockResolvedValueOnce(Response.json(ready))
    .mockImplementationOnce(() => new Promise<Response>(resolve => { release = resolve }))
    .mockResolvedValueOnce(Response.json(ready))
  vi.stubGlobal('fetch', fetch)
  const client = new QueryClient(); clients.push(client)
  render(<QueryClientProvider client={client}><HistoryPreparationOverview /></QueryClientProvider>)
  expect(await screen.findByText('监听就绪')).toBeVisible()
  expect(screen.getByRole('region', { name: '历史补齐进程' })).not.toHaveTextContent(/12345|进程编号|强制回收|待收束资源/)
  fireEvent.click(screen.getByRole('button', { name: '重新读取补齐状态' }))
  await screen.findByText('正在读取补齐状态…')
  expect(screen.getByText('监听就绪')).toBeVisible()
  await waitFor(() => expect(release).toBeDefined())
  release!(Response.json({}, { status: 503 }))
  expect(await screen.findByRole('alert')).toHaveTextContent('当前保留上次读取结果和时间')
  expect(screen.getByText('监听就绪')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '重新读取补齐状态' }))
  await waitFor(() => expect(screen.queryByRole('alert')).toBeNull())
  expect(screen.getByText('监听就绪')).toBeVisible()
  expect(fetch.mock.calls.every(([path, init]) => path === '/v1/ui/qmt-history-preparation' && (init?.method ?? 'GET') === 'GET')).toBe(true)
  expect(screen.getAllByRole('button')).toHaveLength(1)
})

test.each([
  { schema_version: 'old' }, { qmt_connection: 'connected' }, { data_qualification: 'qualified' },
  { observed_at: 'invalid' }, { read_only: false }, { process: {} },
])('拒绝错误schema或未经核实来源声明：%o', async invalid => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ ...ready, ...invalid })))
  await expect(fetchHistoryPreparation(new AbortController().signal)).rejects.toThrow('历史补齐状态格式无效')
})

test('系统状态共用补齐卡在读取中和失败时继续显示原状态与原时间', async () => {
  let release!: (response: Response) => void
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(Response.json(ready))
    .mockImplementationOnce(() => new Promise<Response>(resolve => { release = resolve }))
    .mockResolvedValueOnce(Response.json({ ...ready, process: { ...ready.process, state: 'closed', label: '已停止', ready: false } })))
  function Page() { const query = useHistoryPreparationStatus(); return <><HistoryPreparationStatus query={query} /><button onClick={() => void query.refetch()}>刷新</button></> }
  const client = new QueryClient(); clients.push(client)
  render(<QueryClientProvider client={client}><Page /></QueryClientProvider>)
  const card = await screen.findByRole('region', { name: '历史补齐进程' })
  const original = card.textContent
  fireEvent.click(screen.getByRole('button', { name: '刷新' }))
  await screen.findByText(/当前显示上次读取的状态和时间/)
  expect(card.textContent).toBe(original)
  release(Response.json({}, { status: 503 }))
  await screen.findByRole('alert')
  expect(card.textContent).toBe(original)
  fireEvent.click(screen.getByRole('button', { name: '刷新' }))
  await screen.findByText('已停止')
  expect(screen.queryByRole('alert')).toBeNull()
})
