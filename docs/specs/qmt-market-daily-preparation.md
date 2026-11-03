# 全市场日线缓存准备与批量捕获

状态：accepted。范围：WT外部HPR准备、v8捕获与原身份续接。
架构决策见[ADR0021](../architecture/adr/0021-market-daily-cache-preparation.md)，
接口见[模块](../modules/qmt-market-daily-preparation.md)，操作见[手册](../runbooks/qmt-market-daily-preparation.md)。

## MDP1 职责与来源

WT外部来源工作流使用原HPR `market.history_prepare` 更新QMT缓存，随后用原v8
`market.market_data`分别读取none/front_ratio。证券全集来自调用者固定版本的证券池；
证券池属于业务输入，格式准入不代表证券存在或当日应有交易。
内置SDK仍是原策略线程调用四参数 `download_history_data`，不增加策略文件、网络或线程。
官方内置API声明单证券下载；官方列表示例逐证券调用。列表读取沿原get_market_data_ex。

## MDP2 显式能力

HPR沿原v6 profile/操作/策略/结果，新增显式
`qmt.history-preparation-limits.v3`，与v2相同字段、额度、截止和单次SDK语义，证券格式接收
六位代码.SH/.SZ/.BJ。v1/v2保持原沪深准入。BJ下载资格取实际SDK回包及后续读取证据；
格式合格与已有BJ日线可读证据分别登记。旧配置和金融通道保持原语义。

## MDP3 有界与恢复

一次工作流固定原请求、证券池摘要、两来源连接身份和缓存日期窗口；每个HPR slot固定
原UUID、参数、业务截止、完整结果及consumed。重进相同目录先核配置和原请求，已有slot
只续核原ID；未知、404/410、丢确认保持原责任，禁止换ID重复下载。确定拒绝保留原件，
由操作方建立下一次明确观察。原Host Journal和票据拥有通信事实。

首次准备前通过原RetainedReadClient分别准入HPR与v8完整binding，持久保存原
HPR-BINDING及capture/BINDING；后者继续由原BatchAnalysisSource消费。暂停后续接
先核两端当前认证与固定binding，再允许任何新准备或批读。旧ID与未知责任保持原值，
来源变化结束当前工作流准入。正式CLI还固定实际连接配置；完成包离线重读不访问来源。
公开run在创建目录、slot或进入原ID等待前拒绝bool、非数字和NaN/Inf绝对D。

工作流总截止、单请求截止与每次最多处理数量分别有界；额度不足暂停原工作流，后续继续。
新slot在容量等待完成后生成原请求；容量等待与每次原结果续核分别最多使用原scope的一次
total_timeout_ms观察预算，均受同一工作流剩余D约束。旧请求的UUID、参数和deadline_ms
保持原值，后继观察预算仅限定查询等待，不延长SDK或重新提交原未知请求。
进度文件仅索引原slot，不清Journal、不制造已完成事实。并行仅在终端外使用独立客户端；
每个slot唯一工作线程。所有已提交工作在原请求截止内退出后才返回。

正式外部CLI可在原BoundHistorySource显式选择有界HTTP复用。连接仅属于该运输实例的
最外层rpc_budget，嵌套沿原较小预算，每次交换沿原绝对截止；作用域退出即关闭。每次
交换使用原认证规则，不缓存签名或nonce。异常退役连接并返回原未知/异常，连接层不
重放失败请求。服务端主动关闭后的后继交换可以新建连接；关闭失败保留连接owner和
异常链。默认单次交换关闭与金融调用继续原行为；不新增常驻池、线程或请求额度。

## MDP4 覆盖及消费

HPR call_returned仅证明原SDK函数返回。全部HPR确认后，原v8持久消费方保存原批次结果并
确认消费，输出既有C包。每个证券的none/front引用同一原批次身份和真实接收时间；不伪造
独立请求或时间。实际日期、空/缺失/无效分别保留；缓存尾早于目标日不等同数据损坏，停牌、
上市、交易日及复权/共同闭合基准由C与原QNA按实际材料核定。

## MDP5 增量与发行

初次准备使用业务日期窗口；已有成功捕获时，后继观察可显式以原实际尾日重叠更新，保持
至少40期所需的原读取窗口。工作流不创建定时任务，不逐轮强制重复多年下载。相同工作流
完成后离线重读不再调用SDK；新观察使用新业务身份。正式安装、SDK替身、真实切片与
全市场真实数据分别记录资格，合成数据不得进入真实指标。

## MDP6 显式缓存优先观察

新请求使用schema=`guanheng.market-daily-preparation.v2`并明确mode=`cache-first`；其余capture、preparation、source_association沿原结构。v1目录、原349类slot及结果保持原契约，新模式使用新的独占业务目录，不迁移、重标或覆盖旧请求。操作员总观察预算独立于请求身份，可以显式修订；已派发正文/票据/SDK截止保持，未知继续原ID。

新模式先沿原v8捕获cache，保存完整原绑定、批次、结果、实收时间和consumed。按`t2108.ashare/2`实际数据口径核front_ratio：观察尾日等于capture.end_date、至少40条实际记录、最后40个close均有限且为正。none/front_ratio沿原请求end_date指定复权参考，保存原共同日期/basis；不伪造因子资格或历史首次可知。合法空/缺失、过期、暖机不足、非正价格及来源不可读分别列明。格式/身份或绑定错误保持失败，不能当缺数据去下载。

