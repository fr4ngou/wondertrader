import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import MinuteWorkspace from './MinuteWorkspace'

vi.mock('../components/MarketCandlestickChart', () => ({
  MarketCandlestickChart: ({ bundle, loading }: { bundle?: { symbol: string }; loading: boolean }) =>
    !bundle ? <p>图表读取中</p> : <div role="img" aria-label={'分钟图 ' + bundle.symbol} />,
}))
const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.unstubAllGlobals() })
const watchlistCapability = { available: true, editable: true, max_items: 100,
  scope: 'personal-observation', affects_strategy: false, reason: null }
const id = '12345678-1234-4234-8234-123456789abc'
function list(symbols = ['600000.SH'], version = 1) {
  return { schema_version: 'guanheng.personal-watchlist.v1', watchlist_id: id, version, symbols,
    updated_at: '2026-10-23T01:0' + (version - 1) + ':00Z', affects_strategy: false, editable: true, reason: null }
}
function chart(symbol: string) {
  return { schema_version: '1.4', symbol, period: '1m', data_available: true,
    as_of: '2026-10-23T01:31:00Z', source_kind: 'wondertrader', source_period: '1m', source_bar_count: 1,
    derived: false, candles: [{ occurred_at: '2026-10-23T01:31:00Z', open: 3, high: 3.1, low: 2.9, close: 3.05, volume: 10 }],
    overlay_unavailable_sources: ['strategy', 'bridge'] }
}
function show(market = true, personal: unknown = watchlistCapability) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })
  clients.push(client)
  render(<QueryClientProvider client={client}><MinuteWorkspace
    capability={{ available: market, reason: market ? null : '分钟来源未配置' }} watchlistCapability={personal} />
  </QueryClientProvider>)
}
function submitAdd(symbol: string) {
  const input = screen.getByRole('textbox', { name: '加入个人观察的证券代码' })
  fireEvent.change(input, { target: { value: symbol } })
  fireEvent.submit(input.closest('form')!)
}

test('真实API完整列表保存和移出不取行情；仅点击代码沿原分钟入口，移出当前代码保留图', async () => {
  const requests: { url: string; method: string; body?: string }[] = []
  let stored = list()
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    requests.push({ url, method, body: init?.body as string | undefined })
    if (url === '/v1/ui/watchlists/default') {
      if (method === 'GET') return Response.json(stored)
      const target = JSON.parse(String(init?.body))
      stored = list(target.symbols, stored.version + 1)
      return Response.json({ schema_version: stored.schema_version, changed: true, watchlist: stored })
    }
    if (url.startsWith('/v1/ui/market/chart/')) return Response.json(chart('600000.SH'))
    throw new Error('unexpected source')
  }))
  show()
  await waitFor(() => expect(screen.getByRole('button', { name: '加入个人观察' })).toBeEnabled())
  expect(requests.map(row => row.url)).toEqual(['/v1/ui/watchlists/default'])
  submitAdd('510300.sh')
  await screen.findByText('已保存个人观察；策略交易范围不变。')
  expect(requests.map(row => row.method)).toEqual(['GET', 'PUT'])
  expect(JSON.parse(requests[1].body!)).toEqual({ schema_version: 'guanheng.personal-watchlist.v1',
    watchlist_id: id, expected_version: 1, symbols: ['600000.SH', '510300.SH'] })
  fireEvent.change(screen.getByRole('textbox', { name: '截止时间' }), { target: { value: '2026-10-23T15:00:00+08:00' } })
  fireEvent.click(screen.getByRole('button', { name: '查看 600000.SH 分钟线' }))
  await screen.findByRole('img', { name: '分钟图 600000.SH' })
  expect(requests.filter(row => row.url.startsWith('/v1/ui/market/chart/'))).toHaveLength(1)
  const url = requests.find(row => row.url.startsWith('/v1/ui/market/chart/'))!.url
  expect(url).toContain('/v1/ui/market/chart/600000.SH?')
  expect(new URL(url, 'http://example.invalid').searchParams.get('before')).toBe('2026-10-23T15:00:00+08:00')
  expect(new URL(url, 'http://example.invalid').searchParams.get('limit')).toBe('2000')
  fireEvent.click(screen.getByRole('button', { name: '移出 600000.SH 的个人观察' }))
  await waitFor(() => expect(screen.queryByRole('button', { name: '查看 600000.SH 分钟线' })).not.toBeInTheDocument())
  expect(screen.getByRole('img', { name: '分钟图 600000.SH' })).toBeVisible()
  expect(requests.filter(row => row.url.startsWith('/v1/ui/market/chart/'))).toHaveLength(1)
  expect(requests.map(row => row.url).some(value => /bootstrap|control|strategy|account|subscriptions/.test(value))).toBe(false)
})

