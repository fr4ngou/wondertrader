import { CAPITAL_HISTORY_DEFAULT_DAYS, CAPITAL_HISTORY_MAX_DAYS, capitalDisplayNumber } from './strategyReturnPresentation'
import type {
  AccountExecutionProjection,
  BacktestTradeLedgerPage,
  BacktestPerformanceReport,
  AuditEventFilters,
  AuditEventPage,
  ConsoleBootstrap,
  ConsoleOverview,
  ExecutionQueueProjection,
  MarketChartBundle,
  MarketChartPeriod,
  MarketDataSubscriptionProjection,
  MarketQuoteProjection,
  PublicObservationProjection,
  MarketSymbolSuggestionPage,
  OrderExecutionTrace,
  OrderLedgerFilters,
  OrderLedgerPage,
  OrderSummary,
  OperationsWorkbenchProjection,
  OperationalLogQueryPage,
  PerformanceReport,
  PortfolioPnLSnapshot,
  PortfolioPositionsSnapshot,
  PortfolioPerformanceSeries,
  ProblemDefinition,
  ProblemDictionary,
  QMTConnectionStatus,
  StrategyRegistrySnapshot,
  StrategyEligibilityProjection,
  StrategyRuntimeState,
  StrategyWorkbenchDetail,
  Watchlist,
  WatchlistMutationRequest,
  WatchlistMutationResult,
} from './types'

import type { ReplenishmentProjection } from './replenishment'

export const BOOTSTRAP_QUERY_KEY = ['ui-bootstrap'] as const
export const OVERVIEW_QUERY_KEY = ['console-overview'] as const
export const WATCHLIST_QUERY_KEY = ['watchlist', 'default'] as const
export const QMT_CONNECTION_QUERY_KEY = ['qmt-connection-status'] as const

// 默认交互读取使用有限截止；独立行情页按服务端能力声明的预算读取，
// 另留传输时间，避免浏览器提前中止仍在正常执行的来源历史查询。
export const INTERACTIVE_STATUS_TIMEOUT_MS = 6_500
export const DEFERRED_OVERVIEW_TIMEOUT_MS = 20_000
export const AUDIT_TRACE_TIMEOUT_MS = DEFERRED_OVERVIEW_TIMEOUT_MS

type ScheduledRead = {
  sequence: number
  signal?: AbortSignal
  started: boolean
  settled: boolean
  start: (remainingMs: number) => Promise<Response>
  expiresAt: number
  timeoutMessage: string
  queueTimer: ReturnType<typeof setTimeout>
  resolve: (response: Response) => void
  reject: (reason?: unknown) => void
  abortQueued: () => void
}

type ReadLaneName = 'status' | 'overview' | 'workspace' | 'audit'

// 排队和传输共享同一截止类型，公开投影边界据此区分超时与连接失败。
class ReadDeadlineError extends Error {}
class ReadCapacityError extends Error {
  constructor() { super('读取请求较多，请稍后重试'); this.name = 'ReadCapacityError' }
}

/** 保留HTTP状态供业务边界解释；正文仍不进入公开错误。 */
export class ReadHttpError extends Error {
  constructor(readonly status: number, context: string) {
    super(`${context}读取失败（HTTP ${status}），请稍后重试`)
    this.name = 'ReadHttpError'
  }
}

type ReadLane = {
  active: number
  limit: number
  queue: ScheduledRead[]
}

// Browsers expose only a small per-origin connection pool. Keep two slots reserved
// for status and audit evidence, and share the remaining two between Overview and
// workspace projections. Without the aggregate cap, four workspace reads plus the
// shell and SSE can prevent a newly selected order trace from reaching Console at
// all, even though every logical lane has its own queue.
const MAX_ACTIVE_READS = 4
const MAX_BACKGROUND_READS = 2
// 每条读取通道独立保留32个等待名额，工作区满额不占用状态/审计的等待容量。
export const MAX_QUEUED_READS_PER_LANE = 32
const READ_LANE_PRIORITY: ReadLaneName[] = ['status', 'audit', 'workspace', 'overview']
const scheduledReadLanes: Record<ReadLaneName, ReadLane> = {
  status: { active: 0, limit: 1, queue: [] },
  overview: { active: 0, limit: 1, queue: [] },
  workspace: { active: 0, limit: 2, queue: [] },
  audit: { active: 0, limit: 1, queue: [] },
}
let scheduledReadSequence = 0

