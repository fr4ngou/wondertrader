import type { V2Summary } from './backtestV2'

const percentage = (value: number) => new Intl.NumberFormat('zh-CN', { style: 'percent', maximumFractionDigits: 4 }).format(value)

/** 独立展示signal原始事实；WT执行证券在原生观察中展示，不按数组位置配对。 */
export default function V2EvaluationSummary({ value }: { value: V2Summary }) {
  const { pipeline, producer_readiness: ready, target_admission: admission } = value
  const signal = pipeline.signal
  const allocation = pipeline.allocation
  return <section aria-label="V2策略摘要">
    <h3>策略：{signal.strategy_id} · {signal.strategy_version}</h3>
    <p>本次使用评估区间信号起点，实际成交周期未注入。完整信号历史保存在原实验输出中。</p>
    <h3>目标准入：{admission.accepted ? '已通过现金模型权重准入' : '原始权重超额，本日停止新增提交'}</h3>
    <p>原始总权重：<strong>{percentage(allocation.raw_diagnostic.total_weight)}</strong>（报告精确值 {admission.raw_total_fraction}）。</p>
    <p>准入政策：超过总权重上限时拒绝新增目标；原始权重保持原值。分配容量参数：{percentage(allocation.raw_diagnostic.pre_risk_capacity)}。</p>
    {!admission.accepted ? <p role="status">本日没有新增目标提交。此前的实际持仓及未决目标继续以 WT 原生观察为准；本轮已完成表示回放与结果收口完成。</p> : null}
    <h3>信号证券原始权重</h3>
    <p>此表是信号侧原始权重；执行侧的实际持仓和本次目标提交见下方 WT 观察，两组证券分别保留来源角色。</p>
    {allocation.latest_raw_weights ? <><p>最后真实分配事件：{allocation.latest_event_date}</p>
      <div className="account-table-scroll"><table style={{ minWidth: 'auto', width: '100%' }}><thead><tr><th>信号证券</th><th>原始权重</th></tr></thead>
        <tbody>{allocation.latest_raw_weights.map(([symbol, weight]) => <tr key={symbol}><td>{symbol}</td><td>{percentage(weight)}</td></tr>)}</tbody></table></div></>
      : <p>尚无分配事件，初始化目标未发出。</p>}
    <h3>输入与来源资格</h3>
    <ul><li>本次原生输入：已通过本域准入</li><li>旧离线数据范围门槛：{ready.legacy_offline_ready ? '已满足报告列明条件' : '尚未满足'}</li>
      <li>真实数据来源：尚未取得资格</li><li>历史真实生产：尚未取得资格</li><li>实时与实盘：尚未取得资格</li></ul>
    <details><summary>查看策略计算身份</summary><p className="backtest-hash">{signal.algorithm_id}</p><p className="backtest-hash">信号起点：{signal.signal_profile}</p>
      <p className="backtest-hash">固定配置 SHA256：{value.stable_spec_sha256}</p>
      <p className="backtest-hash">当日输入 SHA256：{value.daily_input_sha256}</p></details>
  </section>
}
