import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import MinuteWorkspace from './MinuteWorkspace'

vi.mock('../components/MarketCandlestickChart', () => ({ MarketCandlestickChart: ({ bundle }: { bundle?: { symbol: string; period: string } }) =>
  bundle ? ('data_available' in bundle && !bundle.data_available ? <p>暂无权威 K 线</p> : <div role="img" aria-label={bundle.symbol + ' ' + bundle.period} />) : <p>图表读取中</p> }))
const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.unstubAllGlobals() })
const daily = { schema_version: '1.6', symbol: '510300.SH', period: '1d', source_period: '1d', derived: false,
  data_available: true, as_of: '2026-10-22T16:00:00Z',
  candles: [{ occurred_at: '2026-10-22T16:00:00Z', open: 4, close: 4.1, high: 4.2, low: 3.9, volume: 100 }],
  native_source: { provider: 'Qmt', qualification: 'DevelopmentVerified', timestamp_semantics: 'source_date', chart_minute_boundary: 'source_date', volume_unit: 'unknown' } }
function mount(periods = ['1m', '1d']) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client)
  render(<QueryClientProvider client={client}><MinuteWorkspace capability={{ available: true, periods, reason: null }} /></QueryClientProvider>)
}
test('源日线周期切换、来源日期/未知单位、带时区截止及失败后恢复均为GET', async () => {
  const requests: string[] = []; let failing = false
  const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    requests.push(String(input)); expect(init?.method ?? 'GET').toBe('GET')
    return failing ? new Response('', { status: 503 }) : Response.json(daily)
  })
  vi.stubGlobal('fetch', fetch); mount()
  expect(screen.queryByRole('button', { name: '5 分钟' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: '日线' }))
  const input = screen.getByRole('textbox', { name: '证券代码' })
  fireEvent.change(input, { target: { value: '510300.sh' } }); fireEvent.submit(input.closest('form')!)
  expect(await screen.findByRole('img', { name: '510300.SH 1d' })).toBeVisible()
  expect(screen.getByRole('status', { name: '最后数据时点' })).toHaveTextContent('最新交易日：2026-10-23')
  expect(screen.getByRole('status', { name: '读图说明' })).toHaveTextContent('日线按交易日显示')
  expect(screen.getByRole('status', { name: '读图说明' })).toHaveTextContent('成交量单位待确认')
  fireEvent.change(screen.getByRole('textbox', { name: '截止时间' }), { target: { value: '2026-10-22T15:00:00+08:00' } })
  fireEvent.submit(input.closest('form')!)
  await screen.findByRole('img', { name: '510300.SH 1d' })
  expect(new URL(requests.at(-1)!, 'http://local').searchParams.get('before')).toBe('2026-10-22T15:00:00+08:00')
  failing = true; fireEvent.submit(input.closest('form')!)
  expect(await screen.findByRole('alert')).toHaveTextContent('行情图表读取失败')
  expect(screen.getByRole('img', { name: '510300.SH 1d' })).toBeVisible()
  expect(screen.getByRole('status', { name: '最后数据时点' })).toHaveTextContent('最新交易日：2026-10-23')
  failing = false; fireEvent.click(screen.getByRole('button', { name: '重试读取' }))
  expect(await screen.findByRole('img', { name: '510300.SH 1d' })).toBeVisible()
  expect(requests.every(value => new URL(value, 'http://local').searchParams.get('period') === '1d')).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: '分时' }))
  await screen.findByRole('button', { name: '读取分钟线' })
})

test('同查询刷新中和业务失败保留图；不同查询不串数据，成功空更新为空', async () => {
  let respond!: (response: Response) => void
  let deferred = false
  const fetch = vi.fn(async () => deferred ? new Promise<Response>(resolve => { respond = resolve }) : Response.json({ ...daily, source_kind: 'wondertrader' }))
  vi.stubGlobal('fetch', fetch); mount()
  fireEvent.click(screen.getByRole('button', { name: '日线' }))
  const input = screen.getByRole('textbox', { name: '证券代码' })
  fireEvent.change(input, { target: { value: '510300.SH' } }); fireEvent.submit(input.closest('form')!)
  await screen.findByRole('img', { name: '510300.SH 1d' })
  deferred = true; fireEvent.submit(input.closest('form')!)
  await screen.findByText('正在刷新，当前显示上次成功读取的结果。')
  expect(screen.getByRole('img', { name: '510300.SH 1d' })).toBeVisible()
  respond(Response.json({ ...daily, source_kind: 'wondertrader', data_available: false, candles: [], native_source: null, missing_reason: '行情暂时无法更新' }))
  await screen.findByRole('alert')
  expect(screen.getByRole('img', { name: '510300.SH 1d' })).toBeVisible()
  fireEvent.change(input, { target: { value: '600000.SH' } }); fireEvent.submit(input.closest('form')!)
  await waitFor(() => expect(screen.queryByRole('img')).toBeNull())
  respond(Response.json({ ...daily, symbol: '600000.SH', data_available: false, candles: [] }))
  await screen.findByText('暂无权威 K 线')
  expect(screen.getByRole('status', { name: '最后数据时点' })).toHaveTextContent('未取得有效行情')
  expect(screen.queryByRole('status', { name: '读图说明' })).toBeNull()
})
test('canonical能力只提供原分钟周期', () => {
  vi.stubGlobal('fetch', vi.fn()); mount(['1m', '5m'])
  expect(screen.queryByRole('button', { name: '日线' })).toBeNull()
  expect(screen.getByRole('button', { name: '5 分钟' })).toBeVisible()
})
