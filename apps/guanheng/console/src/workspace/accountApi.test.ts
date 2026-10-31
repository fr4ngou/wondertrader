import { afterEach, expect, it, vi } from 'vitest'
import { AccountReadBusyError, fetchAccountOverview, type AccountOverviewV1 } from './accountApi'
import sourceFixture from './account.fixture.json'

afterEach(() => vi.unstubAllGlobals())
const fixture = () => structuredClone(sourceFixture) as AccountOverviewV1
const respond = (value: unknown) => vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(value))))

it.each(['9007199254740992', '9007199254740993'])('旧来源代际%s超出可精确表示范围，整轮拒绝而不混同身份', async generation => {
  const wire = JSON.stringify(fixture()).replaceAll('"generation":1', '"generation":' + generation)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(wire)))
  await expect(fetchAccountOverview()).rejects.toThrow('账户数据格式无效')
})

it('接纳实际后端合成投影，保留零、来源未知和逐批时间', async () => {
  const value = fixture()
  value.groups.account.rows[0].fields.available.value = 0
  respond(value)
  const result = await fetchAccountOverview()
  expect(result.groups.account.rows[0].fields.available.value).toBe(0)
  expect(result.groups.position.rows[0].fields.frozen.value).toBeNull()
  expect(result.groups.position.execution_finished_at).toBe(value.groups.position.execution_finished_at)
})

it('拒绝将未完成批次附带的记录解释成有效持仓', async () => {
  const value = fixture()
  value.groups.position.status = 'unavailable'
  respond(value)
  await expect(fetchAccountOverview()).rejects.toThrow('账户数据格式无效')
})

it('拒绝present空值和非法来源身份，保留读取失败', async () => {
  const value = fixture()
  value.groups.position.rows[0].fields.quantity.value = null
  respond(value)
  await expect(fetchAccountOverview()).rejects.toThrow('账户数据格式无效')
  const identity = fixture()
  identity.groups.position.source!.generation = 0
  respond(identity)
  await expect(fetchAccountOverview()).rejects.toThrow('账户数据格式无效')
})

it('不接受无界或过小的来源预算，也不触发网络读取', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  await expect(fetchAccountOverview(undefined, Infinity)).rejects.toThrow('账户读取预算无效')
  await expect(fetchAccountOverview(undefined, 0)).rejects.toThrow('账户读取预算无效')
  expect(fetchMock).not.toHaveBeenCalled()
})

it('容量满额保留账户繁忙原因，丢弃未经审核的服务端正文', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async () => new Response('{"detail":"internal-secret"}', { status: 429 })))
  await expect(fetchAccountOverview()).rejects.toBeInstanceOf(AccountReadBusyError)
  await expect(fetchAccountOverview()).rejects.toThrow('账户读取繁忙，请等待本轮结束后刷新')
})
