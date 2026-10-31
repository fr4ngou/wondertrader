import { expect, test } from 'vitest'

import {
  configurationStateLabel,
  localizedRuntimeBlockers,
  multiStrategyPlatformSummary,
  releaseEvidenceLabel,
  runtimeParticipationLabel,
  strategyNextStep,
} from './strategyPresentation'
import type {
  StrategyEligibilityProjection,
  StrategyRuntimeState,
  StrategyWorkbenchDetail,
} from './types'

const runtime: StrategyRuntimeState = {
  schema_version: '1.0',
  strategy_id: 'resonance-regime-v2',
  strategy_version: '0.1.0',
  environment: 'simulation',
  lifecycle: 'running',
  state_version: 1,
  blocking_reasons: ['strategy has no positive active budget'],
  accepts_new_events: true,
  can_emit_intents: false,
  available_actions: ['pause', 'stop'],
  executable: false,
}

const detail = {
  configured: false,
  disabled: false,
  runtime,
  readiness: null,
} as unknown as StrategyWorkbenchDetail

test('explains a registered inactive strategy without calling it running', () => {
  expect(runtimeParticipationLabel(runtime)).toBe('进程在线 · 不参与决策')
  expect(configurationStateLabel(detail)).toBe('仅登记为候选')
  expect(releaseEvidenceLabel(detail)).toBe('未绑定到当前活动配置')
  expect(localizedRuntimeBlockers(runtime)).toEqual(['该策略尚未分配活动预算'])
  expect(strategyNextStep(detail)).toContain('不会参与当前决策')
  expect(strategyNextStep(detail)).toContain('在对话中比较配置')
})

test('distinguishes an active strategy from an inactive candidate', () => {
  const active = {
    ...detail,
    configured: true,
    configured_budget: 0.8,
    runtime: { ...runtime, can_emit_intents: true, blocking_reasons: [] },
    readiness: { next_required_stage: 'realtime_shadow' },
  } as unknown as StrategyWorkbenchDetail

  expect(configurationStateLabel(active)).toBe('已加入活动配置')
  expect(runtimeParticipationLabel(active.runtime)).toBe('参与当前决策')
  expect(releaseEvidenceLabel(active)).toBe('下一项：实时影子验证')
  expect(strategyNextStep(active)).toContain('正在参与当前决策')
})

test('separates loaded multi-strategy capability from the active strategy count', () => {
  const projection = {
    items: [{ configured_enabled: true }],
    source_coverage: { active_config: 'complete', strategy_registry: 'complete' },
  } as unknown as StrategyEligibilityProjection

  expect(multiStrategyPlatformSummary(projection)).toBe(
    '多策略协调能力已加载 · 当前活动配置为单策略',
  )
  expect(multiStrategyPlatformSummary({
    ...projection,
    items: [{ configured_enabled: true }, { configured_enabled: true }],
  } as StrategyEligibilityProjection)).toContain('当前活动配置含 2 个策略')
  expect(multiStrategyPlatformSummary({
    ...projection,
    source_coverage: { active_config: 'partial' },
  } as StrategyEligibilityProjection)).toContain('当前活动配置状态不可用')
})
