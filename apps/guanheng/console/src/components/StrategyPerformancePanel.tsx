import { useQuery } from '@tanstack/react-query'
import { lazy, Suspense, useState } from 'react'
import { fetchStrategyCapitalHistory } from '../api'
import { EmptyState } from './EmptyState'
import { absoluteChinaTime } from './RelativeTime'
import { CAPITAL_HISTORY_DEFAULT_DAYS } from '../strategyReturnPresentation'
const StrategyHistoryChart = lazy(() => import('./StrategyHistoryChart').then(module => ({ default: module.StrategyHistoryChart })))

export function StrategyPerformancePanel({ strategyId, lineage, epoch, compact = false }: { strategyId: string; lineage?: string; epoch?: string | null; compact?: boolean }) {
  const [sampling, setSampling] = useState<'daily' | 'snapshots'>('daily')
  const query = useQuery({ queryKey: ['strategy-capital-history', strategyId, lineage, epoch, sampling, CAPITAL_HISTORY_DEFAULT_DAYS], queryFn: ({ signal }) => fetchStrategyCapitalHistory(strategyId, lineage!, epoch!, signal, { sampling, days: CAPITAL_HISTORY_DEFAULT_DAYS }), enabled: Boolean(strategyId && lineage && epoch), staleTime: 30_000, retry: 1 })
  const data = query.isError ? undefined : query.data
  const range = data?.window_start && data.window_end
    ? `请求范围：${absoluteChinaTime(data.window_start)} 至 ${absoluteChinaTime(data.window_end)}（起点包含、终点不含）`
    : '请求范围不可用；图中仅展示已取得的观察范围。'
  return <section className="strategy-performance-panel"><div className="card-heading"><div><h2>历史收益与回撤</h2><span>所选策略 · 同一版本链与资本纪元</span></div></div>
    <label className="strategy-history-controls">历史视图<select aria-label="历史估值采样" value={sampling} onChange={event => setSampling(event.target.value as 'daily' | 'snapshots')}><option value="daily">每日估值 · 最近 {CAPITAL_HISTORY_DEFAULT_DAYS} 天</option><option value="snapshots">最近快照 · 最多 1000 条</option></select></label>
    <p className="reader-meta">{sampling === 'daily' ? '每天按北京时间保存观测日，选择最后一条真实快照；当天为截至查询的最新观察，正式收盘结果需另行确认。' : '按实际估值时间展示最近保存的盘中快照。'}</p>
    {!lineage || !epoch ? <EmptyState title="策略资本身份不可用" detail="历史收益读取需要明确的版本链和资本纪元。" /> : query.isError ? <EmptyState title="策略历史估值不可用" detail={sampling === 'daily' ? '每日估值读取失败或采样身份不匹配；可切换最近快照核对，服务状态保留故障原因。' : '策略资本历史接口读取失败；请查看服务状态。'} /> : !data ? <p>正在读取策略历史估值…</p> : <>
      <p className="reader-meta">{range}</p>
      {!data.points.length ? <EmptyState title="暂无历史估值" detail="所选资本身份在当前窗口没有已保存的快照。" /> : <>
        <p className="reader-meta">来源：Portfolio 策略资本快照 · 实际保存观察 {absoluteChinaTime(data.points[0].captured_at)} 至 {absoluteChinaTime(data.points.at(-1)!.captured_at)} · 最新估值 {absoluteChinaTime(data.points.at(-1)!.valuation_at)}{data.truncated ? sampling === 'daily' ? ' · 每日样本点已截断' : ' · 最近 1000 条快照窗口已截断' : ''}</p>
        {data.points.length === 1 ? <p className="reader-meta">当前仅有 1 个观察点，尚未形成可展示的历史变化。</p> : null}
        <Suspense fallback={<p>正在加载曲线…</p>}><StrategyHistoryChart history={data} /></Suspense>
        <p className="reader-meta">投入本金收益率 =（策略权益 − 投入本金）÷ 投入本金，分母包含初始与追加本金。{sampling === 'daily' ? '每日采样回撤只衡量每日采样的有效连续片段；缺日和受阻记录均断开曲线，盘中最大回撤仍需盘中记录确认。' : '片段回撤按有效连续片段的最高收益指数计算，受阻记录断开片段。'}图中展示离散估值，期间未观察的变化不可推断。</p>
        {!compact ? <div className="reader-table-scroll"><table className="reader-table"><thead><tr><th>实际估值时间</th><th>保存观察时间</th><th>权益</th><th>投入本金</th><th>投资盈亏</th><th>状态</th></tr></thead><tbody>{data.points.slice(-10).reverse().map((point, index) => <tr key={`${point.captured_at}-${index}`}><td>{absoluteChinaTime(point.valuation_at)}</td><td>{absoluteChinaTime(point.captured_at)}</td><td>{point.net_asset_value.toFixed(2)}</td><td>{point.contributed_principal.toFixed(2)}</td><td>{point.investment_pnl.toFixed(2)}</td><td>{point.status === 'ready' ? '有效估值' : '估值受阻'}</td></tr>)}</tbody></table></div> : null}
      </>}
    </>}
  </section>
}
