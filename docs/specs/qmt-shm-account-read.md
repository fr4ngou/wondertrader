# QMT共享内存账户只读接入

状态：accepted。类型：跨模块功能规格；要求前缀QAR。账户读取开发及共享内存接入已获授权，具体实现、安装、真实SDK和用户入口分别验收。框架文件修改、终端重启、生产切换及真实交易沿既有具体授权边界。本规格只定义读取适配。

## 目标与原生复用

将共享内存账户读取接入现有原生账户观察链，使独立观衡服务和中文账户页面能够显示持仓、委托、成交、资金的实际查询结果、来源与未知项。正式运行链脱离旧终端HTTP及旧QMT工程。

复用[原生能力目录](../development/wondertrader-capabilities.md)WT-T01、WT-T02、WT-T04及[账户展示规格](native-account-console.md)的原TraderAdapter四查询、统计、owner pump和有限进程。WT负责原生对象、账户统计及执行边界；本适配只承担固定只读函数、通信来源和字段转换。金融字段规则只保留一个运输无关mapper。ManagedTrader的共同基线、资本服务及逐单审批不进入本链。账户观察不增加余额/持仓数据库。

本规格扩展[QSW](qmt-shm-wt-binding.md)和[显式能力决策](../architecture/adr/0005-explicit-read-capabilities.md)；[ADR-0006](../architecture/adr/0006-account-read-source-boundary.md)规定来源职责，[ADR-0007](../architecture/adr/0007-account-observation-read-state.md)规定只读进程恢复边界。旧NQB/NQH的fixture及HTTP安装证据保留原资格；新来源按本规格验收。

## 完整链与所有者

~~~mermaid
sequenceDiagram
    participant UI as 独立观衡服务/账户页
    participant Scan as 受管AccountScan owner
    participant WT as 原TraderAdapter/只读插件owner
    participant Worker as 只读worker/共用C++ Core
    participant Host as 认证Host/通信Journal
    participant Agent as QMT原策略线程
    UI->>Scan: 固定部署来源，单轮有限观察
    Scan->>WT: 正常初始化，登录和原四查询
    WT->>Worker: 固定datatype值任务
    Worker->>Host: 绑定校验，原请求身份及绝对D，单次持久受理
    Host->>Agent: 认证SHM，只读operation
    Agent->>Agent: 三参数SDK，白名单投影，同截止finalizer
    Agent-->>Host: 原结果bytes，observation=null
    Host-->>Worker: 原终态/原三B/原SHA
    Worker-->>WT: 有限不可变值事件
    WT->>WT: owner验整批/唯一mapper/一次Rsp
    WT-->>Scan: inspection v3冻结值与关闭证明
    Scan-->>UI: IPC v2，公开DTO 2.0，账号掩码
~~~

部署owner选择唯一账户、环境、币种、金融profile及认证能力；请求不能选择账号。Agent原线程独占SDK及结果finalizer；Host不调用SDK。worker只运输普通值，owner独占BaseData、WTS对象和SPI。原账户Scan每轮新实例，顺序仍为position→order→deal→account；查询失败停止后续交付，已完成组保留逐组资格，整轮不授成功。没有执行器、历史成交push或写调用。

## QAR-R1 显式能力与配置

封闭operation为account.trade_detail，policy为qmt.account-read.v1、版本1.0。新增read-profile版本qmt.read-profile.v3；形状仍为五字段read_profile_version/read_operations/execution_timeout_ms/control_profile/operation_profiles。v3必须显式包含account.trade_detail，可同时包含已登记market.full_tick及market.history_1m，操作精确排序去重；各descriptor仍只有policy_id/policy_version/execution_timeout_ms/limits。顶层执行毫秒为各descriptor最大值。新C++共用Core完整理解所发布v3；各业务门面只调用其编译期固定操作。旧v1/v2字节、默认选择及拒绝未知语义保持。旧客户端默认仍选择其已理解版本；需要消费组合v3的行情/历史调用者通过显式新版本选择接缝升级，配置未声明v3时不自动扩授。v3共用profile校验与各固定operation的数据validator分别组织，避免用profile版次推断业务操作。

