import { WorkspaceDock } from '../workspace/WorkspaceDock'
import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { NavLink, useLocation, useSearchParams } from 'react-router-dom'
import brand from '../../config/project-branding.json'
import { getCatalog, getDefinition, getHistory, getSeries, read } from './api'
import { ObservationChart } from './ObservationChart'
import { DataAssets } from './DataAssets'
import { ObservationExports } from './ObservationExports'
import { ObservationDownload } from './ObservationDownload'
import { T2108Coverage, sourceTypeLabel, methodVersionLabel } from './T2108Coverage'
import { ReadNotice } from './ReadNotice'
import { FieldCoverage } from './FieldCoverage'
import { keyboardRange, latestRange, presetRange, presets } from './dates'
import { sourceChartDate } from '../sourceChartPresentation'
import { ChartHistoryTrack } from '../components/ChartHistoryTrack'
import { boardDatasets, defaultMetric } from './presets'
import {statusLabel,sourceLabel,failureLabel,displayedUnit,displayedPrimary,automaticUpdateLabel,localSchedulerLabel,frequencyLabel} from './presentation'
import type { Catalog, Definition, Range, Row, Series } from './types'
import './observation.css'
import { exactObservationValue, observationNumber, observationDisplayUnit } from './numbers'
import { MarketObservationGroup, groupedBoard, groupDateDomain } from './MarketObservationGroup'
import { ExecutiveWeeklyChart, isExecutiveNet, isShareholderNet } from './ExecutiveWeeklyChart'

const value = (v: unknown, key?: string) => key === 'source_kind' ? sourceTypeLabel(v) : key === 'method_version' ? methodVersionLabel(v) : typeof v === 'number' ? new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 4 }).format(v) : v == null ? '不可用' : String(v)
function Message({ children, retry }: { children: ReactNode; retry?: () => void }) {
  return <div className="observation-message" role="status"><p>{children}</p>{retry && <button onClick={retry}>重新读取</button>}</div>
}

