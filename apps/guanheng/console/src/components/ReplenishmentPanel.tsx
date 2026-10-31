import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchReplenishment } from '../api'
import { replenishmentTime as time, replenishmentValue as value, replenishmentDisplayScope, hasReplenishmentDisplayScope, knownIdentity } from '../replenishment'
import type { ReplenishmentItem } from '../replenishment'
import { EmptyState } from './EmptyState'
import { InfoTip } from './InfoTip'
import { StatusPill } from './StatusPill'

function waitLabel(wait?: ReplenishmentItem['wait']) {
  return wait ? `${wait.amount} ${wait.unit === 'trading_days' ? '个交易日' : '个交易秒'}` : '暂无'
}

function identityText(identity: unknown) {
  return knownIdentity(identity) ? identity : '待核对'
}

const FIELD_HELP: Record<string, string> = {
  '策略版本': '该机会保存的策略版本，用于区分当前配置与历史记录。',
  '配置归属': '该机会保存的配置身份。归属缺失时保持待核对。',
  '机会原目标': '创建或承接该机会时保存的目标引用。原目标与最新目标不同仍可属于同一持续机会，执行承接由 Portfolio 核验。',
  '原始目标量': '策略在本次调整开始时给出的目标数量。来源：已保存的策略意图。不可用表示历史记录缺少该事实。',
  '保留份额': '已经保留、不再继续补单的数量。来源：Portfolio 补单记录。',
  '补单政策': '决定分档、等待和价格边界的政策版本。“待核对”表示当前记录未提供可验证值。',
  '运行方式': '表示该记录获得真实执行授权、仅影子观察，或尚待核对。来源：记录中的授权模式。',
  '本档等待': '当前档位在下次检查前要等待的交易日或交易秒。来源：补单策略。',
  '已续期次数': '当前补单阶段已延长的次数。来源：补单生命周期记录。',
  '当前累计偏离': '当前参考价相对原始参考价的累计变化。数值缺失时显示待核对。',
  '偏离公式': '用于计算累计偏离的公式或规则标识。来源：补单政策事实。',
  '最大允许偏离': '本次补单允许的价格偏离上限；“范围不设上限”是明确的政策设置。',
  '原始参考价': '补单周期开始时保存的参考价。来源：初始价格证据。',
  '当前参考价': '最近一次权威价格证据中用于检查边界的价格。',
  '本档价格边界': '当前分档根据策略计算的价格阈值。它是业务条件，未单独授权委托。',
  '实际可执行边界': '合并当前档位、风控和授权后的最终价格边界。不可用表示条件尚未齐备。',
  '价格证据时间': '当前参考价与边界所依据行情的采集时间。精确时间按中国标准时间显示。',
  '首次开始等待': '该补单首次进入可等待状态的时间。来源：Portfolio 生命周期事实。',
  '下一次业务检查': '策略和业务条件预计重新评估的时间。“暂无”表示未安排。',
  '下一次执行重试': '执行层预计重试的时间。它只有在授权和所有安全条件齐备时才会生效。',
  '旧挂单到期': '与该补单关联的旧委托有效期截止时间。“暂无”表示没有可用到期事实。',
  '记录更新时间': '该补单事实最后一次写入 Portfolio 的时间，用于判断记录新鲜度。',
}

