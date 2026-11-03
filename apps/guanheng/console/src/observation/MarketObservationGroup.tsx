import { useMemo } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { getHistory, getSeries } from './api'
import { ObservationChart } from './ObservationChart'
import { ReadNotice } from './ReadNotice'
import type { Catalog, Definition, Line, Range, Row, Series } from './types'
import { exactObservationValue, observationNumber, observationDisplayUnit } from './numbers'
import './market-group.css'

export const groupedBoard = (board:string) => ['breadth','turnover','earnings','executive'].includes(board)
export const benchmarkMetric='market.sh000001'
const metricName=(id:string)=>id===benchmarkMetric?'上证指数':id.startsWith('msi.')?'MSI累计指标':id.startsWith('rana.')?'RANA':id.startsWith('trin.')?'TRIN阿姆氏指标':id.startsWith('t2108.')?'T2108':id.startsWith('breadth.thrust.')?'Breadth Thrust广度推力':'市场广度'

export function groupDateDomain(catalog:Catalog,board:string,fallback:Definition['coverage']) {
  const metrics=catalog.datasets.filter(item=>item.board===board && item.id!==benchmarkMetric)
  const benchmark=catalog.datasets.find(item=>item.id===benchmarkMetric)
  return {start:metrics.reduce((day,item)=>item.coverage.start<day?item.coverage.start:day,fallback.start),
    end:[...metrics,...(benchmark?[benchmark]:[])].reduce((day,item)=>item.coverage.end>day?item.coverage.end:day,fallback.end),
    observations:metrics.reduce((n,item)=>Math.max(n,item.coverage.observations),fallback.observations)}
}