export default function ObservationShell({ appearance, embedded = false }: { appearance?: ReactNode; embedded?: boolean }) {
  const [search] = useSearchParams(); const pinned = search.get('snapshot_id') || undefined
  const catalog = useQuery({ retry: false, queryKey: ['observation', 'catalog', pinned], queryFn: ({ signal }) => getCatalog(signal, pinned), refetchInterval: pinned ? false : 60000 })
  const runtime = useQuery({ retry: false, queryKey: ['observation', 'updates'], queryFn: ({ signal }) => read<{ scheduler: { enabled: boolean;state?:string;last_heartbeat?:string|null };process?:{state:string;label:string;error?:string|null};schedule?:{timezone:string;times:string[]}|null;runs?:{status:string;completed_at:string;execution_mode?:string}[] }>('updates', {}, signal), refetchInterval: 60000 })
  const runtimeData=runtime.data
  const latestRun=runtimeData?.runs?.find(run=>run.execution_mode==='scheduled')
  const location = useLocation(); const remote = import.meta.env.VITE_OBSERVATION_ONLY === 'true'
  const path = location.pathname; const tab = path.endsWith('/data') ? 'data' : path.endsWith('/quality') ? 'quality' : path.endsWith('/api') ? 'api' : 'boards'
  return <div className="guanheng">
    <aside className="observation-sidebar"><NavLink className="observation-brand" to="/observation">{brand.short_name}<small>{brand.display_name}</small></NavLink>
      {!remote && <><a href="/dashboard">总览</a><a href="/market">行情</a></>}
      <NavLink className="observation-current" to="/observation">市场观察</NavLink>
      {!remote && <><a href="/strategies">策略</a><a href="/orders">交易记录</a><a href="/operations">系统状态</a></>}
      <div className="observation-sidebar-note">行情与市场观察<br />交易执行保持隔离</div>
    </aside>
    <main className="observation-workspace">{appearance ? <div className="observation-appearance">{appearance}</div> : null}<header className="observation-page-heading"><div>{embedded ? <h1>市场观察</h1> : <><span className="observation-eyebrow">市场观察</span><h1>衡量市场的位置与变化</h1></>}</div><details className="observation-auto"><summary>{runtime.isError ? '自动更新状态暂不可用' : runtime.isPending ? '正在检查更新状态…' : automaticUpdateLabel(runtimeData?.scheduler,latestRun?.status)}</summary><small>{runtimeData && <>{localSchedulerLabel(runtimeData.process)}<br /></>}{runtimeData?.schedule ? `${runtimeData.schedule.times.join(' / ')} · ${runtimeData.schedule.timezone==='Asia/Shanghai'?'北京时间':runtimeData.schedule.timezone}` : '更新时刻配置暂不可用'}{runtimeData?.scheduler?.last_heartbeat && <><br />最近心跳：{new Date(runtimeData.scheduler.last_heartbeat).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'})}</>}{catalog.data && <><br />数据发布：{new Date(catalog.data.published_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'})}</>}</small></details></header>
      <nav className="observation-tabs" aria-label="市场观察页面">{[['boards', '', '看板'], ['data', '/data', '指标说明'], ['quality', '/quality', '更新与缺口'], ['api', '/api', '导出']].map(([id, suffix, label]) => <NavLink key={id} className={tab === id ? 'active' : ''} to={'/observation' + suffix + location.search}>{label}</NavLink>)}</nav>
      <ReadNotice label="更新状态" query={runtime} />
      <ReadNotice label="观察目录" query={catalog} />
      {!catalog.data ? catalog.isPending ? <Message>正在读取观察数据目录…</Message> : null : <>
        {tab !== 'boards' && <p className="observation-note">数据发布于 {new Date(catalog.data.published_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}</p>}
        {tab === 'boards' && (catalog.data.datasets.length ? <Boards catalog={catalog.data} /> : <Message>观察目录已连接，当前尚无已接纳的数据集。请查看更新与缺口。</Message>)}
        {tab === 'data' && <DataAssets key={catalog.data.snapshot_id} catalog={catalog.data} />}
        {tab === 'quality' && <Quality catalog={catalog.data} schedule={runtimeData?.schedule} />}
        {tab === 'api' && <ObservationExports key={catalog.data.snapshot_id} catalog={catalog.data} />}
      </>}
    </main>
  </div>
}

