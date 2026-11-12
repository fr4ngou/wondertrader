import { useSyncExternalStore } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { QueryClient } from '@tanstack/react-query'
import { decodePersonalWatchlist, fetchPersonalWatchlist, normalizePersonalSymbol,
  sameWatchlistSymbols, savePersonalWatchlist, WatchlistSaveError, WATCHLIST_MAX_ITEMS } from './watchlistApi'
import type { PersonalWatchlist as Snapshot } from './watchlistApi'

export const PERSONAL_WATCHLIST_QUERY_KEY = ['independent-watchlist', 'default'] as const
const capabilityKeys = ['available', 'editable', 'max_items', 'scope', 'affects_strategy', 'reason']
type Capability = { available: boolean; editable: boolean }
type Phase = 'idle' | 'saved' | 'unknown' | 'conflict' | 'rejected' | 'review' | 'verified' | 'confirmed'
type Intent = { id: string; minimumVersion: number; symbols: readonly string[] }
type UiState = Readonly<{ phase: Phase; saving: boolean; reading: boolean; confirmedId: string | null; intent: Readonly<Intent> | null }>

/**
 * 同一QueryClient只保留一份当前目标/阶段；路由卸载只取消订阅，不结束已发出的PUT。
 * 目标最多100项，不存版本历史或持久日志；只有用户动作会发一次PUT，GET只核实结果。
 */
class WatchlistUiOwner {
  private value: UiState
  private readonly listeners = new Set<() => void>()

  constructor(private readonly client: QueryClient) {
    this.value = Object.freeze({ phase: 'idle', saving: false, reading: false, intent: null,
      confirmedId: client.getQueryData<Snapshot>(PERSONAL_WATCHLIST_QUERY_KEY)?.watchlist_id ?? null })
  }

  getSnapshot = (): UiState => this.value
  subscribe = (listener: () => void) => {
    this.listeners.add(listener)
    return () => { this.listeners.delete(listener) }
  }

  private publish(update: Partial<UiState>) {
    this.value = Object.freeze({ ...this.value, ...update })
    this.listeners.forEach(listener => listener())
  }

  observe(snapshot: Snapshot) {
    // 在途PUT尚未收口时，较早GET不能解除其门禁；后续GET再核完整目标和最低版本。
    if (this.value.saving) return
    const pending = this.value.intent
    if (pending) {
      if (snapshot.watchlist_id === pending.id && snapshot.version >= pending.minimumVersion
        && sameWatchlistSymbols(snapshot.symbols, pending.symbols)) {
        this.publish({ intent: null, phase: 'verified' })
      } else this.publish({ phase: 'review' })
    } else if (this.value.confirmedId === null) this.publish({ confirmedId: snapshot.watchlist_id })
  }

  beginRead(): boolean {
    if (this.value.saving || this.value.reading) return false
    this.publish({ reading: true })
    return true
  }

  endRead() { this.publish({ reading: false }) }

  confirm(snapshot: Snapshot) {
    if (this.value.saving || this.value.reading
      || ['unknown', 'conflict', 'rejected'].includes(this.value.phase)) return
    this.publish({ intent: null, confirmedId: snapshot.watchlist_id, phase: 'confirmed' })
  }

  async save(snapshot: Snapshot, target: readonly string[]): Promise<boolean> {
    if (this.value.saving || this.value.reading || this.value.intent !== null) return false
    const pending = Object.freeze({ id: snapshot.watchlist_id,
      minimumVersion: snapshot.version + Number(!sameWatchlistSymbols(snapshot.symbols, target)),
      symbols: Object.freeze([...target]) })
    // 先发布唯一目标再调用公共API；卸载期间的成功/异常都由本owner接收。
    this.publish({ saving: true, intent: pending })
    try {
      const result = await savePersonalWatchlist(snapshot, pending.symbols)
      const saved = decodePersonalWatchlist(result.watchlist)
      this.client.setQueryData<Snapshot>(PERSONAL_WATCHLIST_QUERY_KEY, current => {
        if (current && (current.watchlist_id !== saved.watchlist_id || current.version > saved.version)) return current
        return saved
      })
      this.publish({ saving: false, intent: null, phase: 'saved' })
      return true
    } catch (error) {
      this.publish({ saving: false, phase: error instanceof WatchlistSaveError ? error.state : 'unknown' })
      return false
    }
  }
}

const watchlistOwners = new WeakMap<QueryClient, WatchlistUiOwner>()
function watchlistOwner(client: QueryClient): WatchlistUiOwner {
  let owner = watchlistOwners.get(client)
  if (!owner) {
    owner = new WatchlistUiOwner(client)
    watchlistOwners.set(client, owner)
  }
  return owner
}

