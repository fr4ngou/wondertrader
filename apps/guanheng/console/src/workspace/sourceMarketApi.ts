import { fetchReadJson } from '../api'
import { isProcessStatus, type ProcessStatus } from './operationsApi'

export type SourceMarketStatus = {
  schema_version: 'guanheng.source-market-app-status.v1'; read_only: true
  observed_at: string; process: ProcessStatus; data_qualification: 'not_checked'
}

export async function fetchSourceMarketStatus(signal: AbortSignal): Promise<SourceMarketStatus> {
  const data = await fetchReadJson<unknown>('/v1/ui/source-market', '历史查询进程状态', signal, 'status')
  if (data === null || typeof data !== 'object' || Array.isArray(data)) throw new Error('历史查询进程状态格式无效，请重新读取')
  const value = data as Record<string, unknown>
  if (value.schema_version !== 'guanheng.source-market-app-status.v1' || value.read_only !== true
    || typeof value.observed_at !== 'string' || !Number.isFinite(Date.parse(value.observed_at))
    || value.data_qualification !== 'not_checked' || !isProcessStatus(value.process)) {
    throw new Error('历史查询进程状态格式无效，请重新读取')
  }
  return value as SourceMarketStatus
}
