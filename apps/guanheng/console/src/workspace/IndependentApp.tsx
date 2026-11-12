import { lazy, Suspense } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { fetchReadJson } from '../api'
import './independent.css'
import { ObserverLayout } from './ObserverLayout'

const MinuteWorkspace = lazy(() => import('./MinuteWorkspace'))
const AccountWorkspace = lazy(() => import('./AccountWorkspace'))
const StrategyWorkspace = lazy(() => import('./StrategyWorkspace'))
const BacktestWorkspace = lazy(() => import('./BacktestWorkspace'))
const OperationsWorkspace = lazy(() => import('./OperationsWorkspace'))
const ObservationShell = lazy(() => import('../observation/ObservationShell'))
const navigation = [
  ['dashboard', '总览'], ['market', '行情'], ['observation', '市场观察'],
  ['strategies', '策略'], ['account', '账户'], ['orders', '交易记录'], ['operations', '系统状态'],
] as const

export type Capabilities = { read_only: boolean; features: Record<string, {
  available: boolean; periods?: string[]; timeout_seconds?: number; reason: string | null
}> }

const unknownFeatures: Capabilities['features'] = {
  minute_chart: { available: false, periods: ['1m', '5m', '1d'], reason: '连接信息暂不可用，可直接查询行情。' },
  account: { available: false, reason: '连接信息暂不可用，可主动刷新账户。' },
}

async function readCapabilities(signal: AbortSignal): Promise<Capabilities> {
  const data = await fetchReadJson<Capabilities>('/v1/ui/capabilities', '应用能力', signal, 'status')
  if (data == null || typeof data !== 'object' || data.read_only !== true || typeof data.features?.minute_chart?.available !== 'boolean') {
    throw new Error('应用能力格式无效，当前保持只读')
  }
  return data
}

export default function IndependentApp() {
  const capability = useQuery({ queryKey: ['independent-capabilities'], queryFn: ({ signal }) => readCapabilities(signal), retry: false })
  const features = capability.data?.features ?? unknownFeatures
  const location = useLocation()
  const title = navigation.find(([id]) => location.pathname.startsWith(`/${id}`))?.[1] ?? '工作区'
  if (location.pathname === '/observation' || location.pathname.startsWith('/observation/')) {
    return <ObserverLayout connected={Boolean(capability.data)} failed={capability.isError}>
      <Suspense fallback={<p role="status">正在加载市场观察…</p>}><ObservationShell embedded /></Suspense>
    </ObserverLayout>
  }
  return <ObserverLayout connected={Boolean(capability.data)} failed={capability.isError}>
      {capability.isError ? <section className="workspace-page" role="alert"><h2>连接信息暂时无法更新</h2><p>{capability.error.message}</p>{capability.data ? <p>当前保留已读取的页面及连接信息，可继续查看数据和各自的查询时间。</p> : null}<button onClick={() => void capability.refetch()}>重新读取连接信息</button></section> : null}
      {capability.isPending ? <p role="status">正在读取连接信息…</p> : null}
      <Suspense fallback={<p role="status">正在加载工作区…</p>}><Routes>
            <Route path="/" element={<Navigate to="/market" replace />} />
            <Route path="/dashboard" element={<AccountWorkspace key="overview" view="overview" capability={features.account ?? unknownFeatures.account} />} />
            <Route path="/market" element={<MinuteWorkspace capability={features.minute_chart} capabilityPending={capability.isPending} accountCapability={features.account} watchlistCapability={features.personal_watchlist} searchCapability={features.security_search} initialSearch={new URLSearchParams(location.search).get('search') ?? ''} />} />
            <Route path="/account" element={<AccountWorkspace capability={features.account ?? unknownFeatures.account} />} />
            <Route path="/orders" element={<AccountWorkspace key="trading-records" view="trading-records" capability={features.account ?? unknownFeatures.account} />} />
            <Route path="/strategies" element={<StrategyWorkspace />} />
            <Route path="/operations" element={<OperationsWorkspace />} />
            <Route path="/portfolio" element={<StrategyTabRedirect tab="holdings" />} />
            <Route path="/backtests" element={<BacktestWorkspace />} />
            {['/research/*', '/news/*'].map(path => <Route path={path} element={<Navigate to="/market" replace />} key={path} />)}
            <Route path="/grafana/*" element={<Navigate to="/operations" replace />} />
            <Route path="/audit" element={<Navigate to="/operations" replace />} />
            <Route path="*" element={<section className="workspace-page"><h1>{title}</h1><EmptyState title="该功能尚未接通" detail="当前版本尚未接通此功能，可先使用行情页查看已接入的分钟数据。" /></section>} />
          </Routes></Suspense>
  </ObserverLayout>
}

function StrategyTabRedirect({ tab }: { tab: string }) {
  const { search } = useLocation()
  const params = new URLSearchParams(search)
  params.set('tab', tab)
  return <Navigate to={`/strategies?${params}`} replace />
}
