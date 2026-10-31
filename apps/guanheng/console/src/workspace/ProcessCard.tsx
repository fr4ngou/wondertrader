import type { ProcessStatus } from './operationsApi'
import './operations.css'

export default function ProcessCard({ title, status, impact }: { title: string; status: ProcessStatus; impact: string }) {
  return <section className="surface-card" aria-label={title}>
    <h2>{title}</h2><strong className={status.error ? 'operations-fault' : ''}>{status.label}</strong>
    <p>{status.reason}</p><p>影响：{impact}</p>
    {status.error ? <p role="note">故障原因：{status.error}</p> : null}
    <p className="operations-note">处理：{status.action}</p>
  </section>
}
