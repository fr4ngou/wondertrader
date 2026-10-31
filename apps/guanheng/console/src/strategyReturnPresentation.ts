import type { StrategyCapitalHistory, StrategyCapitalSleeve } from './types'
import { absoluteChinaTime } from './components/RelativeTime'

export const CAPITAL_HISTORY_DEFAULT_DAYS = 30
export const CAPITAL_HISTORY_MAX_DAYS = 90
const DAY_MS = 86_400_000
const dayFormat = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
})
const clockFormat = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
})

export type CapitalHistoryPoint = StrategyCapitalHistory['points'][number]
export interface CapitalHistorySample {
  key: string
  label: string
  day: string
  point: CapitalHistoryPoint | null
  returnValue: number | null
  drawdown: number | null
}

export const finiteNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)

/** Decimal wire values become finite numbers only at the display boundary. */
export function capitalDisplayNumber(value: unknown): number | null {
  if (finiteNumber(value)) return value
  if (typeof value !== 'string' || !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?$/.test(value)) return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

export function capitalReturnMetrics(sleeve?: StrategyCapitalSleeve) {
  const principal = capitalDisplayNumber(sleeve?.contributed_principal)
  const pnl = capitalDisplayNumber(sleeve?.investment_pnl)
  const ratio = capitalDisplayNumber(sleeve?.return_on_principal)
  const available = sleeve?.reconciliation_status === 'reconciled' && sleeve.pnl_metrics_available === true
    && finiteNumber(principal) && principal > 0 && finiteNumber(pnl) && finiteNumber(ratio)
  const reason = !sleeve ? '未取得同一账户边界的策略资本快照。'
    : sleeve.reconciliation_status !== 'reconciled' ? '当前对账受阻，收益指标等待有效资本快照。'
      : finiteNumber(principal) && principal <= 0 ? '投入本金须大于零，当前收益指标不可用。'
        : '当前快照尚未提供完整的投入本金、投资盈亏及收益率。'
  return { principal: available ? principal : null, pnl: available ? pnl : null,
    ratio: available ? ratio : null, available, reason }
}

export function chinaObservationDay(value: string) {
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return null
  const parts = dayFormat.formatToParts(date)
  return ['year', 'month', 'day'].map(type => parts.find(part => part.type === type)!.value).join('-')
}

function sample(point: CapitalHistoryPoint | null, key: string, label: string, day: string): CapitalHistorySample {
  const ready = point?.status === 'ready'
  return { key, label, day, point,
    returnValue: ready && finiteNumber(point.return_on_principal) ? point.return_on_principal : null,
    drawdown: ready && finiteNumber(point.drawdown) ? point.drawdown : null }
}

export function capitalHistorySamples(history: StrategyCapitalHistory): CapitalHistorySample[] {
  if (history.sampling !== 'daily') {
    const days = new Set(history.points.map(point => chinaObservationDay(point.valuation_at)))
    return history.points.map((point, index) => {
      const day = chinaObservationDay(point.valuation_at) ?? '日期不可用'
      const date = new Date(point.valuation_at)
      const clock = Number.isFinite(date.getTime()) ? clockFormat.format(date) : '时间不可用'
      return sample(point, `${point.captured_at}-${index}`, days.size > 1 ? `${day}\n${clock}` : clock, day)
    })
  }
  // The owner has already selected each observed day's last real snapshot.
  // These empty axis slots are presentation gaps, never synthetic capital facts.
  const points = new Map<string, CapitalHistoryPoint>()
  for (const point of history.points) {
    const day = chinaObservationDay(point.captured_at)
    if (day) points.set(day, point)
  }
  const observedDays = [...points.keys()].sort()
  const first = history.window_start ? chinaObservationDay(history.window_start) : observedDays[0]
  const endMs = history.window_end ? Date.parse(history.window_end) : NaN
  const last = Number.isFinite(endMs) ? chinaObservationDay(new Date(endMs - 1).toISOString()) : observedDays.at(-1)
  if (!first || !last) return []
  const startMs = Date.parse(`${first}T00:00:00+08:00`)
  const result: CapitalHistorySample[] = []
  for (let at = startMs; result.length < CAPITAL_HISTORY_MAX_DAYS; at += DAY_MS) {
    const day = chinaObservationDay(new Date(at).toISOString())!
    if (day > last) break
    result.push(sample(points.get(day) ?? null, day, day, day))
  }
  return result
}

export function capitalHistoryTooltip(value: CapitalHistorySample) {
  if (!value.point) return `${value.day}<br/>当日没有保存观察，收益与回撤不可用`
  const point = value.point
  const percent = (number: number | null) => number == null ? '不可用' : `${(number * 100).toFixed(2)}%`
  return `${value.day}<br/>实际估值：${absoluteChinaTime(point.valuation_at)}<br/>保存观察：${absoluteChinaTime(point.captured_at)}`
    + `<br/>${point.status === 'ready' ? '有效估值' : '估值受阻'}<br/>投入本金收益率：${percent(value.returnValue)}`
    + `<br/>回撤：${percent(value.drawdown)}`
}

/** Zero-only observations use a small explicit display range, not 0–100%. */
export function zeroObservationRange(values: Array<number | null>, drawdown = false) {
  const observed = values.filter(finiteNumber)
  return observed.length && observed.every(value => value === 0)
    ? { min: -.001, max: drawdown ? 0 : .001 } : {}
}
