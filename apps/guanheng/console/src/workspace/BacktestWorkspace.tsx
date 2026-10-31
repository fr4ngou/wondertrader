import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchBacktestDay, fetchBacktestRecords, fetchBacktestArchive, type BacktestDay } from './backtestApi'
import BacktestPerformance from './BacktestPerformance'
import { isRetainedReport, type RetainedSummary } from './backtestRetained'
import { backtestMoney } from './backtestMoney'

const stages: Record<string, string> = { buying: '买入中', selling: '卖出中', converged: '已达到目标持仓', waiting_fee: '等待费用信息',
  waiting_cash: '等待可用资金', waiting_basis: '等待资金数据', waiting_pending: '等待调仓结果', waiting_sellable: '等待可卖数量',
  awaiting_buy: '等待买入条件', supersession_required: '等待前次调仓完成', blocked: '暂缓调仓', initializing: '初始化' }
const recordLabels: Record<string, string> = { ready: '可计算', warming: '历史数据预热中', warming_up: '历史数据预热中', blocked_raw_total: '目标仓位超限', ...stages }
const reasonLabels: Record<string, string> = { frozen_buy_actual_confirmed: '持仓已达到买入目标', frozen_sell_actual_confirmed: '已完成目标减仓', waiting_warmup: '等待历史数据预热完成',
  native_pending_conflict: '调仓结果需要核查', native_pending_unresolved: '等待前次调仓结果', actual_outside_frozen_stage: '持仓变化需要核查',
  native_sellable_insufficient: '可卖数量不足，等待可卖', frozen_sell_ready: '已提交减仓目标，等待成交',
  frozen_buy_ready: '已提交买入目标，等待成交', stage_budget_exhausted: '本轮调仓已暂停',
  observation_precedes_frozen_basis: '等待最新持仓数据', prior_generation_unresolved: '等待前次调仓完成', universe_handoff_required: '证券范围变化需要核查',
  fresh_post_sell_basis_required: '等待卖出后的资金更新', no_dated_allocation: '尚无调仓信号',
  explicit_buy_fee_reserve_unavailable: '费用信息缺失，暂缓买入', whole_buy_group_unfunded: '可用资金尚不足以完成本次买入' }
const reasonText = (reason: string) => reasonLabels[reason] ?? '等待策略运行条件满足'
const replayTime = (time: number) => { const value = String(time); return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)} ${value.slice(8, 10)}:${value.slice(10, 12)}` }
const chineseDate = (date: number) => { const s = String(date); return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}` }

const names: Record<string, string> = { '510300.SH': '沪深300', '510050.SH': '上证50', '510500.SH': '中证500', '512100.SH': '中证1000', '588000.SH': '科创50', '589000.SH': '科创综指', '159780.SZ': '双创50', '515080.SH': '红利' }
const security = (symbol: string) => names[symbol] ? `${names[symbol]} · ${symbol}` : symbol
const readTime = (time: number) => new Date(time).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
function DayDetail({ value }: { value: BacktestDay }) {
  const record = value.record; const positions = record.capture?.observation.positions ?? []
  const retained = isRetainedReport(value.report_schema) ? value.evaluation_summary as RetainedSummary | null : null
  return <article className="surface-card"><h3>{chineseDate(record.trading_date)} · 当日结果</h3>
    <p>{recordLabels[record.status] ?? '等待运行条件'} · {reasonText(record.reason)}</p>
    {record.capture ? <><div className="account-funds">
      <div><h4>回测净值（元）</h4><strong>{backtestMoney(record.capture.basis.nav_cny)}</strong></div>
      <div><h4>回测现金（元）</h4><strong>{backtestMoney(record.capture.basis.cash_cny)}</strong></div>
    </div><h4>回测持仓</h4>{positions.some(p => p.actual > 0) ? <div className="account-table-scroll"><table><thead><tr><th>证券</th><th>持仓（份）</th><th>可卖（份）</th></tr></thead>
      <tbody>{positions.filter(p => p.actual > 0).map(p => <tr key={p.symbol}><td>{security(p.symbol)}</td><td>{p.actual}</td><td>{p.sellable}</td></tr>)}</tbody></table></div> : <p>当日没有持仓。</p>}</> : <p>当日资金数据暂不可用。</p>}
    {retained && Object.keys(retained.exit_paths).length ? <p>退出提示：{Object.keys(retained.exit_paths).map(security).join('、')} 达到策略退出条件。</p> : null}
  </article>
}

export default function BacktestWorkspace() {
  return <section className="workspace-page account-workspace backtest-workspace">
    <header className="page-heading"><div><h1>回测与报告</h1><p>查看WT已保存的策略回测表现、逐日结果及报告比较。</p></div><span className="read-only-stamp">只读报告</span></header>
    <p>回测运行和报告保存由WT入口负责。</p>
    <CompletedArchive />
  </section>
}