function Boards({ catalog }: { catalog: Catalog }) {
  const [search, setSearch] = useSearchParams()
  const requested = search.get('metric') || defaultMetric(catalog,catalog.preferences.default_board)
  const available = boardDatasets(catalog)
  const requestedBoard = catalog.datasets.find(d => d.id === requested)?.board
  const dataset = available.find(d => d.id === requested) || available.find(d=>d.id===defaultMetric(catalog,requestedBoard || catalog.preferences.default_board)) || available[0]
  const [detail, setDetail] = useState('rows')
  const focus = search.get('focus') || 'both'; const mode = search.get('mode') || 'fixed_base'; const activity = search.get('activity') || 'all'
  const [futuresMatrix, setFuturesMatrix] = useState(true)
  const weeklyExecutive = isExecutiveNet(dataset.id)
  const defaultPreset = weeklyExecutive ? 'all' : dataset.default_preset || 'd30'
  const coverage = !weeklyExecutive && groupedBoard(dataset.board) ? groupDateDomain(catalog, dataset.board, dataset.coverage) : dataset.coverage
  const today = sourceChartDate(new Date().toISOString())
  const dateDomain = { start: coverage.start, end: today }
  const selectedPreset = search.get('preset') || (search.get('start') ? '' : defaultPreset)
  const range = isShareholderNet(dataset.id) && selectedPreset === 'all' ? presetRange('all', coverage.end, coverage)
    : search.get('start') && search.get('end') ? { start: search.get('start')!, end: search.get('end')! }
    : presetRange(selectedPreset || defaultPreset, coverage.end, coverage)
  const parameters = { window: search.get('window') || (dataset.board === 'spread' ? '756' : '20'), k: search.get('k') || '2', method: search.get('method') || 'sma', pcr_type: search.get('pcr_type') || 'oi' }
  const definition = useQuery({ retry: false, queryKey: ['observation', 'definition', dataset.id, catalog.snapshot_id], queryFn: ({ signal }) => getDefinition(dataset.id, catalog.snapshot_id, signal) })
  const history = useQuery({ retry: false, queryKey: ['observation', 'history', dataset.id, catalog.snapshot_id], queryFn: ({ signal }) => getHistory(dataset.id, catalog.snapshot_id, signal) })
  const series = useQuery({ retry: false, queryKey: ['observation', 'series', dataset.id, catalog.snapshot_id, range, parameters], queryFn: ({ signal }) => getSeries(dataset.id, catalog.snapshot_id, { ...range, ...parameters }, signal) })
  const updateRange = (next: Range, preset = '') => {
    const nextSearch = new URLSearchParams(search); nextSearch.set('metric', dataset.id); nextSearch.set('start', next.start); nextSearch.set('end', next.end); nextSearch.set('preset', preset)
    setSearch(nextSearch, { replace: true })
  }
  const select = (id: string) => {
    const next=available.find(item=>item.id===id)!
    const outside=range.end<next.coverage.start || range.start>next.coverage.end
    const openWeekly = isExecutiveNet(next.id) && (!weeklyExecutive || next.id !== dataset.id && isShareholderNet(next.id))
    const preset = openWeekly ? 'all' : outside ? next.default_preset || 'd30' : selectedPreset
    const nextRange = openWeekly || outside ? presetRange(preset, next.coverage.end, next.coverage) : range
    setSearch({ metric:id,start:nextRange.start,end:nextRange.end,preset,...(search.get('snapshot_id') ? {snapshot_id:search.get('snapshot_id')!} : {}) })
    setDetail('rows')
  }
  const parameter = (key: string, input: string) => { const next = new URLSearchParams(search); next.set('metric', dataset.id); next.set(key, input); setSearch(next, { replace: true }) }
  const originalDefinition = series.data?.definition || definition.data?.definition
  const d = useMemo(()=> originalDefinition?.board==='systemc' ? {...originalDefinition,label:dataset.label,
    lines:originalDefinition.lines.map(line=>line.key===originalDefinition.primary_field?{...line,name:dataset.label}:line)} : originalDefinition,
    [originalDefinition,dataset.label])
  const hidden = search.has('hidden') ? (search.get('hidden') || '').split(',').filter(Boolean) : d?.lines.filter(line => line.shown === false).map(line => line.key) || []
  const shownLines = d?.lines.filter(line=>dataset.board!=='crossmarket' || mode!=='raw_panels' || ['hscei_rebased','a_rebased'].includes(line.key)) || []
  const primaryRows=d ? series.data?.rows.filter(row=>typeof row[d.primary_field]==='number') : undefined
  const last = primaryRows?.at(-1)
  const primaryLine=d?.lines.find(line=>line.key===d.primary_field)
  const primaryUnit=d&&primaryLine?displayedUnit(primaryLine,d,mode):d?.unit
  const shareholder = isShareholderNet(dataset.id)
  const primary = shareholder && typeof last?.net_amount_cny === 'number' ? -last.net_amount_cny
    : d && primaryRows ? displayedPrimary(d, primaryRows, mode) : undefined
  useEffect(()=>{
    if(d?.axis_type==='tenor')return
    const keydown=(event:KeyboardEvent)=>{
      const target=event.target
      if(event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey ||
        target instanceof Element && target.closest('input,select,textarea,[contenteditable]:not([contenteditable="false"]),[role="dialog"],.observation-plot,.observation-table-scroll'))return
      const next=keyboardRange(event.key,range,dateDomain)
      if(next){event.preventDefault();if(next.start!==range.start||next.end!==range.end)updateRange(next)}
    }
    window.addEventListener('keydown',keydown)
    return()=>window.removeEventListener('keydown',keydown)
  },[d?.axis_type,dateDomain.start,dateDomain.end,range.start,range.end,search])
  return <>
    <div className="observation-board-nav">{catalog.boards.filter(board => board.id !== 'pending').map((board, index) => <button key={board.id} className={dataset.board === board.id ? 'active' : ''} disabled={!defaultMetric(catalog,board.id)} onClick={() => select(defaultMetric(catalog,board.id)!)}><small>{String(index + 1).padStart(2, '0')}</small>{board.label}</button>)}</div>
    <section className="observation-panel observation-controls"><label>查看指标<select aria-label="观察口径" value={dataset.id} onChange={e => select(e.target.value)}>{available.filter(v => v.board === dataset.board).map(v => <option key={v.id} value={v.id}>{v.label}</option>)}</select></label>
      {d?.axis_type !== 'tenor' ? <div className="observation-presets" role="group" aria-label="快捷日期">{presets.map(([key, label]) =>
        <button key={key} aria-pressed={selectedPreset === key} className={selectedPreset === key ? 'active' : ''}
          onClick={() => updateRange(presetRange(key, today, key==='all'?coverage:undefined), key)}>{label}</button>)}</div> : null}
      <span className="observation-note" aria-label="当前日期范围">{range.start} 至 {range.end}</span>
      <p className="observation-note">资料截至 {dataset.coverage.end}{dataset.board==='executive' && ' · 已披露资料，非盘中实时'}{d?.primary_coverage?.end && d.primary_coverage.end!==dataset.coverage.end && ` · 主指标截至 ${d.primary_coverage.end}`} {range.end<dataset.coverage.end && <button onClick={()=>updateRange(latestRange(range,selectedPreset,dataset.coverage,dateDomain),selectedPreset)}>查看最新数据</button>}</p>
    </section>
    <WorkspaceDock layoutId="observation" primaryTitle="指标图" secondaryTitle="原始数据与原图" side="below"
      primary={<section className="observation-panel"><div className="observation-chart-title"><div><h2>{groupedBoard(dataset.board)?catalog.boards.find(board=>board.id===dataset.board)?.label:dataset.label}</h2><p className="observation-note">所选日期内 {series.data?.total ?? '…'} 条记录</p></div><div className="observation-last"><span>{shareholder ? '最新日可计价净减持' : primaryLine?.name}</span><strong title={last&&d?exactObservationValue(primary,primaryUnit):undefined}>{last && d ? observationNumber(primary,primaryUnit) : '—'} <small>{d && primaryLine ? observationDisplayUnit(displayedUnit(primaryLine,d,mode)) : ''}</small></strong><span>{last?.date}</span></div></div>
      {d?.id==='t2108.ashare' && <T2108Coverage row={last} definitionVersion={d.definition_version} mixedMethods={new Set(series.data?.rows.map(row=>row.method_version || d.definition_version || 'unregistered')).size>1} />}
      <FieldCoverage metric={dataset.id} row={series.data?.rows.at(-1)} />
      {d?.parameters && <div className="observation-inline"><label>窗口<input aria-label="计算窗口" type="number" min="2" max="2000" value={parameters.window} onChange={e => parameter('window', e.target.value)} /></label><label>倍数<input aria-label="通道倍数" type="number" min="0" max="10" step="0.5" value={parameters.k} onChange={e => parameter('k', e.target.value)} /></label><select aria-label="通道算法" value={parameters.method} onChange={e => parameter('method', e.target.value)}><option value="sma">算术均值</option><option value="ema">EMA中心</option><option value="ema_moments">EMA矩通道</option></select>{dataset.board === 'pcr' && <select aria-label="PCR口径" value={parameters.pcr_type} onChange={e => parameter('pcr_type', e.target.value)}><option value="oi">持仓</option><option value="volume">成交</option></select>}</div>}
      {!groupedBoard(dataset.board) && <div className="observation-inline">{(dataset.board==='pcr' ? [['both','三图联动'],['upper','只看PCR'],['lower','放大认购/认沽']] : [['both', '上下图'], ['upper', '只看上图'], ['lower', '放大下图']]).map(([id, label]) => <button key={id} className={focus === id ? 'active' : ''} onClick={() => parameter('focus',id)}>{label}</button>)}
        {dataset.board === 'crossmarket' && <><select aria-label="价格比较模式" value={mode} onChange={e => parameter('mode',e.target.value)}><option value="fixed_base">固定基准100</option><option value="window_return">区间涨幅</option><option value="raw_panels">原始点位分图</option></select><select aria-label="成交市场" value={activity} onChange={e => parameter('activity',e.target.value)}><option value="all">两个市场成交</option><option value="a_activity">只看上证成交</option><option value="hscei_activity">只看国企成交</option></select></>}
        {dataset.board === 'cffex' && dataset.id.startsWith('cffex_') && <button onClick={() => setFuturesMatrix(!futuresMatrix)}>{futuresMatrix ? '切换单项详细' : '四品种2×2'}</button>}
      </div>}
      <ReadNotice label="指标数据" query={series} /><ReadNotice label="历史导航" query={history} /><ReadNotice label="指标说明" query={definition} />
      {weeklyExecutive ? (series.data ? <><ExecutiveWeeklyChart catalog={catalog} data={series.data} range={range} navigationCoverage={dateDomain} onRange={updateRange} /><ChartHistoryTrack coverage={coverage} range={range} /></> : series.isPending ? <Message>正在读取周度净减持…</Message> : null) : groupedBoard(dataset.board) ? <MarketObservationGroup catalog={catalog} metric={dataset.id} board={dataset.board} range={range} parameters={parameters} onRange={updateRange}/> : dataset.board === 'cffex' && dataset.id.startsWith('cffex_') && futuresMatrix ? <div className="observation-matrix">{['if', 'ih', 'ic', 'im'].map(product => <FuturesCard key={product} product={product} version={catalog.snapshot_id} range={range} onRange={updateRange} />)}</div> : !series.data || !d ? series.isPending ? <Message>正在读取所选窗口…</Message> : null : !series.data.rows.length ? <><Message>所选日期没有已发布观察。休市和未披露日期保持空值。</Message><ChartHistoryTrack coverage={coverage} range={range} /></> : <>
        {<ObservationChart definition={d} rows={series.data.rows} history={history.data} range={range} hidden={hidden} focus={focus} mode={mode} activity={activity} onRange={updateRange} onHidden={keys=>parameter('hidden',keys.join(','))} />}
        {dataset.board === 'crossmarket' && <p className="observation-note">本窗口国企涨幅 {change(series.data.rows, 'hscei_close')}，上证涨幅 {change(series.data.rows, 'a_close')}。</p>}
        <div className="observation-line-toggles">{shownLines.map(line => <label key={line.key}><input type="checkbox" checked={!hidden.includes(line.key)} onChange={() => parameter('hidden', hidden.includes(line.key) ? hidden.filter(key => key !== line.key).join(',') : [...hidden, line.key].join(','))} /><i style={{ background: line.color }} />{line.name} · {d && displayedUnit(line,d,mode)}</label>)}</div>
      </>}
      {d && <details className="observation-reading"><summary>怎么看这张图 · 点击展开</summary><p><b>{d.how_to_read?.purpose || d.reading}</b></p>{d.how_to_read?.signals.map((signal, i) => <p key={i}>{signal}</p>)}<p>{d.how_to_read?.example}</p><p>{d.how_to_read?.boundary}</p>{d.lines.map(line => <p key={line.key}><b style={{ color: line.color }}>{line.name}（{line.unit}）</b>：{line.reading}</p>)}</details>}
      {d?.term_notes?.length ? <details className="observation-reading"><summary>名词小备注 · 点击展开</summary><dl>{d.term_notes.map(note => <div key={note.term}><dt>{note.term}</dt><dd>{note.note}</dd></div>)}</dl></details> : null}
    </section>}
    secondary={d && <section className="observation-panel"><div className="observation-tabs">{[['rows', '原始数据'], ['reference', '原图对照']].map(([id, label]) => <button key={id} className={detail === id ? 'active' : ''} onClick={() => setDetail(id)}>{label}</button>)}</div>
      {detail === 'rows' && (!series.data ? series.isPending ? <Message>正在读取所选日期的数据表…</Message> : null : <><div className="observation-inline"><ObservationDownload params={{ metric_id: dataset.id, snapshot_id: catalog.snapshot_id, ...range, ...parameters, format: 'csv' }} filename={`${dataset.label}-${range.start}-${range.end}.csv`}>导出当前CSV</ObservationDownload><ObservationDownload params={{ metric_id: dataset.id, snapshot_id: catalog.snapshot_id, ...range, ...parameters, format: 'json' }} filename={`${dataset.label}-${range.start}-${range.end}.json`}>导出当前JSON</ObservationDownload><span>表格与图表固定同一版本</span></div><DataTable key={dataset.id + range.start + range.end} definition={d} rows={series.data.rows} /></>)}
      {detail === 'reference' && <Reference definition={d} version={catalog.snapshot_id} range={range} />}
    </section>} />
  </>
}

