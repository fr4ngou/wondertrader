import { useEffect, useMemo, useRef } from 'react'
import * as echarts from 'echarts/core'
import { BarChart, CandlestickChart, LineChart } from 'echarts/charts'
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkPointComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer, SVGRenderer } from 'echarts/renderers'

import type { MarketChartBundle } from '../types'
import { diagnosticLabel } from '../diagnosticPresentation'
import { sourceChartDate } from '../sourceChartPresentation'
import { EmptyState } from './EmptyState'
import { buildMarketChartContinuity, formatMarketGapDuration } from './marketChartContinuity'

echarts.use([
  BarChart,
  CandlestickChart,
  LineChart,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkPointComponent,
  TooltipComponent,
  CanvasRenderer,
  SVGRenderer,
])

export function MarketCandlestickChart({
  bundle,
  loading = false,
  visibleCount,
}: {
  bundle?: MarketChartBundle
  loading?: boolean
  visibleCount: number | 'all'
}) {
  const root = useRef<HTMLDivElement>(null)
  const continuity = useMemo(
    () => buildMarketChartContinuity(bundle?.candles ?? [], bundle?.period ?? '1d'),
    [bundle],
  )

  useEffect(() => {
    if (!root.current || !bundle?.data_available || bundle.candles.length === 0) {
      return undefined
    }
    const chart = echarts.init(root.current, undefined, {
      renderer: import.meta.env.MODE === 'test' ? 'svg' : 'canvas',
    })
    const intraday = bundle.period !== '1d'
    const hasVolume = bundle.volume_available !== false
    const labels = bundle.candles.map((item) => {
      const date = new Date(item.occurred_at)
      return intraday
        ? date.toLocaleString('zh-CN', {
            month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
            ...(bundle.native_source ? { timeZone: bundle.native_source.timezone } : {}),
          })
        : sourceChartDate(item.occurred_at, bundle.native_source?.timezone)
    })
    const startValue = visibleCount === 'all'
      ? 0
      : Math.max(0, bundle.candles.length - visibleCount)
    const timeKey = (value: string) => {
      const date = new Date(value)
      if (intraday) {
        return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}-${date.getHours()}-${date.getMinutes()}`
      }
      return sourceChartDate(value, bundle.native_source?.timezone)
    }
    const candleIndex = new Map(bundle.candles.map((item, index) => [timeKey(item.occurred_at), index]))
    const overlayMarkers = (bundle.overlays ?? []).flatMap((item) => {
      const index = candleIndex.get(timeKey(item.occurred_at))
      if (index === undefined) return []
      const price = item.price ?? bundle.candles[index].close
      const markerStyle = item.kind === 'execution'
        ? (item.direction === 'buy' ? '#b94f55' : '#536d82')
        : '#4d738e'
      return [{
        name: item.label,
        coord: [index, price],
        value: item.kind === 'signal' ? '信号' : '成交',
        symbol: 'pin',
        symbolSize: item.kind === 'execution' ? 38 : 32,
        itemStyle: { color: markerStyle, borderColor: '#f6f7f8', borderWidth: 1 },
        label: { color: '#ffffff', fontSize: 9, formatter: '{c}' },
        tooltip: { formatter: item.label },
      }]
    })
    const benchmarkPoints = bundle.benchmark?.data_available
      ? bundle.benchmark.points
      : []
    const benchmarkByTime = new Map(benchmarkPoints.map((item) => [timeKey(item.occurred_at), item.close]))
    const benchmarkBase = benchmarkPoints[0]?.close
    const benchmarkData = benchmarkBase
      ? bundle.candles.map((item) => {
          const close = benchmarkByTime.get(timeKey(item.occurred_at))
          return close === undefined ? null : (close / benchmarkBase) * 100
        })
      : []
    const priceSeries = intraday
      ? continuity.segments.map((data) => {
          const pointCount = data.reduce<number>(
            (total, value) => total + (value === null ? 0 : 1),
            0,
          )
          return {
            name: '分时价', type: 'line' as const,
            showSymbol: pointCount === 1, symbolSize: 6,
            smooth: false, connectNulls: false, data,
            lineStyle: { color: '#477a98', width: 1.6 },
            areaStyle: { color: 'rgba(71,122,152,.10)' },
          }
        })
      : [{
          name: '价格', type: 'candlestick' as const,
          data: bundle.candles.map((item) => [item.open, item.close, item.low, item.high]),
          itemStyle: {
            color: '#c75f63', color0: '#5d7185',
            borderColor: '#c75f63', borderColor0: '#5d7185',
          },
        }]
    const priceWithEvidence = priceSeries.map((series, index) => ({
      ...series,
      markPoint: index === 0 && overlayMarkers.length ? {
        silent: false,
        data: overlayMarkers,
      } : undefined,
    }))
    const benchmarkName = bundle.benchmark?.data_available
      ? `基准 ${bundle.benchmark.symbol}`
      : null
    const benchmarkSeries = benchmarkName
      ? continuity.segments.map((segment) => ({
          name: benchmarkName,
          type: 'line' as const,
          yAxisIndex: hasVolume ? 2 : 1,
          showSymbol: false,
          connectNulls: false,
          data: segment.map((value, index) => value === null ? null : benchmarkData[index]),
          lineStyle: { color: '#8a7a6b', width: 1.2, type: 'dashed' as const },
        }))
      : []
    chart.setOption({
      animationDuration: 220,
      textStyle: { color: '#4f5964', fontFamily: 'Inter, system-ui, sans-serif', fontSize: 12 },
      grid: hasVolume ? [
        { left: 12, right: 12, top: 38, height: '64%', containLabel: true },
        { left: 12, right: 12, top: '77%', height: '13%', containLabel: true },
      ] : [
        { left: 12, right: 12, top: 38, height: '78%', containLabel: true },
      ],
      legend: {
        top: 0, right: 4,
        data: [intraday ? '分时价' : '价格', ...(hasVolume ? ['成交量'] : []), ...(benchmarkName ? [benchmarkName] : [])],
        textStyle: { color: '#596570', fontSize: 12 },
      },
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      xAxis: [
        {
          type: 'category', data: labels, boundaryGap: true,
          axisLine: { lineStyle: { color: '#aeb5bd' } }, axisLabel: { color: '#697580', fontSize: 11 },
        },
        ...(hasVolume ? [{
          type: 'category', gridIndex: 1, data: labels, boundaryGap: true,
          axisLine: { lineStyle: { color: '#aeb5bd' } }, axisLabel: { show: false },
        }] : []),
      ],
      yAxis: [
        {
          scale: true, axisLabel: { color: '#697580', fontSize: 11 },
          splitLine: { lineStyle: { color: 'rgba(79, 91, 103, .13)' } },
        },
        ...(hasVolume ? [{
          gridIndex: 1, scale: true, splitNumber: 2,
          axisLabel: {
            color: '#697580', fontSize: 10,
            formatter: (value: number) => `${Math.round(value / 10_000)}万`,
          },
          splitLine: { show: false },
        }] : []),
        {
          scale: true, position: 'right', offset: 2,
          axisLabel: { color: '#697580', fontSize: 10, formatter: (value: number) => `${value.toFixed(0)}` },
          axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false },
        },
      ],
      dataZoom: [
        {
          type: 'inside', xAxisIndex: hasVolume ? [0, 1] : [0], startValue, endValue: bundle.candles.length - 1,
          zoomOnMouseWheel: true, moveOnMouseWheel: false, moveOnMouseMove: true,
        },
        {
          type: 'slider', xAxisIndex: hasVolume ? [0, 1] : [0], bottom: 0, height: 18,
          startValue, endValue: bundle.candles.length - 1,
          borderColor: '#aeb5bd', fillerColor: 'rgba(93,113,133,.16)',
          handleStyle: { color: '#5d7185' }, textStyle: { color: '#697580', fontSize: 10 },
        },
      ],
      series: [
        ...priceWithEvidence,
        ...(hasVolume ? [{
          name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
          data: bundle.candles.map((item) => ({
            value: item.volume,
            itemStyle: { color: item.close >= item.open ? 'rgba(199,95,99,.42)' : 'rgba(93,113,133,.38)' },
          })),
        }] : []),
        ...benchmarkSeries,
      ],
    })
    const observer = typeof ResizeObserver === 'undefined'
      ? null
      : new ResizeObserver(() => chart.resize())
    observer?.observe(root.current)
    return () => {
      observer?.disconnect()
      chart.dispose()
    }
  }, [bundle, continuity, visibleCount])

  // A background refresh retains the previous verified candles. Replacing the
  // chart DOM here would also orphan its ECharts instance until bundle changes.
  if (loading && !bundle) {
    return (
      <EmptyState
        title="正在读取权威 K 线"
        detail="正在从行情服务读取已发布的历史行情；读取完成前不会断言数据不存在。"
      />
    )
  }
  if (!bundle?.data_available || bundle.candles.length === 0) {
    return (
      <EmptyState
        title="暂无权威 K 线"
        detail={bundle?.schema_version === '1.4' || bundle?.schema_version === '1.5' || bundle?.schema_version === '1.6'
          ? bundle.missing_reason ?? '原生行情暂不可用。'
          : diagnosticLabel(bundle?.missing_reason, '行情服务尚未发布该标的和周期的闭合行情。')}
      />
    )
  }
  const kind = bundle.period === '1d' ? 'K 线' : '分时走势'
  const volumeLabel = bundle.volume_partial
    ? '，近期报价聚合段成交量暂未提供'
    : bundle.volume_available === false ? '，成交量暂未提供' : '与成交量'
  const continuityLabel = continuity.gapCount > 0
    ? `，已按 ${continuity.gapCount} 个长时间数据缺口断开连线`
    : ''
  return (
    <div className="market-chart-frame">
      <div ref={root} className="market-chart" aria-label={`${bundle.symbol} ${bundle.period} ${kind}${volumeLabel}${continuityLabel}`} />
      {continuity.gapCount > 0 ? (
        <div className="market-chart-gap-note" role="status">
          已按 {continuity.gapCount} 个长时间数据缺口断开连线；空白区间不代表价格横盘
          {continuity.largestGapMinutes ? `（最长约 ${formatMarketGapDuration(continuity.largestGapMinutes)}）` : ''}。
        </div>
      ) : null}
    </div>
  )
}
