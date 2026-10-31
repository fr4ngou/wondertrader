import { useQuery } from '@tanstack/react-query'
import { Activity, Braces, ChartNoAxesCombined, LockKeyhole, Target } from 'lucide-react'
import { lazy, Suspense, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import {
  fetchBacktestReport,
  fetchBacktestReports,
  fetchBacktestTrades,
  fetchExecutionQueue,
  fetchStrategyRegistry,
  fetchStrategyEligibility,
  fetchStrategyRuntime,
  fetchStrategyWorkbenchDetail,
} from '../api'
const BacktestEquityChart = lazy(() => import('../components/BacktestEquityChart').then(module => ({ default: module.BacktestEquityChart })))
import { WorkspaceTabs } from '../components/WorkspaceTabs'
import { AccountCapitalDetails } from './PortfolioPage'
import { StrategyCapitalPanel } from '../components/StrategyCapitalPanel'
import { StrategyPerformancePanel } from '../components/StrategyPerformancePanel'
import { StrategyTradeHistory } from '../components/StrategyTradeHistory'
import { selectedCapital } from '../strategyCapitalPresentation'
import '../components/InformationWorkspace.css'
import { EmptyState } from '../components/EmptyState'
import { InfoTip } from '../components/InfoTip'
import { ReplenishmentPanel } from '../components/ReplenishmentPanel'
import { StrategyLoopStatus } from '../components/StrategyLoopStatus'
import { StrategyTargetReplacements } from '../components/StrategyTargetReplacements'
import { StrategyPositionState } from '../components/StrategyPositionState'
import { absoluteChinaTime } from '../components/RelativeTime'
import { RelativeTime } from '../components/RelativeTime'
import { diagnosticLabel } from '../diagnosticPresentation'
import { queueDayLabel, queueProgressLabel, queueStageLabel } from '../executionQueuePresentation'
import { problemDefinitions } from '../problemDictionary'
import {
  configurationStateLabel,
  localizedRuntimeBlockers,
  multiStrategyPlatformSummary,
  runtimeParticipationLabel,
} from '../strategyPresentation'
import type { ConsoleBootstrap, StrategyWorkbenchDetail } from '../types'
import type { AutomationRuntimeIssue } from '../types'

const lifecycleLabels: Record<string, string> = {
  running: '运行中', paused: '已暂停', stopped: '已停止', starting: '正在启动',
  pausing: '正在暂停', error: '异常', unavailable: '暂无权威状态',
}

const modeLabels: Record<string, string> = {
  backtest: '回测', shadow: '影子运行（只计算、不下单）', simulation: '模拟盘', live: '实盘',
}

const percent = (value?: number | null) => value == null ? '—' : `${(value * 100).toFixed(2)}%`

function inactiveStrategyRole(strategyId: string) {
  if (strategyId === 'etf-market-rule-v1') return '旧版规则候选 · 当前组合未分配预算'
  if (strategyId === 'resonance-regime-v2') return '历史对照版本 · 仅用于比较验证'
  return '已登记候选 · 未参与当前决策'
}

const STRATEGY_NAMES: Record<string, string> = {
  'etf-market-rule-v1': 'ETF 行情规则策略',
  'resonance-regime-v1': '共振市场状态 ETF 策略',
  'resonance-regime-v2': '共振固定份额 ETF 候选',
}

const STRATEGY_PURPOSES: Record<string, string> = {
  'etf-market-rule-v1': '验证 ETF 行情规则；当前没有资金预算，不参与决策。',
  'resonance-regime-v1': '根据完整日线批次计算八只 ETF 的市场状态与目标权重。',
  'resonance-regime-v2': '固定份额分配候选版本；当前保留用于比较，未启用。',
}

function strategyDisplayName(strategyId: string, fallback: string) {
  return STRATEGY_NAMES[strategyId] ?? fallback
}

export function releaseHistoryMessage(detail: StrategyWorkbenchDetail): string {
  const error = detail.errors.release_readiness
  if (error === 'Replay profile disabled') return 'Replay 服务未启用，发布门禁证据不可用。'
  if (detail.release_evidence_scope === 'unavailable'
    || (error && error !== 'no release evidence matches the active config')) {
    return 'Replay 发布记录读取不可用，请查看服务状态。'
  }
  const config = detail.release_evidence_config_version ?? detail.readiness?.config_version
  if (detail.release_evidence_scope === 'historical_config'
    || (config && config !== detail.active_config_version)) {
    return `历史发布凭证对应 ${config ?? '历史配置'}；原记录保留当时结果，当前配置的执行资格由下方权威状态说明。`
  }
  if (detail.readiness) return `已读取 ${config ?? '当前配置'} 的发布证据；发布阶段结果供审阅，当前执行资格见下方。`
  return '当前配置尚无发布凭证；当前功能和执行资格由 Portfolio 与 Bridge 的实时状态说明。'
}

const releaseStages: Record<string, string> = {
  historical_backtest: '历史回测', event_replay: '事件回放', realtime_shadow: '实时影子验证',
  simulation: '模拟盘验证', small_live: '小资金实盘验证',
}
const queueWaitLabels: Record<string, string> = {
  waiting_market: '等待可用行情', waiting_session: '等待允许的交易时段',
  waiting_allocation: '等待组合资金分配', blocked: '安全条件阻断',
}

export function issueAffectsStrategy(
  issue: AutomationRuntimeIssue,
  strategyScopeIds: ReadonlySet<string>,
  strategySymbols: ReadonlySet<string>,
) {
  if (issue.lifecycle === 'resolved') return false
  if (issue.impact_scope_kind === 'platform' || issue.impact_scope_kind === 'account') return true
  if (issue.impact_scope_kind === 'strategy') return strategyScopeIds.has(issue.impact_scope_id)
  return issue.impact_scope_kind === 'symbol' && strategySymbols.has(issue.impact_scope_id)
}

export function StrategyPage({ bootstrap }: { bootstrap: ConsoleBootstrap }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const tabs = [{ id: 'overview', label: '概览' }, { id: 'holdings', label: '持仓与目标' }, { id: 'replenishment', label: '调仓与补单' }, { id: 'trades', label: '交易记录' }, { id: 'performance', label: '收益与回撤' }, { id: 'backtests', label: '回测' }, { id: 'configuration', label: '配置与运行' }]
  const activeTab = tabs.some(item => item.id === searchParams.get('tab')) ? searchParams.get('tab')! : 'overview'
  const [search, setSearch] = useState('')
  const changeTab = (tab: string) => setSearchParams(current => { const next = new URLSearchParams(current); next.set('tab', tab); return next })
  const backtestReportsAvailable = bootstrap.backtest_reports_available === true
  const eligibility = useQuery({
    queryKey: ['strategies', 'eligibility'],
    queryFn: ({ signal }) => fetchStrategyEligibility(signal),
    refetchInterval: 15_000,
    retry: 1,
  })
  const registry = useQuery({
    queryKey: ['strategies', 'registry'], queryFn: ({ signal }) => fetchStrategyRegistry(signal),
    staleTime: 300_000, retry: 1,
  })
  const runtimes = useQuery({
    queryKey: ['strategies', 'runtime'], queryFn: ({ signal }) => fetchStrategyRuntime(signal),
    refetchInterval: 30_000, retry: 1,
  })
  const reports = useQuery({
    queryKey: ['backtests', 'reports'], queryFn: ({ signal }) => fetchBacktestReports(signal),
    enabled: backtestReportsAvailable && activeTab === 'backtests', staleTime: 300_000, retry: 1,
  })
  const selectedStrategy = searchParams.get('strategy') ?? ''
  const selectedReport = searchParams.get('report') ?? ''
  const setSelectedReport = (report: string) => setSearchParams(current => { const next = new URLSearchParams(current); next.set('report', report); return next }, { replace: true })
  const executionQueue = useQuery({
    queryKey: ['orders', 'execution-queue'], queryFn: ({ signal }) => fetchExecutionQueue(signal),
    refetchInterval: 15_000, retry: 1,
  })
  const eligibilityData = eligibility.isError ? undefined : eligibility.data
  const activeStrategyIdentities = new Set(
    eligibilityData?.items
      .filter((item) => item.configured_enabled)
      .map((item) => `${item.strategy_id}@${item.strategy_version}`) ?? [],
  )
  const activeEligibilityItems = eligibilityData?.items.filter((item) => item.configured_enabled) ?? []
  const problemDefinitionByCode = new Map(
    problemDefinitions().map((item) => [item.issue_code, item]),
  )

  const selectStrategy = (identity: string) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      next.set('strategy', identity)
      for (const key of ['lineage', 'epoch', 'report']) next.delete(key)
      return next
    }, { replace: true })
  }

  useEffect(() => {
    if (!selectedStrategy && !eligibility.isPending && !registry.isError && registry.data?.strategies[0]) {
      const item = registry.data.strategies.find((candidate) => (
        activeStrategyIdentities.has(`${candidate.strategy_id}@${candidate.strategy_version}`)
      )) ?? registry.data.strategies[0]
      selectStrategy(`${item.strategy_id}@${item.strategy_version}`)
    }
  }, [eligibilityData, eligibility.isPending, registry.data, selectedStrategy])
  const [strategyId, strategyVersion] = selectedStrategy.split('@')
  const detail = useQuery({
    queryKey: ['strategies', 'detail', strategyId, strategyVersion],
    queryFn: ({ signal }) => fetchStrategyWorkbenchDetail(strategyId, strategyVersion, signal),
    enabled: Boolean(strategyId && strategyVersion), staleTime: 30_000, retry: 1,
  })
  const detailData = detail.isError ? undefined : detail.data
  const reportBindingUnavailable = detail.isError || Boolean(detailData?.errors?.performance_reports || detailData?.errors?.historical_performance_reports)
  const boundReports = !reportBindingUnavailable ? [...(detailData?.performance_reports ?? []), ...(detailData?.historical_performance_reports ?? [])] : []
  const allowedReports = reports.data?.filter(report => boundReports.some(bound => bound.report_hash === report.report_hash)) ?? []
  useEffect(() => { if (activeTab === 'backtests' && allowedReports.length && !allowedReports.some(item => item.report_hash === selectedReport)) setSelectedReport(allowedReports[0].report_hash) }, [activeTab, detailData, reports.data, selectedReport])
  const backtest = useQuery({
    queryKey: ['backtests', selectedReport, selectedStrategy], queryFn: ({ signal }) => fetchBacktestReport(selectedReport, signal),
    enabled: activeTab === 'backtests' && backtestReportsAvailable && reports.isSuccess && !reports.isFetching
      && Boolean(allowedReports.some((item) => item.report_hash === selectedReport)),
    staleTime: 300_000, retry: 1,
  })
  const trades = useQuery({
    queryKey: ['backtests', selectedReport, 'trades', selectedStrategy],
    queryFn: ({ signal }) => fetchBacktestTrades(selectedReport, 12, 0, '', signal),
    enabled: activeTab === 'backtests' && backtestReportsAvailable && reports.isSuccess && !reports.isFetching
      && Boolean(allowedReports.some((item) => item.report_hash === selectedReport)),
    staleTime: 300_000, retry: 1,
  })
  // A failed refetch may retain cached data. Render facts only after the current read succeeds.
  const reportsReady = backtestReportsAvailable && reports.isSuccess && !reports.isFetching && detail.isSuccess && !detail.isFetching && !reportBindingUnavailable
  const selectedReportReady = reportsReady && Boolean(allowedReports.some((item) => item.report_hash === selectedReport))
  const backtestReady = selectedReportReady && backtest.isSuccess && !backtest.isFetching
  const tradesReady = selectedReportReady && trades.isSuccess && !trades.isFetching
  const runtime = detailData?.runtime
    ?? (runtimes.isError ? undefined : runtimes.data)?.find((item) => item.strategy_id === strategyId && item.strategy_version === strategyVersion)
  const blockers = localizedRuntimeBlockers(runtime)
  const selectedEligibility = eligibilityData?.items.find(
    (item) => item.strategy_id === strategyId && item.strategy_version === strategyVersion,
  )
  const requestedLineage = searchParams.get('lineage')
  const requestedEpoch = searchParams.get('epoch')
  const selectedLineage = requestedLineage ?? selectedEligibility?.strategy_lineage_id
  const selectedEpoch = requestedEpoch ?? selectedEligibility?.genesis_epoch_id
  const executionQueueData = executionQueue.isError ? undefined : executionQueue.data
  const strategyQueueItems = [...(executionQueueData?.carryover_pending ?? []), ...(executionQueueData?.today_activity ?? [])]
    .filter((item) => item.strategy_id === strategyId
      && item.strategy_version === strategyVersion)
  const strategyScopeIds = new Set([
    strategyId,
    selectedStrategy,
    selectedLineage,
    selectedEpoch,
  ].filter((value): value is string => Boolean(value)))
  const strategySymbols = new Set(strategyQueueItems.map((item) => item.symbol))
  const strategyIssues = (bootstrap.overview.trading_operations?.active_issues
    ?? bootstrap.overview.operations?.runtime_issues
    ?? []).filter((item) => issueAffectsStrategy(item, strategyScopeIds, strategySymbols))
  const queueCoverageComplete = executionQueueData != null
    && executionQueueData.calendar_status === 'available'
    && Object.values(executionQueueData.source_coverage).every((value) => value === 'complete')
  const eligibilityCoverageComplete = eligibilityData != null
    && Object.keys(eligibilityData.source_coverage).length > 0
    && Object.values(eligibilityData.source_coverage).every((value) => value === 'complete')
  const selectedEligibilityAvailable = eligibilityCoverageComplete && selectedEligibility != null
    && selectedEligibility.projection_state !== 'unavailable'
    && (!detailData?.active_config_id || detailData.active_config_id === eligibilityData.active_config_id)
  const boundary = detail.isError ? undefined : detailData?.execution_boundary
  const accountAutomation = bootstrap.overview.trading_operations

  const sleeves = bootstrap.overview.errors?.account_capital_reconciliation ? [] : bootstrap.overview.trading_operations?.reconciliations?.[0]?.strategy_sleeves ?? []
  const sleeve = selectedCapital(sleeves, strategyId, strategyVersion, selectedLineage, selectedEpoch)
  return (
    <section className="workspace-page information-workspace">
      <header className="page-heading">
        <div><h1>策略</h1><p>按策略查看持仓、仓位目标、交易和表现。</p></div>
        <span className="read-only-stamp"><LockKeyhole size={14} /> 业务只读</span>
      </header>

      <div className="strategy-layout unified-strategy-layout">
        <article className="surface-card strategy-catalog-card">
          <div className="card-heading"><div><h2>当前运行策略</h2><span>{eligibilityCoverageComplete ? '当前组合实际采用的策略' : '当前组合资格不可用'}</span></div><Target size={18} /></div>
          <label className="rail-search">搜索策略<input value={search} onChange={event => setSearch(event.target.value)} placeholder="策略名称 / 版本" /></label><div className="strategy-catalog-list">
            {eligibilityCoverageComplete ? (registry.isError ? undefined : registry.data)?.strategies.filter(item => !search || `${item.strategy_id} ${item.display_name} ${item.strategy_version}`.toLowerCase().includes(search.toLowerCase())).filter((item) => activeStrategyIdentities.has(`${item.strategy_id}@${item.strategy_version}`)).map((item) => {
              const identity = `${item.strategy_id}@${item.strategy_version}`
              const itemRuntime = (runtimes.isError ? undefined : runtimes.data)?.find((state) => state.strategy_id === item.strategy_id && state.strategy_version === item.strategy_version)
              return <button className={identity === selectedStrategy ? 'strategy-catalog-row strategy-catalog-row-active' : 'strategy-catalog-row'} key={identity} onClick={() => selectStrategy(identity)} type="button"><span><strong>{strategyDisplayName(item.strategy_id, item.display_name)}</strong><small>{identity}</small><small>当前活动策略 · 参与当前决策</small></span><em>{runtimeParticipationLabel(itemRuntime)}</em></button>
            }) : <EmptyState title="当前运行策略资格不可用" detail="等待 Portfolio 提供覆盖完整的活动配置资格，再区分当前运行策略与候选版本。" />}
          </div>
          {eligibilityCoverageComplete ? <details className="strategy-candidate-group" open={Boolean(search)}><summary>未启用候选与历史版本（{(registry.isError ? undefined : registry.data)?.strategies.filter(item => !search || `${item.strategy_id} ${item.display_name} ${item.strategy_version}`.toLowerCase().includes(search.toLowerCase())).filter((item) => !activeStrategyIdentities.has(`${item.strategy_id}@${item.strategy_version}`)).length ?? 0}）</summary><div className="strategy-catalog-list">
            {(registry.isError ? undefined : registry.data)?.strategies.filter(item => !search || `${item.strategy_id} ${item.display_name} ${item.strategy_version}`.toLowerCase().includes(search.toLowerCase())).filter((item) => !activeStrategyIdentities.has(`${item.strategy_id}@${item.strategy_version}`)).map((item) => {
              const identity = `${item.strategy_id}@${item.strategy_version}`
              const itemRuntime = (runtimes.isError ? undefined : runtimes.data)?.find((state) => state.strategy_id === item.strategy_id && state.strategy_version === item.strategy_version)
              return <button className={identity === selectedStrategy ? 'strategy-catalog-row strategy-catalog-row-active' : 'strategy-catalog-row'} key={identity} onClick={() => selectStrategy(identity)} type="button"><span><strong>{strategyDisplayName(item.strategy_id, item.display_name)}</strong><small>{identity}</small><small>{inactiveStrategyRole(item.strategy_id)} · {STRATEGY_PURPOSES[item.strategy_id] ?? '当前未参与决策。'}</small></span><em>{runtimeParticipationLabel(itemRuntime)}</em></button>
            })}
          </div></details> : null}
          {registry.isError ? <EmptyState title="策略列表不可用" detail="未取得权威策略注册表。" /> : null}
        </article>

        <article className="surface-card strategy-detail-card">
          <div className="card-heading"><div><h2>{detailData?.strategy ? strategyDisplayName(detailData.strategy.strategy_id, detailData.strategy.display_name) : '策略详情'}</h2><span>{selectedStrategy || '等待策略'}</span></div><Activity size={18} /></div>
          <WorkspaceTabs items={tabs} active={activeTab} onChange={changeTab} label="策略详情标签" prefix="strategy" />
          <div id="strategy-panel" role="tabpanel" aria-labelledby={`strategy-tab-${activeTab}`}>
          {activeTab === 'overview' || activeTab === 'holdings' ? <StrategyCapitalPanel sleeve={sleeve} target={detailData?.current_target} metricsOnly={activeTab === 'overview'} error={bootstrap.overview.errors?.account_capital_reconciliation} /> : null}
          {activeTab === 'holdings' ? <details className="account-ownership-details"><summary>账户对账与人工归属</summary><AccountCapitalDetails bootstrap={bootstrap} /></details> : null}
          {activeTab === 'trades' && strategyId ? <StrategyTradeHistory key={selectedStrategy} strategyId={strategyId} /> : null}
          {activeTab === 'performance' ? <StrategyPerformancePanel strategyId={strategyId} lineage={sleeve?.strategy_lineage_id} epoch={sleeve?.genesis_epoch_id} /> : null}
          {activeTab === 'overview' ? <StrategyPerformancePanel compact strategyId={strategyId} lineage={sleeve?.strategy_lineage_id} epoch={sleeve?.genesis_epoch_id} /> : null}
          {activeTab === 'overview' ? <><StrategyCapitalPanel sleeve={sleeve} target={detailData?.current_target} compact holdingsOnly /><button className="reader-link" onClick={() => changeTab('holdings')}>查看完整持仓 →</button></> : null}
          {activeTab === 'overview' && blockers.length ? <div className="strategy-readonly-note"><strong>当前运行提醒</strong><span>{blockers.join('；')}</span><button onClick={() => changeTab('configuration')}>查看原因</button></div> : null}
          {activeTab === 'overview' || activeTab === 'replenishment' ? <StrategyLoopStatus
            runtime={accountAutomation?.automation_runtime}
            coverage={accountAutomation?.source_coverage?.automation_runtime_projection_consistency ?? 'unavailable'}
          /> : null}
          {activeTab === 'replenishment' ? <ReplenishmentPanel key={selectedStrategy}
            strategyId={strategyId} strategyVersion={strategyVersion} activeConfigId={detailData?.active_config_id}
          /> : null}
          {activeTab === 'configuration' ? <>
      <article className="surface-card strategy-eligibility-card">
        <div className="card-heading"><div><span className="eyebrow">Portfolio 权威资格投影</span><h2>允许策略与执行资格</h2></div><span className="read-only-stamp">只读</span></div>
        {eligibility.isError ? <div className="coverage-gap"><div><strong>策略资格不可用</strong><span>不会把已注册策略误报为允许执行，也不会把缺少来源显示为零。</span></div></div> : null}
        {eligibilityData && !eligibilityCoverageComplete ? <div className="coverage-gap"><div><strong>策略资格覆盖不完整</strong><span>不能确认当前没有允许策略；资格数量保持不可用，请查看矩阵中的来源状态。</span></div></div> : null}
        {eligibilityData ? <>
          <div className="eligibility-summary"><span>当前生效的策略组合 <InfoTip label="当前生效的策略组合">Control 已采用的活动配置版本，决定哪些策略获得预算。</InfoTip><strong>{eligibilityCoverageComplete ? eligibilityData.active_config_version ?? '无' : '不可用'}</strong></span><span>已纳入当前组合 <InfoTip label="已纳入当前组合">策略已在当前活动配置中启用并获得预算。</InfoTip><strong>{eligibilityCoverageComplete ? eligibilityData.items.filter((item) => item.configured_enabled).length : '不可用'}</strong></span><span>可进入自动执行 <InfoTip label="可进入自动执行">治理、运行、资金和目标条件均满足后，策略才会进入自动候选。</InfoTip><strong>{eligibilityCoverageComplete ? eligibilityData.items.filter((item) => item.automation_candidate).length : '不可用'}</strong></span><span>当前可推进 <InfoTip label="当前可推进">当前组合、运行状态、有效目标与队列来源均完整。</InfoTip><strong>{eligibilityCoverageComplete ? eligibilityData.items.filter((item) => item.candidate_ready).length : '不可用'}</strong></span></div>
          <p className="dashboard-supporting-fact">{multiStrategyPlatformSummary(eligibilityData)}</p>
          {activeEligibilityItems.length ? <div className="eligibility-table">
            <div className="eligibility-row eligibility-head"><span>策略</span><span>当前生效组合</span><span>已纳入当前组合</span><span>可进入自动执行</span><span>最新有效目标</span><span>今日队列</span><span>当前可推进</span><span>原因说明</span></div>
            {activeEligibilityItems.map((item) => <div className={`eligibility-row eligibility-${item.projection_state}`} key={`${item.strategy_id}@${item.strategy_version}`}>
              <span><button className="eligibility-strategy-select" type="button" onClick={() => selectStrategy(`${item.strategy_id}@${item.strategy_version}`)}><strong>{strategyDisplayName(item.strategy_id, item.display_name)}</strong></button><small>{item.strategy_id} @ {item.strategy_version}</small><small>{item.strategy_lineage_id ?? '未绑定权威版本链'}{item.genesis_epoch_id ? ` · 运行纪元 ${item.genesis_epoch_id.slice(0, 8)}` : ''}</small></span>
              <span>{eligibilityData.active_config_version ?? '无活动配置'}</span>
              <span>{item.disabled ? '已停用' : item.configured_enabled ? `已纳入 · 预算 ${percent(item.configured_budget)}` : '未纳入'}</span>
              <span>{item.automation_candidate ? '条件齐备' : '条件未齐备'}</span>
              <span>{item.dependency_status.valid_target === 'unavailable' ? '不可用' : item.valid_target_available ? '存在' : '不存在'}</span>
              <span>{item.today_pending_count == null ? '不可用' : `待执行 ${item.today_pending_count} · 完成 ${item.today_completed_count ?? 0} · 失败 ${item.today_failed_count ?? 0}`}</span>
              <span><strong>{item.projection_state === 'ready' ? '可推进' : item.projection_state === 'unavailable' ? '来源不可用' : '已阻断'}</strong></span>
              <span>{item.blocking_issue_codes.length ? item.blocking_issue_codes.map((code) => {
                const definition = problemDefinitionByCode.get(code)
                const title = definition?.title ?? '中文问题说明尚未登记'
                return <span className="eligibility-blocker-definition" key={code}><small>{title}</small><InfoTip label={title}>{definition ? `含义：${definition.meaning} 影响：${definition.impact} 处理：${definition.recommended_action} 事实来源：${definition.fact_source}。词典更新时间：${absoluteChinaTime(definition.updated_at)}。来源不可用时：${definition.unavailable_meaning}` : '该技术状态尚未进入权威中文问题词典，当前按来源不可用和安全阻断处理。'}</InfoTip></span>
              }) : <small>全部依赖满足</small>}{item.blocking_issue_codes.length ? <details className="technical-details"><summary>技术详情</summary><code>{item.blocking_issue_codes.join(', ')}</code></details> : null}</span>
            </div>)}</div> : eligibilityCoverageComplete ? <EmptyState title="当前组合没有启用策略" detail="权威来源覆盖完整，当前没有获得预算的策略。" /> : <EmptyState title="策略资格记录不可用" detail="来源覆盖不完整，空列表不代表当前没有允许策略。" />}
          {eligibilityData.items.length > activeEligibilityItems.length ? <p className="dashboard-supporting-fact">其余 {eligibilityData.items.length - activeEligibilityItems.length} 个候选与历史版本已收进下方折叠区，不参与当前组合决策。</p> : null}
        </> : eligibility.isLoading ? <EmptyState title="正在读取策略资格" detail="正在由 Portfolio 组合注册、配置、运行态和自动执行事实。" /> : null}
      </article>

          {detailData ? <>
            <div className="strategy-overview-grid">
              <div><span>活动配置模式</span><strong>{modeLabels[detailData.active_config_mode ?? ''] ?? '暂无权威状态'}</strong></div>
              <div><span>运行状态</span><strong>{lifecycleLabels[runtime?.lifecycle ?? 'unavailable']}</strong></div>
              <div><span>配置状态</span><strong>{configurationStateLabel(detailData)}</strong></div>
              <div><span>策略预算</span><strong>{percent(detailData.configured_budget)}</strong></div>
            </div>
            <p className="strategy-description">活动配置决定账户运行模式；策略负责计算仓位目标，实际订单由组合风控和执行端逐笔核验。</p>
            <p className="strategy-description">{STRATEGY_PURPOSES[detailData.strategy.strategy_id] ?? detailData.strategy.description}</p>
            <div className="strategy-parameter-card">
              <div className="card-heading"><div><h2>参数快照</h2><span>只展示当前权威配置</span></div><Braces size={18} /></div>
              <dl className="strategy-parameter-list">
                {Object.entries(detailData.configured_parameters).map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{String(value)}</dd></div>)}
                {!Object.keys(detailData.configured_parameters).length ? <div><dt>参数</dt><dd>沿用策略默认值</dd></div> : null}
                <div><dt>活动配置</dt><dd>{detailData.active_config_version ?? '未绑定'} · {detailData.active_config_mode ?? '未知模式'}</dd></div>
                {detailData.active_config_mode === 'simulation' ? <div><dt>模拟切换依据</dt><dd>{detailData.simulation_mode_activation ? '当前配置激活记录已核对' : detailData.simulation_promotion ? '历史模拟晋级记录已核对' : detailData.errors.simulation_mode_activation ? '当前配置激活记录不可用' : '暂无可核对的切换记录'}</dd></div> : null}
              </dl>
            </div>
            {blockers.length ? <div className="strategy-readonly-note"><strong>当前说明</strong><span>{blockers.join('；')}</span></div> : null}
            <section className="strategy-parameter-card" aria-label="当前功能与执行资格">
              <div className="card-heading"><div><h2>当前功能与执行资格</h2><span>Portfolio 当前资格与 Bridge 即时委托边界</span></div></div>
              {selectedEligibilityAvailable ? <dl className="strategy-parameter-list">
                <div><dt>策略信号</dt><dd>{selectedEligibility.intent_eligible ? '具备产出意图条件' : '信号条件未齐备'}</dd></div>
                <div><dt>自动执行候选</dt><dd>{selectedEligibility.automation_candidate ? '已进入自动候选' : '自动候选条件未齐备'}</dd></div>
                <div><dt>最新有效目标</dt><dd>{selectedEligibility.valid_target_available ? '有效目标已就绪' : '当前没有有效目标'}</dd></div>
                <div><dt>Portfolio 当前可推进</dt><dd>{selectedEligibility.candidate_ready ? '策略条件已就绪' : '策略条件仍有阻断'}</dd></div>
                {selectedEligibility.blocking_issue_codes.length ? <div><dt>当前资格限制</dt><dd>{selectedEligibility.blocking_issue_codes.map((code) => diagnosticLabel(code)).join('；')}</dd></div> : null}
              </dl> : <p>当前资格来源不可用或覆盖不完整，等待 Portfolio 提供完整的当前配置事实。</p>}
              <p>{boundary ? boundary.published_preflight_ready ? 'Bridge 当前模拟委托预检通过；实际订单仍需逐笔风控、签名与执行检查。' : boundary.blocking_reasons.length ? `Bridge 当前委托安全阻断：${boundary.blocking_reasons.map((reason) => diagnosticLabel(reason)).join('；')}。当前订单须逐项满足上述条件，并核对允许时段与行情。` : 'Bridge 当前委托预检未通过，等待执行端提供明确状态。' : 'Bridge 即时委托边界不可用，当前委托资格无法确认。'}</p>
              {boundary?.blocking_reasons.length ? <details className="technical-details"><summary>执行边界技术详情</summary><code>{boundary.blocking_reasons.join(', ')}</code></details> : null}
              {strategyQueueItems.some((item) => item.wait_state) ? <p>{[...new Set(strategyQueueItems.map((item) => item.wait_state ? queueWaitLabels[item.wait_state] : null).filter(Boolean))].join('；')}。等待状态由执行队列提供；达到允许时段后仍需重新核对有效目标和行情。</p> : null}
            </section>
            <section className="strategy-readonly-note" aria-label="历史回测与发布凭证"><strong>历史回测与发布凭证</strong><span>{releaseHistoryMessage(detailData)}</span>
              {detailData.historical_release_gates?.length ? <details className="technical-details"><summary>查看最近原发布记录（{detailData.historical_release_gates.length} 项，最多 20 项）</summary>{detailData.historical_release_gates.map((gate) => <p key={gate.gate_id}>{releaseStages[gate.stage] ?? gate.stage} · {gate.status === 'passed' ? '当时通过' : gate.status === 'failed' ? '当时失败' : '当时待验收'} · 配置 {gate.config_version} · 数据集 {gate.dataset_version} · 代码 {gate.code_commit} · {absoluteChinaTime(gate.created_at)}{gate.reasons.length ? ` · ${gate.reasons.join('；')}` : ''}</p>)}</details> : null}
              {detailData.historical_performance_reports?.map((report) => <p key={report.report_hash}>历史报告 · 数据集 {report.dataset_version} · 收益 {percent(report.total_return)} · 最大回撤 {percent(report.maximum_drawdown)} · {report.trade_count} 笔成交</p>)}
            </section>
            <div className="strategy-operational-detail">
              <div><span>最近运行事件</span><strong>{runtime?.last_event_at ? <RelativeTime value={runtime.last_event_at} /> : '权威来源不可用'}</strong></div>
              <div><span>最近成功自动循环</span><strong>{detailData.last_successful_automation_loop_at ? <RelativeTime value={detailData.last_successful_automation_loop_at} /> : '尚无成功循环记录'}</strong></div>
              <div><span>最近策略意图</span><strong>{detailData.recent_intents?.[0] ? `${detailData.recent_intents[0].symbol} · 目标 ${(detailData.recent_intents[0].target_weight * 100).toFixed(2)}% · ${absoluteChinaTime(detailData.recent_intents[0].occurred_at)}` : detailData.errors.recent_intents ? '权威来源不可用' : '当前没有策略意图'}</strong></div>
              <div><span>相关活动故障</span><strong>{strategyIssues.length ? strategyIssues.map((item) => <Link key={item.issue_key} title={`技术代码：${item.issue_code}`} to={`/operations?tab=logs&issue_code=${encodeURIComponent(item.issue_code)}`}>{diagnosticLabel(item.issue_code)}</Link>) : '没有影响该策略的活动故障'}</strong></div>
            </div>
            <section className="strategy-queue-detail" aria-label="当前仓位目标">
              <header><div><strong>当前仓位目标</strong><span>{detailData.current_target ? `来源交易日 ${detailData.current_target.source_trade_date} · 收盘 ${absoluteChinaTime(detailData.current_target.source_closed_at)}` : '按活动配置读取完整目标'}</span></div></header>
              {detailData.current_target ? <>
                <p>本次计算时间：{absoluteChinaTime(detailData.current_target.observed_at)}</p>
                <p>{detailData.current_target.decision?.status === 'initializing'
                  ? '策略仍在初始化；该记录作为初始化状态展示，执行层等待策略确认正式目标。'
                  : detailData.current_target.decision
                    ? `策略已确认目标 · 规则版本 ${detailData.current_target.decision.rule_version} · 按 ${detailData.current_target.decision.history_start} 至 ${detailData.current_target.decision.history_end} 的 ${detailData.current_target.decision.history_batch_count} 批历史输入重算。`
                    : '历史目标记录；计算依据见原策略意图与证据。'}</p>
                <p>目标仓位由策略决定；执行层核对真实持仓和在途委托，决定保留、撤销或替换旧单。目标被接替的记录与实际成交分别保留。</p>
                <p>{detailData.current_target.evidence_refs.some((ref) => ref.startsWith('mode-only-target-source:')) ? '由同一业务配置的已核实收盘目标接续' : '由当前配置计算'} · {detailData.current_target.config_version} · {detailData.current_target.valid_until ? `有效至 ${absoluteChinaTime(detailData.current_target.valid_until)}` : '依最新目标规则有效'}{detailData.current_target.valid_until && new Date(detailData.current_target.valid_until).getTime() <= new Date(detailData.generated_at).getTime() ? ' · 已到期' : ''}</p>
                <div className="strategy-intent-list">{detailData.current_target.items.map((item) => <div key={item.symbol}><span><strong>{item.symbol}</strong><small>{item.reason}</small></span><span><strong>目标 {(item.target_weight * 100).toFixed(2)}%</strong></span></div>)}</div>
              </> : <p>{detailData.errors.current_target ? '当前目标来源不可用，请查看系统状态。' : '当前活动配置尚无完整仓位目标。'}</p>}
            </section>
            {detailData.recent_intents?.length ? <div className="strategy-intent-list">{detailData.recent_intents.slice(0, 5).map((intent) => <div key={intent.intent_id}><span><strong>{intent.symbol}</strong><small>{intent.sleeve ?? '未分仓'} · 配置 {intent.config_version}</small></span><span><strong>目标 {(intent.target_weight * 100).toFixed(2)}%</strong><small>置信度 {(intent.confidence * 100).toFixed(1)}%</small></span><span><strong>{absoluteChinaTime(intent.occurred_at)}</strong><small>{intent.reason}</small></span></div>)}</div> : null}
            <StrategyTargetReplacements history={detailData.target_replacements} unavailable={Boolean(detailData.errors.target_replacements)} />
            <StrategyPositionState report={detailData.strategy_state} version={strategyVersion} unavailable={Boolean(detailData.errors.strategy_state)} />
            <section className="strategy-queue-detail" aria-label="所选策略今日执行事项">
              <header><div><strong>今日执行事项</strong><span>命令前队列与跨日未终态</span></div><Link to={`/orders?strategy_id=${encodeURIComponent(strategyId)}`}>打开交易记录</Link></header>
              {executionQueue.isError ? <p>执行队列来源不可用，不能确认没有待执行事项。</p> : strategyQueueItems.length ? strategyQueueItems.map((item) => <div key={item.queue_item_id}>
                <span><strong>{item.symbol} · {item.side === 'buy' ? '买入' : item.side === 'sell' ? '卖出' : '撤单'}</strong><small>{queueDayLabel(item)} · {item.correlation_id}</small><small>{selectedLineage && selectedEpoch && (item.identity.strategy_lineage_id !== selectedLineage || item.identity.genesis_epoch_id !== selectedEpoch) ? '与当前资本身份不一致' : `资本身份 ${item.identity.strategy_lineage_id ?? '不可用'} / ${item.identity.genesis_epoch_id ?? '不可用'}`}</small></span>
                <span><strong>{item.wait_state ? queueWaitLabels[item.wait_state] : queueStageLabel(item.stage)}</strong><small>{queueProgressLabel(item)} · 未执行数量 {item.remaining_quantity}</small><small>{item.blocking_issue_codes.map((code) => diagnosticLabel(code)).join('；')}</small><details className="technical-details"><summary>技术详情</summary><code>{item.stage} · {item.blocking_issue_codes.join(', ')}</code></details></span>
              </div>) : queueCoverageComplete ? <p>权威队列覆盖完整，所选策略当前没有当天或跨日未终态事项。</p> : <p>队列覆盖不完整，不能确认所选策略当前没有待执行事项。</p>}
            </section>
          </> : detail.isError ? <EmptyState title="策略详情不可用" detail="不会用旧缓存冒充当前状态。" /> : <EmptyState title="正在读取策略" detail="等待策略服务返回权威事实。" />}
          </> : null}
          {activeTab === 'backtests' ? <>

      <div className="section-divider"><ChartNoAxesCombined size={18} /><div><h2>已发布回测</h2><p>展示所选策略已明确登记的回测报告，历史覆盖以登记证据为准。</p></div></div>
      <div className="backtest-layout compact-backtest-layout">
        <article className="surface-card backtest-report-list">
          <div className="card-heading"><div><h2>报告</h2><span>{reportsReady ? `${allowedReports.length} 份` : reports.isPending && backtestReportsAvailable ? '读取中' : '不可用'}</span></div></div>
          {!backtestReportsAvailable ? <EmptyState title="回测服务未启用" detail="当前部署未启用回测服务，已发布报告暂时不可读取。" /> : reports.isError ? <EmptyState title="回测报告不可用" detail="回测服务已启用，但当前读取失败，请查看系统状态。" /> : reportBindingUnavailable ? <EmptyState title="策略回测关联不可用" detail="策略报告归属读取失败或身份不匹配，当前无法确认回测记录。" /> : !reportsReady ? <EmptyState title="正在读取回测报告" detail="等待当前回测服务返回报告列表。" /> : allowedReports.length ? <div className="backtest-report-buttons">{allowedReports.map((item) => <button className={selectedReport === item.report_hash ? 'backtest-report-button backtest-report-active' : 'backtest-report-button'} key={item.report_hash} onClick={() => setSelectedReport(item.report_hash)} type="button"><strong>{item.model_version}</strong><span>{item.dataset_version}</span><small>收益 {percent(item.total_return)} · 回撤 {percent(item.maximum_drawdown)}</small></button>)}</div> : <EmptyState title="暂无回测报告" detail="当前投影没有明确归属该策略的报告；历史覆盖以登记证据为准。" />}
        </article>
        <article className="surface-card backtest-main-card">
          <div className="card-heading"><div><h2>净值与回撤</h2><span>{backtestReady ? backtest.data.model_version : '不可用'}</span></div></div>
          {backtestReady ? <><div className="backtest-metrics"><div><span>总收益</span><strong>{percent(backtest.data.total_return)}</strong></div><div><span>年化收益</span><strong>{percent(backtest.data.annualized_return)}</strong></div><div><span>最大回撤</span><strong>{percent(backtest.data.maximum_drawdown)}</strong></div><div><span>夏普</span><strong>{backtest.data.sharpe_ratio?.toFixed(2) ?? '—'}</strong></div><div><span>交易</span><strong>{backtest.data.trade_count}</strong></div></div><Suspense fallback={<p>正在加载图表…</p>}><BacktestEquityChart report={backtest.data} /></Suspense></> : <EmptyState title={!backtestReportsAvailable ? '回测服务未启用' : reports.isError ? '回测报告不可用' : backtest.isError ? '报告详情不可用' : !reportsReady || (selectedReportReady && backtest.isFetching) ? '正在读取报告详情' : '请选择报告'} detail="当前没有可展示的净值与回撤事实。" />}
        </article>
      </div>

      <article className="surface-card backtest-trades-card compact-trades-card">
        <div className="card-heading"><div><h2>最近回测成交</h2><span>完整重跑和分析请通过对话完成</span></div><span>{tradesReady ? `${trades.data.total} 笔` : '不可用'}</span></div>
        {tradesReady && trades.data.items.length ? <div className="backtest-trade-table"><div className="backtest-trade-row backtest-trade-head"><span>序号</span><strong>标的</strong><span>方向</span><span>数量</span><span>价格</span><time>日期</time></div>{trades.data.items.map((item) => <div className="backtest-trade-row" key={item.trade_id}><span>{item.sequence}</span><strong>{item.symbol}</strong><span>{item.side === 'buy' ? '买入' : '卖出'}</span><span>{item.quantity}</span><span>{item.price.toFixed(3)}</span><time>{absoluteChinaTime(item.occurred_at)}</time></div>)}</div> : <EmptyState title={!backtestReportsAvailable ? '回测服务未启用' : reports.isError ? '回测报告不可用' : trades.isError ? '回测成交不可用' : !tradesReady && selectedReportReady ? '正在读取回测成交' : tradesReady ? '暂无成交明细' : '请选择报告'} detail="当前没有可展示的回测成交事实。" />}
      </article>
          </> : null}
          </div>
        </article>
      </div>
    </section>
  )
}
