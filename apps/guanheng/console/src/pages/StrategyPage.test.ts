import { expect, test } from 'vitest'

import type { AutomationRuntimeIssue } from '../types'
import { issueAffectsStrategy } from './StrategyPage'

const baseIssue: AutomationRuntimeIssue = {
  schema_version: '1.0',
  issue_key: 'operations:test:strategy:strategy-a',
  issue_code: 'automation_runtime_blocked',
  source_component: 'operations',
  severity: 'critical',
  impact_scope_kind: 'strategy',
  impact_scope_id: 'strategy-a',
  lifecycle: 'active',
  last_authoritative_state: 'active',
  revision: 1,
  retryable: true,
  user_safe_summary: 'test',
  reason_parameters: {},
  evidence_refs: [],
  first_observed_at: '2026-09-18T00:00:00Z',
  last_observed_at: '2026-09-18T00:00:00Z',
  last_authoritative_observed_at: '2026-09-18T00:00:00Z',
}

test('matches strategy and symbol scopes exactly while retaining account blockers', () => {
  const strategyScopes = new Set(['strategy-a', 'strategy-a@1.0.0', 'strategy-a@lineage-1'])
  const symbols = new Set(['510300.SH'])

  expect(issueAffectsStrategy(baseIssue, strategyScopes, symbols)).toBe(true)
  expect(issueAffectsStrategy({ ...baseIssue, impact_scope_id: 'strategy-a-copy' }, strategyScopes, symbols)).toBe(false)
  expect(issueAffectsStrategy({ ...baseIssue, impact_scope_kind: 'symbol', impact_scope_id: '510300.SH' }, strategyScopes, symbols)).toBe(true)
  expect(issueAffectsStrategy({ ...baseIssue, impact_scope_kind: 'symbol', impact_scope_id: '000001.SZ' }, strategyScopes, symbols)).toBe(false)
  expect(issueAffectsStrategy({ ...baseIssue, impact_scope_kind: 'account', impact_scope_id: 'account-safe' }, strategyScopes, symbols)).toBe(true)
  expect(issueAffectsStrategy({ ...baseIssue, impact_scope_kind: 'platform', impact_scope_id: 'automation' }, strategyScopes, symbols)).toBe(true)
})
