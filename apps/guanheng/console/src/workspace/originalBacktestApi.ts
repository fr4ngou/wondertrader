import { archiveConfiguration, fetchBacktestReadJson, tradingDate, validDigest, validId, type ArchiveEntry } from './backtestApi'
import { boundedBacktestTree, invalidBacktest, isObject } from './backtestV2'

export const ORIGINAL_STRATEGY = 'resonance-original-351f9d5-stable'
export const ORIGINAL_WT_STRATEGY = 'resonance-original-wt-351f9d5-stable'
export const ORIGINAL_NATIVE_REPORT_SCHEMA = 'guanheng.original-native-replay-report.v1'
export const ORIGINAL_VERSION = '0.1.0a1'
export type OriginalArchiveEntry = {
  /** 原版研究报告族；没有WT运行所有者或请求身份。 */ report_family: 'resonance-original'
  /** 导入生成的不可变报告选择ID。 */ run_id: string
  /** 原组合日期行数。 */ record_count: number
  /** 原报告正文SHA256。 */ report_sha256: string
  /** 导入完成证明SHA256。 */ receipt_sha256: string
  /** 研究模型适用范围。 */ scope: string
  /** 原冻结区间、标签及输入摘要，不表示WT运行。 */ configuration: ArchiveEntry['configuration']
  /** 轻量身份和归一化权益口径；null为本次归属未知。 */ summary?: {
    /** 独立原版报告族，避免与人民币本金合同混用。 */ report_family: 'resonance-original'
    /** 原算法固定身份与独立展示版本。 */ strategy: {
      /** 固定策略业务ID。 */ id: string
      /** 原版对照展示版本。 */ version: string
    }
    /** 归一化权益，无人民币单位。 */ unit: 'normalized-equity'
    /** 原组合初始权益。 */ initial_equity: 1
  } | null
}
export const isOriginalEntry = (entry: ArchiveEntry | OriginalArchiveEntry): entry is OriginalArchiveEntry =>
  'report_family' in entry && entry.report_family === 'resonance-original'

const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const count = (v: unknown): v is number => Number.isSafeInteger(v) && Number(v) >= 0 && Number(v) <= 65536
const text = (v: unknown): v is string => typeof v === 'string' && v.length > 0 && v.length <= 512 && !/[\u0000-\u001f]/.test(v)

/** 仅原版分支准入；未知family、伪造WT命令身份及不一致的摘要均拒绝。 */
export function validateOriginalEntry(v: Record<string, unknown>, summaries: boolean): OriginalArchiveEntry {
  const names = ['report_family', 'run_id', 'record_count', 'report_sha256', 'receipt_sha256', 'scope', 'configuration', ...(summaries ? ['summary'] : [])]
  if (Object.keys(v).length !== names.length || names.some(k => !Object.hasOwn(v, k))
    || v.report_family !== 'resonance-original' || !validId(v.run_id) || !validDigest(v.report_sha256)
    || !validDigest(v.receipt_sha256) || !count(v.record_count) || Number(v.record_count) > 4096
    || !text(v.scope) || !archiveConfiguration(v.configuration)) invalidBacktest()
  if (summaries && v.summary !== null) {
    if (!isObject(v.summary) || Object.keys(v.summary).length !== 4 || v.summary.report_family !== 'resonance-original' || v.summary.unit !== 'normalized-equity'
      || v.summary.initial_equity !== 1 || !isObject(v.summary.strategy) || Object.keys(v.summary.strategy).length !== 2
      || v.summary.strategy.id !== ORIGINAL_STRATEGY || v.summary.strategy.version !== ORIGINAL_VERSION) invalidBacktest()
  }
  return v as OriginalArchiveEntry
}

