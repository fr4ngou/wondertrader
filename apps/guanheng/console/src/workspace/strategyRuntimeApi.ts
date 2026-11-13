import { fetchReadJson } from '../api'
import { validateCapitalFields, type CapitalFields } from './strategyCapital'
import { diagnosticWire } from './strategyDiagnosticWire.generated'
import { projectCurrentAuxiliary, type CurrentAuxiliaryFields } from './currentAuxiliary'

export const runtimeLabels = {
  waiting_allocation: '等待确认策略归属',
  initialized: '策略已初始化', waiting: '等待策略所需事实', holding: '保持当前目标', targets_ready: '目标已准备',
  initializing: '正在准备目标', selling: '正在调整卖出目标', buying: '正在调整买入目标',
  converged: '理论持仓已达到本阶段目标', waiting_basis: '等待完整资金与价格',
  waiting_sellable: '等待持仓可卖', waiting_pending: '等待原生未决目标处理',
  waiting_cash: '等待可用资金', waiting_fee: '等待费用信息',
  supersession_required: '等待原目标处理完成', blocked: '本轮目标暂未执行',
  waiting_broker_position: '等待更新券商持仓', waiting_actual_cycle: '等待确认实际开仓信息',
  waiting_market_input: '等待策略所需行情',
  observing: '分析运行中', // WT只读模式持续计算，不调用目标提交；与后端公开状态同步。
} as const
export type DiagnosticRange = {
  /** 原输入/实际评估范围首日，YYYY-MM-DD；空范围为null。 */ first_date: string | null
  /** 原输入/实际评估范围尾日，YYYY-MM-DD；空范围为null。 */ last_date: string | null
  /** 此范围应有市场日数，计数单位为日。 */ expected_dates: number
}
export type DiagnosticCoverage = {
  /** 同范围应有字段值数，显式零值也属于已有值。 */ expected_count: number
  /** 原输入中非null值数，不由页面重算指标。 */ non_null_count: number
  /** 首个有值的市场日，YYYY-MM-DD；没有值为null。 */ first_non_null_date: string | null
  /** 最后有值的市场日，YYYY-MM-DD；没有值为null。 */ last_non_null_date: string | null
  /** 缺整行/缺字段的原计数；未披露原因不在页面补造。 */ missing_reasons: Partial<Record<'observation_missing' | 'not_supplied_in_observation', number>>
}
export type DiagnosticRole = {
  /** 原纯核业务角色；物理证券由本轮roles的键拥有。 */ role: string
  /** 各依赖字段的完整输入及实际评估覆盖，不表示来源取得时间。 */ field_coverage: Record<string, {
    /** 完整输入范围的字段覆盖。 */ input: DiagnosticCoverage
    /** 实际评估范围的字段覆盖。 */ evaluation: DiagnosticCoverage
  }>
  /** 原角色实际依赖的辅助字段名，价格独立角色可为空。 */ auxiliary_fields: string[]
  /** 最近实际评估日缺字段，未评估时为空且阶段明确。 */ latest_missing_fields: string[]
  /** 各原分支的依赖/缺口及可计算状态，页面不重算分支条件。 */ branches: Record<string, {
    /** 此原分支实际依赖字段。 */ required_fields: string[]
    /** 本次原诊断已确认缺失的字段。 */ missing_fields: string[]
    /** 未评估、不可用、部分有值或输入齐全。 */ state: 'not_evaluated' | 'unavailable' | 'partially_observed' | 'inputs_present'
  }>
  /** 原输入阶段，缺字段与未评估分别表达。 */ input_state: 'not_evaluated' | 'input_missing' | 'ready'
  /** 原机器BUY/SELL次数；旧结果未记录时为null。 */ signal_counts: {
    /** 原评估范围内BUY次数。 */ BUY: number
    /** 原评估范围内SELL次数。 */ SELL: number
  } | null
  /** 最近评估日的原机器动作，未记录为null。 */ latest_action: 'BUY' | 'SELL' | 'HOLD' | null
  /** 原信号阶段；输入缺失和正常条件未触发分别表达。 */ signal_state: 'not_evaluated' | 'not_recorded' | 'input_missing' | 'signal_generated' | 'conditions_not_met'
  /** 原机器最近成功计算的市场日，YYYY-MM-DD；未计算为null。 */ last_successful_calculation_date: string | null
  /** 最近依赖同时有值的评估日，YYYY-MM-DD；未取得为null。 */ last_fully_informed_date: string | null
}
export type StrategyDiagnostics = {
  /** V1拥有的诊断协议；独立于策略数学及执行授权版本。 */ schema: 'guanheng.strategy-business-diagnostics.v1'
  /** 真实实收与历史研究知晓假设分别标识。 */ auxiliary_availability_model: 'actually-received' | 'research-next-common-session-0925-v1' | 'unavailable'
  /** 原纯核计算阶段，成功与等待/失败分别表达。 */ calculation_state: 'not_scheduled' | 'market_not_ready' | 'warming_up' | 'input_rejected' | 'calculation_failed' | 'completed'
  /** 原稳定错误码；成功为null，禁止供应商或异常原文。 */ error_code: string | null
  /** 完整输入市场日范围；失败且未知时为null。 */ input_range: DiagnosticRange | null
  /** 原机器实际评估范围；失败且未知时为null。 */ evaluation_range: DiagnosticRange | null
  /** 本轮物理证券到原角色诊断的映射；未知失败允许空对象。 */ roles: Record<string, DiagnosticRole>
  /** 原目标变化状态，不代表已发委托。 */ target_state: 'not_calculated' | 'produced' | 'unchanged'
  /** 同回测的原NSQ执行阶段，目标setter接收仍为pending。 */ execution_state: 'not_observed' | 'not_requested' | 'pending' | 'completed' | 'failed'
}
export type RuntimePosition = {
  /** 本轮策略证券代码，六位代码加SH/SZ市场。 */ symbol: string
  /** 原目标权重，比例0..1；无计算为null。 */ target_weight: number | null
  /** 原WT理论持仓份数；未取得为null。 */ theoretical_quantity: number | null
  /** 原WT理论可卖份数；未取得为null。 */ theoretical_sellable: number | null
  /** 原WT未决目标份数；无原观察为null。 */ pending_target: number | null
  /** 原NSQ阶段或ASA已提交目标份数；尚未提交为null。 */ stage_target: number | null
  /** ASA自有或旧券商查询的实际份数；口径由position_basis区分，未知为null。 */ broker_quantity: number | null
  /** 同次ASA自有或旧券商查询的可卖份数；未知为null。 */ broker_sellable: number | null
  /** 自有持仓按已核原价计算的市值，人民币元。 */ market_value_cny?: string
  /** 该标的原报价时间，带时区。 */ market_value_observed_at?: string
  /** 持仓表按 WT 最近一笔已验证报价计算的市值。 */ market_value_basis?: 'last-quote'
}
export type StrategyRuntime = {
  /** 原公开运行结果协议版本，新增诊断采用可选字段兼容旧响应。 */ schema_version: 'guanheng.strategy-runtime.v1'
  /** 此入口只读，不拥有策略运行或交易副作用。 */ read_only: true
  /** 本轮公开读取时刻，带时区ISO时间；不替代决策或券商时间。 */ observed_at: string
  /** WT原生命周期状态，旧响应可缺失。 */ runtime_state?: string
  /** 未配置执行组件时的原明确信息，旧响应可缺失。 */ execution_state?: 'not_started'
  /** 此次公开结果未配置、等待或已有策略投影。 */ state: 'unconfigured' | 'waiting' | 'available'
  /** 原WT策略投影；未配置或尚未发布时为null。 */ strategy: null | (CapitalFields & CurrentAuxiliaryFields & {
    /** WT发布的策略身份；旧App回包可缺失。 */ strategy_id?: string
    /** 原目录中文名称。 */ display_name: string
    /** WT实际版本；null表示尚未发布。 */ strategy_version: string | null
    /** 原NSQ/分析等待阶段，不由页面推断执行状态。 */ status: keyof typeof runtimeLabels
    /** 与原阶段固定匹配的中文标签。 */ status_label: string
    /** 实际决策时刻，带时区ISO时间；尚未计算为null。 */ decision_at: string | null
    /** WT 自有估值的等待原因，早期响应可缺。 */
    valuation_reason?: string | null
    /** 自有账本尚未确认的成交手续费笔数。旧响应可缺，null表示未知，0表示无待确认项。 */
    owned_valuation?: { unknown_fee_count: number | null } | null
    /** 最近已核策略收益使用的估值时间。 */
    capital_return?: { valued_at: string }
    /** 已消费的闭合信号。日期为市场日，历史模型持有与实际归属分开。 */
    consumed_signal?: {
      decision_at: string
      decision_date: string
      eligible_date: string
      securities: { symbol: string, qualified: boolean, actions: ('BUY' | 'SELL')[], model_held: boolean | null, auxiliary_missing: string[] }[]
    }
    /** 券商持仓原接收时刻，带时区ISO时间；未知为null。 */ broker_observed_at: string | null
    /** 原兼容字段固定false，实际执行观察资格由下一字段表达。 */ broker_position_qualified: false
    /** 原执行观察是否通过准入，旧响应可缺失。 */ execution_position_qualified?: boolean
    /** ASA自有归属与旧账户范围分开，旧响应可缺。 */ position_basis?: 'strategy-allocated'
    /** 原策略证券的理论及券商事实，均保留各自缺失值。 */ positions: RuntimePosition[]
    /** V1统一诊断；未计算/旧生产者未记录为null，旧公开响应可缺失。 */ diagnostics?: StrategyDiagnostics | null
    /** 附加诊断自身的可用性，独立于已核资金、持仓及策略状态；旧响应可缺失。 */ diagnostics_state?: 'available' | 'absent' | 'unavailable'
    /** 稳定诊断缺失/错误原因；可用为null，旧响应可缺失，不携带原文。 */ diagnostics_reason?: 'not_calculated' | 'not_recorded' | 'invalid_diagnostics' | null
  })
}
const record = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === 'object' && !Array.isArray(v)
const time = (v: unknown) => typeof v === 'string' && v.length <= 64 && /(Z|[+-]\d{2}:\d{2})$/.test(v) && Number.isFinite(Date.parse(v))
const quantity = (v: unknown) => v === null || typeof v === 'number' && Number.isSafeInteger(v) && v >= 0

