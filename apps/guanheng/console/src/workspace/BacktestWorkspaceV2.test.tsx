import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import BacktestWorkspace from './BacktestWorkspace'
import { fetchReadJson } from '../api'
import source from './backtest-v2-days.fixture.json'

vi.mock('../api', () => ({ fetchReadJson: vi.fn() }))
const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(c => c.clear()); vi.resetAllMocks() })
const owner = 'a'.repeat(32); const request = '1'.repeat(32)
type Wire = Record<string, any>
function mount(days: Wire[]) {
  vi.mocked(fetchReadJson).mockImplementation(async (url) => {
    const path = String(url)
    if (path === '/v1/ui/backtest/archive') return { schema: 'nbw-archive-index-v1', runs: [], invalid_receipts: 0, unarchived_runs: 0, scope: 'synthetic-only' }
    if (path.includes('/workspace')) return { schema: 'nbw-workspace-v1', owner_id: owner, available: true, reason: null,
      configuration: { label: '合成原生回测样本', start: 202403250930, end: 202403281500, session_sha256: 'c'.repeat(64), max_seconds: 20 },
      runs: [{ owner_id: owner, request_id: request, run_id: 'b'.repeat(32), status: 'completed', reason: '回放与结果收口完成', elapsed_ms: 500,
        pid: 123, exit_code: 0, forced: false, pid_reaped: true, pipes_joined: true, record_count: days.length, scope: 'synthetic-only' }], scope: 'synthetic-only' }
    if (path.includes('/records?')) return { request_id: request, report_sha256: days[0].report_sha256, total: days.length, offset: 0,
      records: days.map(d => ({ trading_date: d.record.trading_date, minute: d.record.minute, status: d.record.status, reason: d.record.reason })), scope: 'synthetic-only' }
    const index = Number(path.match(/records\/(\d+)/)?.[1])
    return days[index]
  })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } }); clients.push(client)
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/strategies?tab=backtests']}><BacktestWorkspace /></MemoryRouter></QueryClientProvider>)
}

it('已封存旧报告仅呈现持仓和调仓结果，算法与诊断字段不进入页面', async () => {
  mount(structuredClone(source.roles))
  fireEvent.click(await screen.findByRole('button', {name:'查看 2024-03-25'}))
  expect(await screen.findByRole('heading', {name:'2024-03-25 · 当日结果'})).toBeVisible()
  expect(screen.getByRole('heading', {name:'回测持仓'})).toBeVisible()
  expect(screen.getByRole('heading', {name:'本次调仓'})).toBeVisible()
  expect(document.body).not.toHaveTextContent(/SHA256|historical_model|pipeline|策略：resonance|来源资格/)
  expect(document.querySelector('pre')).toBeNull()
})

it('旧报告预热仍明确资金缺失和无调仓', async () => {
  const first: Wire = structuredClone(source.roles[0])
  first.evaluation_summary = null
  first.record = {...first.record,status:'warming_up',capture:null,outcome:null,submit_vector:[],readback:[]}
  mount([first]);fireEvent.click(await screen.findByRole('button', {name:'查看 2024-03-25'}))
  expect(await screen.findByText('当日资金数据暂不可用。')).toBeVisible()
  expect(screen.getByText('当日没有新增调仓目标。')).toBeVisible()
})

it('未知报告格式失败后可手动恢复，页面不回显原始协议', async () => {
  const days: Wire[] = structuredClone(source.roles);days[0].report_schema='unknown-private-schema'
  mount(days);fireEvent.click(await screen.findByRole('button', {name:'查看 2024-03-25'}))
  expect(await screen.findByRole('button', {name:'重读当日结果'})).toBeVisible()
  expect(document.body).not.toHaveTextContent('unknown-private-schema')
  days[0].report_schema='nsb-v2-report-v1';fireEvent.click(screen.getByRole('button', {name:'重读当日结果'}))
  expect(await screen.findByRole('heading', {name:'2024-03-25 · 当日结果'})).toBeVisible()
})
