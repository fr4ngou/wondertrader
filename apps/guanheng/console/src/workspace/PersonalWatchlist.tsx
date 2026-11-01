import { useEffect, useId, useRef, useState, useSyncExternalStore } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { QueryClient } from '@tanstack/react-query'
import {
  decodePersonalWatchlist, fetchPersonalWatchlist, normalizePersonalSymbol, sameWatchlistSymbols,
  savePersonalWatchlist, WatchlistSaveError, WATCHLIST_MAX_ITEMS,
} from './watchlistApi'
import type { PersonalWatchlist as Snapshot } from './watchlistApi'
import { searchSecurities } from './securitySearchApi'
import './personal-watchlist.css'

export const PERSONAL_WATCHLIST_QUERY_KEY = ['independent-watchlist', 'default'] as const
const capabilityKeys = ['available', 'editable', 'max_items', 'scope', 'affects_strategy', 'reason']
type Capability = { available: boolean; editable: boolean }
type Phase = 'idle' | 'saved' | 'unknown' | 'conflict' | 'rejected' | 'review' | 'verified' | 'confirmed'
type Intent = { id: string; minimumVersion: number; symbols: readonly string[] }
type Props = { capability?: unknown; searchCapability?: unknown; initialSearch?: string; chartAvailable: boolean; chartBusy: boolean; chartPeriodLabel?: string; onView: (symbol: string) => void }

type UiState = Readonly<{
  phase: Phase
  saving: boolean
  reading: boolean
  confirmedId: string | null
  intent: Readonly<Intent> | null
}>

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

/** 能力关闭时不挂读取组件；个人偏好与分钟查询始终各自准入。 */
export default function PersonalWatchlist(props: Props) {
  const capability = capabilityValue(props.capability)
  const chartHint = props.chartAvailable ? `仍可直接查询${props.chartPeriodLabel ?? '分钟线'}。` : '分钟行情尚未配置，手工查询入口保持。'
  if (!capability?.available) return <article className="surface-card personal-watchlist" aria-label="我的个人观察">
    <h2>我的个人观察</h2>
    <p role={capability === null ? 'alert' : 'status'}>{capability === null
      ? '个人观察能力资料格式无效，暂不能读取或编辑。' + chartHint
      : props.capability === undefined ? '个人观察尚未配置。' + chartHint
        : '个人观察暂不可用，请检查本机配置或偏好资料。' + chartHint}</p>
    <p>个人观察只保存本页偏好；策略交易范围不变。</p>
  </article>
  return <AvailableWatchlist {...props} capability={capability} />
}

