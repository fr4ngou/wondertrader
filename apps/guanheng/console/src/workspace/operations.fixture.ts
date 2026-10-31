import type { OperationsStatus } from './operationsApi'
import type { SourceMarketStatus } from './sourceMarketApi'
import type { ExecutionProcessStatus } from './executionProcessApi'
import type { HistoryPreparationStatus } from './historyPreparationApi'
const process = { state: 'disabled', label: '未配置', reason: '当前应用未配置此受管进程', pid: null,
  ready: false, pending: false, forced: false, error: null, action: '请维护人员核对配置后重新读取' }
export const historyPreparationFixture: HistoryPreparationStatus = {
  schema_version: 'guanheng.history-preparation-app-status.v1', read_only: true, observed_at: '2026-10-29T01:32:20Z',
  process, qmt_connection: 'not_checked', data_qualification: 'not_checked',
}
export const sourceMarketFixture: SourceMarketStatus = {
  schema_version: 'guanheng.source-market-app-status.v1', read_only: true, observed_at: '2026-10-28T09:31:20Z',
  process, data_qualification: 'not_checked',
}
export const executionProcessFixture: ExecutionProcessStatus = {
  schema_version: 'guanheng.execution-app-status.v1', read_only: true, observed_at: '2026-10-28T09:32:20Z',
  process, configuration_sha256: null, execution_qualification: 'not_checked', recovery_ready: false,
}
export const operationsFixture: OperationsStatus = {
  schema_version: 'guanheng.operations.v2', read_only: true, observed_at: '2026-10-28T09:31:20Z',
  collection: process, host: process,
  query: { state: 'unconfigured', reason: '尚未配置行情查询连接', history_supported: null, snapshot_supported: null, source: null },
  telemetry: { source: 'QMT 全推 → 共享内存 → WT 原生 DataKit', available: false, status: 'unconfigured', latest_source_time_ms: null,
    received_at: null, published_at: null, status_file_updated_at: null, active: null, connected: null,
    snapshot_age_seconds: null, generation: null, phase: null, received_ticks: null, pushed_ticks: null, processed_ticks: null,
    native_subscribed: null, coverage: null, missing_symbols: null, queue_depth: null, overflows: null, receiver_heartbeats: null,
    error: null, failure: null, reason: '当前应用未配置行情采集进程' },
}
