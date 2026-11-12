import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import StrategyCatalogWorkspace from './StrategyCatalogWorkspace'
vi.mock('./StrategyDetails',()=>({default:({strategy}:{strategy:{strategy_id:string}})=><p>运行归属：{strategy.strategy_id}</p>}))
const runtime = vi.hoisted(() => ({ online: false, offline: '' }))
vi.mock('./liveStrategyApi', () => ({ useLiveStrategyPerformance: (strategy?: {strategy_id:string}) => ({
 data: { state: runtime.online && strategy?.strategy_id === 'resonance-regime-v1' ? 'available' : strategy?.strategy_id === runtime.offline ? 'not_current' : 'waiting',
 reason: '当前WT未发布所选策略身份。',
 current: { is_current: runtime.online && strategy?.strategy_id === 'resonance-regime-v1', key_matches: runtime.online && strategy?.strategy_id === 'resonance-regime-v1', scope_id: 'synthetic' }, coverage: {history_scope_id:'synthetic'} },
 isError: false, isPending: false, refetch: vi.fn() }) }))
vi.mock('./StrategyTargetHistory', () => ({ default: ({ strategy }: { strategy: { strategy_id: string } }) => <p>目标归属：{strategy.strategy_id}</p> }))
vi.mock('./LiveStrategyPerformance', () => ({ default: () => <p>实际线上观察图表</p> }))
const clients:QueryClient[]=[]
const catalog={schema:'guanheng.strategy-catalog.v1',read_only:true,scope:'registered-definitions',strategies:[
 {strategy_id:'resonance-regime-v1',strategy_version:'1.1.2',display_name:'共振策略',description:'计算市场状态与目标权重。',historical_versions:[]},
 {strategy_id:'other',strategy_version:'2.0',display_name:'第二策略',description:'第二策略简介',historical_versions:[]}]}
const emptyArchive = { schema: 'nbw-archive-summary-index-v1', runs: [], invalid_receipts: 0, unarchived_runs: 0, scope: 'fixture' }
function stubCatalog(value: unknown) {
 const fetch = vi.fn(async (path: string, _init?: RequestInit) =>
   Response.json(path === '/v1/ui/strategy-catalog' ? value : emptyArchive))
 vi.stubGlobal('fetch', fetch)
 return fetch
}
afterEach(()=>{cleanup();clients.splice(0).forEach(client=>client.clear());vi.unstubAllGlobals();runtime.online=false;runtime.offline=''})
function mount(){const client=new QueryClient({defaultOptions:{queries:{retry:false}}});clients.push(client);render(<QueryClientProvider client={client}><MemoryRouter><StrategyCatalogWorkspace/></MemoryRouter></QueryClientProvider>)}
test('显式策略选择决定唯一运行详情和回测链接，简介可查看',async()=>{
 const fetch=stubCatalog(catalog);mount()
 expect(await screen.findByLabelText('选择策略')).toBeVisible()
 await screen.findByText('运行归属：resonance-regime-v1')
 expect(screen.getByRole('link',{name:'查看该策略回测 →'})).toHaveAttribute('href','/backtests?strategy=resonance-regime-v1%401.1.2')
 fireEvent.change(screen.getByLabelText('选择策略'),{target:{value:'other'}})
 expect(await screen.findByText('运行归属：other')).toBeVisible()
 expect(screen.queryByText('运行归属：resonance-regime-v1')).toBeNull()
 fireEvent.click(screen.getByRole('button',{name:'策略说明'}))
 expect(screen.getByText('第二策略简介')).toBeVisible()
 expect(screen.getByRole('link',{name:'查看该策略回测 →'})).toHaveAttribute('href','/backtests?strategy=other%402.0')
 expect(fetch.mock.calls.every(call=>(call[1]?.method??'GET')==='GET')).toBe(true)
})
test('读取失败后手动恢复，空目录明确展示',async()=>{
 let first = true
 vi.stubGlobal('fetch',vi.fn(async (path: string) => {
   if (path !== '/v1/ui/strategy-catalog') return Response.json({}, {status: 503})
   if (first) { first = false; return Response.json({}, {status: 503}) }
   return Response.json({...catalog,strategies:[]})
 }))
 mount();expect(await screen.findByRole('alert')).toHaveTextContent('策略目录读取失败')
 fireEvent.click(screen.getByRole('button',{name:'重新读取策略'}))
 expect(await screen.findByText('当前没有登记策略。')).toBeVisible()
})
test.each(['resonance-original-wt-351f9d5-stable', 'new-strategy'])('离线策略 %s 共用页签并按所选身份显示空态', async (id) => {
 const definition = { strategy_id: id, strategy_version: '0.1.0a2', display_name: '已登记策略', description: '所选版本的说明', historical_versions: [] }
 runtime.offline = id
 stubCatalog({...catalog,strategies:[...catalog.strategies,definition]});mount()
 await screen.findByText('运行归属：resonance-regime-v1')
 fireEvent.change(screen.getByLabelText('选择策略'),{target:{value:id}})
 expect(await screen.findByText('当前未在线运行')).toBeVisible()
 expect(screen.getByRole('region',{name:'当前持仓与运行'})).toHaveTextContent('当前WT未发布所选策略身份。')
 expect(screen.queryByText('运行归属：resonance-regime-v1')).toBeNull()
 fireEvent.click(screen.getByRole('button',{name:'线上表现'}))
 expect(screen.getByRole('region',{name:'线上表现'})).toHaveTextContent('当前WT未发布所选策略身份。')
 fireEvent.click(screen.getByRole('button',{name:'目标仓位记录'}))
 expect(await screen.findByText('目标归属：'+id)).toBeVisible()
 fireEvent.click(screen.getByRole('button',{name:'策略说明'}))
 expect(screen.getAllByRole('link',{name:/回测/})).toHaveLength(1)
 expect(screen.getByRole('link',{name:/回测/})).toHaveAttribute('href','/backtests?strategy='+id+'%400.1.0a2')
 expect(screen.getByText(definition.description)).toBeVisible()
 expect(screen.queryByText('原版研究与回测')).toBeNull()
})

