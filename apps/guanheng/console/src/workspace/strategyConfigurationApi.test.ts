import { afterEach, expect, it, vi } from 'vitest'
import {
  ConfigurationWriteError, decodeConfigurationWorkspace, fetchConfigurationWorkspace, lookupConfigurationRequest,
  saveStrategyConfiguration, validateStrategyConfiguration,
} from './strategyConfigurationApi'
import type { ConfigurationReceipt, SaveConfigurationIntent } from './strategyConfigurationApi'
import fixture from './strategy-configuration.fixture.json'
import unicodeFixture from './strategy-configuration-unicode.fixture.json'

afterEach(() => { vi.unstubAllGlobals() })
const prefix = 'guanheng.strategy-configuration-'
const current = () => decodeConfigurationWorkspace(structuredClone(fixture))
const intent = (): SaveConfigurationIntent => ({ store_id: 'b'.repeat(32), expected_revision: 0, request_id: 'c'.repeat(32),
  configuration: current().catalog[0].example, configuration_sha256: 'd'.repeat(64) })
const receipt = (): ConfigurationReceipt => ({ revision: 1, request_id: 'c'.repeat(32), request_sha256: 'e'.repeat(64),
  configuration_sha256: 'd'.repeat(64), configuration: current().catalog[0].example, saved_at: '2026-10-28T01:00:00Z' })
function respond(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }) }

it.each(unicodeFixture.names.map(name => ({ name, points: Array.from(name).length })))('端点共用非BMP样本按码点读取保存版本，长度$points', ({ name }) => {
  const saved = receipt()
  saved.configuration.config_revision = name
  const value = { ...structuredClone(fixture), store: { ...fixture.store, revision: 1, versions: [saved] } }
  expect(decodeConfigurationWorkspace(value).store?.versions[0].configuration.config_revision).toBe(name)
})

it.each(['\ud800', '\udc00', unicodeFixture.names[1] + '尾'])('孤立代理及超128码点响应拒绝', name => {
  const incoming = structuredClone(fixture)
  incoming.catalog[0].example.config_revision = name
  expect(() => decodeConfigurationWorkspace(incoming)).toThrow('格式或身份无效')
})

it('读取真实形状的空工作区，副本与输入分离', async () => {
  const incoming = structuredClone(fixture)
  const parsed = decodeConfigurationWorkspace(incoming)
  incoming.catalog[0].example.budget_weight = .1
  expect(parsed.catalog[0].example.budget_weight).toBe(.8)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond(fixture)))
  expect((await fetchConfigurationWorkspace()).store?.revision).toBe(0)
})

it.each([
  { runtime_effect: true }, { editable: 'true' }, { owner_id: ['a'.repeat(32)] }, { max_versions: 33 },
  { store: { ...fixture.store, revision: 1 } }, { reason: { private: true } }, { extra: 'unsupported' },
])('拒绝资格或类型矛盾 %j', change => {
  expect(() => decodeConfigurationWorkspace({ ...structuredClone(fixture), ...change })).toThrow('格式或身份无效')
})

it('校验请求只带纯配置，返回过期说明且无部署路径', async () => {
  const expected = intent().configuration
  const fetch = vi.fn().mockResolvedValue(respond({ schema: prefix + 'validation.v1', configuration: expected,
    configuration_sha256: 'd'.repeat(64), validation_time: '2026-10-28T01:00:00Z', validity: 'expired',
    qualification: 'configuration-only; data/runtime/execution-unqualified' }))
  vi.stubGlobal('fetch', fetch)
  expect((await validateStrategyConfiguration(expected)).validity).toBe('expired')
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ schema: prefix + 'validation-request.v1', configuration: expected })
})

it('单次保存核请求、配置摘要及新版本，未自动重试', async () => {
  const fetch = vi.fn().mockResolvedValue(respond({ schema: prefix + 'saved.v1', store_id: 'b'.repeat(32), receipt: receipt(), runtime_effect: false }))
  vi.stubGlobal('fetch', fetch)
  expect((await saveStrategyConfiguration(intent())).revision).toBe(1)
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(JSON.parse(fetch.mock.calls[0][1].body).configuration_sha256).toBeUndefined()
})

it.each([409, 422, 503])('保存HTTP %s统一固定说明并保留结果语义', async status => {
  const fetch = vi.fn().mockResolvedValue(respond({ detail: 'private secret path' }, status))
  vi.stubGlobal('fetch', fetch)
  const error = await saveStrategyConfiguration(intent()).catch(error => error)
  expect(error).toBeInstanceOf(ConfigurationWriteError)
  expect(error.state).toBe(status === 409 ? 'conflict' : status === 422 ? 'rejected' : 'unknown')
  expect(error.message).not.toContain('private')
  expect(fetch).toHaveBeenCalledTimes(1)
})

it('成功响应身份矛盾保持未知，原请求GET只核查不写', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(respond({ schema: prefix + 'saved.v1', store_id: 'b'.repeat(32),
    receipt: { ...receipt(), request_id: 'f'.repeat(32) }, runtime_effect: false }))
    .mockResolvedValueOnce(respond({ schema: prefix + 'request.v1', store_id: 'b'.repeat(32), request_id: 'c'.repeat(32), status: 'saved', receipt: receipt() }))
  vi.stubGlobal('fetch', fetch)
  await expect(saveStrategyConfiguration(intent())).rejects.toMatchObject({ state: 'unknown' })
  expect((await lookupConfigurationRequest(intent()))?.request_id).toBe('c'.repeat(32))
  expect(fetch.mock.calls[1][1].method).toBeUndefined()
  expect(String(fetch.mock.calls[1][0])).toContain('/requests/' + 'c'.repeat(32))
})

it('缺少原请求回执只返回未确认，不伪造成功', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond({ schema: prefix + 'request.v1', store_id: 'b'.repeat(32), request_id: 'c'.repeat(32), status: 'absent', receipt: null })))
  expect(await lookupConfigurationRequest(intent())).toBeNull()
})

it('JSON字段顺序变化保留同一配置身份，非法日期响应拒绝', async () => {
  const saved = receipt()
  saved.configuration = Object.fromEntries(Object.entries(saved.configuration).reverse()) as typeof saved.configuration
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(respond({ schema: prefix + 'saved.v1', store_id: 'b'.repeat(32), receipt: saved, runtime_effect: false })))
  expect((await saveStrategyConfiguration(intent())).revision).toBe(1)
  const bad = structuredClone(fixture)
  bad.catalog[0].example.valid_until = '2024-02-30T00:00:00Z'
  expect(() => decodeConfigurationWorkspace(bad)).toThrow('格式或身份无效')
})
