import type { StrategyCapitalSleeve, StrategyWorkbenchDetail } from '../types'
import { holdingsWithTargets } from '../strategyCapitalPresentation'
import { EmptyState } from './EmptyState'
import { absoluteChinaTime } from './RelativeTime'
import { capitalReturnMetrics } from '../strategyReturnPresentation'

const money = (value?: number | null) => value == null ? '不可用' : value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
const pct = (value?: number | null) => value == null ? '不可用' : `${(value * 100).toFixed(2)}%`

export function StrategyCapitalPanel({ sleeve, target, compact = false, error, metricsOnly = false, holdingsOnly = false }: {
  sleeve?: StrategyCapitalSleeve; target?: StrategyWorkbenchDetail['current_target']; compact?: boolean; error?: string; metricsOnly?: boolean; holdingsOnly?: boolean
}) {
  const rows = holdingsWithTargets(sleeve, target)
  const returns = capitalReturnMetrics(sleeve)
  const totalReturnAvailable = sleeve?.total_return_available ?? sleeve?.pnl_metrics_available
  const currentWeight = sleeve?.positions && sleeve.net_asset_value > 0 ? sleeve.market_value / sleeve.net_asset_value : undefined
  const targetWeight = target ? target.items.reduce((sum, item) => sum + item.target_weight, 0) : undefined
  return <section className="strategy-capital-panel" aria-label="策略持仓与目标">
    {!holdingsOnly ? <><div className="strategy-capital-metrics">
      <div><span>策略权益</span><strong>¥ {money(sleeve?.net_asset_value)}</strong><small>{sleeve?.reconciliation_status === 'reconciled' ? '该快照已对账' : '该快照估值待核对'}</small></div>
      <div><span>投入本金收益率</span><strong>{pct(returns.ratio)}</strong><small>投资盈亏 ¥ {money(returns.pnl)}</small><small>{returns.available ? `投入本金 ¥ ${money(returns.principal)}，包含初始与追加本金` : returns.reason}</small></div>
      <div><span>当前仓位</span><strong>{pct(currentWeight)}</strong><small>以策略权益为分母</small></div>
      <div><span>目标仓位</span><strong>{pct(targetWeight)}</strong><small>{target?.valid_until && Date.parse(target.valid_until) <= Date.now() ? '目标已到期' : target ? '当前目标快照' : '目标来源待核对'}</small></div>
    </div>
    {!sleeve ? <EmptyState title="策略资金不可用" detail={error ?? '未取得所选策略版本、版本链和资本纪元的唯一资金事实。'} /> : <p className="reader-meta">估值 {sleeve.valuation_at ? absoluteChinaTime(sleeve.valuation_at) : '时间不可用'} · 浮动收益 ¥ {money(sleeve.pnl_metrics_available ? sleeve.unrealized_pnl : undefined)} · 费用 ¥ {money(sleeve.pnl_metrics_available ? sleeve.fees : undefined)}{sleeve.reconciliation_status !== 'reconciled' ? ' · 当前对账受阻，估值仅供核对' : ''}</p>}
    {sleeve ? <p className="reader-meta">投资盈亏按累计投入本金核算，浮动收益按持仓成本核算。</p> : null}
    {sleeve?.fees_settlement_pending ? <p className="reader-meta">账户内有盘中参考费用待结算核对；费用及收益按保守账本展示，待核对余额暂不增加策略预算。</p> : null}
    {sleeve ? <p className="reader-meta">累计收益率：{pct(totalReturnAvailable ? sleeve.total_return : undefined)}。{totalReturnAvailable ? '按初始本金计算。' : (sleeve.capital_contributions_total ?? 0) > 0 ? '追加本金后缺少划转时点估值，暂无法计算扣除资金流影响的累计收益率。' : '当前缺少按初始本金计算累计收益所需的有效事实。'}</p> : null}
    </> : null}
    {!metricsOnly ? <><div className="card-heading"><div><h2>{compact ? '持仓与目标摘要' : '持仓与目标'}</h2><span>差额 = 目标 − 当前，单位：百分点</span></div></div>
    {target ? <p className="reader-meta">目标交易日 {target.source_trade_date} · {absoluteChinaTime(target.observed_at)} · {target.valid_until ? `有效至 ${absoluteChinaTime(target.valid_until)}` : '有效期按目标规则'}</p> : <p className="reader-meta">当前目标尚无可展示事实。</p>}
    {rows.length ? <div className="reader-table-scroll"><table className="reader-table"><thead><tr><th>证券</th><th>数量</th><th>市值</th><th>当前仓位</th><th>目标仓位</th><th>差额</th></tr></thead><tbody>{(compact ? rows.slice(0, 5) : rows).map(row => <tr key={row.symbol}><th>{row.symbol}</th><td>{sleeve?.positions ? money(row.position?.quantity ?? 0) : '不可用'}</td><td>{sleeve?.positions ? money(row.position?.market_value ?? 0) : '不可用'}</td><td>{pct(row.currentWeight)}</td><td>{pct(row.targetWeight)}</td><td>{row.gap == null ? '不可用' : `${row.gap >= 0 ? '+' : ''}${(row.gap * 100).toFixed(2)} pp`}</td></tr>)}</tbody></table></div> : <EmptyState title={sleeve?.positions ? '当前没有持仓与目标' : '持仓明细不可用'} detail="持仓明细和完整目标由各自的权威来源提供。" />}
    </> : null}
  </section>
}
