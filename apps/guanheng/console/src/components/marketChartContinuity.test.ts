import { expect, test } from 'vitest'

import type { MarketChartCandle } from '../types'
import { buildMarketChartContinuity, formatMarketGapDuration } from './marketChartContinuity'

function candle(occurredAt: string, close: number): MarketChartCandle {
  return {
    occurred_at: occurredAt,
    open: close,
    high: close,
    low: close,
    close,
    volume: null,
  }
}

test('keeps a continuous one-minute sequence in one exact segment', () => {
  const result = buildMarketChartContinuity([
    candle('2026-08-14T01:30:00Z', 4.70),
    candle('2026-08-14T01:31:00Z', 4.71),
    candle('2026-08-14T01:32:00Z', 4.72),
  ], '1m')

  expect(result).toEqual({
    segments: [[4.70, 4.71, 4.72]],
    gapCount: 0,
    largestGapMinutes: null,
  })
})

test('breaks an intraday line across a missing authoritative interval', () => {
  const result = buildMarketChartContinuity([
    candle('2026-08-04T02:01:00Z', 4.60),
    candle('2026-08-04T02:02:00Z', 4.61),
    candle('2026-08-14T03:24:00Z', 4.71),
  ], '1m')

  expect(result.segments).toEqual([
    [4.60, 4.61, null],
    [null, null, 4.71],
  ])
  expect(result.gapCount).toBe(1)
  expect(result.largestGapMinutes).toBe(14_482)
})

test('uses the selected period to distinguish delayed bars from a real gap', () => {
  const candles = [
    candle('2026-08-14T01:30:00Z', 4.70),
    candle('2026-08-14T01:40:00Z', 4.71),
    candle('2026-08-14T02:00:00Z', 4.72),
  ]

  const result = buildMarketChartContinuity(candles, '5m')

  expect(result.gapCount).toBe(1)
  expect(result.segments).toEqual([
    [4.70, 4.71, null],
    [null, null, 4.72],
  ])
})

test('does not split authoritative daily candles across non-trading days', () => {
  const result = buildMarketChartContinuity([
    candle('2026-08-07T07:00:00Z', 4.60),
    candle('2026-08-10T07:00:00Z', 4.71),
  ], '1d')

  expect(result).toEqual({
    segments: [[4.60, 4.71]],
    gapCount: 0,
    largestGapMinutes: null,
  })
})

test('formats long gaps for people without changing the retained minute fact', () => {
  expect(formatMarketGapDuration(14_482)).toBe('10.1 天')
  expect(formatMarketGapDuration(90)).toBe('1.5 小时')
  expect(formatMarketGapDuration(12)).toBe('12 分钟')
})
