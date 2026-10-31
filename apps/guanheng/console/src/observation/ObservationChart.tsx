import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { BarChart, CandlestickChart, LineChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { AxisPointerComponent, BrushComponent, DataZoomComponent, GridComponent, LegendComponent, MarkLineComponent, TitleComponent, ToolboxComponent, TooltipComponent } from 'echarts/components'
import type { Definition, History, Line, Range, Row } from './types'
import { keyboardRange } from './dates'
echarts.use([LineChart, BarChart, CandlestickChart, CanvasRenderer, AxisPointerComponent, BrushComponent, DataZoomComponent, GridComponent, LegendComponent, MarkLineComponent, TitleComponent, ToolboxComponent, TooltipComponent])

const axis = (line: Line, gridIndex = 0, position = 'left') => ({ type: 'value', gridIndex, position, name: line.unit, scale: true,
  nameTextStyle: { color: line.color }, axisLine: { show: true, lineStyle: { color: line.color } },
  axisLabel: { color: line.color, formatter: (v: number) => new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2, notation: Math.abs(v) >= 10000 ? 'compact' : 'standard' }).format(v) },
  splitLine: { lineStyle: { color: '#dce1e8', type: 'dashed' } } })

export const tooltipValue = (value:unknown) => typeof value==='number' && Number.isFinite(value)
  ? new Intl.NumberFormat('zh-CN',{maximumFractionDigits:4}).format(value) : value==null ? '不可用' : String(value)

export function brushRange(values: number[], range: Range): Range | null {
  if (values.length !== 2 || !values.every(Number.isFinite)) return null
  const start = Math.max(Date.parse(range.start), Math.min(...values))
  const end = Math.min(Date.parse(range.end), Math.max(...values))
  return start <= end ? { start:new Date(start).toISOString().slice(0,10), end:new Date(end).toISOString().slice(0,10) } : null
}

export function legendHidden(lines: Line[], hidden: string[], selected: Record<string,boolean>): string[] {
  const result=new Set(hidden)
  for (const line of lines) if (line.name in selected) {
    if (selected[line.name]) result.delete(line.key)
    else result.add(line.key)
  }
  return [...result]
}

