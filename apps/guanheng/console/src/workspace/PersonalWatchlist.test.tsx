import { afterEach, expect, test, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { usePersonalWatchlist, PERSONAL_WATCHLIST_QUERY_KEY } from './usePersonalWatchlist'
import * as api from './watchlistApi'
vi.mock('./watchlistApi', async original => ({ ...await original<typeof import('./watchlistApi')>(), fetchPersonalWatchlist: vi.fn(), savePersonalWatchlist: vi.fn() }))
const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.resetAllMocks() })
const capability = { available: true, editable: true, max_items: 100, scope: 'personal-observation', affects_strategy: false, reason: null }
function snapshot(symbols: string[] = [], version = 1) {
  return api.decodePersonalWatchlist({ schema_version: api.WATCHLIST_SCHEMA, watchlist_id: '12345678-1234-4234-8234-123456789abc', version, symbols,
    updated_at: `2026-11-01T01:0${version}:00Z`, affects_strategy: false, editable: true, reason: null })
}
function Harness({ value }: { value: unknown }) {
  const m = usePersonalWatchlist(value)
  return <><span>{m.symbols.join(',')}</span><p role="status">{m.message}</p><button disabled={!m.canEdit} onClick={() => void m.toggle('300308.SZ')}>星标</button>
    <button onClick={() => void m.reread()}>刷新自选</button>{m.needsReview && !m.needsRead ? <button onClick={m.confirm}>确认</button> : null}</>
}
function show(value: unknown = capability, existing?: QueryClient) {
  const client = existing ?? new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } }); if (!existing) clients.push(client)
  return { client, ...render(<QueryClientProvider client={client}><Harness value={value} /></QueryClientProvider>) }
}
const saved = (watchlist: api.PersonalWatchlist) => ({ schema_version: api.WATCHLIST_SCHEMA, changed: true, watchlist })
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes }); return { promise, resolve } }
test.each([null, {}, { ...capability, affects_strategy: true }, { ...capability, available: false, editable: false, reason: '未配置' }])('不可用偏好不触发请求：%j', value => {
  show(value); expect(api.fetchPersonalWatchlist).not.toHaveBeenCalled(); expect(screen.getByText('星标')).toBeDisabled()
})
test('星标使用原版本化偏好增减', async () => {
  vi.mocked(api.fetchPersonalWatchlist).mockResolvedValue(snapshot()); vi.mocked(api.savePersonalWatchlist).mockResolvedValueOnce(saved(snapshot(['300308.SZ'], 2))).mockResolvedValueOnce(saved(snapshot([], 3)))
  show(); await waitFor(() => expect(screen.getByText('星标')).toBeEnabled()); fireEvent.click(screen.getByText('星标')); await screen.findByText('300308.SZ')
  expect(api.savePersonalWatchlist).toHaveBeenNthCalledWith(1, snapshot(), ['300308.SZ'])
  fireEvent.click(screen.getByText('星标')); await waitFor(() => expect(api.savePersonalWatchlist).toHaveBeenCalledTimes(2)); await waitFor(() => expect(screen.queryByText('300308.SZ')).not.toBeInTheDocument())
})
test('未知结果通过查询核实而不重复保存', async () => {
  vi.mocked(api.fetchPersonalWatchlist).mockResolvedValueOnce(snapshot()).mockResolvedValueOnce(snapshot(['300308.SZ'], 2)); vi.mocked(api.savePersonalWatchlist).mockRejectedValueOnce(new api.WatchlistSaveError('unknown'))
  show(); await waitFor(() => expect(screen.getByText('星标')).toBeEnabled()); fireEvent.click(screen.getByText('星标')); await screen.findByText('保存结果待确认，请刷新自选。')
  expect(screen.getByText('星标')).toBeDisabled(); fireEvent.click(screen.getByText('星标')); expect(api.savePersonalWatchlist).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByText('刷新自选')); await waitFor(() => expect(screen.getByText('星标')).toBeEnabled()); expect(screen.getByText('300308.SZ')).toBeVisible(); expect(api.savePersonalWatchlist).toHaveBeenCalledTimes(1)
})
test('冲突后核实不同列表，确认后继续', async () => {
  vi.mocked(api.fetchPersonalWatchlist).mockResolvedValueOnce(snapshot()).mockResolvedValueOnce(snapshot(['588170.SH'], 3)); vi.mocked(api.savePersonalWatchlist).mockRejectedValueOnce(new api.WatchlistSaveError('conflict'))
  show(); await waitFor(() => expect(screen.getByText('星标')).toBeEnabled()); fireEvent.click(screen.getByText('星标')); await screen.findByText('自选已更新，请刷新后确认。')
  fireEvent.click(screen.getByText('刷新自选')); fireEvent.click(await screen.findByText('确认')); await waitFor(() => expect(screen.getByText('星标')).toBeEnabled()); expect(screen.getByText('588170.SH')).toBeVisible()
})
test('路由卸载保留在途保存，旧GET不回退成功版本', async () => {
  const pending = deferred<api.WatchlistSaveResult>(), stale = deferred<api.PersonalWatchlist>()
  vi.mocked(api.fetchPersonalWatchlist).mockResolvedValueOnce(snapshot()).mockReturnValueOnce(stale.promise); vi.mocked(api.savePersonalWatchlist).mockReturnValueOnce(pending.promise)
  const first = show(); await waitFor(() => expect(screen.getByText('星标')).toBeEnabled()); fireEvent.click(screen.getByText('星标')); first.unmount(); show(capability, first.client)
  expect(screen.getByText('星标')).toBeDisabled(); await act(async () => { pending.resolve(saved(snapshot(['300308.SZ'], 2))) }); await act(async () => { stale.resolve(snapshot()) })
  await waitFor(() => expect(screen.getByText('星标')).toBeEnabled()); expect(first.client.getQueryData<api.PersonalWatchlist>(PERSONAL_WATCHLIST_QUERY_KEY)?.version).toBe(2)
  expect(screen.getByText('300308.SZ')).toBeVisible(); expect(api.savePersonalWatchlist).toHaveBeenCalledTimes(1)
})
