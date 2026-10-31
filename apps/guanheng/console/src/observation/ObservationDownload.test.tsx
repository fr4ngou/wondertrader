import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ObservationDownload } from './ObservationDownload'
import { downloadObservation } from './api'

vi.mock('./api', async original => ({ ...await original<typeof import('./api')>(), downloadObservation: vi.fn() }))
beforeEach(() => {
  vi.stubGlobal('URL', class extends globalThis.URL { static createObjectURL = vi.fn(() => 'blob:fixture'); static revokeObjectURL = vi.fn() })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.mocked(downloadObservation).mockReset() })

it('读取失败保持页面，用户重试后下载完整文件并释放对象URL', async () => {
  vi.mocked(downloadObservation).mockRejectedValueOnce(new Error('观察读取超过本次时间')).mockResolvedValueOnce(new Blob(['complete']))
  render(<ObservationDownload params={{ metric_id: 'first', format: 'csv' }} filename="指标.csv">下载 CSV</ObservationDownload>)
  fireEvent.click(screen.getByRole('button', { name: '下载 CSV' }))
  expect(await screen.findByText(/本次未生成下载文件/)).toBeVisible()
  expect(URL.createObjectURL).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: '下载 CSV' }))
  await waitFor(() => expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledOnce())
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:fixture')
  expect(screen.queryByText(/本次未生成下载文件/)).toBeNull()
})

it('切换查询与退出页面取消原下载，旧读取不会生成文件或污染新查询', async () => {
  const signals: AbortSignal[] = []
  vi.mocked(downloadObservation).mockImplementation((_params, signal) => new Promise((_resolve, reject) => {
    signals.push(signal!); signal!.addEventListener('abort', () => reject(new Error('cancelled')))
  }))
  const view = render(<ObservationDownload params={{ metric_id: 'first', format: 'csv' }} filename="first.csv">下载 CSV</ObservationDownload>)
  fireEvent.click(screen.getByRole('button', { name: '下载 CSV' }))
  expect(screen.getByRole('button', { name: '正在准备下载…' })).toBeDisabled()
  view.rerender(<ObservationDownload params={{ metric_id: 'second', format: 'csv' }} filename="second.csv">下载 CSV</ObservationDownload>)
  expect(signals[0].aborted).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: '下载 CSV' }))
  view.unmount()
  expect(signals[1].aborted).toBe(true)
  expect(URL.createObjectURL).not.toHaveBeenCalled()
})
