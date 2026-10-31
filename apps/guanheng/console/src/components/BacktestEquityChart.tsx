import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'

import type { BacktestPerformanceReport } from '../types'

echarts.use([LineChart, DataZoomComponent, GridComponent, LegendComponent, TooltipComponent, SVGRenderer])

export function BacktestEquityChart({ report }: { report: BacktestPerformanceReport }) {
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!root.current) return undefined
    const chart = echarts.init(root.current, undefined, { renderer: 'svg' })
    const initial = report.initial_capital
    const dates = report.valuation_points.map((item) => item.occurred_at)
    chart.setOption({
      animationDuration: 300,
      textStyle: { color: '#4f5964', fontFamily: 'Inter, system-ui, sans-serif' },
      legend: { top: 0, right: 4, textStyle: { color: '#596570' } },
      tooltip: { trigger: 'axis' },
      grid: [
        { left: 48, right: 16, top: 34, height: '59%' },
        { left: 48, right: 16, top: '76%', bottom: 24 },
      ],
      xAxis: [
        { type: 'category', data: dates, boundaryGap: false, axisLabel: { show: false }, axisLine: { lineStyle: { color: '#aeb5bd' } } },
        { type: 'category', data: dates, boundaryGap: false, gridIndex: 1, axisLabel: { color: '#697580', formatter: (value: string) => value.slice(0, 10) }, axisLine: { lineStyle: { color: '#aeb5bd' } } },
      ],
      yAxis: [
        { type: 'value', axisLabel: { color: '#697580', formatter: (value: number) => `${((value / initial - 1) * 100).toFixed(0)}%` }, splitLine: { lineStyle: { color: 'rgba(79,91,103,.13)' } } },
        { type: 'value', gridIndex: 1, max: 0, axisLabel: { color: '#697580', formatter: (value: number) => `${(value * 100).toFixed(0)}%` }, splitLine: { lineStyle: { color: 'rgba(79,91,103,.09)' } } },
      ],
      dataZoom: [{ type: 'inside', xAxisIndex: [0, 1] }],
      series: [
        { name: '策略净值', type: 'line', data: report.valuation_points.map((item) => item.net_asset_value), showSymbol: false, smooth: 0.12, lineStyle: { width: 2, color: '#5d7185' }, areaStyle: { color: 'rgba(93,113,133,.10)' } },
        { name: '基准', type: 'line', data: report.valuation_points.map((item) => item.benchmark_value ?? null), showSymbol: false, lineStyle: { width: 1.2, color: '#477a98', type: 'dashed' } },
        { name: '回撤', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: report.drawdown_curve.map((item) => item.drawdown), showSymbol: false, lineStyle: { width: 1.4, color: '#c75f63' }, areaStyle: { color: 'rgba(199,95,99,.12)' } },
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
  }, [report])

  return <div ref={root} className="backtest-equity-chart" aria-label="回测净值、基准和回撤曲线" />
}
