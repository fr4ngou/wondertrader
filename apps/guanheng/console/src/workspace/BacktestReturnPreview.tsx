import type { ArchivePerformancePreview } from './backtestApi'

/** 只绘制目录提供的样本，保留缺口；完整交互仍在报告分析。 */
export default function BacktestReturnPreview({ points, count }: {
  /** 按原记录序号排序的累计收益率样本。 */
  points: ArchivePerformancePreview['points']
  /** 原报告期数，用于按原时间顺序定位横坐标。 */
  count: number
}) {
  const observed = points.flatMap(([, value]) => value === null ? [] : [value])
  if (!observed.length) return null
  const scale = Math.max(1, ...observed.map(Math.abs))
  const min = Math.min(...observed) / scale
  const max = Math.max(...observed) / scale
  const segments: [number, number][][] = []
  let segment: [number, number][] = []
  for (const [index, value] of points) {
    if (value === null) {
      segment = []
      continue
    }
    if (!segment.length) segments.push(segment)
    const x = count > 1 ? 2 + 104 * index / (count - 1) : 54
    const y = max === min ? 14 : 26 - 24 * (value / scale - min) / (max - min)
    segment.push([x, y])
  }
  return <svg className="bt-return-preview" role="img" aria-label="累计收益率小图" viewBox="0 0 108 28">
    {segments.map(line => line.length === 1
      ? <circle key={line[0][0]} cx={line[0][0]} cy={line[0][1]} r="1.7" fill="currentColor" />
      : <polyline key={line[0][0]} points={line.map(point => point.join(',')).join(' ')}
          fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />)}
  </svg>
}
