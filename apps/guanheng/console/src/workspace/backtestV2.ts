/** 本模块只校验公开日摘要，不计算策略、分配、资金或signal→execution映射。 */
export const V2_REPORT_SCHEMA = 'nsb-v2-report-v1' as const
import packageProfiles from '../../../guanheng_app/v2_package_profiles.json'
const symbols = ['159780.SZ', '510050.SH', '510300.SH', '510500.SH', '512100.SH', '515080.SH', '588000.SH', '589680.SH']
type Json = Record<string, unknown>
export type V2Summary = {
  kind: 'resonance-v2'
  pipeline: {
    schema: 'guanheng.v2-history-result.v1'
    signal: { strategy_id: string; strategy_version: string; algorithm_id: string; signal_profile: string }
    allocation: { latest_event_date: string | null; latest_raw_weights: [string, number][] | null
      raw_diagnostic: { total_weight: number; pre_risk_capacity: number; exceeds_one: boolean; exceeds_pre_risk_capacity: boolean } }
    source_qualified: false; historically_produced: false; execution_qualified: false
  }
  signal_trace: Json
  stable_spec_sha256: string; daily_input_sha256: string
  target_admission: { accepted: boolean; policy_id: 'reject-overweight-v1'; code: 'accepted' | 'blocked_raw_total'; raw_total_fraction: string }
  producer_readiness: { native_input_ready: true; legacy_offline_ready: boolean; source_qualified: false; historically_produced: false }
}

export const isObject = (v: unknown): v is Json => v !== null && typeof v === 'object' && !Array.isArray(v)
export function invalidBacktest(): never { throw new Error('回测数据格式或身份无效，请重新读取') }
function requireValue(value: unknown): asserts value { if (!value) invalidBacktest() }
function keys(value: unknown, names: string): asserts value is Json {
  requireValue(isObject(value))
  const expected = names.split(' ')
  requireValue(Object.keys(value).length === expected.length && expected.every(k => Object.hasOwn(value, k)))
}
const text = (v: unknown, max = 256): v is string => typeof v === 'string' && v.length > 0 && v.length <= max && !/[\u0000-\u001f]/.test(v)
const sha = (v: unknown) => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v)
const finite = (v: unknown, min = -Number.MAX_VALUE, max = Number.MAX_VALUE): v is number => typeof v === 'number' && Number.isFinite(v) && v >= min && v <= max
function date(v: unknown): v is string {
  if (typeof v !== 'string' || !/^(?:19|[2-9]\d)\d{2}-\d{2}-\d{2}$/.test(v)) return false
  const parsed = new Date(`${v}T00:00:00Z`)
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === v && v <= '9998-12-31'
}

/** 公开day的有限树准入先于访问/展示；不用JSON.stringify分配无界诊断字符串。 */
export function boundedBacktestTree(value: unknown): void {
  let nodes = 0; let chars = 0
  function visit(v: unknown, depth: number) {
    if (++nodes > 65536 || depth > 32) invalidBacktest()
    if (typeof v === 'string') { chars += v.length; if (chars > 524288) invalidBacktest(); return }
    if (v === null || typeof v === 'boolean' || finite(v)) return
    if (Array.isArray(v)) { if (v.length > 4096) invalidBacktest(); for (const row of v) visit(row, depth + 1); return }
    if (!isObject(v) || Object.keys(v).length > 64) invalidBacktest()
    for (const [key, child] of Object.entries(v)) { chars += key.length; if (chars > 524288) invalidBacktest(); visit(child, depth + 1) }
  }
  visit(value, 0)
}

const meta = 'algorithm_id strategy_id strategy_version core_version core_wheel_sha256 feature_source_sha256 signal_source_sha256 input_sha256 trace_sha256 source_revision factor_revision signal_profile history_start evaluation_start evaluation_end knowledge_cutoff'
function metadata(value: unknown): asserts value is Json {
  keys(value, meta)
  requireValue(value.strategy_id === 'resonance-regime-v2' && value.strategy_version === '0.1.0'
    && value.algorithm_id === 'resonance-regime-v2@0.1.0/no-cycle-signal-trace-v1'
    && value.signal_profile === 'legacy-backtest-evaluation-range-v1')
  for (const name of ['core_wheel_sha256', 'feature_source_sha256', 'signal_source_sha256', 'input_sha256', 'trace_sha256', 'source_revision', 'factor_revision']) requireValue(sha(value[name]))
  requireValue(date(value.history_start) && date(value.evaluation_start) && date(value.evaluation_end)
    && value.history_start <= value.evaluation_start && value.evaluation_start <= value.evaluation_end)
  requireValue(typeof value.knowledge_cutoff === 'string' && value.knowledge_cutoff === `${value.evaluation_end}T07:00:00Z`)
}
function weights(value: unknown): number {
  requireValue(Array.isArray(value) && value.length === 8)
  let total = 0
  value.forEach((pair, i) => {
    requireValue(Array.isArray(pair) && pair.length === 2 && pair[0] === symbols[i] && finite(pair[1], 0, .25))
    total += pair[1]
  })
  return total
}

