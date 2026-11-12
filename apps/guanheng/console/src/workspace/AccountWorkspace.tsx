import { WorkspaceDock } from './WorkspaceDock'
import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { FinancialValue } from './FinancialValue'
import { useQuery } from '@tanstack/react-query'
import { absoluteChinaTime } from '../components/RelativeTime'
import type { Capabilities } from './IndependentApp'
import type { AccountField, AccountGroup, AccountKind, AccountRow } from './accountApi'
import { useAccountReadView } from './useAccountReadView'
import { StatusBadge } from './StatusBadge'
import { fetchRunningStrategies } from './strategyCatalogApi'

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

function numericField(field?: AccountField): number | null {
  if (field?.availability !== 'present' || field.value === null || String(field.value).trim() === '') return null
  const number = Number(field.value)
  return Number.isFinite(number) ? number : null
}

/** 汇总同一完整持仓批次；任一持仓金额未知时保留整体未知。 */
function positionTotal(group: AccountGroup | undefined, field: 'market_value' | 'float_profit') {
  if (group?.status !== 'complete') return null
  let total = 0
  for (const row of group.rows) {
    if (numericField(row.fields.quantity) === 0) continue
    const value = numericField(row.fields[field])
    if (value === null) return null
    total += value
  }
  return Number.isFinite(total) ? total : null
}