/** 只核公开诊断线协议；角色依赖、覆盖及信号数学继续由V1唯一实现拥有。 */
export function validateStrategyDiagnostics(value: unknown, symbols: ReadonlySet<string>): StrategyDiagnostics {
  const invalid = () => { throw new Error('策略业务诊断格式无效，请重新读取') }
  const need = (condition: boolean) => { if (!condition) invalid() }
  const keys = (v: unknown, names: string): Record<string, unknown> => {
    const expected = names.split(' ')
    if (!record(v) || Object.keys(v).length !== expected.length || expected.some(key => !Object.hasOwn(v, key))) return invalid()
    return v
  }
  const text = (v: unknown): v is string => typeof v === 'string' && v.length > 0 && v.length <= 64 && !/[\u0000-\u001f\u007f]/.test(v)
  const oneOf = (v: unknown, choices: readonly string[]) => typeof v === 'string' && choices.includes(v)
  const count = (v: unknown): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v >= 0 && v <= 32768
  const date = (v: unknown): v is string => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v)
    && Number.isFinite(Date.parse(v)) && new Date(v).toISOString().slice(0, 10) === v
  const optionalDate = (v: unknown) => v === null || date(v)
  const names = (v: unknown): v is string[] => Array.isArray(v) && v.length <= 64 && v.every(text) && new Set(v).size === v.length
  const sameNames = (actual: readonly string[], expected: readonly string[]) => actual.length === expected.length
    && actual.every((name, index) => name === expected[index])
  const sameKeys = (actual: Record<string, unknown>, expected: readonly string[]) => Object.keys(actual).length === expected.length
    && expected.every(name => Object.hasOwn(actual, name))
  const body = keys(value, 'schema auxiliary_availability_model calculation_state error_code input_range evaluation_range roles target_state execution_state')
  need(body.schema === diagnosticWire.schema
    && oneOf(body.auxiliary_availability_model, ['actually-received', 'research-next-common-session-0925-v1', 'unavailable'])
    && oneOf(body.calculation_state, ['not_scheduled', 'market_not_ready', 'warming_up', 'input_rejected', 'calculation_failed', 'completed'])
    && oneOf(body.target_state, ['not_calculated', 'produced', 'unchanged'])
    && oneOf(body.execution_state, ['not_observed', 'not_requested', 'pending', 'completed', 'failed'])
    && (body.error_code === null || text(body.error_code)))
  if (!record(body.roles)) return invalid()
  if (body.input_range === null && body.evaluation_range === null) {
    need(body.calculation_state !== 'completed' && body.target_state === 'not_calculated'
      && body.error_code !== null && Object.keys(body.roles).length === 0)
    return value as StrategyDiagnostics
  }
  const ranges: Record<string, Record<string, unknown>> = {}
  for (const scope of ['input', 'evaluation']) {
    const range = keys(body[scope + '_range'], 'first_date last_date expected_dates')
    need(count(range.expected_dates) && range.expected_dates <= 4096 && optionalDate(range.first_date) && optionalDate(range.last_date)
      && (range.first_date === null) === (range.expected_dates === 0) && (range.last_date === null) === (range.expected_dates === 0)
      && (range.expected_dates === 0 || String(range.first_date) <= String(range.last_date)))
    ranges[scope] = range
  }
  need(Number(ranges.evaluation.expected_dates) <= Number(ranges.input.expected_dates))
  if (ranges.evaluation.expected_dates) need(String(ranges.input.first_date) <= String(ranges.evaluation.first_date)
    && String(ranges.evaluation.last_date) <= String(ranges.input.last_date))
  need(Object.keys(body.roles).length === symbols.size && Object.keys(body.roles).every(symbol => symbols.has(symbol)))
  const commonRoles: Readonly<Record<string, string>> = diagnosticWire.common_roles
  const branchDeclarations: Readonly<Record<string, Readonly<Record<string, readonly string[]>>>> = diagnosticWire.branches
  need(symbols.size === Object.keys(commonRoles).length + 1 && Object.keys(commonRoles).every(symbol => symbols.has(symbol)))
  const within = (day: unknown, scope: string) => day === null || date(day)
    && ranges[scope].first_date !== null && String(ranges[scope].first_date) <= day && day <= String(ranges[scope].last_date)
  for (const [symbol, roleValue] of Object.entries(body.roles)) {
    const row = keys(roleValue, 'role field_coverage auxiliary_fields latest_missing_fields branches input_state signal_counts latest_action signal_state last_successful_calculation_date last_fully_informed_date')
    need(row.role === (commonRoles[symbol] ?? diagnosticWire.remaining_role))
    const declaredBranches = branchDeclarations[String(row.role)]
    const declaredAuxiliary = [...new Set(Object.values(declaredBranches).flat())]
    if (!names(row.auxiliary_fields) || !names(row.latest_missing_fields)) return invalid()
    const auxiliary = row.auxiliary_fields
    need(sameNames(auxiliary, declaredAuxiliary) && row.latest_missing_fields.every(field => auxiliary.includes(field)))
    need(oneOf(row.input_state, ['not_evaluated', 'input_missing', 'ready'])
      && oneOf(row.signal_state, ['not_evaluated', 'not_recorded', 'input_missing', 'signal_generated', 'conditions_not_met'])
      && (row.latest_action === null || oneOf(row.latest_action, ['BUY', 'SELL', 'HOLD'])))
    if (row.signal_counts === null) need(row.signal_state === 'not_recorded' && row.latest_action === null)
    else {
      const counts = keys(row.signal_counts, 'BUY SELL')
      need(count(counts.BUY) && count(counts.SELL) && row.signal_state !== 'not_recorded')
    }
    need(within(row.last_successful_calculation_date, 'evaluation') && within(row.last_fully_informed_date, 'evaluation')
      && (row.input_state === 'not_evaluated') === (row.last_successful_calculation_date === null)
      && (row.last_fully_informed_date === null || row.last_successful_calculation_date !== null
        && String(row.last_fully_informed_date) <= String(row.last_successful_calculation_date)))
    if (!record(row.field_coverage) || Object.keys(row.field_coverage).length > 64 || !record(row.branches) || Object.keys(row.branches).length > 64) return invalid()
    need(sameKeys(row.field_coverage, [...diagnosticWire.market_fields, ...declaredAuxiliary])
      && sameKeys(row.branches, Object.keys(declaredBranches)))
    for (const field of Object.values(row.field_coverage)) {
      const coverage = keys(field, 'input evaluation')
      for (const scope of ['input', 'evaluation']) {
        const facts = keys(coverage[scope], 'expected_count non_null_count first_non_null_date last_non_null_date missing_reasons')
        need(count(facts.expected_count) && count(facts.non_null_count) && facts.non_null_count <= facts.expected_count
          && facts.expected_count === ranges[scope].expected_dates && within(facts.first_non_null_date, scope) && within(facts.last_non_null_date, scope)
          && (facts.first_non_null_date === null) === (facts.non_null_count === 0) && (facts.last_non_null_date === null) === (facts.non_null_count === 0)
          && (facts.non_null_count === 0 || String(facts.first_non_null_date) <= String(facts.last_non_null_date)))
        if (!record(facts.missing_reasons)) return invalid()
        need(Object.keys(facts.missing_reasons).every(key => ['observation_missing', 'not_supplied_in_observation'].includes(key))
          && Object.values(facts.missing_reasons).every(count)
          && Object.values(facts.missing_reasons).reduce<number>((total, item) => total + Number(item), 0) === Number(facts.expected_count) - Number(facts.non_null_count))
      }
    }
    for (const [name, branch] of Object.entries(row.branches)) {
      const facts = keys(branch, 'required_fields missing_fields state')
      if (!names(facts.required_fields) || !names(facts.missing_fields)) return invalid()
      const required = facts.required_fields
      need(sameNames(required, declaredBranches[name])
        && sameNames(facts.missing_fields, required.filter(field => (row.latest_missing_fields as string[]).includes(field)))
        && oneOf(facts.state, ['not_evaluated', 'unavailable', 'partially_observed', 'inputs_present']))
    }
  }
  need(new TextEncoder().encode(JSON.stringify(value)).length <= 131072)
  return value as StrategyDiagnostics
}

