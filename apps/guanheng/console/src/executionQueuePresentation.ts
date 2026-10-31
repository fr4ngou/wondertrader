import type { ExecutionQueueItem, ExecutionQueueProjection } from './types'

const queueStages: Record<ExecutionQueueItem['stage'], { label: string; terminal: boolean }> = {
  target_observed: { label: '已观察目标', terminal: false },
  capital_pending: { label: '等待资本复核', terminal: false },
  planned: { label: '计划已形成', terminal: false },
  risk_pending: { label: '等待风险复核', terminal: false },
  approved: { label: '已批准待命令', terminal: false },
  command_pending: { label: '等待命令签名', terminal: false },
  signed: { label: '已签名待发送', terminal: false },
  submitted: { label: '已提交柜台', terminal: false },
  partial_fill: { label: '部分成交', terminal: false },
  filled: { label: '已成交完成', terminal: true },
  cancelled: { label: '已取消', terminal: true },
  rejected: { label: '已拒绝', terminal: true },
  failed: { label: '失败', terminal: true },
  superseded: { label: '已失效并结束', terminal: true },
}

function queueStage(stage: string) {
  return Object.hasOwn(queueStages, stage) ? queueStages[stage as ExecutionQueueItem['stage']] : undefined
}

export function queueStageLabel(stage: string): string {
  return queueStage(stage)?.label ?? '执行阶段不可用'
}

export function queueIsTerminal(item: ExecutionQueueItem): boolean {
  return queueStage(item.stage)?.terminal === true
}

export function queueDayLabel(item: ExecutionQueueItem): string {
  if (queueIsTerminal(item)) return item.originated_before_today ? '历史事项今日结束' : '当天已结束事项'
  return item.originated_before_today ? '跨日未终态' : '当天事项'
}

export function queueProgressLabel(item: ExecutionQueueItem): string {
  if (!queueStage(item.stage)) return '等待权威阶段'
  if (item.stage === 'superseded') return '原事项已结束；未执行数量保留为历史记录，当前目标按实际持仓继续核对'
  if (queueIsTerminal(item)) return '已结束'
  return item.wait_state === 'blocked' ? '已阻断' : '尚未终态'
}

export type ExecutionQueueSummary = {
  authoritative: boolean
  todayTotal: number | null
  riskPending: number | null
  approvedPendingCommand: number | null
  waitingSend: number | null
  submitted: number | null
  partialFill: number | null
  completed: number | null
  cancelled: number | null
  rejectedOrFailed: number | null
  carryoverPending: number | null
}

export function summarizeExecutionQueue(
  projection: ExecutionQueueProjection,
): ExecutionQueueSummary {
  const coverage = Object.values(projection.source_coverage)
  const authoritative = projection.calendar_status === 'available'
    && coverage.length > 0
    && coverage.every((value) => value === 'complete')
    && !projection.truncated
  if (!authoritative) {
    return {
      authoritative: false,
      todayTotal: null,
      riskPending: null,
      approvedPendingCommand: null,
      waitingSend: null,
      submitted: null,
      partialFill: null,
      completed: null,
      cancelled: null,
      rejectedOrFailed: null,
      carryoverPending: null,
    }
  }

  const count = (...stages: string[]) => projection.today_activity.filter(
    (item) => stages.includes(item.stage),
  ).length
  return {
    authoritative: true,
    todayTotal: projection.today_activity.length,
    riskPending: count('risk_pending'),
    approvedPendingCommand: count('approved', 'command_pending'),
    waitingSend: count('signed'),
    submitted: count('submitted'),
    partialFill: count('partial_fill'),
    completed: count('filled'),
    cancelled: count('cancelled'),
    rejectedOrFailed: count('rejected', 'failed'),
    carryoverPending: projection.carryover_pending.length,
  }
}

export function queueCountLabel(value: number | null): string {
  return value == null ? '不可用' : String(value)
}
