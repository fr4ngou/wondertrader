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

可选 `security_names` 按本次返回的持仓和成交代码投影已准入证券目录，目录缺项时页面保留代码。线上表现的日期汇总显示实际或参考净值、正持仓项数、成交笔数，并按证券与方向合计已返回的成交份数和笔数。未知方向单列，部分或截断时标明汇总范围。选定日期的持仓和逐笔成交在主面板净值图下方，悬停只预览汇总，点击或日期选择固定明细。窄屏将日期和汇总放在图表前。每日持仓表与汇总只计正持仓，持仓表保留 `positions_observed_at` 原时间（旧响应沿明细原时间），成交及持仓均保留账户范围或ASA归属。运行与持仓页沿各自来源时钟合表展示，见[目标仓位历史](strategy-target-history.md#sth3-页面与验证)。对照验收使用同证券、同取样时间及相同范围，覆盖零仓位、盘中快照推进和历史日期。

验收覆盖真实普通安装发布文件→新模块→原读池HTTP→策略页面、双身份匹配、跨scope/基准隔离、原时间和每日缺口、实际成交去重/未知归属、空/失败、并发/独占/取消、停止/来源异常及有界读取。源码、普通安装、真实来源和页面交付分别登记。


## LSP-5 同账户多策略归属读取

已发布的冻结阶段作为展示事实读取：校验版本、策略/配置/证券身份和目标数量结构，复制原冻结目标，并核对原提交读回。展示层不构造执行规划状态，不重新计算数量或验证该旧阶段当前是否有资格继续交易。净值、现金、费用资格由各自发布字段独立呈现；净值尚未核实仍保留有效持仓、目标和同轮其他策略。真实执行恢复继续沿原规划器完整核验。读取失败在原Web日志记录异常类型及最多八个代码位置，保留原503语义；异常正文、局部变量和来源资料不进入日志。

状态：accepted / source-validated，普通安装及实际采用另验。原配置CTA结果按 `strategy_id` 逐项验证和选择；目录汇集同轮全部身份，原单策略无参数查询保持兼容。多策略无选择的旧summary只保留旧策略，不将任意map顺序当选择。显式ID不存在时返回空选择，禁止退回其他策略。原版线上身份与原版WT回测身份分别保留来源版本。

有 `allocation_observation` 的发布使用ASA原 `strategy_observation` 同一只读事务：自有份额、可卖、现金、原已提交目标、实际D分配和账本身份摘要。新增DTO字段均可缺，旧字段消费者保持兼容。实际D投影数量/金额/费用复用原持久allocations及原费用分配函数，内部转移不标实际柜台成交。手续费待确认提示沿自有账本笔数，报价缺失时继续展示；最近合格估值使用已核收益的原估值时间。发布只保留最近2000条且显式 `fills_truncated`，原账本不删。原成交时刻缺失时保持成交组partial，不能以App刷新时间生成买卖点；费用未知保持None。原owner读取时刻只表明当前归属账被观察，不表明任何价格估值。

App按账本摘要+策略ID/版本隔离展示历史，当前进程身份仍逐代核实。同ETF两个策略分别复制各自持仓与原D分配，`attribution=strategy-allocated`。缺ASA成交投影时该策略成交保持unavailable，不能按NAP的同代码补入。旧单策略NAP路径保持 `account-universe-only`，界面明确账户聚合、策略归属未确认。账户页及详情的账户组保留原范围，并单列来源说明；策略详情持仓优先ASA。

ASA现金以独立cash_observed_at/cash_runtime_scope_id保留原归属观察时间及运行来源，NAV的observed_at仍只用于估值；ASA现金可独立显示；缺原策略估值/连续资金流时NAV、PnL、收益率和曲线保持未知，不能用账户现金、账户PnL或初始额度制造NAV。目标沿原已提交ASA意图或原WT分策略signals文件；缺意图不补零。原版九证券沿来源完整集合展示，读取器不施加旧八证券合同。

验收：两个真实profile的原发布文件可读；共用ETF自有持仓与成交互不污染；原版9证券；单策略旧接口及NAP语义；按id切换、缺源降级、目标/持仓/现金独立于净值、原成交时间和费用未知、原账本无新增写入；页面保持既有布局及选择器。

原版profile报告通过已核ctx映射发布definition（ID、线上版本、完整九证券）；归属或行情暂缺仍保留真实声明。旧发布缺声明时保持证券范围未知。Retained共享归属等待态waiting_allocation有独立中文标签；此时缺ASA不得复制全账户库存。详情assignment.scope在ASA路径为strategy-allocated，账户组自身仍为全账户。


## LSP-6 ASA自有组合估值与参考曲线

状态：accepted / implementation（v3）；v2冻结保留。估值唯一owner为Native策略profile，在原回调借用内只读当前ASA快照和原context.quote/tick，调用shared owned_valuation；观衡只复制原结果。估值不改资金账、费用、目标、原金融指纹或策略准入，不创建线程、来源查询或另一报价owner。估值错误只降级展示。

每个正持仓均需同一回调已核原价CNY/份，tick精度及报价上海时刻沿原quote_value。报价不足/过期/未来/错误维度为unavailable，现金空仓无需报价即可估值。自有真实现金与所有实际费用已知时state=actual，nav=cash+持仓原价市值。费用未确认时actual现金/NAV保持null；可发布state=reference-fee-pending和reference_nav=原ledger_cash+市值，明确只扣已知费用、尚未扣未知费用；不能把未知费用填0或模型费。市值按每份原价乘自有份额求和；金额最终ROUND_HALF_UP到分，独立于Decimal上下文。

基准仅取原已配置资本声明（原版initial_capital_cny，旧策略capital_baseline.total_cny或原policy.initial_capital_cny），不取账户总资产。相对配置资本变化额/率属于reference_change_cny/reference_return_pct，明确不是现金流调整后的投资收益；return_pct保持null。现金owner时刻、每证券报价clock、估值计算clock及基准来源/SHA分别保留。报价历史截至估值clock准入，App读后不重新赋价；估值未知时保留最后已核点及原时间，并显示本轮原因。WT提供可用的资金流收益及其上次已核实际净值时，摘要使用该估值资格和原时刻，展示“上次已核净值时间”。该摘要不补造日线点，不沿用其他估值的参考金额、盈亏或报价时间。

曲线沿原布局区分实际NAV实线与“参考净值（手续费待确认）”虚线；日观察仅保留该日最后合格估值及资格，引用与实际字段分列。actual point_count继续仅统计实际点，reference_point_count和对应日期范围单列；参考线不冒充实际净值历史。v3历史key含ASA账、策略ID/版本、估值schema及基准声明SHA，与v2纯持仓/账户delta历史隔离；新费用事实补齐后同日参考点可由更晚实际估值替换。

验收：真实ASA+两个实际profile本地quote getter整链（无Source/金融）验证100w空仓首点、持仓缺价/过期、未知费用参考线、后补费用实际NAV、共同ETF自有估值隔离、原金融指纹五字段原字节及原目标/账/权限不变；原NAP单策略兼容；已有浏览器曲线/悬停/切换及资格中文标签。

本次线上角色费用范围沿ASA-5：coordinator只入原Source fee_cny及已确认实际FeeFact，未知None；Native fees/fee_bound仅预留。纯ASA独立模拟输入和模型费不授此角色实际净值资格，QA合成费用明确为实际费用替身；本切片不改变费用持久格式或状态机。

持仓与目标仓位表独立展示逐标的参考市值。当前合格报价缺失或超过原有效期时，观衡沿显式配置的 WT 只读报价入口批量查询最新已验证原始报价，按本轮已归属的实际份额乘以该证券报价。休市、跨日和重启后仍可展示最近报价，保留原证券报价时间，并明确标注“按最近报价”。仅接受已核证券、原价币种和原报价时钟，未来报价或查询失败保持已取得的同轮数据。参考市值不进入 WT 当前估值、资金、收益、手续费或交易资格。最近报价由App独立的有界读取owner补充：复用BoundedReader的单线程和一个排队位，同一时刻仅一批报价在途；页面主请求只投影内存中最后成功报价并合并刷新需求，不等待网络。报价缓存、待刷证券及逐证券投影错误各最多采用协议MAX_SYMBOLS（64）个最近使用项，超过时淘汰旧项，后续读取可重新刷新；此界限只管理展示资源，不形成交易限制。来源查询使用既有MarketClient配置预算，不续期、不创建交易或新持久记录。失败保留原成功价格及原时钟，未知保持未知，错误变化及恢复记入既有Web日志。App退出先停止核心读取，再按原总关闭截止回收报价owner；重启由原报价来源重新取得最近值。

ASA详情先固定所选策略快照，整条ASA详情分支跳过NAP；账户聚合沿券商账户页独立读取。NAP失败/耗D不改变ASA归属或现有总D，缺归属标“等待确认策略归属”。原默认单策略仍读取原账户分组。
