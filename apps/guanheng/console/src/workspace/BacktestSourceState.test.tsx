import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import BacktestSourceState from './BacktestSourceState'
const clients:QueryClient[]=[]
afterEach(()=>{cleanup();clients.splice(0).forEach(c=>c.clear());vi.unstubAllGlobals()})
test.each([['unconfigured','尚未配置WT回测归档目录'],['invalid_path','配置的回测归档目录不存在'],['invalid_archive','完成证明格式无效'],['empty','目录中当前没有已保存报告']])('准确解释%s',(state,reason)=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json({schema_version:'guanheng.backtest-source.v1',read_only:true,persistent:true,state,reason})))
 const c=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});clients.push(c)
 render(<QueryClientProvider client={c}><BacktestSourceState/></QueryClientProvider>)
 return screen.findByText(reason).then(element=>{expect(element).toBeVisible();expect(document.body).not.toHaveTextContent('历史报告目录读取失败')})
})
