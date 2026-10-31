import { useEffect, useRef, useState } from 'react'
import { useQueryClient, type QueryClient } from '@tanstack/react-query'

import {
  BOOTSTRAP_QUERY_KEY,
  QMT_CONNECTION_QUERY_KEY,
  WATCHLIST_QUERY_KEY,
} from '../api'
import type { StreamEvent } from '../types'

const CONSOLE_EVENT_TYPES = [
  'ui.bootstrap.invalidated',
  'account.updated',
  'market.updated',
  'control.emergency_stop.activated',
  'control.watchlist.updated',
  'strategy.runtime.paused',
  'strategy.runtime.resumed',
  'strategy.runtime.started',
  'strategy.runtime.stopped',
  'strategy.config.activated',
  'strategy.config.rolled_back',
  'replay.promotion_review.recorded',
  'replay.backtest_job.queued',
  'replay.backtest_job.stop_requested',
  'audit.ledger.event',
  'ui.audit_stream.degraded',
  'ui.audit_stream.recovered',
] as const

export type ConsoleStreamState = 'disabled' | 'connecting' | 'online' | 'syncing' | 'reconnecting'

const STREAM_EVENT_QUERY_KEYS: Record<string, ReadonlyArray<readonly unknown[]>> = {
  'ui.bootstrap.invalidated': [BOOTSTRAP_QUERY_KEY],
  'account.updated': [
    QMT_CONNECTION_QUERY_KEY,
    ['portfolio-pnl'],
    ['portfolio-performance'],
    ['portfolio-positions'],
    ['portfolio-allocation'],
    ['portfolio-contributions'],
    ['orders'],
  ],
  'market.updated': [
    ['market-chart'],
    ['dashboard-market-chart'],
    ['market-quote'],
    ['market-data-subscriptions'],
  ],
  'control.emergency_stop.activated': [
    BOOTSTRAP_QUERY_KEY,
    ['operations'],
  ],
  'control.watchlist.updated': [WATCHLIST_QUERY_KEY],
  'strategy.runtime.paused': [['strategy-runtime'], ['strategy-workbench-detail']],
  'strategy.runtime.resumed': [['strategy-runtime'], ['strategy-workbench-detail']],
  'strategy.runtime.started': [['strategy-runtime'], ['strategy-workbench-detail']],
  'strategy.runtime.stopped': [['strategy-runtime'], ['strategy-workbench-detail']],
  'strategy.config.activated': [
    BOOTSTRAP_QUERY_KEY,
    ['direction-configs'],
    ['direction-config-activations'],
    ['strategy-runtime'],
    ['strategy-workbench-detail'],
  ],
  'strategy.config.rolled_back': [
    BOOTSTRAP_QUERY_KEY,
    ['direction-configs'],
    ['direction-config-activations'],
    ['strategy-runtime'],
    ['strategy-workbench-detail'],
  ],
  'replay.promotion_review.recorded': [
    ['audit', 'promotion-reviews'],
    ['project', 'milestones'],
  ],
  'replay.backtest_job.queued': [['backtests', 'jobs']],
  'replay.backtest_job.stop_requested': [['backtests', 'jobs']],
}

export function queryKeysForStreamEvent(eventType: string): ReadonlyArray<readonly unknown[]> {
  return STREAM_EVENT_QUERY_KEYS[eventType] ?? []
}

export function sourceEventType(event: StreamEvent): string {
  const projected = event.payload.source_event_type
  return event.event_type === 'audit.ledger.event' && typeof projected === 'string'
    ? projected
    : event.event_type
}

export function queryKeysForEvent(event: StreamEvent): ReadonlyArray<readonly unknown[]> {
  if (
    event.event_type === 'audit.ledger.event'
    && event.payload.delivery_mode === 'history'
  ) return []
  const effectiveType = sourceEventType(event)
  const exact = queryKeysForStreamEvent(effectiveType)
  if (exact.length) return exact
  if (effectiveType.startsWith('account.') || effectiveType.startsWith('qmt.account.')) {
    return [
      QMT_CONNECTION_QUERY_KEY,
      ['portfolio-pnl'],
      ['portfolio-performance'],
      ['portfolio-positions'],
      ['portfolio-allocation'],
      ['portfolio-contributions'],
      ['orders'],
    ]
  }
  if (
    effectiveType.startsWith('execution.')
    || effectiveType.startsWith('bridge.')
    || effectiveType.startsWith('qmt.order.')
  ) {
    return [
      ['orders'],
      ['order-trace'],
      ['portfolio-pnl'],
      ['portfolio-performance'],
      ['portfolio-positions'],
      ['portfolio-allocation'],
    ]
  }
  if (effectiveType.startsWith('market.')) {
    return [['market-chart'], ['dashboard-market-chart'], ['market-quote']]
  }
  if (effectiveType.startsWith('strategy.')) {
    return [['strategy-runtime'], ['strategy-workbench-detail'], ['portfolio-allocation']]
  }
  if (effectiveType.startsWith('portfolio.')) {
    return [
      ['portfolio-pnl'],
      ['portfolio-performance'],
      ['portfolio-positions'],
      ['portfolio-allocation'],
      ['portfolio-contributions'],
    ]
  }
  if (effectiveType.startsWith('replay.')) {
    return [['backtests'], ['audit']]
  }
  if (effectiveType.startsWith('control.') || effectiveType.startsWith('operations.')) {
    return [BOOTSTRAP_QUERY_KEY, ['operations']]
  }
  if (event.event_type === 'audit.ledger.event') return [['audit']]
  return []
}

