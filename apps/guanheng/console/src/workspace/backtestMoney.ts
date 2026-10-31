/** 将报告十进制文本按分四舍五入显示；原文继续保留在报告，无浮点转换。 */
export function backtestMoney(value: string | null): string {
  if (value === null || value.length > 512 || !/^-?\d+(?:\.\d+)?$/.test(value)) return '不可用'
  const negative = value.startsWith('-')
  const [whole, fraction = ''] = (negative ? value.slice(1) : value).split('.')
  let cents = BigInt(whole) * 100n + BigInt((fraction + '00').slice(0, 2))
  if ((fraction[2] ?? '0') >= '5') cents++
  return `${negative && cents !== 0n ? '-' : ''}${(cents / 100n).toLocaleString('zh-CN')}.${String(cents % 100n).padStart(2, '0')}`
}
