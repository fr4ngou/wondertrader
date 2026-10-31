import { fetchReadJson } from '../api'

export const WATCHLIST_SCHEMA = 'guanheng.personal-watchlist.v1' as const
export const WATCHLIST_MAX_ITEMS = 100
const endpoint = '/v1/ui/watchlists/default'
const uuid4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const symbolPattern = /^[0-9]{6}\.(SH|SZ)$/
const snapshotKeys = ['schema_version', 'watchlist_id', 'version', 'symbols', 'updated_at',
  'affects_strategy', 'editable', 'reason'] as const

export type PersonalWatchlist = Readonly<{
  schema_version: typeof WATCHLIST_SCHEMA
  watchlist_id: string
  version: number
  symbols: readonly string[]
  updated_at: string
  affects_strategy: false
  editable: boolean
  reason: string | null
}>
export type WatchlistSaveResult = Readonly<{
  schema_version: typeof WATCHLIST_SCHEMA
  changed: boolean
  watchlist: PersonalWatchlist
}>

export class WatchlistSaveError extends Error {
  readonly state: 'conflict' | 'rejected' | 'unknown'

  constructor(state: 'conflict' | 'rejected' | 'unknown') {
    super(state === 'conflict' ? '个人观察列表已在其他页面更新，请重新读取后确认'
      : state === 'rejected' ? '个人观察保存请求未通过校验，请检查后重新读取'
        : '个人观察保存结果尚未确认，请重新读取核实；请勿重复保存')
    this.name = 'WatchlistSaveError'
    this.state = state
  }
}

function invalid(): never { throw new Error('个人观察资料格式或身份无效，请重新读取') }
function keys(value: unknown, expected: readonly string[]): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).length === expected.length && expected.every(key => Object.hasOwn(value, key))
}
function utf8(value: unknown, max: number): value is string {
  if (typeof value !== 'string' || value.length > max) return false
  for (const point of value) {
    const unit = point.charCodeAt(0)
    if (point.length === 1 && unit >= 0xd800 && unit <= 0xdfff) return false
  }
  return new TextEncoder().encode(value).length <= max
}
function validUtc(value: unknown): value is string {
  if (typeof value !== 'string' || value.length > 27) return false
  const match = /^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.[0-9]{1,6})?Z$/.exec(value)
  if (!match) return false
  const [year, month, day, hour, minute, second] = match.slice(1).map(Number)
  if (year < 1) return false
  const parsed = new Date(0)
  parsed.setUTCFullYear(year, month - 1, day)
  parsed.setUTCHours(hour, minute, second, 0)
  return parsed.getUTCFullYear() === year && parsed.getUTCMonth() === month - 1
    && parsed.getUTCDate() === day && parsed.getUTCHours() === hour
    && parsed.getUTCMinutes() === minute && parsed.getUTCSeconds() === second
}
function symbols(value: unknown): readonly string[] {
  if (!Array.isArray(value) || value.length > WATCHLIST_MAX_ITEMS) return invalid()
  const result: string[] = []
  const seen = new Set<string>()
  for (const item of value) {
    if (typeof item !== 'string' || !symbolPattern.test(item) || seen.has(item)) return invalid()
    result.push(item)
    seen.add(item)
  }
  return Object.freeze(result)
}

/** 与分钟输入相同的完整证券形状；此结果只证明可保存观察代码。 */
export function normalizePersonalSymbol(value: unknown): string {
  if (!utf8(value, 32)) return invalid()
  const canonical = value.trim().toUpperCase()
  if (!symbolPattern.test(canonical)) return invalid()
  return canonical
}

/** 新值树与输入分离；固定false和闭合字段防止旧DTO混入当前能力。 */
export function decodePersonalWatchlist(value: unknown): PersonalWatchlist {
  if (!keys(value, snapshotKeys) || value.schema_version !== WATCHLIST_SCHEMA
    || typeof value.watchlist_id !== 'string' || !uuid4.test(value.watchlist_id)
    || !Number.isSafeInteger(value.version) || (value.version as number) < 1
    || !validUtc(value.updated_at) || value.affects_strategy !== false || typeof value.editable !== 'boolean'
    || (value.editable ? value.reason !== null : !utf8(value.reason, 256) || value.reason.length === 0)) return invalid()
  return Object.freeze({ schema_version: WATCHLIST_SCHEMA, watchlist_id: value.watchlist_id,
    version: value.version as number, symbols: symbols(value.symbols), updated_at: value.updated_at,
    affects_strategy: false, editable: value.editable, reason: value.reason as string | null })
}

export function sameWatchlistSymbols(first: readonly string[], second: readonly string[]): boolean {
  return first.length === second.length && first.every((value, index) => value === second[index])
}

export async function fetchPersonalWatchlist(signal?: AbortSignal): Promise<PersonalWatchlist> {
  return decodePersonalWatchlist(await fetchReadJson<unknown>(endpoint, '个人观察', signal, 'workspace', 6500))
}

/** 单次完整替换；响应丢失与格式矛盾均先GET核实，不在此函数自动重试。 */
export async function savePersonalWatchlist(previous: PersonalWatchlist, target: readonly string[]): Promise<WatchlistSaveResult> {
  const before = decodePersonalWatchlist(previous)
  const desired = symbols(target)
  const changed = !sameWatchlistSymbols(before.symbols, desired)
  if (!before.editable || changed && before.version === Number.MAX_SAFE_INTEGER) return invalid()
  const request = { schema_version: WATCHLIST_SCHEMA, watchlist_id: before.watchlist_id,
    expected_version: before.version, symbols: [...desired] }
  const body = JSON.stringify(request)
  if (new TextEncoder().encode(body).length > 4096) return invalid()
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 6500)
  let status: number | undefined
  try {
    const response = await fetch(endpoint, { method: 'PUT', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, signal: controller.signal, body })
    status = response.status
    if (!response.ok) throw new Error()
    const value: unknown = await response.json()
    if (!keys(value, ['schema_version', 'changed', 'watchlist']) || value.schema_version !== WATCHLIST_SCHEMA
      || typeof value.changed !== 'boolean' || value.changed !== changed) return invalid()
    const saved = decodePersonalWatchlist(value.watchlist)
    if (!saved.editable || saved.watchlist_id !== before.watchlist_id || saved.version !== before.version + Number(changed)
      || !sameWatchlistSymbols(saved.symbols, desired) || !changed && saved.updated_at !== before.updated_at) return invalid()
    return Object.freeze({ schema_version: WATCHLIST_SCHEMA, changed, watchlist: saved })
  } catch {
    // 不消费上游detail/网络异常原文；503/迟到/坏响应可能发生在实际提交之后。
    throw new WatchlistSaveError(status === 409 ? 'conflict'
      : status !== undefined && [403, 413, 415, 422].includes(status) ? 'rejected' : 'unknown')
  } finally { clearTimeout(timer) }
}
