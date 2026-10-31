import { expect, it } from 'vitest'
import { chartOptions } from './ObservationChart'
import type { Definition } from './types'
const definition = {id:'pcr_510050',board:'pcr',frequency:'交易日日频',lines:[
  {key:'close',name:'对应指数日K',unit:'指数点',color:'#c65761',panel:'price',chart_type:'candlestick',shown:true},
  {key:'pcr',name:'日终PCR',unit:'倍',color:'#2768b2',panel:'main',chart_type:'line',shown:true},
  {key:'call_count',name:'认购数量',unit:'张',color:'#c65761',panel:'context',chart_type:'bar',shown:true},
]} as unknown as Definition

it('月度主指标只连接真实观察点，每日指数保留独立日历且零值不丢失',()=>{
  const d={id:'valuation_marketcap_gdp_observed',board:'valuation',frequency:'市值月末与指数日频',primary_field:'ratio',primary_coverage:{end:'2026-10-31'},lines:[
    {key:'ratio',name:'市值/GDP',unit:'倍',panel:'main',observed_dates_only:true},
    {key:'sse_close',name:'上证每日收盘',unit:'指数点',panel:'context'},
  ]} as unknown as Definition
  const rows=Array.from({length:45},(_,i)=>({date:new Date(Date.UTC(2026,8,i+1)).toISOString().slice(0,10),ratio:i===0?0:i===30?.7:null,sse_close:3000+i}))
  const result=chartOptions(d,rows,[],'both','fixed_base','all').series as {name:string;data:number[][];showSymbol:boolean}[]
  expect(result[0].data).toEqual([[Date.parse('2026-09-01'),0],[Date.parse('2026-10-01'),.7]])
  expect(result[1].data).toHaveLength(45)
  expect(result[0].showSymbol).toBe(true)
  expect(result[1].showSymbol).toBe(false)
})
it('PCR为单条日终折线；指数日K和数量柱保留',()=>{
  const options=chartOptions(definition,[{date:'2026-10-16',open:3000,close:3100,low:2900,high:3200,pcr:.6092,pcr_open:9,pcr_high:99,call_count:1000}],[],'both','fixed_base','all')
  const series=options.series as {name:string;type:string;data:number[][]}[]
  expect(series.find(s=>s.name==='日终PCR')).toMatchObject({type:'line',data:[[Date.parse('2026-10-16'),.6092]]})
  expect(series.filter(s=>s.type==='candlestick')).toHaveLength(1)
  expect(series.find(s=>s.name==='对应指数日K')?.data[0].slice(1)).toEqual([3000,3100,2900,3200])
  expect(series.find(s=>s.name==='认购数量')?.type).toBe('bar')
})
