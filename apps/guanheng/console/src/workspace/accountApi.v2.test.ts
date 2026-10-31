import { afterEach, expect, it, vi } from 'vitest'
import { fetchAccountOverview, validateAccountOverview, type AccountOverviewV1, type AccountOverviewV2 } from './accountApi'
import oldFixture from './account.fixture.json'
import shmFixture from './account-v2.fixture.json'

// 合成公开DTO；不代表HTTP/原生/SDK生产来源资格。本轮仅定义，未执行。
afterEach(() => vi.unstubAllGlobals())
const fixture = () => structuredClone(shmFixture) as AccountOverviewV2
const objectAt = (root: unknown, path: string[]) => {
  let value = root
  for (const key of path) value = (value as Record<string, unknown>)[key]
  return value as Record<string, unknown>
}
const set = (path: string[], value: unknown) => (root: unknown) => {
  objectAt(root, path.slice(0, -1))[path[path.length - 1]] = value
}
const extra = (path: string[], values: Record<string, unknown>) => (root: unknown) => Object.assign(objectAt(root, path), values)
const src = ['groups', 'position', 'source']
const transport = [...src, 'transport']
const broker = [...src, 'broker_session']

it('旧DTO1维持独立原形状，新DTO2保留运输和券商登录unknown', () => {
  const old = validateAccountOverview(structuredClone(oldFixture)) as AccountOverviewV1
  expect(old.schema_version).toBe('1.0')
  expect(Object.keys(old.groups.position.source!)).toEqual(['kind', 'account_label', 'agent_id', 'environment', 'session_id', 'generation'])
  const value = validateAccountOverview(fixture())
  expect(value.schema_version).toBe('2.0')
  if (value.schema_version !== '2.0') throw new Error('expected synthetic DTO2')
  expect(value.groups.position.source!.transport.route.route_epoch).toBe(17)
  expect(value.groups.position.source!.broker_session).toEqual({ availability: 'unknown', value: null, reason: '未取得券商登录会话证据' })
  expect(value.groups.position.source).not.toHaveProperty('session_id')
  expect(value.groups.account.rows[0].fields.total_asset.value).toBe(123456.789)
})

it.each([
  ['未知版次', set(['schema_version'], '3.0')], ['数组版次', set(['schema_version'], ['2.0'])],
  ['顶层数组状态', set(['status'], ['complete'])], ['组数组状态', set(['groups', 'position', 'status'], ['complete'])],
  ['字段数组资格', set(['groups', 'position', 'rows', '0', 'fields', 'quantity', 'availability'], ['present'])],
  ['v2装旧source', set(src, structuredClone(oldFixture.groups.position.source))],
  ['v1装新source', set(['schema_version'], '1.0')], ['环境越界', set([...src, 'environment'], 'paper')],
  ['transport数组', set(transport, [])], ['route数组', set([...transport, 'route'], [])],
  ['epoch布尔', set([...transport, 'route', 'route_epoch'], true)], ['epoch字符串', set([...transport, 'route', 'route_epoch'], '17')],
  ['epoch负值', set([...transport, 'route', 'route_epoch'], -1)], ['epoch失真', set([...transport, 'route', 'route_epoch'], 2 ** 53)],
  ['Host错长度', set([...transport, 'host_instance_id'], 'a'.repeat(31))], ['代际大写hex', set([...transport, 'transport_generation'], 'B'.repeat(32))],
  ['摘要错类型', set([...transport, 'capability_sha256'], ['c'.repeat(64)])],
  ['路由空', set([...transport, 'route', 'route_id'], '')], ['路由超128码点', set([...transport, 'route', 'route_id'], 'x'.repeat(129))],
  ['路由surrogate', set([...transport, 'route', 'executor_id'], '\ud800')],
  ['登录冒充present', set([...broker, 'availability'], 'present')], ['登录代伪造', set([...broker, 'value'], 'broker-secret-session')],
  ['登录原因改写', set([...broker, 'reason'], '已经登录')], ['非掩码账号', set([...src, 'account_label'], 'PRIVATE_ACCOUNT_123456')],
  ['错误掩码宽度', set([...src, 'account_label'], '****12345')],
  ['账号C1', set([...src, 'account_label'], '****ab\u0085d')], ['账号surrogate', set([...src, 'account_label'], '****ab\ud800d')],
] as const)('拒绝混版与错误类型：%s', (_label, mutate) => {
  const value = fixture(); mutate(value)
  expect(() => validateAccountOverview(value)).toThrow('账户数据格式无效')
})

