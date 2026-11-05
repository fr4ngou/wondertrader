# 标准 TraderQMT 实时事件与查询交接

类型：功能规格。整体状态：proposed。适用范围：自有标准 TraderQMT 的订单/成交事件消费、真实缺字段补查、同实例交付去重、查询交接与停止。代码存在、隔离链验证和目标 SDK 运行事实分别登记。

已接受实施切片为SEV-R2的Common页校验与真实上下文携带、SEV-R3明确列出的mapper可选规范金融输出，以及SEV-R2b的独立事件mapper与P8事件begin、SEV-R2c的同次准备事件读取上下文、SEV-R4a的有限交付索引及SEV-R11的完整字段测试消费者。accepted只允许对应独立切片实现与验证；SEV-R14单独接受query_first首次准备的持久前沿选择，SEV-R8其余生产交接承诺继续proposed；缺字段补查按本文后续各已接受切片执行。SEV-R11只接受已知查询后新增事件的隔离验证，能力位保持0。

依赖：[标准交易插件](native-qmt-standard-trader.md) STQ-P7/P8/P9、[共享内存交易](qmt-shm-trading.md) QST-R5/R6/R11/R18/R20/R21、[账户只读](qmt-shm-account-read.md)。本规格细化 STQ-P5 的后继消费设计；旧接口、金融解释与已接受要求继续生效。查询与回报覆盖的来源证据、跨进程应用未知仍为本规格显式待决项，不由新增配置布尔值消除。

## 背景、目标与原生复用

源策略已沿原 callback 保存订单/成交原字段，Host 已持久保存事件和 R21 原命令关联，原生客户端已有真实有界事件页入口。标准插件当前完成账户查询的 worker→owner→worker→owner 链；后继实时观察应沿相同线程职责送回原 WT SPI。

复用[原生能力目录](../development/wondertrader-capabilities.md) WT-T01、WT-T02、WT-T08、WT-T09：ITraderApi/ITraderSpi、TraderAdapter 查询推进与业务归约、原订单成交对象及日志；供应商回报交接由自有插件负责。固定上游 08b230dd05facf6d650d949bfe51054115a2ecb1 的 XTP/OES 查询与推送共用对象映射，HTS 在推送前以成交 ID 抑制重复；这些接缝为本设计依据。SDK 特定恢复承诺与插件状态保持分别适用，不能跨供应商推定。

目标是将真实事件交到原 onPushOrder/onPushTrade，并保留来源、身份、时间、错误、重复和未知的实际范围。Host 继续保存通信事实，WT 继续归约持仓、资金、统计与订单业务。自有层只保存有界交付标识和必要原诊断，不计算第二份金融状态，不新增四查询原子门、逐单审批、生产资格等级或虚构 SDK 能力。

## SEV-R1 调用链与所有权

同一已测内存策略与原 init/set_account/agent_tick/order_callback/deal_callback/orderError_callback 保持。回调投影、原线程 SDK 和 I/O 职责沿 QST，不另建 QMT 策略或更换 loader。

1. Agent 原回调→TradeEventBuffer：有限原字段、原 session、单调本地序号及连续页。
2. Host 原 TradeEventRecords 事务：原事件/摘要、连续 durable、源 ACK 意图及 R21 proof；提交成功后才确认源缓冲。
3. 标准插件唯一 worker：原 QmtHostTradeClient.events() 读取真实已持久页，仅携独立值进入 completion。
4. 创建插件的 owner：验证来源并准备唯一金融 mapper 候选；将纯值身份 Plan 回送同 worker。
5. worker：沿原 D 运行 P8 身份 resolve/原 lookup，回送纯值 Resolved。
6. owner：P8 finish、重复检查和最终 generation/detach/stop/D 检查，释放自有锁后调用 SPI。

worker 不持有 BaseDataMgr、WTSArray、SPI 或 Candidate。Candidate 只在原 owner 销毁。停止后晚到 Plan/Resolved/事件页仍为独立值，不能延长 SDK 回调对象生命周期。并行入站、SDK同步重入、异步回调不改变此分工。

## SEV-R2 真实事件页与公开接缝

本节中Common页校验和真实上下文携带为accepted实施切片；Bootstrap event begin按SEV-R2b接受，Standard完整字段隔离消费接线按SEV-R11接受，生产交接仍在proposed整体范围。当前 [QmtHostTradeClient.h](../../src/GuanhengCommon/QmtHostTradeClient.h) 的实际类型为QmtTradeEventPage，Host请求/响应协议保持。events原五参数及返回类型不变，本SEV-R2页校验切片不新增QmtTradeEventsResult别名、overload、getter或平行运输封套；后继同次准备上下文按SEV-R2c独立接受。

Common准确头文件如下，均位于namespace guanheng、现QmtHostTradeClient.h；实现放现QmtHostTradeClient.cpp，不新增cpp或Bootstrap反向依赖：

~~~cpp
struct QmtTradeEventPage {
    Status status;
    QmtTradeEventSource source;
    std::string page_json;
    std::uint64_t next_sequence = 0, durable_through = 0,
                  source_ack_through = 0;
    std::size_t event_count = 0;
    unsigned http_status = 0;
    bool gap = false;
    // 原成功返回结构尾追加，均为同次Core的真实值。
    std::string read_profile_body;
    std::size_t read_result_capacity = 0;
    std::size_t admitted_event_page_capacity = 0;
};

// Common本地原请求值，由实际Task冻结，不增加Host JSON字段。
struct QmtTradeEventRequestBounds {
    std::uint64_t after_seq = 0;
    std::size_t limit = 0, max_bytes = 0;
};

// 独立DOM和派生事实；表示纯校验结果，不表示Host来源认证token。
struct QmtValidatedTradeEventPage {
    rapidjson::Document source_binding;
    rapidjson::Document document;
    std::uint64_t next_sequence = 0, durable_through = 0,
                  source_ack_through = 0;
    std::size_t event_count = 0;
    bool gap = false;
};

Status validate_qmt_trade_event_page(
    const std::string& page_json,
    const QmtTradeEventSource& source,
    const QmtTradeEventRequestBounds& original_request,
    const QmtExpectedTrade& expected,
    const QmtTradeReadDescriptor& admitted_limits,
    std::size_t admitted_event_page_capacity,
    SignedHttpDeadline& original_deadline,
    QmtValidatedTradeEventPage& out);

// QmtHostTradeClient现成员签名保持。
QmtTradeEventPage events(
    const QmtTradeEventSource&, std::uint64_t after,
    std::size_t limit, std::size_t max_bytes, SignedHttpDeadline&);
~~~

Common头显式包含rapidjson/document.h，Validated的Document拥有内存，可移动、不可复制，输入string销毁后仍有效。out在全部校验/分配及原D后检成功后一次无分配移动发布；失败/异常保持原out。函数不声明noexcept，分配异常沿现调用者边界处理，不能发布部分成功页。

read_profile_body/read_result_capacity来自同次Core prepare已验证的profile原bytes/容量；admitted_event_page_capacity来自同次refresh实际已验证的Host页容量。refresh确认max_events等于profile，Host页容量可小于profile.max_event_page_bytes，且已核不超过该客户端私有HTTP response_capacity。三个尾值从这些实际缓存复制，不由page正文推算，不新发HTTP。原页body保持真实原bytes，字段复制完成后再核原D；失败时新尾值为空/0，原source/after/http_status错误语义保持。

源/请求准入与页正文规则从原events各提取一个Common私有实现。Core在HTTP前核原source/bounds并持有解析后source_binding，在HTTP成功后使用同一正文函数；公开纯validator调用同样两部分。每次边界准入仅一次有界页正文parser调用，保留原SAX预检/DOM、UTF8/重复键/深度/节点/有限数约束。owner复验取得Validated后直接消费其DOM，不再额外parse同一page。Common不涉及WT对象、SDK、SPI或金融转换。

Bootstrap事件入口按SEV-R2b接受，显式传入可信expected：

~~~cpp
QmtAccountIdentityBegin begin_qmt_trade_event_identity(
    const QmtTradeEventPage& page,
    const QmtTradeEventRequestBounds& original_request,
    std::size_t event_index,
    const QmtExpectedTrade& expected,
    const AccountBinding& account,
    wtp::IBaseDataMgr* base,
    const QmtAccountIdentityBudget& budget,
    SignedHttpDeadline& original_deadline);
~~~

调用者与各层校验职责必须同时满足：

1. expected来自Standard::Impl.expected的独立可信副本，含固定account/binding_id/binding_sha256；account的账户/环境与expected.account一致，币种/金融profile保持原部署准入。page.receipt.binding_id不能反过来充当期望；公开profile也不能提供可信binding_id。expected.writes_enabled不成为事件读取或账户读的准入门。
2. original_request是实际events调用的after/limit/max_bytes，入队冻结，经原task_id/generation的Task→Completion原样交owner并计费。零limit/零max_bytes非法、after=0合法。不能从next_sequence/count反推请求，不能由响应自选limit。
3. Core在真实HTTP前后保持原线程/HTTP owner/原D与EOF错误处理。Standard宿主在event begin之前，用自身冻结的http.max_response_bytes核original_request.max_bytes及page.admitted_event_page_capacity不越界，并核原任务预留。纯validator只在显式传入的actualHostcap内校验；现begin参数不能独立重建HTTP配置，不能声称它单独完成上述宿主私有HTTP上限检查。
4. owner以真实page.read_profile_body/read_result_capacity和expected.account调用现validate_qmt_trade_read_profile；核完整v4/account2.0、descriptor.binding_sha256等于expected.binding_sha256、原profile SHA等于source B.capability_sha256。调用纯validator时使用该已验descriptor、可信expected与同次实际Host页cap；actualHostcap须为正且不超过profile页上限，request.max_bytes须为正且不超过actualHostcap。profile较大上限不能替代较小actualHostcap。
5. 纯validator核真实page_json/source/bounds/receipt/账户/固定binding_id/连续性/预算及原D，并产出派生值；begin比对公开page的next/count/durable/source_ack/gap与这些值。event_index是真实events数组零基下标，仅接order/deal；error沿SEV-R7。合法gap是页事实，按SEV-R7处理，不能改为codec失败。
6. 页和尾字段是公开可修改值。格式、SHA关联与重复parse不能认证任意一致伪造的JSON来自Host。event begin只消费同一可信worker真实客户端调用所得的completion；私有task/generation/ticket共同保留expected、实际bounds、源B/session/profile/预算的来源链。既有Core提供的成功值与任意磁盘反序列化/人工拼装值分开，不能用后者补造来源资格。
7. begin返回现QmtAccountIdentityBegin独占Candidate/Plan；resolve/finish签名保持。原query begin与event begin共用已准入原行后的金融构造、重复预检、身份Plan、lookup和写槽。原P8错owner/ticket保留双句柄；同owner同ticket终态消费；原行/DOM均拥有独立内存，不借用输入page。
8. 历史source B/session仍可沿现events读取诊断，Common codec不新增“source必须等于当前pin/session”的规则。新尾profile/cap来自该客户端当前真实上下文；历史页与其不符时，后继begin拒绝作为当前金融观察，不能用当前profile升级旧来源。公开page空/0旧形态保留原诊断兼容，新增begin要求完整真实上下文。

真实page_json顶层只有schema_version/receipt/events。实际qmt.trade-event-receipt.v1的精确键为schema_version/session_id/binding_id/host_binding_sha256/durable_through/ack_intended_through/source_ack_through/observed_published_through/gap；event精确键为schema_version/session_id/binding_id/sequence/kind/payload。receipt以host_binding_sha256关联调用者原source B；完整B在本地source中。event没有source_event_sha256或逐事件raw字段。

纯validator保留原完整规则：after为0..2^53-1；limit不越profile max_events；页和单event字节受实际请求/max_event_bytes约束；ack_intended等于durable、source_ack不越durable、observed_published不小于durable；从after+1逐项连续，next不越durable；after小于durable时空页拒绝；初始空流与已到前沿空页合法。HTTP409/404、截断、晚回原错误继续由Core返回，只有原正常HTTP200进入页codec；不能借lookup的409规则扩大events成功分支。

这里的receipt是实际事件持久前沿收据，与QmtBoundReceipt的binding_json/request_body/read_profile_body及Core原账户结果认证是两条契约。事件只经独立provenance进入唯一金融核心；不能把事件receipt转换成账户Core receipt/QmtAccountResult/account-batch，也不能补造查询execution/UTC/result_sha。

### SEV-R2b 独立事件mapper与P8 begin（accepted切片）

本切片只实现完整order/deal事实的owner金融构造及既有P8三阶段身份解析；不装配Standard/SPI、缺字段补查或query/live交接。合法gap页中的已验连续prefix可进入本纯映射链；Standard的gap写屏障仍待装配，begin成功不授新写许可。实际Host来源由原HTTP链保证；一致的公开page/profile/bounds值通过纯校验不构成来源认证。

Bootstrap公开接口冻结如下，类型位于原QmtAccountIdentity.h；Result尾附event_provenance，query结果恒为null。原resolve/finish及兼容包装签名不变：

~~~cpp
struct QmtTradeEventProvenance {
    QmtTradeEventSource source;
    QmtTradeEventRequestBounds original_bounds;
    std::size_t event_index = 0;
    std::uint64_t sequence = 0;
    std::string kind, page_json, read_profile_body;
    std::size_t read_result_capacity = 0, admitted_event_page_capacity = 0;
    std::string derived_page_sha256, derived_event_sha256;
};
// QmtAccountIdentityResult尾部：
// std::shared_ptr<const QmtTradeEventProvenance> event_provenance;
QmtAccountIdentityBegin begin_qmt_trade_event_identity(
    const QmtTradeEventPage&, const QmtTradeEventRequestBounds& original_bounds,
    std::size_t event_index, const QmtExpectedTrade& trusted_expected,
    const AccountBinding&, wtp::IBaseDataMgr*,
    const QmtAccountIdentityBudget&, SignedHttpDeadline& original_deadline);

// 原AccountMapping.h；仅stage1/2、恰一行、固定view3、显式canonical输出。
AccountBatch map_trade_event_rows(unsigned stage, const rapidjson::Value& rows,
    const AccountBinding&, wtp::IBaseDataMgr*, const AccountCanonicalLimits&);
~~~

事件begin在DOM/金融分配前核原D、总预算、page/profile原bytes与Common既有硬上限，使用真实read_result_capacity验证完整profile、原profile摘要匹配B、可信expected与AccountBinding的account/environment一致；纯page validator沿原bounds与真实admitted_event_page_capacity核整页，并核公开page派生字段、http_status/status一致。实际HTTP响应上限仍由原宿主/Core负责，不能用profile重建该私有额度。event_index必须落在真实events数组内；order派生stage1、deal派生stage2，error或缺金融必需字段沿明确失败返回，不补造金融事实。

provenance保留原page/profile/B/session和原bounds独立值；derived_page_sha256对原page_json字节计算，derived_event_sha256对选中原event对象的json_text字节计算，两者均为本地派生摘要。新event身份view使用独立schema=qmt.wt-event-identity.v1；保留原stage/output_index、order_id/ref_order/trade_id、原remark/order_ref presence/value、classification/entrust_id/user_tag/reason、lookup_response_index/lookup_sha256字段，以event_index/sequence/kind/derived_page_sha256/derived_event_sha256替换query专用request_id/result_sha256。B/session经同一结果provenance引用，不给事件填查询UUID、查询摘要或UTC。

私有Plan只保存已准入rows的独立DOM、transport和来源种类，不留假account封套。query仍由原Shm入口核完整receipt/UTC，原views/身份view/预算字节保持。event mapper复用唯一金融循环及canonical决定，source/request_id/result_sha/started/finished/seconds全空，source_rows=1、source_to_output={0}、canonical_records恰一项；显式传AccountCanonicalLimits{1, originalBudget.max_total_bytes}，不增资源配置。缺字段、非法字段及异常沿原mapper错误边界释放整批。

事件逻辑计费使用Identity cpp集中定义的两个constexpr：provenance固定128字节，覆盖来源/bounds/index/sequence/capacity字段及共享引用/摘要索引预留；group固定64字节，覆盖单行分组/输出映射/lookup引用索引预留。它们为逻辑预留常量，不能描述为sizeof或实际物理占用。事件begin总计：128 + provenance内七个字符串（B/session/kind/page/profile/两SHA）各size+1 + json_text([原payload])字节 + mapper views各size（不加NUL）+ source_to_output.size()*sizeof(size_t) + mapper canonical_bytes（原key/hash各一个逻辑NUL）+64+group broker/symbol/trade_id各size+1。原token缓存、lookup原回复、身份view沿既有size计费继续累加同一total及原lookup/view子额度；不重授预算。provenance由Candidate/Plan/Resolved/Result共享同一const对象，保留一份计一次；DOM/分配器物理开销不作等量承诺。

事件ticket保存真实原session。resolve先沿原D调用真实client.prepare，再核same_source(当前B, ticket原session)，结束前再次prepare并核同一ticket来源；不以未prepare客户端的空来源增加前置资格门。query保留现行首次prepare取得session、末次prepare核该session的行为。错owner或错ticket的finish保留两个句柄；同票据终态才消费，失败不交出金融array，可保留有限provenance/lookup/身份诊断。所有候选构造、resolve及finish均消费原absolute D，原输入先销毁后worker仍持独立值。

### SEV-R2c 首次取页前的真实读取上下文（accepted切片）

Standard 首次调度前须依据真实已验 profile/Host 页限额冻结请求与额度。现 prepare 只返回 Status，真实上下文在 Core 私有状态中；成功 events 的尾值只可用于取页后的复核。调用者不能猜首个请求 limit/max_bytes，也不能把私有 HTTP 接收上限当作 Host 已准入页上限。本切片在自有 Common 增加如下显式接缝，不改 WT 框架、源策略、Host 协议或既有 events 五参入口：

~~~cpp
struct QmtTradeEventReadContext {
    QmtTradeEventSource source;
    std::string read_profile_body;
    QmtTradeReadDescriptor admitted_limits;
    std::size_t read_result_capacity = 0;
    std::size_t admitted_event_page_capacity = 0;
};
Status QmtHostTradeClient::prepare_event_read_context(
    SignedHttpDeadline& original_deadline, QmtTradeEventReadContext& out);
~~~

创建线程调用该方法；新入口先沿Core原check核创建线程及原D，失败直接返回，避免错误线程进入prepare前改写Core的accepting标记。该防御只收紧本新入口，不授权整个客户端并发调用、不改变原prepare。预检成功后内部只执行同一次既有 prepare（read-binding 与 refresh），直接使用该次 Status 判断成功。成功后复制原 B/session、profile、已校验 descriptor、read result 上限及 refresh 实际 Host 页上限为独立临时值，全部复制完成后再次核原 D，再以无异常移动赋值一次发布 out。失败、错误线程、已过期、来源变化、准入或分配异常均保留 out 原值；异常沿既有调用者边界处理，不能交出半个上下文。Core 原 prepare 的内部状态副作用保持，方法不承诺内部回滚，也不凭旧 ready 标记发布旧快照。

该方法不取事件页、不发命令、不做 lookup、不新起网络客户端/线程。旧 prepare 保持原行为。Standard 后继可在同一原 Prepare/Login Task 内用新方法替换原 trade.prepare，取得独立完成值；不得先 prepare 再调用新方法增加重复 I/O。上下文仅为已验读取配置，不包含 cursor、accepting、写资格或查询/成交覆盖结论。

所有字段必须来自本次真实私有 Core；公开 DTO 被调用者改写不构成 Host 来源认证。admitted_event_page_capacity 已由原 refresh 核 profile 范围且不越客户端私有 HTTP 上限；不能用 descriptor.max_event_page_bytes 替代实际 Host 较小上限。后继 Task 必须保存可信独立值，owner 再核资源关系；该接口本身不装配 Standard 或承诺长期索引计费。

