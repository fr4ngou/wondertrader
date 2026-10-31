import { useEffect, useMemo, useState } from 'react'

const shanghaiFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})

export function absoluteChinaTime(value?: string | null) {
  if (!value) return '时间不可用'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '时间格式不可识别'
  return `${shanghaiFormatter.format(date).replaceAll('/', '-')}（北京时间）`
}

export function relativeTimeLabel(value?: string | null, nowMs = Date.now()) {
  if (!value) return '时间不可用'
  const dateMs = new Date(value).getTime()
  if (Number.isNaN(dateMs)) return '时间格式不可识别'
  const seconds = Math.round((nowMs - dateMs) / 1000)
  if (seconds < -60) return `${Math.ceil(Math.abs(seconds) / 60)} 分钟后`
  if (seconds < 0) return '刚刚（时间略超前）'
  if (seconds < 60) return '刚刚更新'
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前更新`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时前更新`
  return `${Math.floor(seconds / 86400)} 天前更新`
}

export function RelativeTime({
  value,
  staleAfterSeconds,
}: {
  value?: string | null
  staleAfterSeconds?: number
}) {
  const [nowMs, setNowMs] = useState(Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])
  const label = useMemo(() => relativeTimeLabel(value, nowMs), [nowMs, value])
  const ageSeconds = value ? Math.max(0, (nowMs - new Date(value).getTime()) / 1000) : null
  const stale = staleAfterSeconds != null && ageSeconds != null && ageSeconds > staleAfterSeconds
  return (
    <details className={stale ? 'relative-time relative-time-stale' : 'relative-time'}>
      <summary><time dateTime={value ?? undefined}>{stale ? `已过期 · ${label}` : label}</time></summary>
      <span>{absoluteChinaTime(value)}</span>
    </details>
  )
}
