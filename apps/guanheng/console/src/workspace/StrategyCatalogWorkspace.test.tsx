import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import StrategyCatalogWorkspace from './StrategyCatalogWorkspace'
vi.mock('./StrategyDetails',()=>({default:({strategy}:{strategy:{strategy_id:string}})=><p>运行归属：{strategy.strategy_id}</p>}))
const clients:QueryClient[]=[]
const catalog={schema:'guanheng.strategy-catalog.v1',read_only:true,scope:'registered-definitions',strategies:[
 {strategy_id:'resonance-regime-v1',strategy_version:'1.1.2',display_name:'共振策略',description:'计算市场状态与目标权重。',historical_versions:[]},
 {strategy_id:'other',strategy_version:'2.0',display_name:'第二策略',description:'第二策略简介',historical_versions:[]}]}
afterEach(()=>{cleanup();clients.splice(0).forEach(client=>client.clear());vi.unstubAllGlobals()})
function mount(){const client=new QueryClient({defaultOptions:{queries:{retry:false}}});clients.push(client);render(<QueryClientProvider client={client}><MemoryRouter><StrategyCatalogWorkspace/></MemoryRouter></QueryClientProvider>)}
test('显式策略选择决定唯一运行详情和回测链接，简介可查看',async()=>{
 const fetch=vi.fn().mockResolvedValue(Response.json(catalog));vi.stubGlobal('fetch',fetch);mount()
 expect(await screen.findByLabelText('选择策略')).toBeVisible()
 await screen.findByText('运行归属：resonance-regime-v1')
 expect(screen.getByRole('link',{name:'查看该策略回测 →'})).toHaveAttribute('href','/backtests?strategy=resonance-regime-v1%401.1.2')
 fireEvent.change(screen.getByLabelText('选择策略'),{target:{value:'other@2.0'}})
 expect(await screen.findByText('运行归属：other')).toBeVisible()
 expect(screen.queryByText('运行归属：resonance-regime-v1')).toBeNull()
 fireEvent.click(screen.getByRole('button',{name:'策略说明'}))
 expect(screen.getByText('第二策略简介')).toBeVisible()
 expect(screen.getByRole('link',{name:'查看该策略回测 →'})).toHaveAttribute('href','/backtests?strategy=other%402.0')
 expect(fetch.mock.calls.every(call=>call[0]==='/v1/ui/strategy-catalog'&&(call[1]?.method??'GET')==='GET')).toBe(true)
})
test('读取失败后手动恢复，空目录明确展示',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(Response.json({},{status:503})).mockResolvedValueOnce(Response.json({...catalog,strategies:[]})))
 mount();expect(await screen.findByRole('alert')).toHaveTextContent('策略目录读取失败')
 fireEvent.click(screen.getByRole('button',{name:'重新读取策略'}))
 expect(await screen.findByText('当前没有登记策略。')).toBeVisible()
})
test('切换原版研究条目展示归一化模型且不读取当前账户详情',async()=>{
 const original={strategy_id:'resonance-original-351f9d5-stable',strategy_version:'0.1.0a1',display_name:'共振原版（原组合对照）',description:'原stable组合对照',historical_versions:[]}
 const fetch=vi.fn().mockResolvedValue(Response.json({...catalog,strategies:[...catalog.strategies,original]}));vi.stubGlobal('fetch',fetch);mount()
 await screen.findByText('运行归属：resonance-regime-v1')
 fireEvent.change(screen.getByLabelText('选择策略'),{target:{value:original.strategy_id+'@'+original.strategy_version}})
 expect(await screen.findByText('原版研究与回测')).toBeVisible()
 expect(screen.queryByText('运行归属：resonance-regime-v1')).toBeNull()
 expect(screen.getByText(/初始归一化权益为 1/)).toBeVisible()
 expect(fetch.mock.calls.every(call=>call[0]==='/v1/ui/strategy-catalog')).toBe(true)
})
