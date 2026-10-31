import { fetchReadJson } from '../api'
import { isProcessStatus, type ProcessStatus } from './operationsApi'

export type HistoryPreparationStatus = {
  schema_version: 'guanheng.history-preparation-app-status.v1'; read_only: true; observed_at: string
  process: ProcessStatus; qmt_connection: 'not_checked'; data_qualification: 'not_checked'
}

export async function fetchHistoryPreparation(signal: AbortSignal): Promise<HistoryPreparationStatus> {
  const data = await fetchReadJson<unknown>('/v1/ui/qmt-history-preparation', '历史补齐状态', signal, 'status')
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('历史补齐状态格式无效，请重新读取')
  const value = data as Record<string, unknown>
  if (value.schema_version !== 'guanheng.history-preparation-app-status.v1' || value.read_only !== true
    || typeof value.observed_at !== 'string' || !Number.isFinite(Date.parse(value.observed_at))
    || !isProcessStatus(value.process) || value.qmt_connection !== 'not_checked' || value.data_qualification !== 'not_checked') {
    throw new Error('历史补齐状态格式无效，请重新读取')
  }
  return data as HistoryPreparationStatus
}
