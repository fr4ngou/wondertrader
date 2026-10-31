import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'

import * as api from '../api'
import { OrdersPage } from './OrdersPage'
import type { ConsoleBootstrap, ExecutionQueueProjection } from '../types'

vi.mock('../api', () => ({
  fetchExecutionQueue: vi.fn(), fetchAccountExecutionBatches: vi.fn(),
  fetchOrders: vi.fn(), fetchOrderTrace: vi.fn(),
}))

afterEach(cleanup)

function renderQueue(stage: string) {
  vi.mocked(api.fetchExecutionQueue).mockResolvedValue({
    calendar_status: 'available', source_coverage: { queue: 'complete' },
    today_activity: [{ queue_item_id: 'retired-item', correlation_id: 'prior-correlation',
      identity: { source_kind: 'automatic_strategy' }, strategy_id: 'fixture-strategy', strategy_version: 'fixture-version',
      symbol: 'FIXTURE.SH', side: 'sell', stage, originated_before_today: true,
      changed_today: true, remaining_quantity: 100, completed_quantity: 0, target_quantity: 100,
      blocking_issue_codes: [], wait_state: null, risk_status: 'accepted', approval_status: 'failed',
      command_status: 'not_reached', stage_entered_at: '2026-01-02T01:00:00Z', last_changed_at: '2026-01-02T01:00:00Z' }],
    carryover_pending: [], truncated: false, trading_date: '2026-01-02',
  } as unknown as ExecutionQueueProjection)
  vi.mocked(api.fetchAccountExecutionBatches).mockResolvedValue({ batches: [] } as never)
  vi.mocked(api.fetchOrders).mockResolvedValue({ items: [], total: 0 } as never)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  const view = render(<QueryClientProvider client={client}><MemoryRouter><OrdersPage bootstrap={{ overview: {} } as ConsoleBootstrap} /></MemoryRouter></QueryClientProvider>)
  return { client, view }
}

test('an unfilled superseded approval ends its waiting clock without claiming a fill', async () => {
  const { client, view } = renderQueue('superseded')
  try {
    const row = await screen.findByRole('button', { name: /FIXTURE.SH.*已失效并结束/ })
    expect(row).toHaveTextContent('历史事项今日结束')
    expect(row).toHaveTextContent('未执行数量保留为历史记录')
    expect(row).toHaveTextContent('0 / 100')
    expect(row).toHaveTextContent('结束于')
    expect(row).not.toHaveTextContent('尚未终态')
    expect(row).not.toHaveTextContent('已成交完成')
    expect(row).not.toHaveTextContent('等待 0 分钟')
  } finally {
    view.unmount()
    client.clear()
  }
})

test('an unknown stage remains unavailable and retains its original code in selected details', async () => {
  const { client, view } = renderQueue('future_stage_v2')
  try {
    const row = await screen.findByRole('button', { name: /FIXTURE.SH.*执行阶段不可用/ })
    expect(row).toHaveTextContent('等待权威阶段')
    fireEvent.click(row)
    const detail = await screen.findByRole('region', { name: '待执行事项调用链' })
    expect(detail).toHaveTextContent('执行阶段不可用')
    fireEvent.click(within(detail).getByText('阶段技术详情'))
    expect(within(detail).getByText('future_stage_v2')).toBeVisible()
    expect(detail).not.toHaveTextContent('已成交完成')
  } finally {
    view.unmount()
    client.clear()
  }
})
