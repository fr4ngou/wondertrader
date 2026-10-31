import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import * as api from '../api'
import type { AutomationRuntimeStatus, ConsoleBootstrap, ExecutionQueueProjection, StrategyEligibilityProjection, StrategyWorkbenchDetail, TradingOperationsProjection } from '../types'
import { releaseHistoryMessage, StrategyPage } from './StrategyPage'
import { installProblemDictionary } from '../problemDictionary'

vi.mock('../api', () => ({
  fetchStrategyEligibility: vi.fn(), fetchStrategyRegistry: vi.fn(), fetchStrategyRuntime: vi.fn(),
  fetchStrategyWorkbenchDetail: vi.fn(), fetchExecutionQueue: vi.fn(), fetchBacktestReports: vi.fn(),
  fetchBacktestReport: vi.fn(), fetchBacktestTrades: vi.fn(), fetchReplenishment: vi.fn(),
}))

const stamp = '2026-01-01T00:00:00Z'
const strategy = { strategy_id: 'fixture-strategy', strategy_version: 'fixture-version', display_name: '测试策略', description: 'fixture' }
const bootstrap = { backtest_reports_available: false, overview: { errors: {} } } as ConsoleBootstrap
let detail: StrategyWorkbenchDetail
let eligibility: StrategyEligibilityProjection
const clients: QueryClient[] = []

beforeEach(() => {
  vi.resetAllMocks()
  installProblemDictionary({ schema_version: '1.0', definitions: [{
    schema_version: '1.0', issue_code: 'fresh_quote_unavailable', match_values: ['fresh quote unavailable'],
    title: '当前没有满足委托门禁的新鲜行情', meaning: '行情不足', impact: '委托等待',
    recommended_action: '等待允许时段和行情', fact_source: 'Bridge', unavailable_meaning: '无法确认',
    registry_version: 'fixture', updated_at: stamp,
  }], alert_category_labels: {}, alert_source_labels: {}, alert_titles: {}, alert_value_labels: {} })
  detail = {
    schema_version: '1.2', strategy, active_config_id: 'current-config', active_config_version: 'current-fixture',
    active_config_mode: 'simulation', configured: true, disabled: false, configured_budget: 0.2,
    configured_parameters: {}, readiness: null, performance_reports: [], errors: {}, generated_at: stamp,
    read_only: true, executable: false, release_evidence_scope: 'historical_config',
    release_evidence_config_version: 'historical-fixture',
    historical_release_gates: [{ gate_id: 'gate', ...strategy, stage: 'historical_backtest',
      code_commit: 'frozen-code', config_version: 'historical-fixture', dataset_version: 'frozen-dataset',
      status: 'passed', required_evidence_refs: [], evidence_refs: [], reasons: [], created_at: stamp }],
    execution_boundary: { published_preflight_ready: false, blocking_reasons: ['fresh quote unavailable'] },
  } as unknown as StrategyWorkbenchDetail
  eligibility = {
    schema_version: '1.0', source_component: 'portfolio', active_config_id: detail.active_config_id,
    active_config_version: detail.active_config_version, generated_at: stamp, read_only: true,
    source_coverage: { active_config: 'complete', strategy_runtime: 'complete', strategy_portfolio_targets: 'complete' },
    items: [{ schema_version: '1.0', ...strategy, registered: true, configured_enabled: true, disabled: false, configured_budget: 0.2,
      intent_eligible: true, automation_candidate: true, candidate_ready: true, projection_state: 'ready',
      accepts_new_events: true, runtime_lifecycle: 'running', valid_target_available: true,
      dependency_status: { valid_target: 'satisfied' }, blocking_issue_codes: [] }],
  }
  vi.mocked(api.fetchStrategyEligibility).mockImplementation(async () => eligibility)
  vi.mocked(api.fetchStrategyRegistry).mockResolvedValue({ strategies: [strategy] } as never)
  vi.mocked(api.fetchStrategyRuntime).mockResolvedValue([])
  vi.mocked(api.fetchStrategyWorkbenchDetail).mockImplementation(async () => detail)
  vi.mocked(api.fetchExecutionQueue).mockResolvedValue({
    calendar_status: 'available', source_coverage: { queue: 'complete' }, today_activity: [], carryover_pending: [],
  } as unknown as ExecutionQueueProjection)
})
afterEach(() => {
  cleanup()
  clients.forEach(client => client.clear())
  clients.length = 0
})

