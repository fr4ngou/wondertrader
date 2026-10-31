# QMT HTTP 接入原生只读查询

类型：后继方案草案。状态：按原生查询语义收敛，来源上下文及共用传输契约已分别冻结；HTTP领域接线唯一最终要求见[NQH规格](../specs/native-qmt-http-bootstrap.md)，实施及各级证据继续。事实基线：QMT `2083e96a`、WT固定上游 `08b230dd`及[NQB已审fixture候选](../evidence/2026-10-22-native-qmt-readonly-bootstrap.md)。原生接口依据见[独立源码核查](../evidence/2026-10-22-native-trader-query-semantics.md)。本方案保留HTTP优先、原生复用与独立业务发布；WT共享内存绑定和通达信交易继续暂缓。

## 目标与根因

沿WT原登录→持仓→委托→成交→资金→ready顺序，将每次QMT只读结果完整、正确地交给对应SPI。原ITraderApi和原XTP/CTP插件采用四次独立查询，没有共同券商原子批次要求。各批保留各自请求身份、观察时间和查询范围；四次查询不宣称同一时刻。

既有通用HTTP结果仍须核实来源账户/环境/会话和单批完整性，字段保留修正不能独立证明这些条件。优先使用已有`account.trade_detail`原线程采集和原OperationQueue/Journal结果所有者。`AccountSnapshot/state/sync`在字段与用途吻合时可复用，整条旧对账与Observation发布链作为可选来源；不额外把旧`reconciled`状态加成只读初始化前置。当前fixture标签证明继续限定fixture来源。

## 已核实职责

| 所有者/入口 | 已有能力 | 接入边界 |
|---|---|---|
| QMT `account.trade_detail` | 绑定原账户，在原策略线程查询；原队列/Journal提供请求与终态结果 | 每批核完整数组、成功/失败、来源身份和字段；通用envelope尚未自动给出全部证明 |
| 可选 `AccountSnapshot/state/sync` | 既有业务投影、边界及事件发布事实 | 按实际字段/权限复用；旧快照不授本轮成功，NativeCapture的None与[]归并也需核实，不将整批名称当完整性证明 |
| 可选Restricted ObservationBuffer→Host | 既有会话/窗口/水位与持久发布屏障 | 选择该入口时遵守其现有访问限制；其reconciled/clock_health条件不扩成所有只读查询的全局前置 |
| WT ITraderApi/TraderAdapter | 原顺序四查询初始化、账户及持仓/委托统计、query与push区别 | 接受独立完整查询；不拥有QMT来源证明，局部订单防重不构成任意成交重放幂等 |
| 自有HTTP/插件边界 | 认证传输、预算、解锁后owner回调、stop/drain/join及只读拒写 | 读取既有公开envelope并映射；不另建事实数据库、对账器或事件reducer |

当前源端依据：QMT `qmt_agent/broker/adapters.py`、`gateway/operation_queue.py`，以及可选来源的`common/contracts.py`、`qmt_agent/native_observation.py`、`broker/native_capture.py/native_producer.py`和Host observations。来源调查当时主目录只读复核为上述提交、Git干净；源码研究不证明已安装或启用这些入口。

[来源链补核](../evidence/2026-10-22-native-trader-query-semantics.md)进一步确认：原账户已由bindings注入，原协议区分None、空数组和异常，原Journal可保存扩展结果；缺口集中在本次执行身份、观察区间及完整范围声明。相同ContextInfo更新bindings时账户可以变化而generation保持，旧ID终态也可直接复用，故前后health加generation仍不足以代替逐批账户身份。新增元数据须在原执行上下文产生并随原结果保存；旧终态保留旧身份，不从当前health回填。

当前Adapter还固定向原get_trade_detail_data传第四参数`"qmt"`；官方定义该参数筛选ORDER/DEAL的策略子集。因此当前委托/成交入口不具备账户全量范围。后继源契约须明确不筛选策略的三参数只读查询和返回范围，兼容保留旧筛选消费者；原默认范围保持，不能通过添加complete=true把子集授为全账户完成。此结论及官方依据见同一补核记录。

## 来源契约须补齐的事实

| 范围 | 保留/补齐要求 |
|---|---|
| 资金 | 原总资产、可用与原生冻结现金；previous_balance单独声明来源，day_start_asset不能自动替代 |
| 持仓 | 只读合计必需总持仓V及可卖A，0≤A≤V；按[NQB合计资格](../specs/native-qmt-readonly-bootstrap.md)标识aggregate-only。精确今昨、分项可卖、成本、真实委托冻结各自按来源presence；V-A表示当前不可用，不替代委托冻结 |
| 委托 | 原券商ID、原始总量/成交/活动剩余与终态撤拒量、委托限价、来源原生日期时间及状态；采集时刻不替代委托时间 |
| 成交 | 原订单/成交二元身份、数量、原生成交价/金额/日期时间；可空缺失明确，不用批次日期补造原生日期 |
| 完整性 | 每一查询成功、范围/分页终结/截断/容量、合法空数组与None/失败分别声明；ACCOUNT唯一行；请求关联正确，旧结果不授本次成功 |
| 归属 | 原command/strategy归属和WT adapter/localid归属分开；旧QMT或外部订单可只读统计，WT管理标签留空。将来授本地管理归属时才要求可信映射，HTTP自述标签不构成证明 |

