import { useIsFetching, useQueries, useQueryClient } from '@tanstack/react-query'
import type { ArchiveEntry } from './backtestApi'
import { fetchBacktestPerformance } from './backtestPerformanceApi'

export const performanceKey = (entry: ArchiveEntry) => ['backtest-performance', entry.run_id, entry.receipt_sha256, entry.report_sha256]

/** 沿原绩效接口核实报告归属，最多两份并行，复用同一完成身份的查询缓存。 */
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
