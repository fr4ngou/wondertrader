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

test('直达日线等能力后再读取，手动刷新共用预算，日周月传真实范围', async () => {
  let complete!: (value: Response) => void
  const capability = new Promise<Response>(resolve => { complete = resolve })
  const chart = vi.mocked(fetchMarketChart).mockImplementation(async symbol => ({ schema_version: '1.0', symbol, period: '1d', data_available: false, candles: [] }))
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => String(input) === '/v1/ui/capabilities' ? capability : Promise.reject(new Error('目录暂不可用'))))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client)
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/market?search=300308.SZ']}><IndependentApp /></MemoryRouter></QueryClientProvider>)
  const refresh = await screen.findByRole('button', { name: '刷新' })
  expect(chart).not.toHaveBeenCalled(); expect(refresh).toBeDisabled(); fireEvent.click(refresh); expect(chart).not.toHaveBeenCalled()
  complete(Response.json({ read_only: true, features: { minute_chart: { available: true, timeout_seconds: 30 } } }))
  await waitFor(() => expect(chart).toHaveBeenCalledWith('300308.SZ', '1d', undefined, expect.any(AbortSignal), 60, undefined, 30700, undefined))
  expect(screen.getByRole('button', { name: '日线' })).toHaveAttribute('aria-pressed', 'true')
  fireEvent.click(screen.getByRole('button', { name: '5日' }))
  await waitFor(() => expect(chart).toHaveBeenLastCalledWith('300308.SZ', '1d', undefined, expect.any(AbortSignal), 5, undefined, 30700, undefined))
  fireEvent.keyDown(window, { key: 'w' })
  await waitFor(() => expect(chart).toHaveBeenLastCalledWith('300308.SZ', '1w', undefined, expect.any(AbortSignal), 2000, undefined, 30700, { dailyLimit: 5 }))
  fireEvent.click(screen.getByRole('button', { name: '2年' }))
  await waitFor(() => expect(chart).toHaveBeenLastCalledWith('300308.SZ', '1w', undefined, expect.any(AbortSignal), 2000, undefined, 30700, { years: 2 }))
})
test('唯一自动搜索选择ETF，快捷键不抢输入', async () => {
  const chart = vi.mocked(fetchMarketChart).mockImplementation(async symbol => ({ schema_version: '1.0', symbol, period: '1d', data_available: false, candles: [] }))
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url === '/v1/ui/capabilities') return Response.json({ read_only: true, features: { minute_chart: { available: true, timeout_seconds: 30 } } })
    if (url.startsWith('/v1/ui/securities/search?')) return Response.json({ schema_version: 'guanheng.security-search.v1', query: '588170',
      catalog_id: 'a'.repeat(64), generated_at: '2026-11-01T01:00:00Z', results: [{ symbol: '588170.SH', code: '588170', exchange: 'SH', name: '科创半导体ETF',
      security_type: 'etf', pinyin_initials: 'kcbdtetf', pinyin_full: 'kechuangbandaotietf', match: 'code' }] })
    throw new Error('unexpected source request')
  }))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client)
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/market']}><IndependentApp /></MemoryRouter></QueryClientProvider>)
  const input = await screen.findByRole('combobox', { name: '全局证券搜索' })
  expect(screen.getAllByRole('combobox')).toHaveLength(1); expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  fireEvent.keyDown(window, { key: '/' }); expect(input).toHaveFocus(); fireEvent.change(input, { target: { value: '588170' } })
  fireEvent.click(await screen.findByRole('option', { name: /科创半导体ETF/ }))
  await waitFor(() => expect(chart).toHaveBeenCalledWith('588170.SH', '1d', undefined, expect.any(AbortSignal), 60, undefined, 30700, undefined))
  expect(await screen.findByRole('heading', { name: '科创半导体ETF' })).toBeVisible()
  fireEvent.keyDown(input, { key: 'm' }); expect(screen.getByRole('button', { name: '日线' })).toHaveAttribute('aria-pressed', 'true')
  fireEvent.keyDown(window, { key: 'm' })
  await waitFor(() => expect(chart).toHaveBeenLastCalledWith('588170.SH', '1mo', undefined, expect.any(AbortSignal), 2000, undefined, 30700, { dailyLimit: 60 }))
})

test('模糊查询深链进入唯一搜索并列候选，明确选择后才查询规范证券', async () => {
 const chart=vi.mocked(fetchMarketChart).mockImplementation(async symbol=>({schema_version:'1.0',symbol,period:'1d',data_available:false,candles:[]}))
 vi.stubGlobal('fetch',vi.fn(async(input:RequestInfo|URL)=>{
  const url=String(input)
  if(url==='/v1/ui/capabilities')return Response.json({read_only:true,features:{minute_chart:{available:true,periods:['1d'],reason:null}}})
  if(url.includes('/securities/search?'))return Response.json({schema_version:'guanheng.security-search.v1',query:'68817',catalog_id:'a'.repeat(64),generated_at:'2026-11-01T00:00:00Z',results:[0,1].map(i=>({symbol:`68817${i}.SH`,code:`68817${i}`,exchange:'SH',name:`测试证券${i}`,security_type:'stock',pinyin_initials:'cszq',pinyin_full:'ceshizhengquan',match:'code'}))})
  throw new Error('unexpected source request')
 }))
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}});clients.push(client)
 render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/market?search=68817']}><IndependentApp/></MemoryRouter></QueryClientProvider>)
 expect(await screen.findByRole('combobox',{name:'全局证券搜索'})).toHaveValue('68817')
 await screen.findByRole('option',{name:/测试证券0/});expect(chart).not.toHaveBeenCalled()
 fireEvent.submit(screen.getByRole('search',{name:'证券搜索'}));expect(chart).not.toHaveBeenCalled()
 fireEvent.click(screen.getByRole('option',{name:/测试证券1/}));await waitFor(()=>expect(chart).toHaveBeenCalledWith('688171.SH','1d',undefined,expect.any(AbortSignal),60,undefined,6500,undefined))
})

test('晚到自选只补默认图表，保留正在IME组词的搜索草稿',async()=>{
 let finish!: (value:Response)=>void;const late=new Promise<Response>(resolve=>{finish=resolve})
 vi.mocked(fetchMarketChart).mockResolvedValue({schema_version:'1.0',symbol:'600000.SH',period:'1d',data_available:false,candles:[]})
 vi.stubGlobal('fetch',vi.fn(async(input:RequestInfo|URL)=>{
  if(String(input)==='/v1/ui/capabilities')return Response.json({read_only:true,features:{minute_chart:{available:true,periods:['1d'],reason:null},personal_watchlist:{available:true,editable:true,max_items:100,scope:'personal-observation',affects_strategy:false,reason:null}}})
  if(String(input)==='/v1/ui/watchlists/default')return late
  return new Response('',{status:503})
 }))
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}});clients.push(client)
 render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/market']}><IndependentApp/></MemoryRouter></QueryClientProvider>)
 const input=await screen.findByRole('combobox',{name:'全局证券搜索'});fireEvent.compositionStart(input);fireEvent.change(input,{target:{value:'浦发'}})
 finish(Response.json({schema_version:'guanheng.personal-watchlist.v1',watchlist_id:'12345678-1234-4234-8234-123456789abc',version:1,symbols:['600000.SH'],updated_at:'2026-11-01T00:00:00Z',affects_strategy:false,editable:true,reason:null}))
 await waitFor(()=>expect(fetchMarketChart).toHaveBeenCalled());expect(input).toHaveValue('浦发');fireEvent.compositionEnd(input);expect(input).toHaveValue('浦发')
})
