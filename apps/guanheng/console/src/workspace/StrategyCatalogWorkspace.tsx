import { Link, useSearchParams } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import StrategyDetails from './StrategyDetails'
import { StrategyPicker, strategyKey, useStrategySelection } from './StrategyPicker'
import { useLiveStrategyPerformance } from './liveStrategyApi'
import './live-strategy.css'

const LiveStrategyPerformance = lazy(() => import('./LiveStrategyPerformance'))
const StrategyTargetHistory = lazy(() => import('./StrategyTargetHistory'))

/** 策略目录决定当前选择，运行详情按同一身份读取。 */
export default function StrategyCatalogWorkspace() {
  const selection = useStrategySelection()
  const [params, setParams] = useSearchParams()
  const selected = selection.selected
  const live = useLiveStrategyPerformance(selected)
  const online = !!live.data?.current.is_current && !live.isError
  const hasObservation = live.data?.state === 'available' && live.data.current.key_matches
  const selectedView = params.get('view') ?? (hasObservation ? 'performance' : 'runtime')
  const description = selectedView === 'description'
  const unavailable = live.data?.state === 'not_current' && !live.isError
  function view(value: string) {
    const next = new URLSearchParams(params); next.set('view', value); setParams(next)
  }
  return <section className="workspace-page strategy-catalog-workspace">
    <header className="strategy-page-heading"><h1>策略</h1><StrategyPicker selection={selection} />
      {selected ? <Link className="strategy-backtest-link" to={'/backtests?' + new URLSearchParams({ strategy: strategyKey(selected) })}>查看该策略回测 →</Link> : null}
    </header>
    {selected ? <>
      <div className="strategy-selected"><h2>{selected.display_name}</h2><span>{selected.strategy_version === null ? '版本未提供' : `版本 ${selected.strategy_version}`} </span>
        {online ? <span className="strategy-live-badge" role="status">线上运行 · 已核验</span>
          : <span className="strategy-offline-badge" role="status">{live.isPending ? '正在核验运行状态…' : !live.isError && (live.data?.state === 'not_current' || live.data?.current.process_state === 'exited') ? '当前未在线运行' : '运行状态待确认'}</span>}
      </div>
      {live.isError ? <p role="alert">{live.error.message}；当前在线标记待重新核验。<button onClick={() => void live.refetch()}>重试运行状态</button></p> : null}
      <nav className="strategy-view-tabs" aria-label="策略详情视图">
        <button aria-pressed={selectedView === 'performance'} onClick={() => view('performance')}>线上表现</button>
        <button aria-pressed={!description && selectedView !== 'performance' && selectedView !== 'targets'} onClick={() => view('runtime')}>运行与持仓</button>
        <button aria-pressed={selectedView === 'targets'} onClick={() => view('targets')}>目标仓位记录</button>
        <button aria-pressed={description} onClick={() => view('description')}>策略说明</button>
      </nav>
      {description ? <p className="strategy-description">{selected.description}</p>
        : selectedView === 'targets' ? <Suspense fallback={<p role="status">正在加载目标记录…</p>}><StrategyTargetHistory key={strategyKey(selected)} strategy={selected} /></Suspense>
        : selectedView === 'performance' ? hasObservation && live.data ? <>
          {!online ? <p role="status">当前运行状态尚未确认，以下保留已观察事实及其原时间。</p> : null}
          <Suspense fallback={<p role="status">正在加载线上图表…</p>}><LiveStrategyPerformance key={`${strategyKey(selected)}:${live.data.coverage.history_scope_id ?? live.data.current.scope_id}`} data={live.data} /></Suspense>
        </> : <StrategyObservationStatus title="线上表现" message={
          live.isPending ? '正在读取线上表现…' : live.isError ? '线上表现读取失败，请重试运行状态。'
            : live.data?.reason ?? '所选策略版本尚无线上的净值或成交记录。'
        } />
        : unavailable ? <StrategyObservationStatus title="当前持仓与运行" message={live.data?.reason ?? '当前没有该版本的运行与持仓发布。'} />
        : <StrategyDetails key={strategyKey(selected)} strategy={selected} />}
    </> : null}
  </section>
}

function StrategyObservationStatus({ title, message }: { title: string; message: string }) {
  return <section className="surface-card strategy-compact" aria-label={title}>
    <h3>{title}</h3>
    <p role="status">{message}</p>
  </section>
}