function RunningStrategies() {
  const query = useQuery({ queryKey: ['overview-running-strategies'],
    queryFn: ({ signal }) => fetchRunningStrategies(signal), retry: false, refetchInterval: 15_000 })
  return <section className="surface-card overview-running" aria-label="正在运行的策略">
    <h2>正在运行的策略</h2>
    {query.isError ? <p role="status">本轮运行状态读取失败。<button onClick={() => void query.refetch()}>重新读取</button></p>
      : query.isPending ? <p role="status">正在读取运行状态…</p>
        : query.data === null ? <p role="status">当前运行状态待核实。</p>
          : query.data.length === 0 ? <p role="status">当前没有运行中的策略。</p> : null}
    {!query.isError && query.data?.length ? <ul>{query.data.map(row => {
      const key = `${row.strategy_id}@${row.strategy_version ?? 'unknown'}`
      return <li key={key}><NavLink to={'/strategies?' + new URLSearchParams({ strategy: key, view: 'runtime' })}>
        <span><strong>{row.display_name}</strong>{row.strategy_version ? <small>v{row.strategy_version}</small> : null}</span>
        <span className="overview-strategy-state"><span aria-hidden="true" />{row.status_label}</span>
      </NavLink></li>
    })}</ul> : null}
  </section>
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
    overview: { title: '总览', description: '账户资金与记录概况。', badge: '只读总览' },
  }[view]
  const tabs: ('position' | 'order' | 'deal')[] = recordsOnly ? ['order', 'deal'] : ['position', 'order', 'deal']
  const [tab, setTab] = useState<'position' | 'order' | 'deal'>(recordsOnly ? 'order' : 'position')
  const [page, setPage] = useState(0)
  const query = useAccountReadView(capability)
  const data = query.data?.current
  const publication=data?.schema_version==='4.0' ? data.publication : null
  const funds = query.data?.complete.account ?? data?.groups.account
  const fundRow = funds?.status === 'complete' ? funds.rows[0] : undefined
  const group = query.data?.complete[tab] ?? data?.groups[tab]
  const fundsPrevious = data?.groups.account.status === 'unavailable' && funds?.status === 'complete'
  const groupPrevious = data?.groups[tab].status === 'unavailable' && group?.status === 'complete'
  const pages = Math.max(1, Math.ceil((group?.rows.length ?? 0) / 50))
  const pageIndex = Math.min(page, pages - 1)
  const state = query.isFetching ? 'refreshing' : !capability.available ? 'unconfigured' : publication?.state ?? data?.status ?? 'waiting'
  const stateLabel = ({ refreshing: '正在更新', ready: '已发布', stopped: '已停止', degraded: '更新失败',
    unconfigured: '未配置', waiting: '等待数据', complete: '读取完成', partial: '部分可用', unavailable: '不可用' } as Record<string,string>)[state] ?? state
  const latest = publication?.last_success_at ?? funds?.execution_finished_at ?? null
  const positionGroup = query.data?.complete.position ?? data?.groups.position
  const holdingValue = positionTotal(positionGroup, 'market_value')
  const accountProfit = numericField(fundRow?.fields.float_profit)
  const floatingProfit = accountProfit ?? positionTotal(positionGroup, 'float_profit')
  const fundsAt = funds?.execution_finished_at ?? null
  const positionsAt = positionGroup && ('received_at' in positionGroup ? positionGroup.received_at : positionGroup.execution_finished_at)
  const accountStatus = (overview: boolean) => <div className="account-heading-meta">
    <div className="account-heading-status" role="status">
      <StatusBadge state={state} label={`账户 · ${stateLabel}`} />
      <small>{latest ? `${overview ? '账户更新于' : '数据时间'} ${timeText(latest)}` : overview ? '等待账户数据' : capability.reason ?? '等待首轮数据'}</small>
    </div>
    <button onClick={() => void query.refetch()} disabled={query.isFetching}>
      {overview ? (query.isFetching ? '更新中…' : '刷新') : (query.isFetching ? '正在读取账户…' : '刷新账户')}
    </button>
  </div>
  if (view === 'overview') return <section className="workspace-page account-workspace overview-workspace">
    <header className="page-heading account-page-heading"><h1>总览</h1>{accountStatus(true)}</header>
    {query.isError ? <p role="alert">{query.error.message}</p> : null}
    <WorkspaceDock layoutId="overview" primaryTitle="账户概况" secondaryTitle="正在运行的策略" secondaryWidth={340}
      secondary={<RunningStrategies />}
      primary={<><section className="overview-financials" aria-label="账户金额">
      <div className="overview-amounts">
        <article className="surface-card"><h2>总持仓金额（元）</h2><strong>{holdingValue === null ? '未知' : <FinancialValue value={holdingValue} />}</strong>
          {positionsAt ? <small>持仓 {timeText(positionsAt)}</small> : null}</article>
        <article className="surface-card"><h2>总金额（元）</h2><strong>{fieldText(fundRow?.fields.total_asset, false, true)}</strong>
          {fundsAt ? <small>账户总资产 · {timeText(fundsAt)}</small> : null}</article>
        <article className="surface-card"><h2>浮动盈亏（元）</h2><strong className={floatingProfit === null ? undefined : floatingProfit > 0 ? 'financial-gain' : floatingProfit < 0 ? 'financial-loss' : undefined}>
          {floatingProfit === null ? '未知' : <FinancialValue value={floatingProfit} />}</strong>
          {floatingProfit !== null ? <small>{accountProfit === null ? '按持仓汇总' : '账户发布'} · {timeText((accountProfit === null ? positionsAt : fundsAt) ?? null)}</small> : null}</article>
      </div>
      <dl className="overview-secondary-funds">
        <div><dt>账户可用资金（元）</dt><dd>{fieldText(fundRow?.fields.available, false, true)}</dd></div>
        <div><dt>账户冻结现金（元）</dt><dd>{fieldText(fundRow?.fields.frozen_cash, false, true)}</dd></div>
      </dl>
    </section>
    <div className="overview-counts">{(['position', 'order', 'deal'] as const).map(kind => {
      const records = query.data?.complete[kind] ?? data?.groups[kind]
      return <article className="surface-card" key={kind}><h2>{names[kind]}记录</h2>
        <strong>{records?.status === 'complete' ? records.rows.length.toLocaleString('zh-CN') : '—'}</strong>
      </article>
    })}</div></>} />
    <nav className="overview-links" aria-label="账户快捷入口"><NavLink to="/account">资金与持仓 →</NavLink>
      <NavLink to="/orders">委托与成交 →</NavLink><NavLink to="/operations">系统状态 →</NavLink></nav>
  </section>
  const fundsContent = data ? <>
    <div className="account-funds">{[['total_asset', '总资产'], ['available', '可用资金'], ['frozen_cash', '冻结现金'], ['commission', '来源手续费']].map(([key, label]) => <article className="surface-card" key={key}>
        <h2>{label}（元）</h2><strong title={fundRow?.fields[key]?.reason ?? undefined}>{fieldText(fundRow?.fields[key], false, true)}</strong>
      </article>)}</div>
      {funds ? <>{fundsPrevious || funds.status !== 'complete' || funds.rows.length === 0 ? <p>{fundsPrevious ? `本轮资金未更新，保留上次成功结果。${data.groups.account.reason ?? ''}` : funds.status !== 'complete' ? funds.reason ?? '本轮资金查询未完成，金额保持未知。' : funds.rows.length === 0 ? '本轮资金返回为空，未作为零资产处理。' : ''}</p> : null}
        {fundRow ? <details><summary>更多资金字段</summary><dl className="account-money-details">{[['previous_balance', '前余额'], ['frozen_margin', '冻结保证金'], ['frozen_commission', '冻结手续费'], ['position_profit', '持仓盈亏'], ['float_profit', '浮动盈亏']].map(([key, label]) => <div key={key}><dt>{label}（元）</dt><dd title={fundRow.fields[key]?.reason ?? undefined}>{fieldText(fundRow.fields[key], false, true)}</dd></div>)}</dl></details> : null}</> : null}
  </> : null
  const recordsContent = data ? <>
    <div role="tablist" aria-label={recordsOnly ? '交易记录类型' : '账户记录'} className="period-switch">{tabs.map((kind, index, kinds) => <button role="tab" className={tab === kind ? 'period-active' : ''} tabIndex={tab === kind ? 0 : -1} aria-selected={tab === kind} id={`account-tab-${kind}`} aria-controls={`account-panel-${kind}`} key={kind}
        onClick={() => { setTab(kind); setPage(0) }} onKeyDown={event => {
          const target = event.key === 'ArrowRight' ? kinds[(index + 1) % kinds.length] : event.key === 'ArrowLeft' ? kinds[(index + kinds.length - 1) % kinds.length]
            : event.key === 'Home' ? kinds[0] : event.key === 'End' ? kinds[kinds.length - 1] : null
          if (target) { event.preventDefault(); setTab(target); setPage(0); document.getElementById(`account-tab-${target}`)?.focus() }
        }}>{names[kind]}</button>)}</div>
      {group ? <article className="surface-card" role="tabpanel" id={`account-panel-${tab}`} aria-labelledby={`account-tab-${tab}`}>
        <div className="account-table-heading"><h2>{names[tab]}</h2><small>数据时间 {timeText('received_at' in group ? group.received_at : group.execution_finished_at)}</small></div>{groupPrevious ? <p role="status">本轮{names[tab]}未更新，保留上次成功结果。{data.groups[tab].reason}</p> : null}
        {group.status === 'unavailable' ? <p role="status">{group.reason ?? `本轮${names[tab]}查询未完成，请稍后重读。`}</p>
          : group.rows.length === 0 ? <p role="status">{group.source?.kind === 'wt_native_observation' ? `最近发布的${names[tab]}观察为空。` : `本轮${names[tab]}查询完整，返回 0 条记录。`}</p>
            : <div className="account-table-scroll" tabIndex={0} role="region" aria-label={`${names[tab]}明细，可横向滚动`}><table><thead><tr><th scope="col">证券</th>{tab !== 'position' ? <th scope="col">{tab === 'deal' ? '成交编号 / 委托编号' : '委托编号'}</th> : null}
              {columns[tab].map(([key, label]) => <th scope="col" key={key}>{label}</th>)}
            </tr></thead><tbody>{group.rows.slice(pageIndex * 50, (pageIndex + 1) * 50).map((row, index) => <tr key={`${tab}-${pageIndex}-${index}`}><RowIdentity row={row} kind={tab} />{columns[tab].map(([key]) => <td key={key} title={row.fields[key]?.reason ?? undefined}>{fieldText(row.fields[key], key === 'side', ['market_value', 'position_profit', 'float_profit', 'amount'].includes(key))}</td>)}</tr>)}</tbody></table></div>}
        {group.status === 'complete' && group.rows.length ? <div className="account-actions" aria-label="账户明细分页"><span>{group.rows.length} 条记录 · 第 {pageIndex + 1} / {pages} 页</span><button disabled={pageIndex === 0} onClick={() => setPage(pageIndex - 1)}>上一页</button><button disabled={pageIndex + 1 === pages} onClick={() => setPage(pageIndex + 1)}>下一页</button></div> : null}
      </article> : null}
      <details className="compact-details"><summary>交易日</summary><p>券商交易日：{fieldText(data.trade_date)}。</p></details>
  </> : null
  return <section className="workspace-page account-workspace">
    <header className="page-heading account-page-heading"><h1>{labels.title}</h1>{accountStatus(false)}</header>
    {query.isError ? <p role="alert">{query.error.message}{data ? ' · 保留上次成功结果' : ''}</p> : null}
    {!capability.available && latest ? <p role="status">{capability.reason ?? '账户读取当前不可用'}。当前显示已读取的账户结果。</p> : null}
    {data ? <>
      {data.status !== 'complete' || publication?.state === 'degraded' ? <p role="status">{data.reason}</p> : null}
      {recordsOnly ? recordsContent : <WorkspaceDock layoutId="account" primaryTitle="资金" secondaryTitle="持仓、委托与成交" side="below"
        primary={fundsContent} secondary={recordsContent} />}
    </> : null}
  </section>
}
