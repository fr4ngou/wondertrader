import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { StrategyCapitalHistory } from '../types'
import { StrategyPerformancePanel } from './StrategyPerformancePanel'

vi.mock('./StrategyHistoryChart', () => ({ StrategyHistoryChart: ({ history }: { history: StrategyCapitalHistory }) => <div data-testid="scope-curve">{history.strategy_id}:{history.genesis_epoch_id}:{history.sampling}</div> }))
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function history(id: string, epoch: string, equity: number, sampling: 'daily' | 'snapshots' = 'daily'): StrategyCapitalHistory {
  return { schema_version: 'strategy-capital-history-v1', strategy_id: id, strategy_lineage_id: `${id}:lineage`, genesis_epoch_id: epoch, source_kind: 'strategy_capital_snapshots', calculation_method: 'return-on-contributed-principal-v1', sampling, window_start: '2026-10-04T00:00:00+08:00', window_end: '2026-10-05T00:00:00+08:00', truncated: false, read_only: true, generated_at: '2026-10-04T00:00:00Z', points: [{ captured_at: '2026-10-04T00:00:00Z', valuation_at: '2026-10-04T00:00:00Z', strategy_version: '1', net_asset_value: equity, contributed_principal: 100, capital_contributions_total: 0, investment_pnl: equity - 100, status: 'ready', return_on_principal: equity / 100 - 1, drawdown: 0 }] }
}

test('daily default and snapshot switch keep late sampling responses isolated', async () => {
  let release!: (response: Response) => void
  const late = new Promise<Response>(resolve => { release = resolve })
  const fetchMock = vi.fn((input: RequestInfo | URL) => String(input).includes('sampling=daily')
    ? late : Promise.resolve(Response.json(history('strategy-a', 'epoch-a', 123, 'snapshots'))))
  vi.stubGlobal('fetch', fetchMock)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  render(<QueryClientProvider client={client}><StrategyPerformancePanel strategyId="strategy-a" lineage="strategy-a:lineage" epoch="epoch-a" /></QueryClientProvider>)
  await waitFor(() => expect(fetchMock).toHaveBeenCalled())
  expect(String(fetchMock.mock.calls[0][0])).toContain('sampling=daily')
  expect(String(fetchMock.mock.calls[0][0])).toContain('days=30')
  fireEvent.change(screen.getByLabelText('历史估值采样'), { target: { value: 'snapshots' } })
  expect(await screen.findByTestId('scope-curve')).toHaveTextContent('snapshots')
  await act(async () => release(Response.json(history('strategy-a', 'epoch-a', 888))))
  expect(screen.getByTestId('scope-curve')).toHaveTextContent('snapshots')
  expect(screen.getByText('123.00')).toBeInTheDocument()
  expect(screen.queryByText('888.00')).not.toBeInTheDocument()
  expect(screen.getByText(/当前仅有 1 个观察点/)).toBeInTheDocument()
  expect(screen.getByText(/请求范围：/)).toBeInTheDocument()
})

test.each(['strategy', 'epoch'])('ignores late history after a %s identity change', async change => {
  let release!: (response: Response) => void
  const late = new Promise<Response>(resolve => { release = resolve })
  const nextId = change === 'strategy' ? 'strategy-b' : 'strategy-a'
  const nextEpoch = change === 'epoch' ? 'epoch-b' : 'epoch-a'
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => String(input).includes('strategy-a/capital-history') && String(input).includes('epoch-a') ? late : Promise.resolve(Response.json(history(nextId, nextEpoch, 123)))))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  const tree = (id: string, epoch: string) => <QueryClientProvider client={client}><StrategyPerformancePanel strategyId={id} lineage={`${id}:lineage`} epoch={epoch} /></QueryClientProvider>
  const { rerender } = render(tree('strategy-a', 'epoch-a'))
  await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalled())
  rerender(tree(nextId, nextEpoch))
  expect(await screen.findByTestId('scope-curve')).toHaveTextContent(`${nextId}:${nextEpoch}`)
  await act(async () => release(Response.json(history('strategy-a', 'epoch-a', 888))))
  expect(screen.getByTestId('scope-curve')).toHaveTextContent(`${nextId}:${nextEpoch}`)
  expect(screen.queryByText('888.00')).not.toBeInTheDocument()
  expect(screen.getByText('123.00')).toBeInTheDocument()
})

test('does not read history without capital identity and distinguishes confirmed empty from unavailable', async () => {
  const fetchMock = vi.fn().mockResolvedValue(Response.json({ ...history('strategy-a', 'epoch-a', 100), points: [] }))
  vi.stubGlobal('fetch', fetchMock)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const { rerender } = render(<QueryClientProvider client={client}><StrategyPerformancePanel strategyId="strategy-a" /></QueryClientProvider>)
  expect(screen.getByText('策略资本身份不可用')).toBeInTheDocument()
  expect(fetchMock).not.toHaveBeenCalled()
  rerender(<QueryClientProvider client={client}><StrategyPerformancePanel strategyId="strategy-a" lineage="strategy-a:lineage" epoch="epoch-a" /></QueryClientProvider>)
  expect(await screen.findByText('暂无历史估值')).toBeInTheDocument()
  fetchMock.mockResolvedValue(Response.json({ error: 'unavailable' }, { status: 503 }))
  await act(async () => { await client.invalidateQueries({ queryKey: ['strategy-capital-history'] }) })
  expect(await screen.findByText('策略历史估值不可用', {}, { timeout: 4000 })).toBeInTheDocument()
  expect(screen.queryByText('暂无历史估值')).not.toBeInTheDocument()
})
