import type { OperationsSnapshot } from './types'

type OperationalAlert = NonNullable<OperationsSnapshot['alerts']>[number]
export type AlertLabels = {
  category: (key: string) => string | undefined
  source: (key: string) => string | undefined
  title: (key: string) => string | undefined
  value: (key: string) => string | undefined
}

function titleFromDynamicKey(labels: AlertLabels, alertKey: string): string | null {
  if (alertKey.startsWith('service:')) return `${formatAlertSource(labels, alertKey.slice(8))}未就绪`
  return null
}

function durationLabel(seconds: number): string {
  if (seconds < 60) return `${seconds < 10 ? seconds.toFixed(1) : Math.round(seconds)} 秒`
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)} 分钟`
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)} 小时`
  return `${(seconds / 86400).toFixed(1)} 天`
}

export function formatAlertCategory(labels: AlertLabels, category: string): string {
  return labels.category(category) ?? `未翻译类别：${category}`
}

export function formatAlertSource(labels: AlertLabels, source: string): string {
  return labels.source(source) ?? source
}

export function formatAlertTitle(labels: AlertLabels, alert: Pick<OperationalAlert, 'alert_key' | 'category'>): string {
  return labels.title(alert.alert_key) ?? titleFromDynamicKey(labels, alert.alert_key)
    ?? `${formatAlertCategory(labels, alert.category)}告警`
}

export function formatAlertValue(labels: AlertLabels, value: OperationalAlert['observed_value'], category: string): string {
  if (value === null || value === undefined || value === '') return '暂无权威值'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'number') {
    if (['qmt_heartbeat_stale', 'account_snapshot_stale', 'quote_stale', 'backup_stale'].includes(category)) {
      return durationLabel(value)
    }
    return String(value)
  }
  const direct = labels.value(value)
  if (direct) return direct
  return value.split(';').map((part) => {
    const [key, detail] = part.split(':', 2)
    if (key === 'affected_symbols') return `影响标的 ${detail} 个`
    if (key === 'date_range') return `日期范围 ${detail?.replace('..', ' 至 ')}`
    if (key === 'bars') return `缺少行情日期 ${detail} 个`
    return labels.value(part) ?? part
  }).join('；')
}

export function formatOperationalAlert(labels: AlertLabels, alert: OperationalAlert) {
  return {
    title: formatAlertTitle(labels, alert),
    category: formatAlertCategory(labels, alert.category),
    source: formatAlertSource(labels, alert.source),
    observed: formatAlertValue(labels, alert.observed_value, alert.category),
    threshold: formatAlertValue(labels, alert.threshold, alert.category),
    rawKey: alert.alert_key,
  }
}
