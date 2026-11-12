import { useEffect, useMemo, useRef, useState } from 'react'
import * as echarts from 'echarts/core'
import { LineChart, ScatterChart, type LineSeriesOption, type ScatterSeriesOption } from 'echarts/charts'
import { GridComponent, TooltipComponent, DataZoomComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import { absoluteChinaTime } from '../components/RelativeTime'
import type { LiveDay, LivePerformance } from './liveStrategyApi'
import { FinancialValue } from './FinancialValue'
import { StrategySecurityLabel } from './StrategyPositionTargets'
import { observerChartColors, useObserverTheme } from './observerAppearance'
import './live-strategy.css'

echarts.use([LineChart, ScatterChart, GridComponent, TooltipComponent, DataZoomComponent, SVGRenderer])
const money = (v: string | null) => v === null ? '尚无观测' : `${Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 2 })} 元`
const chartValue = (d: LiveDay) => d.nav_cny ?? d.reference_nav_cny ?? null
const side = (v: string) => v === 'BUY' ? '买入' : v === 'SELL' ? '卖出' : '方向未确认'
const sourceTime = (v: string | null) => v ? absoluteChinaTime(v) : '该日未取得净值观测'
const heldPositions = (day: LiveDay) => day.positions.filter(position => position.quantity > 0)

/** 悬停只读本轮实际观察，点击固定日期；交易标记只放在确有净值的日期。 */
function LiveChart({ days, onHover, onSelect }: {
  /** 实际来源日期与已观察事实。 */ days: LiveDay[]
  /** 悬停预览，不触发请求。 */ onHover: (day: string | null) => void
  /** 点击固定详细日期。 */ onSelect: (day: string) => void
}) {
  const root = useRef<HTMLDivElement>(null)
  const theme = useObserverTheme()
  const latestDays = useRef(days); latestDays.current = days
  const callbacks = useRef({ onHover, onSelect }); callbacks.current = { onHover, onSelect }
  const key = JSON.stringify(days.map(d => [d.date, d.nav_cny, d.reference_nav_cny, d.valuation_state, d.deals.filter(x => x.side === 'BUY').length, d.deals.filter(x => x.side === 'SELL').length]))
  useEffect(() => {
    if (!root.current || !days.some(d => chartValue(d) !== null)) return
    const palette = observerChartColors(root.current)
    const chart = echarts.init(root.current, undefined, { renderer: 'svg' })
    const series: (LineSeriesOption | ScatterSeriesOption)[] = [{ name: '实际发布净值', type: 'line', showSymbol: true, symbolSize: 7, connectNulls: false,
      data: days.map(d => d.nav_cny === null ? null : Number(d.nav_cny)), lineStyle: { color: palette.accent, width: 2 }, itemStyle: { color: palette.accent } },
      { name: '参考净值（手续费待确认）', type: 'line', showSymbol: true, symbolSize: 7, connectNulls: false,
        data: days.map(d => d.reference_nav_cny == null ? null : Number(d.reference_nav_cny)), lineStyle: { color: '#a66b16', width: 2, type: 'dashed' }, itemStyle: { color: '#a66b16' } }]
    for (const direction of ['BUY', 'SELL']) series.push({ name: `账户${side(direction)}`, type: 'scatter', symbol: 'triangle', symbolRotate: direction === 'SELL' ? 180 : 0,
      symbolSize: 12, itemStyle: { color: direction === 'BUY' ? '#d74654' : '#008763' }, z: 4,
      data: days.flatMap((d, i) => chartValue(d) !== null && d.deals.some(t => t.side === direction) ? [[i, Number(chartValue(d))]] : []) })
    chart.setOption({ animation: false, grid: { left: 80, right: 24, top: 25, bottom: 64 },
      textStyle: { fontFamily: 'Segoe UI, Microsoft YaHei, sans-serif', color: palette.muted },
      xAxis: { type: 'category', data: days.map(d => d.date), boundaryGap: false, axisLabel: { color: palette.muted }, axisLine: { lineStyle: { color: palette.border } } },
      yAxis: { type: 'value', scale: true, splitLine: { lineStyle: { color: palette.line } }, axisLabel: { color: palette.muted, formatter: (n: number) => `${(n / 10000).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}万` } },
      tooltip: { ...palette.tooltip, trigger: 'axis', renderMode: 'richText', formatter: (input: unknown) => {
        const p = Array.isArray(input) ? input[0] : input
        const index = p && typeof p === 'object' && 'dataIndex' in p ? Number(p.dataIndex) : -1
        const d = latestDays.current[index]; if (!d) return ''
        return [d.date, `${d.reference_nav_cny != null ? '参考净值（手续费待确认）' : '实际发布净值'}：${money(chartValue(d))}`, d.positions_state === 'unavailable' ? '持仓尚无观测' : `持仓 ${heldPositions(d).length} 项`,
          d.deals_state === 'unavailable' ? '成交来源尚未取得' : `实际成交 ${d.deals.length} 笔`, '点击固定当日详情'].join('\n')
      } }, dataZoom: [{ type: 'inside' }, { ...palette.slider, type: 'slider', bottom: 10, height: 18, showDetail: false }], series })
    const dayAt = (x: number, y: number) => {
      if (!chart.containPixel({ gridIndex: 0 }, [x, y])) return null
      const index = Math.round(Number(chart.convertFromPixel({ xAxisIndex: 0 }, x)))
      return days[index]?.date ?? null
    }
    chart.getZr().on('mousemove', event => callbacks.current.onHover(dayAt(event.offsetX, event.offsetY)))
    chart.getZr().on('globalout', () => callbacks.current.onHover(null))
    chart.getZr().on('click', event => { const d = dayAt(event.offsetX, event.offsetY); if (d) callbacks.current.onSelect(d) })
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(() => chart.resize())
    observer?.observe(root.current)
    return () => { observer?.disconnect(); chart.dispose() }
    // The financial shape owns chart updates; response/poll timestamps do not rebuild it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, theme])
  return <div className="live-strategy-chart" ref={root} role="img" aria-label="实际发布净值曲线与实际成交标记；可悬停预览并点击固定日期，键盘可使用日期选择" />
}

/** 线上实际观察与运行详情分开；无历史时显示真实覆盖，保持完整空与未知的区别。 */
export default function LiveStrategyPerformance({ data }: {
  /** 与当前选择、完整运行scope严格绑定的已准入结果。 */ data: LivePerformance
}) {
  const [pinned, setPinned] = useState<string | null>(null)
  const [hover, setHover] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(false)
  const latest = data.daily.at(-1)?.date
  const date = data.daily.some(d => d.date === pinned) ? pinned : latest
  const selected = data.daily.find(d => d.date === date)
  const preview = data.daily.find(d => d.date === hover) ?? selected
  const previewPositions = preview ? heldPositions(preview) : []
  const selectedPositions = selected ? heldPositions(selected) : []
  const positionsTime = selected?.positions_observed_at ?? selected?.positions[0]?.observed_at
  const valuation = data.summary?.valuation_state
  const amount = data.summary?.nav_cny ?? data.summary?.reference_nav_cny ?? null
  const change = data.summary?.reference_change_cny ?? data.summary?.pnl_cny ?? null
  const capitalReturn = data.summary?.capital_return
  const returnValue = data.summary?.return_pct ?? null
  const referenceReturn = returnValue === null && valuation
  const totalPoints = data.coverage.point_count + (data.coverage.reference_point_count ?? 0)
  const allocated = data.coverage.attribution === 'strategy-allocated'
  const positionScope = allocated ? '策略自有持仓' : '策略证券范围内的账户持仓'
  const rows = useMemo(() => data.daily, [data.daily])
  function select(value: string) { setPinned(value); setHover(null); setExpanded(true) }
  return <section className="surface-card live-strategy-panel" aria-label="线上策略实际观察">
    <div className="live-strategy-heading"><h3>线上表现</h3><span>实际发布观察 · 人民币</span></div>
    <div className="live-strategy-metrics">
      <div><small>{valuation === 'reference-fee-pending' ? '参考净值（手续费待确认）' : '策略净值'}</small><strong>{amount !== null ? <FinancialValue value={amount} /> : '尚无观测'}</strong></div>
      <div><small>{valuation ? '相对配置资本变化（参考）' : '原发布基准变化'}</small><strong>{change !== null ? <FinancialValue value={change} /> : '尚无观测'}</strong></div>
      <div><small>{referenceReturn ? '配置资本参考变化率' : '投资收益率'}</small><strong>{returnValue !== null ? `${returnValue}%` : referenceReturn && data.summary?.reference_return_pct != null ? `${data.summary.reference_return_pct}%` : '口径待核实'}</strong></div>
      <div><small>净值实际覆盖</small><strong>{data.coverage.point_count} 个实际日{data.coverage.reference_point_count ? ` · ${data.coverage.reference_point_count} 个参考日` : ''}</strong></div>
    </div>
    <p className="live-strategy-note">{data.coverage.reason}</p>
    {data.summary ? <p className="live-strategy-note">{data.summary.return_reason} · 净值时间 {sourceTime(data.summary.observed_at)}{data.summary.price_observed_at ? ` · 行情原时间 ${sourceTime(data.summary.price_observed_at)}` : ''}{capitalReturn && returnValue !== null ? ` · 收益估值截止 ${sourceTime(capitalReturn.valued_at)}` : ''}</p> : null}
    {capitalReturn ? <details className="compact-details">
      <summary>策略资金进出（{capitalReturn.flow_count} 笔）</summary>
      <p>收益起算 {sourceTime(capitalReturn.baseline_at)} · 本次需覆盖至 {sourceTime(capitalReturn.coverage_required_at)} · 追加覆盖至 {capitalReturn.inflow_through ? sourceTime(capitalReturn.inflow_through) : '待核对'} · 提取覆盖至 {capitalReturn.outflow_through ? sourceTime(capitalReturn.outflow_through) : '待核对'}</p>
      {returnValue !== null ? <p>收益所用净值 <FinancialValue value={capitalReturn.valuation_nav_cny} /> 元</p> : null}
      {capitalReturn.flow_count > capitalReturn.flows.length ? <p>显示最近 {capitalReturn.flows.length} 笔。</p> : null}
      {capitalReturn.flows.length ? <div className="live-table-scroll"><table><thead><tr><th>生效时间</th><th>资金方向</th><th>金额（元）</th></tr></thead>
        <tbody>{capitalReturn.flows.map(flow => <tr key={flow.id}><td>{sourceTime(flow.effective_at)}</td><td>{flow.direction === 'inflow' ? '追加' : '提取'}</td><td><FinancialValue value={flow.amount_cny} /></td></tr>)}</tbody></table></div> : null}
    </details> : null}
    <p className="live-strategy-attribution">{allocated ? '持仓、现金和成交来自ASA已确认的本策略归属；缺少策略估值时净值保持未知。' : '买卖点及成交来自券商账户，并按本策略证券范围筛选；策略归属尚未确认。'}持仓沿实际观察日期记录，历史缺日保持空白。</p>
    {data.coverage.valuation_state === 'unavailable' ? <p role="status">本轮自有组合估值未完成，保留最后已核点和原时间；正持仓报价缺失或过期时保持未知。</p> : null}
    {valuation === 'reference-fee-pending' ? <p className="live-strategy-note">参考曲线仅扣已知费用，实际手续费尚待确认；金额和配置资本变化率均属于参考值，投资收益率未核实。</p> : null}
    {data.coverage.deals_truncated ? <p role="status">当前窗口成交较多，界面显示有界明细，已观察历史继续保存。</p> : null}
    {data.daily.length ? <>
      {totalPoints ? <LiveChart days={rows} onHover={setHover} onSelect={select} /> : <p role="status">当前还没有实际净值点，已取得的成交与持仓可在下方查看。</p>}
      {(data.coverage.reference_point_count ?? 0) > 0 ? <p className="live-strategy-note">蓝色实线表示实际净值，棕色虚线表示参考净值（手续费待确认）；两种资格分别保留。</p> : null}
      {data.coverage.point_count === 1 ? <p className="live-strategy-note">当前只有 1 个实际净值点。后续真实发布会继续累积，暂不连接成历史收益曲线。</p> : null}
      <div className="live-day-picker"><label>观察日期<select value={date ?? ''} onChange={e => select(e.target.value)}>{data.daily.map(d => <option key={d.date} value={d.date}>{d.date}</option>)}</select></label>
        <button onClick={() => setExpanded(v => !v)} aria-expanded={expanded}>{expanded ? '收起详细信息' : '展开详细信息'}</button></div>
      {preview ? <div className="live-day-preview" aria-live="polite"><strong>{preview.date}{hover ? ' · 悬停预览' : ' · 所选日期'}</strong>
        <span>{preview.reference_nav_cny != null ? '参考净值（手续费待确认）' : '净值'} {money(chartValue(preview))}</span><span>{preview.positions_state === 'unavailable' ? '持仓未取得' : `持仓 ${previewPositions.length} 项`}</span>
        <span>{preview.deals_state === 'unavailable' ? '成交未取得' : `${allocated ? '策略实际成交' : '账户范围成交'} ${preview.deals.length} 笔`}</span>
        <div>{preview.positions_state === 'unavailable' ? '该日没有持仓观测。' : previewPositions.length ? previewPositions.map((p, i) => <span key={p.symbol}>{i > 0 ? '；' : null}<StrategySecurityLabel symbol={p.symbol} names={data.security_names} /> {p.quantity.toLocaleString('zh-CN')}份</span>) : '当日完整持仓为空。'}</div>
        <div>{preview.deals_state === 'unavailable' ? '该日没有成交观测。' : preview.deals.length ? preview.deals.map((d, i) => <span key={d.id}>{i > 0 ? '；' : null}{side(d.side)} <StrategySecurityLabel symbol={d.symbol} names={data.security_names} /> {d.quantity.toLocaleString('zh-CN')}份</span>) : '当日完整查询无成交。'}</div>
      </div> : null}
      {selected ? <div className="live-day-columns" role="region" aria-label={`${selected.date}每日持仓和成交`}>
        <section><h4>当日持仓 <small>{positionScope}</small></h4>{positionsTime ? <p className="live-strategy-note">持仓观察时间 {absoluteChinaTime(positionsTime)}</p> : null}{selected.positions_state === 'unavailable' ? <p>该日没有持仓观测。</p> : selectedPositions.length ? <div className="live-table-scroll"><table><thead><tr><th>证券</th><th>数量（份）</th><th>可卖（份）</th></tr></thead><tbody>{selectedPositions.map(p => <tr key={p.symbol}><td><StrategySecurityLabel symbol={p.symbol} names={data.security_names} /></td><td>{p.quantity.toLocaleString('zh-CN')}</td><td>{p.sellable.toLocaleString('zh-CN')}</td></tr>)}</tbody></table></div> : <p>当日完整持仓为空。</p>}</section>
        <section><h4>{allocated ? '策略实际成交' : '账户范围成交'} <small>{allocated ? 'ASA已确认归属' : '归属未确认'}</small></h4>{selected.deals_state === 'unavailable' ? <p>该日没有成交观测。</p> : selected.deals.length ? <div className="live-table-scroll"><table><thead><tr><th>时间</th><th>证券 / 方向</th><th>单价（元）</th><th>数量（份）</th>{expanded ? <th>金额（元）</th> : null}</tr></thead><tbody>{selected.deals.map(d => <tr key={d.id}><td>{d.time}</td><td><StrategySecurityLabel symbol={d.symbol} names={data.security_names} /><br />{side(d.side)}</td><td>{d.price_cny}</td><td>{d.quantity.toLocaleString('zh-CN')}</td>{expanded ? <td>{d.amount_cny}</td> : null}</tr>)}</tbody></table></div> : <p>当日完整查询无成交。</p>}{selected.deals_state === 'partial' ? <p role="status">部分成交字段不可用，当前保留已确认明细。</p> : null}</section>
      </div> : null}
      {expanded && selected ? <div className="live-day-financials"><span>{selected.reference_cash_cny != null ? '参考现金（手续费待确认）' : '现金'} {money(selected.cash_cny ?? selected.reference_cash_cny ?? null)}{(selected.reference_cash_cny != null ? selected.reference_cash_observed_at : selected.cash_observed_at) ? ` · 现金观察 ${sourceTime((selected.reference_cash_cny != null ? selected.reference_cash_observed_at : selected.cash_observed_at) ?? null)}` : ''}</span><span>市值 {money(selected.market_value_cny)}</span><span>原发布基准变化 {money(selected.pnl_cny)}</span><span>{sourceTime(selected.observed_at ?? selected.reference_observed_at ?? null)}</span></div> : null}
    </> : <p role="status">{data.reason}</p>}
  </section>
}
