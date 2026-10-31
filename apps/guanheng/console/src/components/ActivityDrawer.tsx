import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, BellRing, CircleDot, ExternalLink, RadioTower, X } from 'lucide-react'
import { Link } from 'react-router-dom'

import { fetchAuditEvents } from '../api'
import { sourceEventType, type ConsoleStreamState } from '../hooks/useConsoleStream'
import { operationalAlertPresentation } from '../operationalAlertPresentation'
import type { OperationsSnapshot, StreamEvent } from '../types'

type AlertItem = NonNullable<OperationsSnapshot['alerts']>[number]

const streamStateLabels: Record<ConsoleStreamState, string> = {
  disabled: '未启用', connecting: '连接中', online: '实时连接', syncing: '间歇同步', reconnecting: '正在重连',
}

function eventLabel(eventType: string) {
  const known: Record<string, string> = {
    'account.updated': '账户状态已更新', 'market.updated': '行情状态已更新',
    'control.emergency_stop.activated': '全局急停已启用',
    'control.watchlist.updated': '自选列表已更新',
    'strategy.runtime.paused': '影子策略已暂停', 'strategy.runtime.resumed': '影子策略已恢复',
    'strategy.runtime.started': '影子策略已启动', 'strategy.runtime.stopped': '影子策略已停止',
    'strategy.config.activated': '策略配置已激活', 'strategy.config.rolled_back': '策略配置已回滚',
    'replay.promotion_review.recorded': '晋级审阅已记录',
    'replay.backtest_job.queued': '回测任务已排队',
    'replay.backtest_job.stop_requested': '回测任务已请求停止',
    'ui.audit_stream.degraded': '权威事件流暂时降级',
    'ui.audit_stream.recovered': '权威事件流已恢复',
  }
  if (known[eventType]) return known[eventType]
  if (eventType.startsWith('execution.')) return '订单执行状态已更新'
  if (eventType.startsWith('bridge.')) return '订单桥接状态已更新'
  if (eventType.startsWith('qmt.')) return 'QMT 状态已更新'
  if (eventType.startsWith('account.')) return '账户事实已更新'
  if (eventType.startsWith('strategy.')) return '策略状态已更新'
  if (eventType.startsWith('portfolio.')) return '组合状态已更新'
  if (eventType.startsWith('replay.')) return '回测与回放状态已更新'
  if (eventType.startsWith('control.') || eventType.startsWith('operations.')) return '系统控制状态已更新'
  return '平台事实已更新'
}

function eventDestination(eventType: string) {
  if (eventType.startsWith('strategy.')) return '/strategies'
  if (eventType.startsWith('market.')) return '/market'
  if (eventType.startsWith('account.') || eventType.startsWith('control.')) return '/operations'
  if (eventType.startsWith('replay.backtest')) return '/strategies'
  if (eventType.startsWith('replay.')) return '/operations'
  if (eventType.startsWith('execution.') || eventType.startsWith('qmt.') || eventType.startsWith('bridge.')) return '/orders'
  return '/operations'
}

