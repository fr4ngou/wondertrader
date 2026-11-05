import { expect, test } from 'vitest'
import { sourceChartDate, sourceChartTimeNotice } from './sourceChartPresentation'
import type { MarketChartNativeSource } from './types'

test('原生日线零点标签按上海交易日展示，与UTC日期分界分别表达', () => {
  expect(sourceChartDate('2026-10-22T16:00:00Z')).toBe('2026-10-23')
  expect(sourceChartDate('2026-10-23T00:00:00+08:00')).toBe('2026-10-23')
  const source = { chart_minute_boundary: 'source_date', timestamp_semantics: 'source_date', volume_unit: 'unknown' } as MarketChartNativeSource
  expect(sourceChartTimeNotice(source)).toBe('不复权 · 日线按交易日显示 · 成交量单位待确认。')
})

test('当日快照沿原源时刻提示，归档日期说明不变', () => {
  const source = { chart_minute_boundary: 'source_date', timestamp_semantics: 'source_date', volume_unit: 'unknown',
    current_day: { date: 20261105, source_at: '2026-11-05T02:31:22Z', observed_at: '2026-11-05T02:32:00Z', closed: false } } as MarketChartNativeSource
  expect(sourceChartTimeNotice(source)).toBe('不复权 · 日线按交易日显示 · 成交量单位待确认 · 当日快照 10:31:22。')
})