function abortError(signal: AbortSignal): unknown {
  return signal.reason ?? new DOMException('The operation was aborted.', 'AbortError')
}

function activeReadCount(): number {
  return Object.values(scheduledReadLanes).reduce((total, lane) => total + lane.active, 0)
}

function activeBackgroundReadCount(): number {
  return scheduledReadLanes.workspace.active + scheduledReadLanes.overview.active
}

function canStartRead(laneName: ReadLaneName): boolean {
  const lane = scheduledReadLanes[laneName]
  if (lane.active >= lane.limit || lane.queue.length === 0 || activeReadCount() >= MAX_ACTIVE_READS) {
    return false
  }
  return (laneName !== 'workspace' && laneName !== 'overview')
    || activeBackgroundReadCount() < MAX_BACKGROUND_READS
}

function runScheduledReads(): void {
  while (true) {
    const laneName = READ_LANE_PRIORITY.find(canStartRead)
    if (laneName == null) return
    const lane = scheduledReadLanes[laneName]
    const next = lane.queue.shift()
    if (next == null) continue
    clearTimeout(next.queueTimer)
    if (next.settled) continue
    if (next.signal?.aborted) {
      next.settled = true
      next.reject(abortError(next.signal))
      continue
    }
    const remainingMs = next.expiresAt - Date.now()
    if (remainingMs <= 0) {
      next.settled = true
      next.signal?.removeEventListener('abort', next.abortQueued)
      // 完成回调可能先于队列timer运行；同步发现逾期同样属于读取截止。
      next.reject(new ReadDeadlineError(next.timeoutMessage))
      continue
    }
    lane.active += 1
    next.started = true
    void next.start(remainingMs).then(
      (response) => {
        lane.active -= 1
        next.signal?.removeEventListener('abort', next.abortQueued)
        if (!next.settled) {
          next.settled = true
          next.resolve(response)
        }
        runScheduledReads()
      },
      (reason) => {
        lane.active -= 1
        next.signal?.removeEventListener('abort', next.abortQueued)
        if (!next.settled) {
          next.settled = true
          next.reject(reason)
        }
        runScheduledReads()
      },
    )
  }
}

function scheduleRead(
  start: (remainingMs: number) => Promise<Response>,
  signal: AbortSignal | undefined,
  laneName: ReadLaneName,
  timeoutMs: number,
  timeoutMessage: string,
): Promise<Response> {
  if (signal?.aborted) return Promise.reject(abortError(signal))
  if (scheduledReadLanes[laneName].queue.length >= MAX_QUEUED_READS_PER_LANE) {
    return Promise.reject(new ReadCapacityError())
  }
  return new Promise<Response>((resolve, reject) => {
    const scheduled: ScheduledRead = {
      sequence: scheduledReadSequence++,
      signal,
      started: false,
      settled: false,
      start,
      expiresAt: Date.now() + timeoutMs,
      timeoutMessage,
      queueTimer: undefined as unknown as ReturnType<typeof setTimeout>,
      resolve,
      reject,
      abortQueued: () => {
        if (scheduled.settled || scheduled.started) return
        scheduled.settled = true
        clearTimeout(scheduled.queueTimer)
        const lane = scheduledReadLanes[laneName]
        const index = lane.queue.indexOf(scheduled)
        if (index >= 0) lane.queue.splice(index, 1)
        reject(signal == null ? undefined : abortError(signal))
      },
    }
    // The deadline begins when the user requests the projection. A busy lane
    // cannot defer this timer or turn a queued read into an infinite spinner.
    scheduled.queueTimer = setTimeout(() => {
      if (scheduled.settled || scheduled.started) return
      scheduled.settled = true
      const lane = scheduledReadLanes[laneName]
      const index = lane.queue.indexOf(scheduled)
      if (index >= 0) lane.queue.splice(index, 1)
      signal?.removeEventListener('abort', scheduled.abortQueued)
      reject(new ReadDeadlineError(timeoutMessage))
      runScheduledReads()
    }, timeoutMs)
    signal?.addEventListener('abort', scheduled.abortQueued, { once: true })
    const lane = scheduledReadLanes[laneName]
    lane.queue.push(scheduled)
    lane.queue.sort((left, right) => left.sequence - right.sequence)
    runScheduledReads()
  })
}

