import { absoluteChinaTime } from '../components/RelativeTime'
import type { StrategyDetails } from './strategyDetailsApi'
import { useStrategyTargetHistory } from './strategyTargetHistoryApi'

const quantity = (value: number) => value.toLocaleString('zh-CN')
const weight = (value: number) => value.toLocaleString('zh-CN', { style: 'percent', maximumFractionDigits: 2 })

export function StrategyPositionTargets({ details }: { details: StrategyDetails }) {
  const query = useStrategyTargetHistory(details.strategy, null)
  const summary = query.data?.source?.latest_targets
  const latest = new Map(summary?.map(row => [row.symbol, row]))
  const positions = new Map(details.calculation?.positions.map(row => [row.symbol, row]))
  const symbols = [...new Set([...positions.keys(), ...latest.keys()])].sort()
  return <section aria-label="目标仓位汇总">
    <h4>目标仓位汇总</h4>
    {query.isError && <p role="status">最近目标变化读取失败。{query.data && <>当前显示 {absoluteChinaTime(query.data.observed_at)} 的记录。</>}</p>}
    {query.isFetching && !query.data && <p role="status">正在读取最近目标变化…</p>}
    {query.data?.state === 'available' && !summary && <p role="status">当前服务尚未提供逐标的变化汇总。</p>}
    {query.data && query.data.state !== 'available' && <p role="status">{query.data.reason}</p>}
    {query.data?.source?.incomplete_tail && <p role="status">原生记录末行仍在写入，汇总显示已完整写入的变化。</p>}
    {symbols.length > 0 ? <div className="account-table-scroll" role="region" aria-label="逐标的目标与最近变化" tabIndex={0}>
      <table><thead><tr><th>证券</th><th>目标仓位</th><th>最近记录目标（份）</th><th>上次变化（份）</th><th>记录时间</th></tr></thead>
        <tbody>{symbols.map(symbol => {
          const target = latest.get(symbol)
          const currentWeight = positions.get(symbol)?.target_weight
          return <tr key={symbol}>
            <th scope="row"><StrategySecurityLabel symbol={symbol} names={details.security_names} /></th>
            <td>{currentWeight == null ? '—' : weight(currentWeight)}</td>
            <td>{target ? quantity(target.target_quantity) : '—'}</td>
            <td>{target ? target.previous_target_quantity === null ? '首次记录' : `${quantity(target.previous_target_quantity)} → ${quantity(target.target_quantity)}` : '—'}</td>
            <td>{target ? absoluteChinaTime(target.changed_at) : '—'}</td>
          </tr>
        })}</tbody></table>
    </div> : <p>尚未取得逐标的目标仓位。</p>}
  </section>
}

export function StrategySecurityLabel({ symbol, names }: { symbol: string; names?: Record<string, string> }) {
  const name = Object.hasOwn(names ?? {}, symbol) ? names?.[symbol] : undefined
  return name ? <>{name} <small>{symbol}</small></> : <>{symbol}</>
}
