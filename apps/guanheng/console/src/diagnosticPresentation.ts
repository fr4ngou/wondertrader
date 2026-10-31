import { problemDefinitionFor } from './problemDictionary'
import type { QMTConnectionLayerState } from './types'

export type DiagnosticDefinition = {
  title: string
  meaning: string
  impact: string
  action: string
  source: string
}

const UNKNOWN_DIAGNOSTIC: DiagnosticDefinition = {
  title: '诊断说明尚未登记',
  meaning: '平台返回了尚未进入中文问题词典的技术状态。',
  impact: '该状态按不可用处理，不解释为正常。',
  action: '在技术详情中复制代码，并补充问题词典后再判断。',
  source: 'Console BFF 中文问题词典',
}

const CONNECTION_STATE_LABELS: Record<QMTConnectionLayerState, string> = {
  online: '在线', busy: '繁忙', degraded: '降级', stale: '已过期', offline: '离线',
  unavailable: '无权威数据', not_exposed: 'QMT 未提供',
}

export function connectionStateLabel(
  layer: 'gateway' | 'agent' | 'trading_server' | 'account',
  state: QMTConnectionLayerState,
): string {
  if (state === 'degraded' && layer === 'agent') return '最近仍运行 · 订单门禁等待'
  if (state === 'degraded' && layer === 'account') return '快照仍可读 · 订单门禁等待'
  return CONNECTION_STATE_LABELS[state]
}

export function diagnosticLabel(value?: string | null, fallback = '暂无权威说明'): string {
  if (!value) return fallback
  return diagnosticDefinition(value).title
}

export function diagnosticDefinition(value?: string | null): DiagnosticDefinition {
  const definition = value ? problemDefinitionFor(value) : undefined
  if (!definition) return UNKNOWN_DIAGNOSTIC
  return {
    title: definition.title,
    meaning: definition.meaning,
    impact: definition.impact,
    action: definition.recommended_action,
    source: definition.fact_source,
  }
}
