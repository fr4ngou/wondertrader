import { afterEach, expect, test, vi, beforeEach } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import BacktestWorkspace from './BacktestWorkspace'
import * as api from './backtestApi'
import * as performance from './backtestPerformanceApi'
import * as catalog from './strategyCatalogApi'
import fixture from './backtest-performance.fixture.json'

vi.mock('./backtestApi', async original => ({ ...await original<typeof api>(), fetchBacktestArchiveSummaries: vi.fn() }))
vi.mock('./backtestPerformanceApi', async original => ({ ...await original<typeof performance>(), fetchBacktestPerformance: vi.fn() }))
vi.mock('./strategyCatalogApi', async original => ({ ...await original<typeof catalog>(), fetchStrategyCatalog: vi.fn() }))
const analysisModule = vi.hoisted(() => ({ loads: 0 }))
vi.mock('./BacktestPerformance', () => { analysisModule.loads++; return ({ default: ({entry, entries, mainSelector, initialComparison}: {entry: api.ArchiveEntry; entries:api.ArchiveEntry[];mainSelector:import('react').ReactNode;initialComparison:string}) =>
    <div><h1>回测分析</h1>{mainSelector}<span>可选{entries.length}</span><span>{entry.run_id}</span><span>对比{initialComparison}</span></div> }) })

const clients: QueryClient[] = []
const current = {strategy_id:'resonance-regime-v1',strategy_version:'1.1.2',display_name:'共振策略',description:'当前策略',historical_versions:[]}
const summary = (version='1.1.2', id='resonance-regime-v1') => ({strategy:{id,version},initial_capital_cny:fixture.left.metrics.initial_capital_cny})
const left = {...fixture.left_entry,summary:summary()}
const right = {...fixture.right_entry,summary:summary()}
const extra = {...left,run_id:'3'.repeat(32),receipt_sha256:'4'.repeat(64)}
const index = (runs:api.ArchiveEntry[]):api.ArchiveSummaryIndex => ({schema:'nbw-archive-summary-index-v1',runs,invalid_receipts:0,unarchived_runs:0,scope:'isolated-raw-BT'})

beforeEach(() => {
  vi.mocked(catalog.fetchStrategyCatalog).mockResolvedValue([current])
  vi.mocked(performance.fetchBacktestPerformance).mockImplementation(async entry => ({...fixture.left,run_id:entry.run_id,
    strategy:{id:entry.summary?.strategy.id??current.strategy_id,version:entry.summary?.strategy.version??current.strategy_version,algorithm_id:null}} as performance.BacktestPerformance))
})
afterEach(() => {cleanup();clients.splice(0).forEach(client=>client.clear());vi.resetAllMocks()})
function mount(path='/backtests', client=new QueryClient({defaultOptions:{queries:{retry:false}}})) {
  clients.push(client)
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><BacktestWorkspace /></MemoryRouter></QueryClientProvider>)
}

test('列表保持分析模块未加载，打开报告才加载完整视图',async()=>{
  vi.mocked(api.fetchBacktestArchiveSummaries).mockResolvedValue(index([left]))
  mount();await screen.findByRole('region',{name:'策略回测列表'})
  expect(analysisModule.loads).toBe(0)
  fireEvent.click(screen.getByRole('button',{name:'打开回测分析'}))
  expect(await screen.findByRole('heading',{name:'回测分析'})).toBeVisible()
  expect(analysisModule.loads).toBe(1)
})

test('真实空目录保持空报告且只读',async()=>{
  vi.mocked(api.fetchBacktestArchiveSummaries).mockResolvedValue(index([]))
  mount();expect(await screen.findByText('该策略暂无已保存的回测报告。')).toBeVisible()
  expect(performance.fetchBacktestPerformance).not.toHaveBeenCalled()
  expect(screen.queryByRole('button',{name:/启动|保存/})).toBeNull()
})

test('目录和策略切换只读取归属，未打开报告不占完整绩效读池',async()=>{
  const old=Array.from({length:3},(_,i)=>({...left,run_id:String(i+4).repeat(32),summary:summary('0.9')}))
  vi.mocked(api.fetchBacktestArchiveSummaries).mockResolvedValue(index([left,right,...old]))
  vi.mocked(performance.fetchBacktestPerformance).mockReturnValue(new Promise(()=>{}))
  mount();expect(await screen.findByText('当前策略的回测 · 2 份已完成报告')).toBeVisible()
  expect(screen.getByRole('button',{name:'打开回测分析'})).toBeEnabled()
  expect(performance.fetchBacktestPerformance).not.toHaveBeenCalled()
  fireEvent.change(screen.getByLabelText('选择策略'),{target:{value:'resonance-regime-v1@0.9'}})
  expect(await screen.findByText('当前策略的回测 · 3 份已完成报告')).toBeVisible()
  expect(performance.fetchBacktestPerformance).not.toHaveBeenCalled()
  fireEvent.change(screen.getByLabelText('选择策略'),{target:{value:'resonance-regime-v1@1.1.2'}})
  fireEvent.click(screen.getByRole('button',{name:'打开回测分析'}))
  expect(await screen.findByRole('heading',{name:'回测分析'})).toBeVisible()
  expect(screen.getByText('可选2')).toBeVisible()
})

