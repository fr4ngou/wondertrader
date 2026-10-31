import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { DataAssets } from './DataAssets'
import { ObservationExports } from './ObservationExports'
import type { Catalog, Definition } from './types'

const state = vi.hoisted(() => ({ fail: false }))
const coverage = { start: '2026-10-01', end: '2026-10-16', observations: 12 }
const definition: Definition = { id: 'opaque_metric', board: 'valuation', label: '平均市净率', source: 'baostock.pb',
  source_url: 'https://example.invalid/source', frequency: 'daily', coverage, unit: '倍', primary_field: 'raw_key',
  field_schema: { raw_key: { label: '市净率', unit: '倍' } }, parameters: false, lines: [],
  formula: '有效股票市净率的算术平均', reading: '结合历史位置阅读', limitations: ['历史覆盖有限'] }
const catalog: Catalog = { snapshot_id: 'a'.repeat(64), published_at: '2026-10-17T00:00:00Z', boards: [],
  datasets: [{ ...definition, dataset_version: 'b'.repeat(64) }, { ...definition, id: 'second_metric', label: '月末估值',
    frequency: 'monthly', source: 'shenwan.801003', coverage: { start: '2025-01-01', end: '2025-12-31', observations: 12 }, dataset_version: 'c'.repeat(64) }],
  preferences: { default_board: 'valuation', default_datasets: {} } }
vi.mock('./api', async importOriginal => ({ ...await importOriginal<typeof import('./api')>(),
  getDefinition: vi.fn(async () => { if (state.fail) throw new Error('说明暂时不可用'); return { definition } }),
  read: vi.fn(() => { throw new Error('日常说明页面应按需读取指标定义') }),
  downloadObservation: vi.fn(async () => new Blob(['fixture'])),
}))
let query: QueryClient
beforeEach(() => {
  vi.stubGlobal('URL', class extends globalThis.URL { static createObjectURL = vi.fn(() => 'blob:fixture'); static revokeObjectURL = vi.fn() })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
})
afterEach(() => { cleanup(); query?.clear(); state.fail = false; vi.clearAllMocks(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
function open(component = <DataAssets catalog={catalog} />) {
  query = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={query}><MemoryRouter>{component}</MemoryRouter></QueryClientProvider>)
}

it('以中文说明选择字段，隐藏资产身份、字段代码及原始JSON', async () => {
  const view = open()
  expect(await screen.findByText('有效股票市净率的算术平均')).toBeVisible()
  expect(screen.getByText('市净率（倍）')).toBeVisible()
  expect(screen.getByRole('link', { name: '查看来源页面' })).toHaveAttribute('href', definition.source_url)
  expect(view.container.textContent).not.toMatch(/[a-f0-9]{64}|opaque_metric|raw_key|baostock\.pb|资产ID|SHA-256/)
  expect(view.container.querySelector('pre')).toBeNull()
  const api = await import('./api')
  expect(api.read).not.toHaveBeenCalled()
  fireEvent.change(screen.getByLabelText('搜索指标说明'), { target: { value: '申万' } })
  const table = screen.getByRole('table')
  expect(within(table).getByText('月末估值')).toBeVisible()
  expect(within(table).queryByRole('button', { name: '平均市净率' })).toBeNull()
  fireEvent.change(screen.getByLabelText('按频率筛选'), { target: { value: 'daily' } })
  expect(screen.getByText('没有符合条件的指标，请调整搜索或频率。')).toBeVisible()
})

it('同指标重读失败保留原说明及成功时间，并通过用户重读恢复', async () => {
  open(); await screen.findByText(definition.formula)
  state.fail = true
  await act(async () => { await query.refetchQueries({ queryKey: ['observation', 'definition'] }) })
  expect(await screen.findByText(/指标说明读取失败/)).toBeVisible()
  expect(screen.getByText(definition.formula)).toBeVisible()
  expect(document.querySelector('time')).toHaveAttribute('datetime')
  state.fail = false
  fireEvent.click(screen.getByRole('button', { name: '重新读取指标说明' }))
  await screen.findByText(definition.formula)
})

it('导出固定同一快照、指标和日期，切换指标恢复其覆盖，错误范围阻止下载', async () => {
  const view = open(<ObservationExports catalog={catalog} />)
  const api = await import('./api')
  fireEvent.click(screen.getByRole('button', { name: '下载 CSV' }))
  expect(api.downloadObservation).toHaveBeenLastCalledWith({ metric_id: 'opaque_metric', snapshot_id: catalog.snapshot_id,
    start: coverage.start, end: coverage.end, format: 'csv' }, expect.any(AbortSignal))
  await screen.findByRole('button', { name: '下载 CSV' })
  expect(view.container.textContent).not.toMatch(/[a-f0-9]{64}|GET \/v1|opaque_metric/)
  fireEvent.change(screen.getByLabelText('导出开始日期'), { target: { value: '2026-10-17' } })
  expect(screen.queryByRole('button', { name: '下载 CSV' })).toBeNull()
  fireEvent.change(screen.getByLabelText('导出指标'), { target: { value: 'second_metric' } })
  fireEvent.click(screen.getByRole('button', { name: '下载 JSONL' }))
  expect(api.downloadObservation).toHaveBeenLastCalledWith({ metric_id: 'second_metric', snapshot_id: catalog.snapshot_id,
    start: '2025-01-01', end: '2025-12-31', format: 'jsonl' }, expect.any(AbortSignal))
  await screen.findByRole('button', { name: '下载 JSONL' })
  fireEvent.change(screen.getByLabelText('导出结束日期'), { target: { value: '' } })
  expect(screen.queryByRole('button', { name: '下载 JSONL' })).toBeNull()
})

it('空目录给出可理解的说明和导出状态', () => {
  open(<><DataAssets catalog={{ ...catalog, datasets: [] }} /><ObservationExports catalog={{ ...catalog, datasets: [] }} /></>)
  expect(screen.getByText('当前尚无已发布的指标，请查看更新与缺口。')).toBeVisible()
  expect(screen.getByText('当前尚无可导出的指标，请查看更新与缺口。')).toBeVisible()
  expect(screen.queryByRole('link')).toBeNull()
})
