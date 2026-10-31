import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AccountWorkspace from './AccountWorkspace'
import { validateAccountOverview, type AccountField, type AccountOverviewV2 } from './accountApi'
import shmFixture from './account-v2.fixture.json'
import oldFixture from './account.fixture.json'
import { accountReadView } from './accountPresentation'

// 公开DTO合成页面定义；本轮未运行DOM/浏览器/npm。
const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.unstubAllGlobals() })
const fixture = () => structuredClone(shmFixture) as AccountOverviewV2
const response = (value: unknown) => new Response(JSON.stringify(value))
const present = (value: string | number): AccountField => ({ availability: 'present', value, reason: null })
function records() {
  const value = fixture()
  value.groups.order.rows = [{ identity: { m_strInstrumentID: '510300', m_strExchangeID: 'SH', m_strOrderSysID: 'synthetic-shm-order' },
    fields: { side: present(48), quantity: present(137), filled: present(19), remaining: present(118), price: present(3.25), state: present(50) } }]
  value.groups.deal.rows = [{ identity: { m_strInstrumentID: '510300', m_strExchangeID: 'SH', m_strOrderSysID: 'synthetic-shm-order', m_strTradeID: 'synthetic-shm-deal' },
    fields: { side: present(48), quantity: present(19), price: present(3.25), amount: present(61.75) } }]
  return value
}
function mount(view: 'account' | 'trading-records' = 'account', available = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })
  clients.push(client)
  render(<QueryClientProvider client={client}><AccountWorkspace view={view}
    capability={{ available, reason: available ? null : '尚未配置账户读取来源', timeout_seconds: 15 }} /></QueryClientProvider>)
}

it('DTO2展示持仓、可卖、掩码账户及逐批时间，内部运输标识保留原DTO', async () => {
  const fetchMock = vi.fn().mockResolvedValue(response(fixture()))
  vi.stubGlobal('fetch', fetchMock); mount()
  await screen.findByText('600000.SH')
  const panel = within(screen.getByRole('tabpanel'))
  expect(panel.queryByText(/Host|运输|摘要|会话|a{32}|b{32}|c{64}/)).not.toBeInTheDocument()
  expect(panel.getByText('700')).toBeInTheDocument()
  expect(panel.getByText('420')).toBeInTheDocument()
  expect(panel.getByText(/查询时间（北京时间）/)).toBeInTheDocument()
  expect(screen.queryByText(/来源会话：|synthetic-session|journal_generation|transport_binding/)).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /切换来源|选择账户|下单|撤单/ })).not.toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('交易记录同样接DTO2，切换成交复用一轮且不出现资金卡片', async () => {
  const fetchMock = vi.fn().mockResolvedValue(response(records()))
  vi.stubGlobal('fetch', fetchMock); mount('trading-records')
  await screen.findByText('synthetic-shm-order')
  expect(screen.getAllByRole('tab').map(tab => tab.textContent)).toEqual(['委托', '成交'])
  expect(screen.queryByRole('heading', { name: '总资产（元）' })).not.toBeInTheDocument()
  expect(screen.queryByText(/Host|运输|摘要|券商登录/)).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('tab', { name: '成交' }))
  expect(within(screen.getByRole('tabpanel')).getByText('synthetic-shm-deal')).toBeInTheDocument()
  expect(screen.getByText('61.75')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('旧DTO1同样只显示业务来源和时间', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(oldFixture))); mount()
  await screen.findByText('600000.SH')
  expect(screen.queryByText(/来源会话：|synthetic-session|代际/)).not.toBeInTheDocument()
  expect(screen.queryByText(/Host 运输绑定|券商登录未知/)).not.toBeInTheDocument()
})

it('完整空持仓和资金查询失败分开，缺失资金不显示零资产', async () => {
  const value = fixture(); value.status = 'partial'; value.groups.position.rows = []
  Object.assign(value.groups.account, { status: 'unavailable', rows: [], source: null, reason: '本轮资金查询未完成，金额保持未知。' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(value))); mount()
  await screen.findByText('本轮持仓查询完整，返回 0 条记录。')
  expect(screen.getByText('本轮资金查询未完成，金额保持未知。')).toBeInTheDocument()
  expect(screen.queryByText('123,456.789')).not.toBeInTheDocument()
  expect(screen.queryByText('0')).not.toBeInTheDocument()
})

