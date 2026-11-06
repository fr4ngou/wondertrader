import { diagnosticWire } from './strategyDiagnosticWire.generated'

export type CurrentAuxiliaryValue = {
  /** 原实际证券，不替换来源。 */ symbol: string
  /** 原派生字段名，单位沿V1声明。 */ field: string
  /** 原有限数值，零保持为真实值。 */ value: number
  /** 来源统计日，YYYY-MM-DD。 */ statistic_date: string
  /** 全依赖真实知晓上界，带时区。 */ known_by: string
  /** 原完整依赖交易日期。 */ source_dates: string[]
  /** 原完整来源SHA256集合。 */ sources: string[]
}
export type CurrentAuxiliary = {
  /** 独立当前消费公开投影版本。 */ schema: 'guanheng.current-auxiliary-consumption.v1'
  /** 实际求值截止，区别于读取时刻。 */ decision_at: string
  /** 最近实际闭合行情日。 */ market_basis_date: string
  /** 原当前视图稳定数据修订摘要。 */ data_revision: string
  /** 原唯一派生版本。 */ derivation_version: string
  /** 原历史行保持的发布事实，历史覆盖独立表达。 */ historical_rows_unchanged: true
  /** 原角色必需字段，无辅助依赖时为空。 */ required_fields: Record<string, string[]>
  /** 原全部可用派生值，包含角色不消费的字段。 */ available_fields: Record<string, Record<string, CurrentAuxiliaryValue>>
  /** 原本次实际消费值，不以可用值补齐。 */ consumed_fields: Record<string, Record<string, CurrentAuxiliaryValue>>
  /** 原已在历史帧生效的字段分区。 */ historical_effective_fields: Record<string, Record<string, CurrentAuxiliaryValue>>
}
export type CurrentAuxiliaryFields = {
  /** 可选当前消费，兼容旧公开响应。 */ current_auxiliary?: CurrentAuxiliary | null
  /** 当前附加信息的独立可用性。 */ current_auxiliary_state?: 'available' | 'absent' | 'unavailable'
  /** 稳定原因码，不携带原文。 */ current_auxiliary_reason?: 'not_calculated' | 'not_recorded' | 'invalid_current_auxiliary' | null
}
const record = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === 'object' && !Array.isArray(v)
const stamp = (v: unknown): v is string => typeof v === 'string' && v.length <= 64 && /(Z|[+-]\d{2}:\d{2})$/.test(v) && Number.isFinite(Date.parse(v))
const day = (v: unknown): v is string => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v)
  && Number.isFinite(Date.parse(v)) && new Date(v).toISOString().slice(0, 10) === v
const hash = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v)
const need = (v: unknown): void => { if (!v) throw new Error('当前辅助消费格式无效') }
const keys = (v: unknown, names: readonly string[]): v is Record<string, unknown> => record(v)
  && Object.keys(v).length === names.length && names.every(n => Object.hasOwn(v, n))
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)

/** 只核原值、时间及归属；角色依赖复用V1生成声明，不执行信号数学。 */
function validate(value: unknown, symbols: ReadonlySet<string>, decisionAt: unknown): CurrentAuxiliary {
  if (!keys(value, ['schema', 'decision_at', 'market_basis_date', 'data_revision', 'derivation_version',
    'historical_rows_unchanged', 'required_fields', 'available_fields', 'consumed_fields', 'historical_effective_fields'])) throw new Error('当前辅助消费格式无效')
  need(value.schema === 'guanheng.current-auxiliary-consumption.v1' && stamp(value.decision_at) && stamp(decisionAt)
    && Date.parse(String(value.decision_at)) === Date.parse(String(decisionAt)) && day(value.market_basis_date)
    && hash(value.data_revision) && value.derivation_version === diagnosticWire.current_derivation_version
    && value.historical_rows_unchanged === true && symbols.size === 8)
  for (const name of ['required_fields', 'available_fields', 'consumed_fields', 'historical_effective_fields']) need(keys(value[name], [...symbols]))
  const common: Readonly<Record<string, string>> = diagnosticWire.common_roles
  const branches: Readonly<Record<string, Readonly<Record<string, readonly string[]>>>> = diagnosticWire.branches
  const mapping = value as unknown as CurrentAuxiliary
  need(Object.keys(common).every(s => symbols.has(s)))
  for (const symbol of symbols) {
    const required = [...new Set(Object.values(branches[common[symbol] ?? diagnosticWire.remaining_role]).flat())]
    need(same(mapping.required_fields[symbol], required))
    const available = mapping.available_fields[symbol]
    need(record(available) && Object.keys(available).length <= 4)
    for (const [field, item] of Object.entries(available)) {
      need(keys(item, ['symbol', 'field', 'value', 'statistic_date', 'known_by', 'source_dates', 'sources']))
      need(diagnosticWire.current_fields.some(f => f === field) && item.symbol === symbol && item.field === field
        && typeof item.value === 'number' && Number.isFinite(item.value)
        && (field === 'shares_delta_yi' || item.value >= 0 && item.value <= 100)
        && day(item.statistic_date) && item.statistic_date <= String(value.market_basis_date)
        && stamp(item.known_by) && Date.parse(item.known_by) <= Date.parse(String(value.decision_at))
        && item.statistic_date <= new Date(Date.parse(item.known_by) + 8 * 3600_000).toISOString().slice(0, 10))
      const limits = diagnosticWire.current_dependency_ranges[field as keyof typeof diagnosticWire.current_dependency_ranges]
      need(limits && Array.isArray(item.source_dates) && item.source_dates.length >= limits[0] && item.source_dates.length <= limits[1]
        && item.source_dates.every(day) && same([...new Set(item.source_dates)].sort(), item.source_dates)
        && item.source_dates.at(-1) === item.statistic_date)
      need(Array.isArray(item.sources) && item.sources.length >= 1 && item.sources.length <= 64
        && item.sources.every(hash) && same([...new Set(item.sources)].sort(), item.sources))
    }
    for (const name of ['consumed_fields', 'historical_effective_fields'] as const) {
      const fields = mapping[name][symbol]
      need(record(fields) && Object.keys(fields).every(f => Object.hasOwn(available, f)))
      for (const [field, item] of Object.entries(fields)) {
        // JSON键顺序变化不改变同一字段事实身份，逐属性比较原值。
        need(keys(item, Object.keys(available[field])) && Object.entries(available[field]).every(([k, v]) => same((item as unknown as Record<string, unknown>)[k], v)))
      }
    }
    const expected = required.filter(f => Object.hasOwn(available, f) && !Object.hasOwn(mapping.historical_effective_fields[symbol], f))
    need(same(Object.keys(mapping.consumed_fields[symbol]).sort(), expected.sort()))
  }
  return mapping
}