验收以实际认证回环服务覆盖同次准备恰两次 GET/零事件或写请求、实际 Host 页 cap 小于 profile 最大值、原 profile/descriptor/来源一致与独立寿命、错误线程/过期无新 HTTP，先成功再错线程调用保持此前真实accepting及全部out、read-binding/refresh 失败和超时保留已有 out、成功后来源或配置变化导致下次失败且旧 out 保持。旧 prepare/events/账户及关闭回归按影响保留。完整 Standard 调度、首 cursor、SPI 和 query/live 仍属后继范围。

## SEV-R3 来源元数据与唯一金融 mapper

[AccountMapping](../../src/GuanhengQmtBootstrap/AccountMapping.cpp) 继续是订单/成交金融解释的唯一实现。[ShmAccountMapping](../../src/GuanhengQmtBootstrap/ShmAccountMapping.cpp) 保留真实账户 Core receipt/原请求/版本/UTC 区间验证。内部将来源封套元数据与金融行核心分离，查询与事件调用同一金融行核心。

事件来源元数据至少表达：kind、原 B/session/sequence、在原完整页中的 index、原页有限 bytes 诊断引用及 derived 摘要、来源记录中的实际日期时间。没有 query request_id、SDK查询 started_at/completed_at 或原 account result_sha 时明确为不适用；不得填写本机接收UTC冒充源执行区间，或以 sequence 冒充请求ID。事件捕获本身没有提供 UTC 观测区间，缺失保持缺失。

来源元数据使用独立 event provenance 值，不能将可选事件字段加入旧 v2/v3 查询 JSON 后仍声称字节不变。旧查询 AccountBatchMetadata/公开金融 views/ABI 和 P7/P8身份视图保持原语义、字段、排序及 bytes；事件诊断输出采用独立来源表示，数值/状态规则仍共用同一核心。接受后若确需新公开 JSON 形状，应单独冻结其实际消费者；本提案不先发明运输版本。

所有必需字段、缺省/空/null、有限数、整数、数量守恒、价格 ABI 中性值、日期时区、成交额及去重规则继续沿现 mapper。SDK 原价格类型字段可保留诊断，本切片不将现未知价格 ABI 提升为已知金融事实。事件 kind 不授权新金融含义。

### SEV-R3 accepted：可选规范金融输出

本节规范输出切片复用WT-T01/WT-T02的原WTS对象和本仓唯一AccountMapping金融解释，只公开既有去重处的规范事实。事件provenance与Bootstrap事件入口按SEV-R2b接受；Standard事件消费及完整交付索引仍为proposed。各切片均不构造事件查询封套或本地UTC。

公开C++接口冻结如下，位于guanheng::bootstrap；原六参函数符号保持，新七参重载显式启用：

```cpp
struct AccountCanonicalRecord {
    std::string canonical_key, derived_facts_sha256;
};
struct AccountCanonicalLimits {
    std::size_t max_records, max_bytes;
};
// AccountBatch尾部新增：
std::vector<AccountCanonicalRecord> canonical_records;
std::size_t canonical_bytes = 0;
AccountBatch map_account_rows(unsigned stage, const rapidjson::Value& rows,
    const AccountBinding&, wtp::IBaseDataMgr*, const AccountBatchMetadata&,
    unsigned view_version, const AccountCanonicalLimits&);
```

- 原六参入口不生成新输出：canonical_records为空、canonical_bytes为0。新重载只接受order/deal（stage=1/2），view_version仍仅2/3；max_records为1..4096，max_bytes为1..既有protocol::hard_view_bytes（64MiB）。无隐藏额度。rows仍借用至返回，输出持有独立字符串；owner/BaseData/WTS线程要求沿原mapper，无新增I/O、时钟、线程或持久状态。
- 每个最终WTS数组下标恰有一项canonical_records；原行通过既有source_to_output定位。仅在现canonical/seen完成金融校验且决定首次保留该行的位置生成，重复行不新增记录、不重复计费。原批内同key异事实仍拒绝；旧views、view_bytes、source_to_output、WTS槽和缺省预算保持。
- canonical_key为json_text编码的固定顺序JSON字符串数组，编码UTF-8，无空白：订单为["guanheng.account-financial-key.v1","order",account,environment,currency,profile,WT市场,证券,八位规范来源日期,broker_order_id]；成交将kind改为"deal"并在尾部追加原scoped_trade_id。订单号来自m_strOrderSysID；成交的broker_order_id是原RefOrder，scoped_trade_id仍由现exchange/code/day/raw_trade_id算法产生。key补齐账号/环境/币种/profile/市场/证券/来源日作用域；它不包含本地EntrustID、userTag、token或查询时间，也不授WT归属。固定顺序JSON及字符串长度编码消除分隔符歧义。
- account/environment/currency/profile来自可信AccountBinding，启用时account须非空、UTF-8字节数<=63且无现边界控制字符；environment精确live或simulation，currency精确CNY，profile精确cny_cash_shsz_v1。非法UTF-8拒绝。市场/证券/day/broker/scoped_trade_id直接使用本次mapper已校验的局部值，不在插件重复解析原行。相同柜台订单号跨账号、环境、市场、证券或来源日得到不同key；该作用域不构成跨未知柜台会话复用编号的永久唯一承诺。
- derived_facts_sha256为现canonical/seen处normalized UTF-8 JSON bytes的SHA256小写64位hex。摘要只表示派生规范金融事实，不是Host源原文字节hash，也不替代R21 proof。canonical不加入本地UTC、查询request/result元数据、批次下标、v2/v3视图版本或额外Remark/OrderRef原始字段。
- 数值等价完全沿现canonical：可表示的整数/浮点转同double，日期和时间文本等价形式转同规范数值；signed zero沿既有Writer表示保持。字符串保留解码后的UTF-8值，不做大小写、Unicode归一或标识别名；不同JSON转义写法解码同值后等价。可选字段缺失/null沿现fact生成同unknown；空币种与缺省币种保留既有不同reason，摘要可不同。非法类型、bool及未知事实沿原fact/必需字段校验语义，不借新摘要放宽金融准入。
- 订单跨批同key的真实状态、已成交或余量变化产生不同摘要，后继消费者据原金融语义处理状态演进；同批冲突仍拒绝。成交同key异金融事实是冲突依据，摘要接口不将其解释为合法新成交。无新增跨批状态或账本。
- canonical_bytes严格等于每个唯一输出的canonical_key.size()+1+derived_facts_sha256.size()+1之和，包含两个逻辑NUL字节。计数/字节逐项在发布前核对max_records/max_bytes，等于上限可接受，少1字节拒绝；算术使用先减后比避免溢出。此值只计本次可选字符串有效载荷，不声称覆盖vector、分配器或完整事件索引的实际内存。caller后继若保留输出，须将该量纳入其已冻结总预算；现P7/P8未请求输出，其预算不变。
- 任一格式、容量、hash或构造失败沿现异常语义抛出，局部AccountBatch的RAII释放整批WTS对象；没有可见半批或部分输出。SHA256统一复用本文件原CNG算法，保持hash句柄先于object缓冲区释放，并保持原scoped_trade_id逐字节结果。

验收使用现currency_probe：原四类/v2v3断言保留；新增独立固定key/hash或等价/不等价反例、完整作用域差异、来源文本转义、数值及日期时间等价、缺省/null、真实订单状态变化与同批冲突、唯一记录去重计费、max_bytes-1/等值、max_records边界、非法绑定/非法UTF-8、原scoped_trade_id固定向量和原views/source_to_output不变。运行结果由实际制品另记。

## SEV-R4 派生摘要、同会话去重与回调窗口

Host 原事件 SHA 继续由 TradeEventRecords/R21 保存并验证。C++ 从已校验事件解析值经同一 codec 生成的摘要明确为 derived，仅用于本实例重复交付检查/诊断，不与 source_event_sha256 比较，不替代 R21 proof。字符串、bool/null及数值类型的处理必须固定，精确重复样本的派生值稳定；规范等价与源字节相同分别记录。保留实际原页 body 即可，不为本功能新增 Host raw/SHA 封套或 JSON-span 算法。

本实例使用仅在内存中的 volatile 交付索引。它在当前插件实例寿命内保留记录，实例退出即消失，不新增持久去重表、数据库、Host消费票据或金融业务账本，不跨进程继承“已交付”结论。其长寿命占用预先纳入 SEV-R6 的现插件总预算。索引记录两种有限事实：

- 运输身份：完整 B、session、sequence 与 derived 事件摘要。同一身份重复不再调用 SPI；同一身份冲突走现错误/诊断通道。
- 金融交付身份：mapper 的 canonical_key/derived_facts_sha256 和实际交付处置。同一成交即使由不同 sequence 回报，金融事实相同则抑制重复 SPI；同成交身份金融事实冲突保留错误，不再次累加。R21归属及原 token 仍独立核对，不能以金融相同掩盖原身份冲突。

订单完全相同规范快照只交付一次；同 OrderID 的真实后续状态仍可交付，不能只按 OrderID 永远抑制。没有来源版本或顺序保证时不自行“修复”乱序状态、不重建累计成交量。委托/成交额、持仓和可用量仍由原 WT 处理。

交付步骤为预留有限记录→标记本次 delivering→锁外 SPI→记录 returned。SPI 前必须完成去重、额度、原 D 和实例检查。SPI 同步重入不能再次领取同一记录；复入 pump 本身必须有明确串行保护。回调返回后才记录 returned；异常、进程退出或无法确定返回路径保留 delivery_unknown，禁止把同一增量当作未投递自动重放。该记录不命名为 wt_applied，不宣称金融事务提交。

页内按 sequence 顺序处理。read_cursor 只推进实际读取的前沿，handled_cursor 只推进已有明确处置的连续前缀；returned、duplicate、纯error诊断分别计数，不能把 handled_cursor 称为SPI已应用水位。未决补查/交付异常保留原项，后继消费不得跳洞伪造连续。Host 原事件持续保留，C++处置不发送源ACK、不删原事件。

### SEV-R4a 有限交付索引（accepted实施接口）

当前插件的有界内存交付索引位于自有TraderQMT/EventDeliveryIndex，不创建金融数据库或第二份持仓资金状态。接口以[EventDeliveryIndex.h](../../src/TraderQMT/EventDeliveryIndex.h)为准：构造冻结完整原B/session及资源额度；reserve接已验证的单条运输/规范金融/管理身份值；start标记实际SPI开始，finish以Returned/Unknown/Suppressed结束。reserve失败不改变原索引，所有分配在start之前完成；start/finish无分配且noexcept。创建线程串行拥有索引，错线程reserve返回Conflict，start/finish拒绝且不改状态；不授并发调用或跨实例恢复能力。

运输身份为本实例冻结B/session内sequence（1..2^53-1）与derived_event_sha256，金融身份为唯一mapper给出的canonical_key和derived_facts_sha256。identity_signature由Standard按真实P8身份view取得classification、entrust_id、user_tag与原字段中经过Common完整token验证的SDK token；使用固定JSON数组编码。order另在同一签名加入唯一mapper的WTS对象原volume/price/direction/offset/business_type/exchange/code/orderDate等不可变规范字段，不能重复解析源金融行或计算新的仓位。trade同key异facts，或同金融身份异管理/不可变签名均冲突。允许签名缺失的external/unresolved表示保持真实分类及空管理身份，不能借相同金融值掩盖来源token冲突。

索引保留order已交付的有限规范快照，精确旧快照再次到达时抑制；同key真实后继active快照可交付。order_filled只取mapper生成的getVolTraded用于单调性检查，不生成/修补任何金融值；新快照filled低于此前已交付值拒绝。终态后此前从未见过的异快照拒绝，避免再次计取消；不猜来源版本或自动纠正乱序。trade同key同facts且同签名仅交付一次，即使运输sequence不同。任何已知same-sequence的新内容或kind不一致均冲突。

纯error诊断以diagnostic=true、空金融key/hash/signature准入，只占运输项；其start/finish记录诊断通知是否返回，不产生金融数组。非诊断只接受完整的金融三字符串和有限order_filled；kind冲突拒绝。每条新运输项与每条新金融快照各占一个records额度；同金融不同sequence的已返回重复只新增运输项。base逻辑字节=128+B.size()+1+session.size()+1；transport逻辑字节=96+四字符串(eventSHA/key/factsSHA/signature)各size+1；每金融快照逻辑字节=128+三个字符串(key/factsSHA/signature)各size+1。financial group/vector结构预留包括在每快照固定128中；重复key的逻辑计费可保守重复，不声称sizeof或物理RSS。无长期原页/lookup正文副本，原文通过原Host通信事实及B/session/sequence引用；在途/未知链的正文和lookup仍由Standard原临时预算保持。数量1..1000000，bytes1..512MiB，原base无法容纳时构造拒绝；运算先减后比防溢出，满额不清集合/逐出/借新额度。完全已知returned重复即使满额仍可识别，任何新运输项仍须额度。

reserve新交付先登记Reserved状态并返回绑定本索引实例的ticket；同金融/运输Reserved或Started再次reserve返回Pending，不重入SPI。start只将匹配Reserved转Started；finish Returned/Unknown只从Started转对应终态，Suppressed仅从Reserved转明确未调用。错误ticket/错误线程/重复finish不改变事实。Returned表示SPI正常返回，未声明WT金融事务提交；Unknown不自动重放；Suppressed保持未调用语义且不当已应用。独立新seq遇已有Unknown/Pending/Suppressed金融项，先检查身份、类型和成交事实冲突，再返回原处置；该次不登记新运输项或新金融快照，不伪造返回或推进handled。原项后续正常返回后，调用方可用原新seq重新reserve，按当时已返回事实判断新订单快照或重复；未准入的事实不能被提前固定为Duplicate。

验收包括同seq重复/冲突、跨seq同成交、同key异facts/身份、order正常演进/旧快照/终态后新快照/成交量倒退、wrong-thread/ticket/reentrant状态、未知/抑制、记录/字节等值与少1、满额旧重复仍可识别及分配异常无半索引。源码测试与实际运行分别登记。

## SEV-R5 真实缺字段补查

源snapshot允许省略字段，正式入口分别识别：金融必需字段确实缺失、字段原值非法、可选字段unknown。补查仅用于缺少必要事实的可核实观察；已有null/非法值不能静默覆盖成合法值，可选unknown继续沿原mapper规则。

1. 保留原事件。只有账户、证券及券商订单身份，或成交的完整作用域身份足以精确定位时，才调度该类型一次真实AccountV4查询；不能按价量、最近单或时间近似定位。
2. 补查在同一worker内用同一个原绝对D，沿Core真实receipt、原B/结果bytes/hash和唯一mapper；不重发SDK写、不新起TTL。相同待办只读取其原结果，不能无限重查。
3. 订单补查得到的是同一订单的后续真实快照。账户、标的、券商订单身份、买卖方向、原委托数量、原委托价格等不可变事实中双方实际存在的合法原值必须一致，规则复用唯一mapper的规范化与字段含义；缺少必要定位、无唯一匹配、不可变事实冲突、容量或原D失败均保留诊断，不发布补零对象。
4. 订单状态、已成交数量、剩余数量允许随真实进展变化，不要求与较早回调数值相等。发布候选使用整条真实查询行及其真实查询provenance，金融守恒/字段合法性由同一mapper核验；不将事件的旧状态与查询的新数量拼为第三条行。保留原事件及触发关联，明确这是event-triggered query的后续观察，不能称为原回调时点状态。正常从未成交到部分成交、从部分成交到成交/撤单的实际查询快照须可验证交付。
5. 成交补查仍要求精确同scoped trade与broker订单身份，双方共有的金融事实必须一致。只采用对应的整条真实成交查询行，保留其查询来源；不能把累计数量/总成交额相减、分摊或合计成新的成交，不按订单号把多笔成交合并为该事件。
6. 后续快照也沿原归属/去重/原D和SPI规则。真实policy2 ORDER查询可按已接受QST-R21Q，在原Host通信事务中保存AccountQuery关联证明；后继lookup明确区分该查询证明与原事件证明，分别保留各自provenance，不把补查结果改称原事件。该证明仍不表示成交已被持仓查询吸收；查询未找到也不证明命令未执行。

## SEV-R6 原截止、预算与公平调度

事件页任务在入插件队列前固定 SignedHttpDeadline.end。取页、owner排队、事件begin、补查、resolve、finish、SPI前检查全部沿原D；一页内较晚事件不另获完整TTL。超时后保留原诊断和已发生回调的处置，不再发布该任务剩余金融观察。下一次独立页轮询有自己的原D，不能用新轮询重新包装已有delivery_unknown或掩盖原失败。

复用实际 profile 的 max_events/max_event_page_bytes/max_event_bytes、HTTP max_response_bytes、现插件 max_queue/max_queue_bytes、request_ms、close_ms 及 P8三个有效载荷预算。每流至多一个页处理链在途；事件任务与读/命令共用原有限队列，禁止另起无限事件线程或独占循环。

现 StandardQmtTrader::Impl::publish 将完成值入队并notify_all，wait看到results非空即返回StandardQmtPumpReady；因此“空页等下一次pump”会由该空页completion自己唤醒并连续请求。调度采用现 std::chrono::steady_clock 的显式空闲cadence，worker仍只消费已入队任务。新增普通时间配置 event_poll_ms，单位毫秒，整数1..60000，缺省1000；本条定义唯一缺省，由插件init读取并冻结，部署配置可在该范围内指定。它仅限制HTTP轮询频率，不能表示交易资格、源完成或查询覆盖。源profile当前没有此配置，不从不存在的profile字段读取。

同一流状态只需next_event_poll_at、page_chain_inflight及既有游标/容量；由插件mutex保护调度状态，owner决定入队，worker返回独立值。wait只给出当时可推进事实；pump在同一准入锁内重核生命周期/inflight/到期/容量并一次登记任务，业务并发入队抢先占满时保留未准入状态，不创建失败completion。沿以下唯一时序：

1. 事件消费者沿现连接生命周期启用时，允许首个页任务在当前单调时点调度。其开始/查询交接按SEV-R8实际集成定义，轮询计时不创造完成门。
2. 一旦成功入队，置page_chain_inflight；整页的取页、全部owner处理、补查、身份resolve/finish都属于该链。任何completion、读/命令唤醒或重复pump都不能再起第二页。
3. 页链正常结束后，在owner完成原处置/释放临时额度的同一调度状态转换中设置next_event_poll_at=steady_now+event_poll_ms，再清inflight。空页同样执行此转换。非空页也适用同一间隔，避免用“页还有数据”重新形成无限紧轮询；分页吞吐与积压延迟按实际预算验收。
4. wait在请求StandardQmtPumpReady时，除既有results/错误外，将“生命周期允许、无inflight、单调时钟已到next_event_poll_at且队列和预留可准入”作为可pump条件。等待目标为调用者原wait_end与有效next_event_poll_at的较早值；每次唤醒都重查条件。只有具备准入空间时才纳入计时唤醒；队列满时等待现任务退役的notify或原wait_end，避免已过期的timer造成CPU空转。其他flags的等待行为保持。
5. cadence到期可返回现StandardQmtPumpReady，pump每次最多提交一个新页；现StandardQmtDeadline仍只表示本次wait的timeout_ms耗尽，并非业务任务超时。wait不发HTTP、不调用SPI，且timeout_ms=0仍为非阻塞检查。业务completion/stop可提前唤醒，但不把next_event_poll_at提前，也不因轮询尚未到期延后已有结果处理。
6. 页任务的业务D只在该页成功准入队列前由同次steady_now+原request_ms冻结。此前空闲等待没有在途业务任务，不能记为该页业务Timeout；入队后的排队/HTTP/owner耗时都扣同一D。wait自己的超时不改该D，cadence也不授已有任务新TTL。
7. 合法gap页沿SEV-R7保持正常页与有限cadence，继续观测实际prefix；它不进入运输失败分支。真正失败沿原Status/诊断处理，不按成功空页重新排同一失败链。资源不足时保留未准入状态、等额度真实释放，重复pump不无限创建失败completion；已有delivery_unknown保留且不重放。stop/detach清除后继调度资格并唤醒wait，所有已开始操作沿原close D处理。

