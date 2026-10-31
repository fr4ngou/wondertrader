import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchMarketChart } from '../api'
import { MarketCandlestickChart } from '../components/MarketCandlestickChart'
import { absoluteChinaTime } from '../components/RelativeTime'
import type { Capabilities } from './IndependentApp'
import PersonalWatchlist from './PersonalWatchlist'
import { sourceChartDate, sourceChartTimeNotice } from '../sourceChartPresentation'
import type { MarketChartPeriod } from '../types'
import SourceHistoryStatus from '../components/SourceHistoryStatus'

export default function MinuteWorkspace({ capability, watchlistCapability }: { capability: Capabilities['features'][string]; watchlistCapability?: unknown }) {
  const [input, setInput] = useState('')
  const [symbol, setSymbol] = useState('')
  const [period, setPeriod] = useState<MarketChartPeriod>('1m')
  const availablePeriods = (capability.periods ?? ['1m', '5m']).filter((value): value is MarketChartPeriod => ['1m', '5m', '1d'].includes(value))
  const seriesName = period === '1d' ? '日线' : '分钟线'
  const [beforeInput, setBeforeInput] = useState('')
  const [before, setBefore] = useState('')
  const [validation, setValidation] = useState('')
  const chart = useQuery({
    queryKey: ['independent-minute-chart', symbol, period, before],
    queryFn: ({ signal }) => fetchMarketChart(symbol, period, '000300.SH', signal, 2000, before),
    enabled: Boolean(symbol), retry: false,
  })
  // Query按证券/周期/截止拥有成功缓存；刷新状态只增加说明，不抹去原值。
  const bundle = chart.data
  const dataTime = bundle?.data_available && bundle.candles.length
    ? bundle.as_of : null
  function readMinute(requested: string) {
    if (chart.isFetching) return
    const normalized = requested.trim().toUpperCase()
    if (!/^\d{6}\.(SH|SZ)$/.test(normalized)) { setValidation('请输入六位证券代码和交易所，例如 600000.SH'); return }
    const cutoff = beforeInput.trim()
    if (cutoff && (!/(Z|[+-]\d{2}:\d{2})$/.test(cutoff) || !Number.isFinite(Date.parse(cutoff)))) {
      setValidation('截止时间须包含时区，例如 2026-01-01T15:00:00+08:00'); return
    }
    setValidation('')
    // 相同查询也有主动刷新语义；来源返回200但不可用时，恢复后可按原参数重读。
    if (normalized === symbol && cutoff === before) void chart.refetch()
    else { setSymbol(normalized); setBefore(cutoff) }
  }
  return <section className="workspace-page">
    <header className="page-heading"><div><h1>行情</h1><p>查看证券走势与历史行情。</p></div><span className="read-only-stamp">只读行情</span></header>
    <PersonalWatchlist capability={watchlistCapability} chartAvailable={true} chartBusy={chart.isFetching}
      chartPeriodLabel={seriesName}
      onView={selected => { if (!chart.isFetching) { setInput(selected); readMinute(selected) } }} />
    <article className="surface-card market-chart-card">
      <form className="market-chart-toolbar" onSubmit={event => { event.preventDefault(); readMinute(input) }}>
        <label>证券代码<input aria-label="证券代码" value={input} onChange={event => setInput(event.target.value)} placeholder="例如 600000.SH" /></label>
        <label>截止时间（含时区，可选）<input aria-label="截止时间" value={beforeInput} onChange={event => setBeforeInput(event.target.value)} placeholder={`留空读取最近${seriesName}`} /></label>
        <button type="submit" disabled={chart.isFetching}>读取{seriesName}</button>
        <div className="period-switch" aria-label="K 线周期">{availablePeriods.map(value => <button type="button" key={value} aria-pressed={period === value} className={period === value ? 'period-active' : ''} onClick={() => setPeriod(value)}>{value === '1m' ? '分时' : value === '1d' ? '日线' : '5 分钟'}</button>)}</div>
      </form>
      {validation ? <p role="alert">{validation}</p> : null}
      {chart.isError ? <div role="alert"><p>{chart.error.message}</p><p>{bundle ? '刷新失败，当前保留上次成功读取的结果，数据时间见下方。' : '本次尚未取得行情，可稍后重试。'}</p><button onClick={() => void chart.refetch()}>重试读取</button></div> : null}
      {chart.isFetching && bundle ? <p role="status">正在刷新，当前显示上次成功读取的结果。</p> : null}
      {!symbol ? <p role="status">输入证券代码后读取已发布的{seriesName}。</p>
        : !chart.isError || bundle ? <MarketCandlestickChart bundle={bundle} loading={chart.isFetching} visibleCount="all" /> : null}
      {bundle ? <>
        {bundle.data_available && bundle.candles.length && bundle.native_source ? <p role="status" aria-label="读图说明">{sourceChartTimeNotice(bundle.native_source)}</p> : null}
        <SourceHistoryStatus bundle={bundle} />
        {bundle.data_available && bundle.candles.length ? <p className="market-chart-meta">{bundle.candles.length} 根 K 线</p> : null}
      </> : null}
      <p role="status" aria-label="最后数据时点">{dataTime
        ? bundle?.native_source?.timestamp_semantics === 'source_date'
          ? <>最新交易日：<time dateTime={dataTime}>{sourceChartDate(dataTime)}</time></>
          : <>行情截至：<time dateTime={dataTime}>{absoluteChinaTime(dataTime)}</time></>
        : '未取得有效行情'}</p>
    </article>
    <p className="portfolio-data-note">当前展示历史行情。查看最新数据时，请重新读取。</p>
  </section>
}
