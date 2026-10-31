import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { ArchiveEntry } from './backtestApi'
import { differenceNames, fetchBacktestComparison, fetchBacktestPerformance, type BacktestPerformance as Performance } from './backtestPerformanceApi'
import './backtest-performance.css'
import { HISTORICAL_REPORT_SCHEMA } from './backtestHistorical'
import { isRetainedReport } from './backtestRetained'
import { backtestMoney } from './backtestMoney'

const date = (day: number | null) => day === null ? '—' : `${String(day).slice(0, 4)}-${String(day).slice(4, 6)}-${String(day).slice(6, 8)}`
const time = (minute: number) => `${date(Math.floor(minute / 10000))} ${String(minute).slice(-4, -2)}:${String(minute).slice(-2)}`
const pct = (value: number | null) => value === null ? '不可用' : `${value.toLocaleString('zh-CN', { maximumFractionDigits: 4 })}%`

/** 曲线只连相邻已观察日末；未知点切断线段，金额原值保留在日期表。 */
function EquityCurve({ value }: { value: Performance }) {
  const numbers = value.points.map(([, nav]) => nav === null ? null : Number(nav))
  const observed = numbers.filter((nav): nav is number => nav !== null)
  if (!observed.length) return null
  if (observed.some(nav => !Number.isFinite(nav))) return <p>部分净值超出图表数值范围，请查看原始日期表。</p>
  const low = Math.min(...observed); const high = Math.max(...observed)
  const scale = Math.max(Math.abs(low), Math.abs(high), 1)
  const bottom = low / scale; const span = high / scale - bottom
  let commands = ''; let consecutive = false
  numbers.forEach((nav, i) => {
    if (nav === null) { consecutive = false; return }
    const x = 24 + i / Math.max(numbers.length - 1, 1) * 672
    const y = span === 0 ? 100 : 172 - (nav / scale - bottom) / span * 144
    commands += `${consecutive ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)} `
    consecutive = true
  })
  return <figure className="backtest-equity"><figcaption>模型日末净值（元） · 缺失观察处断开</figcaption>
    <svg viewBox="0 0 720 200" role="img" aria-label="已观察日末模型净值曲线" preserveAspectRatio="xMidYMid meet">
      <line x1="24" x2="696" y1="172" y2="172" stroke="currentColor" opacity=".2" />
      <path d={commands} fill="none" stroke="currentColor" strokeWidth="2" />
      {numbers.map((nav, i) => nav === null ? null : <circle key={i} cx={24 + i / Math.max(numbers.length - 1, 1) * 672}
        cy={span === 0 ? 100 : 172 - (nav / scale - bottom) / span * 144} r="2" fill="currentColor" />)}
    </svg><div className="backtest-equity-range"><span>{date(value.points[0][0])}</span><span>{date(value.points.at(-1)![0])}</span></div>
    <p className="backtest-equity-scale">图示净值范围：{low.toLocaleString('zh-CN', { maximumFractionDigits: 4 })} 至 {high.toLocaleString('zh-CN', { maximumFractionDigits: 4 })} 元；各报告分别缩放，原值见日期表。</p>
  </figure>
}