原wait的输入flags/返回bit值和C ABI签名保持，PumpReady扩展为“有完成值或有可准入的到期调度工作”。新消费者未装配时保持旧谓词。宿主可继续wait→pump；pump先处理已到的读/命令/关闭完成值，后尝试一个事件页准入，同一worker队列中已排业务任务先于新事件任务。事件resolve/补查沿同链原D和额度接回队尾，不插队延长业务截止。空闲HTTP计数、混合负载公平性和可观察延迟必须在实际验收记录，不能只观察低CPU或空页成功。

去重记录需要独立显式资源额度，建议增加 max_event_delivery_records 与 max_event_delivery_bytes 两项普通插件配置，无资格含义：数量为1..1000000，字节为1..现max_queue_bytes。实际装配事件消费者时两值由部署资源配置显式提供，不设隐藏缺省；未装配的旧查询调用不要求它们。额度在init一次冻结，从现 max_queue_bytes 总预留中显式划分长寿命占用，不能作为该总额之外的附加容量；不占用Host既有事件表预算，不从空闲读/命令额度静默借用。总预留必须留下既有读/命令任务与一条事件链的实际空间，数量额度计算运输项和金融项占用，不能将两套索引藏为零成本。静态配置关系在init开线程前检查；依赖远端profile的最大页/单记录关系在worker真实prepare后、首次事件任务准入前检查，失败按原受控关闭保留owner。不得假定init已知道尚未取得的远端profile。

逻辑计费包含来源身份、key、摘要、实际保留页/补查/lookup诊断和每项固定索引预留；同一页bytes仅计一次，引用有固定成本。临时原页、Candidate、Plan、Resolved并存时都在现队列总账中有预留。额度描述逻辑有效载荷，不声称等于分配器/进程物理内存。满额不逐出本实例已经交付的去重事实，不用清集合换继续处理；同项重取/诊断仍可用，新增观察报告背压。具体固定索引成本在实现冻结时明确并测临界值。

## SEV-R7 归属、错误、stop与可观测性

合法gap页必须保持status.ok()==true及gap==true。gap表示实际来源缺口，不能仅因gap丢弃页中已完整验证的连续prefix，也不能让它跳过账户/身份/金融/原D校验。

Standard看到合法gap后，在触发任何后继SPI或可重入回调之前，先在本实例状态锁下设置sticky缺口状态、阻止后继新写并标记降级，再释放锁处理已验证prefix；账户四查询继续。该状态控制本实例后继新写的准入；已受理/已派发命令保留原身份和阶段，不倒改结果、不假称停止已经进入SDK的调用、不隐式撤单。Common纯codec只报告gap事实，不拥有插件写开关。

页内真实连续prefix继续沿唯一mapper、身份核验、volatile去重和锁外SPI交付。read_cursor只到实际读取的连续prefix，handled_cursor只到有明确处置的连续前缀；不能用gap.sequence、observed_published_through、durable或source_ack将未收到/未交付的项补成已处理。gap前已在途票据可能随后完成并成为真实可读prefix，因此在原有限cadence下继续观察，实际新页各有其独立入队D；已有在途处理仍用原D，不因gap续期。新的真实prefix只有通过同样完整准入后才能交付。

gap后的空页、源ACK推进、短暂正常状态或新页gap字段变化均不清除sticky状态，不自动恢复新写，也不表示恢复完成。恢复与首次query/live cutover及跨进程覆盖仍按SEV-R8明确缺口处理；本切片不增加“清gap后重试”命令或资格配置。显式stop/detach、运输/身份/金融失败及原D规则仍适用，不能以继续观察为由维持失去资源所有权的无限循环。

owned/external/unresolved/conflict沿STQ-P7。真实外部或未恢复归属的金融观察保留原金融批次和空身份槽；不能据它们恢复自有未决命令，也不创建整批查询资格门。conflict/运输错误/原D失败不给该处理的可发布数组。orderError没有官方独立完整token保证，保留账户/源诊断；仅有明确原命令关联与确定失败事实时才对原委托发确定拒绝。

首次stop沿P9冻结原close D。停止新事件页/补查和新业务入队，owner收回Candidate，worker保留已开始I/O及晚回调owner并真实drain/join。stop/detach之后的金融completion不再调用SPI；已开始的SPI允许按原生命周期返回并登记处置。回调内stop只登记，不能自join。未交付/unknown原事件仍在Host，停止不隐式撤单、不推进源ACK、不清持久事实。关闭超时保留真实owner/DLL，不以线程标记代替回调结束。

状态诊断至少区分页取得、映射/补查、身份未决、重复抑制、SPI开始/返回/异常、停止抑制及原D耗尽。输出有限来源B摘要/session/sequence、kind、处置、原页/查询/lookup诊断引用；账户/原正文进入受控记录，普通日志不展开敏感数据。源持久、源ACK、C++handled与SPI returned分别展示，不能合并为“交易已完成”。

## SEV-R8 查询交接与恢复缺口

四查询继续沿原 TraderAdapter 的position→orders→trades→account链独立完成，查询的原结果不因事件暂存被伪造或拼成原子四快照。原查询成功与实时增量覆盖是两项事实。

固定Adapter的onRspTrades只累计统计/checkSelfMatch，不增减持仓；onPushTrade先改持仓/undone并回调，之后才checkSelfMatch。相同TradeID/RefOrder返回false不能撤销前述应用。因此“查询trade集合已出现则过滤所有晚回报”没有足够覆盖保证：position先读100、之后成交+10、trade查询含该笔时过滤会留100；position已含该笔读110、晚回报再push会成120。

以下待决项由源接入与标准插件集成共同完成，不转为用户审批或任意newqual开关：

| 缺口 | 需要核实的真实事实 | 影响/后续动作 |
| --- | --- | --- |
| 首次query/live cutover | QMT查询和回报的覆盖/排序/补发完成依据；是否有实际共同标记或可验证的单查询交接协议 | 当前文档没有保证；在明确真实方案前，隔离稳定流链可实现，完整生产启动交接仍未验收；不编造共同水位或强制源提供原子四查询 |
| 快照已含、回调迟到 | 可区分已吸收与新增成交的真实证据 | 单凭本地sequence、UTC区间、空页或静默时长不足；需真实交错验收 |
| 同实例网络断开 | 原WT实例、原B/session、原游标仍在且已保存事件前缀连续 | 可按原游标重取已知未交付项；不重复初始化统计，不重放delivery_unknown；当前恢复接线需实现和验证 |
| Agent/Host换代 | 新旧B/session以及源回报是否完整、原关联证明的实际范围 | 保留旧流，禁止继承前沿或用新源自动覆盖旧未知 |
| 新C++进程 | 新WT查询基线包含的事实及旧SPI应用情况 | 原事件持久/源ACK都不能证明WT已应用；不能盲重放历史增量 |
| SPI返回与进程退出窗口 | 消费者回调与持久事实之间的真实提交关系 | 当前无共同事务；记录未知。新增Host消费票据若后续必要，另接受独立规格，不在本切片偷偷加表 |

实现不得给这些缺口填常数“基线完成”、fakeAccountResult或新qualification字段。真实SDK有限观察可以提供特定输入证据；未覆盖的顺序/重启不提升为普遍exactly-once承诺。完整切片的生效范围必须对应实际已闭合的交接场景；未闭合项保持本规格proposed范围中的缺口，不回写既有P9/P7通过结论。

## SEV-R9 兼容、集成与回退

旧账户v2/v3金融views、P7身份结果、P8单线程包装与三阶段生命周期、原HTTP/SHM协议、Host事件/关联存储和源SDK调用入口保持。旧查询调用不要求新增事件预算；事件begin复用原P8显式预算，长期交付资源在Standard消费者装配前冻结。补查使用真实账户2.0版本，不升级旧receipt。Common接缝按SEV-R2、mapper规范输出按SEV-R3、独立事件provenance/mapper/begin及其临时逻辑计费按SEV-R2b accepted切片实施；Standard长期索引计费、首cursor和完整交接仍须后继冻结。

必要产品接缝限定如下：Common按已接受切片实施；其余后继接缝完成各自冻结与接受后再按所有权实施。本提案没有已证必改WT核心项：

| 自有模块 | 必要接缝 | 需保持的原行为 |
| --- | --- | --- |
| QmtHostTradeClient.h/.cpp 与现 Common codec | accepted切片：QmtTradeEventPage尾附真实profile/read_result_capacity/actualHostcap；RequestBounds放Common，纯validator显式可信expected/descriptor/cap/原D并产独立DOM；实际HTTP仍由原events拥有 | Host请求/响应协议、事件receipt、EOF/原D/原状态、旧页诊断入口保持 |
| QmtAccountIdentity.h/.cpp | accepted SEV-R2b：独立事件begin、provenance及统一rows/transport Plan，私有ticket区分来源并复核原session | P8 handle类型、resolve/finish签名、错owner/ticket双句柄保留、原query结果bytes与默认预算保持 |
| AccountMapping.h/.cpp；ShmAccountMapping查询接线保持 | accepted可选canonical及SEV-R2b独立map_trade_event_rows入口，沿原canonical/seen和唯一金融循环产生 | query的Core receipt/UTC验证仍由原Shm入口负责；event没有查询封套；原金融算法与默认views不变 |
| StandardQmtTrader.h/.cpp | 原Task/Completion携实际bounds/page纯值；一条event链、长寿命volatile交付索引、cadence及wait/pump谓词；原owner Candidate表/worker客户端复用 | 单worker、原业务队列/原D/锁外SPI、现C ABI和stop/drain所有权保持 |

私有PlanData应保存已准入行的独立DOM与来源种类，公共输入的page/profile/bounds均不被借用；不能为沿用当前data.rows访问方式临时包装成合法account-batch或补造request_id/result_sha。查询路径原ticket字段及输出保持，事件诊断中的这些查询专用字段明确不适用。事件来源的session比较复用现same_source校验处，事件模式传实际原session，查询模式保留原约定。

普通配置仅本提案的event_poll_ms和两项交付索引资源额度。无新网络client、线程、SDK函数、WT虚接口或金融数据库。Host/Agent现回调、事件存储/ACK/R21和HTTP协议继续原实现。旧ManagedTrader不作为本事件链旁路；生产Factory继续按标准插件规格与实际验收独立接线。

回退关闭新事件消费者装配并保留原Host事件/命令数据，不能删除原事件或清库“恢复”。已发生但未确认的SPI处置保留未知，回退不使它变成可重投。实际部署与源订阅/生命周期仍沿原流程登记，本文件不授权真实委托、撤单或发布。

## SEV-R10 验收矩阵

验证复用现固定08b230原Adapter、标准插件候选、真实Host/Agent替身和HTTP入口；SDK使用能记录实际回调/调用数的替身。源码测试定义不等于已执行通过。

| ID | 场景 | 必须观察的结果 |
| --- | --- | --- |
| SEV-R1 | callback→原Host事务/R21→HTTP页→三阶段→SPI完整链 | 原页/查询原文可核；金融数值来自唯一mapper；worker不触碰WT/BaseData，owner释放候选 |
| SEV-R2 | page字段与正文冲突、错schema、profile空/错SHA/错容量、错可信binding_id/B/session/账户、实际Hostcap小于profile上限、错原请求边界/index/kind/序号/前沿 | 同一codec按对应规则拒绝，SPI为0；不能从receipt反取expected或以profile扩大Hostcap；任意一致伪造JSON不被声称为Host来源 |
| SEV-R2a | Common独立DOM寿命、失败out不变、原空页/409/截断/晚D/历史source诊断、合法gap连续页 | 原events五参及body字节保持；HTTP错误不进入成功codec，gap保持成功事实；历史页读取与owner当前金融准入分列 |
| SEV-R3 | 原查询金融/身份样本及预算临界；真实完整event | 旧v2/v3/P7 bytes和P8结果保持；事件无伪queryUTC；规范key/hash仅唯一canonical产生 |
| SEV-R4 | 同页重取、不同seq同成交、同key异文、订单重复取消与后继状态 | 真正SPI次数/原Adapter持仓和undone正确；冲突可见；derived不冒充source SHA |
| SEV-R5 | 缺必需字段/可选unknown/null非法；订单补查唯一匹配且状态/成交/剩余真实变化、不可变事实冲突；成交同scoped trade或多笔/合计反例 | 原D不续；合法后续订单整行和查询provenance可发布，不混合字段；不可变冲突拒绝，成交禁止合计补造；原事件保留 |
| SEV-R6 | 每阶段队列等待、页/记录满额、原D已尽、同页后段超期、读命令并行 | 预算连续、背压保留事实；读/命令得到实际进展，超期剩余SPI为0 |
| SEV-R6a | 真实wait→pump循环连续空页、业务completion/伪唤醒/重复pump、非空分页 | 以可控steady时钟核在完成时点+poll间隔前新HTTP为0；到期且可准入只增1次；没有新增轮询线程/空页自激 |
| SEV-R6b | timer到期队列满、额度释放、wait返回后并发业务抢占容量、wait超时/零超时、stop与到期竞争 | 满额不CPU空转/不创建失败循环；释放后一次准入；Deadline仅wait超时，到期PumpReady与业务D分别断言；stop后新HTTP为0 |
| SEV-R7 | SPI重入查询/重入pump/detach/回调内stop、worker晚回、drain超时 | 至多一次领取；停止后无新SPI；所有权和真实join/保留按原D；不隐式撤单 |
| SEV-R7a | 合法gap页含完整连续prefix，SPI重入新写/账户读 | Common保持status.ok与gap；首个后继SPI前sticky阻新写/降级；账户读继续，prefix正常映射去重交付；游标只推进真实prefix |
| SEV-R7b | gap前在途票据晚完成形成新prefix，随后空页/源ACK推进/页gap变化 | 原有限cadence继续读取真实prefix并去重；原在途D不续；sticky不清、新写不恢复、未知不冒充恢复完成 |
| SEV-R8a | position前成交、position后trade查询前成交、position已含但回报晚到 | 明确实际覆盖依据；核两交错的最终持仓/统计；未知不能被channel_ready掩盖 |
| SEV-R8b | HTTP断连同实例/新B/session/新进程/SPI前后退出 | 分别核游标、源持久/ACK、SPI returned；不自动重投未知；已证范围单列 |
| SEV-R9 | 未装配事件消费者的旧查询与Factory/原D/关闭链 | 既有结果和资源归属保持；新预算无隐式旧调用要求 |

真实SDK还需核实际字段存在、完整token回显、回调顺序/重复/迟到和终端生命周期。四查询cutover及跨进程应用未知必须有独立验收结论；本地正常流与重复抑制通过只授其对应范围。

## SEV-R11 标准候选完整字段事件消费（accepted实施范围）

用户确认继续开发查询与回报正确交接的完整目标。本节先装配标准候选的完整字段稳定流；它是整体实现步骤，不替代SEV-R5缺字段补查或R8生产启动/重连覆盖。生产Factory仍旧，event_consumption_complete保持0，不新增baseline_complete/用户资格开关。已知基线后的增量必须在固定原版WT实际Adapter中验正常归约；首次查询/迟到成交两种交错的真实源覆盖仍须独立闭合。

### 启用、上下文与资源

原配置缺少两项event delivery资源时保持旧查询/命令/生命周期，不调度events；任一event资源出现时必须同时提供max_event_delivery_records和max_event_delivery_bytes，读取普通event_poll_ms（缺省1000）。资源存在表示装配候选功能，无交易资格含义。四查询返回只作首次消费者调度的流程标记，绝不证明持仓吸收范围、原子四快照或开新写的额外条件；旧写入口仍沿原登录/正常准入。

max_event_delivery_bytes作为原max_queue_bytes中的预留分区，不能另加到其外。init开线程前冻结并检查静态预算，保留普通读/写任务空间；初始成功prepare取得真实context后核远端关系。Common上下文预留可保守使用4*私有HTTP接收上限+512覆盖其四个独立字符串与逻辑固定部分，无需复制Common私有魔数；此处是内存上界，不将HTTP上限冒充实际Host页容量。Prepare/Login在原task中替换同一次trade.prepare为prepare_event_read_context，不增加重复准备I/O；成功值移动交owner持有，实际值计费在任务→持久上下文交接时连续，不漏计并存值。

首次bounds after_seq=0、limit取真实descriptor.max_events、max_bytes取真实Host已准入cap（并核不越profile与HTTP上限），不拿源ACK/durable表示WT应用。该起点仅授本候选隔离稳定流范围，不授历史回报盲重放生产资格。若实际预算无法容纳一条最大源项/请求页，明确容量失败，不改小请求循环试探。

页链的保守逻辑reserve冻结为3*max_bytes+4*context_reserve+3*P8.max_total_bytes+2048；另留一个普通任务预算ordinary_reserve=8*HTTP上限+3*P8.max_total_bytes+8192。init核静态partition/基本任务条件；远端context到达后要求总预算同时容纳delivery分区、context_reserve、页链reserve、ordinary_reserve及任务固定预留。该式覆盖原页/独立值/候选/Plan/Resolved并存，描述逻辑有效载荷，不等于RSS。必要资源不足返回明确原因，不动态借索引分区或清去重事实续跑。实现的固定控制任务512仍单独计费，临时链reserve和长期分区只计一次。

### 原worker、owner与回调

只扩展现有Task/Completion和唯一worker，不新增轮询线程。worker取页前在同一原D prepare当前context，核原B/session/profile及请求实际cap，再调用原events，回送完整独立page。source变化/HTTP失败沿原Status，历史源读取能力不自动成为当前金融准入。取页、所有页项begin/resolve/finish及SPI前检查都沿成功入队时冻结的同一absolute D。

owner保留一份显式EventChain（page/context/bounds/D/index/预留/最多一个Candidate），worker只拿纯值Plan，逐条使用现事件begin→原worker resolve→owner finish，不把Candidate/Base/WTS交给worker。不得一次创建整页候选，页后项不获新TTL。已在途事件任务完成值优先按原pump处理；页续阶段入原业务队尾，先前读/写任务先行。

任务名额在每次终态回调前按现TaskCredit退还。页余项为一份已计费owner continuation，下一项要先在同一准入锁中取得新task名额/512控制预留，才构造begin并将Plan放回队尾；并发业务抢占时保留continuation，不分配失败completion空转。第一页取得后的首项可转移当前task credit到Resolve。所有可抛构造/索引/身份记忆在SPI前完成；无业务锁时才调用onPushOrder/onPushTrade。回调内queryAccount等按原队列准入，重入pump拒绝。

完整项finish后只取唯一mapper的canonical和WTS对象生成R4a交付观察，恢复原管理身份后remember原委托；不重复解释源金融字段。交付索引reserve→最后generation/D/stop/detach检查→实际callback lambda内start→原SPI→finish(Returned)。回调异常标Unknown；明确未调用保持Suppressed。重复只识别Returned事实；Pending/Unknown不自动重投。error项只有有限原诊断通知和运输处置，不虚构原委托拒绝。

合法gap先在原状态锁中sticky阻新写，再进行任何可重入通知/金融SPI；继续交付真实连续prefix和后续合法新prefix，空页/源ACK推进不解除sticky，四查询继续。缺字段/非法字段目前保留明确失败，完整补查按R5后继实现，不补零/拼行/伪查询。完整流失败不作为空页自动重试。

### 调度与关闭

每流最多一条page链。正常整页/空页结束时，在同次受锁状态转换中释放临时reserve、设置next_poll_at=now+event_poll_ms并清inflight；后续pump/普通completion不提前cadence。wait不发HTTP/SPI，原flags/C ABI保持，只有timer到期且可准入或已计费continuation可推进才返回PumpReady；queue满不对过期timer忙等，原wait截止与业务D分别处理。continuation的原D到期可唤醒owner完成失败处置，不能因满额永久不检查D。

