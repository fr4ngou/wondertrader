import { useEffect, useState } from 'react'

import { INTERACTIVE_STATUS_TIMEOUT_MS } from '../api'

export const WORKSPACE_RESOURCE_TIMEOUT_MS = INTERACTIVE_STATUS_TIMEOUT_MS

export function WorkspaceLoading({
  timeoutMs = WORKSPACE_RESOURCE_TIMEOUT_MS,
  onReload = () => window.location.reload(),
}: {
  timeoutMs?: number
  onReload?: () => void
}) {
  const [timedOut, setTimedOut] = useState(false)

  useEffect(() => {
    const timer = window.setTimeout(() => setTimedOut(true), timeoutMs)
    return () => window.clearTimeout(timer)
  }, [timeoutMs])

  if (timedOut) {
    return (
      <div className="workspace-loading workspace-load-error" role="alert">
        <strong>工作区资源加载超时</strong>
        <span>本机资源未在交互期限内完成；页面不会继续假装正在加载。</span>
        <div className="workspace-load-actions">
          <button type="button" onClick={onReload}>重新加载工作台</button>
          <a href="/operations">打开系统状态</a>
        </div>
      </div>
    )
  }

  return (
    <div className="workspace-loading" role="status" aria-live="polite">
      <div className="boot-orbit" />
      <strong>正在打开工作区</strong>
      <span>权威数据仍由本地 Console 统一读取</span>
    </div>
  )
}
