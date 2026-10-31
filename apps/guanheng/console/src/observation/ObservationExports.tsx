import { useState } from 'react'
import { ObservationDownload } from './ObservationDownload'
import type { Catalog } from './types'

export function ObservationExports({ catalog }: { catalog: Catalog }) {
  const [selection, setSelection] = useState(catalog.datasets[0]?.id || '')
  const metric = catalog.datasets.find(item => item.id === selection) || catalog.datasets[0]
  const [range, setRange] = useState({ start: metric?.coverage.start || '', end: metric?.coverage.end || '' })
  const valid = !!metric && !!range.start && !!range.end && range.start <= range.end
    && range.start >= metric.coverage.start && range.end <= metric.coverage.end
  return <section className="observation-panel"><h2>导出观察数据</h2>
    <p>选择指标和日期，下载当前页面所用的数据版本。CSV 可用表格软件打开；JSON 和 JSONL 供程序读取。空值表示该项数据缺失。</p>
    {!metric ? <p role="status">当前尚无可导出的指标，请查看更新与缺口。</p> : <>
      <div className="observation-inline observation-data-controls">
        <label>指标<select aria-label="导出指标" value={metric.id} onChange={event => {
          const next = catalog.datasets.find(item => item.id === event.target.value)!
          setSelection(next.id); setRange({ start: next.coverage.start, end: next.coverage.end })
        }}>{catalog.datasets.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        <label>开始日期<input type="date" aria-label="导出开始日期" min={metric.coverage.start} max={metric.coverage.end} value={range.start} onChange={event => setRange({ ...range, start: event.target.value })} /></label>
        <label>结束日期<input type="date" aria-label="导出结束日期" min={metric.coverage.start} max={metric.coverage.end} value={range.end} onChange={event => setRange({ ...range, end: event.target.value })} /></label>
      </div>
      <p>可用日期：{metric.coverage.start} 至 {metric.coverage.end}。</p>
      {valid ? <div className="observation-inline">{['csv', 'json', 'jsonl'].map(format => <ObservationDownload key={format} params={{ metric_id: metric.id, snapshot_id: catalog.snapshot_id, ...range, format }} filename={`${metric.label}-${range.start}-${range.end}.${format}`}>{'下载 ' + format.toUpperCase()}</ObservationDownload>)}</div>
        : <p role="status">请选择覆盖范围内的日期，开始日期须早于或等于结束日期。</p>}
    </>}
  </section>
}
