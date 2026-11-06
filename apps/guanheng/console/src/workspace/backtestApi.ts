import { fetchReadJson as fetchBoundedJson } from '../api'
import { boundedBacktestTree, V2_REPORT_SCHEMA, validateV2Summary, type V2Summary } from './backtestV2'
import { HISTORICAL_REPORT_SCHEMA, validateHistoricalSummary } from './backtestHistorical'
import { PER_DATE_REPORT_SCHEMA, RETAINED_REPORT_SCHEMA, isRetainedReport, retainedSymbols, validatePerDateWindow, validateRetainedSummary } from './backtestRetained'
import { ORIGINAL_SIGNAL_ALGORITHM } from './originalNativeIdentity'

/** 报告排队、原件核验及比较共用后端30秒，另留1秒HTTP余量。 */
export function fetchBacktestReadJson<T>(input: RequestInfo | URL, context: string, signal?: AbortSignal): Promise<T> {
  return fetchBoundedJson<T>(input, context, signal, 'workspace', 31_000)
}

export type BacktestRun = {
  owner_id: string; request_id: string; run_id: string | null
  status: 'running' | 'completed' | 'incomplete' | 'busy'; reason: string
  elapsed_ms: number; pid: number | null; exit_code: number | null
  forced: boolean | null; pid_reaped: boolean | null; pipes_joined: boolean | null
  record_count: number; scope: string
  archive_status?: 'pending' | 'not-applicable' | 'available' | 'unavailable' | 'unknown'
  archive_reason?: string; archive_receipt_sha256?: string | null
}
export type BacktestWorkspaceData = {
  schema: 'nbw-workspace-v1'; owner_id: string; available: boolean; reason: string | null
  configuration: null | { label: string; start: number; end: number; session_sha256: string; max_seconds: number }
  runs: BacktestRun[]; scope: string
}
export type RecordHeader = { trading_date: number; minute: number; status: string; reason: string }
export type BacktestRecords = { request_id: string; report_sha256: string; total: number; offset: number; records: RecordHeader[]; scope: string }
export type BacktestDay = { request_id: string; index: number; report_sha256: string; record: RecordHeader & {
  capture: { basis: { nav_cny: string; cash_cny: string }; observation: { positions: { symbol: string; actual: number; sellable: number; pending_target?: number | null }[] } } | null
  outcome: { status: string; reason: string; submit_targets: { symbol: string; shares: number }[] } | null
  submit_vector?: { symbol: string; quantity: number }[]; readback?: [string, number][]; previous_status?: string | null
}; evaluation_summary: Record<string, unknown> | V2Summary | null; report_schema?: typeof V2_REPORT_SCHEMA | typeof HISTORICAL_REPORT_SCHEMA | typeof RETAINED_REPORT_SCHEMA | typeof PER_DATE_REPORT_SCHEMA; scope: string }

