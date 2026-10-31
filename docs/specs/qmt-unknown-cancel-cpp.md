# QMT 未知取消 C++ 实施契约

状态：accepted implementation（动态未验）。类型：Common/Standard 唯一 C++ 实施正文。日期：2026-10-25。

本规格细化[未知委托定向核查与取消](qmt-unknown-cancel.md)的 UC-R2/R4/R7/R8 及 UC-R9 C/D，固定 Common DTO、调用、版本冻结、Standard 状态机、观察合并、字段预算和生命周期。Host/Agent wire、Journal、原业务准入及账户事实沿主规格；C++ 精确字段与并存预算以本文为唯一正文。accepted implementation 确认实施要求，产品实现、编译、隔离验收和运行资格分别取得证据。

## UC-CPP-R0 范围、复用与资格边界

复用 WT-T01/T02/T09 的 queryOrders、orderAction、原订单 isAlive 与正常查询/事件交接，沿 [WT 原生能力目录](../development/wondertrader-capabilities.md)及[复用规则](../development/wondertrader-reuse.md)。新增状态仅保存通信身份、原文和有限观察；资金、持仓及订单金融归约属于 WT/唯一 mapper，实际账户事实属于 QMT。

Standard 使用原唯一 worker、Pending、队列、TaskCredit、generation 和 stop/drain/join。自动 ORDER 读仅让 Host 原 BoundReadJournal/TradeOrderLinks 获得真实通信 proof；审计不调用 mapper、BaseDataMgr、remember、onRspOrders、onPushOrder，不增加 queries/inserts/cancels。正常 Query→Resolve→onRspOrders、EventPage→EventResolve 保持原通道。没有真实 WT alive 订单时不能主动造单或发起取消。

私有 cancel reference 只在 worker 本轮栈内；首次 lookup 后可 resume_cancel。跨轮只保存已验实际 QmtTradeReceipt，使用现 public resume(receipt,D) 重新完整准入后 GET 原 UUID。公开 receipt 不转换成私有句柄或 prepared token，不授 POST。

unknown insert 继续持有原 receipt/fence，当前一般恢复后重开 insert 的解除契约保持未闭合。实施不新增人工资格、不改 WT 框架、不切生产 Factory，不授权真实 SDK/账户动作或生产发布。Common HTTP/解析临时对象与宿主逻辑 payload 分层，本文不声明 RSS 上界。

源码入口：TradeClient.cpp/h 指 [QmtHostTradeClient.cpp](../../src/GuanhengCommon/QmtHostTradeClient.cpp) / [头文件](../../src/GuanhengCommon/QmtHostTradeClient.h)；Standard.cpp 指 [StandardQmtTrader.cpp](../../src/TraderQMT/StandardQmtTrader.cpp)；BoundReadCore.cpp 指 [QmtBoundReadCore.cpp](../../src/GuanhengCommon/QmtBoundReadCore.cpp)；HostCodec.cpp 指 [QmtHostCodec.cpp](../../src/GuanhengCommon/QmtHostCodec.cpp)；HistoryClient.h 指 [QmtHostHistoryClient.h](../../src/GuanhengCommon/QmtHostHistoryClient.h)；HTTP.cpp 指 [BoundedSignedHttp.cpp](../../src/GuanhengCommon/BoundedSignedHttp.cpp)。行号辅助定位，行为与字段须按当前源码验证。

## UC-CPP-R1 Common 精确 DTO 与调用

以下 C++17 声明固定新增字段和接口；它不代表产品已经实现。字段均属于通信身份/原文，禁止添加金融状态或 WT 地址。

~~~cpp
class QmtTradeCancelReference {
public:
    ~QmtTradeCancelReference() = default;
    QmtTradeCancelReference(const QmtTradeCancelReference&) = delete;
    QmtTradeCancelReference& operator=(const QmtTradeCancelReference&) = delete;
    QmtTradeCancelReference(QmtTradeCancelReference&&) noexcept = default;
    QmtTradeCancelReference& operator=(QmtTradeCancelReference&&) noexcept = default;
    const QmtTradeReceipt& receipt() const noexcept { return receipt_; }
    QmtTradePhase phase() const noexcept { return phase_; }
    const std::string& record_json() const noexcept { return record_json_; }
private:
    QmtTradeCancelReference() = default;
    friend class QmtTradeClientCore;
    std::shared_ptr<const std::string> owner_; // 原 Core owner 身份
    QmtTradeReceipt receipt_;                // 实际取消的原 admitted B/body/profile
    QmtTradePhase phase_ = QmtTradePhase::Unknown;
    std::string record_json_;                // 唯一已验完整 bound-trade 原记录编码
    std::string original_command_id_;        // 原 insert UUID，恰 36 字节
    std::string original_command_sha256_;    // 原 insert canonical SHA，恰 64 字节
};
struct QmtTradeCancelLookupResult {
    Status status;
    bool no_cancel = false;
    std::unique_ptr<QmtTradeCancelReference> reference;
    std::string response_body;
    unsigned http_status = 0;
    bool response_complete = false;
};
// 以下为原 QmtHostTradeClient 的新增 public 声明。
QmtTradeCancelLookupResult lookup_cancel(
    const QmtTradeOrderReference& original, SignedHttpDeadline& originalD);
