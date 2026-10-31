import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import StrategyConfigurationWorkspace from './StrategyConfigurationWorkspace'
import * as api from './strategyConfigurationApi'
import fixture from './strategy-configuration.fixture.json'
import unicodeFixture from './strategy-configuration-unicode.fixture.json'

vi.mock('./strategyConfigurationApi', async original => ({ ...await original<typeof api>(), fetchConfigurationWorkspace: vi.fn(),
  validateStrategyConfiguration: vi.fn(), saveStrategyConfiguration: vi.fn(), lookupConfigurationRequest: vi.fn() }))
afterEach(() => { cleanup(); vi.resetAllMocks() })
beforeEach(() => {
  vi.mocked(api.fetchConfigurationWorkspace).mockResolvedValue(api.decodeConfigurationWorkspace(structuredClone(fixture)))
  vi.mocked(api.validateStrategyConfiguration).mockImplementation(async configuration => ({ schema: 'guanheng.strategy-configuration-validation.v1',
    configuration: structuredClone(configuration), configuration_sha256: 'd'.repeat(64), validation_time: '2026-10-28T01:00:00Z', validity: 'expired',
    qualification: 'configuration-only; data/runtime/execution-unqualified' }))
})
function show(client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } })) {
  const view = render(<QueryClientProvider client={client}><StrategyConfigurationWorkspace /></QueryClientProvider>)
  return { client, ...view }
}
async function load() {
  fireEvent.change(await screen.findByRole('combobox', { name: '策略版本' }), { target: { value: 'resonance-regime-v1@1.2.0' } })
  fireEvent.click(screen.getByRole('button', { name: '加载明确标注的合成示例' }))
}
async function validate() {
  fireEvent.click(screen.getByRole('button', { name: '调用唯一业务核校验' }))
  await screen.findByText('配置内部规则校验通过。配置有效期已结束。')
}

it.each(unicodeFixture.names.map(name => ({ name, points: Array.from(name).length })))('共用非BMP名称完整输入、校验及保存版本回读$points', async ({ name }) => {
  const value = api.decodeConfigurationWorkspace(structuredClone(fixture))
  value.store!.revision = 1
  value.store!.versions = [{ revision: 1, request_id: 'c'.repeat(32), request_sha256: 'e'.repeat(64),
    configuration_sha256: 'd'.repeat(64), configuration: { ...value.catalog[0].example, config_revision: name }, saved_at: '2026-10-28T01:00:00Z' }]
  vi.mocked(api.fetchConfigurationWorkspace).mockResolvedValue(api.decodeConfigurationWorkspace(value))
  show()
  await screen.findByText(`版本 1 · ${name}`)
  await load()
  const input = screen.getByLabelText('业务修订名称')
  expect(input).not.toHaveAttribute('maxlength')
  fireEvent.change(input, { target: { value: name } })
  expect(input).toHaveValue(name)
  await validate()
  expect(vi.mocked(api.validateStrategyConfiguration).mock.calls[0][0].config_revision).toBe(name)
  fireEvent.change(input, { target: { value: unicodeFixture.names[1] + '尾' } })
  expect(input).toHaveValue(unicodeFixture.names[1])
})

it('完整配置主流程展示实际预算/映射，经唯一核后保存新版本', async () => {
  vi.mocked(api.saveStrategyConfiguration).mockImplementation(async intent => ({ revision: 1, request_id: intent.request_id,
    configuration: intent.configuration, configuration_sha256: intent.configuration_sha256, request_sha256: 'e'.repeat(64), saved_at: '2026-10-28T01:01:00Z' }))
  show()
  await screen.findByText('尚未保存配置版本。空目录保持空状态，可主动加载合成示例。')
  expect(screen.queryByRole('button', { name: '调用唯一业务核校验' })).not.toBeInTheDocument()
  await load()
  expect(screen.getByLabelText('策略预算权重')).toHaveValue(.8)
  expect(screen.getByLabelText('kc_composite 信号证券')).toHaveValue('589680.SH')
  expect(screen.getByLabelText('kc_composite 执行证券')).toHaveValue('589000.SH')
  expect(screen.getByRole('button', { name: '保存为App配置新版本' })).toBeDisabled()
  await validate()
  fireEvent.click(screen.getByRole('button', { name: '保存为App配置新版本' }))
  await screen.findByText('App配置版本已保存；实际运行生效尚待宿主确认。')
  expect(api.validateStrategyConfiguration).toHaveBeenCalledTimes(1)
  expect(api.saveStrategyConfiguration).toHaveBeenCalledTimes(1)
  expect(vi.mocked(api.saveStrategyConfiguration).mock.calls[0][0].configuration.budget_weight).toBe(.8)
})

