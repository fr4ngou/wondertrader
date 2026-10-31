import { useQuery } from '@tanstack/react-query'
import { absoluteChinaTime } from '../components/RelativeTime'
import { fetchStrategyRuntime, strategyRuntimeLabel } from './strategyRuntimeApi'
import './operations.css'
import './strategy-runtime.css'

const shares = (value: number | null) => value === null ? '未知' : value.toLocaleString('zh-CN')
const clock = (value: string | null) => value ? absoluteChinaTime(value) : '尚未取得'
const publishedLabels: Record<string,string> = {new:'待启动',starting:'启动中',stopping:'停止中',closed:'已停止',faulted:'失败'}

/** 总览只展示运行结果；目录、算法和运行部署分别由原入口拥有。 */
export default function StrategyRuntimeSummary() {
  const query = useQuery({ queryKey: ['independent-strategy-runtime'], queryFn: ({ signal }) => fetchStrategyRuntime(signal),
    retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false })
  const data = query.data
  const strategy = data?.strategy
  const active = strategy?.positions.filter(p => [p.broker_quantity, p.broker_sellable].some(n => n !== null && n > 0))
  const positionsComplete = strategy?.positions.every(p => p.broker_quantity !== null && p.broker_sellable !== null)
  return <section className="surface-card strategy-runtime-summary" aria-label="策略运行结果">
    <div className="operations-heading"><h2>策略运行结果</h2><button disabled={query.isFetching} onClick={() => void query.refetch()}>{query.isFetching ? '正在读取…' : '刷新策略结果'}</button></div>
    {query.isError ? <p role="alert">{query.error.message}{data ? '。当前保留上次成功结果和原数据时间。' : ''}</p> : null}
    {query.isFetching && data ? <p role="status">正在刷新，当前显示上次成功结果。</p> : null}
    {data?.state === 'unconfigured' ? <p role="status">当前尚未接入策略运行结果。</p> : null}
    {data?.state === 'waiting' ? <p role="status">等待策略发布运行结果。</p> : null}
    {data?.runtime_state && publishedLabels[data.runtime_state] ? <p role="status">WT最近发布：{publishedLabels[data.runtime_state]}。下方保留最后完整结果及原数据时间。</p> : null}
    {strategy ? <>
      <h3>{strategy.display_name} <small>v{strategy.strategy_version}</small></h3>
      <p role="status">{strategyRuntimeLabel(strategy)}</p>
      {strategy.status === 'waiting_market_input' ? <p>请维护人员在WT入口核对策略所需行情；实际持仓保留原查询时间。</p> : null}
      <p>决策时间（北京时间）：{clock(strategy.decision_at)}</p>
      <p>持仓接收时间（北京时间）：{clock(strategy.broker_observed_at)}</p>
      {!positionsComplete ? <p role="status">实际持仓信息尚未完整取得。</p> : null}
      {active?.length ? <div className="account-table-scroll runtime-table" role="region" aria-label="策略实际持仓" tabIndex={0}>
        <table><thead><tr><th>证券</th><th>实际持仓（份）</th><th>可卖（份）</th></tr></thead>
          <tbody>{active.map(p => <tr key={p.symbol} aria-label={`${p.symbol}策略结果`}>
            <th scope="row">{p.symbol}</th>
            <td>{shares(p.broker_quantity)}</td><td>{shares(p.broker_sellable)}</td>
          </tr>)}</tbody></table>
      </div> : null}
      {active?.length === 0 && positionsComplete ? <p>当前券商查询没有持仓。</p> : null}
      <p className="portfolio-data-note">实际持仓以券商查询为准；委托与成交见交易记录。</p>
    </> : null}
    {data ? <p className="portfolio-data-note">结果读取时间（北京时间）：{clock(data.observed_at)}</p> : null}
  </section>
}
