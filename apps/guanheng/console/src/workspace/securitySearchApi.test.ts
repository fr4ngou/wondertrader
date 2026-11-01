import { afterEach, expect, test, vi } from 'vitest'
import { decodeSecuritySearch, searchSecurities, SECURITY_SEARCH_SCHEMA } from './securitySearchApi'

afterEach(() => vi.restoreAllMocks())
const id = '4db2e4201db801878f71838e98e0f3157f0cfc482e2cfc9fd724b55dcf2252ba'
const item = { symbol: '688170.SH', code: '688170', exchange: 'SH', name: '德龙激光', security_type: 'stock',
  pinyin_initials: 'dljg', pinyin_full: 'delongjiguang', match: 'code' }
function value(overrides = {}) { return { schema_version: SECURITY_SEARCH_SCHEMA, query: '68817', catalog_id: id,
  generated_at: '2026-11-01T10:00:00Z', results: [item], ...overrides } }

test('闭合搜索合同保留真实规范身份', () => {
  const result = decodeSecuritySearch(value())
  expect(result.results[0]).toEqual(item)
  expect(Object.isFrozen(result.results)).toBe(true)
})

test.each([
  value({ extra: 1 }), value({ catalog_id: 'bad' }), value({ results: [{ ...item, symbol: '688170.SSE' }] }),
  value({ results: [item, item] }), value({ results: [{ ...item, code: '688171' }] }),
])('拒绝畸形或重复证券身份', invalid => expect(() => decodeSecuritySearch(invalid)).toThrow('证券搜索资料'))

test('请求只发送编码后的原搜索词和固定上限', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(value({ query: '德龙 激光' })),
    { status: 200, headers: { 'Content-Type': 'application/json' } })))
  await searchSecurities(' 德龙 激光 ')
  expect(fetch).toHaveBeenCalledWith('/v1/ui/securities/search?query=%E5%BE%B7%E9%BE%99%20%E6%BF%80%E5%85%89&limit=12', expect.anything())
})
