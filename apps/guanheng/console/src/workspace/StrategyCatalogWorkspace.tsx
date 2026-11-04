import { Link, useSearchParams } from 'react-router-dom'
import StrategyDetails from './StrategyDetails'
import { StrategyPicker, strategyKey, useStrategySelection } from './StrategyPicker'

/** 策略目录决定当前选择，运行详情按同一身份读取。 */
export default function StrategyCatalogWorkspace() {
  const selection = useStrategySelection()
  const [params, setParams] = useSearchParams()
  const selected = selection.selected
  const description = params.get('view') === 'description'
  function view(value: string) {
    const next = new URLSearchParams(params); next.set('view', value); setParams(next)
  }
  return <section className="workspace-page strategy-catalog-workspace">
    <header className="strategy-page-heading"><h1>策略</h1><StrategyPicker selection={selection} />
      {selected ? <Link className="strategy-backtest-link" to={'/backtests?' + new URLSearchParams({ strategy: strategyKey(selected) })}>查看该策略回测 →</Link> : null}
    </header>
    {selected ? <>
      <div className="strategy-selected"><h2>{selected.display_name}</h2><span>{selected.strategy_version === null ? '版本未提供' : `版本 ${selected.strategy_version}`} </span></div>
      <nav className="strategy-view-tabs" aria-label="策略详情视图">
        <button aria-pressed={!description} onClick={() => view('runtime')}>运行与持仓</button>
        <button aria-pressed={description} onClick={() => view('description')}>策略说明</button>
      </nav>
      {description ? <p className="strategy-description">{selected.description}</p>
        : <StrategyDetails key={strategyKey(selected)} strategy={selected} />}
    </> : null}
  </section>
}