export type OriginalPerformance = {
  /** 归一化原版绩效投影，区别于WT人民币绩效。 */ schema: 'orr-performance-v1'
  /** 不可变报告选择ID。 */ run_id: string
  /** 完成证明原字节SHA256，与报告一起隔离缓存。 */ receipt_sha256: string
  /** 原报告原字节SHA256。 */ report_sha256: string
  /** 固定算法与展示版本。 */ strategy: {
    /** 原版对照业务ID。 */ id: string
    /** 独立展示版本。 */ version: string
    /** 原stable算法身份。 */ algorithm_id: string
  }
  /** 与目录完全相同的冻结区间及输入摘要。 */ configuration: ArchiveEntry['configuration']
  /** 数值单位，仅表示归一化权益。 */ unit: 'normalized-equity'
  /** 原模型指标，不采用人民币本金。 */ metrics: {
    /** 原组合归一化初值，恒为1。 */ initial_equity: 1
    /** 最后可用归一化权益；null表示没有观测。 */ last_equity: number | null
    /** 累计收益，百分数；缺观测为null。 */ total_return_pct: number | null
    /** 已观察日末最大回撤，正百分数；缺观测为null。 */ observed_max_drawdown_pct: number | null
    /** 原组合模型零费用，不代表真实交易成本。 */ fees: 0
  }
  /** 有值、缺失日期数量及最后可用交易日。 */ observations: {
    /** 当前报告日期总数。 */ total: number
    /** 有权益观测的日期数。 */ available: number
    /** 权益缺失日期数。 */ missing: number
    /** 最后有值的上海交易日YYYYMMDD；无值为null。 */ last_trading_date: number | null
  }
  /** 实际交易日与归一化日末权益。 */ points: [number, number | null][]
  /** 原成交、等权、费用及预热模型的声明。 */ model: Record<string, unknown>
  /** 已冻结来源说明，不将其当成历史首次可知证明。 */ source: unknown
  /** 数据类型，明确服务器原字段或QMT重算等来源区别。 */ data_kind: string
  /** 完整冻结输入规范JSON的SHA256。 */ input_sha256: string
  /** 固定原算法来源清单规范JSON的SHA256。 */ source_manifest_sha256: string
  /** 研究报告不授账户执行资格。 */ execution_qualified: false
  /** 历史首次可知时点未取得资格。 */ point_in_time_qualified: false
  /** 明确的模型适用范围。 */ scope: string
}
function identity(v: unknown, e: OriginalArchiveEntry): Record<string, unknown> {
  boundedBacktestTree(v)
  if (!isObject(v) || v.run_id !== e.run_id || v.receipt_sha256 !== e.receipt_sha256 || v.report_sha256 !== e.report_sha256) invalidBacktest()
  return v
}
/** 读原版投影，不发起回测；逐行日期与完成原件身份保持一致。 */
export async function fetchOriginalPerformance(e: OriginalArchiveEntry, signal?: AbortSignal): Promise<OriginalPerformance> {
  const v = identity(await fetchBacktestReadJson<unknown>(`/v1/ui/backtest/archive/${e.run_id}/performance?receipt_sha256=${e.receipt_sha256}`, '原版回测绩效', signal), e)
  if (v.schema !== 'orr-performance-v1' || v.unit !== 'normalized-equity' || !isObject(v.strategy)
    || v.strategy.id !== ORIGINAL_STRATEGY || v.strategy.version !== ORIGINAL_VERSION || v.strategy.algorithm_id !== ORIGINAL_STRATEGY
    || !archiveConfiguration(v.configuration) || Object.entries(e.configuration).some(([k, val]) => (v.configuration as Record<string, unknown>)[k] !== val)
    || !isObject(v.metrics) || v.metrics.initial_equity !== 1 || v.metrics.fees !== 0
    || ![v.metrics.last_equity, v.metrics.total_return_pct, v.metrics.observed_max_drawdown_pct].every(n => n === null || finite(n))
    || !isObject(v.observations) || v.observations.total !== e.record_count || !count(v.observations.available) || !count(v.observations.missing)
    || Number(v.observations.available) + Number(v.observations.missing) !== e.record_count
    || !Array.isArray(v.points) || v.points.length !== e.record_count || !isObject(v.model) || !text(v.data_kind)
    || !validDigest(v.input_sha256) || !validDigest(v.source_manifest_sha256) || !text(v.scope)
    || v.execution_qualified !== false || v.point_in_time_qualified !== false) invalidBacktest()
  let previous = 0; let available = 0; let lastDate: number | null = null; let last: number | null = null
  for (const p of v.points) {
    if (!Array.isArray(p) || p.length !== 2 || !tradingDate(p[0]) || p[0] <= previous || p[1] !== null && (!finite(p[1]) || p[1] < 0)) invalidBacktest()
    previous = p[0]
    if (p[1] !== null) { available++; lastDate = p[0]; last = p[1] }
  }
  if (available !== v.observations.available || lastDate !== v.observations.last_trading_date || last !== v.metrics.last_equity) invalidBacktest()
  return v as OriginalPerformance
}

