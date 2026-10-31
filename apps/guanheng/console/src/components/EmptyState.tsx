import { DatabaseZap } from 'lucide-react'

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty-state" role="status">
      <DatabaseZap size={22} aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <p>{detail}</p>
      </div>
    </div>
  )
}
