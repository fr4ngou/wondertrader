import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import App from './App'
// Resolve the dashboard dependencies before tests start; a timed-out test must
// not resume module loading and mutate the next test's shared response fixture.
import './pages/DashboardPage'
import { BOOTSTRAP_QUERY_KEY } from './api'
import type { ConsoleBootstrap, OrderSummary } from './types'

class EventSourceStub {
  addEventListener() {}
  removeEventListener() {}
  close() {}
}

let eligibilityCoverageComplete = true
let eligibilityRefreshFails = false
let executionQueueRefreshFails = false
let accountExecutionRefreshFails = false
let registryStrategies: Array<Record<string, unknown>> = []
let eligibilityItems: Array<Record<string, unknown>> = []
let eligibilityTargetCoverage: 'complete' | 'unavailable' = 'complete'
let strategyDetailEnabled = false
let strategyReportBindingUnavailable = false
let strategyDetailMode: 'simulation' | 'shadow' | null = null
let strategySignalRuntimeEnabled = false
let executionQueueItems: Array<Record<string, unknown>> = []
let backtestReportsFixture: Array<Record<string, unknown>> = []
let backtestReportsFailure = false
let backtestDetailFailure = false
let backtestTradesFailure = false
let backtestReportsDeferred: Promise<Response> | null = null
let receiptArtifactStatus: 'verified' | 'not_checked' | 'failed' = 'not_checked'
let eligibilityDeferred: Promise<Response> | null = null

const bootstrap: ConsoleBootstrap = {
  schema_version: '1.4',
  generated_at: '2026-08-19T01:00:00Z',
  overview_complete: true,
  display_only: true,
  control_locked: true,
  control_unlock_available: false,
  control_session: null,
  ui_capabilities: {
    schema_version: '1.0',
    bff_contract_version: '2026-08-19',
    supported_operator_capabilities: [],
    authorization_source: 'none',
    grants_operator_authority: false,
    live_execution_available: false,
    manual_order_available: false,
    manual_cancel_available: false,
  },
  live_available: false,
  manual_order_available: false,
  manual_cancel_available: false,
  workspaces: ['dashboard', 'market', 'strategies', 'portfolio', 'orders', 'operations'],
  qmt_connection_status: {
    schema_version: '1.0',
    agent_id: 'guoxin-qmt-1',
    generated_at: '2026-08-19T01:00:00Z',
    layers: [
      { schema_version: '1.0', layer: 'gateway', state: 'offline', evidence_source: 'gateway_sync', detail: 'QMT 已退出' },
      { schema_version: '1.0', layer: 'agent', state: 'offline', evidence_source: 'agent_heartbeat', detail: 'Agent 未运行' },
      { schema_version: '1.0', layer: 'trading_server', state: 'not_exposed', evidence_source: 'qmt_not_exposed', detail: '未提供' },
      { schema_version: '1.0', layer: 'account', state: 'unavailable', evidence_source: 'account_snapshot', detail: '暂无快照' },
    ],
    blocking_reasons: ['agent offline'],
    read_only: true,
    executable: false,
  },
  overview: {
    generated_at: '2026-08-19T01:00:00Z',
    read_only: true,
    release_gates: [],
    release_readiness: [],
    performance_reports: [],
    errors: {},
  },
}

function renderApp(path: string, data: ConsoleBootstrap = bootstrap) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  client.setQueryData(BOOTSTRAP_QUERY_KEY, data)
  return { ...render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></QueryClientProvider>), client }
}

