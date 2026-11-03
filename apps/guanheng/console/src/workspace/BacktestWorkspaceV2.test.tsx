import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import BacktestDateDetail from './BacktestDateDetail'
import { fetchLedger, type Ledger } from './backtestVisualApi'
import fixture from './backtest-performance.fixture.json'

// 已封存报告继续使用只读明细；缺少可适配原件时保持未知，不从目标推造成交。
vi.mock('./backtestVisualApi', () => ({ fetchLedger: vi.fn() }))
const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(c => c.clear()); vi.resetAllMocks() })
function mount(value: Partial<Ledger>) {
  vi.mocked(fetchLedger).mockResolvedValue({ schema:'nbw-ledger-v1', run_id:fixture.left_entry.run_id, receipt_sha256:fixture.left_entry.receipt_sha256,
    report_sha256:fixture.left_entry.report_sha256, date:20240109, positions_available:false, positions:[], trades_available:false, total:0, offset:0, trades:[], ...value })
  const client = new QueryClient({ defaultOptions: { queries: { retry:false } } }); clients.push(client)
  render(<QueryClientProvider client={client}><BacktestDateDetail entry={fixture.left_entry} day={20240109} dates={[20240109]} onDay={() => {}} /></QueryClientProvider>)
}
test('旧报告缺失持仓原件与成交原件分别显示未知', async () => {
  mount({}); expect(await screen.findByText('当日持仓或盈亏数据未知。')).toBeVisible()
  expect(screen.queryByText('当日日末空仓。')).toBeNull()
  fireEvent.click(screen.getByRole('tab', { name:'当日交易' }))
  expect(await screen.findByText('该报告的原生成交明细暂不可用。')).toBeVisible()
})
test('完整原件的真空仓与零成交按各自语义显示', async () => {
  mount({ positions_available:true, trades_available:true })
  expect(await screen.findByText('当日日末空仓。')).toBeVisible()
  fireEvent.click(screen.getByRole('tab', { name:'当日交易' }))
  expect(await screen.findByText('当日没有成交。持仓可在另一页签查看。')).toBeVisible()
})
test('旧报告明细读取失败可重读，页面不回显内部错误', async () => {
  mount({ positions_available:true })
  await screen.findByText('当日日末空仓。')
  vi.mocked(fetchLedger).mockRejectedValueOnce(new Error('unknown-private-schema'))
  fireEvent.click(screen.getByRole('button', { name:'全部交易记录' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('日期明细读取失败')
  expect(document.body).not.toHaveTextContent('unknown-private-schema')
  fireEvent.click(screen.getByRole('button', { name:'重读明细' }))
  expect(await screen.findByText('该报告的原生成交明细暂不可用。')).toBeVisible()
})
