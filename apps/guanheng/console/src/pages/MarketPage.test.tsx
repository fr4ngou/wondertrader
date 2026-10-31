import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { fetchDefaultWatchlist, fetchMarketChart, fetchMarketQuote, fetchPublicObservation, fetchMarketSymbolSuggestions, updateDefaultWatchlist } from '../api'
import type { ConsoleBootstrap, MarketChartBundle, MarketSymbolSuggestionPage, Watchlist } from '../types'
import { MarketPage } from './MarketPage'

vi.mock('../api', () => ({
  fetchDefaultWatchlist: vi.fn(async () => ({ items: [], name: '我的观察', version: 1 })),
  fetchMarketDataSubscriptions: vi.fn(async () => ({
    target_converged: true, lifecycle: 'converged', target_universe: { members: [] },
  })),
  fetchMarketChart: vi.fn(),
  fetchMarketQuote: vi.fn(async () => ({ quote: null })),
  fetchPublicObservation: vi.fn(),
  fetchMarketSymbolSuggestions: vi.fn(),
  updateDefaultWatchlist: vi.fn(),
}))

vi.mock('../components/MarketCandlestickChart', () => ({
  MarketCandlestickChart: ({ bundle }: { bundle: MarketChartBundle }) => (
    bundle.data_available && bundle.candles.length
      ? <div role="img" aria-label={`${bundle.candles.length} 根权威 K 线`} />
      : <div role="status" aria-label="权威行情空结果">暂无权威 K 线</div>
  ),
}))

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.clearAllMocks()
  vi.mocked(fetchDefaultWatchlist).mockResolvedValue({
    schema_version: '1.0', watchlist_id: '00000000-0000-0000-0000-000000000001',
    name: '我的观察', version: 1, items: [],
    updated_at: '2026-09-26T00:00:00Z', affects_strategy: false,
  })
  vi.mocked(fetchMarketQuote).mockResolvedValue({
    schema_version: '1.0', symbol: '159780.SZ', quote: null, data_available: false,
    missing_reason: 'not collected',
  })
  vi.mocked(fetchPublicObservation).mockResolvedValue({
    symbol: '159780.SZ', period: '1d', candles: [], chart_available: false,
    chart_reason: '公开 K 线来源暂不可用', as_of: null, last_price: null,
    price_as_of: null, price_kind: null, quote_reason: '公开报价来源暂不可用',
    source_id: null, price_source_id: null, read_only: true, trading_eligible: false,
  })
})

const bootstrap = {
  overview: { active_config: { include_symbols: ['159780.SZ'], etf_candidates: {} } },
} as ConsoleBootstrap

const verifiedChart: MarketChartBundle = {
  schema_version: '1.3', symbol: '159780.SZ', period: '1d',
  candles: [{ occurred_at: '2026-09-24T07:00:00Z', open: 1, high: 1.1, low: 0.9, close: 1.05, volume: 1000 }],
  data_available: true, as_of: '2026-09-24T07:00:00Z',
  overlay_unavailable_sources: ['bridge', 'strategy', 'benchmark'],
}

const nativeChart: MarketChartBundle = {
  ...verifiedChart, schema_version: '1.4', period: '1m', source_kind: 'wondertrader',
  source_period: '1m', derived: false, overlay_unavailable_sources: [],
  native_source: {
    provider: 'Qmt', dataset_version: 'fixture-v1', content_id: 'a'.repeat(64),
    qualification: 'DevelopmentVerified', coverage: 'Unknown', adjustment: 'none',
    source_minute_boundary: 'right', chart_minute_boundary: 'left', timezone: 'Asia/Shanghai',
  },
}

test('shows readable chart units without internal qualification labels', async () => {
  vi.mocked(fetchMarketChart).mockImplementation(async (_symbol, period) => ({ ...nativeChart, period, overlay_unavailable_sources: ['benchmark'] }))
  mount()
  fireEvent.click(screen.getByRole('button', { name: '分时' }))
  expect(await screen.findByText(/WonderTrader 原生行情/)).toBeInTheDocument()
  const source = screen.getByRole('status', { name: '读图说明' })
  expect(source).toHaveTextContent('不复权 · 时间为北京时间')
  expect(source).not.toHaveTextContent('开发验证')
  expect(screen.getByRole('status', { name: '行情附加证据缺口' })).toHaveTextContent('上方历史 K 线仍按 WonderTrader 的权威行情展示')
})

