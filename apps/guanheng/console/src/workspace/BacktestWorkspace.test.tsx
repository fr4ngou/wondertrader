import { afterEach, expect, test, vi, beforeEach } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import BacktestWorkspace from './BacktestWorkspace'
import * as api from './backtestApi'
import * as performance from './backtestPerformanceApi'
import * as catalog from './strategyCatalogApi'
import fixture from './backtest-performance.fixture.json'
import { performanceKey } from './useBacktestReports'

vi.mock('./backtestApi', async original => ({ ...await original<typeof api>(), fetchBacktestArchive: vi.fn() }))
vi.mock('./backtestPerformanceApi', async original => ({ ...await original<typeof performance>(), fetchBacktestPerformance: vi.fn() }))
vi.mock('./strategyCatalogApi', async original => ({ ...await original<typeof catalog>(), fetchStrategyCatalog: vi.fn() }))
vi.mock('./BacktestPerformance', () => ({ reportLabel: (entry: api.ArchiveEntry) => entry.configuration.label, reportKey:(entry: api.ArchiveEntry)=>entry.run_id+entry.receipt_sha256,
  default: ({ entry, entries, mainSelector, initialComparison, ready, onRefreshArchive }: { ready:boolean;onRefreshArchive:()=>void;entry: api.ArchiveEntry; entries:api.ArchiveEntry[]; mainSelector: import('react').ReactNode; initialComparison:string }) => <div><h1>回测分析</h1>{mainSelector}<span>{entry.record_count}期</span><span>对比{initialComparison}</span><span>可选{entries.length}</span><button disabled={!ready} onClick={onRefreshArchive}>刷新分析</button></div> }))
const clients: QueryClient[] = []
const strategies = [{strategy_id:'resonance-regime-v1',strategy_version:'1.1.2',display_name:'共振策略',description:'当前策略',historical_versions:[]},
  {strategy_id:'other',strategy_version:'2.0',display_name:'另一个策略',description:'隔离策略',historical_versions:[]}]
const index = (runs:api.ArchiveEntry[]) => ({ schema:'nbw-archive-index-v1' as const,runs,invalid_receipts:0,unarchived_runs:0,scope:'isolated-raw-BT' })
const entry3 = {...fixture.left_entry,run_id:'3'.repeat(32),receipt_sha256:'4'.repeat(64)}
beforeEach(() => {
  vi.mocked(catalog.fetchStrategyCatalog).mockResolvedValue(strategies)
  vi.mocked(performance.fetchBacktestPerformance).mockImplementation(async entry => ({...fixture.left, run_id:entry.run_id,
    strategy:{id:'resonance-regime-v1',version:'1.1.2',algorithm_id:null}} as performance.BacktestPerformance))
})
afterEach(() => { cleanup(); clients.splice(0).forEach(c => c.clear()); vi.resetAllMocks() })
function mount(path='/backtests', client=new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  clients.push(client)
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><BacktestWorkspace /></MemoryRouter></QueryClientProvider>)
}

test('先选择策略显示空报告列表，保持只读', async () => {
  vi.mocked(api.fetchBacktestArchive).mockResolvedValue(index([]))
  mount(); expect(await screen.findByText('该策略暂无已保存的回测报告。')).toBeVisible()
  expect(screen.getByLabelText('选择策略')).toHaveValue('resonance-regime-v1@1.1.2')
  expect(screen.queryByRole('button', { name: /启动|取消运行|保存/ })).toBeNull()
})

test('默认主报告为截止日期最新，列表打开分析后仍可返回', async () => {
  const newer = {...fixture.right_entry,configuration:{...fixture.right_entry.configuration,end:202611021500}}
  vi.mocked(api.fetchBacktestArchive).mockResolvedValue(index([fixture.left_entry,newer]))
  mount(); await screen.findByText('当前策略的回测 · 2 份已完成报告')
  const rows=within(screen.getByRole('region',{name:'策略回测列表'})).getAllByRole('row')
  expect(within(rows[1]).getByRole('radio')).toBeChecked()
  fireEvent.click(screen.getByRole('button',{name:'打开回测分析'}))
  expect(await screen.findByLabelText('选择历史回测')).toHaveValue(newer.run_id)
  fireEvent.click(screen.getByRole('button',{name:'← 返回回测列表'}))
  expect(await screen.findByRole('region',{name:'策略回测列表'})).toBeVisible()
})

