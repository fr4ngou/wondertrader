import type { ArchiveEntry } from './backtestApi'
import { backtestMoney } from './backtestMoney'

/** 日期、百分比和选择标签仅生成文字，不引入图表或完整报告组件。 */
export const reportDate = (n: number) => `${String(n).slice(0, 4)}-${String(n).slice(4, 6)}-${String(n).slice(6, 8)}`
export const reportPct = (n: number | null) => n === null ? '未知' : `${n.toLocaleString('zh-CN', { maximumFractionDigits: 4 })}%`
export const reportKey = (e: ArchiveEntry) => e.run_id + e.receipt_sha256
/** 报告序号仅用于区分选项，本金取完成证明绑定的归属摘要或已核验绩效；标签不参与金融推断。 */
export const reportLabel = (e: ArchiveEntry, capital?: string, number = 1) => `报告${number} · ${capital === undefined ? '本金待读取' : `${backtestMoney(capital)}元`} · 至${reportDate(Math.floor(e.configuration.end / 10000))} · ${e.record_count}期`