/** 已通过有限树准入；对象键顺序不属于JSON事实，数组顺序仍属于事实。 */
function sameJson(left: unknown, right: unknown): boolean {
  if (left === right) return true
  if (Array.isArray(left)) return Array.isArray(right) && left.length === right.length && left.every((v, i) => sameJson(v, right[i]))
  if (!isObject(left) || !isObject(right)) return false
  const names = Object.keys(left)
  return names.length === Object.keys(right).length && names.every(k => Object.hasOwn(right, k) && sameJson(left[k], right[k]))
}

/** 八个非负权重的有限累加允许舍入误差；相对量级比较让零总和保持严格零。
 * 这里只核同一报告的重复事实，精确准入仍由后端原分数表示，不用浮点诊断替代。
 */
function sameTotal(left: number, right: number): boolean {
  return left === right || Math.abs(left - right) <= Number.EPSILON * 16 * Math.max(Math.abs(left), Math.abs(right))
}
function diagnostics(value: unknown, end: unknown): void {
  requireValue(Array.isArray(value) && value.length === 8)
  value.forEach((v, i) => {
    keys(v, 'symbol trade_date price_position volume_ratio change_pct trade_direction regime_score regime_label missing_auxiliary')
    requireValue(v.symbol === symbols[i] && v.trade_date === end)
    for (const k of ['price_position', 'volume_ratio', 'change_pct', 'regime_score']) requireValue(v[k] === null || finite(v[k]))
    requireValue(typeof v.trade_direction === 'string' && ['NEUTRAL', 'ACCUMULATE', 'DISTRIBUTE'].includes(v.trade_direction)
      && (v.regime_label === null || text(v.regime_label, 32)) && Array.isArray(v.missing_auxiliary) && v.missing_auxiliary.length <= 4)
    requireValue(new Set(v.missing_auxiliary).size === v.missing_auxiliary.length)
    for (const name of v.missing_auxiliary) requireValue(typeof name === 'string' && ['shares_delta_yi', 'share_probability', 'turnover_percentile', 'margin_percentile'].includes(name))
  })
}

