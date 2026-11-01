import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import PersonalWatchlist from './PersonalWatchlist'
import { usePersonalWatchlist } from './usePersonalWatchlist'
const clients:QueryClient[]=[]
afterEach(()=>{cleanup();clients.splice(0).forEach(c=>c.clear());vi.unstubAllGlobals()})
test('100项自选按可见行读取，单行失败明确显示且可重试',async()=>{
 let observed=0;vi.stubGlobal('IntersectionObserver',class {constructor(private callback:IntersectionObserverCallback){} observe(target:Element){this.callback([{target,isIntersecting:observed++<4} as IntersectionObserverEntry],this as unknown as IntersectionObserver)} disconnect(){}})
 const symbols=Array.from({length:100},(_,i)=>`${600000+i}.SH`);const urls:string[]=[];let failed=false
 vi.stubGlobal('fetch',vi.fn(async(input:RequestInfo|URL)=>{const url=String(input);urls.push(url)
  if(url==='/v1/ui/watchlists/default')return Response.json({schema_version:'guanheng.personal-watchlist.v1',watchlist_id:'12345678-1234-4234-8234-123456789abc',version:1,symbols,updated_at:'2026-11-01T00:00:00Z',affects_strategy:false,editable:true,reason:null})
  if(url.includes('/securities/search?')){const symbol=new URL(url,'http://test').searchParams.get('query')!;return Response.json({schema_version:'guanheng.security-search.v1',query:symbol,catalog_id:'a'.repeat(64),generated_at:'2026-11-01T00:00:00Z',results:[{symbol,code:symbol.slice(0,6),exchange:'SH',name:`测试证券${symbol.slice(0,6)}`,security_type:'stock',pinyin_initials:'cszq',pinyin_full:'ceshizhengquan',match:'code'}]})}
  if(url.includes('/chart/600001.SH')&&!failed){failed=true;return new Response('',{status:503})}
  if(url.includes('/chart/'))return Response.json({schema_version:'1.6',data_available:true,candles:Array.from({length:5},(_,i)=>({close:10+i}))})
  throw new Error('unexpected request')
 }))
 function View(){const model=usePersonalWatchlist({available:true,editable:true,max_items:100,scope:'personal-observation',affects_strategy:false,reason:null});return <PersonalWatchlist model={model} selected="600000.SH" onView={vi.fn()} ready dailySupported timeoutMs={6500}/>}
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}});clients.push(client);render(<QueryClientProvider client={client}><View/></QueryClientProvider>)
 const retry=await screen.findByRole('button',{name:'重试 600001.SH 的名称和小图'});expect(screen.getByText('读取失败')).toBeVisible()
 await waitFor(()=>expect(screen.getAllByRole('img')).toHaveLength(3));expect(urls.some(url=>url.includes('600099'))).toBe(false)
 expect(screen.getByText('测试证券600000')).toBeVisible();fireEvent.click(retry);await waitFor(()=>expect(screen.getAllByRole('img')).toHaveLength(4));expect(screen.queryByText('读取失败')).toBeNull()
})
