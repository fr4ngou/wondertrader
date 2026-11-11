import { useEffect, useMemo, useRef } from 'react'
import { useQueries } from '@tanstack/react-query'
import { init, type ComposeOption } from 'echarts/core'
import type { BarSeriesOption, LineSeriesOption } from 'echarts/charts'
import type { DataZoomComponentOption, GridComponentOption, LegendComponentOption, TooltipComponentOption } from 'echarts/components'
import { getSeries } from './api'
import { ReadNotice } from './ReadNotice'
import { buildExecutiveWeeks, executiveWeekStats, readWeeklyIndex, shanghaiToday, WEEKLY_INDEXES } from './executiveWeekly'
import type { DailyClose, ExecutiveWeek, WeeklyIndex } from './executiveWeekly'
import type { Catalog, Range, Series } from './types'
import './executive-weekly.css'

// 图表组件与渲染器由同路由加载的 ObservationChart 注册。
type Options = ComposeOption<BarSeriesOption | LineSeriesOption | GridComponentOption | LegendComponentOption | DataZoomComponentOption | TooltipComponentOption>
const barName = '周度净减持'
const benchmark = 'market.sh000001'
const format = (value: number | null) => value === null ? '—' : value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

export function weeklyExecutiveOptions(weeks: ExecutiveWeek[], narrow: boolean, archived: boolean): Options {
  return {
    animation: false,
    grid: { left: narrow ? 42 : 63, right: narrow ? 42 : 67, top: 37, bottom: narrow ? 125 : 107 },
    xAxis: {
      type: 'category', data: weeks.map(week => week.label), boundaryGap: true,
      axisLabel: { color: '#777', rotate: 50, hideOverlap: true, fontSize: narrow ? 9 : 11,
        formatter: (value, i) => weeks[i]?.partial || weeks[i]?.unpriced ? value + '*' : value },
      axisLine: { lineStyle: { color: '#aeb7c4' } },
      axisTick: { alignWithLabel: true },
    },
    yAxis: [
      { type: 'value', scale: true, name: '指数点位', nameTextStyle: { color: '#747474' },
        axisLabel: { color: '#555', formatter: value => narrow ? String(value) : Number(value).toFixed(2) },
        splitLine: { lineStyle: { color: '#e5e7ea' } } },
      { type: 'value', name: '净减持(亿元)', position: 'right', nameTextStyle: { color: '#747474' },
        axisLabel: { color: '#555', formatter: value => Number(value).toFixed(narrow ? 1 : 2) },
        splitLine: { show: false } },
    ],
    tooltip: { trigger: 'axis', renderMode: 'richText', confine: true, axisPointer: { type: 'line' },
      formatter: (input) => {
        if (!Array.isArray(input) || !input.length) return ''
        const week = weeks[input[0].dataIndex]
        if (!week) return ''
        return [`${week.label}  ${week.start} 至 ${week.end}${week.partial ? '（部分周）' : ''}`,
          ...(week.unpriced ? [`缺少历史价格 ${week.unpriced} 笔 · 显示可计价小计`] : []),
          ...(week.estimated ? [`其中 ${week.estimated} 笔以历史价格估算`] : []),
          ...input.map(item => `${item.seriesName}  ${format(typeof item.value === 'number' ? item.value : null)}${item.seriesName === barName ? ' 亿元' : ' 点'}`)].join('\n')
      } },
    legend: { bottom: narrow ? 2 : 0, itemWidth: 18, itemHeight: 9, textStyle: { color: '#555', fontSize: narrow ? 10 : 12 },
      data: [barName, ...WEEKLY_INDEXES.map(index => index.name)] },
    dataZoom: [
      { type: 'inside', filterMode: 'none', zoomOnMouseWheel: 'ctrl', moveOnMouseWheel: false },
      { type: 'slider', filterMode: 'none', bottom: narrow ? 52 : 31, height: 19, showDetail: false,
        borderColor: '#c5d1e2', fillerColor: 'rgba(86,127,186,.17)', dataBackground: { lineStyle: { color: '#90acd0' }, areaStyle: { color: '#d4e1f2' } } },
    ],
    series: [
      { type: 'bar', name: barName, yAxisIndex: 1, barMaxWidth: 18, data: weeks.map(week => week.netSales),
        itemStyle: { color: item => typeof item.value === 'number' && item.value < 0 ? '#cd5754' : '#80a5cf', opacity: .85 } },
      ...WEEKLY_INDEXES.map(index => ({
        type: 'line' as const, name: index.name, showSymbol: false, connectNulls: archived,
        data: weeks.map(week => week.closes[index.symbol] ?? null),
        itemStyle: { color: index.color }, lineStyle: { color: index.color, width: 2 },
      })),
    ],
  }
}

