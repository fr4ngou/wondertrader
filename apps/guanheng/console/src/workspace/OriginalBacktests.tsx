import { useState } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import BacktestVisualChart, { reportDate, reportPct } from './BacktestVisualChart'
import { fetchOriginalLedger, fetchOriginalPerformance, fetchOriginalSignals, fetchOriginalVisuals, type OriginalArchiveEntry, type OriginalPerformance } from './originalBacktestApi'

const value = (n: number | null) => n === null ? '未知' : n.toLocaleString('zh-CN', { maximumFractionDigits: 8 })
const key = (e: OriginalArchiveEntry) => ['original-performance', e.run_id, e.receipt_sha256, e.report_sha256]
const label = (e: OriginalArchiveEntry) => `${e.configuration.label} · ${reportDate(Math.floor(e.configuration.start / 10000))} 至 ${reportDate(Math.floor(e.configuration.end / 10000))}`

function OriginalSignalTable({ entry, day }: {
  /** 当前不可变原版报告。 */ entry: OriginalArchiveEntry
  /** 原信号日筛选，独立于次日组合成交日。 */ day: number | null
}) {
  const [offset, setOffset] = useState(0)
  const query = useQuery({ queryKey: ['original-signals', entry.run_id, entry.receipt_sha256, day, offset], queryFn: ({ signal }) => fetchOriginalSignals(entry, day, offset, signal), retry: false, staleTime: Infinity })
  return <section className="bt-chart-panel" aria-label="原版算法信号"><h3>原算法 BUY / SELL 信号</h3><p className="bt-muted">按信号发生日筛选，价格为信号日收盘价；组合成交在下一交易日按原模型推进。</p>
    {query.isPending ? <p role="status">正在读取原算法信号…</p> : null}
    {query.isError ? <p role="alert">原算法信号读取失败。<button onClick={() => void query.refetch()}>重读算法信号</button></p> : null}
    {query.data ? <>{query.data.total ? <div className="bt-trade-table" role="region" aria-label="原算法信号表" tabIndex={0}><table><thead><tr><th>信号日</th><th>证券</th><th>动作</th><th>信号价</th><th>原算法理由</th></tr></thead><tbody>{query.data.signals.map(s => <tr key={s.index}><td>{reportDate(s.date)}</td><td>{s.symbol}</td><td>{s.action}</td><td>{value(s.price)}</td><td>{s.reason || '原报告未保存理由'}</td></tr>)}</tbody></table></div> : <p role="status">所选日期没有原算法信号。</p>}
      <div className="bt-pagination"><button disabled={!offset || query.isFetching} onClick={() => setOffset(offset - 50)}>信号上一页</button><span>{query.data.total} 个信号 · 第 {Math.floor(offset / 50) + 1} 页</span><button disabled={offset + 50 >= query.data.total || query.isFetching} onClick={() => setOffset(offset + 50)}>信号下一页</button></div></> : null}
  </section>
}

