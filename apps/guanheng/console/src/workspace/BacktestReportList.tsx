import { useState } from 'react'
import type { ArchiveEntry } from './backtestApi'
import type { BacktestPerformance } from './backtestPerformanceApi'
import { backtestMoney } from './backtestMoney'
import { reportDate, reportPct } from './BacktestVisualChart'

export type ReportItem = {
  /** 同一运行、完成收据和报告摘要的归档条目。 */ entry: ArchiveEntry
  /** 已校验的策略身份、人民币本金和绩效，全部取原公开投影。 */ value: BacktestPerformance
}

/** 当前策略内选择主报告及可选对比报告。 */
export default function BacktestReportList({ reports, pending, onOpen }: {
  /** 按截止日期倒序排列的同策略报告。 */ reports: ReportItem[]
  /** 仍有报告在核验身份；此时空列表保持加载状态。 */ pending: boolean
  /** 打开所选主报告和同策略可选对比报告。 */ onOpen: (run: string, compare?: string) => void
}) {
  const [mainId, setMainId] = useState('')
  const [compareId, setCompareId] = useState('')
  const main = reports.find(item => item.entry.run_id === mainId) ?? reports[0]
  const compare = reports.find(item => item.entry.run_id === compareId && item !== main)
  const label = (item: ReportItem) => `${backtestMoney(item.value.metrics.initial_capital_cny)}元 · 至${reportDate(Math.floor(item.entry.configuration.end / 10000))}`
  return <>
    <p className="bt-list-count">当前策略的回测 · {reports.length} 份已完成报告</p>
    {pending ? <p role="status">正在读取报告列表…</p> : null}
    {!reports.length && !pending ? <p role="status">该策略暂无已保存的回测报告。</p> : null}
    {reports.length ? <>
      <div className="bt-report-list" role="region" aria-label="策略回测列表" tabIndex={0}><table>
        <thead><tr><th>主报告</th><th>回测区间</th><th>初始本金（元）</th><th>总收益</th><th>最大日末回撤</th><th>操作</th></tr></thead>
        <tbody>{reports.map((item, index) => <tr key={item.entry.run_id} className={item === main ? 'bt-list-main' : ''}>
          <td><input type="radio" name="backtest-main" aria-label={`主报告 ${index + 1}`} checked={item === main} onChange={() => setMainId(item.entry.run_id)} /></td>
          <td><strong>{reportDate(Math.floor(item.entry.configuration.start / 10000))} 至 {reportDate(Math.floor(item.entry.configuration.end / 10000))}</strong><small>{item.entry.record_count} 期 · 报告 {index + 1}</small></td>
          <td>{backtestMoney(item.value.metrics.initial_capital_cny)}</td><td className="bt-return">{reportPct(item.value.metrics.total_return_pct)}</td><td>{reportPct(item.value.metrics.observed_max_drawdown_pct)}</td>
          <td><div className="bt-list-actions"><button onClick={() => onOpen(item.entry.run_id)}>查看分析</button>
            <button aria-pressed={item === compare} disabled={item === main} onClick={() => setCompareId(item === compare ? '' : item.entry.run_id)}>{item === compare ? '取消对比' : '设为对比'}</button></div></td>
        </tr>)}</tbody>
      </table></div>
      <div className="bt-list-selection"><span><b>主报告：</b>{label(main)}{compare ? <><br className="bt-mobile-break" /><b>对比报告：</b>{label(compare)}</> : null}</span>
        <button onClick={() => onOpen(main.entry.run_id, compare?.entry.run_id)}>{compare ? '打开对比分析' : '打开回测分析'}</button></div>
    </> : null}
  </>
}
