# 观衡原生数据与执行接入实现规格

类型：功能最终规格。状态：accepted（用户已授权开始整个方案、并行实施确定项，待定项集中后续决策）。上位要求为[移植方案 R1–R13](../migration/guanheng-qmt-tdx.md)。本规格固定可实施接口和开发资格，生产启用另按授权及实机证据执行。

2026-10-22仓库归属澄清：观衡全部迁入本仓库，旧QMT工程停止开发并退出最终依赖；按[最终仓库归属](../migration/guanheng-qmt-tdx.md#最终仓库归属与旧工程退役)执行。下文旧owner和Host描述表示需核实、复用或迁入的职责，不能据此保留旧项目的业务进程、数据库及发布链。最小券商接入端由本仓库维护，WT重合能力直接复用，观衡独有业务仍独立发布。

2026-10-21 用户已确认 HTTP 先行、共享内存绑定和通达信交易暂缓、观衡独立受管发布。当前接线范围遵循[HTTP 增量规格](qmt-http-market.md)，下文的上一阶段接口仍保留；受限 SHM 模式和当前显式 HTTP 模式分别按各自契约验证。

当前职责补充：原生行情及业务消费者按[NMC规格](native-market-consumers.md)收敛，新增PG分钟接纳暂停默认接线。下文GNA-R4的强四快照、bootstrap/confirm_resume和保留消费者恢复约束现有ManagedTrader候选，不代表上游ITraderApi的通用要求；普通原生执行器到QMT签名命令尚未接通。替代恢复先证明快照/增量交接、未知结果及权限，再按核心审批与切换边界实施，详见[业务地图](../migration/business-adaptation-map.md)。

## GNA-R1 模块与接口

原生结构和插件接口复用 WT，新增代码放独立目录。共同类型由 `src/GuanhengCommon/ProviderTypes.h` 唯一维护；行情/历史与执行分别有独立的强类型端点接口。公共接口冻结后再修改生产者/消费者；已有通信帧、ACL及许可契约先核实复用，所需最小接入代码迁入本仓库。共享内存与WT绑定仍暂缓，持久化和恢复职责先按WT原生能力收敛，旧工程不作为最终运行或发布依赖。

来源身份包括 provider、instance_id、session_id、generation；执行另含 account_id、environment、route_epoch。每项能力独立标识 supported、qualification 与 reason，连接不提升能力资格。Simulation、ReadOnly、Live 显式区分；无合格后端的原生工厂默认 unavailable。

## GNA-R2 行情与分钟订阅

ParserQMT/ParserTDX 实现 IParserApi 工厂、可注入端点、生命周期及订阅，使用 WTSTickStruct/WTSTickData。只有具备资格且带真实来源时间的完整累计快照使用 procFlag=1；WT 完成累计量处理，历史 OHLCV 与观测快照不伪造为 tick。复制回调输入，限定回调线程/生命周期、订阅容量，拒绝旧代际、非法数值、重复及倒序样本；断线和不支持能力明确回报原因。

外部受管 Runtime 显式驱动行情 pump 和交易回报领取，提供有界 poll_once、启动/停止及重入保护；WT ParserAdapter 的 run 返回不授来源 ready。通过真实 ParserAdapter.initExt 验证注入快照到 WT stub 的调用链。Runtime 使用非拥有引用，先停止调度再由 WT adapter 释放插件；重新绑定要求递增来源代际。

Retained QMT 报价在提交新读取前发现签名 Host 会话换代时，只在原路由、执行方、路由代际和能力摘要均相同的情况下重新认证已观察到的新连接。关闭旧解析器后，沿原轮询节拍在同一端点接续该已认证绑定。保留每只证券已交付的时间水位，收到合格的新时间报价才恢复连接状态。旧报价及同一时间报价不跨会话交付。如果换代发生在成功结果的最后绑定检查，先按原收据及结果摘要确认消费，隔离该笔旧行情，再接续新传输。尚无结果、身份冲突及消费未确认继续沿原请求处理。

`MinutePipeline` 提供同步 writer/reader 的薄接线：完整累计快照经 WT 原生累计差分/分钟计算，读取注册与 `onMinuteEnd` 推进闭合消费者。已验证时钟控制闭合时刻，首次接入按每证券抑制缺起始基线的分钟；每次重绑均隔离该证券旧来源已写入但未闭合的 bucket，并抑制新来源首分钟，重绑提供的基线证据不能授予旧缓存新来源身份。重复、旧会话、未订阅、未来/无效时钟和消费者应用未知明确拒绝或隔离。保留来源、资格及覆盖未知说明，采样快照的真实 OHLC 完整性按来源证据单独验收。午休及分钟边界复用 WT 时段规则。

WT Writer 的映射容器、创建/扩容/写入、最后活动时间、checker 过期检查与解除映射、归档及停止清理由统一生命周期互斥门保护，块指针在受保护区内验证。停止先关闭准入并唤醒队列，退出生命周期门后回收输入/归档/checker 线程，随后清理映射；重复停止安全。`mapping_expiry_secs` 默认 600、范围 1..86400，`mapping_check_interval_ms` 默认 10000、范围 1..60000；两项由 writer 配置在初始化时固定，异常值拒绝初始化，测试可缩短预算执行实际过期与重映射，不改变分钟计算。全部线程停止后才能卸载。

缓存清理每次在生命周期门内核对停止状态、关闭六类实时映射后执行删除；外部文件占用等失败保留最多五次、间隔 300 秒的重试语义。重试等待退出生命周期门及缓存/块锁，并以停止谓词和队列条件变量唤醒；等待期间的新写入在下一轮重新核对及关闭映射后处理。停止可中断等待，最终删除失败明确记录日志，不授清理成功。过期与检查预算按原值完整十进制正整数校验，拒绝小数、尾随字符、窄化溢出及越界。

## GNA-R3 原生历史、覆盖与补数

复用 WtDtHelper 的 DSB 存储和读取以及 IHisDataLoader 接缝，实现 LC1 导入、分钟范围查询、数据来源/单位与版本记录。LC1 数据必须显式提供证券、单位、分钟边界与来源资格；合成样本只授开发验证。验证完整记录、日期时间、OHLC/有限数、升序与重复冲突；原生写入失败必须如实失败，已发布文件保持可恢复。

数据布局使用 WT 原生 his/min1/<exchange>/<code>.dsb；查询返回真实已存 Bar、来源和覆盖状态。只有调用者提供已确认的预期交易分钟及其版本依据时才能判定缺口；缺少日历/停牌等适用证据返回 unknown。补数通过有界待办/显式 worker 推进，先查已有数据，仅对已知缺口请求已支持端点，合并去重后回读验证；策略与同步历史回调不执行耗时补数。相同请求共享待办，能力缺失明确 pending/unavailable，部分页不能提升完整性。

未结束的来源页仅保存在有界 Task 暂存中；取得源页完成依据后，Store 在同一根 lease 内读取最新版、核对来源、合并并发布，防止并发补数丢失新分钟或回退版本。根目录忙时保留暂存，下次 worker 重试。队列重建会重新取得尚未发布的页，不能从部分页提升覆盖。冻结及再次冻结共用原数据/元数据双摘要校验。行情绑定按实例保留有界且不淘汰的最大已见代际，容量耗尽拒绝新实例，防止 A→B→A 复用旧绑定。

Windows 历史根 lease 使用永久文件 `.guanheng-lease-lock` 的 share=0 原生句柄，持有范围覆盖 `.guanheng-writer` 目录创建、全部读写/冻结工作及目录删除；异常构造释放句柄，析构先删除目录标记再释放句柄，永久 gate 文件保留。仅原生 sharing/lock violation 映射为 Backpressure，权限/磁盘等 IO 保留 OS 错误。既有目录标记继续表示使用中或崩溃遗留，保持关闭并走显式恢复核验，不自动解锁。

冻结和恢复共同使用原子目录认领创建全新目标根；同一目标仅认领成功者写入，其他调用返回 Conflict，已有根保持原样。发布失败的候选保留核查，不自动清理或授读取完整资格。目标经过同步完成及回读验真后交给消费者。

冻结回测输入必须使用固定原生数据副本及内容身份；修订、源切换、分钟末端及复权/量额语义在返回元数据保留，不静默混合来源。文件操作发生在 QMT 外部。

## GNA-R4 受管交易与回报

TraderQMT/TraderTDX 复用 ITraderApi/ITraderSpi；端点、授权校验与状态接收者显式注入，默认禁写。受管提交/撤单入口验证原签名字节、命令身份与 WT 字段、账户/环境/代际/路由、模式和能力；裸 WT orderInsert/orderAction 缺授权上下文必须拒绝。真实签名校验和最终执行许可由现有上游授权模块/Host 承担；本仓库不能用模拟校验器授予生产资格。

原始签名字节原样传递，幂等与持久提交阶段复用唯一 Host Journal。本地映射仅为有界派生索引；明确区分未调用拒绝、Host 持久受理、柜台受理、submission_unknown。结果未知保持诊断并阻止新写，继续查询/回报；禁止盲重试、自动切源或把未知映射为可重试失败。重复命令及冲突请求在隔离端点证明副作用次数。

账户/持仓/订单/成交映射完整初始化原生字段，空成功与失败分别处理，回报保留原身份并拒绝旧会话。回调使用 WT 引用生命周期；异步/重入/释放行为有界且可回归。持仓与账本复用既有框架/业务权威，不建立第二套真实持仓或执行 Journal。

初始账户快照与可靠事件必须由唯一 Host 提供同一执行身份、事件流身份、完整快照边界及其已吸收事件水位；前端从该水位以后消费回报，不能从缺省零或普通 last_event_seq 推断持仓已吸收范围。四类快照须属于相同受管边界，来源缺少原子依据时保持不可写并说明缺项。正常查询不得悄然重设流游标；重连/恢复依原 Host 证明保持连续性。

成交去重使用账户/环境/交易日/柜台成交身份，独立于传输 event_id/cursor；相同成交在新包络中重发也只向 WT 投递一次，内容冲突保持核查。派生索引有界且不能通过静默淘汰允许旧成交重新入账。订单状态与总量、已成、剩余的组合一致，Filled/PartFilled/未成交/撤单等状态按真实语义校验。交易端停止失败通过受管状态入口传播给 Runtime，保持 Stopping 和重试资格，成功停止后才允许释放对象。

强类型 `CoherentBaseline` 包含完整执行身份、Host stream_id、boundary_id、inclusive_cursor 及完整性证明；`ExecutionEndpoint.bootstrap` 原子返回此证明与账户/持仓/委托/成交四快照，各快照证明必须完全相同。缺省实现 unavailable，数值为零的水位仅在显式完整原子证明中有效。原子成交快照必须覆盖该流可能重发的柜台事实去重范围；前端以其初始化有界派生身份索引，从 inclusive_cursor 之后消费同流回报。新消费者的四类初始化全部成功交付后才开放回报归约及新写；同实例重连保持原证明、消费游标和身份索引。

WT positions/orders/trades 初始化回调各交付一次，后续返回 NotSupported，最新只读观察经现有 Broker 查询而不重送 WT 归约器，单纯不支持观察不改变写资格。WT account 回调先交付统一初始边界，之后可消费同身份同流的最新完整账户观察，始终不改变事件游标。订单 `remaining` 是活动未成交量，`inactive_quantity` 是已撤/已拒的未成交量，三者与累计 traded 合计等于总量；Filled 全成且无余量，PartFilled 严格部分成交并有活动余量，Submitting/Accepted 无已成，Canceled 无活动余量且有失效量，Rejected 无成交且全量失效。日期和毫秒时间必须合法。

WT 回调可能已应用后抛异常时，消费者进入 delivery_unknown；同消费者禁止重新应用，普通 Host reconcile 不能证明 WT 已应用范围。`inspect_reports` 保持 Host 回报只读诊断，受控创建新 WT 消费者并取得新的原子基线后恢复。柜台成交身份索引满额不淘汰旧事实，新写及未知新成交保持 Backpressure，受控重建依据由原 Host 提供。受管 `ManagedTrader.stop` 传播 close 异常并保留停止核查，Runtime 只有全部停止成功才到 Stopped；原生 void disconnect 委派 stop 并保留可诊断状态。

回调允许重入，因此每个 WT 回调返回后与下一事件应用前重新检查 delivery_unknown、消费者就绪/补发阶段、连接及身份；重入账户查询已应用后抛异常也立即终止本批次，禁止继续归约或报告成功。BrokerAccepted 必须提供非空、少于64字节且无嵌入NUL的原生订单号；撤单柜台受理身份必须与授权目标相同。无法关联的已调用回执保留原证据并归 submission_unknown。

同消费者重连须取得 Host `RetainedResumeProof`：原 `CoherentBaseline`、精确 after_cursor、Host权威冻结 through_cursor、相同交易日及完整性。缺少接缝、证明、同流边界、连续性或交易日时保持 Degraded/禁写。恢复期间 `resuming` 禁止新写，连续归约至 through_cursor 后才调用 `RetainedConsumerRecovery`；无跳游标，无重放初始三类快照。自有 `ManagedTraderAdapter` 使用原 WT 登录/查询/归约逻辑，Connect交受管Runtime登录，Close走真实 lost；经证明的恢复调用 WT 非虚 `restoreRetainedChannel`，仅在原 ALLREADY、相同交易日下恢复原 sinks ready，不修改持仓或统计。ready/lost幂等，恢复通知发生同步stop、重入或隔离后必须重检状态，保持实际通道与受管ready一致。跨日恢复须新消费者原子基线。同消费者正常补发与临时证明缺口恢复具有可调用入口和实际WT回归，实际Host默认confirm_resume仍Unavailable。

消费者应用未知统一触发真实WT资格撤销，初始ready、恢复ready、查询和订单/成交回调采用相同隔离责任层；内层异常被吞后，外层也不能恢复ready或继续归约。`RetainedConsumerRecovery.invalidate_retained_channel` 通过 WT 非虚 `invalidateRetainedChannel` 与真实Close共用lost机制，保留Host只读诊断，不变更持仓或事件水位。每个sink成功lost通知不重复，抛异常者可能已经应用，作为幂等控制通知保留待重试，不授恰好一次语义。所有受影响sink均尝试撤销，使用快照列表避免回调重入改变集合；待确认lost阻断恢复。`channel_isolated` 仅在全部撤销确认后为真，`retry_consumer_isolation` 只重试未确认通知，保留delivery_unknown及禁写，不能复活旧消费者。停止路径同样传播未确认lost，成功停止后才可释放。

## GNA-R5 观衡兼容与策略复用

保留观衡研究、独有审批和页面等用户功能，重合运行能力全部使用WT；原Bridge等进程和存储布局属于待替换/收敛的当前实现，不能固定为最终必需。现有兼容门面仅作为切换期候选，能力核实完成后按最终原生接缝修订。Python业务算法可通过薄上下文适配复用，运行底座无wtpy必需依赖。策略时间来自回放或源事件，历史预热/补发不重复产生已过期的执行意图。

观衡 DTO 映射严格处理时间、量额、空值、来源及资格；签名命令原字节保留，实际生产接线缺项明确 unavailable。端点不通过 HTTP/文件交换绕过受限 QMT 侧边界。

复用原图表/覆盖/批量/分析窗口模型及原 Portfolio、Bridge 构造和签名逻辑，提供独立兼容适配和隔离契约验证。原 shadow 审批的拒绝结果继续保持零委托；正向签名验证只消费独立合成的既有授权模型，测试密钥保持测试作用域。原服务及页面的生产切换另登记实际接线和资格。Broker 历史/快照投影集中校验来源、字段和能力，缺少确定字段语义返回 unavailable。

使用 WtBtPorter 原生外部数据加载器与 CTA 闭合日线回放回调驱动同一纯策略核心，比较源时间、完整条数、决策和影子目标；结果与固定输入的纯核心整段输出一致。无外部私有核心的通用 CI 显式 skipped，本地指定受控核心时必须实际通过。

## GNA-R6 验证、分工与待定项

受管外部运行入口 `ManagedRuntime` 由单一创建线程调用 `start/stop/poll_once`，非拥有绑定 `MarketParser/ManagedTrader`；真实推进 `market.pump` 和 `trader.poll_reports(limit,budget_ms)`，批次及每回合截止受配置限制，两个来源交替优先调度。交易回报重载保留原无参入口，并将单次请求取运行时剩余预算与实例上限的较小值。来源故障分别呈现，行情故障期间仍推进交易回报；重入轮询明确 pending，回调停止请求在当前调用返回后关闭端点，先停止再释放引用对象。同步调用依赖端点/消费者遵守预算；超过实际耗时上限必须报告 timeout，本实现不授予抢占中止能力。市场重连使用来源权威递增 generation，不能从 WT `ParserAdapter.run` 的 true 推导业务 ready。

原生 `GuanhengRuntimeProbe --self-test` 运行合成端点 → MarketParser → 真实 WT ParserAdapter.initExt → Stub 的快照链及受管交易回报轮询，包含重入、预算、故障和停止生命周期。`--status` 在无端点时明确 unavailable，`--help` 输出入口用法。此 Probe 是隔离开发与包级验收入口，实际生产 daemon 和真实 Transport 资格依上游交付。`ParserAdapter` 构造初始化 `_check_time=false`，普通配置路径仍由配置覆盖，使 `initExt` 时间检查具有确定缺省值。

固定合成数据验证原生历史导入/查询/补数、订阅、四个工厂、受管交易与回报、Python 业务门面的完整隔离调用链；正向与异常覆盖部分页、重复/冲突、坏数据、磁盘失败、容量/超时、旧代际、未知提交和恢复。测试使用独立假后端记录真实调用次数，无账户登录、真实委托/撤单或部署。已有原生及打包流程继续通过；新增 DLL/入口进入相同制品与包级检查。关键路径独立审查。

并行所有权：行情/历史 Agent 负责 GuanhengData、ParserQMT/TDX 及 market 测试；交易 Agent 负责 GuanhengExecution、TraderQMT/TDX 及 execution 测试；业务 Agent 负责 integrations/guanheng 和 business 测试。主 Agent 负责共同类型、CMake/制品/跨模块集成、索引、状态和统一审查。各模块公共头由所属 Agent 编写并向消费者明确冻结；接口变更先同步消费者。

共享内存绑定、TDX 真实交易后端、实际历史来源/许可和任何新待定项集中登记到[决策清单](../migration/decisions.md)。不确定项不阻塞确定模块的实现与隔离验收，也不获得虚构的生产实现或资格。全部确定项完成后一次提交可审阅决策包，逐项标明影响、选项和建议。
