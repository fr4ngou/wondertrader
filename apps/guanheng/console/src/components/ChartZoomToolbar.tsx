import type { RefObject } from 'react'
import { getInstanceByDom } from 'echarts/core'
import { Minus, Plus, RotateCcw } from 'lucide-react'

/** 只改变当前图的可见范围，仍由原图处理数据、日期和选中点。 */
export function ChartZoomToolbar({ plot }: { plot: RefObject<HTMLDivElement | null> }) {
  function zoom(factor?: number) {
    const chart = plot.current ? getInstanceByDom(plot.current) : undefined
    if (!chart) return
    if (factor === undefined) {
      chart.dispatchAction({ type: 'dataZoom', start: 0, end: 100 })
      return
    }
    const window = (chart.getOption().dataZoom as { start: number; end: number }[] | undefined)?.[0]
    if (!window) return
    const width = Math.min(100, Math.max(0.5, (window.end - window.start) * factor))
    const start = Math.max(0, Math.min(100 - width, (window.start + window.end - width) / 2))
    chart.dispatchAction({ type: 'dataZoom', start, end: start + width })
  }
  return <div className="observer-chart-tools" role="group" aria-label="图表缩放">
    <button type="button" onClick={() => zoom(0.75)} aria-label="放大图表" title="放大图表"><Plus size={15} /></button>
    <button type="button" onClick={() => zoom(1.33)} aria-label="缩小图表" title="缩小图表"><Minus size={15} /></button>
    <button type="button" onClick={() => zoom()} aria-label="显示完整区间" title="显示完整区间"><RotateCcw size={14} /></button>
  </div>
}