function OriginalTrades({ entry, day, dates, onDay }: {
  /** 当前不可变原版报告身份。 */ entry: OriginalArchiveEntry
  /** null查询所有交易，日期由图表或选择器显式选择。 */ day: number | null
  /** 当前报告的已核日期，不跨报告复用。 */ dates: number[]
  /** 切换日期同时由父级重建本页分页状态。 */ onDay: (day: number | null) => void
}) {
  const [offset, setOffset] = useState(0)
  const query = useQuery({ queryKey: ['original-ledger', entry.run_id, entry.receipt_sha256, day, offset],
    queryFn: ({ signal }) => fetchOriginalLedger(entry, day, offset, signal), retry: false, staleTime: Infinity })
  return <section className="bt-chart-panel" aria-label="原版模拟调仓">
    <h3>组合模拟调仓</h3>
    <label>交易日<select aria-label="原版交易日" value={day ?? ''} onChange={e => onDay(e.target.value ? Number(e.target.value) : null)}>
      <option value="">全部交易日</option>{dates.map(d => <option key={d} value={d}>{reportDate(d)}</option>)}
    </select></label>
    <p className="bt-muted">成交额为归一化权益，模型份额为该成交额除以价格。BUY/SELL 是开平动作，REFILL/TRIM 是等权调仓动作。日末持仓数量未保存在原报告中。</p>
    {query.isPending ? <p role="status">正在读取模拟调仓…</p> : null}
    {query.isError ? <p role="alert">模拟调仓读取失败。<button onClick={() => void query.refetch()}>重读模拟调仓</button></p> : null}
    {query.data ? <>
      {!query.data.trades_available ? <p role="status">模拟成交原件未知。</p> : query.data.total === 0 ? <p role="status">所选日期没有组合模拟调仓。</p> : <div className="bt-trade-table" role="region" aria-label="原版模拟调仓表" tabIndex={0}><table>
        <thead><tr><th>成交日</th><th>信号日</th><th>证券</th><th>动作</th><th>价格</th><th>模型份额</th><th>归一化成交额</th></tr></thead>
        <tbody>{query.data.trades.map(t => <tr key={t.index}><td>{reportDate(t.date)}</td><td>{reportDate(t.signal_date)}</td><td>{t.symbol}</td><td>{t.action}</td><td>{value(t.price)}</td><td>{value(t.quantity)}</td><td>{value(t.amount)}</td></tr>)}</tbody>
      </table></div>}
      <div className="bt-pagination"><button disabled={!offset || query.isFetching} onClick={() => setOffset(offset - 50)}>上一页</button><span>{query.data.total} 笔 · 第 {Math.floor(offset / 50) + 1} 页</span><button disabled={offset + 50 >= query.data.total || query.isFetching} onClick={() => setOffset(offset + 50)}>下一页</button></div>
    </> : null}
  </section>
}

