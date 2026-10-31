import { afterEach, expect, it, vi } from 'vitest'
import { fetchReadJson } from '../api'
import { commandBacktest, fetchBacktestRecords, fetchBacktestWorkspace } from './backtestApi'

vi.mock('../api', () => ({ fetchReadJson: vi.fn() }))
afterEach(() => { vi.resetAllMocks(); vi.unstubAllGlobals() })
const id = 'a'.repeat(32)
const run = { owner_id: id, request_id: '1'.repeat(32), run_id: 'b'.repeat(32), status: 'completed', reason: '已完成',
  elapsed_ms: 500, pid: 123, exit_code: 0, forced: false, pid_reaped: true, pipes_joined: true, record_count: 5, scope: 'isolated-raw-BT' }
const workspace = { schema: 'nbw-workspace-v1', owner_id: id, available: true, reason: null,
  configuration: { label: '合成样本', start: 202401030930, end: 202401091500, session_sha256: 'c'.repeat(64), max_seconds: 30 }, runs: [run], scope: 'isolated-raw-BT' }

for (const field of ['owner_id', 'request_id', 'run_id'] as const) {
  it(`拒绝将${field}数组强转成字符串身份`, async () => {
    const invalid = { ...run, [field]: [run[field]] }
    vi.mocked(fetchReadJson).mockResolvedValue({ ...workspace, runs: [invalid] })
    await expect(fetchBacktestWorkspace()).rejects.toThrow('格式或身份无效')
  })
}

it('拒绝工作区owner数组和配置摘要数组', async () => {
  vi.mocked(fetchReadJson).mockResolvedValue({ ...workspace, owner_id: [id], runs: [] })
  await expect(fetchBacktestWorkspace()).rejects.toThrow('格式或身份无效')
  vi.mocked(fetchReadJson).mockResolvedValue({ ...workspace, configuration: { ...workspace.configuration, session_sha256: ['c'.repeat(64)] } })
  await expect(fetchBacktestWorkspace()).rejects.toThrow('格式或身份无效')
})

it('拒绝报告摘要数组', async () => {
  vi.mocked(fetchReadJson).mockResolvedValue({ request_id: run.request_id, report_sha256: ['c'.repeat(64)], total: 0, offset: 0, records: [], scope: run.scope })
  await expect(fetchBacktestRecords(id, run.request_id, 0)).rejects.toThrow('格式或身份无效')
})

it('拒绝将状态数组强转成已完成状态', async () => {
  vi.mocked(fetchReadJson).mockResolvedValue({ ...workspace, runs: [{ ...run, status: ['completed'] }] })
  await expect(fetchBacktestWorkspace()).rejects.toThrow('格式或身份无效')
})

for (const failure of ['malformed-json', 'network'] as const) {
  it(`${failure}仅展示固定中文核查说明`, async () => {
    vi.stubGlobal('fetch', failure === 'network'
      ? vi.fn().mockRejectedValue(new Error('Failed to fetch NBW_PRIVATE_RESPONSE_TOKEN'))
      : vi.fn().mockResolvedValue(new Response('NBW_PRIVATE_RESPONSE_TOKEN', { status: 200 })))
    let message = ''
    try { await commandBacktest(id, run.request_id) } catch (error) { message = (error as Error).message }
    expect(message).toContain('刷新状态核查')
    expect(message).not.toContain('NBW_PRIVATE')
    expect(message).not.toContain('Failed to fetch')
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1)
  })
}
