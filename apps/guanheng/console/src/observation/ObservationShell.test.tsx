import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, vi, it, expect } from 'vitest'
import App from '../App'
// Routing assertions exercise the real lazy boundary after its module is ready;
// Vite's first transform belongs to setup, not the request-isolation timeout.
import './ObservationShell'

let activeQuery: QueryClient | undefined
function pendingFetch(_url: unknown, options?: RequestInit) {
  return new Promise((_resolve, reject) => {
    const abort = () => reject(new DOMException('aborted', 'AbortError'))
    if (options?.signal?.aborted) abort()
    else options?.signal?.addEventListener('abort', abort, { once: true })
  })
}
afterEach(() => {
  cleanup()
  activeQuery?.clear()
  activeQuery = undefined
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})

it.each(['/observation','/observation/data','/observation/quality','/observation/api'])('观察入口%s不启动交易bootstrap或事件流', async path => {
  vi.stubEnv('VITE_OBSERVATION_ONLY', 'false')
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ snapshot_id: 'a'.repeat(64), published_at: '2026-10-17T00:00:00Z', boards: [], datasets: [], preferences: { default_board: 'bond', default_datasets: {} } }) })
  vi.stubGlobal('fetch', fetch)
  const events = vi.fn(); vi.stubGlobal('EventSource', events)
  const query = activeQuery = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  // Keep the catalog pending after the isolated routing branch mounts.
  fetch.mockImplementation(pendingFetch)
  const ui = render(<QueryClientProvider client={query}><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></QueryClientProvider>)
  expect(await screen.findByRole('heading', { name: '衡量市场的位置与变化' }, { timeout: 10000 })).toBeInTheDocument()
  await waitFor(() => expect(fetch).toHaveBeenCalled())
  for (const [name, href] of [['总览', '/dashboard'], ['行情', '/market'], ['策略', '/strategies'], ['交易记录', '/orders'], ['系统状态', '/operations']]) {
    expect(screen.getByRole('link', { name })).toHaveAttribute('href', href)
  }
  expect(fetch.mock.calls.every(call => String(call[0]).includes('/v1/ui/market-observation/'))).toBe(true)
  expect(events).not.toHaveBeenCalled()
  ui.unmount(); query.clear()
}, 15000)

it('远端观察专用入口只显示观察导航且不启动交易读取', async () => {
  vi.stubEnv('VITE_OBSERVATION_ONLY', 'true')
  const fetch = vi.fn().mockImplementation(pendingFetch); vi.stubGlobal('fetch', fetch)
  const events = vi.fn(); vi.stubGlobal('EventSource', events)
  const query = activeQuery = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const ui = render(<QueryClientProvider client={query}><MemoryRouter initialEntries={['/observation']}><App /></MemoryRouter></QueryClientProvider>)
  await screen.findByRole('heading', { name: '衡量市场的位置与变化' }, { timeout: 10000 })
  expect(screen.getByRole('link', { name: '市场观察' })).toHaveAttribute('href', '/observation')
  expect(screen.queryByRole('link', { name: '策略' })).not.toBeInTheDocument()
  expect(fetch.mock.calls.every(call => String(call[0]).includes('/v1/ui/market-observation/'))).toBe(true)
  expect(events).not.toHaveBeenCalled()
  ui.unmount(); query.clear()
})
