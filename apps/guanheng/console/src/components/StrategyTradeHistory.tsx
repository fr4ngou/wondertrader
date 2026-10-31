import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchOrders } from '../api'
import { EmptyState } from './EmptyState'
import { absoluteChinaTime } from './RelativeTime'

const statuses: Record<string, string> = { pending: '待处理', received: '已接收', submitted: '已提交', partially_filled: '部分成交', filled: '已成交', cancelled: '已撤单', rejected: '已拒绝', failed: '失败', expired: '已到期', duplicate: '重复', error: '异常' }
export function StrategyTradeHistory({ strategyId }: { strategyId: string }) {
  const [symbol, setSymbol] = useState('')
  const [from, setFrom] = useState('')
  const [until, setUntil] = useState('')
  const [offset, setOffset] = useState(0)
  const filters = { strategy_id: strategyId, symbol: symbol.trim(), created_from: from ? new Date(`${from}T00:00:00+08:00`).toISOString() : '', created_to: until ? new Date(`${until}T23:59:59.999+08:00`).toISOString() : '', limit: 20, offset }
  const query = useQuery({ queryKey: ['strategy-orders', filters], queryFn: ({ signal }) => fetchOrders(filters, signal), retry: 1, staleTime: 15_000 })
  const data = query.isError ? undefined : query.data
  return <section><div className="card-heading"><div><h2>历史交易记录</h2><span>按策略标识查询历史委托，包含各版本；资本纪元归属见因果链。</span></div></div>
    <div className="reader-filters"><label>证券<input value={symbol} placeholder="如 510300.SH" onChange={e => { setSymbol(e.target.value); setOffset(0) }} /></label><label>开始日期<input type="date" value={from} onChange={e => { setFrom(e.target.value); setOffset(0) }} /></label><label>结束日期<input type="date" value={until} onChange={e => { setUntil(e.target.value); setOffset(0) }} /></label></div>
    {query.isError ? <EmptyState title="交易记录不可用" detail="委托账本读取失败，请稍后刷新。" /> : !data ? <EmptyState title="正在读取交易记录" detail="正在读取所选策略的历史委托。" /> : !data.items.length ? <EmptyState title="当前筛选下没有交易记录" detail="已完成本次账本查询。" /> : <div className="reader-table-scroll"><table className="reader-table"><thead><tr><th>时间</th><th>证券</th><th>方向</th><th>委托量 / 成交量</th><th>成交均价</th><th>模式</th><th>状态</th><th>详情</th></tr></thead><tbody>{data.items.map(item => <tr key={item.command_id}><td>{absoluteChinaTime(item.created_at)}</td><th>{item.symbol}</th><td>{item.side === 'buy' ? '买入' : item.side === 'sell' ? '卖出' : '撤单'}</td><td>{item.quantity} / {item.filled_quantity ?? '不可用'}</td><td>{item.average_fill_price ?? '不可用'}</td><td>{item.execution_mode === 'simulation' ? '模拟盘' : '实盘'}</td><td>{statuses[item.status] ?? item.status}</td><td><Link to={`/orders?strategy_id=${encodeURIComponent(strategyId)}&correlation_id=${encodeURIComponent(item.correlation_id)}`}>因果链</Link></td></tr>)}</tbody></table></div>}
    <div className="reader-pagination"><button disabled={offset === 0 || query.isFetching} onClick={() => setOffset(Math.max(0, offset - 20))}>上一页</button><span>{data ? `共 ${data.total} 笔 · 第 ${offset / 20 + 1} 页` : '记录数量不可用'}</span><button disabled={!data?.has_more || query.isFetching} onClick={() => setOffset(offset + 20)}>下一页</button></div>
  </section>
}
