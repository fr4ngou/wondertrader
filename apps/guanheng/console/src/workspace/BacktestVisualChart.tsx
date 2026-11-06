import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { LineChart, ScatterChart, type LineSeriesOption, type ScatterSeriesOption } from 'echarts/charts'
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent, AxisPointerComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import type { Visuals } from './backtestVisualApi'
import { backtestMoney } from './backtestMoney'

echarts.use([LineChart, ScatterChart, DataZoomComponent, GridComponent, LegendComponent, TooltipComponent, AxisPointerComponent, SVGRenderer])
export const reportDate = (n: number) => `${String(n).slice(0, 4)}-${String(n).slice(4, 6)}-${String(n).slice(6, 8)}`
export const reportPct = (n: number | null) => n === null ? '未知' : `${n.toLocaleString('zh-CN', { maximumFractionDigits: 4 })}%`

type ChartReport = {
  /** 原报告日期与权益，原数值格式保留。 */ points: [number, string | number | null][]
  /** 所属模型的初始权益；归一化和人民币分别声明。 */ metrics: {
    /** WT初始人民币本金，沿原十进制文本。 */ initial_capital_cny?: string
    /** 原组合归一化初值，原版恒为1。 */ initial_equity?: number
  }
}

/** 同步真实日期、缺口、回撤与原生成交标记；缩放/点日仅影响只读视图。 */
export default function BacktestVisualChart({ left, right, visual, rightVisual, mode, markers, onDay, equityUnit = 'CNY' }: {
  /** 主报告已核验净值。 */ left: ChartReport
  /** 对比报告自己的净值与本金。 */ right?: ChartReport
  /** 主报告派生及成交计数；未读到时保留主曲线。 */ visual?: Pick<Visuals, 'points' | 'trades_available'>
  /** 对比报告派生；不可把主报告派生用于右曲线。 */ rightVisual?: Pick<Visuals, 'points' | 'trades_available'>
  /** 明确数值单位；原版归一化权益不转换为人民币。 */ equityUnit?: 'CNY' | 'normalized-equity'
  /** 主图显示百分比或人民币净值。 */ mode: 'return' | 'nav'
  /** 是否显示买/卖/多笔成交日。 */ markers: boolean
  /** 用户选择交易日，归右侧明细owner。 */ onDay: (day: number) => void
}) {
  const root = useRef<HTMLDivElement>(null)
  const onDayRef = useRef(onDay)
  onDayRef.current = onDay
  useEffect(() => {
    if (!root.current || !left.points.length) return
    const chart = echarts.init(root.current, undefined, { renderer: 'svg' })
    const days = [...new Set([...left.points, ...(right?.points ?? [])].map(p => p[0]))].sort((a, b) => a - b)
    const dates = days.map(reportDate)
    const series: (LineSeriesOption | ScatterSeriesOption)[] = []
    const reports = [{ report: left, visual, color: '#1763ee', name: '主报告' }, ...(right ? [{ report: right, visual: rightVisual, color: '#d99117', name: '对比报告' }] : [])]
    for (const item of reports) {
      const navs = new Map(item.report.points)
      const initial = Number(equityUnit === 'normalized-equity' ? item.report.metrics.initial_equity : item.report.metrics.initial_capital_cny)
      const values = days.map(day => { const nav = navs.get(day); if (nav === undefined || nav === null) return null
        const value = mode === 'nav' ? Number(nav) : (Number(nav) / initial - 1) * 100
        return Number.isFinite(value) ? value : null })
      series.push({ name: item.name, type: 'line', data: values, showSymbol: false, connectNulls: false,
        lineStyle: { color: item.color, width: 2 }, itemStyle: { color: item.color } })
      const auxiliary = new Map(item.visual?.points.map(p => [p[0], p]))
      series.push({ name: `${item.name}回撤`, type: 'line', xAxisIndex: 1, yAxisIndex: 1, showSymbol: false,
        data: days.map(day => auxiliary.get(day)?.[2] ?? null), connectNulls: false,
        lineStyle: { color: right ? item.color : '#e97979', width: 1.4 }, areaStyle: { color: right ? item.color : '#e97979', opacity: .12 } })
      if (markers && item.visual?.trades_available) {
        for (const kind of ['buy', 'sell', 'multiple'] as const) {
          const color = kind === 'buy' ? '#e54351' : kind === 'sell' ? '#008c63' : '#8a55d9'
          const data = days.flatMap((day, index) => {
            const p = auxiliary.get(day); if (!p || values[index] === null) return []
            const total = p[3] + p[4] + p[5]
            const actual = total > 1 || p[5] ? 'multiple' : p[3] ? 'buy' : 'sell'
            return total && actual === kind ? [{ value: [index, values[index]], label: { show: total > 1, formatter: String(total), position: 'top' as const, color } }] : []
          })
          series.push({ name: `${item.name}${kind === 'buy' ? '买入' : kind === 'sell' ? '卖出' : '多笔/其他'}`, type: 'scatter', data,
            symbol: kind === 'multiple' ? 'circle' : 'triangle', symbolRotate: kind === 'sell' ? 180 : 0,
            symbolSize: 10, itemStyle: { color }, z: 5 })
        }
      }
    }
    chart.setOption({ animation: false, textStyle: { fontFamily: 'Segoe UI, Microsoft YaHei, sans-serif', color: '#6e7e98' },
      legend: { show: !!right, data: reports.map(r => r.name), top: 0 },
      grid: [{ left: 62, right: 22, top: 38, height: '57%' }, { left: 62, right: 22, top: '76%', bottom: 54 }],
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      tooltip: { trigger: 'axis', renderMode: 'richText', axisPointer: { type: 'line' }, formatter: (input: unknown) => {
        const p = Array.isArray(input) ? input[0] : input
        const index = p && typeof p === 'object' && 'dataIndex' in p ? Number(p.dataIndex) : -1
        const day = days[index]; if (day === undefined) return ''
        return [reportDate(day), ...reports.flatMap(item => {
          const nav = new Map(item.report.points).get(day)
          const row = item.visual?.points.find(r => r[0] === day)
          const label = equityUnit === 'normalized-equity' ? '归一化权益' : '净值'
          const shown = nav === undefined || nav === null ? '未知' : equityUnit === 'normalized-equity' ? Number(nav).toLocaleString('zh-CN', { maximumFractionDigits: 8 }) : backtestMoney(String(nav)) + ' 元'
          return [`${item.name}${label}：${shown}`, `日收益：${reportPct(row?.[1] ?? null)}`, `日末回撤：${reportPct(row?.[2] ?? null)}`]
        })].join('\n')
      } },
      xAxis: [0, 1].map(index => ({ type: 'category', gridIndex: index, data: dates, boundaryGap: false,
        axisLabel: { hideOverlap: true, showMinLabel: true, showMaxLabel: true, formatter: (v: string) => v.slice(0, 7) }, axisLine: { lineStyle: { color: '#cfdaea' } } })),
      yAxis: [{ type: 'value', scale: true, axisLabel: { formatter: (n: number) => mode === 'return' ? `${n.toFixed(0)}%` : equityUnit === 'normalized-equity' ? n.toFixed(3) : `${(n / 10000).toFixed(1)}万` }, splitLine: { lineStyle: { color: '#e7edf5' } } },
        { type: 'value', gridIndex: 1, max: 0, axisLabel: { formatter: '{value}%' }, splitLine: { lineStyle: { color: '#e7edf5' } } }],
      dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], filterMode: 'none' }, { type: 'slider', xAxisIndex: [0, 1], bottom: 8, height: 18, showDetail: false }], series })
    chart.getZr().on('click', event => {
      if (chart.containPixel({ gridIndex: [0, 1] }, [event.offsetX, event.offsetY])) {
        const point = chart.convertFromPixel({ xAxisIndex: 0 }, event.offsetX)
        const index = Math.round(Number(point))
        if (days[index]) onDayRef.current(days[index])
      }
    })
    if (typeof ResizeObserver === 'undefined') {
      const resize = () => chart.resize(); window.addEventListener('resize', resize)
      return () => { window.removeEventListener('resize', resize); chart.dispose() }
    }
    const observer = new ResizeObserver(() => chart.resize()); observer.observe(root.current)
    return () => { observer.disconnect(); chart.dispose() }
  }, [left, right, visual, rightVisual, mode, markers, equityUnit])
  return <div ref={root} className="bt-visual-chart" role="img" aria-label="真实日期收益与日末回撤曲线；可点选日期，键盘用户使用右侧日期选择" />
}
