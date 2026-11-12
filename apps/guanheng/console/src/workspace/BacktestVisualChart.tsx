import { ChartZoomToolbar } from '../components/ChartZoomToolbar'
import { observerChartColors, useObserverTheme } from './observerAppearance'
import { useEffect, useMemo, useRef } from 'react'
import * as echarts from 'echarts/core'
import { LineChart, ScatterChart, type LineSeriesOption, type ScatterSeriesOption } from 'echarts/charts'
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent, AxisPointerComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import type { DaySummary, Visuals } from './backtestVisualApi'
import type { BenchmarkSeries } from './backtestBenchmarks'
import { backtestMoney } from './backtestMoney'
import { reportSymbol } from './backtestSymbols'
import { reportDate, reportPct } from './backtestPresentation'

echarts.use([LineChart, ScatterChart, DataZoomComponent, GridComponent, LegendComponent, TooltipComponent, AxisPointerComponent, SVGRenderer])
const emptySummaries: ReadonlyMap<number, DaySummary> = new Map()
const emptyBenchmarks: readonly BenchmarkSeries[] = []

/** 成交散点的dataIndex是标记序号，轴日期才是统一交易日；避免悬停买卖标记串日。 */
export function chartHoverDay(value: unknown, days: readonly number[], labels: ReadonlyMap<string, number>): number | undefined {
  if (!value || typeof value !== 'object') return undefined
  const item = value as { axisValue?: unknown; value?: unknown; dataIndex?: unknown; seriesType?: unknown }
  if (typeof item.axisValue === 'string' && labels.has(item.axisValue)) return labels.get(item.axisValue)
  if (item.seriesType === 'scatter' && Array.isArray(item.value)) return days[Number(item.value[0])]
  return days[Number(item.dataIndex)]
}

/** 全量摘要已在报告加载时读取，悬停只格式化该日；未知与空仓/无成交分别说明。 */
export function daySummaryLines(row: DaySummary | undefined, label: string): string[] {
  if (!row) return [`${label}持仓与买卖摘要暂不可用`, '点击查看日期详情']
  const lines = [`${label} · 当日日末持仓`]
  if (row[1] === null) lines.push('持仓未知')
  else if (!row[1].length) lines.push('空仓')
  else {
    lines[0] += ` · ${row[1].length}只`
    lines.push(...summaryNames(row[1]))
  }
  if (row[2] === null) lines.push('当日成交未知')
  else if (!row[2].length && !row[3]?.length && !row[4]) lines.push('当日无成交')
  else {
    for (const [name, values] of [['买入', row[2]], ['卖出', row[3] ?? []]] as const) {
      const names = summaryNames(values)
      lines.push(...names.map((line, index) => index ? `　　 ${line}` : `${name} ${line}`))
    }
    if (row[4]) lines.push(`其它方向成交 ${row[4]} 笔`)
  }
  return [...lines, '点击固定日期详情']
}

/** 每行两只仅控制排版，全部证券仍保留；数量/价格/盈亏由点击固定的原件详情显示。 */
function summaryNames(values: readonly [string, string][]): string[] {
  const names = values.map(([code]) => {
    const full = reportSymbol(code)
    return full === code ? code.match(/\d{6}/)?.[0] ?? code : full.split(' · ')[0].replace(/ETF$/, '')
  })
  return names.flatMap((name, index) => index % 2 ? [] : [names.slice(index, index + 2).join('、')])
}

type ChartReport = {
  /** 原报告日期与权益，原数值格式保留。 */ points: [number, string | number | null][]
  /** 所属模型的初始权益；归一化和人民币分别声明。 */ metrics: {
    /** WT初始人民币本金，沿原十进制文本。 */ initial_capital_cny?: string
    /** 原组合归一化初值，原版恒为1。 */ initial_equity?: number
  }
}

