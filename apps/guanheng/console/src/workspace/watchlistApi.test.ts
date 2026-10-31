import { afterEach, expect, it, vi } from 'vitest'
import { fetchReadJson } from '../api'
import { WATCHLIST_SCHEMA, WatchlistSaveError, decodePersonalWatchlist, fetchPersonalWatchlist,
  normalizePersonalSymbol, savePersonalWatchlist, sameWatchlistSymbols } from './watchlistApi'

vi.mock('../api', () => ({ fetchReadJson: vi.fn() }))
afterEach(() => { vi.resetAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers() })
const id = '00000000-0000-4000-8000-000000000001'
const stamp = '2026-10-23T01:00:00Z'
const raw = () => ({ schema_version: WATCHLIST_SCHEMA, watchlist_id: id, version: 1,
  symbols: ['600000.SH'], updated_at: stamp, affects_strategy: false as const, editable: true, reason: null })
const saved = (symbols: string[], version = 2) => ({ schema_version: WATCHLIST_SCHEMA,
  changed: version !== 1, watchlist: { ...raw(), symbols, version } })

it('有效空保留身份和版本，缺资料不能成为空成功', () => {
  expect(decodePersonalWatchlist({ ...raw(), symbols: [] }).symbols).toEqual([])
  for (const value of [null, [], {}, { ...raw(), watchlist_id: '' }]) {
    expect(() => decodePersonalWatchlist(value)).toThrow('格式或身份无效')
  }
})

it('复制并冻结完整值树，输入及返回数组不能改变已确认偏好', () => {
  const input = raw()
  const snapshot = decodePersonalWatchlist(input)
  input.symbols.push('510300.SH')
  expect(snapshot.symbols).toEqual(['600000.SH'])
  expect(Object.isFrozen(snapshot)).toBe(true)
  expect(Object.isFrozen(snapshot.symbols)).toBe(true)
  expect(() => (snapshot.symbols as string[]).push('510300.SH')).toThrow()
})

it.each([
  { ...raw(), version: true }, { ...raw(), version: 0 }, { ...raw(), version: 1.5 },
  { ...raw(), version: Number.MAX_SAFE_INTEGER + 1 }, { ...raw(), affects_strategy: true },
  { ...raw(), schema_version: '1.0' }, { ...raw(), audit_event_id: 'fake' },
  { ...raw(), editable: true, reason: '矛盾' }, { ...raw(), editable: false, reason: null },
  { ...raw(), watchlist_id: '12345678-1234-4234-8234-123456789ABC' },
])('拒绝不相容DTO和不安全版本 %#', value => {
  expect(() => decodePersonalWatchlist(value)).toThrow('格式或身份无效')
})

it.each(['2026-02-30T01:00:00Z', '2026-10-23T25:00:00Z', '2026-10-23T01:00:60Z',
  '2026-10-23T01:00:00+08:00', '2026-10-23T01:00:00', '0000-01-01T00:00:00Z'])('严格UTC日期拒绝自动归一化 %s', updated_at => {
  expect(() => decodePersonalWatchlist({ ...raw(), updated_at })).toThrow()
})

it('代码输入只规范观察代码，重复和非规范磁盘形状不被悄悄修正', () => {
  expect(normalizePersonalSymbol(' 600000.sh ')).toBe('600000.SH')
  for (const value of ['600000', '600000.SSE', '六00000.SH', ' '.repeat(33) + '600000.SH']) {
    expect(() => normalizePersonalSymbol(value)).toThrow()
  }
  for (const symbols of [['600000.SH', '600000.SH'], ['600000.sh'], [true], [['600000.SH']]]) {
    expect(() => decodePersonalWatchlist({ ...raw(), symbols })).toThrow()
  }
})

it('数量与UTF8原因分别限额，损坏Unicode不能成为有效说明', () => {
  const symbols = Array.from({ length: 100 }, (_, index) => String(index).padStart(6, '0') + '.SH')
  expect(decodePersonalWatchlist({ ...raw(), symbols }).symbols).toHaveLength(100)
  expect(() => decodePersonalWatchlist({ ...raw(), symbols: [...symbols, '999999.SH'] })).toThrow()
  for (const reason of ['中'.repeat(86), '\ud800', '']) {
    expect(() => decodePersonalWatchlist({ ...raw(), editable: false, reason })).toThrow()
  }
})

it('GET复用已有读取调度与预算，只请求个人观察入口', async () => {
  vi.mocked(fetchReadJson).mockResolvedValue(raw())
  const controller = new AbortController()
  expect((await fetchPersonalWatchlist(controller.signal)).symbols).toEqual(['600000.SH'])
  expect(fetchReadJson).toHaveBeenCalledExactlyOnceWith('/v1/ui/watchlists/default', '个人观察', controller.signal, 'workspace', 6500)
})

it('PUT只发送一次完整目标和期望版本，不增加审计字段', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(saved(['600000.SH', '510300.SH']))))
  vi.stubGlobal('fetch', fetch)
  const result = await savePersonalWatchlist(decodePersonalWatchlist(raw()), ['600000.SH', '510300.SH'])
  expect(result.changed).toBe(true)
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(fetch.mock.calls[0][0]).toBe('/v1/ui/watchlists/default')
  expect(fetch.mock.calls[0][1].method).toBe('PUT')
  expect(JSON.parse(fetch.mock.calls[0][1].body as string)).toEqual({ schema_version: WATCHLIST_SCHEMA,
    watchlist_id: id, expected_version: 1, symbols: ['600000.SH', '510300.SH'] })
  expect(fetchReadJson).not.toHaveBeenCalled()
})

