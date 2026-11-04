import { expect, it } from 'vitest'
import { validateStrategyRuntime } from './strategyRuntimeApi'
import { validateRetainedSummary, retainedSymbols } from './backtestRetained'
import current from './strategy-published-new.fixture.json'
import saved from './backtest-saved-old.fixture.json'

it('实际新纯核回包和已保存旧回测各按自身版本与证券读取，交错调用保持归属', () => {
  const fresh = validateStrategyRuntime(current)
  expect(fresh.strategy?.strategy_version).toBe('1.2.1')
  expect(fresh.strategy?.positions.map(p => p.symbol)).toContain('589680.SH')
  const symbols = retainedSymbols(saved.record.capture.observation.positions.map(p => p.symbol))
  const historical = validateRetainedSummary(saved.evaluation_summary, saved.record.trading_date, symbols)
  expect(historical.strategy_version).toBe('1.1.2')
  expect(Object.keys(historical.targets)).toContain('589000.SH')
  expect(validateStrategyRuntime(current).strategy?.positions.map(p => p.symbol)).not.toContain('589000.SH')
})

it('缺失活动版本和等待期证券保持原缺失事实，错误证券格式仍拒绝', () => {
  const waiting = structuredClone(current)
  waiting.strategy.strategy_version = null as unknown as string
  waiting.strategy.positions = waiting.strategy.positions.slice(0, 3)
  expect(validateStrategyRuntime(waiting).strategy?.strategy_version).toBeNull()
  waiting.strategy.positions[0].symbol = 'unknown'
  expect(() => validateStrategyRuntime(waiting)).toThrow()
})