test.each(['当前查询没有已发布的分钟线。', '原生行情读取超时或连接不可用，请稍后重试。'])(
  'keeps native minute result visible when public data exists: %s', async (reason) => {
    vi.mocked(fetchDefaultWatchlist).mockResolvedValue({
      schema_version: '1.0', watchlist_id: '00000000-0000-0000-0000-000000000001',
      name: '我的观察', version: 1, updated_at: '2026-09-26T00:00:00Z', affects_strategy: false,
      items: [{ symbol: '159780.SZ', tags: [], added_at: '2026-09-26T00:00:00Z' }],
    })
    vi.mocked(fetchPublicObservation).mockResolvedValue({
      symbol: '159780.SZ', period: '1m', chart_available: true, candles: verifiedChart.candles,
      as_of: verifiedChart.as_of, last_price: 1.05, read_only: true, trading_eligible: false,
      source_id: 'tencent.public-display',
    })
    vi.mocked(fetchMarketChart).mockImplementation(async (_symbol, period) => ({
      ...nativeChart, period, candles: [], data_available: false, missing_reason: reason,
    }))
    mount()
    fireEvent.click(screen.getByRole('button', { name: '分时' }))
    expect(await screen.findByText(reason)).toBeInTheDocument()
    expect(screen.getByRole('status', { name: '权威行情空结果' })).toBeInTheDocument()
    expect(screen.queryByText(/当前显示腾讯公开 K 线/)).not.toBeInTheDocument()
    expect(screen.queryByRole('img', { name: '1 根权威 K 线' })).not.toBeInTheDocument()
  },
)

function suggestionPage(query: string, symbol: string): MarketSymbolSuggestionPage {
  return {
    schema_version: '1.0', query,
    items: [{
      schema_version: '1.0', symbol, display_name: null,
      market_data_available: true, already_in_watchlist: false,
      source_kinds: ['market_fact'],
    }],
    source_coverage: {
      active_config: 'complete', watchlist: 'complete',
      market_facts: 'complete', order_history: 'complete',
    },
  }
}

function mount(pageBootstrap = bootstrap) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><MarketPage bootstrap={pageBootstrap} /></QueryClientProvider>)
  return client
}

test('shows public observation candles with source and keeps strategy scope separate', async () => {
  vi.mocked(fetchDefaultWatchlist).mockResolvedValue({
    schema_version: '1.0', watchlist_id: '00000000-0000-0000-0000-000000000001',
    name: '我的观察', version: 1, updated_at: '2026-09-26T00:00:00Z',
    affects_strategy: false,
    items: [{ symbol: '588170.SH', display_name: null, note: null, tags: [], added_at: '2026-09-26T00:00:00Z' }],
  } as Watchlist)
  vi.mocked(fetchMarketChart).mockResolvedValue({
    schema_version: '1.3', symbol: '588170.SH', period: '1d', candles: [],
    data_available: false, missing_reason: 'no authoritative market bars',
  })
  vi.mocked(fetchPublicObservation).mockResolvedValue({
    symbol: '588170.SH', period: '1d', chart_available: true,
    candles: [{ occurred_at: '2026-09-24T07:00:00+00:00', open: 0.98, high: 1.01, low: 0.97, close: 0.982, volume: 1000 }],
    as_of: '2026-09-24T07:00:00+00:00', chart_reason: null,
    last_price: 0.982, price_as_of: '2026-09-24T07:00:00+00:00', price_kind: 'spot', quote_reason: null,
    source_id: 'tencent.public-display', price_source_id: 'tencent.public-display',
    read_only: true, trading_eligible: false,
  })
  mount({ overview: { active_config: { include_symbols: [], etf_candidates: {} } } } as unknown as ConsoleBootstrap)
  expect(await screen.findByRole('img', { name: '1 根权威 K 线' })).toBeInTheDocument()
  expect(screen.getByText(/当前显示腾讯公开 K 线/)).toBeInTheDocument()
  expect(screen.getByText('公开观察价')).toBeInTheDocument()
  expect(screen.getByText('0.982')).toBeInTheDocument()
  expect(screen.getByText('0 只 · 由活动配置决定')).toBeInTheDocument()
})