test('同策略可比较，切换策略清除报告选择并按核验身份隔离', async () => {
  vi.mocked(api.fetchBacktestArchive).mockResolvedValue(index([fixture.left_entry,fixture.right_entry,entry3]))
  vi.mocked(performance.fetchBacktestPerformance).mockImplementation(async entry => ({...fixture.left,run_id:entry.run_id,
    strategy: entry.run_id===entry3.run_id ? {id:'other',version:'2.0',algorithm_id:null} : {id:'resonance-regime-v1',version:'1.1.2',algorithm_id:null}} as performance.BacktestPerformance))
  mount(); await screen.findByText('当前策略的回测 · 2 份已完成报告')
  await waitFor(()=>expect(performance.fetchBacktestPerformance).toHaveBeenCalledTimes(3))
  const options=screen.getAllByRole('button',{name:'设为对比'})
  fireEvent.click(options.find(button=>!(button as HTMLButtonElement).disabled)!)
  fireEvent.click(screen.getByRole('button',{name:'打开对比分析'}))
  expect(await screen.findByText('可选2')).toBeVisible()
  fireEvent.change(screen.getByLabelText('选择策略'),{target:{value:'other@2.0'}})
  expect(await screen.findByText('当前策略的回测 · 1 份已完成报告')).toBeVisible()
  expect(screen.queryByRole('heading',{name:'回测分析'})).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'打开回测分析'}))
  expect(await screen.findByLabelText('选择历史回测')).toHaveValue(entry3.run_id)
  expect(screen.getByText('可选1')).toBeVisible()
})

test('读取失败可重读，身份未核实的报告保持未归类', async () => {
  vi.mocked(api.fetchBacktestArchive).mockResolvedValue(index([fixture.left_entry]))
  vi.mocked(performance.fetchBacktestPerformance).mockRejectedValueOnce(new Error('读取失败'))
  mount(); expect(await screen.findByRole('alert')).toHaveTextContent('1 份报告读取失败')
  expect(screen.queryByRole('region',{name:'策略回测列表'})).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'重读失败报告'}))
  expect(await screen.findByText('当前策略的回测 · 1 份已完成报告')).toBeVisible()
})

test('多份元数据最多两份并行读取，完成后继续后续报告', async () => {
  vi.mocked(api.fetchBacktestArchive).mockResolvedValue(index([fixture.left_entry,fixture.right_entry,entry3]))
  let release:()=>void=()=>{}
  const gate=new Promise<void>(resolve=>{release=resolve})
  vi.mocked(performance.fetchBacktestPerformance).mockImplementation(async entry=>{await gate;return {...fixture.left,run_id:entry.run_id,strategy:{id:'resonance-regime-v1',version:'1.1.2',algorithm_id:null}} as performance.BacktestPerformance})
  mount(); await waitFor(()=>expect(performance.fetchBacktestPerformance).toHaveBeenCalledTimes(2))
  release()
  expect(await screen.findByText('当前策略的回测 · 3 份已完成报告')).toBeVisible()
})

test('未知深链接读取归档身份后仍须重新选择，不借用其他策略数据', async () => {
  vi.mocked(api.fetchBacktestArchive).mockResolvedValue({schema:'nbw-archive-index-v1',runs:[],invalid_receipts:0,unarchived_runs:0,scope:'test'})
  mount('/backtests?strategy=missing@1&run='+fixture.left_entry.run_id)
  expect(await screen.findByText('该策略当前不在目录中，请重新选择。')).toBeVisible()
  expect(api.fetchBacktestArchive).toHaveBeenCalledTimes(1)
})

test('没有活动身份时，首次目录和全部绩效失败仍可重读并恢复旧报告', async () => {
  vi.mocked(catalog.fetchStrategyCatalog).mockResolvedValue([])
  vi.mocked(api.fetchBacktestArchive).mockRejectedValueOnce(new Error('unavailable')).mockResolvedValue(index([fixture.left_entry]))
  vi.mocked(performance.fetchBacktestPerformance).mockRejectedValueOnce(new Error('unavailable')).mockResolvedValue(fixture.left as performance.BacktestPerformance)
  mount()
  fireEvent.click(await screen.findByRole('button', { name: '刷新历史报告' }))
  fireEvent.click(await screen.findByRole('button', { name: '重读失败报告' }))
  expect(await screen.findByText('当前策略的回测 · 1 份已完成报告')).toBeVisible()
  expect(screen.getByLabelText('选择策略')).toHaveValue(`${fixture.left.strategy.id}@${fixture.left.strategy.version}`)
})

