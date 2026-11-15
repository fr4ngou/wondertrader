import type { Definition,Line,Row } from './types'

export function automaticUpdateLabel(scheduler?:{enabled:boolean;state?:string;last_heartbeat?:string|null},lastStatus?:string) {
  if(!scheduler)return '自动更新状态暂不可用'
  if(!scheduler.enabled && scheduler.state==='stopped')return '自动更新已停止'
  if(scheduler.state==='not_running_or_stale')return scheduler.last_heartbeat?'自动更新心跳已过期，请查看更新与缺口':'自动更新尚未收到心跳，请查看更新与缺口'
  if(!scheduler.enabled)return '自动更新尚未启用'
  if(scheduler.state && scheduler.state!=='running')return '自动更新心跳异常，请查看更新与缺口'
  if(lastStatus==='failed')return '最近定时更新失败'
  if(lastStatus==='partial')return '自动更新已运行 · 部分来源待补'
  return '自动更新已启用'
}

export function localSchedulerLabel(process?:{state:string;label:string;error?:string|null}) {
  if(!process)return '本实例调度状态暂不可用'
  if(process.state==='independent')return '由独立观察服务更新'
  if(process.state==='disabled')return '本实例未托管调度'
  return `本实例调度：${process.error || process.label}`
}

export function displayedUnit(line:Line,definition:Definition,mode:string) {
  if(definition.board==='crossmarket' && ['hscei_rebased','a_rebased'].includes(line.key)) return mode==='raw_panels'?'指数点':mode==='window_return'?'%':line.unit
  return line.unit
}
export function displayedPrimary(definition:Definition,rows:Row[],mode:string) {
  const key=definition.primary_field
  if(definition.board!=='crossmarket' || !['hscei_rebased','a_rebased'].includes(key))return rows.at(-1)?.[key]
  if(mode==='raw_panels')return rows.at(-1)?.[key==='a_rebased'?'a_close':'hscei_close']
  if(mode==='window_return'){
    const first=rows.find(row=>typeof row[key]==='number')?.[key];const last=rows.at(-1)?.[key]
    return typeof first==='number' && first>0 && typeof last==='number' ? (last/first-1)*100 : null
  }
  return rows.at(-1)?.[key]
}