const id = /^[a-f0-9]{32}$/
const digest = /^[a-f0-9]{64}$/
export const validId = (value: unknown): value is string => typeof value === 'string' && id.test(value)
export const validDigest = (value: unknown): value is string => typeof value === 'string' && digest.test(value)
const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const number = (value: unknown) => typeof value === 'number' && Number.isFinite(value)
const boundedText = (value: unknown, max = 512): value is string => typeof value === 'string' && value.length <= max && !/[\u0000-\u001f]/.test(value)
export function tradingDate(value: unknown): value is number {
  if (!Number.isSafeInteger(value) || (value as number) < 19000101 || (value as number) > 99981231) return false
  const s = String(value); const text = `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`; const day = new Date(`${text}T00:00:00Z`)
  return Number.isFinite(day.getTime()) && day.toISOString().slice(0, 10) === text
}
function invalid(): never { throw new Error('回测数据格式或身份无效，请重新读取') }
function exactKeys(value: Record<string, unknown>, required: string[], optional: string[] = []) {
  if (required.some(k => !Object.hasOwn(value, k)) || Object.keys(value).some(k => !required.includes(k) && !optional.includes(k))) return invalid()
}
function run(value: unknown): BacktestRun {
  if (!object(value) || !validId(value.owner_id) || !validId(value.request_id)
    || typeof value.status !== 'string' || !['running', 'completed', 'incomplete', 'busy'].includes(value.status)
    || !boundedText(value.reason) || !boundedText(value.scope)
    || !Number.isSafeInteger(value.elapsed_ms) || (value.elapsed_ms as number) < 0 || !Number.isInteger(value.record_count) || (value.record_count as number) < 0 || (value.record_count as number) > 4096
    || ['forced', 'pid_reaped', 'pipes_joined'].some(key => value[key] !== null && typeof value[key] !== 'boolean')
    || ['pid', 'exit_code'].some(key => value[key] !== null && !Number.isInteger(value[key]))
    || value.run_id !== null && !validId(value.run_id)) return invalid()
  if (value.status === 'completed' && (value.forced !== false || value.exit_code !== 0 || value.pid_reaped !== true || value.pipes_joined !== true
    || !validId(value.run_id) || !Number.isSafeInteger(value.pid) || (value.pid as number) <= 0)) return invalid()
  if (value.archive_status !== undefined && (!['pending', 'not-applicable', 'available', 'unavailable', 'unknown'].includes(String(value.archive_status))
    || !boundedText(value.archive_reason) || value.archive_receipt_sha256 !== null && !validDigest(value.archive_receipt_sha256)
    || value.archive_status === 'available' && (value.status !== 'completed' || !validDigest(value.archive_receipt_sha256)))) return invalid()
  return value as BacktestRun
}

export async function fetchBacktestWorkspace(signal?: AbortSignal): Promise<BacktestWorkspaceData> {
  const value = await fetchBacktestReadJson<unknown>('/v1/ui/backtest/workspace', '回测工作区', signal)
  if (!object(value) || value.schema !== 'nbw-workspace-v1' || !validId(value.owner_id)
    || typeof value.available !== 'boolean' || typeof value.scope !== 'string'
    || value.reason !== null && typeof value.reason !== 'string' || !Array.isArray(value.runs) || value.runs.length > 128) return invalid()
  const config = value.configuration
  if (config !== null && (!object(config) || typeof config.label !== 'string' || !number(config.start) || !number(config.end)
    || !number(config.max_seconds) || !validDigest(config.session_sha256))) return invalid()
  if (value.available && config === null) return invalid()
  value.runs.forEach(item => { if (run(item).owner_id !== value.owner_id) invalid() })
  return value as BacktestWorkspaceData
}

/** 写请求只发一次；丢失回执保留同request身份供状态核查/再次认领，禁止自动重试。 */
export async function commandBacktest(ownerId: string, requestId: string, cancel = false, archive = false): Promise<BacktestRun> {
  if (!validId(ownerId) || !validId(requestId)) return invalid()
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 6500)
  let httpStatus: number | undefined
  try {
    const response = await fetch(archive ? `/v1/ui/backtest/runs/${requestId}/archive` : cancel ? `/v1/ui/backtest/runs/${requestId}/cancel` : '/v1/ui/backtest/runs', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
      body: JSON.stringify({ owner_id: ownerId, request_id: requestId }),
    })
    httpStatus = response.status
    if (!response.ok) throw new Error()
    const value = run(await response.json())
    if (value.owner_id !== ownerId || value.request_id !== requestId) return invalid()
    return value
  } catch {
    if (controller.signal.aborted) throw new Error('回测操作回执超时，请刷新状态核查；原运行可能仍在继续')
    // 原始网络/JSON错误可能带响应正文；公开异常只使用本层固定中文与状态码。
    const status = httpStatus === undefined ? '' : `（HTTP ${httpStatus}）`
    throw new Error(`回测操作未取得有效回执${status}，请刷新状态核查；原运行可能仍在继续`)
  } finally { clearTimeout(timer) }
}

