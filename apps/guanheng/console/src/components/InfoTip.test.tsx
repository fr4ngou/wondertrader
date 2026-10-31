import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, test } from 'vitest'

import { InfoTip } from './InfoTip'


describe('InfoTip', () => {
  test('opens a Chinese explanation from the keyboard-focusable summary control', () => {
    render(<InfoTip label="最新有效目标">协调器可使用的完整目标事实。</InfoTip>)
    const control = screen.getByRole('button', { name: '说明：最新有效目标' })
    control.focus()
    fireEvent.click(control)
    expect(control).toHaveFocus()
    expect(screen.getByRole('tooltip')).toHaveTextContent('协调器可使用的完整目标事实。')
  })
})
