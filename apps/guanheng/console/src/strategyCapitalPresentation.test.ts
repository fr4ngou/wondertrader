import { expect, test } from 'vitest'
import { holdingsWithTargets, selectedCapital } from './strategyCapitalPresentation'
import type { StrategyCapitalSleeve, StrategyWorkbenchDetail } from './types'

const sleeve = { strategy_id: 'a', strategy_version: '1', strategy_lineage_id: 'lineage', genesis_epoch_id: 'epoch', net_asset_value: 100, positions: [{ symbol: 'x', quantity: 2, valuation_price: 10, market_value: 20 }] } as StrategyCapitalSleeve
const target = { items: [{ symbol: 'x', target_weight: .3 }, { symbol: 'y', target_weight: .1 }] } as StrategyWorkbenchDetail['current_target']
test('capital selection rejects another epoch, strategy, version, and ambiguous scope', () => {
  expect(selectedCapital([sleeve], 'a', '1', 'lineage', 'epoch')).toBe(sleeve)
  expect(selectedCapital([sleeve], 'a', '1', 'lineage', 'other')).toBeUndefined()
  expect(selectedCapital([sleeve], 'b', '1')).toBeUndefined()
  expect(selectedCapital([sleeve], 'a', '2')).toBeUndefined()
  expect(selectedCapital([sleeve, { ...sleeve, genesis_epoch_id: 'other' }], 'a', '1')).toBeUndefined()
})
test('unknown position coverage stays unknown, while an authoritative empty list confirms zero', () => {
  expect(holdingsWithTargets({ ...sleeve, positions: undefined }, target)[0].currentWeight).toBeUndefined()
  const rows = holdingsWithTargets(sleeve, target)
  expect(rows[0].currentWeight).toBe(.2)
  expect(rows[0].gap).toBeCloseTo(.1)
  expect(rows[1].currentWeight).toBe(0)
  expect(holdingsWithTargets(undefined, target)[0].gap).toBeUndefined()
})
