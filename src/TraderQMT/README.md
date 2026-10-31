# TraderQMT

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

标准交易适配器的目标是通过既有外部 Host / Windows 共享内存通道连接 QMT，复用 WonderTrader 的 ITraderApi、原 TraderAdapter 查询推进、WT 委托身份和金融归约。标准接口不引入逐单审批或额外资格模型。

当前提供自有候选实现 [StandardQmtTrader](StandardQmtTrader.h)，按[标准插件规格 STQ-P8/P9](../../docs/specs/native-qmt-standard-trader.md)实现连接、登录、独立四查询、限价现金委托、撤单入口和受控退出。[真实候选工厂](StandardFactory.cpp)已完成固定原版Adapter查询、直接标准SPI、正常关闭和实际共享内存正向写的[限定验证](../../docs/evidence/2026-10-24-qmt-standard-trader.md)。生产Factory.cpp仍为旧实现，标准层完整故障矩阵及正式切换继续验收。完整字段稳定流及真实共享内存SDK替身至原Adapter的回报消费已限定验收，生产查询/回报交接、缺字段补查与跨进程恢复仍待完成；候选诊断的 event_consumption_complete 固定为 0，不能据此候选宣告交易插件完整或直接用于生产交易。

后继[异常验证](../../docs/evidence/2026-10-24-qmt-standard-trader-faults.md)已完成丢回复、SDK进入后未知和原回归共13方法14场景：原UUID核查、不重发，未知后仍可查询账户；源交接未确认与资源关闭分别登记。完整关闭故障、实时回报和恢复继续验收。

最新[在途关闭验证](../../docs/evidence/2026-10-24-qmt-standard-close.md)扩展至15方法16场景：请求未完成时，关闭到期保留原API/worker/DLL，重复关闭沿同一次截止，工作实际排空后才回收。[事件页Common校验](../../docs/evidence/2026-10-24-qmt-event-codec.md)已有34个新增场景和六组原生回归通过；该切片提供真实页上下文与独立DOM，完整事件金融映射及P8由下述后继完成限定验收，SPI交付由后继完整消费者完成限定验收，生产查询交接仍在实施。上述结果使用固定原版WT与自有适配，真实券商下单/撤单调用为0。

[独立事件金融映射与P8关联](../../docs/evidence/2026-10-24-qmt-event-identity.md)已完成限定验证：事件保留独立原页/来源元数据，完整order/deal与查询复用唯一金融mapper，owner/worker三阶段处理，不填写查询专用身份或UTC。完整字段持续调度、有限交付索引及SPI已按[SEV-R4a/R11](../../docs/specs/native-qmt-standard-events.md)装配候选，并已取得[固定上游19事件模式限定通过](../../docs/evidence/2026-10-24-qmt-standard-events.md)及[真实共享内存三场景/一项清理回归通过](../../docs/evidence/2026-10-25-qmt-standard-shm-events.md)；首次/重连query/live交接、缺字段补查及生产验收仍待完成，event_consumption_complete保持0。

首次事件取页可使用Common的prepare_event_read_context(originalD,out)，沿同次真实准备返回原profile、来源、descriptor与实际Host页上限；新入口在原prepare前核线程/D，失败保留out，原prepare/events保持。[读取配置证据](../../docs/evidence/2026-10-24-qmt-event-read-context.md)分别记录限定开发、独立审查与既有候选复用范围；该接缝已用于上述完整字段Standard候选消费者，动态结果与独立full/delta审查见上述消费者及组合证据；可复验入口见测试模块说明（外部历史/待归仓路径：`../../tests/integration/qmt_standard_trader/README.md`）。

## 配置

原生 TraderAdapter 继续拥有 module、id、user、pass、savedata 和 riskmon。插件通过普通 WTSVariant 读取以下显式字段，不读取旧 QMT 工程，不调用终端旧 HTTP。

| 字段 | 含义与范围 |
|---|---|
| instance_id | 当前插件实例标识，1..48 个 ASCII 字母、数字、下划线或短横线 |
| expected_account / environment / currency / profile | 固定账户；当前 Trade 客户端仅支持 live、CNY、cny_cash_shsz_v1 |
| max_rows | 固定行数上限，1..4096，与实际可信 profile 上限共同约束 |
| trading_date | WT 运行上下文注入的有效交易日期 YYYYMMDD；不猜本机日期，不填 0 |
| base_url | 外部共享内存 Host 地址；沿原签名客户端校验，不是 QMT 终端 HTTP |
| key_id_env / hmac_secret_env | 凭证环境变量名称；值分别最多 128 / 4096 字节 |
| timeout_ms / max_response_bytes | 单跳网络配置上限；1..30000 毫秒 / 8192..16 MiB |
| binding_id / binding_sha256 / writes_enabled | 既有可信交易绑定及实际写开关；由原客户端核验 |
| request_ms / close_ms | 每任务原截止预算 1..300000 毫秒；首次关闭预算 1..120000 毫秒 |
| max_queue / max_queue_bytes | 所有未完成任务总数 1..1024；队列、候选与通信缓存有效载荷 1 KiB..512 MiB |
| max_pending_commands | 未决原指令收据数量上限，1..4096；结果未知时不逐出原收据 |
| max_lookup_bytes / max_identity_view_bytes / max_total_bytes | 沿账户身份模块的原预算，各为 1..64 MiB，子预算不超过 total |
| max_event_delivery_records / max_event_delivery_bytes | 测试事件消费者同时显式提供，条目1..1000000、字节1..max_queue_bytes；从原总字节额度划分，不另增总额；两者缺省时保持原查询路径 |
| event_poll_ms | 已启用候选消费者的整页完成后轮询间隔，1..60000毫秒，缺省1000；不表示查询与回报已同步 |

