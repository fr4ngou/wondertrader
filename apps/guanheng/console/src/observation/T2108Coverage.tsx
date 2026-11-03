import type { Row } from './types'

const count = (value: unknown) => typeof value === 'number' && Number.isFinite(value)
  ? value.toLocaleString('zh-CN', { maximumFractionDigits: 4 }) : '尚未取得'

export const sourceTypeLabel = (value: unknown) => value === 'sdk-synthetic' ? 'SDK演示数据，供功能验证'
  : value === 'actual-qmt' ? 'QMT当前等比前复权观察' : '来源类型尚未确认'

export const methodVersionLabel = (value: unknown) => value === 't2108.ashare/1' ? '原收盘参考核验口径'
  : value === 't2108.ashare/2' ? '供应商前复权序列口径' : '原观察口径尚未登记'

/** 将有效分母紧邻主数值显示，避免部分覆盖的样本比例被读成全市场比例。 */
export function T2108Coverage({ row, definitionVersion }: { row?: Row; mixedMethods?: boolean; definitionVersion?: string }) {
  if (!row) return null
  const method = row.method_version || definitionVersion
  return <div className="observation-note" role="note" aria-label="40期均线样本覆盖">
    <p><b>合格股票 {count(row.eligible_count)} / {count(row.market_count)} 只</b> · 覆盖率 {count(row.coverage_pct)}%</p>
    <p>均线上方 {count(row.above_count)} 只 · 等于均线 {count(row.equal_count)} 只 · 均线下方 {count(row.below_count)} 只</p>
    <p>尚缺日线 {count(row.missing_count)} 只 · 日线过期 {count(row.stale_count)} 只 · 不足40期 {count(row.insufficient_count)} 只 · {method === 't2108.ashare/1' ? '复权待核' : '前复权不可用'} {count(row.adjustment_unverified_count)} 只</p>
    {[row.empty_count,row.invalid_count,row.partition_count].some(value=>typeof value==='number' && value>0) && <p>缺失中：空结果 {count(row.empty_count)} 只 · 无效数据 {count(row.invalid_count)} 只 · 区间待补齐 {count(row.partition_count)} 只</p>}
  </div>
}