QmtTradeResult resume_cancel(
    const QmtTradeCancelReference& actual, SignedHttpDeadline& originalD);
~~~

字段最小性：owner 防跨 client；receipt 支持原 UUID GET；phase/record 是正式 R4 accessor 约定；原 insert UUID/SHA 把该句柄绑定唯一目标。账户、EntrustID、userTag、broker、实际 cancel UUID/SHA 均已有于 receipt/record，不再复制成字段。LookupResult 不增加 reference_json/source_result_json/原 insert receipt。unique_ptr 转移结果；引用对象不可复制，析构释放 receipt/record/两个目标串和 owner 引用。共享 owner UUID 的字符串沿既有 Core 归属计一次，不能每句柄重复计算其 payload。

lookup_cancel：先 check owner/thread/D，再核 original.owner、原 insert receipt 原 bytes/UUID/SHA/operation；按正式 R4 精确形状读取。在完整、未过 D 的合法 200 才解释 cancel:null；404/409/超时/截断分别保留原语义。对实际记录复用现 bound-trade validator，并核 operation=cancel、original_command_id、account/binding_id/EntrustID/userTag 与原 insert 一致，broker 与已有原关联一致。缺当前 broker proof 仍可读历史实际取消，所得句柄不授 create_cancel。实际 admitted/dispatch/result B 保存原历史真值；不换成当前 B。

先构造全部私有字段，再检查 record_json.size() ≤ min(C,record_capacity(descriptor))，固定错误原因最长 38 字节，最后核 D 后一次 move 发布；异常保持 reference 为空。record_json 是嵌套 cancel 的唯一完整已验 canonical 编码，不保额外嵌套 DOM 或额外 raw 字段；response_body 保持完整运输原文。因此确有 response/record 两份文本。新增原因若超过 38 必须同步预算。

resume_cancel 在任何可返回分支先把phase设Unknown，并完整保存actual.receipt；original_record=false。随后检查同Core owner（含线程）、目标UUID/SHA和已验receipt一致性，再复用原resume做一次原UUID GET。错owner/过D/验证失败不退回默认NotSent；只有真实original_record能更新phase。receipt复制失败时不返回半对象，调用方原私有句柄保持完整。它继承本轮D、不携prepared token、不调用submit；新client真实lookup重建句柄，公开receipt只可public resume重新准入后GET。

## UC-CPP-R2 版本、来源与 owner 冻结

固定来源分两层：Common Core独立冻结HostStatusVersion与SourceStatusVersion两个私有枚举、原B/session/原profile；首次成功prepare同时固定。每次refresh对两个版本分别精确校验，create_cancel前、submit前均刷新/比较；同owner任一版本漂移/降级按stale。Host v2/Source v1仅保原普通能力，不能授unknown cancel。audit_source只保存一份worker首次prepare取得的B/session并检查活实例不换代，不能替代两个版本枚举或Core profile冻结。版本枚举不增加字符串payload。所有Pending共用插件generation，同B/实例的order.state非NotStarted即表示已消耗一次新ORDER额度。

## UC-CPP-R3 Standard 精确状态与原子观察

沿现 Impl::Pending map、mutex、generation、TaskCredit、Task/Completion 队列；新增 Kind::AuditOriginal。以下清单固定完整私有字段；不保任意原因串、DOM、私有句柄或 WT 地址。

~~~cpp
enum class PendingOperation { Insert, Cancel };
enum class PendingRole { OriginalCall, UnadmittedTargetLookup, TargetObservation };
enum class OrderAuditState { NotStarted, Started, Terminal };
enum class TargetLookupState { NotObserved, NoCancel, Actual };
enum class AuditDiagnostic { None, RetryTransport, Deadline, Capacity,
    IdentityConflict, SourceChanged, HardFault, Stopping };
