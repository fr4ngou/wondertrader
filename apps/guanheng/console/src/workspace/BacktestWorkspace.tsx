import { Component, lazy, Suspense, type ReactNode } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { useBacktestArchiveSummaries } from './useBacktestReports'
import { reportKey, reportLabel } from './backtestPresentation'
import BacktestSourceState from './BacktestSourceState'
import { StrategyPicker, strategyKey, useStrategySelection } from './StrategyPicker'
import BacktestReportList, { type ReportItem } from './BacktestReportList'
import './backtest-performance.css'

// 完整分析及图表只随已选中的报告加载，列表共享的文字格式保持轻量。
const BacktestPerformance = lazy(() => import('./BacktestPerformance'))

/** 只隔离当前分析视图；归档目录与返回入口继续由外层工作区提供。 */
class BacktestAnalysisBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    if (this.state.failed) return <div>
      <p role="alert">回测分析页面加载失败。请检查连接后重新加载报告，或返回回测列表。</p>
      {/* 新document重建lazy与ESM加载状态，重新发起失败的分块请求；保留当前报告URL。 */}
      <button onClick={() => window.location.reload()}>重新加载报告</button>
    </div>
    return this.props.children
  }
}

/** 轻量归属目录先提供可选择列表，完整绩效只由主/对比选择读取。 */
export default function BacktestWorkspace() {
  const [params, setParams] = useSearchParams()
  const runId = params.get('run')
  const query = useBacktestArchiveSummaries()
  const entries = [...(query.data?.runs ?? [])].sort((a, b) => b.configuration.end - a.configuration.end || a.run_id.localeCompare(b.run_id))
  const selection = useStrategySelection(entries, true)
  const strategy = selection.selected
  const reports: ReportItem[] = entries.flatMap(entry => {
    const summary = entry.summary
    return summary && summary.strategy.id === strategy?.strategy_id && summary.strategy.version === strategy?.strategy_version ? [{ entry, summary }] : []
  })
  const unclassified = entries.filter(item => item.summary === null).length
  const selected = reports.find(item => item.entry.run_id === runId)
  const compareId = params.get('compare')
  const comparison = reports.find(item => item.entry.run_id === compareId && item !== selected)
  const capitals = Object.fromEntries(reports.map(item => [reportKey(item.entry), item.summary.initial_capital_cny]))
  function open(run: string, compare?: string) {
    if (!strategy) return
    const next = new URLSearchParams(params); next.set('strategy', strategyKey(strategy)); next.set('run', run)
    if (compare && compare !== run) next.set('compare', compare); else next.delete('compare')
    setParams(next)
  }
  function back() { const next = new URLSearchParams(params); next.delete('run'); next.delete('compare'); setParams(next) }
  return <section className="workspace-page bt-workspace">
    <header className="strategy-page-heading"><h1>{runId ? '回测' : '回测记录'}</h1><StrategyPicker selection={selection} archivePending={query.isPending} />
      {strategy ? <Link className="strategy-backtest-link" to={'/strategies?' + new URLSearchParams({ strategy: strategyKey(strategy) })}>查看策略 →</Link> : null}
      {!runId && strategy ? <button disabled={query.isFetching} onClick={() => void query.refetch()}>刷新列表</button> : null}
    </header>
      {query.isPending ? <p role="status">正在读取回测记录…</p> : null}
      {query.isError ? <><p role="alert">报告目录读取失败。{query.data ? '保留上次目录及读取时间。' : ''}</p><BacktestSourceState /><button onClick={() => void query.refetch()}>刷新历史报告</button></> : null}
      {query.data?.invalid_receipts ? <p role="alert">{query.data.invalid_receipts} 份报告未通过校验，请核查原件。</p> : null}
      {query.data?.unarchived_runs ? <p role="status">{query.data.unarchived_runs} 项运行尚未保存完成证明。</p> : null}
      {unclassified ? <p role="alert">{unclassified} 份报告的归属读取失败，其他报告仍可查看。<button disabled={query.isFetching} onClick={() => void query.refetch()}>重读报告目录</button></p> : null}
    {strategy ? <>
      {runId ? <>
        <button className="bt-back-list" onClick={back}>← 返回回测列表</button>
        {selected && compareId && !comparison ? <p role="status">当前策略下未取得该对比报告，请重新选择。<button onClick={() => open(runId)}>重新选择对比报告</button></p> : selected ? <BacktestAnalysisBoundary key={strategyKey(strategy) + selected.entry.run_id + selected.entry.receipt_sha256 + (compareId ?? '')}><Suspense fallback={<p role="status">正在读取所选报告…</p>}><BacktestPerformance
          entry={selected.entry} entries={reports.map(item => item.entry)} capitalLabels={capitals} initialComparison={params.get('compare') ?? ''}
          ready={true}
          onRefreshArchive={() => void query.refetch()} archiveRefreshing={query.isFetching}
          mainSelector={<label>主报告<select aria-label="选择历史回测" value={selected.entry.run_id} onChange={event => open(event.target.value, params.get('compare') ?? undefined)}>
            {reports.map((item, index) => <option key={item.entry.run_id} value={item.entry.run_id}>{reportLabel(item.entry, capitals[reportKey(item.entry)], index + 1)}</option>)}
          </select></label>} /></Suspense></BacktestAnalysisBoundary> : <p role="status">{query.isPending ? '正在读取所选报告…' : '当前策略下未取得该报告，请返回列表重新选择。'}</p>}
      </> : query.data ? <BacktestReportList key={strategyKey(strategy)} reports={reports} pending={false} unclassified={unclassified} onOpen={open} /> : null}
    </> : null}
  </section>
}
