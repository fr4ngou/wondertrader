import { afterEach, expect, test, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, useLocation } from 'react-router-dom'
import IndependentApp from './IndependentApp'
import accountFixture from './account-v2.fixture.json'

const personalClients: QueryClient[] = []
afterEach(() => { cleanup(); personalClients.splice(0).forEach(client => client.clear()); vi.unstubAllGlobals() })

function Location() { return <output aria-label="当前路径">{useLocation().pathname}</output> }

test('连接信息首次失败仍可从账户页主动读取，元数据失败只影响自身提示', async () => {
  const fetch = vi.fn(async (input: RequestInfo | URL) => String(input) === '/v1/ui/account/overview'
    ? Response.json(accountFixture) : new Response('', { status: 503 }))
  vi.stubGlobal('fetch', fetch)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); personalClients.push(client)
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/account']}><IndependentApp /></MemoryRouter></QueryClientProvider>)
  await screen.findByRole('heading', { name: '连接信息暂时无法更新' })
  expect(await screen.findByRole('heading', { level: 1, name: '账户' })).toBeVisible()
  expect(fetch.mock.calls.filter(call => String(call[0]) === '/v1/ui/account/overview')).toHaveLength(0)
  fireEvent.click(screen.getByRole('button', { name: '刷新账户' }))
  expect(await screen.findByText('700')).toBeVisible()
})

test('连接信息后台失败保留账户路由和成功数据，重读连接信息后恢复', async () => {
  let failure = false
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    if (String(input) === '/v1/ui/account/overview') return Response.json(accountFixture)
    if (String(input) === '/v1/ui/capabilities') return failure ? new Response('', { status: 503 }) : Response.json({ read_only: true,
      features: { minute_chart: { available: false, reason: null }, account: { available: false, reason: '连接信息提示关闭' } } })
    throw new Error('unexpected source')
  }))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); personalClients.push(client)
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/account']}><IndependentApp /></MemoryRouter></QueryClientProvider>)
  fireEvent.click(await screen.findByRole('button', { name: '刷新账户' }))
  await screen.findByText('700')
  failure = true
  await act(async () => { await client.refetchQueries({ queryKey: ['independent-capabilities'] }) })
  await screen.findByRole('heading', { name: '连接信息暂时无法更新' })
  expect(screen.getByRole('heading', { level: 1, name: '账户' })).toBeVisible()
  expect(screen.getByText('700')).toBeVisible()
  failure = false
  fireEvent.click(screen.getByRole('button', { name: '重新读取连接信息' }))
  await waitFor(() => expect(screen.queryByRole('heading', { name: '连接信息暂时无法更新' })).not.toBeInTheDocument())
  expect(screen.getByText('700')).toBeVisible()
})

test('交易记录路由复用只读账户能力，返回账户恢复默认持仓视图', async () => {
  const fetchMock = vi.fn(async () => Response.json({ read_only: true, features: {
    minute_chart: { available: false, reason: '行情未配置' }, account: { available: false, reason: '来源未配置' },
  } }))
  vi.stubGlobal('fetch', fetchMock)
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={['/orders']}><IndependentApp /><Location /></MemoryRouter>
  </QueryClientProvider>)
  expect(await screen.findByRole('heading', { level: 1, name: '交易记录' })).toBeInTheDocument()
  expect(await screen.findByText('来源未配置')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('link', { name: '账户' }))
  expect(await screen.findByRole('heading', { level: 1, name: '账户' })).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

test.each([['/research', '/market', '行情'], ['/research/legacy?tab=news', '/market', '行情'], ['/news', '/market', '行情'], ['/news/legacy', '/market', '行情'], ['/grafana/legacy', '/operations', '系统状态']])(
  'retires %s while preserving core navigation', async (initial, target, heading) => {
    const requests: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input); requests.push(url)
      if (url === '/v1/ui/capabilities') return Response.json({ read_only: true, features: {
        minute_chart: { available: false, reason: '行情来源未配置' },
      } })
      throw new Error('unexpected service request')
    }))
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[initial]}><IndependentApp /><Location /></MemoryRouter>
    </QueryClientProvider>)
    // 首次懒加载会延后Routes提交；先等待用户可见页面，再核最终导航与请求。
    expect(await screen.findByRole('heading', { name: heading, level: 1 }, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.getByLabelText('当前路径')).toHaveTextContent(target)
    const nav = screen.getByRole('navigation', { name: '主要工作区' })
    expect([...nav.querySelectorAll('a')].map(a => a.textContent)).toEqual(['总览', '行情', '市场观察', '策略', '账户', '交易记录', '系统状态'])
    expect(nav.querySelector('a[href="/research"]')).toBeNull()
    expect(document.querySelector('iframe')).toBeNull()
    expect(requests).toEqual(target === '/operations'
      ? ['/v1/ui/capabilities', '/v1/ui/wt-runtime', '/v1/ui/operations/status'] : ['/v1/ui/capabilities'])
  },
)

