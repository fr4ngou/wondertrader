import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'

import type { PortfolioPerformanceSeries } from '../types'

echarts.use([LineChart, DataZoomComponent, GridComponent, LegendComponent, TooltipComponent, SVGRenderer])

export function PortfolioEquityChart({ series }: { series: PortfolioPerformanceSeries }) {
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!root.current || !series.data_available || series.points.length === 0) return undefined
    const chart = echarts.init(root.current, undefined, { renderer: 'svg' })
    const dates = series.points.map((item) => item.occurred_at)
    chart.setOption({
      animationDuration: 260,
      textStyle: { color: '#4f5964', fontFamily: 'Inter, system-ui, sans-serif' },
      legend: { top: 0, right: 4, textStyle: { color: '#596570' } },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(248, 249, 251, .96)',
        borderColor: 'rgba(73, 83, 94, .2)',
        textStyle: { color: '#242b33' },
      },
      grid: [
        { left: 56, right: 18, top: 34, height: '57%' },
        { left: 56, right: 18, top: '75%', bottom: 20 },
      ],
      xAxis: [
        { type: 'category', data: dates, boundaryGap: false, axisLabel: { show: false }, axisLine: { lineStyle: { color: '#aeb5bd' } } },
        { type: 'category', data: dates, boundaryGap: false, gridIndex: 1, axisLabel: { color: '#697580', formatter: (value: string) => value.slice(5, 10) }, axisLine: { lineStyle: { color: '#aeb5bd' } } },
      ],
      yAxis: [
        { type: 'value', scale: true, axisLabel: { color: '#697580', formatter: (value: number) => value.toFixed(4) }, splitLine: { lineStyle: { color: 'rgba(79,91,103,.13)' } } },
        { type: 'value', gridIndex: 1, min: 0, axisLabel: { color: '#697580', formatter: (value: number) => `${(value * 100).toFixed(1)}%` }, splitLine: { lineStyle: { color: 'rgba(79,91,103,.09)' } } },
      ],
      dataZoom: [{ type: 'inside', xAxisIndex: [0, 1] }],
      series: [
        { name: '账户净值', type: 'line', data: series.points.map((item) => item.net_asset_value), showSymbol: false, smooth: 0.1, lineStyle: { width: 2, color: '#5d7185' }, areaStyle: { color: 'rgba(93,113,133,.10)' } },
        { name: '回撤', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: series.points.map((item) => item.drawdown), showSymbol: false, lineStyle: { width: 1.3, color: '#c75f63' }, areaStyle: { color: 'rgba(199,95,99,.10)' } },
      ],
    })
    const resize = () => chart.resize()
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', resize)
      return () => { window.removeEventListener('resize', resize); chart.dispose() }
    }
    const observer = new ResizeObserver(resize)
    observer.observe(root.current)
    return () => { observer.disconnect(); chart.dispose() }
  }, [series])

  return <div ref={root} className="portfolio-equity-chart" aria-label="模拟账户净值与回撤曲线" />
}