export async function fetchBacktestRecords(ownerId: string, requestId: string, offset: number, signal?: AbortSignal, archive?: ArchiveSelection): Promise<BacktestRecords> {
  if (!validId(ownerId) || !validId(requestId) || !Number.isSafeInteger(offset) || offset < 0 || offset > 4096) return invalid()
  const params = new URLSearchParams({ owner_id: ownerId, offset: String(offset), limit: '50' })
  if (archive) { validateArchiveSelection(archive); params.delete('owner_id'); params.set('receipt_sha256', archive.receiptSha) }
  const path = archive ? `/v1/ui/backtest/archive/${archive.runId}/records` : `/v1/ui/backtest/runs/${requestId}/records`
  const value = await fetchBacktestReadJson<unknown>(`${path}?${params}`, '回测记录', signal)
  if (!object(value) || value.request_id !== requestId || !validDigest(value.report_sha256)
    || !Number.isInteger(value.total) || (value.total as number) < 0 || (value.total as number) > 4096 || value.offset !== offset
    || !Array.isArray(value.records) || value.records.length > 50 || typeof value.scope !== 'string') return invalid()
  if (value.records.length > Math.max(0, (value.total as number) - offset)
    || archive?.reportSha !== undefined && value.report_sha256 !== archive.reportSha) return invalid()
  let previous = 0
  for (const row of value.records) {
    if (!object(row) || !tradingDate(row.trading_date) || row.trading_date <= previous || row.minute !== 1500 || !boundedText(row.status) || !boundedText(row.reason)) return invalid()
    previous = row.trading_date
  }
  return value as BacktestRecords
}