只为实际缺口生成固定PLAN：暖机已足但尾日落后时，从原实际尾日的次日补到目标日；暖机不足时补授权起点到原最早缓存日的前一日，尾日缺口单独补；无缓存时才用完整授权窗口。缓存已足的范围不重复下载；需要修订的非正价格只补其有限日期区间。单次计划最多每证券三个有界区间，合并相交区间；准备范围始终在preparation授权窗口内。无法通过准备修复的分片/来源错误保留明确不可用状态。新PLAN及每个原slot唯一拥有一个调用，沿原HPR/v6/v3、原容量/并发/单SDK/票据规则推进。

全部计划缺口责任确认后，沿原v8对全池实际回读到capture；初次缓存全池已足时，直接封存该次真实cache捕获，避免重复SDK读取。RESULT.capture明确记录最终捕获目录cache或capture。准备成功仅说明call_returned，最终QUALITY按原数据重算，不依据准备回执填就绪。所有证券都在质量清单中，部分覆盖按原T2108口径保留，full_coverage仅在全池合格时成立；没有合格观察时返回明确source_unavailable，不发布合格RESULT。正常完成封存原capture与QUALITY摘要，旧epoch/未知仍保留原ID。新命令暂停后复用原cache/PLAN/slot和请求，不再生成已尝试身份。

MDP只拥有缓存观察/缺口编排与资格索引；原Host拥有通信责任、Agent拥有SDK、BatchAnalysisSource拥有原捕获，观衡仍拥有指标计算与ready发布。不得新增并行服务、定时器或另一套重试/Journal。完整全A执行须显式授权；工程验证先走至多同一小切片真实入口，再复用既有回归，不扩新测试矩阵。


MDP6新增持久字段（日期均为原市场日YYYYMMDD；实收时间沿原带时区来源字符串）：

| 对象/字段 | 定义与缺失语义 |
|---|---|
| REQUEST.schema / mode | 显式v2协议及cache-first编排选择，v1默认语义保持。 |
| CACHE-QUALITY / QUALITY.schema / qualification | 本地质量索引版本及原T2108数据口径版本；不新增行情来源。 |
| observation_date / minimum_rows / securities | 原capture.end_date、固定40期、原请求证券总数。 |
| counts / eligible_count / full_coverage | 各互斥原因证券数、合格数、全池全部合格布尔值；零合格沿原不可用类。 |
| rows[symbol].reason / eligible / status | 本地口径分类、合格布尔值、原front_ratio来源状态。 |
| rows / first_date / last_date | 原前复权实际行数及首尾日；无数据日期为null，行数为0。 |
| bad_close_dates / warmup_insufficient | 最后40行非正收盘日数组、原行数不足40布尔值。 |
| source_received_at / adjustment / reference_end_date | 原front批次实收时刻、front_ratio、原请求复权参考尾日；不冒充首次可知时间。 |
| original_common_basis / capture_sha256 | 原none/front共同尾日（无共同日为null）、完整原manifest字节摘要。 |
| PLAN.schema / qualification / cache_sha256 / tasks | 计划版本、口径版本、初次实读摘要及固定有限准备区间数组。 |
| tasks.index / symbol / start_date / end_date / reason | 原slot序号、证券、SDK允许起止日、缺口原因；一个任务对应一个原HPR责任。 |
| PROGRESS.required_preparations / cache_eligible_count | 固定PLAN区间总数及初次缓存合格数；不表示下载次数或最终覆盖。 |
| RESULT.mode / capture / quality_sha256 | 编排模式、最终捕获目录（cache或capture）、完整QUALITY字节摘要。 |
| RESULT.coverage_qualified / eligible_count / required_preparations / qualification | 全池合格布尔值、实读合格数、原计划区间数、原数据口径版本。其他字段沿原结果定义。 |

MDP6字段声明旁逐项保留中文说明：QUALITY引用当次原捕获/实收时刻，PLAN固定初次缓存缺口，PROGRESS只表示阶段准备责任，RESULT表示最终实读封存。计数分别标明证券只数、记录条数、任务项数或批次份数；市场日YYYYMMDD、SDK止日、带时区实收时间与本地UTC封存时间分别声明。空数组、0、None及False按各字段原义保留，完成阶段不替代数据覆盖资格。此注释补充保持原Python AST及请求/slot/材料责任。


## MDP7 v2新请求准入余量

仅v2显式把minimum_new_request_seconds=30传给原批捕获和原HPR执行器，再沿原RetainedReadClient的新slot分支执行。单位为外部单调观察截止剩余秒数，默认0保留v1及其他消费者行为。检查位于当前绑定认证之后、transport.plan及slot落盘之前；不足30秒时返回固定read_new_request_budget_exhausted，不生成新ID/SDK正文/票据/slot。已有slot绕过新准入检查，始终沿原ID/票据/已派发deadline核查及保存/consumed。原SDK单次上限、ticket、Host、容量、吞吐及结果未知分类保持。

CLI保持原Pending退出协议，以固定原因明确表示本阶段停止新准入。监督owner仅对该确定的未准入原因记录admission-paused并在原绝对总截止内续阶段，复用同根已有slot；其他Pending/失败仍停止。整个原CLI可串行包含初读、本阶段HPR和最终回读，外部阶段观察预算应覆盖整条链，不能把单个子阶段预算当整次run预算。阶段延长不修改既有短deadline或Unknown原件，独立后继观察以新业务身份明确登记。

HPR单次原call_deadline最多scope时限，外部新准入余量应比较整次CLI观察截止：内部new_request_observation_deadline参数传外部单调截止秒值，缺省沿原deadline；它只用于新准入判断，不扩大原call_deadline、SDK deadline或票据。两个截止的职责分别保留。
