import { archiveConfiguration, fetchBacktestReadJson, tradingDate, validDigest, validId, type ArchiveEntry } from './backtestApi'
import { boundedBacktestTree, invalidBacktest, isObject } from './backtestV2'
import { HISTORICAL_REPORT_SCHEMA, HISTORICAL_SCOPE } from './backtestHistorical'
import { PER_DATE_REPORT_SCHEMA, PER_DATE_SCOPE, RETAINED_REPORT_SCHEMA, RETAINED_SCOPE } from './backtestRetained'

export const differenceNames = {
  window: '回放时间窗口', initial_capital: '初始本金', input: '历史或来源输入', strategy: '策略与版本',
  configuration: '策略配置', model: '回放与资金模型', fees: '费用依据',
} as const
export type Difference = keyof typeof differenceNames
export type BacktestPerformance = {
  schema: 'nbw-performance-v1'; run_id: string; request_id: string; receipt_sha256: string; request_sha256: string
  report_sha256: string; installation_sha256: string; session_sha256: string; session_id: string
  report_schema: 'nsb-report-v2' | 'nsb-v2-report-v1' | 'nsb-historical-report-v1' | typeof RETAINED_REPORT_SCHEMA | typeof PER_DATE_REPORT_SCHEMA; configuration: ArchiveEntry['configuration']
  strategy: { id: string; version: string; algorithm_id: string | null }
  input: { history_sha256: string; market_manifest_source: string; capital_source: string; fee_reserve_cny: string | null
    fee_source: string | null; policy_sha256: string; configuration_sha256: string }
  metrics: { initial_capital_cny: string; last_nav_cny: string | null; total_return_pct: number | null
    observed_max_drawdown_pct: number | null; native_cumulative_fees_cny: string | null }
  observations: { total: number; available: number; missing: number; last_trading_date: number | null }
  points: [number, string | null][]; scope: string
}
export type BacktestComparison = { schema: 'nbw-comparison-v1'; left: BacktestPerformance; right: BacktestPerformance
  differences: Difference[]; scope: string }

function keys(value: unknown, names: string): asserts value is Record<string, unknown> {
  const expected = names.split(' ')
  if (!isObject(value) || Object.keys(value).length !== expected.length || expected.some(k => !Object.hasOwn(value, k))) invalidBacktest()
}
const text = (v: unknown, max = 512): v is string => typeof v === 'string' && v.length > 0 && v.length <= max && !/[\u0000-\u001f]/.test(v)
// 金额保留原十进制文本；画图时单独检查可表示性，避免将超大金额转换为Infinity。
const decimal = (v: unknown): v is string => typeof v === 'string' && v.length <= 512 && /^-?\d+(?:\.\d+)?$/.test(v)
const nullableDecimal = (v: unknown) => v === null || decimal(v)
const nullableNumber = (v: unknown): v is number | null => v === null || typeof v === 'number' && Number.isFinite(v)