function PerformanceCard({ value, label }: { value: Performance; label: string }) {
  const [page, setPage] = useState(0)
  const { metrics: metrics, observations } = value
  return <article className="surface-card backtest-performance-card" aria-label={label}>
    <h4>{label} · {value.configuration.label}</h4>
    {value.report_schema === HISTORICAL_REPORT_SCHEMA ? <p>历史日末回测假设：源成交金额单位未知，按元解释；历史首次可知时间和修订记录未知。</p> : null}
    {isRetainedReport(value.report_schema) ? <p>按本批次前复权数据回测，历史可知时间采用收盘假设；结果用于模拟评估。</p> : null}
    <p>版本 {value.strategy.version} · {time(value.configuration.start)} 至 {time(value.configuration.end)}（上海时间）</p>
    <dl className="backtest-performance-metrics">
      <div><dt>模型收益率</dt><dd>{pct(metrics.total_return_pct)}</dd></div>
      <div><dt>已观察日末最大回撤</dt><dd>{pct(metrics.observed_max_drawdown_pct)}</dd></div>
      <div><dt>初始本金（元）</dt><dd>{backtestMoney(metrics.initial_capital_cny)}</dd></div>
      <div><dt>末个模型净值（元）</dt><dd>{backtestMoney(metrics.last_nav_cny)}</dd></div>
      <div><dt>回测累计费用（元）</dt><dd>{backtestMoney(metrics.native_cumulative_fees_cny)}</dd></div>
    </dl>
    <p>共 {observations.total} 条日末记录；可用 {observations.available} 条，缺失 {observations.missing} 条。最新交易日：{date(observations.last_trading_date)}。</p>
    {!observations.available ? <p role="status">资金数据暂不可用，暂无绩效指标。</p> : <>
      {observations.missing ? <p>指标按已有数据计算，缺失日期保留空白。</p> : null}
      <EquityCurve value={value} />
    </>}
    <details><summary>查看日期与净值</summary>
      <div className="account-table-scroll" tabIndex={0} role="region" aria-label={`${label}日期净值表`}><table>
        <thead><tr><th>交易日</th><th>日末模型净值（元）</th></tr></thead><tbody>
          {value.points.slice(page * 50, (page + 1) * 50).map(([day, nav]) => <tr key={day}><td>{date(day)}</td><td>{nav ?? '观察缺失'}</td></tr>)}
        </tbody></table></div>
      <div className="account-actions"><span>第 {page + 1} 页</span><button disabled={page === 0} onClick={() => setPage(page - 1)}>净值上一页</button>
        <button disabled={(page + 1) * 50 >= value.points.length} onClick={() => setPage(page + 1)}>净值下一页</button></div>
    </details>
  </article>
}

/** 同一固定报告对在刷新/失败时保留上次结果；切换身份由查询键隔离。 */
export default function BacktestPerformance({ entry, entries, ready = true }: { entry: ArchiveEntry; entries: ArchiveEntry[]; ready?: boolean }) {
  const [rightId, setRightId] = useState('')
  const right = entries.find(item => item.run_id === rightId && item.run_id !== entry.run_id)
  const single = useQuery({ queryKey: ['backtest-performance', entry.run_id, entry.receipt_sha256, entry.report_sha256],
    queryFn: ({ signal }) => fetchBacktestPerformance(entry, signal), enabled: ready && !right, retry: false,
    refetchOnWindowFocus: false, refetchOnReconnect: false })
  const comparison = useQuery({ queryKey: ['backtest-comparison', entry.run_id, entry.receipt_sha256, right?.run_id, right?.receipt_sha256],
    queryFn: ({ signal }) => fetchBacktestComparison(entry, right!, signal), enabled: ready && !!right, retry: false,
    refetchOnWindowFocus: false, refetchOnReconnect: false })
  const current = right ? comparison : single
  const pair = right ? comparison.data : undefined
  const value = !right ? single.data : undefined
  return <section className="backtest-performance" aria-label="回测绩效与比较"><h3>回测绩效与比较</h3>
    <p>收益按初始本金和回测损益计算；回撤按日末净值计算。</p>
    <div className="backtest-performance-controls"><label>选择比较报告<select aria-label="选择比较报告" value={right?.run_id ?? ''} onChange={event => setRightId(event.target.value)}>
      <option value="">仅查看当前报告</option>{entries.filter(item => item.run_id !== entry.run_id).map((item, index) => <option key={item.run_id} value={item.run_id}>
        {item.configuration.label} · 报告 {index + 1}</option>)}
    </select></label><button disabled={!ready || current.isFetching} onClick={() => void current.refetch()}>重新读取绩效</button></div>
    {current.isFetching ? <p role="status">正在读取{right ? '比较结果' : '报告'}…{pair || value ? '当前显示上次结果。' : ''}</p> : null}
    {current.isError ? <p role="alert">报告读取失败。{pair || value ? '当前保留上次结果。' : ''}请稍后重试。</p> : null}
    {(pair || value) && current.dataUpdatedAt ? <p>读取于 {new Date(current.dataUpdatedAt).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })}（北京时间）</p> : null}
    {value ? <PerformanceCard key={value.run_id + value.receipt_sha256} value={value} label="当前报告" /> : null}
    {pair ? <><p role="status">{pair.differences.length ? `比较条件存在差异：${pair.differences.map(key => differenceNames[key]).join('、')}。请结合这些条件解读结果。`
      : '两份报告的所列输入和模型条件一致。'}</p>
      <div className="backtest-performance-pair"><PerformanceCard key={'left' + pair.left.run_id} value={pair.left} label="当前报告" />
        <PerformanceCard key={'right' + pair.right.run_id} value={pair.right} label="比较报告" /></div></> : null}
  </section>
}