test('已登记但尚无WT运行发布的策略可选，显示待启用', async () => {
 const id = 'registered-strategy'
 runtime.offline = id
 stubCatalog({...catalog,strategies:[
   {strategy_id:id,strategy_version:'3.0',display_name:'预登记策略',description:'独立登记',historical_versions:[],catalog_status:'registered'},
   ...catalog.strategies,
 ]})
 mount()
 expect(await screen.findByRole('option',{name:'预登记策略'})).toBeVisible()
 expect(screen.getByRole('option',{name:'v3.0 · 已登记'})).toBeVisible()
 expect(screen.getByText('已登记 · 待启用')).toBeVisible()
 expect(screen.getByRole('region',{name:'当前持仓与运行'})).toHaveTextContent('该策略已登记，等待 WT 发布该版本的运行与持仓记录。')
 expect(screen.queryByText('线上运行 · 已核验')).toBeNull()
 fireEvent.click(screen.getByRole('button',{name:'目标仓位记录'}))
 expect(await screen.findByText('目标归属：'+id)).toBeVisible()
})

test('精确当前线上策略默认展示运行与持仓，仍可打开线上图表和切换策略',async()=>{
 runtime.online=true
 stubCatalog(catalog);mount()
 expect(await screen.findByText('线上运行 · 已核验')).toBeVisible()
 const navigation = screen.getByRole('navigation', { name: '策略详情视图' })
 expect(navigation.querySelector('button')?.textContent).toBe('运行与持仓')
 expect(screen.getByRole('button', { name: '运行与持仓' })).toHaveAttribute('aria-pressed', 'true')
 fireEvent.click(screen.getByRole('button', { name: '线上表现' }))
 expect(await screen.findByText('实际线上观察图表')).toBeVisible()
 fireEvent.click(screen.getByRole('button', { name: '运行与持仓' }))
 fireEvent.change(screen.getByLabelText('选择策略'),{target:{value:'other'}})
 expect(screen.queryByText('线上运行 · 已核验')).toBeNull()
 expect(await screen.findByText('运行归属：other')).toBeVisible()
})