按实际选用的公开入口补齐必要事实，沿该入口原采集/结果所有者处理。先定义兼容版本、缺失语义和消费者，保留原资金/数量算法、账户绑定、签名权限及失败控制。必需字段缺失明确不可用，不用零值补造。每批成功后才交SPI；原Adapter接受null仍可能推进，适配层不能把错误、202或缺页变成空成功。公开只读就绪与真实交易资格分别定义。

## 源端最小兼容扩展（正式规格已冻结）

后继源码调查建议在原account.trade_detail增加受限`scope`，缺省`strategy`保持当前四参数调用与固定qmt筛选，显式`account`使用原项目已有的三参数调用。保持bindings账户唯一所有者，拒绝客户端account_id与任意strategy_name。通过原catalog/capability公开scope和结果契约版本，新消费者遇旧服务明确不支持；不能静默使用旧策略子集。源端唯一最终规格为QMT仓库`docs/specs/qmt-account-query-context.md`（qmt.account-query.v1），独立工作树已开发并通过源码及DTO修正独立复审，206项定向通过；严格门禁要求更新原策略制品，尚未安装，见[来源候选证据](../evidence/2026-10-22-qmt-source-build-review.md)；下面保留职责摘要，字段和验收要求以该规格为准。

原data形状保持，终态新增带版本的逐批observation：实际agent/账户/环境/session/generation、account_type/datatype/scope、服务器执行起止区间、交易日来源/可用性、完整性和范围。元数据在原QMT执行owner采集，转换完成后、原Journal持久化前固定。[]与None沿原语义分别保留；新资格将None标为未得到完整集合，容量/getter/native异常保持整批失败。complete只描述本次声明范围内完整返回并转换的集合，不扩大为柜台原子观察。

身份变化须沿原owner有明确代际规则：实际绑定账户、环境或来源session变化时推进现有generation；真实调用前冻结上下文，调用后核对代际，覆盖A→B→A变化。现同ContextInfo换bindings及reconfigure不全推进代际，不能只新增响应字段而保留这个缺口。该变化涉及源端状态语义，已由源端最终规格及ADR-0515定义，开发回归覆盖排队与执行中变化及兼容；旧终态始终保留旧身份，不回写其数据或摘要。

既有codec默认有深度及单容器项数限制，普通Queue当前未传ConversionBudget，尚无已启用的累计节点/字节预算证明。若本次契约需要更严格总容量，应沿原转换owner接入已有budget并保持超限整批失败。原摘要保持Journal持久结果投影，observation在摘要前固定；后加的返回计时单独声明。复用现有结果JSON，无数据库schema或第二存储要求。

验证保留默认四参数与显式三参数的精确原调用、四datatype、非法scope/账户覆盖拒绝、capability兼容、请求内容冲突、合法空/None/异常、执行前后身份切换、A→B→A、旧终态恢复及摘要投影。Agent代码继续Python3.6标准库约束。实施位置为原broker Adapter、gateway core/Queue/capability及现有测试，先完成跨仓库最终契约，再修改源端与WT消费者。

## 接线顺序

1. 核实当前公开版本、所需原字段、原账户与会话绑定；冻结逐查询成功、合法空、分页和错误契约，先用原线程采集fixture验证。
2. 自有HTTP适配沿已签名的只读查询入口保留完整envelope，不另建账户状态库。开发测试使用隔离loopback源；可选state/sync只有在字段与访问契约吻合时接入。
3. NQB worker创建/独占HTTP客户端，逐次查询并冻结该批验证结果；owner pump按原顺序提供对应回调。每批请求/账户/会话、必需字段或完整性不合格时明确失败，禁止ready。各批时间分别记录，不要求同一snapshot_id。
4. 验证stop取消等待、晚结果拒收、实际回调排空和join；排空未完成时保留client/DLL所有权，进程资格不替代常驻恢复。
5. 原始真实QMT来源、完整字段和实际安装身份分别取得后，进行只读接线验收。历史成交仅送onRspTrades，原生实时成交仅送onPushTrade；持续回报交接/去重/缺口/恢复另验。交易写通道与生产部署按单独授权和完整方案执行。

## HTTP传输复用接缝

当前实现入口为`src/GuanhengData/QmtHttpClient.h/.cpp`，消费者包括`QmtHttpEndpoint`、`QmtPollingParser`和`MarketBridge`；它仍只允许两个market操作。`GuanhengQmtBootstrap/ReadOnlyTrader.cpp`当前只有fixture源。唯一最终规格为[QRT共用只读传输](../specs/qmt-shared-read-transport.md)，现已在自有模块实施，尚未完成独立审查。下面保留架构摘要，接口、准入、错误及验收以QRT规格为准；原冻结候选及验证身份保持。

