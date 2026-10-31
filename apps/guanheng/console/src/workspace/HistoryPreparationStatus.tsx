import { useQuery } from '@tanstack/react-query'
import { absoluteChinaTime } from '../components/RelativeTime'
import { fetchHistoryPreparation } from './historyPreparationApi'
import ProcessCard from './ProcessCard'

export function useHistoryPreparationStatus() {
  return useQuery({ queryKey: ['independent-history-preparation'],
    queryFn: ({ signal }) => fetchHistoryPreparation(signal), retry: false, refetchOnWindowFocus: false, staleTime: 0 })
}

export function HistoryPreparationStatus({ query }: { query: ReturnType<typeof useHistoryPreparationStatus> }) {
  return <>
    {query.isFetching ? <p role="status">正在读取历史补齐进程…{query.data ? '当前显示上次读取的状态和时间。' : ''}</p> : null}
    {query.isError ? <p role="alert">历史补齐状态读取失败：{query.error.message}。{query.data ? '当前保留上次读取的状态和时间。' : '请稍后重新读取。'}</p> : null}
    {query.data ? <ProcessCard title="历史补齐进程" status={query.data.process}
      impact={`状态读取时间：${absoluteChinaTime(query.data.observed_at)}。来源连接：待核实。监听就绪后仍需核实际补齐结果及历史回读的覆盖、日期和单位。`} /> : null}
  </>
}

export function HistoryPreparationOverview() {
  const query = useHistoryPreparationStatus()
  return <section className="surface-card" aria-label="历史补齐进程">
    <div className="operations-heading"><h2>历史数据更新</h2><button disabled={query.isFetching}
      onClick={() => void query.refetch()}>{query.isFetching ? '正在读取补齐状态…' : '重新读取补齐状态'}</button></div>
    {query.isError ? <p role="alert">{query.error.message}。{query.data ? '当前保留上次读取结果和时间。' : '请稍后重新读取。'}</p> : null}
    {query.data ? <><p>{query.data.process.label}</p><p className="portfolio-data-note">状态读取时间：{absoluteChinaTime(query.data.observed_at)}。具体历史范围见行情查询。</p></>
      : query.isPending ? <p role="status">正在读取历史补齐进程…</p> : null}
  </section>
}
