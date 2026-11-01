import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import OperationsWorkspace from './OperationsWorkspace'
import { fetchWtInstances } from './wtInstancesApi'
vi.mock('./wtInstancesApi',()=>({fetchWtInstances:vi.fn()}))
vi.mock('./operationsApi',()=>({fetchOperations:vi.fn().mockRejectedValue(new Error('来源不在线'))}))
const clients:QueryClient[]=[]
afterEach(()=>{cleanup();clients.splice(0).forEach(c=>c.clear());vi.clearAllMocks()})
test.each([['unavailable','读取失败','status-error'],['unconfigured','未配置','status-neutral']] as const)('实例%s保留真实状态而不混淆配置',async(state,label,color)=>{
 vi.mocked(fetchWtInstances).mockResolvedValue({schema_version:'guanheng.wt-instances.v1',read_only:true,observed_at:'2026-11-01T00:00:00Z',instances:[{scope_id:'a'.repeat(64),label:'账户WT',state,reason:'具体来源原因',published_at:null,runtime:null}]})
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}});clients.push(client);render(<QueryClientProvider client={client}><OperationsWorkspace/></QueryClientProvider>)
 expect(await screen.findByText(label)).toHaveClass(color);expect(screen.getByText('具体来源原因')).toBeVisible()
})
