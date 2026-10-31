import type { StrategyCapitalSleeve, StrategyWorkbenchDetail } from './types'

export function selectedCapital(sleeves: StrategyCapitalSleeve[], strategyId: string, version: string, lineage?: string | null, epoch?: string | null) {
  const matches = sleeves.filter(item => item.strategy_id === strategyId && item.strategy_version === version
    && (!lineage || item.strategy_lineage_id === lineage) && (!epoch || item.genesis_epoch_id === epoch))
  return matches.length === 1 ? matches[0] : undefined
}

export function holdingsWithTargets(sleeve: StrategyCapitalSleeve | undefined, target: StrategyWorkbenchDetail['current_target']) {
  const symbols = new Set([...(sleeve?.positions?.map(item => item.symbol) ?? []), ...(target?.items.map(item => item.symbol) ?? [])])
  return [...symbols].sort().map(symbol => {
    const position = sleeve?.positions?.find(item => item.symbol === symbol)
    const currentWeight = sleeve?.positions && sleeve.net_asset_value > 0
      ? (position?.market_value ?? 0) / sleeve.net_asset_value : undefined
    const targetWeight = target?.items.find(item => item.symbol === symbol)?.target_weight
    return { symbol, position, currentWeight, targetWeight,
      gap: currentWeight != null && targetWeight != null ? targetWeight - currentWeight : undefined }
  })
}
