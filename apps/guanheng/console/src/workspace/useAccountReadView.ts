import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchAccountOverview } from './accountApi'
import { accountReadView, type AccountReadView } from './accountPresentation'
import type { Capabilities } from './IndependentApp'

const accountOverviewKey = ['independent-account-overview'] as const

/** 行情和账户共用同一发布批次与同来源回退。 */
export function useAccountReadView(capability?: Capabilities['features'][string]) {
  const client = useQueryClient()
  return useQuery({
    queryKey: accountOverviewKey,
    queryFn: async ({ signal }) => accountReadView(await fetchAccountOverview(signal, capability?.timeout_seconds ?? 30),
      client.getQueryData<AccountReadView>(accountOverviewKey)),
    enabled: capability?.available === true, retry: false, refetchInterval: 15_000,
    refetchOnWindowFocus: false, refetchOnReconnect: false,
  })
}
