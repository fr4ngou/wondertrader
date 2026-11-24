import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import ObservationShell from './ObservationShell'
import type { Catalog, DataRepair, Definition } from './types'

const charts=vi.hoisted(()=>({last:undefined as {rows:unknown[]}|undefined}))
vi.mock('./ObservationChart', () => ({ ObservationChart: (props:{rows:unknown[]}) => {charts.last=props;return <div>图表已读取</div>} }))
vi.mock('./ExecutiveWeeklyChart', async importOriginal => ({
  ...await importOriginal<typeof import('./ExecutiveWeeklyChart')>(),
  ExecutiveWeeklyChart: () => <div>weekly chart</div>,
}))
const pcrState=vi.hoisted(()=>({partial:false,newer:false,contextOnly:false,referenceFixture:false,stale:false,schedule:null as null|{timezone:string;times:string[]}}))
const coverage = { start:'2022-10-17',end:'2026-10-16',observations:970 }
const definitions = Object.fromEntries([
  ['pcr_510050','pcr','上证50ETF'],['system_c.research','systemc','旧日频候选'],
  ['system_c.weekly.pressure','systemc','恒科价量压力'],['pcr_510300','pcr','沪深300ETF'],
  ['structure.csi2000','structure.csi2000','小盘弹性独强，但成交未接力'],
  ['structure.star50','structure.star50','成交集中度、市场宽度与科创承接'],
  ['structure.ipo_supply','structure.ipo_supply','IPO减持供给压强与科创50折价'],
  ['turnover.gt5.ashare','turnover','换手活跃度 · 沪深北'],
  ['turnover.gt5.shsz','turnover','换手活跃度 · 沪深'],
].map(([id,board,label]) => [id,{id,board,label,frequency:'交易日日频 · 已核四年窗口',coverage,
  parameters:false,lines:[],field_schema:{date:{label:'日期'}},primary_field:'value',limitations:[],source:'测试来源'} as unknown as Definition]))
const catalog:Catalog = {snapshot_id:'a'.repeat(64),published_at:'2026-10-18T00:00:00Z',
  boards:[{id:'pcr',label:'PCR'},{id:'systemc',label:'系统 C'},
    {id:'structure.csi2000',label:'小盘弹性独强，但成交未接力'},
    {id:'structure.star50',label:'成交集中度、市场宽度与科创承接'},
    {id:'structure.ipo_supply',label:'IPO减持供给压强与科创50折价'},{id:'turnover',label:'换手活跃度'}],
  preferences:{default_board:'pcr',default_datasets:{pcr:'pcr_510050',systemc:'system_c.research'}},
  datasets:Object.values(definitions).map(d=>({...d,dataset_version:'b'.repeat(64)}))}
