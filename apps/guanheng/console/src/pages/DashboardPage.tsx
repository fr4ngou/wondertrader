import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  AlertTriangle,
  CircleDollarSign,
  LockKeyhole,
  ShieldCheck,
  WalletCards,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'

import {
  fetchExecutionQueue,
  fetchPortfolioPerformance,
  fetchPortfolioPnl,
  fetchPortfolioPositions,
  fetchRecentOrders,
  fetchStrategyEligibility,
  fetchStrategyRuntime,
} from '../api'
import { EmptyState } from '../components/EmptyState'
import { PortfolioEquityChart } from '../components/PortfolioEquityChart'
import { PortfolioPositionTable } from '../components/PortfolioPositionTable'
import { RelativeTime } from '../components/RelativeTime'
import { SnapshotFreshness } from '../components/SnapshotFreshness'
import { StatusPill } from '../components/StatusPill'
import { queueCountLabel, summarizeExecutionQueue } from '../executionQueuePresentation'
import { orderSideNames, orderStatusNames } from '../orderPresentation'
import { multiStrategyPlatformSummary } from '../strategyPresentation'
import type { AutomationRuntimeStatus, ConsoleBootstrap } from '../types'

const cny = new Intl.NumberFormat('zh-CN', {
  style: 'currency', currency: 'CNY', maximumFractionDigits: 2,
})

function money(value?: number | null) {
  return value == null ? '—' : cny.format(value)
}

function environmentLabel(value: string) {
  if (value === 'simulation') return '模拟盘'
  if (value === 'shadow') return '影子运行'
  if (value === 'backtest') return '回测'
  if (value === 'live') return '实盘'
  return '未知环境'
}

function lifecycleLabel(value: string) {
  if (value === 'running') return '运行中'
  if (value === 'paused') return '已暂停'
  if (value === 'stopped') return '已停止'
  if (value === 'error') return '异常'
  return '状态未知'
}

function gateLabel(bootstrap: ConsoleBootstrap) {
  const gate = bootstrap.overview.automation_gate
  if (gate == null) return '不可用'
  if (gate.global_kill_switch || gate.account_kill_switch) return '已停止'
  return gate.auto_execution_enabled ? '已启用' : '已关闭'
}

const loopLabels: Record<AutomationRuntimeStatus['loop_state'], string> = {
  idle: '空闲', waiting: '正常等待', advancing: '正在推进', converging: '正在收敛',
  blocked: '已阻断', unavailable: '不可用',
}

const healthLabels: Record<AutomationRuntimeStatus['business_health'], string> = {
  healthy: '业务正常', degraded: '业务降级', blocked: '交易受阻', unavailable: '不可用',
}