stop/detach取消新调度和新SPI；Candidate始终owner退役。worker仍持有Plan/结果时保持页链reserve及纯值owner直到实际work/drain结束，不能提前返还其借用预算。release按现原close D保留超时owner/DLL，实际join后清链/索引/上下文及其计费，原pending收据保留规则不变。客户端线程、源ACK、Host持久和SPI returned分别表达。
显式registerSpi(NULL)属于正常detach处置。成功的在途Query在owner阶段直接抑制后继映射/回调，不调用已撤销的SPI或BaseDataMgr，不把正常detach伪报为依赖I/O故障。已进入Resolve的成功结果由owner退役Candidate及其预算，纯值完成结果销毁后归还本结果额度/任务名额；不继续finish/remember/SPI。当前真实generation、原D、运输失败、缺Resolved和Resolved失败仍先保留对应错误事实，不能被detach分支吞成成功。正常detach自身不触发故障关闭；显式stop/release仍沿原生命周期。此规则同时覆盖查询与事件Resolve，写命令事实及原pending不变。


### 本节必须实际验收

固定纯上游WT+自有候选DLL实跑：真实取页/owner→worker→owner→SPI；已知非空基线100后新增20最终120，重复同seq/跨seq成交仍120；订单重复取消不重计、合法部分成交→取消；真实HTTP连续空页cadence/分页/普通查询公平性；资源records/bytes边界；gap先阻写再回调且账户读继续；来源变化/非法/缺字段/原D失败无剩余SPI；回调重入查询/pump/stop/detach和关闭超时保留/最终回收。旧16场景及关联Common回归按实际影响重验。每项未执行明确保留，不以索引单测代替Standard实际装配。


## SEV-R12 共享内存事件至原生Adapter组合验收（accepted验证范围）

本节把R11已实现的完整字段稳定流接到真实RestrictedTradingAgent、Windows命名共享内存及build_trade_runtime。它只扩展隔离验证，沿原协议和实现，不改变R5/R8未闭合范围，也不新增终端策略、生产Factory或WT框架修改。源SDK为可记录原线程调用的替身；真实券商下单/撤单、终端重启和生产切换均不在本验证动作内。

验证固定原版08b230 TraderAdapter及原标准候选DLL。源端四查询先给出已知的合成持仓100/可用100、账户资金及空当日委托/成交；Native观察原Adapter进入Ready后才发起本次新增委托。这是该夹具明确控制的先后事实，不表示生产查询与回报具有共同水位。委托由原Adapter.buy产生原localid/EntrustID/UserTag，经过标准orderInsert、真实签名请求、Host原命令事务和原源线程SDK替身；身份关联必须来自该原命令及回调，不预填Host证明表、不编造SDKtoken或管理标签。

SDK替身同步回调完整部分成交委托及20股成交，源回调→原事件缓冲→SHM→Host原事件事务/源ACK→同标准插件唯一worker读页→owner/worker金融及P8→原SPI→原Adapter归约。原页、原源字段、B/session、原UUID和R21证明可逐项回读。源持久/ACK与WT SPI次数分别验，不用独立客户端代替标准消费者。

正常模式的预期是原生持仓由100到120，可用量仍100，委托未成交数量从100到80。随后由原Adapter.cancel(localid)经标准orderAction/原lookup到真实源cancel替身，原回调发完整部分撤单；最终WT未成交数量为0、无活动委托、持仓仍120。insert/cancel替身各一次，SDK实际调用为0；初始position→order→deal→account及成交后原生账户自动查询按真实入口记录。

跨seq重复模式在相同源SDK回调入口重复发送成交、取消及已见订单快照，保留真实不同运输seq；最终金融归约和原委托数量保持正常值，SPI仅交付唯一成交及合法订单进展。回调stop模式在新增成交的原SPI栈请求停止，保留当前借用，后继回调和新命令均受原stop规则，未发取消不能记为已撤；该模式的实际SDK次数和残留委托事实分别登记。模式不得通过删事件/改持仓/预填身份/延后到虚构安全点取得通过。

所有源SDK入口须在原fixture策略线程，WT/BaseData/SPI在插件owner，HTTP/纯值关联在唯一worker。混合队列沿原D/容量/有限cadence；有效字段、数量、价格、时间、交易日和用户标签逐原值验。构造后立即登记清理；全局截止覆盖启动、原命令、页处理、停止、drain、join、DLL删除及Host/Agent/HTTP资源回收。首次关闭D保持，超时保留真实owner，不能重启子进程来冒充同一次通过。

实际编译、测试、独立审查与原件SHA分别记录。已有R11成功模式按原输入范围复用；新增组合测试通过不能授予真实SDK字段、生产初始/重连交接或跨进程exactly-once保证。


## SEV-R13 同实例事件读取有限运输恢复（accepted实施）

### 目标、根因和范围

本节解决同一Standard实例在有效事件页取得之前的一次真实运输中断导致整通道永久停止的问题。Common当前单次返回运输失败，Standard owner将EventPage非ok统一fail；恢复在自有插件与通信边界实施，保持原WT Adapter、mapper、金融归约和生产Factory。

适用前提是本实例已有已验证context和稳定事件消费，尚未取得本页有效page、尚无该页Plan/Candidate/SPI。真实线路为GET read-binding、GET trade-status、只读POST trade-events；最后一个POST仅查询Host原持久事件。恢复只适用于这三跳的显式事件读取调用，不推广至交易submit/resume、账户查询、EventResolve或SPI。初次query/live共同覆盖、长断线缺页、新源/新进程和跨进程应用恢复仍按R8保留缺口；不得由本片授予新基线保证。

### 固定类型和单次Common接口

BoundedSignedHttp.h增加固定POD SignedHttpFailure，包含recovery（None默认、TransportInterrupted）、origin（None、NativeTransport、IncompleteBody、RemoteHttp、Deadline、LocalOrProtocol）、native_error:uint32、native_operation:uint64及实际HTTP阶段。SignedHttpResult尾附该POD；Status及reason继续表达原诊断，不承担重试分类。POD构造、复制和移动均无分配。

默认与未知错误一律不可恢复。允许TransportInterrupted的最窄集合仅为真实WinHTTP ERROR_WINHTTP_CANNOT_CONNECT、ERROR_WINHTTP_CONNECTION_ERROR、ERROR_WINHTTP_TIMEOUT，以及合法且已声明Content-Length下实际body严格少于声明长度的提前EOF。大于声明长度、容量、头部/JSON/编码/协议、认证、TLS/证书、DNS、重定向、crypto、本地setup、分配/其他异常、wait内部错误均不在允许集。HTTP code已经可见且非200时整次不可恢复，包括错误正文再次截断；完整202/204/408/429/500/503/504在本事件读取中均为非200终态。通用HTTP层对业务202的合法语义保持；事件入口必须返回非ok状态，禁止非200返回ok加空页。原D耗尽、原线程错误和stop独立终态。

同步原生错误仅捕获一次GetLastError；异步REQUEST_ERROR核WINHTTP_ASYNC_RESULT指针及长度后复制实际dwError/dwResult，形状错误归LocalOrProtocol。WAIT_FAILED与真正原D耗尽分别保存；异常出口清除恢复许可，不能沿用先前事实。可恢复分类必须来自底层实际分支，禁止由Status/reason字符串或send_attempted反推。

WinHTTP回调ABI边界及其异常终止路径必须不抛异常。catch先清TransportInterrupted许可，以ErrorCode标量、空或已预建原因和无分配move提交失败并唤醒原event；禁止在catch里重新构造诊断字符串。若mutex或清理路径本身失败，使用不依赖该失败锁或动态分配的固定终态通知保留真实owner及原D，由原持有者完成排空，禁止异常越过callback ABI、伪成功或重试。测试须在REQUEST_ERROR已捕获原生分类之后注入持续及后继new失败，确认异常不逃出回调、固定不可恢复事实保留、原owner真实关闭；正常网络中断分类不受本地分配异常伪装。

QmtHostTradeClient.h增加固定POD QmtTradeEventReadFailure，保outcome（None默认、Failure、ControlStoppedBeforeStage）、stage（None、Binding、Status、Page、Publish）、SignedHttpFailure、http_status、send_attempted、response_complete。旧prepare_event_read_context(D,out)和events(source,after,limit,max_bytes,D)符号/调用形状保留；新增重载各尾附QmtTradeEventReadFailure*和const QmtAccountControl*，无默认参数歧义。QmtAccountControl沿已有QmtHistoryControl原子停止值；Standard持专用event_control，不能复用会中止普通账户查询的同一个实例。

旧重载和普通prepare/业务命令维持单次机制；Common不循环。新event-only重载共用原prepare/refresh/events认证、版本pin、B/session/profile/cap和页校验，禁止复制一套协议解释。每次入口先把failure置默认不可恢复；成功、协议失败、错owner/D/stop、异常都不得泄漏上一轮许可。prepare失败/异常保持out原契约，旧out不能当成本轮成功。每跳之前及成功发布out之前核原owner/D/control；原owner/D错误先独立保留。仅本地control已停止、下一阶段尚未准入且此前阶段完全成功时，产生ControlStoppedBeforeStage（包括Publish前停止），它没有TransportInterrupted许可。已经进入的exchange先完整取得并校验真实结果；其运输/HTTP/协议/解析错误保持Failure，禁止由同时到来的control覆盖。停止只关闭尚未准入阶段，已经进入的exchange仍由原D和HTTP owner排空。

### 原owner状态、原D和资源

EventChain显式区分ReadInFlight、ReadRetryWait、PageReady、ResolveInFlight，不把失败设置为空页ready后结算。仅Kind::EventPage真实固定类型、原ticket/generation匹配、原D未尽且完全没有有效页/Plan/Candidate/SPI时进入ReadRetryWait。原B/session/profile/read_result_capacity、请求bounds、read_cursor、handled_cursor、交付索引和chain reserve保持；unknown/hard/gap/close事实保持sticky，不通过恢复解禁。

每次失败完成值真实析构后归还本任务512与TaskCredit；链reserve持续保有。下一次只在原event_poll_ms到期且有原FIFO名额/512时复制同context/bounds、取得新本地task ticket并排原业务队尾；不建新业务UUID/receipt，不改limit/max_bytes，不重login/四查询，不刷新chain.deadline。下一轮完整prepare两GET核同代后才读原bounds的POST页。有限cadence与原request_ms给出尝试上界1+ceil(request_ms/event_poll_ms)，运算检查溢出；只计实际进入读取的尝试，排空检查另计固定有限计数，不保存历史正文。

晚WinHTTP回调仍可能持有原upload/body/buffer，64项drain表只限制资源数量。worker在失败后及下一次读取前使用同一个trade client的drain_callbacks(0)核真实排空。Pending保留旧HTTP owner和chain reserve，交回固定失败/排空待定事实，owner按同一cadence重新排一个FIFO检查任务；Pending任务不发任何HTTP，不让唯一worker在整个恢复窗口等待。排空成功后才允许新读取，其余drain错误终态。失败局部context/body/完成值先真实销毁再退费；原回调持有的借用额度持续到真实drain，禁止累计多轮未计费载荷。

wait/event_ready/event_wake在原mutex下按phase判断。RetryWait在D尽时即使队列满也唤醒终结；D前到期无名额时等待额度notify或原D，禁止过期timer自旋。普通query按原FIFO和各自D进展；普通completion/pump不得提前恢复cadence。Task复制/预留/发布异常按真实容量或异常终态，不冒充运输失败。新固定POD/phase/time_point/计数纳入既有固定控制预留；原逻辑payload公式不变，不增加第二金融账本或错误正文队列。

有效page仍只在原accept_event_page校验成功后推进read_cursor，逐项原begin/resolve/finish/SPI成功才推进handled_cursor；从此不适用本读取恢复。完整gap页沿原prefix规则处理，不能改为retry；不同B/session/profile/版本/cap不满足原请求界限时终态。真实终态EventPage错误在worker交付前锁存既有hard_fault/writes_blocked并停止取后继任务，owner再通知SPI及停止；worker不访问SPI/WT。本地ControlStoppedBeforeStage独立于真实终态：worker只交付固定停止事实，owner核该实例原stop/detach控制已成立后正常退役，不触发hard_fault、WTE_Close或停止仍允许的普通Query；无对应控制则为真实不变量错误。实际Failure不因event_detached而被吞。原D尽只报一次终态，顶层Timeout与最后固定运输事实分别保有。

stop/registerSpi(NULL)设置专用event_control并notify，RetryWait不重排。每跳准入与stop用明确原子读取线性化语义，已准入exchange保持原截止；不声称已进入原生调用可以瞬时撤回。成功在途结果按原detach规则抑制；真实失败不吞为成功。超时close保留原owner/DLL/charge，真实join后才清链和索引。

### 验收和资格

保持原R12合成已知基线100，实际Host/HMAC/Win32 SHM/Agent原线程SDK替身接固定原版Adapter，完整链证明下列范围。每项记录实际原生错误码、页请求与bounds、原D、页/handled游标、SPI/SDK次数及真实资源关闭。不能只手填POD证明网络分类。

| 组 | 真实触发与必要断言 |
|---|---|
| 基本恢复 | 稳定初始化后分别丢Binding/Status/非空Page响应；仅重新事件读取，login/四查询不重放；原持仓120/可用100/撤后undone0，insert/cancel替身各1、成交SPI1 |
| 前缀 | 已投prefix后下一页断流及跨seq重复；Returned不重投，未投连续项各一次，Host持久/源ACK与handled分别核 |
| 非恢复类型 | 完整202/204/401/403/409/429/500/503/504及错误正文截断、坏JSON/hash/B/session/profile/版本、非法头/超cap/安全及异常；本失败不进入重读，保原诊断 |
| 原D/公平 | 连续中断至原D、cadence前pump、队列满及释放、普通query在等待期间进展；D恒定、有限attempt、无自旋、终态后新写HTTP0 |
| 生命周期 | 三跳之间stop/detach、RetryWait停止、真实晚回调guard；未drain时新读取0，close过D保owner，释放后实际drain/join |
| 容量/异常 | need/need-1、context复制/new失败、回调跨cadence；失败不获恢复许可、无半Task/负charge、借用真实结束前不退费 |
| 边界 | 恢复后新B/session/profile、有效page之后EventResolve/SPI异常；不跨界套用读取恢复、不伪造源ACK为WT已投 |
| 兼容 | events disabled、原命令lost-submit/source-unknown、UC核查/定向取消、旧账户V3/V4及Common单次接口保持原行为 |

本片只修改自有HTTP/Common/Standard及其工具/测试，全部受影响自有消费者重编。生产标准DLL不包含故障注入hook，专用测试库独立；固定上游与26项既有框架保护清单核对。真实交易、终端重启、生产Factory切换及新增WT核心改动仍按原授权边界。实现、编译、独立审查、动态及生产首次交接分别登记。


### R13-B 前缀恢复与跨页重复成交的组合观察

沿R12同一真实Host/HMAC/Win32 SHM/原Adapter夹具，先由初始四查询建立已知合成持仓100，再真实insert产生序号1订单、2成交20。owner确认原SPI返回、持仓120/可用100/undone80，并观察本Standard实际发出的after_seq=2空页后，才由原Adapter.cancel(localid)触发源线程替身依次回报：序号3为原成交重复、4为新撤单进展、5为原已见订单快照。源端仍通过真实on_deal/on_order分配运输seq；测试调度接缝默认保持旧场景，代理只转发或截断真实响应。

在after_seq=2的真实非空页上制造一次提前EOF，保存Host原完整页与线上实际前缀。恢复仍用同context/B/session/profile、after_seq、limit/max_bytes和原页D，重新完整prepare后只读POST。恢复实际有效页必须包含重复成交3及尚未投递的撤单4，后续处理覆盖到5；不能把代理已收到的故障页当作Standard已接受。若实际源/Host分页未形成所需窗口，该用例失败并保留原件。

源Host durable/source ACK及source published/retained分别记录；原SPI调用数及Adapter金融结果独立核对。前缀与最终检查点分别记录原native after_seq请求、SPI已返回和金融值；最终订单SPI2/成交SPI1、持仓120/可用100/undone0、无活动委托，insert/cancel替身各一次，真实SDK0，全部owner按原截止关闭。跨seq重复不得重复增加持仓、重复账户自动查询或重放原写。

当前公开Standard诊断没有read_cursor/handled_cursor/Returned字段。测试以真实下一页请求、原SPI返回和金融值作联合观察，并明确内部推进关系来自单一实现源码；禁止把这些推论包装成直接私有状态快照。精确内部原D的直接观察由独立期限专项承担，前缀测试保留其实际请求时序/有界cadence与同请求界限。正常receipt的ACK前沿可在重读期间推进，事件原值与请求界限必须保持，不能误要求合法receipt整页字节完全不变。

本项仍限定同实例已知基线后的增量恢复。R8共同快照水位、重连、跨进程应用恢复及生产券商资格继续保留原边界。

## SEV-R13-D FIFO名额、原截止与owner公平（accepted 验证范围）

类型：R13已有原截止/公平要求的可执行验收补充，范围为自有Standard消费者；WT金融归约、终端协议、真实SDK与生产Factory保持原范围。普通任务的完成数量上限与原事件链截止分别成立，持续普通完成不能使事件链取得新D或无界等待。

1. 名额以真实outstanding为准，包含排队、执行和未由owner退役的完成值；queued/ready为不同公共观察。Query到Resolve转移同一TaskCredit，只有真实回调入口退名额。保持max_queue=16；测试可显式用256MiB字节预算隔离名额背压，原Candidate/Plan/链预留不缩小，不把本组当字节need/need-1验证。
2. 满16且ready0时，经过retry_at后wait(PumpReady,有限timeout)须等待真实可推进事实或本次wait/原链截止，不能对过期retry_at空转。原链D到期不依赖可用名额，下一次owner pump须及时锁定事件Timeout/写门，保留原金融状态、来源与未决命令责任。无ready场景以原GetThreadTimes与steady elapsed记录有界CPU/等待事实。
3. 在原D及cadence前，通过pump(1)真正交付一份普通Resolve、释放唯一名额，空pump在cadence前不能追加事件任务；到cadence后恰追加512控制预留及一项FIFO任务，再次pump不能重复入队。完整源查询/真实原账户SPI、最终金融和真实关闭分别核验。
4. D4根因窗口：一份真实普通Resolve在ready中，普通任务自己的D晚于事件链原D。owner在事件链已过D、普通D仍有效时调用pump(1)，即使本次普通完成预算恰好耗尽，也必须检查并锁定原事件Timeout。截止维护不能由delivered<limit这一条件无限延后。保留实际不可逆完成值、原receipt/Started/U及生命周期；不把终止当作原金融SPI已交付。
5. 先以冻结未修自有产品复现D4，失败批次保存；再在自有owner截止职责层修正并复验。未公开的链D不伪装为诊断字段：以原HTTP故障观察、完成pump起止及request_ms给出严格上下界，并证明与普通任务D窗口分离。
6. 本条只认证owner实际获得pump机会后的及时截止。owner完全未获调度时的ReadRetryWait到期，当前不由本测试推出worker自主停写的新跨线程保证；既有EventPage真实终态在worker发布前fence规则继续适用。该额外承诺须独立收敛契约、验证必要性和真实时序。

所有门沿原总D登记/释放；真实session保留/释放与普通HTTP响应门分别核。使用实际原Factory/Adapter、Host/HMAC/SHM、原线程SDK替身，公开准入/队列/字节差额与真实SPI各自取证；禁止构造假Task、假时钟或私有状态。产品/源码定义、原样失败、修后通过与完整R13未覆盖矩阵分别登记。

容量组合夹具须容纳初始查询及16份手动查询的真实通信记录；Host读Journal显式限定64条、2MiB并记录/核对实际配置，原策略线程查询和事件保留预算仍有限。该预算仅用于隔离native名额/cadence条件；native max_queue=16及所有原D不变。共享夹具的Host配置接缝默认空实现，原用例配置保持；预算不足的真实queue_full失败须保留，不能冒充消费者恢复缺陷或删减恢复金融断言。

容量组合代理显式限定1024份HTTP取证记录，默认共享代理仍256；原8MiB总字节及128个有效页上限保持。原input记录并核实际取证额度；触及默认记录容量的失败原件保留，不以关闭代理导致的运输失败归因产品恢复。

## SEV-R5a 账户请求级停止基础（accepted；完整R5待交付）

