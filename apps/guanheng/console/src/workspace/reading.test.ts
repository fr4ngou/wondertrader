import { afterEach, expect, it, vi } from 'vitest'
import { fetchReadJson } from '../api'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

it('账户独立预算覆盖原生采集等待，默认状态预算保持原值', async () => {
  vi.useFakeTimers()
  let receivedSignal!: AbortSignal
  vi.stubGlobal('fetch', vi.fn((_input, init: RequestInit) => {
    receivedSignal = init.signal as AbortSignal
    return new Promise<Response>((_resolve, reject) => receivedSignal.addEventListener('abort', () => reject(receivedSignal.reason), { once: true }))
  }))
  const read = fetchReadJson('/v1/ui/account/overview', '账户', undefined, 'workspace', 16_500)
  const timedOut = expect(read).rejects.toThrow('账户读取超时，请稍后重试')
  await vi.advanceTimersByTimeAsync(8_000)
  expect(receivedSignal.aborted).toBe(false)
  await vi.advanceTimersByTimeAsync(8_501)
  await timedOut
  expect(receivedSignal.aborted).toBe(true)
})

it('JSON读取边界保留调用者取消身份，不转成连接故障', async () => {
  vi.stubGlobal('fetch', vi.fn((_input, init: RequestInit) => new Promise((_resolve, reject) => {
    init.signal?.addEventListener('abort', () => reject(init.signal?.reason), { once: true })
  })))
  const controller = new AbortController()
  const request = fetchReadJson('/v1/ui/capabilities', '应用能力', controller.signal)
  controller.abort(new DOMException('caller cancelled', 'AbortError'))
  await expect(request).rejects.toMatchObject({ name: 'AbortError', message: 'caller cancelled' })
})

it('完成回调先于过期队列timer时仍报告读取超时且不访问来源', async () => {
  vi.useFakeTimers()
  const started = new Date('2026-10-22T00:00:00Z')
  vi.setSystemTime(started)
  let completeFirst!: (response: Response) => void
  const fetchMock = vi.fn(() => new Promise<Response>(resolve => { completeFirst = resolve }))
  vi.stubGlobal('fetch', fetchMock)
  // status通道容量为1；第二个请求必须等待前一个真正完成。
  const first = fetchReadJson('/v1/ui/capabilities?request=first', '应用能力', undefined, 'status')
  const queued = fetchReadJson('/v1/ui/capabilities?request=queued', '应用能力', undefined, 'status')
  expect(fetchMock).toHaveBeenCalledTimes(1)
  const timedOut = expect(queued).rejects.toThrow('应用能力读取超时，请稍后重试')
  // 只推进墙钟，不执行timer；模拟Promise完成回调先于已逾期timer获调度。
  vi.setSystemTime(started.getTime() + 6501)
  completeFirst(new Response('{"read_only":true}', { status: 200 }))
  await expect(first).resolves.toEqual({ read_only: true })
  await timedOut
  expect(fetchMock).toHaveBeenCalledTimes(1)
  expect(vi.getTimerCount()).toBe(0)
})
