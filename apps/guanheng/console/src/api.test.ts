import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  fetchBacktestReports,
  fetchBootstrap,
  fetchDefaultWatchlist,
  fetchExecutionQueue,
  fetchMarketChart,
  fetchPublicObservation,
  fetchOperationsWorkbench,
  fetchOperationalErrorLogs,
  fetchOrderTrace,
  fetchOverview,
  fetchPortfolioPnl,
  fetchQmtConnectionStatus,
  fetchRecentOrders,
  fetchStrategyRegistry,
  fetchStrategyEligibility,
  fetchStrategyWorkbenchDetail,
  AUDIT_TRACE_TIMEOUT_MS,
  DEFERRED_OVERVIEW_TIMEOUT_MS,
  INTERACTIVE_STATUS_TIMEOUT_MS,
  MAX_QUEUED_READS_PER_LANE,
  fetchReadJson,
} from './api'

function abortablePendingFetch(_input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  return new Promise((_resolve, reject) => {
    init?.signal?.addEventListener('abort', () => {
      reject(new DOMException('aborted', 'AbortError'))
    }, { once: true })
  })
}

describe('bounded interactive status reads', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('keeps one slow preview below two foreground reads and independent status/audit capacity', async () => {
    const mock = vi.fn(abortablePendingFetch)
    vi.stubGlobal('fetch', mock)
    const controller = new AbortController()
    const read = (path: string, lane: Parameters<typeof fetchReadJson>[3]) =>
      fetchReadJson(path, '测试', controller.signal, lane, 10_000)
    const results = [read('/preview/1', 'preview'), read('/preview/2', 'preview'),
      read('/main', 'workspace'), read('/search', 'workspace'), read('/status', 'status'), read('/audit', 'audit')]
    const settled = Promise.allSettled(results)
    expect(mock.mock.calls.map(([url]) => url)).toEqual(['/preview/1', '/main', '/search', '/status', '/audit'])
    controller.abort()
    await settled
  })

  it.each([
    ['QMT connection', fetchQmtConnectionStatus, 'QMT 连接状态读取超时'],
  ] as const)('fails a hanging %s read with an explicit deadline', async (_label, request, message) => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn(abortablePendingFetch))

    const result = request(undefined, 25)
    const rejection = expect(result).rejects.toThrow(message)
    await vi.advanceTimersByTimeAsync(25)

    await rejection
  })

  it('preserves caller cancellation instead of misreporting it as a timeout', async () => {
    vi.stubGlobal('fetch', vi.fn(abortablePendingFetch))
    const controller = new AbortController()
    const result = fetchQmtConnectionStatus(controller.signal, 5_000)

    controller.abort()

    await expect(result).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('keeps status reads independent from a busy workspace lane', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn(abortablePendingFetch)
    vi.stubGlobal('fetch', fetchMock)

    const bootstrapController = new AbortController()
    const first = fetchBootstrap(bootstrapController.signal)
    const second = fetchQmtConnectionStatus(undefined, 25)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    const statusRejection = expect(second).rejects.toThrow('QMT 连接状态读取超时')
    await vi.advanceTimersByTimeAsync(25)
    await statusRejection

    bootstrapController.abort()
    await expect(first).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('expires a queued status read before it reaches fetch', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn(abortablePendingFetch)
    vi.stubGlobal('fetch', fetchMock)
    const controller = new AbortController()
    const active = fetchQmtConnectionStatus(controller.signal, 5_000)
    const queued = fetchQmtConnectionStatus(undefined, 25)
    expect(fetchMock).toHaveBeenCalledTimes(1)

    const rejection = expect(queued).rejects.toThrow('QMT 连接状态读取超时')
    await vi.advanceTimersByTimeAsync(25)
    await rejection
    expect(fetchMock).toHaveBeenCalledTimes(1)

    controller.abort()
    await expect(active).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('reserves browser connection capacity for status and audit reads', async () => {
    const fetchMock = vi.fn(abortablePendingFetch)
    vi.stubGlobal('fetch', fetchMock)

    const controllers = Array.from({ length: 5 }, () => new AbortController())
    const requests = controllers.map((controller) => fetchBootstrap(controller.signal))
    await Promise.resolve()
    expect(fetchMock).toHaveBeenCalledTimes(2)

    controllers.forEach((controller) => controller.abort())
    await Promise.allSettled(requests)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('bounds waiting reads before fetch and releases capacity on cancellation without blocking status', async () => {
    const mock = vi.fn(abortablePendingFetch); vi.stubGlobal('fetch', mock)
    const controllers = Array.from({ length: MAX_QUEUED_READS_PER_LANE + 2 }, () => new AbortController())
    const reads = controllers.map((controller, index) => fetchReadJson(`/capacity-${index}`, '行情', controller.signal, 'workspace', 5000))
    const settled = Promise.allSettled(reads)
    const replacement = new AbortController(), status = new AbortController()
    let recovered: Promise<unknown> | undefined, reserved: Promise<unknown> | undefined
    try {
      expect(mock).toHaveBeenCalledTimes(2)
      await expect(fetchReadJson('/overflow', '行情', undefined, 'workspace', 5000)).rejects.toThrow('行情读取请求较多')
      expect(mock).toHaveBeenCalledTimes(2)
      controllers[2].abort(); await expect(reads[2]).rejects.toMatchObject({ name: 'AbortError' })
      recovered = fetchReadJson('/capacity-recovered', '行情', replacement.signal, 'workspace', 5000)
      reserved = fetchReadJson('/reserved-status', '状态', status.signal, 'status', 5000)
      expect(mock).toHaveBeenCalledTimes(3)
      controllers.forEach(controller => controller.abort())
      await settled
      expect(mock.mock.calls.some(call => String(call[0]) === '/capacity-recovered')).toBe(true)
    } finally {
      controllers.forEach(controller => controller.abort()); replacement.abort(); status.abort()
      await Promise.allSettled([...reads, ...[recovered,reserved].filter((p): p is Promise<unknown> => p !== undefined)])
    }
  })

  it('does not let a deferred overview block an active workspace projection', async () => {
    const overviewController = new AbortController()
    const fetchMock = vi.fn()
      .mockImplementationOnce(abortablePendingFetch)
      .mockResolvedValueOnce(new Response('[]', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const overview = fetchOverview(overviewController.signal)
    const reports = fetchBacktestReports()

    await expect(reports).resolves.toEqual([])
    expect(fetchMock).toHaveBeenCalledTimes(2)
    overviewController.abort()
    await expect(overview).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('does not let queued workspace reads consume the reserved audit slot', async () => {
    const workspaceControllers = Array.from({ length: 4 }, () => new AbortController())
    const tracePayload = {
      schema_version: '1.0', correlation_id: '11111111-1111-4111-8111-111111111111',
      stages: [], complete: false, read_only: true,
    }
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => (
      String(input).includes('/trace')
        ? Promise.resolve(new Response(JSON.stringify(tracePayload), {
            status: 200, headers: { 'Content-Type': 'application/json' },
          }))
        : abortablePendingFetch(input, init)
    ))
    vi.stubGlobal('fetch', fetchMock)

    const busyReads = workspaceControllers.map((controller) => fetchBootstrap(controller.signal))
    await Promise.resolve()
    expect(fetchMock).toHaveBeenCalledTimes(2)

    await expect(fetchOrderTrace(tracePayload.correlation_id)).resolves.toEqual(tracePayload)
    expect(fetchMock).toHaveBeenCalledTimes(3)

    workspaceControllers.forEach((controller) => controller.abort())
    await Promise.allSettled(busyReads)
  })

  it('bounds the deferred overview without blocking the shell deadline', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn(abortablePendingFetch))

    const result = fetchOverview()
    const rejection = expect(result).rejects.toThrow('工作台详细投影读取超时')
    await vi.advanceTimersByTimeAsync(DEFERRED_OVERVIEW_TIMEOUT_MS)

    await rejection
  })

  it('gives the six-stage audit trace its bounded detailed-projection deadline', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn(abortablePendingFetch))

    let settled = false
    const result = fetchOrderTrace('11111111-1111-4111-8111-111111111111')
    void result.then(() => { settled = true }, () => { settled = true })
    await vi.advanceTimersByTimeAsync(INTERACTIVE_STATUS_TIMEOUT_MS)
    expect(settled).toBe(false)

    const rejection = expect(result).rejects.toThrow('订单因果链读取超时')
    await vi.advanceTimersByTimeAsync(AUDIT_TRACE_TIMEOUT_MS - INTERACTIVE_STATUS_TIMEOUT_MS)
    await rejection
  })

  it('gives strategy detail enough time for one bounded internal read retry', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn(abortablePendingFetch))

    let settled = false
    const result = fetchStrategyWorkbenchDetail('resonance-regime-v1', '1.0.0')
    void result.then(() => { settled = true }, () => { settled = true })
    await vi.advanceTimersByTimeAsync(INTERACTIVE_STATUS_TIMEOUT_MS)
    expect(settled).toBe(false)

    const rejection = expect(result).rejects.toThrow('策略详情读取超时')
    await vi.advanceTimersByTimeAsync(DEFERRED_OVERVIEW_TIMEOUT_MS - INTERACTIVE_STATUS_TIMEOUT_MS)
    await rejection
  })
})

describe('bounded read-only workspace projections', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it.each([
    ['bootstrap', () => fetchBootstrap()],
    ['market', () => fetchMarketChart('510300.SH', '1d')],
    ['personal observation', () => fetchPublicObservation('588170.SH', '1d')],
    ['strategies', () => fetchStrategyRegistry()],
    ['strategy eligibility', () => fetchStrategyEligibility()],
    ['backtests', () => fetchBacktestReports()],
    ['portfolio', () => fetchPortfolioPnl()],
    ['orders', () => fetchRecentOrders()],
    ['operations', () => fetchOperationsWorkbench()],
    ['error logs', () => fetchOperationalErrorLogs()],
    ['execution queue', () => fetchExecutionQueue()],
    ['watchlist', () => fetchDefaultWatchlist()],
  ] as const)('fails a hanging %s projection instead of loading forever', async (_label, request) => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn(abortablePendingFetch))

    const result = request()
    const rejection = expect(result).rejects.toThrow('读取超时')
    await vi.advanceTimersByTimeAsync(INTERACTIVE_STATUS_TIMEOUT_MS)

    await rejection
  })
})

