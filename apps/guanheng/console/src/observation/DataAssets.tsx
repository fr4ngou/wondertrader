import { useDeferredValue, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getDefinition } from './api'
import { ReadNotice } from './ReadNotice'
import { frequencyLabel, sourceLabel } from './presentation'
import type { Catalog } from './types'

const count = (n: number) => new Intl.NumberFormat('zh-CN').format(n)

export function DataAssets({ catalog }: { catalog: Catalog }) {
  const [filter, setFilter] = useState('')
  const term = useDeferredValue(filter.trim().toLocaleLowerCase())
  const [frequency, setFrequency] = useState('')
  const [selection, setSelection] = useState(catalog.datasets[0]?.id || '')
  const selected = catalog.datasets.some(item => item.id === selection) ? selection : catalog.datasets[0]?.id || ''
  const definition = useQuery({ retry: false, queryKey: ['observation', 'definition', selected, catalog.snapshot_id],
    queryFn: ({ signal }) => getDefinition(selected, catalog.snapshot_id, signal), enabled: !!selected })
  const visible = catalog.datasets.filter(item => (!frequency || item.frequency === frequency)
    && `${item.label} ${sourceLabel(item.source || '')}`.toLocaleLowerCase().includes(term))
  const d = definition.data?.definition
  return <section className="observation-panel"><h2>指标说明</h2>
    <p>查看每项指标的来源、覆盖日期、计算方法和读法。</p>
    <div className="observation-inline observation-data-controls">
      <label>搜索<input aria-label="搜索指标说明" placeholder="指标名称或来源" value={filter} maxLength={200} onChange={event => setFilter(event.target.value)} /></label>
      <label>频率<select aria-label="按频率筛选" value={frequency} onChange={event => setFrequency(event.target.value)}>
        <option value="">全部频率</option>{[...new Set(catalog.datasets.map(item => item.frequency))].map(item => <option key={item} value={item}>{frequencyLabel(item)}</option>)}
      </select></label>
    </div>
    {!catalog.datasets.length ? <p role="status">当前尚无已发布的指标，请查看更新与缺口。</p> : <div className="observation-asset-grid"><div>
      <p>符合条件 {visible.length} 项</p>
      <div className="observation-table-scroll"><table><thead><tr><th>指标 / 来源</th><th>频率</th><th>覆盖日期</th><th>观察条数</th></tr></thead>
        <tbody>{visible.map(item => <tr key={item.id}><td><button className="observation-link" aria-pressed={selected === item.id} onClick={() => setSelection(item.id)}>{item.label}</button>
          <small>{item.source ? sourceLabel(item.source) : '来源说明待补'}</small></td><td>{frequencyLabel(item.frequency)}</td><td>{item.coverage.start}<br />{item.coverage.end}</td><td>{count(item.coverage.observations)}</td></tr>)}</tbody>
      </table></div>
      {!visible.length && <p role="status">没有符合条件的指标，请调整搜索或频率。</p>}
    </div><aside>
      <ReadNotice label="指标说明" query={definition} />
      {definition.isPending ? <p role="status">正在读取指标说明…</p> : null}
      {d && <><h3>{d.label}</h3>
        <Link className="observation-button" to={'/observation?' + new URLSearchParams({ metric: d.id, snapshot_id: catalog.snapshot_id, preset: catalog.datasets.find(item=>item.id===d.id)?.default_preset || 'd30' })}>在看板查看</Link>
        <p>来源：{sourceLabel(d.source)}{d.source_url && <> · <a href={d.source_url} target="_blank" rel="noreferrer">查看来源页面</a></>}</p>
        <p>{frequencyLabel(d.frequency)} · 覆盖 {d.coverage.start} 至 {d.coverage.end} · {count(d.coverage.observations)} 条观察</p>
        <h4>计算方法</h4><p>{d.formula}</p><h4>如何阅读</h4><p>{d.reading}</p>
        <h4>字段含义</h4><ul>{Object.entries(d.field_schema).map(([key, field]) => <li key={key}>{field.label}{field.unit && `（${field.unit}）`}</li>)}</ul>
        {d.limitations.length > 0 && <><h4>使用范围</h4><ul>{d.limitations.map((text, index) => <li key={index}>{text}</li>)}</ul></>}
      </>}
    </aside></div>}
  </section>
}
