import { useQuery } from '@tanstack/react-query'
import { fetchReadJson } from '../api'

export type BacktestSource = { schema_version: 'guanheng.backtest-source.v1'; read_only: true; persistent: true;
  state: 'unconfigured' | 'invalid_path' | 'invalid_archive' | 'empty' | 'available'; reason: string }
export async function fetchBacktestSource(signal: AbortSignal): Promise<BacktestSource> {
  const data = await fetchReadJson<BacktestSource>('/v1/ui/backtest/source', '回测报告来源', signal)
  if (data?.schema_version !== 'guanheng.backtest-source.v1' || data.read_only !== true || data.persistent !== true
    || !['unconfigured','invalid_path','invalid_archive','empty','available'].includes(data.state)
    || typeof data.reason !== 'string' || !data.reason || data.reason.length > 500) throw new Error('报告来源状态格式无效，请重新读取')
  return data
}

/** 仅在原目录读取失败后解释来源；普通报告主链继续沿原API和查询身份。 */
export default function BacktestSourceState() {
  const query = useQuery({queryKey:['backtest-source-state'],queryFn:({signal})=>fetchBacktestSource(signal),retry:false,
    refetchOnMount:'always',refetchOnWindowFocus:false,refetchOnReconnect:false})
  const data = query.data
  return <div aria-label="回测报告来源状态">
    {query.isPending ? <p role="status">正在核对报告目录配置…</p> : null}
    {query.isError ? <p role="alert">报告来源状态暂时无法读取，请核对观衡读取服务后重试。</p> : null}
    {data ? <p role={['invalid_path','invalid_archive'].includes(data.state)?'alert':'status'}>{data.reason}
      {data.state==='available' ? ' 本次目录请求未完成，可按“刷新历史报告”重新读取。' : ''}</p> : null}
    {query.isError ? <button onClick={()=>void query.refetch()}>重读报告来源状态</button> : null}
  </div>
}
