import type { Range } from './types'
const DAY = 86400000
const time = (value: string) => Date.parse(value + 'T00:00:00Z')
const iso = (value: number) => new Date(value).toISOString().slice(0, 10)
export const presets = [['d5', '近 5 日'], ['w1', '最近一周'], ['d15', '15天'], ['d30', '30天'], ['m1', '近 1 月'], ['m3', '近 3 月'], ['m6', '6个月'], ['y1', '一年'], ['y2', '2年'], ['y3', '3年'], ['y4', '4年'], ['all', '全部']]
export function latestRange(range:Range, preset:string, coverage:Range, domain:Range):Range {
  if(preset)return presetRange(preset,coverage.end,preset==='all'?coverage:domain)
  return {start:iso(Math.max(time(domain.start),time(coverage.end)-(time(range.end)-time(range.start)))),end:coverage.end}
}
export function presetRange(key: string, end: string, coverage?: Range): Range {
  if (!presets.some(([id])=>id===key)) key='d30'
  const last = time(end); let start = last
  if (key === 'all') return coverage ? { start: coverage.start, end: coverage.end } : { start: end, end }
  if (key === 'w1' || key.startsWith('d')) start -= ((key === 'w1' ? 7 : Number(key.slice(1))) - 1) * DAY
  else {
    const date = new Date(last); const day = date.getUTCDate(); date.setUTCDate(1)
    if (key.startsWith('m')) date.setUTCMonth(date.getUTCMonth() - Number(key.slice(1)))
    else date.setUTCFullYear(date.getUTCFullYear() - Number(key.slice(1)))
    const month = date.getUTCMonth(); date.setUTCDate(day)
    if (date.getUTCMonth() !== month) date.setUTCDate(0)
    start = date.getTime()
  }
  return { start: iso(coverage ? Math.max(time(coverage.start), start) : start), end: iso(coverage ? Math.min(last, time(coverage.end)) : last) }
}
export function keyboardRange(key: string, range: Range, coverage: Range): Range | null {
  const lo = time(coverage.start) / DAY; const hi = time(coverage.end) / DAY
  let start = time(range.start) / DAY; let end = time(range.end) / DAY
  if (![lo, hi, start, end].every(Number.isFinite) || start > end) return null
  const total = hi - lo + 1; const size = Math.min(total, end - start + 1)
  let next = size
  if (key === 'ArrowUp') next = Math.max(1, Math.floor(size * .8))
  else if (key === 'ArrowDown') next = Math.min(total, Math.max(size + 1, Math.ceil(size * 1.25)))
  else if (key === 'ArrowLeft' || key === 'ArrowRight') start += Math.max(1, Math.round(size * .2)) * (key === 'ArrowLeft' ? -1 : 1)
  else return null
  if (next !== size) start = Math.round((start + end) / 2 - (next - 1) / 2)
  start = Math.max(lo, Math.min(hi - next + 1, start)); end = start + next - 1
  return { start: iso(start * DAY), end: iso(end * DAY) }
}
