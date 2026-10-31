import type {Row} from './types'

const metrics=new Set(['breadth.ashare','trin.ashare','rana.ashare','turnover.gt5.ashare'])
export function FieldCoverage({metric,row}:{metric:string;row?:Row}) {
  if(!metrics.has(metric)||!row)return null
  const count=(key:string)=>typeof row[key]==='number' ? row[key] as number : 0
  const turnover=metric==='turnover.gt5.ashare'
  const fields:[string,string][]=[['identity_unverified_count','股票池资格待核'],['state_unverified_count','交易状态待核'],['missing_quote_count','行情尚缺']]
  if(!turnover)fields.push(['missing_price_count','涨跌比较价尚缺'])
  if(metric==='trin.ashare')fields.push(['missing_volume_count','涨跌组成交量尚缺'])
  if(turnover)fields.push(['missing_float_count','可用非限售股本尚缺'])
  const issues=fields.filter(([key])=>count(key)>0).map(([key,label])=>`${label} ${count(key)} 只`)
  if(turnover&&count('turnover_missing_count')>0&&!issues.length)issues.push(`换手资格尚缺 ${count('turnover_missing_count')} 只`)
  const references=!turnover ? count('special_reference_count') : 0
  const halted=count('halted_with_trades_count')
  if(!issues.length&&!references&&!halted)return null
  const percent=typeof row.turnover_confirmed_lower_bound_pct==='number'
    ? new Intl.NumberFormat('zh-CN',{maximumFractionDigits:4}).format(row.turnover_confirmed_lower_bound_pct) : undefined
  return <aside className="observation-message" role="status">
    {issues.length>0&&<p>来源缺口：{issues.join('；')}。已取得的其他字段继续展示。</p>}
    {turnover&&row.turnover_gt5_pct==null&&<p>完整市场占比暂缺。{percent!==undefined&&<>已确认至少 {percent}%，待缺口补齐后确认完整比例。</>}</p>}
    {!turnover&&count('unclassified_count')>0&&<p>涨跌统计按已确认样本阅读；尚缺股票保留在股票池中。</p>}
    {references>0&&<p>{references} 只首日或新增交易证券采用来源参考价，参考价不代表前一日真实成交价。</p>}
    {halted>0&&<p>{halted} 只证券有停牌标志且当日已有成交，计入当日统计。</p>}
  </aside>
}