export function strategyRuntimeLabel(strategy: NonNullable<StrategyRuntime['strategy']>) {
  return strategy.status === 'converged'
    ? strategy.execution_position_qualified === true ? '本轮调仓已完成' : '本阶段策略计算已完成'
    : runtimeLabels[strategy.status]
}

/** 附加诊断单独归一化；本函数仅在原核心资金/持仓校验全部通过后调用。 */
function projectDiagnosticFields(strategy: Record<string, unknown>, symbols: ReadonlySet<string>):
  Pick<NonNullable<StrategyRuntime['strategy']>, 'diagnostics' | 'diagnostics_state' | 'diagnostics_reason'> {
  const unavailable = () => {
    // 每次投影最多一条固定事件，不输出原数据；告警本身不影响核心结果。
    try { console.warn('strategy_diagnostics_unavailable') } catch { /* 只读附加告警保持尽力而为。 */ }
    return { diagnostics: null, diagnostics_state: 'unavailable' as const, diagnostics_reason: 'invalid_diagnostics' as const }
  }
  const metadata = strategy.diagnostics_state !== undefined || strategy.diagnostics_reason !== undefined
  const absentReason = strategy.decision_at === null ? 'not_calculated' : 'not_recorded'
  if (strategy.diagnostics === undefined || strategy.diagnostics === null) {
    if (!metadata) return { diagnostics: null, diagnostics_state: 'absent',
      diagnostics_reason: absentReason }
    if (strategy.diagnostics_state === 'unavailable' && strategy.diagnostics_reason === 'invalid_diagnostics')
      return { diagnostics: null, diagnostics_state: 'unavailable', diagnostics_reason: 'invalid_diagnostics' }
    if (strategy.diagnostics_state === 'absent'
      && strategy.diagnostics_reason === absentReason)
      return { diagnostics: null, diagnostics_state: 'absent', diagnostics_reason: absentReason }
    return unavailable()
  }
  try {
    const diagnostics = validateStrategyDiagnostics(strategy.diagnostics, symbols)
    if (metadata && (strategy.diagnostics_state !== 'available' || strategy.diagnostics_reason !== null)) return unavailable()
    return { diagnostics, diagnostics_state: 'available', diagnostics_reason: null }
  } catch {
    return unavailable()
  }
}

