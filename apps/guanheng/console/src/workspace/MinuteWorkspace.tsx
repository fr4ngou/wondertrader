import { WorkspaceDock } from './WorkspaceDock'
import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import SourceHistoryStatus from '../components/SourceHistoryStatus'
import { Keyboard, RefreshCw, Star } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { fetchMarketChart, INTERACTIVE_STATUS_TIMEOUT_MS } from '../api'
import { MarketCandlestickChart } from '../components/MarketCandlestickChart'
import { ChartHistoryTrack } from '../components/ChartHistoryTrack'
import type { Capabilities } from './IndependentApp'
import PersonalWatchlist, { useSecurityIdentity } from './PersonalWatchlist'
import { accountFills, heldAccountSymbols } from './marketAccountFacts'
import { useAccountReadView } from './useAccountReadView'
import { usePersonalWatchlist } from './usePersonalWatchlist'
import { sourceChartDate, sourceCurrentDayNotice } from '../sourceChartPresentation'
import type { MarketChartPeriod } from '../types'
import { absoluteChinaTime } from '../components/RelativeTime'
import { keyboardRange, presetRange } from '../observation/dates'
import type { Range } from '../observation/types'
import './market-workspace.css'

const minuteRanges = [[5, '最近5分钟'], [15, '最近15分钟'], [30, '最近30分钟']] as const
const calendarRanges = [
  ['d5', '近 5 日'], ['w1', '最近7天'], ['m1', '1个月'], ['m3', '近 3 月'],
  ['y1', '1年'], ['y2', '2年'], ['y3', '3年'],
] as const
type MinuteWindow = { scope: string; latest: number; end: number; minutes: number }
const minuteMs = 60_000
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
  const [dateSelection, setDateSelection] = useState<{ range: Range; preset?: string }>()
  const [minuteRange, setMinuteRange] = useState<typeof minuteRanges[number][0]>(30)
  const [minuteSelection, setMinuteSelection] = useState<MinuteWindow>()
  const sourceSeconds = capability.timeout_seconds
  const timeoutMs = typeof sourceSeconds === 'number' && Number.isFinite(sourceSeconds) && sourceSeconds > 0 && sourceSeconds <= 30
    ? sourceSeconds * 1000 + 700 : INTERACTIVE_STATUS_TIMEOUT_MS
  const intraday = period === '1m' || period === '5m'
  const today = sourceChartDate(new Date().toISOString())
  const scope = `${symbol}:${period}`
  const activeMinute = minuteSelection?.scope === scope ? minuteSelection : undefined
  const minutes = activeMinute?.minutes ?? minuteRange
  const range = dateSelection?.range
  const before = intraday ? activeMinute && activeMinute.end < activeMinute.latest ? new Date(activeMinute.end).toISOString() : undefined
    : range && `${range.end}T23:59:59+08:00`
  const limit = intraday ? Math.ceil(minutes / (period === '5m' ? 5 : 1)) : period === '1d' && !range ? 60 : 2000
  const queryRange = intraday ? undefined : range ? { fromDate: range.start } : period === '1d' ? undefined : { dailyLimit: 60 }
  const chart = useQuery({ queryKey: ['independent-market-chart', symbol, period, limit, before, queryRange],
    queryFn: ({ signal }) => fetchMarketChart(symbol, period, undefined, signal, limit, before, timeoutMs, queryRange),
    enabled: Boolean(symbol) && !capabilityPending, staleTime: intraday ? 15_000 : 60_000, retry: false, refetchOnWindowFocus: false })
  const bundle = chart.data
  const archive = useQuery({ queryKey: ['market-chart-archive', symbol],
    queryFn: ({ signal }) => fetchMarketChart(symbol, '1d', undefined, signal, 1, undefined, timeoutMs, { archiveBounds: true, preview: true }),
    enabled: !!symbol && !!bundle?.native_source && capability.available === true && availablePeriods.includes('1d'),
    staleTime: 600_000, retry: false, refetchOnWindowFocus: false })
  const archiveWindow = archive.data?.archive_window
  const coverage = archiveWindow ? { start: sourceChartDate(archiveWindow.from_at), end: sourceChartDate(archiveWindow.to_at) } : undefined
  const displayedBundle = useMemo(() => {
    const last = bundle?.candles.at(-1)
    if (!intraday || !bundle || !last) return bundle
    const cutoff = Date.parse(last.occurred_at) - minutes * minuteMs
    const candles = bundle.candles.filter(candle => Date.parse(candle.occurred_at) > cutoff)
    return candles.length === bundle.candles.length ? bundle : { ...bundle, candles }
  }, [bundle, intraday, minutes])
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
  const first = displayedBundle?.first_source_at ?? displayedBundle?.candles[0]?.occurred_at
  const actualWindow = first && last ? { start: sourceChartDate(first), end: sourceChartDate(last.occurred_at) } : undefined
  const visibleWindow = intraday ? actualWindow : bundle?.source_bar_count === 2000 ? actualWindow : range ?? actualWindow
  function navigateChart(key: string) {
    if (key === 'End') {
      if (intraday) setMinuteSelection(undefined)
      else if (dateSelection?.preset) {
        setDateSelection({ preset: dateSelection.preset, range: presetRange(dateSelection.preset, today) })
      } else setDateSelection(undefined)
      return true
    }
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(key)) return false
    if (intraday && (last || activeMinute)) {
      const latest = activeMinute?.latest ?? Date.parse(last!.occurred_at)
      const end = activeMinute?.end ?? latest
      const step = period === '5m' ? 5 : 1
      const next = key === 'ArrowUp' ? Math.max(step, Math.floor(minutes * .8))
        : key === 'ArrowDown' ? Math.min(2000 * step, Math.max(minutes + 1, Math.ceil(minutes * 1.25))) : minutes
      const delta = key === 'ArrowLeft' ? -step * minuteMs : key === 'ArrowRight' ? step * minuteMs : 0
      setMinuteSelection({ scope, latest, end: Math.min(latest, end + delta), minutes: next })
    } else if (visibleWindow) {
      const next = keyboardRange(key, visibleWindow, { start: coverage?.start ?? visibleWindow.start, end: today })
      if (next && (next.start !== visibleWindow.start || next.end !== visibleWindow.end)) {
        setDateSelection({ range: next })
      }
    }
    return true
  }
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
          {minuteRanges.map(([value, label]) => <button key={value} aria-pressed={!activeMinute && minuteRange === value}
            onClick={() => { setMinuteRange(value); setMinuteSelection(undefined) }}>{label}</button>)}
        </div> : <div className="market-ranges" aria-label="显示范围">
          {calendarRanges.map(([key, label]) => <button key={key} aria-pressed={dateSelection?.preset === key}
            onClick={() => setDateSelection({ preset: key, range: presetRange(key, today) })}>{label}</button>)}
        </div>}
        <button className="market-refresh" disabled={!symbol || busy} onClick={() => { if (!busy) void chart.refetch() }}><RefreshCw size={15} />刷新</button>
        <details className="market-shortcuts"><summary><Keyboard size={15} /><span>快捷键</span></summary><div>/ 搜索 · D 日线 · W 周线 · M 月线<br />聚焦图表后 ↑↓ 缩放 · ←→ 移动日期</div></details>
      </div>
      <div className="market-plot" aria-busy={busy} role="group" aria-label="行情图表，方向键缩放和移动日期" tabIndex={symbol ? 0 : undefined}
        onPointerDown={event => { if (!(event.target instanceof Element && event.target.closest('button'))) event.currentTarget.focus({ preventScroll: true }) }}
        onKeyDown={event => {
          if (!event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey && navigateChart(event.key)) event.preventDefault()
        }}>
        {!symbol ? <div className="market-choose">从顶部搜索，或选择左侧自选证券。</div>
          : chart.isError ? <div className="market-read-error" role="alert">{chart.error.message}{bundle ? ' · 当前保留上次结果' : ''}</div> : null}
        {symbol && (!chart.isError || bundle) ? <MarketCandlestickChart bundle={displayedBundle} loading={chart.isFetching || capabilityPending} visibleCount="all"
          intradayCandles={view !== 'timeline'} fills={fills} onNavigate={navigateChart} /> : null}
        {coverage && visibleWindow ? <ChartHistoryTrack coverage={coverage} range={visibleWindow}
          label={intraday ? '日线归档 · 分钟图所在日期' : '日线归档'} /> : null}
        {archive.isError ? <small className="market-history-status">日线归档范围暂不可用</small> : null}
      </div>
      <footer className="market-data-footer"><span role="status">{busy ? '正在更新…' : last ? `数据截至 ${intraday ? absoluteChinaTime(last.occurred_at) : sourceChartDate(last.occurred_at)} · ${displayedBundle?.candles.length} 根` : '等待行情'}</span>
        {dealGroup && last ? <span>买卖点来自账户已发布成交</span> : null}
        {last && sourceCurrentDayNotice(bundle?.native_source) ? <span>{sourceCurrentDayNotice(bundle?.native_source)}</span> : null}</footer>
      {bundle ? <SourceHistoryStatus bundle={bundle} /> : null}
    </article>} />
  </section>
}
