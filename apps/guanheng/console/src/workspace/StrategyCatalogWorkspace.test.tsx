import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import StrategyCatalogWorkspace from './StrategyCatalogWorkspace'
vi.mock('./StrategyDetails',()=>({default:({strategy}:{strategy:{strategy_id:string}})=><p>运行归属：{strategy.strategy_id}</p>}))
const runtime = vi.hoisted(() => ({ online: false }))
vi.mock('./liveStrategyApi', () => ({ useLiveStrategyPerformance: (strategy?: {strategy_id:string}) => ({
 data: { state: runtime.online && strategy?.strategy_id === 'resonance-regime-v1' ? 'available' : 'not_current',
 current: { is_current: runtime.online && strategy?.strategy_id === 'resonance-regime-v1', key_matches: runtime.online && strategy?.strategy_id === 'resonance-regime-v1', scope_id: 'synthetic' }, coverage: {history_scope_id:'synthetic'} },
 isError: false, isPending: false, refetch: vi.fn() }) }))
vi.mock('./LiveStrategyPerformance', () => ({ default: () => <p>实际线上观察图表</p> }))
const clients:QueryClient[]=[]
const catalog={schema:'guanheng.strategy-catalog.v1',read_only:true,scope:'registered-definitions',strategies:[
 {strategy_id:'resonance-regime-v1',strategy_version:'1.1.2',display_name:'共振策略',description:'计算市场状态与目标权重。',historical_versions:[]},
 {strategy_id:'other',strategy_version:'2.0',display_name:'第二策略',description:'第二策略简介',historical_versions:[]}]}
afterEach(()=>{cleanup();clients.splice(0).forEach(client=>client.clear());vi.unstubAllGlobals();runtime.online=false})
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
test('WT原版只展示原生撮合，不保留非WT对照入口',async()=>{
 const original={strategy_id:'resonance-original-wt-351f9d5-stable',strategy_version:'0.1.0a1',display_name:'共振原版（WT回测）',description:'WT原版回测',historical_versions:[]}
 const fetch=vi.fn().mockResolvedValue(Response.json({...catalog,strategies:[...catalog.strategies,original]}));vi.stubGlobal('fetch',fetch);mount()
 await screen.findByText('运行归属：resonance-regime-v1')
 fireEvent.change(screen.getByLabelText('选择策略'),{target:{value:original.strategy_id+'@'+original.strategy_version}})
 expect(await screen.findByText('原版研究与回测')).toBeVisible()
 expect(screen.queryByText('运行归属：resonance-regime-v1')).toBeNull()
 expect(screen.getByText(/WT 框架的历史时钟/)).toBeVisible()
 expect(screen.queryByText(/归一化权益/)).toBeNull()
 expect(fetch.mock.calls.every(call=>call[0]==='/v1/ui/strategy-catalog')).toBe(true)
})

test('精确当前线上策略有标记并默认展示线上图表，切换后清除标记',async()=>{
 runtime.online=true
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json(catalog)));mount()
 expect(await screen.findByText('线上运行 · 已核验')).toBeVisible()
 expect(await screen.findByText('实际线上观察图表')).toBeVisible()
 fireEvent.change(screen.getByLabelText('选择策略'),{target:{value:'other@2.0'}})
 expect(screen.queryByText('线上运行 · 已核验')).toBeNull()
 expect(await screen.findByText('运行归属：other')).toBeVisible()
})
