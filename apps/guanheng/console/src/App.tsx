import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  Blocks,
  CandlestickChart,
  ChevronRight,
  LayoutDashboard,
  ReceiptText,
  ServerCog,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Component, Fragment, lazy, Suspense, useEffect, useMemo, useState } from 'react'
import type { ErrorInfo, ReactNode } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'

import {
  BOOTSTRAP_QUERY_KEY,
  fetchBootstrap,
  fetchOverview,
  fetchProblemDictionary,
  OVERVIEW_QUERY_KEY,
} from './api'
import { ActivityDrawer } from './components/ActivityDrawer'
import { ConnectionDetails } from './components/ConnectionDetails'
import { StatusPill } from './components/StatusPill'
import { WorkspaceLoading } from './components/WorkspaceLoading'
import { connectionStateLabel } from './diagnosticPresentation'
import { useConsoleStream } from './hooks/useConsoleStream'
import { useQmtConnectionStatus } from './hooks/useQmtConnectionStatus'
import { OperationsPage } from './pages/OperationsPage'
import { installProblemDictionary } from './problemDictionary'
import type {
  ConsoleBootstrap,
  QMTConnectionLayer,
  QMTConnectionLayerState,
  WorkspaceId,
} from './types'

const ObservationShell = lazy(() => import('./observation/ObservationShell'))
import projectBrand from '../config/project-branding.json'

const workspaceLoaders = {
  dashboard: () => import('./pages/DashboardPage'),
  market: () => import('./pages/MarketPage'),
  strategies: () => import('./pages/StrategyPage'),
  portfolio: () => import('./pages/PortfolioPage'),
  orders: () => import('./pages/OrdersPage'),
  // Operations is the recovery surface for every other workspace. Keep it in
  // the shell bundle so a failed or stalled lazy chunk cannot hide diagnostics.
  operations: () => Promise.resolve({ OperationsPage }),
}

function preloadWorkspace(id: WorkspaceId) {
  if (typeof window !== 'undefined') {
    void workspaceLoaders[id]().catch(() => undefined)
  }
}

const DashboardPage = lazy(() => workspaceLoaders.dashboard().then((module) => ({ default: module.DashboardPage })))
const MarketPage = lazy(() => workspaceLoaders.market().then((module) => ({ default: module.MarketPage })))
const StrategyPage = lazy(() => workspaceLoaders.strategies().then((module) => ({ default: module.StrategyPage })))
const OrdersPage = lazy(() => workspaceLoaders.orders().then((module) => ({ default: module.OrdersPage })))

const navigation = [
  { id: 'dashboard', label: '总览', icon: LayoutDashboard },
  { id: 'market', label: '行情', icon: CandlestickChart },
  { id: 'strategies', label: '策略', icon: Blocks },
  { id: 'orders', label: '交易记录', icon: ReceiptText },
  { id: 'operations', label: '系统状态', icon: ServerCog },
] satisfies Array<{ id: WorkspaceId; label: string; icon: typeof LayoutDashboard }>

