import type { StrategyWorkbenchDetail } from '../types'
import { absoluteChinaTime } from './RelativeTime'

export function StrategyTargetReplacements({ history, unavailable }: {
  history: StrategyWorkbenchDetail['target_replacements']; unavailable: boolean
}) {
  return <section className="strategy-queue-detail" aria-label="目标接替记录">
    <header><strong>目标接替记录</strong><span>策略评估、原执行任务与实际成交分别留存</span></header>
    {history ? <>
      {history.items.length ? history.items.map((item) => <article key={item.event_id}>
        <p><strong>{item.symbol}</strong> · {absoluteChinaTime(item.replaced_at)} 接替原{item.side === 'sell' ? '卖出' : '买入'}任务</p>
        <p>新评估规则 {item.successor_rule_version} · {item.config_version} · 计算于 {absoluteChinaTime(item.evaluated_at)} · 来源交易日 {item.source_trade_date} · 新目标 {(item.target_weight * 100).toFixed(2)}%</p>
        <p>接替依据：当前生效策略完成新评估，并按已核实持仓 {item.observed_position_quantity.toLocaleString('zh-CN')} 份协调原任务。</p>
        <p>原任务阻断：{item.prior_state_available ? item.prior_blocking_reason_labels.map((label) => label.startsWith('等待条件核验：') ? '条件待核对' : label).join('；') || '当时未记录阻断原因' : '原状态记录不可用'}</p>
        <details className="technical-details"><summary>评估与原任务引用</summary>
          <p>原规则 {item.previous_strategy_version} · 原目标 {item.previous_target_revision} · 任务 {item.episode_id} / 修订 {item.previous_revision}</p>
          <p>后继评估 {item.successor_target_id}</p><p>{item.decision_input_refs.join('；')}</p>
        </details>
      </article>) : <p>已核对当前配置，尚无目标接替记录。</p>}
      {history.truncated ? <p>显示最近 20 条接替记录，较早记录保留在执行历史中。</p> : null}
    </> : <p>{unavailable ? '目标接替记录不可用，请查看系统状态。' : '当前目标尚未形成，接替记录待核对。'}</p>}
  </section>
}
