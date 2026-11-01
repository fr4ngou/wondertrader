import { AlertCircle, CheckCircle2, Circle, LoaderCircle, PauseCircle } from 'lucide-react'
import './status-presentation.css'

/** 颜色表达当前事实层级；进程ready只用蓝色，实际读取成功才用绿色。 */
export function StatusBadge({ state, label }: { state: string; label: string }) {
  const tone = ['faulted', 'unavailable', 'degraded', 'failed'].includes(state) ? 'error'
    : ['complete', 'responding'].includes(state) ? 'success'
      : ['ready'].includes(state) ? 'info'
        : ['starting', 'stopping', 'refreshing', 'waiting'].includes(state) ? 'pending' : 'neutral'
  const Icon = tone === 'error' ? AlertCircle : tone === 'success' ? CheckCircle2
    : tone === 'pending' ? LoaderCircle : state === 'closed' || state === 'stopped' ? PauseCircle : Circle
  return <span className={`status-badge status-${tone}`}><Icon size={14} aria-hidden="true" />{label}</span>
}
