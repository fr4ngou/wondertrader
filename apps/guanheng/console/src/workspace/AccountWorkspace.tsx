import { useState } from 'react'
import { FinancialValue } from './FinancialValue'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { absoluteChinaTime } from '../components/RelativeTime'
import type { Capabilities } from './IndependentApp'
import { fetchAccountOverview, type AccountField, type AccountGroup, type AccountKind, type AccountRow } from './accountApi'
import { accountReadView, type AccountReadView } from './accountPresentation'
import StrategyRuntimeSummary from './StrategyRuntimeSummary'

const names: Record<AccountKind, string> = { position: '持仓', order: '委托', deal: '成交', account: '资金' }
const columns: Record<Exclude<AccountKind, 'account'>, [string, string][]> = {
  position: [['direction', '持仓方向'], ['quantity', '总量'], ['sellable', '可卖'], ['average_price', '来源均价'], ['open_price', '来源开仓价'], ['market_value', '市值'],
    ['position_profit', '持仓盈亏'], ['float_profit', '浮动盈亏'], ['yesterday', '来源昨持数量'], ['frozen', '来源冻结数量'], ['onroad', '在途数量']],
  order: [['side', '方向'], ['quantity', '委托量'], ['filled', '已成交'], ['remaining', '剩余量'], ['price', '委托价'], ['state', '来源状态码'], ['cancel', '撤拒数量'], ['date', '来源日期'], ['time', '来源时间']],
  deal: [['side', '方向'], ['quantity', '成交量'], ['price', '成交价'], ['amount', '成交额'], ['date', '来源日期'], ['time', '来源时间']],
}
const money = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 4 })

function fieldText(field?: AccountField, side = false, currency = false) {
  if (!field || field.availability !== 'present') return field?.availability === 'invalid' ? '来源值无效' : '未知'
  if (side && (field.value === 48 || field.value === 49)) return field.value === 48 ? '买入' : '卖出'
  if (currency && (typeof field.value === 'number' || typeof field.value === 'string')) return <FinancialValue value={field.value} />
  return typeof field.value === 'number' ? money.format(field.value) : field.value ?? '未知'
}

function timeText(value: string | null) {
  return value && Number.isFinite(Date.parse(value)) ? absoluteChinaTime(value) : '未知'
}

function GroupSource({ group }: { group: AccountGroup }) {
  const source = group.source
  if (source?.kind === 'wt_native_observation' && 'received_at' in group) return <div className="account-source" aria-label={`${names[group.datatype]}来源`}>
    <p>WT原生券商观察；账户名称及运行环境尚未提供。</p>
    <p>本地接收时间：{timeText(group.received_at)}；副本发布时间：{timeText(group.published_at)}</p>
    {group.status==='complete' && group.reason ? <p role="status">{group.reason}</p> : null}
  </div>
  return <div className="account-source" aria-label={`${names[group.datatype]}来源`}>
    <p>{source && source.kind !== 'wt_native_observation' ? <>QMT · {source.account_label} · {source.environment === 'live' ? '实盘来源' : source.environment === 'simulation' ? '模拟来源' : '来源环境未知'}</> : '尚未取得有效来源'}</p>
    <p>查询时间（北京时间）：{timeText(group.execution_started_at)} 至 {timeText(group.execution_finished_at)}</p>
  </div>
}

function RowIdentity({ row, kind }: { row: AccountRow; kind: AccountKind }) {
  const id = row.identity
  const symbol = id.m_strInstrumentID ? `${id.m_strInstrumentID}.${id.m_strExchangeID ?? '?'}` : id.wt_symbol ?? '证券未知'
  return <><td>{symbol}</td>{kind !== 'position' ? <td>{kind === 'deal' ? id.m_strTradeID ?? '未知' : id.m_strOrderSysID ?? '未知'}
    {kind === 'deal' ? <small>委托：{id.m_strOrderSysID ?? '未知'}</small> : null}</td> : null}</>
}

