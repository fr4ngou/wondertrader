import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Keyboard, RefreshCw, Star } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { fetchMarketChart, INTERACTIVE_STATUS_TIMEOUT_MS } from '../api'
import { MarketCandlestickChart } from '../components/MarketCandlestickChart'
import type { Capabilities } from './IndependentApp'
import PersonalWatchlist, { useSecurityIdentity } from './PersonalWatchlist'
import { usePersonalWatchlist } from './usePersonalWatchlist'
import { sourceChartDate } from '../sourceChartPresentation'
import type { MarketChartPeriod } from '../types'
import SourceHistoryStatus from '../components/SourceHistoryStatus'
import { absoluteChinaTime } from '../components/RelativeTime'
import './market-workspace.css'

type Range = 5 | 30 | 60 | '1y' | '2y' | '3y'
const periods = [['1m', '分时'], ['5m', '5分钟'], ['1d', '日线'], ['1w', '周线'], ['1mo', '月线']] as const
const canonical = (value: string) => /^\d{6}\.(SH|SZ)$/.test(value.trim().toUpperCase()) ? value.trim().toUpperCase() : ''

export default function MinuteWorkspace({ capability, capabilityPending = false, watchlistCapability, initialSearch = '' }: {
  capability: Capabilities['features'][string]; capabilityPending?: boolean; watchlistCapability?: unknown; searchCapability?: unknown; initialSearch?: string
}) {
  const navigate = useNavigate()
  const watchlist = usePersonalWatchlist(watchlistCapability)
  const [defaultSymbol, setDefaultSymbol] = useState('')
  useEffect(() => {
    // 晚到自选只补默认图表，不导航、不覆盖搜索草稿；移出也保留当前图。
    if (!initialSearch.trim() && !defaultSymbol && watchlist.symbols[0]) setDefaultSymbol(watchlist.symbols[0])
  }, [initialSearch, watchlist.symbols[0], defaultSymbol])
  const symbol = initialSearch.trim() ? canonical(initialSearch) : defaultSymbol
  const identity = useSecurityIdentity(symbol)
  const [requestedPeriod, setPeriod] = useState<MarketChartPeriod>('1d')
  const availablePeriods = useMemo(() => {
    const declared = capability.periods?.filter((value): value is MarketChartPeriod => periods.some(([period]) => value === period))
    return declared?.length ? declared : periods.map(([value]) => value)
  }, [capability.periods])
  const period = availablePeriods.includes(requestedPeriod) ? requestedPeriod
    : availablePeriods.includes('1d') ? '1d' : availablePeriods[0]
  const [range, setRange] = useState<Range>(60)
  const sourceSeconds = capability.timeout_seconds
  const timeoutMs = typeof sourceSeconds === 'number' && Number.isFinite(sourceSeconds) && sourceSeconds > 0 && sourceSeconds <= 30
    ? sourceSeconds * 1000 + 700 : INTERACTIVE_STATUS_TIMEOUT_MS
  const intraday = period === '1m' || period === '5m'
  const queryRange = typeof range === 'number' ? { dailyLimit: range } : { years: Number(range[0]) }
  const limit = intraday ? 2000 : period === '1d' && typeof range === 'number' ? range : 2000
  const chart = useQuery({ queryKey: ['independent-market-chart', symbol, period, intraday ? 2000 : range],
    queryFn: ({ signal }) => fetchMarketChart(symbol, period, undefined, signal, limit, undefined, timeoutMs,
      intraday || period === '1d' && typeof range === 'number' ? undefined : queryRange),
    enabled: Boolean(symbol) && !capabilityPending, retry: false, refetchOnWindowFocus: false })
  const bundle = chart.data
  const busy = capabilityPending || chart.isFetching
  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      const target = event.target instanceof Element ? event.target : null
      if (event.ctrlKey || event.metaKey || event.altKey || event.isComposing || target?.closest('input,textarea,select,[contenteditable="true"]')) return
      const requested = ({ d: '1d', w: '1w', m: '1mo' } as const)[event.key.toLowerCase() as 'd' | 'w' | 'm']
      if (requested && availablePeriods.includes(requested)) { event.preventDefault(); setPeriod(requested) }
    }
    window.addEventListener('keydown', shortcut)
    return () => window.removeEventListener('keydown', shortcut)
  }, [availablePeriods])
  const last = bundle?.data_available ? bundle.candles.at(-1) : undefined
  const prior = bundle?.candles.at(-2)
  const change = last && prior && prior.close !== 0 ? (last.close / prior.close - 1) * 100 : undefined
  const price = (value?: number) => value?.toLocaleString('zh-CN', { maximumFractionDigits: 3 }) ?? '—'
  const type = identity.data?.security_type
  const present = watchlist.symbols.includes(symbol)
  function open(selected: string) { navigate(`/market?${new URLSearchParams({ search: selected })}`) }
  return <section className="market-workspace" aria-label="证券行情">
    <PersonalWatchlist model={watchlist} selected={symbol} onView={open} ready={!capabilityPending && !chart.isFetching}
      dailySupported={availablePeriods.includes('1d')} timeoutMs={timeoutMs} />
    <article className="market-instrument">
      <header className="market-instrument-header"><div className="market-instrument-title">
        <h1>{identity.data?.name ?? (symbol || '行情')}</h1><code>{symbol}</code>
        {type ? <span>{type === 'etf' ? 'ETF' : type === 'index' ? '指数' : '股票'}</span> : null}
      </div><button className="market-star" type="button" disabled={!symbol || !watchlist.canEdit || !present && watchlist.full}
        aria-pressed={present} onClick={() => void watchlist.toggle(symbol)}>
        <Star size={18} fill={present ? 'currentColor' : 'none'} />{present ? '已加入自选' : '加入自选'}</button></header>
      <div className="market-price-strip"><div className={change === undefined ? '' : change >= 0 ? 'market-up' : 'market-down'}>
        <strong>{price(last?.close)}</strong><small>{change === undefined ? '收盘价' : `${change >= 0 ? '+' : ''}${change.toFixed(2)}% · ${period === '1d' ? '较上一交易日' : period === '1w' ? '较上周' : period === '1mo' ? '较上月' : '较上一分钟'}`}</small></div>
        <dl><div><dt>开盘</dt><dd>{price(last?.open)}</dd></div><div><dt>最高</dt><dd>{price(last?.high)}</dd></div>
          <div><dt>最低</dt><dd>{price(last?.low)}</dd></div><div><dt>成交量</dt><dd>{last?.volume?.toLocaleString('zh-CN', { maximumFractionDigits: 0 }) ?? '—'}
          {last?.volume != null ? bundle?.native_source?.volume_unit === 'share' ? ' 股' : bundle?.native_source?.volume_unit === 'lot' ? ' 手' : '' : ''}</dd></div></dl>
      </div>
      <div className="market-controls"><div className="market-periods" aria-label="K 线周期">{periods.filter(([value]) => availablePeriods.includes(value)).map(([value, label]) =>
        <button key={value} aria-pressed={period === value} onClick={() => setPeriod(value)}>{label}</button>)}</div>
        {!intraday ? <div className="market-ranges" aria-label="显示范围">{([5, 30, 60, '1y', '2y', '3y'] as const).map(value =>
          <button key={value} aria-pressed={range === value} onClick={() => setRange(value)}>{typeof value === 'number' ? `${value}日` : `${value[0]}年`}</button>)}</div> : null}
        <button className="market-refresh" disabled={!symbol || busy} onClick={() => { if (!busy) void chart.refetch() }}><RefreshCw size={15} />刷新</button>
        <details className="market-shortcuts"><summary><Keyboard size={15} /><span>快捷键</span></summary><div>/ 搜索 · D 日线 · W 周线 · M 月线</div></details>
      </div>
      <div className="market-plot" aria-busy={busy}>
        {!symbol ? <div className="market-choose">从顶部搜索，或选择左侧自选证券。</div>
          : chart.isError ? <div className="market-read-error" role="alert">{chart.error.message}{bundle ? ' · 当前保留上次结果' : ''}</div> : null}
        {symbol && (!chart.isError || bundle) ? <MarketCandlestickChart bundle={bundle} loading={chart.isFetching || capabilityPending} visibleCount="all" /> : null}
      </div>
      <footer className="market-data-footer"><span role="status">{busy ? '正在更新…' : last ? `数据截至 ${intraday ? absoluteChinaTime(last.occurred_at) : sourceChartDate(last.occurred_at)} · ${bundle?.candles.length} 根` : '等待行情'}</span>
        {bundle ? <details><summary>数据来源</summary><SourceHistoryStatus bundle={bundle} />
          <p>{bundle.source_bar_count != null ? `来源K线 ${bundle.source_bar_count} 根` : ''}{bundle.native_source ? ` · ${bundle.native_source.provider} · ${bundle.native_source.adjustment === 'none' ? '不复权' : ''}` : ''}</p>
          </details> : null}</footer>
    </article>
  </section>
}
