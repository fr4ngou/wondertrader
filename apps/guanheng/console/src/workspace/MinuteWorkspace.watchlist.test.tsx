import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, useLocation } from 'react-router-dom'
import MinuteWorkspace from './MinuteWorkspace'
vi.mock('../components/MarketCandlestickChart',()=>({MarketCandlestickChart:({bundle}:{bundle?:{symbol:string}})=>bundle?<div role="img" aria-label={`主图 ${bundle.symbol}`}/>:null}))
const clients:QueryClient[]=[]
afterEach(()=>{cleanup();clients.splice(0).forEach(c=>c.clear());vi.unstubAllGlobals()})
const cap={available:true,editable:true,max_items:100,scope:'personal-observation',affects_strategy:false,reason:null}
const snapshot=(symbols=['600000.SH'],version=1)=>({schema_version:'guanheng.personal-watchlist.v1',watchlist_id:'12345678-1234-4234-8234-123456789abc',version,symbols,updated_at:`2026-10-23T01:0${version}:00Z`,affects_strategy:false,editable:true,reason:null})
function Workspace(){const location=useLocation();return <MinuteWorkspace capability={{available:true,periods:['1d'],reason:null}} watchlistCapability={cap} initialSearch={new URLSearchParams(location.search).get('search')??''}/>}
function mount(){const c=new QueryClient({defaultOptions:{queries:{retry:false}}});clients.push(c);render(<QueryClientProvider client={c}><MemoryRouter initialEntries={['/market?search=600000.SH']}><Workspace/></MemoryRouter></QueryClientProvider>)}
test('星标偏好增减使用规范身份，移出当前证券保留主图和查询',async()=>{
 let stored=snapshot();const calls:{url:string;method:string}[]=[]
 vi.stubGlobal('fetch',vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{const url=String(input),method=init?.method??'GET';calls.push({url,method})
  if(url==='/v1/ui/watchlists/default'){if(method==='PUT'){stored=snapshot(JSON.parse(String(init?.body)).symbols,stored.version+1);return Response.json({schema_version:stored.schema_version,changed:true,watchlist:stored})}return Response.json(stored)}
  if(url.includes('/chart/'))return Response.json({schema_version:'1.6',symbol:'600000.SH',period:'1d',data_available:true,candles:[{occurred_at:'2026-10-23T00:00:00+08:00',open:3,high:3.1,low:2.9,close:3,volume:10}]})
  return new Response('',{status:503})
 }))
 mount();await screen.findByRole('img',{name:'主图 600000.SH'});await waitFor(()=>expect(screen.getByRole('button',{name:'已加入自选'})).toBeEnabled())
 fireEvent.click(screen.getByRole('button',{name:'已加入自选'}));await waitFor(()=>expect(screen.getByRole('button',{name:'加入自选'})).toBeEnabled())
 expect(screen.getByRole('img',{name:'主图 600000.SH'})).toBeVisible();fireEvent.click(screen.getByRole('button',{name:'加入自选'}));await waitFor(()=>expect(stored.symbols).toEqual(['600000.SH']))
 expect(calls.filter(c=>c.url.includes('/chart/')&&c.url.includes('limit=60'))).toHaveLength(1);expect(calls.filter(c=>c.method==='PUT')).toHaveLength(2)
})
test('自选读取失败只影响偏好，规范日线仍可读取',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(input:RequestInfo|URL)=>String(input).includes('/chart/')?Response.json({schema_version:'1.6',symbol:'600000.SH',period:'1d',data_available:true,candles:[]}):new Response('',{status:503})))
 mount();await screen.findByRole('img',{name:'主图 600000.SH'});expect(await screen.findByText('自选读取失败')).toBeVisible();expect(screen.getByRole('button',{name:'加入自选'})).toBeDisabled()
})