export function buildGroup(board:string,scope:string,selected:string,data:Map<string,Series>,range?:Range) {
  const benchmark=data.get(benchmarkMetric)
  const template=data.get(selected)||benchmark||data.values().next().value
  if(!template)return
  const rows=new Map<string,Row>();const lines:Line[]=[]
  const panels:NonNullable<Definition['panel_groups']>=[{id:'benchmark',title:'上证指数 · 原始日线'}]
  for(const [id,series] of data)for(const row of series.rows){
    const day=String(row.date);const merged=rows.get(day)||{date:day}
    for(const [key,value] of Object.entries(row))if(key!=='date')merged[id+'|'+key]=value
    rows.set(day,merged)
  }
  function add(id:string,field:string,panel:string,overrides:Partial<Line>={}) {
    const definition=data.get(id)?.definition
    const original=definition?.lines.find(line=>line.key===field)
    lines.push({name:original?.name||definition?.field_schema[field]?.label||field,
      unit:original?.unit||definition?.field_schema[field]?.unit||'无量纲',color:original?.color||'#267b86',
      shown:true,formula:original?.formula||definition?.formula||'',reading:original?.reading||definition?.reading||'',
      ...overrides,key:id+'|'+field,panel})
  }
  add(benchmarkMetric,'close','benchmark',{name:'上证指数',color:'#c65761'})
  if(board==='breadth'){
    panels.push({id:'rana',title:'RANA 红绿柱 / MSI 累计线 · '+(scope==='ashare'?'沪深北':'沪深')},
      {id:'t2108',title:'T2108 · 沪深北合格样本（40期均线上方比例）',min:0,max:100},
      {id:'thrust',title:'Breadth Thrust / 上涨−下跌家数',min:0,max:1},
      {id:'trin',title:'TRIN · 阿姆氏指标',min:0})
    add('rana.'+scope,'rana','rana',{name:'RANA',chart_type:'bar',signed:true,reference_levels:[{value:0,name:'零线',color:'#8993a0'}]})
    add('msi.'+scope,'msi','rana',{name:'MSI',axis:'right',color:'#d68b24'})
    add('t2108.ashare','above_sma40_pct','t2108',{name:'T2108',color:'#805aad',reference_levels:[{value:20,name:'20%',color:'#4f9e76'},{value:80,name:'80%',color:'#bf626c'}]})
    add('breadth.thrust.'+scope,'breadth_thrust','thrust',{name:'Breadth Thrust',color:'#2479b6',reference_levels:[{value:.4,name:'0.40',color:'#4f9e76'},{value:.615,name:'0.615',color:'#bf626c'}]})
    add('breadth.'+scope,'net_advances','thrust',{name:'上涨−下跌家数',unit:'只',chart_type:'bar',signed:true,axis:'right'})
    add('trin.'+scope,'trin','trin',{name:'TRIN',reference_levels:[{value:1,name:'1.00',color:'#8993a0'}]})
  }else{
    const definition=data.get(selected)?.definition
    const originalGroups=new Map<string,Line[]>()
    for(const line of definition?.lines||[]){
      if(line.key==='sse_close'&&definition?.context_source?.table===benchmarkMetric)continue
      const group=originalGroups.get(line.panel)||[];group.push(line);originalGroups.set(line.panel,group)
    }
    for(const [original,group] of originalGroups){
      const panel='metric-'+original
      panels.push({id:panel,title:originalGroups.size>1?group[0].name:definition!.label})
      for(const line of group)add(selected,line.key,panel,{...line,panel,
        observed_dates_only:board==='earnings',
        observation_dates:board==='earnings'?data.get(selected)?.rows.map(row=>String(row.date)):undefined,
        axis:line.axis||(line.unit!==group[0].unit?'right':undefined)})
    }
  }
  const actualDays=[...rows.keys()].sort()
  const start=range?.start||actualDays[0],end=range?.end||actualDays.at(-1)
  const calendar=(benchmark?.definition.trading_days||[]).filter(day=>start&&end&&day>=start&&day<=end)
  const tradingDays=new Set([...calendar,...(benchmark?.rows.map(row=>String(row.date))||[])])
  if(board==='breadth'||board==='turnover')for(const row of rows.values())tradingDays.add(String(row.date))
  for(const day of tradingDays)if(!rows.has(day))rows.set(day,{date:day})
  for(const row of rows.values())if(tradingDays.has(String(row.date)))for(const line of lines){
    if(!line.observed_dates_only && row[line.key]===undefined)row[line.key]=null
  }
  return {definition:{...template.definition,id:'group.'+board,label:board==='breadth'?'完整市场广度':template.definition.label,
      primary_field:lines[1]?.key||lines[0].key,lines,panel_groups:panels,reference_levels:[],price_above:false,overlay:false},
    rows:[...rows.values()].sort((a,b)=>String(a.date).localeCompare(String(b.date)))}
}