本片只扩展同一个QmtHostAccountClient/QmtBoundReadCore的调用栈控制。保持原HTTP owner、线程、receipt、Host协议及普通账户查询；完整缺字段匹配、补查预算、P8来源与Standard接续另行交付。

公开新增QmtAccountReadOutcome{None,Failure,ControlStoppedBeforeStage}、QmtAccountReadStage{None,Binding,Verify,Submit,Result,FinalVerify,Publish}，以及QmtAccountReadControlResult{outcome,stage}，均为固定枚举/POD。四个兼容重载为：

```cpp
Status prepare(SignedHttpDeadline&, QmtAccountReadControlResult*, const QmtAccountControl*);
QmtAccountPreparation create_request(QmtAccountDatatype, SignedHttpDeadline&,
    QmtAccountReadControlResult*, const QmtAccountControl*);
QmtAccountResult submit_once(std::unique_ptr<QmtPreparedAccountRead>, SignedHttpDeadline&,
    QmtAccountReadControlResult*, const QmtAccountControl*);
QmtAccountResult resume(const QmtBoundReceipt&, SignedHttpDeadline&,
    QmtAccountReadControlResult*, const QmtAccountControl*);
```

无默认参数；旧签名及其默认control行为保留。新重载即使out为空仍执行新请求级契约。request_control仅在同步调用栈借用，与构造control的停止值做OR；不保存进token、receipt、实例或HTTP回调，不重置任一停止值。停止该请求不停止普通查询。调用者保持control存活到本次同步方法返回；原HTTP回调资源仍由原client的drain负责。

每个新入口先把out置Failure/None；完整成功清回None/None。Binding为prepare/resume首次read-binding GET；Verify为prepare第二次及create/submit前read-binding GET；Submit为唯一账户POST；Result为原receipt UUID的GET；FinalVerify为终态发布前read-binding GET；Publish为本地成功token/context/data发布。每跳使用同一个原SignedHttpDeadline，先核原owner和D，再核control，已准入exchange由原D实际返回并排空。控制正常停止返回Pending/qmt_account_control_stopped及ControlStoppedBeforeStage/未准入stage，不授运输恢复许可，不证明已POST请求未执行。

真实运输、HTTP、身份、协议、业务失败优先于并发stop。已经收到的回复先完成其原校验；错误保留Failure及原Status/receipt/原件。POST回复丢失沿旧机制只GET原UUID；若真实POST失败同时遇stop，则保留实际失败并停止下一跳。完整合法202后可以在下一Result阶段正常停止。已收到源端失败终态时，控制停止不能将其改写为正常停止。所有异常保持Failure，失败结果不得带可使用data。原D耗尽保持Timeout而不改写正常stop。原UUID/receipt从提交前保留，正常停止后的恢复仅resume，禁止重POST。

旧resume在有限默认/已验容量下允许预读Binding失败后继续GET原receipt终态作审计，最终Binding验证仍决定数据采用。新请求级resume显式核首次Binding结果，真实失败立即返回并保Failure/原receipt，避免停止后再推进原审计GET；该逐跳停止契约与旧无请求级control的恢复入口分别明确。实现共用现有验证和follow逻辑，仅传递调用栈控制，不复制账户协议算法。该显式差异防止新请求把已经发生的Binding失败丢弃后继续GET。

验收使用真实loopback HTTP、公开客户端、真实账户终态校验及线程安全停止值：覆盖Binding/Verify/Submit/Result/FinalVerify/Publish边界，原D、停止与真实失败竞争、原receipt与至多一次POST、停止请求后同实例普通查询继续成功；纯定义核类型/旧重载兼容。无真实SDK、额外client/线程产品改动、P8/Standard/mapper/WT变动。测试、编译、动态、独审分别登记，静态实现不授完整R5资格。

## SEV-R5b 唯一mapper部分事实准入基础（accepted；完整R5待交付）

仅AccountMapping提供order/deal单行纯值inspection，完整map复用同一个字段解码、日期/时间/市场规范化和数量关系校验。旧map重载、views/TradeID/canonical/source_to_output及原128币种/金融样本保持；inspection不调用WT/BaseData、网络、CNG或SDK，不拥有原D/查询/身份认领。caller在调用前后继续核原D；本片不接P8/Standard，不授完整R5或R8交接。

精确接口：
```cpp
AccountRowInspection inspect_account_row(unsigned stage, const std::string& raw_row_utf8,
    const AccountBinding&, const AccountInspectionLimits&);
```
stage仅1(order)/2(deal)。输入为原单行JSON对象文本，不接受补齐/改写行。limits显式max_input_bytes（1..1048576）及max_output_bytes（1..4096），无默认。输入长度在解析前核，结构/UTF8/重复键/深度/节点沿原JsonBoundary。非法stage/binding/limits、JSON边界、容量、分配失败抛出原异常，不返回金融分类；赋值式调用失败保留caller原out。未完成检查不能报告Invalid/Missing。无原D参数或内部新钟；caller原D已尽应在其原Status层结束。

AccountRowInspection返回固定source=`guanheng.account-row-inspection.v1`、独立AccountBinding副本、AccountRowFacts、AccountInspectionKind{Complete,MissingRequired,Invalid}、required/present/valid/invalid/missing/unknown六个uint64位图、uint32 relations、locator_complete、input_bytes/output_bytes。present表示HasMember；valid表示独立字段值合法且已知；invalid只标已存在的非法值；missing=required&~present；unknown仅可选字段未提供或原规则允许的未知。关系矛盾独立标relations，不把合法单字段值删掉；任意invalid/relations或非对象行使Kind=Invalid，优先于MissingRequired。非对象行金融Invalid，仍保固定required/missing，无定位。无非法事实且missing非零才MissingRequired；其余Complete。

字段位固定：Code=0、Exchange=1、Account=2、Currency=3、Order=4、Trade=5、Side=6、Date=7、Time=8、Quantity=9、Filled=10、Remaining=11、State=12、Price=13、Amount=14、Cancel=15。仅16位有效。order必需Code/Exchange/Order/Side/Date/Time/Quantity/Filled/Remaining/State/Price；deal必需Code/Exchange/Order/Trade/Side/Date/Time/Quantity/Price/Amount。Account/Currency均可选，Cancel仅order可选；不适用位全0。原键来自QmtAccountFields：Date/Time按stage对应insert/trade，Quantity对应order quantity或deal volume，Price对应limit_price或deal price。

RowFacts每个字段使用std::optional，无缺失数值填0：code、exchange、raw_exchange、account、currency、order、trade、raw_date、raw_time为optional<string>；side/date/time/state为optional<unsigned>；quantity/filled/remaining/price/amount/cancel为optional<double>。exchange规范成SSE/SZSE；日期/time沿唯一原函数；原日期/时间文本另保留。required null/错误类型/非法值为invalid；quantity及deal price必须正，order price=0合法，filled/remaining/amount允许0，side仅48/49，state仅49..57，精确整数上限沿原2^53-1。

可选字段保持原规则：account缺失unknown，存在须与绑定字符串精确一致（null非法）；currency缺失或空串unknown（空串原值保留），CNY已知，null/冲突非法；order cancel缺失/null unknown，已知0与其他非负精确整数保原值，并核状态关联。remark/order_ref沿上层运输原标量诊断，未纳入本金融位图，绝不转作身份token。完整mapper其他可选观察facts的unknown/invalid视图原逻辑保持。

relations固定bit：FilledExceedsQuantity=1、RemainingMismatch=2、AllTradedMismatch=4、CancelMismatch=8。仅所有参与值各自valid时检查。remaining=quantity-filled；state56要求filled=quantity；cancel在状态53/54/57时等quantity-filled，其余状态为0。缺任一依赖不猜值，但所有现存其他字段仍继续检查。完整map要求解码Complete后才构造WTS；原错误reason不作为分类依据。

locator_complete是局部事实足够精确定位的布尔值，不授查询或归属资格。先要求Kind非Invalid；order须valid Code/Exchange/Order，deal另须Trade/Date；可信账户域来自独立binding参数。DEAL返回原trade作用域组成，不计算新派生TradeID；后继只沿已有scoped_trade_id及精确broker匹配，不能合计成交。ORDER缺date仍可有局部locator，后继唯一匹配/共有事实一致由完整R5另验。

逻辑占用：input_bytes=原raw字节数；output_bytes=固定256控制/标量预留，加source、binding的account/environment/currency/profile和RowFacts实际保留的每个字符串字节+各一个逻辑NUL；空optional不计，已保留空串计1。先核所有输出字符串总量后发布，checked累计且不超max_output_bytes；结果不保原DOM/raw输入。上限限定逻辑payload和既有SAX结构规模，不宣称等于allocator/进程内存，不包含完整R5查询/候选并存峰值。

验收定义须覆盖逐必需字段删除/null/坏值，missing与另字段invalid同在，所有字段扫描而非首错退出，可计算关系矛盾、optional缺/null/空/0、日期/时间/数值等价、定位不足、恰need/need-1、原文销毁后独立值、边界/资源失败不伪分类。旧金融/规范/事件mapper回归原入口保留，调用唯一解码后的完整views/规范摘要/TradeID/source_to_output保持。静态定义、编译、动态及独审分别登记。

## SEV-R5c 事件触发查询的纯匹配基础（accepted；完整R5待接线）

本接受片限定新增AccountEventMatch.h/.cpp及独立纯值测试。R5a Common、R5b mapper、P8和Standard保持原样；完整worker补查/来源交付后续按本节影响闭包另行冻结。使用WT原订单/成交与现AccountMapping金融语义，不新增金融账本、用户资格、审批或WT改动。

### 输入、输出与匹配

精确入口为：
```cpp
AccountEventMatchResult match_account_event_row(unsigned stage,
    const std::string& event_row_json, const QmtAccountResult& query,
    const AccountBinding&, const AccountEventMatchLimits&);
```
stage仅1/2。query是同次原Core已成功采用的AccountV4/account2只读DTO；账户/类型/标头/receipt/原B/原D/摘要/来源由原账户链与后继P8调用者验证，本函数的status前提检查不认证数据、不重新获得身份资格。函数只读data_json.rows数组，原完整query各字符串保持原值；include现DTO不调用或构造Common客户端。

结果为纯POD：kind、row_index、query_rows/scanned_rows/matched_rows/invalid_rows/uncertain_rows、event_missing/event_invalid/conflict_fields、event_relations、query_bytes/peak_work_bytes。kind固定Matched、NotRequired、InvalidEvent、EventLocatorMissing、NotMatched、Ambiguous、InvalidQuery、UncertainQuery、IncompleteMatch、Conflict；仅Matched返回可用原数组row_index，其余索引为size_t最大值。无行复制输出、无fake AccountResult、无金融字段合成。结构/JSON/额度/分配失败抛原异常，失败赋值不覆盖原结果；调用者前后核原D/control，异常不能伪成NotMatched。

事件使用R5b唯一inspection。Complete返回NotRequired，Invalid返回InvalidEvent；仅MissingRequired且locator_complete才扫描补查。事件缺定位返回EventLocatorMissing。字段位及关系位完全复用R5b，不按错误reason分类，不覆盖present-null/invalid。

ORDER精确定位按Code/Exchange/Order，账户作用域来自已验证的binding；DEAL按Code/Exchange/Order/Trade/Date。DEAL作用域为原scoped_trade_id的exchange/code/date/rawtrade完整组成加broker，直接比较组成值，保留原TradeID构造owner；不按broker合计、多笔分摊、最近值或时间近似。日期/时间/市场等价只消费R5b规范值，输入raw不变。

每个查询行均调用同一inspection。金融Invalid的任一行记录InvalidQuery，不因跳过坏行而授唯一匹配；非对象行也按该金融类型处理。缺定位行若任一已有合法定位字段明确不同则可排除；否则它可能属于目标，记录UncertainQuery。定位完整且精确相同的每个原行都计matched_rows；相同字节重复也算两行，不执行seen去重。只有完整扫描后才能返回Matched。

ORDER双方共同valid的Code/Exchange/Account/Currency/Order/Side/Date/Time/Quantity/Price必须一致；Filled/Remaining/State/Cancel允许真实后续状态，原数量关系仍由R5b核。DEAL双方所有共同valid事实必须一致。可选unknown与真实0/空值遵循原inspection规则，不以unknown覆盖已知值。唯一匹配行仍缺必需金融字段返回IncompleteMatch；不产生补零对象。

扫描完成后的优先级为InvalidQuery、UncertainQuery、Ambiguous（精确匹配超过1）、NotMatched（0匹配）、Conflict（唯一行共有不可变事实冲突）、IncompleteMatch、Matched。conflict_fields按R5b位标识实际共有事实差异。查询原文/行序/数值/可选诊断字段全保持，只有Matched的原index可以供后继完整mapper采用。

### 明确逻辑额度

limits显式四项：max_event_bytes为1..1MiB；max_query_bytes为1..64MiB；max_rows为1..4096且不能超过固定binding.row_limit；max_work_bytes为1..64MiB。query的data_json沿原1MiB JSON边界；结构/节点/深度仍沿JsonBoundary。参数错误和容量不足是未完成处理，不返回金融结果分类。

query_bytes逐项累计现DTO实际字符串字节及每项一个逻辑NUL：bound.result的status.reason/data_json/envelope_json/request_id/operation_id；bound.receipt的binding_json/request_body/read_profile_body；bound.native_result_json；remote_error_code。每个字符串仅按本对象实际持有计算一次，空串计1。不把data_json与envelope/native的实际重复存储当成共享引用而漏计。

峰值基数为128固定结果/计数预留 + 原event_row_json字节及NUL + query_bytes，再加一份event inspection的实际output_bytes，记为U。计数得到本行编码长度L后，在调用json_text前先核序列化峰值U+2*(L+1)：原StringBuffer与返回std::string构造期间同时持有两份逻辑文本。返回后原Buffer已析构，行检查峰值为U+(L+1)+row inspection实际output_bytes。peak_work_bytes取两阶段与各行的最大值；两inspection同时存在，单行处理结束后才释放本轮串与inspection，后继行不累计旧值。所有加法先减后比，包含双份文本前置预留，硬限内累加。序列化大小先用同一RapidJSON Writer的计数输出核额度，再使用原json_text；没有另写JSON或金融转换算法。inspection接收剩余额度与其原4096上限较小者，资源不足抛原异常。逻辑有效载荷不声称等于DOM/分配器物理内存；DOM/SAX仍受原输入及节点硬限。

### 后继接线影响闭包与边界

待后继冻结：Standard::begin_event在MissingRequired且可定位时，以同一TaskCredit/原链D接回原worker队尾，只使用既有account client及R5a request_control=event_control。一次create/submit，后续只resume原receipt；普通查询control保持独立。stop/detach关闭新阶段，已发生失败和原receipt保留，不套用R13事件页运输重试许可。补查完成后本matcher返回原index，owner/P8须接收完整原query、原事件provenance与index，沿真实源认证/唯一mapper/身份resolve/去重构造一条event-triggered query观察。现begin_qmt_trade_event_identity不能把查询行伪装为payload，现begin_qmt_account_identity不能接筛行后伪造的AccountResult；因此新的P8来源入口是明确待实现接缝。

完整后继需保持原query执行区间、receipt/结果SHA与事件B/session/sequence/page分别保存；ORDER采用真实后续整行，DEAL采用同一笔真实整行。transport sequence的去重事实与查询后续金融事实分别登记；原事件页的处理前沿只有实际处置后推进。既有EventChain reserve、CompletionRing、Candidate/Plan/Resolved并存与HTTP drain借用必须在总额度中前置预留；本片的纯匹配峰值不冒充完整R5峰值公式。完整接线需要改自有Standard、QmtAccountIdentity及相关来源/交付接缝，公共接口与总峰值另由根核定，当前均未修改。

验收：真实字段缺失、null/非法、完全相同重复、多匹配、潜在未定位、明确不同定位排除、ORDER后续状态/不变量冲突、DEAL同broker多trade及多市场/多日期、共有事实冲突、optional unknown、空结果、原行不拼改、恰need/need-1、长非金融可选备注使双文本序列化峰值超过inspection阶段的独立人工oracle及原少计额度拒绝、checked硬限、分配异常强失败契约。旧mapper与Common/P8/Standard行为分别回归。纯fixture与真实运输/SDK/生产资格分开；本片不授完整R5或R8。

## SEV-R5d-A 原完整查询单行映射（accepted；完整R5待接线）

本接受片限定选行mapper与共用Shm metadata接缝，B双来源P8与C Standard补查仍为后继草稿。原公共API、R5a/R5b/R5c、WT和Host协议保持。

## 目标与影响闭包

R5c可在完整查询中排除定位明确不同的缺字段行，现P8全批金融映射仍会因该行失败。A提供从完整原rows按原index构造一条金融对象的唯一mapper接缝；旧全批入口保持原规则和字节。调用者必须另执行R5c全扫描及来源关系检查；A自身的选行不授唯一匹配或身份归属。

产品范围严格四文件：src/GuanhengQmtBootstrap/AccountMapping.h/.cpp、ShmAccountMapping.h/.cpp。新增独立测试为 tests/integration/qmt_shm_account/mapping/selected_row_probe.cpp。根拥有CMake/build/README接线。Common、inspection/matcher算法、QmtAccountIdentity、Standard、Host/Agent、WT全部保持；不新增数据库、资格或金融循环。

## 精确公开API

AccountMapping.h新增：

    struct AccountSelectedRowBatch {
      AccountBatch batch;
      std::size_t original_row_index=0;
      std::size_t original_row_count=0;
    };
    AccountSelectedRowBatch map_account_row_at(unsigned stage,
      const rapidjson::Value& original_rows, std::size_t row_index,
      const AccountBinding&, wtp::IBaseDataMgr*,
      const AccountBatchMetadata&, const AccountCanonicalLimits&);

ShmAccountMapping.h新增：

    AccountSelectedRowBatch map_shm_account_row_v2(unsigned stage,
      const QmtAccountResult& original_query, std::size_t row_index,
      const AccountBinding&, wtp::IBaseDataMgr*,
      const AccountCanonicalLimits&);

相对001草稿只去掉新map_account_row_at的view_version参数：此新入口固定view3，无额外版本选择；旧六参/七参canonical/事件入口、旧两个Shm符号签名不改。包装由AccountBatch的unique_ptr形成move-only，默认move/RAII沿现类型；未返回包装不代表成功，异常沿原函数表达。

## 选择与金融合同

1. 新入口stage仅1/2，base非空，原rows为完整数组且数量<=binding.row_limit，row_index<size，所选行必须对象；原canonical_admission继续验证绑定/限额。空rows/越界/无效stage在任何WT数组构造前拒绝。实际空缺金融/现存非法字段与各项金融关系沿同一decode_trade_row及后续原构造规则。
2. AccountMapping.cpp只改现map_account_rows_impl的行选择机制：一个私有selection值表达全批或单个原下标，一份for循环按逻辑序号映射原下标后取const row引用。原循环内decode、seen/reverse_ids、scoped_trade_id、WT构造与append helper、views/canonical原样共用。不复制行DOM，不建立筛选数组，不造新查询封套；源码不出现第二套order/deal金融构造循环。
3. 新成功包装：original_row_index==输入原index；original_row_count==完整原rows.Size；batch.source_rows==1；source_to_output精确{0}；array/views/canonical_records各1项；view_version3、views.index0。本地输出下标与原行下标分别持有。原index允许0，不能以0当缺失；禁止把local0传R21Q或proof。
4. 来源source/started/finished/seconds/request_id/result_sha保持完整原query metadata；规范key/derivedhash、TradeID/RefOrder及全部金融views内容仍由唯一mapper生成。所选完整行的字段整体采用，不拼接事件值，不覆盖null/invalid，不补默认金额。
5. 新选择入口不检查其他原行的金融有效性、不去重原rows、也不授全批有效性。两个相同原行仍由后继R5c判Ambiguous；它不借选择规避全扫描。测试须同时证实该职责边界。旧全批映射继续访问所有行，原非法/缺字段拒绝和duplicate去重保持。

