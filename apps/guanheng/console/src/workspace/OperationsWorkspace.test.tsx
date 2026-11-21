import {afterEach, beforeEach, expect, test, vi} from 'vitest'
import {cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react'
import {QueryClient, QueryClientProvider} from '@tanstack/react-query'
import OperationsWorkspace from './OperationsWorkspace'
import {fetchWtRuntime, type WtRuntimeObservation} from './wtRuntimeApi'
import {fetchOperations} from './operationsApi'
import {fetchWtInstances, type WtInstances} from './wtInstancesApi'
import {operationsFixture} from './operations.fixture'

vi.mock('./wtRuntimeApi',()=>({fetchWtRuntime:vi.fn()}))
vi.mock('./wtInstancesApi',()=>({fetchWtInstances:vi.fn()}))
vi.mock('./operationsApi',()=>({fetchOperations:vi.fn()}))
const clients: QueryClient[]=[]
const runtime: WtRuntimeObservation={schema_version:'guanheng.wt-runtime-observation.v1',read_only:true,
 observed_at:'2026-10-30T01:20:00Z',published_at:'2026-10-30T01:19:58Z',state:'available',
 reason:'以下为WT最近发布的状态；当前存活、来源连接和策略执行结果需分别核实。',
 runtime:{state:'ready',label:'基础就绪',ready:true,components:[{name:'history',display_name:'历史查询',state:'ready',label:'基础就绪',ready:true,pending:true,forced:false}]}}
const instances=(value:WtRuntimeObservation):WtInstances=>({schema_version:'guanheng.wt-instances.v1',read_only:true,
 observed_at:value.observed_at,instances:[{...value,scope_id:'a'.repeat(64),label:'WT'}]})
beforeEach(()=>{vi.mocked(fetchOperations).mockResolvedValue(operationsFixture);vi.mocked(fetchWtRuntime).mockResolvedValue(runtime)
 vi.mocked(fetchWtInstances).mockImplementation(async signal=>instances(await fetchWtRuntime(signal)))})
afterEach(()=>{cleanup();clients.splice(0).forEach(c=>c.clear());vi.resetAllMocks()})
function mount(){const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});clients.push(client);render(<QueryClientProvider client={client}><OperationsWorkspace/></QueryClientProvider>)}

test('中文发布状态与两个时间分别展示，只提供读取动作',async()=>{
 mount()
 const card=await screen.findByRole('region',{name:'WT运行状态'})
 expect(card).toHaveTextContent('基础就绪')
 expect(card).toHaveTextContent('2026-10-30 09:20:00')
 expect(card).toHaveTextContent('2026-10-30 09:19:58')
 expect(card).toHaveTextContent('最近发布的状态')
 expect(card).toHaveTextContent('历史查询')
 expect(screen.getAllByRole('button')).toHaveLength(1)
 expect(screen.getByRole('button')).toHaveTextContent('重新读取状态')
 expect(document.body.textContent).not.toMatch(/[a-f0-9]{64}|PID|控制身份|配置摘要/)
})

