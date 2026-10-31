import { fetchReadJson } from '../api'
import { isProcessStatus, type ProcessStatus } from './operationsApi'

export type ExecutionProcessStatus = { schema_version: 'guanheng.execution-app-status.v1'; read_only: true;
  observed_at: string; process: ProcessStatus; configuration_sha256: string | null;
  execution_qualification: 'not_checked'; recovery_ready: false }
export async function fetchExecutionProcessStatus(signal: AbortSignal): Promise<ExecutionProcessStatus> {
  const data = await fetchReadJson<unknown>('/v1/ui/execution-process', '策略执行进程状态', signal, 'status')
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('策略执行进程状态格式无效，请重新读取')
  const value = data as Record<string, unknown>
  if (value.schema_version !== 'guanheng.execution-app-status.v1' || value.read_only !== true
    || typeof value.observed_at !== 'string' || !Number.isFinite(Date.parse(value.observed_at))
    || !isProcessStatus(value.process) || value.execution_qualification !== 'not_checked' || value.recovery_ready !== false
    || !(value.configuration_sha256 === null || typeof value.configuration_sha256 === 'string' && /^[a-f0-9]{64}$/.test(value.configuration_sha256))) {
    throw new Error('策略执行进程状态格式无效，请重新读取')
  }
  return data as ExecutionProcessStatus
}
