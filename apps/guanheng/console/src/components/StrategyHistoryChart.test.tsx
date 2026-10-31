import { cleanup, render } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { StrategyCapitalHistory } from '../types'
import { StrategyHistoryChart } from './StrategyHistoryChart'

const chart = vi.hoisted(() => ({ setOption: vi.fn(), dispose: vi.fn(), resize: vi.fn() }))
vi.mock('echarts/core', async importOriginal => ({ ...await importOriginal<typeof import('echarts/core')>(), init: vi.fn(() => chart) }))
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals() })

test('preserves blocked valuation gaps and disposes the previous identity chart', () => {
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  const history = { strategy_id: 'strategy-a', points: [
    { captured_at: '2026-10-01T00:00:00Z', valuation_at: '2026-10-01T00:00:00Z', status: 'ready', return_on_principal: 0.1, drawdown: 0 },
    { captured_at: '2026-10-02T00:00:00Z', valuation_at: '2026-10-02T00:00:00Z', status: 'blocked', return_on_principal: null, drawdown: null },
    { captured_at: '2026-10-03T00:00:00Z', valuation_at: '2026-10-03T00:00:00Z', status: 'ready', return_on_principal: 0.2, drawdown: 0 },
  ] } as StrategyCapitalHistory
  const { rerender } = render(<StrategyHistoryChart history={history} />)
  expect(chart.setOption.mock.calls[0][0].series).toEqual(expect.arrayContaining([
    expect.objectContaining({ data: [0.1, null, 0.2], connectNulls: false }),
    expect.objectContaining({ data: [0, null, 0], connectNulls: false }),
  ]))
  rerender(<StrategyHistoryChart history={{ ...history, strategy_id: 'strategy-b', points: [] }} />)
  expect(chart.dispose).toHaveBeenCalledTimes(1)
  expect(chart.setOption.mock.calls[1][0].series[0].data).toEqual([])
})

test('daily gaps, actual timestamps and a zero single point remain visible', () => {
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  render(<StrategyHistoryChart history={{ sampling: 'daily', window_start: '2031-03-12T00:00:00+08:00', window_end: '2031-03-14T00:00:00+08:00', points: [
    { captured_at: '2031-03-12T01:00:00Z', valuation_at: '2031-03-11T06:00:00Z', status: 'ready', return_on_principal: 0, drawdown: 0 },
  ] } as StrategyCapitalHistory} />)
  const options = chart.setOption.mock.calls[0][0]
  expect(options.xAxis[1].data).toEqual(['2031-03-12', '2031-03-13'])
  expect(options.series[0].data).toEqual([0, null])
  expect(options.series[1]).toMatchObject({ name: '每日采样回撤', data: [0, null], showSymbol: true, connectNulls: false })
  expect(options.yAxis[1]).toMatchObject({ min: -.001, max: 0 })
  expect(options.tooltip.formatter([{ dataIndex: 0 }])).toContain('2031-03-11')
  expect(options.tooltip.formatter([{ dataIndex: 0 }])).toContain('保存观察')
})
