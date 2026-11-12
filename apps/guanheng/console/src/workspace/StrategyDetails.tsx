import { useQuery, useQueryClient } from '@tanstack/react-query'
import { absoluteChinaTime } from '../components/RelativeTime'
import { fetchStrategyDetails, type OptionalFact, type StrategyDetails as Details } from './strategyDetailsApi'
import type { AccountField, AccountGroup, AccountRow } from './accountApi'
import { accountReadView, type AccountReadView } from './accountPresentation'
import './operations.css'
import { FinancialValue } from './FinancialValue'
import { StatusBadge } from './StatusBadge'
import { Link } from 'react-router-dom'
import { StrategyCapitalSummary } from './StrategyCapitalSummary'
import { StrategyPositionTargets, StrategySecurityLabel } from './StrategyPositionTargets'
import { strategyKey } from './StrategyPicker'
import { currentAuxiliaryPresentation } from './currentAuxiliary'
import type { StrategyDefinition } from './strategyCatalogApi'

type DetailsReadView = { current: Details; account: AccountReadView | undefined }

const amount = (v: unknown) => typeof v === 'number' || typeof v === 'string' && v.trim() && Number.isFinite(Number(v))
  ? Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 2 }) : '尚未取得'
const field = (v?: AccountField, currency = false) => v?.availability === 'present'
  ? currency && (typeof v.value === 'number' || typeof v.value === 'string')
    ? <FinancialValue value={v.value} /> : amount(v.value) : '尚未取得'
