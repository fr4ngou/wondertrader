# QMT未知委托定向核查与取消

状态：accepted implementation（动态未验）。类型：未知委托定向核查与取消主规格。日期：2026-10-25。UC-R1–R8、UC-R9 A/B/C/D及对应R10实施契约已确认；Common/Standard的准确DTO、状态机、合并矩阵与宿主逻辑payload预算由[C++实施契约](qmt-unknown-cancel-cpp.md)唯一规定。设计确认、产品实现、隔离验收和生产生效分别取得证据。当前阶段不切生产Factory、不运行真实SDK，不宣告整体unknown取消或一般恢复交易完成。[ADR-0011](../architecture/adr/0011-unknown-order-targeted-cancel.md)记录事实归属和取舍。

## 目标与原生接缝

在原 insert 调用结果未知而新 insert 关闭时，继续按原 UUID 核查；有当前真实 order/deal 或 ORDER 查询关联证明，且 WT 已有真实可撤订单时，原 `orderAction` 能发送目标明确的一次取消。原 insert 始终保留 unknown。原取消自身结果未知时沿其原 UUID 核查，不换 UUID 重发。

复用 WT-T01/T02/T09：ITraderApi 查询/撤单、原 WT 订单对象与 isAlive、EntrustID/UserTag/OrderID、原 SPI。复用原 HostTradingJournal、BoundReadJournal、TradeOrderLinks、原认证 HTTP/SHM、唯一 Agent 策略线程、Standard 唯一 worker。新机制只记录或读取通信事实。WT 金融归约、QMT 实际账户结果、生产 Factory、SEV-R8 基线交接及 event_consumption_complete 范围保持。

自动审计只更新通信 proof 和有限诊断；不自动重复 onRspOrders，不伪造 order event。真实完整 WT 订单继续由原正常 queryOrders→P7→onRspOrders 或真实 event→P8→onPushOrder 恢复。没有这份真实 WT 订单时，自动发现并主动投 SPI 的能力仍属后继，不能报告本切片已覆盖。

## UC-R1 事实与唯一准入规则

三个事实各自保留，诊断首错不得替代准入状态：