it('修改参数撤销旧校验资格，非法参数展示中文拒绝', async () => {
  show(); await load(); await validate()
  fireEvent.change(screen.getByLabelText('策略预算权重'), { target: { value: '1' } })
  expect(screen.getByRole('button', { name: '保存为App配置新版本' })).toBeDisabled()
  vi.mocked(api.validateStrategyConfiguration).mockRejectedValue(new api.ConfigurationWriteError('rejected'))
  fireEvent.click(screen.getByRole('button', { name: '调用唯一业务核校验' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('未通过业务校验')
  expect(api.saveStrategyConfiguration).not.toHaveBeenCalled()
})

it('默认根未配置仍可选参数校验，保存保持关闭', async () => {
  vi.mocked(api.fetchConfigurationWorkspace).mockResolvedValue({ ...api.decodeConfigurationWorkspace(fixture), available: false,
    editable: false, store: null, reason: '策略配置保存尚未配置；可先查看版本和校验业务参数' })
  show(); await load(); await validate()
  expect(screen.getByRole('button', { name: '保存为App配置新版本' })).toBeDisabled()
})

it('响应丢失跨卸载保留唯一请求，以GET核同一请求并恢复', async () => {
  vi.mocked(api.saveStrategyConfiguration).mockRejectedValue(new api.ConfigurationWriteError('unknown'))
  vi.mocked(api.lookupConfigurationRequest).mockImplementation(async intent => ({ revision: 1, request_id: intent.request_id,
    configuration: intent.configuration, configuration_sha256: intent.configuration_sha256, request_sha256: 'e'.repeat(64), saved_at: '2026-10-28T01:01:00Z' }))
  const view = show(); await load(); await validate()
  fireEvent.click(screen.getByRole('button', { name: '保存为App配置新版本' }))
  await screen.findByRole('heading', { name: '原保存请求待核查' })
  await waitFor(() => expect(screen.getByRole('button', { name: '按原请求编号核查保存结果' })).toBeEnabled())
  const intent = vi.mocked(api.saveStrategyConfiguration).mock.calls[0][0]
  view.unmount(); show(view.client)
  fireEvent.click(await screen.findByRole('button', { name: '按原请求编号核查保存结果' }))
  await screen.findByText('已按原请求编号核实保存成功；实际运行生效尚待宿主确认。')
  expect(api.lookupConfigurationRequest).toHaveBeenCalledWith(intent)
  expect(api.saveStrategyConfiguration).toHaveBeenCalledTimes(1)
})

it('CAS冲突后暂停保存，明确重读后重新校验', async () => {
  vi.mocked(api.saveStrategyConfiguration).mockRejectedValue(new api.ConfigurationWriteError('conflict'))
  show(); await load(); await validate()
  fireEvent.click(screen.getByRole('button', { name: '保存为App配置新版本' }))
  await screen.findByText('配置版本已在其他页面变化，请重新读取当前版本后确认。')
  expect(screen.getByRole('button', { name: '保存为App配置新版本' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: '重新读取配置版本' }))
  await waitFor(() => expect(screen.queryByText('配置版本已在其他页面变化，请重新读取当前版本后确认。')).not.toBeInTheDocument())
  expect(screen.getByRole('button', { name: '保存为App配置新版本' })).toBeDisabled()
})

it('核查尚未见回执时保留原请求并继续暂停新增保存', async () => {
  vi.mocked(api.saveStrategyConfiguration).mockRejectedValue(new api.ConfigurationWriteError('unknown'))
  vi.mocked(api.lookupConfigurationRequest).mockResolvedValue(null)
  show(); await load(); await validate()
  fireEvent.click(screen.getByRole('button', { name: '保存为App配置新版本' }))
  const check = await screen.findByRole('button', { name: '按原请求编号核查保存结果' })
  await waitFor(() => expect(check).toBeEnabled())
  fireEvent.click(check)
  await screen.findByText('本次读取尚未见到原请求的持久回执，原请求继续保留，请在服务恢复后继续核查。')
  expect(screen.getByRole('button', { name: '保存为App配置新版本' })).toBeDisabled()
  expect(api.saveStrategyConfiguration).toHaveBeenCalledTimes(1)
})
