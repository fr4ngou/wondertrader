import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchReadJson } from '../api'
import { commandBacktest, fetchBacktestDay, fetchBacktestWorkspace, fetchBacktestArchive, fetchArchiveConfiguration, fetchBacktestRecords } from './backtestApi'
import day from './backtest-day.fixture.json'

vi.mock('../api', () => ({ fetchReadJson: vi.fn() }))
afterEach(() => { vi.resetAllMocks(); vi.unstubAllGlobals() })
const run = { owner_id: 'a'.repeat(32), request_id: '1'.repeat(32), run_id: 'b'.repeat(32), status: 'completed', reason: '已完成',
  elapsed_ms: 500, pid: 123, exit_code: 0, forced: false, pid_reaped: true, pipes_joined: true, record_count: 5, scope: 'isolated-raw-BT' }
const workspace = { schema: 'nbw-workspace-v1', owner_id: run.owner_id, available: true, reason: null,
  configuration: { label: '合成验证样本', start: 202401030930, end: 202401091500, session_sha256: 'c'.repeat(64), max_seconds: 30 }, runs: [run], scope: 'isolated-raw-BT' }

it('校验工作区和真实形态当日资金、持仓、阶段', async () => {
  vi.mocked(fetchReadJson).mockResolvedValueOnce(workspace).mockResolvedValueOnce(day)
  expect((await fetchBacktestWorkspace()).runs[0].status).toBe('completed')
  expect((await fetchBacktestDay(run.owner_id, run.request_id, 4)).record.capture?.basis.nav_cny).toBe('100000')
})

describe.each([
  { ...workspace, runs: [{ ...run, forced: true }] },
  { ...workspace, runs: [{ ...run, pid_reaped: false }] },
  { ...workspace, runs: [{ ...run, owner_id: 'd'.repeat(32) }] },
  { ...workspace, configuration: null },
])('拒绝伪完成或来源身份失配', value => {
  it('保留无数据状态', async () => {
    vi.mocked(fetchReadJson).mockResolvedValue(value)
    await expect(fetchBacktestWorkspace()).rejects.toThrow('格式或身份无效')
  })
})

it('拒绝缺少阶段数组的当日响应，避免页面运行时崩溃', async () => {
  vi.mocked(fetchReadJson).mockResolvedValue({ ...day, record: { ...day.record, outcome: { status: 'converged', reason: '' } } })
  await expect(fetchBacktestDay(run.owner_id, run.request_id, 4)).rejects.toThrow('格式或身份无效')
})

it('启动与取消各只发送一次同编号；不自动重试', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(run), { status: 202 }))
  vi.stubGlobal('fetch', fetch)
  await commandBacktest(run.owner_id, run.request_id)
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ owner_id: run.owner_id, request_id: run.request_id })
  fetch.mockResolvedValue(new Response('{}', { status: 409 }))
  await expect(commandBacktest(run.owner_id, run.request_id, true)).rejects.toThrow('刷新状态核查')
  expect(fetch).toHaveBeenCalledTimes(2)
})

const archiveEntry = { run_id: run.run_id, owner_id: run.owner_id, request_id: run.request_id, record_count: 5,
  report_sha256: 'a'.repeat(64), receipt_sha256: 'd'.repeat(64), configuration: { ...workspace.configuration, name: 'configured' }, scope: run.scope }
const archiveIndex = { schema: 'nbw-archive-index-v1', runs: [archiveEntry], invalid_receipts: 0, unarchived_runs: 0, scope: run.scope }

it('历史归档使用稳定run与receipt，保留原请求并且只发GET', async () => {
  vi.mocked(fetchReadJson).mockResolvedValueOnce(archiveIndex).mockResolvedValueOnce({ request_id: run.request_id, report_sha256: archiveEntry.report_sha256,
    total: 0, offset: 0, records: [], scope: run.scope })
  expect((await fetchBacktestArchive()).runs[0].run_id).toBe(run.run_id)
  await fetchBacktestRecords(run.owner_id, run.request_id, 0, undefined,
    { runId: run.run_id, receiptSha: archiveEntry.receipt_sha256, reportSha: archiveEntry.report_sha256 })
  expect(vi.mocked(fetchReadJson).mock.calls[1][0]).toBe(`/v1/ui/backtest/archive/${run.run_id}/records?offset=0&limit=50&receipt_sha256=${archiveEntry.receipt_sha256}`)
})

it('重复历史run或改变归档报告SHA明确拒绝', async () => {
  vi.mocked(fetchReadJson).mockResolvedValueOnce({ ...archiveIndex, runs: [archiveEntry, archiveEntry] })
  await expect(fetchBacktestArchive()).rejects.toThrow('格式或身份无效')
  vi.mocked(fetchReadJson).mockResolvedValueOnce({ request_id: run.request_id, report_sha256: 'f'.repeat(64), total: 0, offset: 0, records: [], scope: run.scope })
  await expect(fetchBacktestRecords(run.owner_id, run.request_id, 0, undefined,
    { runId: run.run_id, receiptSha: archiveEntry.receipt_sha256, reportSha: archiveEntry.report_sha256 })).rejects.toThrow('格式或身份无效')
})

it('历史配置与目录固定身份和值逐字段一致', async () => {
  vi.mocked(fetchReadJson).mockResolvedValue({ schema: 'nbw-archive-configuration-v1', run_id: run.run_id, request_id: run.request_id,
    report_sha256: archiveEntry.report_sha256, receipt_sha256: archiveEntry.receipt_sha256, installation_sha256: 'e'.repeat(64),
    configuration: { ...archiveEntry.configuration, label: '被替换的配置' }, session_configuration: {}, policy: {}, fee_reserve_cny: '0', fee_source: 'synthetic', scope: run.scope })
  await expect(fetchArchiveConfiguration(archiveEntry)).rejects.toThrow('格式或身份无效')
})

it('归档available必须同时有真实completed回收事实与完整receipt摘要', async () => {
  vi.mocked(fetchReadJson).mockResolvedValue({ ...workspace, runs: [{ ...run, archive_status: 'available', archive_reason: '已归档', archive_receipt_sha256: null }] })
  await expect(fetchBacktestWorkspace()).rejects.toThrow('格式或身份无效')
})

it('显式归档重试只POST原owner/request的archive入口', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...run, archive_status: 'unknown', archive_reason: '归档尚未确认', archive_receipt_sha256: null }), { status: 200 }))
  vi.stubGlobal('fetch', fetch)
  await commandBacktest(run.owner_id, run.request_id, false, true)
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(fetch.mock.calls[0][0]).toBe(`/v1/ui/backtest/runs/${run.request_id}/archive`)
})
