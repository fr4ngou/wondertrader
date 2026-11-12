import { fetchReadJson } from '../api'
import { validateAccountOverview, type AccountOverview } from './accountApi'
import { validateStrategyRuntime, type StrategyRuntime } from './strategyRuntimeApi'
import { validateCapitalFields, type CapitalFields } from './strategyCapital'

export type OptionalFact = { value: string | number | null; reason: string | null }
export type StrategyDetails = CapitalFields & {
  schema_version: 'guanheng.strategy-details.v1'; read_only: true; observed_at: string
  /** 本轮公开运行四身份的不可逆摘要；null为未配置，缺失兼容旧App。只约束缓存归属。 */
  runtime_scope_id?: string | null
  strategy: {
    /** 本轮WT实际发布的策略身份。 */ strategy_id: string
    /** 本轮WT实际版本；null保持未提供，不从App发行推断。 */ strategy_version: string | null
    /** 原中文展示名称。 */ display_name: string
  }
  assignment: { scope: 'current-account-inventory' | 'strategy-allocated'; label: string; reason: string }
  execution: { state: string; label: string; reason: string; started_at: OptionalFact; duration_seconds: OptionalFact }
  /** 已准入证券目录按规范代码投影的简称；缺项或旧App可缺失。 */ security_names?: Record<string, string>
  account: AccountOverview | null; account_reason: string | null
  calculation: StrategyRuntime['strategy']; calculation_reason: string | null
  budget_cny: OptionalFact; returns: {
    /** WT已核对的资金流调整收益率，单位%。 */ cumulative_pct: OptionalFact
    /** 已核收益的期末估值时刻。 */ valued_at?: string
  }
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
    || !text(v.strategy.strategy_id) || !(v.strategy.strategy_version === null || text(v.strategy.strategy_version) && /^[A-Za-z0-9][A-Za-z0-9_.+-]{0,63}$/.test(v.strategy.strategy_version)) || !text(v.strategy.display_name)
    || !object(v.assignment) || !['current-account-inventory','strategy-allocated'].includes(String(v.assignment.scope)) || !text(v.assignment.label) || !text(v.assignment.reason)
    || !object(v.execution) || !['unconfigured','not_started','disabled','new','starting','ready','stopping','closed','faulted','unavailable'].includes(String(v.execution.state))
    || !text(v.execution.label) || !text(v.execution.reason) || !timeFact(v.execution.started_at) || !numericFact(v.execution.duration_seconds, true)
    || !numericFact(v.budget_cny, true) || !object(v.returns) || !numericFact(v.returns.cumulative_pct)
    || !(v.account_reason === null || text(v.account_reason)) || !(v.calculation_reason === null || text(v.calculation_reason))) return invalid()
  if (v.account !== null) validateAccountOverview(v.account)
  if (v.returns.valued_at !== undefined && (typeof v.returns.valued_at !== 'string'
    || !timeFact({ value: v.returns.valued_at, reason: null })
    || (v.returns.cumulative_pct as OptionalFact).value === null)) return invalid()
  if (v.security_names !== undefined && (!object(v.security_names) || Object.entries(v.security_names).some(([symbol, name]) =>
    !/^\d{6}\.(SH|SZ)$/.test(symbol) || !text(name) || !name.trim()))) return invalid()
  if (v.runtime_scope_id !== undefined && v.runtime_scope_id !== null
    && (typeof v.runtime_scope_id !== 'string' || !/^[a-f0-9]{64}$/.test(v.runtime_scope_id))) return invalid()
  // 采用同一消费者的诊断独立降级结果；丢弃返回值会把坏附加信息继续交给页面。
  const calculation = v.calculation === null ? null : validateStrategyRuntime({schema_version:'guanheng.strategy-runtime.v1',read_only:true,
    observed_at:v.observed_at,state:'available',strategy:v.calculation}).strategy
  validateCapitalFields(v)
  return { ...v, calculation } as StrategyDetails
}
export async function fetchStrategyDetails(signal: AbortSignal, strategyId?: string) {
  return validateStrategyDetails(await fetchReadJson<unknown>('/v1/ui/strategy-details' + (strategyId ? '?' + new URLSearchParams({strategy_id: strategyId}) : ''), '策略详情', signal, 'workspace', 4000))
}
