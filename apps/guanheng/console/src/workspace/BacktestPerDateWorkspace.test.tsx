import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import BacktestWorkspace from './BacktestWorkspace'
import * as api from './backtestApi'
import * as performanceApi from './backtestPerformanceApi'
import fixture from './backtest-per-date.fixture.json'

vi.mock('./backtestApi', () => ({ fetchBacktestArchive: vi.fn(), fetchArchiveConfiguration: vi.fn(), fetchBacktestRecords: vi.fn(), fetchBacktestDay: vi.fn() }))
vi.mock('./backtestPerformanceApi', async importOriginal => ({ ...await importOriginal<typeof performanceApi>(), fetchBacktestPerformance: vi.fn() }))
afterEach(() => { cleanup(); vi.resetAllMocks() })

it('逐日原报告的回测资金、持仓和曲线以中文业务内容展示', async () => {
  // 组件验证只注入传输测试上下文；正式归档准入另由服务端验证。
  const day = fixture.days[0]
  const entry = fixture.entry as api.ArchiveEntry
  vi.mocked(api.fetchBacktestArchive).mockResolvedValue({ schema: 'nbw-archive-index-v1', runs: [entry], invalid_receipts: 0, unarchived_runs: 0, scope: entry.scope })
  vi.mocked(api.fetchArchiveConfiguration).mockResolvedValue({ schema: 'nbw-archive-configuration-v1', run_id: entry.run_id, request_id: entry.request_id,
    receipt_sha256: entry.receipt_sha256, report_sha256: entry.report_sha256, installation_sha256: 'c'.repeat(64), configuration: entry.configuration,
    session_configuration: {}, policy: {}, fee_reserve_cny: '0', fee_source: null, scope: entry.scope })
  vi.mocked(api.fetchBacktestRecords).mockResolvedValue({ request_id: entry.request_id, report_sha256: entry.report_sha256,
    total: 400, offset: 0, records: [{ trading_date: day.record.trading_date, minute: 1500, status: day.record.status, reason: day.record.reason }], scope: entry.scope })
  vi.mocked(api.fetchBacktestDay).mockResolvedValue(day as api.BacktestDay)
  vi.mocked(performanceApi.fetchBacktestPerformance).mockResolvedValue(fixture.performance as performanceApi.BacktestPerformance)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  const view = render(<QueryClientProvider client={client}><MemoryRouter><BacktestWorkspace /></MemoryRouter></QueryClientProvider>)
  const date = String(day.record.trading_date)
  const label = `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`
  await fireEvent.click(await screen.findByRole('button', { name: `查看历史 ${label}` }))
  expect(await screen.findByRole('heading', { name: `${label} · 当日结果` })).toBeVisible()
  expect(await screen.findByText(/共 400 条日末记录/)).toBeVisible()
  expect(screen.getByText('回测现金（元）')).toBeVisible()
  expect(screen.getByText('当日没有持仓。')).toBeVisible()
  expect(screen.getByRole('img', { name: '已观察日末模型净值曲线' })).toBeVisible()
  expect(view.container.textContent).not.toMatch(/manifest_sha256|market_window|[a-f0-9]{64}|RT\/broker|per-date-front/)
})
