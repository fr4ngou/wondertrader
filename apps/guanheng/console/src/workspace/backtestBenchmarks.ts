import { useQueries, type UseQueryResult } from '@tanstack/react-query'
import { fetchMarketChart } from '../api'
import { reportDate } from './backtestPresentation'

/** 产品内固定的价格指数身份与曲线样式，数据沿原 WT 日线。 */
export const BACKTEST_BENCHMARKS = [
  { symbol: '000001.SH', name: '上证指数', color: '#98671e' },
  { symbol: '000300.SH', name: '沪深300', color: '#7952a0' },
  { symbol: '000905.SH', name: '中证500', color: '#007f78' },
  { symbol: '932000.SH', name: '中证2000', color: '#aa4674' },
  { symbol: '000016.SH', name: '上证50', color: '#496985' },
] as const
type Benchmark = typeof BACKTEST_BENCHMARKS[number]
export type BenchmarkSymbol = Benchmark['symbol']
export type BenchmarkSeries = Benchmark & {
  /** 主报告评价起点前的最后一个合格上海交易日；缺失时不能归一化。 */ baseDay: number | null
  /** 按上海交易日索引的收盘价累计百分数；日期缺失时无键。 */ values: Readonly<Record<number, number>>
}
const pageSize = 2000
const shanghai = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' })

function tradingDay(time: string) {
  const parts = shanghai.formatToParts(new Date(time))
  const part = (key: Intl.DateTimeFormatPartTypes) => parts.find(item => item.type === key)?.value
  return Number(`${part('year')}${part('month')}${part('day')}`)
}

/** 沿现有含端点日线查询向前分页，直到找到评价期之前的真实收盘基点。 */
export async function readBacktestBenchmark(index: Benchmark, start: number, end: number, signal?: AbortSignal): Promise<BenchmarkSeries> {
  let before = `${reportDate(end)}T23:59:59+08:00`
  let upperDay = end
  let base: { day: number; close: number } | undefined
  const closes = new Map<number, number>()
  for (;;) {
    const bundle = await fetchMarketChart(index.symbol, '1d', undefined, signal, pageSize, before)
    if (bundle.symbol !== index.symbol || bundle.period !== '1d' || bundle.source_kind !== 'wondertrader') {
      throw new Error('指数日线身份不匹配')
    }
    let previous = 0
    let firstDay = 0
    for (const candle of bundle.candles) {
      const day = tradingDay(candle.occurred_at)
      if (day <= previous || day > upperDay) throw new Error('指数日线日期不匹配')
      firstDay ||= day
      previous = day
      if (day === bundle.native_source?.current_day?.date || !Number.isFinite(candle.close) || candle.close <= 0) continue
      if (day < start) base = { day, close: candle.close }
      else closes.set(day, candle.close)
    }
    if (base || bundle.candles.length < pageSize) break
    const nextBefore = new Date(Date.parse(`${reportDate(firstDay)}T00:00:00+08:00`) - 1000)
    before = nextBefore.toISOString()
    upperDay = tradingDay(before)
  }
  const values: Record<number, number> = {}
  if (base) for (const [day, close] of closes) {
    const percent = (close / base.close - 1) * 100
    if (Number.isFinite(percent)) values[day] = percent
  }
  return { ...index, baseDay: base?.day ?? null, values }
}

function combineBenchmarks(results: UseQueryResult<BenchmarkSeries>[]) {
  return { series: results.flatMap(query => query.data?.baseDay ? [query.data] : []), results }
}

/** 只发已选指数的只读日线请求，报告切换或取消勾选沿 Query 取消。 */
export function useBacktestBenchmarks(selected: readonly BenchmarkSymbol[], start?: number, end?: number) {
  const indexes = BACKTEST_BENCHMARKS.filter(index => selected.includes(index.symbol))
  const { series, results } = useQueries({ queries: indexes.map(index => ({
    queryKey: ['backtest-index-close', index.symbol, start, end],
    queryFn: ({ signal }: { signal: AbortSignal }) => readBacktestBenchmark(index, start!, end!, signal),
    enabled: start !== undefined && end !== undefined && start <= end,
    staleTime: 60_000, retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false,
  })), combine: combineBenchmarks })
  return { indexes, series, results }
}
