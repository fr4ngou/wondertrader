import { cleanup, render } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { Definition } from './types'
import { ObservationChart } from './ObservationChart'

const chart = vi.hoisted(() => ({ setOption: vi.fn(), on: vi.fn(), dispatchAction: vi.fn(), resize: vi.fn(), dispose: vi.fn() }))
const init = vi.hoisted(() => vi.fn(() => chart))
vi.mock('echarts/core', () => ({ use: vi.fn(), init }))
vi.mock('../workspace/observerAppearance', () => ({ useObserverTheme: () => 'light', observerChartColors: () => ({}) }))
beforeEach(() => vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} }))
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals() })

it('后台父组件刷新和日期变化沿用图表实例，卸载时释放并使用最新交互回调', () => {
  const definition = { id: 'fixture', board: 'valuation', frequency: 'daily', lines: [
    { key: 'value', name: '样本', color: '#123456', unit: '倍', panel: 'main', shown: true },
  ] } as Definition
  const rows = [{ date: '2026-11-20', value: 7 }]
  const range = { start: '2026-11-01', end: '2026-11-22' }
  const onRange = vi.fn(), onHidden = vi.fn()
  const props = { definition, rows, range, hidden: [], focus: 'both', mode: 'fixed_base', activity: 'all', onRange, onHidden }
  const { rerender, unmount } = render(<ObservationChart {...props} />)
  // 状态轮询会让父组件重渲染并生成内容相同的新数组。
  rerender(<ObservationChart {...props} hidden={[]} />)
  expect(init).toHaveBeenCalledOnce()
  expect(chart.dispose).not.toHaveBeenCalled()
  const latestRange = vi.fn(), latestHidden = vi.fn()
  rerender(<ObservationChart {...props} range={{ ...range, start: '2026-11-10' }} onRange={latestRange} onHidden={latestHidden} />)
  expect(init).toHaveBeenCalledOnce()
  // 更新采用完整选项替换，减少面板/曲线时旧配置也退出。
  expect(chart.setOption).toHaveBeenLastCalledWith(expect.any(Object), { notMerge: true })
  chart.on.mock.calls.find(([name]) => name === 'legendselectchanged')![1]({ selected: { '样本': false } })
  expect(latestHidden).toHaveBeenCalledWith(['value'])
  expect(onHidden).not.toHaveBeenCalled()
  chart.on.mock.calls.find(([name]) => name === 'brushEnd')![1]({ areas: [{ coordRange: [Date.parse('2026-11-01'), Date.parse('2026-11-20')] }] })
  expect(latestRange).toHaveBeenCalledWith({ start: '2026-11-10', end: '2026-11-20' })
  unmount()
  expect(chart.dispose).toHaveBeenCalledOnce()
})
