import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { RelativeUpdateTime, relativeUpdateText } from './RelativeUpdateTime'

afterEach(() => { cleanup(); vi.useRealTimers() })

test('renders Chinese relative update time with a complete Beijing timestamp', () => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-09-19T02:00:00Z'))
  render(<RelativeUpdateTime value="2026-09-19T01:57:00Z" freshnessThresholdSeconds={600} />)
  expect(screen.getByText('3 分钟前更新')).toBeInTheDocument()
  expect(screen.getByText('北京时间 2026/09/19 09:57:00')).toHaveAttribute('dateTime', '2026-09-19T01:57:00Z')
})

test('makes missing, expired, and future timestamps explicit', () => {
  const now = Date.parse('2026-09-19T02:00:00Z')
  expect(relativeUpdateText(null, now, 600).primary).toBe('暂无更新时间')
  expect(relativeUpdateText('2026-09-19T00:00:00Z', now, 600).primary).toBe('已过期 · 已 2 小时未更新')
  expect(relativeUpdateText('2026-09-19T02:03:00Z', now, 600).primary).toBe('时间异常 · 比当前时间晚 3 分钟')
})