export async function fetchBacktestDay(ownerId: string, requestId: string, index: number, signal?: AbortSignal, expectedReportSha?: string, expectedTradingDate?: number, archive?: ArchiveSelection): Promise<BacktestDay> {
  if (!validId(ownerId) || !validId(requestId) || !Number.isSafeInteger(index) || index < 0 || index >= 4096
    || expectedReportSha !== undefined && !validDigest(expectedReportSha) || expectedTradingDate !== undefined && !tradingDate(expectedTradingDate)) return invalid()
  if (archive) validateArchiveSelection(archive)
  const path = archive ? `/v1/ui/backtest/archive/${archive.runId}/records/${index}?receipt_sha256=${archive.receiptSha}`
    : `/v1/ui/backtest/runs/${requestId}/records/${index}?owner_id=${ownerId}`
  const value = await fetchBacktestReadJson<unknown>(path, '回测当日详情', signal)
  boundedBacktestTree(value)
  if (!object(value) || value.request_id !== requestId || value.index !== index || !validDigest(value.report_sha256)
    || expectedReportSha !== undefined && value.report_sha256 !== expectedReportSha
    || !object(value.record) || typeof value.scope !== 'string'
    || value.report_schema !== undefined && ![V2_REPORT_SCHEMA, HISTORICAL_REPORT_SCHEMA, RETAINED_REPORT_SCHEMA, PER_DATE_REPORT_SCHEMA].includes(value.report_schema as typeof RETAINED_REPORT_SCHEMA)) return invalid()
  const record = value.record
  exactKeys(value, ['request_id', 'index', 'report_sha256', 'record', 'evaluation_summary', 'scope'], ['report_schema'])
  exactKeys(record, ['trading_date', 'minute', 'status', 'reason', 'capture', 'outcome', 'previous_status', 'submit_vector', 'readback',
    ...(value.report_schema === PER_DATE_REPORT_SCHEMA ? ['market_window'] : [])])
  if (!tradingDate(record.trading_date) || expectedTradingDate !== undefined && record.trading_date !== expectedTradingDate
    || record.minute !== 1500 || !boundedText(record.status) || !boundedText(record.reason)) return invalid()
  const capture = record.capture
  if (capture !== null) {
    if (!object(capture) || !object(capture.basis) || !object(capture.observation)
      || typeof capture.basis.nav_cny !== 'string' || capture.basis.nav_cny.length > 256 || !/^-?\d+(?:\.\d+)?$/.test(capture.basis.nav_cny)
      || typeof capture.basis.cash_cny !== 'string' || capture.basis.cash_cny.length > 256 || !/^-?\d+(?:\.\d+)?$/.test(capture.basis.cash_cny)
      || !Array.isArray(capture.observation.positions) || capture.observation.positions.length > 8) return invalid()
    for (const position of capture.observation.positions) {
      if (!object(position) || typeof position.symbol !== 'string' || !Number.isSafeInteger(position.actual) || (position.actual as number) < 0
        || !Number.isSafeInteger(position.sellable) || (position.sellable as number) < 0 || (position.sellable as number) > (position.actual as number)
        || position.pending_target !== undefined && position.pending_target !== null && (!Number.isSafeInteger(position.pending_target) || (position.pending_target as number) < 0)) return invalid()
    }
    if (new Set(capture.observation.positions.map(p => (p as Record<string, unknown>).symbol)).size !== capture.observation.positions.length) return invalid()
  }
  const outcome = record.outcome
  if (outcome !== null) {
    if (!object(outcome) || typeof outcome.status !== 'string' || typeof outcome.reason !== 'string'
      || !Array.isArray(outcome.submit_targets) || outcome.submit_targets.length > 8) return invalid()
    for (const target of outcome.submit_targets) {
      if (!object(target) || typeof target.symbol !== 'string' || !Number.isSafeInteger(target.shares) || (target.shares as number) < 0) return invalid()
    }
    if (new Set(outcome.submit_targets.map(p => (p as Record<string, unknown>).symbol)).size !== outcome.submit_targets.length) return invalid()
  }
  if (value.evaluation_summary !== null && !object(value.evaluation_summary)) return invalid()
  if (value.report_schema === PER_DATE_REPORT_SCHEMA) validatePerDateWindow(record.market_window, record.trading_date, value.evaluation_summary)
  const v2 = value.report_schema === V2_REPORT_SCHEMA
  const retained = isRetainedReport(value.report_schema)
  const symbols = retained && object(capture) && object(capture.observation) && Array.isArray(capture.observation.positions)
    ? retainedSymbols(capture.observation.positions.map(p => object(p) ? p.symbol : null)) : []
  if (retained && (!object(capture) || !object(capture.observation) || capture.observation.verified !== true
    || !object(capture.basis) || capture.basis.native_nav_verified !== true || !Array.isArray(capture.observation.positions)
    || capture.observation.positions.length !== 8 || capture.observation.positions.some((p, i) => !object(p) || p.symbol !== symbols[i]))) return invalid()
  if (v2 || retained) {
    if (!Array.isArray(record.submit_vector) || ![0, 8].includes(record.submit_vector.length) || !Array.isArray(record.readback) || record.readback.length > 8
      || record.previous_status !== null && typeof record.previous_status !== 'string') return invalid()
    for (const target of record.submit_vector) if (!object(target) || typeof target.symbol !== 'string' || !/^(?:SSE|SZSE)\.ETF\.[0-9]{6}$/.test(target.symbol)
      || !Number.isSafeInteger(target.quantity) || (target.quantity as number) < 0) return invalid()
    if (new Set(record.submit_vector.map(p => (p as Record<string, unknown>).symbol)).size !== record.submit_vector.length) return invalid()
    for (const row of record.readback) if (!Array.isArray(row) || row.length !== 2 || typeof row[0] !== 'string'
      || !/^(?:SSE|SZSE)\.ETF\.[0-9]{6}$/.test(row[0]) || !Number.isSafeInteger(row[1]) || row[1] < 0) return invalid()
    if (new Set(record.readback.map(row => (row as unknown[])[0])).size !== record.readback.length) return invalid()
    if (value.evaluation_summary === null) {
      if (record.status !== 'warming_up' || (retained ? !object(capture) : capture !== null) || outcome !== null || record.submit_vector.length || record.readback.length) return invalid()
    } else {
      const summary = retained ? validateRetainedSummary(value.evaluation_summary, record.trading_date as number, symbols) : validateV2Summary(value.evaluation_summary, record.trading_date as number)
      if (capture === null || !object(capture) || !object(capture.observation) || capture.observation.verified !== true
        || !object(capture.basis) || capture.basis.native_nav_verified !== true
        || !Array.isArray(capture.observation.positions) || capture.observation.positions.length !== 8
        || capture.observation.positions.some(p => !object(p) || typeof p.symbol !== 'string' || !/^[0-9]{6}\.(?:SH|SZ)$/.test(p.symbol))) return invalid()
      if (retained) {
        if (object(outcome) && object(outcome.state) && object(outcome.state.target)) {
          const target = outcome.state.target
          const saved = summary as import('./backtestRetained').RetainedSummary
          if (target.strategy_id !== saved.strategy_id || typeof target.algorithm_id !== 'string'
            || !target.algorithm_id.startsWith(`${saved.strategy_id}@${saved.strategy_version}/`)
            || !Array.isArray(target.universe) || target.universe.length !== symbols.length || target.universe.some((symbol, index) => symbol !== symbols[index])) return invalid()
        }

        if (capture.observation.positions.some((p, i) => !object(p) || p.symbol !== symbols[i])
          || !object(outcome) || record.status !== outcome.status || !Array.isArray(outcome.submit_targets)
          || outcome.submit_targets.length !== record.submit_vector.length || ![0, 8].includes(outcome.submit_targets.length)
          || record.submit_vector.length === 0 && record.readback.length !== 0) return invalid()
        for (let i = 0; i < outcome.submit_targets.length; i++) {
          const target = outcome.submit_targets[i] as Record<string, unknown>; const vector = record.submit_vector[i] as Record<string, unknown>
          const symbol = symbols[i]; const native = `${symbol.endsWith('.SH') ? 'SSE' : 'SZSE'}.ETF.${symbol.slice(0, 6)}`
          if (target.symbol !== symbol || vector.symbol !== native || vector.quantity !== target.shares
            // WT目标枚举省略零目标；只在此原协议字段中按零核对，原读回列表保持原样。
            || ((record.readback.find(row => (row as unknown[])[0] === native) as unknown[] | undefined)?.[1] ?? 0) !== target.shares) return invalid()
        }
        if (record.readback.some(row => !symbols.some(symbol =>
          (row as unknown[])[0] === `${symbol.endsWith('.SH') ? 'SSE' : 'SZSE'}.ETF.${symbol.slice(0, 6)}`))) return invalid()
      } else if (!(summary as V2Summary).target_admission.accepted) {
        if (record.status !== 'blocked_raw_total' || outcome !== null || record.submit_vector.length || record.readback.length) return invalid()
      } else if (record.status === 'blocked_raw_total' || !object(outcome) || record.status !== outcome.status
        || !Array.isArray(outcome.submit_targets) || outcome.submit_targets.length !== record.submit_vector.length
        || record.submit_vector.length === 0 && record.readback.length !== 0) return invalid()
    }
  } else if (value.report_schema === HISTORICAL_REPORT_SCHEMA) {
    if (value.evaluation_summary === null) {
      if (record.status !== 'warming_up' || capture !== null || outcome !== null) return invalid()
    } else validateHistoricalSummary(value.evaluation_summary, record.trading_date)
  } else if (object(value.evaluation_summary) && ('historical_model' in value.evaluation_summary || 'kind' in value.evaluation_summary || 'pipeline' in value.evaluation_summary || 'signal_trace' in value.evaluation_summary)) return invalid()
  return value as BacktestDay
}