const personalCapability = { available: true, editable: true, max_items: 100,
  scope: 'personal-observation', affects_strategy: false, reason: null }
function personalSnapshot(symbols: string[] = [], version = 1) {
  return { schema_version: 'guanheng.personal-watchlist.v1', watchlist_id: '12345678-1234-4234-8234-123456789abc',
    version, symbols, updated_at: '2026-10-23T01:0' + (version - 1) + ':00Z',
    affects_strategy: false, editable: true, reason: null }
}
function mountPersonalMarket() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })
  personalClients.push(client)
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/market']}><IndependentApp /></MemoryRouter></QueryClientProvider>)
}

test('真实独立壳将个人观察能力传入行情页；分钟关闭仍可一次保存且不读旧bootstrap', async () => {
  const requests: { url: string; method: string }[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    requests.push({ url, method })
    if (url === '/v1/ui/capabilities') return Response.json({ read_only: true, features: {
      minute_chart: { available: false, reason: '分钟未配置' }, personal_watchlist: personalCapability,
    } })
    if (url === '/v1/ui/watchlists/default') {
      if (method === 'GET') return Response.json(personalSnapshot())
      const body = JSON.parse(String(init?.body))
      expect(body).toEqual({ schema_version: 'guanheng.personal-watchlist.v1',
        watchlist_id: '12345678-1234-4234-8234-123456789abc', expected_version: 1, symbols: ['600000.SH'] })
      return Response.json({ schema_version: 'guanheng.personal-watchlist.v1', changed: true,
        watchlist: personalSnapshot(['600000.SH'], 2) })
    }
    throw new Error('unexpected old service')
  }))
  mountPersonalMarket()
  expect(await screen.findByRole('heading', { name: '我的个人观察' }, { timeout: 5000 })).toBeVisible()
  const input = await screen.findByRole('textbox', { name: '加入个人观察的证券代码' })
  await waitFor(() => expect(input).toBeEnabled())
  fireEvent.change(input, { target: { value: '600000.SH' } })
  fireEvent.submit(input.closest('form')!)
  await screen.findByText('已保存个人观察；策略交易范围不变。')
  expect(screen.getByText('交易只读')).toBeVisible()
  expect(screen.getByRole('button', { name: '查看 600000.SH 分钟线' })).toBeEnabled()
  expect(requests).toEqual([{ url: '/v1/ui/capabilities', method: 'GET' },
    { url: '/v1/ui/watchlists/default', method: 'GET' }, { url: '/v1/ui/watchlists/default', method: 'PUT' }])
})

test('独立壳的个人观察能力关闭只请求capabilities，不采用旧自选接口', async () => {
  const requests: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    requests.push(String(input))
    if (String(input) !== '/v1/ui/capabilities') throw new Error('unexpected source')
    return Response.json({ read_only: true, features: {
      minute_chart: { available: false, reason: '分钟未配置' },
      personal_watchlist: { ...personalCapability, available: false, editable: false, reason: '未配置' },
    } })
  }))
  mountPersonalMarket()
  expect(await screen.findByText('个人观察暂不可用，请检查本机配置或偏好资料。仍可直接查询分钟线。', {}, { timeout: 5000 })).toBeVisible()
  expect(screen.queryByRole('textbox', { name: '加入个人观察的证券代码' })).not.toBeInTheDocument()
  expect(requests).toEqual(['/v1/ui/capabilities'])
})

type RouteReadOutcome = 'committed' | 'uncommitted' | 'different-target' | 'different-id' | 'different-order' | 'get-failure'
const routeOutcomes: RouteReadOutcome[] = ['committed', 'uncommitted', 'different-target', 'different-id', 'different-order', 'get-failure']
const routeStates = (['pending', 'unknown'] as const).flatMap(phase => routeOutcomes.map(outcome => ({ phase, outcome })))