## Shm来源准入和生命周期

原map_shm_account_batch_impl中封套/receipt/request/profile/固定account+datatype/执行区间/摘要提取共用一个私有helper。返回私有AdmittedShmRows值，拥有rapidjson::Document data及AccountBatchMetadata metadata；其他只用于校验的DOM可在helper内销毁。原rows通过仍存活的data读取，不能返回指向helper栈内已销毁Document的Value指针。原fullmap和新selectedmap共同消费此helper，分别在最后调用原map_account_rows与新map_account_row_at。

新Shm入口固定原v4/account2.0语义；完整query始终保持原QmtAccountResult，原result/native/request_id/operation_id、policy2/profile/hash/B/request/account/执行区间规则沿既有v2分支，没有另一次认证。可信输入前提是同次Core已采用成功原终态；status.ok或手造DTO不能获得该运输事实。新函数不持有输入JSON或Core/HTTP引用，调用返回后包装独立。

新路径可在helper前拒绝非法stage；旧路径的错误顺序、可接受版本、返回字段及异常表达保持，必要的结构重整只搬移同一准入逻辑。原fullmap与新selected都在metadata准入完成后才开始WT构造。

## 额度、失败与范围

A沿原JSON hard boundary、binding.row_limit与AccountCanonicalLimits：新输出只一记录，max_records仍经原1..4096验证，原数组总行数另受binding.row_limit约束，max_bytes仍1..64MiB；canonical实际字节按key/hash各NUL。新返回包装仅增加两个size_t原索引，不新增来源字符串副本或全批row复制；其固定结构开销不冒充全生命周期逻辑预算。

canonical_bytes恰need通过/need-1拒绝；失败的WT对象由同一append/array RAII回收，不部分返回。JSON、金融、容量、分配异常维持本层既有异常合同，不引入新Status/reason解释，不把失败伪成金融匹配kind。调用者的赋值式接收在抛异常时保持旧包装。不得用A的canonical额度证明B的max_work或C的HTTP/来源并存额度；二者另片冻结。

## 独立测试合同（计划组数，不是已执行断言数）

1. ORDER原index2：index0是明确不同broker的Missing行，index1不同完整行。R5c真实调用返回Matched/index2；selected返回local0/original2/count3，原fullmap按旧规则拒绝。DEAL同类至少一例。
2. 所选行自身Missing、present-null/invalid、金融关系冲突各拒；所选合法但无关Invalid行时selected自身可构造，R5c必须InvalidQuery，明确caller职责，不能把该独立mapper结果当发布资格。
3. 相同原行重复：R5c Ambiguous，选择入口的机械index语义保持；原fullmap重复处理、source_to_output/TradeID旧行为保持。
4. view/canonical兼容：使用独立合法单行control夹具对同金融原值比较全部views/canonical/TradeID；多行合法fullmap对照选定原行的WT金融槽与规范记录，差异只限显式本地index和包装原index，不自己写金融转换oracle。
5. 两个stage与固定view3；空rows、非array、超row_limit、index==size/size_t最大值、所选非对象、base空、stage0/3拒绝；原UTC/currency/0/unknown及原order price0语义保持。
6. canonical实际need人工计算与need-1；max_records0/超硬限、max_bytes0/超硬限拒绝；不把测试256MiB当此API额度。
7. Shm完整合成可信DTO：request/operation ID、policy/schema、原profile/hash、account/datatype、执行区间错各拒；成功完整输入前后原字节/摘要不变，包装来源逐字段对应。明确这是metadata接缝单测，不授Core认证/HTTP资格。
8. helper返回后input所有原字符串/DOM销毁，返回batch金融views/canonical独立；失败赋值保持先前有效包装；测试专用new注入与WTArray分配失败资源验证沿现隔离探针方案，不新增生产hook/global override混链。
9. 旧128金融、115canonical、31事件mapping、独立4append、142inspection、72matcher定义各自原入口保持，根安排受影响编译/真实回归；原样本源码不为选行修改。新增断言数量实施后再精确登记，当前不声称通过。

B后继真正Core HTTP结果→P8双来源另测完整来源/身份；C后继真实Host/HMAC/WinSHM/Adapter另测SPI/FIFO/关闭。A独立测试不替代二者。



## SEV-R5d-B 双来源P8身份接续（accepted；实现与验证分开登记）

本接受片仅QmtAccountIdentity.h/.cpp，原行选择A、R5a Common、R5b/R5c算法及Standard/Host/Agent/WT保持。沿一份金融mapper与原P8解析/写槽；新B独立测试另由验证owner实现。完整R5 Standard I/O/FIFO/额度接线仍为C后继，R8不由本片授予。

### 精确新增声明

```cpp
// R5d-B新增声明；旧入口保留。
// 包含 QmtAccountIdentity.h 与 AccountEventMatch.h 后的 guanheng::bootstrap 命名空间。
struct QmtEventQueryIdentityBudget {
 QmtAccountIdentityBudget identity;
 AccountEventMatchLimits match{};
 std::size_t max_work_bytes=0; // 1..64MiB，整个同票据逻辑并存峰值上限
};
struct QmtEventQueryProvenance {
 QmtAccountResult original_query; // 只接原Core已验证值；完整复制一次，绝不筛rows
 std::size_t original_row_index=0, original_row_count=0;
 std::string derived_row_sha256; // 唯一Writer重编码的派生摘要，不冒充原线上行片段
};
struct QmtIdentityBrokerProof {
 QmtTradeBrokerProofKind kind=QmtTradeBrokerProofKind::None;
 bool dispatched=false, has_broker_proof=false;
 bool has_event=false, has_query=false;
 QmtTradeEventSource event_source; // 仅实际Reference.source；历史query B保留在原lookup
 std::uint64_t source_sequence=0, query_row_index=0;
 std::string source_event_sha256, query_request_id, query_result_sha256;
 std::size_t lookup_response_index=static_cast<std::size_t>(-1);
 std::string lookup_sha256;
};
// QmtAccountIdentityResult尾追加（旧两入口保持null/空）：
// std::shared_ptr<const QmtEventQueryProvenance> query_provenance;
// std::vector<QmtIdentityBrokerProof> broker_proofs;
// 新入口最多一项proof，与identity_views本地输出0对应；历史原行index独立。
QmtAccountIdentityBegin begin_qmt_event_query_identity(
 const QmtTradeEventPage& original_page,
 const QmtTradeEventRequestBounds& original_request, std::size_t event_index,
 const QmtAccountResult& original_query, std::size_t original_row_index,
 const QmtExpectedTrade&, const AccountBinding&, wtp::IBaseDataMgr*,
 const QmtEventQueryIdentityBudget&, SignedHttpDeadline& original_deadline);
// Candidate/Plan/Resolved各增加上述begin为friend（Resolved仅用于前置核真实State固定大小）；resolve/finish签名与原Query/Event入口不变。
// 不新增Common方法、worker、逐HTTP跳控制、公开预算可变对象。
```

## 1. 输入与事实所有者

begin参数：原Core采用的 QmtTradeEventPage、其原请求bounds/event_index；原Core采用的完整 AccountV4/account2 QmtAccountResult、R5c选出的原row_index；expectedTrade/AccountBinding/BaseData、旧identity+match限额和新max_work、同一绝对D。

公开DTO没有认证能力。caller必须提交实际同请求/同轮原Core结果；status.ok不是身份资格。B继续完整核原事件page/profile/source、原query receipt/request/native/data metadata、账户/环境/类型、control2/account2、原B和profile一致；查询自身无交易session字段，不能补写。事件source.session由resolve前后真实trade.prepare + event_source核对。

查询receipt的 request_body/read_profile_body/read_result_capacity、native_result_json/result_sha和data.execution区间全部保留。原event page/index/sequence/kind、B/session/profile/bounds原值全部保留。它们可先后发生；不表示同一原子账户水位。

原金融行只来自query.rows[original_row_index]。ORDER允许R5c已准入的真实后续filled/remaining/state/cancel；其它共有有效事实按唯一mapper typed事实相符。DEAL必须 scoped trade+broker精确唯一，多个成交不合计。原query所有rows完整保留，重复相同行也仍为Ambiguous；Invalid/Uncertain不能跳过。

## 2. begin 的顺序与原行分组接缝

1. 原D、stage、原输入硬长度与旧三个identity子限额/new work限额核准；用原长度算 admission_parse，checked前置核后才解析。
2. 复用事件begin已有page准入与原请求bounds校验。query保留完整原DTO；核同原B/profile/账户/policy/datatype。只用已验原page事件kind决定stage1/2。
3. 原事件payload用同一Writer计数再编码，调用完整R5c matcher；必须Matched且与实参原index一致。完整扫描后核D。金融Invalid/Missing/结构/资源各沿原typed/Status边界，不靠reason字符串分类。
4. 在已拥有的query data DOM上对选中完整原行、两identity scalar做CountWriter长度测量。计算全阶段不可变need；任何缺项/overflow/超cap在来源复制和WT构造前失败。不同的两个完整token先Conflict，普通备注/null/缺失保持原值。
5. 克隆完整query一次；复制event provenance一次，置于同一个不可变 EventQuerySources owner。新SelectedRow wrapper记录原index/count。调用A真实map_shm_account_row_v2；额外无金融循环；调用前已含其同步输出/双文本峰值。
6. 对build_groups提取最小共享“给定原row、output下标”的私有收集器。旧全批仍先核rows.Size==batch.source_rows、遍历原source_to_output；新选行分支核wrapper原index/count与完整rows一致、本地batch一行/map{0}，然后收集完整rows[原index]→本地0。金融对象读取broker/symbol/trade、duplicate scalar校验、slot校验继续原实现。不能构造一元素假rows使旧条件表面成立。
7. Plan为标量指针保留一个所选完整原row DOM，不借caller；该DOM是查询原行的值副本，不改变原查询DTO/来源名字。event触发行仍只在event provenance。publish前原D检查，一次发布Candidate/Plan。

## 3. 私有 State 与三阶段所有权

新增 IdentitySourceKind::EventQuery。

私有 EventQuerySources 精确持有：QmtTradeEventProvenance event、QmtEventQueryProvenance query、const QmtEventQueryIdentityBudget budget、const size_t reserved_work_bytes/identity_view_bound（构造时冻结）。IdentityTicket仅增加 shared_ptr<const EventQuerySources> event_query_sources；原owner/deadline/stage/output_count/旧limits等继续。budget与reserved随同一ticket使用；不允许resolve或finish传新值。

IdentityPlanData沿原rows/transport/groups/data.ticket；EventQuery的rows采用完整所选row对象（不是伪查询数组），group scalar指向此拥有的对象。复用row访问器收集，不保存外部DOM指针。Candidate仍独占WT array/BaseData关联，只在begin owner创建/finish/销毁。

Resolved沿原groups/identity_views/lookup_responses/status，新增最多一项纯值 broker_proofs。worker不持WT/BaseData/SPI引用。Result尾增query_provenance和broker_proofs，旧Query/Event为空；新event/query_provenance用aliasing shared_ptr指向同一个Sources的两个成员。Result保来源也保预留摘要，ticket与Sources没有反向引用循环。

同owner同ticket的finish使用原无异常move移交views/lookups/proof/batch与来源；错owner/ticket保两句柄及原费用。Candidate早退，worker仍持Plan/Resolved及完整Sources，最终late结果仅纯值释放；不跨线程释放WT，不提前退整份reservation。外层C以后须把这项reservation作为同EventChain任务责任持到所有值真实析构，B不自行操作Standard余额。

## 4. 历史 broker proof 的精确合同

新增纯DTO见拟头：kind、dispatched、has_broker_proof、has_event、has_query、event_source、source_sequence/source_event_sha256、query_request_id/query_result_sha256/query_row_index、lookup_response_index/lookup_sha256。

这些值仅从真实lookup的private Reference已验facts/source提取。在Reference/cache销毁前复制完成且已前置计费；不能带私有Reference跨线程。has_event由完整实际source pair/seq/SHA确定，has_query由实际query UUID/SHA/index组确定；原index0有效。kind沿facts.broker_proof_kind，不由当前补查猜测。

一个kind=AccountQuery的proof仍可带真实历史Event来源；两组都保留。历史query UUID/SHA/index可以与本次financial query完全不同：不能当前query回填。历史query host_binding当前只在原lookup回复/private字段中；保原lookup_response_index及SHA供准确引用，不扩Common getter或从当前B合成。EventSource使用Reference.source真实历史B/session，与触发event_source也各自独立。

有效完整标准404→external，proof=None、无event/query；未知/未派发/无broker proof→原unresolved，保金融batch且不猜tag；409/证券或broker矛盾保持原失败。无完整remark token→external，OrderRef仅诊断。一个输出组最多一次lookup，缺proof不被新query数据自动升级。

## 5. 新 view 封闭字段与旧字节

新schema仅 qmt.wt-event-query-identity.v1。封闭字段：schema_version,stage,output_index,order_id,ref_order,trade_id,m_strRemark,m_strOrderRef,classification,entrust_id,user_tag,reason,lookup_response_index,lookup_sha256,event_trigger,selected_query,broker_proof。

- m_strRemark/m_strOrderRef沿原{presence,value}，取query整行；原event标量在原page中。未知/null/0/空串保留，不能字符串化0。
- event_trigger：event_index/sequence/kind/derived_page_sha256/derived_event_sha256。
- selected_query：request_id/result_sha256/original_row_index/original_row_count/derived_row_sha256。
- broker_proof：kind(none/event/account_query)/dispatched/has_broker_proof/event/query；event=null或{source_sequence,source_event_sha256}；query=null或{query_request_id,query_result_sha256,query_row_index}。完整历史event B/session保纯DTO和原lookup，view引用现有raw索引。相较revision002显式补dispatched真实事实；不伪造当前可写权限。

所有派生SHA名称明确为派生；selected_query.result_sha256来自真实native终态字段，历史proof SHA来自lookup。query batch metadata仍是原查询source/区间；event provenance仍是原page。本地batch.index=0、proof原query index、本次financial原index三者不得互换。

旧Query/Event入口/schema/view金融bytes/canonical/source_to_output/TradeID保持；旧budget默认和API不改变。新分支复用原resolve身份校验与finish写槽；不得复制金融转换、HTTP校验、或另做token识别器。

## 6. 原D、停止和异常

B不增加Common控制参数。整个resolve是一个已准入唯一worker任务，共用原D执行prepare→最多一次lookup→最终prepare；只读源发生unknown不自动恢复insert。stop/detach若发生在任务已准入后，保持当前同步任务原D和真实失败，返回到合法任务边界停止后继I/O；owner不向SPI发布这项金融结果。B只有身份值转换，本身不发SPI。

begin各解析/匹配/构造/发布边界、resolve各原I/O边界、finish最终写槽/发布均检查同D。未完成任务不授新窗口。请求超时仍保可用原来源；任务边界是否启动属于后继C。真实已发生Failure不被正常stop替换，成功后晚D按原Timeout处理。

new分支checked容量→Backpressure；bad_alloc→IoError且允许空reason以避免catch再次分配；原校验/关联错误保其分类。固定错误文本可在已计诊断对象内预备，不能错误路径无限追加。资源/结构检查失败不伪成金融Invalid/Missing。异常整批RAII回收、无partial array。


### 全阶段前置逻辑费用（权威合同）

这是同票据一次预留合同，不是 allocator 物理内存限额。所有加法、乘法、ceil 都 checked；任一溢出、任一旧子限额非法、need 大于 max_work_bytes 或 max_work_bytes 大于 64 MiB，begin 返回 Backpressure 且没有 Candidate/Plan。输入 JSON 原 SAX 字节/节点/深度限制继续独立生效。运行前不得用后测峰值替代此准入。

## 1. 计量与无需新同步的预留

- t(s)=UTF-8 bytes(s)+1；空 string 也计一个逻辑 NUL。两个内容相同的 string 各计一次。move 不重复计，同一 immutable shared owner 的别名不重复计。
- 固定对象成本按实际拟实现的 sizeof 类型相加，而不是旧128/64常数：IdentityTicket、IdentityPlanData、三种 State、EventQuerySources、QmtEventQueryProvenance、两份 Group、一份 CachedLookup、一份 QmtIdentityBrokerProof、Result、一个size_t映射槽、一个canonical记录、一个lookup string元素、一个identity string元素。使用固定元素数量1；已经嵌入的子对象不再次加 sizeof。编译探针输出此项准确数值，人工表逐项对照。固定容器的实际元素也按sizeof计入：seen的一项pair<const string,pair<string,size_t>>、DEAL reverse_ids的一项pair<const string,string>、lookup cache的一项pair<const string,CachedLookup>；若CachedLookup/键等已作为该pair嵌入成员计入，就从独立项中去掉同一份sizeof。vector元素/initializer_list临时string对象按实际元素数独立计。树节点链接、allocator控制块/容量余量不算逻辑载荷。A独立分配的 sizeof(wtp::WTSArray)、一个数组元素指针槽 sizeof(wtp::WTSObject*)、stage对应 sizeof(wtp::WTSOrderInfo) 或 sizeof(wtp::WTSTradeInfo) 必须加入；借用的合同/BaseData对象不复制、不重计。唯一mapper的AccountRowInspection固定结构至少计两个 sizeof(AccountRowInspection)，覆盖返回值未做NRVO时局部与接收对象并存，其字符串另在4096事实银行内计；matcher内部inspection固定/字符串已包含原match.max_work定义，不能再把该定义当整个B的固定对象上界。A调用栈上的AccountSelectedRowBatch、AdmittedShmRows/AccountBatchMetadata、临时AccountBatch容器按实际非嵌入实例逐个列 sizeof，编译探针检查清单；保守重复存活允许多计，不可漏独立WT对象。
- JSON DOM 的逻辑内容另计：J(n)=9*(n+1) 是以原编码长度 n 为输入的保守上界（键/字符串解码文本含NUL至多 n+1，标量/容器逻辑单元每项8，单元数至多 n+1）。这不宣称 DOM arena 的物理容量。持有多个 DOM 就分别计；已有解析节点/深度上限不取消。
- X(n)=32*(n+1) 界定任意有效原 JSON 经同一 UTF8 Writer 规范重编码的文本长度：UTF8 字符串至多6倍逃逸，有限数字 Writer缓冲25字节，整数缓冲至多21，结构标点保留。只用来界定小型 transport/metadata 临时重编码；选中大行使用真正 CountingOutputStream + 同一 RapidJSON Writer 计数 S，不构造第二套 JSON 算法。
- 所有 json_text 输出均先计 Buffer 与返回 string 同时存在的 2*(encoded_length+1)。DOM 的 J 项还在，同时算入。
- caller 原 page/query 在 begin 期间仍活着，分别计 E/Q；克隆来源另计 E'/Q'。本合同保守地在后续相位也不退 caller 输入额度。Candidate 早退不减预留，直到最后一个来源 shared owner/返回结果真实析构后外层 owner 才退其整份费用。
- begin 内部先以长度计算 admission_parse 峰值并核 cap，再解析/计数；随后一次算完整 need 并核 cap，才复制来源或构造 WT。解析前置阶段不发布票据；发布后的 ticket reservation 永不改变。后续阶段只检实际值不超过既定分项，不追加额度或新D。

## 2. 原输入和来源精确清单

Q = 以下10个 t 的和：bound.result.status.reason、data_json、envelope_json、request_id、operation_id；bound.receipt.binding_json、request_body、read_profile_body；bound.native_result_json；remote_error_code。bound.receipt.read_result_capacity 及 JsonResult 的 http_status/terminal/remote_ok 是固定对象字段，不丢弃。

E = page.status.reason、page.source.binding_json、page.source.session_id、page.page_json、page.read_profile_body 的5个 t；page所有数值/布尔与 original_bounds/event_index 的固定成员另按固定对象计。来源 event_provenance 还拥有 kind、derived_page_sha256、derived_event_sha256；各按 t，两个 SHA 各65，kind 最大 t("order")=6。