describe('operations workbench scope', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('requests only the receipt count needed by the system status page', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) => new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await fetchOperationsWorkbench(undefined, 8)

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock.mock.calls[0][0]).toBe('/v1/ui/operations/workbench?limit=8')
  })
})

describe('execution queue pagination', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  function queueItem(index: number) {
    return {
      schema_version: '1.0' as const,
      queue_item_id: `00000000-0000-4000-8000-${String(index).padStart(12, '0')}`,
      correlation_id: `10000000-0000-4000-8000-${String(index).padStart(12, '0')}`,
      identity: { source_kind: 'automatic_strategy' as const },
      strategy_id: 'strategy-a', strategy_version: '1.0.0', config_version: 'config-v1',
      symbol: '510300.SH', side: 'buy' as const,
      target_quantity: 100, completed_quantity: 0, remaining_quantity: 100,
      stage: 'planned' as const, wait_state: null,
      stage_entered_at: '2026-09-18T01:00:00Z', last_changed_at: '2026-09-18T01:00:00Z',
      event_at: '2026-09-18T01:00:00Z', originated_before_today: false, changed_today: true,
      blocking_issue_codes: [], next_legal_stage: 'risk_pending',
      risk_status: 'not_evaluated' as const, approval_status: 'not_reached' as const,
      command_status: 'not_reached' as const,
    }
  }

  function queuePage(index: number, nextCursor: string | null) {
    return {
      schema_version: '1.0' as const,
      agent_id: 'guoxin-qmt-1', account_id: '******1314', account_environment: 'simulation' as const,
      projection_revision: 42, as_of: '2026-09-18T01:00:00Z', trading_date: '2026-09-18',
      calendar_status: 'available' as const, today_activity: [queueItem(index)], carryover_pending: [],
      source_coverage: { execution_queue: 'complete' as const },
      truncated: nextCursor != null, next_cursor: nextCursor, read_only: true as const,
    }
  }

  it('reads beyond twenty pages without silently truncating the queue', async () => {
    const pageCount = 21
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = new URL(String(input), 'http://console.test')
      const cursor = url.searchParams.get('cursor')
      const index = cursor == null ? 0 : Number(cursor.replace('cursor-', ''))
      const nextCursor = index + 1 < pageCount ? `cursor-${index + 1}` : null
      return Promise.resolve(new Response(JSON.stringify(queuePage(index, nextCursor)), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      }))
    })
    vi.stubGlobal('fetch', fetchMock)

    const projection = await fetchExecutionQueue()

    expect(fetchMock).toHaveBeenCalledTimes(pageCount)
    expect(projection.today_activity).toHaveLength(pageCount)
    expect(projection.truncated).toBe(false)
    expect(projection.next_cursor).toBeNull()
    expect(String(fetchMock.mock.calls[0][0])).toContain('limit=200')
    expect(String(fetchMock.mock.calls[20][0])).toContain('projection_revision=42')
    expect(String(fetchMock.mock.calls[20][0])).toContain('cursor=cursor-20')
  })

  it('rejects a repeated cursor instead of looping forever', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(queuePage(0, 'cursor-1')), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify(queuePage(1, 'cursor-1')), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchExecutionQueue()).rejects.toThrow('重复游标')
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
