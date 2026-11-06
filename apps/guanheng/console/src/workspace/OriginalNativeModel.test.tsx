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
test('旧原生负现金天数显式呈现，成交时刻与信号算法分开解释', async () => {
  // 明确合成模型摘要，只验证现金缺口不会被曲线隐藏，不模拟或重算WT净值。
  vi.mocked(fetchArchiveConfiguration).mockResolvedValue({ ...fixture.left_entry, schema:'nbw-archive-configuration-v1',
    installation_sha256:'e'.repeat(64), session_configuration:{}, policy:{}, fee_reserve_cny:'0', fee_source:'synthetic', original_native: {
    signal_algorithm_id: 'resonance-original-351f9d5-stable', reference_report_sha256: 'a'.repeat(64), source_snapshot_sha256: 'b'.repeat(64),
    execution_model: 'signal-close-to-next-WT-native-tick', historical_model: {},
    evaluation_window: { warmup_date: '2024-01-02', from: '2024-01-03', to: '2024-01-09' },
    cash_deficit_count: 2, cash_deficit_dates: [20240104, 20240105], source_qualified: false, execution_qualified: false, point_in_time_qualified: false,
  } } as ArchiveConfiguration)
  mount()
  expect(await screen.findByRole('alert')).toHaveTextContent('2 个负现金日，首日 2024-01-04')
  expect(screen.getByText(/通常为下一交易日开盘/)).toBeVisible()
  expect(screen.getByText(/冻结 SELL 的余量保留至可卖/)).toBeVisible()
  expect(screen.getByText(/原始信号算法与执行模型/)).toBeVisible()
})

test('现金约束版展示原生限价和实际现金约束，不沿用旧跳空负现金说明', async () => {
  vi.mocked(fetchArchiveConfiguration).mockResolvedValue({ ...fixture.left_entry, schema:'nbw-archive-configuration-v1',
    installation_sha256:'e'.repeat(64), session_configuration:{}, policy:{}, fee_reserve_cny:'0', fee_source:'synthetic', original_native: {
    signal_algorithm_id:'resonance-original-351f9d5-stable',reference_report_sha256:'a'.repeat(64),source_snapshot_sha256:'b'.repeat(64),
    execution_model:'D-close-intent; WT-native-limit-next-tick; unfilled-intent-retained',historical_model:{},
    evaluation_window:{warmup_date:'2024-01-02',from:'2024-01-03',to:'2024-01-09'},cash_deficit_count:0,cash_deficit_dates:[],
    source_qualified:false,execution_qualified:false,point_in_time_qualified:false,
  }})
  mount()
  expect(await screen.findByText(/现金约束版：保留原版/)).toHaveTextContent('未成交卖出款保持未到账')
  expect(screen.getByText(/本报告核验的负现金日为 0/)).toBeVisible()
  expect(screen.queryByText(/旧版按 D 日净值和价格/)).toBeNull()
})
test('首次读取失败时保留未知状态和手动重读，不报零现金缺口', async () => {
  vi.mocked(fetchArchiveConfiguration).mockRejectedValue(new Error('unavailable'))
  mount()
  expect(await screen.findByRole('alert')).toHaveTextContent('现金缺口状态未知')
  expect(screen.queryByText(/负现金日为 0/)).toBeNull()
  expect(screen.getByRole('button', { name: '重读模型说明' })).toBeVisible()
})
