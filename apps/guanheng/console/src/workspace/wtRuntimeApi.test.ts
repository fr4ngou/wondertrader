import { afterEach, expect, test, vi } from 'vitest'
import { fetchWtRuntime } from './wtRuntimeApi'
afterEach(()=>vi.unstubAllGlobals())
const fixture=()=>({schema_version:'guanheng.wt-runtime-observation.v1',read_only:true,
 observed_at:'2026-10-30T01:00:00Z',published_at:'2026-10-30T00:59:59Z',state:'available',reason:'最近发布状态',
 runtime:{state:'ready',label:'基础就绪',ready:true,components:[{name:'history',display_name:'历史查询',state:'ready',label:'基础就绪',ready:true,pending:true,forced:false}]}})
const respond=(value:unknown)=>vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify(value))))

test.each(['runtime','component'])('拒绝%s生命周期中的非字符串状态',async target=>{
 for(const state of [['closed'],{},null,false]){
  const value=fixture()
  const published=target==='runtime'?value.runtime:value.runtime.components[0]
  Object.assign(published,{state,ready:false})
  respond(value)
  await expect(fetchWtRuntime(new AbortController().signal)).rejects.toThrow('WT运行状态格式无效')
 }
})
test('读取固定只读入口并保留两个独立时间',async()=>{
 const value=fixture();respond(value)
 const result=await fetchWtRuntime(new AbortController().signal)
 expect(result.published_at).not.toBe(result.observed_at)
 expect(result.runtime?.components[0].display_name).toBe('历史查询')
 expect(vi.mocked(fetch).mock.calls[0][0]).toBe('/v1/ui/wt-runtime')
 expect(vi.mocked(fetch).mock.calls[0][1]?.method??'GET').toBe('GET')
})
test.each([false,true])('兼容原四组件及可选交易通信 %s',async withTradeHost=>{
 const value=fixture()
 value.runtime.components=['host','history','collection','execution',...(withTradeHost?['trade_host']:[])].map(name=>({...value.runtime.components[0],name,display_name:name==='trade_host'?'交易通信':name}))
 respond(value)
 const result=await fetchWtRuntime(new AbortController().signal)
 expect(result.runtime?.components).toHaveLength(withTradeHost?5:4)
 if(withTradeHost)expect(result.runtime?.components.find(c=>c.name==='trade_host')?.display_name).toBe('交易通信')
})
test.each([7,9,10])('按公共合同读取%s组件且保留扩展',async count=>{
 const value=fixture()
 const names=['host','trade_host','account_host','account_observation','history','collection','execution','analysis_host','analysis_window','additional_reader']
 value.runtime.components=names.slice(0,count).map(name=>({...value.runtime.components[0],name,display_name:'运行服务'}))
 respond(value)
 expect((await fetchWtRuntime(new AbortController().signal)).runtime?.components).toHaveLength(count)
})

test.each([
 {state:'available',label:'等待策略数据通信',ready:false,basis_date:null,published_at:null},
 {state:'available',label:'正在更新策略数据',ready:true,basis_date:'2026-10-29',published_at:'2026-10-30T01:00:00Z'},
 {state:'unavailable',label:'策略数据状态暂不可用',ready:null,basis_date:null,published_at:null},
])('数据事实与服务ready独立：$label',async data=>{
 const value=fixture();(value.runtime.components[0] as Record<string,unknown>).data=data
 respond(value)
 expect((await fetchWtRuntime(new AbortController().signal)).runtime?.components[0].data).toEqual(data)
})

test.each([
 {state:'available',label:'已发布',ready:true,basis_date:null,published_at:null},
 {state:'unavailable',label:'未知',ready:true,basis_date:null,published_at:null},
])('拒绝互相矛盾的数据合同 $state',async data=>{
 const value=fixture();(value.runtime.components[0] as Record<string,unknown>).data=data
 respond(value)
 await expect(fetchWtRuntime(new AbortController().signal)).rejects.toThrow('WT运行状态格式无效')
})

test.each(['duplicate','missing_flag','invalid_name','false_ready'])('拒绝%s组件发布形态',kind=>{
 const value=fixture()
 if(kind==='duplicate')value.runtime.components.push({...value.runtime.components[0]})
 if(kind==='missing_flag')delete (value.runtime.components[0] as Record<string,unknown>).pending
 if(kind==='invalid_name')value.runtime.components[0].name='../private-process'
 if(kind==='false_ready')value.runtime.state='closed'
 respond(value)
 return expect(fetchWtRuntime(new AbortController().signal)).rejects.toThrow('WT运行状态格式无效')
})

test.each(['runtime','component'])('拒绝%s问题说明中的非文本关系和缺失业务说明',async target=>{
 for(const issue of [
  {relation:['first_reported'],summary:'问题',impact:'影响',action:'处理'},
  {relation:'first_reported',summary:123,impact:'影响',action:'处理'},
  {relation:'also_reported',summary:'问题',impact:'',action:'处理'},
 ]){
  const value=fixture();Object.assign(target==='runtime'?value.runtime:value.runtime.components[0],{issue})
  respond(value)
  await expect(fetchWtRuntime(new AbortController().signal)).rejects.toThrow('WT运行状态格式无效')
 }
})


test.each([
 {state:'available',writes_enabled:true,label:'WT下单开关已开启'},
 {state:'available',writes_enabled:false,label:'WT下单开关已关闭'},
 {state:'unavailable',writes_enabled:null,label:'WT下单开关暂不可核实'},
])('读取执行开关并区分关闭和未知：$label',async control=>{
 const value=fixture();Object.assign(value.runtime.components[0],{name:'execution',execution_control:control})
 respond(value)
 expect((await fetchWtRuntime(new AbortController().signal)).runtime?.components[0].execution_control).toEqual(control)
})

test.each([
 {state:'available',writes_enabled:null,label:'错误已知'},
 {state:'unavailable',writes_enabled:false,label:'错误关闭'},
 {state:'available',writes_enabled:1,label:'错误布尔'},
 {state:'ready',writes_enabled:true,label:'混用生命周期'},
 {state:'available',writes_enabled:true,label:42},
])('拒绝矛盾或非布尔的执行开关 $state',async control=>{
 const value=fixture();Object.assign(value.runtime.components[0],{name:'execution',execution_control:control})
 respond(value)
 await expect(fetchWtRuntime(new AbortController().signal)).rejects.toThrow('WT运行状态格式无效')
})
