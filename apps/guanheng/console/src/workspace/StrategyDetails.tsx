import { useQuery, useQueryClient } from '@tanstack/react-query'
import { absoluteChinaTime } from '../components/RelativeTime'
import { fetchStrategyDetails, type OptionalFact, type StrategyDetails as Details } from './strategyDetailsApi'
import type { AccountField, AccountGroup } from './accountApi'
import { accountReadView, type AccountReadView } from './accountPresentation'
import './operations.css'
import { FinancialValue } from './FinancialValue'

type DetailsReadView = { current: Details; account: AccountReadView | undefined }
const queryKey = ['independent-strategy-details']

const amount = (v: unknown) => typeof v === 'number' || typeof v === 'string' && v.trim() && Number.isFinite(Number(v))
  ? Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 2 }) : '尚未取得'
const field = (v?: AccountField, currency = false) => v?.availability === 'present'
  ? currency && (typeof v.value === 'number' || typeof v.value === 'string')
    ? <FinancialValue value={v.value} /> : amount(v.value) : '尚未取得'
const clock = (v?: string | null) => v ? absoluteChinaTime(v) : '尚未取得'
const groupTime = (v?: AccountGroup) => v && 'received_at' in v ? v.received_at : v?.execution_finished_at
function Fact({ name, fact, unit = '' }: { name: string; fact: OptionalFact; unit?: string }) {
  return <div><dt>{name}</dt><dd>{fact.value === null ? '暂不可用' : unit === '元'
    ? <FinancialValue value={fact.value} /> : `${amount(fact.value)}${unit}`}
    {fact.reason ? <small>{fact.reason}</small> : null}</dd></div>
}

/** 当前持仓直接消费券商原发布；归属沿用户确认，策略运行由独立execution事实说明。 */
export default function StrategyDetails() {
  const client = useQueryClient()
  const query = useQuery({queryKey,queryFn:async({signal}):Promise<DetailsReadView>=>{
    const current = await fetchStrategyDetails(signal)
    const previous = client.getQueryData<DetailsReadView>(queryKey)?.account
    return {current,account:current.account ? accountReadView(current.account,previous) : previous}
  },
    retry:false,refetchOnWindowFocus:false,refetchOnReconnect:false})
  const data = query.data?.current
  const currentGroups = data?.account?.groups
  const moneyGroup = query.data?.account?.complete.account ?? currentGroups?.account
  const positionGroup = query.data?.account?.complete.position ?? currentGroups?.position
  const account = moneyGroup?.status === 'complete' ? moneyGroup.rows[0]?.fields : undefined
  const positions = positionGroup?.status === 'complete' ? positionGroup.rows : undefined
  return <section className="surface-card" aria-label="策略实际详情">
    <div className="operations-heading"><h3>当前持仓与运行</h3><button disabled={query.isFetching} onClick={()=>void query.refetch()}>{query.isFetching?'正在读取详情…':'刷新策略详情'}</button></div>
    {query.isError ? <p role="alert">{query.error.message}{data?'。当前保留上次成功结果和原数据时间。':''}</p> : null}
    {query.isPending ? <p role="status">正在读取策略详情…</p> : null}
    {data ? <>
      {query.isFetching ? <p role="status">正在刷新，当前显示上次成功详情。</p> : null}
      <p role="status"><b>{data.execution.label}</b> · {data.execution.reason}</p>
      <dl className="operations-facts">
        <div><dt>策略开始时间</dt><dd>{data.execution.started_at.value === null ? '尚未取得' : clock(String(data.execution.started_at.value))}<small>{data.execution.started_at.reason}</small></dd></div>
        <Fact name="运行时长" fact={data.execution.duration_seconds} unit="秒" />
        <Fact name="策略预算（元）" fact={data.budget_cny} unit="元" />
        <Fact name="累计收益率" fact={data.returns.cumulative_pct} unit="%" />
      </dl>
      <h4>券商账户资金</h4><p>账户资金为全账户查询值；策略预算按WT独立分配展示。</p>
      <dl className="operations-facts">
        <div><dt>账户总资产（元）</dt><dd>{field(account?.total_asset, true)}</dd></div>
        <div><dt>账户可用资金（元）</dt><dd>{field(account?.available, true)}</dd></div>
        <div><dt>账户冻结现金（元）</dt><dd>{field(account?.frozen_cash, true)}</dd></div>
        <div><dt>账户现金总额</dt><dd>尚未取得<small>当前来源未单独发布现金总额；可用资金见上方。</small></dd></div>
      </dl>
      {currentGroups?.account.status !== 'complete' && moneyGroup?.status === 'complete' ? <p role="status">本轮资金未更新，当前保留上次成功资金及原查询时间。</p> : null}
      <p>资金查询时间：{clock(groupTime(moneyGroup))}</p>
      <h4>策略持仓</h4><p>{data.assignment.reason}</p>
      {data.account_reason ? <p role="alert">{data.account_reason}</p> : null}
      {data.account?.reason ? <p>{data.account.reason}</p> : null}
      {currentGroups?.position.status !== 'complete' && positionGroup?.status === 'complete' ? <p role="status">本轮持仓未更新，当前保留上次成功持仓及原查询时间。</p> : null}
      {positions ? positions.length ? <div className="account-table-scroll" role="region" aria-label="策略当前持仓" tabIndex={0}>
        <table><thead><tr><th>证券</th><th>数量（份）</th><th>可卖（份）</th><th>市值（元）</th><th>持仓浮盈（元）</th></tr></thead>
          <tbody>{positions.map((row,index)=><tr key={index}><th scope="row">{row.identity.m_strInstrumentID ? `${row.identity.m_strInstrumentID}.${row.identity.m_strExchangeID??'?'}` : row.identity.wt_symbol??'证券未知'}</th>
            <td>{field(row.fields.quantity)}</td><td>{field(row.fields.sellable)}</td><td>{field(row.fields.market_value, true)}</td><td>{field(row.fields.float_profit, true)}</td></tr>)}</tbody></table>
      </div> : <p>本次完整持仓查询返回为空。</p> : <p role="status">{positionGroup?.reason??'当前持仓尚未取得。'}</p>}
      <p>持仓查询时间：{clock(groupTime(positionGroup))}</p>
      {data.calculation_reason ? <p role="status">{data.calculation_reason}</p> : null}
      {data.calculation ? <p>策略最近计算：{data.calculation.status_label}；决策时间：{clock(data.calculation.decision_at)}</p> : null}
      <p className="portfolio-data-note">本次详情读取：{clock(data.observed_at)}</p>
    </> : null}
  </section>
}
