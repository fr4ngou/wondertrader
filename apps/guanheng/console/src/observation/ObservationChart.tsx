import { useEffect, useRef, useState } from 'react'
import * as echarts from 'echarts/core'
import { BarChart, CandlestickChart, LineChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { AxisPointerComponent, BrushComponent, GridComponent, LegendComponent, MarkLineComponent, TitleComponent, ToolboxComponent, TooltipComponent } from 'echarts/components'
import type { Definition, History, Line, Range, Row } from './types'
import { observerChartColors, useObserverTheme } from '../workspace/observerAppearance'
import { keyboardRange } from './dates'
import { ChartDateControls, ChartHistoryTrack } from '../components/ChartHistoryTrack'
import { sourceChartDate } from '../sourceChartPresentation'
import { observationNumber, observationDisplayUnit } from './numbers'
echarts.use([LineChart, BarChart, CandlestickChart, CanvasRenderer, AxisPointerComponent, BrushComponent, GridComponent, LegendComponent, MarkLineComponent, TitleComponent, ToolboxComponent, TooltipComponent])


const axis = (line: Line, gridColor: string, gridIndex: number, position = 'left') => ({ type: 'value', gridIndex, position, name: observationDisplayUnit(line.unit), scale: true,
  nameTextStyle: { color: line.color }, axisLine: { show: true, lineStyle: { color: line.color } },
  axisLabel: { color: line.color, formatter: (v: number) => observationNumber(v,line.unit) },
  splitLine: { lineStyle: { color: gridColor, type: 'dashed' } } })

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

export function chartOptions(definition: Definition, input: Row[], hidden: string[], focus: string, mode: string, activity: string, range?: Range, palette?: ReturnType<typeof observerChartColors>) {
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
  const panels=definition.panel_groups
  const groups = panels ? panels.map(panel=>lines.filter(line=>line.panel===panel.id)) : pcr ? (focus==='upper' ? [lines.filter(line=>line.panel==='main')] : focus==='lower' ? [lines.filter(line=>line.panel==='context')] : ['price','main','context'].map(panel=>lines.filter(line=>line.panel===panel))).filter(group=>group.length) : [upper,lower].filter(group=>group.length)
  const both = groups.length===2; const triple=groups.length===3; const metricRight = definition.metric_right || definition.id.startsWith('valuation_marketcap_gdp')
  const tenor = definition.axis_type === 'tenor'
  const plotted = rows
  const axes: object[] = []; const series: object[] = []
  const grid = panels ? panels.map((_,i)=>({left:74,right:74,top:34+i*190,height:140})) : triple ? [{left:74,right:70,top:'6%',height:'22%'},{left:74,right:70,top:'38%',height:'25%'},{left:74,right:70,top:'73%',height:'18%'}] : both ? [{ left: 74, right: 70, top: 48, height: '46%' }, { left: 74, right: 70, top: '65%', height: '22%' }] : [{ left: 74, right: 70, top: 48, bottom: 80 }]
  const xAxis = grid.map((_, index) => ({ type: tenor ? 'category' : 'time', gridIndex: index,
    ...(tenor ? {data:plotted.map(row=>row.tenor)} : {min:Date.parse(range?.start || String(rows[0]?.date)),max:Date.parse(range?.end || String(rows.at(-1)?.date))}), boundaryGap: false,
    axisLabel: { color: palette?.muted ?? '#647185', hideOverlap: true, ...(tenor ? {} : {formatter:(value:number)=>new Date(value).toISOString().slice(0,10)}) }, axisLine: { lineStyle: { color: palette?.border ?? '#cbd3dd' } } }))
  for (const [index, group] of groups.entries()) {
    if (!group.length) continue
    const main = panels ? group.find(line=>line.axis!=='right') || group[0] : group.find(line => line.panel !== 'context') || group[0]
    const explicitRight = group.find(line=>line.axis==='right')
    const context = explicitRight || (panels ? undefined : !split ? group.find(line => line.panel === 'context') : undefined)
    const first = metricRight && context ? context : main; const second = metricRight && context ? main : context
    const firstIndex = axes.length
    const limits = definition.board === 'valuation' && second && metricRight ? [{min:0,max:7000},{min:0,max:2.4}] : definition.board==='breaknet' && group.some(line=>line.chart_type==='bar') ? [{min:0},{min:0}] : []
    axes.push({...axis(first, palette?.line ?? '#dce1e8', index), ...limits[0], ...(panels?.[index].min===undefined?{}:{min:panels[index].min}), ...(panels?.[index].max===undefined?{}:{max:panels[index].max})})
    if (second) axes.push({...axis(second, palette?.line ?? '#dce1e8', index, 'right'), ...limits[1]})
    for (const line of group) {
      const right = second && (explicitRight ? line.axis==='right' : panels ? line.axis==='right' : (metricRight && line.panel !== 'context') || (!metricRight && line.panel === 'context'))
      const levels = line.reference_levels || (line.key === definition.primary_field && definition.reference_levels?.length ? definition.reference_levels : [])
      const markers = definition.event_markers
      const events = markers && !Array.isArray(markers) && markers.anchor === line.key ? plotted.flatMap(row => {
        const event = markers.values.find(item => item.code === row[markers.field])
        return event ? [{ xAxis: Date.parse(String(row.date)), name: event.label,
          lineStyle: { color: event.color, type: 'dashed' }, label: { show: false } }] : []
      }) : []
      const candle = line.chart_type === 'candlestick'
      const bar = line.chart_type === 'bar'
      const observations=line.observation_dates?new Set(line.observation_dates):undefined
      const data = candle ? plotted.map(row=>[Date.parse(String(row.date)),...(line.candle_fields || ['open','close','low','high']).map(key=>row[key] ?? null)]) : tenor ? plotted.map(row => row[line.key] ?? null) : plotted.filter(row=>row[line.key] !== undefined && (!line.observed_dates_only || row[line.key]!==null || observations?.has(String(row.date)))).map(row=>[Date.parse(String(row.date)),row[line.key]])
      const values=data.map(value=>Array.isArray(value)?value[1]:value)
      const observedCount=values.filter(value=>typeof value==='number').length
      const hasIsolatedPoint=values.some((value,i)=>typeof value==='number' && typeof values[i-1]!=='number' && typeof values[i+1]!=='number')
      series.push({ name: line.name, type: candle ? 'candlestick' : bar ? 'bar' : 'line', xAxisIndex: index, yAxisIndex: firstIndex + (right ? 1 : 0), showSymbol: observedCount < 40 || hasIsolatedPoint || line.observed_dates_only || (!definition.primary_coverage && /月|季|半年|周频/.test(definition.frequency)),
        tooltip:{valueFormatter:(v:unknown)=>observationNumber(Array.isArray(v)?v[1]:v,line.unit)+observationDisplayUnit(line.unit)},
        ...(bar ? {barMaxWidth:12,barGap:'15%'} : {}),
        ...(candle ? {encode:{x:0,y:[1,2,3,4],tooltip:[1,2,3,4]},dimensions:['日期','开盘','收盘','最低','最高'],barMaxWidth:14} : {}),
        symbolSize: 4, connectNulls: false, data, itemStyle: candle ? {color:'#c65761',color0:'#24996f',borderColor:'#c65761',borderColor0:'#24996f'} : { color: line.signed ? (item:{value:unknown})=>{const v=Array.isArray(item.value)?item.value[1]:item.value;return typeof v==='number'&&v<0?'#24996f':'#c65761'} : line.color }, lineStyle: { color: line.color, width: 1.8 },
        markLine: { silent: true, symbol: 'none', data: [...levels.map(level => ({ yAxis: level.value, name: level.name, lineStyle: { color: level.color, type: 'dashed' }, label: { formatter: level.name, color: level.color, position: 'insideEndTop' } })), ...events] } })
    }
  }
  return { animation: false, useUTC:true, color: lines.map(line => line.color), grid, xAxis, yAxis: axes, series,
    title:panels ? panels.map((panel,i)=>({text:panel.title,left:74,top:8+i*190,textStyle:{fontSize:13,fontWeight:'normal',color:palette?.ink ?? '#455569'}})) : pcr ? groups.map((group,index)=>({text:group[0].panel==='price'?group[0].name+' · 红涨绿跌':group[0].panel==='main'?'PCR与通道':'认购 / 认沽数量',left:74,top:triple ? ['0%','32%','67%'][index] : both ? [0,'59%'][index] : 0,textStyle:{fontSize:11,fontWeight:'normal',color:palette?.muted ?? '#647185'}})) : [],
    tooltip: { ...palette?.tooltip, trigger: 'axis', renderMode:'richText', confine: true, valueFormatter:tooltipValue },
    axisPointer: { link: [{ xAxisIndex: 'all' }] }, brush: definition.axis_type === 'tenor' ? undefined : { xAxisIndex: 'all', brushMode: 'single', brushType: 'lineX', transformable: false, throttleType: 'debounce', throttleDelay: 250 },
    toolbox: { right: 55, feature: definition.axis_type === 'tenor' ? {} : { brush: { type: ['lineX', 'clear'] }, restore: {} } },
    legend: { bottom: 4, type: 'scroll', data: lines.map(line => line.name), selected:Object.fromEntries(definition.lines.map(line=>[line.name,!hidden.includes(line.key)])), textStyle: { color: palette?.muted, fontSize: 11 } } }
}

export function ObservationChart({ definition, rows, history, historyLabel = '完整历史', range, hidden, focus, mode, activity, onRange, onHidden }: {
  definition: Definition; rows: Row[]; history?: History; range: Range; hidden: string[]; focus: string; mode: string; activity: string; onRange: (range: Range) => void; onHidden?: (hidden:string[])=>void
  historyLabel?: string // 导航数据的真实身份；组合图传基准名称，省略时表示当前指标的完整历史。
}) {
  const plot = useRef<HTMLDivElement>(null)
  const instance = useRef<ReturnType<typeof echarts.init> | null>(null)
  const navigationCoverage = history && { start: history.coverage.start, end: sourceChartDate(new Date().toISOString()) }
  const theme = useObserverTheme()
  const [brushing, setBrushing] = useState(false)
  const interaction = useRef({ onRange, onHidden, definition, hidden, range })
  interaction.current = { onRange, onHidden, definition, hidden, range }
  // 画布随组件创建与释放；轮询、数据和日期变化只更新同一实例。
  useEffect(() => {
    if (!plot.current) return
    const chart = echarts.init(plot.current)
    instance.current = chart
    chart.on('legendselectchanged',((event:{selected:Record<string,boolean>})=>{
      const latest = interaction.current
      latest.onHidden?.(legendHidden(latest.definition.lines, latest.hidden, event.selected))
    }) as never)
    chart.on('brushEnd', ((event: { areas: { coordRange?: [number, number] }[] }) => {
      const values = event.areas[0]?.coordRange
      if (!values) return
      const selected = brushRange(values,interaction.current.range)
      if (selected) { setBrushing(false); interaction.current.onRange(selected) }
    }) as never)
    const resize = new ResizeObserver(() => chart.resize()); resize.observe(plot.current)
    return () => { resize.disconnect(); chart.dispose(); instance.current = null }
  }, [])
  useEffect(() => {
    const chart = instance.current
    if (!chart || !plot.current) return
    const options=chartOptions(definition, rows, hidden, focus, mode, activity, range, observerChartColors(plot.current))
    // 完整替换选项，保证缩减面板、曲线或切换图形时清除旧配置。
    chart.setOption({...options,legend:{...options.legend,selectedMode:!!onHidden}}, { notMerge: true })
    if (definition.axis_type !== 'tenor' && brushing) chart.dispatchAction({ type: 'takeGlobalCursor', key: 'brush', brushOption: { brushType: 'lineX', brushMode: 'single' } })
  }, [definition, rows, hidden, focus, mode, activity, range.start, range.end, theme, brushing, !!onHidden])
  return <div className="observation-plot" tabIndex={0} role="group" aria-label="图表，方向键缩放和移动日期"
    onPointerDown={event => event.currentTarget.focus({ preventScroll: true })}
    onKeyDown={event => { if (definition.axis_type === 'tenor' || !navigationCoverage || event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) return; const next = keyboardRange(event.key, range, navigationCoverage); if (next) { event.preventDefault(); event.stopPropagation(); interaction.current.onRange(next) } }}>
    {definition.axis_type !== 'tenor' ? <ChartDateControls range={range} coverage={navigationCoverage} onRange={onRange}>
      <button type="button" aria-pressed={brushing} onClick={() => setBrushing(value => !value)}>{brushing ? '取消框选' : '框选日期'}</button>
    </ChartDateControls> : null}
    <div ref={plot} style={definition.panel_groups?{height:definition.panel_groups.length*190+70}:undefined} className={'observation-chart'+(definition.board==='pcr' && focus==='both' ? ' observation-chart-pcr' : '')} />
    {definition.axis_type !== 'tenor' && (history ? <ChartHistoryTrack coverage={history.coverage} range={range} label={historyLabel} /> : <p className="observation-note">历史范围暂不可用</p>)}
  </div>
}
