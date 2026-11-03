import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import ObservationShell from './ObservationShell'
import type { Catalog, Definition } from './types'

const state = vi.hoisted(() => ({ failure: '', futures: false, empty: false }))
vi.mock('./ObservationChart', () => ({ ObservationChart: () => <div data-testid="chart">固定版本图表</div> }))
const coverage = { start: '2026-10-01', end: '2026-10-16', observations: 2 }
function definition(id: string): Definition {
  return { id, board: id.startsWith('cffex') ? 'cffex' : 'valuation', label: id, frequency: 'daily',
    coverage, parameters: false, primary_field: 'value', lines: [], field_schema: { date: { label: '日期' }, value: { label: '值' } },
    source: '人工样本', source_url: 'https://example.invalid/fixture', unit: '倍', limitations: [], reading: '人工样本', formula: '人工样本' }
}
function catalog(): Catalog {
  const id = state.futures ? 'cffex_if' : 'pb_test', d = definition(id)
  return { snapshot_id: 'a'.repeat(64), published_at: '2026-10-17T00:00:00Z',
    boards: [{ id: d.board, label: d.board }], preferences: { default_board: d.board, default_datasets: { [d.board]: id } },
    datasets: [{ ...d, dataset_version: 'b'.repeat(64) }] }
}
vi.mock('./api', () => ({
  getCatalog: async () => { if (state.failure === 'catalog') throw new Error('目录读取失败'); return catalog() },
  getDefinition: async (id: string) => { if (state.failure === 'definition:' + id) throw new Error('定义读取失败'); return { definition: definition(id) } },
  getSeries: async (id: string) => { if (state.failure === 'series:' + id) throw new Error('指标读取失败'); return { definition: definition(id), rows: state.empty ? [] : [{ date: '2026-10-16', value: 7 }], total: state.empty ? 0 : 1, next_cursor: null } },
  getHistory: async (id: string) => {
    if (state.failure === 'history:' + id) throw new Error('子历史读取失败')
    return { coverage, points: [], aggregation: 'none', raw_count: 2 }
  },
  apiURL: () => '/fixture-export',
  read: async (path: string) => {
    if (state.failure === path) throw new Error('子资料读取失败')
    return path.startsWith('reference/') ? { image: 'data:image/png;base64,AA==', review: { summary: '已读取原图结论' } }
      : { scheduler: { enabled: false }, runs: [{ status: 'partial', completed_at: '2026-10-17T00:00:00Z', sources: [{ source_id: 'fixture-receipt-source', status: 'failed' }] }] }
  },
}))

let active: QueryClient | undefined
afterEach(() => { cleanup(); active?.clear(); active = undefined; state.failure = ''; state.futures = false; state.empty = false })
function open(path = '/observation?metric=pb_test') {
  const query = active = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={query}><MemoryRouter initialEntries={[path]}><ObservationShell /></MemoryRouter></QueryClientProvider>)
  return query
}

it('原图成功后单独资料重读失败，保留原图与结论并可手动恢复', async () => {
  const query = open()
  await screen.findByTestId('chart')
  fireEvent.click(screen.getByRole('button', { name: '原图对照' }))
  await screen.findByRole('img', { name: '用户提供的原始图表' })
  state.failure = 'reference/pb_test'
  await query.refetchQueries({ queryKey: ['observation', 'reference'] })
  await screen.findByText(/原图资料读取失败：子资料读取失败/)
  expect(screen.getByRole('img', { name: '用户提供的原始图表' })).toBeInTheDocument()
  expect(screen.queryByText('已读取原图结论')).toBeNull()
  state.failure = ''
  fireEvent.click(screen.getByRole('button', { name: '重新读取原图资料' }))
  expect(await screen.findByRole('img', { name: '用户提供的原始图表' })).toBeVisible()
})

it.each(['history:pb_test', 'definition:pb_test'])('首次%s失败仍使用序列携带定义绘图', async failure => {
  state.failure = failure
  open()
  expect(await screen.findByTestId('chart')).toBeVisible()
  expect(screen.getByText('7', { selector: 'td' })).toBeVisible()
  expect(await screen.findByText(/读取失败：/)).toBeVisible()
})

