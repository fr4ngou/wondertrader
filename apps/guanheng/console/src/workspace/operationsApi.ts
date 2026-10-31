import { fetchReadJson } from '../api'

export type ProcessStatus = {
  state: string; label: string; reason: string; pid: number | null
  ready: boolean | null; pending: boolean | null; forced: boolean | null; error: string | null; action: string
}
export type OperationsStatus = {
  schema_version: 'guanheng.operations.v2'; read_only: true; observed_at: string
  collection: ProcessStatus; host: ProcessStatus
  query: { state: 'unconfigured' | 'responding' | 'unavailable'; reason: string
    history_supported: boolean | null; snapshot_supported: boolean | null; source: string | null }
  telemetry: { source: string; available: boolean; status: string; latest_source_time_ms: number | null
    received_at: string | null; published_at: string | null; status_file_updated_at: string | null
    active: boolean | null; connected: boolean | null; generation: number | null; phase: string | null
    snapshot_age_seconds: number | null; received_ticks: number | null; pushed_ticks: number | null
    processed_ticks: number | null; native_subscribed: number | null; coverage: number | null
    missing_symbols: number | null; queue_depth: number | null; overflows: number | null; receiver_heartbeats: number | null
    reason: string; error: string | null; failure: { stage: string; exception_kind: string | null; winerror: number | null } | null }
}

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}
export function isProcessStatus(value: unknown): value is ProcessStatus {
  return object(value) && ['state', 'label', 'reason', 'action'].every(k => typeof value[k] === 'string')
    && ['ready', 'pending', 'forced'].every(k => value[k] === null || typeof value[k] === 'boolean')
    && (value.error === null || typeof value.error === 'string')
    && (value.pid === null || (Number.isSafeInteger(value.pid) && Number(value.pid) > 0))
}
const nullableBoolean = (v: unknown) => v === null || typeof v === 'boolean'
const nullableTime = (v: unknown) => v === null || (typeof v === 'string' && Number.isFinite(Date.parse(v)))
const nullableCount = (v: unknown) => v === null || (typeof v === 'number' && Number.isSafeInteger(v) && v >= 0)

export async function fetchOperations(signal: AbortSignal): Promise<OperationsStatus> {
  const data = await fetchReadJson<unknown>('/v1/ui/operations/status', '系统状态', signal, 'status')
  if (!object(data) || data.schema_version !== 'guanheng.operations.v2' || data.read_only !== true
    || typeof data.observed_at !== 'string' || !Number.isFinite(Date.parse(data.observed_at))
    || !isProcessStatus(data.collection) || !isProcessStatus(data.host) || !object(data.query) || !object(data.telemetry)) {
    throw new Error('系统状态格式无效，请重新读取')
  }
  const q = data.query, t = data.telemetry
  if (!['unconfigured', 'responding', 'unavailable'].includes(String(q.state)) || typeof q.reason !== 'string'
    || (q.source !== null && !['QMT', '通达信'].includes(String(q.source)))
    || !nullableBoolean(q.history_supported) || !nullableBoolean(q.snapshot_supported)
    || typeof t.source !== 'string' || typeof t.reason !== 'string' || typeof t.status !== 'string' || typeof t.available !== 'boolean'
    || !nullableBoolean(t.active) || !nullableBoolean(t.connected)
    || ![t.received_at, t.published_at, t.status_file_updated_at].every(nullableTime)
    || ![t.latest_source_time_ms, t.received_ticks, t.pushed_ticks, t.processed_ticks, t.native_subscribed,
      t.coverage, t.missing_symbols, t.queue_depth, t.overflows, t.receiver_heartbeats, t.generation].every(nullableCount)
    || (t.latest_source_time_ms !== null && Number(t.latest_source_time_ms) > 8640000000000000)
    || (t.phase !== null && typeof t.phase !== 'string') || (t.error !== null && typeof t.error !== 'string')
    || !(t.snapshot_age_seconds === null || (typeof t.snapshot_age_seconds === 'number' && Number.isFinite(t.snapshot_age_seconds) && t.snapshot_age_seconds >= 0))
    || !(t.failure === null || (object(t.failure) && typeof t.failure.stage === 'string'
      && (t.failure.exception_kind === null || typeof t.failure.exception_kind === 'string') && nullableCount(t.failure.winerror)))) {
    throw new Error('系统状态格式无效，请重新读取')
  }
  return data as OperationsStatus
}
