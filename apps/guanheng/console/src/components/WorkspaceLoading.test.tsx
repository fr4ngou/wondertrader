import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { WorkspaceLoading } from './WorkspaceLoading'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

test('ends a stalled workspace load with explicit recovery actions', () => {
  vi.useFakeTimers()
  const reload = vi.fn()
  render(<WorkspaceLoading timeoutMs={1_000} onReload={reload} />)

  expect(screen.getByRole('status')).toHaveTextContent('正在打开工作区')

  act(() => vi.advanceTimersByTime(999))
  expect(screen.getByRole('status')).toHaveTextContent('正在打开工作区')

  act(() => vi.advanceTimersByTime(1))
  expect(screen.getByRole('alert')).toHaveTextContent('工作区资源加载超时')
  expect(screen.getByRole('link', { name: '打开系统状态' })).toHaveAttribute('href', '/operations')

  fireEvent.click(screen.getByRole('button', { name: '重新加载工作台' }))
  expect(reload).toHaveBeenCalledTimes(1)
})

test('clears the deadline when the loading fallback unmounts', () => {
  vi.useFakeTimers()
  const { unmount } = render(<WorkspaceLoading timeoutMs={1_000} />)

  unmount()
  act(() => vi.advanceTimersByTime(1_000))

  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})