vi.mock('./api',()=>({
  downloadObservation:vi.fn(async()=>new Blob(['fixture'])),
  getCatalog:async()=>pcrState.newer?{...catalog,datasets:catalog.datasets.map(d=>({...d,coverage:{...d.coverage,end:'2026-10-19'}}))}:catalog,
  getDefinition:async(id:string)=>({definition:definitions[id]}),
  getHistory:async()=>({coverage,points:[],raw_count:970,aggregation:'none'}),
  getSeries:vi.fn(async(id:string,_version:string,params:{pcr_type?:string})=>({
    definition:pcrState.partial ? {...definitions[id],parameters:true,primary_field:'pcr',lines:[{key:'pcr',name:'日终PCR',unit:'倍'}]} : definitions[id],
    rows:pcrState.referenceFixture ? id==='csi300_daily.reference' ? [{date:'2026-10-16',close:4000},{date:'2026-10-18',close:4100}] : [{date:'2026-10-16',value:1,sse_close:3000},{date:'2026-10-19',sse_close:3010}] : pcrState.partial ? [{date:'2026-10-16',pcr:params.pcr_type==='volume'?.8:.5,pcr_quality:'partial_reconciled',
      pcr_selected_quality:params.pcr_type==='volume'?'complete_reconciled':'postclose_evidence_missing'}] : pcrState.contextOnly ? [{date:'2026-10-16',value:1},{date:'2026-10-19',sse_close:3000}] : [{date:'2026-10-16',value:1}],
    total:1,next_cursor:null})),
  apiURL:(_path:string,params:Record<string,string>)=>'/exports?'+new URLSearchParams(params),read:async(path:string)=>path.startsWith('reference/')?{profile:{start:'2026-10-16',end:'2026-10-19'}}:pcrState.stale?{scheduler:{enabled:false,state:'not_running_or_stale',last_heartbeat:'2026-10-18T12:30:00+00:00'},schedule:null,runs:[]}:pcrState.newer?{scheduler:{enabled:true,state:'running'},schedule:pcrState.schedule || {timezone:'Asia/Shanghai',times:['08:30','20:30']},runs:[{status:'partial',completed_at:'2026-10-19T12:31:35Z',execution_mode:'scheduled'}]}:{scheduler:{enabled:false},schedule:pcrState.schedule,runs:[]},
}))
afterEach(()=>{cleanup();pcrState.partial=false;pcrState.newer=false;pcrState.contextOnly=false;pcrState.referenceFixture=false;pcrState.stale=false;pcrState.schedule=null;charts.last=undefined;vi.clearAllMocks()})
async function open(initial='/observation?metric=pcr_510050&preset=d30') {
  const query=new QueryClient({defaultOptions:{queries:{retry:false}}})
  const result=render(<QueryClientProvider client={query}><MemoryRouter initialEntries={[initial]}><ObservationShell /></MemoryRouter></QueryClientProvider>)
  if(initial.includes('/quality'))await screen.findByRole('heading',{name:'更新与数据缺口'})
  else {await screen.findByRole('heading',{name:'上证50ETF'});await screen.findByText('图表已读取')}
  return {query,...result}
}
const dates=()=>screen.getByLabelText('当前日期范围').textContent!.split(' 至 ')

it.each(['structure.csi2000','structure.star50','structure.ipo_supply','turnover.gt5.ashare','turnover.gt5.shsz'])('撤下的看板旧链接回退到可用图表：%s',async metric=>{
  await open('/observation?metric='+metric)
  expect(screen.queryByText('小盘弹性独强，但成交未接力')).toBeNull()
  expect(screen.queryByText('成交集中度、市场宽度与科创承接')).toBeNull()
  expect(screen.queryByText('IPO减持供给压强与科创50折价')).toBeNull()
  expect(screen.queryByText(/换手活跃度/)).toBeNull()
})

it('撤下看板不从旧多看板链接、指标说明或导出选择器重新出现',async()=>{
  await open('/observation?boards=structure.csi2000,structure.star50,structure.ipo_supply,turnover,pcr')
  expect(screen.getAllByText('图表已读取')).toHaveLength(1)
  expect(screen.queryByText('小盘弹性独强，但成交未接力')).toBeNull()
  expect(screen.queryByText('成交集中度、市场宽度与科创承接')).toBeNull()
  expect(screen.queryByText('IPO减持供给压强与科创50折价')).toBeNull()
  expect(screen.queryByText(/换手活跃度/)).toBeNull()
  fireEvent.click(screen.getByRole('link',{name:'指标说明'}))
  await screen.findByRole('heading',{name:'指标说明'})
  expect(screen.queryByText('小盘弹性独强，但成交未接力')).toBeNull()
  expect(screen.queryByText('成交集中度、市场宽度与科创承接')).toBeNull()
  expect(screen.queryByText('IPO减持供给压强与科创50折价')).toBeNull()
  expect(screen.queryByText(/换手活跃度/)).toBeNull()
  fireEvent.click(screen.getByRole('link',{name:'导出'}))
  await screen.findByRole('combobox',{name:'导出指标'})
  expect(screen.queryByRole('option',{name:'小盘弹性独强，但成交未接力'})).toBeNull()
  expect(screen.queryByRole('option',{name:'成交集中度、市场宽度与科创承接'})).toBeNull()
  expect(screen.queryByRole('option',{name:'IPO减持供给压强与科创50折价'})).toBeNull()
  expect(screen.queryByRole('option',{name:/换手活跃度/})).toBeNull()
})

