import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import type { StrategyCapitalHistory } from '../types'
import { capitalHistorySamples, capitalHistoryTooltip, zeroObservationRange } from '../strategyReturnPresentation'
echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, SVGRenderer])

export function StrategyHistoryChart({ history }: { history: StrategyCapitalHistory }) {
  const root = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!root.current) return
    const chart = echarts.init(root.current, undefined, { renderer: 'svg' })
    const samples = capitalHistorySamples(history)
    const returns = samples.map(point => point.returnValue)
    const drawdowns = samples.map(point => point.drawdown)
    chart.setOption({ animation: false, textStyle: { fontFamily: 'system-ui', color: '#66717d' }, legend: { right: 0, top: 0 }, tooltip: { trigger: 'axis', formatter: (values: unknown) => {
      const value = Array.isArray(values) ? values[0] : values
      const index = typeof value === 'object' && value !== null && 'dataIndex' in value ? Number(value.dataIndex) : -1
      return samples[index] ? capitalHistoryTooltip(samples[index]) : '观察时间不可用'
    } }, grid: [{ top: 35, left: 62, right: 20, height: '55%' }, { top: '73%', left: 62, right: 20, bottom: history.sampling === 'daily' ? 32 : 48 }],
      xAxis: [0, 1].map(index => ({ type: 'category', gridIndex: index, data: samples.map(point => point.key), axisLabel: { show: index === 1, hideOverlap: true, formatter: (_value: string, position: number) => samples[position]?.label ?? '' } })),
      yAxis: [0, 1].map(index => ({ type: 'value', gridIndex: index, splitNumber: index === 1 ? 2 : 5, ...zeroObservationRange(index === 1 ? drawdowns : returns, index === 1), axisLabel: { formatter: (value: number) => `${(value * 100).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}%` }, splitLine: { lineStyle: { color: '#e6ebef' } } })),
      series: [{ name: '投入本金收益率', type: 'line', data: returns, showSymbol: true, symbolSize: history.points.length === 1 ? 7 : 4, connectNulls: false, lineStyle: { color: '#3f566e', width: 2 }, itemStyle: { color: '#3f566e' } }, { name: history.sampling === 'daily' ? '每日采样回撤' : '片段回撤', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: drawdowns, connectNulls: false, showSymbol: history.points.length === 1, symbolSize: 7, lineStyle: { color: '#b35f5d' }, itemStyle: { color: '#b35f5d' }, areaStyle: { color: '#f1dedd' } }] })
    const observer = new ResizeObserver(() => chart.resize())
    observer.observe(root.current)
    return () => { observer.disconnect(); chart.dispose() }
  }, [history])
  return <div className="backtest-equity-chart strategy-capital-history-chart" ref={root} aria-label={history.sampling === 'daily' ? '策略资本每日估值收益与每日采样回撤曲线' : '策略资本历史收益与片段回撤曲线'} />
}