test('keeps verified K-bars visible while naming each missing overlay in Chinese', async () => {
  vi.mocked(fetchMarketChart).mockResolvedValue(verifiedChart)
  mount()

  expect(await screen.findByRole('img', { name: '1 根权威 K 线' })).toBeInTheDocument()
  const gap = screen.getByRole('status', { name: '行情附加证据缺口' })
  expect(gap).toHaveTextContent('上方历史 K 线仍按 Market Data 的权威行情展示')
  for (const label of ['成交标记', '策略信号标记', '基准指数走势']) {
    expect(gap).toHaveTextContent(`${label}暂不可用`)
  }
  expect(screen.queryByText('K 线暂不可用')).not.toBeInTheDocument()
})

test('does not show an evidence-gap warning when all overlays are available', async () => {
  vi.mocked(fetchMarketChart).mockResolvedValue({ ...verifiedChart, overlay_unavailable_sources: [] })
  mount()

  expect(await screen.findByRole('img', { name: '1 根权威 K 线' })).toBeInTheDocument()
  expect(screen.queryByRole('status', { name: '行情附加证据缺口' })).not.toBeInTheDocument()
})

test('keeps last successful K bars after a failed background refresh', async () => {
  vi.mocked(fetchMarketChart)
    .mockResolvedValueOnce({ ...verifiedChart, overlay_unavailable_sources: [] })
    .mockRejectedValueOnce(new Error('source temporarily unavailable'))
  const client = mount()
  expect(await screen.findByRole('img', { name: '1 根权威 K 线' })).toBeInTheDocument()

  await act(async () => {
    await client.refetchQueries({ queryKey: ['market', 'chart', '159780.SZ', '1d'] })
  })
  await waitFor(() => expect(screen.getByText(/K 线本次更新失败/)).toBeInTheDocument())
  expect(screen.getByRole('img', { name: '1 根权威 K 线' })).toBeVisible()
  expect(screen.getByText(/当前保留上次成功结果/)).toBeInTheDocument()
})

test('来源范围与图表在重读、失败和恢复时一起更新', async () => {
  const observed: MarketChartBundle = { ...nativeChart, schema_version: '1.7',
    source_observation: { source_schema: 'qmt.source-selection-observation.v1', state: 'Partial',
      source_window: { from_at: '2026-09-24T07:00:00Z', to_at: '2026-09-24T07:00:00Z' }, source_rows: 1,
      selected_rows: 1, requested_limit: 2000, preparation_state: 'Unknown', preparation_request_id: '00000000-0000-4000-8000-000000000001' },
  }
  vi.mocked(fetchMarketChart).mockImplementation(async (_symbol, period) => period === '1m' ? observed : verifiedChart)
  const client = mount()
  fireEvent.click(screen.getByRole('button', { name: '分时' }))
  expect(await screen.findByRole('status', { name: '行情提示' })).toHaveTextContent('部分历史行情缺失')
  let rejectRead!: (error: Error) => void
  vi.mocked(fetchMarketChart).mockImplementation(() => new Promise((_resolve, reject) => { rejectRead = reject }))
  let pending!: Promise<void>
  act(() => { pending = client.refetchQueries({ queryKey: ['market', 'chart', '159780.SZ', '1m'] }) })
  await screen.findByText('正在刷新，当前显示上次成功读取的结果。')
  expect(screen.getByRole('status', { name: '行情提示' })).toHaveTextContent('部分历史行情缺失')
  expect(screen.getByRole('img', { name: '1 根权威 K 线' })).toBeVisible()
  await act(async () => { rejectRead(new Error('temporary read failure')); await pending })
  expect(await screen.findByText(/当前保留上次成功结果/)).toBeVisible()
  expect(screen.getByRole('status', { name: '行情提示' })).toHaveTextContent('部分历史行情缺失')
  vi.mocked(fetchMarketChart).mockResolvedValue(observed)
  await act(async () => { await client.refetchQueries({ queryKey: ['market', 'chart', '159780.SZ', '1m'] }) })
  expect(await screen.findByRole('status', { name: '行情提示' })).toHaveTextContent('历史数据更新结果待确认，请稍后重新读取')
  expect(screen.getByRole('img', { name: '1 根权威 K 线' })).toBeVisible()
  client.clear()
})

