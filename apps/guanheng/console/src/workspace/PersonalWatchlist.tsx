import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, X } from 'lucide-react'
import { fetchMarketChart } from '../api'
import { searchSecurities } from './securitySearchApi'
import type { PersonalWatchlistModel } from './usePersonalWatchlist'
export { PERSONAL_WATCHLIST_QUERY_KEY } from './usePersonalWatchlist'

export function useSecurityIdentity(symbol: string, enabled = true, preview = false, timeoutMs = 6500) {
  return useQuery({ queryKey: ['security-identity', symbol],
    queryFn: async ({ signal }) => (await searchSecurities(symbol, signal, preview, timeoutMs)).results.find(item => item.symbol === symbol) ?? null,
    enabled: enabled && Boolean(symbol), staleTime: 300_000, retry: false, refetchOnWindowFocus: false })
}

function FiveDaySparkline({ values }: { values: number[] }) {
  if (!values.length) return <span className="market-mini-empty">暂无日线</span>
  const minimum = Math.min(...values), maximum = Math.max(...values)
  const coordinates = values.map((value, index) => [values.length === 1 ? 36 : 3 + index * 66 / (values.length - 1),
    maximum === minimum ? 15 : 27 - (value - minimum) / (maximum - minimum) * 24])
  return <svg width="72" height="30" viewBox="0 0 72 30" role="img" aria-label={`最近${values.length}个交易日走势`}
    className={values.at(-1)! >= values[0] ? 'market-up' : 'market-down'}>
    {values.length === 1 ? <circle cx="36" cy="15" r="2" fill="currentColor" />
      : <polyline points={coordinates.map(point => point.join(',')).join(' ')} fill="none" stroke="currentColor" strokeWidth="1.6" />}
  </svg>
}
function WatchlistRow({ symbol, selected, model, onView, ready, dailySupported, timeoutMs }: {
  symbol: string; selected: boolean; model: PersonalWatchlistModel; onView: (symbol: string) => void; ready: boolean; dailySupported: boolean; timeoutMs: number
}) {
  const element = useRef<HTMLLIElement>(null)
  const client = useQueryClient()
  const [visible, setVisible] = useState(typeof IntersectionObserver === 'undefined')
  useEffect(() => {
    if (!element.current || typeof IntersectionObserver === 'undefined') return
    const observer = new IntersectionObserver(entries => setVisible(entries.some(entry => entry.isIntersecting)))
    observer.observe(element.current)
    return () => observer.disconnect()
  }, [])
  const identity = useSecurityIdentity(symbol, visible && ready, true, timeoutMs)
  const history = useQuery({ queryKey: ['watchlist-five-days', symbol],
    queryFn: ({ signal }) => fetchMarketChart(symbol, '1d', undefined, signal, 5, undefined, timeoutMs, { preview: true }),
    enabled: visible && ready && dailySupported, staleTime: 60_000, retry: false, refetchOnWindowFocus: false })
  useEffect(() => {
    // 退出视口或主图开始读取时，撤下低优先级排队；不碰主图自己的查询身份。
    if (!visible || !ready) {
      void client.cancelQueries({ queryKey: ['watchlist-five-days', symbol], exact: true })
      if (!selected) void client.cancelQueries({ queryKey: ['security-identity', symbol], exact: true })
    }
  }, [client, symbol, visible, ready, selected])
  const values = history.data?.data_available ? history.data.candles.map(item => item.close) : []
  const type = identity.data?.security_type
  return <li ref={element} className={selected ? 'market-watch-selected' : ''}>
    <button type="button" className="market-watch-open" aria-pressed={selected} onClick={() => onView(symbol)}
      aria-label={`查看 ${identity.data?.name ?? symbol}`}>
      <span className="market-watch-identity"><strong title={identity.data?.name ?? symbol}>{identity.data?.name ?? symbol}</strong>
        <small>{symbol} · {type === 'etf' ? 'ETF' : type === 'index' ? '指数' : type === 'stock' ? '股票' : '证券'}</small></span>
      {values.length ? <FiveDaySparkline values={values} /> : <span className="market-mini-empty">
        {!dailySupported ? '无日线来源' : history.isError ? '读取失败' : history.isPending ? '待更新' : '暂无日线'}</span>}
      <span className="market-watch-price">{values.at(-1)?.toLocaleString('zh-CN', { maximumFractionDigits: 3 }) ?? '—'}</span>
    </button>
    <button type="button" className="market-watch-remove" aria-label={`移出 ${symbol} 的自选`} disabled={!model.canEdit}
      onClick={() => void model.toggle(symbol)}><X size={13} /></button>
    {identity.isError || history.isError ? <button className="market-watch-retry" type="button"
      title={history.error?.message ?? identity.error?.message} disabled={!ready || identity.isFetching || history.isFetching}
      aria-label={`重试 ${symbol} 的名称和小图`} onClick={() => {
        void identity.refetch(); if (dailySupported) void history.refetch()
      }}><RefreshCw size={12} />重试</button> : null}
  </li>
}
export default function PersonalWatchlist({ model, selected, onView, ready, dailySupported, timeoutMs }: {
  model: PersonalWatchlistModel; selected: string; onView: (symbol: string) => void; ready: boolean; dailySupported: boolean; timeoutMs: number
}) {
  return <aside className="market-watchlist" aria-label="我的自选">
    <header><h2>自选 <span>{model.symbols.length}</span></h2>
      <button type="button" aria-label="刷新自选" disabled={model.loading || model.saving} onClick={() => void model.reread()}><RefreshCw size={15} /></button>
    </header>
    {model.message ? <div className="market-watch-message" role="status">{model.message}</div> : null}
    {model.needsReview && !model.needsRead ? <button onClick={model.confirm}>确认当前列表</button> : null}
    <ul>{model.symbols.map(symbol => <WatchlistRow key={symbol} symbol={symbol} selected={symbol === selected}
      model={model} onView={onView} ready={ready} dailySupported={dailySupported} timeoutMs={timeoutMs} />)}</ul>
    {!model.symbols.length && !model.loading ? <div className="market-watch-empty">搜索证券后，点击星标加入自选。</div> : null}
    <footer>最近 5 个交易日</footer>
  </aside>
}
