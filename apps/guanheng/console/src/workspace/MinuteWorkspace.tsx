import { WorkspaceDock } from './WorkspaceDock'
import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import SourceHistoryStatus from '../components/SourceHistoryStatus'
import { Keyboard, RefreshCw, Star } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { fetchMarketChart, INTERACTIVE_STATUS_TIMEOUT_MS } from '../api'
import { MarketCandlestickChart } from '../components/MarketCandlestickChart'
import type { Capabilities } from './IndependentApp'
import PersonalWatchlist, { useSecurityIdentity } from './PersonalWatchlist'
import { accountFills, heldAccountSymbols } from './marketAccountFacts'
import { useAccountReadView } from './useAccountReadView'
import { usePersonalWatchlist } from './usePersonalWatchlist'
import { sourceChartDate, sourceCurrentDayNotice } from '../sourceChartPresentation'
import type { MarketChartPeriod } from '../types'
import { absoluteChinaTime } from '../components/RelativeTime'
import './market-workspace.css'

const minuteRanges = [[5, '最近5分钟'], [15, '最近15分钟'], [30, '最近30分钟']] as const
const calendarRanges = [
  ['7d', '最近7天', { calendarDays: 7 }], ['1mo', '1个月', { calendarMonths: 1 }],
  ['3mo', '3个月', { calendarMonths: 3 }], ['1y', '1年', { years: 1 }],
  ['2y', '2年', { years: 2 }], ['3y', '3年', { years: 3 }],
] as const
const tradingRanges = [[5, '5个交易日'], [30, '30个交易日'], [60, '60个交易日']] as const
type Range = typeof calendarRanges[number][0] | typeof tradingRanges[number][0]
const periods = [['1m', '1分K'], ['5m', '5分K'], ['1d', '日线'], ['1w', '周线'], ['1mo', '月线']] as const
type ChartView = MarketChartPeriod | 'timeline'
const canonical = (value: string) => /^\d{6}\.(SH|SZ|BJ)$/.test(value.trim().toUpperCase()) ? value.trim().toUpperCase() : ''

