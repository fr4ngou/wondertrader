import { afterEach, expect, test, vi } from 'vitest'
import { fetchWtInstances } from './wtInstancesApi'
const fixture = ()=>({schema_version:'guanheng.wt-instances.v1',read_only:true,observed_at:'2026-11-01T01:00:00Z',
 instances:[{scope_id:'a'.repeat(64),label:'账户WT',state:'unavailable',reason:'账户状态文件暂不可读',published_at:null,runtime:null},
 {scope_id:'b'.repeat(64),label:'行情与历史WT',state:'available',reason:'WT原发布',published_at:'2026-11-01T00:59:00Z',
 runtime:{state:'ready',label:'基础就绪',ready:true,components:[{name:'history',display_name:'历史查询',state:'ready',label:'基础就绪',ready:true,pending:true,forced:false}]}}]})
afterEach(()=>vi.unstubAllGlobals())
test('独立实例保留局部错误和行情历史事实',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json(fixture())))
 const result=await fetchWtInstances(new AbortController().signal)
 expect(result.instances).toHaveLength(2)
 expect(result.instances[0].state).toBe('unavailable')
 expect(result.instances[1].runtime?.components[0].name).toBe('history')
})
test('重复实例与无效来源状态拒绝',async()=>{
 const value=fixture();value.instances[1].scope_id=value.instances[0].scope_id
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json(value)))
 await expect(fetchWtInstances(new AbortController().signal)).rejects.toThrow('WT实例状态格式无效')
})
