# 标准 TraderQMT

类型：功能规格。状态：分段接受。STQ-P2/P3版本准入及原文运输、STQ-P7账户身份、STQ-P8线程分工和STQ-P9自有候选接口实施范围accepted；完整故障矩阵、实时消费、查询交接、恢复和生产切换继续核实。完整标准插件与真实SDK尚未验收。

后继实施范围：本文件STQ-P7的有限账户身份覆盖要求accepted，优先完成标准查询消费所需的自有适配层；标准Factory、SPI消费与重启交接仍分别验收。该接受范围不授权新增WonderTrader框架修改或真实委托。

实现状态：STQ-P2/P3的显式版本、原始字段运输、receipt和完整内存准备已完成隔离验证，详见[账户投影证据](../evidence/2026-10-24-qmt-account-projection.md)。STQ-P7的batch.v2金融消费及有限WT身份覆盖已通过[原生/SHM隔离验证](../evidence/2026-10-24-qmt-account-identity.md)。P8线程分工已通过限定验收；P9标准候选Factory/SPI及真实SHM正向写已通过[11方法12场景](../evidence/2026-10-24-qmt-standard-trader.md)，标准层完整故障矩阵、实时事件/恢复、生产Factory切换和真实SDK字段回显仍待验证。

## 当前实施边界

只读观察的运输换代由Standard原IO worker拥有完整ReadGeneration。每轮账户Query与后继Resolve、每个事件页及其查询/身份续段共用该轮账户客户端、身份客户端及完整认证上下文；Task和Completion只传有限数值票据。新一轮重新核同一账户、完整原profile/资源合同及Source业务session，允许其认证运输binding改变。完整Source应用session变化继续形成明确故障。已进入的一轮保持原精确binding和原绝对截止，原请求未知继续原身份，不重派。原金融命令客户端及收据独立保留，读取换代不重绑或重发写命令。

原事件交付index、read/handled cursor在同一Source业务session内保持；下一页在认证完成后采用新运输上下文，页内全部续段继续精确绑定该页。同一认证运输内的观察复用账户/身份客户端和原HTTP owner；新观察在SDK请求前发现精确绑定变化时建立完整后继代际，旧在途票据继续持原代际及原D。每个读取代际使用原队列预算预留两份响应银行及有限认证材料，数量受原max_queue限制。实际客户端由原IO worker在旧票据归零并排空HTTP回调后销毁；owner只释放票据，关闭继续沿首次原截止核全部客户端回收。实际跨运输连续运行、Source应用换代拒绝及生产恢复分别登记证据。

自有执行算法参数校验与原工厂消费同一Variant名称，并复用原`StrUtil::split`取factory/unit前两段的规则。额外段等原工厂可接受的名称形式保持原解释，实际选中的股票算法均须核相同min_order要求，避免参数校验与实际装配身份不一致。

现金股票/T+1数量目标使用原`WtExeFact.WtStockMinImpactExeUnit`区分总持仓与可卖量；通用MinImpact默认读取可用仓位，资格只覆盖已验证的总量与可用量相等条件。股票执行器的`min_order`为显式正整数，取值不超过INT32_MAX，现金ETF首模型为100份。自有StandardExecutionHost在创建交易API及启动其工作线程前校验该参数，缺失、零、负数、非整数或非有限值以InvalidConfiguration拒绝。原股票执行器决定当次可执行卖出数量，WT策略目标及券商未完成责任分别保持原owner；不把受可卖量约束的部分执行记作已达到策略目标。

首先实施显式账户投影版本与端到端准入，复用已有原线程读取、Bound Journal、codec及唯一金融mapper。版本事实唯一取自可信`operation_profiles.account.trade_detail.policy_version`：原值1.0保持，新值2.0仅适用于显式v4/control2组合，不新增另一配置开关。它参与实际账户descriptor与profile原文，不随每次请求或写开关改变。旧配置、v3与v4/account1.0保持原行为。

本阶段同时实现源端投影、可信profile/策略配置、Host版本准入、C++账户请求/receipt/terminal选择及相应回归。账户字段的读取和运输不自动建立WT归属，不开启交易。生产Factory、线程与SPI生命周期、身份覆盖和查询/回报交接需后续明确完整要求后接线。

标准插件验收复用固定上游源码及已批准覆盖构建；当前工作树冻结的其他框架差异不进入该资格。现成构建接缝为`tests/integration/native_realtime_strategy/build.py`使用的固定快照机制，自有Trader目标在该机制上接线，本轮不新增WT框架修改。

## 账户投影与身份

### STQ-P1 事实所有者与原生接缝

目标是让标准四查询提供真实券商账户事实，并恢复本系统原 WT 委托身份。复用能力目录 [WT-T01、WT-T02、WT-T08、WT-T09](../development/wondertrader-capabilities.md)：[ITraderApi/ITraderSpi](../../src/Includes/ITraderApi.h) 的 queryPositions/queryOrders/queryTrades/queryAccount 与 onRsp*；[TraderAdapter](../../src/WtCore/TraderAdapter.cpp) 的查询推进、持仓/统计和策略通知；[WT Order/Trade](../../src/Includes/WTSTradeDef.hpp) 的标准身份槽。金融转换唯一入口仍为 [AccountMapping](../../src/GuanhengQmtBootstrap/AccountMapping.cpp)。Host 保存原命令、关联证明、原事件及交付状态，WT 拥有持仓、资金和订单业务归约。

实际链为 RestrictedTradingAgent → RestrictedReadAgent._initialize → AccountQueryAdapter → 原 get_trade_detail_data → 原 native result/finalizer → control2/Host Bound Journal → QmtBoundReadCore(AccountV4) → ShmAccountMapping → map_account_rows → 有限身份覆盖 → 标准 SPI。身份覆盖查询单独经 QmtHostTradeClient.lookup → HostTradingJournal.lookup_trade_order → TradeOrderLinks，沿既有 [QST-R21](qmt-shm-trading.md) 和 [NQT](native-qmt-trade-client.md) 校验原文、身份、来源与摘要。

每个账户查询有各自 request_id、原 D、started_at/completed_at、原结果 SHA 和完整性；四次调用沿 WT 原查询链独立完成。四个时间区间与一次事件页水位不能构成原子账户快照。正常 writes_enabled、账户绑定和终端模式继续使用实际配置，不增加批准级别或逐单资格状态。

### STQ-P2 显式版本与源投影

本段版本选择已接受，实施同时更新生产者、Host与C++消费者。既有v3与旧v4/account policy_version=1.0保持batch.v1原行为；新增v4/account2.0由可信descriptor显式冻结选择。

| 项目 | 原 v3 | 标准交易 v4 候选 |
|---|---|---|
| read_profile_version | qmt.read-profile.v3 | qmt.read-profile.v4 |
| control/B 版本 | 1.0 | 2.0 |
| account operation_id / policy_id | account.trade_detail / qmt.account-read.v1 | 保持同名 |
| account descriptor policy_version | 1.0 | 2.0 |
| limits schema、数值预算与字段 | qmt.account-read.v1，原值 | 沿原形状与预算 |
| account data.schema_version | qmt.account-batch.v1 | qmt.account-batch.v2 |
| order/deal 来源字段 | 原白名单 | 原白名单加 m_strRemark、m_strOrderRef |
| position/account 来源字段 | 原白名单 | 保持原字段 |

policy_version 2.0 是显式投影契约，参加公开 profile 原字节与 capability SHA；旧 v4/1.0 不能被当作具备身份恢复字段。v3 的 descriptor、请求、结果 schema、白名单顺序及成功/错误行为保持。旧 v3 与旧 v4/account1.0 仍采用原白名单和 batch.v1；新增 v4/account2.0 只接收 batch.v2。客户端在 prepare 时从实际已核 profile 冻结账户请求 policy_version 和预期 data schema，恢复原 receipt 时保持原选择，不能看到响应后反向选择版本。标准交易恢复入口显式要求 account2.0；通用 v4 账户客户端仍支持旧 account1.0。错误组合在 SDK 调用前拒绝。market 操作版本保持原值。

源 adapter 工厂从已校验的账户 descriptor 决定投影版本；可采用 AccountQueryAdapter 的显式 keyword projection_version（默认 1、仅精确整数 1/2），v3 与旧 v4/account1.0 的读工厂选择 1，RestrictedTradingAgent 的已核 v4/account2.0 选择 2。不根据写开关、请求内容、SDK 对象是否恰好含某属性隐式切换。读请求仍只有 account_type=stock、datatype、scope=account，strategy_name 仍为 null；新增字段不改变 SDK 原三参数调用和查询范围。

batch.v2 的外层字段精确沿 batch.v1：schema_version、account_binding、query、execution、completeness、trading_date、rows；只改变 schema 值及 order/deal 行允许集合。两个新增字段复用原 _field/_scalar/_Budget：真正 getter 每字段每行至多一次，字段缺失则键缺失，显式 null/空串/零分别保留，不 trim、不把数字转文字、不按前缀补全。合法 JSON 标量类型沿既有源快照规则；身份采用条件在下一条独立收紧。属性抛错、超额和原 D 超期沿原失败路径，不能返回已截断行。两个键和标量的 nodes/chars/bytes 全额计入同一预算，getter 与编码前后核同一个执行 D。目标 Python 3.6.8 标准库约束保持。

m_strRemark 是完整 sdk_user_order_id 回显候选；只有精确非空文本并符合已接受 token 契约时进入关联查询。m_strOrderRef 是券商原始本地引用，只保留和展示；当前原系统没有证明它等于 WT EntrustID、command UUID 或 broker OrderSysID，不能据它建立替代关联。普通手工备注不能凭格式相似取得原 WT 身份；只有完整精确命中 Host 已持久 token 才继续验证。非字符串 Remark、缺失、null、空串及未知 token 均不猜测归属。合法但不具备身份资格的标量保留作诊断，身份覆盖视其为不可关联；复杂类型、非有限数及非法 Unicode 仍由原标量边界拒绝。

### STQ-P3 Bound 原文、金融映射和身份覆盖

原生`QmtBoundReceipt`在原binding_json/request_body后追加read_profile_body与read_result_capacity，默认空/0保持原两字段聚合初始化。新AccountV4请求保存已核完整原profile和实际result容量；恢复核profile原摘要等于原B.capability_sha256、完整联合预算、账户及原请求policy。policy2.0收据必须完整，不能用当前profile给原收据升级。旧V4空/0收据只沿原policy1.0既有核查路径，V3和市场路径保持原语义。

