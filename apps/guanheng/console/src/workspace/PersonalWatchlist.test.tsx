import { afterEach, expect, test, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import PersonalWatchlist, { PERSONAL_WATCHLIST_QUERY_KEY } from './PersonalWatchlist'
import * as api from './watchlistApi'

vi.mock('./watchlistApi', async importOriginal => {
  const actual = await importOriginal<typeof import('./watchlistApi')>()
  return { ...actual, fetchPersonalWatchlist: vi.fn(), savePersonalWatchlist: vi.fn() }
})
const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.resetAllMocks() })
const id = '12345678-1234-4234-8234-123456789abc'
const otherId = '12345678-1234-4234-9234-123456789abc'
const capability = { available: true, editable: true, max_items: 100,
  scope: 'personal-observation', affects_strategy: false, reason: null }

function snapshot(symbols: string[] = [], version = 1, identity = id, editable = true) {
  return api.decodePersonalWatchlist({ schema_version: api.WATCHLIST_SCHEMA, watchlist_id: identity, version, symbols,
    updated_at: '2026-10-23T01:0' + (version - 1) + ':00Z', affects_strategy: false, editable,
    reason: editable ? null : '临时资料需要检查，当前仅供查看' })
}
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
function show(overrides: Partial<Parameters<typeof PersonalWatchlist>[0]> = {}, existing?: QueryClient) {
  const client = existing ?? new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } })
  clients.push(client)
  const props = { capability, chartAvailable: true, chartBusy: false, onView: vi.fn(), ...overrides }
  const view = render(<QueryClientProvider client={client}><PersonalWatchlist {...props} /></QueryClientProvider>)
  return { client, props, ...view }
}
function addInput(value: string) {
  const input = screen.getByRole('textbox', { name: '加入个人观察的证券代码' })
  fireEvent.change(input, { target: { value } })
  return input.closest('form')!
}
async function ready(value = snapshot()) {
  vi.mocked(api.fetchPersonalWatchlist).mockResolvedValue(value)
  const view = show()
  await waitFor(() => expect(screen.getByRole('button', { name: '加入个人观察' })).toBeEnabled())
  return view
}
function saved(value: api.PersonalWatchlist): api.WatchlistSaveResult {
  return { schema_version: api.WATCHLIST_SCHEMA, changed: true, watchlist: value }
}