export default function MinuteWorkspace({ capability, capabilityPending = false, accountCapability, watchlistCapability, initialSearch = '' }: {
  capability: Capabilities['features'][string]; capabilityPending?: boolean; accountCapability?: Capabilities['features'][string]; watchlistCapability?: unknown; searchCapability?: unknown; initialSearch?: string
}) {
  const navigate = useNavigate()
  const watchlist = usePersonalWatchlist(watchlistCapability)
  const account = useAccountReadView(accountCapability)
  const held = useMemo(() => heldAccountSymbols(account.data?.complete.position), [account.data?.complete.position])
  const firstSymbol = watchlist.symbols[0] ?? held[0]
  const [defaultSymbol, setDefaultSymbol] = useState('')
  useEffect(() => {
    // 晚到自选只补默认图表，不导航、不覆盖搜索草稿；移出也保留当前图。
    if (!initialSearch.trim() && !defaultSymbol && firstSymbol) setDefaultSymbol(firstSymbol)
  }, [initialSearch, firstSymbol, defaultSymbol])
  const symbol = initialSearch.trim() ? canonical(initialSearch) : defaultSymbol
  const identity = useSecurityIdentity(symbol)
  const [requestedView, setView] = useState<ChartView>('1d')
  const availablePeriods = useMemo(() => {
    const declared = capability.periods?.filter((value): value is MarketChartPeriod => periods.some(([period]) => value === period))
    return declared?.length ? declared : periods.map(([value]) => value)
  }, [capability.periods])
  const requestedPeriod = requestedView === 'timeline' ? '1m' : requestedView
  const period = availablePeriods.includes(requestedPeriod) ? requestedPeriod
    : availablePeriods.includes('1d') ? '1d' : availablePeriods[0]
  const view = period === '1m' && (requestedView === 'timeline' || requestedPeriod !== period) ? 'timeline' : period
  const [range, setRange] = useState<Range>(60)
  const [minuteRange, setMinuteRange] = useState<typeof minuteRanges[number][0]>(30)
  const sourceSeconds = capability.timeout_seconds
  const timeoutMs = typeof sourceSeconds === 'number' && Number.isFinite(sourceSeconds) && sourceSeconds > 0 && sourceSeconds <= 30
    ? sourceSeconds * 1000 + 700 : INTERACTIVE_STATUS_TIMEOUT_MS
  const intraday = period === '1m' || period === '5m'
  const queryRange = typeof range === 'number' ? { dailyLimit: range } : calendarRanges.find(([key]) => key === range)?.[2]
  const limit = intraday ? Math.ceil(minuteRange / (period === '5m' ? 5 : 1))
    : period === '1d' && typeof range === 'number' ? range : 2000
  const chart = useQuery({ queryKey: ['independent-market-chart', symbol, period, intraday ? minuteRange : range],
    queryFn: ({ signal }) => fetchMarketChart(symbol, period, undefined, signal, limit, undefined, timeoutMs,
      intraday || period === '1d' && typeof range === 'number' ? undefined : queryRange),
    enabled: Boolean(symbol) && !capabilityPending, staleTime: intraday ? 15_000 : 60_000, retry: false, refetchOnWindowFocus: false })
  const bundle = chart.data
  const displayedBundle = useMemo(() => {
    const last = bundle?.candles.at(-1)
    if (!intraday || !bundle || !last) return bundle
    const cutoff = Date.parse(last.occurred_at) - minuteRange * 60_000
    const candles = bundle.candles.filter(candle => Date.parse(candle.occurred_at) > cutoff)
    return candles.length === bundle.candles.length ? bundle : { ...bundle, candles }
  }, [bundle, intraday, minuteRange])
  const busy = capabilityPending || chart.isFetching
  const dealGroup = account.data?.complete.deal
  const fills = useMemo(() => accountFills(dealGroup, symbol), [dealGroup, symbol])
  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      const target = event.target instanceof Element ? event.target : null
      if (event.ctrlKey || event.metaKey || event.altKey || event.isComposing || target?.closest('input,textarea,select,[contenteditable="true"]')) return
      const requested = ({ d: '1d', w: '1w', m: '1mo' } as const)[event.key.toLowerCase() as 'd' | 'w' | 'm']
      if (requested && availablePeriods.includes(requested)) { event.preventDefault(); setView(requested) }
    }
    window.addEventListener('keydown', shortcut)
    return () => window.removeEventListener('keydown', shortcut)
  }, [availablePeriods])
  const last = displayedBundle?.data_available ? displayedBundle.candles.at(-1) : undefined
  const prior = displayedBundle?.candles.at(-2)
  const change = last && prior && prior.close !== 0 ? (last.close / prior.close - 1) * 100 : undefined
  const price = (value?: number) => value?.toLocaleString('zh-CN', { maximumFractionDigits: 3 }) ?? '—'
  const type = identity.data?.security_type
  const present = watchlist.symbols.includes(symbol)
  const isHeld = held.includes(symbol)
  function open(selected: string) { navigate(`/market?${new URLSearchParams({ search: selected })}`) }
  return <section className="market-workspace" aria-label="证券行情">
    <WorkspaceDock layoutId="market" primaryTitle="证券行情" secondaryTitle="自选证券" side="left" secondaryWidth={250}
      secondary={<PersonalWatchlist model={watchlist} held={held} selected={symbol} onView={open} ready={!capabilityPending && !chart.isFetching}
        dailySupported={availablePeriods.includes('1d')} timeoutMs={timeoutMs} />}
      primary={<article className="market-instrument">
      <header className="market-instrument-header"><div className="market-instrument-title">
        <h1>{identity.data?.name ?? (symbol || '行情')}</h1><code>{symbol}</code>
        {type ? <span>{type === 'etf' ? 'ETF' : type === 'index' ? '指数' : '股票'}</span> : null}
      </div><button className="market-star" type="button" disabled={!symbol || !watchlist.canEdit || !present && watchlist.full}
        aria-pressed={present} onClick={() => void watchlist.toggle(symbol)}>
        <Star size={18} fill={present || isHeld ? 'currentColor' : 'none'} />{present ? '已加入自选' : isHeld ? watchlist.canEdit ? '收藏持仓标的' : '持仓已加入自选' : '加入自选'}</button></header>
      <div className="market-price-strip"><div className={change === undefined ? '' : change >= 0 ? 'market-up' : 'market-down'}>
        <strong>{price(last?.close)}</strong><small>{change === undefined ? '收盘价' : `${change >= 0 ? '+' : ''}${change.toFixed(2)}% · ${period === '1d' ? '较上一交易日' : period === '1w' ? '较上周' : period === '1mo' ? '较上月' : '较上一分钟'}`}</small></div>
        <dl><div><dt>开盘</dt><dd>{price(last?.open)}</dd></div><div><dt>最高</dt><dd>{price(last?.high)}</dd></div>
          <div><dt>最低</dt><dd>{price(last?.low)}</dd></div><div><dt>成交量</dt><dd>{last?.volume?.toLocaleString('zh-CN', { maximumFractionDigits: 0 }) ?? '—'}
          {last?.volume != null ? bundle?.native_source?.volume_unit === 'share' ? ' 股' : bundle?.native_source?.volume_unit === 'lot' ? ' 手' : '' : ''}</dd></div></dl>
      </div>
      <div className="market-controls"><div className="market-periods" aria-label="K 线周期">
        {availablePeriods.includes('1m') ? <button aria-pressed={view === 'timeline'} onClick={() => setView('timeline')}>分时</button> : null}
        {periods.filter(([value]) => availablePeriods.includes(value)).map(([value, label]) =>
          <button key={value} aria-pressed={view === value} onClick={() => setView(value)}>{label}</button>)}</div>
        {intraday ? <div className="market-ranges" aria-label="分钟显示范围">
          {minuteRanges.map(([value, label]) => <button key={value} aria-pressed={minuteRange === value} onClick={() => setMinuteRange(value)}>{label}</button>)}
        </div> : <><div className="market-ranges" aria-label="显示范围">
          {calendarRanges.map(([value, label]) => <button key={value} aria-pressed={range === value} onClick={() => setRange(value)}>{label}</button>)}
        </div><label className="market-trading-range">按交易日<select aria-label="按交易日选择范围" value={typeof range === 'number' ? range : ''}
          onChange={event => { const picked = tradingRanges.find(([value]) => String(value) === event.target.value); if (picked) setRange(picked[0]) }}>
          <option value="" disabled>选择交易日</option>{tradingRanges.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label></>}
        <button className="market-refresh" disabled={!symbol || busy} onClick={() => { if (!busy) void chart.refetch() }}><RefreshCw size={15} />刷新</button>
        <details className="market-shortcuts"><summary><Keyboard size={15} /><span>快捷键</span></summary><div>/ 搜索 · D 日线 · W 周线 · M 月线</div></details>
      </div>
      <div className="market-plot" aria-busy={busy}>
        {!symbol ? <div className="market-choose">从顶部搜索，或选择左侧自选证券。</div>
          : chart.isError ? <div className="market-read-error" role="alert">{chart.error.message}{bundle ? ' · 当前保留上次结果' : ''}</div> : null}
        {symbol && (!chart.isError || bundle) ? <MarketCandlestickChart bundle={displayedBundle} loading={chart.isFetching || capabilityPending} visibleCount="all"
          intradayCandles={view !== 'timeline'} fills={fills} /> : null}
      </div>
      <footer className="market-data-footer"><span role="status">{busy ? '正在更新…' : last ? `数据截至 ${intraday ? absoluteChinaTime(last.occurred_at) : sourceChartDate(last.occurred_at)} · ${displayedBundle?.candles.length} 根` : '等待行情'}</span>
        {dealGroup && last ? <span>买卖点来自账户已发布成交</span> : null}
        {last && sourceCurrentDayNotice(bundle?.native_source) ? <span>{sourceCurrentDayNotice(bundle?.native_source)}</span> : null}</footer>
      {bundle ? <SourceHistoryStatus bundle={bundle} /> : null}
    </article>} />
  </section>
}