it('DTO2整轮不可用保留中文原因和空来源，未配置不读取', async () => {
  const fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock); mount('account', false)
  expect(fetchMock).not.toHaveBeenCalled(); cleanup()
  const value = fixture(); value.status = 'unavailable'; value.reason = '本轮未取得账户观察，请明确刷新重读'
  for (const group of Object.values(value.groups)) Object.assign(group, { status: 'unavailable', rows: [], source: null,
    request_id: null, execution_started_at: null, execution_finished_at: null, result_sha256: null })
  fetchMock.mockResolvedValue(response(value)); mount()
  await screen.findByText(value.reason)
  expect(screen.queryByText(/Host 运输绑定已核验/)).not.toBeInTheDocument()
  expect(screen.queryByText('600000.SH')).not.toBeInTheDocument()
})

it('私有额外字段使DTO2整体拒绝，页面固定去敏且不自动重发', async () => {
  const value = fixture()
  Object.assign(value.groups.position.source!.transport, { secret: 'private-secret-not-for-display', path: 'private-path' })
  const fetchMock = vi.fn().mockResolvedValue(response(value))
  vi.stubGlobal('fetch', fetchMock); mount()
  await screen.findByText('账户数据格式无效，请重新读取')
  expect(screen.queryByText(/private-secret|private-path/)).not.toBeInTheDocument()
  expect(screen.queryByText('600000.SH')).not.toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('刷新失败保留旧DTO2，明确刷新后取得新的本轮值', async () => {
  let finish!: (value: Response) => void
  const fresh = fixture(); fresh.groups.position.rows[0].fields.quantity.value = 800
  const fetchMock = vi.fn().mockResolvedValueOnce(response(fixture()))
    .mockImplementationOnce(() => new Promise<Response>(resolve => { finish = resolve }))
    .mockResolvedValueOnce(response(fresh))
  vi.stubGlobal('fetch', fetchMock); mount()
  await screen.findByText('600000.SH')
  fireEvent.click(screen.getByRole('button', { name: '刷新账户' }))
  await screen.findByRole('button', { name: '正在读取账户…' })
  expect(screen.getByText('700')).toBeInTheDocument()
  finish(new Response('{}', { status: 503 }))
  await screen.findByText(/账户读取失败（HTTP 503）/)
  expect(screen.getByText('600000.SH')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(2)
  fireEvent.click(screen.getByRole('button', { name: '刷新账户' }))
  await screen.findByText('800')
  expect(fetchMock).toHaveBeenCalledTimes(3)
})

it.each(['account', 'trading-records'] as const)('DTO2的%s入口保持本地50行分页及无自动重连刷新', async view => {
  const value = records(), kind = view === 'account' ? 'position' : 'order'
  const original = value.groups[kind].rows[0]
  value.groups[kind].rows = Array.from({ length: 51 }, (_, index) => ({ ...structuredClone(original),
    identity: { m_strInstrumentID: String(600000 + index), m_strExchangeID: 'SH', m_strOrderSysID: 'synthetic-page-order' } }))
  const fetchMock = vi.fn().mockResolvedValue(response(value))
  vi.stubGlobal('fetch', fetchMock); mount(view)
  await screen.findByText('600000.SH')
  expect(screen.getAllByRole('row')).toHaveLength(51)
  expect(screen.queryByText('600050.SH')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '下一页' }))
  expect(screen.getByText('600050.SH')).toBeInTheDocument()
  expect(screen.getAllByRole('row')).toHaveLength(2)
  fireEvent.focus(window); fireEvent(window, new Event('online'))
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

const capabilityCases = (['account', 'trading-records'] as const).flatMap(view =>
  (['1.0', '2.0'] as const).map(version => ({ view, version })))

it.each(capabilityCases)('来源停用后保留已有$version缓存及原时间：$view', async ({ view, version }) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })
  clients.push(client)
  const value = version === '1.0' ? structuredClone(oldFixture) : records()
  const fetchMock = vi.fn().mockResolvedValue(response(value))
  vi.stubGlobal('fetch', fetchMock)
  const content = (available: boolean) => <QueryClientProvider client={client}><AccountWorkspace view={view}
    capability={{ available, reason: available ? null : '账户来源已停用', timeout_seconds: 15 }} /></QueryClientProvider>
  const mounted = render(content(true))
  await screen.findByRole('tabpanel')
  expect(fetchMock).toHaveBeenCalledTimes(1)
  mounted.rerender(content(false))
  expect(screen.getByText('账户来源已停用')).toBeInTheDocument()
  expect(screen.getByRole('tabpanel')).toBeInTheDocument()
  expect(screen.getByText(/当前显示已读取的账户结果/)).toBeInTheDocument()
  expect(screen.queryByText(/来源会话：|Host 运输绑定已核验/)).not.toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it.each(capabilityCases)('预缓存$version且来源禁用的挂载展示已读值：$view', ({ view, version }) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })
  clients.push(client)
  client.setQueryData(['independent-account-overview'], accountReadView(validateAccountOverview(version === '1.0' ? structuredClone(oldFixture) : records())))
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  render(<QueryClientProvider client={client}><AccountWorkspace view={view}
    capability={{ available: false, reason: '账户来源已停用', timeout_seconds: 15 }} /></QueryClientProvider>)
  expect(screen.getByText('账户来源已停用')).toBeInTheDocument()
  expect(screen.getByRole('tabpanel')).toBeInTheDocument()
  expect(screen.getByText(/当前显示已读取的账户结果/)).toBeInTheDocument()
  expect(screen.queryByText(/来源会话：|Host 运输绑定已核验/)).not.toBeInTheDocument()
  expect(fetchMock).not.toHaveBeenCalled()
})