function RecordDetails({ item }: { item: ReplenishmentItem }) {
  const riskNames: Record<string, string> = { account_daily_loss: '账户当日亏损', strategy_drawdown: '策略回撤', position_loss: '持仓亏损', position_weight: '持仓占比' }
  const fields = [
    ['策略版本', identityText(item.strategy_version)],
    ['配置归属', knownIdentity(item.config_id) ? `${identityText(item.config_version)} · ${item.config_id}` : '待核对'],
    ['机会原目标', identityText(item.target_revision)],
    ['原始目标量', value(item.original_intended_quantity)], ['保留份额', value(item.retained_quantity)],
    ['补单政策', item.policy ?? '待核对'], ['运行方式', item.authorization_mode === 'execute' ? '已获执行授权' : item.authorization_mode === 'shadow' ? '影子观察' : '待核对'],
    ['本档等待', waitLabel(item.wait)], ['已续期次数', value(item.renewals_used)],
    ['当前累计偏离', item.cumulative_deviation == null ? '待核对' : `${(item.cumulative_deviation * 100).toLocaleString('zh-CN', { maximumFractionDigits: 4 })}%`],
    ['偏离公式', item.deviation_formula ?? '暂无'],
    ['最大允许偏离', item.deviation_mode === 'uncapped' ? '范围不设上限' : item.maximum_deviation == null ? '待核对' : `${item.maximum_deviation * 100}%`],
    ['原始参考价', value(item.original_reference_price)], ['当前参考价', value(item.reference_price)],
    ['本档价格边界', value(item.business_boundary)], ['实际可执行边界', value(item.effective_boundary)],
    ['价格证据时间', time(item.boundary_evidence_at)],
    ['首次开始等待', time(item.first_eligible_at)], ['下一次业务检查', time(item.next_review_at)],
    ['下一次执行重试', time(item.next_retry_at)], ['旧挂单到期', time(item.order_live_deadline)],
    ['记录更新时间', time(item.updated_at)],
  ]
  const risk = item.risk_target
  return <details className="replenishment-details">
    <summary>查看等待与价格详情</summary>
    <dl className="replenishment-facts">{fields.map(([label, text]) => <div key={label}><dt>{label}<InfoTip label={label}>{FIELD_HELP[label]}</InfoTip></dt><dd>{text}</dd></div>)}</dl>
    {!!item.stages?.length && <div className="replenishment-stages">{item.stages.map((stage) => <p key={stage.index}>第 {stage.index + 1} 档 · {stage.status} · {stage.authorized ? '已授权档位' : '尚未授权'} · 价格边界 {value(stage.boundary)} · 等待 {waitLabel(stage.wait)}</p>)}</div>}
    {risk && <div className="replenishment-risk"><strong>独立风险退出</strong><p>指标 {riskNames[risk.metric] ?? risk.metric} · 当前 {value(risk.metric_value)} · 触发值 {value(risk.trigger_ratio)} · 保留量 {value(risk.retained_quantity)}</p><p>触发于 {time(risk.triggered_at)} · 目标有效至 {time(risk.valid_until)} · 风险政策有效至 {time(risk.policy_valid_until)}</p></div>}
  </details>
}

function Records({ items }: { items: ReplenishmentItem[] }) {
  return <div className="replenishment-list">{items.map((item) => <section key={item.episode_id} className="replenishment-record">
      <div className="replenishment-record-heading"><div><strong>{item.symbol ?? '证券待核对'} · {item.side === 'buy' ? '买入' : item.side === 'sell' ? '卖出' : '方向待核对'}</strong><small>{identityText(item.strategy_id)}</small></div><StatusPill tone={item.terminal ? 'ok' : 'info'}>{item.state_label}</StatusPill></div>
      <p className="replenishment-quantities">剩余 <strong>{value(item.remaining_quantity)}</strong> 份 · 实际成交 <strong>{value(item.filled_quantity)}</strong> 份{item.stage_index != null && <> · 第 {item.stage_index + 1} 档</>}</p>
      {item.legacy_read_only ? <p>历史记录仅供查看，等待核对后才能解释其执行状态。</p> : <>
        {!!item.blocking_reason_labels?.length && <p>{item.blocking_reason_labels.join('；')}</p>}
        {!!item.blocking_reasons?.length && item.blocking_reason_labels?.includes('条件待核对，请查看系统状态')
          ? <details className="technical-details"><summary>技术详情</summary><code>{item.blocking_reasons.join('、')}</code></details> : null}
        <p><strong>下一步：</strong>{item.next_action ?? '等待核对'} <span>（{item.next_action_owner ?? '负责人待核对'}）</span></p>
        <p className="replenishment-next">下一次业务复核：{time(item.next_review_at)} · 执行层重试：{time(item.next_retry_at)}</p>
        <RecordDetails item={item} />
      </>}
    </section>)}</div>
}