function capabilityValue(value: unknown): Capability | null {
  if (value === undefined) return { available: false, editable: false }
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return null
  const data = value as Record<string, unknown>
  if (Object.keys(data).length !== capabilityKeys.length || !capabilityKeys.every(key => Object.hasOwn(data, key))
    || typeof data.available !== 'boolean' || typeof data.editable !== 'boolean'
    || data.max_items !== WATCHLIST_MAX_ITEMS || data.scope !== 'personal-observation' || data.affects_strategy !== false
    || !data.available && data.editable) return null
  if (data.editable) { if (data.reason !== null) return null }
  else {
    if (typeof data.reason !== 'string' || !data.reason.length || data.reason.length > 256) return null
    for (const point of data.reason) {
      const unit = point.charCodeAt(0)
      if (point.length === 1 && unit >= 0xd800 && unit <= 0xdfff) return null
    }
    if (new TextEncoder().encode(data.reason).length > 256) return null
  }
  return { available: data.available, editable: data.editable }
}

/** 自选只有一份版本化偏好；行情查询不依赖偏好是否可编辑。 */
export function usePersonalWatchlist(value: unknown) {
  const capability = capabilityValue(value)
  const client = useQueryClient()
  const owner = watchlistOwner(client)
  const state = useSyncExternalStore(owner.subscribe, owner.getSnapshot, owner.getSnapshot)
  const query = useQuery({
    queryKey: PERSONAL_WATCHLIST_QUERY_KEY,
    queryFn: async ({ signal }) => {
      const incoming = await fetchPersonalWatchlist(signal)
      const current = client.getQueryData<Snapshot>(PERSONAL_WATCHLIST_QUERY_KEY)
      // 保存成功后的迟到GET不能回退版本，相同版本必须表示相同列表。
      if (current?.watchlist_id === incoming.watchlist_id) {
        if (current.version > incoming.version) { owner.observe(current); return current }
        if (current.version === incoming.version && (current.updated_at !== incoming.updated_at
          || !sameWatchlistSymbols(current.symbols, incoming.symbols))) throw new Error('自选版本资料矛盾，请刷新')
      }
      owner.observe(incoming)
      return incoming
    },
    enabled: Boolean(capability?.available), retry: false, structuralSharing: false,
    refetchOnWindowFocus: false, refetchOnReconnect: false, refetchOnMount: 'always',
  })
  const snapshot = query.data
  const fresh = query.isSuccess && !query.isFetching
  const needsRead = ['unknown', 'conflict', 'rejected'].includes(state.phase)
  const needsReview = state.phase === 'review' || Boolean(snapshot && state.confirmedId && snapshot.watchlist_id !== state.confirmedId)
  const canEdit = Boolean(capability?.editable && fresh && snapshot?.editable
    && state.confirmedId === snapshot.watchlist_id && !state.saving && !state.reading
    && !needsRead && !needsReview && snapshot.version < Number.MAX_SAFE_INTEGER)
  async function reread() {
    if (!capability?.available || !owner.beginRead()) return
    try { await query.refetch({ throwOnError: true }) } catch { /* 保留当前列表和待核实目标。 */ }
    finally { owner.endRead() }
  }
  async function toggle(requested: string) {
    if (!canEdit || !snapshot) return
    const symbol = normalizePersonalSymbol(requested)
    const present = snapshot.symbols.includes(symbol)
    if (!present && snapshot.symbols.length >= WATCHLIST_MAX_ITEMS) return
    await owner.save(snapshot, present ? snapshot.symbols.filter(item => item !== symbol) : [...snapshot.symbols, symbol])
  }
  const messages: Partial<Record<Phase, string>> = {
    unknown: '保存结果待确认，请刷新自选。', conflict: '自选已更新，请刷新后确认。',
    rejected: '保存未通过，请刷新自选。', review: '请确认当前列表后继续编辑。',
  }
  const message = capability === null ? '手工自选资料格式无效' : !capability?.available ? '手工自选暂不可用'
    : query.isError ? '自选读取失败' : state.saving ? '正在保存…'
      : needsReview ? '请确认当前自选列表' : messages[state.phase] ?? ''
  return { snapshot, symbols: snapshot?.symbols ?? [], canEdit, message,
    loading: query.isFetching, saving: state.saving, needsReview, needsRead,
    reread, toggle, confirm: () => { if (snapshot && fresh && !needsRead) owner.confirm(snapshot) },
    full: (snapshot?.symbols.length ?? 0) >= WATCHLIST_MAX_ITEMS }
}
export type PersonalWatchlistModel = ReturnType<typeof usePersonalWatchlist>
