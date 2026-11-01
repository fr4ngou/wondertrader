import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { SecurityAutocomplete } from './SecurityAutocomplete'
import { searchSecurities, type SecuritySearchResponse } from './securitySearchApi'

vi.mock('./securitySearchApi', () => ({ searchSecurities: vi.fn() }))
const search = vi.mocked(searchSecurities)
const result = (name = '德龙激光', code = '688170'): SecuritySearchResponse => ({
  schema_version: 'guanheng.security-search.v1', query: code, catalog_id: 'a'.repeat(64), generated_at: '2026-11-01T01:00:00Z',
  results: [{ symbol: `${code}.SH`, code, exchange: 'SH', name, security_type: 'stock',
    pinyin_initials: 'dljg', pinyin_full: 'delongjiguang', match: 'code' }],
})
afterEach(() => { cleanup(); vi.resetAllMocks() })

test('输入代码前缀自动展开名称、代码和类别，点击选择规范代码', async () => {
  search.mockResolvedValue(result())
  const selected = vi.fn()
  render(<SecurityAutocomplete onSelect={selected} />)
  fireEvent.change(screen.getByRole('combobox'), { target: { value: '68817' } })
  const option = await screen.findByRole('option', { name: /德龙激光.*股票.*688170.SH/ })
  expect(search).toHaveBeenCalledWith('68817', expect.any(AbortSignal))
  expect(selected).not.toHaveBeenCalled()
  fireEvent.click(option)
  expect(selected).toHaveBeenCalledWith('688170.SH')
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
})

test('中文输入法确认后才查询，上下键和Enter选择，Escape关闭', async () => {
  search.mockResolvedValue(result())
  const selected = vi.fn()
  render(<SecurityAutocomplete onSelect={selected} />)
  const input = screen.getByRole('combobox')
  fireEvent.compositionStart(input)
  fireEvent.change(input, { target: { value: '德龙' } })
  await act(() => new Promise(resolve => setTimeout(resolve, 230)))
  expect(search).not.toHaveBeenCalled()
  fireEvent.submit(screen.getByRole('search'))
  expect(selected).not.toHaveBeenCalled()
  fireEvent.compositionEnd(input)
  await screen.findByRole('option')
  fireEvent.keyDown(input, { key: 'ArrowUp' })
  expect(screen.getByRole('combobox')).toHaveAttribute('aria-activedescendant', screen.getByRole('option').id)
  fireEvent.submit(screen.getByRole('search'))
  expect(selected).toHaveBeenCalledWith('688170.SH')
  fireEvent.focus(input)
  fireEvent.keyDown(input, { key: 'Escape' })
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
})

test('快速换词取消旧请求，迟到结果不能覆盖新候选，清空关闭', async () => {
  let first!: (value: SecuritySearchResponse) => void
  search.mockImplementationOnce(() => new Promise(resolve => { first = resolve }))
    .mockResolvedValue(result('浦发银行', '600000'))
  render(<SecurityAutocomplete onSelect={vi.fn()} />)
  const input = screen.getByRole('combobox')
  fireEvent.change(input, { target: { value: '68817' } })
  await waitFor(() => expect(search).toHaveBeenCalledTimes(1))
  const previousSignal = search.mock.calls[0][1]!
  fireEvent.change(input, { target: { value: 'pfyh' } })
  expect(previousSignal.aborted).toBe(true)
  await screen.findByRole('option', { name: /浦发银行/ })
  await act(async () => { first(result()) })
  expect(screen.queryByRole('option', { name: /德龙激光/ })).not.toBeInTheDocument()
  fireEvent.change(input, { target: { value: '' } })
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
})

test('空结果与失败分别解释，失焦收起且可重新输入恢复', async () => {
  search.mockResolvedValueOnce({ ...result(), results: [] }).mockRejectedValueOnce(new Error('证券搜索暂不可用'))
    .mockResolvedValue(result())
  render(<SecurityAutocomplete onSelect={vi.fn()} />)
  const input = screen.getByRole('combobox')
  fireEvent.change(input, { target: { value: '不存在' } })
  expect(await screen.findByText(/没有找到匹配证券/)).toBeVisible()
  fireEvent.change(input, { target: { value: '德龙' } })
  expect(await screen.findByRole('alert')).toHaveTextContent('证券搜索暂不可用')
  fireEvent.blur(input, { relatedTarget: document.body })
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  fireEvent.change(input, { target: { value: '68817' } })
  expect(await screen.findByRole('option')).toHaveTextContent('德龙激光')
})

test('同词重新打开后读取失败保留成功候选，继续允许选择', async () => {
  search.mockResolvedValueOnce(result()).mockRejectedValueOnce(new Error('搜索刷新失败'))
  const selected = vi.fn()
  render(<SecurityAutocomplete onSelect={selected} />)
  const input = screen.getByRole('combobox')
  fireEvent.change(input, { target: { value: '68817' } })
  await screen.findByRole('option')
  fireEvent.keyDown(input, { key: 'Escape' })
  fireEvent.focus(input)
  expect(await screen.findByRole('alert')).toHaveTextContent('保留上次同词搜索结果')
  fireEvent.click(screen.getByRole('option'))
  expect(selected).toHaveBeenCalledWith('688170.SH')
})
