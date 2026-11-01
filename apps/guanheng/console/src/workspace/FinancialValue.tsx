import { observationNumber } from '../observation/numbers'

/** 展示金额使用中文数量单位；悬停保留来源原值，数量、价格和日期沿各自口径。 */
export function FinancialValue({ value }: { value: number | string }) {
  const numeric = typeof value === 'number' ? value : value.trim() ? Number(value) : NaN
  if (!Number.isFinite(numeric)) return <>{value}</>
  const exact = typeof value === 'number'
    ? value.toLocaleString('zh-CN', { maximumFractionDigits: 20 }) : value
  return <span title={`${exact}元`}>{observationNumber(numeric, '元')}</span>
}