/** 校验完整只读投影及归档身份；收益、费用和回撤由服务端原生报告投影拥有。 */
export function validatePerformance(value: unknown, entry: ArchiveEntry): BacktestPerformance {
  keys(value, 'schema run_id request_id receipt_sha256 request_sha256 report_sha256 installation_sha256 session_sha256 session_id report_schema configuration strategy input metrics observations points scope')
  if (value.schema !== 'nbw-performance-v1' || !validId(value.run_id) || !validId(value.request_id)
    || value.run_id !== entry.run_id || value.request_id !== entry.request_id || value.receipt_sha256 !== entry.receipt_sha256
    || value.report_sha256 !== entry.report_sha256 || !text(value.scope)
    || !['nsb-report-v2', 'nsb-v2-report-v1', 'nsb-historical-report-v1', RETAINED_REPORT_SCHEMA, PER_DATE_REPORT_SCHEMA].includes(String(value.report_schema))
    || ['receipt_sha256', 'request_sha256', 'report_sha256', 'installation_sha256', 'session_sha256', 'session_id'].some(k => !validDigest(value[k]))
    || !archiveConfiguration(value.configuration)) invalidBacktest()
  const configuration = value.configuration
  if ((value.report_schema === HISTORICAL_REPORT_SCHEMA) !== (value.scope === HISTORICAL_SCOPE)) invalidBacktest()
  if ((value.report_schema === RETAINED_REPORT_SCHEMA) !== (value.scope === RETAINED_SCOPE)) invalidBacktest()
  if ((value.report_schema === PER_DATE_REPORT_SCHEMA) !== (value.scope === PER_DATE_SCOPE)) invalidBacktest()
  if (Object.entries(entry.configuration).some(([k, v]) => configuration[k as keyof ArchiveEntry['configuration']] !== v)) invalidBacktest()
  keys(value.strategy, 'id version algorithm_id')
  if (!text(value.strategy.id, 256) || !text(value.strategy.version, 256) || value.strategy.algorithm_id !== null && !text(value.strategy.algorithm_id, 512)) invalidBacktest()
  keys(value.input, 'history_sha256 market_manifest_source capital_source fee_reserve_cny fee_source policy_sha256 configuration_sha256')
  const input = value.input
  if (['history_sha256', 'policy_sha256', 'configuration_sha256'].some(k => !validDigest(input[k]))
    || !text(value.input.market_manifest_source) || !text(value.input.capital_source)
    || !nullableDecimal(value.input.fee_reserve_cny) || value.input.fee_source !== null && !text(value.input.fee_source)) invalidBacktest()
  keys(value.metrics, 'initial_capital_cny last_nav_cny total_return_pct observed_max_drawdown_pct native_cumulative_fees_cny')
  const metrics = value.metrics
  if (!decimal(metrics.initial_capital_cny) || metrics.initial_capital_cny.startsWith('-') || !/[1-9]/.test(metrics.initial_capital_cny)
    || !nullableDecimal(metrics.last_nav_cny) || !nullableDecimal(metrics.native_cumulative_fees_cny)
    || typeof metrics.native_cumulative_fees_cny === 'string' && metrics.native_cumulative_fees_cny.startsWith('-')
    || !nullableNumber(metrics.total_return_pct) || !nullableNumber(metrics.observed_max_drawdown_pct)
    || metrics.observed_max_drawdown_pct !== null && metrics.observed_max_drawdown_pct < 0) invalidBacktest()
  keys(value.observations, 'total available missing last_trading_date')
  const observations = value.observations
  if (['total', 'available', 'missing'].some(k => !Number.isInteger(observations[k]) || (observations[k] as number) < 0 || (observations[k] as number) > 4096)
    || observations.total !== entry.record_count || (observations.available as number) + (observations.missing as number) !== observations.total
    || !Array.isArray(value.points) || value.points.length !== observations.total) invalidBacktest()
  let previous = 0; let available = 0; let lastDate: number | null = null; let lastNav: string | null = null
  for (const point of value.points) {
    if (!Array.isArray(point) || point.length !== 2 || !tradingDate(point[0]) || point[0] <= previous || !nullableDecimal(point[1])) invalidBacktest()
    previous = point[0]
    if (point[1] !== null) { available++; lastDate = point[0]; lastNav = point[1] as string }
  }
  if (available !== observations.available || lastDate !== observations.last_trading_date || lastNav !== metrics.last_nav_cny
    || available === 0 && [metrics.total_return_pct, metrics.observed_max_drawdown_pct, metrics.native_cumulative_fees_cny].some(v => v !== null)) invalidBacktest()
  return value as BacktestPerformance
}
export async function fetchBacktestPerformance(entry: ArchiveEntry, signal?: AbortSignal): Promise<BacktestPerformance> {
  if (!validId(entry.run_id) || !validDigest(entry.receipt_sha256)) invalidBacktest()
  const value = await fetchBacktestReadJson<unknown>(`/v1/ui/backtest/archive/${entry.run_id}/performance?receipt_sha256=${entry.receipt_sha256}`, '回测绩效', signal)
  boundedBacktestTree(value)
  return validatePerformance(value, entry)
}
export async function fetchBacktestComparison(left: ArchiveEntry, right: ArchiveEntry, signal?: AbortSignal): Promise<BacktestComparison> {
  if (!validId(left.run_id) || !validId(right.run_id) || left.run_id === right.run_id || !validDigest(left.receipt_sha256) || !validDigest(right.receipt_sha256)) invalidBacktest()
  const query = new URLSearchParams({ left_run_id: left.run_id, left_receipt_sha256: left.receipt_sha256,
    right_run_id: right.run_id, right_receipt_sha256: right.receipt_sha256 })
  const value = await fetchBacktestReadJson<unknown>(`/v1/ui/backtest/comparison?${query}`, '回测比较', signal)
  boundedBacktestTree(value)
  keys(value, 'schema left right differences scope')
  if (value.schema !== 'nbw-comparison-v1' || !text(value.scope) || !Array.isArray(value.differences) || value.differences.length > 7) invalidBacktest()
  const order = Object.keys(differenceNames); let prior = -1
  for (const name of value.differences) {
    const index = order.indexOf(String(name))
    if (index <= prior) invalidBacktest()
    prior = index
  }
  validatePerformance(value.left, left); validatePerformance(value.right, right)
  return value as BacktestComparison
}