function page() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, retryDelay: 0 } } })
  clients.push(client)
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/strategies?strategy=${strategy.strategy_id}@${strategy.strategy_version}&tab=configuration`]}><StrategyPage bootstrap={bootstrap} /></MemoryRouter></QueryClientProvider>)
  return client
}

test.each(['evaluated', 'initializing'] as const)('shows %s decision separately from execution and fills', async (status) => {
  detail.current_target = {
    portfolio_target_id: 'target', config_id: 'current-config', config_version: 'current-fixture',
    source_trade_date: '2026-09-30', source_closed_at: stamp, observed_at: stamp, valid_until: null,
    target_weights: { '159780.SZ': 0 }, evidence_refs: [],
    items: [{ symbol: '159780.SZ', target_weight: 0, reason: '测试策略判断' }],
    decision: { status, rule_version: 'fixture-version', model_state_method: 'causal_history_replay',
      history_start: '2026-01-01', history_end: '2026-09-30', history_batch_count: 180,
      required_dependencies: [], execution_context_revision: null },
  }
  page()
  expect(await screen.findByText(status === 'evaluated' ? /策略已确认目标 · 规则版本/ : /策略仍在初始化/)).toBeVisible()
  expect(screen.getByText(/目标被接替的记录与实际成交分别保留/)).toBeVisible()
  expect(screen.getByText(/本次计算时间：/)).toHaveTextContent('2026-01-01 08:00')
})

test.each(['recorded', 'empty', 'unavailable'] as const)('shows %s replacement facts separately from fills', async (state) => {
  if (state !== 'unavailable') detail.target_replacements = {
    strategy_id: strategy.strategy_id, strategy_version: strategy.strategy_version,
    config_id: detail.active_config_id!, truncated: false, items: state === 'empty' ? [] : [{
      event_id: 'replacement-event', episode_id: 'old-episode', previous_revision: 3,
      previous_target_revision: 'september-stop-target', previous_strategy_version: 'old-rule',
      successor_target_id: 'successor-evaluation', successor_rule_version: 'new-rule', config_version: 'direction-new',
      symbol: '159780.SZ', side: 'sell', replaced_at: stamp, evaluated_at: stamp,
      source_trade_date: '2026-09-30', target_weight: .1846579, observed_position_quantity: 88700,
      prior_state_available: true, prior_blocking_reasons: ['execution_permission_blocked'],
      prior_blocking_reason_labels: ['执行权限尚未满足'], decision_input_refs: ['history-fixture'],
    }],
  }
  else detail.errors.target_replacements = 'upstream unavailable'
  page()
  const panel = await screen.findByRole('region', { name: '目标接替记录' })
  if (state === 'recorded') {
    expect(panel).toHaveTextContent('新评估规则 new-rule')
    expect(panel).toHaveTextContent('新目标 18.47%')
    expect(panel).toHaveTextContent('已核实持仓 88,700 份')
    expect(panel).toHaveTextContent('执行权限尚未满足')
    expect(panel).toHaveTextContent('september-stop-target')
    expect(panel).toHaveTextContent('successor-evaluation')
  } else expect(panel).toHaveTextContent(state === 'empty' ? '尚无目标接替记录' : '目标接替记录不可用')
})

test('shows frozen release history beside ready Portfolio and an actual quote safety block', async () => {
  page()
  const current = await screen.findByLabelText('当前功能与执行资格')
  expect(await within(current).findByText('策略条件已就绪')).toBeInTheDocument()
  expect(within(current).getByText(/Bridge 当前委托安全阻断/)).toHaveTextContent('当前没有满足委托门禁的新鲜行情')
  const history = screen.getByLabelText('历史回测与发布凭证')
  expect(history).toHaveTextContent('历史发布凭证对应 historical-fixture')
  expect(history).toHaveTextContent('当时通过')
  expect(history).toHaveTextContent('frozen-code')
  expect(history).toHaveTextContent('frozen-dataset')
  expect(history).not.toHaveTextContent('读取不可用')
})

test('legacy missing-config release response is explained as absent rather than service failure', async () => {
  delete detail.release_evidence_scope
  delete detail.release_evidence_config_version
  delete detail.historical_release_gates
  detail.errors.release_readiness = 'no release evidence matches the active config'
  page()
  expect(await screen.findByText(/当前配置尚无发布凭证/)).toBeInTheDocument()
  expect(await screen.findByText('策略条件已就绪')).toBeInTheDocument()
  expect(screen.queryByText(/发布记录读取不可用/)).not.toBeInTheDocument()
})

test('a real Replay read failure remains visible while Portfolio keeps its current meaning', async () => {
  detail.release_evidence_scope = 'unavailable'
  detail.errors.release_readiness = 'release evidence unavailable'
  page()
  expect(await screen.findByText('Replay 发布记录读取不可用，请查看服务状态。')).toBeInTheDocument()
  expect(await screen.findByText('策略条件已就绪')).toBeInTheDocument()
})

test.each(['coverage', 'config', 'projection'] as const)('does not present current readiness with %s inconsistency', async (fault) => {
  if (fault === 'coverage') eligibility.source_coverage.strategy_runtime = 'unavailable'
  if (fault === 'config') eligibility.active_config_id = 'other-config'
  if (fault === 'projection') eligibility.items[0].projection_state = 'unavailable'
  page()
  const current = await screen.findByLabelText('当前功能与执行资格')
  await waitFor(() => expect(current).toHaveTextContent('当前资格来源不可用或覆盖不完整'))
  expect(within(current).queryByText('策略条件已就绪')).not.toBeInTheDocument()
})

test('a failed eligibility refresh hides previously ready facts', async () => {
  const client = page()
  const current = await screen.findByLabelText('当前功能与执行资格')
  expect(await within(current).findByText('策略条件已就绪')).toBeInTheDocument()
  vi.mocked(api.fetchStrategyEligibility).mockRejectedValue(new Error('owner unavailable'))
  await act(async () => { await client.invalidateQueries({ queryKey: ['strategies', 'eligibility'] }) })
  await waitFor(() => expect(current).toHaveTextContent('当前资格来源不可用或覆盖不完整'))
  expect(within(current).queryByText('策略条件已就绪')).not.toBeInTheDocument()
})

test('queue waiting for a legal session remains a waiting fact alongside strategy readiness', async () => {
  vi.mocked(api.fetchExecutionQueue).mockResolvedValue({
    calendar_status: 'available', source_coverage: { queue: 'complete' }, carryover_pending: [],
    today_activity: [{ ...strategy, queue_item_id: 'item', correlation_id: 'correlation', identity: {},
      symbol: 'fixture-symbol', side: 'buy', remaining_quantity: 1, stage: 'planned',
      wait_state: 'waiting_session', blocking_issue_codes: [], originated_before_today: false }],
  } as unknown as ExecutionQueueProjection)
  page()
  const current = await screen.findByLabelText('当前功能与执行资格')
  expect(await within(current).findByText('策略条件已就绪')).toBeInTheDocument()
  expect(current).toHaveTextContent('等待允许的交易时段')
  expect(current).not.toHaveTextContent('发布故障')
})

test('old readiness payload preserves its historical config identity', () => {
  delete detail.release_evidence_scope
  delete detail.release_evidence_config_version
  detail.readiness = { config_version: 'frozen-legacy-config' } as never
  expect(releaseHistoryMessage(detail)).toContain('历史发布凭证对应 frozen-legacy-config')
})

test('retired prior-day approvals are ended history while the current target remains independent', async () => {
  vi.mocked(api.fetchExecutionQueue).mockResolvedValue({
    calendar_status: 'available', source_coverage: { queue: 'complete' }, carryover_pending: [],
    today_activity: [{ ...strategy, queue_item_id: 'retired-item', correlation_id: 'prior-correlation', identity: {},
      symbol: 'fixture-symbol', side: 'sell', remaining_quantity: 100, completed_quantity: 0,
      stage: 'superseded', wait_state: null, blocking_issue_codes: [], originated_before_today: true }],
  } as unknown as ExecutionQueueProjection)
  page()
  const queue = await screen.findByLabelText('所选策略今日执行事项')
  expect(await within(queue).findByText('已失效并结束')).toBeVisible()
  expect(queue).toHaveTextContent('历史事项今日结束')
  expect(queue).toHaveTextContent('原事项已结束；未执行数量保留为历史记录')
  expect(queue).toHaveTextContent('未执行数量 100')
  expect(queue).not.toHaveTextContent('跨日未终态 · prior-correlation')
})

test('a failed detail refresh hides cached release and execution facts', async () => {
  const client = page()
  expect(await screen.findByLabelText('历史回测与发布凭证')).toBeInTheDocument()
  vi.mocked(api.fetchStrategyWorkbenchDetail).mockRejectedValue(new Error('detail unavailable'))
  await act(async () => { await client.invalidateQueries({ queryKey: ['strategies', 'detail'] }) })
  expect(await screen.findByText('策略详情不可用')).toBeInTheDocument()
  expect(screen.queryByLabelText('历史回测与发布凭证')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('当前功能与执行资格')).not.toBeInTheDocument()
})


test('reads explicitly bound historical reports without current readiness and excludes unrelated reports', async () => {
  const historical = { report_hash: 'historical-report', model_version: 'historical model', dataset_version: 'shared-dataset', total_return: 0.1, maximum_drawdown: 0.05, trade_count: 0 }
  detail.historical_performance_reports = [historical] as never
  vi.mocked(api.fetchBacktestReports).mockResolvedValue([historical, { ...historical, report_hash: 'unrelated-report', model_version: 'unrelated model' }] as never)
  vi.mocked(api.fetchBacktestReport).mockResolvedValue({ ...historical, valuation_points: [], drawdown_curve: [], annualized_return: 0.1 } as never)
  vi.mocked(api.fetchBacktestTrades).mockResolvedValue({ report_hash: historical.report_hash, total: 0, items: [] } as never)
  const enabled = { ...bootstrap, backtest_reports_available: true }
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  clients.push(client)
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/strategies?strategy=${strategy.strategy_id}@${strategy.strategy_version}&tab=backtests`]}><StrategyPage bootstrap={enabled} /></MemoryRouter></QueryClientProvider>)
  expect(await screen.findByRole('button', { name: /historical model/ })).toBeInTheDocument()
  await waitFor(() => expect(api.fetchBacktestReport).toHaveBeenCalledWith(historical.report_hash, expect.any(AbortSignal)))
  expect(screen.queryByRole('button', { name: /unrelated model/ })).not.toBeInTheDocument()
  expect(api.fetchBacktestReport).not.toHaveBeenCalledWith('unrelated-report', expect.anything())
  fireEvent.click(screen.getByRole('tab', { name: '配置与运行' }))
  expect(screen.getByLabelText('历史回测与发布凭证')).toHaveTextContent('historical-fixture')
})