test('WT失败保留成功结果和原时间，行情查询独立读取，恢复后更新',async()=>{
 vi.mocked(fetchWtRuntime).mockResolvedValueOnce(runtime).mockRejectedValueOnce(new Error('read failed'))
  .mockResolvedValue({...runtime,observed_at:'2026-10-30T01:21:00Z',runtime:{...runtime.runtime!,state:'closed',label:'已停止',ready:false}})
 mount();await screen.findAllByText('基础就绪')
 const refresh=screen.getByRole('button',{name:'重新读取状态'});await waitFor(()=>expect(refresh).toBeEnabled())
 fireEvent.click(refresh)
 expect(await screen.findByRole('alert')).toHaveTextContent('保留上次成功结果和时间')
 expect(screen.getByRole('region',{name:'WT运行状态'})).toHaveTextContent('09:20:00')
 expect(screen.getByRole('region',{name:'行情查询服务'})).toBeVisible()
 await waitFor(()=>expect(refresh).toBeEnabled());fireEvent.click(refresh)
 expect(await screen.findByText('已停止')).toBeVisible()
 expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

test('CURRENT返回单实例失败时保留旧组件和原发布时间，失败状态持续显示，恢复后替换',async()=>{
 const unavailable=instances(runtime)
 unavailable.instances[0]={...unavailable.instances[0],state:'unavailable',reason:'此WT实例读取失败',published_at:null,runtime:null}
 vi.mocked(fetchWtInstances).mockResolvedValueOnce(instances(runtime)).mockResolvedValueOnce(unavailable)
  .mockResolvedValue(instances({...runtime,runtime:{...runtime.runtime!,state:'closed',label:'已停止',ready:false}}))
 mount()
 const card=await screen.findByRole('region',{name:'WT运行状态'})
 const refresh=screen.getByRole('button',{name:'重新读取状态'})
 await waitFor(()=>expect(refresh).toBeEnabled());fireEvent.click(refresh)
 await waitFor(()=>expect(card).toHaveTextContent('读取失败'))
 expect(within(card).getByRole('alert')).toHaveTextContent('上次成功结果和原发布时间；当前运行状态未知')
 expect(card).toHaveTextContent('历史查询')
 expect(card).toHaveTextContent('2026-10-30 09:19:58')
 await waitFor(()=>expect(refresh).toBeEnabled());fireEvent.click(refresh)
 await waitFor(()=>expect(card).toHaveTextContent('已停止'))
 expect(within(card).queryByRole('alert')).not.toBeInTheDocument()
})

test('未配置时明确说明，保持行情来源未知',async()=>{
 vi.mocked(fetchWtRuntime).mockResolvedValue({...runtime,state:'unconfigured',reason:'尚未配置独立WT状态读取',runtime:null,published_at:null})
 mount()
 expect(await screen.findByText('尚未配置独立WT状态读取')).toBeVisible()
 expect(screen.queryByText(/最近发布：/)).not.toBeInTheDocument()
 expect(screen.getAllByText('未知').length).toBeGreaterThan(0)
})

test('数据通信等待与服务就绪分开，刷新后显示发布数据及其时间',async()=>{
 const item={...runtime.runtime!.components[0],name:'analysis_window',display_name:'策略数据更新'}
 const waiting:WtRuntimeObservation={...runtime,runtime:{...runtime.runtime!,components:[{...item,
   data:{state:'available',label:'等待策略数据通信',ready:false,basis_date:null,published_at:null}}]}}
 const published:WtRuntimeObservation={...runtime,runtime:{...runtime.runtime!,components:[{...item,
   data:{state:'available',label:'策略数据已发布',ready:true,basis_date:'2026-10-29',published_at:'2026-10-30T01:01:00Z'}}]}}
 vi.mocked(fetchWtRuntime).mockResolvedValueOnce(waiting).mockResolvedValueOnce(published)
 mount()
 const card=await screen.findByRole('region',{name:'WT运行状态'})
 expect(card).toHaveTextContent('基础就绪')
 expect(card).toHaveTextContent('等待策略数据通信')
 expect(card).toHaveTextContent('尚未发布策略数据')
 expect(card).not.toHaveTextContent('最近数据交易日')
 const refresh=screen.getByRole('button',{name:'重新读取状态'});await waitFor(()=>expect(refresh).toBeEnabled())
 fireEvent.click(refresh)
 await waitFor(()=>expect(card).toHaveTextContent('策略数据已发布'))
 expect(card).toHaveTextContent('数据交易日 2026-10-29')
 expect(card).toHaveTextContent('2026-10-30 09:01:00')
 expect(screen.getAllByRole('button')).toHaveLength(1)
})

test('首先报告和同时报告分别解释，读取失败保留原问题，恢复只更新已发布事实',async()=>{
 const first={relation:'first_reported' as const,summary:'策略数据更新未完成正常关闭',impact:'本次正常停止尚未完成',action:'核对原关闭记录'}
 const other={relation:'also_reported' as const,summary:'行情采集停止超时，已使用强制回收',impact:'正常关闭资格待核',action:'核对资源回收结果'}
 const fault:WtRuntimeObservation={...runtime,runtime:{...runtime.runtime!,state:'faulted',label:'失败',ready:false,issue:first,
  components:[{name:'collection',display_name:'行情采集',state:'faulted',label:'失败',ready:false,pending:false,forced:true,issue:other}]}}
 vi.mocked(fetchWtRuntime).mockResolvedValueOnce(fault).mockRejectedValueOnce(new Error('read failed')).mockResolvedValue(runtime)
 mount();expect(await screen.findByRole('complementary',{name:'首先报告的问题'})).toHaveTextContent(first.summary)
 expect(screen.getByRole('complementary',{name:'同时报告的问题'})).toHaveTextContent(other.summary)
 expect(screen.getAllByText('影响：',{exact:true})).toHaveLength(2)
 expect(screen.getAllByText('处理：',{exact:true})).toHaveLength(2)
 const refresh=screen.getByRole('button',{name:'重新读取状态'});await waitFor(()=>expect(refresh).toBeEnabled());fireEvent.click(refresh)
 expect(await screen.findByRole('alert')).toHaveTextContent('保留上次成功结果和时间')
 expect(screen.getByRole('complementary',{name:'首先报告的问题'})).toHaveTextContent(first.summary)
 await waitFor(()=>expect(refresh).toBeEnabled());fireEvent.click(refresh)
 await waitFor(()=>expect(screen.queryByRole('complementary',{name:'首先报告的问题'})).not.toBeInTheDocument())
 expect(screen.queryByRole('alert')).not.toBeInTheDocument()
 expect(screen.getAllByRole('button')).toHaveLength(1)
})


function withSwitch(enabled: boolean | null | undefined): WtRuntimeObservation {
 const execution = {...runtime.runtime!.components[0],name:'execution',display_name:'策略执行',
  execution_control:enabled === undefined ? undefined : enabled === null
   ? {state:'unavailable' as const,writes_enabled:null,label:'WT下单开关暂不可核实'}
   : {state:'available' as const,writes_enabled:enabled,label:enabled ? 'WT下单开关已开启' : 'WT下单开关已关闭'}}
 return {...runtime,runtime:{...runtime.runtime!,components:[execution]}}
}

test.each([[true,'开启'],[false,'关闭'],[null,'未知'],[undefined,'未知']] as const)('执行行只读显示开关 %s',async(enabled,label)=>{
 vi.mocked(fetchWtRuntime).mockResolvedValue(withSwitch(enabled))
 mount()
 expect(await screen.findByText(`WT 下单开关：${label}`)).toBeVisible()
 const card=screen.getByRole('region',{name:'WT运行状态'})
 expect(card).toHaveTextContent('策略执行')
 expect(card).toHaveTextContent('实际委托由策略信号、账户权限和交易风控共同决定')
 expect(screen.getAllByRole('button')).toHaveLength(1)
 expect(screen.getByRole('button')).toHaveTextContent('重新读取状态')
})

test('整轮刷新失败显示当前未知与上次配置，恢复读取关闭值',async()=>{
 vi.mocked(fetchWtRuntime).mockResolvedValueOnce(withSwitch(true)).mockRejectedValueOnce(new Error('read failed')).mockResolvedValue(withSwitch(false))
 mount();await screen.findByText('WT 下单开关：开启')
 const refresh=screen.getByRole('button',{name:'重新读取状态'});await waitFor(()=>expect(refresh).toBeEnabled());fireEvent.click(refresh)
 expect(await screen.findByText('WT 下单开关：当前未知（上次配置：开启）')).toBeVisible()
 expect(screen.getByRole('alert')).toHaveTextContent('保留上次成功结果和时间')
 await waitFor(()=>expect(refresh).toBeEnabled());fireEvent.click(refresh)
 expect(await screen.findByText('WT 下单开关：关闭')).toBeVisible()
 expect(screen.queryByText(/上次配置：开启/)).not.toBeInTheDocument()
})

test('单实例失败仍展示原时间，当前开关未知',async()=>{
 const value=withSwitch(true);const unavailable=instances(value)
 unavailable.instances[0]={...unavailable.instances[0],state:'unavailable',reason:'此WT实例读取失败',published_at:null,runtime:null}
 vi.mocked(fetchWtInstances).mockResolvedValueOnce(instances(value)).mockResolvedValue(unavailable)
 mount();await screen.findByText('WT 下单开关：开启')
 const refresh=screen.getByRole('button',{name:'重新读取状态'});await waitFor(()=>expect(refresh).toBeEnabled());fireEvent.click(refresh)
 expect(await screen.findByText('WT 下单开关：当前未知（上次配置：开启）')).toBeVisible()
 expect(screen.getByRole('region',{name:'WT运行状态'})).toHaveTextContent('2026-10-30 09:19:58')
})

test('停止实例只描述最近配置，开关值不代替运行状态',async()=>{
 const value=withSwitch(true);value.runtime={...value.runtime!,state:'closed',label:'已停止',ready:false}
 vi.mocked(fetchWtRuntime).mockResolvedValue(value)
 mount()
 expect(await screen.findByText('WT 下单开关：最近配置为开启')).toBeVisible()
 expect(screen.getByRole('region',{name:'WT运行状态'})).toHaveTextContent('已停止')
})
