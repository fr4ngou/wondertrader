import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import BacktestWorkspace from './BacktestWorkspace'
import { fetchBacktestArchiveSummaries } from './backtestApi'
import { fetchStrategyCatalog } from './strategyCatalogApi'
import fixture from './backtest-performance.fixture.json'

vi.mock('./backtestApi', async original => ({ ...await original<typeof import('./backtestApi')>(), fetchBacktestArchiveSummaries: vi.fn() }))
vi.mock('./strategyCatalogApi', () => ({ fetchStrategyCatalog: vi.fn() }))
vi.mock('./BacktestPerformance', async () => { throw new Error('private-chunk-failure') })
const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.restoreAllMocks() })

test('分析分块失败保留工作区和返回入口，提示真实重新加载并隔离旧选择', async () => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  vi.mocked(fetchStrategyCatalog).mockResolvedValue([{strategy_id:'resonance-regime-v1',strategy_version:'1.1.2',display_name:'共振策略',description:'测试',historical_versions:[]}])
  const summary = {strategy:{id:'resonance-regime-v1',version:'1.1.2'},initial_capital_cny:'1000000'}
  vi.mocked(fetchBacktestArchiveSummaries).mockResolvedValue({schema:'nbw-archive-summary-index-v1',runs:[{...fixture.left_entry,summary}],invalid_receipts:0,unarchived_runs:0,scope:'isolated-raw-BT'})
  const client = new QueryClient({defaultOptions:{queries:{retry:false}}});clients.push(client)
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/backtests']}><BacktestWorkspace /></MemoryRouter></QueryClientProvider>)
  await screen.findByRole('region',{name:'策略回测列表'})
  fireEvent.click(screen.getByRole('button',{name:'打开回测分析'}))
  expect(await screen.findByRole('alert')).toHaveTextContent('回测分析页面加载失败')
  expect(screen.getByRole('button',{name:'重新加载报告'})).toBeEnabled()
  expect(screen.getByLabelText('选择策略')).toBeVisible()
  expect(document.body).not.toHaveTextContent('private-chunk-failure')
  fireEvent.click(screen.getByRole('button',{name:'← 返回回测列表'}))
  expect(await screen.findByRole('region',{name:'策略回测列表'})).toBeVisible()
  expect(screen.queryByRole('alert')).toBeNull()
})
