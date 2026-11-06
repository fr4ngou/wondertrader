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
  /** 仅按账户证券范围筛选，尚无策略归属证据。 */ attribution: 'account-universe-only'
}
export type LiveDay = {
  /** 真实来源日期，缺日不补行。 */ date: string
  /** 原净值估值时间；仅成交日可空。 */ observed_at: string | null
  /** 原策略净值，元；缺少时为空。 */ nav_cny: string | null
  /** 原发布现金，元。 */ cash_cny: string | null
  /** 原发布市值，元。 */ market_value_cny: string | null
  /** 原资本变化，元；不推断投资收益。 */ pnl_cny: string | null
  /** 投资收益口径尚缺，保持空。 */ return_pct: null
  /** 当日实际观察持仓。 */ positions: LivePosition[]
  /** 当日实际账户证券范围成交。 */ deals: LiveDeal[]
  /** 区分完整空持仓和未知。 */ positions_state: 'available' | 'empty' | 'unavailable'
  /** 区分完整空成交、部分和未知。 */ deals_state: 'available' | 'empty' | 'partial' | 'unavailable'
}
export type LivePerformance = {
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
    /** 首个实际净值日期。 */ from: string | null
    /** 最后实际净值日期。 */ to: string | null
    /** 实际净值点数，区别成交日期数。 */ point_count: number
    /** 明确真实观察口径。 */ basis: 'actual-published-observations'
    /** 观察积累方式。 */ history_state: string
    /** 未覆盖历史和收益归因说明。 */ reason: string
    /** 仅当前有界展示截断，历史原件继续保存。 */ deals_truncated: boolean
    /** 通过原现金原点和基准核实的稳定历史归属；缺证据时按运行代隔离。 */ history_scope_id?: string | null
  }
  /** WT原本金基准，缺少时为空。 */ baseline: { total_cny: string; baseline_at: string; scope_id: string } | null
  /** 当前资本原发布；收益率保持未知。 */ summary: {
    /** 实际策略净值，元。 */ nav_cny: string
    /** 原基准变化，元。 */ pnl_cny: string
    /** 未授投资收益归因。 */ return_pct: null
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
  const current = value.current
  if (current.is_current && (!current.key_matches || current.strategy_id !== id || current.strategy_version !== version || current.process_state !== 'alive')) return invalid()
  if (value.state === 'not_current' && (value.summary !== null || value.baseline !== null || value.daily.length || value.markers.length || current.is_current)) return invalid()
  if (value.summary !== null && (!object(value.summary) || !money(value.summary.nav_cny) || !money(value.summary.pnl_cny)
    || value.summary.return_pct !== null || !text(value.summary.return_reason))) return invalid()
  if (value.baseline !== null && (!object(value.baseline) || !money(value.baseline.total_cny) || !text(value.baseline.baseline_at))) return invalid()
  const deal = (d: unknown) => object(d) && text(d.id) && date(d.date) && text(d.time) && text(d.symbol)
    && ['BUY', 'SELL', 'UNKNOWN'].includes(String(d.side)) && money(d.price_cny) && count(d.quantity) && d.attribution === 'account-universe-only'
  let last = ''
  for (const d of value.daily) {
    if (!object(d) || !date(d.date) || String(d.date) <= last || !Array.isArray(d.positions) || !Array.isArray(d.deals)
      || !['available', 'empty', 'unavailable'].includes(String(d.positions_state)) || !['available', 'empty', 'partial', 'unavailable'].includes(String(d.deals_state))
      || ![d.nav_cny, d.cash_cny, d.market_value_cny, d.pnl_cny].every(m => m === null || money(m)) || d.return_pct !== null
      || d.positions.some(p => !object(p) || !text(p.symbol) || !count(p.quantity) || !count(p.sellable) || !text(p.observed_at))
      || d.deals.some(t => !deal(t) || !money(t.amount_cny))) return invalid()
    last = String(d.date)
  }
  if (value.markers.some(d => !deal(d))) return invalid()
  const points = value.daily.filter(d => d.nav_cny !== null)
  if (value.coverage.point_count !== points.length || value.coverage.from !== (points[0]?.date ?? null)
    || value.coverage.to !== (points.at(-1)?.date ?? null)) return invalid()
  return value as LivePerformance
}

export function useLiveStrategyPerformance(strategy: StrategyDefinition | undefined) {
  const id = strategy?.strategy_id ?? ''; const version = strategy?.strategy_version ?? ''
  return useQuery({ queryKey: ['live-strategy-performance', id, version], enabled: !!id && !!version,
    queryFn: async ({ signal }) => validateLivePerformance(await fetchReadJson<unknown>('/v1/ui/live-strategy-performance?' + new URLSearchParams({ strategy_id: id, strategy_version: version, limit: '90' }), '线上策略观察', signal, 'workspace', 4000), id, version),
    retry: false, refetchInterval: 30_000, refetchIntervalInBackground: true, refetchOnWindowFocus: false, refetchOnReconnect: false })
}