const statuses: Record<string,string> = {
  publication_unknown:'发布结果待核查，请保留原窗口身份',
  success:'更新成功',partial:'部分来源更新成功',failed:'本次更新失败，保留原版本',
  checked_disclosure:'已检查披露页面，新增附件解析待接纳',
  no_new_observations:'已检查，未取得新观察',
  version_restored:'已切回核验过的数据版本',
  snapshot_imported:'已接纳固定历史版本',
}
const sources: Record<string,string> = {
  'ashare-public-day':'沪深北日终广度与换手',
  'wondertrader.indices':'统一行情指数',
  'qmt.t2108':'40期均线股票覆盖',
  'wt.etf_flow':'主要 ETF 总份额与价格',
  'wt.csi300_etf_cap':'沪深300 ETF 市值占比',
  'tencent.indices':'指数行情','baostock.pb':'沪深逐股PB','shenwan.801003':'申万A指估值与成交',
  'chinabond.gov10y':'国债10年收益率','cffex.daily':'中金所期指与期权','sse.options':'上交所ETF期权',
  'szse.options':'深交所ETF期权','sgx.a50':'新交所A50','eastmoney.margin':'两融汇总','eastmoney.shibor':'Shibor利率',
  'chinamoney.irs':'Shibor3M互换','chinamoney.repo':'回购定盘','eastmoney.northbound':'北向成交',
  'eastmoney.marketcap-gdp':'月末市值与GDP','pbc.disclosures':'央行机构统计','nfra.disclosures':'保险统计',
  'eastmoney.annual':'年报盈利与回报','eastmoney.executive':'高管增减持',
  'eastmoney.annual.ashare':'沪深北年报盈利与回报','eastmoney.executive.ashare':'沪深北高管增减持',
  'wealth.disclosures':'银行理财统计','fund.disclosures':'基金与机构披露',
  'fund.allocation':'基金资产配置','pbc.large-bank':'大型银行人民币资金运用',
  'csindex.000985':'中证全指价格',
}
export const statusLabel = (code:string) => statuses[code] || '结果待核实'
export const sourceLabel = (id:string, fallback = '其他数据来源') => sources[id] || fallback
const repairInputs: Record<string,string> = {
  'csi300_etf_cap.ratio': '四只沪深300 ETF 市值与指数自由流通市值',
  'structure.ipo_supply': 'IPO 减持供给回购比',
  'structure.ipo_supply.close': '科创50收盘',
  'structure.ipo_supply.ipo': 'IPO 募资额 · 20 日窗口',
  'structure.ipo_supply.reduction': '重要股东减持毛额 · 20 日窗口',
  'structure.ipo_supply.buyback': '披露回购执行增量 · 20 日窗口',
  'structure.broker_heat': '券商交易生态过热',
  'structure.broker_heat.purchase': '融资买入额 · 252 日窗口',
  'structure.broker_heat.relative': '东方财富与证券 ETF 价格 · 20 日收益',
  'structure.broker_heat.support': '沪深300价格 · 20 日收益',
  'margin_summary_fin_balance': '融资余额',
  'margin_summary_fin_buy': '融资买入额',
  'margin_summary_fin_net_reported': '报表披露的融资净买入额',
  'margin_summary_fin_repay': '融资偿还额',
  'margin_summary_short_balance': '融券余额',
  'margin_summary_total_balance': '两融余额',
  'etf_flow.512890': '红利低波 ETF（512890）',
  'etf_flow.510050': '上证50 ETF（510050）',
  'etf_flow.510300': '沪深300 ETF（510300）',
  'etf_flow.588000': '科创50 ETF（588000）',
  'etf_flow.159949': '创业板50 ETF（159949）',
  'etf_flow.159781': '双创50 ETF（159781）',
  'source.market_structure.000688': '科创50收盘',
  'source.market_structure.000300': '沪深300收盘',
  'source.market_structure.932000': '中证2000收盘与成交额',
  'source.market_structure.stock': '全市场股票横截面',
}
export const repairInputLabel = (id:string) => repairInputs[id] || id
const frequencies: Record<string, string> = { daily: '日度', weekly: '周度', monthly: '月度', quarterly: '季度', yearly: '年度', intraday: '日内', event: '按披露更新', irregular: '不定期' }
export const frequencyLabel = (frequency: string) => frequencies[frequency] || frequency
export function failureLabel(code?:string) {
  if (!code) return '检查记录已保存；实际末期见来源覆盖'
  if (code === 'wt_source_not_registered') return '这一来源仍待接入 WT 数据模块'
  if (code === 'wt_history_incomplete') return 'WT 发布范围仍有缺失交易日'
  if (code === 'wt_t2108_historical_universe_missing') return 'WT 尚缺该日的历史股票池'
  if (code === 'wt_t2108_historical_universe_unqualified') return '该历史股票池的当日来源待核实'
  if (code === 'wt_repair_failed') return 'WT 本轮补采未成功，保留已发布数据'
  if (code === 'ashare_current_feed_has_different_date') return '公开行情已切换交易日，所需日期原件尚缺；继续提供原版本'
  if (code === 'ashare_capture_retry_pending') return '日终原件等待下一次计划重试；当前继续提供原版本'
  if (code === 'ashare_capture_retries_exhausted') return '今日原件捕获已达重试上限，下一自然日继续核验；当前提供原版本'
  if (code === 'ashare_archive_missing') return '所需历史日期的原件尚缺，完整口径重算等待补齐'
  if (code === 'ashare_source_date') return '尚未取得所需交易日的全市场原件，继续提供原版本'
  if (code === 'ashare_source_not_closed') return '全市场日线尚未确认收盘，本批暂未接纳'
  if (code === 'ashare_source_status_unqualified') return '来源出现待核的证券交易状态，继续保留原版本'
  if (code === 'ashare_source_coverage') return '沪深北股票池或原件覆盖尚未齐全，继续保留原版本'
  if (code === 't2108_no_qualified_observations') return '本批尚无同日且满40期有效前复权收盘的股票，保留原指标'
  if (code === 't2108_source_not_closed') return '日线闭合时间尚未核实，本批暂未接纳'
  if (code === 't2108_ready_not_available') return '所需交易日的40期均线原件尚未到达，继续显示原数据'
  if (code === 'market_source_not_configured') return '统一行情读取连接尚未配置，继续保留历史数据'
  if (code === 'market_source_unavailable') return '统一行情暂未提供这组指数日线，继续保留原值；需要补齐对应来源'
  if (code === 'market_no_observations') return '所选日期尚未取得指数日线，继续保留原值'
  if (code === 'market_volume_unit_unknown') return '来源尚未确认成交量单位，本批数据暂未接纳'
  if (code.includes('timeout')) return '来源请求超时，下个窗口重试；当前继续提供原版本'
  if (code.includes('permission') || /401|403/.test(code)) return '来源拒绝访问，保留原版本；需要核对来源许可或权限'
  if (code.includes('rate_limit')) return '来源限制请求频率，已停止本批请求；稍后按计划重试'
  if (code.includes('not_published')) return '来源尚未提供所需观察日，待下一更新窗口复查'
  if (code.includes('schema') || code.includes('identity') || code.includes('incomplete')) return '来源格式、身份或完整性校验未通过，当前批次暂未接纳'
  return '本批来源未通过检查，继续保留原版本；请维护人员核对更新记录'
}
