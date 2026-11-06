import { useState } from 'react'
import type { ArchiveEntry, ArchiveSummary } from './backtestApi'
import { useBacktestReports } from './useBacktestReports'
import { backtestMoney } from './backtestMoney'
import { reportDate, reportPct } from './BacktestVisualChart'

export type ReportItem = {
  /** 同一运行、完成收据和报告摘要的归档条目。 */ entry: ArchiveEntry
  /** 完成证明绑定的归属及人民币本金；完整绩效按当前选择另读。 */ summary: ArchiveSummary
}

/** 当前策略内选择主报告及可选对比报告。 */
export default function BacktestReportList({ reports, pending, unclassified = 0, onOpen }: {
  /** 按截止日期倒序排列的同策略报告。 */ reports: ReportItem[]
  /** 仍有报告在核验身份；此时空列表保持加载状态。 */ pending: boolean
  /** 已完成但本次归属不可读的条目数；避免将未知归属误称策略无报告。 */ unclassified?: number
  /** 打开所选主报告和同策略可选对比报告。 */ onOpen: (run: string, compare?: string) => void
}) {
  const [mainId, setMainId] = useState('')
  const [compareId, setCompareId] = useState('')
  const main = reports.find(item => item.entry.run_id === mainId) ?? reports[0]
  const compare = reports.find(item => item.entry.run_id === compareId && item !== main)
  const selected = [main, compare].filter((item): item is ReportItem => !!item)
  // 列表只复用已读指标；完整准入由打开分析触发，切策略时旧报告不占原读池。
  const performance = useBacktestReports(selected.map(item => item.entry), false)
  const values = new Map(selected.map((item, index) => [item.entry.run_id, performance[index]]))
  const failed = performance.filter(item => item.isError)
  const label = (item: ReportItem) => `${backtestMoney(item.summary.initial_capital_cny)}元 · 至${reportDate(Math.floor(item.entry.configuration.end / 10000))}`
  return <>
    <p className="bt-list-count">当前策略的回测 · {unclassified ? `已识别 ${reports.length} 份` : `${reports.length} 份已完成报告`}</p>
    {pending ? <p role="status">正在读取报告列表…</p> : null}
    {!reports.length && !pending ? <p role="status">{unclassified ? '部分报告归属尚未取得，可重读报告目录。' : '该策略暂无已保存的回测报告。'}</p> : null}
    {failed.length ? <p role="alert">所选报告绩效读取失败，仍可选择其他报告。<button onClick={() => { for (const item of failed) void item.refetch() }}>重读所选绩效</button></p> : null}
    {reports.length ? <>
      <div className="bt-report-list" role="region" aria-label="策略回测列表" tabIndex={0}><table>
        <thead><tr><th>主报告</th><th>回测区间</th><th>初始本金（元）</th><th>总收益</th><th>最大日末回撤</th><th>操作</th></tr></thead>
        <tbody>{reports.map((item, index) => <tr key={item.entry.run_id} className={item === main ? 'bt-list-main' : ''}>
          <td><input type="radio" name="backtest-main" aria-label={`主报告 ${index + 1}`} checked={item === main} onChange={() => setMainId(item.entry.run_id)} /></td>
          <td><strong>{reportDate(Math.floor(item.entry.configuration.start / 10000))} 至 {reportDate(Math.floor(item.entry.configuration.end / 10000))}</strong><small>{item.entry.record_count} 期 · 报告 {index + 1}</small></td>
          <td>{backtestMoney(item.summary.initial_capital_cny)}</td><td className="bt-return" title={values.get(item.entry.run_id)?.data ? undefined : '打开分析后读取完整指标'}>{values.get(item.entry.run_id)?.data ? reportPct(values.get(item.entry.run_id)!.data!.metrics.total_return_pct) : '—'}</td><td title={values.get(item.entry.run_id)?.data ? undefined : '打开分析后读取完整指标'}>{values.get(item.entry.run_id)?.data ? reportPct(values.get(item.entry.run_id)!.data!.metrics.observed_max_drawdown_pct) : '—'}</td>
          <td><div className="bt-list-actions"><button onClick={() => onOpen(item.entry.run_id)}>查看分析</button>
            <button aria-pressed={item === compare} disabled={item === main} onClick={() => setCompareId(item === compare ? '' : item.entry.run_id)}>{item === compare ? '取消对比' : '设为对比'}</button></div></td>
        </tr>)}</tbody>
      </table></div>
      <div className="bt-list-selection"><span><b>主报告：</b>{label(main)}{compare ? <><br className="bt-mobile-break" /><b>对比报告：</b>{label(compare)}</> : null}</span>
        <button onClick={() => onOpen(main.entry.run_id, compare?.entry.run_id)}>{compare ? '打开对比分析' : '打开回测分析'}</button></div>
    </> : null}
  </>
}