struct TradeObservation {
    QmtTradePhase phase = QmtTradePhase::Unknown;
    bool has_record = false;
    bool terminal() const noexcept {
        return has_record && (phase == QmtTradePhase::SdkReturned
            || phase == QmtTradePhase::DefinitelyNotCalled);
    }
};
struct CancelObservation {
    QmtTradeReceipt receipt;
    TradeObservation observed;
};
struct OrderObservation {
    QmtBoundReceipt receipt;
    OrderAuditState state = OrderAuditState::NotStarted;
};
struct Pending {
    QmtTradeReceipt receipt;       // 不改原bytes；只有无异常改key提交时整体替换
    std::size_t charge = 0;
    PendingOperation operation = PendingOperation::Insert;
    PendingRole role = PendingRole::OriginalCall;
    QmtTradeReceipt target_insert; // Cancel必填；Insert target()直接用receipt
    TradeObservation own;
    OrderObservation order;
    TargetLookupState target_lookup = TargetLookupState::NotObserved;
    CancelObservation actual;
    Clock::time_point next_due;
    std::uint64_t inflight_task = 0; // 原写/审计task ID，0表示闲置
};
struct AuditInput {                // mutex内完整复制，锁外仅用独立值
    QmtTradeReceipt receipt, target_insert;
    PendingOperation operation;
    PendingRole role;
    TradeObservation own;
    OrderObservation order;
    TargetLookupState target_lookup;
    CancelObservation actual;
    bool actual_in_other_slot = false; // 仅本轮调度提示，不改变任何持有责任
};
struct AuditSummary {
    PendingRole role = PendingRole::OriginalCall;
    TradeObservation own;          // 对应原immutable receipt；由ticket/key绑定
    OrderObservation order;
    TargetLookupState target_lookup = TargetLookupState::NotObserved;
    CancelObservation actual;
    AuditDiagnostic diagnostic = AuditDiagnostic::None;
    ErrorCode error{};
    bool apply = false;            // 完整初始化前false；不覆盖Pending旧观察
};
// Task仅新增pending_key；AuditOriginal不填order/plan/event_context。
// Completion新增AuditSummary audit；command_id与pending_key做noexcept swap。
// 普通可重读任务另用capacity_reason承载固定容量诊断，见下文；Audit该字段始终为空。
// Audit Completion.status.reason为空；精确未受理事实唯一编码在role，删除own_cancel_not_admitted。
~~~

has_record/phase 与其对应 receipt 构成一个观察组；terminal()由这两项派生，消除可分离的 terminal 缓存。own 的 receipt 是 Pending/Input 已冻结的原字节，Summary 只带无分配的观察元数据，由 key/generation/inflight ticket 关联；actual 把 receipt 与观察元数据封装在同一个值中。OrderObservation 的 receipt/state 同组；TargetLookupState::Actual 当且仅当 actual 非空，NoCancel/NotObserved 的 actual 必为空。

原子性固定如下：

1. owner调度先在mutex内计算并charge全链，再分配key/Task、置inflight。worker出队持锁核key/generation/ticket，完整构造独立AuditInput；无跨锁Pending指针/字符串借用。原写创建Pending时即令inflight_task=原写task.id；owner在全部合法写完成分支（含错误、晚pump、detach抑制）核ticket后才清零/设置next_due，避免原写在途就调度审计。
2. Summary用完整Input初始化全部观察组、role与target_lookup，全部复制完成才令apply=true；初始化复制失败只留下apply=false，Pending完整旧值保持。阶段输出只更新完整观察组；运输失败保留已验旧组，不清has_record、不使终态回退。
3. 新ORDER：在空临时OrderObservation复制完整prepared receipt，成功后设置Started，再通过noexcept swap安装到Summary，之后才submit_once。复制失败不提交，不消费一次ORDER额度；安装成功后即使submit抛异常/超时，Summary仍携原receipt/Started，不再次create。
4. 替换actual：先核新候选全部合法；Input仍保完整旧actual。销毁Summary旧actual，令该槽暂空，在空槽预算内完整复制候选receipt并配齐phase/has_record；成功后noexcept swap，最后同时设target_lookup=Actual。失败则将Input旧CancelObservation整组noexcept move/swap恢复（含phase/has_record和原target_lookup），以完整旧组结束本轮；禁止只恢复receipt。每轮至多一次这类替换，不保第三份summary receipt。旧actual仍unknown时不进入替换路径。
5. owner先处理AuditOriginal，位于通用deadline/fail分支之前。核ticket/generation后，在同一mutex内完成所有可失败准备/身份核对，再通过显式noexcept swap和标量赋值一次提交role、own、order、actual、target_lookup。key更名/合并也在同一次提交。receipt/phase/has_record、read receipt/state及已证未受理事实没有外部可见半快照。失败保Pending完整旧值或完整已提交新值；Summary保留新read责任，不能被通用response_failure清空。
6. 所有catch/晚完成/发布路径保持已保存的新ORDER和精确未受理角色事实。审计晚完成继续做保守receipt/Started记账；只按Common original_record/末D结果采用阶段证据。Input和所有旧组先析构再退charge；Completion仍持有的组继续收费。

