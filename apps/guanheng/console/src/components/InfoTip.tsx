import { CircleHelp } from 'lucide-react'
import type { ReactNode } from 'react'

export function InfoTip({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <details className="info-tip">
      <summary aria-label={`说明：${label}`} role="button" tabIndex={0} title={`查看“${label}”说明`}>
        <CircleHelp aria-hidden="true" size={15} />
      </summary>
      <div className="info-tip-popover" role="tooltip">
        <strong>{label}</strong>
        <span>{children}</span>
      </div>
    </details>
  )
}