账户limits精确为schema_version/account_binding/max_rows/max_nodes/max_scalar_chars/max_data_bytes，schema_version=qmt.account-read.v1。account_binding精确四字段：account_id（1..63个UTF-8字节，禁止C0/DEL/C1控制字符和非成对surrogate）、account_environment（simulation或live）、currency=CNY、financial_profile=cny_cash_shsz_v1。这是受管配置声明，不证明已登录的券商身份。

额度精确整数、拒绝bool：max_rows=1..4096，max_nodes=1..65536，max_scalar_chars=1..262144；max_result_bytes须8192..2097152，max_data_bytes=1024..min(1048576,max_result_bytes-4096)。完整profile实际canonical UTF-8仍<=4096B。额度来源是受管配置；两端使用同一纯validator，不能借Host构造假SDK对象验证配置。descriptor与完整profile原bytes由B.capability_sha256绑定。Journal、三B、认证、base control、wire和order_ready=false保持QSW原语义。

只有显式账户descriptor及实际注入的只读callable同时存在，Agent才开放账户操作；缺少任何一项在连接/SDK前拒绝。生成入口只以globals中固定名称get_trade_detail_data注入该callable，禁止通用函数名、动态任意反射、passorder/cancel、导入旧Agent或set_account。旧行情profile构造无账户依赖。

## QAR-R2 请求与原线程SDK

原八字段请求及认证端点保持。operation_id=account.trade_detail，arguments精确三个字段：account_type=stock、datatype取position/order/deal/account、scope=account。外部account_id、strategy_name、cursor、offset及任意额外参数均拒绝。priority_class仍normal，timeout_ms在100..descriptor.execution_timeout_ms内。

唯一SDK调用为get_trade_detail_data(bound_account_id,'stock',datatype)，恰好三参数，第四参数策略过滤保持缺席。初始化/关闭不查询，I/O线程不查询，单次tick至多处理一项。SDK不可抢占；同一monotonic执行截止覆盖调用前、调用后、每次getter/NumPy item、遍历、投影、DTO编码和原结果finalizer后的发布检查。超期仅形成原ID失败终态，原函数不重调。

## QAR-R3 AccountQueryBatch数据契约

成功data精确七字段，schema_version=qmt.account-batch.v1：

| 字段 | 精确含义与约束 |
|---|---|
| account_binding | R1四字段及origin=trusted_bootstrap_argument；原受管绑定，不推导券商登录 |
| query | account_type=stock、datatype原请求值、scope=account、strategy_name=null |
| execution | started_at/completed_at，UTC RFC3339，Z结尾、固定6位微秒；包括SDK与字段投影，completed_at>=started_at；最终编码仍受同一monotonic截止 |
| completeness | complete=true、truncated=false、row_count精确实际行数、coverage=sdk_returned_list；只证明返回list完整投影 |
| trading_date | value=null、source=unavailable；执行日期不替代券商交易日 |
| rows | 有限JSON对象数组，字段白名单见R4 |

通用终态observation恒为null。SDK返回必须精确内建list；None、tuple、迭代器等不当作空成功。position/order/deal完整空list成功；account必须恰一行。数量超限整批失败，不截断、不以重复SDK调用冒充翻页。SDK自身缓存、隐藏上限及查询时刻未知，coverage不宣称柜台事务一致快照。

所有层拒绝重复/额外键、错误版本/范围/原生类型、非有限数及身份冲突。row_count、原data UTF-8片段大小和整终态共同验限；C++不重编码浮点来替换原SHA或字节预算。末次binding及三B仍须与原receipt一致。

## QAR-R4 账户字段投影与唯一金融映射

