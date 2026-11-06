import { useEffect, useMemo, useRef, useState } from 'react'
import * as echarts from 'echarts/core'
import { LineChart, ScatterChart, type LineSeriesOption, type ScatterSeriesOption } from 'echarts/charts'
import { GridComponent, TooltipComponent, DataZoomComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import { absoluteChinaTime } from '../components/RelativeTime'
import type { LiveDay, LivePerformance } from './liveStrategyApi'
import { FinancialValue } from './FinancialValue'
import './live-strategy.css'

echarts.use([LineChart, ScatterChart, GridComponent, TooltipComponent, DataZoomComponent, SVGRenderer])
const money = (v: string | null) => v === null ? '尚无观测' : `${Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 2 })} 元`
const side = (v: string) => v === 'BUY' ? '买入' : v === 'SELL' ? '卖出' : '方向未确认'
const sourceTime = (v: string | null) => v ? absoluteChinaTime(v) : '该日未取得净值观测'

/** 悬停只读本轮实际观察，点击固定日期；交易标记只放在确有净值的日期。 */
function LiveChart({ days, onHover, onSelect }: {
  /** 实际来源日期与已观察事实。 */ days: LiveDay[]
  /** 悬停预览，不触发请求。 */ onHover: (day: string | null) => void
  /** 点击固定详细日期。 */ onSelect: (day: string) => void
}) {
  const root = useRef<HTMLDivElement>(null)
  const latestDays = useRef(days); latestDays.current = days
  const callbacks = useRef({ onHover, onSelect }); callbacks.current = { onHover, onSelect }
  const key = JSON.stringify(days.map(d => [d.date, d.nav_cny, d.deals.filter(x => x.side === 'BUY').length, d.deals.filter(x => x.side === 'SELL').length]))
  useEffect(() => {
    if (!root.current || !days.some(d => d.nav_cny !== null)) return
    const chart = echarts.init(root.current, undefined, { renderer: 'svg' })
    const series: (LineSeriesOption | ScatterSeriesOption)[] = [{ name: '实际发布净值', type: 'line', showSymbol: true, symbolSize: 7, connectNulls: false,
      data: days.map(d => d.nav_cny === null ? null : Number(d.nav_cny)), lineStyle: { color: '#1763ee', width: 2 }, itemStyle: { color: '#1763ee' } }]
    for (const direction of ['BUY', 'SELL']) series.push({ name: `账户${side(direction)}`, type: 'scatter', symbol: 'triangle', symbolRotate: direction === 'SELL' ? 180 : 0,
      symbolSize: 12, itemStyle: { color: direction === 'BUY' ? '#d74654' : '#008763' }, z: 4,
      data: days.flatMap((d, i) => d.nav_cny !== null && d.deals.some(t => t.side === direction) ? [[i, Number(d.nav_cny)]] : []) })
    chart.setOption({ animation: false, grid: { left: 80, right: 24, top: 25, bottom: 64 },
      textStyle: { fontFamily: 'Segoe UI, Microsoft YaHei, sans-serif' },
      xAxis: { type: 'category', data: days.map(d => d.date), boundaryGap: false },
      yAxis: { type: 'value', scale: true, axisLabel: { formatter: (n: number) => `${(n / 10000).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}万` } },
      tooltip: { trigger: 'axis', renderMode: 'richText', formatter: (input: unknown) => {
        const p = Array.isArray(input) ? input[0] : input
        const index = p && typeof p === 'object' && 'dataIndex' in p ? Number(p.dataIndex) : -1
        const d = latestDays.current[index]; if (!d) return ''
        return [d.date, `实际发布净值：${money(d.nav_cny)}`, d.positions_state === 'unavailable' ? '持仓尚无观测' : `持仓 ${d.positions.length} 项`,
          d.deals_state === 'unavailable' ? '成交来源尚未取得' : `账户范围成交 ${d.deals.length} 笔`, '点击固定当日详情'].join('\n')
      } }, dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 10, height: 18, showDetail: false }], series })
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
  }, [key])
  return <div className="live-strategy-chart" ref={root} role="img" aria-label="实际发布净值曲线与账户证券范围成交标记；可悬停预览并点击固定日期，键盘可使用日期选择" />
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
  const rows = useMemo(() => data.daily, [data.daily])
  function select(value: string) { setPinned(value); setHover(null); setExpanded(true) }
  return <section className="surface-card live-strategy-panel" aria-label="线上策略实际观察">
    <div className="live-strategy-heading"><h3>线上表现</h3><span>实际发布观察 · 人民币</span></div>
    <div className="live-strategy-metrics">
      <div><small>策略净值</small><strong>{data.summary ? <FinancialValue value={data.summary.nav_cny} /> : '尚无观测'}</strong></div>
      <div><small>原发布基准变化</small><strong>{data.summary ? <FinancialValue value={data.summary.pnl_cny} /> : '尚无观测'}</strong></div>
      <div><small>投资收益率</small><strong>口径待核实</strong></div>
      <div><small>净值实际覆盖</small><strong>{data.coverage.point_count} 个观测日</strong></div>
    </div>
    <p className="live-strategy-note">{data.coverage.reason}</p>
    {data.summary ? <p className="live-strategy-note">{data.summary.return_reason} · 估值时间 {sourceTime(data.summary.observed_at)}{data.summary.price_observed_at ? ` · 行情原时间 ${sourceTime(data.summary.price_observed_at)}` : ''}</p> : null}
    <p className="live-strategy-attribution">买卖点及成交来自券商账户，并按本策略证券范围筛选；策略归属尚未确认。持仓沿实际接收日期记录，历史缺日保持空白。</p>
    {data.coverage.deals_truncated ? <p role="status">当前窗口成交较多，界面显示有界明细，已观察历史继续保存。</p> : null}
    {data.daily.length ? <>
      {data.coverage.point_count ? <LiveChart days={rows} onHover={setHover} onSelect={select} /> : <p role="status">当前还没有实际净值点，已取得的成交与持仓可在下方查看。</p>}
      {data.coverage.point_count === 1 ? <p className="live-strategy-note">当前只有 1 个实际净值点。后续真实发布会继续累积，暂不连接成历史收益曲线。</p> : null}
      <div className="live-day-picker"><label>观察日期<select value={date ?? ''} onChange={e => select(e.target.value)}>{data.daily.map(d => <option key={d.date} value={d.date}>{d.date}</option>)}</select></label>
        <button onClick={() => setExpanded(v => !v)} aria-expanded={expanded}>{expanded ? '收起详细信息' : '展开详细信息'}</button></div>
      {preview ? <div className="live-day-preview" aria-live="polite"><strong>{preview.date}{hover ? ' · 悬停预览' : ' · 当前日期'}</strong>
        <span>净值 {money(preview.nav_cny)}</span><span>{preview.positions_state === 'unavailable' ? '持仓未取得' : `持仓 ${preview.positions.length} 项`}</span>
        <span>{preview.deals_state === 'unavailable' ? '成交未取得' : `账户范围成交 ${preview.deals.length} 笔`}</span>
        <div>{preview.positions_state === 'unavailable' ? '该日没有持仓观测。' : preview.positions.length ? preview.positions.map(p => `${p.symbol} ${p.quantity.toLocaleString('zh-CN')}份`).join('；') : '当日完整持仓为空。'}</div>
        <div>{preview.deals_state === 'unavailable' ? '该日没有成交观测。' : preview.deals.length ? preview.deals.map(d => `${side(d.side)} ${d.symbol} ${d.quantity.toLocaleString('zh-CN')}份`).join('；') : '当日完整查询无成交。'}</div>
      </div> : null}
      {selected ? <div className="live-day-columns" role="region" aria-label={`${selected.date}每日持仓和成交`}>
        <section><h4>当日持仓</h4>{selected.positions_state === 'unavailable' ? <p>该日没有持仓观测。</p> : selected.positions.length ? <div className="live-table-scroll"><table><thead><tr><th>证券</th><th>数量（份）</th><th>可卖（份）</th></tr></thead><tbody>{selected.positions.map(p => <tr key={p.symbol}><td>{p.symbol}</td><td>{p.quantity.toLocaleString('zh-CN')}</td><td>{p.sellable.toLocaleString('zh-CN')}</td></tr>)}</tbody></table></div> : <p>当日完整持仓为空。</p>}</section>
        <section><h4>账户范围成交 <small>归属未确认</small></h4>{selected.deals_state === 'unavailable' ? <p>该日没有成交观测。</p> : selected.deals.length ? <div className="live-table-scroll"><table><thead><tr><th>时间</th><th>证券 / 方向</th><th>单价（元）</th><th>数量（份）</th>{expanded ? <th>金额（元）</th> : null}</tr></thead><tbody>{selected.deals.map(d => <tr key={d.id}><td>{d.time}</td><td>{d.symbol}<br />{side(d.side)}</td><td>{d.price_cny}</td><td>{d.quantity.toLocaleString('zh-CN')}</td>{expanded ? <td>{d.amount_cny}</td> : null}</tr>)}</tbody></table></div> : <p>当日完整查询无成交。</p>}{selected.deals_state === 'partial' ? <p role="status">部分成交字段不可用，当前保留已确认明细。</p> : null}</section>
      </div> : null}
      {expanded && selected ? <div className="live-day-financials"><span>现金 {money(selected.cash_cny)}</span><span>市值 {money(selected.market_value_cny)}</span><span>原发布基准变化 {money(selected.pnl_cny)}</span><span>{sourceTime(selected.observed_at)}</span></div> : null}
    </> : <p role="status">{data.reason}</p>}
  </section>
}