export function chartOptions(definition: Definition, input: Row[], hidden: string[], focus: string, mode: string, activity: string, range?: Range) {
  const rows = input.map(row => ({ ...row }))
  let lines = definition.lines
  if (definition.board === 'crossmarket') {
    lines = lines.filter(line => ['hscei_rebased', 'a_rebased', 'hscei_activity', 'a_activity'].includes(line.key))
    if (activity !== 'all') lines = lines.filter(line => line.panel !== 'context' || line.key === activity)
    if (mode === 'window_return' && rows.length) {
      for (const key of ['hscei_rebased', 'a_rebased']) {
        const base = rows.find(row => typeof row[key] === 'number')?.[key]
        if (typeof base === 'number' && base > 0) for (const row of rows) if (typeof row[key] === 'number') row[key] = ((row[key] as number) / base - 1) * 100
      }
      lines = lines.map(line => line.panel === 'main' ? { ...line, unit: '%' } : line)
    }
    if (mode === 'raw_panels') {
      lines = lines.filter(line=>['hscei_rebased','a_rebased'].includes(line.key)).map(line => ({ ...line, key: line.key === 'a_rebased' ? 'a_close' : 'hscei_close', panel: line.key === 'a_rebased' ? 'context' : 'main', unit: '指数点' }))
    }
  }
  const overlay = ['spread', 'pb', 'bond', 'systemc', 'valuation'].includes(definition.board) || definition.overlay
  const split = !overlay || !!definition.price_above || (definition.board === 'crossmarket' && mode === 'raw_panels')
  let upper = lines.filter(line => definition.price_above ? line.panel === 'context' : line.panel !== 'context')
  let lower = lines.filter(line => definition.price_above ? line.panel !== 'context' : line.panel === 'context')
  if (!split) { upper = lines; lower = [] }
  if (focus === 'upper') lower = []
  if (focus === 'lower' && split) { upper = lower; lower = [] }
  const pcr=definition.board==='pcr'
  const groups = pcr ? (focus==='upper' ? [lines.filter(line=>line.panel==='main')] : focus==='lower' ? [lines.filter(line=>line.panel==='context')] : ['price','main','context'].map(panel=>lines.filter(line=>line.panel===panel))).filter(group=>group.length) : [upper,lower].filter(group=>group.length)
  const both = groups.length===2; const triple=groups.length===3; const metricRight = definition.metric_right || definition.id.startsWith('valuation_marketcap_gdp')
  const tenor = definition.axis_type === 'tenor'
  const plotted = rows
  const axes: object[] = []; const series: object[] = []
  const grid = triple ? [{left:74,right:70,top:'6%',height:'22%'},{left:74,right:70,top:'38%',height:'25%'},{left:74,right:70,top:'73%',height:'18%'}] : both ? [{ left: 74, right: 70, top: 48, height: '46%' }, { left: 74, right: 70, top: '65%', height: '22%' }] : [{ left: 74, right: 70, top: 48, bottom: 80 }]
  const xAxis = grid.map((_, index) => ({ type: tenor ? 'category' : 'time', gridIndex: index,
    ...(tenor ? {data:plotted.map(row=>row.tenor)} : {min:Date.parse(range?.start || String(rows[0]?.date)),max:Date.parse(range?.end || String(rows.at(-1)?.date))}), boundaryGap: false,
    axisLabel: { color: '#647185', hideOverlap: true, ...(tenor ? {} : {formatter:(value:number)=>new Date(value).toISOString().slice(0,10)}) }, axisLine: { lineStyle: { color: '#cbd3dd' } } }))
  for (const [index, group] of groups.entries()) {
    if (!group.length) continue
    const main = group.find(line => line.panel !== 'context') || group[0]
    const context = !split ? group.find(line => line.panel === 'context') : undefined
    const first = metricRight && context ? context : main; const second = metricRight && context ? main : context
    const firstIndex = axes.length
    const limits = definition.board === 'valuation' && second && metricRight ? [{min:0,max:7000},{min:0,max:2.4}] : []
    axes.push({...axis(first, index), ...limits[0]})
    if (second) axes.push({...axis(second, index, 'right'), ...limits[1]})
    for (const line of group) {
      const right = second && ((metricRight && line.panel !== 'context') || (!metricRight && line.panel === 'context'))
      const levels = line.key === definition.primary_field && definition.reference_levels?.length ? definition.reference_levels : []
      const candle = line.chart_type === 'candlestick'
      const bar = line.chart_type === 'bar'
      const data = candle ? plotted.map(row=>[Date.parse(String(row.date)),...(line.candle_fields || ['open','close','low','high']).map(key=>row[key] ?? null)]) : tenor ? plotted.map(row => row[line.key] ?? null) : plotted.filter(row=>row[line.key] !== undefined && (!line.observed_dates_only || row[line.key]!==null)).map(row=>[Date.parse(String(row.date)),row[line.key]])
      series.push({ name: line.name, type: candle ? 'candlestick' : bar ? 'bar' : 'line', xAxisIndex: index, yAxisIndex: firstIndex + (right ? 1 : 0), showSymbol: rows.length < 40 || line.observed_dates_only || (!definition.primary_coverage && /月|季|半年|周频/.test(definition.frequency)),
        ...(bar ? {barMaxWidth:12,barGap:'15%'} : {}),
        ...(candle ? {encode:{x:0,y:[1,2,3,4],tooltip:[1,2,3,4]},dimensions:['日期','开盘','收盘','最低','最高'],barMaxWidth:14} : {}),
        symbolSize: 4, connectNulls: false, data, itemStyle: candle ? {color:'#c65761',color0:'#24996f',borderColor:'#c65761',borderColor0:'#24996f'} : { color: line.color }, lineStyle: { color: line.color, width: 1.8 },
        markLine: { silent: true, symbol: 'none', data: levels.map(level => ({ yAxis: level.value, name: level.name, lineStyle: { color: level.color, type: 'dashed' }, label: { formatter: level.name, color: level.color, position: 'insideEndTop' } })) } })
    }
  }
  return { animation: false, useUTC:true, color: lines.map(line => line.color), grid, xAxis, yAxis: axes, series,
    title:pcr ? groups.map((group,index)=>({text:group[0].panel==='price'?group[0].name+' · 红涨绿跌':group[0].panel==='main'?'PCR与通道':'认购 / 认沽数量',left:74,top:triple ? ['0%','32%','67%'][index] : both ? [0,'59%'][index] : 0,textStyle:{fontSize:11,fontWeight:'normal',color:'#647185'}})) : [],
    tooltip: { trigger: 'axis', renderMode:'richText', confine: true, valueFormatter:tooltipValue },
    axisPointer: { link: [{ xAxisIndex: 'all' }] }, brush: definition.axis_type === 'tenor' ? undefined : { xAxisIndex: 'all', brushMode: 'single', brushType: 'lineX', transformable: false, throttleType: 'debounce', throttleDelay: 250 },
    toolbox: { right: 55, feature: definition.axis_type === 'tenor' ? {} : { brush: { type: ['lineX', 'clear'] }, restore: {} } },
    legend: { bottom: 4, type: 'scroll', data: lines.map(line => line.name), selected:Object.fromEntries(definition.lines.map(line=>[line.name,!hidden.includes(line.key)])), textStyle: { fontSize: 11 } } }
}

