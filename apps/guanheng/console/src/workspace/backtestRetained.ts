import { boundedBacktestTree, invalidBacktest, isObject } from './backtestV2'

export const RETAINED_REPORT_SCHEMA = 'guanheng.retained-replay-report.v1' as const
export const PER_DATE_REPORT_SCHEMA = 'guanheng.retained-per-date-replay-report.v1' as const
export const PER_DATE_SCOPE = 'per-date-front-ratio-reconstruction; historical-15:00-assumed; availability/revisions-unknown; RT/broker/production-unqualified'
export const isRetainedReport = (schema: unknown) => schema === RETAINED_REPORT_SCHEMA || schema === PER_DATE_REPORT_SCHEMA
export const RETAINED_SCOPE = 'retained-historical-backtest-only; final-basis/availability-assumed; RT/broker/production-unqualified'
export const retainedSymbols = ['159780.SZ', '510050.SH', '510300.SH', '510500.SH', '512100.SH', '515080.SH', '588000.SH', '589000.SH']
export type RetainedSummary = Record<string, unknown> & { strategy_id: 'resonance-regime-v1'; strategy_version: '1.1.2'; targets: Record<string, number>; exit_paths: Record<string, string> }
const sha = (value: unknown) => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)
const finite = (v: unknown, low: number, high: number): v is number => typeof v === 'number' && Number.isFinite(v) && v >= low && v <= high
function need(value: unknown): asserts value { if (!value) invalidBacktest() }
function keys(value: unknown, names: string): asserts value is Record<string, unknown> {
  need(isObject(value)); const expected = names.split(' ')
  need(Object.keys(value).length === expected.length && expected.every(k => Object.hasOwn(value, k)))
}
function date(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const parsed = new Date(`${value}T00:00:00Z`)
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}

/** 逐日窗口只核传输身份和时点；来源及财务事实由服务端WT报告准入拥有。 */
export function validatePerDateWindow(value: unknown, tradingDate: number, summary: unknown) {
  keys(value, 'manifest_sha256 window_sha256 basis_date factor_revision known_at received_at native_output_sha256')
  for (const name of ['manifest_sha256', 'window_sha256', 'factor_revision', 'native_output_sha256']) need(sha(value[name]))
  const day = String(tradingDate); const current = `${day.slice(0, 4)}-${day.slice(4, 6)}-${day.slice(6, 8)}`
  need(value.basis_date === current)
  const clock = (time: unknown) => {
    need(typeof time === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/.test(time))
    const parsed = Date.parse(time)
    need(Number.isFinite(parsed) && date(time.slice(0, 10)))
    return parsed
  }
  const received = clock(value.received_at)
  need(clock(value.known_at) <= received && received >= Date.parse(`${current}T07:00:00Z`))
  if (summary !== null) {
    need(isObject(summary) && isObject(summary.historical_model))
    const model = summary.historical_model
    need(model.basis_date === current && model.factor_sha256 === value.factor_revision && clock(model.received_at) === received)
  }
}

/** 有限传输值准入；策略与数量计算由原报告拥有。 */
export function validateRetainedSummary(value: unknown, tradingDate: number): RetainedSummary {
  boundedBacktestTree(value)
  keys(value, 'schema strategy_id strategy_version full_result_sha256 input_sha256 configuration_sha256 decision_cutoff current_view budget_fraction targets source_allocation_date exit_paths next_exits holding_days reference_prices model_states analysis_source_kind source_qualified execution_qualified historical_model')
  const day = String(tradingDate); const current = `${day.slice(0, 4)}-${day.slice(4, 6)}-${day.slice(6, 8)}`
  need(value.schema === 'guanheng.retained-replay-decision.v1' && value.strategy_id === 'resonance-regime-v1' && value.strategy_version === '1.1.2'
    && value.decision_cutoff === `${current}T07:00:00Z` && value.source_qualified === false && value.execution_qualified === false)
  for (const key of ['full_result_sha256', 'input_sha256', 'configuration_sha256']) need(sha(value[key]))
  const model = value.historical_model
  keys(model, 'schema adjustment_basis availability_basis basis_date dataset_sha256 factor_sha256 historical_first_available received_at revision_history scope')
  need(model.schema === 'guanheng.retained-historical-model.v1' && model.adjustment_basis === 'final-batch-front-ratio'
    && model.availability_basis === 'assumed-at-Asia/Shanghai:15:00' && model.historical_first_available === 'unknown'
    && model.revision_history === 'unknown' && model.scope === 'historical-backtest-only' && date(model.basis_date) && model.basis_date >= current
    && sha(model.dataset_sha256) && sha(model.factor_sha256))
  need(typeof model.received_at === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(model.received_at))
  const received = new Date(model.received_at)
  need(Number.isFinite(received.getTime()) && received.toISOString().slice(0, 19) === model.received_at.slice(0, 19)
    && received.getTime() >= Date.parse(`${model.basis_date}T07:00:00Z`))
  const view = value.current_view
  keys(view, 'dataset_sha256 received_at history_basis historical_first_available revision_history source_amount_unit amount_usage')
  need(view.dataset_sha256 === model.dataset_sha256 && view.received_at === model.received_at && view.history_basis === 'current-visible-reconstruction'
    && view.historical_first_available === 'unknown' && view.revision_history === 'unknown' && view.source_amount_unit === 'unknown' && view.amount_usage === 'unused')
  need(finite(value.budget_fraction, Number.MIN_VALUE, .95))
  keys(value.targets, retainedSymbols.join(' '))
  for (const weight of Object.values(value.targets)) need(finite(weight, 0, Math.min(.25, value.budget_fraction)))
  need(Object.values(value.targets).reduce<number>((total, w) => total + (w as number), 0) <= 1)
  need(value.source_allocation_date === null ? Object.values(value.targets).every(w => w === 0) : date(value.source_allocation_date) && value.source_allocation_date <= current)
  need(['synthetic-model', 'qmt-native-verified'].includes(String(value.analysis_source_kind)))
  keys(value.model_states, retainedSymbols.join(' '))
  for (const key of ['holding_days', 'reference_prices', 'exit_paths']) need(isObject(value[key]) && Object.keys(value[key]).every(s => retainedSymbols.includes(s) && s !== '510300.SH'))
  need(Object.values(value.holding_days as Record<string, unknown>).every(v => Number.isSafeInteger(v) && finite(v, 0, 4096)))
  need(Object.values(value.reference_prices as Record<string, unknown>).every(v => finite(v, Number.MIN_VALUE, Number.MAX_VALUE)))
  const exits = value.exit_paths as Record<string, unknown>
  need(Object.values(exits).every(v => typeof v === 'string' && v.length > 0 && v.length <= 256 && !/[\u0000-\u001f]/.test(v)))
  need(Array.isArray(value.next_exits) && value.next_exits.length === Object.keys(exits).length && value.next_exits.length <= 7)
  const seen = new Set<string>()
  for (const item of value.next_exits) {
    keys(item, 'symbol cycle_id trade_date path')
    need(typeof item.symbol === 'string' && Object.hasOwn(exits, item.symbol) && !seen.has(item.symbol)
      && typeof item.cycle_id === 'string' && item.cycle_id.length > 0 && item.cycle_id.length <= 256
      && date(item.trade_date) && item.trade_date <= current && item.path === exits[item.symbol])
    seen.add(item.symbol)
  }
  return value as RetainedSummary
}