beforeEach(() => {
  eligibilityDeferred = null
  strategyReportBindingUnavailable = false
  eligibilityCoverageComplete = true
  eligibilityRefreshFails = false
  executionQueueRefreshFails = false
  accountExecutionRefreshFails = false
  registryStrategies = []
  eligibilityItems = []
  eligibilityTargetCoverage = 'complete'
  strategyDetailEnabled = false
  strategyDetailMode = null
  strategySignalRuntimeEnabled = false
  executionQueueItems = []
  backtestReportsFixture = []
  backtestReportsFailure = false
  backtestDetailFailure = false
  backtestTradesFailure = false
  backtestReportsDeferred = null
  receiptArtifactStatus = 'not_checked'
  vi.stubGlobal('EventSource', EventSourceStub)
  vi.stubGlobal('fetch', vi.fn((input: string | URL | Request) => {
    const url = String(input)
    if (url.includes('/v1/ui/problem-dictionary')) {
      return Promise.resolve(new Response(JSON.stringify({
        schema_version: '1.0',
        definitions: [{
          schema_version: '1.0', issue_code: 'account_capital_residual',
          title: '账户资本金额与策略袖套、储备及人工资金合计不一致',
          meaning: '账户资本存在残差', impact: '自动执行保持安全阻断',
          recommended_action: '核对账户资本边界', fact_source: 'Portfolio 账户资本对账',
          unavailable_meaning: '不可用按覆盖不足处理', registry_version: 'test',
          updated_at: bootstrap.generated_at, match_values: [],
        }],
        alert_category_labels: { qmt_heartbeat_stale: 'AI_ETF 心跳超过订单门槛' },
        alert_source_labels: { 'qmt-agent': 'AI_ETF 执行代理' },
        alert_titles: { 'qmt:heartbeat': 'AI_ETF 心跳新鲜度' },
        alert_value_labels: { unavailable: '不可用', verified: '已验证' },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (url.includes('/v1/ui/orders/account-execution-batches')) {
      if (accountExecutionRefreshFails) return Promise.reject(new Error('account execution refresh failed'))
      return Promise.resolve(new Response(JSON.stringify({
        schema_version: '1.0', generated_at: bootstrap.generated_at, source_coverage: 'complete', read_only: true,
        batches: [{
          batch_id: '00000000-0000-4000-8000-000000000701', account_label: '******1314',
          account_environment: 'simulation', account_boundary_captured_at: bootstrap.generated_at,
          current_state: 'active', current_reason_codes: [], successor_batch_id: null,
          active_config_version: 'direction-v7', created_at: bootstrap.generated_at,
          strategy_count: 2, strategy_ids: ['strategy-a', 'strategy-b'],
          strategy_lineages: ['strategy-a@lineage-1', 'strategy-b@lineage-1'],
          available_cash_before_reservations: 100000, available_cash_after_reservations: 70000,
          gross_market_value: 50000,
          allocations: [{
            allocation_decision_id: '00000000-0000-4000-8000-000000000702', strategy_id: 'strategy-a',
            strategy_lineage_id: 'strategy-a@lineage-1', strategy_spendable_cash: 60000,
            requested_amount: 30000, allocated_amount: 30000, decision: 'allocated', reason_codes: [],
          }],
          reservations: [{
            reservation_id: '00000000-0000-4000-8000-000000000703',
            queue_item_id: '00000000-0000-4000-8000-000000000704', strategy_id: 'strategy-a',
            strategy_lineage_id: 'strategy-a@lineage-1', symbol: '510300.SH', side: 'buy', quantity: 6000,
            still_reserved_quantity: 4000, executed_unabsorbed_quantity: 2000, released_quantity: 0,
            cash_reserved: 30000, risk_notional_reserved: 30000, status: 'executed_unabsorbed',
            last_changed_at: bootstrap.generated_at,
          }],
        }],
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (url.includes('/v1/ui/orders/execution-queue')) {
      if (executionQueueRefreshFails) return Promise.reject(new Error('execution queue refresh failed'))
      return Promise.resolve(new Response(JSON.stringify({
        schema_version: '1.0', agent_id: 'guoxin-qmt-1', account_id: '******1314',
        account_environment: 'simulation', projection_revision: 1,
        as_of: bootstrap.generated_at, trading_date: '2026-08-19', calendar_status: 'available',
        today_activity: executionQueueItems, carryover_pending: [], source_freshness: {},
        source_coverage: { execution_queue: 'complete', trading_calendar: 'complete' },
        truncated: false, next_cursor: null, read_only: true,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (url.includes('/v1/ui/orders/') && url.endsWith('/trace')) {
      const correlationId = url.split('/').at(-2) ?? ''
      return Promise.resolve(new Response(JSON.stringify({
        schema_version: '1.0', correlation_id: correlationId, complete: false, read_only: true,
        stages: [
          { stage: 'intent', status: 'accepted', occurred_at: bootstrap.generated_at, summary: '策略意图已形成', evidence_ref_count: 1 },
          { stage: 'risk', status: 'pending', occurred_at: null, summary: '等待风险复核', evidence_ref_count: 0 },
          { stage: 'approval', status: 'unavailable', occurred_at: null, summary: '尚未形成审批事实', evidence_ref_count: 0 },
          { stage: 'command', status: 'unavailable', occurred_at: null, summary: '尚未形成命令事实', evidence_ref_count: 0 },
          { stage: 'qmt', status: 'unavailable', occurred_at: null, summary: '尚未形成 QMT 事实', evidence_ref_count: 0 },
          { stage: 'execution', status: 'unavailable', occurred_at: null, summary: '尚未形成成交事实', evidence_ref_count: 0 },
        ],
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (url.includes('/v1/ui/orders?')) {
      return Promise.resolve(new Response(JSON.stringify({ schema_version: '1.0', items: [], total: 0, limit: 20, offset: 0, has_more: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (url.includes('/v1/ui/operations/workbench')) {
      return Promise.resolve(new Response(JSON.stringify({
        schema_version: '1.3', generated_at: bootstrap.generated_at,
        database_migrations: null, history_jobs: [], operation_policies: [], thresholds: [],
        conversation_receipt_observation_available: true, conversation_receipt_invalid_count: 0,
        conversation_receipts: [{
          schema_version: '1.0', receipt_sha256: 'a'.repeat(64), plan_sha256: 'b'.repeat(64),
          operation_id: 'backtest.resonance-v3', risk_class: 'research_write', status: 'succeeded',
          started_at: bootstrap.generated_at, completed_at: bootstrap.generated_at, duration_ms: 2682,
          git_commit: 'c'.repeat(40), output_count: 1, output_bytes: 7205600,
          strategy: 'resonance-regime-v3@0.1.0', total_return: 0.5209,
          annualized_return: 0.2578, maximum_drawdown: 0.0606, trade_count: 193,
          summary_lines: ['运行 Resonance V3 离线回测执行成功', '交易副作用：无'],
          content_verified: true, artifacts_verified: receiptArtifactStatus === 'verified',
          artifact_verification_status: receiptArtifactStatus, trading_side_effects: 'none',
          read_only: true, executable: false,
        }],
        read_only: true,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (url.includes('/v1/ui/operations/error-logs')) {
      return Promise.resolve(new Response(JSON.stringify({
        schema_version: '1.0', query: {}, truncated: false, next_cursor: null, read_only: true,
        coverage: {
          schema_version: '1.0', status: 'complete', loki_status: 'healthy',
          alloy_status: 'healthy', source_status: 'healthy', minio_status: 'healthy',
          queried_at: bootstrap.generated_at, latest_event_at: bootstrap.generated_at,
          last_successful_query_at: bootstrap.generated_at, last_successful_collection_at: bootstrap.generated_at,
          persistence_status: 'verified', persistence_last_write_at: bootstrap.generated_at,
          retention_days: 14, retention_status: 'verified', source_delay_seconds: 1,
          collection_lag_seconds: 1, dropped_count: 0, drop_status: 'observed',
          invalid_response_line_count: 0, failure_code: null,
        },
        fingerprint_groups: [{
          schema_version: '1.0', stack_fingerprint: 'a'.repeat(64),
          issue_code: 'capital_projection_failed', severity: 'error', service: 'portfolio-risk',
          count: 2, first_event_at: bootstrap.generated_at, last_event_at: bootstrap.generated_at,
          user_safe_summary: '资本投影失败', lifecycle: 'active', service_ready: true,
          lifecycle_reason: '最近五分钟仍有错误事件',
        }],
        events: [{
          schema_version: '1.0', event_at: bootstrap.generated_at, collected_at: bootstrap.generated_at,
          severity: 'error', service: 'portfolio-risk', component: 'capital_projection',
          environment: 'simulation', issue_code: 'capital_projection_failed', user_safe_summary: '资本投影失败',
          exception_type: 'ValueError', stack_fingerprint: 'a'.repeat(64),
          stack_frames: ['capital.py:42:project'], correlation_id: null, trace_id: null,
          strategy_id: 'resonance-regime-v2', strategy_version: '2.0.0', source_version: 'abcdef1',
          redaction_policy_version: '1.0', structured_metadata: {},
        }],
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (url.includes('/v1/ui/strategies/eligibility')) {
      if (eligibilityDeferred) return eligibilityDeferred
      if (eligibilityRefreshFails) return Promise.reject(new Error('eligibility refresh failed'))
      return Promise.resolve(new Response(JSON.stringify({
        schema_version: '1.0', generated_at: bootstrap.generated_at, source_component: 'portfolio',
        active_config_id: null, active_config_version: null, items: eligibilityItems,
        source_coverage: {
          strategy_registry: eligibilityCoverageComplete ? 'complete' : 'partial',
          strategy_runtime: 'complete', active_config: 'complete',
          automation_runtime: 'complete', execution_queue: 'complete',
          strategy_portfolio_targets: eligibilityTargetCoverage,
        },
        read_only: true,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (url.includes('/v1/ui/strategies/registry')) {
      return Promise.resolve(new Response(JSON.stringify({ strategies: registryStrategies }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if ((strategyDetailEnabled || backtestReportsFixture.length > 0) && url.includes('/v1/ui/strategies/strategy-a/versions/1.0.0')) {
      return Promise.resolve(new Response(JSON.stringify({
        strategy: { strategy_id: 'strategy-a', strategy_version: '1.0.0', display_name: '策略 A', description: 'test' },
        configured: false, disabled: false, configured_budget: null, configured_parameters: {},
        active_config_version: null, active_config_mode: strategyDetailMode,
        runtime: strategySignalRuntimeEnabled ? { strategy_id: 'strategy-a', strategy_version: '1.0.0', environment: 'shadow', lifecycle: 'running', blocking_reasons: [], can_emit_intents: true } : null,
        recent_intents: [], performance_reports: backtestReportsFixture, readiness: null,
        errors: { release_readiness: 'Replay profile disabled', ...(strategyReportBindingUnavailable ? { performance_reports: 'identity unavailable' } : {}) },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (url.includes('/v1/ui/backtests/reports?')) {
      if (backtestReportsDeferred) return backtestReportsDeferred
      return Promise.resolve(new Response(backtestReportsFailure ? '{}' : JSON.stringify(backtestReportsFixture), {
        status: backtestReportsFailure ? 503 : 200, headers: { 'Content-Type': 'application/json' },
      }))
    }
    if (url.includes('/v1/ui/backtests/reports/') && url.includes('/trades?')) {
      return Promise.resolve(new Response(backtestTradesFailure ? '{}' : JSON.stringify({
        report_hash: new URL(url, 'http://localhost').pathname.split('/')[5],
        total: 1, items: [{ trade_id: 'trade-1', sequence: 1, symbol: '510300.SH', side: 'buy',
          quantity: 100, price: 4.5, occurred_at: bootstrap.generated_at }],
      }), { status: backtestTradesFailure ? 503 : 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (url.includes('/v1/ui/backtests/reports/')) {
      return Promise.resolve(new Response(backtestDetailFailure ? '{}' : JSON.stringify({
        report_hash: new URL(url, 'http://localhost').pathname.split('/')[5],
        model_version: 'model-v1', initial_capital: 100000, total_return: 0.1,
        annualized_return: 0.1, maximum_drawdown: 0.05, sharpe_ratio: 0.5,
        trade_count: 1, valuation_points: [], drawdown_curve: [],
      }), { status: backtestDetailFailure ? 503 : 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (url.includes('/v1/ui/portfolio/performance')) {
      return Promise.resolve(new Response(JSON.stringify({
        schema_version: '1.1', environment: 'simulation', points: [], data_available: false,
        missing_reason: 'account history unavailable', source_kind: 'qmt_account_snapshot_history',
        calculation_method: 'raw-account-equity-v1', normalization_method: 'first-source-snapshot-equity-v1',
        drawdown_method: 'running-peak-on-full-source-series-v1', cash_flow_adjusted: false,
        source_point_count: 0, generated_at: bootstrap.generated_at, warnings: [],
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (url.includes('/v1/ui/portfolio/positions')) {
      return Promise.resolve(new Response(JSON.stringify({
        schema_version: '1.1', environment: 'simulation', captured_at: bootstrap.generated_at,
        snapshot_age_seconds: 0, snapshot_stale: false, items: [], data_available: false,
        valuation_complete: false, missing_valuation_symbols: [], cost_complete: false,
        missing_cost_symbols: [], unrealized_pnl_complete: false,
        missing_unrealized_pnl_symbols: [], missing_reason: 'account snapshot unavailable', read_only: true,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (url.includes('/v1/ui/portfolio/pnl')) {
      return Promise.resolve(new Response(JSON.stringify({
        schema_version: '1.1', environment: 'simulation', captured_at: bootstrap.generated_at,
        snapshot_age_seconds: 0, snapshot_stale: false, data_available: false,
        valuation_source: 'unavailable', day_pnl_source: 'unavailable', cash_flow_adjusted: false,
        realized_pnl_complete: false, realized_pnl_source: 'unavailable',
        unrealized_pnl_complete: false, unrealized_pnl_source: 'unavailable',
        fees_complete: false, fees_source: 'unavailable', taxes_complete: false,
        taxes_source: 'unavailable', missing_reason: 'account snapshot unavailable',
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (url.includes('/v1/ui/portfolio/replenishment')) {
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (url.includes('/v1/ui/strategies/runtime')) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    if (url.includes('/v1/ui/orders/recent')) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }
    return Promise.resolve(new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }))
  }))
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

test('renders the dedicated strategy holdings workspace', async () => {
  renderApp('/orders')
  await screen.findByRole('heading', { name: '交易记录' })
  const navigation = screen.getByRole('navigation', { name: '主要工作区' })
  expect(navigation.querySelectorAll('a')).toHaveLength(6)
  for (const label of ['总览', '行情', '市场观察', '策略', '交易记录', '系统状态']) {
    expect(screen.getByRole('link', { name: label })).toBeInTheDocument()
  }
  expect(screen.getByText('仅展示 · 操作请通过对话完成')).toBeInTheDocument()
  expect(screen.queryByText('遗漏信号恢复任务')).not.toBeInTheDocument()
  expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes('/v1/ui/recovery-tasks'))).toBe(false)
})

test('does not expose login, unlock, order, cancel, or control actions', async () => {
  renderApp('/orders')
  await screen.findByRole('heading', { name: '交易记录' })
  expect(screen.queryByLabelText('操作 PIN')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /控制中心|解锁/ })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /下单|撤单|急停|启动策略|停止策略/ })).not.toBeInTheDocument()
})

test.each([
  ['not_checked', '回执已核对，产物可按需验真'],
  ['verified', '回执与产物均已校验'],
  ['failed', '产物验真失败，请核对产物与回执'],
] as const)('shows conversation receipt artifact status %s without a trading action or automatic deep read', async (status, verificationLabel) => {
  receiptArtifactStatus = status
  renderApp('/operations')
  await screen.findByRole('heading', { name: '系统状态' })
  expect(await screen.findByText('resonance-regime-v3@0.1.0')).toBeInTheDocument()
  expect(screen.getByText('52.09%')).toBeInTheDocument()
  expect(screen.getByText('6.06%')).toBeInTheDocument()
  expect(screen.getByText(new RegExp(verificationLabel))).toBeInTheDocument()
  if (status !== 'verified') expect(screen.queryByText(/回执与产物均已校验/)).not.toBeInTheDocument()
  expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes('/verification'))).toBe(false)
  expect(screen.queryByRole('button', { name: /执行|重跑|删除/ })).not.toBeInTheDocument()
})

test('keeps platform service readiness distinct from an offline QMT alert', async () => {
  const data: ConsoleBootstrap = {
    ...bootstrap,
    overview: {
      ...bootstrap.overview,
      operations: {
        healthy: false,
        platform_services_ready: true,
        services: [],
        alerts: [{
          alert_key: 'qmt:heartbeat',
          category: 'qmt_heartbeat_stale',
          severity: 'critical',
          source: 'qmt-agent',
          active: true,
        }],
        trading_facts: {
          risk_approval_count: 6,
          order_command_count: 6,
          execution_event_count: 24,
          dead_letter_event_count: 0,
        },
      },
    },
  }
  renderApp('/operations', data)
  expect(await screen.findByText('外围服务正常')).toBeInTheDocument()
  expect(screen.queryByText('外围服务降级')).not.toBeInTheDocument()
  expect(document.querySelector('.alert-card .alert-row')?.getAttribute('data-alert-key')).toBe('qmt:heartbeat')
  fireEvent.click(screen.getByRole('button', { name: '查看实时事件中心' }))
  const drawer = screen.getByRole('complementary', { name: '实时事件中心' })
  const alertRow = drawer.querySelector('[data-alert-key="qmt:heartbeat"]')!
  expect(alertRow).toHaveClass('activity-critical')
  expect(alertRow).toHaveTextContent('AI_ETF 心跳新鲜度')
  expect(alertRow).toHaveTextContent('AI_ETF 执行代理 · AI_ETF 心跳超过订单门槛')
  expect(alertRow).toHaveAttribute('href', '/operations')
})

test('event drawer shows every active owner alert while the overview keeps eight rows', async () => {
  const alerts = Array.from({ length: 10 }, (_, index) => ({
    alert_key: `owner-alert:${index}`, category: 'qmt_heartbeat_stale',
    severity: 'warning' as const, source: 'qmt-agent', active: true,
  }))
  const data: ConsoleBootstrap = { ...bootstrap, overview: { ...bootstrap.overview,
    operations: { ...bootstrap.overview.operations!, alerts },
  } }
  renderApp('/operations', data)
  await screen.findByRole('heading', { name: '系统状态' })
  expect(document.querySelectorAll('.alert-card .alert-row')).toHaveLength(8)
  fireEvent.click(screen.getByRole('button', { name: '查看实时事件中心' }))
  const drawer = screen.getByRole('complementary', { name: '实时事件中心' })
  const rows = Array.from(drawer.querySelectorAll('[data-alert-key]'))
  expect(rows.map((row) => row.getAttribute('data-alert-key'))).toEqual(alerts.map((row) => row.alert_key))
  expect(rows.every((row) => row.classList.contains('activity-warning'))).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: '关闭实时事件中心' }))
  expect(screen.queryByRole('complementary', { name: '实时事件中心' })).not.toBeInTheDocument()
})

test('dashboard keeps the four authority layers visible and does not fake an empty strategy set', async () => {
  eligibilityCoverageComplete = false
  renderApp('/dashboard')

  await screen.findByRole('heading', { name: '总览' }, { timeout: 10_000 })
  const layers = screen.getByLabelText('总览运行状态分层')
  for (const label of ['服务可达性', '账户与交易依赖', '自动执行开关', '自动执行运行状态']) {
    expect(layers).toHaveTextContent(label)
  }
  expect(await screen.findByText('策略资格覆盖不完整')).toBeInTheDocument()
  expect(screen.getByText('不能确认当前没有允许策略；请查看资格矩阵中的缺失来源。')).toBeInTheDocument()
  expect(screen.queryByText('当前没有允许进入自动执行的策略')).not.toBeInTheDocument()
  expect(screen.getByLabelText('首页今日订单汇总')).toHaveTextContent('今日事项0')
})

test.each([
  ['/dashboard', '当前没有允许进入自动执行的策略'],
  ['/strategies?tab=configuration', '当前生效的策略组合'],
])('hides stale eligibility facts after a refresh failure and restores them on success in %s', async (path, fact) => {
  const { client } = renderApp(path)
  await screen.findByRole('heading', { name: path === '/dashboard' ? '总览' : '策略' }, { timeout: 10_000 })
  await waitFor(() => expect(screen.getAllByText(fact).length).toBeGreaterThan(0))

  eligibilityRefreshFails = true
  await act(async () => { await client.invalidateQueries({ queryKey: ['strategies', 'eligibility'] }) })
  await waitFor(() => expect(screen.getByText('策略资格不可用')).toBeInTheDocument())
  expect(screen.queryAllByText(fact)).toHaveLength(0)

  eligibilityRefreshFails = false
  await act(async () => { await client.invalidateQueries({ queryKey: ['strategies', 'eligibility'] }) })
  await waitFor(() => expect(screen.getAllByText(fact).length).toBeGreaterThan(0))
  expect(screen.queryByText('策略资格不可用')).not.toBeInTheDocument()
})

test('keeps registry strategies unclassified and shows disabled Replay evidence during eligibility failure', async () => {
  registryStrategies = [{ strategy_id: 'strategy-a', strategy_version: '1.0.0', display_name: '策略 A' }]
  strategyDetailEnabled = true
  const { client } = renderApp('/strategies?strategy=strategy-a@1.0.0&tab=configuration')
  expect(await screen.findByText('未启用候选与历史版本（1）')).toBeInTheDocument()
  expect(await screen.findByText('Replay 服务未启用，发布门禁证据不可用。')).toBeInTheDocument()

  eligibilityRefreshFails = true
  await act(async () => { await client.invalidateQueries({ queryKey: ['strategies', 'eligibility'] }) })
  expect(await screen.findByText('当前运行策略资格不可用')).toBeInTheDocument()
  expect(screen.queryByText('未启用候选与历史版本（1）')).not.toBeInTheDocument()
  expect(screen.getByText('Replay 服务未启用，发布门禁证据不可用。')).toBeInTheDocument()
})

test.each(['simulation', 'shadow', null] as const)('shows active configuration mode %s independently of persisted signal environment', async (mode) => {
  // This regression checks field ownership; load the lazy page before timing DOM reads.
  await import('./pages/StrategyPage')
  strategyDetailEnabled = true
  strategyDetailMode = mode
  strategySignalRuntimeEnabled = true
  registryStrategies = [{ strategy_id: 'strategy-a', strategy_version: '1.0.0', display_name: '策略 A' }]
  renderApp('/strategies?strategy=strategy-a@1.0.0&tab=configuration')
  const label = await screen.findByText('活动配置模式', {}, { timeout: 10000 })
  expect(within(label.parentElement!).getByText(mode === 'simulation' ? '模拟盘' : mode === 'shadow' ? '影子运行（只计算、不下单）' : '暂无权威状态')).toBeVisible()
  expect(screen.getByText('运行中')).toBeVisible()
  expect(screen.getByText(/实际订单由组合风控和执行端逐笔核验/)).toBeVisible()
})

test('keeps published backtest reads idle when Replay is disabled or bootstrap is older', async () => {
  const { unmount } = renderApp('/strategies?tab=backtests')
  expect((await screen.findAllByText('回测服务未启用')).length).toBeGreaterThanOrEqual(2)
  expect(screen.queryByText('0 份')).not.toBeInTheDocument()
  expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes('/v1/ui/backtests/reports'))).toBe(false)
  unmount()

  const enabled: ConsoleBootstrap = { ...bootstrap, backtest_reports_available: true }
  renderApp('/strategies?strategy=strategy-a@1.0.0&tab=backtests', enabled)
  await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes('/v1/ui/backtests/reports?'))).toBe(true))
})

test('does not reveal an in-flight report result after Replay becomes disabled', async () => {
  strategyDetailEnabled = true
  let finishReports: (response: Response) => void = () => {}
  backtestReportsDeferred = new Promise<Response>((resolve) => { finishReports = resolve })
  const enabled: ConsoleBootstrap = { ...bootstrap, backtest_reports_available: true }
  const { client } = renderApp('/strategies?strategy=strategy-a@1.0.0&tab=backtests', enabled)
  await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes('/v1/ui/backtests/reports?'))).toBe(true))
  client.setQueryData(BOOTSTRAP_QUERY_KEY, { ...enabled, backtest_reports_available: false })
  finishReports(new Response(JSON.stringify([{ report_hash: 'c'.repeat(64), model_version: 'old-model', dataset_version: 'old-dataset', total_return: 0.1, maximum_drawdown: 0.05 }]), { status: 200 }))
  await act(async () => { await backtestReportsDeferred })
  expect(await screen.findAllByText('回测服务未启用')).not.toHaveLength(0)
  expect(screen.queryByText('old-model')).not.toBeInTheDocument()
  expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes(`/v1/ui/backtests/reports/${'c'.repeat(64)}`))).toBe(false)
})

test('shows enabled report failures and recovery without reusing stale report facts', async () => {
  const hash = 'a'.repeat(64)
  backtestReportsFixture = [{ report_hash: hash, model_version: 'model-v1', dataset_version: 'frozen-v1', total_return: 0.1, maximum_drawdown: 0.05 }]
  backtestReportsFailure = true
  const enabled: ConsoleBootstrap = { ...bootstrap, backtest_reports_available: true }
  const { client } = renderApp('/strategies?strategy=strategy-a@1.0.0&tab=backtests', enabled)
  expect(await screen.findAllByText('回测报告不可用', {}, { timeout: 5000 })).not.toHaveLength(0)
  expect(screen.queryByText('0 份')).not.toBeInTheDocument()
  expect(screen.queryByText('暂无回测报告')).not.toBeInTheDocument()

  backtestReportsFailure = false
  await act(async () => { await client.invalidateQueries({ queryKey: ['backtests', 'reports'] }) })
  expect(await screen.findByRole('button', { name: /model-v1/ })).toBeInTheDocument()
  expect(await screen.findByLabelText('回测净值、基准和回撤曲线')).toBeInTheDocument()
  expect(await screen.findByText('510300.SH', { selector: '.backtest-trade-row strong' })).toBeInTheDocument()

  backtestReportsFailure = true
  await act(async () => { await client.invalidateQueries({ queryKey: ['backtests', 'reports'] }) })
  expect(await screen.findAllByText('回测报告不可用', {}, { timeout: 5000 })).not.toHaveLength(0)
  expect(screen.queryByRole('button', { name: /model-v1/ })).not.toBeInTheDocument()
  expect(screen.queryByLabelText('回测净值、基准和回撤曲线')).not.toBeInTheDocument()
  expect(screen.queryByText('510300.SH', { selector: '.backtest-trade-row strong' })).not.toBeInTheDocument()

  client.setQueryData(BOOTSTRAP_QUERY_KEY, { ...enabled, backtest_reports_available: false })
  expect(await screen.findAllByText('回测服务未启用')).not.toHaveLength(0)
  const callCount = vi.mocked(fetch).mock.calls.filter(([input]) => String(input).includes('/v1/ui/backtests/reports')).length
  await act(async () => { await client.invalidateQueries({ queryKey: ['backtests'] }) })
  expect(vi.mocked(fetch).mock.calls.filter(([input]) => String(input).includes('/v1/ui/backtests/reports'))).toHaveLength(callCount)
}, 30000)

test('shows detail and trade read failures instead of cached values', async () => {
  const hash = 'b'.repeat(64)
  backtestReportsFixture = [{ report_hash: hash, model_version: 'model-v1', dataset_version: 'frozen-v1', total_return: 0.1, maximum_drawdown: 0.05 }]
  backtestDetailFailure = true
  backtestTradesFailure = true
  const { client } = renderApp('/strategies?strategy=strategy-a@1.0.0&tab=backtests', { ...bootstrap, backtest_reports_available: true })
  expect(await screen.findByText('报告详情不可用', {}, { timeout: 5000 })).toBeInTheDocument()
  expect(await screen.findByText('回测成交不可用', {}, { timeout: 5000 })).toBeInTheDocument()
  expect(screen.queryByText('0 笔')).not.toBeInTheDocument()

  backtestDetailFailure = false
  backtestTradesFailure = false
  await act(async () => { await client.invalidateQueries({ queryKey: ['backtests', hash] }) })
  expect(await screen.findByLabelText('回测净值、基准和回撤曲线')).toBeInTheDocument()
  expect(await screen.findByText('510300.SH', { selector: '.backtest-trade-row strong' })).toBeInTheDocument()

  backtestDetailFailure = true
  backtestTradesFailure = true
  await act(async () => { await client.invalidateQueries({ queryKey: ['backtests', hash] }) })
  expect(await screen.findByText('报告详情不可用', {}, { timeout: 5000 })).toBeInTheDocument()
  expect(await screen.findByText('回测成交不可用', {}, { timeout: 5000 })).toBeInTheDocument()
  expect(screen.queryByLabelText('回测净值、基准和回撤曲线')).not.toBeInTheDocument()
  expect(screen.queryByText('510300.SH', { selector: '.backtest-trade-row strong' })).not.toBeInTheDocument()
  expect(screen.queryByText('0 笔')).not.toBeInTheDocument()
}, 30000)

test('shows unavailable target evidence and an old-epoch queue item as separate facts', async () => {
  strategyDetailEnabled = true
  eligibilityTargetCoverage = 'unavailable'
  eligibilityItems = [{
    strategy_id: 'strategy-a', strategy_version: '1.0.0', display_name: '策略 A',
    strategy_lineage_id: 'strategy-a@current', genesis_epoch_id: 'current-epoch',
    configured_enabled: true, configured_budget: 0.2, disabled: false,
    automation_candidate: false, candidate_ready: false, projection_state: 'unavailable',
    valid_target_available: false, dependency_status: { valid_target: 'unavailable' },
    today_pending_count: 1, today_completed_count: 0, today_failed_count: 0,
    blocking_issue_codes: ['valid_target_unavailable', 'execution_queue_epoch_mismatch'],
  }]
  executionQueueItems = [{
    schema_version: '1.0', queue_item_id: '00000000-0000-4000-8000-000000000704',
    correlation_id: '10000000-0000-4000-8000-000000000705',
    identity: { source_kind: 'automatic_strategy', strategy_lineage_id: 'strategy-a@old', genesis_epoch_id: 'old-epoch' },
    strategy_id: 'strategy-a', strategy_version: '1.0.0', config_version: 'direction-v7',
    symbol: '510300.SH', side: 'buy', target_quantity: 6000, completed_quantity: 0, remaining_quantity: 6000,
    stage: 'risk_pending', wait_state: null, stage_entered_at: bootstrap.generated_at,
    last_changed_at: bootstrap.generated_at, event_at: bootstrap.generated_at,
    originated_before_today: false, changed_today: true, blocking_issue_codes: [], next_legal_stage: 'approved',
    risk_status: 'pending', approval_status: 'not_reached', command_status: 'not_reached',
  }]
  renderApp('/strategies?strategy=strategy-a@1.0.0&tab=configuration')
  const strategyCell = await screen.findByText('策略 A', { selector: '.eligibility-strategy-select strong' })
  const row = strategyCell.closest('.eligibility-row')
  expect(row).not.toBeNull()
  expect(within(row as HTMLElement).getByText('不可用')).toBeInTheDocument()
  expect(await screen.findByText('与当前资本身份不一致')).toBeInTheDocument()
  expect(screen.queryByText('权威队列覆盖完整，所选策略当前没有当天或跨日未终态事项。')).not.toBeInTheDocument()
})

test.each([
  ['/dashboard', '首页今日订单汇总'],
  ['/orders', '今日订单阶段汇总'],
])('hides cached queue coverage after a refresh failure in %s', async (path, summaryLabel) => {
  const { client } = renderApp(path)
  expect(await screen.findByLabelText(summaryLabel)).toBeInTheDocument()
  executionQueueRefreshFails = true
  await act(async () => { await client.invalidateQueries({ queryKey: ['orders', 'execution-queue'] }) })
  await waitFor(() => expect(screen.queryByLabelText(summaryLabel)).not.toBeInTheDocument())
  expect(screen.queryByText('今日没有订单或待执行事项')).not.toBeInTheDocument()
  expect(screen.queryByText('当前没有队列事项')).not.toBeInTheDocument()

  executionQueueRefreshFails = false
  await act(async () => { await client.invalidateQueries({ queryKey: ['orders', 'execution-queue'] }) })
  expect(await screen.findByLabelText(summaryLabel)).toBeInTheDocument()
})

test('hides cached account batches after a refresh failure', async () => {
  const { client } = renderApp('/orders')
  expect(await screen.findByText('成交待账本吸收')).toBeInTheDocument()
  accountExecutionRefreshFails = true
  await act(async () => { await client.invalidateQueries({ queryKey: ['orders', 'account-execution-batches'] }) })
  expect(await screen.findByText('账户协调投影不可用')).toBeInTheDocument()
  expect(screen.queryByText('成交待账本吸收')).not.toBeInTheDocument()
  accountExecutionRefreshFails = false
  await act(async () => { await client.invalidateQueries({ queryKey: ['orders', 'account-execution-batches'] }) })
  expect(await screen.findByText('成交待账本吸收')).toBeInTheDocument()
})

test('shows account batch allocation and executed-unabsorbed reservation ownership', async () => {
  renderApp('/orders')
  expect(await screen.findByText('执行批次、资金分配与预留')).toBeInTheDocument()
  expect(await screen.findByText('成交待账本吸收')).toBeInTheDocument()
  expect(screen.getAllByText('strategy-a').length).toBeGreaterThan(0)
  expect(screen.getByText('成交待吸收 2000 · 已释放 0')).toBeInTheDocument()
  expect(screen.queryByText('account-1')).not.toBeInTheDocument()
})

test('drills from an execution queue item into the authoritative command and execution audit chain', async () => {
  const correlationId = '10000000-0000-4000-8000-000000000705'
  executionQueueItems = [{
    schema_version: '1.0', queue_item_id: '00000000-0000-4000-8000-000000000704', correlation_id: correlationId,
    identity: { source_kind: 'automatic_strategy', strategy_lineage_id: 'strategy-a@lineage-1', genesis_epoch_id: 'epoch-1' },
    strategy_id: 'strategy-a', strategy_version: '1.0.0', config_version: 'direction-v7',
    symbol: '510300.SH', side: 'buy', target_quantity: 6000, completed_quantity: 0, remaining_quantity: 6000,
    stage: 'risk_pending', wait_state: null, stage_entered_at: bootstrap.generated_at,
    last_changed_at: bootstrap.generated_at, event_at: bootstrap.generated_at,
    originated_before_today: false, changed_today: true, blocking_issue_codes: [], next_legal_stage: 'approved',
    risk_status: 'pending', approval_status: 'not_reached', command_status: 'not_reached',
  }]

  renderApp('/orders')

  const link = await screen.findByRole('link', { name: '查看命令 / QMT / 执行审计链' })
  expect(link).toHaveAttribute('href', '#order-audit-chain')
  fireEvent.click(link)
  expect(await screen.findByText('策略意图已形成')).toBeInTheDocument()
  expect(screen.getByText('尚未形成命令事实')).toBeInTheDocument()
  expect(screen.getByText(correlationId)).toBeInTheDocument()
  expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes(`/v1/ui/orders/${correlationId}/trace`))).toBe(true)
})

test('opens bounded error logs and keeps system status read-only', async () => {
  const data: ConsoleBootstrap = {
    ...bootstrap,
    overview: {
      ...bootstrap.overview,
      operations: {
        healthy: true,
        platform_services_ready: true,
        services: [],
        alerts: [],
        trading_facts: {
          risk_approval_count: 0,
          order_command_count: 0,
          execution_event_count: 0,
          dead_letter_event_count: 0,
        },
      },
    },
  }
  renderApp('/operations', data)
  await screen.findByRole('heading', { name: '系统状态' })

  fireEvent.click(screen.getByRole('button', { name: '错误日志' }))
  expect(await screen.findAllByText('资本投影失败')).toHaveLength(2)
  expect(screen.getByText(/2 次/)).toBeInTheDocument()
  expect(screen.getByText('14 天 · 已验证')).toBeInTheDocument()
  expect(screen.getAllByText('0 条')).toHaveLength(2)

  expect(screen.queryByRole('button', { name: /重试交易|撤单|开启自动执行/ })).not.toBeInTheDocument()
})



test('keeps a critical automation fault visible globally and explains it on system status', async () => {
  const issue = {
    schema_version: '1.0' as const,
    issue_key: 'portfolio:automation_loop_failed:platform:automation',
    issue_code: 'automation_loop_failed',
    source_component: 'portfolio',
    severity: 'critical' as const,
    impact_scope_kind: 'platform' as const,
    impact_scope_id: 'automation',
    lifecycle: 'active' as const,
    last_authoritative_state: 'active' as const,
    revision: 1,
    retryable: true,
    user_safe_summary: '自动执行循环发生错误，新交易风险已阻断',
    reason_parameters: {},
    evidence_refs: ['portfolio:automation-runtime'],
    first_observed_at: '2026-08-19T00:58:00Z',
    last_observed_at: '2026-08-19T01:00:00Z',
    last_authoritative_observed_at: '2026-08-19T01:00:00Z',
  }
  const runtime = {
    schema_version: '1.0' as const,
    generated_at: '2026-08-19T01:00:00Z',
    automation_gate: 'enabled' as const,
    loop_state: 'blocked' as const,
    business_health: 'blocked' as const,
    trading_impact: 'new_risk_blocked' as const,
    last_successful_loop_at: '2026-08-19T00:57:00Z',
    current_block_started_at: '2026-08-19T00:58:00Z',
    last_observed_at: '2026-08-19T01:00:00Z',
    source_component: 'portfolio' as const,
    issues: [issue],
  }
  const data: ConsoleBootstrap = {
    ...bootstrap,
    overview: {
      ...bootstrap.overview,
      trading_operations: {
        schema_version: '1.0',
        generated_at: '2026-08-19T01:00:00Z',
        automation_runtime: runtime,
        automation_runtime_sources: { portfolio: runtime },
        active_issues: [issue],
        reconciliations: [],
        observability_stack_status: { portfolio: 'healthy', operations: 'healthy' },
        source_coverage: { portfolio: 'complete', operations: 'complete' },
        read_only: true,
        executable: false,
      },
    },
  }

  renderApp('/operations', data)

  const alert = await screen.findByRole('alert', { name: '自动执行严重故障' })
  expect(alert).toHaveTextContent('自动执行受阻')
  expect(alert).toHaveTextContent('自动执行循环发生错误，新交易风险已阻断')
  expect(screen.getByRole('link', { name: '查看故障详情' })).toHaveAttribute('href', '/operations')
  expect(screen.getByLabelText('运行状态分层')).toHaveTextContent('已阻断 · 交易受阻')
  expect(screen.getByText('automation_loop_failed')).toBeInTheDocument()
  expect(screen.getByLabelText('1 个严重故障')).toHaveTextContent('1')
  fireEvent.click(screen.getByText('证据、原因与建议下一步'))
  expect(screen.getByText('权威证据引用')).toBeInTheDocument()
  expect(screen.getByText('portfolio:automation-runtime')).toBeInTheDocument()
  expect(screen.getByText(/当前 issue 没有逐阶段身份绑定时保持不可用/)).toBeInTheDocument()
  expect(screen.queryByText(/意图 \/ 目标：未绑定权威事实/)).not.toBeInTheDocument()
})

test('keeps a conflicted Console runtime unavailable across system status and dashboard', async () => {
  const observedAt = bootstrap.generated_at
  const operationsRuntime = {
    schema_version: '1.0' as const,
    generated_at: observedAt,
    automation_gate: 'enabled' as const,
    loop_state: 'waiting' as const,
    business_health: 'healthy' as const,
    trading_impact: 'none' as const,
    last_observed_at: observedAt,
    source_component: 'portfolio' as const,
    issues: [],
  }
  const mismatch = {
    schema_version: '1.0' as const,
    issue_key: 'console:status_projection_mismatch:platform:automation',
    issue_code: 'status_projection_mismatch',
    source_component: 'console',
    severity: 'critical' as const,
    impact_scope_kind: 'platform' as const,
    impact_scope_id: 'automation',
    lifecycle: 'active' as const,
    last_authoritative_state: 'active' as const,
    revision: 1,
    retryable: true,
    user_safe_summary: 'Portfolio 与 Operations 自动执行状态不一致',
    reason_parameters: {},
    evidence_refs: ['portfolio:automation-runtime', 'operations:automation-runtime'],
    first_observed_at: observedAt,
    last_observed_at: observedAt,
    last_authoritative_observed_at: observedAt,
  }
  const data: ConsoleBootstrap = {
    ...bootstrap,
    overview: {
      ...bootstrap.overview,
      operations: {
        healthy: true,
        platform_services_ready: true,
        services: [],
        alerts: [],
        trading_facts: {
          risk_approval_count: 0, order_command_count: 0,
          execution_event_count: 0, dead_letter_event_count: 0,
        },
        automation_runtime: operationsRuntime,
      },
      trading_operations: {
        schema_version: '1.0',
        generated_at: observedAt,
        automation_runtime: null,
        automation_runtime_sources: {
          portfolio: { ...operationsRuntime, loop_state: 'idle' },
          operations: operationsRuntime,
        },
        active_issues: [mismatch],
        reconciliations: [],
        observability_stack_status: {},
        source_coverage: { automation_runtime_projection_consistency: 'partial' },
        read_only: true,
        executable: false,
      },
    },
  }

  renderApp('/operations', data)
  expect(await screen.findByRole('heading', { name: '系统状态' })).toBeInTheDocument()
  expect(screen.getByLabelText('运行状态分层')).toHaveTextContent('整体状态不可确认')
  expect(screen.getByText('status_projection_mismatch')).toBeInTheDocument()
  cleanup()

  renderApp('/dashboard', data)
  expect(await screen.findByRole('heading', { name: '总览' })).toBeInTheDocument()
  expect(screen.getByLabelText('总览运行状态分层')).toHaveTextContent('整体状态不可确认')
  expect(screen.getByLabelText('总览运行状态分层')).not.toHaveTextContent('仅 Operations 观察')
})

test.each([
  ['portfolio', 'Portfolio'],
  ['operations', 'Operations'],
] as const)('keeps only %s facts visible while overall automation health remains unconfirmed', async (source, label) => {
  const observedAt = bootstrap.generated_at
  const observed = {
    schema_version: '1.0' as const,
    generated_at: observedAt,
    automation_gate: 'enabled' as const,
    loop_state: 'waiting' as const,
    business_health: 'healthy' as const,
    trading_impact: 'none' as const,
    last_observed_at: observedAt,
    source_component: 'portfolio' as const,
    issues: [],
  }
  const data: ConsoleBootstrap = {
    ...bootstrap,
    overview: {
      ...bootstrap.overview,
      automation_gate: {
        active_config_id: 'direction-7', global_kill_switch: false,
        account_kill_switch: false, auto_execution_enabled: true, updated_at: observedAt,
      },
      trading_operations: {
        schema_version: '1.0', generated_at: observedAt,
        automation_runtime: null,
        automation_runtime_sources: { [source]: observed },
        active_issues: [], reconciliations: [], observability_stack_status: {},
        source_coverage: { automation_runtime_projection_consistency: 'partial' },
        read_only: true, executable: false,
      },
    },
  }

  renderApp('/operations', data)

  expect(await screen.findByRole('heading', { name: '系统状态' })).toBeInTheDocument()
  expect(screen.getByRole('alert', { name: '自动执行严重故障' })).toHaveTextContent('自动执行状态不可确认')
  expect(screen.getByRole('status', { name: '自动执行状态覆盖缺口' })).toHaveTextContent(`仅 ${label} 提供最近观察`)
  expect(screen.getByLabelText('运行状态分层')).toHaveTextContent(`仅 ${label} 观察：等待条件 · 业务正常`)
  expect(screen.getByLabelText('运行状态分层')).toHaveTextContent('整体状态不可确认')
  expect(screen.getByText('故障覆盖不完整，无法确认当前没有故障')).toBeInTheDocument()
  cleanup()

  renderApp('/dashboard', data)
  expect(await screen.findByRole('heading', { name: '总览' })).toBeInTheDocument()
  expect(screen.getByLabelText('总览运行状态分层')).toHaveTextContent('整体状态不可确认')
  expect(screen.getByLabelText('总览运行状态分层')).toHaveTextContent(`仅 ${label} 观察：正常等待 · 业务正常；另一来源缺失`)
})

test('shows reconciled healthy automation only when both owner observations agree', async () => {
  const observedAt = bootstrap.generated_at
  const observed = {
    schema_version: '1.0' as const,
    generated_at: observedAt,
    automation_gate: 'enabled' as const,
    loop_state: 'waiting' as const,
    business_health: 'healthy' as const,
    trading_impact: 'none' as const,
    last_observed_at: observedAt,
    source_component: 'portfolio' as const,
    issues: [],
  }
  const data: ConsoleBootstrap = {
    ...bootstrap,
    overview: {
      ...bootstrap.overview,
      trading_operations: {
        schema_version: '1.0', generated_at: observedAt,
        automation_runtime: observed,
        automation_runtime_sources: { portfolio: observed, operations: observed },
        active_issues: [], reconciliations: [], observability_stack_status: {},
        source_coverage: { automation_runtime_projection_consistency: 'complete' },
        read_only: true, executable: false,
      },
    },
  }

  renderApp('/operations', data)

  expect(await screen.findByRole('heading', { name: '系统状态' })).toBeInTheDocument()
  expect(screen.queryByRole('status', { name: '自动执行状态覆盖缺口' })).not.toBeInTheDocument()
  expect(screen.getByLabelText('运行状态分层')).toHaveTextContent('等待条件 · 业务正常')
})

test('shows the newer Portfolio fact as partial while Operations catches up', async () => {
  const observedAt = bootstrap.generated_at
  const portfolioRuntime = {
    schema_version: '1.0' as const, generated_at: observedAt,
    automation_gate: 'enabled' as const, loop_state: 'waiting' as const,
    business_health: 'healthy' as const, trading_impact: 'none' as const,
    last_observed_at: observedAt, source_component: 'portfolio' as const, issues: [],
  }
  const data: ConsoleBootstrap = {
    ...bootstrap,
    overview: {
      ...bootstrap.overview,
      automation_gate: {
        active_config_id: 'direction-7', global_kill_switch: false,
        account_kill_switch: false, auto_execution_enabled: true, updated_at: observedAt,
      },
      trading_operations: {
        schema_version: '1.0', generated_at: observedAt,
        automation_runtime: portfolioRuntime,
        automation_runtime_sources: {
          portfolio: portfolioRuntime,
          operations: { ...portfolioRuntime, loop_state: 'idle', last_observed_at: '2026-08-19T00:59:30Z' },
        },
        active_issues: [], reconciliations: [], observability_stack_status: {},
        source_coverage: { automation_runtime_projection_consistency: 'partial' },
        read_only: true, executable: false,
      },
    },
  }

  renderApp('/operations', data)

  expect(await screen.findByRole('heading', { name: '系统状态' })).toBeInTheDocument()
  expect(screen.getByLabelText('运行状态分层')).toHaveTextContent('整体状态不可确认')
  expect(screen.getByLabelText('运行状态分层')).toHaveTextContent('Portfolio 最新观察：等待条件 · 业务正常')
  expect(screen.getByRole('status', { name: '自动执行状态覆盖缺口' })).toHaveTextContent('两路状态尚未一致')
})

test('fails visibly when automation is enabled but both runtime sources are unavailable', async () => {
  const data: ConsoleBootstrap = {
    ...bootstrap,
    overview: {
      ...bootstrap.overview,
      automation_gate: {
        active_config_id: 'direction-7',
        global_kill_switch: false,
        account_kill_switch: false,
        auto_execution_enabled: true,
        updated_at: bootstrap.generated_at,
      },
      trading_operations: {
        schema_version: '1.0',
        generated_at: bootstrap.generated_at,
        automation_runtime: null,
        automation_runtime_sources: {},
        active_issues: [],
        reconciliations: [],
        observability_stack_status: {},
        source_coverage: { portfolio: 'unavailable', operations: 'unavailable' },
        read_only: true,
        executable: false,
      },
    },
  }

  renderApp('/dashboard', data)

  const alert = await screen.findByRole('alert', { name: '自动执行严重故障' })
  expect(alert).toHaveTextContent('自动执行状态不可确认')
  expect(alert).toHaveTextContent('不能把无数据解释为运行正常')
  expect(screen.getByLabelText('1 个严重故障')).toHaveTextContent('1')
})

test('shows authoritative account capital reconciliation separately from bridge account state', async () => {
  const data: ConsoleBootstrap = {
    ...bootstrap,
    overview: {
      ...bootstrap.overview,
      trading_operations: {
        schema_version: '1.0',
        generated_at: bootstrap.generated_at,
        automation_runtime: null,
        automation_runtime_sources: {},
        active_issues: [],
        reconciliations: [{
          schema_version: '1.1',
          account_label: '********1314',
          account_boundary_captured_at: bootstrap.generated_at,
          broker_cash: 900, broker_market_value: 100, broker_total_asset: 1000,
          broker_reported_asset_gap: 7,
          reference_fee_reserve_limit: 9,
          unallocated_reference_fee_balance: 7,
          strategy_sleeve_count: 1,
          strategy_sleeves: [{
            schema_version: '1.1', strategy_lineage_id: 'strategy-a@lineage-1',
            genesis_epoch_id: '00000000-0000-4000-8000-000000000111',
            virtual_cash: 810,
            positions: [{ schema_version: '1.0', symbol: '510300.SH', quantity: 100, valuation_price: 1, market_value: 100 }],
            market_value: 100, net_asset_value: 910,
            realized_pnl: null, unrealized_pnl: null, fees: null, total_return: null,
            daily_return: null, opening_net_asset_value: null,
            pnl_metrics_available: false, daily_return_available: false,
            valuation_at: bootstrap.generated_at,
            valuation_source: 'account_capital_reconciliation',
            reconciliation_status: 'unavailable',
            reconciliation_issue_codes: ['strategy_capital_snapshot_unavailable'],
            account_boundary_captured_at: bootstrap.generated_at,
          }],
          non_strategy_ownership: [
            { schema_version: '1.0', owner_kind: 'external_manual', position_count: 0, total_quantity: 0, market_value: 0 },
            { schema_version: '1.0', owner_kind: 'operator_manual', position_count: 0, total_quantity: 0, market_value: 0 },
            { schema_version: '1.0', owner_kind: 'unknown_history', position_count: 0, total_quantity: 0, market_value: 0 },
          ],
          unallocated_strategy_reserve: 100, independent_cash: 0,
          cash_residual: -90, market_value_residual: 0, asset_residual: -90,
          amount_tolerance: 0.07, reflected_state: 'known', status: 'blocked',
          blocking_issue_codes: ['account_capital_residual'], calculated_at: bootstrap.generated_at,
        }],
        observability_stack_status: {},
        source_coverage: { account_capital_reconciliation: 'complete' },
        read_only: true,
        executable: false,
      },
    },
  }

  const sleeves = data.overview.trading_operations!.reconciliations[0].strategy_sleeves
  sleeves.push({
    ...sleeves[0], strategy_lineage_id: 'strategy-b@lineage-2',
    strategy_id: 'strategy-b', strategy_version: 'v2', positions: [],
  })
  data.overview.trading_operations!.reconciliations[0].strategy_sleeve_count = 2
  renderApp('/portfolio', data)

  await screen.findByRole('heading', { name: '策略' })
  await screen.findByRole('heading', { name: '账户资本对账' })
  expect(screen.getByLabelText('账户资本对账状态')).toHaveTextContent('账户资本差异阻断')
  expect(screen.getByLabelText('账户资本对账状态')).toHaveTextContent('¥1,000.00')
  expect(screen.getByLabelText('账户资本对账状态')).toHaveTextContent('-¥90.00')
  expect(screen.getByLabelText('账户资本对账状态')).toHaveTextContent('QMT 原始字段差额¥7.00')
  expect(screen.getByLabelText('账户资本对账状态')).toHaveTextContent('参考费用预留上界¥9.00')
  expect(screen.getByLabelText('账户资本对账状态')).toHaveTextContent('待核对未分配余额¥7.00')
  expect(screen.getByLabelText('账户资本对账状态')).toHaveTextContent('暂不增加策略预算及收益')
  expect(screen.getByLabelText('账户资本对账状态')).toHaveTextContent('原因待核')
  expect(screen.getByLabelText('人工与未知归属明细')).toHaveTextContent('未知历史归属')
  expect(screen.getByText('策略资金不可用')).toBeInTheDocument()
  expect(screen.getByText('账户资本金额与策略袖套、储备及人工资金合计不一致')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /激活|重建|修改|执行/ })).not.toBeInTheDocument()
})



test('shows an authoritative empty strategy set on the portfolio route', async () => {
  const data: ConsoleBootstrap = {
    ...bootstrap,
    overview: {
      ...bootstrap.overview,
      trading_operations: {
        schema_version: '1.0', generated_at: bootstrap.generated_at,
        automation_runtime: null, automation_runtime_sources: {}, active_issues: [],
        reconciliations: [{
          schema_version: '1.1', account_label: '********1314',
          account_boundary_captured_at: bootstrap.generated_at,
          strategy_sleeve_count: 0, strategy_sleeves: [], non_strategy_ownership: [],
          amount_tolerance: 0.07, reflected_state: 'known', status: 'reconciled',
          blocking_issue_codes: [], calculated_at: bootstrap.generated_at,
        }],
        observability_stack_status: {}, source_coverage: {}, read_only: true, executable: false,
      },
    },
  }
  renderApp('/portfolio', data)
  await screen.findByRole('heading', { name: '策略' })
  expect(screen.getByLabelText('账户资本对账状态')).toHaveTextContent('策略资金袖套0 个')
  cleanup()
  data.overview.trading_operations!.reconciliations[0].reflected_state = 'unavailable'
  renderApp('/portfolio', data)
  await screen.findByRole('heading', { name: '策略' })
  expect(screen.getByLabelText('账户资本对账状态')).toHaveTextContent('策略资金袖套不可用')
  expect(screen.getByLabelText('账户资本对账状态')).toHaveTextContent('持仓归属事实不可用')
  expect(screen.queryByText('当前权威边界没有自动策略资金袖套')).not.toBeInTheDocument()
})



test('shows the holdings source failure reason on a direct portfolio visit', async () => {
  const data: ConsoleBootstrap = {
    ...bootstrap,
    overview: {
      ...bootstrap.overview,
      trading_operations: undefined,
      errors: { account_capital_reconciliation: 'portfolio source unavailable' },
    },
  }
  renderApp('/portfolio', data)
  await screen.findByRole('heading', { name: '策略' })
  expect(screen.getAllByText(/portfolio source unavailable/).length).toBeGreaterThan(0)
})

test('keeps detailed strategy positions outside system status', async () => {
  renderApp('/operations')
  await screen.findByRole('heading', { name: '系统状态' })
  expect(screen.queryByRole('heading', { name: '账户资本对账' })).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: '策略' })).toBeInTheDocument()
})

test('waits for eligibility before selecting the default active strategy', async () => {
  await import('./pages/StrategyPage')
  registryStrategies = [{ strategy_id: 'inactive', strategy_version: '1', display_name: '未纳入策略' }, { strategy_id: 'strategy-a', strategy_version: '1.0.0', display_name: '策略 A' }]
  strategyDetailEnabled = true
  let release!: (response: Response) => void
  eligibilityDeferred = new Promise(resolve => { release = resolve })
  renderApp('/strategies')
  await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes('/strategies/registry'))).toBe(true))
  expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes('/strategies/inactive/versions'))).toBe(false)
  await act(async () => release(new Response(JSON.stringify({ items: [{ strategy_id: 'strategy-a', strategy_version: '1.0.0', configured_enabled: true }], source_coverage: { strategy_registry: 'complete', strategy_runtime: 'complete', active_config: 'complete', automation_runtime: 'complete', execution_queue: 'complete', strategy_portfolio_targets: 'complete' } }), { status: 200 })))
  await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes('/strategies/strategy-a/versions/1.0.0'))).toBe(true))
  expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes('/strategies/inactive/versions'))).toBe(false)
})

test('shows unavailable strategy report binding instead of a confirmed empty history', async () => {
  strategyDetailEnabled = true
  strategyReportBindingUnavailable = true
  backtestReportsFixture = [{ report_hash: 'a'.repeat(64), model_version: '未绑定来源报告', dataset_version: 'shared', total_return: .1, maximum_drawdown: .01 }]
  renderApp('/strategies?strategy=strategy-a@1.0.0&tab=backtests', { ...bootstrap, backtest_reports_available: true })
  expect(await screen.findByText('策略回测关联不可用')).toBeVisible()
  expect(screen.queryByText('暂无回测报告')).not.toBeInTheDocument()
  expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes('/backtests/reports/' + 'a'.repeat(64)))).toBe(false)
})

function historicalOrder(correlation: string, symbol = '510300.SH', strategy = 'strategy-a'): OrderSummary {
  return { schema_version: '1.1', command_id: correlation, correlation_id: correlation, execution_mode: 'simulation', strategy_id: strategy, symbol, side: 'buy', quantity: 100, status: 'filled', created_at: bootstrap.generated_at, execution_detail_available: true, filled_quantity: 100 }
}

test.each([false, true])('opens the selected non-first or later-page historical order trace (laterPage=%s)', async laterPage => {
  const first = '00000000-0000-4000-8000-000000000101'
  const target = '00000000-0000-4000-8000-000000000102'
  const original = vi.mocked(fetch).getMockImplementation()!
  vi.mocked(fetch).mockImplementation((input, init) => {
    const url = String(input)
    if (!url.includes('/v1/ui/orders?')) return original(input, init)
    const params = new URL(url, 'http://localhost').searchParams
    const offset = Number(params.get('offset'))
    const correlation = params.get('correlation_id')
    const items = correlation ? [historicalOrder(correlation, '510500.SH')] : laterPage && !offset ? [historicalOrder(first)] : [historicalOrder(first), historicalOrder(target, '510500.SH')]
    return Promise.resolve(Response.json({ items, total: correlation ? 1 : laterPage ? 22 : 2, offset, limit: 20, has_more: !correlation && laterPage && !offset }))
  })
  renderApp('/strategies?strategy=strategy-a@1.0.0&tab=trades')
  await screen.findByRole('heading', { name: '历史交易记录' })
  if (laterPage) { await waitFor(() => expect(screen.getByRole('button', { name: '下一页' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: '下一页' })) }
  await waitFor(() => expect(screen.getAllByRole('link', { name: '因果链' })).toHaveLength(2))
  fireEvent.click(screen.getAllByRole('link', { name: '因果链' })[1])
  await screen.findByRole('heading', { name: '决策因果链' })
  await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes(`/orders/${target}/trace`))).toBe(true))
  expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes(`/orders/${first}/trace`))).toBe(false)
  expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes(`correlation_id=${target}`))).toBe(true)
})

test('keeps late previous-strategy pagination responses outside the selected strategy', async () => {
  registryStrategies = ['a', 'b'].map(id => ({ strategy_id: `strategy-${id}`, strategy_version: '1.0.0', display_name: `策略 ${id.toUpperCase()}` }))
  eligibilityItems = registryStrategies.map(item => ({ ...item, configured_enabled: true }))
  const original = vi.mocked(fetch).getMockImplementation()!
  let release!: (response: Response) => void
  const late = new Promise<Response>(resolve => { release = resolve })
  vi.mocked(fetch).mockImplementation((input, init) => {
    const url = String(input)
    if (!url.includes('/v1/ui/orders?')) return original(input, init)
    const params = new URL(url, 'http://localhost').searchParams
    const strategy = params.get('strategy_id')!
    if (strategy === 'strategy-a' && params.get('offset') === '20') return late
    return Promise.resolve(Response.json({ items: [historicalOrder('00000000-0000-4000-8000-000000000103', strategy === 'strategy-b' ? '159915.SZ' : '510300.SH', strategy)], total: 21, offset: 0, limit: 20, has_more: true }))
  })
  renderApp('/strategies?strategy=strategy-a@1.0.0&tab=trades')
  await screen.findByText('510300.SH')
  fireEvent.click(screen.getByRole('button', { name: '下一页' }))
  await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes('offset=20'))).toBe(true))
  fireEvent.click(await screen.findByRole('button', { name: /strategy-b@1.0.0/ }))
  await screen.findByText('159915.SZ')
  await act(async () => release(Response.json({ items: [historicalOrder('00000000-0000-4000-8000-000000000104', '588000.SH')], total: 21, offset: 20, limit: 20, has_more: false })))
  expect(screen.queryByText('588000.SH')).not.toBeInTheDocument()
  expect(screen.getByText('共 21 笔 · 第 1 页')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: '因果链' })).toHaveAttribute('href', expect.stringContaining('strategy_id=strategy-b'))
})

test('rejects an invalid URL trace identity without querying another order', async () => {
  renderApp('/orders?strategy_id=strategy-a&correlation_id=invalid')
  expect(await screen.findByText('关联链标识必须是完整 UUID。')).toBeVisible()
  expect(vi.mocked(fetch).mock.calls.some(([input]) => /\/orders\?|\/orders\/invalid\/trace/.test(String(input)))).toBe(false)
})


test.each([['/portfolio', '持仓与目标'], ['/backtests', '回测']])('restores legacy workspace route %s into its selected strategy tab', async (path, tab) => {
  strategyDetailEnabled = true
  renderApp(`${path}?strategy=strategy-a@1.0.0&lineage=fixture-lineage&epoch=fixture-epoch`)
  const tabs = await screen.findByRole('tablist', { name: '策略详情标签' })
  expect(within(tabs).getAllByRole('tab')).toHaveLength(7)
  expect(within(tabs).getByRole('tab', { name: tab })).toHaveAttribute('aria-selected', 'true')
  expect(screen.queryByRole('link', { name: '分策略持仓' })).not.toBeInTheDocument()
  await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes('/strategies/strategy-a/versions/1.0.0'))).toBe(true))
  fireEvent.keyDown(within(tabs).getByRole('tab', { name: tab }), { key: 'End' })
  expect(within(tabs).getByRole('tab', { name: '配置与运行' })).toHaveAttribute('aria-selected', 'true')
  expect(within(tabs).getByRole('tab', { name: '配置与运行' })).toHaveFocus()
})
