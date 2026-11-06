# 交易执行与账户观察

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

保留1.1.2的实时薄桥可显式消费A已发布分析窗口，复用原C解码/计算、原日线Reader和NSQ；启动固定周期及原金融状态保持。[NRT-R24](../specs/native-realtime-strategy.md#nrt-r24-已发布分析窗口的持续消费)定义配置、等待及原恢复身份；[安装证据](../evidence/2026-10-30-retained-market-window.md)覆盖真实冻结窗口发布后的四买入/四周期收敛和17个模型边界，真实持续新日发布、C状态候选及稳定关闭仍待验。

类型：模块说明。所有者角色：执行维护者。原生交易接口、通道及执行单元由标准ITraderApi插件接入；实际采用模块与资格以运行配置及[当前事实](../roadmap/CURRENT.md)为准。现行产品已选择TraderQMTStandard并取得真实模拟交易及原账恢复证据，见[标准入口实际采用](../releases/2026-11-06-native-read-transport-live.md)、[当前配置接续](../releases/2026-11-06-analysis-cache-owner-live.md)。下述有日期的专项记录保留其当时限定范围，SDK替身证据与后继真实部署分别使用；本代完整自然策略目标仍按当前验收记录核实。

后继[异常证据](../evidence/2026-10-24-qmt-standard-trader-faults.md)证明标准候选丢回复不重提交、SDK未知保留且账户可读；当前event_consumption_complete仍0；该值保留生产交接尚未闭合的事实，已知基线后稳定流及完整恢复分别验收。

[关闭后继](../evidence/2026-10-24-qmt-standard-close.md)已验15方法16场景，覆盖请求在途时超时保留原owner及真正排空后回收；[Common页校验后继](../evidence/2026-10-24-qmt-event-codec.md)已验34新增场景和六组原生回归。两项历史限定结果分别覆盖在途关闭和页校验。后继[完整字段消费者](../evidence/2026-10-24-qmt-standard-events.md)已装配标准候选；[共享内存组合](../evidence/2026-10-25-qmt-standard-shm-events.md)验证原线程SDK替身回调经Agent、Win32 SHM、Host原事务/R21、标准唯一worker与原Adapter完成持仓/未成交归约。生产Factory保持原入口，生产查询/恢复交接仍未闭合，真实券商SDK调用为0。

## 券商实际数量与执行观察

受管CTA可显式配置[NRT-R23](../specs/native-realtime-strategy.md#nrt-r23-等待期间的券商pa刷新)，由同一标准插件owner在原pump/wait补查资金、持仓。完整初始查询后启用、整轮结束后计时间隔、原任务ID贯穿身份解析和SPI返回；默认沿原触发路径。补查更新券商事实，原策略理论持仓、预算、成本和绩效继续由WT负责。当前安装主链与跨日/关闭缺口见[验证记录](../evidence/2026-10-30-broker-observation-refresh.md)。

[NRT-R17](../specs/native-realtime-strategy.md#nrt-r17-策略读取当前券商观察)提供产品运行DLL的可选只读券商观察。自有owner从原Adapter完整查询表发布值副本；安装Python的CtaRuntime.broker_observation与INIT/SCHEDULE内CallbackContext.broker_observation返回冻结值。positions_known/account_known、独立revision/接收时刻和发布时刻区分来源；非零方向持仓包含quantity/sellable，已知空仓返回空tuple。运行前后不可用，旧DLL缺能力单独报broker_capability。原策略Position保持自身语义；本接口的[隔离安装证据](../evidence/2026-10-29-native-broker-observation.md)覆盖两代、成交刷新、多证券、空仓及旧库，真实周期和唯一数学核接线继续。

真实持仓、可卖数量及资金以券商查询为事实来源。QMT接入选择已批准的 `position_by_query` 模式，完整持仓查询在WT原生持仓表中替换；回报保留通知并触发查询刷新。策略目标、统计与实际账户数量各自保持原职责，查询异常需显示未刷新。

订单状态与剩余量采用完整有效的券商查询。显式order_context=query_first把完整查询更新到WT原订单表、原未成交量和查询订单统计；getOrders和原cancel共用此表。自有BrokerQueryContext负责配置、批次检查和提交组接线，独立订单数组已移除。重复查询刷新统计，迟到成交通知保留，其数量不再扣已查询余量。原生默认路径及cancel/doCancel正文保持，配置在实例初始化时冻结；完整查询失败不给伪成功空表，结果未知的命令继续保留原身份。要求见[STQ-P12](../specs/native-qmt-standard-trader.md#stq-p12-券商订单收敛到原生订单表accepted开发中)，已验范围见[限定主链证据](../evidence/2026-10-27-qmt-native-order-query-sync.md)。

## 策略线程到交易owner

[OwnerExecCommand](../../src/GuanhengExecution/OwnerExecCommand.h)实现原IExecCommand，挂接原WtExecuterMgr的公开入口。生产线程只交付目标、增量目标或行情的有界值；创建桥的owner按FIFO drain，在锁外调用原Local执行器。桥不创建工作线程、不持有跨线程WT对象，也不改变目标、价格或拆单算法。行情WT对象在owner重建，合约由owner元数据解析器提供。

目标执行器的stub、数据管理器及元数据由宿主在owner配置；桥自身接到的引擎_stub不向目标透传。队列容量、载荷和等待时间必须显式配置，失败锁存状态并停止新准入，已进入目标的调用保留原Standard命令责任。宿主先停生产者，关闭桥并确认无在途，再销毁目标/Adapter/DLL。契约见[STQ-P13](../specs/native-qmt-standard-trader.md#stq-p13-策略到交易owner的执行交接accepted开发中)。原执行管理器→跨线程桥→原算法→Standard→SHM的SDK替身主链已验；原生CTA装配由下节Session负责；真实来源、业务策略及发布资格分别验收。

## 标准执行宿主

标准插件对已提交委托保存原收据，只查询同一个命令 ID，直到原绝对业务截止、停止请求或明确终态。每轮沿原 10ms 有界等待与 HTTP 剩余截止推进，查询次数不另行缩短该业务期限。截止时结果仍未知的委托继续保留身份并阻断新写；后续核查沿原 ID，客户端不重 POST。[STQ-P26](../specs/native-qmt-standard-trader.md#stq-p26-原命令查询沿原绝对截止accepted)定义此边界及门面回归要求。

[StandardExecutionHost](../../src/GuanhengExecution/StandardExecutionHost.h)统一装配自有查询接线、原Local与线程交接桥。外层提供同一插件导出表、原工厂/基础数据和交易owner专用stub；本组件管理初始化、原owner pump、异步查询、原表读取和关闭。显式query_first/position_by_query/poolsize=0选择，普通native入口保持原行为。

生命周期由创建线程独占，生产者只持共享桥。跨线程request_stop关闭目标新准入；最终close核桥无在途、SPI脱离、原插件Closed/joined/drained及API实际删除。未确认时保留owner树与借用依赖至进程结束。公开接口及安装消费约束见[接入手册](../runbooks/qmt-standard-execution-host.md)，验收范围见[限定证据](../evidence/2026-10-27-qmt-standard-execution-host.md)。该组件与外部共享内存通信Host职责独立；原生CTA组合见下节；完整真实来源和生产接线继续验收。

[ExecutionEnvironment](../../src/GuanhengExecution/ExecutionEnvironment.h)提供交易owner专用原IExecuterStub：执行时钟缺省复用原TimeUtils，交易日委托原BaseDataMgr.calcTradingDate，品种/时段经原解析及元数据读取。显式模拟provider可冻结epoch；实例全部访问由创建线程独占，与CTA可变时间字段分离。配置、时区、元数据及安装资格见[宿主手册](../runbooks/qmt-standard-execution-host.md#执行时钟与元数据)。

## 原生CTA装配

[CtaExecutionSession](../../src/GuanhengExecution/CtaExecutionSession.h)以公开接口组合原WtCtaEngine、WtDtMgr、ParserAdapterMgr和CtaStraContext，挂接StandardExecutionHost的共享执行桥。原ticker负责分钟闭合，原策略上下文负责历史窗口/理论部位/策略KV，原引擎负责目标汇总；实际账户数量继续来自券商查询。现金股票也提供原WTSHotMgr空规则实例，满足原sub_tick的必需依赖。

创建控制线程管理初始化、运行推进和关闭；事件监听只记录原子诊断计数。公共配置在原模块初始化前统一预检类型，执行宿主须Ready且未停止。原后台任务失败经task_failure观察，关闭新目标准入并保留失败身份。关闭按Parser确认、原ticker/pool/tasks join、Reader确认、原工厂删除策略、上下文和插件释放、执行宿主关闭推进；pending保留完整依赖树，严格进程截止由外层Job负责。

该装配显式启用，普通原Runner默认行为保持；初始范围为单策略、poolsize=0、有stop/delete能力的Parser和Reader、新的独占生成目录。产品库与确定性测试插件分开构建。接口步骤、配置和安装见[宿主手册](../runbooks/qmt-standard-execution-host.md#原生cta装配)，要求见[STQ-P16](../specs/native-qmt-standard-trader.md#stq-p16-原生cta与执行宿主装配accepted开发中)。限定主链及未验范围登记在[CTA装配证据](../evidence/2026-10-27-qmt-cta-execution-session.md)。

[STQ-P17](../specs/native-qmt-standard-trader.md#stq-p17-同账户多策略固定集合accepted开发中)扩展同一Session为1..64个固定策略，每项独立原上下文/参数/工厂，共用原引擎、执行桥及账户查询表。原引擎按标的汇总理论目标，Local结合实际账户和本通道活动单执行。策略ID按Windows文件身份查重并在全部init后核冻结身份；完整关闭才释放进程内Session占用。已有状态根、同标的人工持仓/外部订单、跨进程唯一执行与资金预算完整接线边界见[专项方案](../migration/multi-strategy-account-ownership.md)，分别保留待验。

[STQ-P18](../specs/native-qmt-standard-trader.md#stq-p18-输出根单写者与两代停止边界accepted开发中)在同一原输出根中取得Windows独占文件租约，覆盖状态目录检查、原生运行及完整关闭，争用返回OutputBusy。Parser/Reader、策略删除或执行关闭仍pending时保留租约；进程退出由OS回收句柄。该机制保护原JSON单写者，完整异常重启及跨输出根账户唯一性仍按原责任交接验证。

## 职责与入口

承担通道生命周期、账户查询、委托与回报归一，以及经允许的目标执行。主要入口为 [TraderAdapter](../../src/WtCore/TraderAdapter.cpp)、[WtLocalExecuter](../../src/WtCore/WtLocalExecuter.cpp)、[WtExeFact](../../src/WtExeFact/CMakeLists.txt) 和 [ITraderApi](../../src/Includes/ITraderApi.h)。

目标接入由标准 `ITraderApi` 插件承接 `TraderAdapter` 的委托、撤单及四类查询，通过 `ITraderSpi` 返回真实订单、成交和账户事实。插件负责供应商字段转换、WT 身份关联、通信防重与有界生命周期；运输认证保留在通信层。策略和执行单元共用该标准接口，产品采用正常写开关、明确账户配置和终端运行模式。

保留的 [TraderQMT 工厂](../../src/TraderQMT/Factory.cpp)创建 [ManagedTrader](../../src/GuanhengExecution/ManagedTrader.cpp)，其标准请求拒绝和私有SignedCommand约束只说明该兼容模块。显式`TraderQMTStandard`使用[StandardFactory](../../src/TraderQMT/StandardFactory.cpp)创建StandardQmtTrader，经原TraderAdapter执行委托、撤单及查询；两个工厂分别构建，不能用兼容入口的行为代表标准插件。接口要求见[QMT交易规格](../specs/qmt-shm-trading.md)，[受管运行时](managed-runtime.md)管理有界生命周期，通信记录归唯一通信owner。

自有[标准候选](../../src/TraderQMT/StandardQmtTrader.h)及[真实候选工厂](../../src/TraderQMT/StandardFactory.cpp)已完成固定原版Adapter查询、直接SPI与共享内存正向写的[限定验收](../evidence/2026-10-24-qmt-standard-trader.md)。原名额在回调前归还、有效载荷在回调结束前保留计费，错误状态在回调前生效。后继已实现完整字段实时增量、有限交付索引和锁外SPI；真实共享内存组合已取得四项通过证据。缺字段补查已接入同一候选，生产交接、一般未知insert解除、完整故障及正式切换继续验收，详见[事件规格](../specs/native-qmt-standard-events.md)。

调用链为策略目标 → 已配置的原生风控及执行规则 → 执行单元 → TraderAdapter → 标准 ITraderApi 插件 → 外部账户；查询与回报沿接入层返回，供执行和业务消费者使用。该链不增加逐单人工审批服务；账户许可、接口认证、可用资金和交易限制继续在各自边界校验。

[账户身份线程接口](../../src/GuanhengQmtBootstrap/QmtAccountIdentity.h)已按begin/worker resolve/owner finish拆分，WT候选留原owner，跨线程只传独立值，原D与预算连续；该接口已完成[限定验收](../evidence/2026-10-24-qmt-account-threads.md)。它提供标准插件装配接缝，生产Factory与完整SPI/事件恢复资格仍按当前接线分别验收。

## 实时回报缺字段补查

自有标准候选对`MissingRequired`且定位字段完整的回报启动同类型账户查询。唯一worker沿原事件截止读取完整查询；金融行匹配、WT对象构造和SPI交付各有明确线程所有者。匹配以原查询下标选取唯一行，保留原事件与完整查询两份来源，预算覆盖二者及映射期间的持有值。多候选或定位不足沿明确失败边界处理，补查不以本地猜测填写缺失金融事实。源码入口为[StandardQmtTrader](../../src/TraderQMT/StandardQmtTrader.cpp)、[AccountEventMatch](../../src/GuanhengQmtBootstrap/AccountEventMatch.cpp)和[QmtAccountIdentity](../../src/GuanhengQmtBootstrap/QmtAccountIdentity.cpp)。

补查回报的去重签名采用Remark语义，OrderRef保留为诊断定位；完整字段旧路径保持各自定义。结果经同一金融mapper交给WT原生SPI，实际运行持仓、未成交量及策略通知归原TraderAdapter。补查成功、事件ACK、金融交付失败和迟到分别记录；交付失败在停止期间仍保留真实原因。

[正常候选整链证据](../evidence/2026-10-25-qmt-event-query-standard.md)覆盖已选功能及兼容输入；[混合容量证据](../evidence/2026-10-26-qmt-mixed-resident-capacity.md)仅以独立instrumented制品验证指定Query/Pending/EventChain窗口，逻辑费用与进程RSS分别解释。上述能力不提供券商持仓查询与历史成交、实时增量之间的共同覆盖证明；完整首次/重连交接仍须取得来源契约并单独验证。

## 原生资金与风险能力

`CtaStraBaseCtx`保存策略理论持仓、费用及损益；`WtEngine`维护组合资金统计，`TraderAdapter`接收券商实际资金；`WtLocalExecuter`支持执行数量scale。上述能力优先复用，策略预算是明确配置输入，不能将理论统计或数量倍率解释成券商子账户隔离。

`RiskMonDefs.h`提供组合资金风控及数量倍率接口，具体规则由已选插件和配置决定；`TraderAdapter`提供配置化报单/撤单频率与总量限制。策略自己的仓位、止损规则继续归策略。接口存在与某条具体限制已经生效分别验收；本次接入不新增独立资本账本或人工审批平台。

## 线程与释放职责

原`TraderAdapter.run`依次注册SPI、调用connect、设置AS_LOGINING。标准候选已实现的线程约定为：连接工作排入worker，宿主在run返回后开始owner线程pump，保证首次Connect回调发生在原初始化状态设置之后；worker只传独立完成值，owner构造WTS对象和投递SPI。API调用过程中同步回调可能重入执行单元：例如StockMinImpact在do_calc持有_mtx_calc时报单，其on_order/on_entrust也使用同一锁。标准接入设计要求插件排队后返回，在下一次pump投递回报，并在回调前释放自身队列锁；实际标准候选已在完整字段及共享内存组合中验此分工；跨进程恢复和未覆盖并发窗口仍须对应证据。

原`TraderAdapter.release`先调用`registerSpi(NULL)`再调用插件`release`；撤销注册及等待在途回调结束分别核实，具体SDK线程的停止/join由插件提供。`ParserAdapter.release`还负责释放插件对象，宿主和插件工厂保持明确的单一删除责任。Adapter的普通析构不等价于显式release。

原`WtLocalExecuter`析构等待其线程池，线程池默认策略含自然排空与join。宿主仍先关闭新工作，确保执行任务结束前Trader、行情数据和执行单元工厂保持存活；`poolsize=0`只限定Local局部调度，不证明所有来源回调已串行化。原Trader的sink使用原始指针，销毁执行器前须确认不会再分发给它。

`WtExecRunner.release`当前只停止日志；C ABI的静态Runner不会在该调用时析构。使用原Runner或公开组件组合时，按实际入口分别验收停止、回调撤销、线程排空和对象销毁。具体源码与限定证据见[原生执行宿主](../evidence/2026-10-23-native-execmon-host.md)。

## 账户、状态与持久边界

固定上游08b230dd的`TraderAdapter.handleEvent(WTE_Close)`通知各sink的on_channel_lost，isReady仍仅取决于_state==AS_ALLREADY；固定StockMinImpact的on_channel_lost为空。适配插件负责在实际断连、关闭或提交未知时立即关闭相应新写准入，自有宿主同时停止向受影响执行器提交新目标/行情调度。Close通知、目标准入、插件准入及实际资源关闭分别验收。该边界属于选用插件与宿主的组合责任，标准接入设计沿自有owner接线，实际行为待验证；框架修改另按批准处理。

账户观察记录账户、来源、会话、时间、完整性及可用性；目标、理论持仓和真实持仓分开。通道状态表达连接、登录、查询进度、ready/lost 和故障。验证结果归测试与交付记录，不形成额外产品资格等级。

标准初始化按登录 → 持仓查询 → 委托查询 → 成交查询 → 资金查询推进。四类查询各自返回真实结果，插件负责查询与并发回报的交接、覆盖核对及成交防重。标准 `ITraderApi` 没有四查询同一原子水位字段；恢复算法依具体来源保证实现，保留缺失、空结果和失败的区别。

已有 `TraderAdapter` 提供运行快照和委托/成交日志，策略/组合状态由相应上下文维护。新增持久化前核对现有记录语义和真实恢复需求；每类执行事实指定唯一所有者。运行日志、持久提交证明与外部成交事实按实际契约解释。

WT `EntrustID/userTag`、柜台 `OrderID` 和成交 `TradeID/RefOrder` 的关联保持原值及明确作用域、跨日规则。跨进程 `command_id` 由通信 owner 自动产生，仅用于内部防重和恢复，用户无需填写或审批。委托调用、受理、部分成交、撤单请求、撤单结果和未知提交分别定义。结果不明确时保留原委托关联与核查状态，基于真实回报和查询决定后续动作。

[R21Q查询恢复](../specs/qmt-shm-trading.md#qst-r21q-当前订单查询观察恢复)沿原通信Journal，在保存真实ORDER查询结果的同一事务中记录原委托关联；查询原ID、结果摘要、原行和B分别有据，历史GET不刷新来源。事件proof和查询proof保持不同类型，金融值仍由唯一mapper生成。原R21Q范围限定insert已sdk_returned且正常写通道可用；后继[UC契约](../specs/qmt-unknown-cancel.md)沿原ORDER观察扩展未知原委托定向取消，已取得限定证据。query/live交接、一般未知insert解除和生产切换继续验收。[ADR-0010](../architecture/adr/0010-order-query-communication-proof.md)说明原记录引用、期限及恢复职责。

## 失败与恢复

未知通信结果、硬故障和关闭分别控制准入。未知insert保原命令身份并暂停新增insert，仍允许只读核查及具备当前真实ORDER关联的单目标取消；精确取消竞争响应保原申请和实际取消两份身份，后继只读取实际原命令。自有插件在业务I/O前预留完成槽，worker移交完整责任后由owner处理；重复回报的金融归约继续归原WT和唯一mapper。取消引用、状态和有限预算见[UC契约](../specs/qmt-unknown-cancel-cpp.md)。

只读审计沿原未知委托身份取得ORDER观察与完整通信收据，收据组在原Pending与完成值之间整体转交。未知委托、每步读取错误及金融回报分别处理；关闭在真实排空后仍可保留待核查收据及其逻辑费用，实例删除再销毁最终持有值。[指定混合容量验收](../evidence/2026-10-26-qmt-audit-resident-capacity.md)以专用测试制品覆盖该过程，当前一般未知insert解除与跨进程完整恢复继续待验。

固定`TraderAdapter.onPushTrade`先更新持仓/统计并通知策略，随后调用checkSelfMatch；后者检查自成交，其返回值没有回滚前述应用。输入成交的去重与查询/回报覆盖交接归插件及供应商协议，按同实例重连、新进程重建分别证明。重复运输序列、不同序列的同一成交、查询已含而回报晚到，以及SPI返回后进程退出分别验证；来源缺少共同水位时明确保留恢复缺口。

依赖异常停止受影响的新增准入，持续摄取已有委托回报。恢复核实完整账户边界、未完成委托、事件覆盖和活动执行入口；外部状态缺失标为未知。

目标执行器具有产生订单和撤单的能力，其启动目标、管理范围和自动清理配置属于交易行为，按规格及授权验证。

必要验证包括重复/乱序回报、部分成交、查询缺页、超时副作用、旧会话复活、实例重启、存储失败、并发准入和恢复后的零重复提交。流程见[验证规范](../development/verification.md)及[故障处理](../runbooks/incidents.md)。

## 查询与实时归约的原生边界

固定上游的`onRspPosition`仅在`AS_LOGINED`推进后续委托查询；`AS_ALLREADY`期间重复持仓响应不重跑四查询。它按返回证券覆盖字段，缺行与完整空集合不清旧证券。普通刷新、完整重连和账户全量替换的语义分别核实；[绝对持仓研究](../migration/qmt-account-snapshot-research.md)记录本次接入的候选方向与尚未解决的执行新鲜度，已批准的显式position_by_query模式及其限定行为见下节；普通默认路径继续保留原语义。

原TraderAdapter的持仓查询覆盖返回符号；委托查询重算未成交但保留原订单缓存；成交历史查询累计成交统计，实时成交回调还更新持仓与未成交量。接入插件须依据真实来源包含关系区分查询已吸收部分与后续增量，单独一个历史成交键集合不足以决定全部副作用。完整重连基线还须处理原Adapter和宿主各自缓存，重复四查询不代表清空重建。

上述职责及交错风险已用固定原上游的公开接口分别验证，见[原生查询/live反例证据](../evidence/2026-10-25-native-query-live-counterexamples.md)。实验的观察顺序和时间戳保留诊断意义，不授来源watermark；新generation的空状态对照也不授查询/实时共同cut。金融状态继续由原WT维护，适配层承担来源契约、归属及生命周期。

## 部分事实与账户请求控制

[唯一账户mapper](../../src/GuanhengQmtBootstrap/AccountMapping.h)的inspect_account_row提供order/deal纯值检查；它与完整映射复用字段解码，分别表达缺必需字段、非法值、可选unknown及数量关系。返回字段位和独立值，不合成完整委托/成交，不拥有查询或金融发布权。JSON、容量及资源失败保留异常；业务调用者前后检查原截止，只有有据的完整原行进入后继金融映射。接口与逻辑计费见[SEV-R5b](../specs/native-qmt-standard-events.md)。

[QmtHostAccountClient](../../src/GuanhengCommon/QmtHostAccountClient.h)保留旧入口，并提供按次QmtAccountControl重载。按次control仅在同步调用栈借用，与构造control做OR；停止一份补查不修改普通查询控制。已准入I/O沿原截止取得实际结果，实际失败优先于并发stop；结果未知保原receipt，后续resume读取原ID。该能力不自动完成缺字段匹配或查询/回报交接，接续状态与资格见[当前证据](../evidence/2026-10-25-qmt-account-request-control.md)。

[AccountEventMatch](../../src/GuanhengQmtBootstrap/AccountEventMatch.h)在只读完整账户结果上定位原始查询行。它复用唯一inspection，完整扫描后才返回唯一index；金融Invalid、潜在匹配、重复、冲突和未补齐分别表达。ORDER核共有不变量并保真实后续状态；DEAL核原成交作用域。原事件和完整查询由调用者保有，原行/来源保持独立；匹配器不构造WT对象或发起请求。所声明逻辑峰值计入DTO全部字符串及序列化双文本阶段，额度失败沿强失败契约。接口已具[纯值验收证据](../evidence/2026-10-25-qmt-event-row-match.md)，完整worker/P8/Standard接线仍单独验收。

## 事件与查询的双来源身份接口

[begin_qmt_event_query_identity](../../src/GuanhengQmtBootstrap/QmtAccountIdentity.h)接收完整原事件页、原事件下标、完整原账户查询和所选原行下标；它重用唯一matcher与选行金融mapper，成功后以独立Sources保留两份来源。触发事件的sequence/SHA、金融查询的UUID/结果摘要/原行、历史委托lookup的proof分别表达各自事实。query_provenance不替代历史broker_proof；OrderRef保留为诊断值，所选query Remark承担该入口的token身份来源。

owner执行begin/finish并拥有WT Candidate；worker只消费不可复制Plan，返回独立Resolved。全阶段使用同一绝对截止和不可变逻辑预算，原数组及引用在失败后保持。预算覆盖有限逻辑值，allocator容量、对象池后备块和物理RSS分别验证。完整双来源组件已取得[限定功能及故障证据](../evidence/2026-10-25-qmt-profile-resource-channel.md)；标准插件的实际补查调度仍属待接线范围。

[纯profile准入](../../src/GuanhengCommon/QmtBoundReadCore.h)在资源不足时原样传播std::bad_alloc，保调用者descriptor原值。Identity在业务异常边界将其表达为IoError/空reason，避免资源不足期间再次分配诊断；resolve的初始holder创建之前仍可抛出原异常。结构、绑定和显式容量错误继续保原Status，调用者据真实类别决定处理，不能经bool将资源失败归为数据非法。

### 查询与迟到成交的已验证接入边界

[三时序后继](../evidence/2026-10-26-qmt-query-live-handoff-tests.md)已在固定原版Adapter、正常QMT插件和真实共享内存运输上实跑：查询先返回含成交的120股，迟到同成交20股再经SPI应用时，WT运行持仓变140而来源仍120；另外两时序控制为100到120。该合成来源实验只证明对应接入条件，不表示真实账户再次买入，也不授完整统计或恢复资格。普通持仓刷新、交易增量和执行器新鲜度继续按各自语义处理，显式查询持仓模式已按批准实现，实际作用与剩余恢复边界见下节。


## 显式查询持仓模式

TraderAdapter的position_by_query默认关闭。配置或五参initExt在初始化时显式选择后，成功完整查询整批替换原生唯一持仓表，成功空集合清空旧持仓，缺行证券移除；实时委托和成交保留通知并触发持仓刷新，该模式不对持仓与可卖数量做回报增减。普通默认路径保留原处理。初始化后不热切换。

持仓校验和整表提交分开；同一持仓锁保护读取与替换，get/enum及交易路径取值副本，外部API/sink/I/O在锁外。查询缓存的新鲜度与实际来源保证分别核对，刷新间的执行窗口仍需验收。该模式只改变持仓观察，订单剩量、成交统计、策略理论持仓和资金不因此获得查询/实时交接正确性。限定验证与未覆盖范围见[持仓模式证据](../evidence/2026-10-26-native-query-position-mode.md)。


## 标准 QMT 正式模块与查询上下文

显式 `TraderQMTStandard` 模块复用唯一 StandardFactory/StandardQmtTrader，构建入口为 [qmt_standard_product](../../cmake/native/qmt_standard_product/CMakeLists.txt)，正常源码清单由 [StandardTargets](../../src/TraderQMT/StandardTargets.cmake) 统一提供。旧 `TraderQMT` 工厂继续原默认选择。

[BrokerQueryContext](../../src/GuanhengExecution/BrokerQueryContext.h) 提供自有 BrokerQueryAdapter 和 BrokerQueryLocalExecuter，沿同一份 order_context 配置选 native/query_first，查询优先同时要求已批准 position_by_query。完整券商 ORDER 数组保留为有界只读观察；首次查询由原Adapter推进，后续仅替换观察。执行器读取当前通道的活动订单及其有符号剩余量，不按成交增减该投影。买卖仍由原 Local 执行、拆单与分配原委托身份，外层只复用原提交组准入。

宿主在原Adapter.init后、run前bind_context；全部查询投影、执行调用和SPI在同一owner，query_first的执行器poolsize须为0。API/DLL由宿主维持至停止与删除确认；断线撤销投影可用性。本模块不另存持仓/资金/成交账本。完整查询/回报交接、活动订单取消刷新、终态责任释放、生产策略宿主接线与跨进程恢复分别继续，当前主路径范围见 [STQ-P10](../specs/native-qmt-standard-trader.md)。

正式可选产品的装载顺序、构建与停止要求见[运行组件手册](../runbooks/qmt-standard-product.md)，开发主路径证据见[三案记录](../evidence/2026-10-27-qmt-standard-product-main.md)。

[STQ-P11后继](../specs/native-qmt-standard-trader.md)已实现同实例确定SDK返回后的终态O→后继P→原WT交付→下一组准入。P采用券商返回值，不按成交计算；完整查询/回报交接和跨进程恢复继续。[全成/部成部撤两轮实证](../evidence/2026-10-27-qmt-next-cycle-main.md)覆盖5条正向链，查询订单撤单扩展仍待用户批准。
## 原生账户独立观察发布

账户查看由独立WT的固定account_observation工厂持有原Scan单轮，原始四组事实通过[NAP-v1](../migration/native-account-publication-proposal.md)定位发布，观衡只读调用原validator/projector。它与R20策略观察分别拥有，原账户/策略账本保持。当前生产者普通安装和失败恢复范围见[证据](../evidence/2026-10-30-native-account-publication.md)，统一装配和页面按同候选验收。

原生产源保持的[生命周期后继](../evidence/2026-10-30-native-account-publication-faults.md)覆盖原常驻认证重连、Native暂停后的父总D回收/恢复、在途停止排空及父进程异常退出后的新代读取。外部物理回收与原Native正常完成分别表达，C原schema4投影与实际HTTP/页面分别验收。


## 原生业务日志

自有 [NativeRuntimeLog](../../src/GuanhengExecution/NativeRuntimeLog.h) 复用原WTSLogger转发入口和spdlog同步轮转，执行器动态分类沿原root回退；info门槛、4份各1MiB、8KiB正文、失败计数及同代生命周期由 [SDO-R5-Native](../specs/strategy-data-and-observability.md#sdo-r5-native-原生业务日志接线)定义。业务生产者完成停止后由原owner关闭；日志失败保持原业务控制流。头文件真实库验证与完整product/现场接线分别见对应验证及发布记录。