test.each([undefined, { ...capability, available: false, editable: false, reason: '未配置' },
  { ...capability, available: 'true' }, { ...capability, max_items: 101 }, { ...capability, scope: 'strategy' },
  { ...capability, available: false, editable: true }, { ...capability, affects_strategy: true }, { ...capability, extra: 1 },
  { ...capability, reason: 'private://token' }, { ...capability, editable: false, reason: '\ud800' }])(
  '缺失、关闭或畸形能力保持零个人观察请求：%j', value => {
    show({ capability: value })
    expect(screen.getByRole('heading', { name: '我的个人观察' })).toBeVisible()
    expect(api.fetchPersonalWatchlist).not.toHaveBeenCalled()
    expect(api.savePersonalWatchlist).not.toHaveBeenCalled()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(screen.queryByText(/private:\/\//)).not.toBeInTheDocument()
  },
)

test('有效空列表允许本地偏好编辑，行情关闭不触发查看', async () => {
  vi.mocked(api.fetchPersonalWatchlist).mockResolvedValue(snapshot())
  show({ chartAvailable: false })
  expect(await screen.findByText('个人观察列表为空；输入完整证券代码加入，仅供本页观察。')).toBeVisible()
  await waitFor(() => expect(screen.getByRole('button', { name: '加入个人观察' })).toBeEnabled())
  expect(screen.getByText('分钟行情尚未配置；个人观察的读取和保存可独立使用。')).toBeVisible()
  expect(api.fetchPersonalWatchlist).toHaveBeenCalledTimes(1)
  expect(api.savePersonalWatchlist).not.toHaveBeenCalled()
})

test('表单提交与快速重复提交只保存一次，收到回执前不乐观加入', async () => {
  await ready(snapshot(['600000.SH']))
  const pending = deferred<api.WatchlistSaveResult>()
  vi.mocked(api.savePersonalWatchlist).mockReturnValue(pending.promise)
  const form = addInput(' 510300.sh ')
  fireEvent.submit(form)
  fireEvent.submit(form)
  expect(api.savePersonalWatchlist).toHaveBeenCalledTimes(1)
  expect(api.savePersonalWatchlist).toHaveBeenCalledWith(snapshot(['600000.SH']), ['600000.SH', '510300.SH'])
  expect(screen.queryByRole('button', { name: '查看 510300.SH 分钟线' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '加入个人观察' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '重新读取个人观察' })).toBeDisabled()
  await act(async () => { pending.resolve(saved(snapshot(['600000.SH', '510300.SH'], 2))) })
  expect(await screen.findByText('已保存个人观察；策略交易范围不变。')).toBeVisible()
  expect(screen.getByRole('button', { name: '查看 510300.SH 分钟线' })).toBeVisible()
  expect(screen.getByRole('textbox', { name: '加入个人观察的证券代码' })).toHaveValue('')
  await waitFor(() => expect(screen.getByRole('textbox', { name: '加入个人观察的证券代码' })).toHaveFocus())
})

test.each(['', '600000', '600000.XY', '🙂.SH', '600000.sh'])('非法或重复输入零PUT：%s', async value => {
  await ready(snapshot(['600000.SH']))
  fireEvent.submit(addInput(value))
  expect(await screen.findByRole('alert')).toBeVisible()
  expect(api.savePersonalWatchlist).not.toHaveBeenCalled()
})

test('100项边界保留完整列表并拒第101项，不截断成较小保存', async () => {
  await ready(snapshot(Array.from({ length: 100 }, (_, n) => String(100000 + n) + '.SH')))
  fireEvent.submit(addInput('600000.SH'))
  expect(await screen.findByText('个人观察最多保存100个证券，请先移出一项。')).toBeVisible()
  expect(screen.getAllByRole('button', { name: /^移出 / })).toHaveLength(100)
  expect(api.savePersonalWatchlist).not.toHaveBeenCalled()
})

test('移出最后一项完整提交空数组，并在回执后显示有效空', async () => {
  await ready(snapshot(['600000.SH']))
  vi.mocked(api.savePersonalWatchlist).mockResolvedValue(saved(snapshot([], 2)))
  fireEvent.click(screen.getByRole('button', { name: '移出 600000.SH 的个人观察' }))
  expect(await screen.findByText('个人观察列表为空；输入完整证券代码加入，仅供本页观察。')).toBeVisible()
  expect(api.savePersonalWatchlist).toHaveBeenCalledWith(snapshot(['600000.SH']), [])
  expect(api.savePersonalWatchlist).toHaveBeenCalledTimes(1)
})

test('未知结果只GET原目标核查，完整目标与身份一致后恢复，原异常不显示', async () => {
  await ready(snapshot(['600000.SH']))
  vi.mocked(api.savePersonalWatchlist).mockRejectedValue(new Error('secret=abc file:///private'))
  fireEvent.submit(addInput('510300.SH'))
  expect(await screen.findByText(/保存结果尚未确认/)).toBeVisible()
  expect(screen.queryByText(/secret=|file:/)).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '加入个人观察' })).toBeDisabled()
  vi.mocked(api.fetchPersonalWatchlist).mockResolvedValue(snapshot(['600000.SH', '510300.SH'], 2))
  fireEvent.click(screen.getByRole('button', { name: '重新读取个人观察' }))
  expect(await screen.findByText('已核实当前列表与本次保存目标一致；策略交易范围不变。')).toBeVisible()
  expect(api.savePersonalWatchlist).toHaveBeenCalledTimes(1)
  expect(api.fetchPersonalWatchlist).toHaveBeenCalledTimes(2)
  expect(screen.getByRole('button', { name: '加入个人观察' })).toBeEnabled()
})

test.each(['unknown', 'conflict', 'rejected'] as const)('保存%s后先读取，目标不同须确认当前列表才能继续', async state => {
  await ready(snapshot(['600000.SH']))
  vi.mocked(api.savePersonalWatchlist).mockRejectedValue(new api.WatchlistSaveError(state))
  fireEvent.submit(addInput('510300.SH'))
  await screen.findByRole('alert')
  expect(screen.getByRole('button', { name: '加入个人观察' })).toBeDisabled()
  expect(screen.queryByRole('button', { name: '确认当前列表后继续编辑' })).not.toBeInTheDocument()
  vi.mocked(api.fetchPersonalWatchlist).mockResolvedValue(snapshot(['000001.SZ'], 2))
  fireEvent.click(screen.getByRole('button', { name: '重新读取个人观察' }))
  expect(await screen.findByText(/本次目标尚未在当前列表中确认/)).toBeVisible()
  expect(screen.getByRole('button', { name: '加入个人观察' })).toBeDisabled()
  expect(api.savePersonalWatchlist).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('button', { name: '确认当前列表后继续编辑' }))
  expect(screen.getByRole('button', { name: '加入个人观察' })).toBeEnabled()
  expect(api.savePersonalWatchlist).toHaveBeenCalledTimes(1)
})

