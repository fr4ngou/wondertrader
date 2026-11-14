import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { createDockview, type DockviewApi, type SerializedDockview } from 'dockview'
import '../workspace/dock-theme.css'
import './observation-dock.css'

const key = 'guanheng.observation.dock.v1'
type Panel = { id: string; title: string; content: ReactNode }

export function ObservationDock({ panels, onClose }: { panels: Panel[]; onClose: (id: string) => void }) {
  const root = useRef<HTMLDivElement>(null)
  const api = useRef<DockviewApi | null>(null)
  const hosts = useRef(new Map<string, HTMLElement>())
  const [ready, setReady] = useState(false)
  const [wide, setWide] = useState(() => window.matchMedia?.('(min-width: 1060px)').matches ?? false)
  const removing = useRef(false)
  const latest = useRef({ panels, onClose })
  latest.current = { panels, onClose }

  useEffect(() => {
    const media = window.matchMedia?.('(min-width: 1060px)')
    if (!media) return
    const change = () => setWide(media.matches)
    media.addEventListener('change', change)
    return () => media.removeEventListener('change', change)
  }, [])

  function reconcile(dock: DockviewApi) {
    const ids = new Set(latest.current.panels.map(panel => panel.id))
    removing.current = true
    try {
      for (const panel of [...dock.panels]) if (!ids.has(panel.id)) dock.removePanel(panel)
      for (const panel of latest.current.panels) {
        if (dock.getPanel(panel.id)) continue
        const last = dock.panels.at(-1)
        dock.addPanel({ id: panel.id, title: panel.title, component: 'observation',
          minimumWidth: 300, position: last ? { referencePanel: last, direction: dock.panels.length % 2 ? 'right' : 'below' } : undefined })
      }
    } finally { removing.current = false }
  }

  useEffect(() => {
    const element = root.current
    if (!wide || !element) return
    const dock = createDockview(element, {
      className: 'observer-dock-surface',
      createComponent: ({ id }) => {
        const host = document.createElement('div')
        host.className = 'observation-dock-panel'
        hosts.current.set(id, host)
        return { element: host, init: () => undefined }
      },
    })
    api.current = dock
    dock.layout(element.clientWidth, element.clientHeight)
    try {
      const saved = JSON.parse(localStorage.getItem(key) || 'null') as SerializedDockview | null
      const ids = latest.current.panels.map(panel => panel.id)
      if (saved && !saved.popoutGroups?.length && Object.keys(saved.panels).length === ids.length &&
          ids.every(id => Object.hasOwn(saved.panels, id))) dock.fromJSON(saved)
    } catch { dock.clear() }
    reconcile(dock)
    const resize = new ResizeObserver(() => dock.layout(element.clientWidth, element.clientHeight))
    resize.observe(element)
    const removed = dock.onDidRemovePanel(panel => {
      hosts.current.delete(panel.id)
      if (!removing.current) latest.current.onClose(panel.id)
    })
    const save = dock.onDidLayoutChange(() => {
      try { localStorage.setItem(key, JSON.stringify(dock.toJSON())) } catch { /* 当前布局可继续使用。 */ }
    })
    setReady(true)
    return () => {
      removed.dispose()
      save.dispose()
      resize.disconnect()
      dock.dispose()
      hosts.current.clear()
      api.current = null
      setReady(false)
    }
  }, [wide])

  const [, redraw] = useState(0)
  const ids = panels.map(panel => panel.id).join(',')
  useEffect(() => {
    if (api.current) {
      reconcile(api.current)
      redraw(value => value + 1)
    }
  }, [ids])

  return <>
    {wide && <><button type="button" onClick={() => {
      const dock = api.current
      if (!dock) return
      removing.current = true
      dock.clear()
      removing.current = false
      reconcile(dock)
      redraw(value => value + 1)
    }}>恢复默认布局</button><div ref={root} className="observation-multi-dock" /></>}
    {wide && ready ? panels.map(panel => {
      const host = hosts.current.get(panel.id)
      return host ? createPortal(panel.content, host, panel.id) : null
    }) : panels.map(panel => <div key={panel.id} className="observation-dock-stack">{panel.content}</div>)}
  </>
}