function change(rows: Row[], key: string) { const a = rows.find(r => typeof r[key] === 'number')?.[key]; const b = [...rows].reverse().find(r => typeof r[key] === 'number')?.[key]; return typeof a === 'number' && typeof b === 'number' ? value((b / a - 1) * 100) + '%' : '不可用' }
function DataTable({ definition, rows }: { definition: Definition; rows: Row[] }) {
  const [exact,setExact] = useState(false)
  const [page,setPage] = useState(0); const pages = Math.max(1,Math.ceil(rows.length / 100)); const selected = Math.min(page,pages - 1)
  const fields = ['date', ...Object.keys(definition.field_schema).filter(key => key !== 'date')]
  return <><div className="observation-inline"><button disabled={selected === 0} onClick={() => setPage(selected - 1)}>上一页</button><span>第{selected + 1}/{pages}页 · 共{rows.length}条 · 每页100条</span><button disabled={selected + 1 >= pages} onClick={() => setPage(selected + 1)}>下一页</button><label><input type="checkbox" checked={exact} onChange={e=>setExact(e.target.checked)} />显示精确原值</label></div><div className="observation-table-scroll" tabIndex={0}><table><thead><tr>{fields.map(key => <th key={key}>{definition.field_schema[key]?.label || key}{definition.field_schema[key]?.unit ? `（${exact?definition.field_schema[key].unit:observationDisplayUnit(definition.field_schema[key].unit)}）` : ''}</th>)}</tr></thead><tbody>{rows.slice(selected * 100,(selected + 1) * 100).map((row, index) => <tr key={String(row.date) + '-' + index}>{fields.map(key => <td key={key} title={exactObservationValue(row[key],definition.field_schema[key]?.unit)}>{typeof row[key]==='number'?observationNumber(row[key],definition.field_schema[key]?.unit,exact):value(row[key],key)}</td>)}</tr>)}</tbody></table></div></>
}
function FuturesCard({ product, version, range, onRange }: { product: string; version: string; range: Range; onRange: (r: Range) => void }) {
  const id = 'cffex_' + product
  const series = useQuery({ retry: false, queryKey: ['observation', id, version, range], queryFn: ({ signal }) => getSeries(id, version, range, signal) })
  const history = useQuery({ retry: false, queryKey: ['observation', 'history', id, version], queryFn: ({ signal }) => getHistory(id, version, signal) })
  const optionsId = { if: 'pcr_io', ih: 'pcr_ho', im: 'pcr_mo', ic: 'pcr_510500' }[product]!
  const options = useQuery({ retry: false, queryKey: ['observation', optionsId, version, range], queryFn: ({ signal }) => getSeries(optionsId, version, range, signal) })
  const optionsHistory = useQuery({ retry: false, queryKey: ['observation', 'history', optionsId, version], queryFn: ({ signal }) => getHistory(optionsId, version, signal) })
  const definition = series.data && { ...series.data.definition, overlay: true, lines: series.data.definition.lines.filter(line => ['total_oi', 'sse_reference'].includes(line.key)) }
  const counts = options.data && {...options.data.definition, parameters:false, primary_field:'put_oi', reference_levels:[], lines:[
    {key:'put_oi',name:'认沽 Put 持仓',color:'#c65761',panel:'main'},
    {key:'call_oi',name:'认购 Call 持仓',color:'#2768b2',panel:'main'},
    {key:'put_volume',name:'认沽 Put 成交',color:'#d69a23',panel:'context'},
    {key:'call_volume',name:'认购 Call 成交',color:'#24996f',panel:'context'},
  ].map(line=>({...line,unit:'张',shown:true,formula:'官方同产品同方向合约汇总',reading:'数量包含买卖双方，买入方向未知'}))}
  return <article className="observation-futures"><h3>{definition?.label ?? product.toUpperCase()}</h3>
    <ReadNotice label={`${product.toUpperCase()}期货`} query={series} /><ReadNotice label={`${product.toUpperCase()}期货历史导航`} query={history} />
    {definition && series.data ? series.data.rows.length ? <ObservationChart definition={definition} rows={series.data.rows} history={history.data} range={range} hidden={[]} focus="upper" mode="fixed_base" activity="all" onRange={onRange} /> : <p>所选日期没有期货观察数据。</p> : series.isPending ? <p>正在读取期货数据…</p> : null}
    <div className="observation-option-counts"><b>{product === 'ic' ? '中证500ETF期权参照' : '对应指数期权'} · 认沽 Put / 认购 Call</b><p>上图期权持仓，下图当日成交，各自区分Put与Call；数量包含买卖双方，买入方向未知。</p>
      <ReadNotice label={`${product.toUpperCase()}期权`} query={options} /><ReadNotice label={`${product.toUpperCase()}期权历史导航`} query={optionsHistory} />
      {counts && options.data ? options.data.rows.length ? <ObservationChart definition={counts} rows={options.data.rows} history={optionsHistory.data} range={range} hidden={[]} focus="both" mode="fixed_base" activity="all" onRange={onRange} /> : <p>所选日期没有期权观察数据。</p> : options.isPending ? <p>正在读取期权数量…</p> : null}
    </div></article>
}

