import { cleanup, render } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { Definition } from './types'
import { ObservationChart, chartOptions } from './ObservationChart'

const chart = vi.hoisted(() => ({ setOption: vi.fn(), on: vi.fn(), dispatchAction: vi.fn(), resize: vi.fn(), dispose: vi.fn() }))
const init = vi.hoisted(() => vi.fn(() => chart))
vi.mock('echarts/core', () => ({ use: vi.fn(), init }))
vi.mock('../workspace/observerAppearance', () => ({ useObserverTheme: () => 'light', observerChartColors: () => ({}) }))
beforeEach(() => vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} }))
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals() })

it('市值与GDP比例按万亿元和倍数读轴，坐标范围随实际数据变化',()=>{
  const definition={id:'valuation_marketcap_gdp_latest',board:'valuation',primary_field:'ratio',frequency:'实际观察日',lines:[
    {key:'ratio',name:'市值/GDP',unit:'倍',panel:'main',shown:true,color:'#2768b2'},
    {key:'marketcap_trillion',name:'全A总市值',unit:'万亿元',panel:'context',shown:true,color:'#d69a23'},
  ]} as Definition
  const option=chartOptions(definition,[{date:'2026-11-24',ratio:.803,marketcap_trillion:112.57}],[],'both','fixed_base','all')
  expect(option.yAxis[0]).toEqual(expect.objectContaining({name:'万亿元',position:'left'}))
  expect(option.yAxis[1]).toEqual(expect.objectContaining({name:'倍',position:'right'}))
  expect(option.yAxis[0]).not.toHaveProperty('max')
  expect(option.yAxis[1]).not.toHaveProperty('max')
  expect(option.series).toEqual(expect.arrayContaining([
    expect.objectContaining({name:'全A总市值',yAxisIndex:0,data:[[Date.parse('2026-11-24'),112.57]]}),
    expect.objectContaining({name:'市值/GDP',yAxisIndex:1,data:[[Date.parse('2026-11-24'),.803]]}),
  ]))
})

it('破净率和家数共用上图、分别用百分数与家数轴，下图显示5日变化', () => {
  const definition = { id:'valuation.breaknet',board:'breaknet',primary_field:'ratio',frequency:'交易日日频', lines:[
    {key:'ratio',name:'破净率',unit:'%',panel:'main',color:'#123456',shown:true},
    {key:'broken_count',name:'破净家数',unit:'只',panel:'main',axis:'right',chart_type:'bar',color:'#987654',shown:true},
    {key:'change5',name:'5日变化',unit:'百分点',panel:'context',color:'#456789',shown:true},
  ] } as Definition
  const option = chartOptions(definition,[{date:'2026-11-20',ratio:20,broken_count:600,change5:2}],[],'both','fixed_base','all')
  expect(option.grid).toHaveLength(2)
  expect(option.yAxis).toHaveLength(3)
  expect(option.series).toEqual(expect.arrayContaining([
    expect.objectContaining({name:'破净率',type:'line',xAxisIndex:0,yAxisIndex:0}),
    expect.objectContaining({name:'破净家数',type:'bar',xAxisIndex:0,yAxisIndex:1}),
    expect.objectContaining({name:'5日变化',type:'line',xAxisIndex:1,yAxisIndex:2}),
  ]))
  const lower = chartOptions(definition,[{date:'2026-11-20',ratio:20,broken_count:600,change5:-2}],[],'lower','fixed_base','all')
  expect(lower.yAxis[0]).not.toHaveProperty('min')
})

it('后台父组件刷新和日期变化沿用图表实例，卸载时释放并使用最新交互回调', () => {
  const definition = { id: 'fixture', board: 'valuation', frequency: 'daily', lines: [
    { key: 'value', name: '样本', color: '#123456', unit: '倍', panel: 'main', shown: true },
  ] } as Definition
  const rows = [{ date: '2026-11-20', value: 7 }]
  const range = { start: '2026-11-01', end: '2026-11-22' }
  const onRange = vi.fn(), onHidden = vi.fn()
  const props = { definition, rows, range, hidden: [], focus: 'both', mode: 'fixed_base', activity: 'all', onRange, onHidden }
  const { rerender, unmount } = render(<ObservationChart {...props} />)
  // 状态轮询会让父组件重渲染并生成内容相同的新数组。
  rerender(<ObservationChart {...props} hidden={[]} />)
  expect(init).toHaveBeenCalledOnce()
  expect(chart.dispose).not.toHaveBeenCalled()
  const latestRange = vi.fn(), latestHidden = vi.fn()
  rerender(<ObservationChart {...props} range={{ ...range, start: '2026-11-10' }} onRange={latestRange} onHidden={latestHidden} />)
  expect(init).toHaveBeenCalledOnce()
  // 更新采用完整选项替换，减少面板/曲线时旧配置也退出。
  expect(chart.setOption).toHaveBeenLastCalledWith(expect.any(Object), { notMerge: true })
  chart.on.mock.calls.find(([name]) => name === 'legendselectchanged')![1]({ selected: { '样本': false } })
  expect(latestHidden).toHaveBeenCalledWith(['value'])
  expect(onHidden).not.toHaveBeenCalled()
  chart.on.mock.calls.find(([name]) => name === 'brushEnd')![1]({ areas: [{ coordRange: [Date.parse('2026-11-01'), Date.parse('2026-11-20')] }] })
  expect(latestRange).toHaveBeenCalledWith({ start: '2026-11-10', end: '2026-11-20' })
  unmount()
  expect(chart.dispose).toHaveBeenCalledOnce()
})
