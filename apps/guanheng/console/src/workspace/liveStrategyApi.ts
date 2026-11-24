import { useQuery } from '@tanstack/react-query'
import { fetchReadJson } from '../api'
import type { StrategyDefinition } from './strategyCatalogApi'

export type LivePosition = {
  /** 原券商证券身份。 */ symbol: string
  /** 原发布持仓数量，份。 */ quantity: number
  /** 同次发布可卖份额。 */ sellable: number
  /** 持仓原接收时间。 */ observed_at: string
}
export type LiveDeal = {
  /** 去敏后的来源成交身份。 */ id: string
  /** 实际来源成交日。 */ date: string
  /** 上海时间。 */ time: string
  /** 原证券代码。 */ symbol: string
  /** 原方向，未知方向保留。 */ side: 'BUY' | 'SELL' | 'UNKNOWN'
  /** 实际成交单价，元。 */ price_cny: string
  /** 实际成交份额。 */ quantity: number
  /** 原成交金额，元。 */ amount_cny: string
  /** 原ASA分配费用，元；未知为null，旧账户投影可缺。 */ fee_cny?: string | null
  /** 仅按账户证券范围筛选，尚无策略归属证据。 */ attribution: 'account-universe-only' | 'strategy-allocated'
}
export type LiveDay = {
  /** 真实来源日期，缺日不补行。 */ date: string
  /** 原净值估值时间；仅成交日可空。 */ observed_at: string | null
  /** 原策略净值，元；缺少时为空。 */ nav_cny: string | null
  /** 原owner未扣未知费用的参考净值，元。 */ reference_nav_cny?: string | null
  /** 参考现金原owner时刻，与实际现金后继观察分别保留。 */ reference_cash_observed_at?: string | null
  /** 只扣已知费用的ledger参考现金，元。 */ reference_cash_cny?: string | null
  /** 参考估值原时刻，缺省兼容旧发布。 */ reference_observed_at?: string | null
  /** 本日最后合格估值资格。 */ valuation_state?: 'actual' | 'reference-fee-pending'
  /** 此估值采用QMT暂记费用的笔数。 */ provisional_fee_count?: number
  /** 原配置资本参考变化额，不当投资损益。 */ reference_change_cny?: string | null
  /** 相对配置资本参考率%，不当投资收益。 */ reference_return_pct?: string | null
  /** 原配置资本，元。 */ valuation_baseline_cny?: string | null
  /** 原发布现金，元。 */ cash_cny: string | null
  /** ASA现金原观察时刻，与NAV时刻独立；旧响应可缺。 */ cash_observed_at?: string
  /** 现金观察对应运行scope，与NAV分别保留。 */ cash_runtime_scope_id?: string
  /** 原发布市值，元。 */ market_value_cny: string | null
  /** 原资本变化，元；不推断投资收益。 */ pnl_cny: string | null
  /** 投资收益口径尚缺，保持空。 */ return_pct: null
  /** 当日实际观察持仓。 */ positions: LivePosition[]
  /** 当日持仓原观察时间，独立于估值。旧响应可沿明细时间。 */ positions_observed_at?: string
  /** 当日实际账户证券范围成交。 */ deals: LiveDeal[]
  /** 区分完整空持仓和未知。 */ positions_state: 'available' | 'empty' | 'unavailable'
  /** 区分完整空成交、部分和未知。 */ deals_state: 'available' | 'empty' | 'partial' | 'unavailable'
}
type CapitalReturn = {
  /** WT原资金基准时刻，带时区。 */ baseline_at: string
  /** 本次实际净值截止，带时区。 */ valued_at: string
  /** 本次收益使用的实际期末净值，元。 */ valuation_nav_cny: string
  /** 本次收益使用的实际现金快照时间。 */ cash_observed_at: string
  /** 流水必须覆盖到的现金和估值较晚时点。 */ coverage_required_at: string
  /** 流入覆盖原时刻，未知为空。 */ inflow_through: string | null
  /** 流出覆盖原时刻，未知为空。 */ outflow_through: string | null
  /** 本次收益期有效事件总数。 */ flow_count: number
  /** 最近最多20条公开资金事件。 */ flows: {
    /** 按策略经济身份生成的事件摘要。 */ id: string
    /** 实际注资或提取。 */ direction: 'inflow' | 'outflow'
    /** 实际人民币金额，正十进制字符串。 */ amount_cny: string
    /** 原资金生效时刻，带时区。 */ effective_at: string
  }[]
  /** 已算出或等待资金覆盖、估值、基准及记录。 */ state: string
  /** WT实际计算的收益率，单位%，未知为空。 */ return_pct: string | null
  /** WT发布的收益说明。 */ reason: string
}

