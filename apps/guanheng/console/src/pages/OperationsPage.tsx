import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Activity, AlertTriangle, Database, LockKeyhole, RadioTower, ScrollText, ServerCog, ShieldCheck } from 'lucide-react'

import { fetchOperationalErrorLogs, fetchOperationsWorkbench } from '../api'
import { EmptyState } from '../components/EmptyState'
import { InfoTip } from '../components/InfoTip'
import { RelativeTime } from '../components/RelativeTime'
import { diagnosticLabel } from '../diagnosticPresentation'
import { operationalAlertPresentation } from '../operationalAlertPresentation'
import { operationalLogLifecycleLabel, operationIdLabel } from '../operationsPresentation'
import type { AutomationRuntimeStatus, ConsoleBootstrap, ConversationOperationReceiptSummary } from '../types'

function TimeValue({ value, staleAfterSeconds }: { value?: string | null, staleAfterSeconds?: number }) {
  return value ? <RelativeTime value={value} staleAfterSeconds={staleAfterSeconds} /> : <>时间不可用</>
}

function formatPercent(value?: number | null) {
  return value == null ? '不适用' : `${(value * 100).toFixed(2)}%`
}

function receiptVerificationLabel(receipt: ConversationOperationReceiptSummary) {
  if (receipt.artifact_verification_status === 'failed') return '产物验真失败，请核对产物与回执'
  if (receipt.content_verified && receipt.artifacts_verified && receipt.artifact_verification_status !== 'not_checked') return '回执与产物均已校验'
  return '回执已核对，产物可按需验真'
}