const clock = (v?: string | null) => v ? absoluteChinaTime(v) : '尚未取得'
const groupTime = (v?: AccountGroup) => v && 'received_at' in v ? v.received_at : v?.execution_finished_at
function positionSymbol({ identity }: AccountRow) {
  if (identity.m_strInstrumentID && identity.m_strExchangeID) return `${identity.m_strInstrumentID}.${identity.m_strExchangeID}`
  return identity.wt_symbol ?? (identity.m_strInstrumentID ? `${identity.m_strInstrumentID}.?` : '证券未知')
}
function runtimeDuration(value: string | number) {
  const seconds = Math.floor(Number(value))
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor(seconds / 3600) % 24
  const minutes = Math.floor(seconds / 60) % 60
  return days > 0 ? `${days}天${hours}小时` : hours > 0 ? `${hours}小时${minutes}分钟`
    : minutes > 0 ? `${minutes}分钟${seconds % 60}秒` : `${seconds}秒`
}
function Fact({ name, fact, unit = '' }: { name: string; fact: OptionalFact; unit?: string }) {
  return <div><dt>{name}</dt><dd>{fact.value === null ? '暂不可用' : unit === '元'
    ? <FinancialValue value={fact.value} /> : unit === '秒' ? runtimeDuration(fact.value) : `${amount(fact.value)}${unit}`}
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
    retry:false,refetchInterval:15_000,refetchOnWindowFocus:false,refetchOnReconnect:false})
  const data = query.data?.current
  const currentGroups = data?.account?.groups
  const moneyGroup = query.data?.account?.complete.account ?? currentGroups?.account
  const positionGroup = query.data?.account?.complete.position ?? currentGroups?.position
  const allocated = data?.calculation?.position_basis === 'strategy-allocated'
  const owned = allocated ? data?.calculation?.positions : undefined
  const positions: AccountRow[] | undefined = allocated ? owned && owned.length > 0 && owned.every(p => p.broker_quantity !== null && p.broker_sellable !== null) ? owned.filter(p => p.broker_quantity! > 0).map(p => ({
    identity: {m_strInstrumentID:p.symbol.slice(0,6),m_strExchangeID:p.symbol.slice(-2)},
    fields: {quantity:{availability:'present' as const,value:p.broker_quantity!,reason:null},sellable:{availability:'present' as const,value:p.broker_sellable!,reason:null}}
  })) : undefined : positionGroup?.status === 'complete' ? positionGroup.rows : undefined
  const hasRunFacts = data && [data.execution.started_at, data.execution.duration_seconds, data.returns.cumulative_pct].some(fact => fact.value !== null)
  const runFacts = data ? <dl className="operations-facts">
    <div><dt>执行开始时间</dt><dd>{data.execution.started_at.value === null ? '尚未取得' : clock(String(data.execution.started_at.value))}{data.execution.started_at.reason ? <details className="compact-details"><summary>说明</summary><small>{data.execution.started_at.reason}</small></details> : null}</dd></div>
    <Fact name="运行时长" fact={data.execution.duration_seconds} unit="秒" />
    {!data.capital_baseline ? <Fact name="策略预算（元）" fact={data.budget_cny} unit="元" /> : null}
    <Fact name="累计收益率" fact={data.returns.cumulative_pct} unit="%" />
  </dl> : null
  return <section className="surface-card strategy-compact" aria-label="策略实际详情">
    <div className="operations-heading"><h3>当前持仓与运行</h3><button disabled={query.isFetching} onClick={()=>void query.refetch()}>{query.isFetching?'正在读取详情…':'刷新策略详情'}</button></div>
    {query.isError ? <p role="alert">{query.error.message}{data?'。当前保留上次成功结果和原数据时间。':''}</p> : null}
    {query.isPending ? <p role="status">正在读取策略详情…</p> : null}
    {data ? <>
      {query.isFetching ? <p role="status">正在刷新，当前显示上次成功详情。</p> : null}
      <div className="compact-status-strip" role="status"><StatusBadge state={data.execution.state} label={data.execution.label} /><small>持仓观察时间 {clock(allocated ? data.calculation?.broker_observed_at : groupTime(positionGroup))}</small><Link to="/account">查看券商账户</Link></div>
      <StrategyCapitalSummary baseline={data.capital_baseline} capital={data.capital} />
      {!data.capital_baseline || hasRunFacts ? runFacts : <details className="compact-details"><summary>运行与收益</summary>{runFacts}</details>}
      {data.execution.state !== 'ready' ? <p role="status">{data.execution.reason}</p> : null}
      {currentGroups?.account.status !== 'complete' && moneyGroup?.status === 'complete' ? <p role="status">本轮资金未更新，当前保留上次成功资金及原查询时间。</p> : null}
      <p className="strategy-catalog-note">{data.assignment.reason}</p>
      <h4>{allocated ? '策略自有持仓' : '账户聚合持仓'} <small>{positions?.length ?? '—'} 项</small></h4>
      {data.account_reason ? <p role="alert">{data.account_reason}</p> : null}
      {!allocated && currentGroups?.position.status !== 'complete' && positionGroup?.status === 'complete' ? <p role="status">本轮持仓未更新，当前保留上次成功持仓及原查询时间。</p> : null}
      {positions ? positions.length ? <div className="account-table-scroll" role="region" aria-label="策略当前持仓" tabIndex={0}>
        <table><thead><tr><th>证券</th><th>数量（份）</th><th>可卖（份）</th><th>市值（元）</th><th>持仓浮盈（元）</th></tr></thead>
          <tbody>{positions.map((row,index)=><tr key={index}><th scope="row"><StrategySecurityLabel symbol={positionSymbol(row)} names={data.security_names} /></th>
            <td>{field(row.fields.quantity)}</td><td>{field(row.fields.sellable)}</td><td>{field(row.fields.market_value, true)}</td><td>{field(row.fields.float_profit, true)}</td></tr>)}</tbody></table>
      </div> : <p>本次完整持仓查询返回为空。</p> : <p role="status">{positionGroup?.reason??'当前持仓尚未取得。'}</p>}

      {data.strategy.strategy_version && <StrategyPositionTargets details={data} />}
      {data.calculation_reason ? <p role="status">{data.calculation_reason}</p> : null}
      {data.calculation ? <p title={currentAuxiliaryPresentation(data.calculation).title}>策略最近计算：{data.calculation.status_label}；决策时间：{clock(data.calculation.decision_at)}；{currentAuxiliaryPresentation(data.calculation).label}</p> : null}

    </> : null}
  </section>
}
