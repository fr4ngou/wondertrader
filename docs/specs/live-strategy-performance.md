# 线上策略实际发布观察

类型：功能规格。状态：accepted / delivered。前缀：LSP。范围：观衡只读策略页及本地观察历史，事实归原WT/券商发布者。

## LSP-1 身份和当前状态

GET `/v1/ui/live-strategy-performance` 必填 strategy_id、strategy_version，可选 limit=90（1–366日），拒绝额外、重复参数和请求正文。严格匹配WT同轮实际发布的策略ID及版本。当前标记还需WT/执行组件ready、原执行生命周期和OS进程身份核实；状态未知保持false。历史数据不授当前运行资格。来源断开影响对应数据，行情服务不可用不单独改变执行状态。

消费者沿原 CURRENT → Runtime → execution.business_observation → ready/strategies → Runtime读取并核同代；原时间和全部身份由原发布者提供。Runtime与execution两个PID都要实际存活，进程创建时间均不得晚于原execution-started事件；原Runtime已退而执行仍在时保持非当前。非当前选择返回not_current，资金、日记录和标记为空。CURRENT读取或身份核验失败返回503，浏览器按同查询保留旧值及原时间。

## LSP-2 金融口径

本轮NAV、PnL、现金与市值仅复制原 strategy-capital-observation 及其基准，人民币金额保留十进制字符串。原WT的CTA资金/交易CSV属于理论账，依据WT-S资金及WT-T08通道能力分别标识，不能充当券商实际成交。当前发布broker-cash-delta含账户现金变化影响；资金流与策略归因缺失时return_pct=null，明确缺少连续投资收益资格。

持仓沿WT已发布券商持仓，成交沿现有NAP完整四查询中的deal分组；两者保留独立原时间。NAP成交无策略归属时仅筛选所选策略证券，并声明attribution=account-universe-only。买卖点属于这些实际账户成交，前端显示归属未确认；未知买卖方向保留unknown，不猜。完整空成交与来源不可用分别为empty/unavailable。账户名称、原环境、凭据、文件路径和原订单号不进入新接口，成交ID使用稳定摘要。

## LSP-3 观察历史及恢复

原发布目前提供当前值，缺少连续实际NAV历史。App在受控watchlist_root下拥有live-strategy-observations.sqlite3及独占租约，保存经原边界验证的展示副本；它不拥有或修改交易账本。构造无IO，原读池调用capture_current，在App生命周期内每30秒观察一次，无额外来源请求、交易调用或daemon线程。GET可同时观察当前值。读取上限按日索引分页，历史保留不设策略交易配额。

current.scope_id包含完整WT身份、执行身份、策略ID/版本和基准SHA，隔离当前标记及缓存。经济历史key独立：对已核broker-cash-delta资本，完整cash_anchor含账户/环境/CNY身份、原基准及初始P/A/价格原件，原金融owner只建一次并在正常恢复时复用。history_scope_id由逻辑instance、策略ID/版本、完整基准及完整现金原点摘要组成，正常重启可连续；换账户、基准、原点或版本严格隔离。缺少明确原点的旧发布限本运行代并说明缺证明。每个NAV/持仓/成交观察保留完整原运行scope作provenance，当前标记仍只认当前真实代。

每个数据组按真实来源时间归上海日期，同日保留最后真实观察，旧来源不覆盖新来源，摘要与曲线共用同一归约。刷新时间不替换来源时间，不补缺日，不将账户数据观测时刻当作NAV估值时刻。真实成交去重后累积于其原交易日；同原成交ID的旧来源不回退较新事实。成交上海完整时刻须不晚于原完整查询完成/接收时刻及当前时刻，坏行明确partial。重启后继续已证同经济scope，单写者租约及SQLite事务保持完整；取消/超时回滚未提交观察。停止后可保留同scope最后数据，当前标记关闭。

NAP的原账户绑定在原ready/完整正文/Runtime前后根核验成功后通过内部可选binding_observer回调提供，LSP只计算{account,environment,currency:CNY}摘要。默认读取返回和所有旧调用保持。摘要与资本现金原点账户摘要一致时，才将NAP成交纳入该经济历史；明文账户和环境不保存或回传。

没有个人观察根时仍显示当前快照，coverage.history_state=snapshot-only；首次真实观测可仅单点。两种模式统一最多2000条成交展示，超限明确deals_truncated/partial，完整历史不删除。历史不足、金额/持仓/成交分别缺失时，各组保持空/未知状态。已建库写入失败且原租约/身份完整、历史仍可验证读取时，history_state=degraded-readonly-history，将只读历史与当前真实快照按同规则合并，说明本轮尚未保存；不改原来源。总D/取消、租约/身份冲突、持久格式损坏保持明确失败。

## LSP-4 API及验收

顶层为schema_version、read_only、observed_at、state、reason、requested、current、coverage、baseline、summary、daily、markers。current.scope_id是完整身份摘要；baseline.scope_id是本次基准原件摘要。coverage使用实际来源首尾日期、点数及basis=actual-published-observations。daily含date、observed_at、nav_cny/cash_cny/market_value_cny/pnl_cny/return_pct及独立positions/deals和状态；positions/deals可用性不由NAV存在性推定。金额和份额单位分别为元、份；日期ISO、时间保留原交易时刻及上海时区解释。

验收覆盖真实普通安装发布文件→新模块→原读池HTTP→策略页面、双身份匹配、跨scope/基准隔离、原时间和每日缺口、实际成交去重/未知归属、空/失败、并发/独占/取消、停止/来源异常及有界读取。源码、普通安装、真实来源和页面交付分别登记。