export type ArchiveSelection = { runId: string; receiptSha: string; reportSha?: string }
export type ArchiveSummary = {
  /** 完成证明绑定的原报告策略身份；名称和文件名均不参与归属推断。 */ strategy: {
    /** 原报告声明的策略业务ID。 */ id: string
    /** 该份报告实际使用的策略版本。 */ version: string
  }
  /** 原模型初始本金，人民币十进制文本；完整绩效在选择后另行核验。 */ initial_capital_cny: string
}
export type ArchiveEntry = {
  /** 原完成归档的运行ID，用于选择同一份报告。 */ run_id: string
  /** 原运行所有者ID，沿完成证明保留。 */ owner_id: string
  /** 原运行请求ID，沿完成证明保留。 */ request_id: string
  /** 原报告记录数，按该报告声明的期数计数。 */ record_count: number
  /** 原规范报告正文的SHA256，绑定完整绩效读取。 */ report_sha256: string
  /** 完成证明原字节的SHA256，绑定同一归档身份。 */ receipt_sha256: string
  /** 原归档声明的适用范围，不扩大运行或交易资格。 */ scope: string
  /** 新目录提供的轻量归属；null为该份原件未取得归属，缺省表示旧目录合同。 */ summary?: ArchiveSummary | null
  /** 完成证明保存的运行配置摘要，展示标签不参与金融归属。 */ configuration: {
    /** 原报告的展示标签。 */ label: string
    /** 原WT回测配置名称。 */ name: string
    /** 原回测起点，YYYYMMDDHHmm整数。 */ start: number
    /** 原回测终点，YYYYMMDDHHmm整数。 */ end: number
    /** 原冻结会话输入的SHA256。 */ session_sha256: string
    /** 原运行截止预算，单位秒。 */ max_seconds: number
  }
}
export type ArchiveIndex = { schema: 'nbw-archive-index-v1'; runs: ArchiveEntry[]; invalid_receipts: number; unarchived_runs: number; scope: string }
export type ArchiveSummaryIndex = Omit<ArchiveIndex, 'schema'> & {
  /** 轻量归属目录的固定协议版本，区别于旧完成证明目录。 */ schema: 'nbw-archive-summary-index-v1'
}
export type ArchiveConfiguration = { schema: 'nbw-archive-configuration-v1'; run_id: string; request_id: string;
  receipt_sha256: string; report_sha256: string; installation_sha256: string; configuration: ArchiveEntry['configuration'];
    session_configuration: unknown; policy: unknown; fee_reserve_cny: unknown; fee_source: unknown; scope: string
    /** 原只读诊断投影；本接口不从诊断推断绩效或交易资格。 */ business_diagnostics?: Record<string, unknown> | null
    /** 仅原版WT族提供的已核模型和资金缺口，旧族缺省。 */ original_native?: OriginalNativeMetadata }