Agent按datatype封闭白名单复制字段；dict与SDK对象遵守同表，每个getter至多读一次，未知字段/方法/备注不读取、不传播。对象getter异常整批失败；正常缺字段保持省略，null/0/bool/字符串保持原值。允许精确JSON标量及可信SDK NumPy标量item后的精确JSON标量；拒绝容器、任意自定义转换、方法、非有限数、非法Unicode和绝对值超过2**53-1的整数。缺失必需字段由唯一原生mapper失败；Agent不另实现金融计算或状态机。

字段表复用现ViewSchemaV2.h，并提取为跨运输唯一命名表。字段总表如下；每行均另允许m_strAccountID/m_strMoneyType。m_strAccountID存在时必须为精确绑定账号，null或空串均判冲突。m_strMoneyType的精确字符串空串表示来源未提供币种，原DTO保留空串；唯一C++ mapper将其source_currency事实表达为unknown/null及明确原因。省略币种仍为unknown；非空币种必须精确匹配受管currency=CNY，null、错误类型及明确冲突仍拒绝。不猜测币种别名，不把空串重写为CNY。WTS ABI采用受管声明CNY，其来源是trusted_bootstrap_argument，不能宣称由SDK空币种证明。

| datatype | 允许字段（除上述两项） |
|---|---|
| position | m_strInstrumentID,m_strExchangeID,m_nVolume,m_nCanUseVolume,m_nYesterdayVolume,m_nFrozenVolume,m_nOnRoadVolume,m_dAvgPrice,m_dOpenPrice,m_dPositionProfit,m_dFloatProfit,m_dMarketValue |
| order | m_strInstrumentID,m_strExchangeID,m_strOrderSysID,m_nOffsetFlag,m_nVolumeTotalOriginal,m_nVolumeTraded,m_nVolumeTotal,m_nOrderStatus,m_dLimitPrice,m_dCancelAmount,m_strInsertDate,m_strInsertTime |
| deal | m_strInstrumentID,m_strExchangeID,m_strOrderSysID,m_strTradeID,m_nOffsetFlag,m_nVolume,m_dPrice,m_dTradeAmount,m_strTradeDate,m_strTradeTime |
| account | m_dBalance,m_dAvailable,m_dPreBalance,m_dCommission,m_dFrozenCash,m_dFrozenMargin,m_dFrozenCommission,m_dPositionProfit,m_dFloatProfit |

原生mapper保持[原NQH字段/现金profile规则](native-qmt-http-bootstrap.md)，先整批核对再SPI。原股/份不乘100；持仓V/A为aggregate-only，不由V-A推冻结或T+1。账户总资产不再加浮盈，冻结现金不冒充保证金。Q/F/U、买卖48/49、原事件时间、派生成交ID和空userTag沿已核唯一算法。可选字段缺失/null保持unknown，原类型无效标invalid；WTS中性槽与事实分别表示。C++新SHM来源先验证本DTO，再交运输无关AccountMapping，旧HTTP只保留历史envelope薄门面，禁止伪造旧source来复用。

## QAR-R5 容量、失败及原请求恢复

行数、节点、累计标量字符、data实际UTF-8、完整终态及QSW各层预算取共同准入。节点按DTO每个值和对象键各计一次，字符按每个键和字符串的Unicode码点累计；共享字符串重复出现重复计量。投影在复制前和复制中验限，不能先展开任意原对象。原生SDK自身分配不受Python投影预算约束。编码逐片计字节并检查deadline，最后同owner的唯一finalizer再验完整终态。view仍16MiB、Scan帧20MiB，两值总40MiB、stderr64KiB；这些是声明的逻辑上限，不是RSS限制。

使用现有失败终态source_shape_invalid/source_value_invalid/result_too_large/qmt_call_failed/execution_timeout/owner_required/invalid_request；错误消息固定中文，不含私有账号或原始异常。失败data=null、observation=null，零SPI交付。停止、线程归属、回调排空、join及超期保留依赖沿原只读插件owner，不新增第二个关闭状态机。

