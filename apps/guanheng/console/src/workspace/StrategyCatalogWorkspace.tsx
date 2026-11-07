import { Link, useSearchParams } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import StrategyDetails from './StrategyDetails'
import { StrategyPicker, strategyKey, useStrategySelection } from './StrategyPicker'
import { ORIGINAL_WT_STRATEGY } from './originalNativeIdentity'
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
  const original = selected?.strategy_id === ORIGINAL_WT_STRATEGY
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
        {hasObservation ? <button aria-pressed={selectedView === 'performance'} onClick={() => view('performance')}>线上表现</button> : null}
        <button aria-pressed={!description && selectedView !== 'performance' && selectedView !== 'targets'} onClick={() => view('runtime')}>{original && !hasObservation ? 'WT回测概况' : '运行与持仓'}</button>
        {!original || hasObservation ? <button aria-pressed={selectedView === 'targets'} onClick={() => view('targets')}>目标仓位记录</button> : null}
        <button aria-pressed={description} onClick={() => view('description')}>策略说明</button>
      </nav>
      {description ? <p className="strategy-description">{selected.description}</p>
        : selectedView === 'targets' && (!original || hasObservation) ? <Suspense fallback={<p role="status">正在加载目标记录…</p>}><StrategyTargetHistory key={strategyKey(selected)} strategy={selected} /></Suspense>
        : hasObservation && selectedView === 'performance' && live.data ? <>
          {!online ? <p role="status">当前运行状态尚未确认，以下保留已观察事实及其原时间。</p> : null}
          <Suspense fallback={<p role="status">正在加载线上图表…</p>}><LiveStrategyPerformance key={`${strategyKey(selected)}:${live.data.coverage.history_scope_id ?? live.data.current.scope_id}`} data={live.data} /></Suspense>
        </>
        : original && !hasObservation ? <section className="surface-card strategy-compact" aria-label="原版WT回测概况">
          <h3>原版研究与回测</h3><p>固定原仓库提交 351f9d5 的 stable 算法，独立还原九只 ETF 的交易信号与组合模拟。</p>
          <p>回测使用 WT 框架的历史时钟、仓位和撮合。原版 BUY/SELL 信号按真实日线推进，已提交合法目标在下一个模拟 tick 撮合，冻结份额按 WT 规则延后；费用、整手约束和人民币资金以各份 WT 报告为准。</p>
          <p className="strategy-catalog-note">当前展示离线研究结果，历史首次可知时点资格待核实。</p>
          <Link to={'/backtests?' + new URLSearchParams({ strategy: strategyKey(selected) })}>查看原版回测记录 →</Link>
        </section> : <StrategyDetails key={strategyKey(selected)} strategy={selected} />}
    </> : null}
  </section>
}
