import { fetchReadJson } from '../api'
import { validateAccountOverview, type AccountOverview } from './accountApi'
import { validateStrategyRuntime, type StrategyRuntime } from './strategyRuntimeApi'

export type OptionalFact = { value: string | number | null; reason: string | null }
export type StrategyDetails = {
  schema_version: 'guanheng.strategy-details.v1'; read_only: true; observed_at: string
  strategy: { strategy_id: 'resonance-regime-v1'; strategy_version: '1.1.2'; display_name: string }
  assignment: { scope: 'current-account-inventory'; label: string; reason: string }
  execution: { state: string; label: string; reason: string; started_at: OptionalFact; duration_seconds: OptionalFact }
  account: AccountOverview | null; account_reason: string | null
  calculation: StrategyRuntime['strategy']; calculation_reason: string | null
  budget_cny: OptionalFact; returns: { cumulative_pct: OptionalFact }
}
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const text = (v: unknown): v is string => typeof v === 'string' && v.length <= 500
function fact(v: unknown): boolean {
  return object(v) && (v.value === null ? text(v.reason) && v.reason.length > 0
    : (typeof v.value === 'string' && v.value.length > 0 && v.value.length <= 64 || typeof v.value === 'number' && Number.isFinite(v.value)) && v.reason === null)
}
function numericFact(v: unknown, nonnegative = false): boolean {
  if (!fact(v)) return false
  const value = (v as OptionalFact).value
  if (value === null) return true
  return !(typeof value === 'string' && !value.trim()) && Number.isFinite(Number(value))
    && Math.abs(Number(value)) <= Number.MAX_SAFE_INTEGER && (!nonnegative || Number(value) >= 0)
}
function timeFact(v: unknown): boolean {
  if (!fact(v)) return false
  const value = (v as OptionalFact).value
  return value === null || typeof value === 'string' && /(Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value))
}
export function validateStrategyDetails(v: unknown): StrategyDetails {
  const invalid = () => { throw new Error('策略详情格式无效，请重新读取') }
  if (!object(v) || v.schema_version !== 'guanheng.strategy-details.v1' || v.read_only !== true
    || !text(v.observed_at) || !Number.isFinite(Date.parse(v.observed_at)) || !object(v.strategy)
    || v.strategy.strategy_id !== 'resonance-regime-v1' || v.strategy.strategy_version !== '1.1.2' || !text(v.strategy.display_name)
    || !object(v.assignment) || v.assignment.scope !== 'current-account-inventory' || !text(v.assignment.label) || !text(v.assignment.reason)
    || !object(v.execution) || !['unconfigured','not_started','disabled','new','starting','ready','stopping','closed','faulted','unavailable'].includes(String(v.execution.state))
    || !text(v.execution.label) || !text(v.execution.reason) || !timeFact(v.execution.started_at) || !numericFact(v.execution.duration_seconds, true)
    || !numericFact(v.budget_cny, true) || !object(v.returns) || !numericFact(v.returns.cumulative_pct)
    || !(v.account_reason === null || text(v.account_reason)) || !(v.calculation_reason === null || text(v.calculation_reason))) return invalid()
  if (v.account !== null) validateAccountOverview(v.account)
  if (v.calculation !== null) validateStrategyRuntime({schema_version:'guanheng.strategy-runtime.v1',read_only:true,
    observed_at:v.observed_at,state:'available',strategy:v.calculation})
  return v as StrategyDetails
}
export async function fetchStrategyDetails(signal: AbortSignal) {
  return validateStrategyDetails(await fetchReadJson<unknown>('/v1/ui/strategy-details', '策略详情', signal, 'workspace', 4000))
}
