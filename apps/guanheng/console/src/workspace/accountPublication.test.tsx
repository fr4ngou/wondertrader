import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AccountWorkspace from './AccountWorkspace'
import { validateAccountOverview, type AccountOverviewV2, type AccountOverviewV4 } from './accountApi'
import { accountReadView } from './accountPresentation'
import original from './account-v2.fixture.json'

// 公开DTO合成测试；真实普通安装/浏览器来源见NAP整链证据。
function fixture(): AccountOverviewV4 {
  return { ...structuredClone(original), schema_version: '4.0', publication: {
    scope_id: 'a'.repeat(64), state: 'ready', revision: 3, updated_at: '2026-10-30T00:00:01.000000Z',
    last_success_at: '2026-10-30T00:00:01.000000Z', runtime_state: 'ready',
  } } as AccountOverviewV4
}
const clients: QueryClient[] = []
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.unstubAllGlobals() })

it('DTO4复用原四组金融字段、掩码与批次时间', () => {
  const value = fixture()
  expect(validateAccountOverview(value)).toEqual(value)
  expect(accountReadView(value).complete).toEqual(value.groups)
})

it.each([
  { scope_id: null }, { revision: 0 }, { revision: true }, { updated_at: null },
  { last_success_at: null }, { state: 'unconfigured' }, { runtime_state: 'unknown' },
  { last_success_at: '2099-01-01T00:00:00.000000Z' }, { secret: 'private-value' },
])('拒绝与来源/时点不一致的发布元数据 %j', change => {
  const value = fixture()
  Object.assign(value.publication, change)
  expect(() => validateAccountOverview(value)).toThrow('账户数据格式无效，请重新读取')
})

it('来源撤回、发布owner换代或DTO切换清除全部旧批回退', () => {
  const first = accountReadView(fixture())
  const missing = fixture()
  missing.status = 'unavailable'; missing.scan_id = null
  missing.publication = { scope_id: null, state: 'unconfigured', revision: 0,
    updated_at: null, last_success_at: null, runtime_state: 'ready' }
  for (const group of Object.values(missing.groups)) Object.assign(group, { status: 'unavailable', rows: [],
    source: null, execution_started_at: null, execution_finished_at: null, request_id: null, result_sha256: null })
  expect(validateAccountOverview(missing)).toEqual(missing)
  expect(accountReadView(missing, first).complete).toEqual({})
  const changed = structuredClone(missing)
  changed.publication = { ...fixture().publication, scope_id: 'b'.repeat(64), state: 'refreshing', last_success_at: null }
  expect(accountReadView(changed, first).complete).toEqual({})
  expect(accountReadView({ ...changed, schema_version: '2.0' } as unknown as AccountOverviewV2, first).complete).toEqual({})
})

it('更新失败显示旧值及原成功时点，成功空批立即清除旧行', async () => {
  const first = fixture()
  const failed = fixture(); failed.publication.state = 'degraded'
  failed.publication.updated_at = '2026-10-30T00:00:02.000000Z'
  failed.reason = 'WT本轮账户更新失败；下方保留上次成功结果和原查询时间。'
  const empty = fixture(); empty.groups.position.rows = []
  empty.publication.last_success_at = empty.publication.updated_at = '2026-10-30T00:00:03.000000Z'
  const fetchMock = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(first)))
    .mockResolvedValueOnce(new Response(JSON.stringify(failed))).mockResolvedValueOnce(new Response(JSON.stringify(empty)))
  vi.stubGlobal('fetch', fetchMock)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } }); clients.push(client)
  render(<QueryClientProvider client={client}><AccountWorkspace capability={{ available: true, reason: null, timeout_seconds: 2 }} /></QueryClientProvider>)
  await screen.findByText('600000.SH')
  fireEvent.click(screen.getByRole('button', { name: '刷新账户' }))
  await screen.findByText('WT本轮更新失败')
  expect(screen.getByText('600000.SH')).toBeInTheDocument()
  expect(screen.getByText(/最近发布：2026-10-30 08:00:02.*上次成功：2026-10-30 08:00:01/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '刷新账户' }))
  await screen.findByText('本轮持仓查询完整，返回 0 条记录。')
  expect(screen.queryByText('600000.SH')).not.toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(3)
})
