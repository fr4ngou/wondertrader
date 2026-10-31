import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, Database, Plus, Search, Star, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import {
  fetchDefaultWatchlist,
  fetchMarketChart,
  fetchMarketDataSubscriptions,
  fetchMarketQuote,
  fetchPublicObservation,
  fetchMarketSymbolSuggestions,
  updateDefaultWatchlist,
} from '../api'
import { MarketCandlestickChart } from '../components/MarketCandlestickChart'
import { EmptyState } from '../components/EmptyState'
import { InfoTip } from '../components/InfoTip'
import { RelativeTime } from '../components/RelativeTime'
import type { ConsoleBootstrap, MarketChartBundle, MarketChartPeriod, MarketQuoteView } from '../types'
import { sourceChartTimeNotice } from '../sourceChartPresentation'

const periods: Array<{ id: MarketChartPeriod; label: string }> = [
  { id: '1m', label: '分时' },
  { id: '5m', label: '5 分钟' },
  { id: '1d', label: '日线' },
]

const overlayGapLabels: Record<NonNullable<MarketChartBundle['overlay_unavailable_sources']>[number], string> = {
  benchmark: '基准指数走势',
  strategy: '策略信号标记',
  bridge: '成交标记',
}

const MARKET_SEARCH_DEBOUNCE_MS = 300

function price(value?: number | null) {
  return value == null ? '—' : value.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
}

function publicSourceName(source?: string | null) {
  return source === 'tencent.public-display' ? '腾讯' : source === 'eastmoney.public-display' ? '东方财富' : '公开来源'
}

function chartSourceName(source?: MarketChartBundle['source_kind']) {
  return source ? ({ wondertrader: 'WonderTrader 原生行情', market_bars: '已采集行情', resonance_daily: '共振日线', mixed: '混合来源', quote_observations: '报价观察' }[source]) : '来源待确认'
}

function quoteFreshnessLabel(quote?: MarketQuoteView | null) {
  if (!quote) return '暂无权威报价'
  if (quote.freshness_state === 'expired') return '行情已过期'
  if (quote.freshness_state === 'unverified') return '缺交易所时间、交易日或市场阶段，实时性待核验'
  return '已核验行情快照'
}

function subscriptionLifecycleLabel(value?: string | null) {
  const labels: Record<string, string> = {
    converged: '已与目标同步',
    pending: '正在同步',
    degraded: '同步受限',
    unavailable: '状态不可用',
  }
  return value ? (labels[value] ?? `待解释状态（${value}）`) : '状态不可用'
}