async function fetchWithDeadline(
  input: RequestInfo | URL,
  init: RequestInit,
  timeoutMs: number,
  timeoutMessage: string,
): Promise<Response> {
  const controller = new AbortController()
  let deadlineExpired = false
  const parentSignal = init.signal
  const abortFromParent = () => controller.abort(parentSignal?.reason)

  if (parentSignal?.aborted) {
    abortFromParent()
  } else {
    parentSignal?.addEventListener('abort', abortFromParent, { once: true })
  }
  const timer = window.setTimeout(() => {
    deadlineExpired = true
    controller.abort()
  }, timeoutMs)

  try {
    const response = await fetch(input, { ...init, signal: controller.signal })
    if (typeof response.arrayBuffer !== 'function') return response
    const body = await response.arrayBuffer()
    return new Response(body.byteLength === 0 ? null : body, {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    })
  } catch (error) {
    if (deadlineExpired) throw new ReadDeadlineError(timeoutMessage)
    throw error
  } finally {
    window.clearTimeout(timer)
    parentSignal?.removeEventListener('abort', abortFromParent)
  }
}

async function fetchReadProjection(
  input: RequestInfo | URL,
  signal: AbortSignal | undefined,
  timeoutMessage: string,
  timeoutMs = INTERACTIVE_STATUS_TIMEOUT_MS,
  laneName: ReadLaneName = 'workspace',
): Promise<Response> {
  return scheduleRead((remainingMs) => fetchWithDeadline(input, {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
    signal,
  }, remainingMs, timeoutMessage), signal, laneName, timeoutMs, timeoutMessage)
}

/** 新入口统一读取JSON投影；保留读取调度预算，并在边界去除底层英文、地址与原始内容。 */
export async function fetchReadJson<T>(
  input: RequestInfo | URL,
  context: string,
  signal?: AbortSignal,
  laneName: ReadLaneName = 'workspace',
  timeoutMs = INTERACTIVE_STATUS_TIMEOUT_MS,
): Promise<T> {
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0 || timeoutMs > 60_000) {
    throw new Error(`${context}读取预算无效，请检查应用连接配置`)
  }
  let response: Response
  try {
    response = await fetchReadProjection(input, signal, `${context}读取超时`, timeoutMs, laneName)
  } catch (error) {
    // 路由卸载等调用者取消仍交由Query管理，不能变成一次用户可见的连接故障。
    if (signal?.aborted) throw error
    if (error instanceof ReadDeadlineError) throw new Error(`${context}读取超时，请稍后重试`)
    if (error instanceof ReadCapacityError) throw new Error(`${context}读取请求较多，请稍后重试`)
    throw new Error(`${context}连接失败，请检查本机观衡服务后重试`)
  }
  if (!response.ok) throw new ReadHttpError(response.status, context)
  try {
    return await response.json() as T
  } catch (error) {
    if (signal?.aborted) throw error
    throw new Error(`${context}数据格式无效，请稍后重试`)
  }
}

async function fetchPriorityRead(
  input: RequestInfo | URL,
  init: RequestInit,
  timeoutMs: number,
  timeoutMessage: string,
): Promise<Response> {
  return scheduleRead(
    (remainingMs) => fetchWithDeadline(input, init, remainingMs, timeoutMessage),
    init.signal ?? undefined,
    'status',
    timeoutMs,
    timeoutMessage,
  )
}

async function responseError(response: Response, fallback: string): Promise<Error> {
  try {
    const payload = await response.json() as { detail?: string }
    return new Error(typeof payload.detail === 'string' ? payload.detail : fallback)
  } catch {
    return new Error(fallback)
  }
}