test('能力提示关闭仍可保存偏好和读取已有行情', async () => {
  const requests: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    requests.push((init?.method ?? 'GET') + ' ' + String(input))
    if (String(input).startsWith('/v1/ui/market/chart/')) return Response.json(chart('600000.SH'))
    if (String(input) !== '/v1/ui/watchlists/default') throw new Error('unexpected route')
    if (init?.method === 'PUT') return Response.json({ schema_version: 'guanheng.personal-watchlist.v1',
      changed: true, watchlist: list(['600000.SH', '510300.SH'], 2) })
    return Response.json(list())
  }))
  show(false)
  await waitFor(() => expect(screen.getByRole('button', { name: '加入个人观察' })).toBeEnabled())
  expect(screen.getByRole('button', { name: '查看 600000.SH 分钟线' })).toBeEnabled()
  submitAdd('510300.SH')
  await screen.findByText('已保存个人观察；策略交易范围不变。')
  expect(requests).toEqual(['GET /v1/ui/watchlists/default', 'PUT /v1/ui/watchlists/default'])
  fireEvent.click(screen.getByRole('button', { name: '查看 600000.SH 分钟线' }))
  expect(await screen.findByRole('img', { name: '分钟图 600000.SH' })).toBeVisible()
  expect(requests.at(-1)).toContain('GET /v1/ui/market/chart/600000.SH?')
})

test('手工查询在自选关闭时保持正常、刷新失败保留图和主动恢复', async () => {
  const requests: string[] = []
  let failure = false
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    requests.push(String(input))
    if (!String(input).startsWith('/v1/ui/market/chart/')) throw new Error('unexpected watchlist')
    return failure ? new Response('', { status: 503 }) : Response.json(chart('600000.SH'))
  }))
  show(true, { ...watchlistCapability, available: false, editable: false, reason: '未配置' })
  expect(screen.getByText(/个人观察暂不可用/)).toBeVisible()
  const input = screen.getByRole('textbox', { name: '证券代码' })
  fireEvent.change(input, { target: { value: '600000.sh' } })
  fireEvent.submit(input.closest('form')!)
  await screen.findByRole('img', { name: '分钟图 600000.SH' })
  failure = true
  fireEvent.submit(input.closest('form')!)
  await screen.findByText('刷新失败，当前保留上次成功读取的结果，数据时间见下方。')
  expect(screen.getByRole('img', { name: '分钟图 600000.SH' })).toBeVisible()
  failure = false
  fireEvent.click(screen.getByRole('button', { name: '重试读取' }))
  await screen.findByRole('img', { name: '分钟图 600000.SH' })
  expect(requests).toHaveLength(3)
  expect(requests.every(value => value.startsWith('/v1/ui/market/chart/'))).toBe(true)
})

test('矛盾PUT回执经真实API成为未知，只GET核实完整目标，不自动重发', async () => {
  const requests: string[] = []
  let committed = false
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    requests.push(method + ' ' + String(input))
    if (String(input) !== '/v1/ui/watchlists/default') throw new Error('unexpected chart')
    if (method === 'PUT') {
      committed = true
      return Response.json({ schema_version: 'guanheng.personal-watchlist.v1', changed: false,
        watchlist: list(['600000.SH', '510300.SH'], 2) })
    }
    return Response.json(committed ? list(['600000.SH', '510300.SH'], 2) : list())
  }))
  show()
  await waitFor(() => expect(screen.getByRole('button', { name: '加入个人观察' })).toBeEnabled())
  submitAdd('510300.SH')
  await screen.findByText(/保存结果尚未确认/)
  expect(screen.getByRole('button', { name: '加入个人观察' })).toBeDisabled()
  expect(screen.queryByRole('button', { name: '查看 510300.SH 分钟线' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '重新读取个人观察' }))
  await screen.findByText('已核实当前列表与本次保存目标一致；策略交易范围不变。')
  expect(requests).toEqual(['GET /v1/ui/watchlists/default', 'PUT /v1/ui/watchlists/default', 'GET /v1/ui/watchlists/default'])
})

test.each(['{"secret":"private://payload"}', 'not-json secret=abc'])(
  '真实GET异常格式保持中文失败和零PUT：%s', async body => {
    const requests: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      requests.push((init?.method ?? 'GET') + ' ' + String(input))
      return new Response(body, { status: 200, headers: { 'Content-Type': 'application/json' } })
    }))
    show(false)
    expect(await screen.findByText(/个人观察读取失败或资料无效/)).toBeVisible()
    expect(screen.getByRole('button', { name: '加入个人观察' })).toBeDisabled()
    expect(screen.queryByText(/private:\/\/payload|secret=abc/)).not.toBeInTheDocument()
    expect(screen.queryByText('个人观察列表为空；输入完整证券代码加入，仅供本页观察。')).not.toBeInTheDocument()
    expect(requests).toEqual(['GET /v1/ui/watchlists/default'])
  },
)