function formatTime(value?: string) {
  if (!value) return '暂无时间'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

function deliveryLabel(event: StreamEvent) {
  return event.payload.delivery_mode === 'history' ? '历史补载' : '实时新增'
}

export function ActivityDrawer({
  open, onClose, alerts, streamEvents, streamState,
}: {
  open: boolean
  onClose: () => void
  alerts: AlertItem[]
  streamEvents: StreamEvent[]
  streamState: ConsoleStreamState
}) {
  const audit = useQuery({
    queryKey: ['activity-drawer', 'audit-events'],
    queryFn: ({ signal }) => fetchAuditEvents({ limit: 12, offset: 0 }, signal),
    enabled: open,
    refetchInterval: open && !['online', 'syncing'].includes(streamState) ? 5_000 : false,
    staleTime: 3_000,
    retry: 1,
  })
  if (!open) return null
  const activeAlerts = alerts.filter((item) => item.active)
  const authoritativeEvents = streamEvents.filter((item) => item.event_type === 'audit.ledger.event')
  const localEvents = streamEvents.filter((item) => item.event_type !== 'audit.ledger.event')
  return (
    <aside className="activity-drawer surface-card" id="activity-drawer" aria-label="实时事件中心">
      <header className="activity-drawer-heading">
        <div><span className="eyebrow">实时事件中心</span><h2>告警与系统动态</h2></div>
        <button type="button" className="icon-button" onClick={onClose} aria-label="关闭实时事件中心"><X size={17} /></button>
      </header>
      <div className={`activity-stream-state activity-stream-${streamState}`}>
        <RadioTower size={15} /><strong>{streamStateLabels[streamState]}</strong>
        <span>SSE 实时投影权威审计账本；仅传输只读元数据，不包含账户密钥或订单指令。</span>
      </div>

      <section className="activity-section" aria-labelledby="activity-alerts-title">
        <div className="activity-section-heading"><h3 id="activity-alerts-title">当前告警</h3><span>{activeAlerts.length} 项</span></div>
        {activeAlerts.length ? activeAlerts.map((item) => {
          const presentation = operationalAlertPresentation(item)
          return (
            <Link className={`activity-item activity-${item.severity}`} data-alert-key={item.alert_key} to="/operations" onClick={onClose} key={item.alert_key}>
              <AlertTriangle size={15} />
              <span>
                <strong>{presentation.title}</strong>
                <small>{presentation.source} · {presentation.category} · {formatTime(item.last_seen_at)}</small>
              </span>
              <ExternalLink size={13} />
            </Link>
          )
        }) : <div className="activity-empty"><CircleDot size={15} />当前没有活动告警</div>}
      </section>

      <section className="activity-section" aria-labelledby="activity-audit-title">
        <div className="activity-section-heading"><h3 id="activity-audit-title">审计账本最近记录</h3><span>{streamState === 'online' ? '实时流已连接' : '每 5 秒刷新'}</span></div>
        {audit.isPending ? <div className="activity-empty">正在读取审计账本…</div> : audit.isError ? (
          <div className="activity-empty activity-error">审计账本暂不可用；不会用本地事件代替。</div>
        ) : audit.data?.items.length ? audit.data.items.map((item) => (
          <Link className="activity-item" to={eventDestination(item.event_type)} onClick={onClose} key={item.event_id}>
            <BellRing size={15} />
            <span><strong>{eventLabel(item.event_type)}</strong><small>{item.source} · {formatTime(item.occurred_at)}</small></span>
            <ExternalLink size={13} />
          </Link>
        )) : <div className="activity-empty"><CircleDot size={15} />暂无权威审计事件</div>}
      </section>

      {authoritativeEvents.length ? (
        <section className="activity-section" aria-labelledby="activity-authoritative-title">
          <div className="activity-section-heading"><h3 id="activity-authoritative-title">权威事实流</h3><span>最近 {authoritativeEvents.length} 项</span></div>
          {authoritativeEvents.slice(0, 12).map((item) => {
            const effectiveType = sourceEventType(item)
            const source = typeof item.payload.source === 'string' ? item.payload.source : 'Audit'
            return (
              <Link className="activity-item" to={eventDestination(effectiveType)} onClick={onClose} key={item.event_id}>
                <RadioTower size={15} />
                <span><strong>{eventLabel(effectiveType)}</strong><small>{deliveryLabel(item)} · {source} · {formatTime(item.occurred_at)}</small></span>
                <ExternalLink size={13} />
              </Link>
            )
          })}
        </section>
      ) : null}

      {localEvents.length ? (
        <section className="activity-section" aria-labelledby="activity-local-title">
          <div className="activity-section-heading"><h3 id="activity-local-title">本次工作台会话</h3><span>最近 {localEvents.length} 项</span></div>
          {localEvents.slice(0, 8).map((item) => (
            <Link className="activity-item" to={eventDestination(item.event_type)} onClick={onClose} key={item.event_id}>
              <RadioTower size={15} />
              <span><strong>{eventLabel(item.event_type)}</strong><small>序号 {item.seq} · {formatTime(item.occurred_at)}</small></span>
              <ExternalLink size={13} />
            </Link>
          ))}
        </section>
      ) : null}
      <footer className="activity-boundary">只读监控中心；不包含下单、撤单、模式切换或风险阈值修改。</footer>
    </aside>
  )
}