// 缓存位于新报告之间时也共享实际在途两槽。
test('缓存穿插不会让四份新报告同时读取',async()=>{
 const entries=Array.from({length:6},(_,i)=>({...fixture.left_entry,run_id:String(i).repeat(32)}))
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}})
 for(const i of [2,3])client.setQueryData(performanceKey(entries[i]),{...fixture.left,run_id:entries[i].run_id,strategy:{id:'resonance-regime-v1',version:'1.1.2',algorithm_id:null}})
 vi.mocked(api.fetchBacktestArchive).mockResolvedValue(index(entries))
 let release:()=>void=()=>{};const gate=new Promise<void>(resolve=>{release=resolve})
 vi.mocked(performance.fetchBacktestPerformance).mockImplementation(async entry=>{await gate;return {...fixture.left,run_id:entry.run_id,strategy:{id:'resonance-regime-v1',version:'1.1.2',algorithm_id:null}} as performance.BacktestPerformance})
 mount('/backtests',client)
 await waitFor(()=>expect(performance.fetchBacktestPerformance).toHaveBeenCalledTimes(2))
 release();expect(await screen.findByText('当前策略的回测 · 6 份已完成报告')).toBeVisible()
})

test('读取途中目录插入新报告，实际在途仍保持两份',async()=>{
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}})
 vi.mocked(api.fetchBacktestArchive).mockResolvedValue(index([fixture.left_entry,fixture.right_entry]))
 let release:()=>void=()=>{};const gate=new Promise<void>(resolve=>{release=resolve})
 vi.mocked(performance.fetchBacktestPerformance).mockImplementation(async entry=>{await gate;return {...fixture.left,run_id:entry.run_id,strategy:{id:'resonance-regime-v1',version:'1.1.2',algorithm_id:null}} as performance.BacktestPerformance})
 mount('/backtests',client)
 await waitFor(()=>expect(performance.fetchBacktestPerformance).toHaveBeenCalledTimes(2))
 await act(async()=>{client.setQueryData(['native-backtest-archive'],index([{...entry3,configuration:{...entry3.configuration,end:202611031500}},fixture.left_entry,fixture.right_entry]))})
 expect(performance.fetchBacktestPerformance).toHaveBeenCalledTimes(2)
 release();expect(await screen.findByText('当前策略的回测 · 3 份已完成报告')).toBeVisible()
})

test('跨策略对比深链接要求重新选择，不能静默变成单份',async()=>{
 vi.mocked(api.fetchBacktestArchive).mockResolvedValue(index([fixture.left_entry,fixture.right_entry]))
 vi.mocked(performance.fetchBacktestPerformance).mockImplementation(async entry=>({...fixture.left,run_id:entry.run_id,strategy:entry.run_id===fixture.left_entry.run_id?{id:'resonance-regime-v1',version:'1.1.2',algorithm_id:null}:{id:'other',version:'2.0',algorithm_id:null}} as performance.BacktestPerformance))
 mount('/backtests?run='+fixture.left_entry.run_id+'&compare='+fixture.right_entry.run_id)
 expect(await screen.findByRole('button',{name:'重新选择对比报告'})).toBeVisible()
 expect(screen.queryByRole('heading',{name:'回测分析'})).toBeNull()
 fireEvent.click(screen.getByRole('button',{name:'重新选择对比报告'}))
 expect(await screen.findByRole('heading',{name:'回测分析'})).toBeVisible()
})

// 分析手动刷新与列表后台核验共享槽位，避免在已有两请求时新增第三个。
test('后台两份报告读取时分析刷新等待完成',async()=>{
 const entries=[fixture.left_entry,fixture.right_entry,entry3]
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}})
 client.setQueryData(performanceKey(entries[0]),{...fixture.left,strategy:{id:'resonance-regime-v1',version:'1.1.2',algorithm_id:null}})
 vi.mocked(api.fetchBacktestArchive).mockResolvedValue(index(entries))
 let release:()=>void=()=>{};const gate=new Promise<void>(resolve=>{release=resolve})
 vi.mocked(performance.fetchBacktestPerformance).mockImplementation(async entry=>{await gate;return {...fixture.left,run_id:entry.run_id,strategy:{id:'resonance-regime-v1',version:'1.1.2',algorithm_id:null}} as performance.BacktestPerformance})
 mount('/backtests?run='+entries[0].run_id,client)
 await waitFor(()=>expect(performance.fetchBacktestPerformance).toHaveBeenCalledTimes(2))
 expect(screen.getByRole('button',{name:'刷新分析'})).toBeDisabled()
 release();await waitFor(()=>expect(screen.getByRole('button',{name:'刷新分析'})).toBeEnabled())
})
