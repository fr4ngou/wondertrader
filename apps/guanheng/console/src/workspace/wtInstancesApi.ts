import { fetchReadJson } from '../api'
import { validateWtRuntime, type WtRuntimeObservation } from './wtRuntimeApi'

export type WtInstance = { scope_id: string; label: string; state: 'available' | 'unconfigured' | 'unavailable';
  reason: string; published_at: string | null; runtime: WtRuntimeObservation['runtime'] }
export type WtInstances = { schema_version: 'guanheng.wt-instances.v1'; read_only: true; observed_at: string; instances: WtInstance[]; catalog_reason?: string }
export async function fetchWtInstances(signal: AbortSignal): Promise<WtInstances> {
  const v = await fetchReadJson<WtInstances>('/v1/ui/wt-instances', 'WT各实例状态', signal, 'status')
  const invalid = () => { throw new Error('WT实例状态格式无效，请重新读取') }
  if (v?.schema_version !== 'guanheng.wt-instances.v1' || v.read_only !== true || !Number.isFinite(Date.parse(v.observed_at))
    || !Array.isArray(v.instances) || !v.instances.length || v.instances.length > 8
    || v.catalog_reason !== undefined && (typeof v.catalog_reason !== 'string' || v.catalog_reason.length > 500)) return invalid()
  const ids = new Set<string>()
  for (const row of v.instances) {
    if (!row || !/^[a-f0-9]{64}$/.test(row.scope_id) || ids.has(row.scope_id) || typeof row.label !== 'string' || !row.label
      || row.label.length > 64 || typeof row.reason !== 'string' || row.reason.length > 500) return invalid()
    ids.add(row.scope_id)
    if (row.state === 'unavailable') {
      if (row.runtime !== null || row.published_at !== null) return invalid()
    } else validateWtRuntime({...row,schema_version:'guanheng.wt-runtime-observation.v1',read_only:true,observed_at:v.observed_at})
  }
  return v
}
