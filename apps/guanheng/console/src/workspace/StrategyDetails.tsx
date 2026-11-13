import { WorkspaceDock } from './WorkspaceDock'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { absoluteChinaTime } from '../components/RelativeTime'
import { fetchStrategyDetails, type OptionalFact, type StrategyDetails as Details } from './strategyDetailsApi'
import { accountReadView, type AccountReadView } from './accountPresentation'
import './operations.css'
import { FinancialValue } from './FinancialValue'
import { StatusBadge } from './StatusBadge'
import { Link } from 'react-router-dom'
import { StrategyCapitalSummary } from './StrategyCapitalSummary'
import { StrategyPositionTargets } from './StrategyPositionTargets'
import { strategyKey } from './StrategyPicker'
import { currentAuxiliaryPresentation } from './currentAuxiliary'
import type { StrategyDefinition } from './strategyCatalogApi'

type DetailsReadView = { current: Details; account: AccountReadView | undefined }

const clock = (v?: string | null) => v ? absoluteChinaTime(v) : '尚未取得'
function Fact({ name, fact, unit, observedAt }: { name: string; fact: OptionalFact; unit: '元' | '%'; observedAt?: string }) {
  return <div><dt>{name}</dt><dd>{fact.value === null ? '暂不可用' : unit === '元'
    ? <FinancialValue value={fact.value} /> : `${fact.value}%`}
    {observedAt ? <small className="strategy-fact-observed">估值截至 <time dateTime={observedAt}>{clock(observedAt)}</time></small> : null}
    {fact.reason ? <details className="compact-details"><summary>说明</summary><small>{fact.reason}</small></details> : null}</dd></div>
}

/** 当前持仓直接消费券商原发布；归属沿用户确认，策略运行由独立execution事实说明。 */
export default function StrategyDetails({ strategy }: {
  /** 目录选择的策略身份；运行接口返回的身份须与之相符。 */ strategy?: Pick<StrategyDefinition, 'strategy_id' | 'strategy_version'>
}) {
  const client = useQueryClient()
  const queryKey = ['independent-strategy-details', strategy ? strategyKey(strategy) : 'current']
  const query = useQuery({queryKey,queryFn:async({signal}):Promise<DetailsReadView>=>{
    const current = await fetchStrategyDetails(signal, strategy?.strategy_id)
    if (strategy && strategyKey(current.strategy) !== strategyKey(strategy)) throw new Error('尚未取得该策略的运行与持仓数据。')
    const cached = client.getQueryData<DetailsReadView>(queryKey)
    // 本代已知时清除上一代持仓；整轮503仍由query保留原视图及错误提示。
    const previous = cached?.current.runtime_scope_id === current.runtime_scope_id ? cached?.account : undefined
    return {current,account:current.account ? accountReadView(current.account,previous) : previous}
  },
    // 日常WT换代后在原页面接收本代事实；失败仍由query保留成功详情和原时间。
    retry:false,refetchInterval:5_000,refetchOnWindowFocus:false,refetchOnReconnect:false})
  const data = query.data?.current
  const currentGroups = data?.account?.groups
  const moneyGroup = query.data?.account?.complete.account ?? currentGroups?.account
  const positionGroup = query.data?.account?.complete.position ?? currentGroups?.position
  const runFacts = data ? <dl className="strategy-run-facts">
    {!data.capital_baseline ? <Fact name="策略预算（元）" fact={data.budget_cny} unit="元" /> : null}
    <Fact name="累计收益率" fact={data.returns.cumulative_pct} unit="%" observedAt={data.returns.valued_at} />
  </dl> : null
  return <section className="surface-card strategy-compact" aria-label="策略实际详情">
    <div className="operations-heading strategy-runtime-heading">
      <h3>当前持仓与运行</h3>
      {data ? <span className="strategy-execution-state" role="status"><StatusBadge state={data.execution.state} label={data.execution.label} /></span> : null}
      <div className="strategy-runtime-actions">
        {data ? <Link to="/account">查看券商账户</Link> : null}
        <button disabled={query.isFetching} onClick={() => void query.refetch()}>{query.isFetching ? '正在读取详情…' : '刷新策略详情'}</button>
      </div>
    </div>
    {query.isError ? <p role="alert">{query.error.message}{data?'。当前保留上次成功结果和原数据时间。':''}</p> : null}
    {query.isPending ? <p role="status">正在读取策略详情…</p> : null}
    {data ? <>
      {data.execution.state !== 'ready' ? <p role="status">{data.execution.reason}</p> : null}
      {currentGroups?.account.status !== 'complete' && moneyGroup?.status === 'complete' ? <p role="status">本轮资金未更新，当前保留上次成功资金及原查询时间。</p> : null}
      <WorkspaceDock layoutId="strategy-runtime" primaryTitle="持仓与目标仓位" secondaryTitle="资金与决策" secondaryWidth={350}
        primary={<StrategyPositionTargets details={data} positionGroup={positionGroup} positionRefreshed={currentGroups?.position.status === 'complete'} />}
        secondary={<>
      <StrategyCapitalSummary baseline={data.capital_baseline} capital={data.capital} />
      {(data.calculation?.owned_valuation?.unknown_fee_count ?? 0) > 0 || data.calculation?.valuation_reason === 'actual_fees_unconfirmed'
        ? <p role="status">实际手续费待确认{data.returns.valued_at ? ' · 最近合格估值 ' + clock(data.returns.valued_at) : ''}</p> : null}
      {runFacts}
      {data.calculation_reason ? <p role="status">{data.calculation_reason}</p> : null}
      {data.calculation ? <p title={currentAuxiliaryPresentation(data.calculation).title}>策略最近计算：{data.calculation.status_label}；决策时间：{clock(data.calculation.decision_at)}；{currentAuxiliaryPresentation(data.calculation).label}</p> : null}
      {data.calculation?.consumed_signal ? <section aria-label="已消费信号">
        <p>{data.calculation.status === 'holding' ? '已计算，目标未变' : data.calculation.status_label} · 信号日 {data.calculation.consumed_signal.decision_date} · 适用交易日 {data.calculation.consumed_signal.eligible_date}</p>
        <table>
          <thead><tr><th>标的</th><th>信号</th><th>历史模型</th><th>辅助数据</th></tr></thead>
          <tbody>{data.calculation.consumed_signal.securities.map(row => <tr key={row.symbol}>
            <td>{row.symbol}</td>
            <td>{row.qualified ? (row.actions.length ? row.actions.map(action => action === 'BUY' ? '买入' : '卖出').join('、') : '未触发') : '输入待核验'}</td>
            <td>{row.model_held === null ? '未知' : row.model_held ? '持有' : '空仓'}</td>
            <td>{row.auxiliary_missing.map(reason => ({
              today_shares_missing: '缺份额', today_margin_missing: '缺融资', today_turnover_missing: '缺成交额',
              shares_units_unknown: '份额单位待核验', margin_units_unknown: '融资单位待核验',
              turnover_units_unknown: '成交额单位待核验',
            }[reason] ?? '待核验')).join('、') || '无缺项记录'}</td>
          </tr>)}</tbody>
        </table>
      </section> : null}

        </>} />
    </> : null}
  </section>
}
