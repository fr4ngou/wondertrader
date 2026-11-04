import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { fetchStrategyCatalog, type StrategyDefinition } from './strategyCatalogApi'
import './strategy-catalog.css'

export const strategyKey = (strategy: Pick<StrategyDefinition, 'strategy_id' | 'strategy_version'>) => `${strategy.strategy_id}@${strategy.strategy_version ?? 'unknown'}`

/** 目录拥有可选身份；URL保留用户选择，未知深链接等待用户重新选择。 */
export function useStrategySelection(saved: StrategyDefinition[] = []) {
  const [params, setParams] = useSearchParams()
  const published = useQuery({ queryKey: ['strategy-catalog'], queryFn: ({ signal }) => fetchStrategyCatalog(signal),
    retry: false, refetchInterval: 15_000, refetchOnWindowFocus: false, refetchOnReconnect: false })
  // 活动目录与已准入的历史报告各保留自身版本；衍生合并复用原查询缓存。
  const definitions = new Map((published.data ?? []).map(item => [strategyKey(item), item]))
  for (const item of saved) if (!definitions.has(strategyKey(item))) definitions.set(strategyKey(item), item)
  const query = { ...published, data: published.data || saved.length ? [...definitions.values()] : undefined }
  const requested = params.get('strategy')
  const selected = requested ? query.data?.find(item => strategyKey(item) === requested) : query.data?.[0]
  function select(value: string) {
    const next = new URLSearchParams(params)
    next.set('strategy', value)
    next.delete('run'); next.delete('compare')
    setParams(next)
  }
  return { query, selected, select, requested }
}

/** 复用目录身份的显式选择器；加载、空目录及失效链接分别呈现。 */
export function StrategyPicker({ selection }: {
  /** 当前页面的目录查询及URL选择状态。 */ selection: ReturnType<typeof useStrategySelection>
}) {
  const { query, selected, select, requested } = selection
  return <div className="strategy-picker">
    <label>选择策略<select aria-label="选择策略" value={selected ? strategyKey(selected) : ''}
      disabled={!query.data?.length} onChange={event => select(event.target.value)}>
      {!selected ? <option value="">{query.isPending ? '正在读取策略…' : '请选择策略'}</option> : null}
      {query.data?.map(item => <option key={strategyKey(item)} value={strategyKey(item)}>{item.display_name} · {item.strategy_version === null ? '版本未提供' : `v${item.strategy_version}`} </option>)}
    </select></label>
    {query.isError ? <div role="alert">策略目录读取失败。<button onClick={() => void query.refetch()}>重新读取策略</button></div> : null}
    {query.data?.length === 0 ? <p role="status">当前没有登记策略。</p> : requested && query.data && !selected ? <p role="status">该策略当前不在目录中，请重新选择。</p> : null}
  </div>
}
