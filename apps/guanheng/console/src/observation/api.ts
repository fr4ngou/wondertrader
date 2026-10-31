import type { Catalog, Definition, History, Series } from './types'
import { observationBase } from './deploymentBase'

const prefix = observationBase(import.meta.env.VITE_OBSERVATION_BASE) + '/v1/ui/market-observation'
export function apiURL(path: string, params: Record<string, string | number | undefined> = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => { if (value !== undefined && value !== '') query.set(key, String(value)) })
  return `${prefix}/${path}${query.size ? '?' + query.toString() : ''}`
}
const requestMilliseconds = 15000
type ReadSlot = { grant: () => void; signal: AbortSignal; abort: () => void }
const waiting: ReadSlot[] = []
let active = 0
function acquire(signal: AbortSignal): Promise<() => void> {
  return new Promise((resolve, reject) => {
    const abort = () => {
      const index = waiting.indexOf(slot)
      if (index >= 0) waiting.splice(index, 1)
      reject(new Error('观察读取已取消。'))
    }
    const slot: ReadSlot = { signal, abort, grant: () => {
      signal.removeEventListener('abort', abort)
      active += 1
      let released = false
      resolve(() => {
        if (released) return
        released = true; active -= 1
        const next = waiting.shift()
        next?.grant()
      })
    } }
    if (signal.aborted) { abort(); return }
    if (active < 2) { slot.grant(); return }
    if (waiting.length >= 32) { reject(new Error('观察读取繁忙，请重新读取。')); return }
    waiting.push(slot)
    signal.addEventListener('abort', abort, { once: true })
  })
}
async function request<T>(path: string, params: Record<string, string | number | undefined>, signal: AbortSignal | undefined, deadline: number, decode: (response: Response) => Promise<T>): Promise<T> {
  const controller = new AbortController()
  const cancel = () => controller.abort()
  signal?.addEventListener('abort', cancel, { once: true })
  if (signal?.aborted || deadline <= Date.now()) cancel()
  const timer = setTimeout(cancel, Math.max(0, deadline - Date.now()))
  let release: (() => void) | undefined
  try {
    // The four-product matrix shares the App's bounded reader; waiting consumes this same deadline.
    release = await acquire(controller.signal)
    if (Date.now() >= deadline) cancel()
    if (controller.signal.aborted) throw new Error('观察读取已取消。')
    const response = await fetch(apiURL(path, params), { signal: controller.signal, credentials: 'same-origin', cache: 'no-store' })
    if (!response.ok) {
      throw new Error(response.status === 422 ? '查询条件无效，请检查日期、计算窗口和参数范围。' : `观察数据读取失败（${response.status}），请重新读取。`)
    }
    const value = await decode(response)
    if (Date.now() >= deadline) cancel()
    if (controller.signal.aborted) throw new Error('观察读取超过本次时间，请重新读取。')
    return value
  } catch (error) {
    if (controller.signal.aborted && !signal?.aborted) throw new Error('观察读取超过本次时间，请重新读取。')
    throw error
  } finally {
    cancel()
    release?.()
    clearTimeout(timer)
    signal?.removeEventListener('abort', cancel)
  }
}
export function read<T>(path: string, params: Record<string, string | number | undefined> = {}, signal?: AbortSignal, deadline = Date.now() + requestMilliseconds): Promise<T> {
  return request(path, params, signal, deadline, async response => {
    const value: unknown = await response.json()
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('观察数据格式无效，请重新读取。')
    return value as T
  })
}

/** 下载与图表共用名额、排队上限和原15秒截止，完整读取后才提供文件。 */
export function downloadObservation(params: Record<string, string | number | undefined>, signal?: AbortSignal): Promise<Blob> {
  return request('exports', params, signal, Date.now() + requestMilliseconds, async response => {
    if (params.snapshot_id && response.headers.get('x-observation-snapshot') !== params.snapshot_id) {
      throw new Error('导出数据版本与当前页面不一致，请重新读取。')
    }
    const reader = response.body?.getReader()
    if (!reader) throw new Error('导出内容暂不可用，请重新读取。')
    const parts: BlobPart[] = []; let bytes = 0
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        bytes += value.byteLength
        if (bytes > 16 * 1024 * 1024) throw new Error('导出超过容量，请缩短日期范围。')
        parts.push(new Uint8Array(value))
      }
      return new Blob(parts, { type: response.headers.get('content-type') || 'application/octet-stream' })
    } finally {
      try { await reader.cancel() } finally { reader.releaseLock() }
    }
  })
}
export const getCatalog = (signal?: AbortSignal, snapshot?: string) => read<Catalog>('catalog', {snapshot_id:snapshot}, signal)
export const getDefinition = (id: string, version: string, signal?: AbortSignal) => read<{ definition: Definition }>('definitions/' + id, { snapshot_id: version }, signal)
export const getHistory = (id: string, version: string, signal?: AbortSignal) => read<History>('history/' + id, { snapshot_id: version }, signal)
export async function getSeries(id: string, version: string, params: Record<string, string | number>, signal?: AbortSignal): Promise<Series> {
  const deadline = Date.now() + requestMilliseconds
  let cursor: string | undefined; let result: Series | undefined; const rows: Series['rows'] = []; const cursors = new Set<string>()
  let dataset: string | undefined; let total: number | undefined
  do {
    result = await read<Series>('series', { ...params, metric_id: id, snapshot_id: version, cursor, limit: 1000 }, signal, deadline)
    if (result.snapshot_id !== version || !/^[a-f0-9]{64}$/.test(result.dataset_version) || result.definition?.id !== id ||
      !Array.isArray(result.rows) || !Number.isInteger(result.total) || result.total < 0 || result.rows.length > 1000 ||
      dataset && dataset !== result.dataset_version || total !== undefined && total !== result.total ||
      result.next_cursor !== null && (typeof result.next_cursor !== 'string' || !result.next_cursor || cursors.has(result.next_cursor))) {
      throw new Error('观察分页版本或格式不一致，请重新读取。')
    }
    dataset = result.dataset_version; total = result.total
    rows.push(...result.rows); cursor = result.next_cursor || undefined
    if (cursor) cursors.add(cursor)
    if (rows.length > 12000) throw new Error('当前结果超出图形预算，请缩短日期；完整原值可从数据接口分区导出。')
  } while (cursor)
  if (rows.length !== total) throw new Error('观察分页记录不完整，请重新读取。')
  return { ...result, rows, next_cursor: null }
}