it('补齐进度展开后按 ETF 显示缺日范围', async () => {
  const {query}=await open()
  act(()=>query.setQueryData<{data_repair_available?: boolean; data_repair?: DataRepair}>(['observation','updates'], previous=>previous && ({
    ...previous,data_repair_available:true,data_repair:{
      id:'job',state:'running',items:[{
        source_id:'wt.etf_flow',state:'repairing',missing_count:2,reason:null,
        inputs:[{id:'etf_flow.159949',missing_count:2,first_missing:'2026-10-15',last_missing:'2026-10-16'}],
      },{
        source_id:'wt.ipo_supply',state:'repairing',missing_count:1,reason:null,
        inputs:[{id:'structure.ipo_supply.buyback',missing_count:1,first_missing:'2026-10-16',last_missing:'2026-10-16'}],
      }],
    },
  })))
  fireEvent.click(await screen.findByRole('button',{name:'正在补齐'}))
  expect(screen.getByText('创业板50 ETF（159949）')).toBeVisible()
  expect(screen.getByText('2026-10-15 至 2026-10-16')).toBeVisible()
  expect(screen.getByText('缺 2 日')).toBeVisible()
  expect(screen.getByText('披露回购执行增量 · 20 日窗口')).toBeVisible()
})

it('保留观衡定时采集标记且仅计算 WT 检查进度', async () => {
  const {query}=await open()
  act(()=>query.setQueryData<{ data_repair_available: boolean; data_repair: DataRepair }>(['observation','updates'], {
    data_repair_available:true, data_repair:{id:'job',state:'partial',items:[
      {source_id:'wt.etf_flow',state:'complete',missing_count:0,reason:null},
      {source_id:'szse.options',state:'observer_scheduled',missing_count:null,reason:null},
      {source_id:'sse.options',state:'waiting_for_wt',missing_count:null,reason:'wt_source_not_registered'},
    ]},
  }))
  fireEvent.click(await screen.findByRole('button',{name:'补齐完成'}))
  expect(screen.getAllByText('观衡定时采集')).toHaveLength(2)
  expect(screen.getByText('补齐完成 · 1/1 项 WT 来源')).toBeVisible()
  expect(screen.getByRole('progressbar',{name:'已检查 WT 来源'})).toHaveAttribute('max','1')
})

it('进度浮层随 WT 回执显示实际阶段、等待重试及发布后复核', async () => {
  const {query}=await open()
  const receipt=(wt_receipt: DataRepair['wt_receipt']) => act(()=>query.setQueryData(['observation','updates'], {
    data_repair_available:true, runs:[], data_repair:{
      id:'job', state:'running', items:[], wt_request:{dates:['2026-10-16']}, wt_receipt,
    },
  }))
  receipt({state:'running'})
  fireEvent.click(await screen.findByRole('button',{name:'正在补齐'}))
  expect(screen.getByText('WT 正在补采')).toBeVisible()
  receipt({state:'running',phase:'readback'})
  expect(await screen.findByText('WT 正在读取补采结果')).toBeVisible()
  receipt({state:'running',phase:'retry_wait'})
  expect(await screen.findByText('WT 正在等待重试')).toBeVisible()
  receipt({state:'published'})
  expect(await screen.findByText('WT 已发布，正在核对覆盖')).toBeVisible()
})

it('多看板保持各自图表，日期可联动，事件标记在关闭看板后仍可见', async () => {
  const {query}=await open()
  act(()=>query.setQueryData(['observation','catalog',undefined], {
    ...catalog, recent_events: {systemc:{state:'complete',events:[{date:'2026-10-16',label:'观察事件'}]}},
  }))
  fireEvent.click(screen.getByRole('button',{name:'多看板'}))
  fireEvent.click(screen.getByRole('button',{name:/系统 C/}))
  await screen.findByRole('heading',{name:'恒科价量压力'})
  expect(screen.getAllByLabelText('当前日期范围')).toHaveLength(2)
  expect(screen.getAllByLabelText('当前日期范围').map(node=>node.textContent)).toEqual([
    '2026-09-17 至 2026-10-16','2026-09-17 至 2026-10-16',
  ])
  fireEvent.click(screen.getByRole('button',{name:/系统 C/}))
  expect(screen.queryByRole('heading',{name:'恒科价量压力'})).toBeNull()
  expect(screen.getByLabelText('近五个交易日事件：2026-10-16 观察事件')).toBeInTheDocument()
})