function OriginalAnalysis({ entry, entries, left, right, comparison, onOpen }: {
  /** 主报告目录，按实际身份筛选。 */ entry: OriginalArchiveEntry
  /** 全部同策略报告，保留各自完成证明。 */ entries: OriginalArchiveEntry[]
  /** 已核主绩效，归一化权益。 */ left: OriginalPerformance
  /** 可选对比绩效，使用自身输入和归一化权益。 */ right?: OriginalPerformance
  /** 当前同策略对比报告。 */ comparison?: OriginalArchiveEntry
  /** 报告选择由URL拥有，刷新可恢复。 */ onOpen: (run: string, compare?: string) => void
}) {
  const [mode, setMode] = useState<'return' | 'nav'>('return')
  const [markers, setMarkers] = useState(true)
  const [day, setDay] = useState<number | null>(null)
  const [outsideDay, setOutsideDay] = useState<number | null>(null)
  function selectDay(candidate: number | null) {
    // 图表日期并集仅用于比较；主报告明细保持自己的真实覆盖，不发越界查询。
    if (candidate !== null && !left.points.some(point => point[0] === candidate)) {
      setOutsideDay(candidate)
      return
    }
    setOutsideDay(null)
    setDay(candidate)
  }
  const visual = useQuery({ queryKey: ['original-visuals', entry.run_id, entry.receipt_sha256], queryFn: ({ signal }) => fetchOriginalVisuals(entry, signal), retry: false, staleTime: Infinity })
  const rightVisual = useQuery({ queryKey: ['original-visuals', comparison?.run_id, comparison?.receipt_sha256], queryFn: ({ signal }) => fetchOriginalVisuals(comparison!, signal), enabled: !!comparison && !!right, retry: false, staleTime: Infinity })
  const metrics = [['总收益', reportPct(left.metrics.total_return_pct)], ['日末最大回撤', reportPct(left.metrics.observed_max_drawdown_pct)], ['期末归一化权益', value(left.metrics.last_equity)], ['模型费用', '0']]
  return <section className="bt-analysis" aria-label="原版回测分析">
    <header className="bt-report-toolbar"><h2>回测分析</h2><label>主报告<select aria-label="选择历史回测" value={entry.run_id} onChange={e => onOpen(e.target.value, comparison?.run_id)}>{entries.map(e => <option key={e.run_id} value={e.run_id}>{label(e)}</option>)}</select></label>
      <label>对比报告<select aria-label="选择比较报告" value={comparison?.run_id ?? ''} onChange={e => onOpen(entry.run_id, e.target.value || undefined)}><option value="">未选择</option>{entries.filter(e => e.run_id !== entry.run_id).map(e => <option key={e.run_id} value={e.run_id}>{label(e)}</option>)}</select></label></header>
    <p className="bt-report-meta">{label(entry)} · {left.data_kind} · 初始归一化权益 1</p>
    <dl className="bt-metric-strip">{metrics.map(([name, shown], i) => <div key={name}><dt>{name}</dt><dd className={i === 0 ? 'bt-return' : ''}>{shown}</dd>{right ? <small>对比：{i === 0 ? reportPct(right.metrics.total_return_pct) : i === 1 ? reportPct(right.metrics.observed_max_drawdown_pct) : i === 2 ? value(right.metrics.last_equity) : '0'}</small> : null}</div>)}</dl>
    <p className="bt-muted">原版模型：下一交易日收盘成交，浮点模型份额，零费用；权益初值为 1。历史首次可知时点资格待核实。</p>
    {comparison ? <p className="bt-comparison-note">对比：{label(comparison)}。各报告保留自己的价格、特征历史与起始持仓状态；区间和输入不同会影响结果。</p> : null}
    {visual.isError || rightVisual.isError ? <p role="alert">交易标记与回撤明细读取失败，权益曲线仍保留。<button onClick={() => { void visual.refetch(); if (comparison) void rightVisual.refetch() }}>重读图表明细</button></p> : null}
    <section className="bt-chart-panel" aria-label="收益与回撤"><div className="bt-chart-controls"><div className="bt-segments"><button aria-pressed={mode === 'return'} onClick={() => setMode('return')}>收益率</button><button aria-pressed={mode === 'nav'} onClick={() => setMode('nav')}>归一化权益</button></div><label><input type="checkbox" checked={markers} onChange={e => setMarkers(e.target.checked)} />模拟调仓标记</label></div>
      <BacktestVisualChart left={left} right={right} visual={visual.data} rightVisual={rightVisual.data} equityUnit="normalized-equity" mode={mode} markers={markers} onDay={selectDay} />
      <p className="bt-muted">点选日期查看主报告模拟调仓，滚轮可缩放；键盘用户可使用交易日选择器。</p>
    </section>
    {outsideDay !== null ? <p role="status">{reportDate(outsideDay)} 仅在对比报告中，当前仍显示主报告明细。请选择主报告覆盖的交易日。</p> : null}
    <OriginalTrades key={entry.run_id + entry.receipt_sha256 + day} entry={entry} day={day} dates={left.points.map(p => p[0])} onDay={selectDay} />
    <OriginalSignalTable key={'signals' + entry.run_id + entry.receipt_sha256 + day} entry={entry} day={day} />
    <OriginalEquityTable key={entry.run_id + entry.receipt_sha256} value={left} />
  </section>
}

function OriginalEquityTable({ value: report }: {
  /** 当前原版报告的日期和原数值，分页不会重算金融指标。 */ value: OriginalPerformance
}) {
  const [page, setPage] = useState(0)
  return <details className="bt-exact-table"><summary>日期与归一化权益原值</summary><div className="bt-trade-table" role="region" aria-label="原版权益原值" tabIndex={0}><table><thead><tr><th>交易日</th><th>归一化权益原值</th></tr></thead><tbody>{report.points.slice(page * 50, page * 50 + 50).map(([day, equity]) => <tr key={day}><td>{reportDate(day)}</td><td>{equity ?? '观察缺失'}</td></tr>)}</tbody></table></div><div className="bt-pagination"><button disabled={!page} onClick={() => setPage(page - 1)}>净值上一页</button><span>第 {page + 1} 页</span><button disabled={(page + 1) * 50 >= report.points.length} onClick={() => setPage(page + 1)}>净值下一页</button></div></details>
}

