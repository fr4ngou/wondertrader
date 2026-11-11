import { useState } from 'react'
import { absoluteChinaTime } from '../components/RelativeTime'
import type { StrategyDefinition } from './strategyCatalogApi'
import { useStrategyTargetHistory } from './strategyTargetHistoryApi'
import { reportSymbol } from './backtestSymbols'
import './live-strategy.css'

/** 沿现有策略页标签/只读表格展示原生目标；跨策略由父级key清除旧页状态。 */
export default function StrategyTargetHistory({strategy}: {strategy: StrategyDefinition}) {
  const [cursors, setCursors] = useState<(string | null)[]>([null])
  const [expanded, setExpanded] = useState<string | null>(null)
  const cursor = cursors[cursors.length-1]
  const query = useStrategyTargetHistory(strategy, cursor)
  const data = query.data
  function refresh() { setExpanded(null); setCursors([null]); if (cursor === null) void query.refetch() }
  return <section className="surface-card live-strategy-panel target-history-panel" aria-label="目标仓位记录">
    <div className="operations-heading"><h3>目标仓位记录</h3><button disabled={query.isFetching} onClick={refresh}>{query.isFetching ? '正在读取…' : '刷新目标记录'}</button></div>
    <p className="live-strategy-note">按证券展示提交给 WT 的目标份数变化，时间来自 WT 行情时钟。目标设置与实际成交分别查看。</p>
    {query.isPending ? <p role="status">正在读取目标仓位记录…</p> : null}
    {query.isError ? <p role="alert">{query.error.message}{data ? '；当前保留上次成功记录及原时间。' : ''}<button onClick={refresh}>重新读取最新记录</button></p> : null}
    {data ? <>
      {data.source ? <p className="live-strategy-note">{data.source.changed_count} 次目标变化 · {data.source.initial_count} 条首次记录 · 已归并 {data.source.unchanged_count} 次同目标重复设置。读取于 {absoluteChinaTime(data.observed_at)}</p> : null}
      {data.state === 'available' ? <p className="live-strategy-attribution">{data.reason}</p> : null}
      {data.source?.incomplete_tail ? <p role="status">最新一条原生记录尚未写完，将在刷新后继续读取。</p> : null}
      {data.items.length ? <div className="live-table-scroll target-history-table" role="region" aria-label="目标份数变化" tabIndex={0}>
        <table><thead><tr><th>目标时间</th><th>证券</th><th>原目标（份）</th><th>新目标（份）</th><th>变动（份）</th><th>记录</th></tr></thead>
          <tbody>{data.items.map(item => <TargetRows key={item.id} item={item} expanded={expanded === item.id} toggle={() => setExpanded(expanded === item.id ? null : item.id)} />)}</tbody>
        </table>
      </div> : <p role="status">{data.state === 'available' ? '当前原生目标日志尚无完整记录。' : data.reason}</p>}
      <div className="target-history-pagination"><button disabled={cursors.length === 1 || query.isFetching} onClick={() => {setExpanded(null); setCursors(cursors.slice(0,-1))}}>较新记录</button><span>第 {cursors.length} 页</span><button disabled={!data.next_cursor || query.isFetching} onClick={() => {setExpanded(null); setCursors([...cursors, data.next_cursor])}}>较早记录</button></div>
    </> : null}
  </section>
}

function TargetRows({item, expanded, toggle}: {item: import('./strategyTargetHistoryApi').TargetHistoryItem; expanded: boolean; toggle: () => void}) {
  const amount = (v: number | null) => v === null ? '未记录' : v.toLocaleString('zh-CN')
  return <><tr>
    <td>{absoluteChinaTime(item.changed_at)}</td><td>{reportSymbol(item.symbol)}</td>
    <td>{amount(item.previous_target_quantity)}</td><td>{amount(item.target_quantity)}</td>
    <td>{item.kind === 'initial' ? '首次记录' : `${item.change_quantity! > 0 ? '+' : ''}${amount(item.change_quantity)}`}</td>
    <td><button aria-expanded={expanded} onClick={toggle}>{expanded ? '收起' : '查看详情'}</button></td>
  </tr>{expanded ? <tr><td colSpan={6}><div className="target-history-details">
    <span>原生日志序号：{item.sequence}</span><span>信号参考价：{item.reference_price_cny} 元/份</span>
    <span>历史算法版本：未记录</span><span>调整原因：原生记录未提供细分原因</span>
    {item.kind === 'initial' ? <span>这是该证券在当前日志中的首次记录，原目标保持未知。</span> : null}
  </div></td></tr> : null}</>
}
