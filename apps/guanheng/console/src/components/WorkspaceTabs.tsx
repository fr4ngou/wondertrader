import type { KeyboardEvent } from 'react'

export function WorkspaceTabs({ items, active, onChange, label, prefix }: {
  items: readonly { id: string; label: string }[]; active: string; onChange: (id: string) => void; label: string; prefix: string
}) {
  const navigate = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let next = index
    if (event.key === 'ArrowRight') next = (index + 1) % items.length
    else if (event.key === 'ArrowLeft') next = (index + items.length - 1) % items.length
    else if (event.key === 'Home') next = 0
    else if (event.key === 'End') next = items.length - 1
    else return
    event.preventDefault()
    onChange(items[next].id)
    document.getElementById(`${prefix}-tab-${items[next].id}`)?.focus()
  }
  return <nav className="workspace-tabs" role="tablist" aria-label={label}>{items.map((item, index) =>
    <button type="button" role="tab" id={`${prefix}-tab-${item.id}`} key={item.id} aria-selected={active === item.id}
      aria-controls={`${prefix}-panel`} tabIndex={active === item.id ? 0 : -1}
      onKeyDown={event => navigate(event, index)} onClick={() => onChange(item.id)}>{item.label}</button>)}</nav>
}