it('目录刷新失败保留看板，指标刷新失败保留图表和数据，成功空替换旧图', async () => {
  const query = open()
  await screen.findByTestId('chart')
  state.failure = 'catalog'
  await query.refetchQueries({ queryKey: ['observation', 'catalog'] })
  await screen.findByText(/观察目录读取失败：目录读取失败/)
  expect(screen.getByTestId('chart')).toBeVisible()
  state.failure = 'series:pb_test'
  await query.refetchQueries({ queryKey: ['observation', 'series'] })
  await screen.findByText(/指标数据读取失败：指标读取失败/)
  expect(screen.getByTestId('chart')).toBeVisible()
  expect(screen.getByText('7', { selector: 'td' })).toBeVisible()
  state.failure = ''; state.empty = true
  await query.refetchQueries({ queryKey: ['observation', 'series'] })
  await screen.findByText(/所选日期没有已发布观察/)
  expect(screen.queryByTestId('chart')).not.toBeInTheDocument()
  expect(screen.queryByText('7', { selector: 'td' })).not.toBeInTheDocument()
})

it('切换日期后的首次失败不显示其他日期图表', async () => {
  open(); await screen.findByTestId('chart')
  state.failure = 'series:pb_test'
  fireEvent.change(screen.getByLabelText('起始日期'), { target: { value: '2026-10-15' } })
  await screen.findByText(/指标数据读取失败：指标读取失败/)
  expect(screen.queryByTestId('chart')).not.toBeInTheDocument()
  expect(screen.queryByText('7', { selector: 'td' })).not.toBeInTheDocument()
})

it('期货首次失败仍显示对应期权和其他品种', async () => {
  state.futures = true; state.failure = 'series:cffex_ih'
  open('/observation?metric=cffex_if')
  await screen.findByText(/IH期货读取失败：指标读取失败/)
  await waitFor(() => expect(screen.getAllByTestId('chart')).toHaveLength(7))
})

it.each(['cffex_ih', 'pcr_ho'])('期货组的%s历史失败只影响导航，图表保留并可恢复', async id => {
  state.futures = true
  const query = open('/observation?metric=cffex_if')
  await waitFor(() => expect(screen.getAllByTestId('chart')).toHaveLength(8))
  state.failure = 'history:' + id
  await query.refetchQueries({ queryKey: ['observation', 'history', id] })
  await screen.findByText(/读取失败：子历史读取失败/)
  expect(screen.getAllByTestId('chart')).toHaveLength(8)
  state.failure = ''
  fireEvent.click(screen.getByRole('button', { name: id === 'cffex_ih' ? '重新读取IH期货历史导航' : '重新读取IH期权历史导航' }))
  await waitFor(() => expect(screen.getAllByTestId('chart')).toHaveLength(8))
})

it('更新回执成功后后台失败保留旧回执，手动重读恢复', async () => {
  const query = open('/observation/quality')
  await screen.findByText('其他数据来源')
  expect(document.body.textContent).not.toContain('fixture-receipt-source')
  expect(document.body.textContent).not.toContain('a'.repeat(12))
  state.failure = 'updates'
  await query.refetchQueries({ queryKey: ['observation', 'updates'] })
  await screen.findByText(/更新回执读取失败：子资料读取失败/)
  expect(screen.getByText('其他数据来源')).toBeInTheDocument()
  state.failure = ''
  fireEvent.click(screen.getByRole('button', { name: '重新读取更新回执' }))
  expect(await screen.findByText('其他数据来源')).toBeVisible()
})

it('看板保留原始数据和原图，移除来源与计算说明入口', async () => {
  open(); await screen.findByTestId('chart')
  expect(screen.queryByRole('button', { name: '来源与质量' })).toBeNull()
  expect(screen.queryByRole('button', { name: '怎么算' })).toBeNull()
  expect(screen.getByRole('button', { name: '原始数据' })).toBeVisible()
  expect(screen.getByRole('button', { name: '原图对照' })).toBeVisible()
  expect(document.body.textContent).not.toContain('a'.repeat(12))
})