普通完成值的容量诊断与审计事实分开：Completion::capacity_reason为std::string，仅普通可重读任务在已经取得Task和完成槽、实际I/O前填固定ASCII qmt_standard_result_capacity（28字节）。空环槽及Insert/Cancel/AuditOriginal均保持空串，Task字段保持原约定。该28字节与普通任务其余有限诊断共同计入原512预留，不增加Audit的T/Σ/Peak。成功发布前真实析构该字符串再结算差额；容量不足及外层异常先析构普通account/resolved/context/page等可重读载荷，再无分配交换容量诊断或发布交付故障，保kind/id/generation/D/order/原charge至owner真正退休。不可丢的三类通信完成值始终保完整receipt/Started/U及已预留额度，不能调用普通载荷丢弃路径；其超过原reserve属于不变量故障，保值并停止后继worker工作。

## UC-CPP-R4 读取状态机与条件合并

一轮读D在入队时取now+request_ms，所有prepare/GET/ORDER/lookup/copy共享它；原写/查询body业务D保持。所有角色均不POST取消、不调用金融mapper/SPI、不增加queries/inserts/cancels。轮间至少隔request_ms，轮转Pending，最多一条audit链（队列/worker/完成队列/owner栈均占audit_inflight）。

| Pending角色/观察 | 本轮允许的读取 | 完成/失败后持有 |
|---|---|---|
| OriginalCall，own未明确终态 | 原receipt GET；必要时一份新ORDER或原ORDER resume；ORDER lookup；cancel lookup；实际B原ID GET | 原调用未知始终保原receipt；insert unknown不因proof/目标取消终态退役 |
| OriginalCall，own明确终态 | 不再GET原调用、不新建ORDER；仍Started的原ORDER只resume；仍未决actual只GET该ID | 未决read/actual责任全部结束后才退役；明确终态原调用仍可留有限槽作read drain |
| UnadmittedTargetLookup，NotObserved | 不GET A；原ORDER若Started则resume；只读ORDER lookup以取得私有原insert引用，再lookup_cancel | 运输失败/畸形/超时保持此角色、A/target/read及原charge，下一轮继续target lookup |
| UnadmittedTargetLookup，NoCancel | 不GET A、不再target lookup、不新建ORDER；若原ORDER仍Started只resume它 | NoCancel仅表示那次合法lookup无实际取消；原A已知未登记独立保真；原read安全后退役A |
| UnadmittedTargetLookup，Actual=B | 不GET A、不新建ORDER；原ORDER若Started只resume；B无其他有效槽时只GET B，已有有效B槽时由B槽承担其原ID GET | B/目标事实保留；按下述矩阵安全移槽/合并；冲突read时保A/B各槽，不覆盖 |
| TargetObservation | 原实际B作为receipt只GET B；Started原ORDER只resume；B已终态不新建ORDER/新GET | B终态且无Started read责任后才退役；它不是原申请A成功，不发普通写回调/统计 |

精确未受理入态：只有完整、未过D、严格校验的精确cancel_pending能将原取消A置为UnadmittedTargetLookup；这是“本次A未登记”的持久通信事实。own.phase仍Unknown、own.has_record保持false，不伪改SdkReturned/DefinitelyNotCalled/NotSent。原写worker一取得该确切结果，就先把Completion.audit设为role=UnadmittedTargetLookup、own=Unknown/has_record=false、apply=true（target_insert已在POST前保存），再尝试后继读取；任何后继catch不得清掉这组事实。owner在普通写错误/晚deadline/detach抑制之前先提交该角色，核原写ticket后再清inflight。role、target_insert和已保存ORDER在同一次owner提交中安装。若该轮后续lookup没有B，仍保A原槽，不能退成普通OriginalCall或清掉目标责任；任何后继404都不把A改回未知，也无新UUID/POST。

