const OPERATION_POLICY_LABELS: Record<string, string> = {
  'qmt.history.v1': 'QMT 历史行情读取',
  'qmt.standard-read.v1': 'QMT 标准只读调用',
}

const OPERATION_ID_LABELS: Record<string, string> = {
  '*': '全部标准只读操作',
  'market.market_data_ex': '扩展历史行情',
  'market.prepare_history_data': '历史数据准备',
  'strategy.validate': '策略包校验',
  'backtest.resonance-v3': 'Resonance V3 离线回测',
  'backtest.resonance-compare': 'Resonance V1/V2/V3 对照',
}

const HISTORY_JOB_ERROR_LABELS: Record<string, string> = {
  history_runner_failed: '历史行情运行器失败',
}

export function operationalErrorStateLabel({
  firstEventAt,
  lastEventAt,
  serviceReady,
  now = Date.now(),
}: {
  firstEventAt: string
  lastEventAt: string
  serviceReady: boolean
  now?: number
}): string {
  const first = new Date(firstEventAt).getTime()
  const last = new Date(lastEventAt).getTime()
  if (Number.isFinite(last) && now - last < 5 * 60 * 1000) return '仍在发生'
  if (serviceReady && Number.isFinite(first) && Number.isFinite(last) && last - first <= 2 * 60 * 1000) {
    return '启动窗口/历史瞬时事件 · 服务已恢复'
  }
  if (serviceReady) return '已恢复'
  return '历史状态待确认'
}

export function operationalLogLifecycleLabel(
  lifecycle: 'active' | 'recovered' | 'startup_transient',
): string {
  if (lifecycle === 'active') return '仍在发生'
  if (lifecycle === 'startup_transient') return '启动窗口事件 · 服务已恢复'
  return '已恢复'
}

export function operationPolicyLabel(policyId: string): string {
  return OPERATION_POLICY_LABELS[policyId] ?? `未命名操作策略（${policyId}）`
}

export function operationIdLabel(operationId: string, summaryLines: string[] = []): string {
  const safeSummary = summaryLines.find((item) => item.trim().length > 0)?.trim()
  return OPERATION_ID_LABELS[operationId] ?? safeSummary ?? `未识别只读操作（${operationId}）`
}

export function historyJobErrorLabel(errorCode?: string | null, errorMessage?: string | null): string {
  const codeLabel = errorCode ? (HISTORY_JOB_ERROR_LABELS[errorCode] ?? `未识别错误（${errorCode}）`) : '历史任务失败'
  if (!errorMessage) return codeLabel

  const marketDataExit = /^marketdata exited with code\s+(-?\d+)$/i.exec(errorMessage.trim())
  if (marketDataExit) return `${codeLabel}：行情数据进程退出，退出码 ${marketDataExit[1]}`
  return `${codeLabel}：保留原始诊断 ${errorMessage}`
}
