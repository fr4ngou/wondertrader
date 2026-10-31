import { describe, expect, it } from 'vitest'

import { queueDayLabel, queueProgressLabel, queueStageLabel, summarizeExecutionQueue } from './executionQueuePresentation'
import type { ExecutionQueueItem, ExecutionQueueProjection } from './types'

const baseItem: ExecutionQueueItem = {
  schema_version: '1.0',
  queue_item_id: '00000000-0000-4000-8000-000000000001',
  correlation_id: '00000000-0000-4000-8000-000000000002',
  identity: { source_kind: 'automatic_strategy' },
  strategy_id: 'strategy-a',
  strategy_version: '1.0.0',
  symbol: '510300.SH',
  side: 'buy',
  target_quantity: 100,
  completed_quantity: 0,
  remaining_quantity: 100,
  stage: 'risk_pending',
  stage_entered_at: '2026-09-17T01:00:00Z',
  last_changed_at: '2026-09-17T01:00:00Z',
  event_at: '2026-09-17T01:00:00Z',
  originated_before_today: false,
  changed_today: true,
  blocking_issue_codes: [],
  risk_status: 'not_evaluated',
  approval_status: 'not_reached',
  command_status: 'not_reached',
}

function projection(overrides: Partial<ExecutionQueueProjection> = {}): ExecutionQueueProjection {
  return {
    schema_version: '1.0',
    agent_id: 'agent-1',
    account_id: '********1314',
    account_environment: 'simulation',
    projection_revision: 1,
    as_of: '2026-09-17T01:00:00Z',
    trading_date: '2026-09-17',
    calendar_status: 'available',
    today_activity: [
      baseItem,
      { ...baseItem, queue_item_id: '00000000-0000-4000-8000-000000000003', stage: 'approved' },
      { ...baseItem, queue_item_id: '00000000-0000-4000-8000-000000000004', stage: 'filled', remaining_quantity: 0, completed_quantity: 100 },
    ],
    carryover_pending: [{ ...baseItem, queue_item_id: '00000000-0000-4000-8000-000000000005', originated_before_today: true }],
    source_coverage: { execution_queue: 'complete', trading_calendar: 'complete' },
    truncated: false,
    read_only: true,
    ...overrides,
  }
}

describe('execution queue presentation', () => {
  it('keeps an unfilled retired approval distinct from pending orders and fills', () => {
    const retired = { ...baseItem, stage: 'superseded' as const, originated_before_today: true }
    expect(queueStageLabel(retired.stage)).toBe('已失效并结束')
    expect(queueDayLabel(retired)).toBe('历史事项今日结束')
    expect(queueProgressLabel(retired)).toContain('原事项已结束')
    expect(queueProgressLabel(retired)).toContain('未执行数量保留为历史记录')
    expect(retired.remaining_quantity).toBe(100)
    expect(retired.completed_quantity).toBe(0)
    expect(summarizeExecutionQueue(projection({ today_activity: [retired], carryover_pending: [] })))
      .toMatchObject({ todayTotal: 1, completed: 0, approvedPendingCommand: 0, carryoverPending: 0 })
  })

  it.each(['filled', 'cancelled', 'rejected', 'failed'] as const)('uses the authoritative %s terminal even with remaining historical quantity', (stage) => {
    const ended = { ...baseItem, stage, originated_before_today: true }
    expect(queueDayLabel(ended)).toBe('历史事项今日结束')
    expect(queueProgressLabel(ended)).toBe('已结束')
  })

  it('keeps a prior-day live order pending and never infers a terminal from zero remaining alone', () => {
    const pending = { ...baseItem, stage: 'submitted' as const, originated_before_today: true, remaining_quantity: 0 }
    expect(queueDayLabel(pending)).toBe('跨日未终态')
    expect(queueProgressLabel(pending)).toBe('尚未终态')
    expect(queueProgressLabel({ ...pending, wait_state: 'blocked' })).toBe('已阻断')
  })

  it('preserves unknown-stage uncertainty', () => {
    expect(queueStageLabel('unknown-stage')).toBe('执行阶段不可用')
    expect(queueProgressLabel({ ...baseItem, stage: 'unknown-stage' } as unknown as ExecutionQueueItem)).toBe('等待权威阶段')
    expect(queueStageLabel('toString')).toBe('执行阶段不可用')
  })

  it('does not claim an approval or new target exists for a pre-approval superseded item', () => {
    const ended = { ...baseItem, stage: 'superseded' as const, approval_status: 'not_reached' as const }
    expect(queueStageLabel(ended.stage)).toBe('已失效并结束')
    expect(queueProgressLabel(ended)).toContain('原事项已结束')
    expect(queueProgressLabel(ended)).not.toContain('审批已结束')
    expect(queueStageLabel(ended.stage)).not.toContain('新目标')
  })

  it('counts only an authoritative complete trading-day projection', () => {
    expect(summarizeExecutionQueue(projection())).toMatchObject({
      authoritative: true,
      todayTotal: 3,
      riskPending: 1,
      approvedPendingCommand: 1,
      completed: 1,
      carryoverPending: 1,
    })
  })

  const incompleteCases: Array<Partial<ExecutionQueueProjection>> = [
    { calendar_status: 'unavailable' as const },
    { source_coverage: { execution_queue: 'partial' as const } },
    { source_coverage: {} },
    { truncated: true },
  ]

  it.each(incompleteCases)('returns unavailable counts for incomplete evidence %#', (overrides) => {
    expect(summarizeExecutionQueue(projection(overrides))).toMatchObject({
      authoritative: false,
      todayTotal: null,
      completed: null,
      carryoverPending: null,
    })
  })
})
