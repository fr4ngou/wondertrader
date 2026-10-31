import { useId, useState, useSyncExternalStore } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { QueryClient } from '@tanstack/react-query'
import {
  cloneConfiguration, ConfigurationWriteError, fetchConfigurationWorkspace, lookupConfigurationRequest,
  saveStrategyConfiguration, validateStrategyConfiguration,
} from './strategyConfigurationApi'
import type { ConfigurationReceipt, ConfigurationValidation, SaveConfigurationIntent, StrategyConfiguration } from './strategyConfigurationApi'
import './strategy-configuration.css'

const queryKey = ['strategy-configuration-workspace'] as const
const roleLabels: Record<string, string> = { csi300: '沪深300', dividend: '红利', kc50: '科创50', kc_composite: '科创综指', sc50: '双创50', sh50: '上证50', zz1000: '中证1000', zz500: '中证500' }
type SaveState = { busy: boolean; pending: SaveConfigurationIntent | null; phase: 'idle' | 'saved' | 'verified' | 'unknown' | 'absent' | 'conflict' | 'rejected'; receipt: ConfigurationReceipt | null }

/** 一个QueryClient保留一个未确认保存；切换tab只取消视图订阅，原请求继续归此owner。 */
class ConfigurationUiOwner {
  private value: SaveState = { busy: false, pending: null, phase: 'idle', receipt: null }
  private readonly listeners = new Set<() => void>()
  constructor(private readonly client: QueryClient) {}
  snapshot = () => this.value
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener) } }
  private publish(value: Partial<SaveState>) { this.value = { ...this.value, ...value }; this.listeners.forEach(listener => listener()) }
  refreshed() { if (!this.value.pending && !this.value.busy) this.publish({ phase: 'idle' }) }
  async save(intent: SaveConfigurationIntent) {
    if (this.value.busy || this.value.pending) return
    this.publish({ busy: true, pending: intent })
    try {
      const receipt = await saveStrategyConfiguration(intent)
      this.publish({ busy: false, pending: null, phase: 'saved', receipt })
      await this.client.invalidateQueries({ queryKey })
    } catch (error) {
      const phase = error instanceof ConfigurationWriteError ? error.state : 'unknown'
      this.publish({ busy: false, phase, pending: phase === 'unknown' ? intent : null })
    }
  }
  async check() {
    const pending = this.value.pending
    if (!pending || this.value.busy) return
    this.publish({ busy: true })
    try {
      const receipt = await lookupConfigurationRequest(pending)
      this.publish(receipt ? { busy: false, pending: null, phase: 'verified', receipt } : { busy: false, phase: 'absent' })
      await this.client.invalidateQueries({ queryKey })
    } catch { this.publish({ busy: false, phase: 'unknown' }) }
  }
}
const owners = new WeakMap<QueryClient, ConfigurationUiOwner>()
function uiOwner(client: QueryClient) { let owner = owners.get(client); if (!owner) { owner = new ConfigurationUiOwner(client); owners.set(client, owner) }; return owner }

const numberFields = [
  ['minimum_history_days', '预热完整交易日数'], ['regime_ma_period', '行情状态均线窗口'],
  ['position_window', '价格位置窗口'], ['volume_window', '成交量窗口'],
] as const
const weightFields = [
  ['budget_weight', '策略预算权重'], ['symbol_cap_weight', '单证券权重上限'], ['max_weight_change', '单次权重变化上限'],
] as const
const validityLabels = { not_yet_valid: '尚未进入有效期', within_window: '当前时间位于配置有效期内', expired: '配置有效期已结束' }
const phaseLabels: Record<SaveState['phase'], string> = {
  idle: '', saved: 'App配置版本已保存；实际运行生效尚待宿主确认。', verified: '已按原请求编号核实保存成功；实际运行生效尚待宿主确认。',
  unknown: '保存结果尚未确认，请沿原请求编号核查；请勿重复保存。', absent: '本次读取尚未见到原请求的持久回执，原请求继续保留，请在服务恢复后继续核查。',
  conflict: '配置版本已在其他页面变化，请重新读取当前版本后确认。', rejected: '保存请求未通过业务校验，请重新读取并检查参数。',
}

