import type { Range } from '../observation/types'
import { keyboardRange } from '../observation/dates'
import type { ReactNode } from 'react'

const dayMs = 86_400_000
const dateControls = [
  ['ArrowUp', '放大日期'], ['ArrowDown', '缩小日期'], ['ArrowLeft', '前移日期'], ['ArrowRight', '后移日期'],
] as const

export function ChartDateControls({ range, coverage, onRange, children }: {
  range: Range; coverage?: Range; onRange: (range: Range) => void; children?: ReactNode
}) {
  return <div className="observer-chart-tools" role="group" aria-label="图表日期">
    {coverage ? dateControls.map(([key, label]) => {
      const next = keyboardRange(key, range, coverage)
      return <button key={key} type="button" disabled={!next || next.start === range.start && next.end === range.end}
        onClick={() => { if (next) onRange(next) }}>{label}</button>
    }) : null}
    {children}
  </div>
}

/** 以日历跨度展示区间的相对位置，比例不代表数据完整率。 */
export function ChartHistoryTrack({ coverage, range, label = '可读历史' }: { coverage: Range; range: Range; label?: string }) {
  const start = Date.parse(coverage.start)
  const end = Date.parse(coverage.end) + dayMs
  const span = end - start
  const left = Math.min(end, Math.max(start, Date.parse(range.start)))
  const right = Math.max(left, Math.min(end, Date.parse(range.end) + dayMs))
  if (!Number.isFinite(right - left) || !Number.isFinite(span) || span <= 0) return null
  const offset = (left - start) / span * 100
  const width = (right - left) / span * 100
  const percent = width > 0 && width < .1 ? '<0.1%' : `${Number(width.toFixed(1))}%`
  return <div className="chart-history-track" role="group" aria-label="历史时间轴">
    <div className="chart-history-summary"><span>{label}</span><span>当前 {range.start} 至 {range.end} · {percent}</span></div>
    <div className="chart-history-rail" aria-hidden="true">{width > 0 ? <span style={{ left: `${offset}%`, width: `${width}%` }} /> : null}</div>
    <div className="chart-history-labels"><time>{coverage.start}</time><time>{coverage.end}</time></div>
  </div>
}
