import { lazy, Suspense } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import StrategyCatalogWorkspace from './StrategyCatalogWorkspace'
import './strategy-catalog.css'

const BacktestWorkspace = lazy(() => import('./BacktestWorkspace'))

/** 复用旧QMT的策略目录层级；策略介绍与原回测分别呈现。 */
export default function StrategyWorkspace() {
  const [params] = useSearchParams()
  const tab = params.get('tab') === 'backtests' ? 'backtests' : 'catalog'
  function target(value: string) { const next = new URLSearchParams(params); next.set('tab', value); return `/strategies?${next}` }
  return <div className="strategy-workspace">
    <nav className="strategy-workspace-tabs account-actions" aria-label="策略工作区">
      <Link to={target('catalog')} aria-current={tab === 'catalog' ? 'page' : undefined}>策略详情</Link>
      <Link to={target('backtests')} aria-current={tab === 'backtests' ? 'page' : undefined}>回测与报告</Link>
    </nav>
    {tab === 'catalog' ? <StrategyCatalogWorkspace />
      : <Suspense fallback={<p role="status">正在加载回测…</p>}><BacktestWorkspace /></Suspense>}
  </div>
}
