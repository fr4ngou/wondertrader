import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'

import {
  fetchQmtConnectionStatus,
  QMT_CONNECTION_QUERY_KEY,
} from '../api'
import type { QMTConnectionStatus } from '../types'

interface QmtConnectionStatusOptions {
  refreshOnVisibility?: boolean
  initialData?: QMTConnectionStatus | null
}

export function useQmtConnectionStatus({
  refreshOnVisibility = false,
  initialData = null,
}: QmtConnectionStatusOptions = {}) {
  const query = useQuery({
    queryKey: QMT_CONNECTION_QUERY_KEY,
    queryFn: ({ signal }) => fetchQmtConnectionStatus(signal),
    initialData: initialData ?? undefined,
    initialDataUpdatedAt: initialData == null
      ? undefined
      : new Date(initialData.generated_at).getTime(),
    staleTime: 3_000,
    refetchInterval: 5_000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: 'always',
    retry: 1,
  })
  const refetch = query.refetch

  useEffect(() => {
    if (!refreshOnVisibility) return undefined
    const refreshVisibleStatus = () => {
      if (document.visibilityState === 'visible') void refetch()
    }
    document.addEventListener('visibilitychange', refreshVisibleStatus)
    window.addEventListener('focus', refreshVisibleStatus)
    return () => {
      document.removeEventListener('visibilitychange', refreshVisibleStatus)
      window.removeEventListener('focus', refreshVisibleStatus)
    }
  }, [refetch, refreshOnVisibility])

  return query
}
