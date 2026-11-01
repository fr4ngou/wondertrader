import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import IndependentApp from './IndependentApp'
import { fetchMarketChart } from '../api'

vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(), fetchMarketChart: vi.fn() }))
vi.mock('../components/MarketCandlestickChart', () => ({ MarketCandlestickChart: () => null }))
const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.resetAllMocks(); vi.unstubAllGlobals() })

test('直达证券页面先等能力读取结束，再按声明的来源截止打开图表', async () => {
  let complete!: (value: Response) => void
  const capability = new Promise<Response>(resolve => { complete = resolve })
  const chart = vi.mocked(fetchMarketChart).mockImplementation(async symbol => ({ schema_version: '1.0', symbol, period: '1m', data_available: false, candles: [] }))
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    if (String(input) === '/v1/ui/capabilities') return capability
    throw new Error('unexpected source request')
  }))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client)
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/market?search=688170.SH']}><IndependentApp /></MemoryRouter></QueryClientProvider>)
  await screen.findByRole('heading', { name: '行情', level: 1 }, { timeout: 5000 })
  expect(chart).not.toHaveBeenCalled()
  const read = screen.getByRole('button', { name: '读取分钟线' })
  expect(read).toBeDisabled()
  fireEvent.click(read)
  // Enter及显式表单提交也经统一入口；禁用自动query不能替代此守卫。
  fireEvent.submit(read.closest('form')!)
  expect(chart).not.toHaveBeenCalled()
  complete(Response.json({ read_only: true, features: { minute_chart: { available: true, timeout_seconds: 30 } } }))
  await waitFor(() => expect(chart).toHaveBeenCalledWith('688170.SH', '1m', '000300.SH', expect.any(AbortSignal), 2000, '', 30700))
})

test('实际外壳选择候选后直接读取对应分钟图，同页选择另一证券也切换', async () => {
  const chart = vi.mocked(fetchMarketChart).mockImplementation(async symbol => ({ schema_version: '1.0', symbol, period: '1m', data_available: false, candles: [] }))
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url === '/v1/ui/capabilities') return Response.json({ read_only: true, features: { minute_chart: { available: true, timeout_seconds: 30 } } })
    if (url.startsWith('/v1/ui/securities/search?')) {
      const first = url.includes('68817')
      const code = first ? '688170' : '600000'
      return Response.json({ schema_version: 'guanheng.security-search.v1', query: first ? '68817' : 'pfyh',
        catalog_id: 'a'.repeat(64), generated_at: '2026-11-01T01:00:00Z', results: [{ symbol: `${code}.SH`, code,
          exchange: 'SH', name: first ? '德龙激光' : '浦发银行', security_type: 'stock',
          pinyin_initials: first ? 'dljg' : 'pfyh', pinyin_full: first ? 'delongjiguang' : 'pufayinhang', match: 'code' }] })
    }
    throw new Error('unexpected source request')
  }))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client)
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/market']}><IndependentApp /></MemoryRouter></QueryClientProvider>)
  await screen.findByRole('heading', { name: '行情', level: 1 }, { timeout: 5000 })
  const input = await screen.findByRole('combobox', { name: '全局证券搜索' })
  fireEvent.change(input, { target: { value: '68817' } })
  fireEvent.click(await screen.findByRole('option', { name: /德龙激光/ }))
  await waitFor(() => expect(chart).toHaveBeenCalledWith('688170.SH', '1m', '000300.SH', expect.any(AbortSignal), 2000, '', 30700))
  expect(screen.getByRole('textbox', { name: '证券代码' })).toHaveValue('688170.SH')
  fireEvent.change(input, { target: { value: 'pfyh' } })
  fireEvent.click(await screen.findByRole('option', { name: /浦发银行/ }))
  await waitFor(() => expect(chart).toHaveBeenLastCalledWith('600000.SH', '1m', '000300.SH', expect.any(AbortSignal), 2000, '', 30700))
  expect(screen.getByRole('textbox', { name: '证券代码' })).toHaveValue('600000.SH')
  // 页内改读另一只，再次选择URL中原来的证券，仍应切回。
  fireEvent.change(screen.getByRole('textbox', { name: '证券代码' }), { target: { value: '688170.SH' } })
  fireEvent.click(await screen.findByRole('button', { name: '读取分钟线' }))
  await waitFor(() => expect(chart).toHaveBeenLastCalledWith('688170.SH', '1m', '000300.SH', expect.any(AbortSignal), 2000, '', 30700))
  fireEvent.change(input, { target: { value: 'pfyh' } })
  fireEvent.focus(input)
  fireEvent.click(await screen.findByRole('option', { name: /浦发银行/ }))
  expect(await screen.findByRole('textbox', { name: '证券代码' })).toHaveValue('600000.SH')
})