export type OriginalVisuals = {
  /** 原版曲线派生与成交计数，权益沿原报告。 */ schema: 'orr-visuals-v1'
  /** 不可变报告选择ID。 */ run_id: string
  /** 完成证明原字节SHA256。 */ receipt_sha256: string
  /** 原报告原字节SHA256。 */ report_sha256: string
  /** 原组合模拟成交日志已知，false保持未知。 */ trades_available: boolean
  /** 日期、日收益%、负回撤%、模拟买入/卖出/其他笔数。 */ points: [number, number | null, number | null, number, number, number][]
}
export async function fetchOriginalVisuals(e: OriginalArchiveEntry, signal?: AbortSignal): Promise<OriginalVisuals> {
  const v = identity(await fetchBacktestReadJson<unknown>(`/v1/ui/backtest/archive/${e.run_id}/visuals?receipt_sha256=${e.receipt_sha256}`, '原版回测曲线', signal), e)
  if (v.schema !== 'orr-visuals-v1' || typeof v.trades_available !== 'boolean' || !Array.isArray(v.points) || v.points.length !== e.record_count) invalidBacktest()
  let previous = 0
  for (const p of v.points) {
    if (!Array.isArray(p) || p.length !== 6 || !tradingDate(p[0]) || p[0] <= previous || p.slice(1, 3).some(n => n !== null && !finite(n)) || p.slice(3).some(n => !count(n))) invalidBacktest()
    previous = p[0]
  }
  return v as OriginalVisuals
}

export type OriginalLedger = {
  /** 成交额和权益的单位，保持原模型。 */ unit: 'normalized-equity'
  /** 原版模拟成交分页，不复用券商成交模型。 */ schema: 'orr-ledger-v1'
  /** 不可变报告选择ID。 */ run_id: string
  /** 完成证明原字节SHA256。 */ receipt_sha256: string
  /** 原报告原字节SHA256。 */ report_sha256: string
  /** 所选交易日，null表示全部日期。 */ date: number | null
  /** 原报告未保存日末持仓数量，保持未知。 */ positions_available: false
  /** 缺原件的空投影，不能解释为空仓。 */ positions: []
  /** 原组合成交是否已知。 */ trades_available: boolean
  /** 日期筛选后的全部模拟成交数。 */ total: number
  /** 当前分页起点，按筛选后序列计数。 */ offset: number
  /** 归一化权益成交额与其计算的浮点份额，费用固定零。 */ trades: {
    /** 原日志稳定序号。 */ index: number
    /** 执行日，上海交易日期YYYYMMDD。 */ date: number
    /** 对应原信号日，上海交易日期YYYYMMDD。 */ signal_date: number
    /** 原六位证券代码。 */ symbol: string
    /** 原模型买入或卖出方向。 */ side: 'buy' | 'sell'
    /** 原日志动作BUY/REFILL/SELL/TRIM。 */ action: string
    /** 原成交价格，单位沿原输入声明。 */ price: number
    /** 本笔归一化权益成交额。 */ amount: number
    /** amount/price得到的浮点模型份额。 */ quantity: number
    /** 原模型零费用。 */ fee: 0
    /** 相对组合权益权重，百分数。 */ weight_pct: number
    /** 原日志理由，缺少原说明时为空字符串。 */ reason: string
  }[]
}
export async function fetchOriginalLedger(e: OriginalArchiveEntry, day: number | null, offset: number, signal?: AbortSignal): Promise<OriginalLedger> {
  if (day !== null && !tradingDate(day) || !count(offset)) invalidBacktest()
  const query = new URLSearchParams({ receipt_sha256: e.receipt_sha256, offset: String(offset) })
  if (day !== null) query.set('day', String(day))
  const v = identity(await fetchBacktestReadJson<unknown>(`/v1/ui/backtest/archive/${e.run_id}/ledger?${query}`, '原版模拟调仓', signal), e)
  if (v.schema !== 'orr-ledger-v1' || v.unit !== 'normalized-equity' || v.date !== day || v.offset !== offset || !count(v.total)
    || v.positions_available !== false || !Array.isArray(v.positions) || v.positions.length !== 0 || typeof v.trades_available !== 'boolean'
    || !Array.isArray(v.trades) || v.trades.length !== Math.min(50, Math.max(0, Number(v.total) - offset))) invalidBacktest()
  let previous = -1
  for (const t of v.trades) {
    if (!isObject(t) || !count(t.index) || t.index <= previous || !tradingDate(t.date) || day !== null && day !== t.date
      || !tradingDate(t.signal_date) || t.signal_date >= t.date || !text(t.symbol) || !/^\d{6}$/.test(t.symbol)
      || !['buy', 'sell'].includes(String(t.side)) || !['BUY', 'REFILL', 'SELL', 'TRIM'].includes(String(t.action))
      || !finite(t.price) || t.price <= 0 || !finite(t.quantity) || t.quantity < 0 || !finite(t.amount) || t.amount < 0
      || t.fee !== 0 || !finite(t.weight_pct) || typeof t.reason !== 'string' || t.reason.length > 2048) invalidBacktest()
    previous = t.index
  }
  return v as OriginalLedger
}

