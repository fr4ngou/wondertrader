/** WT发布的策略资金；读取端只校验和展示，不重算本金、净值或可用现金。 */
export type CapitalBaseline = {
  /** WT资金基准协议版本，决定下列字段的解释方式。 */
  schema: 'guanheng.current-capital-baseline.v1'
  /** 本次启用的总资本，含现有库存；单位元，精确十进制字符串。 */
  total_cny: string
  /** WT保存的基准声明来源，用于区分用户分配与其他资金来源。 */
  source: string
  /** WT首次启用此基准的原时间，含时区；正常重启沿用。 */
  baseline_at: string
  /** 旧系统历史初始本金未迁移，null表示未知。 */
  historical_initial_capital_cny: null
}

/** 金额均为人民币元的精确十进制字符串；零为已知零，null为来源未提供或当前不可用。 */
export type StrategyCapital = {
  /** WT资金观察协议版本。 */
  schema: 'guanheng.strategy-capital-observation.v1'
  /** 所有金额的币种，本协议固定为人民币。 */
  currency: 'CNY'
  /** 本份观察实际采用的资金基准，须与策略详情中的基准一致。 */
  baseline: CapitalBaseline
  /** WT首次初始化或原CTA回调的估值截止时间，含时区；页面刷新保持该原时间。 */
  observed_at: string
  /** 所用报价中最旧的事件时间，含时区；旧发布可省略，null表示未提供。 */
  price_observed_at?: string | null
  /** 券商持仓查询结果的原接收时间，含时区。 */
  position_observed_at: string
  /** 市值使用券商持仓和原CTA价格，或首次初始化的真实QMT快照；两种来源均由WT声明。 */
  market_value_source: 'broker-position+raw-CTA-price' | 'broker-position+raw-QMT-snapshot'
  /** WT原生发布的本次运行损益，包含其原费用口径；允许负值。 */
  native_pnl_cny: string
  /** WT发布的策略总资产，包含现金和库存市值。 */
  nav_cny: string
  /** WT按券商持仓与market_value_source声明的报价发布的库存市值，单位元。 */
  market_value_cny: string
  /** WT发布的策略现金余额；允许负值，与可用资金分开显示。 */
  cash_balance_cny: string
  /** 经账户约束核定的策略可用现金；账户缺失、过期或停止时为null。 */
  spendable_cash_cny: string | null
  /** 原账户观察是否仍满足本次可用资金计算条件；由WT及读取投影判定。 */
  account_observation_qualified: boolean
  /** 原账户批次查询完成时间，含时区；尚未取得时为null。 */
  account_observed_at: string | null
  /** 原账户观察的有效截止，含时区；没有原观察时为null。 */
  account_valid_until: string | null
  /** 券商全账户可用现金上限，作为策略现金约束；未取得为null。 */
  account_available_cny: string | null
  /** 券商全账户冻结现金，作为保守约束；未取得为null，不补零。 */
  account_frozen_cash_cny: string | null
  /** 原完整账户观察正文的SHA256；没有该正文时为null。 */
  account_source_sha256: string | null
  /** 冻结现金及可用上限的作用域为全账户，不表示分配给本策略。 */
  cash_constraint_scope: 'account-wide-conservative-limit'
  /** 旧系统历史累计收益率未迁移，null表示未知。 */
  historical_return_pct: null
}
export type CapitalFields = {
  /** WT发布的运行资本基准；旧协议可省略，尚未发布时为null。 */
  capital_baseline?: CapitalBaseline | null
  /** 与基准同源的策略资金观察；旧协议可省略，尚未发布时为null。 */
  capital?: StrategyCapital | null
}

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
    || !(capital.price_observed_at == null || time(capital.price_observed_at))
    || !['native_pnl_cny','nav_cny','market_value_cny','cash_balance_cny'].every(key => amount(capital[key]))
    || !(capital.spendable_cash_cny === null || amount(capital.spendable_cash_cny))
    || typeof capital.account_observation_qualified !== 'boolean'
    || capital.spendable_cash_cny !== null && capital.account_observation_qualified !== true
    || !(capital.account_observed_at === null || time(capital.account_observed_at))
    || !(capital.account_valid_until === null || time(capital.account_valid_until))
    || !['account_available_cny','account_frozen_cash_cny'].every(key => capital[key] === null || amount(capital[key]))
    || !(capital.account_source_sha256 === null || typeof capital.account_source_sha256 === 'string' && /^[a-f0-9]{64}$/.test(capital.account_source_sha256))
    || capital.cash_constraint_scope !== 'account-wide-conservative-limit'
    || !['broker-position+raw-CTA-price', 'broker-position+raw-QMT-snapshot'].includes(String(capital.market_value_source))
    || capital.historical_return_pct !== null) {
    throw new Error('策略资金格式无效，请重新读取')
  }
}
