import { beforeAll, describe, expect, test } from 'vitest'

import { connectionStateLabel, diagnosticDefinition, diagnosticLabel } from './diagnosticPresentation'
import { installProblemDictionary } from './problemDictionary'

beforeAll(() => installProblemDictionary({
  schema_version: '1.0',
  definitions: [...[
    ['fresh_quote_unavailable', 'fresh quote unavailable', '当前没有满足委托门禁的新鲜行情'],
    ['heartbeat_stale', 'heartbeat stale', 'AI_ETF 心跳超过订单新鲜度，当前不能委托'],
    ['account_snapshot_stale', 'account snapshot stale', '账户快照超过订单新鲜度，当前不能委托'],
    ['authoritative_account_snapshot_history_unavailable', 'authoritative account snapshot history unavailable', '权威账户快照历史不可用'],
  ].map(([issue_code, alias, title]) => ({
    schema_version: '1.0' as const, issue_code, title, meaning: title, impact: '安全阻断',
    recommended_action: '核对权威来源', fact_source: '测试词典', unavailable_meaning: '不可用',
    registry_version: 'test', updated_at: '2026-09-19T00:00:00Z', match_values: [alias],
  })), {
    schema_version: '1.0', issue_code: 'order_source_date_conflict', title: '订单原始日期冲突',
    meaning: '同一明确命令与券商订单身份对应多个原始委托日期，当前事实无法确认唯一订单来源。',
    impact: '保留订单与资金占用，相关标的和账户的新自动执行保持关闭。',
    recommended_action: '核对 QMT 原始委托日期、命令身份与原账户快照及订单账本；保留现有占用，依据独立受控事实恢复。',
    fact_source: 'Portfolio 原订单与预约账本、QMT 原始委托日期',
    unavailable_meaning: '权威来源不可读取时按覆盖不足处理，不解释为条件已经满足。',
    registry_version: 'test', updated_at: '2026-09-19T00:00:00Z', match_values: [],
  }],
  alert_category_labels: {}, alert_source_labels: {}, alert_titles: {}, alert_value_labels: {},
}))

describe('diagnosticLabel', () => {
  test('translates known QMT diagnostics', () => {
    expect(diagnosticLabel('fresh quote unavailable')).toBe('当前没有满足委托门禁的新鲜行情')
    expect(diagnosticLabel('heartbeat stale')).toBe('AI_ETF 心跳超过订单新鲜度，当前不能委托')
    expect(diagnosticLabel('account snapshot stale')).toBe('账户快照超过订单新鲜度，当前不能委托')
    expect(diagnosticLabel('authoritative account snapshot history unavailable')).toBe('权威账户快照历史不可用')
  })

  test('keeps unknown technical codes out of the primary user-facing label', () => {
    expect(diagnosticLabel('future_new_code')).toBe('诊断说明尚未登记')
  })

  test('explains an original order date conflict without releasing existing occupancy', () => {
    expect(diagnosticLabel('order_source_date_conflict')).toBe('订单原始日期冲突')
    const definition = diagnosticDefinition('order_source_date_conflict')
    expect(definition.meaning).toContain('明确命令与券商订单身份')
    expect(definition.meaning).toContain('多个原始委托日期')
    expect(definition.impact).toContain('保留订单与资金占用')
    expect(definition.impact).toContain('新自动执行保持关闭')
    expect(definition.action).toContain('QMT 原始委托日期、命令身份')
    expect(definition.action).toContain('独立受控事实恢复')
    expect(definition.source).toContain('原订单与预约账本')
  })

  test('uses the caller fallback when no diagnostic exists', () => {
    expect(diagnosticLabel(null, '等待上游状态')).toBe('等待上游状态')
  })

  test('separates recent runtime evidence from strict order freshness', () => {
    expect(connectionStateLabel('agent', 'degraded')).toBe('最近仍运行 · 订单门禁等待')
    expect(connectionStateLabel('account', 'degraded')).toBe('快照仍可读 · 订单门禁等待')
    expect(connectionStateLabel('gateway', 'degraded')).toBe('降级')
    expect(connectionStateLabel('agent', 'stale')).toBe('已过期')
  })
})
