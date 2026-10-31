import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { fetchReadJson } from '../api'
import { fetchBacktestDay } from './backtestApi'
import { validateHistoricalSummary } from './backtestHistorical'
import HistoricalBacktestSummary from './HistoricalBacktestSummary'
import fixture from './backtest-historical-day.fixture.json'
import performanceFixture from './backtest-historical-performance.fixture.json'
import { validatePerformance } from './backtestPerformanceApi'
import { backtestMoney } from './backtestMoney'

vi.mock('../api', () => ({ fetchReadJson: vi.fn() }))
afterEach(() => { cleanup(); vi.resetAllMocks() })
const read = () => fetchBacktestDay('a'.repeat(32), fixture.request_id, fixture.index, undefined, fixture.report_sha256, fixture.record.trading_date)

it('实际历史绩效保留回测范围，错配严格报告拒绝', () => {
  expect(validatePerformance(performanceFixture.performance, performanceFixture.entry).report_schema).toBe('nsb-historical-report-v1')
  expect(() => validatePerformance({ ...performanceFixture.performance, report_schema: 'nsb-report-v2' }, performanceFixture.entry)).toThrow('格式或身份无效')
})

it.each([['1061003.9999999998', '1,061,004.00'], ['-0.004', '0.00'], ['-9.995', '-10.00'],
  ['999999999999999999999.995', '1,000,000,000,000,000,000,000.00']])('金额%s按分显示，完整原文留在报告', (source, expected) => {
  expect(backtestMoney(source)).toBe(expected)
})

it('读取普通安装原生报告的真实当日投影并解释回测假设', async () => {
  vi.mocked(fetchReadJson).mockResolvedValue(fixture)
  const value = await read()
  const summary = validateHistoricalSummary(value.evaluation_summary, fixture.record.trading_date)
  render(<HistoricalBacktestSummary value={summary} />)
  expect(screen.getByRole('heading', { name: '历史日线回测' })).toBeVisible()
  expect(screen.getByText(/2026\/10\/29 01:23:25（上海时间）/)).toBeVisible()
  expect(screen.getByText(/源成交金额单位未知，本次按元解释/)).toBeVisible()
  expect(screen.getByText(/历史首次可知时间和修订记录未知/)).toBeVisible()
})

it.each(['missing-schema', 'wrong-schema', 'qualified', 'missing-model', 'amount', 'source', 'received', 'availability', 'reason'])('拒绝%s导致来源或资格混用', async kind => {
  const value = structuredClone(fixture) as unknown as Record<string, any>
  const summary = value.evaluation_summary
  if (kind === 'missing-schema') delete value.report_schema
  if (kind === 'wrong-schema') value.report_schema = 'nsb-v2-report-v1'
  if (kind === 'qualified') summary.qualified = true
  if (kind === 'missing-model') delete summary.historical_model
  if (kind === 'amount') summary.historical_model.source_amount_unit = 'CNY'
  if (kind === 'source') summary.historical_model.dataset_sha256 = '0'.repeat(64)
  if (kind === 'received') summary.historical_model.received_at = '2025-03-05T07:00:00Z'
  if (kind === 'availability') summary.latest_features[0].observation.market_available_at = summary.knowledge_cutoff
  if (kind === 'reason') summary.qualification_reasons = []
  vi.mocked(fetchReadJson).mockResolvedValue(value)
  await expect(read()).rejects.toThrow('格式或身份无效')
})

it('历史报告预热允许空摘要，已完成记录缺摘要拒绝', async () => {
  const value = structuredClone(fixture) as unknown as Record<string, any>
  value.evaluation_summary = null
  vi.mocked(fetchReadJson).mockResolvedValue(value)
  await expect(read()).rejects.toThrow('格式或身份无效')
  Object.assign(value.record, { status: 'warming_up', capture: null, outcome: null })
  vi.mocked(fetchReadJson).mockResolvedValue(value)
  expect((await read()).evaluation_summary).toBeNull()
})