export async function fetchBootstrap(signal?: AbortSignal): Promise<ConsoleBootstrap> {
  const response = await fetchReadProjection(
    '/v1/ui/bootstrap', signal, '工作台初始化读取超时',
  )
  if (!response.ok) {
    throw new Error(`工作台初始化失败（HTTP ${response.status}）`)
  }
  return response.json() as Promise<ConsoleBootstrap>
}

export async function fetchOverview(signal?: AbortSignal): Promise<ConsoleOverview> {
  const response = await fetchReadProjection(
    '/v1/console/overview', signal, '工作台详细投影读取超时',
    DEFERRED_OVERVIEW_TIMEOUT_MS, 'overview',
  )
  if (!response.ok) {
    throw new Error(`工作台详细投影读取失败（HTTP ${response.status}）`)
  }
  return response.json() as Promise<ConsoleOverview>
}

export async function fetchQmtConnectionStatus(
  signal?: AbortSignal,
  timeoutMs = INTERACTIVE_STATUS_TIMEOUT_MS,
): Promise<QMTConnectionStatus> {
  const response = await fetchPriorityRead('/v1/ui/qmt/connection-status', {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
    signal,
  }, timeoutMs, 'QMT 连接状态读取超时')
  if (!response.ok) {
    throw await responseError(response, `QMT 连接状态读取失败（HTTP ${response.status}）`)
  }
  return response.json() as Promise<QMTConnectionStatus>
}

export async function fetchOperationsWorkbench(
  signal?: AbortSignal,
  limit = 50,
): Promise<OperationsWorkbenchProjection> {
  const response = await fetchReadProjection(
    `/v1/ui/operations/workbench?limit=${limit}`, signal, '运维权威投影读取超时',
  )
  if (!response.ok) {
    throw await responseError(response, `运维权威投影读取失败（HTTP ${response.status}）`)
  }
  return response.json() as Promise<OperationsWorkbenchProjection>
}

export async function fetchOperationalErrorLogs(
  signal?: AbortSignal,
): Promise<OperationalLogQueryPage> {
  const params = new URLSearchParams()
  params.append('severities', 'critical')
  params.append('severities', 'error')
  params.set('limit', '100')
  const response = await fetchReadProjection(
    `/v1/ui/operations/error-logs?${params}`, signal, '错误日志读取超时',
  )
  if (!response.ok) {
    throw await responseError(response, `错误日志读取失败（HTTP ${response.status}）`)
  }
  return response.json() as Promise<OperationalLogQueryPage>
}

export async function fetchExecutionQueue(
  signal?: AbortSignal,
): Promise<ExecutionQueueProjection> {
  const maximumQueueItems = 50_000
  for (let restart = 0; restart < 2; restart += 1) {
    let revision: number | undefined
    let cursor: string | undefined
    let combined: ExecutionQueueProjection | undefined
    const seenCursors = new Set<string>()
    let restartRequired = false
    while (true) {
      const params = new URLSearchParams({ limit: '200' })
      if (revision != null && cursor) {
        params.set('projection_revision', String(revision))
        params.set('cursor', cursor)
      }
      const response = await fetchReadProjection(
        `/v1/ui/orders/execution-queue?${params}`,
        signal,
        '待执行队列读取超时',
      )
      if (response.status === 409 && restart === 0) {
        restartRequired = true
        break
      }
      if (!response.ok) {
        throw await responseError(response, `待执行队列读取失败（HTTP ${response.status}）`)
      }
      const page = await response.json() as ExecutionQueueProjection
      if (combined == null) {
        combined = page
        revision = page.projection_revision
      } else {
        combined = {
          ...combined,
          today_activity: [...combined.today_activity, ...page.today_activity],
          carryover_pending: [...combined.carryover_pending, ...page.carryover_pending],
          source_coverage: page.source_coverage,
          truncated: page.truncated,
          next_cursor: page.next_cursor,
        }
      }
      if (!page.truncated || !page.next_cursor) {
        return { ...combined, truncated: false, next_cursor: null }
      }
      const itemCount = combined.today_activity.length + combined.carryover_pending.length
      if (itemCount > maximumQueueItems) {
        throw new Error(`待执行队列超过浏览器安全容量（${maximumQueueItems} 项），请缩小服务端投影范围。`)
      }
      if (seenCursors.has(page.next_cursor)) {
        throw new Error('待执行队列返回了重复游标，已停止读取以避免循环。')
      }
      seenCursors.add(page.next_cursor)
      cursor = page.next_cursor
    }
    if (!restartRequired) break
  }
  throw new Error('待执行队列在分页期间持续变化，请稍后重试。')
}

