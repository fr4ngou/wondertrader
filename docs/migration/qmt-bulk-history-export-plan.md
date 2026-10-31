# QMT 已下载分钟历史的批量导入方案

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

当前优先级：用户确认首次大量历史改用QMT外只读DAT直接转换，已验证两证券301946行，并接入原Importer/WT文件。共享内存bulk保留在线历史读取用途，实时链保持；整批导入优先沿[离线产品入口](../runbooks/qmt-local-dat.md)推进。下文保留在线bulk的设计与恢复职责。

状态：proposed。类型：实施方案；适用范围为2021-11-01起固定证券池的已下载1分钟历史，当前真实两分钟闭环见[实测证据](../evidence/2026-10-27-qmt-source-history-native.md)。本方案继续在自有适配层收敛，不申请新增WT核心改动。

当前执行顺序按[主路径优先](../development/workflow.md#主路径优先)：先接通Host、QMT、C++到WT的整体导入链并取得可用数据，再统一边界/bad case及代码评审。现有纯层证据保留，后续开发优先推进可运行功能。

总体方案继续分段实施；纯快照、SDK边界、Host分页文件及显式控制确认已按[BS/BA/BF/HP/BC/BW合同](../specs/qmt-bulk-history.md)冻结。BC1真实ACK收据与BW1 control3.0语法取得[限定内存验证](../evidence/2026-10-27-qmt-bulk-control-ack.md)；显式v5配置、源端服务及重连入口已实现，编码跨原截止和控制订阅退休的根因回归及独审已通过，见[源端限定证据](../evidence/2026-10-27-qmt-bulk-source-service.md)。实际Host域调度/最终Journal和C++仍待接线，普通接口尚未提供下述bulk运行状态。保留普通history_1m.v1/所有默认、真实SHM主路径、原WT/Helper/DSB/Reader。外部RPC目前empty，不作为替代入口或用户需补充的新来源。

## 目标范围与职责

固定显式证券池版本，20211101至一个固定上海已结束交易日前的日期边界，每证券一个长窗；不自动下载、不订阅、不修复缓存、不猜停牌/退市。SDK仍仅在原QMT主线程调用 ContextInfo.get_market_data_ex，none/fillfalse/subscribefalse；终端只内存，没有新增文件/网络读写。Host外部接收原源值页、持久写CSV与来源清单；原Importer一次每证券写验原生DSB；SourceReader按真实metadata和import receipt读取。

单位/分钟边界unknown保留；原值不乘factor。覆盖事实按证券与区间单独汇总：observed/empty/failed/unknown及实际首末标签/计数，不以无缺页推导全市场每个应有分钟齐备。

## 能力与容量先固定

新增独立显式能力market.history_1m.bulk，明确选择qmt.read-profile.v5/control3.0。新profile含max_calendar_days、max_rows、max_total_bytes、max_page_rows、max_page_bytes、max_pages、max_ranges及原queue/total预算；实际单未确认页。部署数值由有限真实长窗测量后冻结；纯测试示例不作为生产默认，也不扩大普通5日2000行。完整五年一般几十万行，应低于现Helper单文件1000000硬界，但真实行数与字节/时长仍须验。

SDK count 使用所选有限行cap加一的饱和哨兵；相等即报告窗口饱和而非截断成功。SDK仅一次，主线程owner在原D内完成Frame到独立内建tuple快照的脱离复制；I/O worker只接触纯值快照，后续页无需QMT tick。最多一个未ACK页；页内字节/行上限，整个快照累计字节/行上限。不得同时构造完整rows列表、完整JSON及其多份复制。capture期间SDK Frame与纯快照并存占长窗内存：请求cap限制输入、返回shape验证输出，无法静态保证供应商原生内部峰值；当前不可抢占调用也没有独立可杀子进程。必须先实测真实较长窗耗时/内存，过限只能以后续明确分窗规格处理，不能用根Job杀真实QMT或声称硬内存隔离成立。

## 单请求、分页、恢复

1. C++ bulk入口固定请求体/SourceSession/能力SHA与range_id，先持久receipt再POST一次。正文只有一证券、起止和有限cap；外部执行者持有原绝对D和原Job。未知提交后只GET原range_id。
2. Agent主线程经已绑定route接收一次开始消息，调用一次SDK；以预先固定snapshot_id将Frame脱离复制为独占快照后，绑定range_id、会话代际、原窗口、none/fillfalse/subscribefalse以及source语义。状态包含 sdk-running、page-ready、await-ack、completed、failed、expired。单活跃bulk快照，普通能力默认不受隐式升级。
3. 新bulk内部SHM页消息包含range/snapshot、连续页号、行数、首末时间、页字节SHA、终页标记；仍有限单slot传输。Host验证页身份、时间递增与累计预算，私有临时文件写入并持久确认后才ACK；ACK允许Agent释放该页bytes和已ACK的纯值行引用并推进快照游标。重复同号同SHA仅复用已持久页，异SHA固定失败。分页业务复用ControlPeer原CALL/REPLY/ACK和Host单域writer；slot运输ACK不代表持久确认，当前finish_bound整体终态接口不能直接承担分页。
4. 完成只有在最终页及总计数/摘要封口且Host全部持久后成立。Host外部生成QMIv2及成功页CSV清单；HTTP查询只暴露有限状态/外部artifact身份，不把整个长结果再次塞成HTTP大JSON。C++保存可移交Importer的目录与SHA，成功后无需对全结果重复resume。
5. 客户端断连、CLI超时：Host仍沿原range期限/预算责任，GET恢复原range，不重发SDK；已落页继续保留。Host/Agent同代存活且未过期，可重ACK原页推进。Host必须先证实已有页hash才ACK。原期限不因resume刷新。
6. Host重启/Agent重启/终端策略退出或snapshot过期：已落页可保留partial材料；原Frame可能消失，状态unknown/expired。不能凭已落页给丢失快照续编号或自动再调用原大窗SDK。根后续明确新任务只含已证明缺失的时间范围，绑定新session且分数据集，不冒充原请求恢复。未证missing的unknown页不自动补POST。
7. 关闭：Agent Frame释放只能在原主线程已返回SDK后；in-flight SDK责任unknown继续保留。正常结束须明确最终ACK/快照释放、Host持久完成、CLI callbacks排空、原App/Host/Native tree0/EOF/join/closed。异常沿原D与owner；不对QMT进程新增强制终止。

## 最少自有改动与复用

Agent：独立bulk adapter/state，复用原history数值/时间校验；read_capabilities新明确profile；restricted read dispatcher与control/SHM消息接入snapshot分页。Python3.6标准库保持，ContextInfo是唯一SDK owner。

Host：bulk页收集与有界ACK状态、外部私有CSV writer/成功封口、原Journal持久状态及绑定HTTP状态入口。复用现签名、认证、route/代际、Job与App生命周期。页值不会进入日志/stdout；无需另建数据库，原Journal保请求状态，实际历史仍CSV/QMI→DSB。

自有C++：新增bulk客户端/CLI子命令（或独立固定bulk入口），原一次receipt/submit与GET原ID语义；绑定新profile/分页状态和artifact manifest。普通fetch/resume默认与v1保持。原Importer/SourceReader/WT核心不改；直接复用Importer现成chunks[]及跨片严格排序/冲突拒绝，不新增分片拼接器；原CLI全vector/全CSV构造不用于bulk。

## 与扩大普通profile比较及验收

普通月窗方案只改自有上限/version与各验证层，研发量较小，SDK次数仍约证券数×月份数（5000×约60≈30万）。bulk方案约每证券一次SDK（约5000次），传输页数依然取决总字节，不宣称只有5000次运输；多页ACK降低主线程瞬时DTO/整包复制压力。实际节省比例要分别测SDK调用、主线程编码、SHM搬运、Host持久写、QMI/DSB写验；不拿含UI等待的小样本时长当吞吐。

先纯合成：长Frame分页等值、count饱和、字节/总量上限、重复ACK/页hash冲突/错session、任一点断线恢复、Host落盘失败不ACK、过期释放与SDK未回unknown、首因/资源。再同一真实000001.SZ小窗bulk与已验普通v1逐字段一致，之后一个显式月窗测量，达到冻结预算后才选单证券完整五年窗。最后在同一持续会话内按有限证券批次推进整个固定证券池；每批根原D，跨批仍不延长已在途range。测量阶段不不断把两分钟样本改名当全量交付；总计划一直保完整证券池和日期范围及未完成集合。

实施先核定bulk状态、profile和有界原型，再按下述步骤验证；当前没有需要用户处理的审批。纯plan/recovery分类可以独立实现，完整交付保留全证券池与日期范围。

## 实施前的关键核实与顺序

1. 先核逐页调度：SDK只能在QMT原Context线程执行；SDK返回后，后续页不得机械依赖每秒策略tick，否则少SDK调用仍可能有数日传输。若由独立I/O worker处理页，必须先将结果复制/转换为有明确所有权的只读快照，证明它不再借用QMT可变Frame或Context对象；普通线程不调用SDK。保留同代/原D/单未ACK页和有界释放。纯内存处理是否可转移、复制峰值和耗时以实际SDK对象与小窗原型证明。
2. 固定每证券的完整交付边界及多批目录组织。当前QMI v2一个profile绑定一个SourceSession，原Reader按成功导入收据核根；跨连接代次不能把不同身份塞进一个profile。方案必须明确每证券/批次数据根、恢复到新任务的身份和最终原生文件选择方式，复用DSB目录与现有读写，不新增数据库。
3. 分别定义原range GET恢复与已确认终止后的新读取任务。未知的原range不重发；快照已明确过期/释放后，如需重读，保留旧失败材料、使用新range及新数据版本，按完整证券数据集重建或已核定的可验证缺口合并规则处理。调度政策须能继续推进最终全量目标，避免把每次只读补齐变成人工操作；单活动SDK/快照责任仍须先确认。
4. 实现有界合成原型后，先与已验两分钟普通接口逐值对照，再测一证券月窗的SDK、纯转换、页传输、落盘、Helper写验及内存；据实确定长窗与分窗预算，不用含UI等待的总时长估吞吐。最后验证一证券全历史，再按证券库存扩大，输出明确的完成/空/失败/未知清单及ETF范围。

### Host持久接缝的实施选择

后继采用原read_operations通信表和原domain线程，不新增bulk_context列。新C++ bulk客户端在首次请求正文中一次生成snapshot_id、共享时钟域和原deadline_ms/queue_deadline_ms；用户无需输入这些内部字段。Host由原正文与已认证binding重建唯一identity/SourceSession，runtime持首次本地monoD并只收紧。请求正文及现有通信列保存幂等事实；同ID同字节先查原记录，再进行新请求的时效准入，查重与首次受理保持同一事务。

共享queueD独立验证，UTC队列投影不能授予新时限。Host现代Python的monotonic不能代替GetTickCount64，须显式Host端Windows时钟适配。输出根/源语义/文件额度在部署时冻结，任务目录由range/snapshot UUID派生；最终小回执须包含稳定产物根身份和原manifest摘要，旧结果不能按当前新root重新解释。精确新请求、终态和定位schema先写入唯一规格，再实现跨服务消费者。

重启后的queued按新binding拒绝，dispatch按原Journal中断；保持同ID读取旧终态，不恢复原range/snapshot或再次执行SDK。COMMIT返回超时可能已提交成功，后继读取须核原终态，不能以失败覆盖成功或补授过期ACK。collector构造、accept和资源收口都属于原domain线程；未确认资源保留原runtime，阻止新代替换。只读调查和替代比较见Host接缝（外部历史/待归仓路径：`../../build/qmt-bulk-host-seam-002/REPORT.md`）及无新增列选择（外部历史/待归仓路径：`../../build/qmt-bulk-host-seam-002/SEAM-ALTERNATIVE.md`），它们提供源码依据，实际链仍待实现。

源码依据：[Agent历史参数](../../connectors/qmt_shm/agent/guanheng_qmt_shm_agent/history_1m.py)、[能力校验](../../connectors/qmt_shm/agent/guanheng_qmt_shm_agent/read_capabilities.py)、[自有C++读取核心](../../src/GuanhengCommon/QmtBoundReadCore.cpp)、CLI参数与文件（外部历史/待归仓路径：`../../src/GuanhengHistory/QmtHistoryFiles.h`）、[源值历史合同](../specs/qmt-source-history.md)。各接缝按上文分别登记实现和验证；实际批量整链、吞吐及全量覆盖尚无通过结论。
