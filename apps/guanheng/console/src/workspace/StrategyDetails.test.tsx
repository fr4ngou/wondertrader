import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import StrategyDetails from './StrategyDetails'
import { MemoryRouter } from 'react-router-dom'
import { validateStrategyDetails } from './strategyDetailsApi'
import account from './account-v2.fixture.json'
import type { AccountOverviewV2, AccountRow } from './accountApi'
import type { CapitalBaseline, StrategyCapital } from './strategyCapital'

const missing = (reason:string)=>({value:null,reason})
const fixture = ()=>({schema_version:'guanheng.strategy-details.v1',read_only:true,observed_at:'2026-11-01T01:00:00Z',
 strategy:{strategy_id:'resonance-regime-v1',strategy_version:'1.1.2',display_name:'共振市场状态 ETF 策略'},
 assignment:{scope:'current-account-inventory',label:'现有持仓归属此策略',reason:'按用户确认展示当前账户持仓；历史开仓和成交记录不迁移。'},
 execution:{state:'not_started',label:'策略未启动',reason:'当前WT仅提供账户读取。',started_at:missing('来源尚未提供开始时间'),duration_seconds:missing('缺少策略开始时间')},
 account:structuredClone(account) as AccountOverviewV2,account_reason:null,calculation:null,calculation_reason:null,budget_cny:missing('账户可用资金归账户所有'),
 returns:{cumulative_pct:missing('缺少起始本金和期间现金流基准')}})
const clients:QueryClient[]=[]
afterEach(()=>{cleanup();clients.splice(0).forEach(c=>c.clear());vi.unstubAllGlobals()})
function mount(strategy?:{strategy_id:string;strategy_version:string}){const c=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:Infinity}}});clients.push(c);render(<QueryClientProvider client={c}><MemoryRouter><StrategyDetails strategy={strategy}/></MemoryRouter></QueryClientProvider>)}
test('未启动策略仍显示四项当前持仓，资金、预算和收益基准分别解释',async()=>{
 const value=fixture();const row=value.account.groups.position.rows[0]
 value.account.groups.position.rows=[0,1,2,3].map((i):AccountRow=>({...structuredClone(row),identity:{m_strInstrumentID:`5100${i}0`,m_strExchangeID:'SH'},
   fields:{...row.fields,quantity:{availability:'present',value:1200+i,reason:null},sellable:{availability:'present',value:800+i,reason:null},market_value:{availability:'present',value:9800+i,reason:null}}}))
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json(value)));mount()
 const table=await screen.findByRole('region',{name:'策略当前持仓'})
 expect(within(table).getAllByRole('row')).toHaveLength(5)
 expect(table).toHaveTextContent('1,200');expect(table).toHaveTextContent('800');expect(table).toHaveTextContent('9,800')
 expect(screen.getByText('策略未启动')).toBeVisible()
 expect(screen.getByText('账户可用资金归账户所有')).toBeInTheDocument()
 expect(screen.getByText('缺少起始本金和期间现金流基准')).toBeInTheDocument()
 expect(screen.getByText('来源尚未提供开始时间')).toBeInTheDocument()
 expect(screen.queryByText('0%')).not.toBeInTheDocument()
 expect(document.body).not.toHaveTextContent('pid')
})
test('刷新失败保留同一成功详情和原时间，再恢复',async()=>{
 const fetch=vi.fn().mockResolvedValueOnce(Response.json(fixture())).mockResolvedValueOnce(Response.json({}, {status:503}))
   .mockResolvedValue(Response.json({...fixture(),execution:{...fixture().execution,state:'closed',label:'策略已停止'}}))
 vi.stubGlobal('fetch',fetch);mount();await screen.findByText('策略未启动')
 fireEvent.click(screen.getByRole('button',{name:'刷新策略详情'}))
 expect(await screen.findByRole('alert')).toHaveTextContent('保留上次成功结果')
 expect(screen.getByText('策略未启动')).toBeVisible()
 fireEvent.click(screen.getByRole('button',{name:'刷新策略详情'}))
 expect(await screen.findByText('策略已停止')).toBeVisible()
})