test('wires the selected configuration and account loop to the real replenishment panel', async () => {
  const current = { episode_id: 'current-opportunity', strategy_id: strategy.strategy_id,
    strategy_version: strategy.strategy_version, config_id: detail.active_config_id,
    target_revision: 'opportunity-original-target', symbol: 'CURRENT.SH', side: 'sell',
    state_label: '等待合适价格', blocking_reason_labels: ['当前卖价低于本档允许范围'],
    next_review_at: stamp, next_retry_at: stamp }
  vi.mocked(api.fetchReplenishment).mockResolvedValue({ scan_error: null, items: [current,
    { ...current, episode_id: 'historical-opportunity', config_id: 'prior-config', symbol: 'HISTORY.SH' },
  ] })
  const observed: AutomationRuntimeStatus = { schema_version: '1.0', generated_at: stamp,
    automation_gate: 'enabled', loop_state: 'advancing', business_health: 'healthy', trading_impact: 'none',
    last_observed_at: stamp, source_component: 'portfolio', issues: [] }
  const tradingOperations: TradingOperationsProjection = {
    schema_version: '1.0', generated_at: stamp, automation_runtime: observed,
    automation_runtime_sources: { portfolio: observed, operations: observed },
    active_issues: [], reconciliations: [], observability_stack_status: {},
    source_coverage: { automation_runtime_projection_consistency: 'complete' },
    read_only: true, executable: false,
  }
  const complete: ConsoleBootstrap = { ...bootstrap, overview: { ...bootstrap.overview,
    trading_operations: tradingOperations,
  } }
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  clients.push(client)
  const tree = (data: ConsoleBootstrap) => <QueryClientProvider client={client}><MemoryRouter initialEntries={[
    `/strategies?strategy=${strategy.strategy_id}@${strategy.strategy_version}&tab=configuration`,
  ]}><StrategyPage bootstrap={data} /></MemoryRouter></QueryClientProvider>
  const view = render(tree(complete))
  expect(await screen.findByText('策略条件已就绪')).toBeVisible()
  fireEvent.click(screen.getByRole('tab', { name: '调仓与补单' }))
  expect(await screen.findByText('循环正在运行 · 业务正常')).toBeVisible()
  const selected = await screen.findByRole('region', { name: '当前配置补单' })
  expect(await within(selected).findByText('CURRENT.SH · 卖出')).toBeVisible()
  expect(selected).toHaveTextContent('已核对当前配置未结束补单 1 项')
  expect(within(selected).queryByText('HISTORY.SH · 卖出')).not.toBeInTheDocument()
  expect(screen.getByText('历史配置与版本补单（1 项）')).toBeVisible()
  expect(api.fetchReplenishment).toHaveBeenCalledTimes(1)
  const incomplete = { ...complete, overview: { ...complete.overview, trading_operations: {
    ...complete.overview.trading_operations!, source_coverage: { automation_runtime_projection_consistency: 'partial' as const },
  } } }
  view.rerender(tree(incomplete))
  expect(screen.getByText('账户自动循环状态不可确认')).toBeVisible()
  expect(screen.queryByText('循环正在运行 · 业务正常')).not.toBeInTheDocument()
  expect(api.fetchReplenishment).toHaveBeenCalledTimes(1)
})