export type OriginalNativeMetadata = {
  /** 原版信号算法身份，不替代WT执行模型。 */ signal_algorithm_id: string
  /** 原参考报告规范JSON的SHA256。 */ reference_report_sha256: string
  /** 原完整输入规范JSON的SHA256。 */ source_snapshot_sha256: string
  /** 原报告绑定的WT原生执行模型；现金约束版与旧a1分别说明。 */ execution_model: 'signal-close-to-next-WT-native-tick' | 'D-close-intent; WT-native-limit-next-tick; unfilled-intent-retained'
  /** 原报告完整模型声明。 */ historical_model: Record<string, unknown>
  /** ISO评价首尾及额外前一真实交易日暖机。 */ evaluation_window: {
    /** 额外一前日，仅用于WT真实bar暖机。 */ warmup_date: string
    /** 评价开始日，上海YYYY-MM-DD。 */ from: string
    /** 评价结束日，上海YYYY-MM-DD。 */ to: string
  }
  /** 从已校原生逐日现金派生的负现金日期数。 */ cash_deficit_count: number
  /** 负现金日期，上海YYYYMMDD，升序唯一。 */ cash_deficit_dates: number[]
  /** 来源单位及可知性未取得完整资格。 */ source_qualified: false
  /** 研究报告不授账户执行资格。 */ execution_qualified: false
  /** 历史首次可知时点未取得资格。 */ point_in_time_qualified: false
}
function validateArchiveSelection(value: ArchiveSelection) {
  if (!validId(value.runId) || !validDigest(value.receiptSha) || value.reportSha !== undefined && !validDigest(value.reportSha)) return invalid()
}
export function archiveConfiguration(value: unknown): value is ArchiveEntry['configuration'] {
  if (!object(value)) return false
  exactKeys(value, ['label', 'name', 'start', 'end', 'session_sha256', 'max_seconds'])
  return boundedText(value.label, 100) && value.label.length > 0 && boundedText(value.name, 31)
    && /^[A-Za-z][A-Za-z0-9_-]{0,30}$/.test(value.name) && Number.isSafeInteger(value.start) && Number.isSafeInteger(value.end)
    && (value.start as number) < (value.end as number) && validDigest(value.session_sha256)
    && number(value.max_seconds) && (value.max_seconds as number) >= .1 && (value.max_seconds as number) <= 1800
}
export async function fetchBacktestArchive(signal?: AbortSignal): Promise<ArchiveIndex> {
  const value = await fetchBacktestReadJson<unknown>('/v1/ui/backtest/archive', '历史回测归档', signal)
  return archiveIndex(value, false) as ArchiveIndex
}
/** 列表先读原件归属，不再用全部报告的完整绩效发现策略身份。 */
export async function fetchBacktestArchiveSummaries(signal?: AbortSignal): Promise<ArchiveSummaryIndex> {
  const value = await fetchBacktestReadJson<unknown>('/v1/ui/backtest/archive-summaries', '回测报告目录', signal)
  return archiveIndex(value, true) as ArchiveSummaryIndex
}
function archiveIndex(value: unknown, summaries: boolean): ArchiveIndex | ArchiveSummaryIndex {
  boundedBacktestTree(value)
  if (!object(value)) return invalid()
  exactKeys(value, ['schema', 'runs', 'invalid_receipts', 'unarchived_runs', 'scope'])
  if (value.schema !== (summaries ? 'nbw-archive-summary-index-v1' : 'nbw-archive-index-v1') || !Array.isArray(value.runs) || value.runs.length > 128 || !boundedText(value.scope)
    || !Number.isInteger(value.invalid_receipts) || (value.invalid_receipts as number) < 0
    || !Number.isInteger(value.unarchived_runs) || (value.unarchived_runs as number) < 0
    || value.runs.length + (value.invalid_receipts as number) + (value.unarchived_runs as number) > 128) return invalid()
  const ids = new Set<string>()
  for (const entry of value.runs) {
    if (!object(entry)) return invalid()
    exactKeys(entry, ['run_id', 'owner_id', 'request_id', 'record_count', 'report_sha256', 'receipt_sha256', 'configuration', 'scope', ...(summaries ? ['summary'] : [])])
    if (!validId(entry.run_id) || !validId(entry.owner_id) || !validId(entry.request_id) || ids.has(entry.run_id)
      || !validDigest(entry.report_sha256) || !validDigest(entry.receipt_sha256) || !archiveConfiguration(entry.configuration)
      || !Number.isInteger(entry.record_count) || (entry.record_count as number) < 0 || (entry.record_count as number) > 4096 || !boundedText(entry.scope)) return invalid()
    ids.add(entry.run_id)
    if (summaries && entry.summary !== null) {
      if (!object(entry.summary) || !object(entry.summary.strategy)) return invalid()
      exactKeys(entry.summary, ['strategy', 'initial_capital_cny']); exactKeys(entry.summary.strategy, ['id', 'version'])
      if (!boundedText(entry.summary.strategy.id, 256) || !entry.summary.strategy.id.length
        || !boundedText(entry.summary.strategy.version, 256) || !entry.summary.strategy.version.length
        || typeof entry.summary.initial_capital_cny !== 'string' || entry.summary.initial_capital_cny.length > 512
        || !/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(entry.summary.initial_capital_cny) || !/[1-9]/.test(entry.summary.initial_capital_cny)) return invalid()
    }
  }
  return value as ArchiveIndex | ArchiveSummaryIndex
}
export async function fetchArchiveConfiguration(entry: ArchiveEntry, signal?: AbortSignal): Promise<ArchiveConfiguration> {
  validateArchiveSelection({ runId: entry.run_id, receiptSha: entry.receipt_sha256 })
  const value = await fetchBacktestReadJson<unknown>(`/v1/ui/backtest/archive/${entry.run_id}?receipt_sha256=${entry.receipt_sha256}`, '历史冻结配置', signal)
  boundedBacktestTree(value)
  if (!object(value)) return invalid()
  exactKeys(value, ['schema', 'run_id', 'request_id', 'receipt_sha256', 'report_sha256', 'installation_sha256', 'configuration',
    'session_configuration', 'policy', 'fee_reserve_cny', 'fee_source', 'scope'], ['original_native', 'business_diagnostics'])
  if (value.schema !== 'nbw-archive-configuration-v1' || value.run_id !== entry.run_id || value.request_id !== entry.request_id
    || value.receipt_sha256 !== entry.receipt_sha256 || value.report_sha256 !== entry.report_sha256
    || !validDigest(value.installation_sha256) || !archiveConfiguration(value.configuration) || !boundedText(value.scope)) return invalid()
  if (Object.entries(entry.configuration).some(([key, item]) => (value.configuration as Record<string, unknown>)[key] !== item)) return invalid()
  if (value.business_diagnostics !== undefined && value.business_diagnostics !== null && !object(value.business_diagnostics)) return invalid()
  if (value.original_native !== undefined) {
    const m = value.original_native
    if (!object(m) || m.signal_algorithm_id !== ORIGINAL_SIGNAL_ALGORITHM || !validDigest(m.reference_report_sha256) || !validDigest(m.source_snapshot_sha256)
      || !['signal-close-to-next-WT-native-tick', 'D-close-intent; WT-native-limit-next-tick; unfilled-intent-retained'].includes(String(m.execution_model))
      || !object(m.historical_model) || m.historical_model.execution !== m.execution_model
      || m.execution_model === 'D-close-intent; WT-native-limit-next-tick; unfilled-intent-retained' && m.historical_model.cash !== 'actual-D-cash-reserves-all-buy-principal-and-fee-upper-bounds; no-unfilled-sale-credit'
      || !object(m.evaluation_window) || ['warmup_date', 'from', 'to'].some(k => typeof m.evaluation_window !== 'object' || !object(m.evaluation_window)
        || typeof m.evaluation_window[k] !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(String(m.evaluation_window[k])) || !tradingDate(Number(String(m.evaluation_window[k]).replaceAll('-', ''))))
      || !(m.evaluation_window.warmup_date as string < (m.evaluation_window.from as string)) || m.evaluation_window.from as string > (m.evaluation_window.to as string)
      || !Number.isInteger(m.cash_deficit_count) || Number(m.cash_deficit_count) < 0 || Number(m.cash_deficit_count) > 4096
      || !Array.isArray(m.cash_deficit_dates) || m.cash_deficit_dates.length !== m.cash_deficit_count || m.cash_deficit_dates.some((d, i, all) => !tradingDate(d) || i > 0 && d <= all[i - 1])
      || m.source_qualified !== false || m.execution_qualified !== false || m.point_in_time_qualified !== false) return invalid()
  }
  return value as ArchiveConfiguration
}
