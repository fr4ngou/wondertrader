import { fetchBacktestReadJson, type ArchiveEntry, tradingDate } from './backtestApi'
import { boundedBacktestTree, invalidBacktest, isObject } from './backtestV2'

export type PositionPoint = [
  /** 上海交易日 YYYYMMDD，与同报告曲线逐日对应。 */ day: number,
  /** 日末持仓市值除以净值的百分数；null 表示未知。 */ percent: number | null,
  /** 日末持仓市值，人民币十进制文本；已知空仓为 "0"。 */ marketValue: string | null,
  /** 同一日末估值的现金余额，人民币十进制文本；允许负值。 */ cash: string | null,
]
export type Visuals = {
  /** 完成归档的运行身份，与请求一致。 */ run_id: string
  /** 完成收据SHA256，隔离报告切换。 */ receipt_sha256: string
  /** 原报告SHA256。 */ report_sha256: string
  /** 版本化只读投影。 */ schema: 'nbw-visuals-v1'
  /** 原生成交CSV已适配；false表示未知而非零成交。 */ trades_available: boolean
  /** 交易日、日收益%、回撤负百分比、买/卖/其他成交笔数；收益未知为null。 */ points: [number, number | null, number | null, number, number, number][]
  /** 已核报告的仓位扩展；旧服务省略时保持未知。 */ position_points?: PositionPoint[]
}
export type Holding = {
  /** 上海交易日YYYYMMDD。 */ date: number
  /** WT原证券代码。 */ symbol: string
  /** 日末份数，原CSV十进制文本。 */ quantity: string
  /** 累计已实现盈亏（元），未扣费用。 */ realized_cny: string
  /** 持仓浮盈亏（元），未扣费用。 */ floating_cny: string
}
export type Trade = {
  /** 原CSV行序号，稳定区分同分钟多笔。 */ index: number
  /** 上海交易日YYYYMMDD。 */ date: number
  /** 上海时间YYYYMMDDHHmm。 */ time: string
  /** 原WT证券代码。 */ symbol: string
  /** 按原方向/开平映射；无法映射保留unknown。 */ side: 'buy' | 'sell' | 'unknown'
  /** 原多空方向。 */ direction: string
  /** 原开平标识。 */ action: string
  /** 成交价（元），原十进制文本。 */ price: string
  /** 成交份数，原十进制文本。 */ quantity: string
  /** 本笔费用（元），原十进制文本。 */ fee_cny: string
}
export type Ledger = {
  /** 版本化只读明细。 */ schema: 'nbw-ledger-v1'
  /** 请求运行身份。 */ run_id: string
  /** 请求收据摘要。 */ receipt_sha256: string
  /** 原报告摘要。 */ report_sha256: string
  /** 所选交易日；null查询所有成交。 */ date: number | null
  /** 当日日末资金与持仓原件已知；false不能显示空仓。 */ positions_available: boolean
  /** 非零日末持仓；空数组与可用性联合解释。 */ positions: Holding[]
  /** 原成交表可读且已适配。 */ trades_available: boolean
  /** 当前日期筛选后的全部成交笔数。 */ total: number
  /** 当前页起始序号。 */ offset: number
  /** 最多50笔原始成交。 */ trades: Trade[]
}
export type DaySummary = [number, [string, string][] | null, [string, string][] | null, [string, string][] | null, number | null]
/** 同报告全部真实日期的紧凑悬停摘要；null为未知，空集合为已知无持仓/成交。 */
export type DaySummaries = {
  /** 固定只读摘要协议。 */ schema: 'nbw-day-summaries-v1'
  /** 原WT运行身份。 */ run_id: string
  /** 完成收据原字节摘要。 */ receipt_sha256: string
  /** 原报告摘要。 */ report_sha256: string
  /** 日期、持仓、买入合计、卖出合计、其它成交笔数。 */ points: DaySummary[]
}
const decimal = (v: unknown): v is string => typeof v === 'string' && v.length <= 512 && /^-?\d+(?:\.\d+)?$/.test(v)
const text = (v: unknown): v is string => typeof v === 'string' && v.length > 0 && v.length <= 512 && !/[\u0000-\u001f]/.test(v)
const nullableNumber = (v: unknown) => v === null || typeof v === 'number' && Number.isFinite(v)
const count = (v: unknown) => Number.isSafeInteger(v) && Number(v) >= 0 && Number(v) <= 65536
function keys(v: Record<string, unknown>, expected: string) {
  const names = expected.split(' ')
  if (Object.keys(v).length !== names.length || names.some(name => !Object.hasOwn(v, name))) invalidBacktest()
}
function identity(v: unknown, e: ArchiveEntry) {
  if (!isObject(v) || v.run_id !== e.run_id || v.receipt_sha256 !== e.receipt_sha256 || v.report_sha256 !== e.report_sha256) invalidBacktest()
  return v
}
/** 每个固定报告只读取一次；光标移动完全使用本地已核摘要。 */
export async function fetchDaySummaries(entry: ArchiveEntry, signal?: AbortSignal): Promise<DaySummaries> {
  const value = identity(await fetchBacktestReadJson<unknown>(`/v1/ui/backtest/archive/${entry.run_id}/day-summaries?receipt_sha256=${entry.receipt_sha256}`, '日期摘要', signal), entry)
  boundedBacktestTree(value)
  keys(value, 'schema run_id receipt_sha256 report_sha256 points')
  if (value.schema !== 'nbw-day-summaries-v1' || !Array.isArray(value.points) || value.points.length !== entry.record_count) invalidBacktest()
  let previous = 0
  for (const row of value.points) {
    if (!Array.isArray(row) || row.length !== 5 || !tradingDate(row[0]) || row[0] <= previous || row[4] !== null && !count(row[4])) invalidBacktest()
    previous = row[0]
    for (const values of row.slice(1, 4)) {
      if (values === null) continue
      if (!Array.isArray(values) || values.length > 4096) invalidBacktest()
      const symbols = new Set<string>()
      for (const pair of values) {
        if (!Array.isArray(pair) || pair.length !== 2 || !text(pair[0]) || !decimal(pair[1]) || symbols.has(pair[0])) invalidBacktest()
        symbols.add(pair[0])
      }
    }
    if ((row[2] === null) !== (row[3] === null) || (row[2] === null) !== (row[4] === null)) invalidBacktest()
  }
  return value as DaySummaries
}
/** 使用既有31秒HTTP预算；响应绑定完成收据，不触发回测或交易。 */
export async function fetchVisuals(entry: ArchiveEntry, signal?: AbortSignal): Promise<Visuals> {
  const v = identity(await fetchBacktestReadJson<unknown>(`/v1/ui/backtest/archive/${entry.run_id}/visuals?receipt_sha256=${entry.receipt_sha256}`, '回测图表', signal), entry)
  boundedBacktestTree(v)
  keys(v, 'schema run_id receipt_sha256 report_sha256 trades_available points' + (Object.hasOwn(v, 'position_points') ? ' position_points' : ''))
  if (v.schema !== 'nbw-visuals-v1' || typeof v.trades_available !== 'boolean' || !Array.isArray(v.points) || v.points.length !== entry.record_count) invalidBacktest()
  let previous = 0
  for (const row of v.points) {
    if (!Array.isArray(row) || row.length !== 6 || !tradingDate(row[0]) || row[0] <= previous || !nullableNumber(row[1]) || !nullableNumber(row[2]) || row.slice(3).some(n => !count(n))) invalidBacktest()
    previous = row[0]
  }
  const positions = v.position_points
  if (positions !== undefined) {
    if (!Array.isArray(positions) || positions.length !== v.points.length) invalidBacktest()
    for (const [index, point] of positions.entries()) {
      if (!Array.isArray(point) || point.length !== 4 || point[0] !== v.points[index][0]) invalidBacktest()
      const [, ratio, market, cash] = point
      if (ratio === null ? market !== null || cash !== null
        : !nullableNumber(ratio) || ratio < 0 || !decimal(market) || market.startsWith('-') || !decimal(cash)) invalidBacktest()
    }
  }
  return v as Visuals
}
/** 指定日期查询日末持仓和当日交易；null查询全体成交分页。 */
export async function fetchLedger(entry: ArchiveEntry, day: number | null, offset: number, signal?: AbortSignal): Promise<Ledger> {
  if (day !== null && !tradingDate(day) || !count(offset)) invalidBacktest()
  const query = new URLSearchParams({ receipt_sha256: entry.receipt_sha256, offset: String(offset) })
  if (day !== null) query.set('day', String(day))
  const v = identity(await fetchBacktestReadJson<unknown>(`/v1/ui/backtest/archive/${entry.run_id}/ledger?${query}`, '持仓与交易', signal), entry)
  boundedBacktestTree(v)
  keys(v, 'schema run_id receipt_sha256 report_sha256 date positions_available positions trades_available total offset trades')
  if (v.schema !== 'nbw-ledger-v1' || v.date !== day || v.offset !== offset || !count(v.total) || typeof v.positions_available !== 'boolean' || typeof v.trades_available !== 'boolean'
    || !Array.isArray(v.positions) || v.positions.length > 4096 || !Array.isArray(v.trades) || v.trades.length > 50 || v.trades.length !== Math.min(50, Math.max(0, Number(v.total) - offset))) invalidBacktest()
  for (const p of v.positions) {
    if (!isObject(p) || p.date !== day || !text(p.symbol) || !decimal(p.quantity) || !decimal(p.realized_cny) || !decimal(p.floating_cny)) invalidBacktest()
    keys(p, 'date symbol quantity realized_cny floating_cny')
  }
  let previous = -1
  for (const t of v.trades) {
    if (!isObject(t) || !count(t.index) || Number(t.index) <= previous || !tradingDate(t.date) || day !== null && t.date !== day || !text(t.time) || !/^\d{12}$/.test(t.time) || Number(t.time.slice(0, 8)) !== t.date
      || !text(t.symbol) || !['buy', 'sell', 'unknown'].includes(String(t.side)) || !text(t.direction) || !text(t.action) || !decimal(t.price) || !decimal(t.quantity) || !decimal(t.fee_cny)) invalidBacktest()
    keys(t, 'index date time symbol side direction action price quantity fee_cny'); previous = Number(t.index)
  }
  return v as Ledger
}
