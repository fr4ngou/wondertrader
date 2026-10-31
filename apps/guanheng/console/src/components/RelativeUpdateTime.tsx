import { useEffect, useState } from 'react'

const formatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
})

function duration(value: number, future = false) {
  const seconds = Math.max(0, Math.round(value / 1000))
  if (seconds < 60) return future ? `${seconds} 秒` : '不到 1 分钟'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} 分钟`
  const hours = Math.round(minutes / 60)
  if (hours < 48) return `${hours} 小时`
  return `${Math.round(hours / 24)} 天`
}

export function relativeUpdateText(value: string | null, now: number, freshnessThresholdSeconds: number | null) {
  if (!value) return { state: 'missing', primary: '暂无更新时间', exact: null }
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) return { state: 'invalid', primary: '时间格式异常', exact: null }
  const exact = `北京时间 ${formatter.format(timestamp)}`
  const age = now - timestamp
  if (age < 0) return { state: 'future', primary: `时间异常 · 比当前时间晚 ${duration(-age, true)}`, exact }
  if (freshnessThresholdSeconds !== null && age > freshnessThresholdSeconds * 1000) {
    return { state: 'expired', primary: `已过期 · 已 ${duration(age)}未更新`, exact }
  }
  if (age < 60_000) return { state: 'current', primary: '刚刚更新', exact }
  return { state: 'current', primary: `${duration(age)}前更新`, exact }
}

export function RelativeUpdateTime({ value, freshnessThresholdSeconds = null }: {
  value: string | null
  freshnessThresholdSeconds?: number | null
}) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])
  const display = relativeUpdateText(value, now, freshnessThresholdSeconds)
  return <span className={`relative-update-time relative-update-time--${display.state}`} title={display.exact ?? undefined}>
    <span className="relative-update-time__primary">{display.primary}</span>
    {display.exact && <time className="relative-update-time__exact" dateTime={value!}>{display.exact}</time>}
  </span>
}