/** 在核心准入之后独立降级；资金、持仓与历史诊断保持原验证结果。 */
export function projectCurrentAuxiliary(strategy: Record<string, unknown>, symbols: ReadonlySet<string>): CurrentAuxiliaryFields {
  const absent = strategy.decision_at === null ? 'not_calculated' : 'not_recorded'
  const metadata = strategy.current_auxiliary_state !== undefined || strategy.current_auxiliary_reason !== undefined
  try {
    if (strategy.current_auxiliary === undefined || strategy.current_auxiliary === null) {
      if (!metadata || strategy.current_auxiliary_state === 'absent' && strategy.current_auxiliary_reason === absent)
        return { current_auxiliary: null, current_auxiliary_state: 'absent', current_auxiliary_reason: absent }
      if (strategy.current_auxiliary_state === 'unavailable' && strategy.current_auxiliary_reason === 'invalid_current_auxiliary')
        return { current_auxiliary: null, current_auxiliary_state: 'unavailable', current_auxiliary_reason: 'invalid_current_auxiliary' }
      throw new Error('当前辅助消费元数据矛盾')
    }
    const current = validate(strategy.current_auxiliary, symbols, strategy.decision_at)
    need(!metadata || strategy.current_auxiliary_state === 'available' && strategy.current_auxiliary_reason === null)
    return { current_auxiliary: current, current_auxiliary_state: 'available', current_auxiliary_reason: null }
  } catch {
    try { console.warn('strategy_current_auxiliary_unavailable') } catch { /* 附加告警不改变核心读取。 */ }
    return { current_auxiliary: null, current_auxiliary_state: 'unavailable', current_auxiliary_reason: 'invalid_current_auxiliary' }
  }
}

/** 复用原状态行，派生总数放原title，历史计数保持原投影。 */
export function currentAuxiliaryPresentation(strategy: CurrentAuxiliaryFields): { label: string; title: string } {
  const value = strategy.current_auxiliary
  if (!value) return { label: '当前辅助：' + (strategy.current_auxiliary_state === 'unavailable' ? '暂不可用'
    : strategy.current_auxiliary_reason === 'not_calculated' ? '本轮尚未计算' : '旧结果未记录'), title: '当前辅助与历史逐行覆盖分别记录。' }
  const required = Object.values(value.required_fields).reduce((n, fields) => n + fields.length, 0)
  const consumed = Object.values(value.consumed_fields).reduce((n, fields) => n + Object.keys(fields).length, 0)
  const available = Object.values(value.available_fields).reduce((n, fields) => n + Object.keys(fields).length, 0)
  const known = Object.entries(value.required_fields).reduce((n, [s, fields]) => n + fields.filter(f => Object.hasOwn(value.available_fields[s], f)).length, 0)
  const label = consumed === required ? `必需${consumed}/${required}已消费（齐备）`
    : known === required ? `必需${known}/${required}已知，本次当前消费${consumed}项`
      : `本次消费${consumed}/${required}项，${required - known}项尚缺`
  return { label: '当前辅助：' + label, title: `可用派生共${available}项；行情基准日${value.market_basis_date}；历史逐行覆盖保持原值，独立表达。` }
}
