import { afterEach, expect, it, vi } from 'vitest'
import { downloadObservation, getSeries, read } from './api'

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })
const version = 'a'.repeat(64), partition = 'b'.repeat(64)
function page(next: string | null, value = 1) {
  return { snapshot_id: version, dataset_version: partition, definition: { id: 'spread.test' },
    rows: [{ date: `2026-10-0${value}`, spread: value }], total: 2, next_cursor: next }
}

it('各页保留同一快照与数据分区，并合并完整原始行', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(Response.json(page('next'))).mockResolvedValueOnce(Response.json(page(null, 2)))
  vi.stubGlobal('fetch', fetch)
  const result = await getSeries('spread.test', version, { start: '2026-10-01', snapshot_id: 'forged' })
  expect(result.rows.map(row => row.spread)).toEqual([1, 2])
  expect(fetch.mock.calls.every(([url]) => new URL(String(url), 'http://local').searchParams.get('snapshot_id') === version)).toBe(true)
  expect(String(fetch.mock.calls[1][0])).toContain('cursor=next')
})

it('页间快照漂移或循环游标停止整次图表读取', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(Response.json(page('next')))
    .mockResolvedValueOnce(Response.json({ ...page(null, 2), snapshot_id: 'c'.repeat(64) }))
  vi.stubGlobal('fetch', fetch)
  await expect(getSeries('spread.test', version, {})).rejects.toThrow('分页版本或格式不一致')
  fetch.mockReset().mockImplementation(async () => Response.json(page('cycle')))
  await expect(getSeries('spread.test', version, {})).rejects.toThrow('分页版本或格式不一致')
  expect(fetch).toHaveBeenCalledTimes(2)
})

it('跨页共用一个15秒截止，超时会取消正在读取的fetch', async () => {
  vi.useFakeTimers()
  let signal: AbortSignal | undefined
  vi.stubGlobal('fetch', vi.fn((_url, options) => {
    signal = options.signal
    return new Promise((_resolve, reject) => signal!.addEventListener('abort', () => reject(new Error('aborted'))))
  }))
  const result = read('catalog')
  const rejected = expect(result).rejects.toThrow('超过本次时间')
  await vi.advanceTimersByTimeAsync(15000)
  await rejected
  expect(signal?.aborted).toBe(true)
})

it('四品种刷新突发读取最多并发两项，排队取消不发请求且释放后可继续', async () => {
  const finish: (() => void)[] = []
  let active = 0, peak = 0
  const fetch = vi.fn(() => {
    active += 1; peak = Math.max(peak, active)
    return new Promise<Response>(resolve => finish.push(() => { active -= 1; resolve(Response.json({ ok: true })) }))
  })
  vi.stubGlobal('fetch', fetch)
  const first = read('first'), second = read('second'), controller = new AbortController()
  const cancelled = read('cancelled', {}, controller.signal)
  const rejection = expect(cancelled).rejects.toThrow('取消')
  const burst = Array.from({ length: 20 }, (_, i) => read('matrix/' + i))
  await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
  controller.abort(); await rejection
  for (let i = 0; i < 22; i++) {
    await vi.waitFor(() => expect(finish.length).toBeGreaterThan(0))
    finish.shift()!()
  }
  await Promise.all([first, second, ...burst])
  expect(peak).toBe(2)
  expect(fetch.mock.calls.flat().some(value => String(value).includes('cancelled'))).toBe(false)
})

it('排队沿调用者原截止，超期项不会等到获得名额后续期或发请求', async () => {
  vi.useFakeTimers()
  const finish: (() => void)[] = []
  const fetch = vi.fn(() => new Promise<Response>(resolve => finish.push(() => resolve(Response.json({ ok: true })))))
  vi.stubGlobal('fetch', fetch)
  const first = read('first'), second = read('second')
  const queued = read('queued', {}, undefined, Date.now() + 100)
  const rejected = expect(queued).rejects.toThrow('超过本次时间')
  await vi.advanceTimersByTimeAsync(100); await rejected
  finish.splice(0).forEach(done => done())
  await Promise.all([first, second])
  expect(fetch).toHaveBeenCalledTimes(2)
})

it('主线程延迟定时器时，超期排队项仍在发请求前拒绝', async () => {
  vi.useFakeTimers()
  const finish: (() => void)[] = []
  const fetch = vi.fn(() => new Promise<Response>(resolve => finish.push(() => resolve(Response.json({ ok: true })))))
  vi.stubGlobal('fetch', fetch)
  const first = read('first'), second = read('second')
  const queued = read('queued', {}, undefined, Date.now() + 100)
  const rejected = expect(queued).rejects.toThrow('超过本次时间')
  await Promise.resolve()
  vi.setSystemTime(Date.now() + 200)
  finish.splice(0).forEach(done => done())
  await Promise.all([first, second]); await rejected
  expect(fetch).toHaveBeenCalledTimes(2)
})

it('JSON完成跨越原截止且timer尚未执行时仍拒绝成功结果', async () => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => {
    vi.setSystemTime(Date.now() + 15001)
    return { ok: true }
  } }))
  await expect(read('catalog')).rejects.toThrow('超过本次时间')
})

it('下载完整正文前保持共享名额，图表读取排队后继续', async () => {
  const streams: ReadableStreamDefaultController<Uint8Array>[] = []
  const fetch = vi.fn((url: string) => Promise.resolve(String(url).includes('/exports?')
    ? new Response(new ReadableStream<Uint8Array>({ start(controller) { streams.push(controller) } }))
    : Response.json({ ok: true })))
  vi.stubGlobal('fetch', fetch)
  const first = downloadObservation({ format: 'csv' }), second = downloadObservation({ format: 'json' }), queued = read('catalog')
  await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
  streams[0].enqueue(new Uint8Array([1, 2, 3])); streams[0].close()
  expect((await first).size).toBe(3)
  await queued
  expect(fetch).toHaveBeenCalledTimes(3)
  streams[1].close(); await second
})

it('下载正文停滞时原15秒截止取消传输，随后读取仍可用', async () => {
  vi.useFakeTimers()
  let signal: AbortSignal | undefined
  vi.stubGlobal('fetch', vi.fn((_url, options) => {
    signal = options.signal
    return Promise.resolve(new Response(new ReadableStream({ start(controller) {
      signal!.addEventListener('abort', () => controller.error(new Error('aborted')))
    } })))
  }))
  const reading = downloadObservation({ format: 'csv' })
  const rejected = expect(reading).rejects.toThrow('超过本次时间')
  await vi.advanceTimersByTimeAsync(15000); await rejected
  expect(signal?.aborted).toBe(true)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ ok: true })))
  expect(await read('catalog')).toEqual({ ok: true })
})

it('超容量下载取消正文且不给出部分文件', async () => {
  const cancelled = vi.fn()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(new ReadableStream({
    start(controller) { controller.enqueue(new Uint8Array(16 * 1024 * 1024 + 1)) }, cancel: cancelled,
  }))))
  await expect(downloadObservation({ format: 'jsonl' })).rejects.toThrow('导出超过容量')
  expect(cancelled).toHaveBeenCalledOnce()
})

it('下载拒绝其他快照并关闭原传输', async () => {
  let signal: AbortSignal | undefined
  vi.stubGlobal('fetch', vi.fn((_url, options) => {
    signal = options.signal
    return Promise.resolve(new Response('[]', { headers: { 'x-observation-snapshot': 'c'.repeat(64) } }))
  }))
  await expect(downloadObservation({ format: 'json', snapshot_id: version })).rejects.toThrow('数据版本与当前页面不一致')
  expect(signal?.aborted).toBe(true)
})
