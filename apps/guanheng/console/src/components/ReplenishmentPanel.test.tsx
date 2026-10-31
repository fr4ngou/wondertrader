import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { ReplenishmentPanel } from './ReplenishmentPanel'

const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.forEach((client) => client.clear()); clients.length = 0; vi.unstubAllGlobals() })
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  clients.push(client)
  return render(<QueryClientProvider client={client}><ReplenishmentPanel /></QueryClientProvider>)
}
const item = {
  episode_id: 'fixture-episode', strategy_id: 'fixture-strategy', symbol: 'TEST.SH', side: 'sell',
  state_label: '等待合适价格', remaining_quantity: 600, filled_quantity: null, stage_index: 0,
  next_action: '到期后按策略放宽，再检查一次', next_action_owner: '系统自动处理',
  blocking_reason_labels: ['当前价格尚未进入允许范围'], business_boundary: 9.9,
  stages: [{ index: 1, authorized: false, status: '下一档', boundary: 9.875, wait: { amount: 3, unit: 'trading_days' } }],
}
test('shows authoritative progress, expands unapproved stages, and refreshes with read-only requests', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(Response.json({ scan_error: null, items: [item] }))
    .mockResolvedValue(Response.json({ scan_error: null, items: [{ ...item, remaining_quantity: 200, filled_quantity: 400 }] }))
  vi.stubGlobal('fetch', fetch)
  mount()
  expect(await screen.findByText('TEST.SH · 卖出')).toBeVisible()
  expect(screen.getByText(/实际成交/)).toHaveTextContent('实际成交 待核对')
  expect(screen.getByText(/系统自动处理/)).toBeVisible()
  fireEvent.click(screen.getByText('查看等待与价格详情'))
  expect(screen.getByText(/第 2 档/)).toBeVisible()
  expect(screen.getByText(/第 2 档/)).toHaveTextContent('尚未授权')
  fireEvent.click(screen.getByRole('button', { name: '说明：原始目标量' }))
  expect(screen.getByRole('tooltip', { name: /原始目标量/ })).toHaveTextContent('已保存的策略意图')
  fireEvent.click(screen.getByRole('button', { name: '刷新补单进度' }))
  await waitFor(() => expect(screen.getByText(/实际成交/)).toHaveTextContent('实际成交 400'))
  expect(fetch).toHaveBeenCalledTimes(2)
  for (const [url, options] of fetch.mock.calls) {
    expect(url).toBe('/v1/ui/portfolio/replenishment')
    expect(options.method ?? 'GET').toBe('GET')
    expect(options.body).toBeUndefined()
  }
})
test('distinguishes empty records from read failure and hides stale results', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(Response.json({ scan_error: null, items: [] }))
    .mockResolvedValue(new Response('', { status: 503 })))
  mount()
  expect(await screen.findByText('暂无补单记录')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '刷新补单进度' }))
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('读取失败不代表没有补单'), { timeout: 4000 })
})
test('keeps legacy records read-only with unknown quantity', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ scan_error: null, items: [{
    episode_id: 'old', state_label: '等待历史记录核对', legacy_read_only: true,
  }] })))
  mount()
  expect(await screen.findByText('等待历史记录核对')).toBeVisible()
  expect(screen.getByText(/实际成交/)).toHaveTextContent('剩余 待核对 份')
  expect(screen.queryByText('查看等待与价格详情')).not.toBeInTheDocument()
})

test('keeps unfamiliar reason codes behind an optional technical detail', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ scan_error: null, items: [{
    ...item, blocking_reasons: ['future_reason'],
    blocking_reason_labels: ['条件待核对，请查看系统状态'],
  }] })))
  mount()
  expect(await screen.findByText('条件待核对，请查看系统状态')).toBeVisible()
  expect(screen.getByText('future_reason')).not.toBeVisible()
  fireEvent.click(screen.getByText('技术详情'))
  expect(screen.getByText('future_reason')).toBeVisible()
})