除表中明确可选的事件字段外，以上字段均显式提供。实际 v4/account2.0 能力从可信 Host profile 核实，不新增第二个账户版本开关。内存额度描述有效载荷；容器及分配器开销由任务数、行数、字符串和原协议上限共同限制。账户三阶段为候选及工作线程纯值各预留 max_total_bytes，并保留固定错误诊断空间；总额度不足时返回明确容量错误。

## 调用线程与生命周期

创建线程拥有 init、registerSpi、connect/login、pump/wait/stop/release、BaseDataMgr、全部 WT 对象及最终删除。orderInsert、orderAction、query* 和 makeEntrustID 支持有界并发入口，只复制调用期间有效的标量，不保留调用方 WTS 地址；宿主须在关闭后停止新调用并结束所有业务借用，才删除 API 或卸载 DLL。

工作线程独占 AccountV4、Trade 客户端及其真实 HTTP 回调排空。账户数据经 worker 取得 Core 结果，owner 准备唯一金融候选，worker 解析纯值关联计划，owner 完成并调用 SPI。首次 pump 由宿主在原 TraderAdapter.run() 返回后执行；connect/login/业务入口均不直接调用 SPI。SPI 在全部自有锁之外执行，可重入查询或请求 stop；重入 pump 拒绝，回调内 stop 不 join。

registerSpi(NULL) 即时阻止后继回调和事件调度。已成功返回的在途Query直接抑制，不访问已解绑SPI的BaseDataMgr；已进入Resolve的成功值由owner退役候选及其预算。完成值先析构再归还额度；真实运输失败、缺结果及原D错误继续保留，正常解绑自身不伪报I/O故障或触发故障关闭。首次 stop 冻结关闭截止时点并撤销实例 ID 查找；工作线程排空后 owner join。关闭超时保留真实线程、API 和 DLL，后续 release 只观察同一次关闭，不授新业务 TTL。deleteTrader 由工厂在 Closed、已 join、已 drain、无活动 SPI/业务借用时执行，失败保留原指针。

## 指令与错误

WT 生成的 EntrustID/UserTag 沿原样运输；插件只生成内部命令 UUID。原 receipt 和有界回复空间在唯一 POST 之前保存，未知结果最多沿同一截止时间查询原 UUID，不重发 POST。未决结果保留通信收据及指令 ID，不保存另一套持仓、资金或盈亏账本。

取消委托沿 WT 实际 EntrustID 和券商 OrderID，从有限身份索引恢复原 UserTag，再由原 lookup 及 create_cancel 核账户、证券、来源与 broker proof；不要求 WT 撤单对象另填标签。订单类型目前仅覆盖原共享内存协议支持的现金限价普通委托；价格使用原 double 的最短往返十进制，tick、数量格及账户写准入仍由既有源 owner 检查。

[查询恢复后继R21Q](../../docs/specs/qmt-shm-trading.md#qst-r21q-当前订单查询观察恢复)将当前真实ORDER查询作为另一类通信关联证明：保留原insert身份，区分查询原请求/结果/源行/B和历史事件session/sequence。P7按显式证明类型恢复身份，Common及Host在撤单时重核当前来源。该后继已通过[限定组合验收](../../docs/evidence/2026-10-24-qmt-query-recovery.md)，适用原insert已sdk_returned且正常写通道可用；结果未知状态下的受限撤单与完整重启恢复分别继续开发。

明确未派发或未调用的原委托由 owner 至多一次 onRspEntrust(error) 通知，包括原执行 D 之后的确定失败通知；该通知不延长 SDK 机会。超时、缺回复或派发不明不会伪造成拒单。源端明确业务拒绝保留原原因；未知、关联冲突、容量及同步负返回关闭受影响的新写准入并报告。同步队列拒绝无法保存时如实负返回，原 WT undone 行为的必要修正另行核实和批准。

完成任务在外部SPI前归还队列名额，结果有效载荷继续计费至回调结束；Query→Resolve沿同一名额。需要阻断的新写状态在通知SPI前生效，回调内新写同样遵守该状态。明确业务拒绝不额外锁死正常写入。


## 显式正式构建入口

[产品 CMake](../../cmake/native/qmt_standard_product/CMakeLists.txt)提供 `GuanhengStandardTrader`，输出 `TraderQMTStandard.dll`，复用正常Standard工厂与实现，不带测试注入宏；旧Factory保持。`GuanhengBrokerQueryContext`静态库提供[查询优先执行上下文](../GuanhengExecution/BrokerQueryContext.h)，原WT执行与金融职责保持。该入口已进入开发构建与正向整链验证，完整运行接线及生产资格仍按[STQ-P10](../../docs/specs/native-qmt-standard-trader.md)继续；实际证据从[当前状态](../../docs/roadmap/CURRENT.md)读取。
