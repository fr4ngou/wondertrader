import { describe, expect, it } from 'vitest'
import type { MarketChartBundle } from '../types'
import { accountFills, heldAccountSymbols, mapAccountFills } from './marketAccountFacts'
import type { AccountField, AccountGroupV1, AccountRow } from './accountApi'

const present = (value: string | number): AccountField => ({ availability: 'present', value, reason: null })
const row = (symbol: string, fields: AccountRow['fields'], tradeId = ''): AccountRow => ({
  identity: { wt_symbol: symbol, m_strTradeID: tradeId }, fields,
})
const group = (datatype: 'deal' | 'position', rows: AccountRow[]): AccountGroupV1 => ({
  datatype, status: 'complete', rows, source: null, execution_started_at: null, execution_finished_at: null,
  request_id: null, result_sha256: null, reason: null,
})
const candle = (occurred_at: string) => ({ occurred_at, open: 10, high: 11, low: 9, close: 10, volume: 1 })

describe('market account facts', () => {
  it('lists each currently held security once and preserves exchange identity', () => {
    const positions = group('position', [
      row('510500.SH', { quantity: present(100) }), row('510500.SH', { quantity: present('50') }),
      row('159780.SZ', { quantity: present(0) }),
      { identity: { m_strExchangeID: 'BJ', m_strInstrumentID: '920001' }, fields: { quantity: present(50) } },
    ])
    expect(heldAccountSymbols(positions)).toEqual(['510500.SH', '920001.BJ'])
    expect(heldAccountSymbols({ ...positions, status: 'unavailable' })).toEqual([])
  })

  it('uses confirmed direction and amount and maps only to the corresponding source candle', () => {
    const fields = { side: present(48), date: present('20261112'), time: present('09:30:23'), amount: present('1001.2') }
    const fills = accountFills(group('deal', [
      row('510500.SH', fields, 'a'), row('510500.SH', fields, 'a'), row('159780.SZ', fields, 'b'),
      row('510500.SH', { side: present(49), date: fields.date, time: present(93032) }, 'c'),
      row('510500.SH', { ...fields, time: present(93123) }, 'd'),
    ]), '510500.SH')
    expect(fills.map(fill => [fill.side, fill.amount])).toEqual([['buy', 1001.2], ['sell', null], ['buy', 1001.2]])
    const base: MarketChartBundle = { schema_version: '1.5', symbol: '510500.SH', period: '1m', data_available: true,
      candles: [candle('2026-11-12T01:31:00Z'), candle('2026-11-12T01:33:00Z')] }
    const native_source = { chart_minute_boundary: 'source_label', source_minute_boundary: 'right' } as MarketChartBundle['native_source']
    expect(mapAccountFills({ ...base, native_source }, fills)).toEqual([
      { index: 0, side: 'buy', amounts: [1001.2] }, { index: 0, side: 'sell', amounts: [null] },
    ])
    for (const period of ['1w', '1mo'] as const) {
      const nextDay = { ...fills[0], day: '2026-11-13' }
      const beforeWindow = { ...fills[0], day: '2026-11-10' }
      expect(mapAccountFills({ ...base, period, first_source_at: '2026-11-10T16:00:00Z',
        candles: [candle('2026-11-11T16:00:00Z')] }, [...fills, nextDay, beforeWindow])).toEqual([
        { index: 0, side: 'buy', amounts: [1001.2, 1001.2] }, { index: 0, side: 'sell', amounts: [null] },
      ])
    }
  })
})
