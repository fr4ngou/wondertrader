/** WT发布的策略资金；读取端只校验和展示，不重算本金、净值或可用现金。 */
export type CapitalBaseline = {
  schema: 'guanheng.current-capital-baseline.v1'; total_cny: string; source: string; baseline_at: string
  historical_initial_capital_cny: null
}
export type StrategyCapital = {
  schema: 'guanheng.strategy-capital-observation.v1'; currency: 'CNY'; baseline: CapitalBaseline
  observed_at: string; position_observed_at: string; market_value_source: 'broker-position+raw-CTA-price'
  native_pnl_cny: string; nav_cny: string; market_value_cny: string; cash_balance_cny: string
  spendable_cash_cny: string | null; account_observation_qualified: boolean
  account_observed_at: string | null; account_valid_until: string | null
  account_available_cny: string | null; account_frozen_cash_cny: string | null; account_source_sha256: string | null
  cash_constraint_scope: 'account-wide-conservative-limit'; historical_return_pct: null
}
export type CapitalFields = { capital_baseline?: CapitalBaseline | null; capital?: StrategyCapital | null }

const record = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === 'object' && !Array.isArray(v)
const amount = (v: unknown) => typeof v === 'string' && v.length <= 128 && /^-?\d+(?:\.\d+)?$/.test(v) && Number.isFinite(Number(v))
const time = (v: unknown) => typeof v === 'string' && /(Z|[+-]\d{2}:\d{2})$/.test(v) && Number.isFinite(Date.parse(v))
function baseline(v: unknown): v is CapitalBaseline {
  return record(v) && v.schema === 'guanheng.current-capital-baseline.v1' && amount(v.total_cny)
    && typeof v.source === 'string' && v.source.length > 0 && v.source.length <= 256 && time(v.baseline_at)
    && v.historical_initial_capital_cny === null
}

/** 旧v1发布可省略新增字段；新资金保留原金额、来源日期和独立账户约束。 */
export function validateCapitalFields(value: Record<string, unknown>): void {
  const origin = value.capital_baseline
  const capital = value.capital
  if (origin != null && !baseline(origin)) throw new Error('策略资金基准格式无效，请重新读取')
  if (capital == null) return
  if (!record(capital) || !baseline(origin) || !baseline(capital.baseline)
    || capital.baseline.total_cny !== origin.total_cny || capital.baseline.baseline_at !== origin.baseline_at
    || capital.baseline.source !== origin.source || capital.schema !== 'guanheng.strategy-capital-observation.v1'
    || capital.currency !== 'CNY' || !time(capital.observed_at) || !time(capital.position_observed_at)
    || !['native_pnl_cny','nav_cny','market_value_cny','cash_balance_cny'].every(key => amount(capital[key]))
    || !(capital.spendable_cash_cny === null || amount(capital.spendable_cash_cny))
    || typeof capital.account_observation_qualified !== 'boolean'
    || capital.spendable_cash_cny !== null && capital.account_observation_qualified !== true
    || !(capital.account_observed_at === null || time(capital.account_observed_at))
    || !(capital.account_valid_until === null || time(capital.account_valid_until))
    || !['account_available_cny','account_frozen_cash_cny'].every(key => capital[key] === null || amount(capital[key]))
    || !(capital.account_source_sha256 === null || typeof capital.account_source_sha256 === 'string' && /^[a-f0-9]{64}$/.test(capital.account_source_sha256))
    || capital.cash_constraint_scope !== 'account-wide-conservative-limit'
    || capital.market_value_source !== 'broker-position+raw-CTA-price' || capital.historical_return_pct !== null) {
    throw new Error('策略资金格式无效，请重新读取')
  }
}