| 层 | 接口与责任 | 变化时需要核验的消费者 |
|---|---|---|
| 自有公共只读传输 | 从既有客户端收敛签名、有限WinHTTP交换、owner检查、绝对截止、health会话检查、单次POST及原ID认领、回调排空；输出有界的原envelope与传输观察 | 行情和只读账户包装器使用同一实现；不开放任意operation字符串执行能力 |
| 行情包装器 | 保持现有`prepare/session/capability/read_operation/drain_callbacks`调用面、两个market操作白名单和精确参数验证；继续向现有消费者返回其需要的data | Endpoint、PollingParser、Bridge及HTTP预算/关闭测试 |
| 账户只读包装器 | 仅注册`account.trade_detail`的四种已核准查询参数，逐批校验来源/完整性与字段，再交NQB结果队列；结果所有权在worker，SPI只由owner pump交付 | 原生四查询宿主、字段归一和关闭/晚结果测试 |
| fixture与HTTP来源 | 使用相同的单批结果与错误接口，分别提供确定性fixture和实际HTTP结果；来源准备成功后才允许连接事件推进 | fixture原22场景保持；HTTP新增隔离loopback场景 |

公共传输放在自有公共模块，账户插件无需链接行情Store、Reader或原市场服务。原`QmtHttpClient`保留为行情包装器，避免将账户权限、今昨仓或订单状态规则混进传输。操作注册在各包装器形成闭合集合，远端capabilities只能缩小可用集合，不能扩展本地准入。共享的是实际存在的传输与生命周期机制，字段映射继续由对应领域包装器承担。

原响应必须同时保留：`request_id/operation_id/ok/completed_at/data/error_code/error_message`及存在时的`result_sha256`、队列/执行计时和来源扩展。传输错误与远端终态错误分别表达；错误详情保留在受控诊断值中，日志按既有脱敏约束输出。摘要有明确覆盖投影前只作为原证据保存。不能将新拼装的JSON或额外计时字段混入原摘要校验。现有market调用面的成功data语义保持；增加完整结果供新消费者使用，不能让原消费者把远端失败或Pending当成功data。

health前后观察用于发现会话漂移，完整envelope用于关联本次请求；二者分别标识。`completed_at`是执行结果完成时刻，`last_tick_at`是Host回调存活时间；账户观察时刻、交易日和逐批账户身份依赖源公开契约。包装器不能用这些传输字段替代缺失来源事实。

关闭保持原创建线程所有权与显式`drain_callbacks`约束。worker停止新请求后，实际网络等待必须结束并完成回调排空，才允许join后的对象/DLL释放。传输析构等待只是最后资源保护，不能充当有界关闭通过证据。重构先冻结公共返回值/准入/关闭契约，再同步所有消费者；验证原HTTP截止与排空场景、两类包装器互相拒绝操作、同请求结果关联、fixture/HTTP等价投影和四查询原生链。当前历史修复包冻结期间不修改其编译输入。

## 通用operation请求恢复独立处理

现`QmtHttpClient::read_operation`仅允许两个market操作，每次生成新UUID，只在本次截止内认领202/未知交付，返回仅含data。原Gateway OperationQueue→CommandJournal才拥有受理、执行及终态；重启把未完成请求终结为operation_interrupted。其结果摘要在持久写入前计算，随后追加的计时字段不属于同一摘要投影。

后继在原HTTP owner内设计显式不可变ticket、一次submit和只GET原ID的claim接口，保留原错误、终态时间、原data及摘要覆盖定义。ticket首次POST前由宿主保存非秘密请求描述；远端受理/完成继续归原Journal。404或网络超时保留未知，跨会话旧终态只结清原请求，不授当前行情/账户观察资格。原WT查询和CTP/XTP的SDK request ID不承担HTTP持久认领；不引入第二请求数据库。这项跨重启恢复可先服务历史获取，当前只读初始化先沿既有本次调用预算和结果认领契约，未获合格结果时拒绝就绪。

## 验收

原顺序四次独立成功/合法空查询可就绪；每批请求错配、跨账户/会话、失败/None/202/缺页、容量、超时和旧结果拒收；合计V/A与aggregate-only输出、可选今昨/分项可卖和真实冻结各自资格及订单状态量守恒；原价时金额缺失；外部订单空管理标签、本地号冲突、重复与真实冲突；历史成交不冒充push；关闭期间晚回调/drain/join。生产持续流另验查询与推送交接、重复/缺口/乱序及断线/进程恢复，不以只读初始化成功授交易资格。HTTP ticket另测响应丢失、202后超时、新客户端/新进程原ID认领、Gateway重启中断/已完成保留、内容冲突和404未知，核实无猜测性新ID重投。

当前源字段清单修正属于通用序列化根因修复，其审查通过不替代本方案的逐批真实来源验收。方案不新增数据库，不改WT core，不启动真实交易、下载或订阅。
