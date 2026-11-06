import { useQuery } from '@tanstack/react-query'
import { fetchArchiveConfiguration, type ArchiveEntry } from './backtestApi'
import { reportDate } from './BacktestVisualChart'
import { ORIGINAL_CASH_EXECUTION } from './originalNativeIdentity'

/** WT原模型与现金缺口来自同一完成证明，读取失败保持未知。 */
export default function OriginalNativeModel({ entry, label }: {
  /** 绑定WT父完成证明的不可变报告。 */ entry: ArchiveEntry
  /** 主报告或对比报告的业务标签。 */ label: string
}) {
  const query = useQuery({ queryKey: ['original-native-model', entry.run_id, entry.receipt_sha256, entry.report_sha256],
    queryFn: ({ signal }) => fetchArchiveConfiguration(entry, signal), retry: false, staleTime: Infinity })
  const model = query.data?.original_native
  const cashConstrained = model?.execution_model === ORIGINAL_CASH_EXECUTION
  return <details className="bt-method" open><summary>{label} · WT 回测模型与数据</summary>
    {query.isPending ? <p role="status">正在核验原生回测模型与现金缺口…</p> : null}
    {query.isError ? <p role="alert">原生模型说明读取失败，现金缺口状态未知。<button onClick={() => void query.refetch()}>重读模型说明</button></p> : null}
    {query.data && !model ? <p role="alert">该报告未提供原版 WT 模型证明，模型和现金缺口保持未知。</p> : null}
    {model ? <><p>{cashConstrained
      ? '现金约束版：保留原版 BUY/SELL 信号，按 D 日已知收盘价设置 WT 原生限价目标，买入本金与费用上界一起受实际现金约束；未成交卖出款保持未到账。跳空超过限价时保留原意图，后续按当时已知价格和现金继续设置，因此买点、数量和成交笔数会与旧版不同。'
      : '回测由 WT 原生历史时钟、仓位和 CtaMocker 撮合推进。D 日信号先按可卖与冻结份额形成合法目标，已提交目标在下一模拟 tick 撮合，通常为下一交易日开盘；原生日线的成交记录时间戳可能为 15:00。'}冻结 SELL 的余量保留至可卖。采用真实 OHLC、100 份整手，费用来自该报告绑定的 WT 资料。</p>
      <p>评价区间 {model.evaluation_window.from} 至 {model.evaluation_window.to}；额外暖机日 {model.evaluation_window.warmup_date}。原始信号算法与执行模型、整手和费用分别核验。</p>
      <p>{cashConstrained ? '本报告采用 WT 原生限价撮合与策略现金约束。' : '旧版按 D 日净值和价格规划次日目标，CtaMocker 未自动限制股票现金购买力，次日跳空可能产生负现金。'}{model.cash_deficit_count ? <strong role="alert">本报告有 {model.cash_deficit_count} 个负现金日，首日 {reportDate(model.cash_deficit_dates[0])}，这会影响收益结果的可执行性。</strong> : '本报告核验的负现金日为 0。'}</p>
      <p>来源及历史首次可知时点资格仍待核实，报告用于历史研究。</p>
    </> : null}
  </details>
}