function formatDuration(start: string, end?: string | null) {
  const seconds = Math.max(0, Math.floor((new Date(end ?? Date.now()).getTime() - new Date(start).getTime()) / 1000))
  if (seconds < 60) return `${seconds} 秒`
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时 ${Math.floor((seconds % 3600) / 60)} 分钟`
  return `${Math.floor(seconds / 86400)} 天 ${Math.floor((seconds % 86400) / 3600)} 小时`
}

function impactScopeLabel(kind: string, id: string) {
  const kindLabel = kind === 'platform' ? '平台' : kind === 'account' ? '账户' : kind === 'symbol' ? '标的' : '策略'
  return `${kindLabel} · ${id}`
}

function severityLabel(value: string) {
  return value === 'critical' ? '严重阻断' : value === 'error' ? '错误' : '提醒'
}

function componentLabel(value: string) {
  const labels: Record<string, string> = {
    portfolio: '组合与账户服务', operations: '平台运维服务', control: '配置治理服务',
    bridge: '交易桥接服务', strategy: '策略服务', market_data: '行情服务',
  }
  return labels[value] ?? '平台服务'
}

function tradingImpactLabel(value?: string | null) {
  if (value === 'new_risk_blocked') return '新风险失败关闭'
  if (value === 'symbol_blocked') return '标的级失败关闭'
  if (value === 'account_blocked') return '账户级失败关闭'
  if (value === 'none') return '不影响交易推进'
  return '交易影响不可用'
}

function automationGateLabel(value?: string | null) {
  if (value === 'enabled') return '已启用'
  if (value === 'disabled') return '已关闭'
  if (value === 'stopped') return '停止开关生效'
  return '不可用'
}

function loopStateLabel(value?: string | null) {
  if (value === 'idle') return '空闲'
  if (value === 'waiting') return '等待条件'
  if (value === 'advancing') return '正在推进'
  if (value === 'converging') return '正在收敛'
  if (value === 'blocked') return '已阻断'
  return '不可用'
}

function businessHealthLabel(value?: string | null) {
  if (value === 'healthy') return '业务正常'
  if (value === 'degraded') return '业务降级'
  if (value === 'blocked') return '交易受阻'
  return '业务状态不可用'
}

const serviceNames: Record<string, string> = {
  bridge: 'QMT Bridge', control: '控制服务', portfolio: '组合风控', strategy: '策略服务',
  'market-data': '行情服务', replay: '回测回放', audit: '审计服务', operations: '运维服务',
}

export function OperationsPage({ bootstrap }: { bootstrap: ConsoleBootstrap }) {
  const [searchParams] = useSearchParams()
  const requestedTab = searchParams.get('tab')
  const [activeTab, setActiveTab] = useState<'overview' | 'logs'>(
    requestedTab === 'logs' ? requestedTab : 'overview',
  )

  const workbench = useQuery({
    // 此页只展示八条任务回执；缩小同一投影的历史查询范围，避免无用的备份/任务历史拖过交互截止。
    queryKey: ['operations', 'workbench', 8], queryFn: ({ signal }) => fetchOperationsWorkbench(signal, 8),
    refetchInterval: 10_000, retry: 1,
  })
  const errorLogs = useQuery({
    queryKey: ['operations', 'error-logs', '24h'],
    queryFn: ({ signal }) => fetchOperationalErrorLogs(signal),
    enabled: activeTab === 'logs',
    refetchInterval: activeTab === 'logs' ? 15_000 : false,
    retry: 1,
  })
  const operations = bootstrap.overview.operations
  const controlGate = bootstrap.overview.automation_gate
  const tradingOperations = bootstrap.overview.trading_operations
  // The reconciled runtime is authoritative for the overall status. A single
  // source remains visible as evidence, but its healthy value cannot clear a
  // coverage gap in the other required observation path.
  const runtime = tradingOperations?.automation_runtime ?? null
  const runtimeSources: Partial<Record<'portfolio' | 'operations', AutomationRuntimeStatus>> = tradingOperations?.automation_runtime_sources
    ?? (operations?.automation_runtime ? { operations: operations.automation_runtime } : {})
  const runtimeCoverage = tradingOperations?.source_coverage?.automation_runtime_projection_consistency ?? 'unavailable'
  const singleSource = Object.keys(runtimeSources).length === 1
    ? runtimeSources.portfolio ? 'Portfolio' : 'Operations'
    : null
  const singleSourceRuntime = singleSource
    ? (runtimeSources.portfolio ?? runtimeSources.operations)
    : null
  const runtimeIssues = (tradingOperations?.active_issues ?? operations?.runtime_issues ?? [])
    .filter((item) => item.lifecycle !== 'resolved')
  const rootRuntimeIssues = runtimeIssues.filter((item) => item.relationship !== 'symptom')
  const linkedSymptoms = runtimeIssues.reduce((groups, item) => {
    if (item.relationship !== 'symptom' || !item.root_issue_key) return groups
    const current = groups.get(item.root_issue_key) ?? []
    current.push(item)
    groups.set(item.root_issue_key, current)
    return groups
  }, new Map<string, typeof runtimeIssues>())
  const account = bootstrap.overview.account
  const services = operations?.services ?? []
  const alerts = (operations?.alerts ?? []).filter((item) => item.active)
  const facts = operations?.trading_facts
  const platformServicesReady = operations?.platform_services_ready === true

  return (
    <section className="workspace-page">
      <header className="page-heading">
        <div><h1>系统状态</h1><p>只展示 QMT、账户、服务和最近对话任务的权威状态；维护操作仍通过对话完成。</p></div>
        <span className={`read-only-stamp ${platformServicesReady ? '' : 'read-only-stamp-warning'}`}><LockKeyhole size={14} /> {platformServicesReady ? '外围服务正常' : '外围服务降级'}</span>
      </header>

      <nav className="operations-tabs" aria-label="系统状态视图">
        <button type="button" aria-pressed={activeTab === 'overview'} onClick={() => setActiveTab('overview')}>运行概览</button>
        <button type="button" aria-pressed={activeTab === 'logs'} onClick={() => setActiveTab('logs')}>错误日志</button>
      </nav>

      <div hidden={activeTab !== 'overview'}>

      {runtimeCoverage !== 'complete' ? <div className="coverage-gap" role="status" aria-label="自动执行状态覆盖缺口">
        <AlertTriangle size={16} />
        <div>
          <strong>{singleSource ? '自动执行状态仅单侧可读' : Object.keys(runtimeSources).length ? '自动执行状态尚未一致' : '自动执行状态不可用'}</strong>
          <span>{singleSource
            ? `仅 ${singleSource} 提供最近观察；另一来源缺失，整体自动执行健康无法确认。`
            : Object.keys(runtimeSources).length
              ? '两路状态尚未一致；保留各来源事实并等待新的权威观察。'
              : 'Portfolio 与 Operations 均未提供可核对的运行态，整体自动执行健康无法确认。'}</span>
        </div>
      </div> : null}

      <div className="runtime-status-grid" aria-label="运行状态分层">
        <article className="runtime-status-item">
          <span>服务可达性</span>
          <strong>{platformServicesReady ? '外围服务可读取' : '外围服务降级'}</strong>
          <small>{services.filter((item) => item.ready).length}/{services.length || '—'} 个服务 ready</small>
        </article>
        <article className="runtime-status-item">
          <span>账户与交易依赖</span>
          <strong>{account ? (account.reconciled ? '账户已对账' : '账户未完成对账') : '账户状态不可用'}</strong>
          <small>{account?.snapshot_at ? <>快照 <RelativeTime value={account.snapshot_at} /></> : '缺少权威账户快照'}</small>
        </article>
        <article className="runtime-status-item">
          <span>自动执行开关</span>
          <strong>{automationGateLabel(
            controlGate == null
              ? 'unavailable'
              : controlGate.global_kill_switch || controlGate.account_kill_switch
                ? 'stopped'
                : controlGate.auto_execution_enabled ? 'enabled' : 'disabled',
          )}</strong>
          <small>Control 权威开关 · Portfolio 报告 {automationGateLabel(runtime?.automation_gate)}</small>
        </article>
        <article className={`runtime-status-item runtime-status-${runtimeCoverage === 'complete' ? runtime?.business_health ?? 'unavailable' : 'unavailable'}`}>
          <span>自动执行运行状态</span>
          <strong>{runtimeCoverage === 'complete' && runtime
            ? `${loopStateLabel(runtime.loop_state)} · ${businessHealthLabel(runtime.business_health)}`
            : '整体状态不可确认'}</strong>
          <small>{runtimeCoverage === 'complete' && runtime?.last_observed_at
            ? <>最近观察 <RelativeTime value={runtime.last_observed_at} staleAfterSeconds={30} /></>
            : runtimeCoverage === 'partial' && runtime && runtimeSources.portfolio
              ? <>Portfolio 最新观察：{loopStateLabel(runtime.loop_state)} · {businessHealthLabel(runtime.business_health)} · <RelativeTime value={runtime.last_observed_at} staleAfterSeconds={30} />；Operations 投影待追上</>
            : singleSourceRuntime
              ? <>仅 {singleSource} 观察：{loopStateLabel(singleSourceRuntime.loop_state)} · {businessHealthLabel(singleSourceRuntime.business_health)} · <RelativeTime value={singleSourceRuntime.last_observed_at} staleAfterSeconds={30} /></>
              : '缺少一致的 Portfolio 与 Operations 运行状态'}</small>
        </article>
      </div>

      <article className="surface-card runtime-issues-card">
        <div className="card-heading"><div><h2>自动执行故障</h2><span>结构化问题与持久生命周期</span></div><AlertTriangle size={18} /></div>
        {rootRuntimeIssues.length ? <div className="runtime-issue-list">{rootRuntimeIssues.map((issue) => (
          <section className={`runtime-issue-row runtime-issue-${issue.severity}`} key={issue.issue_key}>
            <div><strong>{issue.user_safe_title ?? issue.user_safe_summary}</strong></div>
            <span>{issue.lifecycle === 'stale' ? '覆盖中断，保留最后权威状态' : issue.severity === 'critical' ? '严重阻断' : '需要关注'}</span>
            <p>{issue.user_safe_summary}</p>
            {linkedSymptoms.has(issue.issue_key) ? <div className="linked-symptom">关联影响：<ul>{linkedSymptoms.get(issue.issue_key)?.map((symptom) => <li key={symptom.issue_key}>{symptom.user_safe_title ?? symptom.user_safe_summary}</li>)}</ul></div> : null}
            <dl>
              <div><dt>严重度 / 影响</dt><dd>{severityLabel(issue.severity)} · {impactScopeLabel(issue.impact_scope_kind, '当前范围')}</dd></div>
              <div><dt>首次发现</dt><dd><RelativeTime value={issue.first_observed_at} /></dd></div>
              <div><dt>最近观察</dt><dd><RelativeTime value={issue.last_observed_at} /></dd></div>
              <div><dt>持续时长</dt><dd>{formatDuration(issue.first_observed_at, issue.last_observed_at)}</dd></div>
              <div><dt>最近成功循环</dt><dd><TimeValue value={runtime?.last_successful_loop_at} staleAfterSeconds={30} /></dd></div>
              <div><dt>失败关闭</dt><dd>{tradingImpactLabel(runtime?.trading_impact)}</dd></div>
              <div><dt>事实来源 / 新鲜度</dt><dd>{componentLabel(issue.source_component)} · {formatDuration(issue.last_authoritative_observed_at)} 前</dd></div>
              <div><dt>可重试</dt><dd>{issue.retryable ? '可在根因修复后由原流程重试' : '否'}</dd></div>
            </dl>
            <details>
              <summary>证据、原因与建议下一步</summary>
              <div className="runtime-issue-details">
                <span><b>故障来源</b>{issue.source_component} → {issue.impact_scope_kind} → {issue.impact_scope_id}</span>
                <span><b>技术标识</b>{issue.issue_code}{linkedSymptoms.has(issue.issue_key) ? ` · ${linkedSymptoms.get(issue.issue_key)?.map((symptom) => symptom.issue_code).join(' · ')}` : ''}</span>
                <span><b>故障级因果链</b>当前 issue 没有逐阶段身份绑定时保持不可用；请在交易记录中按权威 batch、queue item、approval、command 与 execution facts 下钻。</span>
                <span><b>原因参数</b>{Object.keys(issue.reason_parameters).length ? JSON.stringify(issue.reason_parameters) : '无附加参数'}</span>
                <span><b>权威证据引用</b>{issue.evidence_refs.join('、') || '暂无引用'}</span>
                <span><b>建议下一步</b>{issue.recommended_next_step ?? '按故障码核对权威来源，修复根因后等待权威健康观察。'}</span>
                <span><b>只读运行手册</b>{issue.runbook_path ?? 'docs/runbooks/automation-runtime-faults.md'}{issue.registry_version ? ` · registry ${issue.registry_version}` : ''}</span>
              </div>
            </details>
          </section>
        ))}</div> : <div className="empty-inline"><ShieldCheck size={15} /> {runtimeCoverage === 'complete' ? '当前没有结构化自动执行故障' : '故障覆盖不完整，无法确认当前没有故障'}</div>}
      </article>

      <div className="operations-summary-grid">
        <article className="surface-card qmt-status-card">
          <div className="card-heading"><div><h2>QMT 与账户</h2><span>当前连接边界</span></div><RadioTower size={18} /></div>
          <ul className="plain-status-list">
            <li><span>Agent</span><strong>{account?.agent_id ?? '暂无权威数据'}</strong></li>
            <li><span>运行模式</span><strong>{account?.trading_mode === 'simulation' ? '模拟盘' : account?.trading_mode === 'shadow' ? '影子运行' : '暂无权威数据'}</strong></li>
            <li><span>账户对账</span><strong>{account ? (account.reconciled ? '一致' : '未完成') : '暂无权威数据'}</strong></li>
            <li><span>快照时间</span><strong><TimeValue value={account?.snapshot_at} staleAfterSeconds={30} /></strong></li>
          </ul>
          {account?.blocking_reasons.length ? <div className="boundary-reasons">{account.blocking_reasons.slice(0, 5).map((item) => <span key={item}>{diagnosticLabel(item)}</span>)}</div> : <p className="empty-inline"><ShieldCheck size={15} /> 当前没有账户阻塞说明</p>}
        </article>

        <article className="surface-card operations-ledger-card">
          <div className="card-heading"><div><h2>交易事实</h2><span>仅统计持久化账本</span></div><Database size={18} /></div>
          <div className="ledger-facts ledger-facts-vertical">
            <div><span>风险审批</span><strong>{facts?.risk_approval_count ?? '—'}</strong></div>
            <div><span>签名命令</span><strong>{facts?.order_command_count ?? '—'}</strong></div>
            <div><span>执行事件</span><strong>{facts?.execution_event_count ?? '—'}</strong></div>
            <div><span>待处理死信</span><strong>{facts?.dead_letter_event_count ?? '—'}</strong></div>
          </div>
        </article>
      </div>

      <article className="surface-card service-status-card">
        <div className="card-heading"><div><h2>服务状态</h2><span>{services.length} 个服务</span></div><ServerCog size={18} /></div>
        {services.length ? <div className="service-status-grid">{services.map((service) => <div className="service-status-row" key={service.service}><span className={service.ready ? 'service-dot service-dot-ok' : 'service-dot service-dot-warning'} /><div><strong>{serviceNames[service.service] ?? service.service}</strong><small>{service.ready ? '可读取' : service.reason || '暂不可用'} · {service.latency_ms.toFixed(0)} ms</small></div><b>{service.deployment_identity.status === 'matched' ? '版本一致' : '版本待核对'}</b></div>)}</div> : <EmptyState title="服务状态不可用" detail="不会把缺少探测结果显示为正常。" />}
      </article>

      <article className="surface-card alert-card">
        <div className="card-heading"><div><h2>当前告警</h2><span>只显示活动项</span></div><AlertTriangle size={18} /></div>
        {alerts.length ? <div className="alert-list">{alerts.slice(0, 8).map((alert) => {
          const item = operationalAlertPresentation(alert)
          return <div className={`alert-row alert-row-${alert.severity}`} data-alert-key={alert.alert_key} key={alert.alert_key}><span>{alert.severity === 'critical' ? '严重' : alert.severity === 'warning' ? '提醒' : '信息'}</span><div><strong>{item.title}</strong><small>{item.source} · {item.category}</small></div><div><small>当前 {item.observed}</small><small>要求 {item.threshold}</small></div></div>
        })}</div> : <div className="empty-inline"><ShieldCheck size={15} /> 当前没有活动告警</div>}
      </article>

      <article className="surface-card conversation-receipts-card">
        <div className="card-heading"><div><h2>最近对话任务</h2><span>回测、诊断与维护的可验证回执</span></div><ScrollText size={18} /></div>
        {workbench.data?.conversation_receipts.length ? <div className="conversation-receipt-list">{workbench.data.conversation_receipts.slice(0, 8).map((receipt) => <section className={`conversation-receipt-row receipt-${receipt.status}`} key={receipt.receipt_sha256}><header><div><strong>{operationIdLabel(receipt.operation_id, receipt.summary_lines)}</strong><span>{receipt.strategy ?? '对话任务回执'}</span></div><span>{receipt.status === 'succeeded' ? '已完成' : receipt.status === 'timed_out' ? '超时' : '失败'}</span></header><div className="conversation-receipt-facts"><span><small>完成时间</small><b><RelativeTime value={receipt.completed_at} /></b></span><span><small>总收益</small><b>{formatPercent(receipt.total_return)}</b></span><span><small>最大回撤</small><b>{formatPercent(receipt.maximum_drawdown)}</b></span><span><small>成交数</small><b>{receipt.trade_count ?? '不适用'}</b></span></div><details className="technical-details"><summary>技术详情</summary><p>操作 {receipt.operation_id} · 耗时 {(receipt.duration_ms / 1000).toFixed(2)} 秒 · 回执 {receipt.receipt_sha256} · {receiptVerificationLabel(receipt)} · 无交易副作用</p></details></section>)}</div> : <EmptyState title={workbench.isError || workbench.data?.conversation_receipt_observation_available === false ? '对话任务回执不可用' : workbench.isPending ? '正在读取对话任务回执' : '暂无对话任务回执'} detail={workbench.isError || workbench.data?.conversation_receipt_observation_available === false ? '回执目录或摘要索引当前不可读，请查看运行状态与错误日志。' : '完成对话式回测或诊断后会显示在这里。'} />}
        {workbench.data?.conversation_receipt_invalid_count ? <p className="receipt-invalid-warning">{workbench.data.conversation_receipt_invalid_count} 份回执未通过校验，已隔离。</p> : null}
      </article>

      <article className="display-only-banner operations-boundary"><Activity size={18} /><div><strong>维护边界</strong><span>本页没有登录、解锁、启停、恢复、迁移、改参或交易入口。需要处理时，直接在对话中告诉我。</span></div></article>
      </div>

      {activeTab === 'logs' ? <section className="operations-tab-panel" aria-label="错误日志">
        <article className="surface-card error-log-coverage-card">
          <div className="card-heading"><div><h2>错误日志 <InfoTip label="错误日志状态">结合错误最后发生时间和当前服务健康度区分“仍在发生”、“已恢复”和“启动窗口/历史瞬时事件”。原始日志、次数和时间范围继续保留。</InfoTip></h2><span>最近 24 小时 · critical / error · 15 秒刷新</span></div><ScrollText size={18} /></div>
          {errorLogs.isError ? <div className="coverage-gap"><AlertTriangle size={16} /><div><strong>错误日志覆盖不可用</strong><span>无法确认当前是否没有错误；业务故障仍以活动告警为准。</span></div></div> : null}
          {errorLogs.data ? <div className="log-coverage-summary">
            <span><small>Loki</small><strong>{errorLogs.data.coverage.loki_status === 'healthy' ? '可查询' : '不可用'}</strong></span>
            <span><small>Alloy / 来源</small><strong>{errorLogs.data.coverage.alloy_status === 'healthy' && errorLogs.data.coverage.source_status === 'healthy' ? '采集正常' : '采集覆盖不完整'}</strong></span>
            <span><small>MinIO</small><strong>{errorLogs.data.coverage.minio_status === 'healthy' ? '存储正常' : '存储覆盖不完整'}</strong></span>
            <span><small>持久化写入</small><strong>{errorLogs.data.coverage.persistence_status === 'verified' ? <>已验证 · <TimeValue value={errorLogs.data.coverage.persistence_last_write_at} /></> : '不可用'}</strong></span>
            <span><small>覆盖</small><strong>{errorLogs.data.coverage.status === 'complete' ? '完整' : errorLogs.data.coverage.status === 'partial' ? '部分' : '不可用'}</strong></span>
            <span><small>最后事件</small><strong><TimeValue value={errorLogs.data.coverage.latest_event_at} /></strong></span>
            <span><small>最后成功采集</small><strong><TimeValue value={errorLogs.data.coverage.last_successful_collection_at} /></strong></span>
            <span><small>采集延迟</small><strong>{errorLogs.data.coverage.collection_lag_seconds == null ? '不可用' : `${errorLogs.data.coverage.collection_lag_seconds.toFixed(1)} 秒`}</strong></span>
            <span><small>保留期</small><strong>{errorLogs.data.coverage.retention_status === 'verified' ? `${errorLogs.data.coverage.retention_days} 天 · 已验证` : '不可用'}</strong></span>
            <span><small>日志丢弃</small><strong>{errorLogs.data.coverage.drop_status === 'observed' ? `${errorLogs.data.coverage.dropped_count ?? 0} 条` : '不可用'}</strong></span>
            <span><small>OTLP 导出失败</small><strong>{errorLogs.data.coverage.export_status === 'observed' ? `${errorLogs.data.coverage.export_failure_count ?? 0} 条` : '不可用'}</strong></span>
            <span><small>无效响应行</small><strong>{errorLogs.data.coverage.invalid_response_line_count} 条</strong></span>
          </div> : null}
        </article>

        {errorLogs.data?.fingerprint_groups.length ? <article className="surface-card">
          <div className="card-heading"><div><h2>重复错误聚合</h2><span>按稳定 stack fingerprint 合并</span></div><AlertTriangle size={18} /></div>
          <div className="error-group-list">{errorLogs.data.fingerprint_groups.filter((group) => group.lifecycle === 'active').map((group) => <div className={`error-group-row severity-${group.severity}`} key={`${group.service}-${group.stack_fingerprint}`}>
            <div><strong>{group.user_safe_summary}</strong><details className="technical-details"><summary>技术详情</summary><code>{group.issue_code} · {group.service}</code></details></div>
            <span>{componentLabel(group.service)}</span><b>{operationalLogLifecycleLabel(group.lifecycle)} · {group.count} 次</b><small><RelativeTime value={group.last_event_at} /></small>
          </div>)}</div>
          {errorLogs.data.fingerprint_groups.some((group) => group.lifecycle !== 'active') ? <details className="technical-details recovered-error-groups"><summary>查看已恢复与启动窗口事件（{errorLogs.data.fingerprint_groups.filter((group) => group.lifecycle !== 'active').length}）</summary><div className="error-group-list">{errorLogs.data.fingerprint_groups.filter((group) => group.lifecycle !== 'active').map((group) => <div className={`error-group-row severity-${group.severity}`} key={`${group.service}-${group.stack_fingerprint}`}><div><strong>{group.user_safe_summary}</strong><details className="technical-details"><summary>技术详情</summary><code>{group.issue_code} · {group.service}</code></details></div><span>{componentLabel(group.service)}</span><b>{operationalLogLifecycleLabel(group.lifecycle)} · {group.count} 次</b><small><RelativeTime value={group.last_event_at} /></small></div>)}</div></details> : null}
        </article> : null}

        {errorLogs.data?.events.length ? <article className="surface-card">
          <div className="card-heading"><div><h2>错误明细</h2><span>只展示脱敏字段和有限调用位置</span></div><Database size={18} /></div>
          <div className="error-event-list">{errorLogs.data.events.map((event, index) => <details className={`error-event-row severity-${event.severity}`} key={`${event.event_at}-${event.stack_fingerprint ?? index}`}>
            <summary><span>{event.severity === 'critical' ? '严重' : '错误'}</span><strong>{event.user_safe_summary}</strong><time><TimeValue value={event.event_at} /></time></summary>
            <dl><div><dt>服务</dt><dd>{event.service} / {event.component}</dd></div><div><dt>异常</dt><dd>{event.exception_type ?? '—'}</dd></div><div><dt>关联 ID</dt><dd>{event.correlation_id ?? '—'}</dd></div><div><dt>策略</dt><dd>{event.strategy_id ? `${event.strategy_id} · ${event.strategy_version}` : '不适用'}</dd></div></dl>
            <code>{event.issue_code ?? 'unclassified'}</code>
            {event.stack_frames.length ? <pre>{event.stack_frames.join('\n')}</pre> : null}
          </details>)}</div>
        </article> : errorLogs.data && !errorLogs.data.events.length && errorLogs.data.coverage.status === 'complete' ? <EmptyState title="当前查询没有错误事件" detail="Loki、Alloy、采集源与存储覆盖完整；该结论仅适用于当前查询窗口。" /> : errorLogs.data && !errorLogs.data.events.length ? <div className="coverage-gap"><AlertTriangle size={16} /><div><strong>错误事件无法确认</strong><span>当前查询没有返回事件，但日志覆盖不完整；系统保留业务故障，不能把空结果解释为无错误。</span></div></div> : null}
      </section> : null}

    </section>
  )
}