export async function fetchAccountExecutionBatches(
  signal?: AbortSignal,
): Promise<AccountExecutionProjection> {
  const response = await fetchReadProjection(
    '/v1/ui/orders/account-execution-batches?limit=20', signal, '账户执行批次读取超时',
  )
  if (!response.ok) {
    throw await responseError(response, `账户执行批次读取失败（HTTP ${response.status}）`)
  }
  return response.json() as Promise<AccountExecutionProjection>
}

export async function fetchMarketChart(
  symbol: string,
  period: MarketChartPeriod,
  benchmarkSymbol?: string,
  signal?: AbortSignal,
  limit = 2000,
  before?: string,
  timeoutMs = INTERACTIVE_STATUS_TIMEOUT_MS,
): Promise<MarketChartBundle> {
  const params = new URLSearchParams({ period, limit: String(limit) })
  if (before) params.set('before', before)
  if (benchmarkSymbol && benchmarkSymbol !== symbol) {
    params.set('benchmark_symbol', benchmarkSymbol)
  }
  const bundle = await fetchReadJson<MarketChartBundle>(
    `/v1/ui/market/chart/${encodeURIComponent(symbol)}?${params}`,
    '行情图表',
    signal,
    'workspace',
    timeoutMs,
  )
  // 原生失败投影没有来源metadata；真实成功空查询仍携带metadata。
  // 将业务不可用归入读取错误，React Query保留同条件上次成功值。
  if (bundle.source_kind === 'wondertrader' && !bundle.data_available && bundle.native_source == null) {
    throw new Error(bundle.missing_reason || '行情暂时无法更新，请稍后重试')
  }
  return bundle
}

export async function fetchMarketQuote(
  symbol: string,
  signal?: AbortSignal,
): Promise<MarketQuoteProjection> {
  const response = await fetchReadProjection(
    `/v1/ui/market/quote/${encodeURIComponent(symbol)}`,
    signal,
    '实时行情读取超时',
  )
  if (!response.ok) {
    throw new Error(`实时行情读取失败（HTTP ${response.status}）`)
  }
  return response.json() as Promise<MarketQuoteProjection>
}

export async function fetchPublicObservation(
  symbol: string,
  period: MarketChartPeriod,
  signal?: AbortSignal,
): Promise<PublicObservationProjection> {
  const response = await fetchReadProjection(
    `/v1/ui/market/public-observation/${encodeURIComponent(symbol)}?period=${period}&limit=240`,
    signal,
    '个人观察公开行情读取超时',
  )
  if (!response.ok) throw new Error(`个人观察公开行情读取失败（HTTP ${response.status}）`)
  return response.json() as Promise<PublicObservationProjection>
}

export async function fetchMarketDataSubscriptions(
  signal?: AbortSignal,
): Promise<MarketDataSubscriptionProjection> {
  const response = await fetchReadProjection(
    '/v1/ui/market/subscriptions', signal, '动态行情订阅状态读取超时',
  )
  if (!response.ok) {
    throw new Error(`动态行情订阅状态读取失败（HTTP ${response.status}）`)
  }
  return response.json() as Promise<MarketDataSubscriptionProjection>
}

export async function fetchPortfolioPnl(signal?: AbortSignal): Promise<PortfolioPnLSnapshot> {
  const response = await fetchReadProjection(
    '/v1/ui/portfolio/pnl', signal, '组合估值读取超时',
  )
  if (!response.ok) {
    throw new Error(`组合估值读取失败（HTTP ${response.status}）`)
  }
  return response.json() as Promise<PortfolioPnLSnapshot>
}

