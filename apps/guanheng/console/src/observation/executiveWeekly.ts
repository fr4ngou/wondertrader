import { fetchMarketChart } from '../api'
import type { Range, Row } from './types'

export const WEEKLY_INDEXES = [
  { symbol: '000985.SH', name: '中证全指', color: '#df831f' },
  { symbol: '000001.SH', name: '上证指数', color: '#315288' },
  { symbol: '399006.SZ', name: '创业板指', color: '#86529a' },
  { symbol: '000688.SH', name: '科创50', color: '#118973' },
] as const
export type WeeklyIndex = typeof WEEKLY_INDEXES[number]['symbol']
export type DailyClose = {
  /** 上海交易日，ISO日历日期。 */ date: string
  /** 指数原始收盘点位。 */ close: number
}
export type ExecutiveWeek = {
  /** 上海自然周周一，ISO日历日期。 */ monday: string
  /** ISO周编号，跨年周使用周所属年份。 */ label: string
  /** 所选范围实际纳入的第一天。 */ start: string
  /** 所选范围实际纳入的最后一天。 */ end: string
  /** 已确认减持额减增持额，单位亿元；缺日或金额未知时为空。 */ netSales: number | null
  /** 缺少历史价格的股东公告笔数；本周净额只显示可计价小计。 */ unpriced: number
  /** 使用历史收盘价估算的公告笔数。 */ estimated: number
  /** 各指数本周最后一条已闭合收盘点位，整周缺失时无键。 */ closes: Partial<Record<WeeklyIndex, number>>
  /** 周首或周尾超出查询/披露覆盖，或本周尚未结束。 */ partial: boolean
}

const DAY = 86_400_000
const dateOf = (time: number) => new Date(time).toISOString().slice(0, 10)
const stamp = (date: string) => Date.parse(date + 'T00:00:00Z')
const shanghai = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' })
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)

function mondayOf(time: number) {
  return time - ((new Date(time).getUTCDay() + 6) % 7) * DAY
}

function isoWeek(monday: number) {
  const year = new Date(monday + 3 * DAY).getUTCFullYear()
  const first = mondayOf(Date.UTC(year, 0, 4))
  return `${year}W${Math.round((monday - first) / (7 * DAY)) + 1}`
}

/** 使用原行情只读分页，含端点查询每次退到前页首日之前。 */
export async function readWeeklyIndex(symbol: WeeklyIndex, range: Range, signal: AbortSignal): Promise<DailyClose[]> {
  const pageSize = 2000
  let end = range.end
  const rows: DailyClose[] = []
  while (end >= range.start) {
    const bundle = await fetchMarketChart(symbol, '1d', undefined, signal, pageSize, `${end}T23:59:59+08:00`)
    if (bundle.symbol !== symbol || bundle.period !== '1d' || bundle.source_kind !== 'wondertrader') throw new Error('指数日线身份无效')
    const current = bundle.native_source?.current_day
    let previous = ''
    let first = ''
    for (const candle of bundle.candles) {
      const date = shanghai.format(new Date(candle.occurred_at))
      if (date <= previous || date > end) throw new Error('指数日线日期无效')
      first ||= date
      previous = date
      if (date >= range.start && !(current && !current.closed && date.replaceAll('-', '') === String(current.date))
        && finite(candle.close) && candle.close > 0) rows.push({ date, close: candle.close })
    }
    if (bundle.candles.length < pageSize || first <= range.start) break
    end = dateOf(stamp(first) - DAY)
  }
  return rows.sort((a, b) => a.date.localeCompare(b.date))
}

/** 日披露覆盖按自然日连续检查，指数只采用本周最后一个有效闭合收盘。 */
export function buildExecutiveWeeks(rows: Row[], indexes: Partial<Record<WeeklyIndex, DailyClose[]>>, range: Range, coverage: Range, today: string): ExecutiveWeek[] {
  const start = stamp(range.start)
  const end = stamp(range.end)
  const byDate = new Map(rows.map(row => [row.date, row]))
  const weeks = new Map<string, ExecutiveWeek>()
  for (let monday = mondayOf(start); monday <= end; monday += 7 * DAY) {
    const from = Math.max(monday, start, stamp(coverage.start))
    const to = Math.min(monday + 6 * DAY, end, stamp(coverage.end))
    let sum = 0
    let unpriced = 0
    let estimated = 0
    let complete = from <= to
    for (let day = from; day <= to; day += DAY) {
      const row = byDate.get(dateOf(day))
      const amount = row?.net_amount_cny
      if (finite(amount)) sum -= amount
      else complete = false
      if (finite(row?.unpriced_count)) unpriced += row.unpriced_count
      if (finite(row?.estimated_count)) estimated += row.estimated_count
    }
    const date = dateOf(monday)
    weeks.set(date, {
      monday: date, label: isoWeek(monday), start: dateOf(Math.max(monday, start)), end: dateOf(Math.min(monday + 6 * DAY, end)),
      netSales: complete ? sum / 100_000_000 : null, unpriced, estimated, closes: {},
      partial: from > monday || to < monday + 6 * DAY || dateOf(monday + 6 * DAY) >= today,
    })
  }
  for (const { symbol } of WEEKLY_INDEXES) {
    for (const { date, close } of indexes[symbol] ?? []) {
      const week = weeks.get(dateOf(mondayOf(stamp(date))))
      if (week && date >= week.start && date <= week.end && finite(close) && close > 0) week.closes[symbol] = close
    }
  }
  return [...weeks.values()]
}

export function executiveWeekStats(weeks: ExecutiveWeek[], indexBasis: 'return' | 'level' = 'return') {
  const values: number[] = []
  const pairs: [number, number][] = []
  for (const [i, week] of weeks.entries()) {
    if (week.partial || week.unpriced || week.netSales === null) continue
    values.push(week.netSales)
    const previous = weeks[i - 1]
    const base = previous?.closes['000985.SH']
    const close = week.closes['000985.SH']
    if (indexBasis === 'level' && close) pairs.push([week.netSales, close])
    if (indexBasis === 'return' && previous && !previous.partial && stamp(week.monday) - stamp(previous.monday) === 7 * DAY && base && close) pairs.push([week.netSales, close / base - 1])
  }
  const count = pairs.length
  const average = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null
  const sumX = pairs.reduce((sum, [x]) => sum + x, 0)
  const sumY = pairs.reduce((sum, [, y]) => sum + y, 0)
  let covariance = 0
  let varianceX = 0
  let varianceY = 0
  for (const [x, y] of pairs) {
    const dx = x - sumX / count
    const dy = y - sumY / count
    covariance += dx * dy
    varianceX += dx * dx
    varianceY += dy * dy
  }
  const divisor = Math.sqrt(varianceX * varianceY)
  return { average, count, correlation: count > 1 && divisor > 0 ? covariance / divisor : null }
}

export function shanghaiToday() {
  return shanghai.format(new Date())
}
