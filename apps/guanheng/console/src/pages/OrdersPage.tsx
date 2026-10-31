import { useQuery } from '@tanstack/react-query'
import {
  ChevronLeft,
  ChevronRight,
  GitBranch,
  LockKeyhole,
  ReceiptText,
  RotateCcw,
  Search,
} from 'lucide-react'
import { type FormEvent, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { fetchAccountExecutionBatches, fetchExecutionQueue, fetchOrderTrace, fetchOrders } from '../api'
import { EmptyState } from '../components/EmptyState'
import { InfoTip } from '../components/InfoTip'
import { absoluteChinaTime } from '../components/RelativeTime'
import { diagnosticLabel } from '../diagnosticPresentation'
import { queueCountLabel, queueDayLabel, queueIsTerminal, queueProgressLabel, queueStageLabel, summarizeExecutionQueue } from '../executionQueuePresentation'
import { orderFailureReasonLabel, orderSideNames, orderStageNames, orderStatusNames } from '../orderPresentation'
import type { ConsoleBootstrap, OrderLedgerFilters, OrderSummary } from '../types'

const PAGE_SIZE = 20
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const SYMBOL_PATTERN = /^[0-9]{6}\.(SH|SZ)$/

type FilterDraft = {
  symbol: string
  strategy_id: string
  status: '' | OrderSummary['status']
  correlation_id: string
  created_from: string
  created_to: string
}

type DatePreset = 'all' | 'today' | '7d' | '30d'

const EMPTY_FILTERS: FilterDraft = {
  symbol: '', strategy_id: '', status: '', correlation_id: '', created_from: '', created_to: '',
}

function dateBoundary(value: string, end = false): string | undefined {
  if (!value) return undefined
  return new Date(`${value}T${end ? '23:59:59.999' : '00:00:00'}+08:00`).toISOString()
}

function localDate(daysAgo = 0) {
  const value = new Date(Date.now() - daysAgo * 24 * 60 * 60 * 1000)
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(value)
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value ?? ''
  return `${part('year')}-${part('month')}-${part('day')}`
}

function price(value?: number | null): string {
  return value == null ? '—' : value.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
}

function money(value: number): string {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency', currency: 'CNY', minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(value)
}

const queueSourceNames: Record<string, string> = {
  automatic_strategy: '自动策略', operator_manual: '人工流程',
}

const queueFactNames: Record<string, string> = {
  not_evaluated: '未复核', not_reached: '尚未到达', accepted: '已接受', rejected: '已拒绝',
  failed: '失败', unavailable: '不可用', not_applicable: '不适用',
}

const accountBatchStateNames: Record<string, string> = {
  planning: '规划中', active: '执行中', blocked: '已阻断', invalidated: '已失效', completed: '已完成',
}

const reservationStateNames: Record<string, string> = {
  provisional: '暂定预留', committed: '已提交预留', unknown: '柜台结果未知',
  executed_unabsorbed: '成交待账本吸收', released: '已释放',
}

export function OrdersPage({ bootstrap }: { bootstrap: ConsoleBootstrap }) {
  const [searchParams] = useSearchParams()
  const strategy = searchParams.get('strategy_id') ?? ''
  const correlation = searchParams.get('correlation_id') ?? ''
  return <OrderLedgerWorkspace key={`${strategy}:${correlation}`} bootstrap={bootstrap} initialStrategyFilter={strategy} initialCorrelationFilter={correlation} />
}

function OrderLedgerWorkspace({ bootstrap, initialStrategyFilter, initialCorrelationFilter }: {
  bootstrap: ConsoleBootstrap; initialStrategyFilter: string; initialCorrelationFilter: string
}) {
  const executionQueue = useQuery({
    queryKey: ['orders', 'execution-queue'],
    queryFn: ({ signal }) => fetchExecutionQueue(signal),
    staleTime: 10_000,
    refetchInterval: 15_000,
    retry: 1,
  })
  const accountExecution = useQuery({
    queryKey: ['orders', 'account-execution-batches'],
    queryFn: ({ signal }) => fetchAccountExecutionBatches(signal),
    staleTime: 10_000,
    refetchInterval: 15_000,
    retry: 1,
  })
  const accountExecutionData = accountExecution.isError ? undefined : accountExecution.data
  const [draft, setDraft] = useState<FilterDraft>({ ...EMPTY_FILTERS, strategy_id: initialStrategyFilter, correlation_id: initialCorrelationFilter })
  const [applied, setApplied] = useState<OrderLedgerFilters>({ limit: PAGE_SIZE, offset: 0, strategy_id: initialStrategyFilter || undefined, correlation_id: initialCorrelationFilter || undefined })
  const [filterError, setFilterError] = useState(initialCorrelationFilter && !UUID_PATTERN.test(initialCorrelationFilter) ? '关联链标识必须是完整 UUID。' : '')
  const [datePreset, setDatePreset] = useState<DatePreset>('all')
  const orders = useQuery({
    queryKey: ['orders', 'ledger', applied],
    queryFn: ({ signal }) => fetchOrders(applied, signal),
    enabled: !applied.correlation_id || UUID_PATTERN.test(applied.correlation_id),
    staleTime: 10_000,
    refetchInterval: 30_000,
    retry: 1,
  })
  const [selected, setSelected] = useState(initialCorrelationFilter)
  const [selectedQueueItemId, setSelectedQueueItemId] = useState('')
  const [selectedQueueTraceCorrelation, setSelectedQueueTraceCorrelation] = useState('')
  useEffect(() => {
    if (applied.correlation_id) {
      setSelected(applied.correlation_id)
      return
    }
    if (!orders.data) return
    if (!orders.data.items.some((item) => item.correlation_id === selected)) {
      setSelected(orders.data.items[0]?.correlation_id ?? '')
    }
  }, [orders.data, selected, applied.correlation_id])
  const requestedTrace = selectedQueueTraceCorrelation || selected
  const traceCorrelation = UUID_PATTERN.test(requestedTrace) ? requestedTrace : ''
  const trace = useQuery({
    queryKey: ['order-trace', traceCorrelation],
    queryFn: ({ signal }) => fetchOrderTrace(traceCorrelation, signal),
    enabled: Boolean(traceCorrelation), staleTime: 10_000, retry: 1,
  })
  const selectedOrder = orders.data?.items.find((item) => item.correlation_id === selected)
  const executionQueueData = executionQueue.isError ? undefined : executionQueue.data
  const queueItems = [...(executionQueueData?.carryover_pending ?? []), ...(executionQueueData?.today_activity ?? [])]
  const knownSymbols = [...new Set([
    ...(bootstrap.overview.active_config?.include_symbols ?? []),
    ...Object.values(bootstrap.overview.active_config?.etf_candidates ?? {}).flat(),
    ...queueItems.map((item) => item.symbol),
    ...(orders.data?.items.map((item) => item.symbol) ?? []),
  ])].sort()
  const knownStrategies = [...new Set([
    ...Object.keys(bootstrap.overview.active_config?.strategy_budgets ?? {}),
    ...queueItems.map((item) => item.strategy_id).filter((value): value is string => Boolean(value)),
    ...(orders.data?.items.map((item) => item.strategy_id).filter((value): value is string => Boolean(value)) ?? []),
  ])].sort()
  const selectedQueueItem = queueItems
    .find((item) => item.queue_item_id === selectedQueueItemId)
  const tracedOrder = orders.data?.items.find((item) => item.correlation_id === traceCorrelation)
  const tracedOrderQueueItem = tracedOrder == null
    ? undefined
    : queueItems.find((item) => item.correlation_id === tracedOrder.correlation_id)
  const tracedQueueItem = queueItems.find((item) => item.correlation_id === traceCorrelation)
  useEffect(() => {
    const items = [...(executionQueueData?.carryover_pending ?? []), ...(executionQueueData?.today_activity ?? [])]
    if (!items.some((item) => item.queue_item_id === selectedQueueItemId)) {
      setSelectedQueueItemId(items[0]?.queue_item_id ?? '')
    }
  }, [executionQueueData, selectedQueueItemId])
  const queueSummary = executionQueueData == null
    ? null
    : summarizeExecutionQueue(executionQueueData)

  const applyFilters = (event: FormEvent) => {
    event.preventDefault()
    const symbol = draft.symbol.trim().toUpperCase()
    const correlationId = draft.correlation_id.trim()
    if (symbol && !SYMBOL_PATTERN.test(symbol)) {
      setFilterError('标的必须使用 510300.SH 或 159915.SZ 格式。')
      return
    }
    if (correlationId && !UUID_PATTERN.test(correlationId)) {
      setFilterError('Correlation ID 必须是完整 UUID。')
      return
    }
    if (draft.created_from && draft.created_to && draft.created_from > draft.created_to) {
      setFilterError('开始日期不能晚于结束日期。')
      return
    }
    setFilterError('')
    setApplied({
      limit: PAGE_SIZE,
      offset: 0,
      symbol: symbol || undefined,
      strategy_id: draft.strategy_id.trim() || undefined,
      status: draft.status || undefined,
      correlation_id: correlationId || undefined,
      created_from: dateBoundary(draft.created_from),
      created_to: dateBoundary(draft.created_to, true),
    })
  }

  const resetFilters = () => {
    setDraft(EMPTY_FILTERS)
    setDatePreset('all')
    setFilterError('')
    setApplied({ limit: PAGE_SIZE, offset: 0 })
  }

  return (
    <section className="workspace-page">
      <header className="page-heading">
        <div><h1>交易记录</h1><p>查询 Bridge 权威委托账本并查看完整决策因果链；页面不提供下单、撤单或实盘操作。</p></div>
        <span className="read-only-stamp"><LockKeyhole size={14} /> 交易只读</span>
      </header>

      <article className="surface-card execution-queue-card">
        <div className="card-heading"><div><span className="eyebrow">Portfolio 权威命令前队列</span><h2>今日订单与待执行</h2></div><span className="read-only-stamp">只读</span></div>
        {executionQueue.isError ? <div className="coverage-gap"><div><strong>执行队列不可用</strong><span>无法确认当前没有待执行事项；Bridge 委托账本仍在下方独立展示。</span></div></div> : null}
        {executionQueueData ? <>
          <div className="queue-summary-grid queue-summary-grid-detailed" aria-label="今日订单阶段汇总">
            <span><small>交易日</small><strong>{queueSummary?.authoritative ? executionQueueData.trading_date : '不可用'}</strong></span>
            <span><small>今日目标事项</small><strong>{queueCountLabel(queueSummary?.todayTotal ?? null)}</strong></span>
            <span><small>待风险复核</small><strong>{queueCountLabel(queueSummary?.riskPending ?? null)}</strong></span>
            <span><small>已批准待命令</small><strong>{queueCountLabel(queueSummary?.approvedPendingCommand ?? null)}</strong></span>
            <span><small>待发送</small><strong>{queueCountLabel(queueSummary?.waitingSend ?? null)}</strong></span>
            <span><small>已提交</small><strong>{queueCountLabel(queueSummary?.submitted ?? null)}</strong></span>
            <span><small>部分成交</small><strong>{queueCountLabel(queueSummary?.partialFill ?? null)}</strong></span>
            <span><small>已完成</small><strong>{queueCountLabel(queueSummary?.completed ?? null)}</strong></span>
            <span><small>已取消</small><strong>{queueCountLabel(queueSummary?.cancelled ?? null)}</strong></span>
            <span><small>已拒绝 / 失败</small><strong>{queueCountLabel(queueSummary?.rejectedOrFailed ?? null)}</strong></span>
            <span><small>跨日未终态</small><strong>{queueCountLabel(queueSummary?.carryoverPending ?? null)}</strong></span>
            <span><small>覆盖状态</small><strong>{queueSummary?.authoritative ? '完整' : '不可用'}</strong></span>
          </div>
          {[...executionQueueData.carryover_pending, ...executionQueueData.today_activity].length ? <div className="execution-queue-list">{[...executionQueueData.carryover_pending, ...executionQueueData.today_activity].map((item) => <button className={`execution-queue-row queue-${item.wait_state === 'blocked' ? 'blocked' : item.stage} ${selectedQueueItemId === item.queue_item_id ? 'execution-queue-row-selected' : ''}`} key={item.queue_item_id} onClick={() => { setSelectedQueueItemId(item.queue_item_id); setSelectedQueueTraceCorrelation('') }} type="button">
            <div><strong>{item.symbol} · {orderSideNames[item.side]}</strong><span>{queueSourceNames[item.identity.source_kind]} · {item.strategy_id ? `${item.strategy_id} @ ${item.strategy_version}` : '无策略归属'}{item.identity.strategy_lineage_id ? ` · lineage ${item.identity.strategy_lineage_id}` : ''}{item.config_version ? ` · 配置 ${item.config_version}` : ''}</span></div>
            <div><strong>{queueStageLabel(item.stage)}</strong><span>风险 {queueFactNames[item.risk_status]} · 审批 {queueFactNames[item.approval_status]} · 命令 {queueFactNames[item.command_status]}</span></div>
            <div><strong>{item.completed_quantity} / {item.target_quantity}</strong><span>{queueIsTerminal(item) ? `结束于 ${absoluteChinaTime(item.last_changed_at)}` : `等待 ${Math.max(0, Math.floor((Date.now() - new Date(item.stage_entered_at).getTime()) / 60000))} 分钟`}</span></div>
            <div><strong>{queueProgressLabel(item)}</strong><span>{item.blocking_issue_codes.map((code) => diagnosticLabel(code)).join('、') || `最近变化 ${absoluteChinaTime(item.last_changed_at)}`}</span><small>{queueDayLabel(item)} · 下一阶段 {item.next_legal_stage ? queueStageLabel(item.next_legal_stage) : '未到达 / 不适用'} · 关联 {item.correlation_id}</small></div>
          </button>)}</div> : queueSummary?.authoritative
            ? <EmptyState title="当前没有队列事项" detail="权威交易日历与队列来源覆盖完整，当前没有命令前待执行或跨日未终态事项。" />
            : <div className="coverage-gap"><div><strong>不能确认当前没有待执行事项</strong><span>交易日历、队列来源或分页覆盖不完整，所有阶段计数保持不可用。</span></div></div>}
          {selectedQueueItem ? <section className="execution-queue-detail" aria-label="待执行事项调用链">
            <header><div><strong>{selectedQueueItem.symbol} · {queueStageLabel(selectedQueueItem.stage)}</strong><span>队列 {selectedQueueItem.queue_item_id} · 关联 {selectedQueueItem.correlation_id}</span><span>lineage {selectedQueueItem.identity.strategy_lineage_id ?? '不适用'} · epoch {selectedQueueItem.identity.genesis_epoch_id ?? '不适用'}</span></div>{selectedQueueItem.strategy_id && selectedQueueItem.strategy_version ? <Link to={`/strategies?strategy=${encodeURIComponent(`${selectedQueueItem.strategy_id}@${selectedQueueItem.strategy_version}`)}${selectedQueueItem.identity.strategy_lineage_id ? `&lineage=${encodeURIComponent(selectedQueueItem.identity.strategy_lineage_id)}` : ''}${selectedQueueItem.identity.genesis_epoch_id ? `&epoch=${encodeURIComponent(selectedQueueItem.identity.genesis_epoch_id)}` : ''}`}>查看策略</Link> : null}</header>
            <div className="queue-call-chain">
              <span><small>来源</small><strong>{queueSourceNames[selectedQueueItem.identity.source_kind]}</strong></span>
              <span><small>意图 / 目标</small><strong>{selectedQueueItem.identity.source_kind === 'automatic_strategy' ? '已绑定权威目标' : queueFactNames.not_applicable}</strong></span>
              <span><small>当前权威阶段</small><strong>{queueStageLabel(selectedQueueItem.stage)}</strong></span>
              {[['风险', selectedQueueItem.risk_status], ['审批', selectedQueueItem.approval_status], ['命令 / 签名', selectedQueueItem.command_status]].map(([label, state]) => <span key={label}><small>{label}</small><strong>{queueFactNames[state] ?? state}</strong></span>)}
            </div>
            <details className="technical-details"><summary>阶段技术详情</summary><code>{selectedQueueItem.stage}</code></details>
            <footer><span>{selectedQueueItem.blocking_issue_codes.length ? selectedQueueItem.blocking_issue_codes.join('、') : '当前无结构化阻断原因'}</span><a href="#order-audit-chain" onClick={() => setSelectedQueueTraceCorrelation(selectedQueueItem.correlation_id)}>查看命令 / QMT / 执行审计链</a><Link to={`/operations?tab=logs&correlation_id=${encodeURIComponent(selectedQueueItem.correlation_id)}`}>查看相关错误日志</Link></footer>
          </section> : null}
        </> : executionQueue.isLoading ? <EmptyState title="正在读取执行队列" detail="正在从 Portfolio 获取策略归属和命令前阶段。" /> : null}
      </article>

      <article className="surface-card account-execution-card">
        <div className="card-heading"><div><span className="eyebrow">Portfolio 账户协调权威事实</span><h2>执行批次、资金分配与预留</h2></div><span className="read-only-stamp">只读</span></div>
        {accountExecution.isError ? <div className="coverage-gap"><div><strong>账户协调投影不可用</strong><span>无法确认资金分配和预留状态；不会从订单数量反推可用资金。</span></div></div> : null}
        {accountExecutionData?.batches.length ? <div className="account-execution-list">{accountExecutionData.batches.map((batch) => <section className="account-execution-batch" key={batch.batch_id}>
          <header><div><strong>{accountBatchStateNames[batch.current_state] ?? batch.current_state}</strong><span>批次 {batch.batch_id.slice(0, 8)}… · 配置 {batch.active_config_version}</span><span>策略 {batch.strategy_ids.length ? batch.strategy_ids.join('、') : batch.strategy_lineages.join('、')}</span></div><time>{absoluteChinaTime(batch.created_at)}</time></header>
          {batch.current_reason_codes.length ? <div className="boundary-reasons">{batch.current_reason_codes.map((reason) => <span key={reason}>{diagnosticLabel(reason)}</span>)}</div> : null}
          <div className="queue-summary-grid">
            <span><small>参与策略</small><strong>{batch.strategy_count}</strong></span>
            <span><small>账户可用现金</small><strong>{money(batch.available_cash_before_reservations)}</strong></span>
            <span><small>预留后现金</small><strong>{money(batch.available_cash_after_reservations)}</strong></span>
            <span><small>持仓市值</small><strong>{money(batch.gross_market_value)}</strong></span>
          </div>
          {batch.allocations.length ? <div className="account-allocation-list">{batch.allocations.map((item) => <div key={item.allocation_decision_id}>
            <span><strong>{item.strategy_id}</strong><small>{item.decision === 'allocated' ? '足额分配' : item.decision === 'partially_allocated' ? '部分分配' : '未分配'}</small></span>
            <span><small>申请</small><strong>{money(item.requested_amount)}</strong></span>
            <span><small>分配</small><strong>{money(item.allocated_amount)}</strong></span>
            <span><small>策略可用</small><strong>{money(item.strategy_spendable_cash)}</strong></span>
          </div>)}</div> : <p className="empty-inline">本批次没有资金分配事实</p>}
          {batch.reservations.length ? <div className="account-reservation-list">{batch.reservations.map((item) => <div key={item.reservation_id}>
            <span><strong>{item.symbol} · {orderSideNames[item.side]}</strong><small>{item.strategy_id}</small></span>
            <span><strong>{reservationStateNames[item.status] ?? item.status}</strong><small>现金 {money(item.cash_reserved)}</small></span>
            <span><strong>保留 {item.still_reserved_quantity}</strong><small>成交待吸收 {item.executed_unabsorbed_quantity} · 已释放 {item.released_quantity}</small></span>
            <time>{absoluteChinaTime(item.last_changed_at)}</time>
          </div>)}</div> : <p className="empty-inline">本批次没有风险预留事实</p>}
        </section>)}</div>
          : accountExecutionData ? <EmptyState title="新协调器上线后尚未形成批次" detail="当前自动执行仍受权威运行条件约束；历史委托继续保留在下方委托账本中，不会被合成为新批次。" />
            : accountExecution.isLoading ? <EmptyState title="正在读取账户执行批次" detail="正在从 Portfolio 获取资金分配和预留事实。" /> : null}
      </article>

      <form className="surface-card order-filter-bar" onSubmit={applyFilters}>
        <label><span>标的</span><input aria-label="订单标的" list="order-symbol-options" onChange={(event) => setDraft((value) => ({ ...value, symbol: event.target.value }))} placeholder="全部标的" value={draft.symbol} /><datalist id="order-symbol-options">{knownSymbols.map((item) => <option key={item} value={item} />)}</datalist></label>
        <label><span>策略</span><input aria-label="订单策略" list="order-strategy-options" onChange={(event) => setDraft((value) => ({ ...value, strategy_id: event.target.value }))} placeholder="全部策略" value={draft.strategy_id} /><datalist id="order-strategy-options">{knownStrategies.map((item) => <option key={item} value={item} />)}</datalist></label>
        <label><span>状态</span><select aria-label="订单状态" onChange={(event) => setDraft((value) => ({ ...value, status: event.target.value as FilterDraft['status'] }))} value={draft.status}><option value="">全部状态</option>{Object.entries(orderStatusNames).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label><span>日期范围</span><select aria-label="订单日期范围" onChange={(event) => {
          const value = event.target.value as DatePreset
          setDatePreset(value)
          setDraft((current) => ({
            ...current,
            created_from: value === 'all' ? '' : value === 'today' ? localDate() : localDate(value === '7d' ? 6 : 29),
            created_to: value === 'all' ? '' : localDate(),
          }))
        }} value={datePreset}><option value="all">全部历史</option><option value="today">今天</option><option value="7d">近 7 天</option><option value="30d">近 30 天</option></select></label>
        <label><span>开始日期</span><input aria-label="订单开始日期" onChange={(event) => setDraft((value) => ({ ...value, created_from: event.target.value }))} type="date" value={draft.created_from} /></label>
        <label><span>结束日期</span><input aria-label="订单结束日期" onChange={(event) => setDraft((value) => ({ ...value, created_to: event.target.value }))} type="date" value={draft.created_to} /></label>
        <details className="order-filter-advanced"><summary>高级筛选</summary><div className="advanced-filter-heading"><span>关联链标识</span><InfoTip label="关联链标识">用于排障时精确定位同一次决策、命令与成交链路。通常无需填写。</InfoTip></div><label className="order-filter-correlation"><span>关联链 UUID</span><input aria-label="订单关联 ID" onChange={(event) => setDraft((value) => ({ ...value, correlation_id: event.target.value }))} placeholder="粘贴完整 UUID" value={draft.correlation_id} /></label></details>
        <div className="order-filter-actions"><button type="submit"><Search size={13} /> 查询</button><button onClick={resetFilters} type="button"><RotateCcw size={13} /> 重置</button></div>
        {filterError ? <p className="order-filter-error" role="alert">{filterError}</p> : null}
      </form>

      <div className="orders-layout">
        <article className="surface-card orders-list-card">
          <div className="card-heading"><div><span className="eyebrow">权威命令记录</span><h2>委托账本</h2></div><div className="order-ledger-count"><strong>{orders.data?.total ?? '—'}</strong><span>匹配记录</span><ReceiptText size={18} /></div></div>
          {orders.data ? <>
            {orders.isError ? <p className="projection-warning projection-warning-muted" role="status">最新订单刷新失败，正在自动重试；下方展示最近一次成功读取的权威账本（{absoluteChinaTime(new Date(orders.dataUpdatedAt).toISOString())}）。</p> : null}
            {orders.data.items.length ? <>
              <div className="order-table">
                <div className="order-table-head"><span>标的 / 方向</span><span>委托 / 成交</span><span>状态 / 均价</span><span>时间</span></div>
                {orders.data.items.map((item) => <button className={selected === item.correlation_id ? 'order-row order-row-active' : 'order-row'} key={item.command_id} onClick={() => { setSelectedQueueTraceCorrelation(''); setSelected(item.correlation_id) }} type="button">
                  <span><strong>{item.symbol}</strong><small>{orderSideNames[item.side]} · {item.strategy_id}</small></span>
                  <span><strong>{item.quantity}</strong><small>{item.execution_detail_available ? `成交 ${item.filled_quantity ?? 0}` : '成交回报不可用'}</small></span>
                  <span><span className={`order-status order-status-${item.status}`}>{orderStatusNames[item.status]}</span><small>{item.trading_session === 'after_hours_fixed_price' ? '盘后固定价格' : item.execution_detail_available ? `均价 ${price(item.average_fill_price)}` : '连续竞价'}</small></span>
                  <span><strong>{absoluteChinaTime(item.created_at)}</strong><small>{item.latest_execution_at ? `回报 ${absoluteChinaTime(item.latest_execution_at)}` : '暂无柜台回报时间'}</small></span>
                </button>)}
              </div>
              <div className="order-pagination"><button aria-label="上一页" disabled={orders.data.offset === 0} onClick={() => setApplied((value) => ({ ...value, offset: Math.max(0, value.offset - value.limit) }))} type="button"><ChevronLeft size={14} /></button><span>{orders.data.offset + 1}–{orders.data.offset + orders.data.items.length} / {orders.data.total}</span><button aria-label="下一页" disabled={!orders.data.has_more} onClick={() => setApplied((value) => ({ ...value, offset: value.offset + value.limit }))} type="button"><ChevronRight size={14} /></button></div>
            </> : <EmptyState title="暂无委托" detail="当前筛选条件下，权威 Bridge 账本没有可展示的命令。" />}
          </> : orders.isError ? <EmptyState title="订单账本不可用" detail="不会回退到模拟状态缓存或伪造订单状态。" />
            : <EmptyState title="正在读取订单账本" detail="正在从 Bridge 获取权威委托与成交状态。" />}
        </article>

        <article className="surface-card order-trace-card" id="order-audit-chain">
          <div className="card-heading"><div><span className="eyebrow">决策证据追踪</span><h2>决策因果链</h2></div><GitBranch size={18} /></div>
          {tracedOrder ? <div className="order-trace-summary">
            <div><span>当前委托</span><strong>{tracedOrder.symbol} · {orderSideNames[tracedOrder.side]} · {orderStatusNames[tracedOrder.status]}</strong></div>
            <div><span>委托数量 / 限价</span><strong>{tracedOrder.quantity} / {price(tracedOrder.limit_price)}</strong></div>
            <div><span>成交数量 / 均价</span><strong>{tracedOrder.execution_detail_available ? `${tracedOrder.filled_quantity ?? 0} / ${price(tracedOrder.average_fill_price)}` : '暂无权威回报明细'}</strong></div>
            <div><span>QMT 柜台委托号</span><code>{tracedOrder.broker_order_id ?? '尚未返回'}</code></div>
            <div><span>最近柜台回报</span><strong>{tracedOrder.latest_execution_at ? absoluteChinaTime(tracedOrder.latest_execution_at) : '尚未返回'}</strong></div>
            <div><span>关联链标识</span><code>{tracedOrder.correlation_id}</code></div>
            <div><span>策略归属</span><strong>{tracedOrderQueueItem?.strategy_version
              ? <Link to={`/strategies?strategy=${encodeURIComponent(`${tracedOrder.strategy_id}@${tracedOrderQueueItem.strategy_version}`)}${tracedOrderQueueItem.identity.strategy_lineage_id ? `&lineage=${encodeURIComponent(tracedOrderQueueItem.identity.strategy_lineage_id)}` : ''}${tracedOrderQueueItem.identity.genesis_epoch_id ? `&epoch=${encodeURIComponent(tracedOrderQueueItem.identity.genesis_epoch_id)}` : ''}`}>{tracedOrder.strategy_id} @ {tracedOrderQueueItem.strategy_version}</Link>
              : tracedOrder.strategy_id}</strong></div>
            <div><span>命令前队列</span><strong>{tracedOrderQueueItem ? `${queueStageLabel(tracedOrderQueueItem.stage)} · ${tracedOrderQueueItem.queue_item_id}` : '当前队列窗口未找到与本委托关联的事项；已形成命令不等于异常'}</strong></div>
            {tracedOrder.rejection_reason ? <div className="order-rejection-reason"><span>拒单 / 失败原因</span><strong>{orderFailureReasonLabel(tracedOrder.rejection_reason)}</strong></div> : null}
          </div> : null}
          {!tracedOrder && tracedQueueItem ? <div className="order-trace-summary"><div><span>当前队列事项</span><strong>{tracedQueueItem.symbol} · {queueStageLabel(tracedQueueItem.stage)}</strong></div><div><span>关联链标识</span><code>{traceCorrelation}</code></div><div><span>命令 / QMT 状态</span><strong>{queueFactNames[tracedQueueItem.command_status] ?? tracedQueueItem.command_status}</strong></div><div><span>权威边界</span><strong>尚未形成当前账本页可见的 Bridge 委托时，后续阶段保持不可用</strong></div></div> : null}
          {trace.data ? <>
            {trace.isError ? <p className="projection-warning projection-warning-muted" role="status">最新因果链刷新失败，正在自动重试；下方展示最近一次成功读取的审计事实（{absoluteChinaTime(new Date(trace.dataUpdatedAt).toISOString())}）。</p> : null}
            <div className="order-trace-verdict"><strong>{trace.data.complete ? '六阶段证据完整' : '因果证据尚不完整'}</strong><span>{trace.data.complete ? '所有阶段均来自不可变审计事实。' : '缺失阶段明确标记不可用，不以相邻状态补全。'}</span></div><div className="order-causal-list">{trace.data.stages.map((stage) => <div className={`order-causal-stage order-causal-${stage.status}`} key={stage.stage}>
              <span className="order-causal-dot" /><div><strong>{orderStageNames[stage.stage]}</strong><small>{stage.summary}</small>{stage.occurred_at ? <time>{absoluteChinaTime(stage.occurred_at)}</time> : null}{stage.evidence_ref_count ? <em>{stage.evidence_ref_count} 条证据引用</em> : null}</div>
            </div>)}</div></>
            : trace.isError ? <EmptyState title="因果链不可用" detail="审计事件缺失时保持不可用，不推测链路。" />
              : traceCorrelation ? <EmptyState title="正在读取因果链" detail="正在从 Audit 获取策略到成交的不可变证据。" />
                : <EmptyState title="请选择委托" detail="选择左侧委托后查看策略到成交的完整证据链。" />}
        </article>
      </div>

    </section>
  )
}
