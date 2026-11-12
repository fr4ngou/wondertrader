import type { MarketChartBundle, MarketChartPeriod } from '../types'
import type { AccountGroup, AccountRow } from './accountApi'
import { sourceChartDate } from '../sourceChartPresentation'

const dayMs = 86_400_000
const minuteMs = 60_000
const exchangeSuffix: Record<string, string> = { SH: 'SH', SSE: 'SH', SZ: 'SZ', SZSE: 'SZ', BJ: 'BJ', BSE: 'BJ' }

export function accountSecuritySymbol(row: AccountRow): string | undefined {
  const id = row.identity
  const exchange = exchangeSuffix[id.m_strExchangeID?.trim().toUpperCase()]
  const symbol = (id.wt_symbol ?? (exchange ? `${id.m_strInstrumentID}.${exchange}` : '')).trim().toUpperCase()
  return /^\d{6}\.(SH|SZ|BJ)$/.test(symbol) ? symbol : undefined
}

function numberField(row: AccountRow, key: string): number | null {
  const field = row.fields[key]
  if (field?.availability !== 'present' || field.value === null || String(field.value).trim() === '') return null
  const value = Number(field.value)
  return Number.isFinite(value) ? value : null
}

export function heldAccountSymbols(group?: AccountGroup): string[] {
  if (group?.status !== 'complete') return []
  const symbols = new Set<string>()
  for (const row of group.rows) {
    const symbol = accountSecuritySymbol(row)
    if (symbol && (numberField(row, 'quantity') ?? 0) > 0) symbols.add(symbol)
  }
  return [...symbols]
}

export type AccountFill = {
  /** 真实成交所属上海交易日期及已验证的北京时间；分钟图要求时间明确。 */
  day: string
  occurredAt: number | null
  /** 仅按成交回报确认的买卖方向及原始金额，未知值保持空。 */
  side: 'buy' | 'sell'
  amount: number | null
}

export function accountFills(group: AccountGroup | undefined, symbol: string): AccountFill[] {
  if (group?.status !== 'complete' || !symbol) return []
  const seen = new Set<string>()
  return group.rows.flatMap(row => {
    if (accountSecuritySymbol(row) !== symbol) return []
    const side = numberField(row, 'side')
    if (side !== 48 && side !== 49) return []
    const date = row.fields.date?.availability === 'present' ? String(row.fields.date.value).replaceAll('-', '') : ''
    if (!/^\d{8}$/.test(date)) return []
    const day = `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6)}`
    const midnight = new Date(`${day}T00:00:00Z`)
    if (!Number.isFinite(+midnight) || midnight.toISOString().slice(0, 10) !== day) return []
    const time = row.fields.time?.availability === 'present' ? String(row.fields.time.value).replaceAll(':', '') : ''
    const clock = /^\d{1,6}$/.test(time) ? time.padStart(6, '0') : ''
    const stamp = clock && Number(clock.slice(0, 2)) < 24 && Number(clock.slice(2, 4)) < 60 && Number(clock.slice(4)) < 60
      ? Date.parse(`${day}T${clock.slice(0, 2)}:${clock.slice(2, 4)}:${clock.slice(4)}+08:00`) : NaN
    const identity = row.identity.m_strTradeID?.trim()
    const key = identity ? `${day}:${identity}` : null
    if (key && seen.has(key)) return []
    if (key) seen.add(key)
    const amount = numberField(row, 'amount')
    return [{ day, occurredAt: Number.isFinite(stamp) ? stamp : null, side: side === 48 ? 'buy' as const : 'sell' as const,
      amount: amount !== null && amount >= 0 ? amount : null }]
  })
}

function dailyKey(day: string, period: MarketChartPeriod): string {
  if (period === '1mo') return day.slice(0, 7)
  if (period !== '1w') return day
  const stamp = new Date(`${day}T00:00:00Z`)
  return String(+stamp - ((stamp.getUTCDay() + 6) % 7) * dayMs)
}

/** 保持缺口，成交落不到已取得的K线时不跳到相邻柱。 */
export function mapAccountFills(bundle: MarketChartBundle, fills: readonly AccountFill[]) {
  const { period, candles, native_source: source } = bundle
  const intraday = period === '1m' || period === '5m'
  const step = (period === '5m' ? 5 : 1) * minuteMs
  const right = source?.chart_minute_boundary === 'source_label' && source.source_minute_boundary === 'right'
  const candleDays = intraday ? [] : candles.map(candle => sourceChartDate(candle.occurred_at, source?.timezone))
  const firstSourceDay = bundle.first_source_at ? sourceChartDate(bundle.first_source_at, source?.timezone) : undefined
  const indexByKey = new Map(candles.map((candle, index) => [
    intraday ? String(Date.parse(candle.occurred_at)) : dailyKey(candleDays[index], period), index,
  ]))
  const markers = new Map<string, { index: number; side: AccountFill['side']; amounts: (number | null)[] }>()
  for (const fill of fills) {
    if (intraday && fill.occurredAt === null) continue
    if (firstSourceDay && fill.day < firstSourceDay) continue
    const bucket = intraday
      ? String((right ? Math.ceil(fill.occurredAt! / step) : Math.floor(fill.occurredAt! / step)) * step)
      : dailyKey(fill.day, period)
    const index = indexByKey.get(bucket)
    if (index === undefined || !intraday && fill.day > candleDays[index]) continue
    const key = `${index}:${fill.side}`
    const existing = markers.get(key)
    if (existing) existing.amounts.push(fill.amount)
    else markers.set(key, { index, side: fill.side, amounts: [fill.amount] })
  }
  return [...markers.values()]
}