test('shows an authoritative empty result without a primary read error', async () => {
  vi.mocked(fetchMarketChart).mockResolvedValueOnce({
    ...verifiedChart, candles: [], data_available: false, missing_reason: 'not_collected',
    overlay_unavailable_sources: [],
  })
  mount()
  expect(await screen.findByRole('status', { name: '权威行情空结果' })).toBeInTheDocument()
  expect(screen.getByText(/当前标的没有已采集的权威 K 线/)).toBeInTheDocument()
  expect(screen.queryByText('K 线暂不可用')).not.toBeInTheDocument()
})

test.each([
  ['expired', '行情已过期'],
  ['unverified', '缺交易所时间、交易日或市场阶段，实时性待核验'],
  ['verified', '已核验行情快照'],
] as const)('uses the server freshness decision for %s quotes', async (state, label) => {
  vi.mocked(fetchMarketChart).mockResolvedValue(verifiedChart)
  vi.mocked(fetchMarketQuote).mockResolvedValue({
    schema_version: '1.0', symbol: '159780.SZ', data_available: true,
    quote: {
      schema_version: '1.0', symbol: '159780.SZ', captured_at: '2026-09-27T04:00:00Z',
      last_price: 1.05, tick_size: 0.001, stale: state !== 'verified',
      freshness_state: state, age_seconds: state === 'expired' ? 3600 : 1,
    },
  })
  mount()
  expect(await screen.findByText(label)).toBeInTheDocument()
})

test('viewing a watched symbol leaves membership unchanged; removal uses its named button', async () => {
  const watched: Watchlist = {
    schema_version: '1.0', watchlist_id: '00000000-0000-0000-0000-000000000001',
    name: '我的观察', version: 6, affects_strategy: false,
    updated_at: '2026-09-26T02:54:37Z',
    items: [{ symbol: '588170.SH', display_name: null, tags: ['个人观察'], added_at: '2026-09-26T02:54:37Z' }],
  }
  vi.mocked(fetchDefaultWatchlist).mockResolvedValue(watched)
  vi.mocked(fetchMarketChart).mockResolvedValue({
    ...verifiedChart, symbol: '588170.SH', candles: [], data_available: false,
    missing_reason: 'no authoritative market bars', overlay_unavailable_sources: [],
  })
  vi.mocked(updateDefaultWatchlist).mockResolvedValue({
    schema_version: '1.0', watchlist: { ...watched, version: 7, items: [] },
    audit_event_id: '00000000-0000-0000-0000-000000000002', replayed: false,
  })
  mount()
  fireEvent.click(await screen.findByRole('button', { name: '查看 588170.SH 行情' }))
  expect(updateDefaultWatchlist).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: '移出观察 588170.SH' })).toHaveTextContent('移出')
  fireEvent.click(screen.getByRole('button', { name: '移出观察 588170.SH' }))
  await waitFor(() => expect(updateDefaultWatchlist).toHaveBeenCalledWith(
    expect.objectContaining({ expected_version: 6, items: [] }),
  ))
})

test('shows an unavailable state after an initial primary read failure', async () => {
  vi.mocked(fetchMarketChart).mockReset().mockRejectedValue(new Error('primary unavailable'))
  mount()
  expect(await screen.findByText('K 线暂不可用')).toBeInTheDocument()
  expect(screen.queryByRole('status', { name: '权威行情空结果' })).not.toBeInTheDocument()
})

