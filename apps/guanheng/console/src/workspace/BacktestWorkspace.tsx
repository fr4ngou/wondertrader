import { useCallback, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchBacktestArchive } from './backtestApi'
import BacktestPerformance, { reportKey, reportLabel } from './BacktestPerformance'
import type { BacktestPerformance as Performance } from './backtestPerformanceApi'
import BacktestSourceState from './BacktestSourceState'

/** 独立回测入口；只读已完成归档，默认显示截止日期最新的一份。 */
export default function BacktestWorkspace() {
  const [runId, setRunId] = useState<string | null>(null)
  const [capitals, setCapitals] = useState<Record<string, string>>({})
  const onReport = useCallback((value: Performance) => {
    const key = value.run_id + value.receipt_sha256
    setCapitals(before => before[key] === value.metrics.initial_capital_cny ? before : { ...before, [key]: value.metrics.initial_capital_cny })
  }, [])
  const query = useQuery({ queryKey: ['native-backtest-archive'], queryFn: ({ signal }) => fetchBacktestArchive(signal), retry: false,
    refetchOnWindowFocus: false, refetchOnReconnect: false })
  const entries = [...(query.data?.runs ?? [])].sort((a, b) => b.configuration.end - a.configuration.end || a.run_id.localeCompare(b.run_id))
  const selected = entries.find(e => e.run_id === runId) ?? entries[0]
  return <section className="workspace-page bt-workspace">
    {query.isPending ? <p role="status">正在读取回测记录…</p> : null}
    {query.isError ? <><p role="alert">报告目录读取失败。{query.data ? '保留上次目录及读取时间。' : ''}</p><BacktestSourceState /><button onClick={() => void query.refetch()}>刷新历史报告</button></> : null}
    {query.data?.invalid_receipts ? <p role="alert">{query.data.invalid_receipts} 份完成证明未通过校验，请核查原件。</p> : null}
    {query.data?.unarchived_runs ? <p role="status">{query.data.unarchived_runs} 项运行尚未保存完成证明。</p> : null}
    {selected ? <BacktestPerformance key={selected.run_id + selected.receipt_sha256} entry={selected} entries={entries} capitalLabels={capitals} onReport={onReport} onRefreshArchive={() => void query.refetch()} archiveRefreshing={query.isFetching} mainSelector={<label>主报告<select aria-label="选择历史回测" value={selected.run_id} onChange={e => setRunId(e.target.value)}>{entries.map((e, index) => <option key={e.run_id} value={e.run_id}>{reportLabel(e, capitals[reportKey(e)], index + 1)}</option>)}</select></label>} /> : query.data ? <><h1>回测分析</h1><p role="status">尚无已保存的回测报告。</p><button onClick={() => void query.refetch()}>刷新历史报告</button></> : null}
  </section>
}
