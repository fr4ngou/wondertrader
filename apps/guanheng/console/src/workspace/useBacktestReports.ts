import { useIsFetching, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchBacktestArchiveSummaries, type ArchiveEntry } from './backtestApi'
import { fetchBacktestPerformance } from './backtestPerformanceApi'

export const performanceKey = (entry: ArchiveEntry) => ['backtest-performance', entry.run_id, entry.receipt_sha256, entry.report_sha256]

/** 策略页和回测页复用轻量完成归档；单份完整原件仍由报告分析按需读取。 */
export function useBacktestArchiveSummaries() {
  return useQuery({ queryKey: ['native-backtest-archive-summaries'],
    queryFn: ({ signal }) => fetchBacktestArchiveSummaries(signal), retry: false,
    staleTime: Infinity, refetchOnWindowFocus: false, refetchOnReconnect: false })
}

/** 只对用户当前选中的主/对比报告读取完整绩效，复用同一完成身份的缓存。 */
export function useBacktestReports(entries: ArchiveEntry[], enabled: boolean) {
  const client = useQueryClient()
  const active = useIsFetching({ predicate: query => query.queryKey[0] === 'backtest-performance' || query.queryKey[0] === 'backtest-comparison' })
  let slots = Math.max(0, 2 - active)
  return useQueries({ queries: entries.map(entry => {
    const state = client.getQueryState(performanceKey(entry))
    // 按实际在途读取占槽；缓存穿插、目录重排及离开旧选择后仍在收尾的请求共享两槽。
    const waiting = (!state || state.status === 'pending') && state?.fetchStatus !== 'fetching'
    const admitted = !waiting || slots-- > 0
    return { queryKey: performanceKey(entry), queryFn: ({ signal }: { signal: AbortSignal }) => fetchBacktestPerformance(entry, signal),
      enabled: enabled && admitted,
      staleTime: Infinity, retry: false, retryOnMount: false, refetchOnWindowFocus: false, refetchOnReconnect: false }
  }) })
}
