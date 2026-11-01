/** 金额显示只改变阅读单位；原值和导出正文始终保持。 */
const exactNumbers = new Intl.NumberFormat('zh-CN', { maximumSignificantDigits: 21 })
export function amountUnit(unit?: string) {
  return unit === '元' || unit === '人民币元' || unit === '万元' || unit === '亿元'
}

export function exactObservationValue(value: unknown, unit?: string): string {
  if (value == null) return '不可用'
  return typeof value === 'number' && Number.isFinite(value)
    ? exactNumbers.format(value) + (unit || '')
    : String(value)
}

export function observationNumber(value: unknown, unit?: string, exact = false): string {
  if (value == null) return '不可用'
  if (typeof value !== 'number' || !Number.isFinite(value)) return String(value)
  if (exact) return exactNumbers.format(value)
  if (amountUnit(unit)) {
    const yuan = value * (unit === '万元' ? 10000 : unit === '亿元' ? 100000000 : 1)
    const scale = Math.abs(yuan) >= 100000000 ? [100000000, '亿'] as const
      : Math.abs(yuan) >= 10000000 ? [10000000, '千万'] as const
        : Math.abs(yuan) >= 10000 ? [10000, '万'] as const : [1, ''] as const
    return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 4 }).format(yuan / scale[0]) + scale[1]
  }
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 4 }).format(value)
}

export const observationDisplayUnit = (unit?: string) => amountUnit(unit) ? '元' : unit || ''
