import { fetchReadJson } from '../api'

export type RuntimeIssue = {relation: 'first_reported' | 'also_reported' | 'unattributed'; summary: string; impact: string; action: string}
type PublishedState = { state: string; label: string; ready: boolean; issue?: RuntimeIssue | null }
// 最近发布数据与服务生命周期分别读取；null表示来源尚未提供该事实。
type PublishedData = {state: 'available' | 'unavailable'; label: string; ready: boolean | null;
  basis_date: string | null; published_at: string | null}
// 原执行配置的开关事实；生命周期、来源许可和风控由各自状态表达。
export type ExecutionControl = {
  /** 本代配置已核实或暂不可核实；缺发布能力不等于关闭。 */
  state: 'available' | 'unavailable'
  /** 原trader.writes_enabled布尔值；null表示未知。 */
  writes_enabled: boolean | null
  /** 后端白名单固定中文说明，不携带配置或异常正文。 */
  label: string
}
export type WtRuntimeObservation = {
  schema_version: 'guanheng.wt-runtime-observation.v1'; read_only: true
  observed_at: string; state: 'available' | 'unconfigured'; reason: string; published_at: string | null
  runtime: (PublishedState & { components: (PublishedState & {
    name: string; display_name: string; pending: boolean; forced: boolean; data?: PublishedData | null
    /** 本代执行配置开关；旧发布者省略时按未知处理。 */
    execution_control?: ExecutionControl | null
  })[] }) | null
}
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const time = (v: unknown): v is string => typeof v === 'string' && Number.isFinite(Date.parse(v))
const states = ['disabled', 'new', 'starting', 'ready', 'stopping', 'closed', 'faulted']
function published(v: unknown): v is Record<string, unknown> {
  return object(v) && typeof v.state === 'string' && states.includes(v.state) && typeof v.label === 'string'
    && typeof v.ready === 'boolean' && (!v.ready || v.state === 'ready') && issue(v.issue)
}
function issue(v: unknown) {
  if (v == null) return true
  return object(v) && typeof v.relation === 'string' && ['first_reported', 'also_reported', 'unattributed'].includes(v.relation)
    && ['summary', 'impact', 'action'].every(key=>typeof v[key] === 'string' && v[key].length > 0 && v[key].length <= 400)
}
function publishedData(v: unknown) {
  if (v == null) return true
  if (!object(v) || typeof v.label !== 'string') return false
  if (v.state === 'unavailable') return v.ready === null && v.basis_date === null && v.published_at === null
  if (v.state !== 'available' || typeof v.ready !== 'boolean') return false
  return v.ready ? typeof v.basis_date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v.basis_date)
    && time(v.published_at) : v.basis_date === null && v.published_at === null
}

function executionControl(v: unknown) {
  if (v == null) return true
  if (!object(v) || typeof v.label !== 'string' || !v.label.length || v.label.length > 160) return false
  return v.state === 'available' ? typeof v.writes_enabled === 'boolean'
    : v.state === 'unavailable' && v.writes_enabled === null
}

export function validateWtRuntime(data: unknown): WtRuntimeObservation {
  const error = () => new Error('WT运行状态格式无效，请重新读取')
  if (!object(data) || data.schema_version !== 'guanheng.wt-runtime-observation.v1' || data.read_only !== true
    || !time(data.observed_at) || typeof data.reason !== 'string') throw error()
  if (data.state === 'unconfigured') {
    if (data.runtime !== null || data.published_at !== null) throw error()
  } else if (data.state === 'available') {
    const runtime = data.runtime
    if (!time(data.published_at) || !published(runtime) || !Array.isArray(runtime.components)
      || !runtime.components.length) throw error()
    const names = new Set<string>()
    for (const c of runtime.components) {
      if (!published(c) || typeof c.name !== 'string' || !/^[a-z][a-z0-9_-]*$/.test(c.name)
        || names.has(String(c.name)) || typeof c.display_name !== 'string'
        || typeof c.pending !== 'boolean' || typeof c.forced !== 'boolean' || !publishedData(c.data)
        || !executionControl(c.execution_control)) throw error()
      names.add(String(c.name))
    }
  } else throw error()
  return data as WtRuntimeObservation
}

export async function fetchWtRuntime(signal: AbortSignal): Promise<WtRuntimeObservation> {
  return validateWtRuntime(await fetchReadJson<unknown>('/v1/ui/wt-runtime', 'WT运行状态', signal, 'status'))
}
