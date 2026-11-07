import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import BacktestPerformance from './BacktestPerformance'
import { reportLabel } from './backtestPresentation'
import * as api from './backtestPerformanceApi'
import * as visuals from './backtestVisualApi'
import { fetchMarketChart } from '../api'
import { BACKTEST_BENCHMARKS, readBacktestBenchmark } from './backtestBenchmarks'
import fixture from './backtest-performance.fixture.json'

// jsdom核交互与数据归属；ECharts布局、光标和标记另由真实浏览器验收。
vi.mock('./BacktestVisualChart', async original => ({ ...await original<typeof import('./BacktestVisualChart')>(), default: () => <div role="img" aria-label="测试曲线" /> }))
vi.mock('./backtestPerformanceApi', async original => ({ ...await original<typeof api>(), fetchBacktestPerformance: vi.fn(), fetchBacktestComparison: vi.fn() }))
vi.mock('./backtestVisualApi', () => ({ fetchVisuals: vi.fn(), fetchLedger: vi.fn(), fetchDaySummaries: vi.fn() }))
vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(), fetchMarketChart: vi.fn() }))
const clients: QueryClient[] = []
beforeEach(() => {
  vi.mocked(api.fetchBacktestPerformance).mockResolvedValue(fixture.left as api.BacktestPerformance)
  vi.mocked(api.fetchBacktestComparison).mockResolvedValue(fixture.comparison as api.BacktestComparison)
  vi.mocked(visuals.fetchVisuals).mockResolvedValue({ points: [], trades_available: false } as unknown as visuals.Visuals)
  vi.mocked(fetchMarketChart).mockImplementation(async symbol => ({ schema_version: '1.0', symbol,
    period: '1d', candles: [], data_available: false, source_kind: 'wondertrader' }))
  vi.mocked(visuals.fetchDaySummaries).mockImplementation(async entry => ({ schema: 'nbw-day-summaries-v1', run_id: entry.run_id,
    receipt_sha256: entry.receipt_sha256, report_sha256: entry.report_sha256,
    points: (entry.run_id === fixture.left_entry.run_id ? fixture.left.points : fixture.right.points).map(([day]) => [Number(day), [], [], [], 0]) }))
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

test('指数多选按需只读；已知空仓和未知估值在同一日期控件下区分', async () => {
  const earlier = Number(fixture.left.points[0][0]), latest = Number(fixture.left.points.at(-1)![0])
  vi.mocked(visuals.fetchVisuals).mockResolvedValue({ points: [], trades_available: false,
    position_points: [[earlier, null, null, null], [latest, 0, '0', '150000']] } as unknown as visuals.Visuals)
  mount()
  expect(await screen.findByText('150,000.00 元')).toBeVisible()
  expect(screen.getByText('日末仓位').nextElementSibling).toHaveTextContent('0%')
  expect(screen.getByRole('checkbox', { name: '上证指数' })).toBeChecked()
  expect(screen.getByRole('checkbox', { name: '沪深300' })).not.toBeChecked()
  fireEvent.click(screen.getByRole('checkbox', { name: '沪深300' }))
  await waitFor(() => expect(vi.mocked(fetchMarketChart).mock.calls.map(call => call[0])).toEqual(['000001.SH', '000300.SH']))
  fireEvent.click(screen.getByRole('button', { name: '净值' }))
  expect(screen.getByText('指数基准显示于收益率图。')).toBeVisible()
  expect(screen.getByRole('checkbox', { name: '沪深300' })).toBeChecked()
  fireEvent.change(screen.getByLabelText('查看交易日'), { target: { value: String(earlier) } })
  expect(screen.getByText('持仓市值').nextElementSibling).toHaveTextContent('未知')
})

test('指数按上海交易日取前一收盘基点，缺日和未闭合当日留空', async () => {
  const candle = (occurred_at: string, close: number) => ({ occurred_at, close, open: close, high: close, low: close })
  vi.mocked(fetchMarketChart).mockResolvedValueOnce({
    schema_version: '1.8', symbol: '000001.SH', period: '1d', source_kind: 'wondertrader', data_available: true,
    candles: [candle('2026-10-27T16:00:00Z', 100), candle('2026-10-28T16:00:00Z', 112), candle('2026-11-01T16:00:00Z', 121)],
    native_source: { current_day: { date: 20261102, closed: false } } as import('../types').MarketChartNativeSource,
  })
  const result = await readBacktestBenchmark(BACKTEST_BENCHMARKS[0], 20261029, 20261102)
  expect(vi.mocked(fetchMarketChart)).toHaveBeenCalledWith('000001.SH', '1d', undefined, undefined, 2000, '2026-11-02T23:59:59+08:00')
  expect(result.baseDay).toBe(20261028)
  expect(result.values[20261029]).toBeCloseTo(12)
  expect(result.values[20261030]).toBeUndefined()
  expect(result.values[20261102]).toBeUndefined()
})

test('切日保持详情页签并复用同报告已读日期，摘要只获取一次', async () => {
  mount(); await screen.findByText('-123.45')
  const last = fixture.left.points.at(-1)![0]; const earlier = fixture.left.points[0][0]
  fireEvent.click(screen.getByRole('tab', { name: '当日交易' }))
  fireEvent.change(screen.getByLabelText('查看交易日'), { target: { value: String(earlier) } })
  await waitFor(() => expect(visuals.fetchLedger).toHaveBeenLastCalledWith(fixture.left_entry, earlier, 0, expect.any(AbortSignal)))
  await screen.findByText('当日没有成交。持仓可在另一页签查看。')
  const requests = vi.mocked(visuals.fetchLedger).mock.calls.length
  fireEvent.change(screen.getByLabelText('查看交易日'), { target: { value: String(last) } })
  await screen.findByText('当日没有成交。持仓可在另一页签查看。')
  expect(visuals.fetchLedger).toHaveBeenCalledTimes(requests)
  expect(visuals.fetchDaySummaries).toHaveBeenCalledOnce()
})

test('摘要读取失败仍能独立点日查看，私有异常不进入页面', async () => {
  vi.mocked(visuals.fetchDaySummaries).mockRejectedValueOnce(new Error('private summary error'))
  mount(); await screen.findByText('-123.45')
  expect(screen.getByText(/悬停摘要暂不可用/)).toBeVisible()
  expect(document.body).not.toHaveTextContent('private summary error')
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