lookup_cancel只在合法完整200+cancel:null置NoCancel。404 unknown_order、409、失联、截断、过D都不是NoCancel，保持NotObserved并保原责任；identity/source/hard故障按原硬停止处理。得到B完整记录时安装Actual=B；B终态是B的真实调用阶段，A仍保持“精确未受理”。无B或B已终态时，A只有在order.state!=Started、无需移交的实际未决责任后才能退役；退役依据包含已证明A未登记，不以null/终态B冒充A的调用结果。

若发现A与实际观察同UUID，先核完整body/SHA/目标/B/profile/容量；异文硬错。OriginalCall相同UUID并为一次GET/一份观察；UnadmittedTargetLookup仍保精确未受理角色，目标记录独立说明此刻真实登记事实，同一UUID本轮只GET一次，不能追认A当时409成功。

实际B仍unknown时不拿最新C覆盖B；有独立B槽且身份完全一致时，A只续自己的Started read，B槽按原receipt GET。只有B.role为OriginalCall或TargetObservation、原receipt/target全部一致时，才算有效B槽。B自身仍为UnadmittedTargetLookup时不充当实际B的GET owner，也不作合并目的，保两槽等待合法观察。worker在锁内核B槽实际receipt/target一致后，只复制actual_in_other_slot布尔提示；锁外不借用B。owner提交时重新验证B是否存在且ticket空闲；B已被合法退役时仍有A.actual完整receipt，下一轮由A继续GET B。该提示不触发删除或放弃任何read。

多槽合并固定选择：有不同Started ORDER read时保原槽，延后合并。只在源A.role=UnadmittedTargetLookup、取得合法实际B、两者目标原insert全字节/SHA与B实际命令身份一致、目的B.role为OriginalCall或TargetObservation、B.inflight_task==0，且下表允许时合并。A自己的完成ticket必须匹配；B在途或identity未能完整核对时延后/硬错，禁止动B的receipt/charge。OriginalCall的unknown A不因同目标就合并到B。

“同read”要求request UUID相同，binding_json/request_body/read_profile_body/read_result_capacity也全部相同；同UUID异文硬错并保两个槽。Terminal必须源自本原read的完整已验终态：Common status.ok+terminal+remote_ok；或terminal+!remote_ok、明确远端error_code且精确qmt_host_native_operation_failed（原验证/末次来源核验已通过）。其他带terminal位的超时/identity/profile错误继续按Started保守持有。此定义沿BoundReadCore.cpp:691–725，不以运输失败或查空释放read。

| A.order / B.order | 固定合并结果 | 可释放的责任 |
|---|---|---|
| 任一NotStarted（receipt空） | 保另一方完整组；两边均空则NotStarted | 空值无read；保留非空的Started/Terminal，不复位已用额度 |
| 同read、同原bytes | 保已证Terminal组（若有），否则Started | 重复receipt只是同一通信操作，销毁重复副本；不增/重造read |
| 不同read、Terminal / Started | 保Started组 | 已完整确认终态的另一原read无后续GET责任，可安全退役 |
| 不同read、Started / Terminal | 保Started组 | 同上 |
| 不同read、Terminal / Terminal | 保目的B的Terminal组 | 两份read均已明确终态；保持已用额度，不再新建ORDER |
| 不同read、Started / Started | **延后合并，A/B均保原槽/原receipt/原charge** | 各自轮转resume原read ID；至少一份真实Terminal后再依上表收敛 |

若无现成B槽，可把A原node安全改key为B、role=TargetObservation、receipt/own由完整actual观察组接管；原A的order原封保留，不掉Started责任；target_insert保持。B已明确终态而A仍Started时，固定保A的UnadmittedTargetLookup槽直到原read安全后退役。已存在B槽且表允许时，向B合并完整B观察和保留read，原A只在无异常提交后退役。

合并提交使用C++17 map node handle及已准备≤36字节新key（或删除源node并原地swap目的字段），比较器为确定的noexcept字符串比较；key分配/所有复制/charge核对都在提取node和修改观察之前完成。进入最终提交后只允许extract、key.swap、无分配node insertion/erase、显式noexcept组swap与标量赋值。目的存在性和inflight在同锁下重核；identity冲突不移槽。任何准备分配失败保A/B/Summary/所有原charge；原read不得因merge失败丢失，仍可先独立提交A本轮新read观察、保持A槽后延期合并，不能回滚已POST的新read身份。

stop/detach不再新建审计，worker每阶段I/O前检查；registerSpi(nullptr)的audit_detached对events_enabled=false同样生效。已进入Common的一次调用保原D/control/drain；停止后不新ORDER/lookup/GET。wait沿event cadence加入审计ready/wake；容量不足不以过期时间忙等，由queue/charge变化notify后重算。stop不改变精确未受理、unknown、terminal或read责任。

