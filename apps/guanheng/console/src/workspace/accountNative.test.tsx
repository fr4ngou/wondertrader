import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AccountWorkspace from './AccountWorkspace'
import { validateAccountOverview } from './accountApi'
import { nativeAccountFixture } from './accountNative.fixture'

const clients: QueryClient[] = []
afterEach(()=>{cleanup();clients.splice(0).forEach(client=>client.clear());vi.unstubAllGlobals()})
function mount(fetch: ReturnType<typeof vi.fn>){
 vi.stubGlobal('fetch',fetch)
 const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});clients.push(client)
 render(<QueryClientProvider client={client}><AccountWorkspace capability={{available:true,reason:null,timeout_seconds:2}}/></QueryClientProvider>)
}
const response=(value:unknown)=>new Response(JSON.stringify(value))

test('原生观察显示已知资金持仓及各自时间，缺失委托不作为零记录',async()=>{
 const fixture=nativeAccountFixture();expect(validateAccountOverview(fixture)).toEqual(fixture)
 mount(vi.fn().mockResolvedValue(response(fixture)))
 expect(await screen.findByText('75,000',{selector:'strong'})).toBeVisible()
 expect(screen.getByText('700')).toBeVisible();expect(screen.getByText('300')).toBeVisible()
 expect(screen.getByLabelText('资金来源')).toHaveTextContent('2026-10-29 09:30:03')
 expect(screen.getByLabelText('持仓来源')).toHaveTextContent('2026-10-29 09:30:01')
 expect(document.body.textContent).not.toMatch(/[a-f0-9]{64}|scope_id|revision|control_id/)
 fireEvent.click(screen.getByRole('tab',{name:'委托'}))
 expect(screen.getByRole('tabpanel')).toHaveTextContent('WT现有观察未提供此类数据')
 expect(screen.getByRole('tabpanel')).not.toHaveTextContent('返回 0 条记录')
 expect(screen.getByText('75,000',{selector:'strong'})).toBeVisible()
})

test('同一观察作用域某组失败保留上次成功组，换运行作用域后清除',async()=>{
 const original=nativeAccountFixture();const partial=nativeAccountFixture()
 partial.groups.account={...partial.groups.account,status:'unavailable',rows:[],received_at:null,published_at:null,revision:null}
 const changed=structuredClone(partial)
 Object.values(changed.groups).forEach(group=>{group.source!.scope_id='b'.repeat(64)})
 const fetch=vi.fn().mockResolvedValueOnce(response(original)).mockResolvedValueOnce(response(partial)).mockResolvedValueOnce(response(changed))
 mount(fetch);await screen.findByText('75,000',{selector:'strong'})
 const refresh=screen.getByRole('button',{name:'刷新账户'});await waitFor(()=>expect(refresh).toBeEnabled());fireEvent.click(refresh)
 expect(await screen.findByText(/本轮资金未更新，保留上次成功结果/)).toBeVisible()
 expect(screen.getByText('75,000',{selector:'strong'})).toBeVisible()
 await waitFor(()=>expect(refresh).toBeEnabled());fireEvent.click(refresh)
 await waitFor(()=>expect(screen.queryByText('75,000',{selector:'strong'})).not.toBeInTheDocument())
})

test.each(['revision','received_at','source'] as const)('拒绝原生完整组缺失%s的伪造成功',field=>{
 const fixture=nativeAccountFixture();(fixture.groups.position as unknown as Record<string,unknown>)[field]=null
 expect(()=>validateAccountOverview(fixture)).toThrow('账户数据格式无效')
})