Query provenance 拥有完整 Q 的一个副本、两个原 size_t、derived_row_sha256(65)。batch.metadata 持有 source、started、finished、seconds、request_id、result_sha 六个 string；它们与 query 的原文分别计。原查询执行区间的 text 上限32，seconds为20字符，request_id36、result_sha64。原金融来源 source 由 Shm helper 生成，见第4节 Msource。

Plan 只保一份所选完整原行 DOM（J(S)）、一份原 transport DOM（J(B)）；完整原 query 始终在来源中。此选行 DOM 是 group 标量指针的纯值 owner，不伪造 QmtAccountResult/rows。选行 index/count 始终是原完整 query 下标/数量；batch.source_to_output 固定本地{0}。

admission_parse 前置项逐份为：原 E+Q；event page DOM J(page_json.size)、event B DOM J(B)、event profile DOM J(P)、query data DOM J(data_json.size)、query B DOM J(Bq)、query profile DOM J(Pq)。原页准入若另产生 QmtValidatedTradeEventPage 的 document/source_binding 就计这两份，不与本表重复创建第二份。query native/request 交 A helper 内部使用（第4节），不要在此重复解析并长期保留。

准入DOM银行明确记为 ADOM = J(page.page_json.size) + J(page.source.binding_json.size) + J(page.read_profile_body.size) + J(query.bound.result.data_json.size) + J(query.bound.receipt.binding_json.size) + J(query.bound.receipt.read_profile_body.size)。这六个独立DOM在同步A调用期间仍存活；Awork中的helper data/native/request/transport/profile是另一套对象。两套都计入begin峰值，不能取二者max、相抵或以原JSON字符串费用代替DOM费用。为简化所有权，后续resolve/finish的保守银行继续保留ADOM，不依赖编译器scope/提前析构退款。

票据文本银行独立记 Tticket：IdentityTicket.account、request_id、result_sha、original_session 四个 string 各自 t；sizeof(IdentityTicket)只含string控制结构，不能覆盖这四份文本。EventQuery分别复制已验binding.account、原query request_id、原native result_sha、原event session。其字段硬界63/36/64/128字节，所以本候选固定前置预留 Tticket_cap=(63+1)+(36+1)+(64+1)+(128+1)=295字节；实际t之和须<=295。与Sources、batch.metadata、query原文内容相同也各计；票据销毁前不退。这295是四字段逐项上界，不是泛用诊断常数。

## 3. matcher、选择和身份标量

- matcher 调用预留 match.max_work_bytes，照R5c原合同覆盖事件原单行文本、全Q、两inspection的输出载荷及每行原序列化双文本；它不包含内部DOM。另加 M_DOM = J(query.bound.result.data_json.size) + J(e) + J(Rrow) + 2*J(1024) + 2*(1024+1)。其中 Rrow=min(1048576, checked X(query.bound.result.data_json.size))：原 matcher 的 encoded_bytes 在 json_text 和 inspect parse之前将每行重编码长度限为1MiB；X给另一保守上界，先checked计算再取min。querydata DOM、event inspect DOM、每行inspect DOM都与外层ADOM区分；即使其中局部顺序析构，预留仍保守相加，不相抵。后两项是inspect调用的 canonical_admission 原account value/validated两DOM及其json_text双文本，取原parse_json(...,1024)硬界；两次inspection顺序执行，这一小银行复用一次，不漏计也不无限累计。再加本调用同时持有的E来源和ADOM。不能拿返回的 peak_work_bytes 事后追认。
- 原 event payload 编码长度 e 和所选原 row 长度 S 用 CountingOutputStream 取得；先在已核 admission_parse 保有 DOM 上计数，后检查生成的两份文本 e/S，再调用 json_text。S 本身还必须适合原部分事实输入上限。若匹配返回非Matched或不同原index，发布失败；不创建 WT。
- remark/order_ref 在选中 row 中的独立标量编码长度 r/o 也通过同一计数Writer取得；缺失按null长度4计预算，presence按bool最大5。长 remark 只进入身份DOM/view，order_fields/trade_fields 金融view不含这两个字段。
- 原event与query各自完整token有值但不同 → Conflict。检查所需临时 token string 两份各最多65；普通备注不复制整条大 string 去做 token检查：长度超过64直接沿现完整token规则判非token，仍保原标量。这不是缩短/重写原备注。

## 4. A 同步调用也预留，金融构造保持唯一

源证据：AccountMapping.cpp decode_trade_row、fact/abi、唯一stage1/2循环；QmtAccountFields.h order_fields14、trade_fields12（均不含remark/order_ref）；Writer::WriteDouble 的25字节缓冲及 UTF8 WriteString 的2+6*n上界。

金融有效行的可变字符串：code6、exchange原2/规范3、account<=63、currency3、broker<=63、trade原<=63/派生WT槽<=63、日期<=10、时间<=12。固定profile/mapping_version、availability、reason、ABI说明的UTF8字节均<=63；本冻结 mapper 输出分支最长说明40字节。固定 JSON key 均<=32。有限数字<=25字符；下表统一以更大的可变字符串编码上界380计叶值，并留一逗号，形成可人工核的保守式：

    G(objects,keys,leaves) = 2*objects + keys*(6*32+4) + leaves*(6*63+3)

| 形态 | 对象数 | 键数 | 叶值数 | 编码上界（不含NUL） |
|---|---:|---:|---:|---:|
| ORDER view3（root7/id5/facts14*3/ABI17*2/price_type3） |37|122|87|57133|
| DEAL view3（root6/id8/facts12*3/ABI12*2） |28|98|71|46315|
| ORDER normalized（root13含facts14*3） |16|69|54|34130|
| DEAL normalized（root11含facts12*3） |14|59|46|29118|

canonical key最多11个<=63字节字符串，数组编码上界 Ckey=2+11*(6*63+3)=4193（保守多一个逗号）；派生SHA字符串65。这些是当前固定schema的上界证明，后续增加键/值长度须更新本表和边界测试，不是任意64KiB预留。

Msource 用固定 Shm helper source 对象的长度算术上界计算：Obj(fields)=2+max(count-1,0)+Σ(UTF8固定key长度+3+value_bound)；Str(n)=6*n+2。source字段：kind=Str(13)、account_id=Str(binding.account.size)、account_environment=Str(binding.environment.size)、transport_binding=X(Bq)、binding_sha256=Str(64)、broker_session=Obj{availability:Str(7),value:4,reason:Str(UTF8("未取得券商登录会话证据").size)}。source固定key是ASCII无需6倍。逐值使用原helper固定字面量，不能凭当前source样本长度代替上界。

A/mapper临时槽（保守相加，即使局部先析构也不退）：
0. canonical_admission的 account value/validated两DOM及 json_text双文本：2*J(1024)+2*(1024+1)，沿其原1024解析硬界。A调用这一银行与matcher M_DOM中同名银行分开计；本片保守相加，不依赖两个调用scope提前退款。
1. Shm helper 的 data/native/request/transport/profile 五DOM：分别 J(对应原string长度)。profile validator内部的DOM按既有Common有限profile职责单列，不宣称此B cap物理覆盖。
2. source DOM J(Msource)、source StringBuffer+返回字符串各 Msource+1；metadata五string（source/Msource、UUID36、SHA64、started32、finished32），返回到mapper仍活着。
3. mapper batch六metadata字符串：上述五项再加seconds21；与helper各自拥有，分别计。
4. decode纯facts输出上界4096（沿原R5b输出硬界，实际这一路没有复制原长remark）。map暂存 code/exchange/broker/date/time/rawtrade/derivedtrade/tuple 等各原长度上限逐项：7、3、4、64、11、13、64、64、84，DEAL key=id+LF+broker上界128，ORDER seen key64。DEAL reverse_ids还持有id和tuple的独立副本，另计64+84，不能与局部id/tuple相抵。scoped_trade_id调用中input原串另计122（24字节prefix+嵌入NUL1+四长度前缀16+exchange/code/day/raw合计80+结尾逻辑NUL1）；四个initializer_list字符串另计(3+1)+(6+1)+(8+1)+(63+1)=84，day[9]按固定数组9计，派生out保守64已在derivedtrade银行中。canonical_record initializer_list实际10个临时string：prefix34、stage6、account64、environment11、currency4、profile17、exchange4、code7、day9、order64，各自含NUL，合计220；ORDER空trade临时再1；DEAL另保守预留trade64（实际为第11个DOM字段，已含J(Ckey)，这里允许多计但不冒称第11个initializer_list元素）。这些string固定结构各按sizeof(string)计入固定表。
5. 金融 view DOM J(F)、canonical normalized DOM J(N)（其facts已CopyFrom，J(N)内包含）、normalized编码双文本2*(N+1)、seen中normalized另1*(N+1)。canonical key DOM J(Ckey)、key编码双文本2*(Ckey+1)、输出key与原encoded move共享（不再次计）；fingerprint65、CNG hash object<=65536、digest32。DEAL scoped_trade_id另一次CNG调用顺序结束，不叠加第二个65536；同时保持其实际输出/tuple文本。
6. 金融view编码双文本2*(F+1)，成功返回的view是该返回string的move，非第三份。source_to_output一个size_t，canonical_record一个固定对象及key/hash文本已在前项。

上表 A 工作银行记 Awork（所有列项 checked相加）。它在调用 A 之前全额预留；返回后保留金融batch那部分到finish，预留数字不缩减。错误路径原A异常/RAII保持；预算失败/异常不产生部分array。

## 5. lookup/两次prepare与真实证明持有

已验 descriptor K=max_command_bytes，R=max_call_result_bytes；K<=65536，R<=2097152。L=4*ceil(K/3)+R+2*16384，沿真实 record_capacity+metadata；最高2217304。新B仍用实际profile验证器取得K/R；不用read_result_capacity替代R。没有有效token时可保守仍预留本银行，避免分支计费状态。

lookup 返回期间必须保留的槽：
- QmtTradeLookupResult.response_body 与 reference_json 各 L+1；后者是当前Common真实完整复制，不可当别名。
- Reference.insert：B<=4096、command<=K、profile<=4096，分别+1；source：历史B<=4096、session<=128；private query_binding_json<=4096；broker<=63；association_error取3固定合法文本最大长度；owner_仅共享原client owner，不复制owner字符串。
- Reference.facts 十string的容量分别63/5/128/9/63/63/64/64/36/64，各+1；这些是account/type/binding/symbol/entrust/tag/token/eventSHA/queryUUID/querySHA。fixed布尔、枚举、seq/index包含于sizeof Reference。
- P8 CachedLookup 复制facts十string、broker、association_error，新增SHA65；token局部、QmtTradeLookup.sdk_user_order_id、cache key 三份各65。单行最多一次lookup且一个cacheentry。
- 原 Plan Group 和 Resolved Group 两份：broker64/symbol10/trade64/classification最长字面量+1/reason最长既有原因字面量+1/entrust64/tag64/SHA65；指向原row的两个scalar只借用该Plan DOM。
- 新 broker proof DTO 从已验 facts/reference 中复制：历史event B4097/session129、eventSHA65/queryUUID37/querySHA65/lookupSHA65；固定kind/四bool/seq/index等按sizeof；无历史event时文本空也计1。原lookup body移入lookup_responses，等同原response_body那一槽，不新复制。
- 生成identity view前销毁Reference/ref_json/cache临时，所需proof已经纯值化；即使不依赖此早释放，预留银行也包含全部重叠峰值。
- prepare同步返回的 source 与末次same_source调用临时 source 各B4097+session129；首次 source 目前活到末次检查结束，不能合并。same_source每次临时解析绑定 J(4096)，顺序两次只需一个临时槽。pin/profile/readiness仍是原client所有者内部状态，不移入P8。

Common自身同步内部另外存在：lookup的原body DOM、reply DOM、raw command/restored/record command、record metadata CopyFrom、编码Buffer+返回string、prepare/refresh回复DOM；均沿既有K/R/L/16384/4096及解析节点硬限。它们不属于新P8持有槽，不能将B cap解释为Common/进程总物理峰值。这里明确列出职责而不是掩去复制。已有HTTP Exchange自持 upload/headers/65536 buffer和晚回调属第8节。

## 6. 新 identity view 的前置上界

以 PROPOSED-HEADER 与 DRAFT 的封闭键集做长度算术，不重新实现金融JSON：Obj如上、Str(n)=6*n+2、uint64/size_t最多20字符、bool最多5。两source_scalar字段各Obj{presence:5,value:原scalar编码长度r或o}。其它固定文本/keys由其准确字面量长度计算；broker/entrust/tag/scopedtrade<=63、event_trigger.kind<=5、broker_proof.kind最长account_query=13字节、SHA64、UUID36、reason取现合法原因最长值；broker_proof采用event和query均存在的最大合法形态。event_trigger/selected_query固定成员的全部值逐项纳入。该算术结果记 V。

在创建 view DOM前检查 V+1<=identity.max_identity_view_bytes；保守预留 J(V)（view DOM）+2*(V+1)（Buffer/string），并且Result拥有原lookup/proof/batch。若保守界超配置，即便特定输出较小也先拒绝；不得先编码再赌成功。可在已预留V内用CountingWriter缩到实际长度用于旧identity输出统计，预留不退。

金融view与identity view不同；F/N只来自第4节金融schema，V可随真实长remark增长。测试必须分开测二者，防止remark混入金融预算。

## 7. 相位公式和不可变ticket

所有银行有详细上述槽清单，S_fixed按真实类型表求值。

- admission_need = E+Q+ADOM。checked核后才进行初次解析。
- match_need = admission_need +2*(e+1)+match.max_work_bytes+M_DOM。matcher自身包含Q/e，重复计是保守，合同不作退款抵消。
- begin_need = S_fixed + E+Q + ADOM + Tticket_cap + E'+Q' + event额外kind/SHA + query额外rowSHA + J(S)+J(Bq) + 2*(e+1)+2*(S+1) + Awork + 两Group银行 + 两token冲突临时。
- resolve_need = begin_need + lookup银行（第5节） + identity-view银行（第6节）。这是故意保守的全阶段累加：ADOM、Tticket_cap及A临时银行均继续占预留，不需要跨线程槽账。
- finish_need = resolve_need。finish对views/lookups/proof使用无异常move，双来源aliasing shared_ptr；不会重新编码、复制Q/E或授新cap。WT槽写前核原D、同ticket、全部结果与原子批次shape，发布整批后再交原owner。
- need = max(admission_need,match_need,begin_need,resolve_need,finish_need)。先拒need>max_work_bytes或64MiB。输入上限并不保证其组合可同时准入；大原page/fullquery/长备注/巨大可信R组合可以合法遭到容量拒绝。不能把64MiB扩大为隐性fallback。

保存：EventQuerySources{event,query,budget,reserved_work_bytes=need}；IdentityTicket新增唯一shared_ptr<const EventQuerySources>，其它既有deadline/owner/stage/limits保持；data仍共享ticket。Result的event/query_provenance采用别名shared_ptr指向同一Sources成员，所以源和reservation一直到结果真实析构才消失；不形成ticket↔sources循环。私有State仅新增此来源owner及Resolved一个proof向量（最多1），没有mutex/可变共享额度/lease框架。

旧 identity 三子额度仍按原输出累计规则验收（lookup原body、identityview、原total），不是拿新cap替代旧限制。新银行不反向改变旧Query/Event输出、默认cap和catch行为；新EventQuery资源异常为IoError空reason或已预构造固定原因，不能再被笼统转换为金融Invalid。错owner/ticket保留两句柄也保完整reservation。

### 正常配置关系与示例

match.max_work_bytes <= max_work_bytes只是结构条件，不足以保证准入。必须同时满足 admission_need+2*(e+1)+match.max_work_bytes+M_DOM <= max_work_bytes 以及完整need条件；match.max_work_bytes等于max_work_bytes时，有非空原输入的本入口必然Backpressure，这是显式合同。后继C不能把两个预算默认设为同一值。

一个仅用于验证、尚待完整新公式求和的配置向量：max_work=32MiB；match.max_work=2MiB；identity={lookup1MiB,view256KiB,total4MiB}；可信K=4096/R=8192；实际E<=64KiB、Q<=256KiB、单事件e<=4096、选中行S<=4096、两个标量编码r/o各<=512、原B/profile各<=4096，其他metadata沿上述实际合法限额。这是32MiB待验证准入向量（另要求编译sizeof清单总和<=64KiB，否则该示例失效）。revision002的实际need必须包含新增ADOM、Tticket_cap和M_DOM，旧001“小于16MiB”的未验证估算不再沿用；该输入向量的match_need静态保守约17,363,027字节，低于32MiB，完整need仍须按所有相位和实际sizeof表独立核准。这是待独立计算/原生测试的合成配置，不是已运行数据或新生产默认。测试须打印actual_need并独立展开每项与人工表比较，再验证need/need-1，不能仅断言"没有抛错"。大输入/大R场景仍可以被64MiB硬限拒绝。

## 8. C与HTTP边界

B不增加Common跳控制。resolve是一个已准入worker任务，沿begin保存的绝对D完成两次prepare+最多一次lookup；每次I/O前后现有D检查保持。任务中途stop/detach不伪造HTTP取消；回到合法任务边界关闭下一任务，owner抑制金融SPI且保真实失败。尚未准入的任务不启动I/O。

HTTP Exchange实际拥有 upload string、wide headers、64KiB buffer、请求句柄/完成状态；调用者DTO/control不是异步借用。其client最多64 pending session，drain_callbacks/卸载仍归唯一client/Standard owner。B来源析构与HTTP HANDLE_CLOSING独立，不能用保留query替代HTTP持有清单，也不能用B释放认为可卸载DLL。C后继必须在账户I/O前给EventChain增加完整来源/任务reserve及HTTP pending账，再接FIFO；本片没有替它声称闭合。


### 验证边界

覆盖完整原row唯一性、后续ORDER与精确DEAL、双来源原index/metadata、历史Event/Query proof实际来源、输入销毁后三阶段、错owner/ticket、原D与任务停止、预算need/need-1、ADOM与A helper DOM并存、独立票据文本、matcher内部DOM、长remark、各阶段分配失败/RAII；旧Query/Event/P8/金融映射全部适用兼容。预算实现的sizeof与字段表须独立核对目标值，静态定义不授编译/动态资格。


### SEV-R5d-B 实施前置计费补充（同accepted合同，接口不变）

- 完整 event envelope 的派生摘要沿原 json_text(event)；CountingWriter 在其分配前取得长度 H，begin_need 另加 2*(H+1)，覆盖该独立 StringBuffer 与返回 string。payload 的 e 银行继续独立，两者不相抵。admitted.kind 与来源 kind 同时存在，各最多6字节（含NUL），共12；两个派生SHA继续各65。
- matcher 本身以同类异常表达容量与结构，B先计完整 rows 各原编码长度 Lrow，拒绝超过1MiB的行并核原 rows/输入限额，再核保守子峰值 128+Q+(e+1)+4096+max(2*(max(Lrow)+1),max(Lrow)+1+4096) 不超过 match.max_work_bytes。此保守准入可拒绝非常小的子限额；容量返回固定 Backpressure，余下 matcher 结构异常保持 InvalidInput。match_need 必须在 matcher 调用前核验，完整 need 必须在来源复制和 WT 构造前核验；不靠返回后的 peak_work_bytes 追认。
- 新 QmtEventQueryIdentityBudget.match 使用 {} 零初始化；部分填写 identity/max_work 时，缺少 match 限额按 InvalidInput 确定拒绝，不读取未初始化值。旧 AccountEventMatchLimits 定义不改。
- resolve 首次返回 holder/State 尚未建立前的 bad_alloc 保留原接口传播：Plan 作为值参数已消耗，调用者 catch 后仍在原 owner 回收 Candidate；不能重试该 Plan。holder 建立后的 EventQuery 资源失败为 IoError（允许空 reason）。不二次分配应急对象。
- 匹配的 InvalidEvent/InvalidQuery/NotRequired 按已完成 typed 结论返回 InvalidInput；其余非 Matched/不同原index 返回 Conflict。原结构异常保持 InvalidInput，容量只沿前置 checked Backpressure；不解析 reason。
- admission_aux 文本银行显式为205B：已验 descriptor.binding_sha256 为65，Bootstrap profile摘要比较两份SHA各65，policy字符串4、kind字符串6（均含NUL）。admission_need和begin_need均加此银行；其与后续kind银行的保守重计不退还。