## UC-CPP-R5 DTO 逻辑 payload 边界

定义均是 std::string::size() 有效字节，不含 NUL/capacity/allocator；沿 Standard.cpp:42–52。标量、容器节点、指针和 OS 内存不折算任意倍率，现 task 的 512 是原既有固定诊断预留，单列保留。所有新求和/base64 算术 checked。

| 符号 | 固定定义与依据 |
|---|---|
| B/P | 4096/4096；HostCodec.cpp:81–98；BoundReadCore.cpp:478–507、566–612 |
| K/Q | 交易 max_command_bytes / 账户 max_request_bytes，分别 1..65536；BoundReadCore.cpp:327–337、589–612。Q 未公开给 Standard 时用 65536 硬限，不用 K |
| N/J/S/M/C | 账户 max_result_bytes（8192..2097152）/max_data_bytes（1024..min(1048576,N-4096)）/交易 max_call_result_bytes（1024..2097152）/16384/实际 http.max_response_bytes |
| E | 38；当前 TradeClient 固定 qmt_* 原因最长38、BoundReadCore 35、HTTP 32；新增 Common 原因约束≤38，AuditSummary 不存原因串 |
| b64(n) | 4*ceil(n/3)，用除法和余数避免 n+2 溢出 |
| Ht/Hl/Ha | min(C,b64(K)+S+M) / min(C,b64(K)+S+2*M) / min(C,b64(N)+M)；HTTP 可收紧，不授较小 C 的成功能力 |
| Rt/Ra | B+P+K=8192+K / B+P+Q=8192+Q |
| U | Rt+Ht+min(S,M)+E：现 QmtTradeResult 全字段 |
| A | Ra+Ha+N+J+36+20+128+E：现 QmtAccountResult 全字段；20 是 account.trade_detail |
| O | Rt+2*B+781：私有 ORDER 引用（事件/query proof 可同时持有） |
| L | 2*Hl+O+E：现 ORDER lookup 的 response_body、reference_json、私有 O |
| Rc | Rt+Ht+36+64：新私有 cancel 引用全部字符串，不含共享 Core owner UUID 重复计费 |
| Lc | Rc+Hl+E：新 cancel lookup；明确包含 response_body/record_json 两份，无第三原文 |
| Prep | Ra+P+64：账户 prepared token 内 receipt/profile/request_sha；HistoryClient.h:43–59 |
| Apre | Ra+36+20+E：submit_prepared 在 token.reset 前已复制 output.receipt/request_id/operation_id/status（BoundReadCore.cpp:881–903） |
| G | B+128：一份全实例 audit_source；所有 pending 共用，另为每轮 event_source() 返回临时值计一次 G |

781 = account_id63 + account_type5 + binding_id128 + symbol9 + entrust_id63 + user_tag63 + sdk_user_order_id64 + event_sha64 + query_uuid36 + query_sha64 + broker63 + session128 + association_error31。O 的两个 B 是 source_.binding_json 与 query_binding_json_，insert receipt 内的 B 已在 Rt。原生字段检查和赋值见 TradeClient.cpp:733–794。

A、U、L、Lc 计入返回边界对象；Common 中的 HTTP reply/parser/DOM/codec/wire 临时值见UC-CPP-R7独立范围。额外把 Prep+Apre 的明确 token/输出复制窗口纳入新链保守预留，避免凭“token 已 move”漏掉实际复制。该项不表示其余 Common scratch 也已纳入。

## UC-CPP-R6 分阶段 live-set 与预留公式

所有旧Pending基础P0=36+bytes(receipt)继续计费；扩展ΔP=bytes(target_insert)+bytes(order.receipt)+bytes(actual.receipt)。新的role、TargetLookupState、TradeObservation.has_record及派生terminal()均为有限标量，不新增字符串/槽。取消写在POST前保存target_insert并取得该ΔP。

本轮输入T=36+bytes(receipt)+bytes(target_insert)+bytes(order.receipt)+bytes(actual.receipt)，36是Task.pending_key；worker独立Input不再复制key。Σ=Ra+Rt，对应Summary中order/actual两份receipt；Summary.own仅元数据，原immutable receipt由key/generation/ticket绑定，不加一份Rt。精确未受理角色/空B/NoCancel与多槽合并不同read保留均不增加单槽字符串字段；不同read保留两槽时，原A/B的P0/ΔP分别继续存在，单审计链只复制本次选中一槽的T。目的B仅锁内比较，不复制另一套B快照到worker。