function AvailableWatchlist({ capability, searchCapability, initialSearch = '', chartAvailable, chartBusy, chartPeriodLabel = '分钟线', onView }: Omit<Props, 'capability'> & { capability: Capability }) {
  const client = useQueryClient()
  const inputId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [input, setInput] = useState('')
  const [validation, setValidation] = useState('')
  const [searchInput, setSearchInput] = useState(() => initialSearch.trim())
  const [searchTerm, setSearchTerm] = useState(() => initialSearch.trim())
  const [searchOpen, setSearchOpen] = useState(() => Boolean(initialSearch.trim()))
  const [searchComposing, setSearchComposing] = useState(false)
  const owner = watchlistOwner(client)
  const state = useSyncExternalStore(owner.subscribe, owner.getSnapshot, owner.getSnapshot)
  const { phase, saving, confirmedId, intent } = state
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])

  const query = useQuery({
    queryKey: PERSONAL_WATCHLIST_QUERY_KEY,
    queryFn: async ({ signal }) => {
      const incoming = await fetchPersonalWatchlist(signal)
      const current = client.getQueryData<Snapshot>(PERSONAL_WATCHLIST_QUERY_KEY)
      // PUT已确认较新版本时，晚到GET不能把缓存倒退；相同版本的持久字段也须一致。
      if (current?.watchlist_id === incoming.watchlist_id) {
        if (current.version > incoming.version) { owner.observe(current); return current }
        if (current.version === incoming.version && (current.updated_at !== incoming.updated_at
          || !sameWatchlistSymbols(current.symbols, incoming.symbols))) throw new Error('个人观察版本资料矛盾，请重新读取')
      }
      owner.observe(incoming)
      return incoming
    },
    retry: false, structuralSharing: false, refetchOnWindowFocus: false, refetchOnReconnect: false, refetchOnMount: 'always',
  })
  const searchAvailable = Boolean(searchCapability && typeof searchCapability === 'object'
    && !Array.isArray(searchCapability) && (searchCapability as Record<string, unknown>).available === true)
  const search = useQuery({ queryKey: ['security-search', searchTerm],
    queryFn: ({ signal }) => searchSecurities(searchTerm, signal),
    enabled: searchAvailable && searchOpen && !searchComposing && Boolean(searchTerm) && searchTerm === searchInput.trim(),
    retry: false, refetchOnWindowFocus: false })
  useEffect(() => {
    if (searchComposing) return
    const timer = window.setTimeout(() => setSearchTerm(searchInput.trim()), 200)
    return () => window.clearTimeout(timer)
  }, [searchInput, searchComposing])
  useEffect(() => {
    const term = initialSearch.trim()
    if (term) { setSearchInput(term); setSearchTerm(term); setSearchOpen(true) }
  }, [initialSearch])
  const snapshot = query.data
  const fresh = query.isSuccess && !query.isFetching
  const identityChanged = Boolean(snapshot && confirmedId && snapshot.watchlist_id !== confirmedId)
  const needsRead = phase === 'unknown' || phase === 'conflict' || phase === 'rejected'
  const needsReview = phase === 'review' || identityChanged
  const versionFull = snapshot?.version === Number.MAX_SAFE_INTEGER
  const canEdit = Boolean(fresh && snapshot && snapshot.editable && capability.editable && confirmedId === snapshot.watchlist_id
    && !saving && !state.reading && !needsRead && !needsReview && !versionFull)
  // 保存/确认后回到输入，移出按钮消失时键盘焦点仍有明确落点。
  useEffect(() => {
    if (canEdit && (phase === 'saved' || phase === 'verified' || phase === 'confirmed')) inputRef.current?.focus()
  }, [canEdit, phase])
  const messages: Partial<Record<Phase, string>> = {
    saved: '已保存个人观察；策略交易范围不变。',
    unknown: '个人观察保存结果尚未确认，请重新读取核实；请勿重复保存。',
    conflict: '个人观察列表已在其他页面更新，请重新读取后确认。',
    rejected: '个人观察保存请求未通过校验，请重新读取后检查当前列表。',
    review: '本次目标尚未在当前列表中确认。请检查当前列表，再确认后继续编辑。',
    verified: '已核实当前列表与本次保存目标一致；策略交易范围不变。',
    confirmed: '已确认当前列表；可继续编辑个人观察。',
  }

  async function reread() {
    if (!owner.beginRead()) return
    setValidation('')
    try { await query.refetch({ throwOnError: true }) }
    catch {
      // GET失败保留owner中的原目标/暂停阶段；页面只显示固定中文。
    } finally { owner.endRead() }
  }

  async function save(target: readonly string[], clearInput: boolean) {
    if (!canEdit || !snapshot) return
    setValidation('')
    const succeeded = await owner.save(snapshot, target)
    if (succeeded && mounted.current && clearInput) setInput('')
  }

  function add() {
    if (!canEdit || !snapshot) return
    let symbol: string
    try { symbol = normalizePersonalSymbol(input) }
    catch { setValidation('请输入六位证券代码和交易所，例如 600000.SH。'); return }
    if (snapshot.symbols.includes(symbol)) { setValidation('该证券已在个人观察中，无需重复添加。'); return }
    if (snapshot.symbols.length >= WATCHLIST_MAX_ITEMS) { setValidation('个人观察最多保存100个证券，请先移出一项。'); return }
    void save([...snapshot.symbols, symbol], true)
  }
  function addSymbol(symbol: string) {
    if (!canEdit || !snapshot) return
    if (snapshot.symbols.includes(symbol)) { setValidation('该证券已在个人观察中，无需重复添加。'); return }
    if (snapshot.symbols.length >= WATCHLIST_MAX_ITEMS) { setValidation('个人观察最多保存100个证券，请先移出一项。'); return }
    void save([...snapshot.symbols, symbol], false)
  }
  function confirmCurrent() {
    if (!snapshot || !fresh || needsRead) return
    owner.confirm(snapshot)
    setValidation('')
  }
  const unconfirmed = !fresh || needsRead || needsReview || saving
  return <article className="surface-card personal-watchlist" aria-label="我的个人观察">
    <header className="personal-watchlist-heading"><div><h2>我的个人观察</h2>
      <p>仅个人观察偏好可编辑；添加或移出不改变策略交易范围，也不会订阅行情。</p></div>
      <button type="button" disabled={saving || query.isFetching} onClick={() => void reread()}>重新读取个人观察</button>
    </header>
    {searchAvailable ? <section className="security-search" aria-label="搜索证券"
      onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setSearchOpen(false) }}>
      <form className="personal-watchlist-form" onSubmit={event => { event.preventDefault(); const term = searchInput.trim(); if (term && !searchComposing) { setSearchTerm(term); setSearchOpen(true) } }}>
        <label>搜索证券简称、拼音或代码<input aria-label="搜索证券简称、拼音或代码" value={searchInput} maxLength={64}
          placeholder="例如 68817、浦发银行、pfyh" autoComplete="off" spellCheck={false}
          onFocus={() => setSearchOpen(true)} onCompositionStart={() => setSearchComposing(true)} onCompositionEnd={() => setSearchComposing(false)}
          onKeyDown={event => { if (event.key === 'Escape') setSearchOpen(false); if (event.key === 'Enter' && (searchComposing || event.nativeEvent.isComposing)) event.preventDefault() }}
          onChange={event => { setSearchInput(event.target.value); setSearchOpen(true) }} /></label>
        <button type="submit" disabled={!searchInput.trim() || search.isFetching}>搜索证券</button>
      </form>
      {searchOpen && !searchComposing && searchInput.trim() && searchTerm === searchInput.trim() ? <div className="personal-search-dropdown">
      {search.isFetching ? <p role="status">正在搜索证券目录…</p> : null}
      {search.isError ? <p role="alert">证券目录搜索失败，请稍后重试。</p> : null}
      {search.data && !search.data.results.length ? <p role="status">证券目录中没有匹配项；未生成或补全任何代码。</p> : null}
      {search.data?.results.length ? <ul className="security-search-results" aria-label="证券搜索结果">
        {search.data.results.map(item => <li key={item.symbol}><span><strong>{item.name}</strong> · {item.symbol} · {
          item.security_type === 'stock' ? '股票' : item.security_type === 'etf' ? 'ETF' : '指数'}</span>
          <button type="button" disabled={!chartAvailable || chartBusy} onClick={() => { onView(item.symbol); setSearchOpen(false) }}>查看{chartPeriodLabel}</button>
          <button type="button" disabled={!canEdit || snapshot?.symbols.includes(item.symbol)} onClick={() => addSymbol(item.symbol)}>
            {snapshot?.symbols.includes(item.symbol) ? '已在个人观察' : '加入个人观察'}</button></li>)}
      </ul> : null}
      </div> : null}
    </section> : <p role="status">证券目录搜索尚未配置；仍可输入完整规范代码。</p>}
    <form className="personal-watchlist-form" onSubmit={event => { event.preventDefault(); add() }}>
      <label htmlFor={inputId}>加入个人观察的证券代码<input ref={inputRef} id={inputId} value={input} maxLength={32}
        disabled={!canEdit} placeholder="例如 600000.SH" autoComplete="off" spellCheck={false}
        onChange={event => { setInput(event.target.value); setValidation('') }} /></label>
      <button type="submit" disabled={!canEdit}>加入个人观察</button>
    </form>
    {validation ? <p role="alert">{validation}</p> : null}
    <div aria-live="polite" aria-atomic="true">
      {saving ? <p role="status">正在保存个人观察，请等待本次回执…</p>
        : query.isFetching ? <p role="status">正在读取个人观察，当前暂停编辑…</p>
          : query.isError ? <p role="alert">个人观察读取失败或资料无效，请重新读取；上次偏好尚未确认，暂不能编辑。</p>
            : needsRead ? <p role="alert">{messages[phase]}</p>
              : identityChanged ? <p role="alert">个人观察列表身份已变化，请确认当前列表后继续编辑。</p>
                : messages[phase] ? <p role={phase === 'review' ? 'alert' : 'status'}>{messages[phase]}</p> : null}
    </div>
    {intent ? <p className="personal-watchlist-target">本次待核实的完整观察目标（{intent.symbols.length}项）：{intent.symbols.length ? intent.symbols.join('、') : '空列表'}。</p> : null}
    {snapshot ? <>
      <p>{unconfirmed ? '上次读取的列表（当前状态尚未确认）' : '已确认的个人观察列表'} · {snapshot.symbols.length} / {WATCHLIST_MAX_ITEMS}</p>
      {snapshot.symbols.length ? <ul className="personal-watchlist-items" aria-label="个人观察证券">
        {snapshot.symbols.map(symbol => <li key={symbol}><button type="button" className="personal-watchlist-view"
          disabled={!chartAvailable || chartBusy} onClick={() => { if (chartAvailable && !chartBusy) onView(symbol) }}
          aria-label={'查看 ' + symbol + ' ' + chartPeriodLabel}>{symbol}</button>
          <button type="button" disabled={!canEdit} aria-label={'移出 ' + symbol + ' 的个人观察'}
            onClick={() => void save(snapshot.symbols.filter(item => item !== symbol), false)}>移出</button></li>)}
      </ul> : <p>{unconfirmed ? '上次读取的列表为空；当前状态尚未确认。'
        : '个人观察列表为空；输入完整证券代码加入，仅供本页观察。'}</p>}
      <p className="personal-watchlist-time">偏好保存时间（UTC）：<time dateTime={snapshot.updated_at}>{snapshot.updated_at.replace('T', ' ').replace('Z', ' UTC')}</time></p>
      {fresh && versionFull ? <p role="status">个人观察版本已达到上限，当前仅可查看；请维护偏好资料后重新读取。</p> : null}
      {fresh && (!snapshot.editable || !capability.editable) ? <p role="status">个人观察目前仅可查看，暂不可编辑。请检查本机配置或偏好资料；维护完成后请刷新整个页面，以重新核实应用能力和列表。</p> : null}
      {fresh && needsReview && !needsRead && !saving ? <button type="button" onClick={confirmCurrent}>确认当前列表后继续编辑</button> : null}
    </> : null}
    {!chartAvailable ? <p>分钟行情尚未配置；个人观察的读取和保存可独立使用。</p> : null}
  </article>
}