test('rapidly typed code starts one search for the settled final input', async () => {
  vi.useFakeTimers()
  vi.mocked(fetchMarketChart).mockResolvedValue(verifiedChart)
  vi.mocked(fetchMarketSymbolSuggestions).mockImplementation(async (query) => suggestionPage(query, '588170.SH'))
  mount()
  const input = screen.getByRole('textbox', { name: '搜索或输入证券代码' })

  for (const value of ['58', '588', '5881', '58817', '588170']) {
    act(() => fireEvent.change(input, { target: { value } }))
    await act(async () => { await vi.advanceTimersByTimeAsync(40) })
  }
  expect(fetchMarketSymbolSuggestions).not.toHaveBeenCalled()

  await act(async () => { await vi.advanceTimersByTimeAsync(260) })
  expect(fetchMarketSymbolSuggestions).toHaveBeenCalledTimes(1)
  expect(fetchMarketSymbolSuggestions).toHaveBeenCalledWith('588170', expect.any(AbortSignal))
  await act(async () => { await vi.advanceTimersByTimeAsync(1) })
  expect(screen.getByText('588170.SH')).toBeInTheDocument()
})

test('hides previous suggestions as soon as the search input changes', async () => {
  vi.useFakeTimers()
  vi.mocked(fetchMarketChart).mockResolvedValue(verifiedChart)
  vi.mocked(fetchMarketSymbolSuggestions).mockImplementation(async (query) => (
    suggestionPage(query, query === '58' ? '510500.SH' : '588170.SH')
  ))
  mount()
  const input = screen.getByRole('textbox', { name: '搜索或输入证券代码' })

  act(() => fireEvent.change(input, { target: { value: '58' } }))
  await act(async () => { await vi.advanceTimersByTimeAsync(300) })
  await act(async () => { await vi.advanceTimersByTimeAsync(1) })
  expect(screen.getByText('510500.SH')).toBeInTheDocument()

  act(() => fireEvent.change(input, { target: { value: '588170' } }))
  expect(screen.queryByText('510500.SH')).not.toBeInTheDocument()
  expect(fetchMarketSymbolSuggestions).toHaveBeenCalledTimes(1)
  await act(async () => { await vi.advanceTimersByTimeAsync(300) })
  await act(async () => { await vi.advanceTimersByTimeAsync(1) })
  expect(fetchMarketSymbolSuggestions).toHaveBeenCalledTimes(2)
  expect(screen.getByText('588170.SH')).toBeInTheDocument()
  expect(screen.queryByText('510500.SH')).not.toBeInTheDocument()
})

test('keeps a searched symbol visible in the chart selector without changing strategy scope', async () => {
  vi.useFakeTimers()
  vi.mocked(fetchMarketChart).mockResolvedValue(verifiedChart)
  vi.mocked(fetchMarketSymbolSuggestions).mockImplementation(async (query) => suggestionPage(query, '159780.SZ'))
  mount({ overview: { active_config: null } } as ConsoleBootstrap)
  expect(screen.getByText('当前没有策略范围')).toBeInTheDocument()

  act(() => fireEvent.change(screen.getByRole('textbox', { name: '搜索或输入证券代码' }), {
    target: { value: '159780' },
  }))
  await act(async () => { await vi.advanceTimersByTimeAsync(301) })
  await act(async () => { await vi.advanceTimersByTimeAsync(1) })
  const candidate = screen.getByText('159780.SZ').closest('button')
  expect(candidate).not.toBeNull()
  act(() => fireEvent.click(candidate!))

  const selector = screen.getByRole('combobox', { name: '行情标的' }) as HTMLSelectElement
  expect(selector).toHaveValue('159780.SZ')
  expect(screen.getByRole('option', { name: '159780.SZ（当前查看）' })).toBeInTheDocument()
  expect(screen.getByText('当前没有策略范围')).toBeInTheDocument()
  expect(screen.getByText('个人观察列表为空')).toBeInTheDocument()
  expect(fetchMarketChart).toHaveBeenCalledWith('159780.SZ', '1d', '000300.SH', expect.any(AbortSignal), 2000)
})
