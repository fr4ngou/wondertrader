import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import OriginalNativeModel from './OriginalNativeModel'
import { fetchArchiveConfiguration, type ArchiveConfiguration } from './backtestApi'
import fixture from './backtest-performance.fixture.json'

vi.mock('./backtestApi', async original => ({ ...await original<typeof import('./backtestApi')>(), fetchArchiveConfiguration: vi.fn() }))
const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(c => c.clear()); vi.resetAllMocks() })
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client)
  render(<QueryClientProvider client={client}><OriginalNativeModel entry={fixture.left_entry} label="主报告" /></QueryClientProvider>)
}
test('原生负现金天数显式呈现，成交时刻与原组合模型分开解释', async () => {
  // 明确合成模型摘要，只验证现金缺口不会被曲线隐藏，不模拟或重算WT净值。
  vi.mocked(fetchArchiveConfiguration).mockResolvedValue({ original_native: {
    signal_algorithm_id: 'resonance-original-351f9d5-stable', reference_report_sha256: 'a'.repeat(64), source_snapshot_sha256: 'b'.repeat(64),
    execution_model: 'signal-close-to-next-WT-native-tick', historical_model: {},
    evaluation_window: { warmup_date: '2024-01-02', from: '2024-01-03', to: '2024-01-09' },
    cash_deficit_count: 2, cash_deficit_dates: [20240104, 20240105], source_qualified: false, execution_qualified: false, point_in_time_qualified: false,
  } } as ArchiveConfiguration)
  mount()
  expect(await screen.findByRole('alert')).toHaveTextContent('2 个负现金日，首日 2024-01-04')
  expect(screen.getByText(/通常为下一交易日开盘/)).toBeVisible()
  expect(screen.getByText(/冻结 SELL 的余量保留至可卖/)).toBeVisible()
  expect(screen.getByText(/原组合对照使用次日收盘/)).toBeVisible()
})
test('首次读取失败时保留未知状态和手动重读，不报零现金缺口', async () => {
  vi.mocked(fetchArchiveConfiguration).mockRejectedValue(new Error('unavailable'))
  mount()
  expect(await screen.findByRole('alert')).toHaveTextContent('现金缺口状态未知')
  expect(screen.queryByText(/负现金日为 0/)).toBeNull()
  expect(screen.getByRole('button', { name: '重读模型说明' })).toBeVisible()
})