test('原页面定时读取WT新一代状态，无需重新挂载或点击刷新',async()=>{
 const fetch=vi.fn().mockResolvedValueOnce(Response.json(fixture()))
   .mockImplementation(()=>Promise.resolve(Response.json({...fixture(),execution:{...fixture().execution,state:'closed',label:'策略已停止'}})))
 vi.stubGlobal('fetch',fetch);mount()
 expect(await screen.findByText('策略未启动')).toBeVisible()
 expect(await screen.findByText('策略已停止',{}, {timeout:20_000})).toBeVisible()
 expect(fetch).toHaveBeenCalledTimes(2)
},25_000)

test('WT切到新代而账户暂缺时清除旧代持仓，恢复只显示本代结果',async()=>{
 const first={...fixture(),runtime_scope_id:'a'.repeat(64)}
 const waiting={...fixture(),runtime_scope_id:'b'.repeat(64),account:null,account_reason:'本代账户尚未发布'}
 const recovered={...fixture(),runtime_scope_id:'b'.repeat(64)}
 const row=recovered.account.groups.position.rows[0]
 recovered.account.groups.position.rows=[{...row,identity:{m_strInstrumentID:'588000',m_strExchangeID:'SH'}}]
 vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(Response.json(first)).mockResolvedValueOnce(Response.json(waiting))
   .mockResolvedValue(Response.json(recovered)))
 mount();await screen.findByRole('region',{name:'策略当前持仓'})
 fireEvent.click(screen.getByRole('button',{name:'刷新策略详情'}))
 expect(await screen.findByRole('alert')).toHaveTextContent('本代账户尚未发布')
 expect(screen.queryByRole('region',{name:'策略当前持仓'})).not.toBeInTheDocument()
 expect(screen.getByText('当前持仓尚未取得。')).toBeVisible()
 fireEvent.click(screen.getByRole('button',{name:'刷新策略详情'}))
 expect(await screen.findByText('588000.SH')).toBeVisible()
 expect(within(screen.getByRole('region',{name:'策略当前持仓'})).getAllByRole('row')).toHaveLength(2)
})

test.each([false, 4, 'A'.repeat(64), 'short'])('运行scope格式无效时拒绝详情：%s',scope=>{
 expect(()=>validateStrategyDetails({...fixture(),runtime_scope_id:scope})).toThrow('策略详情格式无效')
})
test('金额按中文单位显示且可查看精确值，持仓份额保持原数量',async()=>{
 const value=fixture()
 const fields=value.account.groups.position.rows[0].fields
 fields.quantity={availability:'present',value:25000000,reason:null}
 fields.market_value={availability:'present',value:25000000,reason:null}
 fields.float_profit={availability:'present',value:-885123435.815,reason:null}
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json(value)));mount()
 const table=await screen.findByRole('region',{name:'策略当前持仓'})
 expect(within(table).getByText('25,000,000')).toBeVisible()
 expect(within(table).getByText('2.5千万')).toHaveAttribute('title','25,000,000元')
 expect(within(table).getByText('-8.8512亿')).toHaveAttribute('title','-885,123,435.815元')
})
test('详情拒绝未知版本和伪造缺失值',()=>{
 expect(()=>validateStrategyDetails({...fixture(),strategy:{...fixture().strategy,strategy_version:'1.0.0'}})).toThrow()
 expect(()=>validateStrategyDetails({...fixture(),budget_cny:{value:null,reason:null}})).toThrow()
})
test('新一轮局部资金持仓失败沿原账户投影保留成功批和原时间',async()=>{
 const first=fixture();const partial=fixture()
 partial.account.status='partial'
 partial.account.groups.position={...partial.account.groups.position,status:'unavailable',rows:[],reason:'本轮来源暂不可用'}
 partial.account.groups.account={...partial.account.groups.account,status:'unavailable',rows:[],reason:'本轮来源暂不可用'}
 const fetch=vi.fn().mockResolvedValueOnce(Response.json(first)).mockResolvedValueOnce(Response.json(partial))
 vi.stubGlobal('fetch',fetch);mount()
 await screen.findByRole('region',{name:'策略当前持仓'})
 fireEvent.click(screen.getByRole('button',{name:'刷新策略详情'}))
 expect(await screen.findByText('本轮持仓未更新，当前保留上次成功持仓及原查询时间。')).toBeVisible()
 expect(screen.getByText('本轮资金未更新，当前保留上次成功资金及原查询时间。')).toBeInTheDocument()
 expect(screen.getByRole('region',{name:'策略当前持仓'})).toBeVisible()
})

