import { useEffect, useRef, useState } from 'react'
import { apiURL, downloadObservation } from './api'

type DownloadProps = { params: Record<string, string | number | undefined>; filename: string; children: string }

/** 查询身份变化时重建动作，取消旧读取并隔离它的进度与错误。 */
export function ObservationDownload(props: DownloadProps) {
  return <DownloadAction key={apiURL('exports', props.params)} {...props} />
}

function DownloadAction({ params, filename, children }: DownloadProps) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const active = useRef<AbortController | undefined>(undefined)
  useEffect(() => () => active.current?.abort(), [])
  async function download() {
    if (active.current) return
    const controller = new AbortController(); active.current = controller
    setBusy(true); setError('')
    try {
      const blob = await downloadObservation(params, controller.signal)
      if (controller.signal.aborted) return
      const url = URL.createObjectURL(blob)
      try {
        const link = document.createElement('a')
        link.href = url; link.download = filename.replace(/[\\/:*?"<>|]/g, '_')
        document.body.appendChild(link)
        try { link.click() } finally { link.remove() }
      } finally { URL.revokeObjectURL(url) }
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : '导出读取失败，请重试。')
    } finally {
      if (active.current === controller) active.current = undefined
      setBusy(false)
    }
  }
  return <><button disabled={busy} onClick={() => void download()}>{busy ? '正在准备下载…' : children}</button>
    {error && <span role="status">{error} 本次未生成下载文件。</span>}</>
}
