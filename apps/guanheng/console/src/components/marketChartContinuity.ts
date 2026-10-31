import type { MarketChartCandle, MarketChartPeriod } from '../types'

const PERIOD_MILLISECONDS: Record<Exclude<MarketChartPeriod, '1d'>, number> = {
  '1m': 60_000,
  '5m': 300_000,
}

const MAX_CONTIGUOUS_INTERVALS = 3

export interface MarketChartContinuity {
  segments: Array<Array<number | null>>
  gapCount: number
  largestGapMinutes: number | null
}

export function formatMarketGapDuration(minutes: number): string {
  if (minutes >= 1_440) {
    const days = minutes / 1_440
    return `${Number.isInteger(days) ? days.toFixed(0) : days.toFixed(1)} 天`
  }
  if (minutes >= 60) {
    const hours = minutes / 60
    return `${Number.isInteger(hours) ? hours.toFixed(0) : hours.toFixed(1)} 小时`
  }
  return `${minutes} 分钟`
}

/**
 * Split display-only intraday lines where the authoritative timeline is not
 * continuous. Every non-null point remains the exact source close and gaps
 * stay visually empty.
 */
export function buildMarketChartContinuity(
  candles: MarketChartCandle[],
  period: MarketChartPeriod,
): MarketChartContinuity {
  if (candles.length === 0) {
    return { segments: [], gapCount: 0, largestGapMinutes: null }
  }
  if (period === '1d') {
    return {
      segments: [candles.map((item) => item.close)],
      gapCount: 0,
      largestGapMinutes: null,
    }
  }

  const maximumGap = PERIOD_MILLISECONDS[period] * MAX_CONTIGUOUS_INTERVALS
  const segmentRanges: Array<{ start: number; end: number }> = []
  let segmentStart = 0
  let gapCount = 0
  let largestGapMilliseconds = 0

  for (let index = 1; index < candles.length; index += 1) {
    const previous = Date.parse(candles[index - 1].occurred_at)
    const current = Date.parse(candles[index].occurred_at)
    const gap = current - previous
    if (!Number.isFinite(gap) || gap <= 0 || gap > maximumGap) {
      segmentRanges.push({ start: segmentStart, end: index })
      segmentStart = index
      gapCount += 1
      if (Number.isFinite(gap) && gap > largestGapMilliseconds) {
        largestGapMilliseconds = gap
      }
    }
  }
  segmentRanges.push({ start: segmentStart, end: candles.length })

  return {
    segments: segmentRanges.map(({ start, end }) => candles.map((item, index) => (
      index >= start && index < end ? item.close : null
    ))),
    gapCount,
    largestGapMinutes: largestGapMilliseconds > 0
      ? Math.round(largestGapMilliseconds / 60_000)
      : null,
  }
}
