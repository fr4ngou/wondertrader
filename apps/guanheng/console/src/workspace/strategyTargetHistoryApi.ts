import { useQuery } from '@tanstack/react-query'
import { fetchReadJson } from '../api'
import { strategyKey } from './StrategyPicker'
import type { StrategyDefinition } from './strategyCatalogApi'

export type TargetHistoryItem = {
  /** 原文件身份及原行的稳定摘要。 */ id: string
  /** 原生CSV行序，从1起。 */ sequence: number
  /** WT行情时刻，上海时区ISO。 */ changed_at: string
  /** 原生证券代码，含历史已退出的证券。 */ symbol: string
  /** 同证券上次目标份数；首观测未知。 */ previous_target_quantity: number | null
  /** 本次设置的目标份数，区别券商实际持仓。 */ target_quantity: number
  /** 前后目标份数之差；首观测为空。 */ change_quantity: number | null
  /** 首观测或有前值依据的目标改变。 */ kind: 'initial' | 'changed'
  /** 原信号参考价，人民币元/份，区别实际成交。 */ reference_price_cny: string
  /** 原日志未记录目标权重。 */ target_weight: null
  /** 原日志未记录历史算法版本。 */ strategy_version: null
  /** 原日志未记录逐笔业务原因。 */ reason: null
}
export type TargetHistory = {
  /** 只读原生目标历史协议。 */ schema_version: 'guanheng.strategy-target-history.v1'
  /** 没有修改目标或交易副作用。 */ read_only: true
  /** App读取时刻，区别WT信号时刻。 */ observed_at: string
  /** 已读取、缺来源及非当前选择。 */ state: 'available' | 'waiting' | 'not_current'
  /** 原生来源与缺失说明。 */ reason: string
  /** 本次请求的精确策略身份。 */ requested: { strategy_id: string; strategy_version: string }
  /** 此原生文件固定前缀的覆盖和分流计数；无源时为空。 */ source: null | {
    /** 唯一来源类别。 */ kind: 'wt-native-signals'
    /** 原生物理文件及逻辑实例身份摘要。 */ source_id: string
    /** 完整固定前缀SHA，跨页保持一致。 */ snapshot_sha256: string
    /** 完整原始设置行数。 */ raw_count: number
    /** 有前值的真实目标变化数。 */ changed_count: number
    /** 各证券首次可见记录数。 */ initial_count: number
    /** 相邻同目标重复设置数。 */ unchanged_count: number
    /** 原生末行尚未写完，下次刷新再纳入。 */ incomplete_tail: boolean
    /** 首个原生行情时刻；无行时为空。 */ first_at: string | null
    /** 最后原生行情时刻；无行时为空。 */ last_at: string | null
    /** 当前标的在此固定前缀中的最近变动或首次记录；旧服务可能缺失。 */ latest_targets?: TargetHistoryItem[]
  }
  /** 当前页倒序的变动及首次记录。 */ items: TargetHistoryItem[]
  /** 同一前缀下一页的不透明游标。 */ next_cursor: string | null
}
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const integer = (v: unknown): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v >= 0
const hash = (v: unknown) => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v)
const time = (v: unknown) => typeof v === 'string' && /(Z|[+-]\d{2}:\d{2})$/.test(v) && Number.isFinite(Date.parse(v))

export function validateTargetHistory(value: unknown, strategy: Pick<StrategyDefinition, 'strategy_id' | 'strategy_version'>): TargetHistory {
  const invalid = () => { throw new Error('目标仓位记录格式或策略身份无效，请重新读取') }
  if (!object(value) || value.schema_version !== 'guanheng.strategy-target-history.v1' || value.read_only !== true
    || !time(value.observed_at) || !['available', 'waiting', 'not_current'].includes(String(value.state))
    || typeof value.reason !== 'string' || value.reason.length > 1000 || !object(value.requested)
    || value.requested.strategy_id !== strategy.strategy_id || value.requested.strategy_version !== strategy.strategy_version
    || !Array.isArray(value.items) || value.items.length > 100
    || !(value.next_cursor === null || typeof value.next_cursor === 'string' && /^[A-Za-z0-9_-]{1,512}$/.test(value.next_cursor))) return invalid()
  const s = value.source
  if (s !== null && (!object(s) || s.kind !== 'wt-native-signals' || !hash(s.source_id) || !hash(s.snapshot_sha256)
    || ![s.raw_count, s.changed_count, s.initial_count, s.unchanged_count].every(integer)
    || Number(s.raw_count) !== Number(s.changed_count)+Number(s.initial_count)+Number(s.unchanged_count)
    || typeof s.incomplete_tail !== 'boolean' || ![s.first_at, s.last_at].every(v => v === null || time(v)))) return invalid()
  if (value.state !== 'available' && (s !== null || value.items.length || value.next_cursor !== null)) return invalid()
  if (value.state === 'available' && s === null) return invalid()
  if (!validHistoryItems(value.items)) return invalid()
  if (object(s) && s.latest_targets !== undefined && (!Array.isArray(s.latest_targets) || s.latest_targets.length > 64
    || !validHistoryItems(s.latest_targets) || new Set(s.latest_targets.map(row => row.symbol)).size !== s.latest_targets.length)) return invalid()
  return value as TargetHistory
}

function validHistoryItems(items: unknown[]): items is TargetHistoryItem[] {
  let previousSequence = Infinity
  const identities = new Set<string>()
  for (const item of items) {
    if (!object(item) || !hash(item.id) || !integer(item.sequence) || item.sequence === 0 || item.sequence >= previousSequence
      || !time(item.changed_at) || typeof item.symbol !== 'string' || !/^\d{6}\.(SH|SZ)$/.test(item.symbol)
      || !integer(item.target_quantity) || !(item.previous_target_quantity === null || integer(item.previous_target_quantity))
      || !['initial','changed'].includes(String(item.kind)) || (item.kind === 'initial') !== (item.previous_target_quantity === null)
      || item.change_quantity !== (item.previous_target_quantity === null ? null : item.target_quantity-Number(item.previous_target_quantity))
      || item.kind === 'changed' && item.change_quantity === 0
      || typeof item.reference_price_cny !== 'string' || item.reference_price_cny.length > 128 || !/^\d+(\.\d+)?$/.test(item.reference_price_cny)
      || !Number.isFinite(Number(item.reference_price_cny)) || item.target_weight !== null || item.strategy_version !== null || item.reason !== null
      || identities.has(String(item.id))) return false
    previousSequence = item.sequence; identities.add(String(item.id))
  }
  return true
}

export function useStrategyTargetHistory(strategy: Pick<StrategyDefinition, 'strategy_id' | 'strategy_version'>, cursor: string | null) {
  return useQuery({ queryKey: ['strategy-target-history', strategyKey(strategy), cursor], retry: false,
    queryFn: async ({signal}) => {
      const params = new URLSearchParams({strategy_id: strategy.strategy_id, strategy_version: strategy.strategy_version ?? '', limit:'20'})
      if (cursor) params.set('cursor', cursor)
      return validateTargetHistory(await fetchReadJson<unknown>('/v1/ui/strategy-target-history?'+params, '目标仓位记录', signal, 'workspace', 4000), strategy)
    }, enabled: strategy.strategy_version !== null, refetchInterval: cursor ? false : 15_000,
    refetchOnWindowFocus: false, refetchOnReconnect: false })
}
