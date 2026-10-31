import type { MarketChartNativeSource } from './types'

/** 图表只说明读图所需的时间与成交量口径，内部身份由接口保留。 */
export function sourceChartTimeNotice(source: MarketChartNativeSource): string {
  const time = source.timestamp_semantics === 'source_date' ? '日线按交易日显示' : '时间为北京时间'
  const volume = source.volume_unit === 'share' ? '成交量：股/份'
    : source.volume_unit === 'lot' ? '成交量：手' : '成交量单位待确认'
  return `不复权 · ${time} · ${volume}。`
}

/** 固定交易日时区，避免日期零点标签在其他浏览器时区变成前一天。 */
export function sourceChartDate(value: string, timeZone = 'Asia/Shanghai'): string {
  const parts = new Intl.DateTimeFormat('en', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(value))
  const get = (kind: string) => parts.find(part => part.type === kind)!.value
  return `${get('year')}-${get('month')}-${get('day')}`
}
