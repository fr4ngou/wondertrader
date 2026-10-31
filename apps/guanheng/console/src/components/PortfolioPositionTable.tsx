import { Clock3, CircleAlert, CircleCheck } from 'lucide-react'

import type { PortfolioPositionsSnapshot } from '../types'
import { diagnosticLabel } from '../diagnosticPresentation'
import { EmptyState } from './EmptyState'

const cny = new Intl.NumberFormat('zh-CN', {
  style: 'currency', currency: 'CNY', maximumFractionDigits: 2,
})

function money(value?: number | null) {
  return value == null ? '—' : cny.format(value)
}

function ageLabel(seconds: number) {
  if (seconds < 60) return `${Math.round(seconds)} 秒`
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟`
  return `${Math.round(seconds / 3600)} 小时`
}

export function PortfolioPositionTable({
  projection,
  loading = false,
  compact = false,
}: {
  projection?: PortfolioPositionsSnapshot
  loading?: boolean
  compact?: boolean
}) {
  if (loading && !projection) {
    return <EmptyState title="正在读取持仓" detail="从 Bridge 的最新权威账户快照读取。" />
  }
  if (!projection?.data_available) {
    return <EmptyState title="账户持仓不可用" detail={diagnosticLabel(projection?.missing_reason, '权威账户快照暂不可用。')} />
  }
  if (!projection.items.length) {
    return projection.snapshot_stale
      ? <EmptyState
          title="最后快照显示空持仓"
          detail={`账户快照已过期（约 ${ageLabel(projection.snapshot_age_seconds)}前）；这里只能确认快照时点没有持仓，QMT 与账户恢复后才能确认当前状态。`}
        />
      : <EmptyState title="当前账户没有持仓" detail="权威账户快照新鲜可用，持仓列表为空；这不是加载失败。" />
  }
  return (
    <div className={compact ? 'position-projection position-projection-compact' : 'position-projection position-projection-full'}>
      <div className="position-projection-head" role="row">
        <strong>标的</strong><span>持仓 / 可卖</span><span>最新价</span>
        {!compact && <span>成本价</span>}
        <span>市值</span>
        {!compact && <span>浮动盈亏</span>}
        <span>数据状态</span>
      </div>
      {projection.items.map((item) => (
        <div className="position-projection-row" role="row" key={item.symbol}>
          <strong>{item.symbol}</strong>
          <span>
            {item.quantity.toLocaleString()} / {item.available_quantity.toLocaleString()}
            {item.frozen_quantity > 0 && <small>冻结 {item.frozen_quantity.toLocaleString()}</small>}
          </span>
          <span>{item.last_price == null ? '—' : item.last_price.toFixed(3)}</span>
          {!compact && <span>{item.cost_price == null ? '暂未提供' : item.cost_price.toFixed(3)}</span>}
          <span>{money(item.position_value)}</span>
          {!compact && (
            <span className={item.unrealized_pnl == null ? '' : item.unrealized_pnl >= 0 ? 'positive' : 'negative'}>
              {item.unrealized_pnl == null ? '暂未提供' : money(item.unrealized_pnl)}
            </span>
          )}
          <small className={item.quote_stale === false ? 'position-state-ok' : 'position-state-warning'}>
            {item.quote_stale === false ? <CircleCheck size={13} /> : item.last_price ? <Clock3 size={13} /> : <CircleAlert size={13} />}
            {item.quote_stale === false
              ? '报价新鲜'
              : item.last_price
                ? '报价已过期'
                : item.valuation_source === 'account_snapshot'
                  ? '快照估值'
                  : '缺少估值'}
          </small>
        </div>
      ))}
      <div className="position-projection-foot">
        <span>{projection.snapshot_stale ? '账户快照已过期' : '账户快照有效'} · {Math.round(projection.snapshot_age_seconds)} 秒前</span>
        <strong>
          {projection.valuation_complete ? `持仓合计 ${money(projection.total_position_value)}` : `${projection.missing_valuation_symbols.length} 个标的缺少估值`}
          {!compact && ` · ${projection.unrealized_pnl_complete ? `浮动盈亏 ${money(projection.total_unrealized_pnl)}` : `${projection.missing_unrealized_pnl_symbols.length} 个标的暂无柜台浮盈`}`}
        </strong>
      </div>
    </div>
  )
}