function CompletedArchive() {
  const [runId, setRunId] = useState<string | null>(null)
  const [page, setPage] = useState(0); const [day, setDay] = useState<number | null>(null)
  const query = useQuery({ queryKey: ['native-backtest-archive'], queryFn: ({ signal }) => fetchBacktestArchive(signal), retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false })
  const available = query.data
  const selected = available?.runs.find(item => item.run_id === runId) ?? available?.runs[0]
  const selection = selected ? { runId: selected.run_id, receiptSha: selected.receipt_sha256, reportSha: selected.report_sha256 } : undefined
  const records = useQuery({ queryKey: ['native-backtest-archive-records', selected?.run_id, selected?.receipt_sha256, page],
    queryFn: ({ signal }) => fetchBacktestRecords(selected!.owner_id, selected!.request_id, page * 50, signal, selection), enabled: !!selected, retry: false })
  const expectedDate = day === null ? undefined : records.data?.records[day - page * 50]?.trading_date
  const details = useQuery({ queryKey: ['native-backtest-archive-day', selected?.run_id, selected?.receipt_sha256, day, expectedDate],
    queryFn: ({ signal }) => fetchBacktestDay(selected!.owner_id, selected!.request_id, day!, signal, selected!.report_sha256, expectedDate, selection), enabled: !!selected && day !== null && expectedDate !== undefined, retry: false })
  return <section aria-label="历史回测报告"><h2>历史回测报告</h2><button disabled={query.isFetching} onClick={() => void query.refetch()}>刷新历史报告</button>
    {query.isPending ? <p role="status">正在读取历史报告…</p> : null}
    {query.isFetching && available ? <p role="status">正在刷新目录，当前显示上次结果。</p> : null}
    {query.isError ? <p role="alert">历史报告目录读取失败。{available ? '当前保留上次结果。' : ''}请稍后刷新。</p> : null}
    {available ? <><p>读取于 {readTime(query.dataUpdatedAt)}（北京时间）</p>
      {available.invalid_receipts || available.unarchived_runs ? <p role="alert">部分回测报告暂不可读取，请检查保存情况。</p> : null}
      {!available.runs.length ? <p role="status">尚无已保存的回测报告。</p> : <label>选择历史回测<select aria-label="选择历史回测" value={selected?.run_id ?? ''} onChange={event => { setRunId(event.target.value); setPage(0); setDay(null) }}>
        {available.runs.map((item, index) => <option key={item.run_id} value={item.run_id}>{item.configuration.label} · 报告 {available.runs.length - index}</option>)}</select></label>}
    </> : null}
    {selected ? <><p>{replayTime(selected.configuration.start)} 至 {replayTime(selected.configuration.end)}（北京时间）</p>
      <BacktestPerformance key={selected.run_id + selected.receipt_sha256} entry={selected} entries={available!.runs} />
      <article className="surface-card"><h3>历史逐日记录</h3>
        {records.isPending ? <p role="status">正在读取历史报告…</p> : null}
        {records.isError ? <p role="alert">历史报告读取失败。{records.data ? '当前保留上次结果。' : ''}<button onClick={() => void records.refetch()}>重读历史报告</button></p> : null}
        {records.data ? <><p>读取于 {readTime(records.dataUpdatedAt)}（北京时间）</p>
          {!records.data.records.length ? <p role="status">本次回测没有逐日记录。</p> : <div className="account-table-scroll"><table><thead><tr><th>交易日</th><th>状态</th><th>结果</th></tr></thead><tbody>{records.data.records.map((row, index) => <tr key={row.trading_date}>
            <td>{chineseDate(row.trading_date)}</td><td>{recordLabels[row.status] ?? '等待运行条件'}</td><td><button onClick={() => setDay(page * 50 + index)}>查看历史 {chineseDate(row.trading_date)}</button></td></tr>)}</tbody></table></div>}
          <div className="account-actions"><span>共 {records.data.total} 条 · 第 {page + 1} 页</span><button disabled={page === 0} onClick={() => { setPage(page - 1); setDay(null) }}>历史上一页</button><button disabled={(page + 1) * 50 >= records.data.total} onClick={() => { setPage(page + 1); setDay(null) }}>历史下一页</button></div>
        </> : null}
      </article></> : null}
    {day !== null && selected ? <>
      {details.isPending ? <p role="status">正在读取历史当日结果…</p> : null}
      {details.isError ? <p role="alert">历史当日结果读取失败。{details.data ? '当前保留上次结果。' : ''}<button onClick={() => void details.refetch()}>重读历史当日</button></p> : null}
      {details.data ? <><p>读取于 {readTime(details.dataUpdatedAt)}（北京时间）</p><DayDetail value={details.data} /></> : null}
    </> : null}
  </section>
}