function Reference({ definition, version, range }: { definition: Definition; version: string; range: Range }) {
  type Profile = {start?:string;end?:string;crop?:number[];image_size?:number[];date_basis?:string;gaps?:string[];verdict?:string}
  const [original,setOriginal] = useState(true); const [zoom,setZoom] = useState<Range>()
  const query = useQuery({ retry: false, queryKey: ['observation', 'reference', definition.id, version], queryFn: ({ signal }) => read<{ image?: string; profile?:Profile; review?: { status?: string; summary?: string; limitations?: string[] } }>('reference/' + definition.id, { snapshot_id: version }, signal) })
  const profile = query.data?.profile
  const selected = zoom || (original && profile?.start && profile.end ? {start:profile.start,end:profile.end} : range)
  const series = useQuery({ retry: false, queryKey: ['observation','reference-series',definition.id,version,selected],queryFn:({signal}) => getSeries(definition.id,version,selected,signal) })
  const history = useQuery({ retry: false, queryKey:['observation','history',definition.id,version],queryFn:({signal})=>getHistory(definition.id,version,signal) })
  const current = series.data?.definition || definition
  const rows = series.data?.rows || []
  const crop = profile?.crop; const size = profile?.image_size
  return <><ReadNotice label="原图资料" query={query} /><ReadNotice label="对照数据" query={series} /><ReadNotice label="对照历史导航" query={history} />
    <div className="observation-inline"><button className={original?'active':''} onClick={()=>{setOriginal(true);setZoom(undefined)}}>原图时间段</button><button className={!original?'active':''} onClick={()=>{setOriginal(false);setZoom(undefined)}}>当前筛选时间段</button><ObservationDownload params={{metric_id:definition.id,snapshot_id:version,...selected,format:'json'}} filename={`${definition.label}-${selected.start}-${selected.end}.json`}>导出本次对照JSON</ObservationDownload></div><p className="observation-note">对照日期 {selected.start} — {selected.end}</p><div className="observation-reference"><div><h3>原图 · 有效图区局部</h3>{query.data?.image ? <>{crop && size ? <svg role="img" aria-label="原图有效图区局部" viewBox={`${crop[0]} ${crop[1]} ${crop[2]-crop[0]} ${crop[3]-crop[1]}`}><image href={query.data.image} width={size[0]} height={size[1]} /></svg> : <img src={query.data.image} alt="用户提供的原始图表" />}<details><summary>展开完整原附件</summary><img src={query.data.image} alt="完整原图附件" /></details></> : <p>{query.isPending ? '正在读取原图…' : query.isError ? '原图暂时无法读取。' : '当前指标尚无原图。'}</p>}</div><div><h3>真实数据对照 · {current.label}</h3>{rows.length ? <ObservationChart definition={current} rows={rows} history={history.data} range={selected} hidden={current.lines.filter(line=>line.shown===false).map(line=>line.key)} focus="both" mode="fixed_base" activity="all" onRange={setZoom} /> : <p>{series.isPending ? '正在读取对照数据…' : series.data ? '所选日期暂无观察数据；保留原始覆盖范围。' : '对照数据暂时无法读取。'}</p>}</div></div></>
}
function Quality({ catalog, schedule }: { catalog: Catalog; schedule?:{timezone:string;times:string[]}|null }) {
  const query = useQuery({ retry: false, queryKey: ['observation', 'updates'], queryFn: ({ signal }) => read<{ runs: { completed_at: string; status: string; execution_mode?:string; operation?:string; date?:string; error_code?:string; sources?: { source_id: string; status: string; latest_period?: string; loaded_period?:string; error_code?: string }[] }[] }>('updates', {}, signal), refetchInterval: 60000 })
  const visibleRuns=query.data?.runs.filter(run=>run.execution_mode!=='source_capture'||run.operation==='ashare_capture'&&run.status!=='attempted')
  return <section className="observation-panel"><h2>更新与数据缺口</h2><p>{schedule ? `每日更新时刻 ${schedule.times.join(' / ')} · ${schedule.timezone==='Asia/Shanghai'?'北京时间':schedule.timezone}` : '更新时刻配置暂不可用'}；实际启用状态见页首。检查时间、源返回的观察末期和已加载末期分别记录。</p>
    <ReadNotice label="更新回执" query={query} />
    {query.isPending ? <Message>正在读取更新回执…</Message> : query.data && !query.data.runs.length && <Message>尚无自动任务回执，当前展示已接纳的历史版本。</Message>}
    {visibleRuns?.filter((run,index,all)=>all.findIndex(item=>item.completed_at===run.completed_at)===index).slice(0,8).map((run,i)=><details key={i} open={i===0}><summary>{new Date(run.completed_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'})} · {run.execution_mode==='source_capture'?'日终原件归档':run.execution_mode==='manual'?'手动来源核验':run.execution_mode==='scheduled'?'自动到期窗口':'历史回执'} · {run.execution_mode==='source_capture'?(run.status==='success'?'原件已保存，等待计划发布':'原件待补，继续提供原版本'):statusLabel(run.status)}</summary>{run.execution_mode==='source_capture'?<p>观察日 {run.date}。{run.status==='success'?'本次保存来源原件；页面数据沿每日更新窗口发布。':failureLabel(run.error_code)}</p>:<div className="observation-table-scroll" tabIndex={0}><table><thead><tr><th>来源</th><th>本次结果</th><th>本次取得末期</th><th>已加载末期</th><th>原因与处理</th></tr></thead><tbody>{run.sources?.map(source=><tr key={source.source_id}><td>{sourceLabel(source.source_id)}</td><td>{statusLabel(source.status)}</td><td>{source.status==='checked_disclosure'?'本次仅检查目录':source.latest_period || '本次未取得观察'}</td><td>{source.loaded_period || '见下方口径覆盖'}</td><td>{failureLabel(source.error_code)}</td></tr>)}</tbody></table></div>}</details>)}
    <h3>全部来源覆盖</h3><div className="observation-table-scroll" tabIndex={0}><table><thead><tr><th>口径</th><th>真实频率</th><th>已加载末期</th><th>观察条数</th></tr></thead><tbody>{catalog.datasets.map(d=><tr key={d.id}><td>{d.label}</td><td>{frequencyLabel(d.frequency)}</td><td>{d.coverage.end}</td><td>{d.coverage.observations}</td></tr>)}</tbody></table></div></section>
}