function Shell({
  bootstrap,
  bootstrapRefreshFailed = false,
  bootstrapLastSuccessAt = 0,
}: {
  bootstrap: ConsoleBootstrap
  bootstrapRefreshFailed?: boolean
  bootstrapLastSuccessAt?: number
}) {
  const location = useLocation()
  const [activityOpen, setActivityOpen] = useState(false)
  useQuery({
    queryKey: ['problem-dictionary'],
    queryFn: async ({ signal }) => installProblemDictionary(await fetchProblemDictionary(signal)),
    staleTime: 300_000,
    retry: 1,
  })
  // Keep the authoritative read-only stream active even while the drawer is closed so
  // visible account, order and strategy projections refresh without a page reload.
  const stream = useConsoleStream(true)
  const needsDetailedOverview = location.pathname === '/dashboard'
    || location.pathname === '/operations'
    || location.pathname === '/portfolio'
    || location.pathname === '/strategies'
  const overviewQuery = useQuery({
    queryKey: OVERVIEW_QUERY_KEY,
    queryFn: ({ signal }) => fetchOverview(signal),
    enabled: bootstrap.overview_complete === false && needsDetailedOverview,
    staleTime: 10_000,
    refetchInterval: 30_000,
    retry: 1,
  })
  const overview = overviewQuery.data ?? bootstrap.overview
  const effectiveBootstrap = useMemo(
    () => overviewQuery.isError && needsDetailedOverview ? { ...bootstrap, overview: { ...overview, errors: { ...overview.errors, account_capital_reconciliation: '当前资金投影读取失败，请刷新或检查来源。' } } } : overview === bootstrap.overview ? bootstrap : { ...bootstrap, overview },
    [bootstrap, overview, overviewQuery.isError, needsDetailedOverview],
  )
  const account = overview.account
  const platformMode = overview.active_config?.mode ?? 'shadow'
  const agentMode = account?.trading_mode ?? 'unknown'
  const modeMatches = account == null || platformMode === agentMode
  const operations = overview.operations
  const platformServicesReady = operations?.platform_services_ready === true
  const tradingOperations = overview.trading_operations
  const automationRuntime = tradingOperations
    ? tradingOperations.automation_runtime
    : operations?.automation_runtime
  const runtimeIssues = tradingOperations?.active_issues ?? operations?.runtime_issues ?? []
  const criticalRuntimeIssues = runtimeIssues.filter(
    (item) => item.lifecycle !== 'resolved' && item.severity === 'critical',
  )
  const autoExecutionEnabled = overview.automation_gate?.auto_execution_enabled === true
  const automationRuntimeSourcesUnavailable = autoExecutionEnabled
    && tradingOperations?.automation_runtime_sources?.portfolio == null
    && tradingOperations?.automation_runtime_sources?.operations == null
  const automationRuntimeCoverageIncomplete = autoExecutionEnabled && (
    automationRuntimeSourcesUnavailable
    || tradingOperations?.source_coverage?.automation_runtime_projection_consistency === 'partial'
    || tradingOperations?.source_coverage?.automation_runtime_projection_consistency === 'unavailable'
  )
  const observedAutomationRuntime = automationRuntime
    ?? tradingOperations?.automation_runtime_sources?.portfolio
    ?? tradingOperations?.automation_runtime_sources?.operations
  const activeCriticalAlertCount = (operations?.alerts ?? []).filter(
    (item) => item.active && item.severity === 'critical',
  ).length
  const criticalNotificationCount = criticalRuntimeIssues.length
    + activeCriticalAlertCount
    + (automationRuntimeCoverageIncomplete ? 1 : 0)
  const overviewLastSuccessAt = overviewQuery.dataUpdatedAt > 0
    ? new Date(overviewQuery.dataUpdatedAt)
    : new Date(overview.generated_at)
  const overviewDataAgeSeconds = Math.max(0, Math.floor((Date.now() - overviewLastSuccessAt.getTime()) / 1000))
  const bootstrapLastSuccess = bootstrapLastSuccessAt > 0
    ? new Date(bootstrapLastSuccessAt)
    : new Date(bootstrap.generated_at)
  const bootstrapDataAgeSeconds = Math.max(0, Math.floor((Date.now() - bootstrapLastSuccess.getTime()) / 1000))
  const connectionQuery = useQmtConnectionStatus({
    refreshOnVisibility: true,
    initialData: bootstrap.qmt_connection_status,
  })
  const layers = new Map((connectionQuery.data?.layers ?? []).map((item) => [item.layer, item]))
  const gateway = layers.get('gateway')
  const agent = layers.get('agent')
  const accountLayer = layers.get('account')
  const heartbeat = agent?.observed_at
    ? `${new Date(agent.observed_at).toLocaleTimeString('zh-CN', { hour12: false })} · ${Math.round(agent.age_seconds ?? 0)} 秒前`
    : '暂无当前心跳'
  const readableMode = (mode: string) => mode === 'simulation'
    ? '模拟盘'
    : mode === 'live'
      ? '实盘'
      : mode === 'shadow'
        ? '影子模式'
        : '未知'
  const modeLabel = modeMatches
    ? `${readableMode(platformMode)}${platformMode === 'shadow' ? ' · 不下单' : ''}`
    : `平台 ${readableMode(platformMode)} · Agent ${readableMode(agentMode)}`

  return (
    <div className={`app-shell ${location.pathname === '/strategies' ? 'information-shell' : ''}`}>
      <a className="skip-link" href="#workspace-content">跳到主要内容</a>
      <aside className="sidebar" aria-label="工作区侧边栏">
        <div className="brand-lockup">
          <div className="brand-mark"><BarChart3 size={21} /></div>
          <div><strong>{projectBrand.short_name}</strong><span>{projectBrand.display_name}</span></div>
        </div>
        <nav aria-label="主要工作区">
          {navigation.map(({ id, label, icon: Icon }) => (<Fragment key={id}>
            {id === 'market' && <NavLink className="nav-item" to="/observation" aria-label="市场观察" title="市场观察"><BarChart3 size={18} aria-hidden="true" /><span>市场观察</span><ChevronRight className="nav-chevron" size={14} aria-hidden="true" /></NavLink>}
            <NavLink
              className={({ isActive }) => isActive ? 'nav-item nav-item-active' : 'nav-item'}
              key={id}
              to={`/${id}`}
              aria-label={label}
              title={label}
              onMouseEnter={() => preloadWorkspace(id)}
              onFocus={() => preloadWorkspace(id)}
            >
              <Icon size={18} aria-hidden="true" />
              <span>{label}</span>
              <ChevronRight className="nav-chevron" size={14} aria-hidden="true" />
            </NavLink>
          </Fragment>))}
        </nav>
        <div className="sidebar-footer">
          <span>本机工作站</span>
          <strong>只读展示台</strong>
        </div>
      </aside>

      <header className="topbar">
        <div className="system-statuses">
          <ConnectionPill label="QMT 网关" layer={gateway} loading={connectionQuery.isPending} failed={connectionQuery.isError} />
          <ConnectionPill label="AI_ETF 执行代理" layer={agent} loading={connectionQuery.isPending} failed={connectionQuery.isError} />
          <ConnectionPill label="账户" layer={accountLayer} loading={connectionQuery.isPending} failed={connectionQuery.isError} />
          {!platformServicesReady ? <StatusPill tone="warning">外围服务降级</StatusPill> : null}
          {bootstrapRefreshFailed ? (
            <StatusPill tone="danger">
              全局投影刷新失败 · 旧数据 {bootstrapDataAgeSeconds} 秒 · 最近成功 {bootstrapLastSuccess.toLocaleTimeString('zh-CN', { hour12: false })}
            </StatusPill>
          ) : overviewQuery.isError ? (
            <StatusPill tone="warning">
              详细投影降级 · 旧数据 {overviewDataAgeSeconds} 秒 · 最近成功 {overviewLastSuccessAt.toLocaleTimeString('zh-CN', { hour12: false })}
             </StatusPill>
           ) : null}
          <StatusPill tone="info">仅展示 · 操作请通过对话完成</StatusPill>
          <StatusPill tone={modeMatches ? 'info' : 'warning'}>{modeLabel}</StatusPill>
        </div>
        <div className="topbar-actions">
          <span className="heartbeat-label"><Activity size={14} /> 心跳 {heartbeat}</span>
          <ConnectionDetails
            status={connectionQuery.data}
            loading={connectionQuery.isPending}
            failed={connectionQuery.isError}
          />
          <button
            className="icon-button activity-button"
            type="button"
            aria-label="查看实时事件中心"
            aria-expanded={activityOpen}
            aria-controls="activity-drawer"
            onClick={() => setActivityOpen((value) => !value)}
          >
            <Bell size={17} />
            {criticalNotificationCount > 0 ? (
              <span className="activity-badge" aria-label={`${criticalNotificationCount} 个严重故障`}>
                {criticalNotificationCount > 99 ? '99+' : criticalNotificationCount}
              </span>
            ) : null}
          </button>
        </div>
      </header>

      <main className="workspace-main" id="workspace-content" tabIndex={-1}>
        {criticalRuntimeIssues.length || automationRuntimeCoverageIncomplete ? (
          <section className="runtime-critical-banner" role="alert" aria-label="自动执行严重故障">
            <AlertTriangle size={22} aria-hidden="true" />
            <div>
              <strong>{criticalRuntimeIssues.length ? '自动执行受阻' : '自动执行状态不可确认'}</strong>
              <span>
                {criticalRuntimeIssues.length
                  ? `${criticalRuntimeIssues[0].user_safe_summary}${automationRuntimeCoverageIncomplete ? '；另一来源覆盖不完整，整体状态仍需核对。' : ''}`
                  : automationRuntimeSourcesUnavailable
                    ? '自动执行开关已开启，但 Portfolio 与 Operations 均未提供运行态；系统按严重故障展示，不能把无数据解释为运行正常。'
                    : '自动执行开关已开启，但运行状态仅单侧可读或两路尚未一致；保留可读事实，整体健康无法确认。'}
              </span>
              <small>
                {bootstrapRefreshFailed
                  ? `当前为旧数据 ${bootstrapDataAgeSeconds} 秒 · 最近成功刷新 ${bootstrapLastSuccess.toLocaleString('zh-CN', { hour12: false })} · `
                  : ''}
                {automationRuntimeCoverageIncomplete && !criticalRuntimeIssues.length
                  ? `投影时间 ${new Date(overview.generated_at).toLocaleString('zh-CN', { hour12: false })}`
                  : `已持续自 ${new Date(criticalRuntimeIssues[0].first_observed_at).toLocaleString('zh-CN', { hour12: false })}`}
                {observedAutomationRuntime?.last_successful_loop_at
                  ? ` · 最近成功循环 ${new Date(observedAutomationRuntime.last_successful_loop_at).toLocaleString('zh-CN', { hour12: false })}`
                  : ' · 尚无成功循环记录'}
              </small>
            </div>
            <NavLink to="/operations">查看故障详情</NavLink>
          </section>
        ) : null}
        <WorkspaceErrorBoundary key={location.pathname}>
          <Suspense key={location.pathname} fallback={<WorkspaceLoading />}>
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<DashboardPage bootstrap={effectiveBootstrap} />} />
              <Route path="/market" element={<MarketPage bootstrap={effectiveBootstrap} />} />
              {['/research/*', '/news/*'].map(path => <Route path={path} element={<Navigate to="/market" replace />} key={path} />)}
              <Route path="/grafana/*" element={<Navigate to="/operations" replace />} />
              <Route path="/strategies" element={<StrategyPage bootstrap={effectiveBootstrap} />} />
              <Route path="/portfolio" element={<Navigate replace to={`/strategies?${new URLSearchParams({ ...Object.fromEntries(new URLSearchParams(location.search)), tab: 'holdings' })}`} />} />
              <Route path="/orders" element={<OrdersPage bootstrap={effectiveBootstrap} />} />
              <Route path="/operations" element={<OperationsPage bootstrap={effectiveBootstrap} />} />
              <Route path="/backtests" element={<Navigate replace to={`/strategies?${new URLSearchParams({ ...Object.fromEntries(new URLSearchParams(location.search)), tab: 'backtests' })}`} />} />
              <Route path="/audit" element={<Navigate to="/operations" replace />} />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </Suspense>
        </WorkspaceErrorBoundary>
      </main>

      <ActivityDrawer
        open={activityOpen}
        onClose={() => setActivityOpen(false)}
        alerts={operations?.alerts ?? []}
        streamEvents={stream.events}
        streamState={stream.state}
      />
    </div>
  )
}

class WorkspaceErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('workspace render failed', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="workspace-loading workspace-load-error" role="alert">
        <ServerCog size={28} />
        <strong>工作区资源加载失败</strong>
        <span>{this.state.error.message || '本地资源暂不可用'}</span>
        <button type="button" onClick={() => window.location.reload()}>重新加载工作台</button>
      </div>
    )
  }
}

const connectionTone: Record<QMTConnectionLayerState, 'ok' | 'warning' | 'danger' | 'muted'> = {
  online: 'ok',
  busy: 'warning',
  degraded: 'warning',
  stale: 'warning',
  offline: 'danger',
  unavailable: 'danger',
  not_exposed: 'muted',
}

const connectionText: Record<QMTConnectionLayerState, string> = {
  online: '在线',
  busy: '繁忙',
  degraded: '降级',
  stale: '已过期',
  offline: '离线',
  unavailable: '无数据',
  not_exposed: '未提供',
}

function ConnectionPill({
  label,
  layer,
  loading,
  failed = false,
}: {
  label: string
  layer?: QMTConnectionLayer
  loading: boolean
  failed?: boolean
}) {
  const state = layer?.state ?? 'unavailable'
  const failedWithoutData = failed && layer == null
  const loadingWithoutData = loading && layer == null
  const title = layer
    ? `${layer.detail}${failed ? '；最新刷新失败，正在自动重试' : ''}`
    : failedWithoutData
      ? '权威连接状态读取失败；页面会自动重试'
      : '正在读取权威连接状态'
  return (
    <span title={title}>
      <StatusPill tone={loadingWithoutData ? 'muted' : failedWithoutData ? 'danger' : connectionTone[state]} pulse={state === 'online'}>
        {label} · {loadingWithoutData
          ? '读取中'
          : failedWithoutData
            ? '读取失败'
            : state === 'degraded'
              ? connectionStateLabel(layer?.layer ?? 'agent', state)
              : connectionText[state]}
      </StatusPill>
    </span>
  )
}