C++账户门面复用BoundReadCore唯一认证codec及create→submit_once→原ID GET路径。create生成不可复制的一次令牌；原receipt（原请求ID/op/body字节、摘要、语义及B）只在本轮活进程的有限内存中保留。submit_once只消费一次令牌。无保留票据的账户读取在首个POST之前，将原调用剩余截止投影为同机GetTickCount64绝对毫秒，放入Host专用HTTP外层execution_deadline_uptime_ms；原SDK请求正文不变。Host以该截止收紧首次排队期限，重复原字节/ID继续返回同一记录并保留首次期限。

若首个POST运输结果不确定，原GET得到完整、标准unknown_operation的404，仍在该submit_once原D内时允许一次原HTTP正文/ID/B/绝对截止的再投递。Host原事务查重负责单次持久受理和单次SDK执行。公开receipt继续只有原ID续查能力；resume、已过原D、其他404或不完整响应均不触发再投递。具体原ID未确认时返回SubmissionUnknown并保留原身份，不将404改成永久接口故障或“未执行”。prepare/create失败零POST；不回退终端HTTP。

每轮必须新进程、新TraderAdapter及插件实例；每阶段只交付一次SPI。丢失进程后不恢复上一轮客户端查询、不加载旧批次，不将旧数据赋给新scan_id。父owner确认旧子树已回收后，后续明确刷新可创建新的scan_id、Adapter和原请求ID，取得新的只读观察。原Host可能已经执行旧读取；其Journal继续保存原派发/终态，晚结果只关联原请求。产品页面在失败或刷新时保留原时间的上次成功结果，按[NAC-R7](native-account-console.md#nac-r7-中文用户入口)分别标注本轮失败和旧批；后端新结果仍按本轮产生，不合并前轮持仓/委托/成交统计。四批实际执行时点与SDK缓存限制保持可见。

账户展示不新增客户端跨进程收据文件、恢复目录、根锁、累计目录或字节配额。Host既有Journal的认证、持久受理、容量和终态职责保持，历史CLI的分页导出持久恢复保持独立规格。真实下单/撤单有外部经济副作用，其unknown必须另按交易执行契约保留原命令身份及核查路径；本条只适用于固定四个读取操作，order_ready=false和写拒绝保持。

## QAR-R6 原生观察、Scan与公开消费者版本

部署trader.source=qmt_shm_bound，trader.read_profile_version=qmt.read-profile.v3，金融profile仍cny_cash_shsz_v1。ReadOnlyTrader为final；其Impl显式持有固定账户client分支，实例一次init后来源不变，旧终端HTTP不作运行回退。Diagnostics v1、工厂及现导出函数签名保持；新inspection.version=3、view=0..4，行金融facts/abi共享mapper。

Scan仅在内存trader装配中注入runtime_deadline_ns，为同一原生进程steady-clock域内原started+total_ms截止的精确正int64纳秒值。runtime_deadline_ns、已撤销的runtime_receipt_directory/runtime_scan_id均禁止出现在部署JSON或用户请求中；后两者也不再由宿主注入。固定MSVC产品明确核时钟表示，init/connect/task/client与close取同一个父绝对截止及各本地更早预算，禁止重新起算父总期限；API单步不可抢占，未完成回调保留依赖，父Job承担最终进程回收。

新Scan部署配置schema_version=2，顶层精确为schema_version/installation_root/library/base_data/trader/budget六字段。安装/库/基础文件继续原句柄锁定及SHA准入。trader沿原固定只读字段，source改qmt_shm_bound并必填read_profile_version；base_url/key_id_env/hmac_secret_env指终端外认证Host，禁止终端HTTP自动回退。max_response_bytes在1..16777216内显式声明；prepare还须满足公布的4*ceil(max_result_bytes/3)+16384联合下限（result=2097152时为2812588），旧HTTP envelope的2MiB上限只保留在旧来源分支。request/round/close/total/view/rows沿既有预算关系并共用父绝对截止。

CLI保留--config与--scan-id两个公共必需选项；schema2受管启动额外必需私有选项--config-sha256，其值为应用准入配置时所读取原始文件bytes之64位小写十六进制SHA256。AccountScanConfig.from_paths将本次已有raw bytes同时交给同一个纯validator核对不可变configuration后计算内部摘要；直接构造schema2须显式提供相同raw bytes，不接受自报digest。raw只在准入时使用，实例只保留不可变配置和摘要。每轮owner不再次读文件、不持配置句柄、不递归锁目录或治理重解析目标链；配置变更需重新准入，旧实例的摘要使native读取不同bytes时明确失败。native对同一次File.read_config取得的body先核摘要，匹配后才parse、装载及连接；不同bytes、摘要缺失或混版一律失败关闭，相同bytes可来自合法别名路径。原配置读取API单步晚回后只清理，禁止继续恢复运行；私有摘要仅通过该child命令参数传递，不改父全局环境，不输出到公开DTO，不替代插件/基础文件已有SHA或安装资格。schema1保持原五参数CLI且拒绝该新选项；不接收--receipt-directory。配置不接受recovery字段或私有恢复路径，旧七字段schema2候选按未知键拒绝，不作自动降级。schema1原形状及既有行为保持。schema2严格准入后接应用唯一受管owner，缺少owner在创建资源前明确拒绝；配置静态准入只说明支持该入口，实际来源可用性由本轮有界查询决定。匹配的原生/IPC2与真实公开主路径证据分别记录，完整安装和故障矩阵另验。

view3 summary.batches[].source在成功交付批次精确为kind/account_id/account_environment/transport_binding/binding_sha256/broker_session；kind=qmt_shm_bound，transport_binding保留完整B，broker_session为{availability:unknown,value:null,reason:未取得券商登录会话证据}。未交付批次source可为null，summary顶层不增加source。每批各自保留query/执行区间/请求ID/原SHA和完整性；不声称四批同一柜台事务。旧view2中agent_id/qmt_session_id原义保持，不以transport_generation填入。

部署文件和公开IPC沿原UTF-8契约。仅在自有Scan把内存trader交给原WTSCfgLoader的边界，用标准RapidJSON ASCII目标编码生成JSON Unicode转义，防止Windows原loader的CP_ACP转换改变字符串；loader解码后的字符串须保留原UTF-8值，禁止中文特判、替换字符或降低绑定校验。原输入bytes摘要先验、数值/bool、原绝对截止与金融映射保持；公开帧继续原UTF-8编码，WT源码和接口保持。

view3行复用既有AccountMapping的逐类结构：position/deal/account精确包含version/view/index/identity/facts/abi；order另必需price_type，其形状精确为availability/value/reason，availability=unknown、value=null、reason为非空文本。这是原生映射已保留的价格类型未知事实；观衡不得因该正常字段拒绝整行，也不得用ABI中性priceType推断真实价格类型。其他额外字段继续拒绝，公开价格类型保持unknown；旧schema1准入行为保持。

Scan IPC schema=guanheng.account-scan.v2，仍只有observation与completion两种长度前缀值帧；绑定原scan_id、view3及部署来源。客户端请求身份只在R5限定的活进程内保留，不塞公开账户值。父进程复用单轮/16等待者的owner与现有已验Job生命周期，创建时绑定Job、隐藏窗口、共用单一总截止，父死亡实际回收子树，管道实际排空。正常close需要closed/joined、worker_live=false、queued=0和匹配退出码；强制回收诚实标forced。

NAC公开schema_version=2.0。group.source.kind=qmt_shm_bound，账号仅account_label掩码，环境保留；transport精确为host_instance_id/transport_generation/route/capability_sha256，broker_session保留上述unknown事实。公开值不包含原账号、secret、原receipt或私有路径。原账户HTTP路由可复用；部署选择来源，用户请求不选账号/运输方式。页面封闭接受2.0并用中文区分运输绑定和登录未知；正常/空/部分失败/不可用和本地50行分页共同验收。新版源不得写入旧1.0槽位，旧安装与证据保留。

## QAR-R7 安装、验收与运维

Python Agent3.6.8标准库、Host锁版本包、C++客户端/插件/Scan完整CRT及观衡应用分别构建发行，同一候选记录完整源码/配置/安装身份；旧树不存在仍能运行。既有WT纯上游08b230dd05facf6d650d949bfe51054115a2ecb1为原Adapter验证来源；其他框架差异不进入新候选。自有构建源清单加入新文件，不改变WT虚接口。

部署顺序为离线新配对/配置→验证安装与能力→获准载入Agent→新Host→原生四查询→业务HTTP/中文页；实际终端载入/重启、生产切换及交易另按具体授权。失败保持原实例和归档，只撤新来源资格。旧终端HTTP退役路线不恢复。小型或大型动态验收均先满足后台隐藏和进程回收要求；当前停启动阶段只读写文件，测试定义不等同实际运行证据。

| ID | 可执行验收入口与证明范围 |
|---|---|
| QAR-R1 | Python profile/Host/pair纯契约：默认v1/v2黄金bytes；v3账户及组合；混版/缺SDK/未知字段/额度放大拒绝；C++同fixture |
| QAR-R2 | 注入替身独立记录线程/精确3参数/四datatype；请求越权和初始化关闭零调用；SDK/转换/编码晚回同截止失败 |
| QAR-R3 | 三B/原bytes/SHA/范围/空list/None/account多行/来源冲突等契约与实际SHM闭环 |
| QAR-R4 | 对象和dict等价、getter一次、未知敏感字段零读取、137/19持仓、各不同Q/F/U、资金及原金额/时间，原Adapter sink独立oracle |
| QAR-R5 | 每个预算及联合边界、一次token/单次持久受理及SDK执行；首个POST运输未知后，标准unknown_operation只在原submit_once/D内原字节再投递至多一次，Host按原绝对截止准入且去重不续期；公开receipt/resume仍仅原GET；其他404、原D结束保留未知。进程死亡旧轮失败、实际回收后新Adapter/新ID新观察；晚回/切代零重复SPI、无客户端收据目录、Host容量及回调关闭异常 |
| QAR-R6 | 固定原Adapter四批实际SPI、晚回/join/父死亡/单总截止、v3→IPC v2→DTO2.0→中文页正常/空/异常/分页 |
| QAR-R7 | 新非editable安装、完整原生包搬迁、旧树缺席、独立full审查、同身份实际用户入口；真实SDK资格单列 |

## 未取得的真实来源资格

SDK函数是否在本安装提供、大小写参数、实际字段与CNY/股/份单位、账户/币种返回值、列表缓存/隐藏限制、登录与权限、事件时间和缺字段/空账户形态均需本仓新制品的获准只读验证。源码形态和合成测试只授对应软件资格；通信成功不授交易资格。后续证据归[证据索引](../evidence/README.md)，本规格不填假通过状态。

## QAR-R公开入口接线（2026-10-28 accepted，开发验收）

按主路径优先，schema2通过现有严格配置准入后，公开账户读取委托给应用唯一ManagedAccountScan，不再由开发期固定False阻止运行。默认未配置仍不可用；缺受管owner的直接schema2调用仍拒绝，保持同轮总预算、配置摘要、创建期Job、IPC/管道及未知资源保留。

依据本机真实C++四查询/正常回收主路径与真实Host两代读取，继续验证GET /v1/ui/account/overview和capabilities、应用收尾。该接线没有新增执行权限，不把主路径结果扩展为45项完整异常、独立安装、浏览器或生产发行资格；这些结果分别记录，正式发布沿原完整门禁。