it('相同顺序no-op保留版本与时间', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(saved(['600000.SH'], 1))))
  vi.stubGlobal('fetch', fetch)
  const result = await savePersonalWatchlist(decodePersonalWatchlist(raw()), ['600000.SH'])
  expect(result.changed).toBe(false)
  expect(result.watchlist.version).toBe(1)
  expect(result.watchlist.updated_at).toBe(stamp)
})

it('提交前无效目标和不可编辑资料均为零PUT', async () => {
  const fetch = vi.fn()
  vi.stubGlobal('fetch', fetch)
  for (const target of [['600000.SH', '600000.SH'], ['600000.sh']]) {
    await expect(savePersonalWatchlist(decodePersonalWatchlist(raw()), target)).rejects.toThrow()
  }
  await expect(savePersonalWatchlist(decodePersonalWatchlist({ ...raw(), editable: false, reason: '暂不能编辑' }), [])).rejects.toThrow()
  expect(fetch).not.toHaveBeenCalled()
})

it.each([
  saved(['600000.SH']), saved(['510300.SH', '600000.SH']), saved(['600000.SH', '510300.SH'], 3),
  { ...saved(['600000.SH', '510300.SH']), changed: false },
  { ...saved(['600000.SH', '510300.SH']), audit_event_id: 'fake' },
  { ...saved(['600000.SH', '510300.SH']), watchlist: { ...raw(), version: 2 } },
])('矛盾200属于保存结果未知且不重试 %#', async value => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(value)))
  vi.stubGlobal('fetch', fetch)
  await expect(savePersonalWatchlist(decodePersonalWatchlist(raw()), ['600000.SH', '510300.SH']))
    .rejects.toMatchObject({ state: 'unknown' })
  expect(fetch).toHaveBeenCalledTimes(1)
})

it.each([[409, 'conflict'], [422, 'rejected'], [403, 'rejected'], [503, 'unknown'], [500, 'unknown']])('按HTTP处理冲突和未知，原始正文不进入错误 %s', async (status, state) => {
  const fetch = vi.fn().mockResolvedValue(new Response('private-path token', { status: status as number }))
  vi.stubGlobal('fetch', fetch)
  const error = await savePersonalWatchlist(decodePersonalWatchlist(raw()), []).catch(value => value)
  expect(error).toBeInstanceOf(WatchlistSaveError)
  expect(error.state).toBe(state)
  expect(error.message).not.toContain('private-path')
  expect(fetch).toHaveBeenCalledTimes(1)
})

it('网络断开只报告未知，不发第二次PUT或隐式GET', async () => {
  const fetch = vi.fn().mockRejectedValue(new Error('private-host/token'))
  vi.stubGlobal('fetch', fetch)
  await expect(savePersonalWatchlist(decodePersonalWatchlist(raw()), [])).rejects.toMatchObject({ state: 'unknown' })
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(fetchReadJson).not.toHaveBeenCalled()
})

it('超过等待预算后保留结果未知，不自动重放', async () => {
  vi.useFakeTimers()
  const fetch = vi.fn((_url: string, options: RequestInit) => new Promise((_resolve, reject) => {
    options.signal?.addEventListener('abort', () => reject(new Error('abort')), { once: true })
  }))
  vi.stubGlobal('fetch', fetch)
  const assertion = expect(savePersonalWatchlist(decodePersonalWatchlist(raw()), [])).rejects.toMatchObject({ state: 'unknown' })
  await vi.advanceTimersByTimeAsync(6500)
  await assertion
  expect(fetch).toHaveBeenCalledTimes(1)
})

it('等待期间修改调用者数组不改变已发送目标和响应核对', async () => {
  let deliver: (response: Response) => void = () => { throw new Error('missing fetch') }
  const fetch = vi.fn((_url: RequestInfo | URL, _options: RequestInit) => new Promise<Response>(resolve => { deliver = resolve }))
  vi.stubGlobal('fetch', fetch)
  const target = ['600000.SH', '510300.SH']
  const pending = savePersonalWatchlist(decodePersonalWatchlist(raw()), target)
  target.reverse()
  deliver(new Response(JSON.stringify(saved(['600000.SH', '510300.SH']))))
  expect((await pending).watchlist.symbols).toEqual(['600000.SH', '510300.SH'])
  expect(JSON.parse(fetch.mock.calls[0][1].body as string).symbols).toEqual(['600000.SH', '510300.SH'])
})

it('完整顺序比较区分排序变化，最大版本只允许no-op', async () => {
  expect(sameWatchlistSymbols(['600000.SH', '510300.SH'], ['510300.SH', '600000.SH'])).toBe(false)
  const fetch = vi.fn()
  vi.stubGlobal('fetch', fetch)
  const previous = decodePersonalWatchlist({ ...raw(), version: Number.MAX_SAFE_INTEGER })
  await expect(savePersonalWatchlist(previous, [])).rejects.toThrow()
  expect(fetch).not.toHaveBeenCalled()
})