it('定时失败记录保留，顶部数据时间取当前实际已发布目录',async()=>{
  const {query,container}=await open()
  act(()=>query.setQueryData(['observation','updates'],{
    scheduler:{enabled:true,state:'running'},
    runs:[{status:'failed',execution_mode:'scheduled',completed_at:'2026-10-17T01:00:00Z'}],
  }))
  await screen.findByText('最近定时更新失败')
  const status=container.querySelector('.observation-auto')
  expect(status).toHaveTextContent('数据发布：'+new Date(catalog.published_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'}))
  expect(status).not.toHaveTextContent(new Date('2026-10-17T01:00:00Z').toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'}))
})

it('年报默认全部年度，切换不相交的日线范围后能直接看到年报，明确URL日期继续保留',async()=>{
  const annual={...definitions.pcr_510050,id:'earnings.eps.shsz',board:'earnings',label:'平均EPS · 沪深年报',
    frequency:'年度年报',coverage:{start:'2021-12-31',end:'2025-12-31',observations:5}}
  definitions[annual.id]=annual
  catalog.boards.push({id:'earnings',label:'盈利与回报'})
  catalog.datasets.push({...annual,dataset_version:'c'.repeat(64),default_preset:'all'})
  catalog.preferences.default_datasets.earnings=annual.id
  try {
    const first=await open()
    expect(dates()).toEqual(['2026-09-17','2026-10-16'])
    fireEvent.click(screen.getByRole('button',{name:'03盈利与回报'}))
    await waitFor(()=>expect(dates()).toEqual(['2021-12-31','2025-12-31']))
    first.unmount()
    const query=new QueryClient({defaultOptions:{queries:{retry:false}}})
    const second=render(<QueryClientProvider client={query}><MemoryRouter initialEntries={['/observation?metric='+annual.id]}><ObservationShell /></MemoryRouter></QueryClientProvider>)
    await waitFor(()=>expect(dates()).toEqual(['2021-12-31','2025-12-31']))
    const {getSeries}=await import('./api')
    await waitFor(()=>expect(vi.mocked(getSeries).mock.calls.at(-1)?.[2]).toEqual(expect.objectContaining({start:'2021-12-31',end:'2025-12-31'})))
    expect(vi.mocked(getSeries).mock.calls.at(-1)?.[2]).not.toHaveProperty('observations')
    second.unmount()
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/observation?metric='+annual.id+'&start=2026-10-01&end=2026-10-16']}><ObservationShell /></MemoryRouter></QueryClientProvider>)
    await waitFor(()=>expect(dates()).toEqual(['2026-10-01','2026-10-16']))
  } finally {
    delete definitions[annual.id];catalog.boards.pop();catalog.datasets.pop();delete catalog.preferences.default_datasets.earnings
  }
})

it('生产持久心跳过期投影显示异常及真实最后心跳',async()=>{
  pcrState.stale=true
  await open()
  expect(await screen.findByText('自动更新心跳已过期，请查看更新与缺口')).toBeInTheDocument()
  expect(screen.getByText(/最近心跳：2026\/10\/18 20:30:00/)).toBeInTheDocument()
  expect(screen.queryByText('自动更新尚未启用')).not.toBeInTheDocument()
})

it('原图对照直接读取固定版本已接纳行，保持参照身份与缺值',async()=>{
  pcrState.referenceFixture=true
  const old=definitions.pcr_510050
  definitions.pcr_510050={...old,board:'valuation',lines:[{key:'sse_close',name:'上证每日收盘',panel:'context'}]} as Definition
  try {
    await open('/observation?metric=pcr_510050&snapshot_id='+catalog.snapshot_id+'&start=2026-10-16&end=2026-10-19')
    fireEvent.click(screen.getByRole('button',{name:'原图对照'}))
    await screen.findByRole('heading',{name:/真实数据对照/})
    await waitFor(()=>expect(charts.last?.rows).toEqual([{date:'2026-10-16',value:1,sse_close:3000},{date:'2026-10-19',sse_close:3010}]))
    vi.stubGlobal('URL',class extends globalThis.URL {static createObjectURL=()=> 'blob:fixture';static revokeObjectURL=()=>{}})
    const click=vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{})
    fireEvent.click(screen.getByRole('button',{name:'导出本次对照JSON'}))
    const {getSeries,downloadObservation}=await import('./api')
    expect(downloadObservation).toHaveBeenCalledWith({metric_id:'pcr_510050',snapshot_id:catalog.snapshot_id,start:'2026-10-16',end:'2026-10-19',format:'json'},expect.any(AbortSignal))
    await waitFor(()=>expect(click).toHaveBeenCalled())
    click.mockRestore();vi.unstubAllGlobals()
    expect(vi.mocked(getSeries).mock.calls.every(args=>args[0]==='pcr_510050' && args[1]===catalog.snapshot_id)).toBe(true)
  } finally {definitions.pcr_510050=old}
})

it.each([true,false])('页首与更新页共同读取配置计划，含不可用=%s',async(configured)=>{
  pcrState.schedule=configured?{timezone:'Asia/Tokyo',times:['09:00','21:00']}:null
  await open('/observation/quality')
  await screen.findByRole('heading',{name:'更新与数据缺口'})
  if(configured){expect(screen.getAllByText(/09:00 \/ 21:00 · Asia\/Tokyo/)).toHaveLength(2)}
  else {expect(screen.getAllByText(/更新时刻配置暂不可用/)).toHaveLength(2)}
  expect(screen.queryByText(/20:30主采/)).not.toBeInTheDocument()
})

it('旧截止保留且明确新末期，用户主动查看最新时保留六个月，部分失败如实显示',async()=>{
  pcrState.newer=true
  await open('/observation?metric=pcr_510050&start=2026-04-16&end=2026-10-16&preset=m6')
  expect(dates()).toEqual(['2026-04-16','2026-10-16'])
  expect(screen.getByText(/资料截至 2026-10-19/)).toBeInTheDocument()
  expect(screen.getByText('自动更新已运行 · 部分来源待补')).toBeInTheDocument()
  expect(screen.getByText(/08:30 \/ 20:30/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button',{name:'查看最新数据'}))
  expect(dates()).toEqual(['2026-04-19','2026-10-19'])
  fireEvent.click(screen.getByRole('button',{name:'02系统 C'}))
  await screen.findByRole('heading',{name:'恒科价量压力'})
  expect(dates()).toEqual(['2026-04-19','2026-10-19'])
})

it('更晚的参照行情不覆盖主指标实际最近数值和日期',async()=>{
  pcrState.contextOnly=true
  const {container}=await open()
  expect(container.querySelector('.observation-last')).toHaveTextContent('2026-10-16')
  expect(container.querySelector('.observation-last')).not.toHaveTextContent('2026-10-19')
  expect(container.querySelector('.observation-last strong')).toHaveTextContent('1')
})

it('共享选定日期跨模块和品种保持，主菜单系统C只有恒科价量压力',async()=>{
  await open(); fireEvent.click(screen.getByRole('button',{name:'6个月'}))
  const selected=dates()
  fireEvent.click(screen.getByRole('button',{name:'02系统 C'}))
  await screen.findByRole('heading',{name:'恒科价量压力'})
  expect(dates()).toEqual(selected)
  expect(screen.queryByRole('option',{name:/旧日频候选/})).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button',{name:'01PCR'}))
  fireEvent.change(screen.getByLabelText('观察口径'),{target:{value:'pcr_510300'}})
  await screen.findByRole('heading',{name:'沪深300ETF'})
  expect(dates()).toEqual(selected)
})

it('日期按钮取得焦点后四方向键连续生效，表单输入保留原生按键',async()=>{
  await open(); const button=screen.getByRole('button',{name:'6个月'})
  fireEvent.click(button);button.focus(); const before=dates()
  fireEvent.keyDown(button,{key:'ArrowUp'})
  await waitFor(()=>expect(dates()).not.toEqual(before)); const zoomed=dates()
  fireEvent.keyDown(window,{key:'ArrowDown'})
  await waitFor(()=>expect(dates()).not.toEqual(zoomed)); const expanded=dates()
  fireEvent.keyDown(window,{key:'ArrowLeft'})
  await waitFor(()=>expect(dates()).not.toEqual(expanded)); const left=dates()
  fireEvent.keyDown(window,{key:'ArrowRight'})
  await waitFor(()=>expect(dates()).not.toEqual(left)); const after=dates()
  expect(screen.queryByLabelText('起始日期')).not.toBeInTheDocument()
  fireEvent.keyDown(screen.getByLabelText('观察口径'),{key:'ArrowUp'})
  expect(dates()).toEqual(after)
})

it('看板主区隐藏内部哈希和核验标签，来源质量中保留可查信息',async()=>{
  await open()
  expect(screen.queryByText(/数据版本 aaaaaaaaaaaa/)).not.toBeInTheDocument()
  expect(screen.queryByText('交易日日频 · 已核四年窗口')).not.toBeInTheDocument()
})

it('持仓成交切换保留日终PCR且没有分钟归档提示',async()=>{
  pcrState.partial=true
  const ui=await open()
  expect(await screen.findByText('日终PCR',{selector:'.observation-last span'})).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('PCR口径'),{target:{value:'volume'}})
  await waitFor(()=>expect(screen.getByLabelText('PCR口径')).toHaveValue('volume'))
  expect(screen.queryByText(/所选区间已归档/)).not.toBeInTheDocument()
  expect(screen.getByText('日终PCR',{selector:'.observation-last span'})).toBeInTheDocument()
  ui.unmount();ui.query.clear()
})


it('重要股东全历史随新快照延长，手选区间保持原日期',async()=>{
  const metric='shareholder.net.ashare'
  const weekly={...definitions.pcr_510050,id:metric,board:'executive',label:'重要股东净减持',
    coverage:{start:'2018-01-01',end:'2026-10-16',observations:3200},primary_field:'net_amount_cny'}
  definitions[metric]=weekly
  catalog.boards.push({id:'executive',label:'股东与高管增减持'})
  catalog.datasets.push({...weekly,dataset_version:'c'.repeat(64),default_preset:'all'})
  catalog.preferences.default_datasets.executive=metric
  const {query}=await open()
  try {
    fireEvent.click(screen.getByRole('button',{name:'03股东与高管增减持'}))
    await waitFor(()=>expect(dates()).toEqual(['2018-01-01','2026-10-16']))
    const newer={...catalog,snapshot_id:'d'.repeat(64),
      datasets:catalog.datasets.map(d=>d.id===metric ? {...d,coverage:{...d.coverage,end:'2026-10-19'}} : d)}
    act(()=>query.setQueryData(['observation','catalog',undefined],newer))
    await waitFor(()=>expect(dates()).toEqual(['2018-01-01','2026-10-19']))
    const {getSeries}=await import('./api')
    const request=()=>vi.mocked(getSeries).mock.calls.at(-1)
    await waitFor(()=>expect(request()).toEqual([metric,newer.snapshot_id,
      expect.objectContaining({start:'2018-01-01',end:'2026-10-19'}),expect.anything()]))
    expect(request()?.[2]).not.toHaveProperty('observations')
    fireEvent.keyDown(window,{key:'ArrowUp'})
    await waitFor(()=>expect(dates()).not.toEqual(['2018-01-01','2026-10-19']))
    const selected=dates()
    act(()=>query.setQueryData(['observation','catalog',undefined],{...newer,snapshot_id:'e'.repeat(64),
      datasets:newer.datasets.map(d=>d.id===metric ? {...d,coverage:{...d.coverage,end:'2026-10-20'}} : d)}))
    await waitFor(()=>expect(dates()).toEqual(selected))
  } finally {
    catalog.boards.pop();catalog.datasets.pop()
    delete definitions[metric];delete catalog.preferences.default_datasets.executive
  }
})