export function ReplenishmentPanel({ strategyId, strategyVersion, activeConfigId }: {
  strategyId?: string; strategyVersion?: string; activeConfigId?: string | null
} = {}) {
  const [showFinished, setShowFinished] = useState(false)
  const query = useQuery({
    queryKey: ['portfolio-replenishment'], queryFn: ({ signal }) => fetchReplenishment(signal),
    staleTime: 5_000, refetchInterval: 15_000, retry: 1,
  })
  const data = query.isError ? undefined : query.data
  const scanComplete = data != null && Object.prototype.hasOwnProperty.call(data, 'scan_error') && data.scan_error == null
  const scope = { strategyId: strategyId ?? '', strategyVersion, configId: activeConfigId }
  const scopeComplete = hasReplenishmentDisplayScope(scope)
  const groups: Record<'current' | 'historical' | 'unknown', ReplenishmentItem[]> = { current: [], historical: [], unknown: [] }
  for (const item of data?.items ?? []) {
    const group = strategyId ? replenishmentDisplayScope(item, scope) : 'current'
    if (group !== 'other_strategy') groups[group].push(item)
  }
  const current = groups.current.filter(item => showFinished || !strategyId || !item.terminal)
  const currentOpenCount = groups.current.filter(item => !item.terminal).length
  return <article className="surface-card replenishment-panel" aria-labelledby="replenishment-heading">
    <div className="card-heading"><div><h2 id="replenishment-heading">补单进度 <InfoTip label="补单进度">展示 Portfolio 保存的分档等待、价格边界和下一步。本区域只读；归属或来源待核对时，数量保持未知。</InfoTip></h2><span>剩余份额、等待原因与下一步 · 只读</span></div><button type="button" disabled={query.isFetching} onClick={() => void query.refetch()}>{query.isFetching ? '正在读取补单' : '刷新补单进度'}</button></div>
    {strategyId ? <label className="reader-meta"><input type="checkbox" checked={showFinished} onChange={event => setShowFinished(event.target.checked)} /> 包含当前配置已结束补单</label> : null}
    {query.isError && <p role="alert" className="replenishment-error">{query.error.message}。请稍后刷新；读取失败不代表没有补单。</p>}
    {query.isPending && <EmptyState title="正在读取补单进度" detail="读取已保存的补单记录。" />}
    {data && !scanComplete ? <p role="alert">补单扫描状态不可用或不完整，当前等待数量尚不能完整确认。</p> : null}
    {strategyId && data ? <section aria-label="当前配置补单">
      <h3>当前配置补单</h3>
      <p>{scanComplete && scopeComplete && !groups.unknown.length ? `已核对当前配置未结束补单 ${currentOpenCount} 项。` : '当前配置归属或来源覆盖尚待核对。'}补单按保存的价格与安全条件推进；账户循环状态见上方，每项的具体等待原因和处理负责人见下方。</p>
      <Records items={current} />
      {scanComplete && scopeComplete && !groups.unknown.length && !current.length ? <p>当前筛选下暂无补单记录；历史记录保留在下方。</p> : null}
    </section> : <Records items={current} />}
    {!strategyId && scanComplete && !current.length ? <EmptyState title="暂无补单记录" detail="新补单产生后会显示在这里；旧调仓计划不会自动导入。" /> : null}
    {!!groups.unknown.length && <section aria-label="归属待核对补单"><h3>归属待核对（{groups.unknown.length} 项）</h3><p>记录缺少可验证的配置或策略版本，当前执行归属保持未知。</p><Records items={groups.unknown} /></section>}
    {!!groups.historical.length && <details><summary>历史配置与版本补单（{groups.historical.length} 项）</summary><p>保留原等待、处理和成交状态；历史状态不会计入当前配置的等待说明。</p><Records items={groups.historical} /></details>}
  </article>
}
