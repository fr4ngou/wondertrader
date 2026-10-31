import { afterEach, expect, test, vi } from 'vitest'
import { fetchBacktestReport, fetchBacktestTrades, fetchStrategyCapitalHistory, fetchStrategyWorkbenchDetail } from './api'

afterEach(() => vi.unstubAllGlobals())

test.each(['report', 'trades'])('rejects a mismatched backtest %s identity', async kind => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ report_hash: 'other', items: [] })))
  await expect(kind === 'report' ? fetchBacktestReport('selected') : fetchBacktestTrades('selected')).rejects.toThrow('身份')
})

test('validates history owner, scope and readonly semantics', async () => {
  const payload = { schema_version: 'strategy-capital-history-v1', strategy_id: 'selected', strategy_lineage_id: 'lineage', genesis_epoch_id: 'epoch', read_only: true, source_kind: 'strategy_capital_snapshots', calculation_method: 'return-on-contributed-principal-v1', points: [] }
  const fetchMock = vi.fn().mockImplementation(async () => Response.json(payload))
  vi.stubGlobal('fetch', fetchMock)
  expect(await fetchStrategyCapitalHistory('selected', 'lineage', 'epoch')).toEqual(payload)
  for (const altered of [{ ...payload, strategy_id: 'other' }, { ...payload, genesis_epoch_id: 'other' }, { ...payload, read_only: false }, { ...payload, source_kind: 'account_snapshot' }, { ...payload, points: {} }]) {
    fetchMock.mockResolvedValueOnce(Response.json(altered))
    await expect(fetchStrategyCapitalHistory('selected', 'lineage', 'epoch')).rejects.toThrow('身份或格式')
  }
})

test('passes daily window parameters and refuses another sampling identity', async () => {
  const payload = { schema_version: 'strategy-capital-history-v1', strategy_id: 'selected', strategy_lineage_id: 'lineage', genesis_epoch_id: 'epoch', read_only: true, source_kind: 'strategy_capital_snapshots', calculation_method: 'return-on-contributed-principal-v1', sampling: 'daily', window_start: '2031-03-12T00:00:00+08:00', window_end: '2031-03-13T00:00:00+08:00', points: [] }
  const fetchMock = vi.fn().mockResolvedValue(Response.json(payload))
  vi.stubGlobal('fetch', fetchMock)
  await expect(fetchStrategyCapitalHistory('selected', 'lineage', 'epoch', undefined, { sampling: 'daily', days: 30 })).resolves.toEqual(payload)
  const url = new URL(String(fetchMock.mock.calls[0][0]), 'https://local.test')
  expect(url.searchParams.get('sampling')).toBe('daily')
  expect(url.searchParams.get('days')).toBe('30')
  for (const altered of [{ ...payload, sampling: 'snapshots' }, { ...payload, sampling: undefined }, { ...payload, window_end: '2031-03-13T00:00:00' }, { ...payload, window_end: payload.window_start }]) {
    fetchMock.mockResolvedValueOnce(Response.json(altered))
    await expect(fetchStrategyCapitalHistory('selected', 'lineage', 'epoch', undefined, { sampling: 'daily' })).rejects.toThrow(/采样身份|窗口格式/)
  }
})

test.each([0, 91, 1.5, NaN])('refuses invalid days %s before requesting history', async days => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  await expect(fetchStrategyCapitalHistory('selected', 'lineage', 'epoch', undefined, { sampling: 'daily', days })).rejects.toThrow('采样参数无效')
  expect(fetchMock).not.toHaveBeenCalled()
})

test('preserves finite history values and gaps while refusing malformed numeric facts', async () => {
  const point = { captured_at: '2031-03-12T01:00:00Z', valuation_at: '2031-03-12T00:45:00Z', strategy_version: 'synthetic', net_asset_value: 123, contributed_principal: 100, capital_contributions_total: 0, investment_pnl: 23, status: 'ready', return_on_principal: .23, drawdown: 0 }
  const payload = { schema_version: 'strategy-capital-history-v1', strategy_id: 'selected', strategy_lineage_id: 'lineage', genesis_epoch_id: 'epoch', read_only: true, source_kind: 'strategy_capital_snapshots', calculation_method: 'return-on-contributed-principal-v1', points: [point] }
  const fetchMock = vi.fn().mockResolvedValue(Response.json(payload))
  vi.stubGlobal('fetch', fetchMock)
  expect((await fetchStrategyCapitalHistory('selected', 'lineage', 'epoch')).points[0]).toEqual(point)
  fetchMock.mockResolvedValueOnce(Response.json({ ...payload, points: [{ ...point, status: 'blocked', return_on_principal: null, drawdown: null }] }))
  expect((await fetchStrategyCapitalHistory('selected', 'lineage', 'epoch')).points[0].return_on_principal).toBeNull()
  fetchMock.mockResolvedValueOnce(Response.json({ ...payload, points: [{ ...point, net_asset_value: 'not-a-number' }] }))
  await expect(fetchStrategyCapitalHistory('selected', 'lineage', 'epoch')).rejects.toThrow('数值格式不匹配')
})

test('rejects a strategy detail returned for another selection', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ strategy: { strategy_id: 'other', strategy_version: 'fixture-version' }, errors: {}, configured_parameters: {}, performance_reports: [] })))
  await expect(fetchStrategyWorkbenchDetail('selected', 'fixture-version')).rejects.toThrow('策略详情身份或格式')
})
