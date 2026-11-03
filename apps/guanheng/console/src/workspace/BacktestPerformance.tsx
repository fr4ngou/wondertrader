import { useEffect, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { RefreshCw, Triangle, Circle } from 'lucide-react'
import type { ArchiveEntry } from './backtestApi'
import { differenceNames, fetchBacktestComparison, fetchBacktestPerformance, type BacktestPerformance as Performance } from './backtestPerformanceApi'
import { fetchVisuals } from './backtestVisualApi'
import { backtestMoney } from './backtestMoney'
import BacktestVisualChart, { reportDate, reportPct } from './BacktestVisualChart'
import BacktestDateDetail from './BacktestDateDetail'
import './backtest-performance.css'
import { performanceKey } from './useBacktestReports'

export const reportKey = (e: ArchiveEntry) => e.run_id + e.receipt_sha256
/** 报告序号仅用于区分选项，本金只取已核验绩效；标签不参与金融推断。 */
export const reportLabel = (e: ArchiveEntry, capital?: string, number = 1) => `报告${number} · ${capital === undefined ? '本金待读取' : `${backtestMoney(capital)}元`} · 至${reportDate(Math.floor(e.configuration.end / 10000))} · ${e.record_count}期`

function ExactDateTable({ value, label }: {
  /** 同一已核验报告的原精度日期净值。 */ value: Performance
  /** 主报告或对比报告业务名称。 */ label: string
}) {
  const [page, setPage] = useState(0)
  return <details className="bt-exact-table"><summary>{label} · 日期与净值原值</summary>
    <div className="bt-trade-table" tabIndex={0} role="region" aria-label={`${label}日期净值表`}><table><thead><tr><th>交易日</th><th>日末净值原值（元）</th></tr></thead><tbody>{value.points.slice(page * 50, page * 50 + 50).map(([date, nav]) => <tr key={date}><td>{reportDate(date)}</td><td>{nav ?? '观察缺失'}</td></tr>)}</tbody></table></div>
    <div className="bt-pagination"><button disabled={page === 0} onClick={() => setPage(page - 1)}>净值上一页</button><span>第 {page + 1} 页</span><button disabled={(page + 1) * 50 >= value.points.length} onClick={() => setPage(page + 1)}>净值下一页</button></div>
  </details>
}

/** 报告身份隔离所有查询；刷新失败保留同一报告的成功结果。 */
export default function BacktestPerformance({ entry, entries, ready = true, mainSelector, capitalLabels = {}, onReport, onRefreshArchive, archiveRefreshing = false, initialComparison = '' }: {
  /** 主报告完成身份。 */ entry: ArchiveEntry
  /** 同一来源可选归档。 */ entries: ArchiveEntry[]
  /** 来源准入开关。 */ ready?: boolean
  /** 页面拥有的主报告选择器。 */ mainSelector?: ReactNode
  /** 由已核验报告所得本金，按运行与收据隔离；未读取保持未知。 */ capitalLabels?: Readonly<Record<string, string>>
  /** 将已核验的业务元数据交还页面生成选择标签。 */ onReport?: (value: Performance) => void
  /** 刷新原归档目录，发现WT后来保存的回测；不执行回测。 */ onRefreshArchive?: () => void
  /** 目录已在刷新时合并重复刷新操作。 */ archiveRefreshing?: boolean
  /** 从同策略列表带入的初始对比报告；本组件继续校验可选集合。 */ initialComparison?: string
}) {
  const [rightId, setRightId] = useState(initialComparison)
  const [mode, setMode] = useState<'return' | 'nav'>('return')
  const [markers, setMarkers] = useState(true)
  const [day, setDay] = useState<number | null>(null)
  const [detailSide, setDetailSide] = useState('left')
  const right = entries.find(e => e.run_id === rightId && e.run_id !== entry.run_id)
  const single = useQuery({ queryKey: performanceKey(entry),
    queryFn: ({ signal }) => fetchBacktestPerformance(entry, signal), enabled: ready && !right, staleTime: Infinity, retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false })
  const comparison = useQuery({ queryKey: ['backtest-comparison', entry.run_id, entry.receipt_sha256, right?.run_id, right?.receipt_sha256],
    queryFn: ({ signal }) => fetchBacktestComparison(entry, right!, signal), enabled: ready && !!right, retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false })
  const current = right ? comparison : single
  const leftValue = right ? comparison.data?.left : single.data
  const rightValue = right ? comparison.data?.right : undefined
  useEffect(() => { if (leftValue) onReport?.(leftValue); if (rightValue) onReport?.(rightValue) }, [leftValue, rightValue, onReport])
  const visual = useQuery({ queryKey: ['backtest-visuals', entry.run_id, entry.receipt_sha256, entry.report_sha256], queryFn: ({ signal }) => fetchVisuals(entry, signal),
    enabled: ready && !!leftValue, retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false })
  const rightVisual = useQuery({ queryKey: ['backtest-visuals', right?.run_id, right?.receipt_sha256, right?.report_sha256], queryFn: ({ signal }) => fetchVisuals(right!, signal),
    enabled: ready && !!right && !!rightValue, retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false })
  const detailEntry = detailSide === 'right' && right ? right : entry
  const detailValue = detailSide === 'right' && rightValue ? rightValue : leftValue
  const selectedDay = day ?? detailValue?.points.at(-1)?.[0] ?? null
  const metrics = leftValue?.metrics
  const metricItems = metrics ? [['总收益', reportPct(metrics.total_return_pct)], ['日末最大回撤', reportPct(metrics.observed_max_drawdown_pct)],
    ['期末净值（元）', backtestMoney(metrics.last_nav_cny)], ['累计费用（元）', backtestMoney(metrics.native_cumulative_fees_cny)]] : []
  return <section className="bt-analysis" aria-label="回测绩效与比较">
    <header className="bt-report-toolbar"><h1>回测分析</h1>{mainSelector}<label>对比报告<select aria-label="选择比较报告" value={right?.run_id ?? ''} onChange={e => { setRightId(e.target.value); setDetailSide('left') }}>
      <option value="">未选择</option>{entries.filter(e => e.run_id !== entry.run_id).map(e => <option key={e.run_id} value={e.run_id}>{reportLabel(e, capitalLabels[reportKey(e)], entries.indexOf(e) + 1)}</option>)}
    </select></label><button className="bt-refresh" aria-label="重新读取绩效" title="刷新报告目录与当前绩效" disabled={current.isFetching || archiveRefreshing || !ready} onClick={() => { onRefreshArchive?.(); void current.refetch() }}><RefreshCw size={18} /></button></header>
    {current.isFetching ? <p role="status">正在读取报告…{leftValue ? '当前保留上次结果。' : ''}</p> : null}
    {current.isError ? <p role="alert">报告读取失败。{leftValue ? '当前保留上次结果及原读取时间。' : ''}请重新读取。</p> : null}
    {leftValue && metrics ? <>
      <div className="bt-report-meta">版本 {leftValue.strategy.version} · {reportDate(Math.floor(leftValue.configuration.start / 10000))} 至 {reportDate(Math.floor(leftValue.configuration.end / 10000))} · 初始本金 {backtestMoney(metrics.initial_capital_cny)} 元</div>
      <dl className="bt-metric-strip">{metricItems.map(([label, value], i) => <div key={label}><dt>{label}</dt><dd className={i === 0 ? 'bt-return' : ''}>{value}</dd>{rightValue ? <small>对比：{i === 0 ? reportPct(rightValue.metrics.total_return_pct) : i === 1 ? reportPct(rightValue.metrics.observed_max_drawdown_pct) : backtestMoney(i === 2 ? rightValue.metrics.last_nav_cny : rightValue.metrics.native_cumulative_fees_cny)}</small> : null}</div>)}</dl>
      {rightValue ? <p className="bt-comparison-note">对比本金 {backtestMoney(rightValue.metrics.initial_capital_cny)} 元 · 至 {reportDate(Math.floor(rightValue.configuration.end / 10000))}。{comparison.data?.differences.length ? `条件差异：${comparison.data.differences.map(k => differenceNames[k]).join('、')}。` : '所列输入和模型条件一致。'}</p> : null}
      {!leftValue.observations.available ? <p role="status">暂无有效资金记录，绩效与曲线未知。</p> : <div className="bt-analysis-grid">
        <section className="bt-chart-panel" aria-label="收益与回撤">
          <div className="bt-chart-controls"><div className="bt-segments"><button aria-pressed={mode === 'return'} onClick={() => setMode('return')}>收益率</button><button aria-pressed={mode === 'nav'} onClick={() => setMode('nav')}>净值</button></div>
            <label className="bt-marker-toggle"><input type="checkbox" checked={markers} onChange={e => setMarkers(e.target.checked)} />买卖标记</label>
            <span className="bt-marker-key"><Triangle size={10} fill="#e54351" color="#e54351" />买入 <Triangle size={10} fill="#008c63" color="#008c63" className="bt-sell-symbol" />卖出 <Circle size={9} fill="#8a55d9" color="#8a55d9" />多笔</span>
          </div>
          {visual.isError || right && rightVisual.isError ? <p role="alert">交易标记与回撤明细读取失败，净值曲线仍保留。<button onClick={() => { void visual.refetch(); if (right) void rightVisual.refetch() }}>重读图表明细</button></p> : null}
          {visual.isFetching ? <p className="bt-muted" role="status">正在读取日收益、回撤和成交日…</p> : null}
          {visual.data && !visual.data.trades_available ? <p className="bt-muted" role="status">主报告的成交原件暂未适配，买卖标记未知。</p> : null}
          {right && rightVisual.data && !rightVisual.data.trades_available ? <p className="bt-muted" role="status">对比报告的成交原件暂未适配，买卖标记未知。</p> : null}
          <BacktestVisualChart left={leftValue} right={rightValue} visual={visual.data} rightVisual={rightVisual.data} mode={mode} markers={markers} onDay={setDay} />
          <p className="bt-muted bt-chart-caption">点选日期查看持仓与交易，滚轮可缩放。</p>
        </section>
        <div className="bt-inspector-wrap">{right ? <label className="bt-detail-source">日期明细所属报告<select aria-label="日期明细所属报告" value={detailSide} onChange={e => setDetailSide(e.target.value)}><option value="left">主报告</option><option value="right">对比报告</option></select></label> : null}
          <BacktestDateDetail key={detailEntry.run_id + detailEntry.receipt_sha256 + selectedDay} entry={detailEntry} day={selectedDay} dates={detailValue?.points.map(p => p[0]) ?? []} onDay={setDay} />
        </div>
      </div>}
      <div className="bt-exact-values">
        <ExactDateTable key={leftValue.run_id + leftValue.receipt_sha256} value={leftValue} label="主报告" />
        {rightValue ? <ExactDateTable key={rightValue.run_id + rightValue.receipt_sha256} value={rightValue} label="对比报告" /> : null}
      </div>
    </> : null}
  </section>
}
