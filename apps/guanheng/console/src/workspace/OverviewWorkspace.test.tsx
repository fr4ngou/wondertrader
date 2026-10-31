import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import IndependentApp from './IndependentApp'
import fixture from './account-v2.fixture.json'
import { historyPreparationFixture } from './operations.fixture'

// 总览复用公开 DTO 与账户只读查询，覆盖来源禁用和已返回账户事实。
const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.unstubAllGlobals() })
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })
  clients.push(client)
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/dashboard']}><IndependentApp /></MemoryRouter></QueryClientProvider>)
}
function capabilities(available: boolean) {
  return { read_only: true, features: {
    minute_chart: { available: false, reason: '行情未配置' },
    account: { available, reason: available ? null : '账户来源尚未开放', timeout_seconds: 15 },
  } }
}

test('账户能力关闭时总览独立读取补齐状态，保留账户原因', async () => {
  const requests: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    requests.push(String(input))
    if (String(input) === '/v1/ui/qmt-history-preparation') return Response.json(historyPreparationFixture)
    if (String(input) === '/v1/ui/capabilities') return Response.json(capabilities(false))
    throw new Error('unexpected data source')
  }))
  mount()
  expect(await screen.findByRole('heading', { level: 1, name: '总览' }, { timeout: 5000 })).toBeInTheDocument()
  expect(screen.getByText('账户来源尚未开放')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '刷新账户' })).toBeDisabled()
  expect(screen.getByText(/策略运行状态和收益曲线尚未接通/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /下单|撤单/ })).not.toBeInTheDocument()
  expect(await screen.findByRole('region', { name: '历史补齐进程' })).toHaveTextContent('未配置')
  expect(requests).toEqual(['/v1/ui/capabilities', '/v1/ui/qmt-history-preparation'])
})

test('总览复用同一DTO2账户读取，保留真实资金字段、来源和未知项', async () => {
  const requests: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input); requests.push(url)
    if (url === '/v1/ui/qmt-history-preparation') return Response.json(historyPreparationFixture)
    if (url === '/v1/ui/capabilities') return Response.json(capabilities(true))
    if (url === '/v1/ui/account/overview') return Response.json(structuredClone(fixture))
    throw new Error('unexpected legacy source')
  }))
  mount()
  expect(await screen.findByRole('heading', { level: 1, name: '总览' }, { timeout: 5000 })).toBeInTheDocument()
  await screen.findByText('600000.SH')
  const assets = screen.getByRole('heading', { name: '总资产（元）' }).closest('article')
  expect(assets).not.toBeNull()
  expect(within(assets!).getByText('123,456.789')).toBeInTheDocument()
  const positions = within(screen.getByRole('tabpanel'))
  expect(positions.getByText('700')).toBeInTheDocument()
  expect(positions.getByText('420')).toBeInTheDocument()
  expect(positions.getAllByText('未知').length).toBeGreaterThan(0)
  expect(positions.getByText(/券商登录未知/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /下单|撤单/ })).not.toBeInTheDocument()
  expect([...requests].sort()).toEqual(['/v1/ui/capabilities', '/v1/ui/account/overview', '/v1/ui/qmt-history-preparation'].sort())
})
