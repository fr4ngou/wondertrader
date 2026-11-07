import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { fetchStrategyCatalog, type StrategyDefinition } from './strategyCatalogApi'
import type { ArchiveEntry } from './backtestApi'
import './strategy-catalog.css'

export const strategyKey = (strategy: Pick<StrategyDefinition, 'strategy_id' | 'strategy_version'>) => `${strategy.strategy_id}@${strategy.strategy_version ?? 'unknown'}`

const versionOrder = new Intl.Collator('en', { numeric: true })
const releaseVersion = /^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:(a|b|rc)(\d+))?$/
const stages = ['a', 'b', 'rc', undefined]
function newestFirst(left: StrategyDefinition, right: StrategyDefinition) {
  const a = left.strategy_version
  const b = right.strategy_version
  if (a === null || b === null) return Number(a === null) - Number(b === null)
  const x = releaseVersion.exec(a), y = releaseVersion.exec(b)
  if (!x || !y) return versionOrder.compare(b, a)
  return versionOrder.compare(`${y[1]}.${y[2] ?? '0'}.${y[3] ?? '0'}`, `${x[1]}.${x[2] ?? '0'}.${x[3] ?? '0'}`)
    || stages.indexOf(y[4]) - stages.indexOf(x[4]) || versionOrder.compare(y[5] ?? '', x[5] ?? '')
}

type StrategyVersion = StrategyDefinition & {
  /** 该身份仅由完成归档发现。 */ historyOnly?: boolean
}
type StrategyGroup = {
  /** 策略发布和归档共用的稳定策略 ID。 */ id: string
  /** 同一策略族使用的中文名称，陌生身份回退到原 ID。 */ name: string
  /** 该族实际登记、发布或已保存的版本，按版本顺序排列。 */ versions: StrategyVersion[]
}

/** 目录拥有可选身份；URL保留用户选择，未知深链接等待用户重新选择。 */
export function useStrategySelection(entries: readonly ArchiveEntry[] = [], preferArchive = false) {
  const [params, setParams] = useSearchParams()
  const published = useQuery({ queryKey: ['strategy-catalog'], queryFn: ({ signal }) => fetchStrategyCatalog(signal),
    retry: false, refetchInterval: 15_000, refetchOnWindowFocus: false, refetchOnReconnect: false })
  // 活动目录与已准入的历史报告各保留自身版本；衍生合并复用原查询缓存。
  const definitions = new Map<string, StrategyVersion>((published.data ?? []).map(item => [strategyKey(item), item]))
  const names = new Map<string, string>()
  for (const item of definitions.values()) if (!names.has(item.strategy_id)) names.set(item.strategy_id, item.display_name)
  const archived = new Set<string>()
  for (const { summary } of entries) if (summary) {
    const { id, version } = summary.strategy
    const item: StrategyVersion = { strategy_id: id, strategy_version: version, display_name: names.get(id) ?? id,
      description: '已保存的历史回测结果。', historical_versions: [], historyOnly: true }
    const key = strategyKey(item)
    archived.add(key)
    if (!definitions.has(key)) definitions.set(key, item)
  }
  const groups = new Map<string, StrategyGroup>()
  for (const item of definitions.values()) {
    let group = groups.get(item.strategy_id)
    if (!group) {
      group = { id: item.strategy_id, name: item.display_name, versions: [] }
      groups.set(item.strategy_id, group)
    }
    group.versions.push(item)
  }
  for (const group of groups.values()) group.versions.sort(newestFirst)
  function defaultVersion(group: StrategyGroup) {
    return (preferArchive ? group.versions.find(item => archived.has(strategyKey(item)))
      : group.versions.find(item => !item.historyOnly)) ?? group.versions[0]
  }
  const requested = params.get('strategy')
  const firstGroup = groups.values().next().value
  const selected = requested ? definitions.get(requested) : firstGroup && defaultVersion(firstGroup)
  function selectVersion(value: string) {
    const next = new URLSearchParams(params)
    next.set('strategy', value)
    next.delete('run'); next.delete('compare')
    setParams(next)
  }
  function selectStrategy(id: string) {
    const group = groups.get(id)
    if (group) selectVersion(strategyKey(defaultVersion(group)))
  }
  return { query: published, groups, selected, selectStrategy, selectVersion, requested }
}

/** 复用目录身份的显式选择器；加载、空目录及失效链接分别呈现。 */
export function StrategyPicker({ selection, archivePending = false }: {
  /** 当前页面的目录查询及URL选择状态。 */ selection: ReturnType<typeof useStrategySelection>
  /** 轻量归档还在读取时，深链接继续等待旧版本归属。 */ archivePending?: boolean
}) {
  const { query, groups, selected, selectStrategy, selectVersion, requested } = selection
  const group = selected && groups.get(selected.strategy_id)
  return <div className="strategy-picker">
    <label>选择策略<select value={group?.id ?? ''} disabled={!groups.size} onChange={event => selectStrategy(event.target.value)}>
      {!selected ? <option value="">{query.isPending ? '正在读取策略…' : '请选择策略'}</option> : null}
      {[...groups.values()].map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
    </select></label>
    <label>选择版本<select value={selected ? strategyKey(selected) : ''} disabled={!group} onChange={event => selectVersion(event.target.value)}>
      {!group ? <option value="">请先选择策略</option> : null}
      {group?.versions.map(item => <option key={strategyKey(item)} value={strategyKey(item)}>{item.strategy_version === null ? '版本未提供' : `v${item.strategy_version}`}{item.catalog_status === 'registered' ? ' · 已登记' : item.historyOnly ? ' · 历史' : ''}</option>)}
    </select></label>
    {query.isError ? <div role="alert">策略目录读取失败。<button onClick={() => void query.refetch()}>重新读取策略</button></div> : null}
    {query.isSuccess && !groups.size && !archivePending ? <p role="status">当前没有登记策略。</p>
      : requested && !selected && (query.isSuccess || query.isError) ? <p role="status">{archivePending ? '正在核对历史策略版本…' : '该策略当前不在目录中，请重新选择。'}</p> : null}
  </div>
}
