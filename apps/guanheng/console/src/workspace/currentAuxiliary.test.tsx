import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import fixture from './current-auxiliary.fixture.json'
import { validateStrategyRuntime } from './strategyRuntimeApi'
import { currentAuxiliaryPresentation } from './currentAuxiliary'
import StrategyRuntimeSummary from './StrategyRuntimeSummary'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

test('真实main003保留7项消费及16项可用值，历史覆盖原零值保持', () => {
  const value = validateStrategyRuntime(fixture).strategy!
  expect(value.current_auxiliary_state).toBe('available')
  expect(value.current_auxiliary?.consumed_fields).toEqual(fixture.strategy.current_auxiliary.consumed_fields)
  expect(currentAuxiliaryPresentation(value).label).toBe('当前辅助：必需7/7已消费（齐备）')
  expect(currentAuxiliaryPresentation(value).title).toContain('可用派生共16项')
  expect(value.diagnostics).toEqual(fixture.strategy.diagnostics)
})

test.each([
  (v: typeof fixture.strategy.current_auxiliary) => { v.schema = 'unknown' },
  (v: typeof fixture.strategy.current_auxiliary) => { v.decision_at = '2099-01-01T00:00:00+00:00' },
  (v: typeof fixture.strategy.current_auxiliary) => { v.required_fields['510050.SH'] = [] },
  (v: typeof fixture.strategy.current_auxiliary) => { v.consumed_fields['510050.SH'] = {} as typeof v.consumed_fields['510050.SH'] },
  (v: typeof fixture.strategy.current_auxiliary) => { v.available_fields['510050.SH'].shares_delta_yi.value = NaN },
  (v: typeof fixture.strategy.current_auxiliary) => { v.available_fields['510050.SH'].shares_delta_yi.sources = [] },
  (v: typeof fixture.strategy.current_auxiliary) => {
    for (const fields of [v.available_fields, v.consumed_fields]) fields['510050.SH'].shares_delta_yi.source_dates = ['2026-11-05']
  },
])('坏附加信息只降级当前诊断，资金/持仓/历史保持', mutate => {
  const bad = structuredClone(fixture)
  mutate(bad.strategy.current_auxiliary)
  const warning = vi.spyOn(console, 'warn').mockImplementation(() => {})
  const value = validateStrategyRuntime(bad).strategy!
  expect(value.current_auxiliary_state).toBe('unavailable')
  expect(value.current_auxiliary).toBeNull()
  expect(value.positions).toEqual(fixture.strategy.positions)
  expect(value.capital).toEqual(fixture.strategy.capital)
  expect(value.diagnostics).toEqual(fixture.strategy.diagnostics)
  expect(warning).toHaveBeenCalledWith('strategy_current_auxiliary_unavailable')
})

test('原状态行表达必需消费，原title表达派生总数', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(fixture))))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  render(<QueryClientProvider client={client}><StrategyRuntimeSummary /></QueryClientProvider>)
  expect(await screen.findByText(/必需7\/7已消费（齐备）/)).toHaveAttribute('title', expect.stringContaining('可用派生共16项'))
  client.clear()
})