Host 的原读 Journal、Bound DTO、结果 hash、原请求/三 B 校验和原 receipt 恢复保持完整，Host 不把 lookup 结果塞进已签名的源账户原文。新增 descriptor/data 版本准入分别贯穿 read_capabilities、可信配置、源工厂、Host Request/Bound 与 Core；QmtAccountFields 的 v3 数组保持，Core 按显式版本选择 v4 附加字段。Source→Host 原数据和 Host→C++ 关联回复各自保留原 bytes/SHA。

C++ 以同一次查询的原 SignedHttpDeadline 完成 Core 验证、必要 lookup、金融映射、身份覆盖和 SPI 前复核；每行 lookup 不授新 TTL。每个完整 token 最多一次 lookup，可在该批次的有限缓存复用；缓存容量不得超过实际 max_rows。查找失败、超时、完整 409、截断回复保持原错误及有限上下文；已准备 WTSArray 由 RAII 释放，禁止先发部分 SPI 批次再报整批失败。

金融字段、金额/数量/价格、CNY/空币种、SH/SZ 映射、日期时间、订单状态与成交 scoped_trade_id 全部继续由 map_account_rows 的唯一实现解释。m_strRemark/m_strOrderRef 不进入另一套财务计算。新增覆盖层只改变已经构造对象的管理身份，并产生独立带来源的身份视图。现有只读 view_version=2/3 的原字节和统计语义保持；新身份视图单独版本化，不能把旧统计 entrustID=brokerID 注释改成真实原委托证明。

map_account_rows 会按规范金融身份折叠重复行，故覆盖层不能将输入 rows 下标与输出数组下标直接 zip。应在调用前验证并构造有限行身份索引，以原金融 key/已输出对象身份取对应覆盖：订单以该批次已验证 broker key，成交以现有 scoped_trade_id+refOrder。相同金融 key 的重复行若身份字段缺失/值/完整 token 产生冲突，整批拒绝并保留原文；不能让金融去重静默丢掉身份差异。broker key 仅用于同批次结果定位，系统归属仍逐条来自完整 token 与 Host 原 insert。

身份视图候选为 qmt.wt-order-identity.v1：account request_id/result_sha256、金融对象 key、来源 Remark/OrderRef 的 presence+原 value、classification（owned/external/unresolved/conflict）、原 lookup bytes/hash（无 lookup 时 null）、采用的 entrust_id/user_tag（未采用时空）、reason。此视图是派生通信诊断，不追加为原账户或订单业务账本。

离线物料准备公开接口新增 `prepare_trade_runtime(agent_root, sdk_metadata, license_bytes)`，与原 `prepare_runtime` 共用同一私有准备实现；前者固定以 `guanheng_qmt_shm_agent.trading_agent` 为闭包根，后者继续以 `guanheng_qmt_shm_agent.restricted` 为闭包根并保持原输出语义。`identity.roots` 必须如实记录实际冻结根，所有依赖均由既有闭包算法发现和核验，禁止手工补入模块绕过核验。policy2.0 的准入须在完整冻结模块及生成策略正文中的可信 settings 一并验证；准备阶段在 QMT 外读取与校验 SDK 文件，运行期复用原内存加载器和策略入口，保持无文件、无网络加载。

### STQ-P4 精确关联与 WT 槽

userTag由WT生成，用于原委托和回报关联；本功能不要求用户提供。标准WT撤单对象本来不携带userTag，适配器从原委托记录恢复WT标记，QMT撤单SDK继续使用券商委托号。该标记的恢复用于正确交回WT及识别管理归属，不构成另一个用户权限或审批条件。

Host 继续仅接受 R21 的完整 sdk_user_order_id 或原 (entrust_id,user_tag) lookup。身份恢复使用完整 token 形式；原 insert 的账户、account_type、binding_id、证券/交易所及 token 与该批次可信账户和行数据精确匹配，原 insert 必须已有 dispatch_binding。原命令原文/SHA、qmt.trade-order-reference.v1 结构和 association_error 均按现有 codec 核对。存在 broker proof 时，还须核 broker_order_id 与该行 m_strOrderSysID 原值一致；证明保留 source/session/sequence/event SHA。

| 关联结果 | 券商金融事实 | WT 管理身份 |
|---|---|---|
| 已派发 insert、完整 token、账户/证券一致、无关联错误且匹配 broker proof | 采用唯一 mapper 的原事实 | owned：Order.EntrustID=原 insert.entrust_id；Order/Trade.UserTag=原 insert.user_tag |
| token 缺失/空/不具备关联文本或 Host 404 未登记 | 保留真实券商单/成交 | external：Order.EntrustID 与 UserTag 为空，Trade.UserTag 为空 |
| 已知 token 但没有派发或完整 broker proof | 保留来源原文与查询诊断 | unresolved：不伪造原 WT 归属，不宣告该自有未决命令已恢复 |
| token 已知而账户/证券/broker 证明冲突，或 Host association_error | 保留原文及已知关联错误 | conflict：不发布带错误归属的对象；沿当前错误停新写和核查 |

owned 与 external 的 Order.OrderID、Trade.RefOrder 均保持真实 broker OrderSysID；Trade.TradeID 继续使用现有 scoped_trade_id，绝不换成 UUID、token 或裸 OrderRef。WTSTradeInfo 没有 EntrustID 槽，禁止向其他字段塞原 EntrustID。所有 WT 64 字节槽在调用 setter 前核可表示长度和编码，不能截断后认领。外部手工单仍影响真实账户/券商统计；空 UserTag 使 WT 不据伪造策略标签认领本系统 localid。

