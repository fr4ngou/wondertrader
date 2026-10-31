import type { OrderExecutionTraceStage, OrderSummary } from './types'

export const orderStageNames: Record<OrderExecutionTraceStage['stage'], string> = {
  intent: '策略意图',
  risk: '组合风控',
  approval: '审批',
  command: '签名命令',
  qmt: 'QMT 回报',
  execution: '成交结果',
}

export const orderStatusNames: Record<OrderSummary['status'], string> = {
  pending: '待发送',
  received: '已接收',
  submitted: '已报',
  partial_fill: '部分成交',
  filled: '已成交',
  cancelled: '已撤',
  rejected: '已拒绝',
  failed: '失败',
  expired: '已过期',
  duplicate: '重复',
  error: '错误',
}

export const orderSideNames: Record<OrderSummary['side'], string> = {
  buy: '买入',
  sell: '卖出',
  cancel: '撤单',
}

export const orderEnvironmentNames: Record<OrderSummary['execution_mode'], string> = {
  simulation: '模拟盘',
  live: '实盘',
}

const ORDER_FAILURE_REASON_LABELS: Record<string, string> = {
  'QMT strategy m_bTrade=0: signal recorded but no broker order routed; operator verified empty broker order view':
    'QMT 策略处于 m_bTrade=0：只记录信号，未向柜台路由订单；操作员已确认柜台委托列表为空。',
}

export function orderFailureReasonLabel(value: string): string {
  return ORDER_FAILURE_REASON_LABELS[value] ?? `柜台返回未识别原因（保留原文）：${value}`
}