/** 同步真实日期、缺口、回撤与原生成交标记；缩放/点日仅影响只读视图。 */
export default function BacktestVisualChart({ left, right, visual, rightVisual, mode, markers, onDay, equityUnit = 'CNY', selectedDay, summaries = emptySummaries, summaryLabel = '主报告', positions = false, benchmarks = emptyBenchmarks }: {
  /** 主报告已核验净值。 */ left: ChartReport
  /** 对比报告自己的净值与本金。 */ right?: ChartReport
  /** 主报告派生及成交计数；未读到时保留主曲线。 */ visual?: Pick<Visuals, 'points' | 'trades_available' | 'position_points'>
  /** 对比报告派生；不可把主报告派生用于右曲线。 */ rightVisual?: Pick<Visuals, 'points' | 'trades_available' | 'position_points'>
  /** 明确数值单位；原版归一化权益不转换为人民币。 */ equityUnit?: 'CNY' | 'normalized-equity'
  /** 主图显示百分比或人民币净值。 */ mode: 'return' | 'nav'
  /** 是否显示买/卖/多笔成交日。 */ markers: boolean
  /** 用户选择交易日，归右侧明细owner。 */ onDay: (day: number) => void
  /** 点击或键盘固定的交易日，不随光标悬停改变。 */ selectedDay?: number | null
  /** 当前明细所属报告的同身份只读摘要。 */ summaries?: ReadonlyMap<number, DaySummary>
  /** 明确持仓摘要来自主报告或对比报告。 */ summaryLabel?: string
  /** 正式回测使用三组同步坐标；线上表现沿原两组坐标。 */ positions?: boolean
  /** 已选且有合格基点的价格指数收益，与主报告交易日对齐。 */ benchmarks?: readonly BenchmarkSeries[]
}) {
  const root = useRef<HTMLDivElement>(null)
  const theme = useObserverTheme()
  const zoom = useRef({ start: 0, end: 100 })
  const keyboardDays = useMemo(() => [...new Set([...left.points, ...(right?.points ?? [])].map(p => p[0]))].sort((a, b) => a - b), [left, right])
  const onDayRef = useRef(onDay)
  onDayRef.current = onDay
  useEffect(() => {
    if (!root.current || !left.points.length) return
    const palette = observerChartColors(root.current)
    const chart = echarts.init(root.current, undefined, { renderer: 'svg' })
    const days = [...new Set([...left.points, ...(right?.points ?? [])].map(p => p[0]))].sort((a, b) => a - b)
    const dates = days.map(reportDate)
    const axes = positions ? [0, 1, 2] : [0, 1]
    const dayByLabel = new Map(dates.map((label, index) => [label, days[index]]))
    const series: (LineSeriesOption | ScatterSeriesOption)[] = []
    const indexes = mode === 'return' ? benchmarks : emptyBenchmarks
    const reports = [{ report: left, visual, color: palette.accent, name: '主报告' }, ...(right ? [{ report: right, visual: rightVisual, color: '#d99117', name: '对比报告' }] : [])].map(item => ({ ...item,
      navs: new Map(item.report.points), auxiliary: new Map(item.visual?.points.map(p => [p[0], p])),
      positionByDay: new Map(item.visual?.position_points?.map(p => [p[0], p[1]])) }))
    for (const item of reports) {
      const navs = item.navs
      const initial = Number(equityUnit === 'normalized-equity' ? item.report.metrics.initial_equity : item.report.metrics.initial_capital_cny)
      const values = days.map(day => { const nav = navs.get(day); if (nav === undefined || nav === null) return null
        const value = mode === 'nav' ? Number(nav) : (Number(nav) / initial - 1) * 100
        return Number.isFinite(value) ? value : null })
      series.push({ id: item.name === '主报告' ? 'nav-main' : 'nav-right', name: item.name, type: 'line', data: values, showSymbol: false, connectNulls: false,
        lineStyle: { color: item.color, width: 2 }, itemStyle: { color: item.color } })
      const auxiliary = item.auxiliary
      series.push({ id: item.name === '主报告' ? 'drawdown-main' : 'drawdown-right', name: `${item.name}回撤`, type: 'line', xAxisIndex: 1, yAxisIndex: 1, showSymbol: false,
        data: days.map(day => auxiliary.get(day)?.[2] ?? null), connectNulls: false,
        lineStyle: { color: right ? item.color : '#e97979', width: 1.4 }, areaStyle: { color: right ? item.color : '#e97979', opacity: .12 } })
      if (positions) series.push({ id: item.name === '主报告' ? 'position-main' : 'position-right', name: `${item.name}日末仓位`, type: 'line',
        xAxisIndex: 2, yAxisIndex: 2, showSymbol: false, step: 'end', connectNulls: false,
        data: days.map(day => item.positionByDay.get(day) ?? null),
        lineStyle: { color: right ? item.color : '#00866b', width: 1.6 } })
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
    for (const index of indexes) series.push({ id: `index-${index.symbol}`, name: index.name, type: 'line',
      showSymbol: false, connectNulls: false, data: days.map(day => reports[0].navs.has(day) ? index.values[day] ?? null : null),
      lineStyle: { color: index.color, type: 'dashed', width: 1.5 }, itemStyle: { color: index.color } })
    chart.setOption({ animation: false, textStyle: { fontFamily: 'Segoe UI, Microsoft YaHei, sans-serif', color: palette.muted },
      legend: { show: !!right || indexes.length > 0, selectedMode: false, type: 'scroll', textStyle: { color: palette.muted }, data: [...reports.map(r => r.name), ...indexes.map(index => index.name)], top: 0 },
      grid: positions ? [
        { left: 62, right: 22, top: 38, bottom: '49%' },
        { left: 62, right: 22, top: '57%', bottom: '28%' },
        { left: 62, right: 22, top: '79%', bottom: 30 },
      ] : [{ left: 62, right: 22, top: 38, height: '57%' }, { left: 62, right: 22, top: '76%', bottom: 30 }],
      axisPointer: { link: [{ xAxisIndex: 'all' }], label: { backgroundColor: palette.ink, color: palette.panel } },
      tooltip: { ...palette.tooltip, trigger: 'axis', triggerOn: 'mousemove|click', confine: true, renderMode: 'richText', axisPointer: { type: 'cross', lineStyle: { color: palette.border, type: 'dashed' } },
        textStyle: { color: palette.ink, fontSize: 12, lineHeight: 18 },
        position: (point: number[], _params: unknown, _dom: unknown, _rect: unknown, size: { contentSize: number[]; viewSize: number[] }) => {
          const top = root.current?.getBoundingClientRect().top ?? 0
          const minimum = Math.max(8, 62 - top)
          const bottom = Math.min(size.viewSize[1] - 8, window.innerHeight - top - 8)
          return [Math.max(8, Math.min(point[0] + 14, size.viewSize[0] - size.contentSize[0] - 8)),
            Math.max(minimum, Math.min(point[1] + 14, bottom - size.contentSize[1]))]
        }, formatter: (input: unknown) => {
        const p = Array.isArray(input) ? input[0] : input
        const day = chartHoverDay(p, days, dayByLabel); if (day === undefined) return ''
        return [reportDate(day), ...reports.flatMap(item => {
          const nav = item.navs.get(day)
          const row = item.auxiliary.get(day)
          const label = equityUnit === 'normalized-equity' ? '归一化权益' : '净值'
          const shown = nav === undefined || nav === null ? '未知' : equityUnit === 'normalized-equity' ? Number(nav).toLocaleString('zh-CN', { maximumFractionDigits: 8 }) : backtestMoney(String(nav)) + ' 元'
          return [`${item.name}${label}：${shown}`, `日收益：${reportPct(row?.[1] ?? null)}`, `日末回撤：${reportPct(row?.[2] ?? null)}`,
            ...(positions ? [`日末仓位：${reportPct(item.positionByDay.get(day) ?? null)}`] : [])]
        }), ...indexes.map(index => `${index.name}：${reportPct(reports[0].navs.has(day) ? index.values[day] ?? null : null)}`), '', ...daySummaryLines(summaries.get(day), summaryLabel)].join('\n')
      } },
      xAxis: axes.map(index => ({ type: 'category', gridIndex: index, data: dates, boundaryGap: false,
        axisLabel: { color: palette.muted, show: !positions || index === 2, hideOverlap: true, showMinLabel: true, showMaxLabel: true, formatter: (v: string) => v.slice(0, 7) }, axisLine: { lineStyle: { color: palette.border } } })),
      yAxis: [{ type: 'value', scale: true, axisLabel: { color: palette.muted, formatter: (n: number) => mode === 'return' ? `${n.toFixed(0)}%` : equityUnit === 'normalized-equity' ? n.toFixed(3) : `${(n / 10000).toFixed(1)}万` }, splitLine: { lineStyle: { color: palette.line } } },
        { type: 'value', gridIndex: 1, max: 0, name: positions ? '日末回撤' : '', nameGap: 8,
          nameTextStyle: { color: palette.muted, align: 'left' }, axisLabel: { color: palette.muted, formatter: '{value}%' }, splitLine: { lineStyle: { color: palette.line } } },
        ...(positions ? [{ type: 'value', gridIndex: 2, min: 0, max: ({ max }: { max: number }) => Math.max(100, max || 0),
          name: '日末仓位', nameGap: 8, nameTextStyle: { color: palette.muted, align: 'left' }, axisLabel: { color: palette.muted, formatter: '{value}%' }, splitLine: { lineStyle: { color: palette.line } } }] : [])],
      dataZoom: [{ type: 'inside', xAxisIndex: axes, filterMode: 'none', zoomOnMouseWheel: 'ctrl', moveOnMouseWheel: false, ...zoom.current }], series })
    chart.on('datazoom', () => {
      const options = chart.getOption().dataZoom as { start: number; end: number }[] | undefined
      if (options?.[0]) zoom.current = { start: options[0].start, end: options[0].end }
    })
    chart.getZr().on('click', event => {
      if (chart.containPixel({ gridIndex: axes }, [event.offsetX, event.offsetY])) {
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
  }, [left, right, visual, rightVisual, mode, markers, equityUnit, summaries, summaryLabel, positions, benchmarks, theme])
  return <><ChartZoomToolbar plot={root} /><div ref={root} className={positions ? 'bt-visual-chart bt-visual-chart-positions' : 'bt-visual-chart'} role="img" tabIndex={0}
    aria-label={positions ? '真实日期收益、日末回撤与日末仓位曲线；点击固定详情，左右键切日' : '真实日期收益与日末回撤曲线；悬停看持仓买卖，点击固定详情，左右键切日'}
    onKeyDown={event => {
      if (event.altKey || event.ctrlKey || event.metaKey || !keyboardDays.length) return
      const index = keyboardDays.indexOf(selectedDay ?? keyboardDays.at(-1)!)
      const next = event.key === 'ArrowLeft' ? Math.max(0, index - 1) : event.key === 'ArrowRight' ? Math.min(keyboardDays.length - 1, index + 1) : event.key === 'Home' ? 0 : event.key === 'End' ? keyboardDays.length - 1 : null
      if (next !== null) { event.preventDefault(); onDayRef.current(keyboardDays[next]) }
    }} /></>
}