test('主报告和对比选择先保留身份，打开分析才交给完整读取',async()=>{
  vi.mocked(api.fetchBacktestArchiveSummaries).mockResolvedValue(index([left,right,extra]))
  mount();await screen.findByText('当前策略的回测 · 3 份已完成报告')
  expect(performance.fetchBacktestPerformance).not.toHaveBeenCalled()
  const compare=screen.getAllByRole('button',{name:'设为对比'}).find(button=>!(button as HTMLButtonElement).disabled)!
  fireEvent.click(compare)
  expect(performance.fetchBacktestPerformance).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button',{name:'打开对比分析'}))
  expect(await screen.findByRole('heading',{name:'回测分析'})).toBeVisible()
  expect(screen.getByText('可选3')).toBeVisible()
})

test('列表可以复用已打开分析的完整身份缓存，保持零额外绩效请求',async()=>{
  vi.mocked(api.fetchBacktestArchiveSummaries).mockResolvedValue(index([left,right]))
  const client=new QueryClient({defaultOptions:{queries:{retry:false}}})
  client.setQueryData(['backtest-performance',left.run_id,left.receipt_sha256,left.report_sha256],fixture.left)
  mount('/backtests',client)
  await screen.findByText('当前策略的回测 · 2 份已完成报告')
  expect(screen.getByRole('region',{name:'策略回测列表'})).toBeVisible()
  fireEvent.click(screen.getByRole('radio',{name:'主报告 2'}))
  expect(screen.getByText('0%',{selector:'.bt-return'})).toBeVisible()
  expect(performance.fetchBacktestPerformance).not.toHaveBeenCalled()
})

test('单条归属失败保留其他报告，刷新目录可以恢复',async()=>{
  vi.mocked(api.fetchBacktestArchiveSummaries).mockResolvedValueOnce(index([left,{...right,summary:null}])).mockResolvedValue(index([left,right]))
  mount();expect(await screen.findByRole('alert')).toHaveTextContent('1 份报告的归属读取失败')
  expect(await screen.findByText('当前策略的回测 · 已识别 1 份')).toBeVisible()
  fireEvent.click(screen.getByRole('button',{name:'重读报告目录'}))
  expect(await screen.findByText('当前策略的回测 · 2 份已完成报告')).toBeVisible()
})

test('同目录刷新失败保留成功列表和原完成身份',async()=>{
  vi.mocked(api.fetchBacktestArchiveSummaries).mockResolvedValueOnce(index([left,right])).mockRejectedValue(new Error('unavailable'))
  mount();await screen.findByText('当前策略的回测 · 2 份已完成报告')
  fireEvent.click(screen.getByRole('button',{name:'刷新列表'}))
  expect(await screen.findByRole('alert')).toHaveTextContent('保留上次目录')
  expect(screen.getByRole('region',{name:'策略回测列表'})).toBeVisible()
})

test('归属决定历史版本，切换策略清除报告选择并保持目录名称',async()=>{
  const old={...extra,summary:summary('0.9')}
  vi.mocked(api.fetchBacktestArchiveSummaries).mockResolvedValue(index([left,right,old]))
  mount('/backtests?run='+left.run_id)
  expect(await screen.findByRole('heading',{name:'回测分析'})).toBeVisible()
  fireEvent.change(screen.getByLabelText('选择策略'),{target:{value:'resonance-regime-v1@0.9'}})
  expect(await screen.findByText('当前策略的回测 · 1 份已完成报告')).toBeVisible()
  expect(screen.queryByRole('heading',{name:'回测分析'})).toBeNull()
  expect(screen.getByRole('option',{name:'共振策略 · v0.9'})).toBeInTheDocument()
})

test('跨策略对比深链接仍要求重选，未知策略不借用其他结果',async()=>{
  vi.mocked(api.fetchBacktestArchiveSummaries).mockResolvedValue(index([left,{...right,summary:summary('2.0','other')}]))
  mount('/backtests?run='+left.run_id+'&compare='+right.run_id)
  expect(await screen.findByRole('button',{name:'重新选择对比报告'})).toBeVisible()
  expect(screen.queryByRole('heading',{name:'回测分析'})).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'重新选择对比报告'}))
  expect(await screen.findByRole('heading',{name:'回测分析'})).toBeVisible()
})

test('没有活动策略时可从归属目录恢复历史报告；未知深链接明确失效',async()=>{
  vi.mocked(catalog.fetchStrategyCatalog).mockResolvedValue([])
  vi.mocked(api.fetchBacktestArchiveSummaries).mockResolvedValue(index([left]))
  const client=new QueryClient({defaultOptions:{queries:{retry:false}}})
  mount('/backtests?strategy=missing@1',client)
  expect(await screen.findByText('该策略当前不在目录中，请重新选择。')).toBeVisible()
  fireEvent.change(screen.getByLabelText('选择策略'),{target:{value:'resonance-regime-v1@1.1.2'}})
  expect(await screen.findByText('当前策略的回测 · 1 份已完成报告')).toBeVisible()
  await act(async()=>{client.setQueryData(['native-backtest-archive-summaries'],index([]))})
  expect(await screen.findByText('当前没有登记策略。')).toBeVisible()
  expect(screen.queryByRole('heading',{name:'回测分析'})).toBeNull()
})