function capitalFixture() {
 const baseline:CapitalBaseline={schema:'guanheng.current-capital-baseline.v1',total_cny:'1000000',source:'用户确认当前策略总资本',
  baseline_at:'2026-11-01T01:00:00+00:00',historical_initial_capital_cny:null}
 const capital:StrategyCapital={schema:'guanheng.strategy-capital-observation.v1',currency:'CNY',baseline,
  observed_at:'2026-11-01T01:05:00+00:00',position_observed_at:'2026-11-01T01:04:00+00:00',market_value_source:'broker-position+raw-CTA-price',
  native_pnl_cny:'500',nav_cny:'1000500',market_value_cny:'350000',cash_balance_cny:'650500',spendable_cash_cny:'600000',
  account_observation_qualified:true,account_observed_at:'2026-11-01T01:04:30+00:00',account_valid_until:'2026-11-01T01:10:00+00:00',
  account_available_cny:'198000000',account_frozen_cash_cny:'10000',account_source_sha256:'a'.repeat(64),
  cash_constraint_scope:'account-wide-conservative-limit',historical_return_pct:null}
 return {...fixture(),capital_baseline:baseline,capital}
}

test('策略资金展示WT同批资产余额和本次盈亏，全账户现金保持独立',async()=>{
 const value=capitalFixture();expect(validateStrategyDetails(value).capital).toEqual(value.capital)
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json(value)));mount()
 const funds=await screen.findByRole('region',{name:'策略资金'})
 expect(within(funds).getByText('100.05万')).toHaveAttribute('title','1000500元')
 expect(within(funds).getByText('65.05万')).toBeVisible()
 expect(within(funds).getByText('60万')).toBeVisible()
 expect(within(funds).getByText('35万')).toBeVisible()
 expect(within(funds).getByText('500')).toHaveAttribute('title','500元')
 expect(funds).not.toHaveTextContent('198000000')
 expect(screen.queryByText('策略预算（元）')).not.toBeInTheDocument()
 expect(screen.queryByText('0%')).not.toBeInTheDocument()
})

test('可用资金未知保留原资产与来源时间，不以账户余额或零代替',async()=>{
 const value=capitalFixture();value.capital.account_observation_qualified=false;value.capital.spendable_cash_cny=null
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json(value)));mount()
 const funds=await screen.findByRole('region',{name:'策略资金'})
 expect(within(funds).getByText('待更新')).toBeVisible()
 expect(within(funds).getByText('100.05万')).toBeVisible()
 expect(within(funds).getByText('65.05万')).toBeVisible()
 expect(funds.querySelector('time')).toHaveAttribute('datetime',value.capital.observed_at)
 expect(()=>validateStrategyDetails({...value,capital:{...value.capital,spendable_cash_cny:'198000000'}})).toThrow('策略资金格式无效')
})

// 目录可能登记多个策略，唯一运行接口的返回值不得借给另一个选择。
test('策略身份不符时保持持仓与资金未取得',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json(capitalFixture())))
 mount({strategy_id:'other',strategy_version:'2.0'})
 expect(await screen.findByRole('alert')).toHaveTextContent('尚未取得该策略的运行与持仓数据')
 expect(screen.queryByRole('region',{name:'策略当前持仓'})).toBeNull()
 expect(screen.queryByRole('region',{name:'策略资金'})).toBeNull()
})