/** 对固定NVB轻量summary做消费边界校验，保持后端reported raw/policy事实。 */
export function validateV2Summary(value: unknown, tradingDate: number): V2Summary {
  boundedBacktestTree(value)
  keys(value, 'kind pipeline signal_trace stable_spec_sha256 daily_input_sha256 target_admission producer_readiness')
  requireValue(value.kind === 'resonance-v2' && sha(value.stable_spec_sha256) && sha(value.daily_input_sha256))
  const p = value.pipeline; const t = value.signal_trace
  keys(p, 'schema dependencies signal latest_features allocation source_qualified historically_produced execution_qualified scope pipeline_sha256')
  requireValue(p.schema === 'guanheng.v2-history-result.v1' && sha(p.pipeline_sha256) && text(p.scope))
  keys(p.dependencies, 'guanheng-strategy-signals guanheng-strategy-variants tzdata')
  metadata(p.signal)
  // 归档可读两代，完整组绑定实际core wheel摘要，禁止逐字段宽放混代。
  requireValue(packageProfiles.profiles.some(profile => (p.signal as Json).core_version === profile.core_version
    && (p.signal as Json).core_wheel_sha256 === profile.core_wheel_sha256
    && (p.dependencies as Json)['guanheng-strategy-signals'] === profile.signal_version
    && (p.dependencies as Json)['guanheng-strategy-variants'] === profile.variants_version
    && (p.dependencies as Json).tzdata === profile.tzdata_version))
  keys(t, `schema ${meta} feature_series_symbols decision_series latest_features historically_produced source_qualified execution_qualified scope`)
  requireValue(t.schema === 'guanheng.signal-trace.v1' && text(t.scope))
  for (const name of meta.split(' ')) requireValue(t[name] === p.signal[name])
  requireValue(Number(String(t.evaluation_end).replaceAll('-', '')) === tradingDate)
  for (const part of [p, t]) for (const key of ['source_qualified', 'historically_produced', 'execution_qualified']) requireValue(part[key] === false)
  requireValue(Array.isArray(t.feature_series_symbols) && t.feature_series_symbols.length === 8 && t.feature_series_symbols.every((s, i) => s === symbols[i]))
  requireValue(Array.isArray(t.decision_series) && t.decision_series.length === 8)
  t.decision_series.forEach((g, i) => { keys(g, 'symbol decisions'); requireValue(g.symbol === symbols[i] && Array.isArray(g.decisions) && g.decisions.length === 0) })
  diagnostics(p.latest_features, t.evaluation_end); diagnostics(t.latest_features, t.evaluation_end)
  requireValue(sameJson(p.latest_features, t.latest_features))
  const a = p.allocation
  keys(a, 'schema algorithm_id strategy_id strategy_version source_sha256 time_policy timezone_data_sha256 input_sha256 source_revision factor_revision trace_sha256 signal_profile knowledge_cutoff history_start evaluation_start evaluation_end allocation_events latest_event_date latest_raw_weights new_event_for_cutoff state raw_diagnostic execution_qualified scope')
  requireValue(a.schema === 'guanheng.fixed-unit-result.v1' && a.algorithm_id === 'resonance-regime-v2@0.1.0/fixed-unit-source-v1'
    && a.strategy_id === p.signal.strategy_id && a.strategy_version === p.signal.strategy_version && a.execution_qualified === false
    && a.time_policy === 'Asia/Shanghai@IANA2026c' && text(a.scope) && typeof a.new_event_for_cutoff === 'boolean'
    && Array.isArray(a.allocation_events) && a.allocation_events.length === 0)
  for (const name of ['source_sha256', 'timezone_data_sha256', 'input_sha256']) requireValue(sha(a[name]))
  for (const name of ['source_revision', 'factor_revision', 'trace_sha256', 'signal_profile', 'knowledge_cutoff', 'history_start', 'evaluation_start', 'evaluation_end']) requireValue(a[name] === t[name])
  let weightTotal = 0
  if (a.latest_event_date === null) requireValue(a.latest_raw_weights === null)
  else {
    requireValue(date(a.latest_event_date) && typeof t.evaluation_start === 'string' && typeof t.evaluation_end === 'string'
      && a.latest_event_date >= t.evaluation_start && a.latest_event_date <= t.evaluation_end)
    weightTotal = weights(a.latest_raw_weights)
  }
  requireValue(a.new_event_for_cutoff === (a.latest_event_date !== null && a.latest_event_date === t.evaluation_end))
  keys(a.state, 'active_buy_ranks sequence csi300_strength previous_raw_weights')
  requireValue(Number.isSafeInteger(a.state.sequence) && (a.state.sequence as number) >= 0 && (a.state.sequence as number) <= 32768
    && finite(a.state.csi300_strength, 0, 1) && Array.isArray(a.state.active_buy_ranks) && a.state.active_buy_ranks.length <= 7)
  const active = new Set<string>()
  for (const pair of a.state.active_buy_ranks) {
    requireValue(Array.isArray(pair) && pair.length === 2 && typeof pair[0] === 'string' && symbols.includes(pair[0]) && pair[0] !== '510300.SH'
      && !active.has(pair[0]) && Number.isSafeInteger(pair[1]) && pair[1] > 0 && pair[1] <= (a.state.sequence as number)); active.add(pair[0])
  }
  if (a.state.previous_raw_weights !== null) weights(a.state.previous_raw_weights)
  requireValue(sameJson(a.state.previous_raw_weights, a.latest_raw_weights))
  keys(a.raw_diagnostic, 'total_weight pre_risk_capacity exceeds_one exceeds_pre_risk_capacity')
  const raw = a.raw_diagnostic
  requireValue(finite(raw.total_weight, 0, 2) && finite(raw.pre_risk_capacity, Number.MIN_VALUE, 1)
    && typeof raw.exceeds_one === 'boolean' && typeof raw.exceeds_pre_risk_capacity === 'boolean'
    && raw.exceeds_one === (raw.total_weight > 1) && raw.exceeds_pre_risk_capacity === (raw.total_weight > raw.pre_risk_capacity))
  requireValue(sameTotal(weightTotal, raw.total_weight))
  keys(value.target_admission, 'accepted policy_id code raw_total_fraction')
  const admission = value.target_admission
  requireValue(typeof admission.accepted === 'boolean' && admission.policy_id === 'reject-overweight-v1'
    && admission.code === (admission.accepted ? 'accepted' : 'blocked_raw_total')
    && typeof admission.raw_total_fraction === 'string' && /^(?:0|[1-9]\d{0,127})(?:\/[1-9]\d{0,126})?$/.test(admission.raw_total_fraction))
  const [numerator, denominator = '1'] = admission.raw_total_fraction.split('/')
  const n = BigInt(numerator); const d = BigInt(denominator)
  requireValue(admission.accepted === (n <= d) && sameTotal(Number(n) / Number(d), raw.total_weight))
  keys(value.producer_readiness, 'native_input_ready legacy_offline_ready source_qualified historically_produced')
  const readiness = value.producer_readiness
  requireValue(readiness.native_input_ready === true && typeof readiness.legacy_offline_ready === 'boolean'
    && readiness.source_qualified === false && readiness.historically_produced === false)
  return value as unknown as V2Summary
}
