import type { StrategyWorkbenchDetail } from '../types'
import { absoluteChinaTime } from './RelativeTime'

const signals: Record<string, string> = { BUY: '买入', SELL: '卖出', HOLD: '保持' }
const exits: Record<string, string> = {
  sh50_trailing_exit: '持有满 10 个交易日，较持仓期最高收盘价回撤超过 5%',
  sc50_trailing_exit: '持有满 10 个交易日，较持仓期最高收盘价回撤超过 10%',
  kc50_trailing_exit: '持有满 10 个交易日，回撤超过 8%，且无大额申购豁免',
  sh50_large_redemption: '大额赎回退出', kc_distribution_cluster: '连续派发退出',
  zz500_top_watch_exit: '顶部观察期退出', zz500_distribution_cluster: '派发累计退出',
  zz1000_watch_break_low: '观察期跌破前低', zz1000_watch_position_exit: '观察期价格位置退出',
  zz1000_watch_trailing_exit: '观察期回撤退出', zz1000_accelerating_top: '加速顶部退出',
  dividend_distribution_cluster: '红利派发累计退出',
}

const applicableRules: Record<string, string[]> = {
  '159780.SZ': ['sc50_trailing_exit'],
  '510050.SH': ['sh50_trailing_exit', 'sh50_large_redemption'],
  '588000.SH': ['kc50_trailing_exit'],
  '589000.SH': ['kc_distribution_cluster'],
  '510500.SH': ['zz500_top_watch_exit', 'zz500_distribution_cluster'],
  '512100.SH': ['zz1000_watch_break_low', 'zz1000_watch_position_exit', 'zz1000_watch_trailing_exit', 'zz1000_accelerating_top'],
  '515080.SH': ['dividend_distribution_cluster'],
}

export function StrategyPositionState({ report, version, unavailable }: {
  report: StrategyWorkbenchDetail['strategy_state']; version: string; unavailable: boolean
}) {
  const state = report?.checkpoint
  return <section className="strategy-queue-detail" aria-label="真实持仓与止损判断">
    <header><strong>真实持仓与止损判断</strong><span>判断时的账本事实 · 实际成交后更新</span></header>
    {state && report ? <>
      {report?.status === 'recovering' ? <p role="status">当前评估待恢复：{report.reasons.join('；')}。下表保留最近成功判断。</p> : null}
      <p>评估于 {absoluteChinaTime(state.evaluated_at)} · 行情截止 {state.source_trade_date} · 前复权基准 {report.analysis_basis_date} · 因子采集于 {absoluteChinaTime(report.analysis_known_at)}</p>
      <p>首笔真实建仓日计为第 0 天。未卖完、加仓、部分卖出和纯拆分保持原持仓周期；模型信号独立演化。</p>
      <div className="table-scroll"><table><thead><tr><th>证券</th><th>实际数量</th><th>连续建仓时间</th><th>已持有交易日</th><th>同口径参考高点</th><th>距高点回撤</th><th>判断与目标</th></tr></thead>
        <tbody>{Object.entries(state.position_cycles).map(([symbol, cycle]) => {
          const peak = state.reference_prices[symbol]
          const close = report.analysis_close_prices[symbol]
          const drawdown = peak && close ? (close / peak - 1) * 100 : null
          const path = state.exit_paths[symbol]
          return <tr key={symbol}><td>{symbol}</td><td>{cycle.quantity.toLocaleString('zh-CN')}</td>
            <td>{cycle.status === 'held' ? absoluteChinaTime(cycle.opened_at) : cycle.status === 'flat' ? '账本确认空仓' : '起点待核实'}</td>
            <td>{state.holding_days[symbol] ?? '—'}</td><td>{peak?.toFixed(4) ?? '—'}</td><td>{drawdown === null ? '—' : `${drawdown.toFixed(2)}%`}</td>
            <td>模型：{signals[state.model_signals[symbol]] ?? '待评估'}
              {path ? <p>退出判断：{exits[path] ?? '策略退出条件已满足'}</p> : null}
              {path && report.exit_decision_dates?.[symbol] ? <p>退出决定形成于 {report.exit_decision_dates[symbol]}。{cycle.status === 'flat' ? '实际已清仓；等待更新日线的新买入信号。' : ''}</p> : null}
              {!path && version === '1.1.2' && applicableRules[symbol] ? <p>本次未产生退出判断。适用规则：{applicableRules[symbol].map(rule => exits[rule]).join('；')}。</p> : null}<br />目标 {((state.target_weights[symbol] ?? 0) * 100).toFixed(2)}%{cycle.quantity > 0 && state.target_weights[symbol] === 0 ? ' · 减仓待完成' : ''}</td></tr>
        })}</tbody></table></div>
    </> : <p>{unavailable ? '持仓周期与分析口径来源不可用，等待来源恢复后核对。' : report?.reasons.join('；') || (version === '1.1.2' ? '等待合格账本与前复权行情完成状态恢复。' : '该规则版本使用历史模型状态；真实持仓周期与统一前复权口径需受控启用 1.1.2。')}</p>}
  </section>
}
