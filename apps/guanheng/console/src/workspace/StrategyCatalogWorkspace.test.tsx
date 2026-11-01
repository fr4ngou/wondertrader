import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import StrategyCatalogWorkspace from './StrategyCatalogWorkspace'
vi.mock('./StrategyDetails',()=>({default:()=>null}))

const clients: QueryClient[] = []
const catalog = { schema: 'guanheng.strategy-catalog.v1', read_only: true, scope: 'registered-definitions', strategies: [
  { strategy_id: 'resonance-regime-v1', strategy_version: '1.1.2', display_name: '共振市场状态 ETF 策略',
    description: '根据完整日线计算市场状态与目标权重。', historical_versions: [] },
] }
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.unstubAllGlobals() })
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client)
  render(<QueryClientProvider client={client}><StrategyCatalogWorkspace /></QueryClientProvider>)
}
test('唯一最新版本只读展示、名称与版本搜索；全部请求为目录GET', async () => {
  const fetch = vi.fn().mockImplementation(() => Promise.resolve(Response.json(catalog)))
  vi.stubGlobal('fetch', fetch); mount()
  expect(await screen.findByRole('heading', { name: '共振市场状态 ETF 策略' })).toBeVisible()
  expect(screen.getByText('根据完整日线计算市场状态与目标权重。')).toBeVisible()
  expect(screen.getByText('v1.1.2')).toBeVisible()
  expect(screen.queryByText(/历史版本/)).toBeNull()
  expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(1)
  expect(screen.getAllByRole('textbox')).toHaveLength(1)
  expect(screen.queryByRole('spinbutton')).toBeNull()
  expect(screen.queryByRole('button')).toBeNull()
  fireEvent.change(screen.getByRole('textbox'), { target: { value: '1.0.0' } })
  expect(screen.queryByRole('heading', { name: '共振市场状态 ETF 策略' })).toBeNull()
  expect(screen.getByRole('status')).toHaveTextContent('没有匹配的策略')
  fireEvent.change(screen.getByRole('textbox'), { target: { value: '1.1.2' } })
  expect(screen.getByRole('heading', { name: '共振市场状态 ETF 策略' })).toBeVisible()
  fireEvent.change(screen.getByRole('textbox'), { target: { value: '不存在的策略' } })
  expect(screen.getByRole('status')).toHaveTextContent('没有匹配的策略')
  expect(fetch.mock.calls.every(call => call[0] === '/v1/ui/strategy-catalog' && (call[1]?.method ?? 'GET') === 'GET')).toBe(true)
})
test('读取失败后手动恢复；空目录清楚展示', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(Response.json({}, { status: 503 }))
    .mockResolvedValueOnce(Response.json({ ...catalog, strategies: [] })))
  mount()
  expect(await screen.findByRole('alert')).toHaveTextContent('策略目录读取失败')
  fireEvent.click(screen.getByRole('button', { name: '重新读取策略' }))
  expect(await screen.findByText('当前没有登记策略。')).toBeVisible()
  expect(screen.queryByRole('alert')).toBeNull()
})
