import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import BacktestWorkspace from './BacktestWorkspace'
import * as api from './backtestApi'
import * as performanceApi from './backtestPerformanceApi'
import * as visualApi from './backtestVisualApi'
import fixture from './backtest-per-date.fixture.json'

vi.mock('./BacktestVisualChart', async original => ({ ...await original<typeof import('./BacktestVisualChart')>(), default: () => <div role="img" aria-label="测试曲线" /> }))
vi.mock('./backtestApi', async original => ({ ...await original<typeof api>(), fetchBacktestArchive:vi.fn() }))
vi.mock('./backtestPerformanceApi', async original => ({ ...await original<typeof performanceApi>(), fetchBacktestPerformance:vi.fn() }))
vi.mock('./backtestVisualApi', () => ({ fetchVisuals:vi.fn(), fetchLedger:vi.fn() }))
const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(c => c.clear()); vi.resetAllMocks(); vi.unstubAllGlobals() })
test('400期逐日归档通过新日期选择器展示空仓，内部协议留在API', async () => {
  const entry = fixture.entry as api.ArchiveEntry
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json({schema:'guanheng.strategy-catalog.v1',read_only:true,scope:'registered-definitions',strategies:[{strategy_id:fixture.performance.strategy.id,strategy_version:fixture.performance.strategy.version,display_name:'测试策略',description:'测试简介',historical_versions:[]}]})))
  vi.mocked(api.fetchBacktestArchive).mockResolvedValue({ schema:'nbw-archive-index-v1', runs:[entry], invalid_receipts:0, unarchived_runs:0, scope:entry.scope })
  vi.mocked(performanceApi.fetchBacktestPerformance).mockResolvedValue(fixture.performance as performanceApi.BacktestPerformance)
  vi.mocked(visualApi.fetchVisuals).mockResolvedValue({ points:[], trades_available:true } as unknown as visualApi.Visuals)
  vi.mocked(visualApi.fetchLedger).mockImplementation(async (_entry, day, offset) => ({ schema:'nbw-ledger-v1',run_id:entry.run_id,receipt_sha256:entry.receipt_sha256,
    report_sha256:entry.report_sha256,date:day,offset,total:0,trades:[],positions:[],positions_available:true,trades_available:true }))
  const client = new QueryClient({ defaultOptions:{ queries:{retry:false} } }); clients.push(client)
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/backtests?run='+entry.run_id]}><BacktestWorkspace /></MemoryRouter></QueryClientProvider>)
  expect(await screen.findByText('当日日末空仓。')).toBeVisible()
  fireEvent.change(screen.getByLabelText('查看交易日'), { target:{value:String(fixture.days[0].record.trading_date)} })
  expect(await screen.findByText('当日日末空仓。')).toBeVisible()
  expect(screen.getByRole('img', { name:'测试曲线' })).toBeVisible()
  expect(document.body).not.toHaveTextContent(/manifest_sha256|market_window|[a-f0-9]{64}|RT\/broker|per-date-front/)
})
