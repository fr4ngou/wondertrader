import { AlertTriangle, ShieldCheck } from 'lucide-react'

import { InfoTip } from '../components/InfoTip'
import { RelativeTime } from '../components/RelativeTime'
import { diagnosticLabel } from '../diagnosticPresentation'
import type { ConsoleBootstrap } from '../types'

function TimeValue({ value }: { value?: string | null }) {
  return value ? <RelativeTime value={value} /> : <>时间不可用</>
}

function formatPercent(value?: number | null) {
  return value == null ? '不可用' : `${(value * 100).toFixed(2)}%`
}

function formatCurrency(value?: number | null) {
  return value == null ? '不可用' : new Intl.NumberFormat('zh-CN', {
    style: 'currency', currency: 'CNY', minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(value)
}

function formatPrice(value: number) {
  return Number(value).toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
}

function accountCapitalStatusLabel(value?: string | null) {
  if (value === 'reconciled') return '账户资本已对账'
  if (value === 'blocked') return '账户资本差异阻断'
  return '账户资本事实不可用'
}

function ownershipKindLabel(value: string) {
  if (value === 'operator_manual') return '平台人工归属'
  if (value === 'external_manual') return '券商外部人工归属'
  return '未知历史归属'
}

export function PortfolioPage({ bootstrap }: { bootstrap: ConsoleBootstrap }) {
  const accountCapital = bootstrap.overview.trading_operations?.reconciliations?.[0]
  const accountCapitalError = bootstrap.overview.errors.account_capital_reconciliation
  return (
    <section className="workspace-page">
      <header className="page-heading">
        <div><h1>分策略持仓</h1><p>查看策略资金、逐证券持仓和账户归属；所有金额来自同一账户快照边界。</p></div>
        <span className="read-only-stamp">只读 · 账户事实</span>
      </header>
      {accountCapital?.strategy_sleeves.length ? (
        <div className="portfolio-sleeves" aria-label="策略资金袖套明细">
          {accountCapital.strategy_sleeves.map((sleeve) => (
            <article className="surface-card portfolio-sleeve-card" key={sleeve.strategy_lineage_id}>
              <header className="portfolio-sleeve-header">
                <div>
                  <span className="eyebrow">策略持仓</span>
                  <h2>{sleeve.strategy_id && sleeve.strategy_version ? `${sleeve.strategy_id} @ ${sleeve.strategy_version}` : sleeve.strategy_lineage_id}</h2>
                  <p>版本链 {sleeve.strategy_lineage_id} · {sleeve.genesis_epoch_id ? `epoch ${sleeve.genesis_epoch_id.slice(0, 8)}` : 'genesis 暂不可用'}</p>
                </div>
                <span className={`portfolio-reconcile-badge ${sleeve.reconciliation_status === 'reconciled' ? 'is-ready' : 'is-blocked'}`}>{accountCapitalStatusLabel(sleeve.reconciliation_status)}</span>
              </header>
              <div className="portfolio-sleeve-primary" aria-label={`${sleeve.strategy_lineage_id} 资金概览`}>
                <div><span>当前净资产</span><strong>{formatCurrency(sleeve.net_asset_value)}</strong><small>策略账面现金 + 持仓市值</small></div>
                <div><span>可用金额</span><strong>{formatCurrency(sleeve.spendable_cash)}</strong><small>策略账面现金扣除已预留金额</small></div>
                <div><span>持仓市值</span><strong>{formatCurrency(sleeve.market_value)}</strong><small>当前账户边界的策略持仓估值</small></div>
              </div>
              <dl className="portfolio-sleeve-secondary">
                <div><dt>账面现金</dt><dd>{formatCurrency(sleeve.virtual_cash)}</dd></div>
                <div><dt>追加本金</dt><dd>{formatCurrency(sleeve.capital_contributions_total)}</dd></div>
                <div><dt>已实现收益</dt><dd>{sleeve.pnl_metrics_available ? formatCurrency(sleeve.realized_pnl) : '不可用'}</dd></div>
                <div><dt>未实现收益</dt><dd>{sleeve.pnl_metrics_available ? formatCurrency(sleeve.unrealized_pnl) : '不可用'}</dd></div>
                <div><dt>累计费用</dt><dd>{sleeve.pnl_metrics_available ? formatCurrency(sleeve.fees) : '不可用'}</dd></div>
                <div><dt>当日收益率</dt><dd>{sleeve.daily_return_available ? formatPercent(sleeve.daily_return) : '不可用'}</dd></div>
                <div><dt>累计收益率</dt><dd>{formatPercent(sleeve.total_return)}</dd></div>
              </dl>
              {sleeve.positions?.length ? (
                <div className="portfolio-positions" aria-label={`${sleeve.strategy_lineage_id} 持仓明细`}>
                  <div className="portfolio-positions-heading"><h3>已持仓标的</h3><span>{sleeve.positions.length} 个标的</span></div>
                  <div className="portfolio-positions-scroll">
                    <table className="portfolio-positions-table">
                      <thead><tr><th scope="col">标的</th><th scope="col">数量</th><th scope="col">估值价</th><th scope="col">市值</th></tr></thead>
                      <tbody>{sleeve.positions.map((position) => (
                        <tr key={position.symbol}><th scope="row">{position.symbol}</th><td>{position.quantity}</td><td>{formatPrice(position.valuation_price)}</td><td>{formatCurrency(position.market_value)}</td></tr>
                      ))}</tbody>
                    </table>
                  </div>
                </div>
              ) : <p className="empty-inline">当前权威边界没有该策略持仓或逐证券明细尚未升级</p>}
              <footer className="portfolio-sleeve-footer">
                <span>估值：{sleeve.valuation_source === 'strategy_capital_snapshot' ? '策略资本快照' : '账户资本对账'} · <TimeValue value={sleeve.valuation_at} /></span>
                <span>账户边界 <TimeValue value={sleeve.account_boundary_captured_at} /></span>
                {sleeve.reconciliation_issue_codes.length ? <span>{sleeve.reconciliation_issue_codes.map((code) => diagnosticLabel(code)).join('、')}</span> : null}
              </footer>
            </article>
          ))}
        </div>
      ) : accountCapital?.reflected_state === 'known' ? <p className="empty-inline">当前权威边界没有自动策略资金袖套</p> : null}
      <AccountCapitalDetails bootstrap={bootstrap} />

    </section>
  )
}

export function AccountCapitalDetails({ bootstrap }: { bootstrap: ConsoleBootstrap }) {
  const accountCapitalError = bootstrap.overview.errors.account_capital_reconciliation
  const accountCapital = accountCapitalError ? undefined : bootstrap.overview.trading_operations?.reconciliations?.[0]
  return <>      <article className={`surface-card account-capital-reconciliation-card runtime-status-${accountCapital?.status === 'reconciled' ? 'healthy' : 'blocked'}`}>
        <div className="card-heading"><div><h2>账户资本对账</h2><span>策略袖套、未分配储备与券商账户的同一边界核对</span></div><InfoTip label="账户资本对账">按原生资金和持仓核对资本连续性；另列 QMT 报告的总资产差额。该差额原因待核，不代表现金流水。“不可用”表示缺少权威事实，不代表金额为零。</InfoTip></div>
        {accountCapital ? <>
          <div className="runtime-status-grid" aria-label="账户资本对账状态">
            <div className="runtime-status-item"><span>状态</span><strong>{accountCapitalStatusLabel(accountCapital.status)}</strong><small>计算于 <TimeValue value={accountCapital.calculated_at} /></small></div>
            <div className="runtime-status-item"><span>券商总资产</span><strong>{formatCurrency(accountCapital.broker_total_asset)}</strong><small>账户边界 <TimeValue value={accountCapital.account_boundary_captured_at} /></small></div>
            <div className="runtime-status-item"><span>QMT 原生现金</span><strong>{formatCurrency(accountCapital.broker_cash)}</strong><small>同一账户快照的可用资金与冻结资金</small></div>
            {(accountCapital.reference_fee_reserve_limit ?? 0) > 0 ? <>
              <div className="runtime-status-item"><span>参考费用预留上界</span><strong>{formatCurrency(accountCapital.reference_fee_reserve_limit)}</strong><small>盘中成交费用尚待独立结算依据核实，策略预算已保守扣除</small></div>
              <div className="runtime-status-item"><span>待核对未分配余额</span><strong>{formatCurrency(accountCapital.unallocated_reference_fee_balance)}</strong><small>保留在真实账户现金中，暂不增加策略预算及收益；预留范围内的差额不单独阻断执行</small></div>
            </> : null}
            <div className="runtime-status-item"><span>QMT 原始字段差额</span><strong>{formatCurrency(accountCapital.broker_reported_asset_gap)}</strong><small>{accountCapital.broker_reported_asset_gap == null ? '原始资金字段尚未齐备' : '总资产－可用资金－冻结资金－账户汇总市值；原因待核'}</small></div>
            <div className="runtime-status-item"><span>策略资金袖套</span><strong>{accountCapital.reflected_state === 'known' ? `${accountCapital.strategy_sleeve_count} 个` : '不可用'}</strong><small>{accountCapital.reflected_state === 'known' ? `未分配储备 ${formatCurrency(accountCapital.unallocated_strategy_reserve)}` : '持仓归属事实不可用；请查看下方阻断原因'}</small></div>
            <div className="runtime-status-item"><span>资产残差</span><strong>{formatCurrency(accountCapital.asset_residual)}</strong><small>容差 {formatCurrency(accountCapital.amount_tolerance)}</small></div>
          </div>
          <div className="strategy-capital-sleeves" aria-label="人工与未知归属明细">
            {accountCapital.non_strategy_ownership.map((owner) => <section key={owner.owner_kind}>
              <header><strong>{ownershipKindLabel(owner.owner_kind)}</strong><small>同一账户估值边界</small></header>
              <dl>
                <div><dt>持仓项</dt><dd>{owner.position_count}</dd></div>
                <div><dt>持仓数量</dt><dd>{owner.total_quantity}</dd></div>
                <div><dt>持仓市值</dt><dd>{formatCurrency(owner.market_value)}</dd></div>
              </dl>
            </section>)}
          </div>
          <p className="empty-inline">人工、外部与未知历史现金统一计入独立现金 {formatCurrency(accountCapital.independent_cash)}；当前权威账本未提供安全的分项收益时保持不可用。未分配策略储备 {formatCurrency(accountCapital.unallocated_strategy_reserve)}。</p>
          {accountCapital.blocking_issue_codes.length ? <div className="boundary-reasons">{accountCapital.blocking_issue_codes.map((item) => <span key={item}>{diagnosticLabel(item)}</span>)}</div> : <p className="empty-inline"><ShieldCheck size={15} /> 策略资金、人工归属、储备和券商资产在同一边界一致</p>}
        </> : <div className="coverage-gap"><AlertTriangle size={16} /><div><strong>账户资本对账事实不可用</strong><span>{accountCapitalError ? `来源错误：${accountCapitalError}` : '账户资本来源未返回权威事实；策略资本、归属和账本一致性待核。'}</span></div></div>}
      </article></>
}
