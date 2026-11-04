import { fetchReadJson } from '../api'
import { validateCapitalFields, type CapitalFields } from './strategyCapital'

export const runtimeLabels = {
  initializing: '正在准备目标', selling: '正在调整卖出目标', buying: '正在调整买入目标',
  converged: '理论持仓已达到本阶段目标', waiting_basis: '等待完整资金与价格',
  waiting_sellable: '等待持仓可卖', waiting_pending: '等待原生未决目标处理',
  waiting_cash: '等待可用资金', waiting_fee: '等待费用信息',
  supersession_required: '等待原目标处理完成', blocked: '本轮目标暂未执行',
  waiting_broker_position: '等待更新券商持仓', waiting_actual_cycle: '等待确认实际开仓信息',
  waiting_market_input: '等待策略所需行情',
  observing: '分析运行中', // WT只读模式持续计算，不调用目标提交；与后端公开状态同步。
} as const
export type RuntimePosition = { symbol: string; target_weight: number | null; theoretical_quantity: number | null;
  theoretical_sellable: number | null; pending_target: number | null; stage_target: number | null;
  broker_quantity: number | null; broker_sellable: number | null }
export type StrategyRuntime = { schema_version: 'guanheng.strategy-runtime.v1'; read_only: true; observed_at: string;
  runtime_state?: string;
  execution_state?: 'not_started';
  state: 'unconfigured' | 'waiting' | 'available'; strategy: null | (CapitalFields & {
    /** WT发布的策略身份；旧App回包可缺失。 */ strategy_id?: string;
    display_name: string; /** WT原版本；null表示尚未发布。 */ strategy_version: string | null; status: keyof typeof runtimeLabels; status_label: string;
    decision_at: string | null; broker_observed_at: string | null; broker_position_qualified: false;
    execution_position_qualified?: boolean; positions: RuntimePosition[] }) }
const record = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === 'object' && !Array.isArray(v)
const time = (v: unknown) => typeof v === 'string' && v.length <= 64 && /(Z|[+-]\d{2}:\d{2})$/.test(v) && Number.isFinite(Date.parse(v))
const quantity = (v: unknown) => v === null || typeof v === 'number' && Number.isSafeInteger(v) && v >= 0

export function strategyRuntimeLabel(strategy: NonNullable<StrategyRuntime['strategy']>) {
  return strategy.status === 'converged'
    ? strategy.execution_position_qualified === true ? '本轮调仓已完成' : '本阶段策略计算已完成'
    : runtimeLabels[strategy.status]
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
    || !Array.isArray(s.positions) || s.positions.length > 8) return invalid()
  const seen = new Set<string>()
  for (const row of s.positions) {
    if (!record(row) || typeof row.symbol !== 'string' || !/^\d{6}\.(SH|SZ)$/.test(row.symbol) || seen.has(row.symbol)
      || !['theoretical_quantity', 'theoretical_sellable', 'pending_target', 'stage_target', 'broker_quantity', 'broker_sellable'].every(k => quantity(row[k]))
      || !(row.target_weight === null || typeof row.target_weight === 'number' && Number.isFinite(row.target_weight) && row.target_weight >= 0 && row.target_weight <= 1)
      || typeof row.theoretical_sellable === 'number' && (typeof row.theoretical_quantity !== 'number' || row.theoretical_sellable > row.theoretical_quantity)
      || typeof row.broker_sellable === 'number' && (typeof row.broker_quantity !== 'number' || row.broker_sellable > row.broker_quantity)) return invalid()
    seen.add(row.symbol)
  }
  validateCapitalFields(s)
  return data as StrategyRuntime
}

export async function fetchStrategyRuntime(signal: AbortSignal): Promise<StrategyRuntime> {
  return validateStrategyRuntime(await fetchReadJson<unknown>('/v1/ui/strategy-runtime', '策略运行结果', signal, 'status'))
}