function WeeklyPlot({ weeks, archived }: { weeks: ExecutiveWeek[]; archived: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    const chart = init(element)
    let narrow = element.clientWidth < 520
    chart.setOption(weeklyExecutiveOptions(weeks, narrow, archived))
    const observer = new ResizeObserver(() => {
      const next = element.clientWidth < 520
      chart.resize()
      if (next !== narrow) {
        narrow = next
        chart.setOption(weeklyExecutiveOptions(weeks, narrow, archived))
      }
    })
    observer.observe(element)
    return () => { observer.disconnect(); chart.dispose() }
  }, [weeks, archived])
  return <div ref={ref} className="executive-weekly-plot" role="img" aria-label="蓝柱为周度净减持，红柱为周度净增持，曲线为四个指数的周收盘点位" />
}

export const isShareholderNet = (metric: string) => metric === 'shareholder.net.ashare'
export const isExecutiveNet = (metric: string) => isShareholderNet(metric) || metric === 'executive.net.shsz' || metric === 'executive.net.ashare'

export function ExecutiveWeeklyChart({ catalog, data, range }: {
  catalog: Catalog
  data: Series
  range: Range
}) {
  const archived = isShareholderNet(data.definition.id)
  const local = import.meta.env.VITE_OBSERVATION_ONLY !== 'true'
  const hasBenchmark = catalog.datasets.some(item => item.id === benchmark)
  const indexes = useQueries({ queries: WEEKLY_INDEXES.map(index => ({
    queryKey: ['observation', 'executive-index-close', index.symbol, catalog.snapshot_id, range],
    enabled: !archived && (index.symbol === '000001.SH' ? hasBenchmark : local),
    retry: false,
    queryFn: async ({ signal }: { signal: AbortSignal }): Promise<DailyClose[]> => {
      if (index.symbol !== '000001.SH') return readWeeklyIndex(index.symbol, range, signal)
      const series = await getSeries(benchmark, catalog.snapshot_id, range, signal)
      return series.rows.flatMap(row => typeof row.close === 'number' ? [{ date: String(row.date), close: row.close }] : [])
    },
  })) })
  const coverage = data.definition.coverage
  const [csi, sse, chinext, star] = indexes.map(result => result.data)
  const today = shanghaiToday()
  const weeks = useMemo(() => {
    const closes = (field: string) => data.rows.flatMap(row => typeof row[field] === 'number'
      ? [{ date: String(row.date), close: row[field] }] : [])
    return buildExecutiveWeeks(data.rows, {
      '000985.SH': archived ? closes('csi_close') : csi,
      '000001.SH': archived ? closes('sse_close') : sse,
      '399006.SZ': archived ? closes('chinext_close') : chinext,
      '000688.SH': archived ? closes('star_close') : star,
    }, range, coverage, today)
  }, [data.rows, archived, csi, sse, chinext, star, range.start, range.end, coverage.start, coverage.end, today])
  const estimated = weeks.reduce((sum, week) => sum + week.estimated, 0)
  const unpriced = weeks.reduce((sum, week) => sum + week.unpriced, 0)
  const stats = executiveWeekStats(weeks, archived ? 'level' : 'return')
  const scope = data.definition.id.endsWith('.ashare') ? '沪深北' : '沪深'
  return <section className="executive-weekly" aria-label={archived ? "重要股东净减持周度图" : "高管净减持周度图"} aria-busy={indexes.some(query => query.isFetching)}>
    <h3>周度{archived ? '重要股东' : '高管'}净减持金额 vs 主要指数</h3>
    <p className="executive-weekly-stats">
      <span>{weeks[0]?.label ?? '—'} — {weeks.at(-1)?.label ?? '—'} · 共 {weeks.length} 周</span>
      <span>周均净减持 <strong>{format(stats.average)}</strong> 亿元</span>
      <span>与中证全指{archived ? '周收盘' : '周涨跌幅'}相关系数 <b>{stats.correlation !== null && stats.correlation > 0 ? '+' : ''}{format(stats.correlation)}</b>{stats.count > 0 && `（${stats.count} 周）`}</span>
    </p>
    {indexes.map((query, i) => <ReadNotice key={WEEKLY_INDEXES[i].symbol} label={WEEKLY_INDEXES[i].name} query={query} />)}
    {indexes.some(query => query.isFetching) && <p role="status" className="executive-weekly-note">正在读取指数日线…</p>}
    {!archived && !local && <p className="executive-weekly-note">中证全指、创业板指、科创50由观衡本地行情提供。</p>}
    <WeeklyPlot weeks={weeks} archived={archived} />
    <p className="executive-weekly-note">{archived
      ? <>沪深北重要股东已披露买卖，按公告日汇总。区间内 {estimated.toLocaleString('zh-CN')} 笔使用历史价格估算，{unpriced.toLocaleString('zh-CN')} 笔缺价。* 标注部分周或缺价周，统计使用完整可计价周。</>
      : <>{scope}高管本人已披露买卖，按股份变动日汇总。* 标注部分周，统计使用完整周。</>} 披露覆盖 {coverage.start} 至 {coverage.end}。正值为净减持。</p>
  </section>
}
