import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import BacktestPerformance, { reportLabel } from './BacktestPerformance'
import * as api from './backtestPerformanceApi'
import * as visuals from './backtestVisualApi'
import fixture from './backtest-performance.fixture.json'

// jsdom核交互与数据归属；ECharts布局、光标和标记另由真实浏览器验收。
vi.mock('./BacktestVisualChart', async original => ({ ...await original<typeof import('./BacktestVisualChart')>(), default: () => <div role="img" aria-label="测试曲线" /> }))
vi.mock('./backtestPerformanceApi', async original => ({ ...await original<typeof api>(), fetchBacktestPerformance: vi.fn(), fetchBacktestComparison: vi.fn() }))
vi.mock('./backtestVisualApi', () => ({ fetchVisuals: vi.fn(), fetchLedger: vi.fn() }))
const clients: QueryClient[] = []
beforeEach(() => {
  vi.mocked(api.fetchBacktestPerformance).mockResolvedValue(fixture.left as api.BacktestPerformance)
  vi.mocked(api.fetchBacktestComparison).mockResolvedValue(fixture.comparison as api.BacktestComparison)
  vi.mocked(visuals.fetchVisuals).mockResolvedValue({ points: [], trades_available: false } as unknown as visuals.Visuals)
  vi.mocked(visuals.fetchLedger).mockImplementation(async (entry, day, offset) => ({ schema: 'nbw-ledger-v1', run_id: entry.run_id,
    receipt_sha256: entry.receipt_sha256, report_sha256: entry.report_sha256, date: day, offset, total: 0,
    trades_available: true, positions_available: true, positions: [{ date: day!, symbol: 'SSE.ETF.510500', quantity: '100', floating_cny: '-123.45', realized_cny: '678.90' }], trades: [] }))
})
afterEach(() => { cleanup(); clients.splice(0).forEach(c => c.clear()); vi.resetAllMocks() })
function mount(onRefreshArchive?: () => void) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client)
  render(<QueryClientProvider client={client}><BacktestPerformance entry={fixture.left_entry} entries={[fixture.left_entry, fixture.right_entry]} onRefreshArchive={onRefreshArchive} /></QueryClientProvider>)
}

test('日期明细显示原持仓浮盈亏，无成交仍保留持仓入口', async () => {
  mount()
  expect(await screen.findByText('-123.45')).toBeVisible()
  expect(screen.queryByText(/以当日日末记录为准/)).toBeNull()
  fireEvent.click(screen.getByRole('tab', { name: '当日交易' }))
  expect(await screen.findByText('当日没有成交。持仓可在另一页签查看。')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '全部交易记录' }))
  expect(await screen.findByText('本报告没有成交。')).toBeVisible()
  expect(visuals.fetchLedger).toHaveBeenLastCalledWith(fixture.left_entry, null, 0, expect.any(AbortSignal))
})

test('选择标签使用已核本金，不将报告名称里的金额当作金融事实', () => {
  const misleading = { ...fixture.left_entry, configuration:{ ...fixture.left_entry.configuration, label:'CNY 1000000' } }
  expect(reportLabel(misleading,'120000',2)).toContain('120,000.00元')
  expect(reportLabel(misleading,undefined,2)).toContain('本金待读取')
  expect(reportLabel(misleading,'120000',2)).not.toContain('1,000,000')
  expect(reportLabel(misleading,'120000',2)).not.toBe(reportLabel(misleading,'120000',3))
})

test('刷新入口同时发现新归档，已固定原件的图表不重复排队', async () => {
  const refresh = vi.fn(); mount(refresh); await screen.findByText('-123.45')
  const before = vi.mocked(visuals.fetchVisuals).mock.calls.length
  fireEvent.click(screen.getByLabelText('重新读取绩效'))
  expect(refresh).toHaveBeenCalledOnce()
  await waitFor(() => expect(api.fetchBacktestPerformance).toHaveBeenCalledTimes(2))
  expect(visuals.fetchVisuals).toHaveBeenCalledTimes(before)
})

test('折叠日期表保留原精度净值与缺失观察', async () => {
  mount(); await screen.findByText('-123.45')
  expect(screen.queryByText('来源与计算口径')).toBeNull()
  fireEvent.click(screen.getByText('主报告 · 日期与净值原值'))
  const table = screen.getByRole('region',{name:'主报告日期净值表'})
  expect(table).toHaveTextContent('观察缺失')
  expect(table).toHaveTextContent(String(fixture.left.points.find(p=>p[1]!==null)![1]))
})

test('对比失败仍保留同一主报告的曲线和金额',async()=>{
  mount();await screen.findByText('-123.45')
  vi.mocked(api.fetchBacktestComparison).mockRejectedValueOnce(new Error('private comparison failure'))
  fireEvent.change(screen.getByLabelText('选择比较报告'),{target:{value:fixture.right_entry.run_id}})
  expect(await screen.findByRole('alert')).toHaveTextContent('当前保留上次结果')
  expect(screen.getByRole('img',{name:'测试曲线'})).toBeVisible()
  expect(screen.getByText('-123.45')).toBeVisible()
  expect(screen.queryByLabelText('日期明细所属报告')).toBeNull()
  expect(document.body).not.toHaveTextContent('private comparison failure')
})

test('比较保留本金差异提示并可切换明细报告，返回单份清除比较', async () => {
  mount(); await screen.findByText('-123.45')
  fireEvent.change(screen.getByLabelText('选择比较报告'), { target: { value: fixture.right_entry.run_id } })
  expect(await screen.findByText(/条件差异/)).toHaveTextContent('初始本金')
  fireEvent.change(screen.getByLabelText('日期明细所属报告'), { target: { value: 'right' } })
  await waitFor(() => expect(visuals.fetchLedger).toHaveBeenLastCalledWith(fixture.right_entry, expect.any(Number), 0, expect.any(AbortSignal)))
  fireEvent.change(screen.getByLabelText('选择比较报告'), { target: { value: '' } })
  await waitFor(() => expect(screen.queryByLabelText('日期明细所属报告')).toBeNull())
})

test('重读失败保留同一报告的成功值，成功空观察替换原曲线', async () => {
  mount(); await screen.findByText('-123.45')
  vi.mocked(api.fetchBacktestPerformance).mockRejectedValueOnce(new Error('读取失败'))
  fireEvent.click(screen.getByLabelText('重新读取绩效'))
  expect(await screen.findByRole('alert')).toHaveTextContent('当前保留上次结果')
  expect(screen.getByRole('img', { name: '测试曲线' })).toBeVisible()
  const empty = structuredClone(fixture.left) as api.BacktestPerformance
  empty.points = empty.points.map(([day]) => [day, null])
  empty.observations = { total: empty.points.length, available: 0, missing: empty.points.length, last_trading_date: null }
  empty.metrics = { ...empty.metrics, last_nav_cny: null, total_return_pct: null, observed_max_drawdown_pct: null, native_cumulative_fees_cny: null }
  vi.mocked(api.fetchBacktestPerformance).mockResolvedValueOnce(empty)
  fireEvent.click(screen.getByLabelText('重新读取绩效'))
  expect(await screen.findByText('暂无有效资金记录，绩效与曲线未知。')).toBeVisible()
  expect(screen.queryByRole('img', { name: '测试曲线' })).toBeNull()
})