test.each([
  snapshot(['600000.SH', '510300.SH'], 2, otherId),
  snapshot(['510300.SH', '600000.SH'], 2),
])('GET同符号异ID或相同集合异顺序均不冒称目标已确认', async received => {
  await ready(snapshot(['600000.SH']))
  vi.mocked(api.savePersonalWatchlist).mockRejectedValue(new api.WatchlistSaveError('unknown'))
  fireEvent.submit(addInput('510300.SH'))
  await screen.findByText(/保存结果尚未确认/)
  vi.mocked(api.fetchPersonalWatchlist).mockResolvedValue(received)
  fireEvent.click(screen.getByRole('button', { name: '重新读取个人观察' }))
  expect(await screen.findByRole('button', { name: '确认当前列表后继续编辑' })).toBeVisible()
  expect(screen.queryByText(/已核实当前列表与本次保存目标一致/)).not.toBeInTheDocument()
  expect(api.savePersonalWatchlist).toHaveBeenCalledTimes(1)
})

test('普通GET变更列表身份须明确确认，不合并旧代码', async () => {
  await ready(snapshot(['600000.SH']))
  vi.mocked(api.fetchPersonalWatchlist).mockResolvedValue(snapshot(['000001.SZ'], 1, otherId))
  fireEvent.click(screen.getByRole('button', { name: '重新读取个人观察' }))
  expect(await screen.findByText(/列表身份已变化/)).toBeVisible()
  expect(screen.queryByRole('button', { name: '查看 600000.SH 分钟线' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '加入个人观察' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: '确认当前列表后继续编辑' }))
  expect(screen.getByRole('button', { name: '加入个人观察' })).toBeEnabled()
})

test('晚到旧GET不覆盖已确认的较新版本', async () => {
  const incoming = deferred<api.PersonalWatchlist>()
  vi.mocked(api.fetchPersonalWatchlist).mockReturnValue(incoming.promise)
  const { client } = show()
  // 模拟同query key已收到PUT新版本回执，而原GET尚未完成。
  act(() => { client.setQueryData(PERSONAL_WATCHLIST_QUERY_KEY, snapshot(['510300.SH'], 3)) })
  await act(async () => { incoming.resolve(snapshot(['600000.SH'], 1)) })
  expect(await screen.findByRole('button', { name: '查看 510300.SH 分钟线' })).toBeVisible()
  expect(screen.queryByRole('button', { name: '查看 600000.SH 分钟线' })).not.toBeInTheDocument()
  expect(client.getQueryData<api.PersonalWatchlist>(PERSONAL_WATCHLIST_QUERY_KEY)?.version).toBe(3)
})

test('同ID同版本持久字段矛盾保持失败，不发布假成功列表', async () => {
  await ready(snapshot(['600000.SH']))
  vi.mocked(api.fetchPersonalWatchlist).mockResolvedValue(snapshot(['000001.SZ']))
  fireEvent.click(screen.getByRole('button', { name: '重新读取个人观察' }))
  expect(await screen.findByText(/个人观察读取失败或资料无效/)).toBeVisible()
  expect(screen.getByRole('button', { name: '加入个人观察' })).toBeDisabled()
  expect(screen.queryByRole('button', { name: '查看 000001.SZ 分钟线' })).not.toBeInTheDocument()
})

test('读取失败暂停编辑，手工重读恢复且不显示底层异常', async () => {
  await ready(snapshot(['600000.SH']))
  vi.mocked(api.fetchPersonalWatchlist).mockRejectedValue(new Error('http://private secret'))
  fireEvent.click(screen.getByRole('button', { name: '重新读取个人观察' }))
  expect(await screen.findByText(/个人观察读取失败或资料无效/)).toBeVisible()
  expect(screen.getByRole('button', { name: '加入个人观察' })).toBeDisabled()
  expect(screen.queryByText(/http:\/\/private|secret/)).not.toBeInTheDocument()
  vi.mocked(api.fetchPersonalWatchlist).mockResolvedValue(snapshot(['600000.SH']))
  fireEvent.click(screen.getByRole('button', { name: '重新读取个人观察' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '加入个人观察' })).toBeEnabled())
  expect(api.savePersonalWatchlist).not.toHaveBeenCalled()
})

