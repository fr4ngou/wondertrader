import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import ObservationShell from './ObservationShell'
import type { Definition } from './types'

const api=vi.hoisted(()=>({series:vi.fn(),download:vi.fn()}))
const coverage={start:'2023-01-01',end:'2026-11-24',observations:726}
const definitions=Object.fromEntries([
  ['pb_shsz_daily','pb','沪深日频原名','equal_pb'],['pb_all','pb','全A原名','equal_pb'],
  ['pb_sw_daily','pb','申万加权','equal_pb'],
  ['valuation_marketcap_gdp_latest','valuation','全A页面快照','ratio'],
  ['valuation_marketcap_gdp_monthly','valuation','沪深月末含B','ratio'],
  ['valuation_marketcap_gdp_observed','valuation','沪深关键日','ratio'],
  ['csi300_daily.reference','valuation','沪深300原名','close'],
].map(([id,board,label,field])=>[id,{id,board,label,coverage,frequency:'实际频率',parameters:false,
  primary_field:field,unit:'倍',source:'测试',source_url:'https://example.invalid/fixture',field_schema:{date:{label:'日期'},[field]:{label:'值',unit:'倍'}},
  lines:[{key:field,name:'主线',unit:'倍',panel:'main',shown:true,formula:'测试',reading:'测试',color:'#2768b2'},
    {key:'sse_reference',name:'上证指数',unit:'指数点',panel:'context',shown:true,formula:'测试',reading:'测试',color:'#c65761'},
    {key:'reference',name:'旧参考',unit:'指数点',panel:'context',shown:false,formula:'测试',reading:'测试',color:'#888888'}],
  limitations:[],reading:'测试',formula:'测试'} as Definition]))
vi.mock('./ObservationChart',()=>({ObservationChart:({definition}:{definition:Definition})=><div data-testid="chart-lines">{definition.lines.map(line=>line.key).join(',')}</div>}))
vi.mock('./api',()=>({
  getCatalog:async()=>({snapshot_id:'a'.repeat(64),published_at:'2026-11-24T10:00:00Z',
    boards:[{id:'pb',label:'等权 PB'},{id:'valuation',label:'市值 / GDP'}],
    datasets:Object.values(definitions).map(d=>({...d,dataset_version:'b'.repeat(64)})),
    preferences:{default_board:'pb',default_datasets:{pb:'pb_sw_daily',valuation:'valuation_marketcap_gdp_observed'}}}),
  getDefinition:async(id:string)=>({definition:definitions[id]}),
  getHistory:async()=>({coverage,points:[],aggregation:'none',raw_count:726}),
  getSeries:(id:string,...args:unknown[])=>{api.series(id,...args);return Promise.resolve({definition:definitions[id],rows:[{date:'2026-11-24',equal_pb:3,ratio:.8,close:4000,marketcap_trillion:112,gdp_trillion:140,gdp_year:2025}],total:1,next_cursor:null})},
  read:async()=>({scheduler:{enabled:false},runs:[]}),
  apiURL:(_path:string,params:Record<string,string>)=>'/export?'+new URLSearchParams(params),
  downloadObservation:(...args:unknown[])=>{api.download(...args);return Promise.reject(new Error('下载参数已记录'))},
}))
let query:QueryClient
async function open(metric:string) {
  query=new QueryClient({defaultOptions:{queries:{retry:false}}})
  render(<QueryClientProvider client={query}><MemoryRouter initialEntries={['/observation?metric='+metric+'&start=2023-11-24&end=2026-11-24&preset=y3']}><ObservationShell /></MemoryRouter></QueryClientProvider>)
  await screen.findByTestId('chart-lines')
  return within(screen.getByRole('group',{name:'观察内容'}))
}
afterEach(()=>{cleanup();query?.clear();vi.clearAllMocks()})
it('等权PB仅两个按钮，一击切换并保留导出日期、口径和快照',async()=>{
  const buttons=await open('pb_shsz_daily')
  expect(buttons.getAllByRole('button')).toHaveLength(2)
  expect(screen.queryByRole('combobox',{name:'观察口径'})).toBeNull()
  expect(screen.queryByText(/申万加权/)).toBeNull()
  expect(screen.getByTestId('chart-lines')).toHaveTextContent('equal_pb,sse_reference')
  fireEvent.click(buttons.getByRole('button',{name:'全A等权 PB（月末）'}))
  await waitFor(()=>expect(api.series).toHaveBeenLastCalledWith('pb_all','a'.repeat(64),expect.objectContaining({start:'2023-11-24',end:'2026-11-24'}),expect.anything()))
  fireEvent.click(await screen.findByRole('button',{name:'导出当前CSV'}))
  await waitFor(()=>expect(api.download).toHaveBeenCalledWith(expect.objectContaining({metric_id:'pb_all',snapshot_id:'a'.repeat(64),start:'2023-11-24',end:'2026-11-24'}),expect.anything()))
})
it.each(['valuation_marketcap_gdp_monthly','csi300_daily.reference'])('市值和GDP比例同图展示，旧链接%s回到全A',async metric=>{
  query=new QueryClient({defaultOptions:{queries:{retry:false}}})
  render(<QueryClientProvider client={query}><MemoryRouter initialEntries={['/observation?metric='+metric+'&preset=y3']}><ObservationShell /></MemoryRouter></QueryClientProvider>)
  expect(await screen.findByTestId('chart-lines')).toHaveTextContent(/^ratio,marketcap_trillion$/)
  expect(screen.queryByRole('group',{name:'观察内容'})).toBeNull()
  expect(screen.queryByRole('combobox',{name:'观察口径'})).toBeNull()
  expect(screen.queryByRole('button',{name:'沪深300走势'})).toBeNull()
  expect(screen.getByText(/全A总市值/,{selector:'.observation-valuation-formula'})).toHaveTextContent('112 万亿元 ÷ 2025年GDP 140 万亿元 = 80%')
  expect(api.series).toHaveBeenLastCalledWith('valuation_marketcap_gdp_latest','a'.repeat(64),expect.anything(),expect.anything())
})
it('旧申万链接回到沪深等权，保持实际数据身份',async()=>{
  const buttons=await open('pb_sw_daily')
  expect(buttons.getByRole('button',{name:'沪深等权 PB（日线）'})).toHaveAttribute('aria-pressed','true')
  expect(api.series).toHaveBeenLastCalledWith('pb_shsz_daily','a'.repeat(64),expect.anything(),expect.anything())
})
