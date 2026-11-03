import { useQuery } from '@tanstack/react-query'
import { absoluteChinaTime } from '../components/RelativeTime'
import { fetchOperations } from './operationsApi'
import { type RuntimeIssue } from './wtRuntimeApi'
import { fetchWtInstances } from './wtInstancesApi'
import './operations.css'
import { StatusBadge } from './StatusBadge'

const time = (value: string | null) => value ? absoluteChinaTime(value) : '未知'
const support = (value: boolean | null) => value === null ? '未知' : value ? '支持' : '未声明支持'
const queryLabels = { unconfigured: '未配置', responding: '本次可响应', unavailable: '不可用' }
const issueLabels = {first_reported: '首先报告的问题', also_reported: '同时报告的问题', unattributed: '问题说明'}

function IssueDetail({issue}: {issue?: RuntimeIssue | null}) {
  return issue ? <aside className="operations-issue" aria-label={issueLabels[issue.relation]}>
    <p><b>{issueLabels[issue.relation]}：</b>{issue.summary}</p>
    <p><b>影响：</b>{issue.impact}</p><p><b>处理：</b>{issue.action}</p>
  </aside> : null
}

export default function OperationsWorkspace() {
  const runtime = useQuery({queryKey:['independent-wt-instances'],queryFn:({signal})=>fetchWtInstances(signal),
    retry:false,refetchOnWindowFocus:false,refetchOnReconnect:false})
  const operations = useQuery({queryKey:['independent-operations'],queryFn:({signal})=>fetchOperations(signal),
    retry:false,refetchOnWindowFocus:false,refetchOnReconnect:false})
  const data = runtime.data; const query = operations.data?.query
  const fetching = runtime.isFetching || operations.isFetching
  return <section className="workspace-page operations-workspace">
    <header className="page-heading"><h1>系统状态</h1><button disabled={fetching}
      onClick={() => void Promise.all([runtime.refetch(), operations.refetch()])}>{fetching ? '正在读取…' : '重新读取状态'}</button></header>
    {runtime.isError ? <p role="alert">WT运行状态读取失败。{data ? '当前保留上次成功结果和时间。' : '请稍后重新读取。'}</p> : null}
    {data?.catalog_reason ? <p role="alert">{data.catalog_reason}</p> : null}
    {data?.instances.map(instance => <section key={instance.scope_id} className="surface-card runtime-instance" aria-label={`${instance.label}运行状态`}>
      <header><div><h2>{instance.label}</h2><StatusBadge state={instance.runtime?.state ?? instance.state}
        label={instance.runtime?.label ?? (instance.state === 'unavailable' ? '读取失败' : '未配置')} /></div><time>{time(instance.published_at)}</time></header>
      {instance.runtime ? <><ul className="runtime-component-list">{instance.runtime.components.map(item => <li key={item.name}>
        <div>{item.display_name}{item.data?.basis_date ? <small>数据交易日 {item.data.basis_date}</small> : null}</div>
        <StatusBadge state={item.state} label={item.label} />
        {item.issue || item.data ? <details className="compact-details"><summary>查看详情</summary><IssueDetail issue={item.issue} />
          {item.data ? <p>{item.data.label}{item.data.ready === null ? ' · 数据状态未知' : item.data.ready ? ' · 保留最近发布数据' : ' · 尚未发布策略数据'}
            {item.data.published_at ? ` · ${time(item.data.published_at)}` : ''}</p> : null}</details> : null}
      </li>)}</ul><details className="compact-details"><summary>实例说明</summary><p>显示此WT实例最近发布的状态。</p>
        <p>本次读取：{time(data.observed_at)}</p><IssueDetail issue={instance.runtime.issue} />
        <p>组件状态由WT发布，业务数据保留各自更新时间。</p></details></> : <p role="status">{instance.reason}</p>}
    </section>)}
    {operations.isError ? <p role="alert">行情查询状态读取失败。{query ? '当前保留上次成功结果和时间。' : '请稍后重新读取。'}</p> : null}
    {query ? <section className="surface-card runtime-instance" aria-label="行情查询服务">
      <header><div><h2>行情查询服务</h2><StatusBadge state={query.state} label={queryLabels[query.state]} /></div>
        <time>{time(operations.data!.observed_at)}</time></header>
      <ul className="runtime-component-list"><li><span>历史查询</span><StatusBadge state={query.history_supported ? 'responding' : 'unknown'} label={support(query.history_supported)} /></li>
        <li><span>快照查询</span><StatusBadge state={query.snapshot_supported ? 'responding' : 'unknown'} label={support(query.snapshot_supported)} /></li></ul>
      <details className="compact-details"><summary>连接说明</summary><p>{query.reason}</p></details>
    </section> : null}
  </section>
}
