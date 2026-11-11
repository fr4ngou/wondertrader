import { expect, test } from 'vitest'
import { buildExecutiveWeeks, executiveWeekStats } from './executiveWeekly'

test('跨年按 ISO 周汇总净减持，金额空白保留，最后收盘落在本周', () => {
  const range = { start: '2025-12-29', end: '2026-01-12' }
  const amounts = [
    ['2025-12-29', -200_000_000], ['2025-12-30', 100_000_000], ['2025-12-31', 0],
    ['2026-01-01', 0], ['2026-01-02', 0], ['2026-01-03', 0], ['2026-01-04', 0],
    ['2026-01-05', 0], ['2026-01-06', 0], ['2026-01-07', null],
    ['2026-01-08', 0], ['2026-01-09', 0], ['2026-01-10', 0], ['2026-01-11', 0],
    ['2026-01-12', 300_000_000],
  ] as const
  const rows = amounts.map(([date, net_amount_cny]) => ({ date, net_amount_cny }))
  const weeks = buildExecutiveWeeks(rows, {
    '000985.SH': [{ date: '2025-12-30', close: 120 }, { date: '2025-12-31', close: 100 }, { date: '2026-01-09', close: 110 }],
  }, range, range, '2026-01-12')
  expect(weeks.map(week => [week.label, week.netSales, week.partial, week.closes['000985.SH']])).toEqual([
    ['2026W1', 1, false, 100], ['2026W2', null, false, 110], ['2026W3', -3, true, undefined],
  ])
  expect(executiveWeekStats(weeks)).toEqual({ average: 1, correlation: null, count: 0 })
})

test('只有本周和上一完整周都有中证全指收盘时才计算该周收益', () => {
  const days = (count: number) => Array.from({ length: count }, (_, offset) => {
    const date = new Date(Date.UTC(2026, 0, 5 + offset)).toISOString().slice(0, 10)
    return { date, net_amount_cny: -100_000_000 * Math.floor(offset / 7) }
  })
  const range = { start: '2026-01-05', end: '2026-02-01' }
  const rows = days(28)
  const weeks = buildExecutiveWeeks(rows, { '000985.SH': [
    { date: '2026-01-09', close: 100 }, { date: '2026-01-16', close: 110 },
    { date: '2026-01-23', close: 132 }, { date: '2026-01-30', close: 171.6 },
  ] }, range, range, '2026-02-02')
  expect(executiveWeekStats(weeks)).toEqual({ average: 10.5, count: 3, correlation: expect.closeTo(1) })
  expect(executiveWeekStats(weeks.filter(week => week.label !== '2026W3')).count).toBe(1)
})
