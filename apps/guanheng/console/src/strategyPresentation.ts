import type {
  StrategyEligibilityProjection,
  StrategyRuntimeState,
  StrategyWorkbenchDetail,
} from './types'

const blockerLabels: Record<string, string> = {
  'no active direction configuration': '没有活动策略配置',
  'active strategy configuration is invalid': '活动策略配置校验失败',
  'active direction configuration is expired': '活动策略配置已过期',
  'active configuration mode is unsupported': '当前运行模式不支持该策略',
  'active configuration stop switch is enabled': '活动配置的停止开关已开启',
  'strategy is disabled by the active configuration': '该策略已被活动配置停用',
  'strategy has no positive active budget': '该策略尚未分配活动预算',
  'automation gate stop switch is enabled': '账户或全局停止开关已开启',
  'strategy lifecycle is paused': '策略生命周期已暂停',
  'strategy lifecycle is stopped': '策略生命周期已停止',
}

const releaseStageLabels: Record<string, string> = {
  historical_backtest: '历史回测',
  event_replay: '事件回放',
  realtime_shadow: '实时影子验证',
  simulation: '模拟盘验证',
  small_live: '小资金实盘',
}

export function runtimeParticipationLabel(runtime?: StrategyRuntimeState | null) {
  if (!runtime) return '暂无权威状态'
  if (runtime.can_emit_intents) return '参与当前决策'
  if (runtime.lifecycle === 'running') return '进程在线 · 不参与决策'
  return '不参与当前决策'
}

export function configurationStateLabel(detail?: StrategyWorkbenchDetail | null) {
  if (!detail) return '正在读取'
  if (detail.disabled) return '活动配置已停用'
  return detail.configured ? '已加入活动配置' : '仅登记为候选'
}

export function localizedRuntimeBlockers(runtime?: StrategyRuntimeState | null) {
  return (runtime?.blocking_reasons ?? []).map(
    (reason) => blockerLabels[reason] ?? `运行限制：${reason}`,
  )
}

export function releaseEvidenceLabel(detail?: StrategyWorkbenchDetail | null) {
  if (!detail) return '正在读取'
  if (!detail.configured) return '未绑定到当前活动配置'
  if (!detail.readiness) return '暂无与当前身份匹配的发布证据'
  if (detail.readiness.next_required_stage) {
    return `下一项：${releaseStageLabels[detail.readiness.next_required_stage] ?? detail.readiness.next_required_stage}`
  }
  return '当前发布证据链已完整'
}

export function strategyNextStep(detail?: StrategyWorkbenchDetail | null) {
  if (!detail) return '等待策略服务返回权威状态。'
  if (!detail.configured) {
    return '该版本只登记为候选，不会参与当前决策。若要启用，需要先在对话中比较配置、确认风险边界，再创建并激活新版本。'
  }
  if (detail.disabled) return '该策略被活动配置停用；需要在对话中审阅配置版本后才能恢复。'
  if (!detail.runtime?.can_emit_intents) {
    return '策略当前不会产生新的目标意图；请按下面的明确限制逐项处理。'
  }
  if (detail.readiness?.next_required_stage) {
    const stage = releaseStageLabels[detail.readiness.next_required_stage]
      ?? detail.readiness.next_required_stage
    return `策略正在参与当前决策，发布证据下一步为“${stage}”。`
  }
  return '策略正在参与当前决策；所有操作仍需通过与 Codex 的对话完成。'
}

export function multiStrategyPlatformSummary(
  projection?: StrategyEligibilityProjection | null,
) {
  if (!projection) return '多策略协调能力状态不可用'
  const coverage = Object.values(projection.source_coverage)
  if (!coverage.length || coverage.some((state) => state !== 'complete')) {
    return '多策略协调能力已加载 · 当前活动配置状态不可用'
  }
  const configuredCount = projection.items.filter((item) => item.configured_enabled).length
  if (configuredCount <= 1) {
    return '多策略协调能力已加载 · 当前活动配置为单策略'
  }
  return `多策略协调能力已加载 · 当前活动配置含 ${configuredCount} 个策略；逐策略资格见下表`
}
