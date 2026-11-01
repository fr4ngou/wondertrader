import { useQuery } from '@tanstack/react-query'
import { absoluteChinaTime } from '../components/RelativeTime'
import { fetchOperations } from './operationsApi'
import { type RuntimeIssue } from './wtRuntimeApi'
import { fetchWtInstances } from './wtInstancesApi'
import './operations.css'

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
    <div className="operations-heading"><div><h1>系统状态</h1><p>查看WT发布的运行状态和行情查询结果。</p></div>
      <button disabled={fetching} onClick={()=>void Promise.all([runtime.refetch(),operations.refetch()])}>{fetching?'正在读取…':'重新读取状态'}</button></div>
    {runtime.isFetching?<p role="status">正在读取WT运行状态…</p>:null}
    {runtime.isError?<p role="alert">WT运行状态读取失败。{data?'当前保留上次成功结果和时间。':'请稍后重新读取。'}</p>:null}
    {data?.catalog_reason?<p role="alert">{data.catalog_reason}</p>:null}
    {data?data.instances.map(instance=><section key={instance.scope_id} className="surface-card" aria-label={`${instance.label}运行状态`}><h2>{instance.label}</h2>
      <p>{instance.runtime?'显示此WT实例最近发布的状态，数据时间见各工作区。':instance.reason}</p><p>本次读取：{time(data.observed_at)}</p>
      {instance.runtime?<><strong>最近发布：{instance.runtime.label}</strong><p>状态更新时间：{time(instance.published_at)}</p>
        <IssueDetail issue={instance.runtime.issue}/>
        <dl className="operations-facts">
          {instance.runtime.components.map(item=><div key={item.name}><dt>{item.display_name}</dt><dd>{item.label}
            <IssueDetail issue={item.issue}/>
            {item.data?<><p>{item.data.label}</p><p>{item.data.ready === null?'数据状态未知':item.data.ready?'保留最近发布数据':'尚未发布策略数据'}</p>
              {item.data.basis_date?<p>最近数据交易日：{item.data.basis_date}</p>:null}
              {item.data.published_at?<p>最近数据发布：{time(item.data.published_at)}</p>:null}</>:null}
          </dd></div>)}
        </dl></>:null}
      <p>观衡只读取已发布结果；关闭或更新观衡后，WT继续独立运行。</p>
    </section>):null}
    {operations.isError?<p role="alert">行情查询状态读取失败。{query?'当前保留上次成功结果和时间。':'请稍后重新读取。'}</p>:null}
    {query?<section className="surface-card" aria-label="行情查询服务"><h2>行情查询服务</h2><strong>{queryLabels[query.state]}</strong>
      <p>{query.reason}</p><p>本次读取：{time(operations.data!.observed_at)}</p>
      <dl className="operations-facts"><div><dt>历史查询</dt><dd>{support(query.history_supported)}</dd></div>
        <div><dt>快照查询</dt><dd>{support(query.snapshot_supported)}</dd></div>
        <div><dt>服务来源</dt><dd>{query.source??'未知'}</dd></div></dl>
      <p>具体行情的日期、缺口和单位，请在行情页查看。</p>
    </section>:null}
  </section>
}