export type LivePerformance = {
  /** 已准入证券目录按本窗口出现的代码投影；旧 App 或缺项时显示代码。 */ security_names?: Record<string, string>
  /** 只读观察协议。 */ schema_version: 'guanheng.live-strategy-performance.v1'
  /** 本接口不授交易权限。 */ read_only: true
  /** 本轮App读取时间。 */ observed_at: string
  /** 当前选择的读取状态。 */ state: 'available' | 'waiting' | 'not_current'
  /** 来源及归属说明。 */ reason: string
  /** 本次请求的精确策略身份。 */ requested: { strategy_id: string; strategy_version: string }
  /** 原运行身份及实际进程核查；不从回测推断在线。 */ current: {
    /** 实际发布或当前选择的ID。 */ strategy_id: string
    /** 对应版本。 */ strategy_version: string
    /** 两字段均匹配。 */ key_matches: boolean
    /** 原运行状态。 */ runtime_state: string | null
    /** 同身份、组件和实际进程均确认后才为真。 */ is_current: boolean
    /** 完整运行与基准身份摘要。 */ scope_id: string | null
    /** 原进程实存核查。 */ process_state: 'alive' | 'exited' | 'unknown'
  }
  /** 净值实际覆盖，不表示交易日连续。 */ coverage: {
    /** 本窗口参考点数，旧发布可缺。 */ reference_point_count?: number
    /** 本轮估值资格，历史最近点仍保留原资格。 */ valuation_state?: string | null
    /** 本轮缺失/等待固定原因。 */ valuation_reason?: string | null
    /** 参考首日，无点为空。 */ reference_from?: string | null
    /** 参考最后日，无点为空。 */ reference_to?: string | null
    /** 首个实际净值日期。 */ from: string | null
    /** 最后实际净值日期。 */ to: string | null
    /** 实际净值点数，区别成交日期数。 */ point_count: number
    /** 明确真实观察口径。 */ basis: 'actual-published-observations'
    /** 观察积累方式。 */ history_state: string
    /** 未覆盖历史和收益归因说明。 */ reason: string
    /** 仅当前有界展示截断，历史原件继续保存。 */ deals_truncated: boolean
    /** 持仓/成交归属；旧发布缺失按账户范围显示。 */ attribution?: 'strategy-allocated' | 'account-universe-only'
    /** 通过原现金原点和基准核实的稳定历史归属；缺证据时按运行代隔离。 */ history_scope_id?: string | null
  }
  /** WT原本金基准，缺少时为空。 */ baseline: { total_cny: string; baseline_at: string; scope_id: string } | null
  /** 当前资本和同一估值时点的收益原发布。 */ summary: {
    /** 未扣未知费用的参考净值，元。 */ reference_nav_cny?: string | null
    /** 原估值资格，旧发布可缺。 */ valuation_state?: 'actual' | 'reference-fee-pending' | null
    /** 原估值的暂记费用笔数，最终结算另行核实。 */ provisional_fee_count?: number
    /** 配置资本参考变化额，元。 */ reference_change_cny?: string | null
    /** 配置资本参考率%，不代表投资收益。 */ reference_return_pct?: string | null
    /** 原配置资本，元。 */ baseline_cny?: string | null
    /** 实际策略净值，元；参考资格时为空。 */ nav_cny: string | null
    /** 原基准变化，元；ASA缺投资损益资格时为空。 */ pnl_cny: string | null
    /** WT资金流调整后的实际收益率，单位%；未知为空。 */ return_pct: string | null
    /** WT资金流观察与累计收益，旧发布可缺。 */ capital_return?: CapitalReturn
    /** 净值来源时间。 */ observed_at: string
    /** 原报价时刻，缺少时不改称实时价格。 */ price_observed_at: string | null
    /** 原损益来源。 */ pnl_source: string
    /** 收益率缺失说明。 */ return_reason: string
  } | null
  /** 按来源日期升序，无人工补值。 */ daily: LiveDay[]
  /** 实际成交标记，账户范围口径。 */ markers: Omit<LiveDeal, 'amount_cny'>[]
}

