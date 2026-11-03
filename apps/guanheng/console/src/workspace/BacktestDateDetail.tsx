import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { ArchiveEntry } from './backtestApi'
import { fetchLedger, type Trade } from './backtestVisualApi'
import { backtestMoney } from './backtestMoney'
import { reportDate } from './BacktestVisualChart'

const names: Record<string, string> = { '510500': '中证500ETF', '510050': '上证50ETF', '510300': '沪深300ETF', '512100': '中证1000ETF', '588000': '科创50ETF', '589000': '科创综指ETF', '515080': '红利ETF', '159780': '双创50ETF' }
export const reportSymbol = (code: string) => { const number = code.match(/\d{6}/)?.[0]; return number && names[number] ? `${names[number]} · ${number}` : code }
const gainClass = (value: string) => Number(value) > 0 ? 'bt-gain' : Number(value) < 0 ? 'bt-loss' : ''
const side = (trade: Trade) => trade.side === 'buy' ? '买入' : trade.side === 'sell' ? '卖出' : `${trade.direction}/${trade.action}`

/** 日期与完整成交共用原件投影；同条件刷新失败保留原值和读取时间。 */
export default function BacktestDateDetail({ entry, day, dates, onDay }: {
  /** 当前明细归属的报告身份。 */ entry: ArchiveEntry
  /** 所选真实交易日。 */ day: number | null
  /** 该报告存在的日期，不推定其他报告日期。 */ dates: number[]
  /** 选择日期回传。 */ onDay: (day: number) => void
}) {
  const [tab, setTab] = useState<'positions' | 'trades'>('positions')
  const [all, setAll] = useState(false)
  const [page, setPage] = useState(0)
  const validDay = day !== null && dates.includes(day)
  const query = useQuery({ queryKey: ['backtest-ledger', entry.run_id, entry.receipt_sha256, entry.report_sha256, all ? null : day, page],
    queryFn: ({ signal }) => fetchLedger(entry, all ? null : day, page * 50, signal), enabled: all || validDay, retry: false,
    refetchOnWindowFocus: false, refetchOnReconnect: false })
  const value = query.data
  return <aside className={`bt-date-detail${all ? ' bt-all-records' : ''}`} aria-label="所选日期持仓与盈亏">
    <label className="bt-date-picker">{all ? '完整交易记录' : '查看交易日'}<select aria-label="查看交易日" value={validDay ? day : ''} onChange={e => { onDay(Number(e.target.value)); setPage(0); setAll(false) }}>
      {!validDay ? <option value="">请选择报告内日期</option> : null}
      {dates.map(d => <option key={d} value={d}>{reportDate(d)}</option>)}
    </select></label>
    <div className="bt-segments" role="tablist" aria-label="日期明细">
      <button role="tab" aria-selected={!all && tab === 'positions'} onClick={() => { setTab('positions'); setAll(false); setPage(0) }}>持仓与盈亏</button>
      <button role="tab" aria-selected={!all && tab === 'trades'} onClick={() => { setTab('trades'); setAll(false); setPage(0) }}>当日交易</button>
    </div>
    {!validDay && !all ? <p role="status">该报告没有所选日期，请选择报告内交易日。</p> : <>
      {query.isFetching ? <p role="status">正在读取{value ? '，保留上次结果' : '日期明细'}…</p> : null}
      {query.isError ? <p role="alert">日期明细读取失败。{value ? '保留上次结果及原时间。' : ''}<button onClick={() => void query.refetch()}>重读明细</button></p> : null}
      {value ? <>
        {tab === 'positions' && !all ? <>
          {!value.positions_available ? <p role="status">当日持仓或盈亏数据未知。</p> : !value.positions.length ? <p role="status">当日日末空仓。</p> : <div className="bt-holdings">
            <div className="bt-holding-head"><span>证券 / 数量（份）</span><span>浮动盈亏（元）</span></div>
            {value.positions.map(p => <details key={p.symbol} className="bt-holding"><summary><span>{reportSymbol(p.symbol)}<small>{p.quantity} 份</small></span><strong className={gainClass(p.floating_cny)}>{backtestMoney(p.floating_cny)}</strong></summary>
              <div>累计已实现盈亏 <strong className={gainClass(p.realized_cny)}>{backtestMoney(p.realized_cny)} 元</strong></div></details>)}
          </div>}
        </> : <>
          {!value.trades_available ? <p role="status">该报告的原生成交明细暂不可用。</p> : !value.total ? <p role="status">{all ? '本报告没有成交。' : '当日没有成交。持仓可在另一页签查看。'}</p> : <>
            <div className="bt-trade-table" tabIndex={0} role="region" aria-label="原生成交明细"><table><thead><tr>{all ? <th>日期</th> : null}<th>证券 / 买卖</th><th>成交价 / 数量</th><th>费用（元）</th></tr></thead><tbody>
              {value.trades.map(t => <tr key={t.index}>{all ? <td>{reportDate(t.date)}</td> : null}<td>{reportSymbol(t.symbol)}<small>{side(t)} · {t.time.slice(8, 10)}:{t.time.slice(10)}</small></td><td>{t.price}<small>{t.quantity} 份</small></td><td>{backtestMoney(t.fee_cny)}</td></tr>)}
            </tbody></table></div>
            <div className="bt-pagination"><button disabled={page === 0} onClick={() => setPage(page - 1)}>上一页</button><span>{page + 1} / {Math.ceil(value.total / 50)} · {value.total} 笔</span><button disabled={(page + 1) * 50 >= value.total} onClick={() => setPage(page + 1)}>下一页</button></div>
          </>}
        </>}
        <p className="bt-read-time">读取于 {new Date(query.dataUpdatedAt).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })}</p>
      </> : null}
    </>}
    <button className="bt-all-button" onClick={() => { setAll(!all); setPage(0) }}>{all ? '返回所选日期' : '全部交易记录'}</button>
  </aside>
}