export default function StrategyConfigurationWorkspace() {
  const nameHelpId = useId()
  const client = useQueryClient()
  const owner = uiOwner(client)
  const saving = useSyncExternalStore(owner.subscribe, owner.snapshot, owner.snapshot)
  const [selectedVersion, setSelectedVersion] = useState('')
  const [draft, setDraft] = useState<StrategyConfiguration | null>(null)
  const [origin, setOrigin] = useState('')
  const [validated, setValidated] = useState<ConfigurationValidation | null>(null)
  const query = useQuery({ queryKey, queryFn: ({ signal }) => fetchConfigurationWorkspace(signal), retry: false,
    refetchOnWindowFocus: false, refetchOnReconnect: false, refetchOnMount: 'always' })
  const check = useMutation({ mutationFn: validateStrategyConfiguration, retry: false, onSuccess: value => {
    setDraft(cloneConfiguration(value.configuration)); setValidated(value)
  } })
  const data = !query.isError && !query.isFetching ? query.data : undefined
  const store = data?.store
  const locked = saving.busy || saving.pending !== null || check.isPending
  const canSave = Boolean(data?.editable && store && draft && validated && !locked && saving.phase !== 'conflict' && saving.phase !== 'rejected')

  function load(value: StrategyConfiguration, description: string) {
    if (locked) return
    setDraft(cloneConfiguration(value)); setValidated(null); setOrigin(description); check.reset()
    setSelectedVersion(`${value.strategy_id}@${value.strategy_version}`)
  }
  function update<K extends keyof StrategyConfiguration>(key: K, value: StrategyConfiguration[K]) {
    if (!draft || locked) return
    setDraft({ ...draft, [key]: value }); setValidated(null); check.reset()
  }
  async function refresh() { setValidated(null); const result = await query.refetch(); if (result.isSuccess) owner.refreshed() }
  const selected = data?.catalog.find(item => `${item.strategy_id}@${item.strategy_version}` === selectedVersion)
  return <section className="workspace-page configuration-workspace">
    <header className="page-heading"><div><h1>策略配置版本</h1><p>选择真实保留策略版本，查看参数、预算和证券映射，校验后保存App配置。</p></div><span className="read-only-stamp">配置管理 · 交易关闭</span></header>
    <p>保存登记App配置版本。实际生效配置、数据预热与策略运行由运行宿主另行确认。</p>
    <p>原生回测当前使用部署冻结输入；本页保存完成后，可切换“原生回测与报告”查看该入口，保存不会自动替换回测输入。</p>
    <div className="account-actions"><button onClick={() => void refresh()} disabled={query.isFetching || locked}>重新读取配置版本</button></div>
    {query.isPending ? <p role="status">正在读取配置版本…</p> : null}
    {query.isError ? <p role="alert">{query.error.message}。请恢复服务后重新读取，当前暂停保存。</p> : null}
    {data?.reason ? <p role="status">{data.reason}</p> : null}
    {saving.phase !== 'idle' ? <p role={['unknown', 'absent', 'conflict', 'rejected'].includes(saving.phase) ? 'alert' : 'status'}>{phaseLabels[saving.phase]}</p> : null}
    {saving.pending ? <article className="surface-card"><h2>原保存请求待核查</h2><p>请求编号：<code>{saving.pending.request_id}</code></p>
      <button disabled={saving.busy} onClick={() => void owner.check()}>{saving.busy ? '正在核查…' : '按原请求编号核查保存结果'}</button></article> : null}
    {data ? <article className="surface-card"><h2>选择策略与版本</h2><label className="configuration-field">策略版本<select value={selectedVersion} disabled={locked} onChange={event => { setSelectedVersion(event.target.value); setDraft(null); setValidated(null) }}>
      <option value="">请选择策略版本</option>{data.catalog.map(item => <option key={`${item.strategy_id}@${item.strategy_version}`} value={`${item.strategy_id}@${item.strategy_version}`}>{item.label}</option>)}</select></label>
      {selected ? <><p>此版本为已迁入的真实业务算法。下面的示例参数用于隔离验证，属于合成配置。</p>
        <button onClick={() => load(selected.example, '当前草稿来自合成示例：2024年有效期、2日预热；请按实际用途逐项设置。')} disabled={locked}>加载明确标注的合成示例</button></> : null}
      <p>V1其他历史版本、V2、V3、迟滞、AI及ETF/补单规则继续逐项接入。</p></article> : null}
    {draft ? <article className="surface-card"><h2>业务参数与预算</h2><p>{origin}</p><p>算法：{draft.strategy_id}@{draft.strategy_version} · 观察版本：{draft.observation_version}</p>
      <fieldset disabled={locked} className="configuration-form"><legend>业务配置</legend>
        <div className="configuration-field"><label>业务修订名称<input aria-describedby={nameHelpId} value={draft.config_revision} onChange={event => update('config_revision', Array.from(event.target.value).slice(0, 128).join(''))} /></label><small id={nameHelpId}>最多128个Unicode码点</small></div>
        <label className="configuration-field">有效期起点（带时区ISO）<input value={draft.valid_from} onChange={event => update('valid_from', event.target.value)} /></label>
        <label className="configuration-field">有效期终点（带时区ISO）<input value={draft.valid_until} onChange={event => update('valid_until', event.target.value)} /></label>
        {numberFields.map(([key, label]) => <label className="configuration-field" key={key}>{label}<input type="number" step="1" value={Number.isFinite(draft[key]) ? draft[key] : ''} onChange={event => update(key, event.target.valueAsNumber)} /></label>)}
        {weightFields.map(([key, label]) => <label className="configuration-field" key={key}>{label}<input aria-label={label} type="number" step="0.01" value={Number.isFinite(draft[key]) ? draft[key] : ''} onChange={event => update(key, event.target.valueAsNumber)} /><span>{Number.isFinite(draft[key]) ? (draft[key] * 100).toFixed(2) + '%' : '待输入'}；权重以1表示100%</span></label>)}
        <label className="configuration-field">基准角色<select value={draft.benchmark_role} onChange={event => update('benchmark_role', event.target.value)}>{draft.symbol_roles.map(([role]) => <option key={role} value={role}>{roleLabels[role] ?? role}</option>)}</select></label>
      </fieldset>
      <p>预算为策略权重，账户现金和资金可用性另取券商事实。预热日数表示当前收盘之前的完整交易日数，并须覆盖全部特征窗口；实际历史覆盖尚待数据来源确认。</p>
      <h3>信号证券 → 执行证券</h3><p>信号只用于计算；完整目标使用执行证券。两者替换映射须保持角色一致。</p>
      <div className="configuration-mappings">{draft.symbol_roles.map(([role, security], index) => <div className="configuration-mapping" key={role}>
        <strong>{roleLabels[role] ?? role}（{role}）</strong><label>信号证券<input aria-label={`${role} 信号证券`} value={security} disabled={locked} onChange={event => update('symbol_roles', draft.symbol_roles.map((row, rowIndex) => rowIndex === index ? [role, event.target.value] : row))} /></label>
        <span aria-hidden="true">→</span><label>执行证券<input aria-label={`${role} 执行证券`} value={draft.execution_symbols.find(row => row[0] === role)?.[1] ?? ''} disabled={locked} onChange={event => update('execution_symbols', draft.execution_symbols.map(row => row[0] === role ? [role, event.target.value] : row))} /></label>
      </div>)}</div>
      <div className="account-actions"><button disabled={locked} onClick={() => { setValidated(null); check.mutate(cloneConfiguration(draft)) }}>{check.isPending ? '正在校验…' : '调用唯一业务核校验'}</button>
        <button disabled={!canSave} onClick={() => { if (store && draft && validated) void owner.save({ store_id: store.store_id, expected_revision: store.revision,
          request_id: crypto.randomUUID().replaceAll('-', ''), configuration: cloneConfiguration(validated.configuration), configuration_sha256: validated.configuration_sha256 }) }}>{saving.busy && !saving.pending ? '正在保存…' : '保存为App配置新版本'}</button></div>
      {check.isError ? <p role="alert">{check.error instanceof ConfigurationWriteError && check.error.state === 'rejected' ? check.error.message : '配置校验暂不可用，请恢复服务后重试。'}</p> : null}
      {validated ? <div role="status"><p>配置内部规则校验通过。{validityLabels[validated.validity]}。</p><p>校验时间：{validated.validation_time}；有效期说明依据该次时间。当前计算仍按原核实际知晓截止准入。</p><p>配置摘要：<code>{validated.configuration_sha256}</code></p><p>数据来源、实际预热与运行资格继续待确认。</p></div> : null}
    </article> : null}
    {store ? <article className="surface-card"><h2>已保存App配置版本</h2><p>当前修订 {store.revision} / 32。每次保存保留完整配置及原请求回执。</p>
      {store.versions.length === 0 ? <p role="status">尚未保存配置版本。空目录保持空状态，可主动加载合成示例。</p>
        : <ol className="configuration-versions">{[...store.versions].reverse().map(item => <li key={item.revision}><strong>版本 {item.revision} · {item.configuration.config_revision}</strong><p>保存时间：{item.saved_at}</p>
          <p>摘要：<code>{item.configuration_sha256}</code></p><button disabled={locked} onClick={() => load(item.configuration, `当前草稿来自已保存App配置版本 ${item.revision}；运行生效状态另行确认。`)}>查看并编辑版本 {item.revision}</button></li>)}</ol>}
    </article> : null}
  </section>
}