/** 沿用原回测列表与分析布局，原版分支保持归一化模型及独立缓存身份。 */
export default function OriginalBacktests({ entries, runId, compareId, onOpen }: {
  /** 当前原版策略的已核目录条目。 */ entries: OriginalArchiveEntry[]
  /** URL拥有的主报告ID；null显示列表。 */ runId: string | null
  /** URL拥有的对比报告ID；null表示未选择。 */ compareId: string | null
  /** 复用父工作区的URL报告选择。 */ onOpen: (run: string, compare?: string) => void
}) {
  const [mainId, setMainId] = useState('')
  const [rightId, setRightId] = useState('')
  const main = entries.find(e => e.run_id === (runId ?? mainId)) ?? (!runId ? entries[0] : undefined)
  const right = entries.find(e => e.run_id === (runId ? compareId : rightId) && e !== main)
  const chosen = [main, right].filter((e): e is OriginalArchiveEntry => !!e)
  const queries = useQueries({ queries: chosen.map(e => ({ queryKey: key(e), queryFn: ({ signal }: { signal: AbortSignal }) => fetchOriginalPerformance(e, signal), retry: false, staleTime: Infinity })) })
  const performance = new Map(chosen.map((e, i) => [e.run_id, queries[i]]))
  const leftValue = main ? performance.get(main.run_id)?.data : undefined
  const rightValue = right ? performance.get(right.run_id)?.data : undefined
  return <>
    {queries.some(q => q.isError) ? <p role="alert">所选原版报告读取失败。<button onClick={() => { for (const q of queries.filter(q => q.isError)) void q.refetch() }}>重读所选绩效</button></p> : null}
    {runId ? !main ? <p role="status">当前策略下未取得该原版报告，请返回列表重新选择。</p> : compareId && !right ? <p role="status">当前策略下未取得该对比报告。<button onClick={() => onOpen(runId)}>重新选择对比报告</button></p> : !leftValue ? <p role="status">正在读取原版报告…</p> : <OriginalAnalysis key={main.run_id + main.receipt_sha256 + compareId} entry={main} entries={entries} left={leftValue} right={rightValue} comparison={right} onOpen={onOpen} /> : <>
      <p className="bt-list-count">当前策略的回测 · {entries.length} 份已完成报告</p>
      {!entries.length ? <p role="status">该策略暂无已保存的回测报告。</p> : <>
        <div className="bt-report-list" role="region" aria-label="策略回测列表" tabIndex={0}><table><thead><tr><th>主报告</th><th>回测区间</th><th>初始归一化权益</th><th>总收益</th><th>最大日末回撤</th><th>操作</th></tr></thead><tbody>{entries.map((e, i) => <tr key={e.run_id} className={e === main ? 'bt-list-main' : ''}><td><input type="radio" name="original-main" aria-label={`主报告 ${i + 1}`} checked={e === main} onChange={() => setMainId(e.run_id)} /></td><td><strong>{label(e)}</strong><small>{e.record_count} 期</small></td><td>1</td><td className="bt-return">{performance.get(e.run_id)?.data ? reportPct(performance.get(e.run_id)!.data!.metrics.total_return_pct) : '—'}</td><td>{performance.get(e.run_id)?.data ? reportPct(performance.get(e.run_id)!.data!.metrics.observed_max_drawdown_pct) : '—'}</td><td><div className="bt-list-actions"><button onClick={() => onOpen(e.run_id)}>查看分析</button><button disabled={e === main} aria-pressed={e === right} onClick={() => setRightId(e === right ? '' : e.run_id)}>{e === right ? '取消对比' : '设为对比'}</button></div></td></tr>)}</tbody></table></div>
        {main ? <div className="bt-list-selection"><span>主报告：{label(main)}{right ? `；对比：${label(right)}` : ''}</span><button onClick={() => onOpen(main.run_id, right?.run_id)}>{right ? '打开对比分析' : '打开回测分析'}</button></div> : null}
      </>}
    </>}
  </>
}