export function validateStrategyRuntime(data: unknown): StrategyRuntime {
  const invalid = () => { throw new Error('策略运行结果格式无效，请重新读取') }
  if (!record(data) || data.schema_version !== 'guanheng.strategy-runtime.v1' || data.read_only !== true
    || !time(data.observed_at) || typeof data.state !== 'string' || !['unconfigured', 'waiting', 'available'].includes(data.state)) return invalid()
  if (data.runtime_state !== undefined && (typeof data.runtime_state !== 'string'
    || !['new','starting','ready','stopping','closed','faulted','unconfigured'].includes(data.runtime_state))) return invalid()
  if (data.execution_state !== undefined && data.execution_state !== 'not_started') return invalid()
  if (data.state !== 'available') { if (data.strategy !== null) return invalid(); return data as StrategyRuntime }
  const s = data.strategy
  if (!record(s) || typeof s.display_name !== 'string' || !s.display_name || s.display_name.length > 256
    || !(s.strategy_version === null || typeof s.strategy_version === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.+-]{0,63}$/.test(s.strategy_version))
    || s.strategy_id !== undefined && (typeof s.strategy_id !== 'string' || !s.strategy_id || s.strategy_id.length > 64)
    || typeof s.status !== 'string' || !Object.hasOwn(runtimeLabels, s.status)
    || s.status_label !== runtimeLabels[s.status as keyof typeof runtimeLabels] || s.broker_position_qualified !== false
    || Object.hasOwn(s, 'execution_position_qualified') && typeof s.execution_position_qualified !== 'boolean'
    || !(s.decision_at === null || time(s.decision_at)) || !(s.broker_observed_at === null || time(s.broker_observed_at))
    || !Array.isArray(s.positions) || s.positions.length > 64) return invalid()
  const seen = new Set<string>()
  for (const row of s.positions) {
    if (!record(row) || typeof row.symbol !== 'string' || !/^\d{6}\.(SH|SZ)$/.test(row.symbol) || seen.has(row.symbol)
      || !['theoretical_quantity', 'theoretical_sellable', 'pending_target', 'stage_target', 'broker_quantity', 'broker_sellable'].every(k => quantity(row[k]))
      || !(row.target_weight === null || typeof row.target_weight === 'number' && Number.isFinite(row.target_weight) && row.target_weight >= 0 && row.target_weight <= 1)
      || typeof row.theoretical_sellable === 'number' && (typeof row.theoretical_quantity !== 'number' || row.theoretical_sellable > row.theoretical_quantity)
      || typeof row.broker_sellable === 'number' && (typeof row.broker_quantity !== 'number' || row.broker_sellable > row.broker_quantity)
      || (row.market_value_basis !== undefined && row.market_value_basis !== 'last-quote')
      || (row.market_value_cny !== undefined || row.market_value_observed_at !== undefined || row.market_value_basis !== undefined)
        && (s.position_basis !== 'strategy-allocated' || typeof row.market_value_cny !== 'string'
          || !/^\d{1,64}(?:\.\d{1,64})?$/.test(row.market_value_cny) || !time(row.market_value_observed_at))) return invalid()
    seen.add(row.symbol)
  }
  if (s.consumed_signal !== undefined) {
    const signal = s.consumed_signal
    const day = (v: unknown): v is string => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v)
    if (!record(signal) || signal.decision_at !== s.decision_at || !day(signal.decision_date)
      || !day(signal.eligible_date) || signal.decision_date >= signal.eligible_date
      || !Array.isArray(signal.securities) || signal.securities.length !== seen.size) return invalid()
    const remaining = new Set(seen)
    for (const row of signal.securities) {
      if (!record(row) || typeof row.symbol !== 'string' || !remaining.delete(row.symbol)
        || typeof row.qualified !== 'boolean' || !Array.isArray(row.actions)
        || !row.actions.every(action => action === 'BUY' || action === 'SELL')
        || !(row.model_held === null || typeof row.model_held === 'boolean')
        || !Array.isArray(row.auxiliary_missing)
        || !row.auxiliary_missing.every(value => typeof value === 'string' && /^[a-z_]+$/.test(value))) return invalid()
    }
  }
  if (s.position_basis !== undefined && s.position_basis !== 'strategy-allocated') return invalid()
  if (record(s.owned_valuation) && s.owned_valuation.unknown_fee_count !== undefined
    && !quantity(s.owned_valuation.unknown_fee_count)) return invalid()
  validateCapitalFields(s)
  return { ...data, strategy: { ...s, ...projectDiagnosticFields(s, seen), ...projectCurrentAuxiliary(s, seen) } } as StrategyRuntime
}

export async function fetchStrategyRuntime(signal: AbortSignal, strategyId?: string): Promise<StrategyRuntime> {
  return validateStrategyRuntime(await fetchReadJson<unknown>('/v1/ui/strategy-runtime' + (strategyId ? '?' + new URLSearchParams({strategy_id:strategyId}) : ''), '策略运行结果', signal, 'status'))
}