test('separates current opportunities, historical configuration and unknown scope with one list read', async () => {
  const { replenishmentDisplayScope } = await import('../replenishment')
  const selected = { strategyId: item.strategy_id, strategyVersion: String(Date.now()), configId: 'selected-config' }
  const current = { ...item, strategy_version: selected.strategyVersion, config_id: selected.configId,
    episode_id: 'continued', target_revision: 'original-opportunity-target', next_review_at: '2030-01-03T07:00:00Z', next_retry_at: '2030-01-02T02:00:00Z' }
  expect(replenishmentDisplayScope(current, selected)).toBe('current')
  expect(replenishmentDisplayScope({ ...current, target_revision: 'successor-target' }, selected)).toBe('current')
  const historical = { ...current, episode_id: 'old-config', config_id: 'prior-config', symbol: 'OLD.SH' }
  const unknown = { ...current, episode_id: 'missing-scope', config_id: null, symbol: 'UNKNOWN.SH' }
  expect(replenishmentDisplayScope(historical, selected)).toBe('historical')
  expect(replenishmentDisplayScope(unknown, selected)).toBe('unknown')
  const fetch = vi.fn().mockResolvedValue(Response.json({ scan_error: null, items: [current, historical, unknown] }))
  vi.stubGlobal('fetch', fetch)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } }); clients.push(client)
  render(<QueryClientProvider client={client}><ReplenishmentPanel strategyId={selected.strategyId} strategyVersion={selected.strategyVersion} activeConfigId={selected.configId} /></QueryClientProvider>)
  expect(await screen.findByText('TEST.SH · 卖出')).toBeVisible()
  expect(screen.getByText('历史配置与版本补单（1 项）')).toBeVisible()
  expect(screen.getByText('归属待核对（1 项）')).toBeVisible()
  expect(within(screen.getByRole('region', { name: '当前配置补单' })).getByText(/下一次业务复核：/)).toHaveTextContent('执行层重试')
  expect(screen.getByText('OLD.SH · 卖出')).not.toBeVisible()
  expect(fetch).toHaveBeenCalledTimes(1)
})

test('does not turn missing scan coverage or a version mismatch into current zero', async () => {
  const { replenishmentDisplayScope } = await import('../replenishment')
  const selected = { strategyId: item.strategy_id, strategyVersion: String(Date.now()), configId: 'selected-config' }
  expect(replenishmentDisplayScope({ ...item, strategy_version: selected.strategyVersion + '-prior', config_id: selected.configId }, selected)).toBe('historical')
  expect(replenishmentDisplayScope({ ...item, legacy_read_only: true }, selected)).toBe('unknown')
  const malformed = { ...item, strategy_version: 42, config_id: selected.configId } as unknown as Parameters<typeof replenishmentDisplayScope>[0]
  expect(replenishmentDisplayScope(malformed, selected)).toBe('unknown')
  expect(replenishmentDisplayScope({ ...item, strategy_id: 'other-strategy' }, selected)).toBe('other_strategy')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ items: [] })))
  mount()
  expect(await screen.findByRole('alert')).toHaveTextContent('扫描状态不可用或不完整')
  expect(screen.queryByText('暂无补单记录')).not.toBeInTheDocument()
  cleanup()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ scan_error: null, items: [] })))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } }); clients.push(client)
  render(<QueryClientProvider client={client}><ReplenishmentPanel strategyId={selected.strategyId} strategyVersion={selected.strategyVersion} /></QueryClientProvider>)
  expect(await screen.findByText(/当前配置归属或来源覆盖尚待核对/)).toBeVisible()
  expect(screen.queryByText(/已核对当前配置未结束补单 0 项/)).not.toBeInTheDocument()
  expect(screen.queryByText(/当前筛选下暂无补单记录/)).not.toBeInTheDocument()
  cleanup()
  const identity = { ...item, strategy_version: selected.strategyVersion, config_id: selected.configId }
  const invalidRows = [
    { ...identity, episode_id: 'object-version', strategy_version: { bad: true }, config_version: ['bad'], target_revision: 42 },
    { ...identity, episode_id: 'array-config', config_id: ['bad'], config_version: { bad: true }, target_revision: ['bad'] },
    { ...identity, episode_id: 'object-strategy', strategy_id: { bad: true }, strategy_version: 42, config_version: 42, target_revision: { bad: true } },
  ]
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ scan_error: null, items: invalidRows })))
  const malformedClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } }); clients.push(malformedClient)
  render(<QueryClientProvider client={malformedClient}><ReplenishmentPanel strategyId={selected.strategyId} strategyVersion={selected.strategyVersion} activeConfigId={selected.configId} /></QueryClientProvider>)
  const unknown = await screen.findByRole('region', { name: '归属待核对补单' })
  expect(within(unknown).getByText('归属待核对（3 项）')).toBeVisible()
  const details = within(unknown).getAllByText('查看等待与价格详情').map(summary => summary.closest('details')!)
  details.forEach(detail => fireEvent.click(within(detail).getByText('查看等待与价格详情')))
  const field = (detail: HTMLElement, label: string) => within(detail).getByText(label, { selector: 'dt' }).closest('div')!.querySelector('dd')!
  expect(field(details[0], '策略版本')).toHaveTextContent(/^待核对$/)
  expect(field(details[0], '配置归属')).toHaveTextContent(`待核对 · ${selected.configId}`)
  expect(field(details[1], '配置归属')).toHaveTextContent(/^待核对$/)
  expect(field(details[2], '策略版本')).toHaveTextContent(/^待核对$/)
  details.forEach(detail => expect(field(detail, '机会原目标')).toHaveTextContent(/^待核对$/))
  expect(within(unknown).getAllByText('待核对').some(element => element.tagName === 'SMALL')).toBe(true)
  expect(unknown).not.toHaveTextContent('[object Object]')
  expect(screen.queryByText(/已核对当前配置未结束补单 0 项/)).not.toBeInTheDocument()
})