export async function fetchReplenishment(signal?: AbortSignal): Promise<ReplenishmentProjection> {
  const response = await fetchReadProjection(
    '/v1/ui/portfolio/replenishment', signal, '补单进度读取超时',
  )
  if (!response.ok) throw new Error(`补单进度读取失败（HTTP ${response.status}）`)
  const data = await response.json() as ReplenishmentProjection
  if (!Array.isArray(data.items)) throw new Error('补单进度返回格式无法识别')
  return data
}

export async function fetchPortfolioPositions(
  signal?: AbortSignal,
): Promise<PortfolioPositionsSnapshot> {
  const response = await fetchReadProjection(
    '/v1/ui/portfolio/positions', signal, '持仓投影读取超时',
  )
  if (!response.ok) throw new Error(`持仓投影读取失败（HTTP ${response.status}）`)
  return response.json() as Promise<PortfolioPositionsSnapshot>
}

export async function fetchPortfolioPerformance(
  signal?: AbortSignal,
): Promise<PortfolioPerformanceSeries> {
  const response = await fetchReadProjection(
    '/v1/ui/portfolio/performance?days=30&max_points=480',
    signal,
    '组合收益序列读取超时',
  )
  if (!response.ok) throw new Error(`组合收益序列读取失败（HTTP ${response.status}）`)
  return response.json() as Promise<PortfolioPerformanceSeries>
}

export async function fetchStrategyRegistry(signal?: AbortSignal): Promise<StrategyRegistrySnapshot> {
  const response = await fetchReadProjection(
    '/v1/ui/strategies/registry', signal, '策略注册表读取超时',
  )
  if (!response.ok) {
    throw new Error(`策略注册表读取失败（HTTP ${response.status}）`)
  }
  return response.json() as Promise<StrategyRegistrySnapshot>
}

export async function fetchStrategyRuntime(signal?: AbortSignal): Promise<StrategyRuntimeState[]> {
  const response = await fetchReadProjection(
    '/v1/ui/strategies/runtime', signal, '策略运行状态读取超时',
  )
  if (!response.ok) {
    throw new Error(`策略运行状态读取失败（HTTP ${response.status}）`)
  }
  return response.json() as Promise<StrategyRuntimeState[]>
}

export async function fetchStrategyEligibility(
  signal?: AbortSignal,
): Promise<StrategyEligibilityProjection> {
  const response = await fetchReadProjection(
    '/v1/ui/strategies/eligibility', signal, '策略资格矩阵读取超时',
  )
  if (!response.ok) {
    throw await responseError(response, `策略资格矩阵读取失败（HTTP ${response.status}）`)
  }
  return response.json() as Promise<StrategyEligibilityProjection>
}

export async function fetchStrategyWorkbenchDetail(
  strategyId: string,
  strategyVersion: string,
  signal?: AbortSignal,
): Promise<StrategyWorkbenchDetail> {
  const response = await fetchReadProjection(
    `/v1/ui/strategies/${encodeURIComponent(strategyId)}/versions/${encodeURIComponent(strategyVersion)}`,
    signal,
    '策略详情读取超时',
    DEFERRED_OVERVIEW_TIMEOUT_MS,
  )
  if (!response.ok) {
    throw new Error(`策略详情读取失败（HTTP ${response.status}）`)
  }
  const data = await response.json() as StrategyWorkbenchDetail
  if (data.strategy?.strategy_id !== strategyId || data.strategy?.strategy_version !== strategyVersion || !data.errors || !data.configured_parameters || !Array.isArray(data.performance_reports)) throw new Error('策略详情身份或格式不匹配')
  return data
}

export async function fetchRecentOrders(signal?: AbortSignal): Promise<OrderSummary[]> {
  const response = await fetchReadProjection(
    '/v1/ui/orders/recent', signal, '最近订单账本读取超时',
  )
  if (!response.ok) throw new Error(`订单账本读取失败（HTTP ${response.status}）`)
  return response.json() as Promise<OrderSummary[]>
}

export async function fetchOrders(
  filters: OrderLedgerFilters,
  signal?: AbortSignal,
): Promise<OrderLedgerPage> {
  const params = new URLSearchParams({
    limit: String(filters.limit),
    offset: String(filters.offset),
  })
  for (const [key, value] of Object.entries(filters)) {
    if (key !== 'limit' && key !== 'offset' && value) params.set(key, String(value))
  }
  const response = await fetchReadProjection(
    `/v1/ui/orders?${params}`, signal, '订单账本读取超时',
  )
  if (!response.ok) throw new Error(`订单账本读取失败（HTTP ${response.status}）`)
  return response.json() as Promise<OrderLedgerPage>
}

