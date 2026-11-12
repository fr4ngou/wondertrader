import { describe, it, expect } from 'vitest'
import { keyboardRange, latestRange, presetRange } from './dates'
import { brushRange, chartOptions, legendHidden, tooltipValue } from './ObservationChart'
import { defaultMetric } from './presets'

it('最新入口保留预设期限或手工跨度，更新真实末期时不改原选区对象',()=>{
  const domain={start:'2005-01-01',end:'2026-10-19'}
  const range={start:'2026-04-16',end:'2026-10-16'}
  expect(latestRange(range,'m6',domain,domain)).toEqual({start:'2026-04-19',end:'2026-10-19'})
  expect(latestRange({start:'2026-10-10',end:'2026-10-16'},'',domain,domain)).toEqual({start:'2026-10-13',end:'2026-10-19'})
  expect(range).toEqual({start:'2026-04-16',end:'2026-10-16'})
})
import {displayedPrimary,displayedUnit} from './presentation'
import {observationBase} from './deploymentBase'
import type { Catalog, Definition, Row } from './types'

describe('观察日期和图形语义', () => {
  const coverage = { start: '2022-10-17', end: '2026-10-16' }
  it('全部日期只输出查询范围，不把目录观察条数混入严格查询',()=>{
    const annual={start:'2021-12-31',end:'2025-12-31',observations:5}
    expect(presetRange('all',annual.end,annual)).toEqual({start:'2021-12-31',end:'2025-12-31'})
  })
  it('带斜杠和不带斜杠的部署配置生成同一个子路径',()=>{
    expect(observationBase('/qmt/')).toBe('/qmt')
    expect(observationBase('/qmt')).toBe('/qmt')
    expect(observationBase('/')).toBe('')
    expect(observationBase('')).toBe('')
    expect(()=>observationBase('//external.invalid')).toThrow()
    expect(()=>observationBase('/qmt/../other')).toThrow()
  })
  it('各价格模式和隐藏状态保留市场身份；图例状态可重新生成',()=>{
    const definition={id:'cross',board:'crossmarket',primary_field:'hscei_rebased',lines:[
      {key:'a_rebased',name:'上证',unit:'基准100',color:'red',panel:'main'},
      {key:'hscei_rebased',name:'国企',unit:'基准100',color:'green',panel:'main'},
    ]} as Definition
    const rows=[{date:'2026-10-15',hscei_close:8000,a_close:3000,hscei_rebased:80,a_rebased:100},{date:'2026-10-16',hscei_close:8800,a_close:3150,hscei_rebased:88,a_rebased:105}]
    expect(displayedPrimary(definition,rows,'raw_panels')).toBe(8800)
    expect(displayedPrimary(definition,rows,'window_return')).toBeCloseTo(10)
    expect(displayedUnit(definition.lines[0],definition,'raw_panels')).toBe('指数点')
    for(const hidden of [[],['hscei_rebased'],['a_rebased'],['hscei_rebased','a_rebased']]){
      for(const mode of ['fixed_base','window_return','raw_panels']){
        const options=chartOptions(definition,rows,hidden,'both',mode,'all')
        expect(options.legend.selected['上证']).toBe(!hidden.includes('a_rebased'))
        expect(options.legend.selected['国企']).toBe(!hidden.includes('hscei_rebased'))
        const sse=options.series.find(s=>(s as {name:string}).name==='上证')
        const hs=options.series.find(s=>(s as {name:string}).name==='国企')
        expect(sse).toMatchObject({data:[[Date.parse(rows[0].date),mode==='raw_panels'?3000:mode==='window_return'?0:100],[Date.parse(rows[1].date),mode==='raw_panels'?3150:mode==='window_return'?expect.closeTo(5):105]]})
        expect(hs).toMatchObject({data:[[Date.parse(rows[0].date),mode==='raw_panels'?8000:mode==='window_return'?0:80],[Date.parse(rows[1].date),mode==='raw_panels'?8800:mode==='window_return'?expect.closeTo(10):88]]})
      }
    }
    const hidden=legendHidden(definition.lines,[],{'国企':false,'上证':true})
    expect(hidden).toEqual(['hscei_rebased'])
    expect(chartOptions(definition,rows,hidden,'both','raw_panels','all').legend.selected).toMatchObject({'国企':false,'上证':true})
    expect(legendHidden(definition.lines,hidden,{'国企':true})).toEqual([])
  })
  it('期指默认进入四品种持仓，来源快照可显式指定默认口径',()=>{
    const catalog={preferences:{default_datasets:{}},datasets:[{id:'basis_ic',board:'cffex'},{id:'cffex_if',board:'cffex'}]} as unknown as Catalog
    expect(defaultMetric(catalog,'cffex')).toBe('cffex_if')
    catalog.preferences.default_datasets.cffex='basis_ic'
    expect(defaultMetric(catalog,'cffex')).toBe('basis_ic')
    expect(defaultMetric(catalog,'unknown')).toBeUndefined()
  })
  it('默认30天包含截止日，所有预设不修改全历史范围', () => {
    expect(presetRange('d30', coverage.end, coverage)).toEqual({ start: '2026-09-17', end: '2026-10-16' })
    expect(presetRange('unknown', coverage.end, coverage)).toEqual(presetRange('d30',coverage.end,coverage))
    expect(presetRange('y4', coverage.end, coverage)).toEqual(coverage)
    expect(presetRange('d15', coverage.end, coverage).start).toBe('2026-10-02')
    expect(presetRange('m6', '2024-08-31', coverage).start).toBe('2024-02-29')
    expect(coverage).toEqual({ start: '2022-10-17', end: '2026-10-16' })
  })
  it('上下缩放、左右平移在完整边界内', () => {
    const range = presetRange('d30', coverage.end, coverage)
    const up = keyboardRange('ArrowUp', range, coverage)!
    expect(Date.parse(up.end) - Date.parse(up.start)).toBeLessThan(Date.parse(range.end) - Date.parse(range.start))
    expect(keyboardRange('ArrowRight', range, coverage)).toEqual(range)
    expect(keyboardRange('ArrowLeft', range, coverage)!.end).toBe('2026-10-10')
    expect(keyboardRange('Enter', range, coverage)).toBeNull()
  })
  it('近五日包含当天，三个月按公历和月末回退', () => {
    expect(presetRange('d5', '2026-11-12')).toEqual({ start: '2026-11-08', end: '2026-11-12' })
    expect(presetRange('m3', '2026-11-12')).toEqual({ start: '2026-08-12', end: '2026-11-12' })
    expect(presetRange('m3', '2024-05-31')).toEqual({ start: '2024-02-29', end: '2024-05-31' })
  })
  it('双轴颜色和图线一致，并保留空值', () => {
    const definition = { id: 'pb_shsz_daily', board: 'pb', primary_field: 'equal_pb', lines: [
      { key: 'equal_pb', name: 'PB', color: '#2768b2', unit: '倍', panel: 'main', shown: true },
      { key: 'sse_reference', name: '上证', color: '#c65761', unit: '指数点', panel: 'context', shown: true },
    ] } as Definition
    const option = chartOptions(definition, [{ date: '2026-10-16', equal_pb: null, sse_reference: 3000 }], [], 'both', 'fixed_base', 'all')
    expect(option.yAxis[0]).toMatchObject({ axisLabel: { color: '#2768b2' } })
    expect(option.yAxis[1]).toMatchObject({ axisLabel: { color: '#c65761' } })
    expect(option.series[0]).toMatchObject({ data: [[Date.parse('2026-10-16'),null]], connectNulls: false })
  })
  it('时间轴直接连接实际观察，周末不插空值，真实缺失保留null', () => {
    const definition = {id:'example',board:'bond',primary_field:'x',lines:[{key:'x',name:'观察',color:'#2768b2',unit:'%',panel:'main'}]} as Definition
    const option = chartOptions(definition,[{date:'2026-10-09',x:2},{date:'2026-10-12',x:4},{date:'2026-10-13',x:null},{date:'2026-10-14',x:5}],[],'both','fixed_base','all',{start:'2026-10-08',end:'2026-10-15'})
    expect(option.xAxis[0]).toMatchObject({type:'time',min:Date.parse('2026-10-08'),max:Date.parse('2026-10-15')})
    expect(option.series[0]).toMatchObject({data:[[Date.parse('2026-10-09'),2],[Date.parse('2026-10-12'),4],[Date.parse('2026-10-13'),null],[Date.parse('2026-10-14'),5]],connectNulls:false})
    expect(brushRange([Date.parse('2026-10-12')+3600000,Date.parse('2026-10-09')],{start:'2026-10-08',end:'2026-10-15'})).toEqual({start:'2026-10-09',end:'2026-10-12'})
  })
  it('上下图共享真实日期；混合频率叠加按各自的观察日连接', () => {
    const definition = { id: 'mixed', board: 'example', primary_field: 'monthly', lines: [
      { key: 'monthly', name: '月度', color: '#2768b2', unit: '%', panel: 'main' },
      { key: 'daily', name: '日度', color: '#c65761', unit: '点', panel: 'context' },
    ] } as Definition
    const rows: Row[] = [{date:'2026-08-31',monthly:2,daily:100},{date:'2026-09-01',daily:101},{date:'2026-09-30',monthly:3,daily:102}]
    const range = {start:'2026-08-30',end:'2026-10-01'}
    const option = chartOptions(definition,rows,[],'both','fixed_base','all',range)
    expect(option.xAxis).toHaveLength(2)
    for (const axis of option.xAxis) expect(axis).toMatchObject({type:'time',min:Date.parse(range.start),max:Date.parse(range.end)})
    expect(option.series[0]).toMatchObject({xAxisIndex:0,data:[[Date.parse('2026-08-31'),2],[Date.parse('2026-09-30'),3]],connectNulls:false})
    expect(option.series[1]).toMatchObject({xAxisIndex:1,data:[[Date.parse('2026-08-31'),100],[Date.parse('2026-09-01'),101],[Date.parse('2026-09-30'),102]]})
    const overlay = chartOptions({...definition,overlay:true},rows,[],'both','fixed_base','all',range)
    expect(overlay.xAxis).toHaveLength(1)
    expect(overlay.series[0]).toMatchObject({data:[[Date.parse('2026-08-31'),2],[Date.parse('2026-09-30'),3]]})
  })
  it('周K使用开收低高原值，独立上图保留时间轴',()=>{
    const definition={id:'weekly',board:'systemc',price_above:true,primary_field:'pressure',lines:[
      {key:'pressure',name:'压力',panel:'main',color:'#2768b2',unit:'无量纲'},
      {key:'close',name:'上证周K',panel:'context',color:'#c65761',unit:'点',chart_type:'candlestick'},
    ]} as Definition
    const option=chartOptions(definition,[{date:'2026-10-09',open:3000,close:3100,low:2900,high:3200,pressure:2}],[],'both','fixed_base','all')
    expect(option.series[0]).toMatchObject({type:'candlestick',xAxisIndex:0,data:[[Date.parse('2026-10-09'),3000,3100,2900,3200]],encode:{x:0,y:[1,2,3,4]}})
    expect(option.series[1]).toMatchObject({type:'line',xAxisIndex:1,data:[[Date.parse('2026-10-09'),2]]})
  })
  it('PCR三层共用日期，指数K线保留OHLC，认购认沽使用柱状且单图可放大',()=>{
    const definition={id:'pcr',board:'pcr',primary_field:'pcr',lines:[
      {key:'close',name:'上证50日K',panel:'price',unit:'指数点',color:'#c65761',chart_type:'candlestick'},
      {key:'pcr',name:'PCR',panel:'main',unit:'倍',color:'#2768b2'},
      {key:'call_count',name:'认购Call',panel:'context',unit:'张',color:'#c65761',chart_type:'bar'},
      {key:'put_count',name:'认沽Put',panel:'context',unit:'张',color:'#24996f',chart_type:'bar'},
    ]} as Definition
    const rows=[{date:'2026-10-16',open:2800,close:2850,low:2750,high:2900,pcr:.6,call_count:100,put_count:60}]
    const range={start:'2026-10-01',end:'2026-10-16'}
    const option=chartOptions(definition,rows,[],'both','fixed_base','all',range)
    expect(option.tooltip).toMatchObject({renderMode:'richText',confine:true})
    expect(tooltipValue(.123456789)).toBe('0.1235')
    expect(tooltipValue(null)).toBe('不可用')
    expect(option.grid).toHaveLength(3)
    for(const axis of option.xAxis)expect(axis).toMatchObject({min:Date.parse(range.start),max:Date.parse(range.end)})
    expect(option.series[0]).toMatchObject({type:'candlestick',xAxisIndex:0,data:[[Date.parse('2026-10-16'),2800,2850,2750,2900]]})
    expect(option.series[1]).toMatchObject({type:'line',xAxisIndex:1})
    expect(option.series[2]).toMatchObject({type:'bar',xAxisIndex:2})
    expect(option.series[3]).toMatchObject({type:'bar',xAxisIndex:2})
    expect(chartOptions(definition,rows,[],'lower','fixed_base','all',range).series).toHaveLength(2)
    expect(chartOptions(definition,rows,[],'upper','fixed_base','all',range).series).toHaveLength(1)
  })
})
