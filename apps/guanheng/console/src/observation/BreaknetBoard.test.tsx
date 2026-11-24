import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import ObservationShell from './ObservationShell'

const api = vi.hoisted(()=>({series:vi.fn(),download:vi.fn()}))
const coverage = {start:'2023-11-24',end:'2026-11-24',observations:726}
const definition = {id:'valuation.breaknet',board:'breaknet',label:'破净率、家数与5日变化',frequency:'交易日日频',
  coverage,parameters:false,primary_field:'ratio',unit:'%',source:'测试同源PB',formula:'测试公式',reading:'测试读法',limitations:[],
  lines:[{key:'ratio',name:'破净率',unit:'%',panel:'main',shown:true,color:'#123456',formula:'',reading:''}],
  field_schema:{date:{label:'日期'},ratio:{label:'破净率',unit:'%'}}}
vi.mock('./ObservationChart',()=>({ObservationChart:()=> <div>破净图已读取</div>}))
vi.mock('./api',()=>({
  getCatalog:async()=>({snapshot_id:'a'.repeat(64),published_at:'2026-11-24T10:00:00Z',boards:[{id:'breaknet',label:'破净观察'}],
    datasets:[{...definition,dataset_version:'b'.repeat(64)}],preferences:{default_board:'breaknet',default_datasets:{breaknet:'valuation.breaknet'}}}),
  getDefinition:async()=>({definition}),
  getHistory:async()=>({coverage,points:[],aggregation:'none',raw_count:726}),
  getSeries:(...args:unknown[])=>{api.series(...args);return Promise.resolve({definition,rows:[{date:'2026-11-24',ratio:20}],total:1,next_cursor:null})},
  read:async()=>({scheduler:{enabled:false},runs:[]}),
  apiURL:(_path:string,params:Record<string,string>)=>'/export?'+new URLSearchParams(params),
  downloadObservation:(...args:unknown[])=>{api.download(...args);return Promise.reject(new Error('测试下载已记录'))},
}))
let query:QueryClient
afterEach(()=>{cleanup();query?.clear();vi.clearAllMocks()})
it('主板与科创板一键切换，导出继承所选板块和快照',async()=>{
  query=new QueryClient({defaultOptions:{queries:{retry:false}}})
  render(<QueryClientProvider client={query}><MemoryRouter initialEntries={['/observation?metric=valuation.breaknet']}><ObservationShell /></MemoryRouter></QueryClientProvider>)
  await screen.findByText('破净图已读取')
  expect(screen.getByRole('button',{name:'主板'})).toHaveAttribute('aria-pressed','true')
  fireEvent.click(screen.getByRole('button',{name:'科创板'}))
  await waitFor(()=>expect(api.series).toHaveBeenLastCalledWith('valuation.breaknet','a'.repeat(64),expect.objectContaining({segments:'star'}),expect.anything()))
  fireEvent.click(screen.getByRole('button',{name:'创业板'}))
  await waitFor(()=>expect(api.series).toHaveBeenLastCalledWith('valuation.breaknet','a'.repeat(64),expect.objectContaining({segments:'chinext'}),expect.anything()))
  fireEvent.click(screen.getByRole('button',{name:'导出当前CSV'}))
  await waitFor(()=>expect(api.download).toHaveBeenCalledWith(expect.objectContaining({metric_id:'valuation.breaknet',snapshot_id:'a'.repeat(64),segments:'chinext'}),expect.anything()))
})

it('开启多选后合并统计，退出多选后恢复一键切换',async()=>{
  query=new QueryClient({defaultOptions:{queries:{retry:false}}})
  render(<QueryClientProvider client={query}><MemoryRouter initialEntries={['/observation?metric=valuation.breaknet']}><ObservationShell /></MemoryRouter></QueryClientProvider>)
  await screen.findByText('破净图已读取')
  fireEvent.click(screen.getByRole('switch',{name:'多选'}))
  fireEvent.click(screen.getByRole('button',{name:'科创板'}))
  await waitFor(()=>expect(api.series).toHaveBeenLastCalledWith('valuation.breaknet','a'.repeat(64),expect.objectContaining({segments:'main,star'}),expect.anything()))
  fireEvent.click(screen.getByRole('button',{name:'主板'}))
  await waitFor(()=>expect(api.series).toHaveBeenLastCalledWith('valuation.breaknet','a'.repeat(64),expect.objectContaining({segments:'star'}),expect.anything()))
  expect(screen.getByRole('button',{name:'科创板'})).toBeDisabled()
  fireEvent.click(screen.getByRole('switch',{name:'多选'}))
  fireEvent.click(screen.getByRole('button',{name:'主板'}))
  await waitFor(()=>expect(api.series).toHaveBeenLastCalledWith('valuation.breaknet','a'.repeat(64),expect.objectContaining({segments:'main'}),expect.anything()))
})

it('旧多板块链接恢复多选，退出后保留一个板块',async()=>{
  query=new QueryClient({defaultOptions:{queries:{retry:false}}})
  render(<QueryClientProvider client={query}><MemoryRouter initialEntries={['/observation?metric=valuation.breaknet&segments=main,star']}><ObservationShell /></MemoryRouter></QueryClientProvider>)
  await screen.findByText('破净图已读取')
  expect(screen.getByRole('switch',{name:'多选'})).toHaveAttribute('aria-checked','true')
  fireEvent.click(screen.getByRole('switch',{name:'多选'}))
  await waitFor(()=>expect(api.series).toHaveBeenLastCalledWith('valuation.breaknet','a'.repeat(64),expect.objectContaining({segments:'main'}),expect.anything()))
  expect(screen.getByRole('button',{name:'科创板'})).toBeEnabled()
})