export function MarketPage({ bootstrap }: { bootstrap: ConsoleBootstrap }) {
  const queryClient = useQueryClient()
  const watchlist = useQuery({
    queryKey: ['watchlist', 'default'],
    queryFn: ({ signal }) => fetchDefaultWatchlist(signal),
    staleTime: 60_000,
    retry: 0,
  })
  const subscriptions = useQuery({
    queryKey: ['market', 'subscriptions'],
    queryFn: ({ signal }) => fetchMarketDataSubscriptions(signal),
    refetchInterval: 30_000,
    retry: 1,
  })
  const configuredSymbols = useMemo(() => [...new Set([
    ...(bootstrap.overview.active_config?.include_symbols ?? []),
    ...Object.values(bootstrap.overview.active_config?.etf_candidates ?? {}).flat(),
  ])].sort(), [bootstrap.overview.active_config])
  const symbols = useMemo(() => [...new Set([
    ...(watchlist.data?.items.map((item) => item.symbol) ?? []),
    ...configuredSymbols,
  ])], [configuredSymbols, watchlist.data])
  const [symbol, setSymbol] = useState('')
  const [symbolSearch, setSymbolSearch] = useState('')
  const [watchlistMessage, setWatchlistMessage] = useState('')
  const [period, setPeriod] = useState<MarketChartPeriod>('1d')
  const normalizedSearch = symbolSearch.trim().toUpperCase()
  const [debouncedSearch, setDebouncedSearch] = useState('')
  useEffect(() => {
    if (normalizedSearch.length < 2) {
      setDebouncedSearch('')
      return
    }
    // Search fans out to four fact owners. Wait for a stable input so typing a
    // code consumes one read window instead of exhausting the shared pool.
    const timer = window.setTimeout(() => setDebouncedSearch(normalizedSearch), MARKET_SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [normalizedSearch])
  const searchReady = normalizedSearch.length >= 2 && debouncedSearch === normalizedSearch
  const validSearchSymbol = /^[0-9]{6}\.(SH|SZ)$/.test(normalizedSearch)
  const suggestions = useQuery({
    queryKey: ['market', 'suggestions', debouncedSearch],
    queryFn: ({ signal }) => fetchMarketSymbolSuggestions(debouncedSearch, signal),
    enabled: searchReady,
    staleTime: 30_000,
    retry: 1,
  })
  const personalSymbols = new Set(watchlist.data?.items.map((item) => item.symbol) ?? [])
  const watchlistMutation = useMutation({
    mutationFn: async ({ action, target }: { action: 'add' | 'remove'; target: string }) => {
      if (!watchlist.data) throw new Error('个人观察列表尚未加载')
      const currentItems = watchlist.data.items
      const items = action === 'add'
        ? [...currentItems, {
          symbol: target,
          display_name: null,
          note: '由控制台加入个人观察',
          tags: ['个人观察'],
          added_at: new Date().toISOString(),
        }]
        : currentItems.filter((item) => item.symbol !== target)
      return updateDefaultWatchlist({
        schema_version: '1.0',
        name: watchlist.data.name,
        expected_version: watchlist.data.version,
        items,
        confirmed: true,
      })
    },
    onSuccess: async (result, variables) => {
      if (result.watchlist.affects_strategy !== false) {
        setWatchlistMessage('安全校验失败：服务未确认该操作与策略隔离。')
        return
      }
      queryClient.setQueryData(['watchlist', 'default'], result.watchlist)
      setWatchlistMessage(variables.action === 'add' ? '已加入个人观察；策略配置保持不变。' : '已移出个人观察；策略配置保持不变。')
      await queryClient.invalidateQueries({ queryKey: ['watchlist', 'default'] })
    },
    onError: (error) => setWatchlistMessage(error instanceof Error ? error.message : '观察列表更新失败'),
  })

  useEffect(() => {
    if (!symbol && symbols[0]) setSymbol(symbols[0])
  }, [symbol, symbols])

  const chart = useQuery({
    queryKey: ['market', 'chart', symbol, period],
    queryFn: ({ signal }) => fetchMarketChart(symbol, period, '000300.SH', signal, 2000),
    enabled: Boolean(symbol),
    staleTime: period === '1d' ? 60_000 : 5_000,
    refetchInterval: period === '1d' ? 60_000 : 5_000,
    retry: 0,
  })
  const quote = useQuery({
    queryKey: ['market', 'quote', symbol],
    queryFn: ({ signal }) => fetchMarketQuote(symbol, signal),
    enabled: Boolean(symbol),
    refetchInterval: 3_000,
    retry: 1,
  })
  const publicObservation = useQuery({
    queryKey: ['market', 'public-observation', symbol, period],
    queryFn: ({ signal }) => fetchPublicObservation(symbol, period, signal),
    enabled: Boolean(symbol && personalSymbols.has(symbol) && (
      chart.isError || quote.isError || (chart.data && !chart.data.data_available) ||
      (quote.data && (!quote.data.quote || quote.data.quote.freshness_state !== 'verified'))
    )),
    staleTime: 60_000,
    retry: 0,
  })
  // 分钟图只投影WT结果；公开观察仍可提供独立观察价及日线产品。
  const currentChart = chart.data
  const publicChart: MarketChartBundle | null = period === '1d' && publicObservation.data?.chart_available && !currentChart?.data_available
    ? {
        schema_version: '1.3', symbol, period,
        candles: publicObservation.data.candles,
        data_available: true, as_of: publicObservation.data.as_of,
        overlays: [], overlays_read_only: true, overlays_executable: false,
      }
    : null
  const visibleChart = currentChart?.data_available ? currentChart : publicChart ?? currentChart
  const publicPrice = quote.data?.quote?.freshness_state === 'verified' ? null : publicObservation.data?.last_price
  return (
    <section className="workspace-page">
      <header className="page-heading">
        <div><h1>行情</h1><p>浏览历史 K 线、实时快照和当前策略范围；个人观察可编辑，始终与策略和交易隔离。</p></div>
        <span className="read-only-stamp"><Star size={14} /> 仅个人观察可编辑</span>
      </header>

      <article className="surface-card market-chart-card">
        <div className="market-chart-toolbar">
          <div><h2>{symbol || '等待标的'} 历史 K 线</h2><span>价格、成交量与策略证据</span></div>
          <div className="market-chart-controls">
            <label><span>标的</span><select aria-label="行情标的" value={symbol} onChange={(event) => setSymbol(event.target.value)}>
              {symbols.map((item) => <option key={item}>{item}</option>)}
              {symbol && !symbols.includes(symbol) ? <option value={symbol}>{symbol}（当前查看）</option> : null}
            </select></label>
            <div className="period-switch" aria-label="K 线周期">{periods.map((item) => <button className={period === item.id ? 'period-active' : ''} key={item.id} onClick={() => setPeriod(item.id)} type="button">{item.label}</button>)}</div>
          </div>
        </div>
        {chart.isError ? <div className="watchlist-message" role="status">K 线本次更新失败，{visibleChart ? '当前保留上次成功结果，数据时间见图表。' : '尚未取得该查询的行情。'}<button onClick={() => void chart.refetch()}>重试读取</button></div> : null}
        {chart.isFetching && visibleChart ? <p role="status">正在刷新，当前显示上次成功读取的结果。</p> : null}
        {visibleChart ? <MarketCandlestickChart bundle={visibleChart} loading={chart.isFetching || publicObservation.isFetching} visibleCount="all" /> : chart.isError
          ? <EmptyState title="K 线暂不可用" detail="没有权威行情时保持空白，不补造价格。" />
          : <EmptyState title="正在读取 K 线" detail={`正在从${period === '1d' ? ' Market Data ' : ' WonderTrader '}获取权威行情。`} />}
        {visibleChart?.native_source && visibleChart.data_available ? <p className="portfolio-data-note" role="status" aria-label="读图说明">{sourceChartTimeNotice(visibleChart.native_source)}</p>
          : visibleChart?.data_available ? <p className="portfolio-data-note">本图行情未声明统一复权基准，拆分或分红可能形成跳空。策略 1.1.2 使用独立核验的前复权分析窗口，判断口径见策略详情。</p> : null}
        {visibleChart ? <SourceHistoryStatus bundle={visibleChart} /> : null}
        {publicChart ? <p className="portfolio-data-note" role="status">当前显示{publicSourceName(publicObservation.data?.source_id)}公开 K 线，仅供个人观察；来源时间见下方。此数据不进入策略、风控或交易。</p> : null}
        {currentChart && !currentChart.data_available && !publicChart ? <p className="portfolio-data-note" role="status">{period === '1d' ? <>当前标的没有已采集的权威 K 线。{publicObservation.data?.chart_reason ?? (publicObservation.isFetching ? '正在读取个人观察公开行情。' : '个人观察公开行情暂不可用。')}</> : currentChart.missing_reason ?? '原生分钟行情暂不可用，请稍后重试。'}</p> : null}
        {currentChart?.overlay_unavailable_sources?.length ? (
          <div className="watchlist-message" role="status" aria-label="行情附加证据缺口">
            <strong>附加证据读取不完整</strong>
            <p>以下信息暂不可用；上方历史 K 线仍按 {period === '1d' ? 'Market Data' : 'WonderTrader'} 的权威行情展示：</p>
            <ul>{currentChart.overlay_unavailable_sources.map(source => (
              <li key={source}>{overlayGapLabels[source]}暂不可用</li>
            ))}</ul>
          </div>
        ) : null}
        <div className="market-chart-meta">
          <span>{visibleChart?.candles.length ?? 0} 根 K 线 · {publicChart ? `${publicSourceName(publicObservation.data?.source_id)}公开观察数据` : chartSourceName(currentChart?.source_kind)}</span>
          <span>{visibleChart?.as_of ? <RelativeTime value={visibleChart.as_of} staleAfterSeconds={period === '1d' ? 172800 : 30} /> : '行情时间不可用'}</span>
        </div>
      </article>

      <div className="market-support-grid">
        <article className="surface-card watchlist-card">
          <div className="card-heading"><div><h2>观察标的</h2><span>个人观察与当前策略范围分区展示</span></div><InfoTip label="观察标的">个人观察只改变本页收藏。当前策略范围来自活动配置，只有经过治理的配置变更才会影响策略。</InfoTip></div>
          <form className="watchlist-search" onSubmit={(event) => {
            event.preventDefault()
            if (validSearchSymbol && !personalSymbols.has(normalizedSearch)) {
              void watchlistMutation.mutateAsync({ action: 'add', target: normalizedSearch })
              setSymbolSearch('')
            }
          }}>
            <label><Search size={15} /><input aria-label="搜索或输入证券代码" onChange={(event) => setSymbolSearch(event.target.value)} placeholder="搜索代码或名称，例如 沪深300" value={symbolSearch} /></label>
            <button disabled={!validSearchSymbol || personalSymbols.has(normalizedSearch) || watchlistMutation.isPending || !watchlist.data} type="submit"><Plus size={15} /> 添加到观察</button>
          </form>
          {normalizedSearch.length >= 2 ? <div className="watchlist-suggestions" aria-label="标的搜索结果">
            {!searchReady || suggestions.isFetching ? <p className="watchlist-search-result">正在搜索系统已知标的…</p> : null}
            {searchReady && suggestions.data && Object.values(suggestions.data.source_coverage).some((state) => state !== 'complete') ? <p className="watchlist-search-result">部分来源暂不可用，已保留其余权威来源的结果。</p> : null}
            {searchReady ? suggestions.data?.items.map((item) => <div className="watchlist-suggestion" key={item.symbol}>
              <button onClick={() => { setSymbol(item.symbol); setSymbolSearch(item.symbol) }} type="button">
                <strong>{item.symbol}</strong><span>{item.display_name ?? '证券名称待核验'}</span>
                <small>{item.source_kinds.length === 1 && item.source_kinds[0] === 'manual_code'
                  ? '代码格式候选 · 请核对交易所和证券名称；当前行情待核验'
                  : `${item.market_data_available ? '当前行情可用' : '当前行情待核验'} · 来源 ${item.source_kinds.map((source) => ({ active_config: '活动配置', watchlist: '个人观察', market_fact: '行情事实', order_history: '历史委托', manual_code: '手动代码' }[source])).join('、')}`}</small>
              </button>
              <button
                disabled={item.already_in_watchlist || watchlistMutation.isPending || !watchlist.data}
                onClick={() => watchlistMutation.mutate({ action: 'add', target: item.symbol })}
                type="button"
              >{item.already_in_watchlist ? '已在观察' : '添加到观察'}</button>
            </div>) : null}
            {searchReady && !suggestions.isFetching && suggestions.data?.items.length === 0 ? <p className="watchlist-search-result">没有找到系统已知标的；可输入完整证券代码继续核验。</p> : null}
            {searchReady && suggestions.isError ? <p className="watchlist-search-result">标的搜索暂不可用，请稍后重试。</p> : null}
          </div> : null}
          {watchlistMessage ? <p className="watchlist-message" role="status">{watchlistMessage}</p> : null}
          <section className="watchlist-section"><header><strong>我的个人观察</strong><span>{watchlist.data?.items.length ?? 0} 只 · 不影响策略</span></header><div className="watchlist-table">
            {watchlist.data?.items.map((item) => <div className="watchlist-symbol watchlist-symbol-managed" key={item.symbol}><button aria-label={`查看 ${item.symbol} 行情`} onClick={() => setSymbol(item.symbol)} type="button"><Star size={13} /><strong>{item.symbol}</strong><span>{item.display_name ?? '个人观察'}</span></button><button aria-label={`移出观察 ${item.symbol}`} disabled={watchlistMutation.isPending} onClick={() => watchlistMutation.mutate({ action: 'remove', target: item.symbol })} type="button"><Trash2 size={14} />移出</button></div>)}
          </div>{watchlist.data && !watchlist.data.items.length ? <EmptyState title="个人观察列表为空" detail="使用上方搜索加入标的；该操作不会改变策略或触发交易。" /> : null}</section>
          <section className="watchlist-section"><header><strong>当前策略范围</strong><span>{configuredSymbols.length} 只 · 由活动配置决定</span></header><div className="watchlist-table">
            {configuredSymbols.map((item) => <button className="watchlist-symbol" key={item} onClick={() => setSymbol(item)} type="button"><Activity size={13} /><strong>{item}</strong><span>策略配置标的</span></button>)}
          </div>{!configuredSymbols.length ? <EmptyState title="当前没有策略范围" detail="活动配置未提供可展示标的。" /> : null}</section>
        </article>

        <article className="surface-card workspace-fact-card">
          <div className="card-heading"><div><h2>行情摘要</h2><span>{publicPrice != null ? '公开来源观察价格' : '最新权威快照'}</span></div><Activity size={18} /></div>
          <div className="workspace-fact-grid">
            <div className="workspace-fact"><span>{publicPrice != null ? publicObservation.data?.price_kind === 'candle_close' ? '最近 K 线收盘价' : '公开观察价' : '最新价'}</span><strong>{price(publicPrice ?? quote.data?.quote?.last_price)}</strong><small>{publicPrice != null ? publicObservation.data?.price_kind === 'candle_close' ? '公开即时报价暂不可用 · 仅供观察' : `${publicSourceName(publicObservation.data?.price_source_id)}公开报价 · 仅供观察` : quoteFreshnessLabel(quote.data?.quote)}</small></div>
            <div className="workspace-fact"><span>买一 / 卖一</span><strong>{price(quote.data?.quote?.bid_price_1)} / {price(quote.data?.quote?.ask_price_1)}</strong><small>{publicPrice != null && publicObservation.data?.price_as_of ? <RelativeTime value={publicObservation.data.price_as_of} staleAfterSeconds={60} /> : quote.data?.quote?.captured_at ? <RelativeTime value={quote.data.quote.captured_at} staleAfterSeconds={15} /> : '暂无权威数据'}</small></div>
            <div className="workspace-fact"><span>订阅同步</span><strong>{subscriptions.data?.target_converged ? '已同步' : '未完成'}</strong><small>{subscriptionLifecycleLabel(subscriptions.data?.lifecycle)}</small></div>
            <div className="workspace-fact"><span>采集范围</span><strong>{subscriptions.data?.target_universe.members.length ?? '—'} 只</strong><small>由活动策略配置决定</small></div>
          </div>
          <p className="portfolio-data-note"><Database size={13} /> 公开观察行情只在本页展示；个人观察更新不影响策略，也不会产生订单或 QMT 调用。</p>
        </article>
      </div>
    </section>
  )
}
import SourceHistoryStatus from '../components/SourceHistoryStatus'