| 事实 | 所有者 | 锁存/解除 |
| --- | --- | --- |
| unknown_fenced | Journal 原未知记录；Agent 当前实例未知调用；Standard 当前实例未知提交 | 表示尚待核清的责任。原unknown结果不改写；insert的独立券商终态及WT应用核清按[NRT-R32](native-realtime-strategy.md#nrt-r32-原命令待核查期间的执行连续性)，其余等待继续保留 |
| hard_fault | 各 owner 的时钟、身份、持久/交接、回调效果、实际事件缺口等失败 | 锁存。unknown 先发生后仍须记住后来的硬故障；无 API 清除 |
| closing/closed | 原生命周期 owner | 沿原 stop/drain/join；取消不得绕过 |

本切片继续拥有定向取消。后继[NRT-R32](native-realtime-strategy.md#nrt-r32-原命令待核查期间的执行连续性)拥有insert核清后的执行连续性，原SDK结果unknown及原UUID/body继续保留；Source实际完整ORDER、Host原Journal完整查询证明及Standard原WT应用分别核验。普通读取成功、定向cancel返回、删除记录、伪sdk_returned和人工“已确认”均不授恢复。活动单/未知cancel保持原核查责任，正式发行与真实交易另验。

`writes_blocked`、`write_admission`、`accepting_commands` 继续表达整体新写关闭，不得因目标取消而恢复 true。实现以一个内部 operation 判定替代各层重复布尔特判：

- `order.insert`：原全部准入条件成立，且没有 unknown_fenced。
- `order.cancel`：固定账户/原 writes_enabled/实际 live/当前认证来源成立，未 close、无 hard_fault/真实 gap，具备本次具体原 insert 的当前 proof；仅在 UC-R2 完整 v2 能力下允许绕过 unknown_fenced 对 insert 的整体阻断。
- 无 v2 来源：原普通取消路径保持；unknown 下取消拒绝。能力版本不是用户批准字段。
- 原 ID 相同 body 的重取、GET 原结果、order lookup、cancel lookup、账户读不依赖新写准入。读成功不清 unknown、不授 SDK 写。

当前 proof 沿 R21Q：真实 event B/session 与当前值一致，或者真实 query 原 result B 与当前 B 一致。query 无 event session。派发 B、观察 B、当前 B 分别保存；不得更换旧观察来源。当前 proof 仅识别订单归属，alive/终态由原 WT 实际订单决定。

## UC-R2 明确能力版本与兼容协商

采用真实运行状态版本协商；保持 read-profile.v4、trade-profile.v1、原私有 binding、原命令/结果/事件/查询/reference wire 及原 profile SHA。原因：TradeEventRecords 的持久 identity 固定完整 profile SHA，单为本恢复能力改 profile 会引入不必要的旧 Journal 身份迁移。

### Source v2

新 Agent 的 `agent.trade.status` 仍接受空对象，返回 `qmt.trade-source-status.v2`。字段为 v1 全集加下列三项，精确字段集合，不接受额外字段：

完整顶层字段：`schema_version,session_id,binding_id,binding_sha256,writes_enabled,source_mode_live,write_admission,closing,gap,queued,executing,commands,completed,events,unknown_fenced,hard_fault,cancel_admission`。events 内原精确字段和前沿关系全部保持；unknown_fenced/硬故障不借用 event sequence。

| 字段 | 类型与定义 |
| --- | --- |
| unknown_fenced | bool；本源实例尚待核清的未知调用责任，原结果与退役条件沿NRT-R32 |
| hard_fault | null 或 `{code: ASCII非空字符串1..128}`；第一个硬故障安全码。硬故障存在本身独立锁存；先前 unknown 不占本槽 |
| cancel_admission | bool；当前源可以接受进一步核验的 cancel，尚未预留容量，亦不证明任何具体订单身份 |

v2 的顶层 gap 只复制 event ring 的真实 gap；hard_fault 不再借用 gap。`write_admission = enabled && live && !closing && !events.closed && gap==null && hard_fault==null && !unknown_fenced`；`cancel_admission` 使用相同条件但省去 unknown_fenced。队列/命令容量在 enqueue 实际占用；executing 保持当前源线程事实，不允许并行 SDK。

新 Agent 总是输出 v2；它不宣称自己仍是 v1 而更换 gap 含义。旧 Host 遇到 v2 按原精确 validator 拒绝。此时无交易派发，不自动降级。

### Host v2

新 Host 的原 `GET /internal/v1/trade-status` 返回 `qmt.trade-host-status.v2`，v1 全集加 `unknown_fenced:bool`、`hard_fault:null|{code}`、`cancel_admission:bool`。HTTP 路径沿现接口，body 的 schema 显式区分。

完整顶层字段：`schema_version,binding,binding_sha256,read_profile_body_b64,read_profile_body_sha256,source_status,writes_enabled,accepting_commands,closing,failure,limits,unknown_fenced,hard_fault,cancel_admission`。limits 与原字段/数值约束保持。

`source_status` 接受精确 v1 或 v2。Host v2+Source v1 时：普通正常路径沿旧语义；cancel_admission 只能等于允许旧取消的整体 accepting_commands，unknown 不能旁路。Host v2+Source v2 时：结合当前 B/session、connected/stream_checked、配置、Journal 独立硬故障、真实 gap、关闭和源 cancel_admission 计算；具体目标 proof 在提交/claim 原锁与事务中再核。Host hard_fault 与原 failure 诊断分别保有，原 failure 可继续给首错说明，准入不能仅看它。

Journal `has_unknown_trade()` 原接口可为旧调用保留；新调度必须取得独立 `{unknown_fenced, hard_fault}`，禁止把 `_trade_failed`/association_error 又折回同一个 unknown bool。前者来自真实unknown行及NRT-R32已保存的原终态查询证明；后者来自原交易提交/时钟/存储故障、关联冲突及 UC-R3 的存量并发冲突。Host仅在原D内直接重核Journal有已证明的原unknown记录、Source v2当前无待核清责任及独立硬条件成立后退休本地等待；旧v1或外部观察false均不能清除。Control `trade.stream` 在同一原域任务 D 下返回这两个事实与原 receipt；所有有限槽及实际源 ACK 顺序保持。

### Common 协商

prepare/refresh 对 v1/v2 分支精确校验。v2 Host 嵌套 v1 Source 可以读和普通写，未知取消仅在 Host v2+Source v2 且实际 cancel_admission 成立时准备。创建私有 prepared cancel 前和 submit 前均刷新并重核。首次成功 prepare 冻结 Host/Source 状态版本及原 B/session；同一 owner 发现版本降级/换代视为 stale，按原生命周期重建，不悄悄换解释方式。

状态版本证明实现接口能力，具体请求仍由各 owner 重核实时事实。保留独立原 profile、HTTP 实际 cap、原 D；不接受由公开 DTO 伪造的恢复能力。

| Common | Host | Source | 读/普通正常写 | unknown 下定向取消 |
| --- | --- | --- | --- | --- |
| 旧 | 旧 | 旧 | 原行为 | 拒绝 |
| 新 | 旧 v1 | 旧 v1 | 原行为；cancel lookup 能力不存在 | 拒绝 |
| 新 | 新 v2 | 旧 v1 | 依旧状态条件正常推进 | 拒绝 |
| 新 | 新 v2 | 新 v2 | 原条件成立时推进 | 当前 proof 和全部硬条件成立时可用 |
| 旧 | 新 v2 | 任意 | 旧 validator 拒绝新 Host schema | 拒绝 |
| 任意 | 旧 | 新 v2 | 旧 Host 拒绝新 Source schema | 拒绝 |
| 新 | v2 畸形/未知版本或同 B 版本漂移 | 任意 | 保留错误，拒绝派发 | 拒绝 |

升级采用停源/排空与原收据保留后的成套制品切换，遵循原授权和生命周期；本文不授权执行。保留原 Journal bytes，无 schema 列迁移，无历史 profile 重写。

当前产品消费者闭包（2026-10-25 对 src/connectors 静态检索）：SourceTradeService.status 产生状态；TradingControlLoop 在 control_trade_agent.py 分派并回复；Host control_trading.py 收取后调用 runtime.validate_source_status；trade_runtime.py 调 trade_status.py 校验、保存及生成 Host 状态；Common QmtHostTradeClient.cpp 的 source_status/refresh 两级消费并拥有 accepting/cancel 判定；Standard 的 run_write/prepare 以及 P7/P8 resolve、R2c event context 经同一个 Common 客户端间接消费。后四者不自行解析状态 JSON。Journal 不解析外部 status，接收 Runtime 在真实 binding 锁下核准的当前源上下文与操作模式。trading_agent.py 的 close/drained 逻辑和策略生成产物间接依赖 service 故障/关闭，须跑原链；各快照及测试的 schema fixture 由所属组一起更新。原 profile validator 与 trade_event_records 的 profile SHA 不改。

## UC-R3 同目标未决取消的原事务收敛

不新增 coalesced 列、别名表或状态。原 trade_commands 的 original_command_id 已足够表示取消目标。

未决实际 cancel 定义：同 original insert UUID 的 `queued/dispatching/unknown` 取消记录。`sdk_returned/definitely_not_called` 为该调用明确终态；signal_sent=true 仍不表示订单已撤。

`submit_trade` 在原锁、原 transaction、原 D 内按以下顺序执行：

1. 同 command_id 已有记录：body 相同则返原记录；不同则原 identity_conflict。此步仍先于新写门。
2. 核原 insert 存在、operation/account/binding/EntrustID/userTag/目标 broker 关联。核实际当前 B/session、操作准入及原业务 D。新增记录的数量/字节容量检查放在步骤3确认无未决取消之后；已占满容量的目标待决取消仍能返回精确cancel_pending并走只读核查。
3. 对 cancel，查询该 original_command_id 的未决记录。数量为 1 时抛出专用 `CancelPending`（原事务无新命令、无 SDK），数量大于 1 时锁存硬冲突；为 0 时才核新增记录count/bytes额度后继续。
4. 先保留本次 canonical command/原 UUID/原 D，再提交；仅 commit 返回、末核 D 成功后才通知原 Control。SDK 仍经唯一 claim。

Runtime 将精确 `CancelPending` 映射为 HTTP 409、现标准错误对象 `{error_code:"cancel_pending",error_message:固定安全中文}`。不能从普通 JournalConflict 文案猜这个分支。该完整、未过原 D 的合法响应只说明“本次新 UUID 未登记；已有目标取消待决”，不宣称本次成功。

Common 将这份已完整校验的业务响应转换为 `Status(Conflict,"qmt_trade_cancel_pending")`；该理由只能在此确切分支生成。原 receipt 保留、original_record=false，phase 保持 Unknown（未取得本次原命令 phase）。Standard先锁存 `PendingRole::UnadmittedTargetLookup`，在通用错误、晚deadline和detach抑制之前提交本次已证未登记事实；保留A原槽、target_insert、原ORDER read及原charge，直到目标/read责任完结后才退役。后续lookup失败或尚无B时继续只读目标核查，不GET已知未登记A、不重POST。完整状态与提交规则见[C++实施契约](qmt-unknown-cancel-cpp.md)。不得把phase或交易统计伪改为SdkReturned；截断、超时或伪409不进入此分支。

claim 继续至多一个 dispatching。unknown fence 下在有限 queued 集合中选择可派发 cancel，不能被前方禁止派发的 insert 饿死；过 D/换 B 的 queued 沿原 definitely_not_called 原因终结。临近 dispatch 前在 Runtime binding 锁与 Journal 事务中再核具体目标 proof、关联冲突和当前来源。已经持久 dispatch 的原调用及 Control active/future/retired 槽不得被新 cancel 抢占。

初始化在原恢复更新之后验证“每目标最多一个未决 cancel”。存量若违反，不猜哪条是真：保留全部原记录，实例进入可读硬阻写状态，并给固定 `cancel_pending_conflict`。读核查仍可取得各自原 UUID；目标 cancel lookup 返回冲突而不随意挑选。

一条取消 unknown 后，仍 alive 的 ORDER 查询不能证明取消未执行，不自动新发另一取消。收到真实终结订单后 WT 自然不再发起取消。主动确认原取消未调用所需证据仍沿原源/Journal，不以查询空或时间推测。

## UC-R4 实际原取消收据的只读恢复接口

新增 `POST /internal/v1/trade-cancel-lookup`，归原 HTTP HMAC、容量、HostTradeRequest 和原 Journal owner。它是只读 POST；任何状态下均不得调用 SDK 或创建取消记录。

请求精确形状：

```json
{"schema_version":"qmt.trade-cancel-lookup.v1","original_command_id":"11111111-1111-4111-8111-111111111111","original_command_sha256":"<64位原insert canonical SHA>"}
```

成功响应精确形状：

```json
{"schema_version":"qmt.trade-cancel-reference.v1","original_command_id":"11111111-1111-4111-8111-111111111111","original_command_sha256":"<同一原insert SHA>","cancel":null}
```

cancel 为 null 或一份现有完整 qmt.bound-trade.v1。选择规则：先核未决唯一性；存在一条未决时返回它，无未决时返回该目标 **seq 最大的实际终态取消记录**，无任何记录才返回 null。不能只查 pending，也不能让重启后较新的 definitely_not_called 记录遮住较旧但仍 unknown 的实际取消。alias 没有引入。包含终态避免竞争请求读得稍晚、目标刚完成就错误地丢掉真实取消收据。该结果只描述当前实际记录，不能证明一个没有入库的竞争请求曾与它绑定。

未知原 insert 返回完整标准 404 unknown_order；原 UUID/SHA/operation/关联不符或未决多条为 409 identity_conflict；无取消记录为 200 cancel:null，不能解释成原 insert 未调用。原 I/O 超时/故障沿 408/503。旧 Host 仍返回原 capability_unavailable，不据此尝试写。

Common的封闭接口、准确字段、owner/版本、原D及失败语义由[C++实施契约 UC-CPP-R1/R2](qmt-unknown-cancel-cpp.md)唯一规定：`QmtTradeCancelReference`仅Core可构造、不可复制，`lookup_cancel`完整验证后一次发布；其receipt/record保存实际取消的历史B，不授新取消token。

首次lookup所得私有引用仅在worker本轮内用于`resume_cancel`；跨轮保存已验实际`QmtTradeReceipt`，由现public `resume(receipt,D)`重新完整准入后GET该原UUID。预检失败保原receipt/Unknown/original_record=false，不返回NotSent；新client通过真实lookup重建私有引用。原`create_cancel`仍仅接`QmtTradeOrderReference`。

## UC-R5 丢响应与并发结果的准确解释

| 窗口 | 必须保留/后继行为 |
| --- | --- |
| A 的 POST 明确返回 cancel_pending | A 未登记；同 D 只读 lookup_cancel 获取目标实际 B；不计 A 成功，不 POST B |
| A 的响应丢失 | A receipt 仍 unknown，只 GET A；可独立 lookup_cancel 观察目标实际 B，但不能声称 B 是 A 的别名或 A 已成功 |
| GET A 后找到 A | 沿 A 的真实 phase/receipt 核查；与 lookup_cancel 返回的相同 UUID 合并内存观察，避免重复 GET/重复统计 |
| GET A 为 404，lookup_cancel 有 B | A 仍未知；B 只作为独立实际目标取消事实供原 ID GET；不得生成 C 重试 A |
| GET A 为 404，lookup_cancel 为 null | 保留 A 未知和无目标记录的当前观察；不把 A 当未调用，不重复 POST |
| B 在竞争回复与 lookup 之间快速完成 | lookup 返回最新实际终态 B；丢失 pending 状态不等于丢收据 |
| lookup 观察到后来另一次明确请求的 C | 只报告 C 为此刻最新目标实际记录；不能追认 A 当时对应 C |
| A/B 任何一次读取超时/畸形/换代 | 保有原 receipts 与 scope，按原 D 结束本轮；下一轮只读，不改阶段或源身份 |

本设计要求“原命令不丢、实际取消可核查、不会因竞争再发 SDK”，不要求把所有重复点击最终归成同一成功请求。持久 coalesced 别名只在后一种额外需求下必需，比较见 ADR 草案。

## UC-R6 Agent 与 Host 的完整执行闭包

Agent TradingKernel 将 `_closed` 的未知含义迁出：显式 close 单独保存；unknown_fenced 单独保存；硬故障单独保存。`execute` 去重先于新准入，原 originalD、owner thread、非重入、live_drain、fixed binding、enabled、symbol规则保持。cancel 仍只使用既有四参数 SDK 调用，Host 是原订单关联的唯一通信 owner。

SourceTradingService enqueue 在占位前后、tick 在执行前、Kernel 在实际 SDK 前使用一致的操作判断。source_unknown 只锁 unknown_fenced；clock/context/publication/handoff/event 失败均进入 hard_fault/明确 close；先 source_unknown 再硬错也必须拒绝后继 cancel。原结果先保存后发布和队列去重保持。实际 SDK 在途时 cancel 最多排队，仍由同一策略线程串行执行；停止不抢占已进入 SDK 的事实。

最后SDK调用准入定义明确reservation线性化点：字段/绑定/原D及clock预检后，Service按既有service→event短锁顺序核operation/关闭/硬错，并由事件owner在与真实gap发布同一锁下核gap/closed、取得至多一个调用票据。此前已发布的gap必须拒绝；此后gap或close只停止后继，当前票据保持原在途责任，不承诺物理SDK零窗口。reserved与sdk_entered分别表达，实际调用边界之前取消/失败票据不得伪造已进入SDK。所有SDK与外部callback在锁外执行，finally真实归还票据，drain计入其实际借用；保留原单策略线程/非重入/原D，无新线程或JSON字段。仅再读一次status不能替代共享原子准入。验收覆盖gap已发布但on_gap通知暂缓且owner已过初门、以及reservation之后的两种真实顺序，前者SDK0，后者最多原在途一次且后继0。

unknown是业务调用事实，物理drain以真实借用为准：若executing/active/queued均0、原结果已保存发布、事件closed且tickets/retained/inflight均0、无真实gap/hard_fault/交接失败，Service不得仅因unknown_fenced阻止物理drain。Agent还必须独立核pending_trade为空，并在尚open的原ControlPeer核原CALL经真实ACK退休；ACK前、未交接、迟到、peer关闭或原D耗尽均不得宣称close确认。ACK后在原close D内可完成正常关闭，保留原unknown结果与fence，关闭不恢复insert。不以重新计时或清未知记录完成关闭。

Host Runtime 负责实际来源锁、状态版本、连接、配置和故障事实；Journal 负责原命令/目标唯一性/关联/持久原 D；Control 负责在既有 active/future/retired 规则下安排可派发任务。对 queued cancel 的当前 source/proof 复核在 claim 发生，不能只在 HTTP 受理时核一次。全部读、事件持久和 ACK 的原顺序保持；unknown 不得阻断真实回报收集。

## UC-R7 Standard 原 worker 的有限审计

公开旧 C ABI/diagnostics 布局保持。新增私有 operation fence 与 AuditOriginal 任务，统一供 orderAction/enqueue/run_write 判断。writes_blocked 诊断在 unknown 时仍为 true；只有实际 cancel 内部分支使用本规范。callback unknown、read identity conflict、实际 gap、stop 等属于硬关闭，不能借该分支绕过。

Pending、AuditInput、AuditSummary的准确字段、角色与观察组，以及条件合并矩阵，由[C++实施契约 UC-CPP-R3/R4](qmt-unknown-cancel-cpp.md)唯一规定；状态只保存通信receipt/阶段/来源与有限诊断，不保存金融归约或WT地址。

触发与调度遵循以下要求：

1. 原写超时/unknown后保原pending，按既有request_timeout_ms（内部request_ms）设置下一读时机；owner pump/wait按真实定时唤醒，最多一条审计链。原写POST前安装inflight ticket，所有写完成分支核ticket后才清零。
2. 每pending在同B/插件实例最多新建一份ORDER read。普通未知原调用先GET自己的原UUID；需要当前proof时先完整保存prepared read receipt/Started再submit_once，后继仅resume原read ID。同来源明确终态后不再新建ORDER；精确未受理角色不GET A、不新建ORDER，只保已有read责任及目标lookup。
3. ORDER真实经过Host/Agent→原BoundReadJournal.finish_bound→TradeOrderLinks。成功后只lookup原token/WT身份并核原command，不执行mapper、不投onRspOrders、不改变identities金融/WT状态；实际取消仍由真实已有WT订单的orderAction发起。
4. 自己未决A与独立实际B观察分开。精确cancel_pending先持久锁存UnadmittedTargetLookup，并在通用错误/晚deadline前提交；无B/读取失败保A原槽和原receipt/read/charge，后继只读目标；合法null或B终态不伪改A阶段。只有目标/read责任完结才退役。A/B有不同Started ORDER read时保两槽、各原ID和charge，待矩阵条件满足再合并；目的在途或合并准备失败不丢receipt。
5. 同UUID须核原body/SHA/目标/B/profile/容量，同文合并观察且每轮最多一次GET，异文硬错；未知B继续原ID GET，不被较新C覆盖。源换代沿原插件/worker生命周期恢复，不在活实例偷偷换B。新实例正常查询可恢复真实订单，不假装持有全部旧pending。
6. 后继每轮可用新有界只读D，全阶段共用该轮D，原写/查询业务D保持；query_first首次待核查沿NRT-R32立即安排，后继轮间至少隔request_ms，轮转pending。单次运输不可用保unknown/原receipt，可证明硬错锁停；容量不足延期并由真实队列/charge变化唤醒，不忙等。
7. owner/worker沿原TaskCredit、generation、锁外I/O、完成值持有和drain。receipt/phase/has_record/read state与未受理角色整组构造/提交；复制失败保完整旧组或完整新组。stop/detach后不新I/O，晚Summary仍先保存新ORDER身份/Started及角色责任，所有持有对象销毁/移交后才归还charge。unknown insert在未满足NRT-R32独立终态及原WT应用时保留fence；原命令身份/原文/SDK unknown结果始终保留于原Journal。

无已完成 ORDER proof 时，既有 orderAction 的 create_cancel/Host 当前 proof 检查仍拒绝，不自动等待到原取消 D 以后再发送。后继自动读不会自动重试该取消请求。

## UC-R8 预算、异常与原 D

不增加线程/数据库/清理器。协议常量仍集中定义，源兼容 Python 3.6.8 标准库。status v2 仍计入原 MAX_METADATA_BYTES（16384）；无额度扩容。cancel lookup 请求计入原 HTTP request cap；响应上限 `record_capacity + MAX_METADATA_BYTES`，与原 order lookup 的保守上限一致。部署 HTTP cap 过小按现能力预算明确拒绝，不扩大实际网络上限。

Journal 未决检查/最新查找在 max_trade_commands<=4096 的原集合内、同锁和原 I/O D 做有界查询与记录校验；仅一次原数据库事务，未入库冲突不占新命令 quota。原 record body/result/MAX_METADATA_BYTES 预留不变。每目标唯一性可用现列查询实现，无新增持久索引要求。

Common/Standard的DTO字段边界、逐阶段live-set、checked arithmetic及宿主逻辑payload预留以[C++实施契约 UC-CPP-R5/R6/R7](qmt-unknown-cancel-cpp.md)为唯一正文，状态为accepted implementation、动态未验。交易R_t与账户R_a分别使用K/Q；私有ORDER引用、lookup双原文、prepared token、输入/summary独立副本及owner改key准备期按实际并存计费。

最多一条审计链，HTTP前完整预留；原pending与所有其他队列/event额度继续保有。精确409后同轮lookup也取得同一唯一链及新增全额预算，容量不足或原D耗尽保未受理角色后延期到只读轮。双Started保两槽原charge；stop/drain前持有对象不提前退费。Common内部HTTP上传/异步排空、parser/DOM/codec临时存储沿各组件现有限额，宿主预算不声明RSS。验收包含小K/大Q、最大N/J、双proof/双原文、复制/合并失败、溢出、恰好/少1字节、满额延期与关闭实际回收。

所有库调用保留原 owner/ticket/D 规则。私有取消引用在完成全部验证和拷贝后一次发布；异常保留已保存 receipts。提交前可证未调用与提交/commit 可能发生后的 unknown 继续区分。普通日志仅用固定错误码、UUID/摘要/类别，不带账户或源 payload。

## UC-R9 精确实施所有权与依赖

采用契约冻结后并行三组、Standard 集成最后收口；没有本文以外的实现授权。

| 组 | 独占产品文件 | 独占主要回归入口 | 交付不变量 |
| --- | --- | --- | --- |
| A 源与共用协议常量 | agent/guanheng_qmt_shm_agent/{trading_kernel.py,trade_service.py,control_trade_agent.py,trading_agent.py,trade_events.py}；必要共用版本常量放现 trade_capabilities.py，不改 profile.v1 形状 | qmt_shm_trading/{test_trading_kernel.py,test_trade_service.py,test_trade_source_status.py,test_trade_control.py,test_trade_handoff.py,test_trading_agent.py,test_trade_strategy.py,test_trade_control_generator.py,test_trade_events.py}；源状态测试若引用 Host validator，待 B 合入运行 | 原单线程、去重、D、有限槽、真实 gap/close、结果先持有；v2 精确发布 |
| B Host/Journal/HTTP | host/guanheng_qmt_shm/{trading_journal.py,trade_order_links.py,trade_runtime.py,control_trading.py,trade_status.py,trade_bound.py,app.py} | qmt_shm_trading/{test_trading_journal.py,test_host_trade_runtime.py,test_host_trade_control.py,test_host_trade_http.py,test_trade_bound.py,test_trade_order_links.py,test_order_query_recovery.py} | 原单 owner/事务/派发前持久、每目标唯一、只读实际取消引用、真实 proof、原 ACK |
| [C Common](qmt-unknown-cancel-cpp.md) | src/GuanhengCommon/QmtHostTradeClient.h/.cpp；不改 QmtBoundReadCore 或金融 mapper | 新 qmt_shm_trading/native_unknown_cancel.cpp、test_native_unknown_cancel.py；现 native_trade_client/native_order_query/native_event_context 链 | 原严格schema/profile/owner/D、Host/Source版本独立冻结、私有首次resume_cancel/跨轮public resume、HTTP至多一次取消POST；准确契约见C++正文 |
| [D Standard（根集成）](qmt-unknown-cancel-cpp.md) | src/TraderQMT/StandardQmtTrader.cpp（h 只在必须声明私有结构时；旧 C ABI 不改）；CMake/构建及正式文档索引由根 | 新 qmt_standard_trader/unknown_cancel_probe.cpp、test_unknown_cancel.py；现 test_standard_trader、test_standard_shm_trader、test_standard_events、test_standard_shm_events | 原唯一worker/owner、TaskCredit/原pending；持久未受理角色、成组观察、双Started条件合并、独立预留与真实回收；无重复SPI、no-new-insert；准确契约见C++正文 |

路径前缀 Agent/Host 均在 connectors/qmt_shm，测试均在 tests/integration。A/B 不同时改同一 validator；B 拥有 Host trade_status，A 仅冻结 Source 输出并对照它。生成策略模块清单如需更新由根定位真实 generator 后独占，不手写生成产物；新增模块优先避免，现 trade_capabilities 常量不会增加导入文件。任何额外文件所有权先向根报告。

交付顺序：冻结 UC-R1–R8→A/B/C 各自实现→根统一编译/组合验证→Standard 接线→真实 SHM+固定原 Adapter 替身完整链→独立 full。只完成某层不得开放恢复能力或宣称 unknown 撤单完成。

## UC-R10 验收入口与通过标准

| 组/要求 | 必须覆盖的故障和观察 | 入口 |
| --- | --- | --- |
| 版本 R2 | 新旧矩阵全部组合；同 B 版本漂移；profile/Journal 原 SHA 不变；v2 malformed 不降级；readonly/config disabled 不授 cancel | 源/Host status tests、native_unknown_cancel |
| 准入 R1/R6 | insert unknown 后目标 cancel 1 次、insert 0 次；source_unknown 后 hard clock/publication/gap/close；SDK前同步 close；原 worker/core 错 owner | kernel/service/host/runtime/native/standard |
| 原证据 | unknown 当前 event、当前真实 ORDER、仅历史证明、无 token/broker、错账户/证券、未派发、旧 policy、proof 在入队后改变 | order_query_recovery、trade_order_links、真实 SHM standard |
| 原事务 R3 | 两客户端同目标竞争；一条实际 cancel，另一精确 cancel_pending；不同目标；旧存量多未决硬拒绝；commit 前失败/commit 后异常/重启；同 ID body 冲突 | trading_journal、host_http/control |
| receipt R4/R5 | 快速终态 B 仍能 lookup；自己的 A 404+目标 B、A找到、双方无记录、读中换代、完整/截断/超时409、篡改目标UUID/SHA/WT身份/B、私有句柄错owner | native_unknown_cancel +真实HostHTTP |
| 取消结果 | bool true 只信号；false 真实返回；cancel unknown 保原ID，再次WT请求不产生第二SDK；未决解除只由该调用明确结果 | kernel→Journal→Common→Standard |
| 审计 R7 | unknown原D耗尽后新只读D；每pending/B至多一个新ORDER读；后继GET原query；不重复onRspOrders/订单统计；读失败保unknown；stop/detach无后继读；无真实ORDER不能造order | standard unknown_cancel +固定原 Adapter |
| 队列/D R8 | 原队列满/字节满/原Journal满/SQLite锁等待/HTTP末D；前方禁止insert不饿死cancel；原inflight不被抢占；析构前charge不退 | 各层异常入口+standard |
| 兼容 | 旧普通 sdk_returned cancel、reference.v1/v2、R2c/R12事件、旧配置、旧SPI/ABI、production Factory不动 | 原受影响完整链 |

通过要求同时断言真实替身 SDK 调用次数、原请求/实际 cancel UUID 与 body、原 phase 不改写、无新 insert、有限预算与关闭实际 owner、原 WT 状态/统计。仅 HTTP fixture 形状成功不替代 Host 真 ORDER proof；仅 helper 测试不证明全链。真实 SDK 调用数本草案为 0。

## 已核源码与待验事实

受控build/qmt-unknown-cancel-contract-002/SOURCES.sha256及实施目录DESIGN-INPUTS-ROOT-VERIFIED.json保存本次引用原bytes与39项设计独审输入。核心锚点：Standard.cpp:192/257/307/413/807/856；Common.cpp:142/209/427/572/615/658/681；trade_runtime.py:104/118/177/219；control_trading.py:62/70/216；trading_journal.py:259/336/393/442/469/483；trade_order_links.py:112/204/254/302；trade_service.py:92/172/238/346；trading_kernel.py:60/97/146；trade_event_records.py:77/237。行号按快照核，根 R12 后继若改同文件须重新对照。

尚需真实只读/官方证据：异常/重启后完整 token 与 ORDER 字段是否实际可用、broker 跨日同号时 SDK cancel 定位范围、真实状态时延。缺字段时本实现保持 unknown，不猜金融字段。持仓查询/成交共同水位仍属 SEV-R8。没有这些真实证据可先完成本草案的通信与替身全链实现，不能据此宣布实盘资格。

## UC 组合负向验收：撤单 claim 提交后业务到期（accepted 测试合同）

采用真实 HostTradingJournal/BoundReadJournal、HostDomainWorker/Future、HostTradingControlLoop 与 SourceTradingService SDK替身。先由原源线程实际进入 insert 替身并形成 unknown，再通过真实 AccountQueryAdapter policy2 ORDER 结果与原 submit_bound/claim_bound/finish_bound 事务形成当前 query proof；lookup 必须核原查询 UUID/SHA/index，不能直接写关联表或把 insert 当 cancel。Harness 的 Runtime 保持明确测试替身，本项不授真实 HostRuntime/HTTP/SHM/Standard 资格。

唯一故障注入限于目标 cancel 的真实 dispatching UPDATE 所在连接：真实 commit 成功返回后只推进显式业务 clock 至该命令原业务D之后；I/O与close使用开始时固定的真实monotonic D，SQL/返回/Future不伪造。真实domain Future须传播提交后业务TimeoutError；公开control.close仍抛失败，cause保留同一Future异常，原job/Future/UUID/bodySHA/dispatching/空source_result与原D保持。原insert unknown不改写，SDKcancel及外发cancel CALL均为0，不能二次claim、删除job或清fault制造成功。

分别证明domain线程真实join与公开close_complete=false、Journal owner仍保留。随后由测试资源owner在同一固定D内处置独占资源，单列此清理并保持业务关闭失败事实。测试通过只证明这个明确故障输入下的保守合同；旧四案历史失败首因仍unknown，原成功oracle及旧失败原件保持。
