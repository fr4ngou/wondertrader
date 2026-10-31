export interface ReplenishmentItem {
  episode_id: string
  strategy_id?: string | null
  // Persisted episode scope; missing identity keeps display membership unknown.
  strategy_version?: string | null
  config_id?: string | null
  config_version?: string | null
  // Evidence only: Portfolio may continue the same opportunity on a successor target.
  target_revision?: string | null
  symbol?: string | null
  side?: string | null
  state_label: string
  remaining_quantity?: number | null
  filled_quantity?: number | null
  original_intended_quantity?: number | null
  retained_quantity?: number | null
  next_action?: string
  next_action_owner?: string
  blocking_reason_labels?: string[]
  blocking_reasons?: string[]
  legacy_read_only?: boolean
  terminal?: boolean
  risk_exit?: boolean
  policy?: string
  authorization_mode?: string
  stage_index?: number
  renewals_used?: number
  cumulative_deviation?: number | null
  deviation_formula?: string | null
  reference_price?: number | null
  original_reference_price?: number | null
  business_boundary?: number | null
  effective_boundary?: number | null
  boundary_evidence_at?: string | null
  deviation_mode?: string
  maximum_deviation?: number | null
  first_eligible_at?: string | null
  next_review_at?: string | null
  next_retry_at?: string | null
  order_live_deadline?: string | null
  updated_at?: string | null
  wait?: { amount: number; unit: string } | null
  stages?: { index: number; authorized: boolean; status: string; boundary: number | null; wait: { amount: number; unit: string } }[]
  risk_target?: { metric: string; metric_value: number; trigger_ratio: number; retained_quantity: number; triggered_at: string; valid_until: string; policy_valid_until: string } | null
}

export interface ReplenishmentProjection { items: ReplenishmentItem[]; scan_error?: unknown }

export function replenishmentTime(value?: string | null) {
  if (!value) return '暂无'
  const date = new Date(value)
  return Number.isNaN(date.valueOf()) ? '时间待核对' : date.toLocaleString('zh-CN', { hour12: false })
}

export function replenishmentValue(value?: number | null) {
  return value == null ? '待核对' : value.toLocaleString('zh-CN', { maximumFractionDigits: 6 })
}

export interface ReplenishmentDisplayScope {
  strategyId: string
  strategyVersion?: string
  configId?: string | null
}

export const knownIdentity = (value: unknown): value is string => typeof value === 'string' && value.length > 0 && value === value.trim()

export function hasReplenishmentDisplayScope(scope: ReplenishmentDisplayScope): boolean {
  return [scope.strategyId, scope.strategyVersion, scope.configId].every(knownIdentity)
}

export function replenishmentDisplayScope(
  item: ReplenishmentItem, scope: ReplenishmentDisplayScope,
): 'current' | 'historical' | 'unknown' | 'other_strategy' {
  if (!knownIdentity(scope.strategyId)) return 'unknown'
  if (knownIdentity(item.strategy_id) && item.strategy_id !== scope.strategyId) return 'other_strategy'
  if (item.legacy_read_only || !hasReplenishmentDisplayScope(scope)
    || ![item.strategy_id, item.strategy_version, item.config_id].every(knownIdentity)) return 'unknown'
  // A continuing opportunity can retain its original target revision. Portfolio
  // owns continuation; a newer target ID alone cannot move it into history.
  return item.strategy_version === scope.strategyVersion && item.config_id === scope.configId
    ? 'current' : 'historical'
}
