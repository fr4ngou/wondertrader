import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AccountWorkspace from './AccountWorkspace'
import type { AccountOverview } from './accountApi'
import sourceFixture from './account.fixture.json'

const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.unstubAllGlobals() })
const fixture = () => structuredClone(sourceFixture) as AccountOverview
const response = (value: unknown) => new Response(JSON.stringify(value))
function mount(available = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })
  clients.push(client)
  render(<QueryClientProvider client={client}><AccountWorkspace capability={{ available, reason: available ? null : '尚未配置账户读取来源', timeout_seconds: 15 }} /></QueryClientProvider>)
}

it('未配置时明确原因并保留主动重读入口', () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  mount(false)
  expect(screen.getByText('尚未配置账户读取来源')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '刷新账户' })).toBeEnabled()
  expect(fetchMock).not.toHaveBeenCalled()
})

it('展示来源持仓和可卖，缺失冻结保持未知，零资金保留为零', async () => {
  const value = fixture()
  value.groups.account.rows[0].fields.available.value = 0
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(value)))
  mount()
  await screen.findByText('600000.SH')
  const row = screen.getAllByRole('row')[1]
  expect(within(row).getByText('700')).toBeInTheDocument()
  expect(within(row).getByText('420')).toBeInTheDocument()
  expect(within(row).queryByText('280')).not.toBeInTheDocument()
  const cash = screen.getByRole('heading', { name: '可用资金（元）' }).closest('article')!
  expect(within(cash).getByText('0')).toBeInTheDocument()
  expect(screen.getAllByText(/\*\*\*\*3456/).length).toBeGreaterThan(0)
  expect(screen.getByText(/券商交易日：未知/)).toBeInTheDocument()
})

it('完整空委托与失败委托分开呈现', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(fixture())))
  mount()
  await screen.findByText('600000.SH')
  fireEvent.click(screen.getByRole('tab', { name: '委托' }))
  expect(screen.getByText('本轮委托查询完整，返回 0 条记录。')).toBeInTheDocument()
  cleanup()
  const partial = fixture()
  partial.status = 'partial'
  partial.close.status = 'failed'
  partial.groups.order = { ...partial.groups.order, status: 'unavailable', source: null, request_id: null,
    result_sha256: null, execution_started_at: null, execution_finished_at: null, reason: '本轮委托查询失败，请检查来源连接' }
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(partial)))
  mount()
  await screen.findByText('600000.SH')
  fireEvent.click(screen.getByRole('tab', { name: '委托' }))
  expect(screen.getByText('本轮委托查询失败，请检查来源连接')).toBeInTheDocument()
  expect(screen.queryByText('本轮委托查询完整，返回 0 条记录。')).not.toBeInTheDocument()
})

it('刷新中和失败保留旧观察，成功后更新为新值', async () => {
  let complete!: (value: Response) => void
  const recovered = fixture()
  recovered.groups.position.rows[0].fields.quantity.value = 800
  const fetchMock = vi.fn().mockResolvedValueOnce(response(fixture()))
    .mockImplementationOnce(() => new Promise<Response>(resolve => { complete = resolve }))
    .mockResolvedValueOnce(response(recovered))
  vi.stubGlobal('fetch', fetchMock)
  mount()
  await screen.findByText('600000.SH')
  fireEvent.click(screen.getByRole('button', { name: '刷新账户' }))
  await screen.findByRole('button', { name: '正在读取账户…' })
  expect(screen.getByText('600000.SH')).toBeInTheDocument()
  complete(new Response('{}', { status: 503 }))
  await screen.findByText(/账户读取失败（HTTP 503）/)
  expect(screen.getByText('700')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '刷新账户' }))
  await screen.findByText('800')
  expect(fetchMock).toHaveBeenCalledTimes(3)
})

it('较多记录按页展示，后页记录仍可查看', async () => {
  const value = fixture()
  const original = value.groups.position.rows[0]
  value.groups.position.rows = Array.from({ length: 51 }, (_, index) => ({ ...structuredClone(original), identity: { m_strInstrumentID: String(600000 + index), m_strExchangeID: 'SH' } }))
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(value)))
  mount()
  await screen.findByText('600000.SH')
  expect(screen.getAllByRole('row')).toHaveLength(51)
  expect(screen.queryByText('600050.SH')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '下一页' }))
  await waitFor(() => expect(screen.getByText('600050.SH')).toBeInTheDocument())
  expect(screen.getAllByRole('row')).toHaveLength(2)
})

it('账户记录标签支持键盘切换，选择与焦点同步', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(fixture())))
  mount()
  await screen.findByText('600000.SH')
  const holdings = screen.getByRole('tab', { name: '持仓' })
  holdings.focus()
  fireEvent.keyDown(holdings, { key: 'ArrowRight' })
  const orders = screen.getByRole('tab', { name: '委托' })
  expect(orders).toHaveFocus()
  expect(orders).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByRole('tabpanel')).toHaveAccessibleName('委托')
})

it('首次读取繁忙时说明等待，并可从相同入口恢复', async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce(new Response('{}', { status: 429 }))
    .mockResolvedValueOnce(response(fixture()))
  vi.stubGlobal('fetch', fetchMock)
  mount()
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('账户读取繁忙，请等待本轮结束后刷新')
  expect(alert).toHaveTextContent('尚未取得账户数据，可稍后按“刷新账户”重试。')
  expect(alert).not.toHaveTextContent('检查来源连接')
  fireEvent.click(screen.getByRole('button', { name: '刷新账户' }))
  await screen.findByText('600000.SH')
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})
