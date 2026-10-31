import { boundedBacktestTree, invalidBacktest, isObject } from './backtestV2'

export const HISTORICAL_REPORT_SCHEMA = 'nsb-historical-report-v1' as const
export const HISTORICAL_SCOPE = 'historical-eod-backtest-only; historical-first-availability/revisions/RT/broker/production-unqualified'
export type HistoricalSummary = Record<string, unknown> & {
  strategy_id: string; strategy_version: string; qualified: false; qualification_reasons: string[]
  historical_model: {
    schema: 'guanheng.historical-eod-model.v1'; dataset_sha256: string; received_at: string
    source_amount_unit: 'unknown'; amount_interpretation: 'assumed-CNY'
    availability_basis: 'assumed-at-model-close'; model_close: 'Asia/Shanghai:15:00'
    historical_first_available: 'unknown'; revision_history: 'unknown'
  }
}
const digest = (v: unknown) => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v)
const text = (v: unknown): v is string => typeof v === 'string' && v.length > 0 && v.length <= 512 && !/[\u0000-\u001f]/.test(v)
function requireValue(value: unknown): asserts value { if (!value) invalidBacktest() }
function exactKeys(value: Record<string, unknown>, names: string) {
  const keys = names.split(' ')
  requireValue(Object.keys(value).length === keys.length && keys.every(k => Object.hasOwn(value, k)))
}

/** 只准入既有回测报告的来源与模型声明；算法和交易资格由报告owner判断。 */
export function validateHistoricalSummary(value: unknown, tradingDate: number): HistoricalSummary {
  boundedBacktestTree(value)
  requireValue(isObject(value))
  exactKeys(value, 'config_sha256 current_targets factor_revision first_ready_date historical_model input_sha256 kernel_version knowledge_cutoff last_closed_date latest_features qualification_reasons qualified signal_states source_revision strategy_id strategy_version')
  const day = String(tradingDate)
  const date = `${day.slice(0, 4)}-${day.slice(4, 6)}-${day.slice(6, 8)}`
  requireValue(value.last_closed_date === date && value.knowledge_cutoff === `${date}T07:00:00Z`
    && value.qualified === false && text(value.strategy_id) && text(value.strategy_version) && text(value.kernel_version))
  for (const key of ['config_sha256', 'factor_revision', 'input_sha256', 'source_revision']) requireValue(digest(value[key]))
  requireValue(Array.isArray(value.qualification_reasons) && value.qualification_reasons.length > 0
    && value.qualification_reasons.length <= 64 && value.qualification_reasons.every(text))
  const model = value.historical_model
  requireValue(isObject(model))
  exactKeys(model, 'schema dataset_sha256 received_at source_amount_unit amount_interpretation availability_basis model_close historical_first_available revision_history')
  requireValue(model.schema === 'guanheng.historical-eod-model.v1' && digest(model.dataset_sha256)
    && model.dataset_sha256 === value.source_revision && model.source_amount_unit === 'unknown'
    && model.amount_interpretation === 'assumed-CNY' && model.availability_basis === 'assumed-at-model-close'
    && model.model_close === 'Asia/Shanghai:15:00' && model.historical_first_available === 'unknown' && model.revision_history === 'unknown')
  // 报告由领域值规范为UTC；校验显式时区及日期，页面始终按上海时间显示。
  requireValue(typeof model.received_at === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(model.received_at))
  const received = new Date(model.received_at)
  requireValue(Number.isFinite(received.getTime()) && received.toISOString().slice(0, 19) === model.received_at.slice(0, 19)
    && received.getTime() >= Date.parse(`${date}T07:00:00Z`))
  requireValue(Array.isArray(value.latest_features) && value.latest_features.length === 8
    && value.latest_features.every(feature => isObject(feature) && isObject(feature.observation)
      && feature.observation.trade_date === date && feature.observation.market_available_at === null))
  for (const key of ['current_targets', 'signal_states']) requireValue(Array.isArray(value[key]) && value[key].length <= 8)
  return value as HistoricalSummary
}
