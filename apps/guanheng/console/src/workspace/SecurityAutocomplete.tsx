import { useEffect, useId, useRef, useState } from 'react'
import { Search } from 'lucide-react'
import { searchSecurities, type SecuritySearchItem } from './securitySearchApi'

type Matches = { term: string; items: readonly SecuritySearchItem[]; loading: boolean; error: string }
const securityType = { stock: '股票', etf: 'ETF', index: '指数' }

/** 输入后查询原证券目录；取消旧请求并核对查询词，避免迟到结果覆盖当前输入。 */
export function SecurityAutocomplete({ onSelect, initialSearch = '' }: { onSelect: (term: string) => void; initialSearch?: string }) {
  const [input, setInput] = useState(initialSearch)
  const [open, setOpen] = useState(Boolean(initialSearch) && !/^\d{6}\.(SH|SZ)$/i.test(initialSearch))
  const [composing, setComposing] = useState(false)
  const [active, setActive] = useState(-1)
  const [matches, setMatches] = useState<Matches>({ term: '', items: [], loading: false, error: '' })
  const listId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const term = input.trim()
  const visible = open && !!term && !composing
  const current = matches.term === term ? matches : { term, items: [], loading: true, error: '' }
  useEffect(() => {
    setInput(initialSearch); setActive(-1)
    setOpen(Boolean(initialSearch) && !/^\d{6}\.(SH|SZ)$/i.test(initialSearch))
  }, [initialSearch])

  useEffect(() => {
    function focusSearch(event: KeyboardEvent) {
      const target = event.target instanceof Element ? event.target : null
      if (event.key === '/' && !event.ctrlKey && !event.metaKey && !event.altKey && !event.isComposing
        && !target?.closest('input,textarea,select,[contenteditable="true"]')) {
        event.preventDefault(); inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', focusSearch)
    return () => window.removeEventListener('keydown', focusSearch)
  }, [])

  useEffect(() => {
    if (!visible) return
    const controller = new AbortController()
    let live = true
    const timer = window.setTimeout(() => {
      setMatches(previous => previous.term === term ? { ...previous, loading: true, error: '' }
        : { term, items: [], loading: true, error: '' })
      void searchSecurities(term, controller.signal).then(result => {
        if (live) setMatches({ term, items: result.results, loading: false, error: '' })
      }).catch((error: unknown) => {
        if (live) setMatches(previous => ({ term, items: previous.term === term ? previous.items : [], loading: false,
          error: error instanceof Error ? error.message : '证券搜索暂不可用，请重试' }))
      })
    }, 200)
    return () => { live = false; window.clearTimeout(timer); controller.abort() }
  }, [term, visible])

  function choose(value: string) {
    setOpen(false)
    setActive(-1)
    onSelect(value)
  }

  return <form className="observer-global-search" role="search" aria-label="证券搜索"
    onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false) }}
    onSubmit={event => {
      event.preventDefault()
      if (composing || !term) return
      const selected = active >= 0 ? current.items[active] : current.items.length === 1 ? current.items[0] : undefined
      if (selected) choose(selected.symbol)
      else if (/^\d{6}\.(SH|SZ)$/i.test(term)) choose(term.toUpperCase())
      else { onSelect(term); setOpen(true) }
    }}>
    <Search size={17} aria-hidden="true" />
    <input ref={inputRef} className="observer-global-search-input" role="combobox" aria-label="全局证券搜索"
      aria-autocomplete="list" aria-expanded={visible} aria-controls={listId}
      aria-activedescendant={visible && current.items[active] ? `${listId}-${active}` : undefined}
      autoComplete="off" placeholder="代码 / 简称 / 拼音" value={input}
      onFocus={() => setOpen(true)}
      onCompositionStart={() => { setComposing(true); setActive(-1) }}
      onCompositionEnd={() => setComposing(false)}
      onChange={event => { setInput(event.target.value); setOpen(true); setActive(-1) }}
      onKeyDown={event => {
        if (composing || event.nativeEvent.isComposing) {
          if (event.key === 'Enter') event.preventDefault()
          return
        }
        if (event.key === 'Escape') { event.preventDefault(); setOpen(false); setActive(-1) }
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault(); setOpen(true)
          const count = current.items.length
          if (count) setActive(index => event.key === 'ArrowDown' ? (index + 1) % count : (index <= 0 ? count - 1 : index - 1))
        }
      }} />
    <kbd aria-label="斜杠键搜索">/</kbd>
    {visible ? <div className="observer-search-dropdown">
      {current.loading ? <p role="status">正在查找证券…</p> : current.error ? <p role="alert">{current.error}{current.items.length ? '；当前保留上次同词搜索结果。' : ''}</p>
        : !current.items.length ? <p role="status">没有找到匹配证券，试试简称、拼音或代码。</p> : null}
      <ul id={listId} role="listbox" aria-label="匹配证券" aria-busy={current.loading}>
        {current.items.map((item, index) => <li key={item.symbol} role="presentation">
          <button type="button" role="option" id={`${listId}-${index}`} aria-selected={active === index}
            onMouseDown={event => event.preventDefault()} onMouseEnter={() => setActive(index)}
            onClick={() => choose(item.symbol)}>
            <span>{item.name}<small>{securityType[item.security_type]}</small></span><code>{item.symbol}</code>
          </button>
        </li>)}
      </ul>
    </div> : null}
  </form>
}