it('新轮持仓失败保留原批和时间，资金更新；下一轮成功空持仓清除旧行', async () => {
  const partial = fixture(); partial.status = 'partial'
  partial.groups.position = { ...partial.groups.position, status: 'unavailable', rows: [], source: null,
    request_id: null, result_sha256: null, execution_started_at: null, execution_finished_at: null, reason: '持仓暂时无法读取' }
  partial.groups.account.rows[0].fields.total_asset = present(987654)
  // 协议对象键的排列与来源身份无关，覆盖原审查触发的嵌套重排。
  function reorder(value: unknown): unknown {
    if (Array.isArray(value)) return value.map(reorder)
    return value !== null && typeof value === 'object'
      ? Object.fromEntries(Object.entries(value).reverse().map(([key, item]) => [key, reorder(item)])) : value
  }
  for (const group of Object.values(partial.groups)) if (group.source) group.source = reorder(group.source) as typeof group.source
  const empty = fixture(); empty.groups.position.rows = []
  const fetchMock = vi.fn().mockResolvedValueOnce(response(fixture())).mockResolvedValueOnce(response(partial)).mockResolvedValueOnce(response(empty))
  vi.stubGlobal('fetch', fetchMock); mount()
  await screen.findByText('700')
  fireEvent.click(screen.getByRole('button', { name: '刷新账户' }))
  await screen.findByText('987,654')
  expect(screen.getByText('700')).toBeVisible()
  expect(screen.getByText(/本轮持仓未更新，保留上次成功结果/)).toBeVisible()
  expect(within(screen.getByRole('tabpanel')).getByText(/查询时间（北京时间）/)).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '刷新账户' }))
  await screen.findByText('本轮持仓查询完整，返回 0 条记录。')
  expect(screen.queryByText('700')).not.toBeInTheDocument()
})

it('已知账户来源改变时，失败的持仓批不回退前一来源', async () => {
  const changed = fixture(); changed.status = 'partial'
  for (const group of Object.values(changed.groups)) if (group.source) group.source.account_label = '****9999'
  changed.groups.position = { ...changed.groups.position, status: 'unavailable', rows: [], source: null,
    request_id: null, result_sha256: null, execution_started_at: null, execution_finished_at: null, reason: '新来源持仓暂时无法读取' }
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response(fixture())).mockResolvedValueOnce(response(changed)))
  mount(); await screen.findByText('700')
  fireEvent.click(screen.getByRole('button', { name: '刷新账户' }))
  await screen.findByText('新来源持仓暂时无法读取')
  expect(screen.queryByText('700')).not.toBeInTheDocument()
  expect(screen.queryByText(/保留上次成功结果/)).not.toBeInTheDocument()
  expect(screen.getByText(/\*\*\*\*9999/)).toBeVisible()
})