it.each([
  ['顶层原账号', extra([], { account_id: 'private-account' })],
  ['组原B', extra(['groups', 'position'], { transport_binding: {} })],
  ['source原账号', extra(src, { account_id: 'private-account' })],
  ['source旧session', extra(src, { session_id: 'old-session' })],
  ['source旧代际', extra(src, { generation: 17 })],
  ['transport完整B', extra(transport, { schema_version: '1.0', journal_generation: null })],
  ['transport私有路径', extra(transport, { path: 'private-path' })],
  ['route额外参数', extra([...transport, 'route'], { cursor: 'private' })],
  ['broker额外字段', extra(broker, { secret: 'private-secret' })],
  ['close额外内容', extra(['close'], { stderr: 'private-stderr' })],
  ['多余组', extra(['groups'], { audit: {} })],
  ['原行透传', extra(['groups', 'position', 'rows', '0'], { raw: {} })],
  ['金融field额外键', extra(['groups', 'position', 'rows', '0', 'fields', 'quantity'], { raw: 700 })],
] as const)('闭合公开DTO拒绝额外键：%s', (_label, mutate) => {
  const value = fixture(); mutate(value)
  expect(() => validateAccountOverview(value)).toThrow('账户数据格式无效')
})

it('DTO1拒绝装入DTO2字段与数组状态，保留原公开类型', () => {
  const value = structuredClone(oldFixture)
  Object.assign(value.groups.position.source, { transport: fixture().groups.position.source!.transport })
  expect(() => validateAccountOverview(value)).toThrow('账户数据格式无效')
  const arrays = structuredClone(oldFixture)
  set(['close', 'status'], ['complete'])(arrays)
  expect(() => validateAccountOverview(arrays)).toThrow('账户数据格式无效')
})

it('按Unicode码点接纳128个非BMP路由字符和四码点账号后缀', () => {
  const value = fixture()
  value.groups.position.source!.transport.route.route_id = '\u{1f642}'.repeat(128)
  value.groups.position.source!.account_label = '****' + '\u{1f642}'.repeat(4)
  expect(validateAccountOverview(value).schema_version).toBe('2.0')
})

it('来源未取得的不可用组接受null，完整空list与失败分开', () => {
  const empty = fixture(); empty.groups.position.rows = []
  expect(validateAccountOverview(empty).groups.position.status).toBe('complete')
  const partial = fixture(); partial.status = 'partial'
  Object.assign(partial.groups.account, { status: 'unavailable', rows: [], source: null, reason: '本轮资金未取得' })
  expect(validateAccountOverview(partial).groups.account.source).toBeNull()
})

it('fetch使用唯一校验，坏结构固定去敏且单次读取不重发', async () => {
  const value = fixture(); extra(src, { secret: 'private-secret-value' })(value)
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(value)))
  vi.stubGlobal('fetch', fetchMock)
  await expect(fetchAccountOverview()).rejects.toThrow('账户数据格式无效，请重新读取')
  expect(fetchMock).toHaveBeenCalledTimes(1)
})


it.each([
  ['关闭失败仍称完整', set(['close', 'status'], 'failed')], ['未join仍称完整', set(['close', 'joined'], false)],
  ['worker仍活仍称完整', set(['close', 'worker_live'], true)], ['非零退出仍称完整', set(['close', 'exit_code'], 3)],
  ['未知源码错误仍称完整', set(['close', 'error_code'], 'source')], ['完整批却称整轮不可用', set(['status'], 'unavailable')],
  ['非有限金融值', set(['groups', 'account', 'rows', '0', 'fields', 'total_asset', 'value'], Infinity)],
] as const)('拒绝矛盾的完成资格及非有限标量：%s', (_label, mutate) => {
  const value = fixture(); mutate(value)
  expect(() => validateAccountOverview(value)).toThrow('账户数据格式无效')
})

it.each(['route_id', 'executor_id'] as const)('运输%s保持生产者Unicode标量域，控制字符不套账号规则', key => {
  for (const routeValue of ['a\u0000b', 'a\n\u007f\u0085\u009fb', '\u{1f642}'.repeat(128)]) {
    const value = fixture()
    value.groups.position.source!.transport.route[key] = routeValue
    const accepted = validateAccountOverview(value) as AccountOverviewV2
    expect(accepted.groups.position.source!.transport.route[key]).toBe(routeValue)
  }
})
