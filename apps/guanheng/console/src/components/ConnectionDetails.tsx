import { Network, ShieldAlert } from 'lucide-react'
import { Link } from 'react-router-dom'

import { connectionStateLabel, diagnosticLabel } from '../diagnosticPresentation'
import type { QMTConnectionLayer, QMTConnectionStatus } from '../types'
import { StatusPill } from './StatusPill'

const layerLabels: Record<QMTConnectionLayer['layer'], string> = {
  gateway: 'QMT 网关',
  agent: '执行代理心跳证据',
  trading_server: '交易服务器',
  account: '账户授权与快照',
}

const layerTones = {
  online: 'ok',
  busy: 'warning',
  degraded: 'warning',
  stale: 'warning',
  offline: 'danger',
  unavailable: 'danger',
  not_exposed: 'muted',
} as const

function formatTime(value?: string | null) {
  if (!value) return '暂无权威时间'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '时间格式无效'
  return parsed.toLocaleString('zh-CN', { hour12: false })
}

function evidenceAge(layer: QMTConnectionLayer) {
  if (layer.observed_at == null) return 'QMT 未提供独立观测时间'
  if (layer.age_seconds == null) return formatTime(layer.observed_at)
  return `${formatTime(layer.observed_at)} · ${Math.max(0, Math.round(layer.age_seconds))} 秒前`
}

export function ConnectionDetails({
  status,
  loading,
  failed,
}: {
  status?: QMTConnectionStatus
  loading: boolean
  failed: boolean
}) {
  return (
    <details className="connection-details">
      <summary aria-label="查看 QMT 连接诊断">
        <Network size={15} aria-hidden="true" />
        <span>连接详情</span>
      </summary>
      <section className="connection-details-panel" aria-label="QMT 连接诊断">
        <header>
          <div>
            <span className="eyebrow">权威连接事实</span>
            <h2>QMT 连接诊断</h2>
          </div>
          <span className="connection-generated-at">
            投影生成 {status ? formatTime(status.generated_at) : '—'}
          </span>
        </header>

        {status?.layers?.length ? (
          <div className="connection-layer-list">
            {status.layers.map((layer) => (
              <article className="connection-layer-row" key={layer.layer}>
                <div className="connection-layer-heading">
                  <strong>{layerLabels[layer.layer]}</strong>
                  <StatusPill tone={layerTones[layer.state]}>
                    {connectionStateLabel(layer.layer, layer.state)}
                  </StatusPill>
                </div>
                <time dateTime={layer.observed_at ?? undefined}>{evidenceAge(layer)}</time>
                <p>{layer.detail}</p>
              </article>
            ))}
          </div>
        ) : (
          <div className="connection-details-empty" role={failed ? 'alert' : 'status'}>
            <ShieldAlert size={20} aria-hidden="true" />
            <strong>{failed ? '权威连接状态读取失败' : loading ? '正在读取权威连接状态' : '暂无权威连接状态'}</strong>
            <span>页面会自动重试；读取失败不会放宽任何交易门禁。</span>
          </div>
        )}

        {status?.blocking_reasons?.length ? (
          <div className="connection-blockers">
            <strong>当前阻塞</strong>
            <ul>
              {status.blocking_reasons.map((reason) => (
                <li key={reason}>{diagnosticLabel(reason)}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <footer>
          <p>
            “未提供”表示 QMT 没有暴露可独立验证的接口，不等于登录失败；“已过期”表示最后证据太旧，系统会停止新增交易风险。
          </p>
          <Link to="/operations">到系统状态查看详情</Link>
        </footer>
      </section>
    </details>
  )
}
