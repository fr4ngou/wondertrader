import type { MarketChartNativeSource } from './types'

/** 原始快照时间随行情显示；读取时间不能充当收盘完成时间。 */
export function sourceCurrentDayNotice(source?: MarketChartNativeSource | null): string | null {
  return source?.current_day
    ? `当日快照 ${new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(new Date(source.current_day.source_at))}`
    : null
}

/** 图表只说明读图所需的时间与成交量口径，内部身份由接口保留。 */
export function sourceChartTimeNotice(source: MarketChartNativeSource): string {
  const time = source.timestamp_semantics === 'source_date' ? '日线按交易日显示' : '时间为北京时间'
  const volume = source.volume_unit === 'share' ? '成交量：股/份'
    : source.volume_unit === 'lot' ? '成交量：手' : '成交量单位待确认'
  const currentNotice = sourceCurrentDayNotice(source)
  const current = currentNotice ? ` · ${currentNotice}` : ''
  return `不复权 · ${time} · ${volume}${current}。`
}

/** 固定交易日时区，避免日期零点标签在其他浏览器时区变成前一天。 */
export function sourceChartDate(value: string, timeZone = 'Asia/Shanghai'): string {
  const parts = new Intl.DateTimeFormat('en', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(value))
  const get = (kind: string) => parts.find(part => part.type === kind)!.value
  return `${get('year')}-${get('month')}-${get('day')}`
}
