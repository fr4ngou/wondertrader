import type { HistoricalSummary } from './backtestHistorical'

const shanghai = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit',
  day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' })

export default function HistoricalBacktestSummary({ value }: { value: HistoricalSummary }) {
  return <section aria-label="历史回测输入说明">
    <h3>历史日线回测</h3>
    <p>策略：{value.strategy_id} · 版本 {value.strategy_version}</p>
    <p>本批实际接收：{shanghai.format(new Date(value.historical_model.received_at))}（上海时间）。回测按交易日 15:00 日末模型计算。</p>
    <p>源成交金额单位未知，本次按元解释。历史首次可知时间和修订记录未知，结果仅供历史回测使用。</p>
    <details><summary>查看回测输入依据</summary>
      <p className="backtest-hash">数据批次 SHA256：{value.historical_model.dataset_sha256}</p>
      <ul>{value.qualification_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
    </details>
  </section>
}