R21原事件proof继续保留；后继[QST-R21Q](qmt-shm-trading.md#qst-r21q-当前订单查询观察恢复)接受真实ORDER查询观察作为独立类型的原委托关联证明。Host在原成功查询结果事务中建立，历史GET不刷新；查询request/result SHA/原行下标/B分别保留，不补造事件session/sequence。P7依据Common已完整准入的Event或AccountQuery类型核验后恢复原WT身份。历史事件或历史查询证明可解释原身份，当前撤单仍由client/Host分别核原当前来源；身份恢复不承诺订单alive、撤单成功或持仓已吸收成交。

### STQ-P5 WT 事件消费与有限传输状态

静态结论：当前 WT TraderAdapter 的 _trade_refs/checkSelfMatch 用于自成交识别，不能直接提供幂等应用。onPushTrade 在调用 checkSelfMatch 之前已改持仓/统计并通知策略；相同 TradeID/RefOrder 只在检查函数中返回 false，调用者没有阻止前述应用。onRspTrades 也按输入累加统计；CSV/rtdata 没有 QST 的 session/B/sequence 原子消费游标。现有 mapper 的 seen 只在单批次内去重，作用域不能扩大为重启恢复证明。以上结论以本次固定源码为限。

Host 必须继续保存现有有限通信事实：原 command/token/WT 身份、未决/unknown、R21 关联及证明、原事件 bytes/SHA、各 source 流连续 durable、ack_intended、source_ack 和 gap。这些记录仍由同一个 Journal owner/事务维护。源业务 ACK、HTTP 成功、RPC ACK、页已取到以及 WT 已应用分别记账；当前 read(events) 不推进任何 WT 消费前沿。

标准插件当前进程内可用 (source B, session, sequence, event SHA) 连续游标抑制同一运输事件重复回调；同 seq 异文拒绝。不同 sequence 的同一成交仍可能是 SDK 重复推送，因此在送 SPI 前还需有限的成交身份+规范事实摘要去重，复用唯一 mapper 的 scoped_trade_id/refOrder 和数值规范化；同身份不同金融事实保留冲突，不再次累加。它只存“已交付哪些原事实”的标识/摘要，不存或计算持仓、资金、盈亏和累计订单状态。事件缺少 mapper 所需金融字段时，保留原事件并沿原 D 查询核实；不能补零构造业务回报。

若完整产品要求跨 C++ 进程恢复该交付游标，最小新增 Host 状态应是每 consumer/epoch/source 一条有限通信记录：连续 delivered_through（消费者报告 SPI 返回的前沿）、至多一个 in_flight(sequence,event_sha256,delivery_epoch) 和故障/不确定状态；原事件无需复制。consumer 与 stream 数目、记录总字节、一次领取/确认均须显式预算和原 D，沿同 Journal owner，确认只能匹配先前实际领取原票据，不能跨来源、跳洞或越过 durable。现有 R18/R20 没有该公开接口；此处是待完整规格接受的最小状态需求，不以文件或代码存在冒充已实现。

在交付前持久 in_flight，SPI 返回后再持久推进 delivered。若在回调前后崩溃而只有 in_flight，Host 能证明交付不确定，不能判定 WT 未应用或已应用。保持未知并进入 WT 原查询恢复，不把同一笔增量盲目重放。即使 delivered 已持久，WT 进程内状态和 Host 事务也没有共同提交证明，重建后仍需原查询恢复；字段名不得称为 wt_applied。Host 不因该前沿自动删源事件或关联证明。

四查询与实时事件如何划分已包含成交，尚缺 QMT 单一查询/回报共同水位或 WT 可原子提交的应用接口。不能通过暂停本地发送、四次查询完成时间或查询空页推导共同快照。后续完整规格必须明确同实例重连和新进程重建的 cutover 条件，覆盖成交在查询间发生、快照已含但回报晚到、SPI 返回后 Host 确认前崩溃；证据未闭合时保留这一恢复缺口，不创建第二套业务账本来猜测修补。

### STQ-P6 验收与待核实项

STQ-P2/P3已接受部分按上述证据登记；完整标准插件后续至少覆盖以下验收，逐项按实际链路证明，不能用运输切片的通过替代尚未实现的身份覆盖和恢复：

1. v3 请求/profile/结果与既有 golden 原 bytes 一致；v4/2.0 的 version/profile SHA/三 B/原 receipt 与 Core、ShmAccountMapping 全链一致；旧版本拒绝新数据。
2. getter 只取一次；missing/null/空串/零、异常 getter、Unicode/非法 scalar、追加键预算边界、SDK 晚回和编码超 D；四 datatype 的成功/错误/空列表沿原契约。
3. 同 broker 不同 token、已知 token 错账户/标的、缺 proof/历史 proof/当前 proof、完整 409、lookup 超时、重复输入金融相同但身份冲突、ABI 槽过长；仅精确已知关联覆盖原 EntrustID/UserTag。
4. 金融 mapper 旧视图与数值 golden 保持，外部手工单仍返回真实事实且 UserTag 空；重复行折叠后覆盖仍对应正确对象。
5. 事件重复页、同 seq 异文、不同 seq 同成交、序列缺口、容量、崩溃边界和查询/事件交错；分开证明 Host 持久、源 ACK、消费者回调返回与恢复结果。

未知项：目标 SDK 在四查询里两个新增字段的真实类型/长度/完整回显需要实际只读证据；当前草案只承诺受限原值投影。WT 原实现的消费原子性缺口已由源码证实，跨重启 cutover 的可行保证仍待专门协议/回归验证。文档索引及完整 TraderQMT 要求由根在合并接受时统一登记，本节不替其他切片宣布完成。

### STQ-P7 标准账户批次的有限身份覆盖

本段明确STQ-P3/P4账户身份部分的实施契约。新增自有QmtAccountIdentity模块，公开map_shm_account_identity_batch(stage, Core结果, 固定AccountBinding, BaseDataMgr, QmtHostTradeClient, 身份预算, 原SignedHttpDeadline)。旧map_shm_account_batch严格保持batch.v1；新增map_shm_account_batch_v2共用同一metadata实现，仅接已核v4/account2.0原receipt和batch.v2，调用唯一map_account_rows一次。查询、金融转换、关联和最终身份写槽均消费原D，不给每行续期，不发SPI。

AccountBatch尾部增加source_to_output，长度等于原source_rows，值为该原行对应的最终WTS数组下标。唯一mapper直接在既有金融去重键命中/新对象分支记录对应关系；金融判断、对象顺序及旧version2/3 views原字节保持。身份层只使用该显式对应表，不复制日期解析、scoped_trade_id和金融key算法。它在任何lookup之前比较同一最终对象所对应全部原行的Remark/OrderRef：presence、JSON标量类别和值必须一致；缺失/null、空串/缺失、0/false、整数/浮点差异均不能被金融去重吞掉。

QmtHostTradeClient.lookup在现唯一原命令/记录/关联校验处，给私有构造的QmtTradeOrderReference增加只读facts：account_id、account_type、binding_id、symbol、entrust_id、user_tag、sdk_user_order_id、dispatched、has_broker_proof、source_sequence和source_event_sha256。有broker proof或association_error必须有原dispatch_binding；证明原来源B/session保持。SDK token文本准入提取为共享纯函数，lookup和覆盖层沿同一规则，不猜前缀。LookupResult尾加response_body、response_complete和not_found：保留有界原回复，reference_json仍只表示完整已验证reference；not_found只在完整、原D内、标准二字段错误正文且error_code精确unknown_order的404为真，断流、其他404、坏正文和超时不能作外部单证明。

身份入口沿原D调用trade client prepare，核其当前event_source B与账户原receipt B相同；采用前再次核相同来源，历史broker proof可解释原身份但不能刷新为当前可撤证明。每个完整token最多lookup一次，缓存只存本批有限结果；次数、缓存项和输出对象数不超过已验profile max_rows与AccountBinding.row_limit中较小者。max_lookup_bytes、max_identity_view_bytes、max_total_bytes由调用者显式提供且为1至64MiB，子预算不得大于total；total计费原data bytes、原金融views bytes、source_to_output索引有效载荷、缓存token/原lookup回复及新身份视图有效载荷，逐次加法防溢出。输入/输出有限行、节点和字符串上限继续限制容器开销；该额度不宣称等于分配器的实际物理内存。

只有全部金融行、身份分组、lookup、预算和原D核实完成后才统一写WT身份槽。owned写Order.EntrustID/UserTag或Trade.UserTag；真实OrderID、TradeID、RefOrder及全部金融值保持唯一mapper输出。external和unresolved的身份槽为空；unresolved保留真实金融批次及明确诊断，表示已知原委托尚缺派发或broker proof，不增加整批Pending或四查询原子门。冲突、运输失败、额度耗尽及原D超时不给可发布数组，RAII释放整批；允许保留有界诊断。setter前核UTF-8和63字节可表示性。

新诊断视图schema为qmt.wt-order-identity.v1，按最终WTS对象输出，包含stage、输出下标、账户request_id/result_sha256、实际broker OrderID/RefOrder和scoped TradeID（不适用时null）、Remark/OrderRef的presence+原scalar、classification、采用的entrust_id/user_tag、reason，以及lookup_response_index/lookup_sha256（无lookup时null）。原lookup bytes仅在返回lookup_responses中每token保存一份，由索引引用；不追加金融账本。position/account不做身份lookup、不新增身份视图。

验收必须含原mapper views/金融槽保持、重复行折叠对应、重复身份差异拒绝、owned/external/unresolved、完整404与坏404/断流、完整409、账户/证券/broker冲突、历史proof身份解释、同token缓存、容量与原D失败及无部分数组。至少一条新增v4/account2.0真实Host/Win32 SHM→Core→唯一mapper→关联覆盖隔离链运行通过；SDK仅替身，标准SPI与真实券商验证分别登记。


### STQ-P8 账户消费的线程分工

本段accepted，实施范围是自有适配层的线程职责收敛。标准插件的唯一I/O工作线程拥有AccountV4与Trade客户端，WT对象、BaseDataMgr和SPI留在创建插件的宿主owner线程。业务入口允许策略/执行线程并发调用，只复制有界值入队；它们不执行网络、金融映射或同步SPI。查询沿worker取得真实Core结果→owner准备金融候选和关联计划→worker解析原关联→owner统一写身份和回调推进。

公开三阶段接口为begin_qmt_account_identity(stage, result, binding, BaseDataMgr, budget, originalDeadline)、resolve_qmt_account_identity(unique_ptr<Plan>, TradeClient)、finish_qmt_account_identity(unique_ptr<Candidate>&, unique_ptr<Resolved>&)。Begin结果包含status与独占candidate/plan；三个句柄由模块私有构造。Candidate拥有原AccountBatch及WT对象，仅由创建它的owner保留和销毁；Plan和Resolved只含独立值，禁止含WT对象、BaseDataMgr、SPI、Candidate指针或借用输入DOM。私有共享ticket只含独立值，用于辨认同批次、原owner、原deadline.end及单次消费，不对用户引入新令牌。

Begin复用现唯一金融mapper和重复身份预检，冻结原Core结果/绑定/预算；身份冲突在任何lookup前失败。Resolve在Trade客户端原owner上沿同一截止时点做原prepare、精确lookup、来源复核与有限视图生成；初始已用预算随计划继续计费，不新增TTL或额度。Finish仅在原Candidate owner上接受同一ticket、未消费且仍在原D内的结果，统一写槽。错误线程或错配批次返回明确错误并同时保留candidate和resolved，允许原owner使用原结果继续完成；candidate始终在调用者原owner表中；不能在错误线程释放其WT对象。其他失败不给可发布数组。插件stop时可在owner先退役candidate，worker晚到的纯值Resolved独立销毁。

原map_shm_account_identity_batch保留公开签名，改为以上唯一实现的顺序包装；旧57场景、原金融views及金融数值保持。新增验收含真实跨线程resolve/owner finish、输入原文销毁后计划独立、错票据与错误线程不消耗candidate、双重消费、原D与预算跨阶段连续、stop退役candidate/迟到结果释放；SDK仍只用替身。

### STQ-P9 标准插件接线与实施状态

本段accepted的实施范围是自有StandardQmtTrader候选类：标准init/registerSpi/connect/login、四查询、WT委托/撤单入口、单worker与owner pump、有限队列及受控关闭。生产Factory切换须在候选类与固定上游TraderAdapter实际链验收后登记；当前Factory仍为旧ManagedTrader，目标是使其退出QMT生产路径。事件消费、查询/回报交接及跨进程恢复仍按STQ-P5单独验收，候选类完成不代表完整交易插件完成。

connect只安排准备，首次owner pump由宿主在原TraderAdapter.run()返回后调用；它推进Connect/Login/四查询的原生回调顺序，不增加独立start_callbacks开关。find/pump/wait/stop/inspect接缝只管理该自有插件的实例与I/O生命周期，不修改WT虚接口。插件在SPI前释放全部自有锁，允许回调重入查询；registerSpi(NULL)即时抑制后继回调，回调内stop只登记停止。工作线程关闭自身客户端并实际drain后，owner才能join与删除；首次close截止时点冻结，超时保留真实owner和DLL。

普通配置沿现有账户/环境/币种/profile/行数、Host地址/凭证环境变量、绑定、writes_enabled及有界请求/关闭/队列预算。交易日由可信WT运行配置trading_date注入并校验有效日期，禁止猜本机日期或返回0。Live来源限制沿实际原生客户端。四查询独立推进，不新增四查询原子门、production_trusted、SignedCommand或逐单审批。

下单复制WT原EntrustID/UserTag和实际委托值，worker自动生成内部命令UUID，先保留原receipt再至多一次POST；提交结果未知只按原receipt查询，禁止重发。撤单使用真实券商OrderID，通过既有原关联恢复并核对账户、标的、当前来源和broker proof；WT撤单对象无需新增UserTag字段。阻塞/失败如实返回，不能为了原Adapter计数而伪造受理。固定上游同步负返回的undone处理正在隔离复现，任何必要框架修正另提证据和批准。


已经受理的原委托若现有客户端提供明确未派发/未调用的终态，owner可在原D之后至多一次交回该原委托的onRspEntrust(error)，使WT依原接口收回其未完成数量；此为已知失败通知，不重新开放网络/SDK调用机会。原D继续约束提交、原ID查询及金融观察发布。超时、缺回复、已派发而结果不明不能被当作确定失败。回调仍受原instance/epoch、detach、stop与对象生命周期约束，禁止错误回报双投。


### STQ-P7Q 查询来源的身份恢复后继

状态：accepted实施契约，沿QST-R21Q采用显式reference.v2与Common私有已验facts。Event分支要求原source_sequence>0及原事件SHA；AccountQuery分支要求原query UUID、结果SHA及0..4095的原源行下标；None和未派发原insert继续unresolved，账户/证券/token/broker冲突仍拒绝整批。query分支没有事件时保持原sequence=0/SHA空，不用事件字段冒充查询。两类分支继续共享原lookup原文、预算、原D、P8票据/owner生命周期和唯一金融mapper，旧身份view形状及reason保持。query proof只恢复EntrustID/UserTag关联，当前可撤由原Common与Host重新核查；不新增WT框架接口、金融账本、用户标签或审批条件。

新增验收覆盖显式query无event、query与历史event并存、历史query身份解释，均核旧views、金融值、原身份槽与查询/写调用数；Host真实ORDER查询→proof持久化→原生cancel链另有对应验收，合成HTTP形状测试不替代该来源证明。


## 未知委托定向取消后继边界

[UC规格](qmt-unknown-cancel.md)及[ADR-0011](../architecture/adr/0011-unknown-order-targeted-cancel.md)按明确v2状态语义承接本规格unknown整体停写的受限取消后继。当前只接受源端/Host/原Journal实施；普通v1路径保持，Common/Standard新增审计预算和完整用户链尚未完成。新Agent/Host版本不得提前切生产；unknown原记录不改，一般恢复新下单的解除机制继续单独闭合。


## STQ-P10 正式标准插件与查询上下文（accepted，开发中）

正式可选模块名为 TraderQMTStandard，复用原 StandardFactory/StandardQmtTrader 源码并从固定上游加已批准差异构建；旧 Factory 与默认模块选择保持。自有 BrokerQueryAdapter/LocalExecuter 从同一份 order_context 配置冻结 native 或 query_first，缺省 native；query_first 同时要求 position_by_query 与 owner 单线程调度。

完整ORDER查询按已批准STQ-P12写入WT原订单表与原未成交量；首次查询继续原WT初始化推进，后续刷新原表。getOrders/getUndoneQty/cancel共用此表，余量采用券商值。持仓保持原已批准查询持仓模式。整次 buy/sell 仍调用原 WtLocalExecuter 拆单，并由现有 StandardSubmission 包装一次。API/DLL 和 owner 生命周期由宿主负责；断线撤销查询可用性，未查询时明确不可用。原事件通知与取消沿原Adapter；完整重连和取消终态组合仍分别验收。

本阶段先跑正式模块装载→原四查询→产品 Context→原 Local buy→真实 SHM 运输/SDK替身→四次 ORDER 刷新→正常关闭，并对 native/query_first 的实际提交次数分别验证。正向主路径完成后再集中异常、恢复及独立评审，不进行真实委托或生产切换。


## STQ-P11 终态后的后继持仓查询与连续提交（accepted，开发中）

本后继仅作用于 order_context=query_first。完整ORDER查询确认本组各子单已终态后，记录当前内部请求序号及已验证来源的摘要；此前排队的P不能解除本组。owner以原有界Query链安排一次后继P，成功回调原WT并返回后，只有来源相同、请求创建晚于终态观察、SDK原调用已确定返回且原Pending已退休的子单，才解除防重复提交责任。新组继续保留原WT委托身份/新原始命令UUID规则。未知原调用保留原UUID及禁重发。

事件终态先安排完整O查询，随后走同一P交付链。普通订单查询、回报、后继P都不新增金融账本；持仓数量完全采用本次券商P，不按成交计算。该序列确认当前可获得的券商持仓已交给WT，不声称跨O/P原子事务或券商缓存零延迟。来源缓存一致性及真实实盘资格另验。

调度使用原max_queue/有效载荷与每任务截止，至多一项自有终态刷新在途；SPI及I/O在管理锁之外。缺终态、查询失败、未知委托、来源变化或回调未确认均保留相应责任或关闭新写。缺省/native路径保持。主路径先验证全成与部成部撤两种终态后，WT应用券商新P并允许第二轮委托；完整取消请求、并发/恢复/异常矩阵及独立review继续按整体主路径后的顺序完成。


## STQ-P12 券商订单收敛到原生订单表（accepted，开发中）

用户2026-10-27明确批准[两文件方案](../migration/native-order-query-sync-proposal.md)。仅TraderAdapter.h/.cpp新增由order_context=query_first选择的完整订单发布，缺省/native保留原路径。完整成功批在交易owner准备候选，在原订单锁内一并替换_orders、_undone_qty及订单查询统计；成交统计及频率时间缓存保留。严格按本通道原WT标签解析localid，外部订单不伪造归属；空查询更新活动表，未知提交责任继续由原Standard保留。

自有BrokerQueryContext已移除rows_与独立数量求和，所有完整订单查询交原Adapter。原cancel/doCancel正文及ITraderApi虚接口保持；原getOrders支持在查询模式以标准证券身份读取原表。订单回报继续通知/日志并安排查询，成交回报继续原通知/成交统计/账户与持仓刷新，已查询余量不再按增量扣减。运行模式初始化冻结，query_first要求position_by_query、完整有界来源及同owner发布；全部受影响消费者须重新编译。

主路径证据见[原订单表同步](../evidence/2026-10-27-qmt-native-order-query-sync.md)。已验范围为真实Host/WinSHM、SDK替身下的订单可见、原生撤单、重复查询统计和迟到成交；取消后终态至下一轮的组合、完整生产宿主与恢复、异常矩阵及独立评审继续。真实下撤单与生产切换未启用。


## STQ-P13 策略到交易owner的执行交接（accepted，开发中）

复用WT-S06/T03的IExecCommand与WtExecuterMgr/WtCtaEngine.addExecuter公开挂接。自有OwnerExecCommand承接set_position、on_position_changed、on_tick，生产者只复制有界值，目标执行器仅由创建桥的交易owner调用。行情只复制WTSTickStruct与标准证券代码，WT对象在owner重新创建并从owner元数据解析器取得合约借用指针；队列不保存WT对象、策略对象、引擎stub或来源缓冲引用。

构造时显式指定max_commands（1..1024）、max_payload_bytes（至64MiB）、max_targets（1..4096）、max_queue_delay_ms（1..30000）。按FIFO交付，不合并目标或自行计算仓位/拆单；载荷计费包括在途项，容器管理开销另由数量上限约束。容量、输入、到期和目标回调异常锁存故障，丢弃尚未进入目标的队列，禁止自动重放已进入回调的目标；原Standard未决命令身份保持。虚回调不向WT线程抛异常，宿主检查status并停止本实例的新目标。创建失败可在初始化抛出，非法线程drain不给目标回调。

owner的drain(max_commands)在锁外调用目标；每项交付前核排队截止。它只保证交付调用返回，实际委托/成交由原Standard和券商事实确认。close停止准入并放弃未交付值，在途回调不能撤回；status的inflight=false与队列空共同确认交接已排空。宿主先停策略/行情生产者，再关闭桥并等待owner回调返回，最后销毁目标/Adapter/DLL；桥不创建线程，不替代Host的生命周期。

目标执行器的stub、元数据和data manager由交易宿主在owner事先设置并拥有，不能把CTA可变状态或其借用对象未经适用并发保证交给目标。桥自身由原Engine设置的_stub不向目标透传；正式宿主时钟/元数据接线仍需单独证明。默认/native装配保持原执行器；显式query_first装配才使用此桥，原Local的poolsize=0。本阶段首先验证原WtExecuterMgr公开入口→跨线程值队列→owner目标接口、来源对象销毁后行情值仍正确、FIFO与关闭；Standard真实运输主链及完整策略宿主继续装配，组件验证不替代最终整链。


## STQ-P14 标准执行宿主装配（accepted，开发中）

自有StandardExecutionHost组合原BrokerQueryAdapter、BrokerQueryLocalExecuter和OwnerExecCommand。原基础数据、ActionPolicyMgr、执行工厂与交易owner专用IExecuterStub由外层宿主提供，至少保留至本实例确认关闭；不将CTA可变_stub跨线程透传。实例创建线程独占初始化、pump、查询、原cancel和最终close，生产者仅持有IExecCommand/OwnerExecCommand的共享引用。

显式query_first/position_by_query、TraderQMTStandard和Local poolsize=0配置在初始化冻结。普通native装配保持原生路径，不能隐式创建此查询优先宿主。插件生命周期/提交组函数由同一已装载DLL的导出表注入，原Adapter仍沿原module装载/工厂创建；Find取得该实例，供原owner pump/inspect/delete使用。该表及DLL必须与Adapter所用模块相同并保持加载，不提供跨DLL STL对象传递。

初始化先验证本模块的模式、基本名称、原执行策略policy及有界队列参数，创建不运行的原Local/桥，再原Adapter.init→绑定Standard→setStub/addSink→原Adapter.run。返回后才开始pump，先推进插件原有界完成，再在真正ready且写未阻断时drain目标队列。读查询依旧由插件worker执行；本宿主只提供原查询入口和原数量/订单读取，不新增金融账本、定时任务、自动补单或风控审批。订单及持仓仍是原表中的券商查询观察。

request_stop只停止目标准入；原owner close先关闭桥，确认无目标回调在途，detach SPI并关闭插件，核Closed/joined/drained/worker退出，再用原导出deleteTrader确认API置空。关闭未确认时保留整棵owner和借用依赖，监督器按原进程截止处理，禁止热卸载或重建新委托。析构遇未确认关闭保留Impl至进程结束，不能销毁活跃SPI/执行对象；外层依赖仍须遵守保持至关闭/进程结束的生命周期合同。原WT核心对象的process-lifetime存储及DLL卸载行为保持。

状态分别报告宿主phase/fault、桥队列及原Standard诊断。非owner调用返回WrongOwner/false或抛明确线程错误，status返回固定WrongOwner值，保持owner状态不被跨线程修改；只有request_stop及command共享引用允许跨线程。配置/初始化/运行/回调失败关闭新目标准入，原命令身份和未知责任留原Standard。宿主不宣称执行交付等同委托/成交。主验收使用公开原WtExecuterMgr→跨线程目标/行情→实际产品宿主→原MinImpact/Adapter→Standard→真实Host/WinSHM/SDK替身，核四轮只提交一次、券商持仓/余量、查询和关闭。正式CTA时钟/元数据、策略及行情宿主整链仍按实际装配分别验收，本规格不改变既有只读RealtimeBridge的scope/空交易限制。

## STQ-P15 交易owner的原生执行环境（accepted，开发中）

自有ExecutionEnvironment实现原IExecuterStub，供StandardExecutionHost的Local使用；独立于CTA可变引擎字段。owner时钟缺省取原TimeUtils::getLocalTimeNow的epoch毫秒，使用线程安全本地时间转换取得date/HHMMSSsss；交易日直接调用原BaseDataMgr.calcTradingDate(reference_session,date,HHMM,true)，与CTA ticker启动使用同一原生接缝，不另写交易日历。所选session必须预先存在，元数据及可选HotMgr装载完成后保持，创建线程独占所有实例方法。

clock provider可显式注入epoch毫秒函数，用于同一接口的冻结时钟/运行模拟；普通实时实例缺省使用系统时钟。该选择只定义执行算法的真实时间，与策略闭合分钟和回测时钟分别命名，不改变原CTA调度或已有限定只读桥。队列截止仍使用原steady_clock，不以市场/系统时间替代请求截止。observe返回同次时钟样本的epoch/date/time/原交易日；get_real_time和get_trading_day分别取各自调用样本，不授跨调用原子时点。无效时钟/未知session/非owner明确拒绝；合约品种及session解析复用原CodeHelper/BaseDataMgr，未知品种及其时段返回空，不合成；原按交易所/品种查询成功不单独证明合约存在。

验收将现有实际产品宿主主链的手写固定HostStub替换成该产品模块，以注入冻结epoch运行原算法/Adapter/真实SHM SDK替身，并实际检查默认系统时钟、交易日委托原计算、元数据指针及非owner拒绝。正式CTA实例、实际ticker/策略调用和两端完整生命周期仍须继续验收，本要求不以该环境模块证明正式CTA入口已完成。

元数据入口接纳原定长容量内、各段非空的2/3段标准代码，3段复权尾标之前须有实际代码；格式未知/超长先返回空，避免把未成形的外部名称交原解析器。更复杂的期权等来源需显式扩展该准入并分别验收。

## STQ-P16 原生CTA与执行宿主装配（accepted，开发中）

自有CtaExecutionSession通过公开接口组合原WtCtaEngine、WtDtMgr、ParserAdapterMgr和CtaStraContext，并挂接已初始化的StandardExecutionHost.command。原策略通过标准ICtaStrategyFact创建/删除；Session独占交付策略，factory、基础数据、HotMgr及执行宿主借用至确认关闭/进程结束。显式创建该Session才使用新装配，不改变WtRunner/RealtimeBridge的受管空交易限制或普通配置默认行为。编译仅固定上游加已批准NCS/查询权威覆盖，WT核心新增修改0。

首个装配支持CTA poolsize=0、单策略、1..16个有stop/delete导出的原Parser、具stop/delete的原Reader，不启独立risk/notifier。原引擎拥有理论部位、目标汇总、过滤、ticker和后台任务，原上下文拥有策略KV；真实持仓及订单仍归已查询Adapter。策略init/on_init/on_bar/on_schedule均由原上下文/ticker驱动，禁止直接手调schedule。输出根由进程宿主在首次原WT插件初始化前独占新建并setGenerateDir；原目录getter有进程缓存，Session核同一目录身份及尚无CTA状态，不在后续切换生成根。进程只装一个Session；旧理论状态导入、持续行情并发资格及多策略扩展分别验收。

创建控制线程独占initialize/start/pump/status/close；request_stop仅发布原子请求并关闭执行桥新准入。initialize先校配置与来源能力，再原engine/data/parser/context装配；start先原engine.run后原parser.run。pump观察原engine.task_failure；失败沿原任务异常身份关闭执行准入、由owner停止且不重放。其余推进原Standard，事件诊断来自原IEngineEvtListener的原子计数，不跨线程读引擎时间/策略变量。

close先关交易准入并请求ticker停止，原Parser停止并确认后join原ticker/pool/tasks；再原Reader停止、原工厂删除策略、释放contexts、Parser/Reader实例，最后关闭Standard执行宿主。Parser/Reader pending保留完整Impl，策略删除异常/不确认不重试删除并保留进程责任。busy回调中close只返回pending，最终由控制线程执行；错误不重放。原engine.stop可能等待正在运行回调，严格进程截止归外层Job，不把局部timeout宣称为整个关闭时限。

主验收经原Factory策略/Context→原ticker闭合→原目标汇总/执行桥→原MinImpact/Adapter→真实Host/WinSHM SDK替身；核同一目标重复调度不重复提交、券商P/O观察、正常停止及最后回调先于删除。Parser/Reader可用测试专用确定性provider，必须明确来源与Clock，不授真实市场或唯一业务核资格。真实来源、同核业务策略、连续行情、多轮/恢复与独立安装继续独立完成。

原CTA的sub_tick始终借用HotMgr（现金股票也如此），Session接口要求非空IHotMgr引用；没有切换规则的现金场景仍提供原WTSHotMgr空规则实例。执行环境自身的可选HotMgr与CTA装配的必需HotMgr分别遵循原调用职责。

产品库由GH_STANDARD_CTA显式构建，缺省关闭；GH_STANDARD_CTA_MAIN另启隔离主链驱动及确定性插件，并在同一固定输入中编译原算法工厂。安装头消费包含可选Session，测试运输代理有限额度独立于8次业务查询预算。

Session在engine.init前统一预检公共配置：environment/data/product/store/riskmon须符合对象类型；name/session/module/id须为指定字符串，poolsize缺省0或整数0；riskmon.active、Parser.active/check_time及data.align_by_section缺省false或Boolean。所有Parser先核类型和活动id唯一性，至少一个活动Parser。初始化依赖执行宿主须Ready且未请求停止；插件私有参数仍由对应插件验证。错误配置按Configuration拒绝并由统一close收口，不调用原Boolean处理容器值。

原JSON加载器省略null字段，因此可选Boolean的JSON null沿缺省false；Session无法区分已被省略的null和缺省。Parser.active为空时按未活动处理，全数组无活动Parser仍拒绝。当前装配要求带类型的WTSVariant配置；原YAML加载器把标量转成字符串，未取得本装配资格。

## STQ-P17 同账户多策略固定集合（accepted，开发中）

2026-10-28用户将同账户多策略的设计核实和自有适配交由本对话推进。[专项方案](../migration/multi-strategy-account-ownership.md)保存评估及尚待确认的人工混用/恢复语义；本节限定已授权的原生多策略装配。

CtaExecutionSession接受1..64项CtaExecutionStrategy固定集合，每项包含独立strategy、factory和可空Object参数。构造检查非空/重复指针、唯一有效策略ID及参数类型；ID使用ASCII字母、数字、点、下划线或横线，小于64字节，排除末尾点及Windows设备名，按大小写无关的文件名检查唯一性。保存已校验原ID，全部策略init结束后核身份保持，再按冻结ID创建上下文。成功构造后统一独占策略，构造抛异常时全部由调用方保留。factory/参数按原借用期限保存，配置由调用方保持存活且不改写。保留原单策略构造及initialize参数入口，该initialize只适用于单项集合；集合入口逐项使用构造参数。集合运行期间固定，策略退场由该策略先提交零目标，配置热删未提供。

全部上下文进入同一个原WtCtaEngine与同一个StandardExecutionHost.command；原on_init/on_schedule/WtExecuterMgr完成求和，适配层不建立第二套持仓或目标汇总。首轮保持poolsize=0；同进程并存第二个Session在接管其策略前拒绝。pending关闭保留占用，确认完整close后释放占用；该机制不提供跨进程账户锁。

关闭在全部原生产者停止后逐项调用各自factory.deleteStrategy，每个策略最多尝试一次；某项false/throw保留整个依赖树，成功删除项不重复删除。全部删除后沿P16关闭上下文、Reader/Parser及执行宿主。原默认native入口、查询权威和未知命令责任保持。

验收覆盖：A600+B400产生账户目标1000；账户1000时A归零仅卖600并保B400；A增加200/B减少200无额外委托；本通道活动买单抵扣未完成差额；参数独立、原JSON按ID隔离、配置拒绝与原单策略路径。已有状态根继续按P16拒绝；跨进程恢复、人工同标的混用、真实交易及生产发布分别待验，不从本集合装配推定资格。

## STQ-P18 输出根单写者与两代停止边界（accepted，开发中）

Session在同一原输出根身份校验后、检查已有CTA状态及初始化行情/引擎前，取得该根`.cta-session.lock`的Windows独占文件句柄。争用按OutputBusy拒绝；OS错误保留为配置/关闭失败。锁只覆盖输出根的单写者，不替代跨根账户执行唯一性。文件仅为进程租约，无持仓、委托或恢复事实。普通native入口保持原路径。

该句柄保持至完整close；Parser/Reader在途、策略删除失败及执行宿主pending均保留租约和原依赖树。完整close确认后释放；初始化拒绝同样沿close释放。进程退出由OS回收租约，文件存在本身不代表占用；后继仍按原已有CTA状态检查拒绝自动重启，保留全部原JSON及未决身份，等待完整恢复语义。

验收：实际跨进程输出根争用在行情DLL装载前拒绝且零委托；正常关闭释放、pending保留；第一原生进程产生两策略原状态并退出后，第二原生进程以同一根启动仍明确拒绝，原文件哈希及券商查询事实保持；两代新输出根可沿相同单策略/多策略主链运行。另验原Parser/Reader延迟停止及在途策略调度时，停止准入→回调返回/原join→策略删除的顺序。严格总体截止仍归外层Job。

## STQ-P19 受管多策略产品宿主与干净停止恢复（accepted，开发中）

后继任务沿用户授权交接本对话：独立安装可运行exe、原执行工厂及显式策略/Parser/Reader装配，固定1..64个策略，共用原Session和唯一账户执行owner；普通native及原空根入口继续保持。产品配置、运行状态和停止收据具有限容量、版本和实例身份，凭证沿原环境契约，监督复用ManagedLocalProcess/ProcessJob隐藏启动和原绝对关闭截止。新目标归策略、汇总与绩效归原上下文/组合、账户事实归原Adapter；新增金融账本0。

产品配置在自有StandardExecutionHost边界核公共字段类型后才进入原Adapter/Local：交易模块/模式/实例为字符串，查询持仓为显式true，布尔开关、poolsize=整数0、有限scale、clear字符串列表、groups对象/有限数量和policy标量按原消费类型准入。原执行算法继续拥有参数业务语义。非负pump计数遇原宿主故障同样停止Session并报告Execution故障。

安装清单绑定exe、全部实际DLL与显式基础资料/策略/Parser/Reader摘要；加载配置和创建进程前均有限遍历核库集合、拒绝新增未登记库及重解析路径。安装目录在本代加载/运行期间冻结，更新通过停机后新安装代际交接。每条输出管道保留上限256KiB，超额沿原监督器停止并排空，原始字节留私有内存。

新增恢复入口只消费上一代完整干净停止授予的同根原生文件：冻结新副作用、停止并join生产者、原查询/事件及提交责任交接完成、全部活动订单为空且全实例未知/未决提交为零。原生策略/用户JSON及组合文件按原save/load保存恢复；自有元数据只保存配置和文件身份及干净关闭标记。运行前消费标记；崩溃、未确认关闭、配置/文件身份不符均保留原件并拒绝执行。空订单查询独自不授恢复资格，未知责任沿原Host/Journal和命令身份核查。

验收以安装目录运行原引擎/ticker/策略集合→唯一owner→原算法/Adapter→真实WinSHM SDK替身链；同状态根两代恢复A/B持仓、用户KV及组合目标，第二代账户已满足时额外委托0。覆盖未决命令、活动单、缺失/损坏/变更状态、同根/同账户争用、关闭pending及截止回收；真实下撤单、生产切换和人工混用保持独立授权及待验。

产品委托结果分项验收：STQ-P19-O1完整查询先见已成交1000，先到400股成交回报、随后到另600股及其重复回报，原账户观察保持1000；原策略下一次主K线把合计目标改为1200时只新增买200。STQ-P19-O2原买1000部分成交500，原MinImpact到期撤掉余500并只补买500，补单成交后再到原单迟到100股及重复回报，后继目标1200仍只新增买200。查询和事件须来自真实运输，撤单沿原执行器及Adapter，逐笔核命令身份、SDK替身次数、源端事件确认、原策略/组合状态与完整关闭。测试使用持续递增tick时间及原分钟闭合，不能手调策略schedule或原执行器撤单伪造产品入口。全撤、撤单拒绝/未知、其他异常及跨进程恢复继续独立验收，O1/O2通过不代表完整P19或模块B完成。

正式产品结果链的后继验收：P19-O3首买1000全撤后以新命令补买1000；O4首单废单57后补买1000；O5撤单SDK返回false时保留原活动订单，原单随后全成，禁止把调用返回认作已撤或另买500。三案均在券商查询达到1000后重放已有TradeID，再由下一次原调度将A600/B400变为A800/B400，仅补买200。源端独立记录SDK实际进入、订单/成交事实及原Journal回执，反复回报保持原去重。B03五组合和未知SDK提交以正式安装exe分别验收，正常关闭、原责任保留及进程/Host/源回收须有原件。实现和资格以实际输入身份登记，本项不授权真实下撤单。

## STQ-P20 唯一原生产品运行实现与同核回调接缝（accepted，开发中）

按模块B完整任务将已验产品运行体收敛为`GuanhengCtaRuntime.dll`；exe仅调用同一C ABI运行体。受管Python子进程通过ctypes加载同一安装的运行体，先配置标准策略Factory回调，再在原创建线程调用运行函数，连接已有唯一Python业务核。保持独立进程、原Session/Host/Factory/ticker、原停止文件及Job截止；不新增嵌入式Python、账户状态或执行循环。原synthetic NRT入口在其原规格范围内保留。

运行ABI版本1：`gh_cta_runtime_abi_version()`返回1；`gh_cta_run(argc,argv,health,user)`同步占用调用线程，argv为原exe完整9项宽字符参数，health可空、user仅原样交给health。同一运行DLL每进程至多调用一次运行入口，防止原WT全局目录及工厂缓存跨代重用。入口捕获C++异常并返回非零，跨ABI不传C++对象。callback/argv/user由调用者保持至返回或进程退出，禁止运行中卸载DLL。

health在同一owner的启动阶段及每次pump前有界调用，0表示业务回调接缝健康；非零沿原失败/关闭流程停止新目标准入，发布失败收据，不授成功ready/恢复资格。health自身只读有限原子状态，不调度算法、不读取账户、不发交易、不抛异常或阻塞。默认exe传空health，运行体仍沿原配置和原逻辑。

完整close确认join后、发布终态前再次读取health；停止期间在途回调发生失败时，终态`ok=false`、`error_code=strategy_callback`且返回非零。停止请求与在途回调失败分别保留，成功停止收据只覆盖回调最终健康的运行。

验收先保持安装exe五组合及停止语义，再用安装DLL/ctypes同一Factory回调驱动真实configured核，核原输入下BT/RT目标一致及完整隔离交易链。ABI空指针/参数数量/重复进入/故障健康检查、模块身份、回调保活、异常和原总截止分别验证。实现、合成主链、真实只读来源及生产资格分别登记，P19冻结003证据保留其原源码身份。

## STQ-P21 原保存加载的产品正常恢复（accepted，开发中）

沿B-05/P19的正常停止恢复要求，在自有Session、Standard与产品运行体衔接。复用原WT engine/context load、原Host/Journal及提交组责任；新增WT核心行为0、金融账本0。[原加载实测](../evidence/2026-10-29-configured-bt-and-native-load.md)已确认停止样本的持久内容可加载。当前自有已有根拒绝和停止交易后无法继续查询是产品接线缺口，新增能力限于此处。

配置可选`recovery:{"mode":"record_clean"}`或`resume_clean`，缺省保持fresh原路径。record_clean要求原空根；resume_clean只接受同根上一代完整clean元数据。配置身份取删除recovery字段后的同一JSON，其余账户、输出根、策略参数、安装路径及交易配置均相同；当前限定savedata=false的query_first显式配置。清单包含策略JSON、可选原用户KV与组合JSON的完整集合/摘要，绑定全部实际安装文件摘要。生命周期元数据不复制金融字段。恢复模式改变仅消耗相同业务配置的停止证明。

Session输出根独占租约内执行准入钩子：核配置/安装/原生文件集合，原子消费clean标记，随后才进入原engine.init及策略init；失败保留金融原件。停止时先关闭目标桥、停止并join Parser/ticker/tasks/Reader，原交易owner继续处理既有查询/事件和提交责任；单调关闭截止沿原Job。交易插件另有单向的新提交准入关闭，查询和原命令核查保持可用。原生状态继续由既有业务事件保存，停止阶段不增加显式save。

Standard新增独立版本1观察结构与C导出，不改既有Diagnostics/Submission结构布局：查询优先模式、新提交关闭标记、活动组、全实例未决子责任、原通信pending、未知/错误，以及最后完整O/P的任务序号和全账户活动订单数。每次普通查询已交付原SPI并返回后才更新观察；该观察不保存或推算账户数量，不主动清除原责任。写准入关闭后再次查询O，再取得晚于O的P；全实例责任为零且O活动单为零，才可准备clean关闭。旧未决SDK结果继续沿原ID核查。

Session.close在根租约释放前核原最终健康与责任并准备恢复材料。最终证明由STQ-P24的父进程两阶段关闭合同统一规定，须绑定实际正常退出和资源回收；子进程准备完成尚不授clean。中途崩溃、未确认关闭、未知/活动责任、文件或配置变化均不授clean，下一次保留原件拒绝resume。pending关闭仍保留依赖树与根租约。clean/consumed及prepared文件均为生命周期证明，原金融文件与Host/Journal不删除、不换空根。有限failure.json只保留阶段、错误枚举和原因摘要供私有诊断，不复制源正文。

验收ID：P21-C1正式安装同根两代A/B持仓/用户KV/组合恢复、券商满足目标时新增委托0；C2活动单/未决或未知阻断clean；C3状态/配置/安装摘要及集合变化拒绝并保留文件；C4生产者pending/回调失败/父截止不授clean、根及账户争用保持；C5缺省fresh五组合/原R11兼容。独立审查绑定最终源码、安装与原件。R11纯决策状态还须经原用户KV接口桥接，其准入与验收另记，当前PythonExecutionProcessConfig明确拒绝恢复模式；C1原生固定策略通过不代表全部业务版本恢复完成。

## STQ-P22 首账户查询与延后创建的股票执行单元（accepted，开发中）

复用WT-T01/T03/T10的原账户回调和股票执行算法。自有query_first宿主先完成四查询，再按首次策略目标创建原执行单元；原Local账户回调只转发给当时已有单元。自有BrokerQueryAdapter复制最近一次完整查询中的原CNY账户回调值，BrokerQueryLocalExecuter在目标/增量调用可能创建单元之后重放该回调，使首个tick沿原股票算法的可用资金和整手规则执行。普通native上下文保持原路径。

该观察只由完整账户查询更新，空结果或缺CNY以及断线清除已知标记；不扣减资金、不累计成交、不按策略分配余额。query_first买入在提交组创建前核最近CNY账户事实已知、available正数且委托名义金额不超过该观察；未知、零或不足返回空OrderIDs及新增末尾枚举BlockedFunds=9，不创建提交组/命令或进入SDK。原SubmissionViewV1布局和既有枚举数值保持。卖出继续由原总量/可卖量及股票算法处理。实际券商对时点、共享资金冻结、费用及最终受理仍为事实来源，单次名义金额检查不授跨证券资金预留资格。

P22-C1：原账户查询先于单元创建，available=1000、价10.01、目标1000份时零SDK；原账户再查询available=2500后，同一目标由原股票算法只买200份。P22-C2：available=0或有限负值按原观察保留、零SDK，后续有效账户回调恢复交易；足额股票正例首笔200；原通用执行器名义资金不足零SDK、后续20000元同目标买1000份。原账户mapper要求资金来源恰一行，空源沿既有合同失败且SDK0；该例验证明确失败和关闭，不能声称同实例Ready恢复。四查询先后和真实WinSHM/原Host/插件路径分别留证。P22-C3：P1000/可卖200仅卖200、可卖0不提交、正常关闭及真实资源回收；既有query_first完整主链与native路径兼容。P22-C4：同批自有库/运行体/安装头及独立审查，原WT源码和对象保持。唯一1.1.2策略/首次接管及完整CTA股票执行资格沿对应主线验收。

## STQ-P23 唯一策略首次存量持仓接管（accepted，开发中）

复用WT-S05/S06和WT-T01的原策略/组合加载及券商查询。显式takeover配置绑定独立输入文件和SHA，搭配record_clean首次运行；resume_clean保留同一配置身份并沿原clean证明加载，不再写接管初值。自有Session取得根租约、确认fresh金融目录为空、原admit成功后才执行一次prepare，再进入原engine/context初始化。中途写失败保留原件，重启不能复用fresh覆盖。

首版输入guanheng.cta-takeover.v1限定唯一resonance-regime-v1@1.1.2，1..8证券，实际数量/可卖、当前接管标记价、实际周期ID/开仓本地分钟、交易日、来源摘要及同一Windows启动时钟捕获/有效截止。代码先沿ExecutionEnvironment既有容量/2或3段准入，再进入原CodeHelper及合约查询；输入交易日须等于同次原环境观察，周期开始不晚于该观察的本地分钟。原交易owner枚举原Adapter全部非零持仓，逐证券核数量/可卖及无空头/额外证券；额外零量条目忽略，原恢复观察核无活动单、未知命令或未决组。held须有周期初值，零仓无周期。可卖约束继续由原Adapter/执行器负责。

迁移起算选项显式takeover-mark：原策略和组合以同一标记价/数量作为新绩效基准，历史累计损益/费用为0；券商平均成本独立保留来源，不伪称为该新基准。原明细开仓时间记录已证明的当前周期时间；原用户变量保留周期来源和退出状态的ASCII输入。新增元数据只记录接管身份及原生初值，后续金融状态由原WT维护，不导入历史成交，不另建持仓/成本账。真实起算价格、周期来源和策略预算仍须沿[接管候选](../migration/retained-strategy-takeover-proposal.md)核准，本开发输入不授真实切换资格。

P23-C1：非空券商1000份经正式Runtime/原Factory加载，INIT读回策略/组合1000、实际开仓时间/用户变量，首个保持目标零新增委托；下一目标减少200时只卖200。P23-C2：同根clean两代保留持仓/周期/KV，第二代零重复买入且不重写首次接管材料。P23-C3：数量/可卖/额外持仓不符、过期/错身份/缺周期、原金融目录非空和未知责任拒绝；失败不改既有金融文件且SDK0。P23-C4：同批库/运行DLL/公开头、安装后完整关闭及独立审查。C唯一数学核、真实复权来源和实时周期持续更新分别沿RR112继续。

## STQ-P24 自有宿主完整关闭与恢复证明（accepted，开发中）

原股票执行单元在最终析构时异常，暴露自有StandardExecutionHost.close只关闭插件、原Local及单元留到宿主析构的窗口。关闭完成必须包含自有宿主拥有的原Local/全部执行单元和Adapter的销毁；BaseDataMgr、执行工厂及原报价依赖在此期间保持有效。原交易worker停止、SPI撤销及join/drain确认后，在owner关闭路径销毁Local与Adapter，随后进入Closed。关闭的command仍拒绝新调用，调用者保留的只读队列状态沿原合同可用。

P21干净恢复使用两阶段关闭证明。子进程在原责任核清及Session关闭后仅写`.cta-clean.prepared.json`和控制目录`close-prepared.json`，两者均不授恢复资格。监督父进程确认正常stop、退出码0、整个Job归零、两条管道EOF、reader线程join及句柄回收后，发布最终事实证明：原准备材料改名为`.cta-clean.json`，控制目录写`guanheng.execution.closed.v2`，含`exit_code=0`和`resources_closed=true`。原金融文件及WT保存内容保持。

停止调用是否及时返回、子进程是否实际正常退出、恢复证明是否完整分别判断。父进程准备证明前必须在原停止截止内核实退出及资源事实，每项文件I/O前后均检查当时最早截止；越过截止停止后续动作并报告停止确认失败。最后一次I/O晚返回时，已经完整发布的证明仍描述真实的正常退出和资源回收，后续可据此核查恢复；它不承诺`close()`按时返回true。完整证明一旦可见不再撤回，避免读者已消费后的反向状态变化。只有clean或只有关闭材料时仍拒绝恢复。该规则不延长原交易、等待、重试或停止预算。

恢复须同时核`guanheng.cta-clean.v2`及其绑定的父进程最终closed.v2、PID/control/config和文件摘要。残留prepared文件、仅有子进程准备材料、旧v1证明、异常退出或未知关闭均拒绝恢复，原件保持。新Runtime与父进程适配同批安装；混装缺少新协议材料时失败关闭。正常停止确认已完成后父进程自身异常不改变已核实的子进程退出事实。监督者在两个文件发布之间失败时，缺少完整证明组合仍拒绝恢复；不通过空目录绕过。

单元或后继依赖析构异常、进程提前退出均保留原金融文件与原命令身份，父进程不发布成功closed及clean证明。该边界覆盖Session.close之后、run函数局部对象析构和Python子进程退出期间的失败。WT执行单元自身缺陷和自有关闭边界分别处理，新增框架修改继续先取得批准。

P24-C1：原股票完整目标/卖出/后继收敛进入关闭，原单元或依赖析构异常时仅可残留prepared材料，无父进程成功closed或最终clean；实际进程/管道与Host/源全部回收。C2：同一原金融状态在缺证明、prepared残留或旧v1证明时拒绝恢复，零新SDK且金融文件不变。C3：原无故障执行单元完整关闭、同根两代及关闭后重复close/status/recovery观察保持；独立审查核对无回调/inflight后才销毁消费者，公开C ABI保持。

## STQ-P25 整套重启后的事件认证续接（proposed，隔离验证中）

同一Source业务会话、同一Host通信Journal及同一原生金融根，在整套WT正常停止后重启。沿[ADR-0017](../architecture/adr/0017-trade-authentication-continuity.md)保留首代原事件及流收据的创世binding，新认证连接通过原附属关系接续。同根恢复继续核订单、未知和关闭证明；原WT保存、加载、持仓与绩效保持。实际故障与原生值重放见[定位证据](../evidence/2026-10-30-native-event-auth-recovery.md)。

候选合同只适用于Host已经显式选择`qmt.trade-auth-continuity.v1`的产品。其事件页使用`qmt.persisted-trade-events.v2`，保留原receipt/events，并在同一原Journal读取事务中提供`continuity`：沿用`qmt.trade-source-continuity.v1`字段session_id、binding_id、current_host_binding_sha256、origin_host_binding_sha256、authenticated。原存储校验当前精确认证关系后，证明绑定本次请求source及原receipt。该证明属于Host认证通信事实；纯Native页校验自身不认证Host。默认单连接保持v1页及原精确hash校验。

Native消费v2时同时核完整字段集、证明schema、业务session/binding、本次请求binding摘要、原receipt摘要及authenticated=true；原receipt前沿、事件顺序/账户/大小、原总截止、原HTTP/HMAC身份和后继身份解析继续适用。原事件正文与收据不改写，不授旧命令重新提交或清除unknown。页额度先计入证明元数据；空间不足沿原容量错误返回。公共生产者和Common消费者须同一候选交付；当前生产路径仍按各自已交付版本运行。

P25-C1：封存原失败的完整七组件同Source/Journal/金融根两代，首代唯一SDK替身调用，二代原策略/账户/NAP实际可读、SDK零增量并完整正常关闭。C2：原v1默认准入与拒绝保持；v2错当前/创世hash、错session/binding、authenticated=false、缺/多字段、前沿和原截止异常均拒绝且输出保持。C3：Journal原命令、原事件及历史来源证明保持；同原认证连接的新增后缀正确消费，unknown仍按原身份阻断。C4：同批安装及搬迁、实际文件SHA、完整进程/Job/线程/管道回收与独立审查；公共owner合入前只授隔离副本资格。

C3的[整套后继证据](../evidence/2026-10-30-native-event-suffix-unknown.md)覆盖同Source业务service下，第二认证连接新增后缀、当前Native实际消费及后继数量观察，以及SDK进入后真正unknown在整个WT/Host重启中的身份保留和拒绝。Source进程冷重开、unknown解除及C4普通发行资格继续分别验证。

## STQ-P26 原命令查询沿原绝对截止（accepted）

原 `run_write` 对一次已提交的命令只查询同一收据/原 ID，持续到原绝对 `task.deadline`、明确停止或已验证终态。明确停止包含整个worker停止，以及P21恢复停机关闭写准入；后者只终止写任务的继续轮询，账户查询仍可执行。已发送且尚无确定结果的原命令保留未知责任。原 10ms 有界等待、HTTP 每跳截止、权限、Journal、未知保留及禁止重 POST 的责任保持。正常运行时查询轮数不额外缩短业务截止；HTTP 快速返回 queued/dispatching/unknown 时仍沿同一原 ID 获取结果。

P26-C1：普通 Native DLL 经标准 Factory/SPI 和真实 HTTP/HMAC，唯一 POST 后至少 65 次 GET 仍为同 ID queued，原 D 尚余；随后在原 D 内收到 SDKReturned，原成功回调仅一次。原实现的第 64 次查询后提前 SubmissionUnknown 红例单独封存。P26-C2：一直 queued 到原 D 的请求保留同 ID、产生未知并正常关闭；原停止、默认下单/明确拒绝及未知不重发路径按影响回归。P26-C3：同批自有 Native 制品、普通执行组件安装、原 WT 源码身份和受影响完整主链分别绑定；该短例不反推历史整包失败的根因或授生产资格。

## STQ-P27 单 worker 按原绝对截止选择待执行任务（accepted，隔离开发中）

当前完整分单链的原生标量计时发现：事件身份解析本身约32ms，但排队约5.3秒；原截止更晚的八项普通任务先执行约4秒。事件页及Query→Resolve连续步骤继承原绝对截止，FIFO队尾会让后继阶段等待较晚截止的任务。自有Standard修正此调度边界；WT行情、策略线程、原账户账本与金融归约保持原实现。

唯一worker在取得原completion槽及原mutex后，从已排队任务中取绝对deadline最早者；相同deadline保持原入队顺序。已执行任务继续沿原截止完成，不中断或迁移；新任务的ID/generation、原HTTP/命令/receipt、收费、TaskCredit、容量、结果Ring、SPI交付及停止/unknown责任保持。Prepare、Login、普通Query、Resolve、Insert、Cancel、AuditOriginal及事件任务共用同一选择逻辑，不新增线程、任务副本、重试、金融事实或延长截止。单owner顺序调用按同一request_ms生成递增截止，其写任务顺序保持。独立重叠调用按各自在enqueue前取得的原截止排序；相同截止按实际入队顺序。业务依赖仍以前一阶段已完成的来源事实、原receipt及券商proof为准：Prepare成功后Login，Query原结果后同ID/D解析，Insert原关联与派发证明后才准入Cancel，Audit只核原责任，不重发原金融命令。Task ID继续表达准入身份及原查询barrier，不代表SDK完成时序。

SEV-R13-C/D及SEV-R5d-C C03/C09中针对任务取出顺序的FIFO描述统一沿本项；入队、结果Ring、名额、cadence、原D与普通任务进展要求保持。P27-C1的手工队列仅证明选择函数，实际并发入站与依赖链继续由P27-C2/C3实际运行验证。

P27-C1：可重现较早截止的事件/Resolve排在较晚普通任务之后的旧选择红例；新实现先取较早截止，等截止稳定，全部任务身份/原截止/载荷/收费保持，混合任务均单次取出。P27-C2：同一Native006冻结源/库的隔离候选完成完整52分单、实际目标、104事件/52成交观察、正常关闭及同根恢复零重复；原300秒运行、30秒单笔/事件页、10秒停止分别核实，失败继续保留。P27-C3：原事件重试/名额/cadence、普通四查询、部分成交/unknown/停止及受影响安装消费按实际输入回归；独立两轴审查绑定最终源、库和运行证据。live源码/正式制品合入及统一发行由集成owner完成，当前仅在冻结副本实施。

### P27查询优先回报的后继查询容量

同次Native030证实该调度候选在成交SPI中出现`position refresh rejected`：16项名额全部占用，等待任务15项。查询优先Adapter的订单回报同步请求O/P，成交回报同步请求A/O/P；事件续段提速须同时保证这段既有调用链的准入。该发现属于自有插件调度和容量职责，原Adapter及WT行为继续复用。

query_first事件的每条PageReady续段在任何身份查询/解析I/O前，一次预留三份普通查询名额和三份既有ordinary_advance字节银行，另取得本续段自身名额及512字节。预留计入原outstanding和payload_bytes，全部任务继续受同一max_queue/max_queue_bytes约束。空间不足时保持原PageReady和原绝对截止，先消费已有任务；到期仍沿原超时保护。新模式max_queue须至少4，容量配置不足在启动前拒绝。

字节配置先核原静态常驻（含原audit-source的4224字节）、事件分区、context及四份ordinary_advance银行；取得实际context后，再核同一常驻账单、实际chain、三份回调银行、原一份普通推进银行、query_extra、minimum_identity_work和512字节的完整最小可推进额度。audit-source的真实收费与最小账单使用同一常量。缺额在安装该context时拒绝，不进入空队列永久等待。新页的准入沿相同续段银行，已有动态任务占用导致的暂时不足仍等待原任务退役。query_first=false保持原容量准入。

预留仅由当前事件SPI在owner线程中的Query入队消费，其他线程、普通查询回调和外部请求继续按剩余容量准入。Query成功入队时，将一份预留转成该真实任务的原收费及原身份，归还保守字节差额；入队分配失败时预留保持，由原异常/unknown边界处理。重复事件或回调返回后未使用的预留随原事件前沿推进归还；异常、解绑和停止仍持有未退役责任，最终join/drain后按原关闭清理。预留属于通信资源，无额外账户账本、委托或查询副本。

P27-C4：原满额回报拒绝的定向红例；不足时续段等待、恰额准入、原三查询全部成功及原截止保持；并发外部查询不能消费该预留，未用部分归还，停止/异常完整回收。最终仍须通过C2完整分单与同根恢复，定向容量通过只授其覆盖范围。

## STQ-P28 未知写任务的恢复停机（accepted，开发中）

最终inventorysession.2的SDK替身实际进入后保留unknown，恢复停机先完成策略侧quiesce并关闭新写准入，再排入原订单查询。自有Standard写任务仍按原30秒业务截止轮询同一命令，其单一worker尚未返回；排队的恢复查询无法推进，原停机截止约8秒先耗尽。诊断限自有宿主阶段和原HTTP身份，WT框架行为保持。

明确恢复停止时，沿已有submissions_closed原子状态唤醒并结束正在等待的写轮询。未发送的请求继续使用原已知未调用分支；已发出的原收据、未决/unknown及原命令身份完整保留，不能因停止变成失败未调用或被删除。正常运行的queued/dispatching/unknown查询仍沿原D；恢复查询和停止后的责任核查继续沿原owner及原队列。全局worker_stop继续承担完整最终停止，不增加金融账本、命令、任务队列或WT行为。

P28-C1：固定失败反馈环使用唯一1.1.2、正式WRI/Factory/CTA/股票执行器/Standard/WinSHM与SDK替身。首代SDK只进入1次，真实原Journal保存unknown；在原停机截止内原生与组件结束，失败关闭保持无clean，pending/forced均false。各关闭/失败/PID及物理资源事实分别核验。

P28-C2：首代停止后，原Host/Journal/原生金融根保持，沿resume_clean启动第二代；原CTA在策略前拒绝缺clean，增加原初始四查询、SDK和交易POST均零增量，原command/body/result摘要、unknown及全部金融文件保持。Host/Source冷重开与未知解除仍按R27各自资格验收。

P28-C3：未请求停止时继续通过原至少65轮原ID查询后在原D内成功的P26正例；停止前SDK未进入、已进入但未决、已返回终态和普通查询行为按受影响边界回归。保持原字节/槽位收费、截止、一次POST及默认分流；普通已知卖买/清仓双代与搬迁安装按最终源验收。

P28-C4：最终普通无诊断Native、完整来源/同批安装、精确源码与包摘要、独立审查及恢复原件交付。诊断版只存独占build，退出交付候选；真实下撤单和生产切换保持原授权要求。

## STQ-P29 查询优先回报的待执行查询合并（accepted实施范围，隔离开发中）

同源回报同步请求O/P和A/O/P，多个证券连续成交时，同datatype查询在唯一worker队列内重复堆积。自有Standard在既有query_first模式中合并owner SPI回调发出的、尚未开始的同datatype普通Query。仅复用仍在原tasks队列内、原deadline不晚于本次请求的任务；保留原ID、最早截止、原收费和原调用，成功返回仍代表异步查询准入。worker已取出的Query、Resolve、事件查询、普通外部调用及所有写/审计任务保持独立，默认native模式保持。队列查找和worker取出由同一mutex保护，合并不消费事件预留槽；回调结束沿原归还规则释放未使用预留。

终态后自有持仓补查可以复用同一队列中ID严格大于全部待协调终态barrier的P任务；其原D须不晚于本次D。已有P已开始时继续建立新的后继P。完整O及P仍沿原身份解析、SPI应用和barrier退休，不以成交量推算账户仓位，不跳过当前事实，不合并或重发金融命令。普通外部四查询及恢复查询仍各自取得新任务身份。本项只调整自有通信查询的重复准入，不增加WT行为或金融账本。

P29-C1：原多证券连续全成回调实链中，识别同datatype待执行查询重复积压；新实现复用待执行任务，已开始查询不被复用、外部查询不合并、原ID/D/名额及字节保持。回调预留在合并、实际入队、停止和异常后完整结算。

P29-C2：同一原目标50400份、1000份分单和100ms来源节奏的实际执行主链，核券商持仓、全部SDK调用及WT成交映射。完整功能按[NRT-R31-C5](native-realtime-strategy.md#nrt-r31-实时执行阶段按券商实际数量确认)的QA每轮240秒、主1200秒/外1500秒及显式运行寿命配置验三轮、停止与同根恢复；单请求、排队、SDK、计算、新鲜度及关闭截止保持。原70秒及600秒场景保留原输入、失败和性能观察资格，70秒性能仍未通过；有限计时和单轮到位不替代完整主链。

P29-C3：普通/搬迁发行、正常及未知关闭、未决/部成/迟到回报和两处prePOST停止窗口按受影响范围回归；最终候选去除诊断计时，绑定同批库/源/制品及独立审查。完整安装和模块资格继续按真实结果登记。

## STQ-P30 停止期间事件读取完成值的统一退休

状态：accepted / in-progress。自有Standard原事件读取将ControlStoppedBeforeStage明确表示为正常生命周期停止，原网络/协议失败为Failure。当前普通停止退休只保存Failure，最终join后退休却把所有非Ok状态都计为错误；同一个正常停止结果晚到最终退休时，会使first_error及恢复unsafe变化。实际P29实现的六项状态反馈环已确定复现这一分类差异；portable001关闭现场的具体检查仍待同次诊断，两个结论分别保留。

自有Standard以唯一分类逻辑处理停止中的EventPage完成值，普通退休和worker已join后的最终退休共用。ControlStoppedBeforeStage不新增失败；真实Failure按原首因规则保留。原HardFault、unknown、入站/owner错误、事件票据、写/Audit责任、命令身份及生命周期均保持，停止后继续完成真实值析构和原资源归还。原WT、原绝对D、事件与SDK调用方式保持。

P30-C1：固定P29原实现对相同完成值的普通/最终退休六项反馈环，正常成功和真实Failure分别保持；正常停止在最终退休的原unsafe红例由新逻辑转绿，最终payload/任务/队列归零且公开release可删除。P30-C2：实际Standard worker在正常停止事件读取后进入最终退休的受控时序，原Factory/SPI和关闭钩子确认原结果，SDK写零增量，真实Failure及unknown仍拒绝干净恢复。P30-C3：普通和搬迁安装的正常两代、原订单/组合/未知矩阵及受影响停止路径按最终同批源/DLL复验，旧失败和旧包保持。P30-C4：最终源码与库SHA、独立delta审查及组装交接；新增WT核心行为和真实交易均0。
# 成交时间解释

QMT原委托/成交字段中的无分隔HHMMSS允许数值式字符串省略前导零；解码时接受1至6位数字并左补零后校验小时、分钟、秒范围，原有HH:MM:SS及最多三位毫秒保留。原raw_time、回报内容、请求/委托/成交身份保持；规范事实使用解释后的毫秒值，等价写法按原去重语义处理。查询和事件共用同一mapper。空串、非数字、超长及无效时分秒继续拒绝，不以缺失值构造成交事实。

