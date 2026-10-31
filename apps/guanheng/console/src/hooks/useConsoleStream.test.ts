import { describe, expect, test, vi } from 'vitest'

import {
  BOOTSTRAP_QUERY_KEY,
  QMT_CONNECTION_QUERY_KEY,
  WATCHLIST_QUERY_KEY,
} from '../api'
import {
  invalidateStreamQueryKeys,
  queryKeysForEvent,
  queryKeysForStreamEvent,
  sourceEventType,
  uniqueQueryKeys,
} from './useConsoleStream'

describe('queryKeysForStreamEvent', () => {
  test('does not reload the global bootstrap for high-frequency market events', () => {
    const keys = queryKeysForStreamEvent('market.updated')

    expect(keys).toContainEqual(['market-chart'])
    expect(keys).toContainEqual(['dashboard-market-chart'])
    expect(keys).toContainEqual(['market-quote'])
    expect(keys).not.toContainEqual(BOOTSTRAP_QUERY_KEY)
  })

  test('refreshes account projections without treating them as configuration changes', () => {
    const keys = queryKeysForStreamEvent('account.updated')

    expect(keys).toContainEqual(QMT_CONNECTION_QUERY_KEY)
    expect(keys).toContainEqual(['portfolio-pnl'])
    expect(keys).toContainEqual(['portfolio-positions'])
    expect(keys).not.toContainEqual(BOOTSTRAP_QUERY_KEY)
  })

  test('routes watchlist and explicit bootstrap invalidations precisely', () => {
    expect(queryKeysForStreamEvent('control.watchlist.updated')).toEqual([WATCHLIST_QUERY_KEY])
    expect(queryKeysForStreamEvent('ui.bootstrap.invalidated')).toEqual([BOOTSTRAP_QUERY_KEY])
    expect(queryKeysForStreamEvent('unknown.event')).toEqual([])
  })

  test('projects authoritative execution facts into order and portfolio refreshes', () => {
    const event = {
      schema_version: '1.0' as const,
      seq: 8,
      event_id: '11111111-1111-4111-8111-111111111111',
      event_type: 'audit.ledger.event',
      occurred_at: '2026-08-16T05:00:00Z',
      payload: { source_event_type: 'execution.order.filled' },
    }

    expect(sourceEventType(event)).toBe('execution.order.filled')
    expect(queryKeysForEvent(event)).toContainEqual(['orders'])
    expect(queryKeysForEvent(event)).toContainEqual(['order-trace'])
    expect(queryKeysForEvent(event)).toContainEqual(['portfolio-positions'])
    expect(queryKeysForEvent(event)).not.toContainEqual(BOOTSTRAP_QUERY_KEY)
  })

  

  test('does not refetch current projections for initial historical audit backfill', () => {
    const keys = queryKeysForEvent({
      schema_version: '1.0',
      seq: 10,
      event_id: '33333333-3333-4333-8333-333333333333',
      event_type: 'audit.ledger.event',
      occurred_at: '2026-08-14T07:00:00Z',
      payload: {
        source_event_type: 'execution.order.filled',
        delivery_mode: 'history',
      },
    })

    expect(keys).toEqual([])
  })

  test('continues to refetch precise projections for live audit increments', () => {
    const keys = queryKeysForEvent({
      schema_version: '1.0',
      seq: 11,
      event_id: '44444444-4444-4444-8444-444444444444',
      event_type: 'audit.ledger.event',
      occurred_at: '2026-08-16T06:00:00Z',
      payload: {
        source_event_type: 'execution.order.filled',
        delivery_mode: 'live',
      },
    })

    expect(keys).toContainEqual(['orders'])
    expect(keys).toContainEqual(['portfolio-positions'])
  })

  test('coalesces duplicate query families from a burst of live facts', () => {
    const keys = uniqueQueryKeys([
      ['orders'],
      ['portfolio-positions'],
      ['orders'],
      ['portfolio-positions'],
      ['order-trace'],
    ])

    expect(keys).toEqual([
      ['orders'],
      ['portfolio-positions'],
      ['order-trace'],
    ])
  })

  test('never cancels an authoritative read already in flight', () => {
    const invalidateQueries = vi.fn().mockResolvedValue(undefined)

    invalidateStreamQueryKeys(
      { invalidateQueries } as never,
      [['orders'], ['orders'], ['portfolio-positions']],
    )

    expect(invalidateQueries).toHaveBeenCalledTimes(2)
    expect(invalidateQueries).toHaveBeenNthCalledWith(
      1,
      { queryKey: ['orders'] },
      { cancelRefetch: false },
    )
    expect(invalidateQueries).toHaveBeenNthCalledWith(
      2,
      { queryKey: ['portfolio-positions'] },
      { cancelRefetch: false },
    )
  })
})