export async function fetchOrderTrace(
  correlationId: string,
  signal?: AbortSignal,
): Promise<OrderExecutionTrace> {
  const response = await fetchReadProjection(
    `/v1/ui/orders/${encodeURIComponent(correlationId)}/trace`,
    signal,
    '订单因果链读取超时',
    AUDIT_TRACE_TIMEOUT_MS,
    'audit',
  )
  if (!response.ok) throw new Error(`订单因果链读取失败（HTTP ${response.status}）`)
  return response.json() as Promise<OrderExecutionTrace>
}

export async function fetchAuditEvents(
  filters: AuditEventFilters,
  signal?: AbortSignal,
): Promise<AuditEventPage> {
  const params = new URLSearchParams({
    limit: String(filters.limit),
    offset: String(filters.offset),
  })
  for (const [key, value] of Object.entries(filters)) {
    if (key !== 'limit' && key !== 'offset' && value) params.set(key, String(value))
  }
  const response = await fetchReadProjection(
    `/v1/ui/audit/events?${params}`, signal, '审计事件账本读取超时',
  )
  if (!response.ok) {
    throw await responseError(response, `审计事件账本读取失败（HTTP ${response.status}）`)
  }
  return response.json() as Promise<AuditEventPage>
}

export async function fetchBacktestReports(signal?: AbortSignal): Promise<PerformanceReport[]> {
  const response = await fetchReadProjection(
    '/v1/ui/backtests/reports?limit=20', signal, '回测报告列表读取超时',
  )
  if (!response.ok) throw new Error(`回测报告列表读取失败（HTTP ${response.status}）`)
  return response.json() as Promise<PerformanceReport[]>
}

export async function fetchBacktestReport(
  reportHash: string,
  signal?: AbortSignal,
): Promise<BacktestPerformanceReport> {
  const response = await fetchReadProjection(
    `/v1/ui/backtests/reports/${encodeURIComponent(reportHash)}`,
    signal,
    '回测报告读取超时',
  )
  if (!response.ok) throw new Error(`回测报告读取失败（HTTP ${response.status}）`)
  const data = await response.json() as BacktestPerformanceReport
  if (data.report_hash !== reportHash) throw new Error('回测报告身份不匹配')
  return data
}

export async function fetchBacktestTrades(
  reportHash: string,
  limit = 100,
  offset = 0,
  symbol = '',
  signal?: AbortSignal,
): Promise<BacktestTradeLedgerPage> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (symbol) params.set('symbol', symbol)
  const response = await fetchReadProjection(
    `/v1/ui/backtests/reports/${encodeURIComponent(reportHash)}/trades?${params}`,
    signal,
    '回测成交明细读取超时',
  )
  if (!response.ok) throw await responseError(response, `回测成交明细读取失败（HTTP ${response.status}）`)
  const data = await response.json() as BacktestTradeLedgerPage
  if (data.report_hash !== reportHash || !Array.isArray(data.items)) throw new Error('回测成交身份或格式不匹配')
  return data
}

export async function fetchDefaultWatchlist(signal?: AbortSignal): Promise<Watchlist> {
  const response = await fetchReadProjection(
    '/v1/ui/watchlists/default', signal, '自选列表读取超时',
  )
  if (!response.ok) throw await responseError(response, `自选列表读取失败（HTTP ${response.status}）`)
  return response.json() as Promise<Watchlist>
}

export async function fetchProblemDefinitions(signal?: AbortSignal): Promise<ProblemDefinition[]> {
  const response = await fetchReadProjection(
    '/v1/ui/problem-definitions', signal, '中文问题词典读取超时',
  )
  if (!response.ok) throw await responseError(response, `中文问题词典读取失败（HTTP ${response.status}）`)
  return response.json() as Promise<ProblemDefinition[]>
}