export function MarketObservationGroup({catalog,metric,board,range,parameters,onRange}:{
  catalog:Catalog;metric:string;board:string;range:Range;parameters:Record<string,string>;onRange:(range:Range)=>void
}){
  const scope=metric.endsWith('.shsz')?'shsz':'ashare'
  const ids=useMemo(()=>board==='breadth'?[benchmarkMetric,'rana.'+scope,'msi.'+scope,'t2108.ashare',
    'breadth.thrust.'+scope,'breadth.'+scope,'trin.'+scope]:[benchmarkMetric,metric],[board,scope,metric])
  const registered=new Set(catalog.datasets.map(item=>item.id))
  const queries=useQueries({queries:ids.map(id=>({retry:false,enabled:registered.has(id),
    queryKey:['observation','series',id,catalog.snapshot_id,range,parameters],
    queryFn:({signal}:{signal:AbortSignal})=>getSeries(id,catalog.snapshot_id,{...range,...parameters},signal)}))})
  const history=useQuery({retry:false,enabled:registered.has(benchmarkMetric),
    queryKey:['observation','history',benchmarkMetric,catalog.snapshot_id],
    queryFn:({signal})=>getHistory(benchmarkMetric,catalog.snapshot_id,signal)})
  const data=new Map<string,Series>()
  queries.forEach((query,index)=>{if(query.data)data.set(ids[index],query.data)})
  const group=buildGroup(board,scope,metric,data,range)
  const cards=board==='breadth'?[{title:'上证指数',items:[[benchmarkMetric,'close','上证指数']]},
    {title:'RANA 与 MSI',items:[['rana.'+scope,'rana','RANA'],['msi.'+scope,'msi','MSI']]},
    {title:'T2108',items:[['t2108.ashare','above_sma40_pct','40期均线上方比例']]},
    {title:'Breadth Thrust',items:[['breadth.thrust.'+scope,'breadth_thrust','广度推力'],['breadth.'+scope,'net_advances','上涨−下跌家数']]},
    {title:'TRIN',items:[['trin.'+scope,'trin','阿姆氏指标']]}]:(group?.definition.panel_groups||[]).map(panel=>({title:panel.title,
      items:group!.definition.lines.filter(line=>line.panel===panel.id).map(line=>{
        const split=line.key.indexOf('|');return [line.key.slice(0,split),line.key.slice(split+1),line.name]
      })}))
  return <div className="observation-group" data-testid="market-observation-group" aria-busy={queries.some(query=>query.isFetching)}>
    {queries.some(query=>query.isFetching)&&<p role="status">正在读取本组基准与指标…</p>}
    <p className="observation-note">统一日期和光标；每条线保留自己的真实观察日及缺口。{board==='breadth'&&'RANA沿原千倍净上涨比例，MSI以19/39期EMA差累计。'}</p>
    {queries.map((query,index)=><ReadNotice key={ids[index]} label={catalog.datasets.find(item=>item.id===ids[index])?.label||metricName(ids[index])} query={query} />)}
    {ids.filter(id=>!registered.has(id)).map(id=><p key={id} role="status">{metricName(id)} 尚未取得可用结果。</p>)}
    {group?<div className="market-group-layout"><ObservationChart definition={group.definition} rows={group.rows} history={history.data} historyLabel="上证指数导航" range={range}
      hidden={[]} focus="both" mode="fixed_base" activity="all" onRange={onRange}/>
      <aside className="market-group-stats" aria-label="本组最新真实观察">{cards.map(card=><section key={card.title}><h3>{card.title}</h3>{card.items.map(([id,field,label])=>{
        const series=data.get(id);const row=series?.rows.at(-1);const unit=series?.definition.field_schema[field]?.unit;const number=row?.[field]
        return <div key={id+field}><span>{label}</span><strong title={exactObservationValue(number,unit)} className={typeof number==='number'&&number<0?'market-number-down':'market-number-up'}>{number==null?'—':observationNumber(number,unit)}<small>{observationDisplayUnit(unit)}</small></strong><time>{row?.date||'暂无观察'}</time>{id.startsWith('msi.')&&<small>累计起始：{row?.cumulative_start||'尚未满39期'}</small>}</div>
      })}</section>)}</aside></div>:<p>正在读取本组观察…</p>}
    <details className="observation-reading"><summary>本组公式、预热、累计起点与真实覆盖</summary>
      <div className="observation-table-scroll"><table><thead><tr><th>指标</th><th>所选日期内有效数</th><th>完整覆盖</th><th>单位 / 预热 / 起点</th></tr></thead><tbody>
        {ids.map(id=>{const series=data.get(id);const definition=series?.definition;const last=series?.rows.at(-1);const coverage=catalog.datasets.find(item=>item.id===id)?.coverage
          return <tr key={id}><td>{definition?.label||metricName(id)}</td><td>{series?.rows.filter(row=>typeof row[definition!.primary_field]==='number').length??'尚缺'}</td>
            <td>{coverage?`${coverage.start} — ${coverage.end}（${coverage.observations}条）`:'尚缺'}</td><td>{definition?.unit} {id.startsWith('msi.')?`39期预热；本段累计起始 ${last?.cumulative_start||'尚未满39期'}`:id.startsWith('breadth.thrust.')?'10期预热':''}</td></tr>})}
      </tbody></table></div>
      {[...data].filter(([id])=>id!==benchmarkMetric).map(([id,series])=><div key={id}><b>{series.definition.label}</b><p>{series.definition.formula}</p>{series.definition.limitations.map((text,index)=><p key={index}>{text}</p>)}</div>)}
    </details>
  </div>
}
