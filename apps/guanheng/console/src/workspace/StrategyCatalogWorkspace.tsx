import { Link, useSearchParams } from 'react-router-dom'
import StrategyDetails from './StrategyDetails'
import { StrategyPicker, strategyKey, useStrategySelection } from './StrategyPicker'
import { ORIGINAL_STRATEGY, ORIGINAL_WT_STRATEGY } from './originalBacktestApi'

/** 策略目录决定当前选择，运行详情按同一身份读取。 */
export default function StrategyCatalogWorkspace() {
  const selection = useStrategySelection()
  const [params, setParams] = useSearchParams()
  const selected = selection.selected
  const description = params.get('view') === 'description'
  const reference = selected?.strategy_id === ORIGINAL_STRATEGY
  const original = reference || selected?.strategy_id === ORIGINAL_WT_STRATEGY
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
        <button aria-pressed={!description} onClick={() => view('runtime')}>{original ? '研究概况' : '运行与持仓'}</button>
        <button aria-pressed={description} onClick={() => view('description')}>策略说明</button>
      </nav>
      {description ? <p className="strategy-description">{selected.description}</p>
        : original ? <section className="surface-card strategy-compact" aria-label="原版研究概况">
          <h3>原版研究与回测</h3><p>固定原仓库提交 351f9d5 的 stable 算法，独立还原九只 ETF 的交易信号与组合模拟。</p>
          {reference ? <p>原组合对照采用下一交易日收盘成交、浮点份额和零费用，初始归一化权益为 1。服务器原字段与 QMT 重算报告分别保留来源和区间。</p>
            : <p>正式回测使用 WT 框架的历史时钟、仓位和撮合。原版 BUY/SELL 信号按真实日线推进，已提交合法目标在下一个模拟 tick 撮合，冻结份额按 WT 规则延后；费用、整手约束和人民币资金以各份 WT 报告为准。</p>}
          <p className="strategy-catalog-note">当前展示离线研究结果，历史首次可知时点资格待核实。</p>
          <Link to={'/backtests?' + new URLSearchParams({ strategy: strategyKey(selected) })}>查看原版回测记录 →</Link>
        </section> : <StrategyDetails key={strategyKey(selected)} strategy={selected} />}
    </> : null}
  </section>
}