| 阶段 | 已有全部P0/ΔP/G之外的新增live-set | 固定寿命/失败约束 |
|---|---|---|
| 调度/排队 | 512+36（暂持完整reserve） | 全链预留先于key分配/入队 |
| worker Input及Summary | 512+T+Σ | 完整旧组初始化；失败apply=false，Pending不改 |
| 来源核验 | 512+T+Σ+G+E | Core Host/Source版本分别冻结；source临时值随后析构 |
| 原A/原实际B GET | 512+T+Σ+U | 每UUID本轮最多一次；U析构后下一I/O |
| 新ORDER token / submit前复制 | 512+T+Σ+Prep+Apre | 新Summary read组在POST前完整安装；后继异常保Started |
| ORDER submit/resume返回 | 512+T+Σ+A | 完整A析构后才lookup；终态证据不因copy失败半更新 |
| ORDER lookup | 512+T+Σ+64+L | 64为唯一SDK token query；双原文/查询销毁后只留O |
| cancel lookup | 512+T+Σ+O+Lc | 仍含双原文与目标UUID/SHA100；actual更新用空槽事务 |
| 首次resume_cancel | 512+T+Σ+Rc+U | private Rc与U真实相加；后继public resume只用保存receipt |
| 初始化/替换组复制失败 | 不超过对应行 | Input保存完整旧组；Summary空槽内候选成功才swap，失败整组恢复并结束本轮 |
| 发布前/完成队列 | 512+36+Σ | Input先析构，key与空command_id swap；保持reserve直到移交 |
| owner比较/准备改key | 512+36+Σ+36 | 最后一项为准备的B新key；A/B旧keys/receipts仍由各P0/ΔP计费 |
| owner合并/延期 | 不超过上一行 | 无B快照副本；两份不同Started不丢、不并；目的inflight则延后 |

宿主审计预留按以下公式计算，owner key准备期独立计入：

~~~text
Peak = max(G+E, U, Prep+Apre, A, 64+L, O+Lc, Rc+U, 36)
AuditReserve(p) = 512 + T(p) + Σ + Peak
~~~

36是新key的有来源逻辑有效字节；原G+E已大于36，因此该项由G+E覆盖，同时必须核对map准备期的实际持有。Σ/T的收据数量无变化；组化标量不以“1024”等任意固定项代替。新read或actual候选复制采用空Summary槽，Input完整旧组充当回滚源；禁止再保整套旧Summary、第三份候选receipt或额外目的B副本。若实施改为这类复制，必须重算对应stage，当前公式不能继续引用。

G全实例只预留一次；AuditReserve动态预留。原写收到精确409后若要在原写D内立即lookup，必须先取得同一个唯一audit_inflight和本式额外预留；原写已有结果/ordinary charge继续保有，其存储不抵扣此链。取不到容量/唯一链或原D耗尽时，不新增HTTP，保Completion中的U角色和原Pending责任，按request_ms安排后继只读轮；不延长原写D。后继独立AuditOriginal按新只读D取本式预留。原event partition/context/chain/ordinary、其他任务和所有pending原额度保持；TaskCredit仍占原一个名额。不同Started读导致A/B槽延后合并时，既有charge全保、max_pending不增长，单audit链轮转。总余额不足只延期，不能丢A角色或read，也不能为新增B分配额外pending槽。

Summary到Pending用noexcept交换，先销毁旧组再回收差额；把新增ΔP从本轮reserve转作长期持有，A/B延期时分别保有。合并后只释放被明确定义为同read重复或真实Terminal的组；依旧Started的那份read连同charge移到存活槽。处理栈/完成值/旧node/newkey先析构，再退剩余chain额度和audit_inflight。release继续在worker_done/drained/join后清tasks/results，保留所有Pending完整charge；客户端/DLL晚回调物理drain保持原owner。

~~~cpp
bool checked_add(size_t a, size_t b, size_t& out) {
    if (b > SIZE_MAX - a) return false;
    out = a + b; return true;
}
bool checked_b64(size_t n, size_t& out) {
    size_t groups = n / 3, rem = n % 3;
    if (rem && !checked_add(groups, 1, groups)) return false;
    if (groups > SIZE_MAX / 4) return false;
    out = groups * 4; return true;
}
// sum逐项checked_add；max仅比较已成功计算值；uint64_t转size_t先核范围。
// charge先核payload_bytes<=max_queue_bytes，再核need<=max_queue_bytes-payload_bytes。
// 失败保Pending/role/read/charge，不做网络，不用删除原责任换容量。
~~~

