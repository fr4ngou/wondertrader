import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom'
import MinuteWorkspace from './MinuteWorkspace'
vi.mock('../components/MarketCandlestickChart', () => ({ MarketCandlestickChart: ({bundle}: {bundle?: {symbol:string;period:string;data_available:boolean}}) => bundle?.data_available
  ? <div role="img" aria-label={`${bundle.symbol} ${bundle.period}`} /> : <p>暂无行情</p> }))
const clients: QueryClient[]=[]
afterEach(()=>{cleanup();clients.splice(0).forEach(c=>c.clear());vi.unstubAllGlobals()})
const daily={schema_version:'1.6',symbol:'510300.SH',period:'1d',source_period:'1d',derived:false,data_available:true,as_of:'2026-10-22T16:00:00Z',
 candles:[{occurred_at:'2026-10-22T16:00:00Z',open:4,close:4.1,high:4.2,low:3.9,volume:100}],
 native_source:{provider:'Qmt',qualification:'DevelopmentVerified',timestamp_semantics:'source_date',chart_minute_boundary:'source_date',volume_unit:'unknown'}}
function Workspace({periods}:{periods:string[]}) { const l=useLocation(),navigate=useNavigate();return <><button onClick={()=>navigate('/market?search=600000.SH')}>换证券</button>
 <MinuteWorkspace capability={{available:true,periods,reason:null}} initialSearch={new URLSearchParams(l.search).get('search')??''}/></> }
function mount(periods=['1m','1d','1w','1mo']) {const client=new QueryClient({defaultOptions:{queries:{retry:false}}});clients.push(client)
 return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/market?search=510300.SH']}><Workspace periods={periods}/></MemoryRouter></QueryClientProvider>)}
test('日线默认、来源日期/未知单位、刷新失败保留同查询，恢复仍使用原证券',async()=>{
 let failing=false
 vi.stubGlobal('fetch',vi.fn(async(input:RequestInfo|URL)=>String(input).includes('/chart/') ? failing ? new Response('',{status:503}):Response.json(daily):new Response('',{status:503})))
 mount();await screen.findByRole('img',{name:'510300.SH 1d'})
 expect(screen.getByText(/数据截至 2026-10-23/)).toBeVisible();expect(screen.queryByText(/100 股|100 手/)).toBeNull()
 failing=true;fireEvent.click(screen.getByRole('button',{name:'刷新'}));expect(await screen.findByRole('alert')).toHaveTextContent('当前保留上次结果')
 expect(screen.getByRole('img',{name:'510300.SH 1d'})).toBeVisible()
 failing=false;fireEvent.click(screen.getByRole('button',{name:'刷新'}));await waitFor(()=>expect(screen.queryByRole('alert')).toBeNull())
})
test('新证券空查询不沿用上一只证券成功图',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(input:RequestInfo|URL)=>String(input).includes('/chart/510300.')?Response.json(daily):String(input).includes('/chart/600000.')?
  Response.json({...daily,symbol:'600000.SH',data_available:false,candles:[]}):new Response('',{status:503})))
 mount();await screen.findByRole('img',{name:'510300.SH 1d'});fireEvent.click(screen.getByText('换证券'));await waitFor(()=>expect(screen.queryByRole('img')).toBeNull())
 expect(await screen.findByText('等待行情')).toBeVisible()
})
test('当前日K显示原始快照时间，保留既有图表和日期',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(input:RequestInfo|URL)=>String(input).includes('/chart/')?
  Response.json({...daily,native_source:{...daily.native_source,current_day:{date:20261023,source_at:'2026-10-23T14:59:06+08:00',observed_at:'2026-10-23T07:05:00Z',closed:false}}}):new Response('',{status:503})))
 mount();await screen.findByRole('img',{name:'510300.SH 1d'})
 expect(screen.getByText('当日快照 14:59:06')).toBeVisible()
 expect(screen.getByText(/数据截至 2026-10-23/)).toBeVisible()
})
test('canonical分钟来源以已声明周期启动，保留5分钟入口',async()=>{
 const urls:string[]=[];vi.stubGlobal('fetch',vi.fn(async(input:RequestInfo|URL)=>{const u=String(input);urls.push(u)
  return u.includes('/chart/')?Response.json({...daily,period:new URL(u,'http://test').searchParams.get('period')}):new Response('',{status:503})}))
 mount(['1m','5m']);await screen.findByRole('img',{name:'510300.SH 1m'})
 expect(screen.queryByRole('button',{name:'日线'})).toBeNull();fireEvent.click(screen.getByRole('button',{name:'1分K'}))
 expect(screen.getByRole('button',{name:'1分K'})).toHaveAttribute('aria-pressed','true')
 fireEvent.click(screen.getByRole('button',{name:'5分K'}))
 await screen.findByRole('img',{name:'510300.SH 5m'})
 fireEvent.click(screen.getByRole('button',{name:'最近15分钟'}))
 await screen.findByRole('img',{name:'510300.SH 5m'})
 expect(urls.filter(u=>u.includes('/chart/')).map(u=>{
  const query=new URL(u,'http://test').searchParams
  return [query.get('period'),query.get('limit')]
 })).toEqual([['1m','30'],['5m','6'],['5m','3']])
})
