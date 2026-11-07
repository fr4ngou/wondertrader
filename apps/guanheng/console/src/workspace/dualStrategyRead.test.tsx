import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import StrategyDetails from './StrategyDetails'
import LiveStrategyPerformance from './LiveStrategyPerformance'
import { validateLivePerformance, type LivePerformance } from './liveStrategyApi'
import { validateStrategyRuntime } from './strategyRuntimeApi'
import runtime from './strategy-runtime.fixture.json'
import StrategyCatalogWorkspace from './StrategyCatalogWorkspace'

vi.mock('echarts/core', () => ({ use: vi.fn(), init: vi.fn() }))
afterEach(() => {cleanup();vi.unstubAllGlobals()})
const id = 'resonance-original-wt-351f9d5-stable'
const version = '0.2.0a1'
const symbols = ['510300.SH','510050.SH','510500.SH','512100.SH','515080.SH','588000.SH','589680.SH','159780.SZ','159352.SZ']
const strategy = () => ({...runtime.strategy,strategy_id:id,strategy_version:version,status:'holding',status_label:'保持当前目标',
  capital:null,capital_baseline:null,position_basis:'strategy-allocated',decision_at:null,broker_observed_at:'2026-11-06T07:00:00Z',
  diagnostics:null,diagnostics_state:'absent',diagnostics_reason:'not_calculated',
  positions:symbols.map((symbol,i)=>({symbol,target_weight:null,theoretical_quantity:null,theoretical_sellable:null,pending_target:null,
    stage_target:200,broker_quantity:i===0?200:i===8?100:0,broker_sellable:i===0?100:0}))})

test('原版九证券沿同一运行合同读取，保留ASA数量和目标', () => {
  const value=validateStrategyRuntime({...runtime,strategy:strategy()})
  expect(value.strategy?.positions).toHaveLength(9)
  expect(value.strategy?.positions[0].broker_quantity).toBe(200)
  expect(value.strategy?.positions[0].stage_target).toBe(200)
  expect(validateStrategyRuntime({...runtime,strategy:{...strategy(),status:'waiting_allocation',status_label:'等待确认策略归属'}}).strategy?.status).toBe('waiting_allocation')
})

test('现有详情布局按所选id查询，展示自有持仓及未知市值', async () => {
  const urls:string[]=[]
  const missing={value:null,reason:'原来源未提供'}
  vi.stubGlobal('fetch',vi.fn(async (input:RequestInfo|URL)=>{
    urls.push(String(input));return new Response(JSON.stringify({schema_version:'guanheng.strategy-details.v1',read_only:true,observed_at:'2026-11-06T07:00:00Z',
      strategy:{strategy_id:id,strategy_version:version,display_name:'共振原版'},runtime_scope_id:null,
      assignment:{scope:'strategy-allocated',label:'ASA已确认策略归属',reason:'ASA自有持仓，账户聚合单列。'},
      execution:{state:'ready',label:'运行中',reason:'原发布',started_at:missing,duration_seconds:missing},
      account:null,account_reason:null,calculation:strategy(),calculation_reason:null,capital:null,capital_baseline:null,
      budget_cny:missing,returns:{cumulative_pct:missing}}),{status:200,headers:{'Content-Type':'application/json'}})
  }))
  render(<MemoryRouter><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}>
    <StrategyDetails strategy={{strategy_id:id,strategy_version:version}} />
  </QueryClientProvider></MemoryRouter>)
  await waitFor(()=>expect(screen.getByText('策略自有持仓')).toBeVisible())
  expect(urls[0]).toContain('strategy_id='+id)
  expect(screen.getByText('159352.SZ')).toBeVisible()
  expect(screen.getByText('200')).toBeVisible()
  expect(screen.getAllByText('尚未取得').length).toBeGreaterThan(0)
})

test('ASA实际成交缺NAV时仍可读，界面保持归属和费用未知', () => {
  const deal={id:'allocated-fill',date:'2026-11-06',time:'14:30:00',symbol:'510300.SH',side:'BUY',price_cny:'2',quantity:200,
    amount_cny:'400.00',fee_cny:null,attribution:'strategy-allocated'}
  const body={schema_version:'guanheng.live-strategy-performance.v1',read_only:true,observed_at:'2026-11-06T07:00:00Z',state:'available',reason:'ASA原实际分配',
    requested:{strategy_id:id,strategy_version:version},current:{strategy_id:id,strategy_version:version,key_matches:true,is_current:false,runtime_state:'closed',scope_id:'a'.repeat(64),process_state:'exited'},
    coverage:{from:null,to:null,point_count:0,basis:'actual-published-observations',history_state:'snapshot-only',reason:'缺少策略估值',deals_truncated:false,attribution:'strategy-allocated'},
    baseline:null,summary:null,daily:[{date:'2026-11-06',observed_at:null,nav_cny:null,cash_cny:null,market_value_cny:null,pnl_cny:null,return_pct:null,
      positions:symbols.map(symbol=>({symbol,quantity:0,sellable:0,observed_at:'2026-11-06T07:00:00Z'})),deals:[deal],positions_state:'empty',deals_state:'available'}],markers:[deal]}
  const value=validateLivePerformance(body,id,version)
  expect(value.summary).toBeNull()
  render(<LiveStrategyPerformance data={value as LivePerformance} />)
  expect(screen.getByText('ASA已确认归属')).toBeVisible()
  expect(screen.getByText('14:30:00')).toBeVisible()
  expect(screen.queryByText('归属未确认')).toBeNull()
  expect(screen.getByText(/当前还没有实际净值点/)).toBeVisible()
})

test('已发布原版线上版本停止后保留运行详情及目标入口', async () => {
  const live={schema_version:'guanheng.live-strategy-performance.v1',read_only:true,observed_at:'2026-11-06T07:00:00Z',state:'available',reason:'已停止，保留实际观察',
    requested:{strategy_id:id,strategy_version:version},current:{strategy_id:id,strategy_version:version,key_matches:true,is_current:false,runtime_state:'closed',scope_id:'a'.repeat(64),process_state:'exited'},
    coverage:{from:null,to:null,point_count:0,basis:'actual-published-observations',history_state:'snapshot-only',reason:'缺少策略估值',deals_truncated:false},
    baseline:null,summary:null,daily:[],markers:[]}
  const calls:string[]=[]
  vi.stubGlobal('fetch',vi.fn(async(input:RequestInfo|URL)=>{
    const url=String(input);calls.push(url)
    const body=url.includes('strategy-catalog')?{schema:'guanheng.strategy-catalog.v1',read_only:true,scope:'registered-definitions',
      strategies:[{strategy_id:id,strategy_version:version,display_name:'原版线上',description:'实际发布',historical_versions:[]}]}:
      url.includes('live-strategy-performance')?live:{}
    return Response.json(body)
  }))
  render(<MemoryRouter initialEntries={['/?view=runtime&strategy='+id+'%40'+version]}><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}>
    <StrategyCatalogWorkspace />
  </QueryClientProvider></MemoryRouter>)
  await screen.findByRole('button',{name:'目标仓位记录'})
  expect(screen.getByRole('button',{name:'运行与持仓'})).toBeVisible()
  expect(await screen.findByRole('button',{name:'刷新策略详情'})).toBeVisible()
  expect(screen.queryByText('原版研究与回测')).toBeNull()
  expect(calls.some(url=>url.includes('strategy-details?strategy_id='+id))).toBe(true)
})