export function ObservationChart({ definition, rows, history, range, hidden, focus, mode, activity, onRange, onHidden }: {
  definition: Definition; rows: Row[]; history?: History; range: Range; hidden: string[]; focus: string; mode: string; activity: string; onRange: (range: Range) => void; onHidden?: (hidden:string[])=>void
}) {
  const plot = useRef<HTMLDivElement>(null); const navigator = useRef<HTMLDivElement>(null)
  const callback = useRef(onRange); callback.current = onRange
  useEffect(() => {
    if (!plot.current) return
    const chart = echarts.init(plot.current)
    const options=chartOptions(definition, rows, hidden, focus, mode, activity, range)
    chart.setOption({...options,legend:{...options.legend,selectedMode:!!onHidden}})
    chart.on('legendselectchanged',((event:{selected:Record<string,boolean>})=>onHidden?.(legendHidden(definition.lines,hidden,event.selected))) as never)
    if (definition.axis_type !== 'tenor') chart.dispatchAction({ type: 'takeGlobalCursor', key: 'brush', brushOption: { brushType: 'lineX', brushMode: 'single' } })
    chart.on('brushEnd', ((event: { areas: { coordRange?: [number, number] }[] }) => {
      const values = event.areas[0]?.coordRange
      if (!values) return
      const selected = brushRange(values,range)
      if (selected) callback.current(selected)
    }) as never)
    const resize = new ResizeObserver(() => chart.resize()); resize.observe(plot.current)
    return () => { resize.disconnect(); chart.dispose() }
  }, [definition, rows, hidden, focus, mode, activity, range.start, range.end])
  useEffect(() => {
    if (!navigator.current || !history || definition.axis_type === 'tenor') return
    const chart = echarts.init(navigator.current)
    const lo = Date.parse(history.coverage.start); const hi = Date.parse(history.coverage.end)
    const percent = (day: string) => hi === lo ? 0 : Math.max(0, Math.min(100, (Date.parse(day) - lo) / (hi - lo) * 100))
    chart.setOption({ animation: false, useUTC: true, grid: { left: 74, right: 70, top: 0, bottom: 28 }, xAxis: { type: 'time', min: lo, max: hi, show: false }, yAxis: { type: 'value', show: false, scale: true },
      series: [{ type: 'line', data: history.points.map(p => [Date.parse(p.date), p.value]), connectNulls: false, showSymbol: false, lineStyle: { color: '#8da5bb', width: 1 }, areaStyle: { color: '#d7e3ee' } }],
      dataZoom: [{ type: 'slider', xAxisIndex: 0, filterMode: 'none', start: percent(range.start), end: percent(range.end), bottom: 0, height: 30, showDetail: true, labelFormatter: (v: number) => new Date(v).toISOString().slice(0, 10) }] })
    chart.on('datazoom', ((event: { start: number; end: number; batch?: {start:number;end:number}[] }) => {
      const selected = event.batch?.[0] || event
      if (!Number.isFinite(selected.start) || !Number.isFinite(selected.end)) return
      callback.current({ start: new Date(lo + (hi - lo) * selected.start / 100).toISOString().slice(0, 10), end: new Date(lo + (hi - lo) * selected.end / 100).toISOString().slice(0, 10) })
    }) as never)
    const resize = new ResizeObserver(() => chart.resize()); resize.observe(navigator.current)
    return () => { resize.disconnect(); chart.dispose() }
  }, [history, range.start, range.end, definition.axis_type])
  return <div className="observation-plot" tabIndex={0} role="group" aria-label="图表，方向键缩放和移动日期"
    onPointerDown={event => event.currentTarget.focus({ preventScroll: true })}
    onKeyDown={event => { if (definition.axis_type === 'tenor' || !history) return; const next = keyboardRange(event.key, range, history.coverage); if (next) { event.preventDefault(); event.stopPropagation(); callback.current(next) } }}>
    <div ref={plot} className={'observation-chart'+(definition.board==='pcr' && focus==='both' ? ' observation-chart-pcr' : '')} />
    {definition.axis_type !== 'tenor' && (history ? <><div ref={navigator} className="observation-history" /><p className="observation-note">完整历史：{history.coverage.start} — {history.coverage.end} · {history.raw_count}条；拖选主图选日期，↑放大 ↓缩小 ←前移 →后移</p></> : <p className="observation-note">历史导航暂不可用，当前日期内的图表仍可查看。</p>)}
  </div>
}