## UC-CPP-R7 分层预算与真实回收

宿主预算包括具体 DTO、队列、快照、summary 及上述 token复制窗口。Common 内部继续受原 HTTP request/response cap、profile/command/account limits、parse bounded guard、HTTP pending session限额与 drain owner 约束：

- account follow 同存 response.body/envelope、decoded native/data、POST wire、末 verify metadata/profile（BoundReadCore.cpp:631–726、900–912）；这些内层临时文本没有被 A 一项全包。
- ORDER lookup 内有 raw K、restored receipt、record 内另一个 body K/source/metadata、DOM、encode StringBuffer（TradeClient.cpp:728–798；HostCodec.cpp:28–45）。L 仅返回边界。
- HTTP state.upload=body 真复制，ExchangeOwner 到 HANDLE_CLOSING 独立持有（HTTP.cpp:459–479）；worker 操作返回、audit chain payload退还与网络 callback物理回收是不同边界。client/DLL 继续由原 work():398–410 drain 后销毁。
- 原 account HTTP request 上限最高4194304，K/Q 只限定内部正文；wire/base64/header/request upload 按原 HTTP cap，不能拿 C 当请求上限。DOM节点、capacity、allocator与OS开销无统一倍率证据。

本文约束宿主逻辑 payload 新增预留。全临时 std::string、capacity、allocator 或 RSS 上界需要另有 scratch 并存与分配器证据，不能按通用倍数推断。

## UC-CPP-R8 验收要求与证据状态

| 必须验收 | 精确可观察断言 |
|---|---|
| 精确未受理精确409→lookup失败→下一轮B | role持久U；A原bytes/phaseUnknown/has_record=false，target/read/charge连续；下一轮GET A=0、cancel POST=0；成功后按B真实phase观察 |
| 精确未受理空/终态 | 合法200 null才NoCancel；404/超时/截断不置NoCancel；无Started责任时可退役未登记A；B terminal不改A phase、不增成功统计；仍Started则保原槽续原read |
| 多槽合并不同Started | A/B同目标、Ra/Rb UUID不同；各原body/profile/B/容量和charge连续；保两槽，不并、不重create；原ID GET；一份真实Terminal后按矩阵收敛 |
| 多槽合并同read/空/终态 | 同UUID同bytes才合并；同UUID异文硬错保槽；空+非空保后者；Terminal+Started保Started；两个Terminal保目的Terminal且不重建ORDER |
| 合并准备失败/目的inflight | B新key分配失败、任何copy失败、B写/审计ticket非0均不删槽/原read；A新POST过的read仍独立提交或保留Summary；无半node/半观察/提前退charge |
| 观察组故障注入 | actual旧B+phase/has_record→新C复制逐字段失败：完整旧B组或完整新C组；read copy失败不POST，POST后异常保完整receipt/Started；roleU从不因后继copy失败丢失 |
| resume_cancel预检 | 错owner、过D、moved-from/不完整句柄：有原receipt时完整保有，phaseUnknown/original_record=false，无POST；异常不返回半对象；跨轮public resume同样不回NotSent |
| 版本 | Host/Source两个版本分别漂移、降级；同B/session仍拒绝；Hostv2/Sourcev1普通能力保持、unknown cancel拒绝；profile冻结独立；不能用audit_source代替版本 |
| 原inflight/晚完成 | 原写POST前ticket已安装，所有写完成分支核ticket才清；晚Audit在通用deadline/fail前记账Started/U；stop/detach阶段间0新I/O，实际drain/join前不释放借用 |
| 预算边界 | K=1024/Q=65536，Rt=9216/Ra=73728；双proof O、lookup双原文、Prep+Apre、Rc+U；need恰好成功、need-1延期、checked溢出0网络；多槽合并两槽旧charge+单链均计费 |
| 业务边界 | 同UUID同body/目标本轮单GET、异文硬错；unknown B不被C覆盖；insert unknown保原receipt/fence；审计金融SPI/queries/inserts/cancels增量0 |

实施验证按[验证规范](../development/verification.md)，逐项证明产品源码、异常出口、对象销毁和真实调用链。当前契约动态未验；上述故障场景、预算实现、Common/Standard 组合与原 Adapter 隔离全链必须取得独立证据，设计审查不替代动态通过。

Standard缺少Q/N/J可信公开快照时，使用原硬限Q=65536/N=2097152/J=1048576，K/S从可信profile validator取得或使用各自硬限。真实SDK token/ORDER可用性、跨日broker定位、状态时延、一般insert解除与生产交接仍需相应契约和证据。
