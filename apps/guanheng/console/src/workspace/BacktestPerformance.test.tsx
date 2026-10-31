import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import BacktestPerformance from './BacktestPerformance'
import * as api from './backtestPerformanceApi'
import fixture from './backtest-performance.fixture.json'

vi.mock('./backtestPerformanceApi', async original => ({ ...await original<typeof api>(), fetchBacktestPerformance: vi.fn(), fetchBacktestComparison: vi.fn() }))
const clients: QueryClient[] = []
beforeEach(() => {
  vi.mocked(api.fetchBacktestPerformance).mockResolvedValue(fixture.left as api.BacktestPerformance)
  vi.mocked(api.fetchBacktestComparison).mockResolvedValue(fixture.comparison as api.BacktestComparison)
})
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.resetAllMocks() })
function mount() {
  const client = new QueryClient({defaultOptions:{queries:{retry:false}}}); clients.push(client)
  render(<QueryClientProvider client={client}><BacktestPerformance entry={fixture.left_entry} entries={[fixture.left_entry,fixture.right_entry]} /></QueryClientProvider>)
}
test('实际原生投影显示模型口径、未知日期、比较条件，切回单份', async () => {
  mount()
  expect(await screen.findByRole('article', {name:'当前报告'})).toContainElement(screen.getByText('模型收益率'))
  expect(screen.getByText('已观察日末最大回撤')).toBeVisible()
  fireEvent.click(screen.getByText('查看日期与净值'))
  expect(screen.getByRole('region', {name:'当前报告日期净值表'})).toHaveTextContent('观察缺失')
  fireEvent.change(screen.getByRole('combobox'), {target:{value:fixture.right_entry.run_id}})
  expect(await screen.findByRole('article', {name:'比较报告'})).toBeVisible()
  expect(screen.getByText(/比较条件存在差异/)).toHaveTextContent('初始本金')
  expect(screen.getAllByRole('img', {name:'已观察日末模型净值曲线'})).toHaveLength(2)
  fireEvent.change(screen.getByRole('combobox'), {target:{value:''}})
  await waitFor(() => expect(screen.queryByRole('article', {name:'比较报告'})).toBeNull())
})
test('比较重读保留旧整对和原时间，错误后手动恢复', async () => {
  mount(); await screen.findByRole('article', {name:'当前报告'})
  fireEvent.change(screen.getByRole('combobox'), {target:{value:fixture.right_entry.run_id}})
  await screen.findByRole('article', {name:'比较报告'})
  let reject!: (error: Error) => void
  vi.mocked(api.fetchBacktestComparison).mockImplementationOnce(() => new Promise((_resolve, fail) => {reject=fail}))
  fireEvent.click(screen.getByRole('button', {name:'重新读取绩效'}))
  await waitFor(() => expect(screen.getByRole('article', {name:'比较报告'})).toBeVisible())
  reject(new Error('归档原件不可用'))
  expect(await screen.findByRole('alert')).toHaveTextContent('当前保留上次结果')
  fireEvent.click(screen.getByRole('button', {name:'重新读取绩效'}))
  expect(await screen.findByRole('article', {name:'比较报告'})).toBeVisible()
})
test('成功空指标替换上次指标；全预热明确不可用', async () => {
  mount(); await screen.findByRole('article', {name:'当前报告'})
  const empty = structuredClone(fixture.left)
  empty.points = empty.points.map(([day]) => [day, null]) as typeof empty.points
  empty.observations = {...empty.observations,available:0,missing:5,last_trading_date:null} as any
  empty.metrics = {...empty.metrics,last_nav_cny:null,total_return_pct:null,observed_max_drawdown_pct:null,native_cumulative_fees_cny:null} as any
  vi.mocked(api.fetchBacktestPerformance).mockResolvedValueOnce(empty as api.BacktestPerformance)
  fireEvent.click(screen.getByRole('button', {name:'重新读取绩效'}))
  expect(await screen.findByText('资金数据暂不可用，暂无绩效指标。')).toBeVisible()
  const card=screen.getByRole('article',{name:'当前报告'})
  expect(within(card).getAllByText('不可用')).toHaveLength(4)
  expect(within(card).queryByRole('img')).toBeNull()
})
