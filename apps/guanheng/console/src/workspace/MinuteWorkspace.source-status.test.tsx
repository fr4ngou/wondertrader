import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import MinuteWorkspace from './MinuteWorkspace'
import { fetchMarketChart } from '../api'
import type { MarketChartBundle } from '../types'
vi.mock('../api',async original=>({...await original<typeof import('../api')>(),fetchMarketChart:vi.fn()}))
vi.mock('../components/MarketCandlestickChart',()=>({MarketCandlestickChart:()=> <div role="img" aria-label="行情图"/>}))
vi.mock('./PersonalWatchlist',()=>({default:()=>null,useSecurityIdentity:()=>({data:{name:'测试证券'}})}))
vi.mock('./usePersonalWatchlist',()=>({usePersonalWatchlist:()=>({symbols:[],canEdit:false,full:false})}))
const clients:QueryClient[]=[]
afterEach(()=>{cleanup();clients.splice(0).forEach(client=>client.clear());vi.resetAllMocks()})
// 同一主页面既保留真实历史缺口和等待状态，又移除来源折叠说明。
test.each([['Pending','正在更新历史数据'],['Unknown','历史数据更新结果待确认'],['Unavailable','历史数据暂时无法补齐'],['Budget','本次历史数据更新已暂停']] as const)('行情精简后保留%s补齐状态',async(preparation_state,message)=>{
 vi.mocked(fetchMarketChart).mockResolvedValue({schema_version:'1.7',symbol:'510300.SH',period:'1d',data_available:true,
  candles:[{occurred_at:'2026-11-02T07:00:00Z',open:10,high:11,low:9,close:10.5,volume:12}],
  source_observation:{source_schema:'qmt.source-selection-observation.v1',state:'Partial',source_window:{from_at:'2026-11-02T07:00:00Z',to_at:'2026-11-02T07:00:00Z'},
   source_rows:1,requested_limit:60,selected_rows:1,preparation_state,preparation_request_id:null}} as MarketChartBundle)
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}});clients.push(client)
 render(<QueryClientProvider client={client}><MemoryRouter><MinuteWorkspace initialSearch="510300.SH" capability={{available:true,periods:['1d'],reason:null}}/></MemoryRouter></QueryClientProvider>)
 expect(await screen.findByText('部分历史行情缺失，当前显示已取得的数据。')).toBeVisible()
 expect(screen.getByText(new RegExp(message))).toBeVisible()
 expect(screen.getByRole('img',{name:'行情图'})).toBeVisible()
 expect(screen.queryByText('数据来源')).toBeNull()
})