test.each([true, false])('readonly快照或能力禁止PUT，但查看分钟按钮独立：%s', async snapshotReadonly => {
  vi.mocked(api.fetchPersonalWatchlist).mockResolvedValue(snapshot(['600000.SH'], 1, id, !snapshotReadonly))
  const { props } = show({ capability: snapshotReadonly ? capability : { ...capability, editable: false, reason: '仅供查看' } })
  expect(await screen.findByText(/个人观察目前仅可查看/)).toBeVisible()
  expect(screen.getByRole('button', { name: '移出 600000.SH 的个人观察' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: '查看 600000.SH 分钟线' }))
  expect(props.onView).toHaveBeenCalledWith('600000.SH')
  expect(api.savePersonalWatchlist).not.toHaveBeenCalled()
})

test.each([{ chartAvailable: false, chartBusy: false }, { chartAvailable: true, chartBusy: true }])(
  '分钟未准入或忙时查看按钮禁用，偏好表单仍按自己的能力：%j', async state => {
    vi.mocked(api.fetchPersonalWatchlist).mockResolvedValue(snapshot(['600000.SH']))
    const { props } = show(state)
    const button = await screen.findByRole('button', { name: '查看 600000.SH 分钟线' })
    expect(button).toBeDisabled()
    fireEvent.click(button)
    expect(props.onView).not.toHaveBeenCalled()
    await waitFor(() => expect(screen.getByRole('button', { name: '加入个人观察' })).toBeEnabled())
  },
)

test('安全整数版本上限仅可查看，不把本地拒绝描述成未知提交', async () => {
  vi.mocked(api.fetchPersonalWatchlist).mockResolvedValue(api.decodePersonalWatchlist({
    ...snapshot(['600000.SH']), version: Number.MAX_SAFE_INTEGER,
  }))
  show()
  expect(await screen.findByText(/个人观察版本已达到上限/)).toBeVisible()
  expect(screen.getByRole('button', { name: '加入个人观察' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '移出 600000.SH 的个人观察' })).toBeDisabled()
  expect(api.savePersonalWatchlist).not.toHaveBeenCalled()
  expect(screen.queryByText(/保存结果尚未确认/)).not.toBeInTheDocument()
})

test('重新挂载时保留缓存列表身份，新的不同ID仍须确认', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })
  client.setQueryData(PERSONAL_WATCHLIST_QUERY_KEY, snapshot(['600000.SH']))
  vi.mocked(api.fetchPersonalWatchlist).mockResolvedValue(snapshot(['000001.SZ'], 1, otherId))
  show({}, client)
  expect(await screen.findByText(/列表身份已变化/)).toBeVisible()
  expect(screen.getByRole('button', { name: '加入个人观察' })).toBeDisabled()
  expect(screen.queryByRole('button', { name: '查看 600000.SH 分钟线' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '确认当前列表后继续编辑' }))
  expect(screen.getByRole('button', { name: '加入个人观察' })).toBeEnabled()
  expect(api.savePersonalWatchlist).not.toHaveBeenCalled()
})

test('列表重读已可编辑但应用能力仍只读时，明确整页刷新且不自动重试写入', async () => {
  vi.mocked(api.fetchPersonalWatchlist).mockResolvedValue(snapshot(['600000.SH'], 1, id, false))
  show({ capability: { ...capability, editable: false, reason: '需要维护' } })
  await screen.findByText(/维护完成后请刷新整个页面，以重新核实应用能力和列表/)
  vi.mocked(api.fetchPersonalWatchlist).mockResolvedValue(snapshot(['600000.SH']))
  fireEvent.click(screen.getByRole('button', { name: '重新读取个人观察' }))
  await waitFor(() => expect(api.fetchPersonalWatchlist).toHaveBeenCalledTimes(2))
  expect(screen.getByRole('button', { name: '加入个人观察' })).toBeDisabled()
  expect(screen.getByText(/维护完成后请刷新整个页面，以重新核实应用能力和列表/)).toBeVisible()
  expect(api.savePersonalWatchlist).not.toHaveBeenCalled()
})
