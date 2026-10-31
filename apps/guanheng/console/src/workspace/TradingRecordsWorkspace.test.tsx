import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AccountWorkspace from './AccountWorkspace'
import type { AccountField, AccountOverview } from './accountApi'
import sourceFixture from './account.fixture.json'

const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.unstubAllGlobals() })
const present = (value: string | number): AccountField => ({ availability: 'present', value, reason: null })
const response = (value: unknown) => new Response(JSON.stringify(value))
function fixture(): AccountOverview {
  const value = structuredClone(sourceFixture) as AccountOverview
  value.groups.order.rows = [{ identity: { m_strInstrumentID: '510300', m_strExchangeID: 'SH', m_strOrderSysID: 'synthetic-order' },
    fields: { side: present(48), quantity: present(200), filled: present(100), remaining: present(100), price: present(4.2), state: present('source-50') } }]
  value.groups.deal.rows = [{ identity: { m_strInstrumentID: '510300', m_strExchangeID: 'SH', m_strOrderSysID: 'synthetic-order', m_strTradeID: 'synthetic-deal' },
    fields: { side: present(48), quantity: present(100), price: present(4.2), amount: present(420) } }]
  return value
}
function mount(available = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })
  clients.push(client)
  render(<QueryClientProvider client={client}><AccountWorkspace view="trading-records"
    capability={{ available, reason: available ? null : '尚未配置账户读取来源', timeout_seconds: 15 }} /></QueryClientProvider>)
}

it('交易记录默认委托，切换成交和键盘导航复用同一观察，无审批或资金卡片', async () => {
  const fetchMock = vi.fn().mockResolvedValue(response(fixture()))
  vi.stubGlobal('fetch', fetchMock); mount()
  await screen.findByText('synthetic-order')
  expect(screen.getByRole('heading', { level: 1, name: '交易记录' })).toBeInTheDocument()
  expect(screen.getAllByRole('tab').map(tab => tab.textContent)).toEqual(['委托', '成交'])
  expect(screen.queryByRole('heading', { name: '总资产（元）' })).not.toBeInTheDocument()
  expect(screen.queryByText(/风险审批|资金分配|已批准待命令/)).not.toBeInTheDocument()
  const orders = screen.getByRole('tab', { name: '委托' }); orders.focus()
  fireEvent.keyDown(orders, { key: 'ArrowRight' })
  expect(screen.getByRole('tab', { name: '成交' })).toHaveFocus()
  expect(screen.getByRole('tabpanel')).toHaveAccessibleName('成交')
  expect(within(screen.getByRole('tabpanel')).getByText('synthetic-deal')).toBeInTheDocument()
  expect(screen.getByText(/查询时间（北京时间）/)).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('未配来源的交易记录保持无查询，完整空委托显示零条', async () => {
  const fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock); mount(false)
  expect(screen.getByText('尚未配置账户读取来源')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '刷新账户' })).toBeEnabled()
  expect(fetchMock).not.toHaveBeenCalled()
  cleanup()
  const empty = fixture(); empty.groups.order.rows = []
  fetchMock.mockResolvedValue(response(empty)); mount()
  await screen.findByText('本轮委托查询完整，返回 0 条记录。')
  expect(screen.queryByText('synthetic-order')).not.toBeInTheDocument()
})

it('委托批失败保留原因，独立完整的成交仍可查看', async () => {
  const value = fixture(); value.status = 'partial'
  value.groups.order = { ...value.groups.order, status: 'unavailable', rows: [], source: null,
    reason: '委托查询未完成，请检查来源连接', execution_started_at: null, execution_finished_at: null,
    request_id: null, result_sha256: null }
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(value))); mount()
  await screen.findByText('委托查询未完成，请检查来源连接')
  expect(screen.queryByText('本轮委托查询完整，返回 0 条记录。')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('tab', { name: '成交' }))
  expect(within(screen.getByRole('tabpanel')).getByText('synthetic-deal')).toBeInTheDocument()
})

it('交易记录刷新失败保留旧观察，明确刷新后恢复', async () => {
  let finish!: (value: Response) => void
  const fetchMock = vi.fn().mockResolvedValueOnce(response(fixture()))
    .mockImplementationOnce(() => new Promise<Response>(resolve => { finish = resolve }))
    .mockResolvedValueOnce(response(fixture()))
  vi.stubGlobal('fetch', fetchMock); mount()
  await screen.findByText('synthetic-order')
  fireEvent.click(screen.getByRole('button', { name: '刷新账户' }))
  await screen.findByRole('button', { name: '正在读取账户…' })
  expect(screen.getByText('synthetic-order')).toBeInTheDocument()
  finish(new Response('{}', { status: 503 }))
  await screen.findByText(/账户读取失败（HTTP 503）/)
  expect(screen.getByText('synthetic-order')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '刷新账户' }))
  await screen.findByText('synthetic-order')
  expect(fetchMock).toHaveBeenCalledTimes(3)
})
