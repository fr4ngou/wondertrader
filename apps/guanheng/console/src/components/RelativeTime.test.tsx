import { render, screen } from '@testing-library/react'
import { describe, expect, test } from 'vitest'

import { absoluteChinaTime, relativeTimeLabel, RelativeTime } from './RelativeTime'


describe('RelativeTime', () => {
  test('uses Chinese relative time and exposes exact China time by focus and click', () => {
    const now = Date.parse('2026-09-19T04:03:00Z')
    expect(relativeTimeLabel('2026-09-19T04:00:00Z', now)).toBe('3 分钟前更新')
    expect(absoluteChinaTime('2026-09-19T04:00:00Z')).toContain('12:00:00')

    render(<RelativeTime value="2026-09-17T04:03:00Z" staleAfterSeconds={3600} />)
    const element = screen.getByText(/已过期/)
    expect(element.closest('summary')).toBeTruthy()
    expect(screen.getByText(/北京时间/)).toBeInTheDocument()
  })

  test('names missing, invalid, and future timestamps explicitly', () => {
    const now = Date.parse('2026-09-19T04:00:00Z')
    expect(relativeTimeLabel(null, now)).toBe('时间不可用')
    expect(relativeTimeLabel('invalid', now)).toBe('时间格式不可识别')
    expect(relativeTimeLabel('2026-09-19T04:05:00Z', now)).toBe('5 分钟后')
  })
})