export default function AccountWorkspace({ capability, view = 'account' }: {
  capability: Capabilities['features'][string]; view?: 'account' | 'trading-records' | 'overview'
}) {
  const recordsOnly = view === 'trading-records'
  const labels = {
    account: { title: '账户', description: '查看券商资金、持仓、委托与成交；每类数据保留自己的来源时间。', badge: '只读账户' },
    'trading-records': { title: '交易记录', description: '查看券商全账户委托与成交；与账户页共用读取结果，各类记录保留自己的来源时间。', badge: '只读记录' },
    overview: { title: '总览', description: '查看账户资金、持仓与策略运行结果。', badge: '只读总览' },
  }[view]
  const tabs: ('position' | 'order' | 'deal')[] = recordsOnly ? ['order', 'deal'] : ['position', 'order', 'deal']
  const [tab, setTab] = useState<'position' | 'order' | 'deal'>(recordsOnly ? 'order' : 'position')
  const [page, setPage] = useState(0)
  const client = useQueryClient()
  const query = useQuery({ queryKey: ['independent-account-overview'],
    queryFn: async ({ signal }) => accountReadView(await fetchAccountOverview(signal, capability.timeout_seconds ?? 30),
      client.getQueryData<AccountReadView>(['independent-account-overview'])), enabled: capability.available,
    retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false })
  const data = query.data?.current
  const publication=data?.schema_version==='4.0' ? data.publication : null
  const funds = query.data?.complete.account ?? data?.groups.account
  const fundRow = funds?.status === 'complete' ? funds.rows[0] : undefined
  const group = query.data?.complete[tab] ?? data?.groups[tab]
  const fundsPrevious = data?.groups.account.status === 'unavailable' && funds?.status === 'complete'
  const groupPrevious = data?.groups[tab].status === 'unavailable' && group?.status === 'complete'
  const pages = Math.max(1, Math.ceil((group?.rows.length ?? 0) / 50))
  const pageIndex = Math.min(page, pages - 1)
  return <section className="workspace-page account-workspace">
    <header className="page-heading"><div><h1>{labels.title}</h1><p>{labels.description}</p></div><span className="read-only-stamp">{labels.badge}</span></header>
    {view === 'overview' ? <StrategyRuntimeSummary /> : null}
    <div className="account-actions"><button className="account-refresh" onClick={() => void query.refetch()} disabled={query.isFetching}>{query.isFetching ? '正在读取账户…' : '刷新账户'}</button>
      <span role="status">{!capability.available ? capability.reason ?? '尚未配置账户读取连接'
        : query.isFetching ? '正在读取账户，请等待本轮完成'
          : publication ? ({waiting:'等待WT首轮账户结果',refreshing:'WT正在更新账户',ready:'正在显示WT已发布结果',degraded:'WT本轮更新失败',stopped:'WT账户发布已停止',unconfigured:'尚未取得WT账户发布'}[publication.state])
            : data ? ({ complete: '四类账户数据读取完成', partial: '本轮部分数据可用', unavailable: '本轮账户数据不可用' }[data.status]) : '尚未取得本轮账户数据'}</span></div>
    {query.isError ? <div role="alert"><p>{query.error.message}</p><p>{data
      ? '本次刷新失败，当前保留上次读取结果，各类数据时间见下方。可按“刷新账户”重试。'
      : '尚未取得账户数据，可稍后按“刷新账户”重试。'}</p></div> : null}
    {data && query.isFetching ? <p role="status">正在刷新，当前显示上次读取结果，各类数据时间见下方。</p> : null}
    {data && !capability.available ? <p role="status">当前显示已读取的账户结果，各类数据时间见下方；可主动刷新检查连接。</p> : null}
    {data ? <>
      {publication ? <div role={publication.state==='degraded' ? 'alert' : 'status'}><p>刷新页面只读取WT发布结果，账户查询由WT独立更新。</p>
        <p>最近发布：{timeText(publication.updated_at)}；上次成功：{timeText(publication.last_success_at)}</p>
        {publication.runtime_state!=='ready' ? <p>WT当前尚未处于就绪状态，以下结果保留原查询时间。</p> : null}</div> : null}
      <p role={data.status === 'complete' ? 'status' : 'alert'}>{data.reason}</p>
      {!recordsOnly ? <div className="account-funds">{[['total_asset', '总资产'], ['available', '可用资金'], ['frozen_cash', '冻结现金'], ['commission', '来源手续费']].map(([key, label]) => <article className="surface-card" key={key}>
        <h2>{label}（元）</h2><strong title={fundRow?.fields[key]?.reason ?? undefined}>{fieldText(fundRow?.fields[key], false, true)}</strong>
      </article>)}</div> : null}
      {!recordsOnly && funds ? <><p>{fundsPrevious ? `本轮资金未更新，保留上次成功结果。${data.groups.account.reason ?? ''}` : funds.status !== 'complete' ? funds.reason ?? '本轮资金查询未完成，金额保持未知。' : funds.rows.length === 0 ? '本轮资金返回为空，未作为零资产处理。' : '资金查询时间见下方。'}</p><GroupSource group={funds} />
        {fundRow ? <details><summary>查看其余来源资金字段</summary><dl className="account-money-details">{[['previous_balance', '前余额'], ['frozen_margin', '冻结保证金'], ['frozen_commission', '冻结手续费'], ['position_profit', '持仓盈亏'], ['float_profit', '浮动盈亏']].map(([key, label]) => <div key={key}><dt>{label}（元）</dt><dd title={fundRow.fields[key]?.reason ?? undefined}>{fieldText(fundRow.fields[key], false, true)}</dd></div>)}</dl></details> : null}</> : null}
      <div role="tablist" aria-label={recordsOnly ? '交易记录类型' : '账户记录'} className="period-switch">{tabs.map((kind, index, kinds) => <button role="tab" className={tab === kind ? 'period-active' : ''} tabIndex={tab === kind ? 0 : -1} aria-selected={tab === kind} id={`account-tab-${kind}`} aria-controls={`account-panel-${kind}`} key={kind}
        onClick={() => { setTab(kind); setPage(0) }} onKeyDown={event => {
          const target = event.key === 'ArrowRight' ? kinds[(index + 1) % kinds.length] : event.key === 'ArrowLeft' ? kinds[(index + kinds.length - 1) % kinds.length]
            : event.key === 'Home' ? kinds[0] : event.key === 'End' ? kinds[kinds.length - 1] : null
          if (target) { event.preventDefault(); setTab(target); setPage(0); document.getElementById(`account-tab-${target}`)?.focus() }
        }}>{names[kind]}</button>)}</div>
      {group ? <article className="surface-card" role="tabpanel" id={`account-panel-${tab}`} aria-labelledby={`account-tab-${tab}`}>
        <h2>{names[tab]}</h2>{groupPrevious ? <p role="status">本轮{names[tab]}未更新，保留上次成功结果。{data.groups[tab].reason}</p> : null}<GroupSource group={group} />
        {group.status === 'unavailable' ? <p role="status">{group.reason ?? `本轮${names[tab]}查询未完成，请稍后重读。`}</p>
          : group.rows.length === 0 ? <p role="status">{group.source?.kind === 'wt_native_observation' ? `最近发布的${names[tab]}观察为空。` : `本轮${names[tab]}查询完整，返回 0 条记录。`}</p>
            : <div className="account-table-scroll" tabIndex={0} role="region" aria-label={`${names[tab]}明细，可横向滚动`}><table><thead><tr><th scope="col">证券</th>{tab !== 'position' ? <th scope="col">{tab === 'deal' ? '成交编号 / 委托编号' : '委托编号'}</th> : null}
              {columns[tab].map(([key, label]) => <th scope="col" key={key}>{label}</th>)}
            </tr></thead><tbody>{group.rows.slice(pageIndex * 50, (pageIndex + 1) * 50).map((row, index) => <tr key={`${tab}-${pageIndex}-${index}`}><RowIdentity row={row} kind={tab} />{columns[tab].map(([key]) => <td key={key} title={row.fields[key]?.reason ?? undefined}>{fieldText(row.fields[key], key === 'side', ['market_value', 'position_profit', 'float_profit', 'amount'].includes(key))}</td>)}</tr>)}</tbody></table></div>}
        {group.status === 'complete' && group.rows.length ? <div className="account-actions" aria-label="账户明细分页"><span>{group.rows.length} 条记录 · 第 {pageIndex + 1} / {pages} 页</span><button disabled={pageIndex === 0} onClick={() => setPage(pageIndex - 1)}>上一页</button><button disabled={pageIndex + 1 === pages} onClick={() => setPage(pageIndex + 1)}>下一页</button></div> : null}
        <details><summary>字段与查询范围说明</summary><p>“未知”表示来源未提供该事实；来源值无效时保持缺失。可卖数量与总量分别来自券商查询，差额不作为委托冻结数量。</p>
          {tab !== 'position' ? <p>此处显示全账户查询记录，记录中的策略归属和价格类型以已取得的信息为准。</p> : null}
          <p>各类数据分别保留来源时点，接收与发布时间以各类来源标注为准。</p></details>
      </article> : null}
      <p>券商交易日：{fieldText(data.trade_date)}。</p>
    </> : null}
  </section>
}