export function uniqueQueryKeys(
  keys: ReadonlyArray<readonly unknown[]>,
): ReadonlyArray<readonly unknown[]> {
  return [...new Map(keys.map((queryKey) => [JSON.stringify(queryKey), queryKey])).values()]
}

export function invalidateStreamQueryKeys(
  queryClient: Pick<QueryClient, 'invalidateQueries'>,
  keys: ReadonlyArray<readonly unknown[]>,
): void {
  uniqueQueryKeys(keys).forEach((queryKey) => {
    // A new SSE fact must not cancel an authoritative projection already in flight.
    // Cancelling queued reads on every account/market update can starve the later
    // dashboard projections even though every upstream request is healthy.
    void queryClient.invalidateQueries({ queryKey }, { cancelRefetch: false })
  })
}

export function useConsoleStream(enabled: boolean) {
  const queryClient = useQueryClient()
  const lastSeq = useRef(0)
  const seenEventIds = useRef<string[]>([])
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [state, setState] = useState<ConsoleStreamState>(enabled ? 'connecting' : 'disabled')

  useEffect(() => {
    if (!enabled) {
      setState('disabled')
      return undefined
    }
    setState('connecting')
    // Bounded SSE bursts preserve native Last-Event-ID recovery while releasing the
    // localhost connection between batches for account, market and order projections.
    const source = new EventSource('/v1/ui/stream?transport=burst', { withCredentials: true })
    let hasOpened = false
    let reconnectTimer: number | undefined
    let pendingQueryKeys: Array<readonly unknown[]> = []
    let invalidationTimer: number | undefined
    const flushInvalidations = () => {
      const queryKeys = pendingQueryKeys
      pendingQueryKeys = []
      invalidationTimer = undefined
      invalidateStreamQueryKeys(queryClient, queryKeys)
    }
    const queueInvalidations = (queryKeys: ReadonlyArray<readonly unknown[]>) => {
      if (!queryKeys.length) return
      pendingQueryKeys.push(...queryKeys)
      if (invalidationTimer === undefined) {
        invalidationTimer = window.setTimeout(flushInvalidations, 120)
      }
    }
    const onEvent = (message: MessageEvent<string>) => {
      try {
        const event = JSON.parse(message.data) as StreamEvent
        if (seenEventIds.current.includes(event.event_id)) return
        seenEventIds.current = [event.event_id, ...seenEventIds.current].slice(0, 256)
        lastSeq.current = event.seq
        if (event.event_type !== 'ui.bootstrap.invalidated') {
          setEvents((current) => [event, ...current].slice(0, 50))
        }
        queueInvalidations(queryKeysForEvent(event))
      } catch {
        // An invalid event cannot mutate UI state; EventSource will keep the stream alive.
      }
    }
    const onOpen = () => {
      hasOpened = true
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer)
      reconnectTimer = undefined
      setState('online')
    }
    const onError = () => {
      if (!hasOpened) {
        setState('reconnecting')
        return
      }
      // A bounded burst ends cleanly and EventSource reconnects by design. Present
      // that normal gap as periodic synchronization; only call it a reconnect if
      // the next burst cannot open within the grace period.
      setState('syncing')
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer)
      reconnectTimer = window.setTimeout(() => setState('reconnecting'), 5_000)
    }
    source.addEventListener('open', onOpen)
    source.addEventListener('error', onError)
    CONSOLE_EVENT_TYPES.forEach((eventType) => {
      source.addEventListener(eventType, onEvent as EventListener)
    })
    return () => {
      CONSOLE_EVENT_TYPES.forEach((eventType) => {
        source.removeEventListener(eventType, onEvent as EventListener)
      })
      source.removeEventListener('open', onOpen)
      source.removeEventListener('error', onError)
      source.close()
      if (invalidationTimer !== undefined) window.clearTimeout(invalidationTimer)
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer)
    }
  }, [enabled, queryClient])

  return { events, state, lastSeq: lastSeq.current }
}
