import { fireEvent, render, screen, cleanup } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ReadNotice } from './ReadNotice'

afterEach(cleanup)

const previous = {
  data: { state: 'running' }, dataUpdatedAt: Date.parse('2026-11-22T10:25:01Z'),
  isError: false, isFetching: false, error: null, refetch: vi.fn(),
}

it('已有结果的后台轮询持续保留页面布局，不插入刷新横幅', () => {
  const { container, rerender } = render(<ReadNotice label="更新状态" query={previous} />)
  expect(container).toBeEmptyDOMElement()
  // 补齐期间每两秒读取状态；请求在途与完成均不应挤动图表。
  for (let cycle = 0; cycle < 3; cycle += 1) {
    const refreshing = { ...previous, isFetching: true }
    rerender(<ReadNotice label="更新状态" query={refreshing} />)
    expect(container).toBeEmptyDOMElement()
    rerender(<ReadNotice label="更新状态" query={previous} />)
    expect(container).toBeEmptyDOMElement()
  }
})

it('失败保留读取时间和重试入口，重试在途保持失败提示，成功后清除', () => {
  const refetch = vi.fn()
  const failed = { ...previous, isError: true, error: new Error('连接中断'), refetch }
  const { container, rerender } = render(<ReadNotice label="更新状态" query={failed} />)
  expect(screen.getByRole('status')).toHaveTextContent('更新状态读取失败：连接中断')
  expect(container.querySelector('time')).toHaveAttribute('dateTime', '2026-11-22T10:25:01.000Z')
  fireEvent.click(screen.getByRole('button', { name: '重新读取更新状态' }))
  expect(refetch).toHaveBeenCalledOnce()
  const retrying = { ...failed, isFetching: true }
  rerender(<ReadNotice label="更新状态" query={retrying} />)
  expect(screen.getByRole('status')).toHaveTextContent('当前保留上次读取结果')
  rerender(<ReadNotice label="更新状态" query={previous} />)
  expect(container).toBeEmptyDOMElement()
})

it('首次失败准确说明尚未取得结果', () => {
  render(<ReadNotice label="指标数据" query={{ ...previous, data: undefined, dataUpdatedAt: 0,
    isError: true, error: new Error('连接中断') }} />)
  expect(screen.getByRole('status')).toHaveTextContent('本次尚未取得结果')
  expect(document.querySelector('time')).toBeNull()
})
