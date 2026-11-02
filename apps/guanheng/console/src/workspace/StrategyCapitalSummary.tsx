import { absoluteChinaTime } from '../components/RelativeTime'
import { FinancialValue } from './FinancialValue'
import type { CapitalBaseline, StrategyCapital } from './strategyCapital'
import './strategy-capital.css'

/** 当前资金只取WT同一发布；历史本金与历史收益继续保留原未知状态。 */
export function StrategyCapitalSummary({ baseline, capital }: { baseline?: CapitalBaseline | null; capital?: StrategyCapital | null }) {
  if (!baseline) return null
  return <section className="strategy-capital" aria-label="策略资金">
    <header><h4>策略资金</h4><span>本次运行基准 <FinancialValue value={baseline.total_cny} /></span>
      {capital ? <time dateTime={capital.observed_at}>估值于 {absoluteChinaTime(capital.observed_at)}</time> : null}</header>
    {capital ? <>
      <dl className="strategy-capital-facts">
        <div><dt>策略总资产</dt><dd><FinancialValue value={capital.nav_cny} /></dd></div>
        <div><dt>可用资金</dt><dd>{capital.spendable_cash_cny === null ? '待更新' : <FinancialValue value={capital.spendable_cash_cny} />}</dd></div>
        <div><dt>现金余额</dt><dd><FinancialValue value={capital.cash_balance_cny} /></dd></div>
        <div><dt>持仓市值</dt><dd><FinancialValue value={capital.market_value_cny} /></dd></div>
        <div data-tone={Number(capital.native_pnl_cny) > 0 ? 'profit' : Number(capital.native_pnl_cny) < 0 ? 'loss' : 'flat'}>
          <dt>本次运行盈亏</dt><dd><FinancialValue value={capital.native_pnl_cny} /></dd></div>
      </dl>
      {capital.spendable_cash_cny === null ? <p className="strategy-capital-note">可用现金待WT确认。</p> : null}
    </> : <p className="strategy-capital-note">资金基准已发布，当前资产和余额等待WT更新。</p>}
    <details className="compact-details"><summary>基准与来源时间</summary>
      <p>本次基准启用：{absoluteChinaTime(baseline.baseline_at)}；现有持仓已计入总额。</p>
      {capital ? <p>持仓查询：{absoluteChinaTime(capital.position_observed_at)}；账户资金查询：{capital.account_observed_at ? absoluteChinaTime(capital.account_observed_at) : '尚未取得'}。</p> : null}
      {capital?.price_observed_at ? <p>所用报价最早时间：{absoluteChinaTime(capital.price_observed_at)}。</p> : null}
    </details>
  </section>
}