test.each(routeStates)('跨实际路由保留$phase的完整目标；返回GET=$outcome只核实且零重发', async ({ phase, outcome }) => {
  const response = personalDeferred<Response>()
  const requests: { url: string; method: string; body?: string }[] = []
  let reads = 0
  let repaired = false
  const target = ['600000.SH', '510300.SH']
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    requests.push({ url, method, body: typeof init?.body === 'string' ? init.body : undefined })
    if (url === '/v1/ui/capabilities') return Response.json({ read_only: true, features: {
      minute_chart: { available: false, reason: '分钟未配置' }, account: { available: false, reason: '账户未配置' },
      personal_watchlist: personalCapability,
    } })
    if (url !== '/v1/ui/watchlists/default') throw new Error('unexpected service')
    if (method === 'PUT') return response.promise
    reads += 1
    if (reads === 1 || outcome === 'uncommitted' && !repaired) return Response.json(personalSnapshot(['600000.SH']))
    if (outcome === 'get-failure' && !repaired) throw new Error('private://secret/path')
    if (outcome === 'different-target' && !repaired) return Response.json(personalSnapshot(['000001.SZ'], 2))
    if (outcome === 'different-id' && !repaired) return Response.json({ ...personalSnapshot(target, 2),
      watchlist_id: '12345678-1234-4234-9234-123456789abc' })
    if (outcome === 'different-order' && !repaired) return Response.json(personalSnapshot([...target].reverse(), 2))
    return Response.json(personalSnapshot(target, 2))
  }))
  mountPersonalMarket()
  const input = await screen.findByRole('textbox', { name: '加入个人观察的证券代码' })
  await waitFor(() => expect(input).toBeEnabled())
  fireEvent.change(input, { target: { value: '510300.SH' } })
  fireEvent.submit(input.closest('form')!)
  await waitFor(() => expect(requests.filter(item => item.method === 'PUT')).toHaveLength(1))
  if (phase === 'unknown') {
    await act(async () => { response.reject(new Error('private://secret/path')) })
    await screen.findByText(/保存结果尚未确认/)
  }
  fireEvent.click(screen.getByRole('link', { name: '账户' }))
  await screen.findByRole('heading', { level: 1, name: '账户' })
  if (phase === 'pending') await act(async () => { response.reject(new Error('private://secret/path')) })
  fireEvent.click(screen.getByRole('link', { name: '行情' }))
  await waitFor(() => expect(reads).toBe(2))
  if (outcome === 'committed') {
    await screen.findByText('已核实当前列表与本次保存目标一致；策略交易范围不变。')
    await waitFor(() => expect(screen.getByRole('button', { name: '加入个人观察' })).toBeEnabled())
    expect(screen.queryByText(/本次待核实的完整观察目标/)).not.toBeInTheDocument()
  } else {
    const message = outcome === 'get-failure' ? /个人观察读取失败或资料无效/
      : outcome === 'different-id' ? /列表身份已变化/ : /本次目标尚未在当前列表中确认/
    await screen.findByText(message)
    expect(screen.getByText(/本次待核实的完整观察目标（2项）：600000.SH、510300.SH/)).toBeVisible()
    expect(screen.getByRole('button', { name: '加入个人观察' })).toBeDisabled()
    expect(screen.queryByText(/已核实当前列表与本次保存目标一致/)).not.toBeInTheDocument()
    if (outcome === 'get-failure') {
      expect(screen.queryByRole('button', { name: '确认当前列表后继续编辑' })).not.toBeInTheDocument()
      repaired = true
      fireEvent.click(screen.getByRole('button', { name: '重新读取个人观察' }))
      await screen.findByText('已核实当前列表与本次保存目标一致；策略交易范围不变。')
      await waitFor(() => expect(screen.getByRole('button', { name: '加入个人观察' })).toBeEnabled())
    } else {
      fireEvent.click(screen.getByRole('button', { name: '确认当前列表后继续编辑' }))
      await waitFor(() => expect(screen.getByRole('button', { name: '加入个人观察' })).toBeEnabled())
    }
  }
  const puts = requests.filter(item => item.method === 'PUT')
  expect(puts).toHaveLength(1)
  expect(JSON.parse(puts[0].body!)).toEqual({ schema_version: 'guanheng.personal-watchlist.v1',
    watchlist_id: '12345678-1234-4234-8234-123456789abc', expected_version: 1, symbols: target })
  expect(screen.queryByText(/private:\/\/secret/)).not.toBeInTheDocument()
  expect(requests.every(item => ['/v1/ui/capabilities', '/v1/ui/watchlists/default'].includes(item.url))).toBe(true)
})

function personalDeferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

test('返回行情时原PUT仍在途，旧GET不解除门禁；晚异常后只GET核实', async () => {
  const response = personalDeferred<Response>()
  const methods: string[] = []
  let committed = false
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url === '/v1/ui/capabilities') return Response.json({ read_only: true, features: {
      minute_chart: { available: false, reason: '分钟未配置' }, account: { available: false, reason: '账户未配置' },
      personal_watchlist: personalCapability,
    } })
    if (url !== '/v1/ui/watchlists/default') throw new Error('unexpected service')
    methods.push(init?.method ?? 'GET')
    if (init?.method === 'PUT') return response.promise
    return Response.json(committed ? personalSnapshot(['600000.SH'], 2) : personalSnapshot())
  }))
  mountPersonalMarket()
  const input = await screen.findByRole('textbox', { name: '加入个人观察的证券代码' })
  await waitFor(() => expect(input).toBeEnabled())
  fireEvent.change(input, { target: { value: '600000.SH' } })
  fireEvent.submit(input.closest('form')!)
  await waitFor(() => expect(methods.filter(item => item === 'PUT')).toHaveLength(1))
  fireEvent.click(screen.getByRole('link', { name: '账户' }))
  await screen.findByRole('heading', { level: 1, name: '账户' })
  fireEvent.click(screen.getByRole('link', { name: '行情' }))
  await waitFor(() => expect(methods.filter(item => item === 'GET')).toHaveLength(2))
  expect(screen.getByText(/正在保存个人观察/)).toBeVisible()
  expect(screen.getByRole('button', { name: '加入个人观察' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '重新读取个人观察' })).toBeDisabled()
  await act(async () => { response.reject(new Error('response lost')) })
  await screen.findByText(/保存结果尚未确认/)
  expect(screen.getByRole('button', { name: '加入个人观察' })).toBeDisabled()
  committed = true
  fireEvent.click(screen.getByRole('button', { name: '重新读取个人观察' }))
  await screen.findByText('已核实当前列表与本次保存目标一致；策略交易范围不变。')
  expect(methods).toEqual(['GET', 'PUT', 'GET', 'GET'])
})

test('原PUT卸载期间成功由同一owner采用，回到行情显示已保存且不重发', async () => {
  const response = personalDeferred<Response>()
  const methods: string[] = []
  let committed = false
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (String(input) === '/v1/ui/capabilities') return Response.json({ read_only: true, features: {
      minute_chart: { available: false, reason: '分钟未配置' }, account: { available: false, reason: '账户未配置' },
      personal_watchlist: personalCapability,
    } })
    if (String(input) !== '/v1/ui/watchlists/default') throw new Error('unexpected service')
    methods.push(init?.method ?? 'GET')
    if (init?.method === 'PUT') return response.promise
    return Response.json(committed ? personalSnapshot(['600000.SH'], 2) : personalSnapshot())
  }))
  mountPersonalMarket()
  const input = await screen.findByRole('textbox', { name: '加入个人观察的证券代码' })
  await waitFor(() => expect(input).toBeEnabled())
  fireEvent.change(input, { target: { value: '600000.SH' } })
  fireEvent.submit(input.closest('form')!)
  await waitFor(() => expect(methods.filter(item => item === 'PUT')).toHaveLength(1))
  fireEvent.click(screen.getByRole('link', { name: '账户' }))
  await screen.findByRole('heading', { level: 1, name: '账户' })
  committed = true
  await act(async () => { response.resolve(Response.json({ schema_version: 'guanheng.personal-watchlist.v1',
    changed: true, watchlist: personalSnapshot(['600000.SH'], 2) })) })
  fireEvent.click(screen.getByRole('link', { name: '行情' }))
  await screen.findByText('已保存个人观察；策略交易范围不变。')
  await waitFor(() => expect(screen.getByRole('button', { name: '加入个人观察' })).toBeEnabled())
  expect(methods).toEqual(['GET', 'PUT', 'GET'])
})