export function DashboardPage({ bootstrap }: { bootstrap: ConsoleBootstrap }) {
  const { overview } = bootstrap
  const account = overview.account
  const mode = overview.active_config?.mode ?? account?.trading_mode ?? 'shadow'
  const operations = overview.operations
  const runtime = overview.trading_operations?.automation_runtime ?? null
  const runtimeSources = overview.trading_operations?.automation_runtime_sources
  const runtimeCoverage = overview.trading_operations?.source_coverage?.automation_runtime_projection_consistency ?? 'unavailable'
  const singleSourceRuntime = runtimeSources && Object.keys(runtimeSources).length === 1
    ? (runtimeSources.portfolio ?? runtimeSources.operations)
    : null
  const singleSourceName = runtimeSources?.portfolio ? 'Portfolio' : 'Operations'
  const pnl = useQuery({
    queryKey: ['portfolio-pnl'], queryFn: ({ signal }) => fetchPortfolioPnl(signal),
    staleTime: 10_000, refetchInterval: 30_000, retry: 1,
  })
  const performance = useQuery({
    queryKey: ['portfolio-performance', 30], queryFn: ({ signal }) => fetchPortfolioPerformance(signal),
    staleTime: 30_000, refetchInterval: 60_000, retry: 1,
  })
  const positions = useQuery({
    queryKey: ['portfolio-positions'], queryFn: ({ signal }) => fetchPortfolioPositions(signal),
    staleTime: 10_000, refetchInterval: 30_000, retry: 1,
  })
  const runtimes = useQuery({
    queryKey: ['strategies', 'runtime'], queryFn: ({ signal }) => fetchStrategyRuntime(signal),
    staleTime: 15_000, refetchInterval: 30_000, retry: 1,
  })
  const eligibility = useQuery({
    queryKey: ['strategies', 'eligibility'], queryFn: ({ signal }) => fetchStrategyEligibility(signal),
    staleTime: 10_000, refetchInterval: 15_000, retry: 1,
  })
  const executionQueue = useQuery({
    queryKey: ['orders', 'execution-queue'], queryFn: ({ signal }) => fetchExecutionQueue(signal),
    staleTime: 10_000, refetchInterval: 15_000, retry: 1,
  })
  const orders = useQuery({
    queryKey: ['orders', 'recent'], queryFn: ({ signal }) => fetchRecentOrders(signal),
    staleTime: 5_000, refetchInterval: 10_000, retry: 1,
  })
  const snapshot = pnl.data
  const activeStrategies = (runtimes.data ?? []).filter((item) => item.lifecycle !== 'unavailable')
  const eligibilityData = eligibility.isError ? undefined : eligibility.data
  const allowedStrategies = (eligibilityData?.items ?? []).filter((item) => item.automation_candidate)
  const eligibilityCoverageComplete = eligibilityData != null
    && Object.keys(eligibilityData.source_coverage).length > 0
    && Object.values(eligibilityData.source_coverage).every((state) => state === 'complete')
  const executionQueueData = executionQueue.isError ? undefined : executionQueue.data
  const queueSummary = executionQueueData == null
    ? null
    : summarizeExecutionQueue(executionQueueData)

  return (
    <section className="workspace-page dashboard-page">
      <header className="page-heading dashboard-heading">
        <div><h1>总览</h1><p>账户、自动执行、策略资格和今日订单集中展示；任何操作都请直接在对话中告诉我。</p></div>
        <div className="heading-statuses"><StatusPill tone={mode === 'simulation' ? 'warning' : 'info'}>{environmentLabel(mode)}</StatusPill><span className="read-only-stamp"><LockKeyhole size={14} /> 只读</span></div>
      </header>

      <article className="display-only-banner">
        <ShieldCheck size={19} />
        <div><strong>网页只负责看，不负责操作</strong><span>回测、策略切换、参数修改、QMT 操作和模拟盘测试全部通过你与 Codex 的对话完成。</span></div>
      </article>

      <div className="runtime-status-grid dashboard-runtime-grid" aria-label="总览运行状态分层">
        <article className="runtime-status-item">
          <span>服务可达性</span>
          <strong>{operations == null ? '不可用' : operations.platform_services_ready ? '外围服务可读取' : '外围服务降级'}</strong>
          <small>{operations?.services?.length ? `${operations.services.filter((item) => item.ready).length}/${operations.services.length} 个服务 ready` : '缺少服务探测样本'}</small>
        </article>
        <article className="runtime-status-item">
          <span>账户与交易依赖</span>
          <strong>{account == null ? '不可用' : account.reconciled ? '账户已对账' : '账户未完成对账'}</strong>
          <small>{account?.snapshot_at ? <>快照 <RelativeTime value={account.snapshot_at} /></> : '缺少权威账户快照'}</small>
        </article>
        <article className="runtime-status-item">
          <span>自动执行开关</span>
          <strong>{gateLabel(bootstrap)}</strong>
          <small>Control 权威门禁，不代表 Portfolio 已正常推进</small>
        </article>
        <article className={`runtime-status-item runtime-status-${runtimeCoverage === 'complete' ? runtime?.business_health ?? 'unavailable' : 'unavailable'}`}>
          <span>自动执行运行状态</span>
          <strong>{runtimeCoverage === 'complete' && runtime
            ? `${loopLabels[runtime.loop_state]} · ${healthLabels[runtime.business_health]}`
            : runtimeCoverage === 'partial' ? '整体状态不可确认' : '自动执行运行状态不可用'}</strong>
          <small>{runtimeCoverage === 'complete' && runtime?.last_observed_at
            ? <>最近观察 <RelativeTime value={runtime.last_observed_at} staleAfterSeconds={30} /></>
            : runtimeCoverage === 'partial' && runtime && runtimeSources?.portfolio
              ? <>Portfolio 最新观察：{loopLabels[runtime.loop_state]} · {healthLabels[runtime.business_health]}；Operations 投影待追上</>
            : singleSourceRuntime
              ? <>仅 {singleSourceName} 观察：{loopLabels[singleSourceRuntime.loop_state]} · {healthLabels[singleSourceRuntime.business_health]}；另一来源缺失</>
              : '缺少一致的 Portfolio 与 Operations 运行状态'}</small>
        </article>
      </div>

      <div className="account-summary-grid">
        {[
          ['账户总权益', money(snapshot?.total_equity), <CircleDollarSign size={18} key="equity" />],
          ['可用资金', money(snapshot?.cash), <WalletCards size={18} key="cash" />],
          ['持仓市值', money(snapshot?.market_value), <Activity size={18} key="value" />],
          ['当日权益变动', money(snapshot?.day_pnl), <Activity size={18} key="pnl" />],
        ].map(([label, value, icon]) => <article className="surface-card account-summary-card" key={String(label)}>{icon}<span>{label}</span><strong>{snapshot?.data_available ? value : '—'}</strong>{snapshot?.data_available ? <SnapshotFreshness stale={snapshot.snapshot_stale} ageSeconds={snapshot.snapshot_age_seconds} /> : <small>暂无权威账户估值</small>}</article>)}
      </div>

      <div className="dashboard-core-grid">
        <article className="surface-card dashboard-positions-card">
          <div className="card-heading"><div><h2>当前持仓</h2><span>数量、可卖量与盈亏</span></div><strong>{positions.data?.items.length ?? '—'} 个标的</strong></div>
          {positions.data ? <PortfolioPositionTable projection={positions.data} loading={positions.isPending} /> : <EmptyState title={positions.isError ? '持仓暂不可用' : '正在读取持仓'} detail="没有权威账户快照时保持空白。" />}
        </article>

        <article className="surface-card dashboard-performance-card">
          <div className="card-heading"><div><h2>账户净值</h2><span>最近 30 天 · 不混入回测收益</span></div></div>
          {performance.data ? <PortfolioEquityChart series={performance.data} /> : <EmptyState title={performance.isError ? '账户收益暂不可用' : '正在读取账户收益'} detail="缺少真实账户序列时不会显示为零。" />}
        </article>
      </div>

      <div className="dashboard-secondary-grid">
        <article className="surface-card dashboard-strategy-card">
          <div className="card-heading"><div><h2>允许策略</h2><span>Portfolio 自动执行资格，不等于订单已获批</span></div><NavLink to="/strategies">查看资格矩阵</NavLink></div>
          {eligibility.isError ? <div className="coverage-gap"><AlertTriangle size={16} /><div><strong>策略资格不可用</strong><span>不能把空列表解释为没有允许策略。</span></div></div> : null}
          {eligibilityData ? allowedStrategies.length ? <div className="dashboard-strategy-list">{allowedStrategies.slice(0, 6).map((item) => <div key={`${item.strategy_id}@${item.strategy_version}`}><span><strong>{item.display_name}</strong><small>{item.strategy_id} @ {item.strategy_version}</small></span><b>{item.candidate_ready ? '候选已就绪' : `允许进入 · ${item.projection_state === 'unavailable' ? '依赖不可用' : '仍有阻断'}`}</b></div>)}</div> : eligibilityCoverageComplete ? <EmptyState title="当前没有允许进入自动执行的策略" detail="该结论来自 Portfolio 资格投影；已登记、已配置、可产出意图和允许进入分别判断。" /> : <div className="coverage-gap"><AlertTriangle size={16} /><div><strong>策略资格覆盖不完整</strong><span>不能确认当前没有允许策略；请查看资格矩阵中的缺失来源。</span></div></div> : eligibility.isLoading ? <EmptyState title="正在读取策略资格" detail="不会用运行中策略数量代替自动执行资格。" /> : null}
          {eligibilityData ? <small className="dashboard-supporting-fact">{multiStrategyPlatformSummary(eligibilityData)}</small> : null}
          {activeStrategies.length ? <small className="dashboard-supporting-fact">运行态可见 {activeStrategies.length} 个策略；运行中不自动等同于允许执行。</small> : null}
        </article>

        <article className="surface-card dashboard-orders-card">
          <div className="card-heading"><div><h2>今日订单与待执行</h2><span>Portfolio 命令前队列 + Bridge 权威账本</span></div><NavLink to="/orders">查看订单工作台</NavLink></div>
          {executionQueue.isError ? <div className="coverage-gap"><AlertTriangle size={16} /><div><strong>今日队列不可用</strong><span>无法确认当前没有待执行事项。</span></div></div> : null}
          {executionQueueData ? <div className="queue-summary-grid dashboard-queue-summary" aria-label="首页今日订单汇总">
            <span><small>交易日</small><strong>{queueSummary?.authoritative ? executionQueueData.trading_date : '不可用'}</strong></span>
            <span><small>今日事项</small><strong>{queueCountLabel(queueSummary?.todayTotal ?? null)}</strong></span>
            <span><small>待风险 / 待命令</small><strong>{queueSummary?.authoritative ? `${queueSummary.riskPending} / ${queueSummary.approvedPendingCommand}` : '不可用'}</strong></span>
            <span><small>跨日未终态</small><strong>{queueCountLabel(queueSummary?.carryoverPending ?? null)}</strong></span>
          </div> : null}
          {orders.data?.length ? <div className="dashboard-order-list">{orders.data.slice(0, 6).map((item) => <div key={item.command_id}><span><strong>{item.symbol}</strong><small>{orderSideNames[item.side]} · {item.quantity} · {item.strategy_id ?? '无策略归属'}</small></span><b>{orderStatusNames[item.status]}</b><time>{new Date(item.created_at).toLocaleString('zh-CN', { hour12: false })}</time></div>)}</div> : orders.isError ? <div className="coverage-gap"><AlertTriangle size={16} /><div><strong>Bridge 委托账本不可用</strong><span>命令前队列仍独立显示；不能推断今日没有订单。</span></div></div> : queueSummary?.authoritative && queueSummary.todayTotal === 0 && queueSummary.carryoverPending === 0 ? <EmptyState title="今日没有订单或待执行事项" detail="交易日历与命令前队列覆盖完整，Bridge 当前也没有可展示命令。" /> : <p className="empty-inline">Bridge 当前没有可展示命令；上方命令前事项仍按 Portfolio 权威队列展示。</p>}
        </article>
      </div>
    </section>
  )
}