function TradingConsoleApp() {
  const location = useLocation()
  useEffect(() => {
    const workspace = navigation.find(({ id }) => location.pathname === `/${id}`)
    if (workspace) preloadWorkspace(workspace.id)
  }, [location.pathname])
  const query = useQuery({
    queryKey: BOOTSTRAP_QUERY_KEY,
    queryFn: ({ signal }) => fetchBootstrap(signal),
    staleTime: 10_000,
    refetchOnWindowFocus: true,
    retry: 2,
  })
  if (query.isPending && query.data == null) {
    return <div className="boot-screen"><div className="boot-orbit" /><strong>正在连接{projectBrand.display_name}</strong><span>读取 QMT、账户和策略投影…</span></div>
  }
  if (query.isError && query.data == null) {
    return (
      <div className="boot-screen boot-error" role="alert">
        <ServerCog size={30} />
        <h1>本地 Console 暂不可用</h1>
        <span>{query.error instanceof Error ? query.error.message : '未知错误'}</span>
        <button type="button" onClick={() => void query.refetch()}>重新连接</button>
      </div>
    )
  }
  return (
    <Shell
      bootstrap={query.data}
      bootstrapRefreshFailed={query.isError}
      bootstrapLastSuccessAt={query.dataUpdatedAt}
    />
  )
}

export default function App() {
  const location = useLocation()
  if (import.meta.env.VITE_OBSERVATION_ONLY === 'true' || location.pathname === '/observation' || location.pathname.startsWith('/observation/')) {
    return <Suspense fallback={<div className="boot-screen">正在读取观衡市场观察…</div>}><ObservationShell /></Suspense>
  }
  return <TradingConsoleApp />
}
