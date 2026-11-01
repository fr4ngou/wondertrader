import { fetchReadJson } from '../api'

export const SECURITY_SEARCH_SCHEMA = 'guanheng.security-search.v1' as const
const symbolPattern = /^[0-9]{6}\.(SH|SZ)$/
const sha256 = /^[0-9a-f]{64}$/
const resultKeys = ['symbol', 'code', 'exchange', 'name', 'security_type', 'pinyin_initials', 'pinyin_full', 'match'] as const

export type SecuritySearchItem = Readonly<{
  symbol: string
  code: string
  exchange: 'SH' | 'SZ'
  name: string
  security_type: 'stock' | 'etf' | 'index'
  pinyin_initials: string
  pinyin_full: string
  match: 'code' | 'name' | 'pinyin_initials' | 'pinyin_full'
}>
export type SecuritySearchResponse = Readonly<{
  schema_version: typeof SECURITY_SEARCH_SCHEMA
  query: string
  catalog_id: string
  generated_at: string
  results: readonly SecuritySearchItem[]
}>

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}
function exact(value: Record<string, unknown>, keys: readonly string[]) {
  return Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key))
}
function text(value: unknown, maximum: number): value is string {
  return typeof value === 'string' && value.length > 0 && new TextEncoder().encode(value).length <= maximum
}
function decodeItem(value: unknown): SecuritySearchItem {
  if (!object(value) || !exact(value, resultKeys) || typeof value.symbol !== 'string' || !symbolPattern.test(value.symbol)
    || typeof value.code !== 'string' || value.symbol !== `${value.code}.${value.exchange}`
    || !['SH', 'SZ'].includes(value.exchange as string) || !text(value.name, 192)
    || !['stock', 'etf', 'index'].includes(value.security_type as string)
    || typeof value.pinyin_initials !== 'string' || !/^[a-z0-9]{1,128}$/.test(value.pinyin_initials)
    || typeof value.pinyin_full !== 'string' || !/^[a-z0-9]{1,256}$/.test(value.pinyin_full)
    || !['code', 'name', 'pinyin_initials', 'pinyin_full'].includes(value.match as string)) throw new Error('证券搜索资料格式无效')
  return Object.freeze(value as SecuritySearchItem)
}

export function decodeSecuritySearch(value: unknown): SecuritySearchResponse {
  const keys = ['schema_version', 'query', 'catalog_id', 'generated_at', 'results']
  if (!object(value) || !exact(value, keys) || value.schema_version !== SECURITY_SEARCH_SCHEMA
    || !text(value.query, 128) || typeof value.catalog_id !== 'string' || !sha256.test(value.catalog_id)
    || !text(value.generated_at, 64) || !Array.isArray(value.results) || value.results.length > 30) throw new Error('证券搜索资料格式无效')
  const results = Object.freeze(value.results.map(decodeItem))
  if (new Set(results.map(item => item.symbol)).size !== results.length) throw new Error('证券搜索资料身份重复')
  return Object.freeze({ schema_version: SECURITY_SEARCH_SCHEMA, query: value.query,
    catalog_id: value.catalog_id, generated_at: value.generated_at, results })
}

export async function searchSecurities(query: string, signal?: AbortSignal): Promise<SecuritySearchResponse> {
  const term = query.trim()
  if (!term || new TextEncoder().encode(term).length > 128) throw new Error('请输入证券简称、拼音或代码')
  return decodeSecuritySearch(await fetchReadJson<unknown>(
    `/v1/ui/securities/search?query=${encodeURIComponent(term)}&limit=12`, '证券搜索', signal, 'workspace', 6500))
}