#### R5d-B 实施补充：可识别双来源的错误出口（accepted）

begin 的结构异常出口返回 InvalidInput 空 reason；实际资源失败为 IoError 空 reason。resolve 已建立返回 holder/State 且持有 EventQuery 来源后，各异常出口沿原分类无分配形成 Status；初始 holder/State 尚未建立前的既有 bad_alloc 传播边界保持。

finish 只读 Candidate 或 Resolved 的纯值来源类型；能识别 EventQuery 时，错 owner、缺 Resolved、错 ticket 及异常出口以固定 code/空 reason 无分配返回。错 owner/错 ticket 两句柄均保留，前置检查不触碰或销毁 WT 对象。Candidate 存在时其来源优先；Candidate 不可用而 Resolved 有来源时可按其识别。两句柄皆空属于既有无来源 API 边界，保持原 InvalidInput 文本行为，无法据此识别此前的入口种类；双消费测试独立登记此边界，不新增来源 flag/句柄。普通 Query/Event 的原诊断行为保持。

新入口原 D 检查后先按旧 identity 三子限额的相同合法谓词准入，任一非法返回 Backpressure/空句柄；共享 PayloadBudget 构造器及旧入口分类保持。验收包含可识别来源的错误 owner/缺结果/错票据无分配与句柄保留，结构异常出口再次分配失败，原 D 优先和六个子限额边界；编译/故障注入结果单独记录。


## SEV-R5d-B-RESOURCE：profile资源异常通道与Identity精确分类（accepted）

本节核定profile资源异常与Identity精确资源分类。实现、测试、编译及动态资格分别登记；既有冻结证据保持原输入身份。

1. `validate_qmt_trade_read_profile` 的实际 `std::bad_alloc` 保留原异常传播，资源catch不构造Status、不创建reason、不二次分配、不返回Backpressure或InvalidInput。显式结构/参数/账户绑定失败沿原Status code/reason，成功仍单次noexcept移动发布；失败保持调用者out原值。此接口不声明noexcept，旧签名/DTO/成功bytes不变。正常输入拒绝可构造原诊断；“资源路径无分配”精确指已捕获bad_alloc的处理路径，不承诺所有非法输入诊断均无分配。
2. Query/Event/EventQuery三个Identity begin的业务try对实际bad_alloc统一以IoError/空reason返回，原owner回收其候选/计划。resolve的初始holder/State未建立前原bad_alloc传播边界保持；holder建立后的业务try精确捕获bad_alloc并返回IoError/空reason。finish同owner/同ticket业务try捕获bad_alloc后IoError/空reason并按原规则退休匹配句柄；同步兼容map入口精确捕获bad_alloc形成同一资源Status。原D、预算、Owner、错票据/错owner保留、候选销毁线程及金融成功值保持。
3. 这项修正显式改变旧异常分类：旧Event profile分配失败从Backpressure改为IoError；若只改Common会误落入旧std::exception→InvalidInput，因此两层一起核定。旧Query通过Shm profile.ok()产生的runtime_error→InvalidInput，以及旧Query/Event业务try其他bad_alloc→InvalidInput，均收敛为精确IoError。结构性std::exception仍沿旧InvalidInput，显式容量Status仍为Backpressure；不能批量改写这些Status。旧非法句柄前置文本诊断和双空句柄边界不在本次扩展为noexcept；本节不宣称所有旧诊断构造均不抛出。
4. Shm mapper的旧/选行入口继续调用同一profile validator；bad_alloc穿透.ok()/check，不改为结构runtime_error。Common prepare及私有receipt的bool调用同样让资源异常穿透，正常非法profile返回码保持。Common已有POST未知/原receipt保存责任、GET恢复、typed只读Failure和实际drain规则保持；不得因资源异常清unknown、重POST或授新D。Standard/WT无需新增分支或测试开关，现owner/worker统一异常边界负责收口。
5. 验收先同来源复现实际point3，然后直接profile单次/persistent故障，核抛出类型、原out哨兵、无资源catch诊断分配；分别测Query/Event/EventQuery begin与resolve/finish资源分类、真实原D和线程/引用回收。旧A selected_row_probe中translated-profile分支只属于旧冻结行为，新来源需明确统计bad_alloc路径，保每个注入点/原金融断言，不能删除注入或放宽到任意失败。重新measure N后按新源分片，不复用旧1299/10263。具体方法/场景计数以实际定义另冻，不预先宣称通过。
6. 本片不增加外部协议/权限/数据库/线程，不修改WT；测试、编译、动态及独审分别登记。完整R5、Standard C、R8及真实SDK仍沿各自范围。


## SEV-R5d-C：标准插件缺字段真实补查接线（accepted，状态与接口要求）

本节核定标准插件的补查状态、来源、控制与生命周期要求；实现、完整逻辑费用及整链运行资格分别验收。容量函数仍须按下面C10关闭全部组成，不能从本节accepted推导为已闭合。复用WT-T01/T02的ITraderApi/ITraderSpi和TraderAdapter、现有Common账户读取、唯一matcher/金融mapper及B三阶段；源码范围为TraderQMT自有接缝，不新增WT修改、网络client、worker、数据库或金融账本。完整R5/R8/生产切换保持各自验收边界。

|要求|行为与验证标准|
|---|---|
|C01 完整路径|原可信完整order/deal沿旧事件begin；账户补查POST为0，旧金融值、旧身份规则及错误语义保持。error事件沿原有限诊断/索引，不进入金融补查。|
|C02 唯一分流|有界计数/编码原payload，复用inspect_account_row。仅MissingRequired且locator_complete进入补查；Invalid、关系冲突、缺定位、解析/资源错误各保真实分类，均不发账户补查。前后检查原D/event_control，不将非法/null解释成缺失。|
|C03 真查询与选行|原单worker执行同datatype账户读取；任务选择统一沿[STQ-P27](native-qmt-standard-trader.md#stq-p27-单-worker-按原绝对截止选择待执行任务accepted隔离开发中)，按原绝对D选择、等D保持入队顺序。完整原QmtAccountResult交唯一matcher，全rows唯一匹配才把原page/index与完整Q/原row_index交B。仅所选行一个对象进入实时SPI，本地下标0与原query下标/数量分别保留；不向历史onRspOrders/Trades回放整批，不改变query_flow_mask。|
|C04 匹配语义|ORDER允许真实后续状态且核原不变量；DEAL核原成交scope。重复完全相同行、多匹配、潜在匹配/Uncertain、InvalidQuery、冲突、无匹配均不发布，不拼字段或合计成交。|
|C05 一次读取|同一EventQuery任务连续调用原prepare、create_request、submit_once，每步用同一个SignedHttpDeadline、显式out控制及event_control。prepared token至多消费一次；Common内部202/follow及原UUID GET沿原算法，不增加外层Pending循环、重create、重POST或刷新D。构造account_control与按次event_control仍做OR；停止补查不停止普通账户查询。|
|C06 真实来源与失败|submit前独立复制完整saved_receipt，核真实B/profile/read_result_capacity与原可信event_context一致；不匹配无POST。保完整原Q、receipt、实际control/outcome/stage及query步骤；异常和空返回receipt不能清原副本。先处理实际Failure，再看迟到或停止；不从reason文本推断可重试。|
|C07 停止与保留|prepare/create/submit各阶段停止、解绑、来源变化/异常、返回后stop均保真实事实。正常ControlStoppedBeforeStage只有Common真实返回时可据其表达；未调用阶段仅保本地步骤/停止事实，不造Common结果。局部copy/source验证bad_alloc等即使control为None，仍是明确本地Failure。detach抑制后继补查/金融SPI，普通查询控制保持。|
|C08 原D与发布锁|原链D覆盖排队、Common内部、matcher、B begin/resolve/finish和SPI前。EventQuery及EventResolve在publish原mutex内、commit前执行Failure优先的写门/worker屏障。实际Failure保原operation status；迟到成功单独记delivery Timeout/late。owner在旧通用deadline过滤前接收新阶段，不用Timeout覆盖已知首因。本轮普通pump配额耗尽仍维护原事件D。|
|C09 单worker/原D|新增Kind::EventQuery及EventPhase::QueryInFlight；事件链最多一个在途阶段。owner构造Candidate，worker仅接独立Plan/值，finish/SPI仍owner且锁外。EventQuery与EventResolve追加同一有界队列，取出统一沿[STQ-P27](native-qmt-standard-trader.md#stq-p27-单-worker-按原绝对截止选择待执行任务accepted隔离开发中)；普通任务按各自原D推进，Common单次同步follow继续沿原内部GET算法。push成功才转TaskCredit，名额与有效载荷分别退役。|
|C10 前置逻辑预算|原max_queue_bytes仍唯一实例总额，硬限512MiB；新完整准入仅events_enabled，关闭事件保持旧准入。采用固定控制/两client及64+64 HTTP槽（含active）+单worker峰值+单owner峰值+实际常驻普通票据/写pending/审计+context/index+单事件链的互斥覆盖清单。各同步入口含拒绝前窗口及真实深文本，不用16DOM乘队列。原页/外层query与B独立来源分别计；外层matcher退出后才进入B。matcher cap由现限额/可信来源checked推导，B cap按同一总额可承诺余额冻结至真实终态，不把两者设为同一值。全部I/O/复制/WT构造前取得费用，超额Backpressure且无对应新I/O，异常不丢值换额度。G3写/UC/event完整同步费用表、新字段sizeof及原64/256/512配置账单须在完整C验收前闭合。逻辑值、allocator余量/物理RSS分别登记。|
|C11 资源与责任|预分配CompletionRing槽先于I/O。EventQuery与带不可丢事实的新事件resolve不走普通容量丢payload路径；保存receipt失败发生在submit前。POST后异常保原UUID/实际返回原件及步骤。资源出口固定code/空reason，不在catch重新分配；B初始holder前Plan消费/异常边界沿B合同。逐阶段负向核引用、金融候选线程和真实退费。|
|C12 新身份来源|EventQuery observation只取所选query Remark作token；OrderRef只诊断，event Remark不fallback。缺失/null/0/普通文本保external规则，两完整有效Remark冲突仍拒绝。当前金融query与历史broker proof保不同来源，不用当前查询回填历史Event/Query proof。|
|C13 原交付索引|用原event sequence/事件SHA与所选query canonical金融事实形成observation。Returned/Unknown/Suppressed/duplicate/ORDER进展及cursor沿原索引；仅真实交付完成推进原handled，不因查到/匹配成功提前ACK。跨完整/补查同Remark、归属与金融不变量可期望Duplicate；仅OrderRef token或两scalar矛盾沿原旧Event规则可能真实Conflict，不能为通过测试暗改旧算法。|
|C14 真实退出|stop先关新阶段，owner可先退WT Candidate；Plan/Resolved及纯值晚完成仍保owner。close D只冻结一次，两个client真实drain、worker_done/active_ingress0及实际join后才清链原件/费用及卸载资格。截止未完成继续保owner/依赖，不以清状态、强杀或刷新D冒充closed。|
|C15 兼容与切换|原Common/Standard/P8/mapper/event retry/unknown-cancel按最终输入复用或重验；新query schema不污染普通查询/旧事件。生产Factory保持现入口直至对应独立发行验收，测试成功不自动切换。|
|C16 整链验收|使用实际候选Factory→Host认证运输→Win32 SHM→原线程SDK替身→原版Adapter公开push验证。核原源码/配置/制品、源调用与POST/UUID计数、WT实际金融getter/借用及原D/Job/tree0/EOF/join/资源关闭；纯值测试不替代这条链，替身不替代真实SDK。|

### C 状态和原件的确切持有者

1. Task保存原id/generation/stage/D、原可信event_context独立值、event bounds/index；page/validated/WT对象只在owner链中。Completion复用完整account，新增saved_receipt、control_result、QueryStep及必要纯值来源定位。步骤至少区分None/Prepare/Create/ReceiptSaved/SubmitEntered/Returned；SubmitEntered仅表明已调用方法，不能断言真实POST已经发出。
2. EventChain持有单个QueryEvidence：完整saved_receipt/account/control/step、origin id/generation/event_index、query_status、resolve_status、query_delivery_status/resolve_delivery_status、query_late/resolve_late及query_received/resolve_received。正常与stop后的完成值都先在原链匹配身份后无分配移动到此holder。Query成功进入B后不清原Q，B复制的Sources是另一实际owner。错generation/ticket/index在pop前锁故障并保原Ring值到真实join后的统一清理，不能移入其他事件或继续I/O。
3. Completion.status始终表示真实operation/local operation结果。新增独立delivery_status及late，发布锁只以固定code/空reason记录本地迟到/交付错误；它们不能覆写prepare/create的原Pending或真实Failure。QueryEvidence.query_status/resolve_status只接原operation，对应query_delivery_status/resolve_delivery_status与query_late/resolve_late分别接其交付事实，不覆盖另一阶段。实际Failure包含typed Failure、非正常非OK、本地资源/校验异常及不合法控制形状；不得仅以control.outcome==Failure识别。正常typed停止、local stop、迟到成功与真实Failure分别测试。
4. publish同锁在commit前先识别真实Failure/delivery_fault并关后继worker/write；无真实Failure再核原D并记delivery Timeout。owner pump在旧通用1530过滤前接收这些事实，然后决定Failure→D/normal stop→成功推进。EventResolve无逐HTTP control，任务已进入后沿B原D完成，回到任务边界抑制SPI。
5. retain_stopped_results新增同样QueryEvidence移交与B真实status保留；这里不做matcher、Bbegin或金融SPI。retire_completion先真实销毁已搬空的控制/结果成员再退其费用；移动进链的内容继续由链银行承担。只在正常交付/重复终态后、mapped Result/observation/SPI借用全部退出，retire_current_event_query才析构该项证据；advance_event单独推进下标不提前退款。stop/detach后原件保到实际join/release；整页链银行按原终态一次退役。
6. 验证冻结确切输入名单，不把C01–C16维度数量当实际执行数。单独覆盖查询成功发布前跨D且队尾有写、真实Failure后跨D/stop、prepare/create正常停止且account为空、本地receipt copy失败control仍None、stop后retain及真实join后析构。公共主链优先；公开ABI不可见的少数receipt/费用事实可用既有测试宏友元只读探针，不增加生产Diagnostics或手造私有状态替代真实调用。

容量实现与整链资格仍须C10/C11/C14/C16的实际证据；本节不新增账户许可或实盘资格等级，不证明R8共同cut、跨重启exactly-once、真实交易或生产发布已完成。

### C10/C11 新事件域异常诊断的有限边界（accepted）

完整新逻辑银行不能用H自动约束任意SPI/第三方std::exception::what()。events_enabled域的init/pump/新接续资源与意外异常出口保有限固定ErrorCode/空reason，保此前已锁定的真实首Failure/SubmissionUnknown，不复制任意what、不在资源catch分配诊断；停止后继业务按原owner/worker及原close D推进。init可先只读识别原事件配置是否存在，以选择此异常策略，原字段准入与合法配置次序保持；events_disabled沿旧异常行为。普通有据的有限本地/来源Status继续保完整原值，C10明确的容量不足仍为Backpressure；不能把真实业务Failure或未知提交改为成功。测试须用长what及分配失败验证有限诊断、首因保留与真实退出，不把模型外allocator/RSS宣称为已验。

#### C 配置文字的原生借用边界

events_enabled 域通过 WTSVariant 的原公开 asCString() 读取配置文字：先核 VT_String，以首个 NUL 终止的 C-string 前缀作为该入口唯一可观察正文；先扫描至 cap+1 并核非空及原字段上限，再仅复制已确认的有界前缀。配置解析及全部后继消费者使用这同一前缀，复制前不得调用按值返回的 getString/asString。底层 std::string 在首 NUL 后的隐藏后缀不属于该公开入口可观察正文，本实现不声称检测或验证该后缀。原公开 API 缺少借用长度，此约定避免为读取配置增加 WT 框架接口或访问私有布局。初始化拒绝前的有限复制窗口须纳入 C10 费用表；events_disabled 保留既有配置行为。

#### C 诊断复制的交付失败

EventQuery Returned 与 EventResolve 的完整原 Status 分别继续由原 account/resolved 对象持有。向 Completion 的 operation 槽复制诊断时先保原 ErrorCode；reason 复制发生资源异常，只清该副本 reason 并将独立 delivery_status 记为固定 IoError/空reason，不改变 operation code，不把它改写成本地 operation Failure。原完整来源 Status 保留，副本诊断降级由 delivery 失败准确记录。真实 operation Failure 优先于 delivery；原 OK 或合法 ControlStoppedBeforeStage/Pending 后的复制异常必须以 delivery IoError 结束，原 Pending 的正常停止身份保持可辨。原 D 只在 delivery 尚为 OK 时补 Timeout，已有交付故障保持。该规则不新增重试、补查、I/O 或 WT 接口。

## SEV-R14 查询优先首次事件前沿（accepted 实施）

范围为自有标准插件显式 `order_context=query_first` 且开启事件消费的首次 Prepare。原 native/default 路径及未开启事件的路径保持原行为。本节收敛新客户端从零重放 Host 历史事件、逐项触发重复账户查询而拖慢实际增量的问题；完整四查询仍各自取得券商事实，不构造四查询原子快照。

1. worker 完成原来源认证、读取上下文和原命令恢复来源固定后，在向 owner 发布首次连接、触发 position→order→deal→account 四查询之前，沿原 Common `events(source, after_seq=0, limit=1, admitted_event_page_capacity, D)` 取得一次有界页。使用已核验 receipt 的 `durable_through=T`，小页的 `next_sequence` 仅代表本页末序号，不能用作完整前沿。
2. 首份 receipt 尚未建立时，原 Host 可以返回 404/NotSupported；在原 Prepare 绝对 D 内、以原 event_poll_ms 等待同一来源的首份 receipt，stop 可唤醒等待。后继合法页成功必须覆盖暂态 Status 为 OK；有效 T=0 与尚无 receipt 分别表达。其他原错误、来源 gap 或到期沿原 Prepare 失败出口结束，不退回猜测的零前沿。
3. owner 仅在首次安装认证上下文时将 `read_cursor` 和 `handled_cursor` 初始化为 T。该值表示随后四查询覆盖的启动基线；交付索引保持空，不为此前事件制造 SPI 已返回记录。完整四查询成功后，原 query_flow_mask=15 才允许消费 T 之后的事件；四查询之间到达的事件继续保留在原 Host 流中，并由原增量链消费。原处理前沿连续检查从 T+1 继续。
4. Login、同实例后继读取及原运输恢复沿已安装上下文和既有游标继续，保持原校验，不重新取得启动前沿。来源换代与原未知委托仍受既有身份和恢复职责约束；本节不清空 pending/retained receipts/unknown_fenced，不替代原 audit、resume 或按原命令身份核查，不授权未知结果重新提交。
5. 小页请求前沿用原 ContextBanks.chain 预留临时逻辑费用，保留至该 Prepare Completion 原终态退役；持久 context 沿原独立费用转移，不重复计入事件交付索引。原 HTTP 页上限、绝对 D、Host 事件保留与 ACK 归属保持，不增加磁盘表、删除或消费确认。

验收先覆盖三个主路径：native/default 从原零游标继续；query_first 在已有多条历史事件时取得完整 durable_through 而非单页 next_sequence，并在原四查询后消费下一条增量；首读 404 后在同一原 D 内出现合法 receipt，Prepare 应成功。原标准插件/Context 验证入口继续承担完整四查询、未知命令责任和增量 SPI 的组合验收；函数级合成验证与完整插件运行证据分别记录。

本节描述查询优先接入的启动分界，不声明券商四查询共享事务、历史事件已逐项交付、跨进程 SPI exactly-once 或真实 SDK 已完成所有交错验收。SEV-R8 其余缺口保留原范围。