export async function fetchProblemDictionary(signal?: AbortSignal): Promise<ProblemDictionary> {
  const response = await fetchReadProjection(
    '/v1/ui/problem-dictionary', signal, '统一中文问题词典读取超时',
  )
  if (!response.ok) throw await responseError(response, `统一中文问题词典读取失败（HTTP ${response.status}）`)
  return response.json() as Promise<ProblemDictionary>
}

export async function fetchMarketSymbolSuggestions(
  query: string,
  signal?: AbortSignal,
): Promise<MarketSymbolSuggestionPage> {
  const params = new URLSearchParams({ query, limit: '20' })
  const response = await fetchReadProjection(
    `/v1/ui/market/suggestions?${params}`,
    signal,
    '标的搜索超时',
  )
  if (!response.ok) throw await responseError(response, `标的搜索失败（HTTP ${response.status}）`)
  return response.json() as Promise<MarketSymbolSuggestionPage>
}

export async function updateDefaultWatchlist(
  payload: WatchlistMutationRequest,
): Promise<WatchlistMutationResult> {
  const response = await fetch('/v1/ui/watchlists/default', {
    method: 'PUT',
    credentials: 'same-origin',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    throw await responseError(
      response,
      response.status === 409
        ? '观察列表已在其他页面更新，请刷新后重试。'
        : `观察列表更新失败（HTTP ${response.status}）`,
    )
  }
  return response.json() as Promise<WatchlistMutationResult>
}

export async function fetchStrategyCapitalHistory(strategyId: string, lineage: string, epoch: string, signal?: AbortSignal,
  options: { sampling?: 'snapshots' | 'daily'; days?: number } = {}): Promise<import('./types').StrategyCapitalHistory> {
  const sampling = options.sampling ?? 'snapshots'
  const days = options.days ?? CAPITAL_HISTORY_DEFAULT_DAYS
  if (!['snapshots', 'daily'].includes(sampling) || !Number.isInteger(days) || days < 1 || days > CAPITAL_HISTORY_MAX_DAYS) throw new Error('策略历史估值采样参数无效')
  const params = new URLSearchParams({ strategy_lineage_id: lineage, genesis_epoch_id: epoch, sampling, days: String(days) })
  const response = await fetchReadProjection(`/v1/ui/strategies/${encodeURIComponent(strategyId)}/capital-history?${params}`, signal, '策略历史估值读取超时')
  if (!response.ok) throw new Error(`策略历史估值读取失败（HTTP ${response.status}）`)
  const data = await response.json() as import('./types').StrategyCapitalHistory
  if (data.schema_version !== 'strategy-capital-history-v1' || data.read_only !== true || data.source_kind !== 'strategy_capital_snapshots' || data.calculation_method !== 'return-on-contributed-principal-v1' || data.strategy_id !== strategyId || data.strategy_lineage_id !== lineage || data.genesis_epoch_id !== epoch || !Array.isArray(data.points)) throw new Error('策略历史估值身份或格式不匹配')
  if ((data.sampling ?? 'snapshots') !== sampling) throw new Error('策略历史估值采样身份或格式不匹配')
  const instant = (value: unknown) => typeof value === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) && Number.isFinite(Date.parse(value))
  if ((data.window_start != null && !instant(data.window_start)) || (data.window_end != null && !instant(data.window_end))
    || (data.window_start && data.window_end && Date.parse(data.window_end) <= Date.parse(data.window_start))) throw new Error('策略历史估值窗口格式不匹配')
  const points = data.points.map(point => {
    if (!point || typeof point !== 'object' || !instant(point.captured_at) || !instant(point.valuation_at) || !['ready', 'blocked'].includes(point.status)) throw new Error('策略历史估值点格式不匹配')
    const values = Object.fromEntries((['net_asset_value', 'contributed_principal', 'capital_contributions_total', 'investment_pnl', 'return_on_principal', 'drawdown'] as const).map(name => {
      if ((name === 'return_on_principal' || name === 'drawdown') && point[name] === null) return [name, null]
      const number = capitalDisplayNumber(point[name])
      if (number === null) throw new Error('策略历史估值数值格式不匹配')
      return [name, number]
    }))
    return { ...point, ...values }
  })
  return { ...data, points }
}
