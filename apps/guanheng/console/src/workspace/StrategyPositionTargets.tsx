import { useState } from 'react'
import { absoluteChinaTime } from '../components/RelativeTime'
import type { AccountField, AccountGroup, AccountRow } from './accountApi'
import { FinancialValue } from './FinancialValue'
import type { StrategyDetails } from './strategyDetailsApi'
import { useStrategyTargetHistory } from './strategyTargetHistoryApi'

const quantity = (value: number) => value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })

function quantityValue(field?: AccountField) {
  if (field?.availability !== 'present' || field.value === null || String(field.value).trim() === '') return null
  const value = Number(field.value)
  return Number.isFinite(value) ? value : null
}

function money(field?: AccountField) {
  return field?.availability === 'present' && field.value !== null ? <FinancialValue value={field.value} /> : '—'
}

function accountSymbol({ identity }: AccountRow) {
  const { m_strInstrumentID: code, m_strExchangeID: exchange, wt_symbol: native } = identity
  if (code && exchange) return `${code}.${exchange}`
  const parts = native?.match(/^(SSE|SZSE)\.(?:[A-Z]+\.)?(\d{6})$/)
  if (parts) return `${parts[2]}.${parts[1] === 'SSE' ? 'SH' : 'SZ'}`
  return native ?? (code ? `${code}.?` : '证券未知')
}

/** 合并显示原持仓与原生目标，各列保留来源、观察时间及未知值。 */
export function StrategyPositionTargets({ details, positionGroup, positionRefreshed }: {
  /** 所选策略与同代实际持仓归属。 */ details: StrategyDetails
  /** 原完整券商持仓或本次未取得的原回执。 */ positionGroup?: AccountGroup
  /** 本轮是否取得完整券商持仓，区分缓存与新读取。 */ positionRefreshed: boolean
}) {
  const [scope, setScope] = useState<'strategy' | 'account'>('strategy')
  const query = useStrategyTargetHistory(details.strategy, null, details.runtime_scope_id)
  const summary = query.data?.source?.latest_targets
  const latest = new Map(summary?.map(row => [row.symbol, row]))
  const positions = details.calculation?.positions ?? []
  const strategySymbols = new Set(positions.map(row => row.symbol))
  const allocated = details.calculation?.position_basis === 'strategy-allocated'
  const scoped = !allocated && strategySymbols.size > 0
  const accountWide = !allocated && (!scoped || scope === 'account')
  const positionTime = allocated ? details.calculation?.broker_observed_at
    : positionGroup && ('received_at' in positionGroup ? positionGroup.received_at : positionGroup.execution_finished_at)
  const accountRows = positionGroup?.status === 'complete' ? positionGroup.rows : undefined
  const actual = allocated ? positions.map(row => ({ symbol: row.symbol, held: row.broker_quantity,
    sellable: row.broker_sellable, marketValue: undefined, profit: undefined }))
    : (accountRows ?? []).map(row => ({ symbol: accountSymbol(row), held: quantityValue(row.fields.quantity),
      sellable: quantityValue(row.fields.sellable), marketValue: row.fields.market_value, profit: row.fields.float_profit }))
      .filter(row => accountWide || strategySymbols.has(row.symbol))
  const rows = actual.filter((row): row is typeof row & { held: number } => row.held !== null && row.held !== 0)
  const basis = allocated ? '策略自有持仓' : accountWide ? '账户聚合持仓' : '策略范围内的账户持仓'
  const positionMessage = allocated ? !positionTime ? '策略自有持仓尚未取得。' : null
    : !accountRows ? positionGroup?.reason ?? '当前持仓尚未取得。'
      : accountRows.length === 0 ? '本次完整持仓查询返回为空。' : null

  return <section className="strategy-position-targets" aria-label="持仓和目标">
    <h4>持仓与目标仓位</h4>
    {scoped ? <div className="strategy-position-controls" role="group" aria-label="持仓范围">
      <button type="button" aria-pressed={!accountWide} onClick={() => setScope('strategy')}>策略相关</button>
      <button type="button" aria-pressed={accountWide} onClick={() => setScope('account')}>全账户</button>
    </div> : null}
    <p className="strategy-catalog-note"><span>{basis}</span>{positionTime ? <> · 持仓观察时间 <time dateTime={positionTime}>{absoluteChinaTime(positionTime)}</time></> : null}</p>
    <p className="strategy-catalog-note">{allocated || accountWide ? details.assignment.reason : '按当前策略标的筛选，持仓归属未确认。'}</p>
    {details.account_reason ? <p role="alert">{details.account_reason}</p> : null}
    {!allocated && accountRows && !positionRefreshed ? <p role="status">本轮持仓未更新，当前保留上次成功持仓及原查询时间。</p> : null}
    {positionMessage ? <p role="status">{positionMessage}</p> : null}
    {query.isError ? <p role="status">最近目标变化读取失败。{query.data ? <>当前显示 {absoluteChinaTime(query.data.observed_at)} 的记录。</> : null}</p> : null}
    {query.isFetching && !query.data ? <p role="status">正在读取最近目标变化…</p> : null}
    {query.data?.state === 'available' && !summary ? <p role="status">当前服务尚未提供逐标的变化汇总。</p> : null}
    {query.data && query.data.state !== 'available' ? <p role="status">{query.data.reason}</p> : null}
    {query.data?.source?.incomplete_tail ? <p role="status">原生记录末行仍在写入，汇总显示已完整写入的变化。</p> : null}
    {rows.length ? <div className="account-table-scroll" role="region" aria-label="持仓与目标仓位表" tabIndex={0}>
      <table aria-label="持仓与目标仓位"><thead><tr><th scope="col">证券</th><th scope="col">实际持仓（份）</th><th scope="col">可卖（份）</th>
        <th scope="col">目标仓位（份）</th><th scope="col">上次目标变化（份）</th><th scope="col">目标记录时间</th><th scope="col">市值（元）</th><th scope="col">持仓浮盈（元）</th></tr></thead>
        <tbody>{rows.map(({ symbol, held, sellable, marketValue, profit }, index) => {
          const target = latest.get(symbol)
          return <tr key={`${symbol}-${index}`}>
            <th scope="row"><StrategySecurityLabel symbol={symbol} names={details.security_names} /></th>
            <td>{quantity(held)}</td>
            <td>{sellable === null ? '—' : quantity(sellable)}</td>
            <td>{target ? quantity(target.target_quantity) : '—'}</td>
            <td>{target ? target.previous_target_quantity === null ? '首次记录' : `${quantity(target.previous_target_quantity)} → ${quantity(target.target_quantity)}` : '—'}</td>
            <td>{target ? <time dateTime={target.changed_at}>{absoluteChinaTime(target.changed_at)}</time> : '—'}</td>
            <td>{money(marketValue)}</td><td>{money(profit)}</td>
          </tr>
        })}</tbody></table>
    </div> : !positionMessage && <p>当前范围内没有可显示的实际持仓。</p>}
  </section>
}

export function StrategySecurityLabel({ symbol, names }: { symbol: string; names?: Record<string, string> }) {
  const name = Object.hasOwn(names ?? {}, symbol) ? names?.[symbol] : undefined
  return name ? <>{name} <small>{symbol}</small></> : <>{symbol}</>
}
