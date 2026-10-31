import type { MarketChartBundle } from '../types'
import './source-history-status.css'

const preparation = {
  NotNeeded: '', CallReturned: '',
  Unknown: '历史数据更新结果待确认，请稍后重新读取。', Pending: '正在更新历史数据，请稍后重新读取。',
  Unavailable: '历史数据暂时无法补齐，请稍后重试。', NotSupported: '当前可读取的历史范围有限。', Budget: '本次历史数据更新已暂停，可稍后重试。',
}

/** 用户只需知道缺失范围和处理方式；来源身份保留在原响应供诊断核查。 */
export default function SourceHistoryStatus({ bundle }: { bundle: MarketChartBundle }) {
  const observation = bundle.source_observation
  if (!bundle.data_available || !bundle.candles.length || !observation) return null
  const partial = observation.state === 'Partial'
  const action = preparation[observation.preparation_state]
  if (!partial && !action) return null
  return <aside className="source-history-status" aria-label="行情提示" role="status">
    {partial ? <p>部分历史行情缺失，当前显示已取得的数据。</p> : null}
    {action ? <p>{action}</p> : null}
  </aside>
}
