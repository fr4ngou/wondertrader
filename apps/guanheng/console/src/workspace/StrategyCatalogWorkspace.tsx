import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchStrategyCatalog } from './strategyCatalogApi'
import './strategy-catalog.css'

/** 策略页仅展示登记资料；配置与算法细节由各自业务owner维护。 */
export default function StrategyCatalogWorkspace() {
  const [search, setSearch] = useState('')
  const query = useQuery({ queryKey: ['strategy-catalog'], queryFn: ({ signal }) => fetchStrategyCatalog(signal),
    retry: false, refetchOnWindowFocus: false })
  const data = !query.isError && !query.isFetching ? query.data : undefined
  const filter = search.trim().toLocaleLowerCase()
  const strategies = data?.filter(item => [item.display_name, item.strategy_id, item.strategy_version]
    .some(value => value.toLocaleLowerCase().includes(filter)))
  return <section className="workspace-page strategy-catalog-workspace">
    <header className="page-heading"><div><h1>策略</h1><p>查看策略简介与版本。</p></div></header>
    <label className="strategy-catalog-search">搜索策略<input value={search} onChange={event => setSearch(event.target.value)}
      placeholder="策略名称 / 版本" /></label>
    {query.isFetching ? <p role="status">正在读取策略目录…</p> : null}
    {query.isError ? <div role="alert"><p>{query.error.message}</p><button onClick={() => void query.refetch()}>重新读取策略</button></div> : null}
    {strategies ? <div className="surface-card strategy-summary-list">
      {strategies.map(item => <article className="strategy-summary-row" key={item.strategy_id + '@' + item.strategy_version}>
        <div className="strategy-summary-heading"><h2>{item.display_name}</h2><span className="strategy-summary-version">v{item.strategy_version}</span></div>
        <p>{item.description}</p>
      </article>)}
      {strategies.length === 0 ? <p role="status">{filter ? '没有匹配的策略。' : '当前没有登记策略。'}</p> : null}
    </div> : null}
  </section>
}
