import { fetchReadJson } from '../api'

export type StrategyDefinition = {
  /** WT活动结果或已保存报告的策略身份。 */ strategy_id: string
  /** 同一来源实际发布的版本；null表示尚未发布。 */ strategy_version: string | null
  /** 稳定中文展示名称，不代表运行或执行资格。 */ display_name: string
  /** 稳定业务说明；历史报告可用其保存身份补充。 */ description: string
  /** 来源明确提供的历史版本；当前未提供时为空数组。 */ historical_versions: string[]
}
function text(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0 && Array.from(value).length <= 256
    && !/[\u0000-\u001f\u007f]/.test(value)
    && !Array.from(value).some(point => point.length === 1 && /[\ud800-\udfff]/.test(point))
}

export async function fetchStrategyCatalog(signal: AbortSignal): Promise<StrategyDefinition[]> {
  const value = await fetchReadJson<unknown>('/v1/ui/strategy-catalog', '策略目录', signal)
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('策略目录格式无效，请重新读取')
  const data = value as Record<string, unknown>
  if (data.schema !== 'guanheng.strategy-catalog.v1' || data.read_only !== true || data.scope !== 'registered-definitions'
    || !Array.isArray(data.strategies) || data.strategies.length > 32
    || data.strategies.some(item => !item || typeof item !== 'object'
      || ![item.strategy_id, item.display_name, item.description].every(text)
      || !(item.strategy_version === null || text(item.strategy_version))
      || !Array.isArray(item.historical_versions) || item.historical_versions.length > 32 || !item.historical_versions.every(text))
    || new Set(data.strategies.map(item => item.strategy_id + '@' + item.strategy_version)).size !== data.strategies.length) {
    throw new Error('策略目录格式无效，请重新读取')
  }
  return data.strategies as StrategyDefinition[]
}