export type OriginalSignals = {
  /** 原算法信号，与组合模拟调仓分别读取。 */ schema: 'orr-signals-v1'
  /** 不可变报告选择ID。 */ run_id: string
  /** 完成证明原字节SHA256。 */ receipt_sha256: string
  /** 原报告原字节SHA256。 */ report_sha256: string
  /** 上海交易日期筛选；null查询全部。 */ date: number | null
  /** 当前筛选的原信号总数。 */ total: number
  /** 当前分页起点。 */ offset: number
  /** 原信号收盘价与原理由，不表示实际成交。 */ signals: {
    /** 原信号稳定序号。 */ index: number
    /** 信号发生日YYYYMMDD。 */ date: number
    /** 六位原证券代码。 */ symbol: string
    /** 原算法动作。 */ action: 'BUY' | 'SELL'
    /** 信号日收盘价，单位沿原输入声明。 */ price: number
    /** 原算法理由；原件缺失理由时为空字符串。 */ reason: string
  }[]
  /** 原模型研究范围。 */ scope: string
}
export async function fetchOriginalSignals(e: OriginalArchiveEntry, day: number | null, offset: number, signal?: AbortSignal): Promise<OriginalSignals> {
  if (day !== null && !tradingDate(day) || !count(offset)) invalidBacktest()
  const query = new URLSearchParams({ receipt_sha256: e.receipt_sha256, offset: String(offset) })
  if (day !== null) query.set('day', String(day))
  const v = identity(await fetchBacktestReadJson<unknown>(`/v1/ui/backtest/archive/${e.run_id}/signals?${query}`, '原版算法信号', signal), e)
  if (v.schema !== 'orr-signals-v1' || v.date !== day || v.offset !== offset || !count(v.total) || !text(v.scope)
    || !Array.isArray(v.signals) || v.signals.length !== Math.min(50, Math.max(0, Number(v.total) - offset))) invalidBacktest()
  let previous = -1
  for (const s of v.signals) {
    if (!isObject(s) || !count(s.index) || s.index <= previous || !tradingDate(s.date) || day !== null && s.date !== day
      || !text(s.symbol) || !/^\d{6}$/.test(s.symbol) || !['BUY', 'SELL'].includes(String(s.action))
      || !finite(s.price) || s.price <= 0 || typeof s.reason !== 'string' || s.reason.length > 2048) invalidBacktest()
    previous = s.index
  }
  return v as OriginalSignals
}
