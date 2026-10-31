import type { ReactNode } from 'react'

type Tone = 'ok' | 'warning' | 'danger' | 'info' | 'muted'

export function StatusPill({
  tone,
  children,
  pulse = false,
}: {
  tone: Tone
  children: ReactNode
  pulse?: boolean
}) {
  return (
    <span className={`status-pill status-${tone}`}>
      <span className={pulse ? 'status-dot pulse' : 'status-dot'} aria-hidden="true" />
      {children}
    </span>
  )
}