const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const text = (v: unknown) => typeof v === 'string' && v.length > 0 && v.length <= 4096
const money = (v: unknown) => typeof v === 'string' && v.length <= 128 && /^-?\d+(?:\.\d+)?$/.test(v) && Number.isFinite(Number(v))
const date = (v: unknown) => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v)
const count = (v: unknown) => Number.isSafeInteger(v) && Number(v) >= 0
const stamp = (v: unknown) => typeof v === 'string' && /(Z|[+-]\d{2}:\d{2})$/.test(v) && Number.isFinite(Date.parse(v))
const invalid = (): never => { throw new Error('线上策略观察格式无效，请重新读取') }

/** 核精确选择和金融字段，避免切换策略后展示上一策略的缓存。 */
export function validateLivePerformance(value: unknown, id: string, version: string): LivePerformance {
  if (!object(value) || value.schema_version !== 'guanheng.live-strategy-performance.v1' || value.read_only !== true
    || !text(value.observed_at) || !['available', 'waiting', 'not_current'].includes(String(value.state)) || !text(value.reason)
    || !object(value.requested) || value.requested.strategy_id !== id || value.requested.strategy_version !== version
    || !object(value.current) || typeof value.current.is_current !== 'boolean' || typeof value.current.key_matches !== 'boolean'
    || !['alive', 'exited', 'unknown'].includes(String(value.current.process_state))
    || !object(value.coverage) || value.coverage.basis !== 'actual-published-observations' || !count(value.coverage.point_count)
    || !(value.coverage.from === null || date(value.coverage.from)) || !(value.coverage.to === null || date(value.coverage.to))
    || !text(value.coverage.reason) || typeof value.coverage.deals_truncated !== 'boolean'
    || !Array.isArray(value.daily) || value.daily.length > 366 || !Array.isArray(value.markers) || value.markers.length > 2000) return invalid()
  if (value.coverage.attribution !== undefined && !['account-universe-only','strategy-allocated'].includes(String(value.coverage.attribution))) return invalid()
  if (value.security_names !== undefined && (!object(value.security_names) || Object.entries(value.security_names).some(([symbol, name]) => !text(symbol) || !text(name)))) return invalid()
  const current = value.current
  if (current.is_current && (!current.key_matches || current.strategy_id !== id || current.strategy_version !== version || current.process_state !== 'alive')) return invalid()
  if (value.state === 'not_current' && (value.summary !== null || value.baseline !== null || value.daily.length || value.markers.length || current.is_current)) return invalid()
  if (value.summary !== null && (!object(value.summary) || !(money(value.summary.nav_cny) || value.summary.nav_cny === null && value.summary.valuation_state === 'reference-fee-pending' && money(value.summary.reference_nav_cny)) || !(money(value.summary.pnl_cny) || value.summary.pnl_cny === null && ['actual','reference-fee-pending'].includes(String(value.summary.valuation_state)))
    || !(value.summary.return_pct === null || money(value.summary.return_pct)) || !text(value.summary.return_reason))) return invalid()
  if (object(value.summary)) {
    const s=value.summary
    if (['reference_nav_cny','reference_change_cny','reference_return_pct','baseline_cny'].some(k=>s[k]!==undefined&&s[k]!==null&&!money(s[k]))) return invalid()
    if (s.valuation_state !== undefined && s.valuation_state !== null && !['actual','reference-fee-pending'].includes(String(s.valuation_state))) return invalid()
    if (s.valuation_state === 'reference-fee-pending' && (s.nav_cny !== null || !money(s.reference_nav_cny))) return invalid()
    if (s.valuation_state === 'actual' && (!money(s.nav_cny) || s.reference_nav_cny != null)) return invalid()
    if (s.provisional_fee_count !== undefined && !count(s.provisional_fee_count)) return invalid()
    const result = s.capital_return
    if (result === undefined) {
      if (s.return_pct !== null) return invalid()
    } else {
      if (!object(result) || !stamp(result.baseline_at) || !stamp(result.valued_at) || !stamp(s.observed_at)
        || !money(result.valuation_nav_cny) || !stamp(result.cash_observed_at) || !stamp(result.coverage_required_at)
        || Date.parse(String(result.coverage_required_at)) !== Math.max(Date.parse(String(result.valued_at)), Date.parse(String(result.cash_observed_at)))
        || Date.parse(String(result.valued_at)) > Date.parse(String(s.observed_at)) || result.return_pct !== s.return_pct
        || !text(result.reason) || !count(result.flow_count) || !Array.isArray(result.flows)
        || result.flows.length > 20 || result.flows.length > Number(result.flow_count)
        || ![result.inflow_through, result.outflow_through].every(v => v === null || stamp(v))
        || !['available','coverage_pending','valuation_pending','reconciliation_pending','basis_pending','record_unavailable'].includes(String(result.state))
        || (result.state === 'available') !== (s.return_pct !== null)
        || (s.return_pct !== null && (!money(s.nav_cny) || Number(s.return_pct) < -100
          || ![result.inflow_through, result.outflow_through].every(v => stamp(v) && Date.parse(String(v)) >= Date.parse(String(result.coverage_required_at)))))
        || result.flows.some(flow => !object(flow) || typeof flow.id !== 'string' || !/^[a-f0-9]{64}$/.test(flow.id)
          || !['inflow','outflow'].includes(String(flow.direction)) || !money(flow.amount_cny) || Number(flow.amount_cny) <= 0
          || !stamp(flow.effective_at))) return invalid()
    }
  }
  if (value.baseline !== null && (!object(value.baseline) || !money(value.baseline.total_cny) || !text(value.baseline.baseline_at))) return invalid()
  const deal = (d: unknown) => object(d) && text(d.id) && date(d.date) && text(d.time) && text(d.symbol)
    && ['BUY', 'SELL', 'UNKNOWN'].includes(String(d.side)) && money(d.price_cny) && count(d.quantity) && ['account-universe-only','strategy-allocated'].includes(String(d.attribution))
  let last = ''
  for (const d of value.daily) {
    if (!object(d) || !date(d.date) || String(d.date) <= last || !Array.isArray(d.positions) || !Array.isArray(d.deals)
      || !['available', 'empty', 'unavailable'].includes(String(d.positions_state)) || !['available', 'empty', 'partial', 'unavailable'].includes(String(d.deals_state))
      || ![d.nav_cny, d.cash_cny, d.market_value_cny, d.pnl_cny].every(m => m === null || money(m)) || d.return_pct !== null
      || d.positions.some(p => !object(p) || !text(p.symbol) || !count(p.quantity) || !count(p.sellable) || !text(p.observed_at))
      || d.positions_observed_at !== undefined && (!text(d.positions_observed_at) || !Number.isFinite(Date.parse(String(d.positions_observed_at))))
      || ['reference_nav_cny','reference_cash_cny','reference_change_cny','reference_return_pct','valuation_baseline_cny'].some(k => d[k] !== undefined && d[k] !== null && !money(d[k]))
      || d.valuation_state !== undefined && !['actual','reference-fee-pending'].includes(String(d.valuation_state))
      || d.provisional_fee_count !== undefined && !count(d.provisional_fee_count)
      || d.cash_observed_at !== undefined && (!text(d.cash_observed_at) || !Number.isFinite(Date.parse(String(d.cash_observed_at))))
      || d.cash_runtime_scope_id !== undefined && (typeof d.cash_runtime_scope_id !== 'string' || !/^[a-f0-9]{64}$/.test(d.cash_runtime_scope_id))
      || d.deals.some(t => !deal(t) || !money(t.amount_cny) || t.fee_cny !== undefined && t.fee_cny !== null && !money(t.fee_cny))) return invalid()
    if (d.valuation_state === 'reference-fee-pending' && (d.nav_cny !== null || !money(d.reference_nav_cny) || !text(d.reference_observed_at))) return invalid()
    if (d.valuation_state === 'actual' && (!money(d.nav_cny) || d.reference_nav_cny != null)) return invalid()
    last = String(d.date)
  }
  if (value.markers.some(d => !deal(d))) return invalid()
  const points = value.daily.filter(d => d.nav_cny !== null)
  if (value.coverage.point_count !== points.length || value.coverage.from !== (points[0]?.date ?? null)
    || value.coverage.to !== (points.at(-1)?.date ?? null)) return invalid()
  const references = value.daily.filter(d => d.reference_nav_cny != null)
  if (value.coverage.reference_point_count !== undefined && value.coverage.reference_point_count !== references.length) return invalid()
  return value as LivePerformance
}

export function useLiveStrategyPerformance(strategy: StrategyDefinition | undefined) {
  const id = strategy?.strategy_id ?? ''; const version = strategy?.strategy_version ?? ''
  return useQuery({ queryKey: ['live-strategy-performance', id, version], enabled: !!id && !!version,
    queryFn: async ({ signal }) => validateLivePerformance(await fetchReadJson<unknown>('/v1/ui/live-strategy-performance?' + new URLSearchParams({ strategy_id: id, strategy_version: version, limit: '90' }), '线上策略观察', signal, 'workspace', 4000), id, version),
    retry: false, refetchInterval: 30_000, refetchIntervalInBackground: true, refetchOnWindowFocus: false, refetchOnReconnect: false })
}
