import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { createDockview, type DockviewApi, type SerializedDockview } from 'dockview'
import { Maximize2, PanelsTopLeft, RotateCcw } from 'lucide-react'
import 'dockview/dist/styles/dockview.css'
import './workspace-dock.css'

type DockProps = {
  /** 稳定的工作区布局身份，每个页面独立保存。 */
  layoutId: string
  /** 主任务面板的标题与原业务内容。 */
  primaryTitle: string
  primary: ReactNode
  /** 关联明细面板的标题与原业务内容。 */
  secondaryTitle: string
  secondary: ReactNode
  /** 默认副面板方向及并排宽度。 */
  side?: 'left' | 'right' | 'below'
  secondaryWidth?: number
  /** 窄屏需要先访问日期等控制时，将副面板排在主面板前。 */ stackSecondaryFirst?: boolean
}

function readLayout(key: string): SerializedDockview | undefined {
  try {
    const value = JSON.parse(localStorage.getItem(key) ?? 'null') as SerializedDockview | null
    if (!value?.panels || !value.grid || value.popoutGroups?.length) return
    if (Object.keys(value.panels).length !== 2 || !value.panels.primary || !value.panels.secondary) return
    return value
  } catch {
    return undefined
  }
}

/** 保留业务组件所属的 React 上下文，Dockview 只负责移动其 DOM 宿主。 */
export function WorkspaceDock({ layoutId, primaryTitle, primary, secondaryTitle, secondary, side = 'right', secondaryWidth = 340, stackSecondaryFirst = false }: DockProps) {
  const shell = useRef<HTMLDivElement>(null)
  const apiRef = useRef<DockviewApi | null>(null)
  const resetRef = useRef<(() => void) | null>(null)
  const [wide, setWide] = useState(() => window.matchMedia?.('(min-width: 1060px)').matches ?? false)
  const [hosts, setHosts] = useState<{ primary: HTMLElement; secondary: HTMLElement } | null>(null)
  useEffect(() => {
    const media = window.matchMedia?.('(min-width: 1060px)')
    if (!media) return
    const resize = () => setWide(media.matches)
    media.addEventListener('change', resize)
    return () => media.removeEventListener('change', resize)
  }, [])
  useEffect(() => {
    const root = shell.current
    if (!wide || !root) return
    const key = `guanheng.workspace-dock.v1.${layoutId}`
    const primaryHost = document.createElement('div')
    const secondaryHost = document.createElement('div')
    const primaryBody = document.createElement('div')
    const secondaryBody = document.createElement('div')
    primaryHost.className = 'observer-dock-content observer-dock-primary'
    secondaryHost.className = 'observer-dock-content observer-dock-secondary'
    primaryBody.className = secondaryBody.className = 'observer-dock-body'
    primaryHost.append(primaryBody)
    secondaryHost.append(secondaryBody)
    const api = createDockview(root, {
      className: 'observer-dock-surface',
      defaultTabComponent: 'observer-tab',
      createTabComponent: () => {
        const element = document.createElement('span')
        element.className = 'observer-dock-tab-label'
        return { element, init: ({ title }) => { element.textContent = title } }
      },
      createComponent: ({ id }) => ({
        element: id === 'primary' ? primaryHost : secondaryHost,
        init: () => undefined,
      }),
      getTabContextMenuItems: () => [],
      floatingGroupBounds: 'boundedWithinViewport',
    })
    api.layout(root.clientWidth, root.clientHeight)
    const primaryPanel = api.addPanel({ id: 'primary', component: 'workspace', title: primaryTitle, minimumWidth: 260 })
    api.addPanel({ id: 'secondary', component: 'workspace', title: secondaryTitle,
      minimumWidth: 230, initialWidth: side === 'below' ? undefined : secondaryWidth,
      position: { referencePanel: primaryPanel, direction: side } })
    primaryPanel.api.setActive()
    const defaults = api.toJSON()
    const reset = () => api.fromJSON(defaults)
    const saved = readLayout(key)
    if (saved) {
      try {
        api.fromJSON(saved)
        const primary = api.getPanel('primary')
        const secondary = api.getPanel('secondary')
        if (!primary || !secondary) reset()
        else {
          primary.api.setTitle(primaryTitle)
          secondary.api.setTitle(secondaryTitle)
        }
      } catch { reset() }
    }
    const save = () => {
      if (!api.getPanel('primary') || !api.getPanel('secondary')) return
      try { localStorage.setItem(key, JSON.stringify(api.toJSON())) } catch { /* 存储禁用时当前布局仍可使用。 */ }
    }
    // 内容的自然高度独立于 Dockview 分配的高度，避免在表格加载或换行后形成内层滚动。
    const minimums = new WeakMap<HTMLElement, number>()
    let frame = 0
    const fit = () => {
      frame = 0
      const grid: { top: number; height: number }[] = []
      let floatingBottom = 0
      for (const group of api.groups) {
        const panel = group.activePanel
        const box = group.api.boundingBox
        if (!panel || !box) continue
        const body = panel.id === 'primary' ? primaryBody : secondaryBody
        if (!body.offsetWidth || !body.isConnected) continue
        const header = group.element.querySelector<HTMLElement>('.dv-tabs-and-actions-container')
        const height = Math.max(80, body.offsetHeight + (header?.offsetHeight ?? 0))
        if (group.api.location.type === 'floating') {
          const floatingWindow = group.element.closest<HTMLElement>('.dv-resize-container')
          if (floatingWindow) floatingWindow.style.minHeight = `${height}px`
          floatingBottom = Math.max(floatingBottom, Math.ceil(box.top + height))
        } else {
          if (minimums.get(group.element) !== height) {
            minimums.set(group.element, height)
            group.api.setConstraints({ minimumHeight: height })
          }
          grid.push({ top: box.top, height })
        }
      }
      const stacked = grid.length > 1 && Math.abs(grid[0].top - grid[1].top) > 1
      const gridHeight = stacked ? grid.reduce((sum, group) => sum + group.height, 0)
        : Math.max(0, ...grid.map(group => group.height))
      const height = Math.max(80, gridHeight, floatingBottom)
      if (root.clientHeight !== height) {
        root.style.height = `${height + 2}px`
        api.layout(root.clientWidth, root.clientHeight)
      }
    }
    const scheduleFit = () => { if (!frame) frame = requestAnimationFrame(fit) }
    const resize = new ResizeObserver(scheduleFit)
    resize.observe(primaryBody)
    resize.observe(secondaryBody)
    let timer: number | undefined
    const events = api.onDidLayoutChange(() => {
      scheduleFit()
      window.clearTimeout(timer)
      timer = window.setTimeout(() => { timer = undefined; save() }, 150)
    })
    apiRef.current = api
    resetRef.current = reset
    setHosts({ primary: primaryBody, secondary: secondaryBody })
    scheduleFit()
    return () => {
      if (timer !== undefined) { window.clearTimeout(timer); save() }
      events.dispose()
      resize.disconnect()
      cancelAnimationFrame(frame)
      apiRef.current = null
      resetRef.current = null
      api.dispose()
      setHosts(null)
    }
  }, [wide, layoutId, primaryTitle, secondaryTitle, side, secondaryWidth])

  function floatPanel() {
    const api = apiRef.current
    if (api?.activePanel) api.addFloatingGroup(api.activePanel)
  }
  function toggleMaximize() {
    const api = apiRef.current
    if (!api?.activePanel) return
    if (api.hasMaximizedGroup()) api.exitMaximizedGroup()
    else api.maximizeGroup(api.activePanel)
  }
  return <div className={`observer-dock observer-dock-${layoutId}`}>
    {wide ? <>
      <div className="observer-dock-tools" role="group" aria-label="面板布局">
        <button type="button" onClick={floatPanel} title="浮动当前面板" aria-label="浮动当前面板"><PanelsTopLeft size={15} /></button>
        <button type="button" onClick={toggleMaximize} title="放大或还原当前面板" aria-label="放大或还原当前面板"><Maximize2 size={15} /></button>
        <button type="button" onClick={() => resetRef.current?.()} title="恢复默认布局" aria-label="恢复默认布局"><RotateCcw size={15} /></button>
      </div>
      <div ref={shell} className="observer-dock-root" />
    </> : null}
    {wide && hosts ? <>
      {createPortal(primary, hosts.primary)}
      {createPortal(secondary, hosts.secondary)}
    </> : <div className="observer-dock-stack">{stackSecondaryFirst ? <>{secondary}{primary}</> : <>{primary}{secondary}</>}</div>}
  </div>
}
