import {describe,it,expect} from 'vitest'
import {buildGroup} from './MarketObservationGroup'
import {chartOptions} from './ObservationChart'
import {observationNumber,exactObservationValue} from './numbers'
import type {Series} from './types'

const series=(id:string,rows:Series['rows']):Series=>({rows,definition:{id,board:'breadth',label:id,lines:[],field_schema:{},
  source:'合成夹具',source_url:'https://example.invalid',unit:'无量纲',frequency:'交易日日频',
  coverage:{start:String(rows[0]?.date),end:String(rows.at(-1)?.date),observations:rows.length},
  primary_field:'close',parameters:false,formula:'合成样本',reading:'合成样本',limitations:[]},
  total:rows.length,snapshot_id:'a'.repeat(64),dataset_version:'b'.repeat(64),next_cursor:null})
describe('市场观察业务展示',()=>{
  it.each([true,false])('40个真实点的孤立状态%s决定可见标记，连续序列保留简洁曲线',isolated=>{
    const benchmark=Array.from({length:100},(_,index)=>({date:new Date(Date.UTC(2026,0,index+1)).toISOString().slice(0,10),close:3000+index}))
    const rows=(isolated?benchmark.filter((_,index)=>index<80 && index%2===0):benchmark.slice(0,40))
      .map(row=>({date:row.date,known_market_pct:17.3}))
    const metric=series('turnover.gt5.ashare',rows)
    metric.definition.lines=[{key:'known_market_pct',name:'换手占比',unit:'%',color:'#123456',panel:'main',shown:true,formula:'合成',reading:'合成'}]
    const group=buildGroup('turnover','ashare',metric.definition.id,new Map([['market.sh000001',series('market.sh000001',benchmark)],[metric.definition.id,metric]]))!
    expect(chartOptions(group.definition,group.rows,[],'both','fixed_base','all').series[1])
      .toMatchObject({showSymbol:isolated,connectNulls:false})
  })
  it('稀疏指标按自身有效点显示标记，基准和空槽不扩大指标覆盖',()=>{
    const benchmark=Array.from({length:100},(_,index)=>({date:new Date(Date.UTC(2026,0,index+1)).toISOString().slice(0,10),close:3000+index}))
    const metric=series('turnover.gt5.ashare',[{date:String(benchmark.at(-1)!.date),known_market_pct:17.3}])
    metric.definition.lines=[{key:'known_market_pct',name:'换手占比',unit:'%',color:'#123456',panel:'main',shown:true,formula:'合成',reading:'合成'}]
    const group=buildGroup('turnover','ashare',metric.definition.id,new Map([['market.sh000001',series('market.sh000001',benchmark)],[metric.definition.id,metric]]))!
    expect(group.rows).toHaveLength(100)
    const plotted=chartOptions(group.definition,group.rows,[],'both','fixed_base','all').series[1]
    expect(plotted).toMatchObject({showSymbol:true,connectNulls:false})
    expect(group.rows.filter(row=>typeof row['turnover.gt5.ashare|known_market_pct']==='number')).toHaveLength(1)
  })
  it.each([
    ['executive','executive.net.ashare','net_amount_cny',-885123435.815],
    ['earnings','earnings.roe.ashare','mean',8],
    ['turnover','turnover.gt5.ashare','known_market_pct',43],
  ])('组合图%s的真实数值和摘要共用完整指标字段身份',(board,id,field,value)=>{
    const metric=series(String(id),[{date:'2026-10-26',[String(field)]:Number(value)}])
    metric.definition.lines=[{key:String(field),name:'主值',unit:'%',color:'#123456',panel:'main',shown:true,formula:'合成',reading:'合成'}]
    const group=buildGroup(String(board),'ashare',String(id),new Map([
      ['market.sh000001',series('market.sh000001',[{date:'2026-10-26',close:3000}])],[String(id),metric]]))!
    const key=group.definition.lines[1].key
    expect(key).toBe(id+'|'+field)
    expect(group.rows[0][key]).toBe(value)
    expect(chartOptions(group.definition,group.rows,[],'both','fixed_base','all').series[1])
      .toMatchObject({data:[[Date.parse('2026-10-26'),value]]})
    expect(key.slice(0,key.indexOf('|'))).toBe(id)
  })
  it('年报均值和历史水位保持各自面板，上证置于最上方',()=>{
    const financial=series('earnings.roe.shsz',[{date:'2025-12-31',mean:8,historical_percentile:70}])
    const line={unit:'%',color:'#123456',shown:true,formula:'合成',reading:'合成'}
    financial.definition.lines=[{...line,key:'mean',name:'平均ROE',panel:'main'},
      {...line,key:'historical_percentile',name:'历史水位',panel:'context'}]
    const group=buildGroup('earnings','shsz','earnings.roe.shsz',new Map([
      ['market.sh000001',series('market.sh000001',[{date:'2025-12-31',close:3000}])],['earnings.roe.shsz',financial]]))!
    expect(group.definition.panel_groups?.map(panel=>panel.id)).toEqual(['benchmark','metric-main','metric-context'])
    const options=chartOptions(group.definition,group.rows,[],'both','fixed_base','all')
    expect(options.grid).toHaveLength(3)
    expect(options.series[1]).toMatchObject({yAxisIndex:1})
    expect(options.series[2]).toMatchObject({yAxisIndex:2})
  })
  it('原月末稀疏线跳过日频对齐槽，真实年度观察的缺失值保留断线',()=>{
    const sample=series('legacy', [{date:'2026-08-31',value:1},{date:'2026-09-01',value:null},{date:'2026-09-30',value:2}])
    sample.definition.board='valuation'
    sample.definition.lines=[{key:'value',name:'月末观察',unit:'%',color:'#123456',panel:'main',shown:true,formula:'合成',reading:'合成',observed_dates_only:true}]
    const before=chartOptions(sample.definition,sample.rows,[],'both','fixed_base','all')
    expect(before.series[0]).toMatchObject({data:[[Date.parse('2026-08-31'),1],[Date.parse('2026-09-30'),2]]})
    sample.definition.lines[0].observation_dates=sample.rows.map(row=>String(row.date))
    const observed=chartOptions(sample.definition,sample.rows,[],'both','fixed_base','all')
    expect(observed.series[0]).toMatchObject({data:[[Date.parse('2026-08-31'),1],[Date.parse('2026-09-01'),null],[Date.parse('2026-09-30'),2]]})
  })
  it('金额保留负号、量级和可查看的精确原值',()=>{
    expect(observationNumber(-885123435.815,'元')).toBe('-8.8512亿')
    expect(exactObservationValue(-885123435.815,'元')).toBe('-885,123,435.815元')
    expect(observationNumber(2500,'万元')).toBe('2.5千万')
    expect(observationNumber(0,'元')).toBe('0')
    expect(exactObservationValue(1e-21,'元')).toBe('0.000000000000000000001元')
    expect(exactObservationValue(-1e-21,'元')).toBe('-0.000000000000000000001元')
  })
  it('五图共享日期与光标，真实交易日缺口保持断线',()=>{
    const group=buildGroup('breadth','shsz','breadth.shsz',new Map([
      ['market.sh000001',series('market.sh000001',[{date:'2026-10-26',close:3000},{date:'2026-10-28',close:3020}])],
      ['breadth.shsz',series('breadth.shsz',[{date:'2026-10-26',net_advances:1},{date:'2026-10-27',net_advances:2},{date:'2026-10-28',net_advances:3}])],
      ['rana.shsz',series('rana.shsz',[{date:'2026-10-26',rana:5},{date:'2026-10-28',rana:-5}])]
    ]))!
    expect(group.rows[1]['market.sh000001|close']).toBeNull()
    expect(group.rows[1]['rana.shsz|rana']).toBeNull()
    const options=chartOptions(group.definition,group.rows,[],'both','fixed_base','all',{start:'2026-10-26',end:'2026-10-28'})
    expect(options.grid).toHaveLength(5)
    expect(options.xAxis.map(axis=>[(axis as {min?:number}).min,(axis as {max?:number}).max])).toEqual(Array(5).fill([Date.parse('2026-10-26'),Date.parse('2026-10-28')]))
    expect(options.axisPointer.link).toEqual([{xAxisIndex:'all'}])
    expect(options.series.every(item=>!(item as {connectNulls:boolean}).connectNulls)).toBe(true)
    expect(options.series[0]).toMatchObject({data:[[Date.parse('2026-10-26'),3000],[Date.parse('2026-10-27'),null],[Date.parse('2026-10-28'),3020]]})
  })
  it('权威交易日历保留全组同时缺失的交易日，休市日期不生成观察',()=>{
    const benchmark=series('market.sh000001',[{date:'2026-10-26',close:3000},{date:'2026-10-28',close:3020}])
    benchmark.definition.trading_days=['2026-10-26','2026-10-27','2026-10-28']
    const group=buildGroup('breadth','shsz','breadth.shsz',new Map([['market.sh000001',benchmark]]),{start:'2026-10-24',end:'2026-10-28'})!
    expect(group.rows.map(row=>row.date)).toEqual(['2026-10-26','2026-10-27','2026-10-28'])
    expect(group.rows[1]['market.sh000001|close']).toBeNull()
    expect(group.rows[1]['rana.shsz|rana']).toBeNull()
  })
  it('指标仍在读取时可先展示基准，不创建缺少坐标轴字段的空面板',()=>{
    const benchmark=series('market.sh000001',[{date:'2026-10-26',close:3000}])
    const group=buildGroup('executive','ashare','executive.net.ashare',new Map([['market.sh000001',benchmark]]))!
    const options=chartOptions(group.definition,group.rows,[],'both','fixed_base','all',{start:'2026-10-26',end:'2026-10-28'})
    expect(options.grid).toHaveLength(1)
  })
})
