import { AlertTriangle, Clock3 } from 'lucide-react'

export function ageLabel(seconds: number) {
  if (seconds < 60) return `${Math.max(0, Math.round(seconds))} 秒前`
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟前`
  if (seconds < 86400) return `${Math.round(seconds / 3600)} 小时前`
  return `${Math.round(seconds / 86400)} 天前`
}

export function snapshotFreshnessLabel(stale: boolean, ageSeconds: number) {
  return stale ? `最后快照 · ${ageLabel(ageSeconds)} · 已过期` : `最新快照 · ${ageLabel(ageSeconds)}`
}

export function SnapshotFreshness({ stale, ageSeconds }: { stale: boolean; ageSeconds: number }) {
  const Icon = stale ? AlertTriangle : Clock3
  return (
    <span className={stale ? 'snapshot-freshness snapshot-freshness-stale' : 'snapshot-freshness'}>
      <Icon size={12} aria-hidden="true" />
      {snapshotFreshnessLabel(stale, ageSeconds)}
    </span>
  )
}
