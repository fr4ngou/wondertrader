# SRI006首次执行退出的冷核边界

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B统一候选失败接收与隔离诊断。状态：root-cause-pending-verification。范围：根已终态的SRI006 SDK替身主链，原件根`build/root-continuous-system-006/qa-main-001/main002`。首节为原件冷核，后继各节分别登记新独占根的动态SDK替身验证；原根保持。主模块仍为[模块B](../migration/module-b-delivery.md)。

## 原现场与精确身份

该统一候选使用inventorysession.2、c050 Host/Runtime和P27 Standard：实际Host SHA `41e0ec1d09358848a52c1da49a4742df9650bcd540f368fa3e1633296a78efe8`，Runtime SHA `0f394940a9f34b25e76cde0bda1d6bd54e6bd80fcca0ef96ae3d4573d8e3f829`，Standard SHA `ef04dae9d60727cc97a82372488ceecadf55e8d33e4adc5679f00ed13e2a050f`。当前[P28后继](2026-10-31-unknown-write-stop.md)的Standard为ea40ee…，两者按实际身份分别记录。P28已验未知提交的恢复停止，不据此认定本次正常业务失败已经修复。

首轮70秒业务断言时尚未达目标：决策序号8、buying/frozen_buy_ready；SDK实际四证券合计10000，目标合计50400，11次SDK调用，Native submission_revision=12、成交映射7，execution_position_qualified=true。该数量比较表示业务尚未完成。具体首次Native失败另沿以下直接原件定位。

原Native failure.v1记录stage=runtime、plugin_error=0、host_fault=3（Plugin）、session_fault=4（Execution）、native_error=0，reason摘要为空字串。close-prepared为closed=true、ok=false、recovery_ready=false、error_code=runtime。WT外层exit2、forced=false，原进程树、EOF、读线程及资源关闭；物理回收与业务失败分别登记。

## 冷核改变的判断

只读打开同一trade-communication.sqlite，11条原trade_commands全部为sdk_returned、sdk_entered=true，source error_code均空。原trade_events有22条，最终durable/ack_intended/source_ack/observed水位均22。后继已更正采证脚本：gap列是规范JSON字节，原bytes `null`解码为None；早期脚本直接对非空bytes取bool所得true属于采证错误。原JSON保持，后继更正见下文。Native当时映射7条成交与Host最终11条命令结果按各自阶段记录。

原运行预算run_ms=300000、start_ms=25000、stop_ms=10000；Standard request_ms=30000、close_ms=4000、max_queue=16、max_pending_commands=16、max_queue_bytes=536870912。当前证据没有支持“30秒总运行耗尽”或“请求预算为5秒”的判断。插件错误码0和空reason尚不能区分首次写unknown fence、事件任务失败或其它先关闭写入口的分支；具体触发任务仍待同次原生见证。

冷反馈命令为`python -I -B .tmp/ms-sri006-failure-feedback-001.py`，已运行并确认固定原失败组合。它只读断言现场，尚未代替能驱动实际失败的动态回归。输出RED-FEEDBACK-001（外部历史/待归仓路径：`../../build/ms-sri006-firstfailure-cold-001/RED-FEEDBACK-001.json`）绑定原failure/close-prepared、配置、业务失败、原SQLite及三实际Native的完整SHA；不输出私有命令、SDK实参或金融正文。辅助JOURNAL-FACTS与SHAPE保留只读核证。

## 下一动作和边界

优先复现本次完整主链的首次关闭写入口，有限诊断限自有Standard/执行宿主，记录首任务类别、返回码、原截止关系及队列/资源状态。先捕获具体首因，再在责任层修改并按相同SDK/回报链验证，保持原命令身份、预算和金融根。根整包owner继续核同次调用链，B维护本模块生产差异和实际回归，不重跑已核原价400期及历史11命令审计。

完整B、统一候选和该故障的修复资格继续pending-verification。WT框架线程调查保持结束，新增WT行为及真实金融操作均0，新增输出全部位于E盘。

## 同包实际复现与首次写保护

`build/ms-sri006-reproduce-001`在独占新根复制原source002的28份QA材料，仅在本次执行组件副本装入自有Standard诊断DLL。运行侧、Host、App、SDK/行情夹具、65秒晚到连接、原600秒总界和各业务截止均保持。诊断源基于同一P27 cdc500…，在21个关闭写入口位置记录首处原行号、任务类别和固定错误/时钟数值；原WT文件及正式产品DLL保持。诊断记录只在首个写保护触发时写一次，退出发行候选。

该次实际重现SDK11/持仓合计10000、决策seq8 buying/frozen_buy_ready、Native成交映射7。首次写保护位于原Standard第361行fence_unknown，任务类别Insert、operation_code=9（SubmissionUnknown），发生在该任务原30秒D之后11毫秒。此后Native host_fault3/session_fault4，插件错误码9；原根现场的插件错误码0及空原因保持原范围，原根首次生产者分支尚无同次直接记录，不能用新9码覆写原0码。

新源Journal的11个不同命令最终均为sdk_returned、SDK已进入且source error_code空。该直接证据证明同症状复现中，本地写结果确认超期触发保护；耗时位于入队、提交准备或原ID结果核查的哪一段仍待分段计时。最终事件gap与关闭阶段继续分别核对。

调用入口为`.tmp/ms-sri006-reproduce-001.py`，由原有限Job包装执行，外Job52356 exit0/279.891秒；控制器成功封存预期业务失败，业务run_control实际exit2、257.878秒。全部12个准备/检查/业务子进程树零、EOF、读线程join和资源关闭，原QA及原Journal冷读前后保持。新冷证明（外部历史/待归仓路径：`../../build/ms-sri006-firstfault-proof-001/PROOF-001.json`） SHA `0f2276fe0a09c8fa60141f5a3837a6324ab0ead910b805c21677abc072910c7c`绑定18份原件，明确业务红例与工具正常回收的区别。

下一分段计时仅在自有第二份诊断副本为最多64笔写任务记录24个固定数值；记录worker开始、准备/提交/同ID查询时间及返回码，查询身份及deadline保持。该同包第二轮正在执行，结果单列后继，不因原源端SDK已返回而提前解除本地未知责任。

## 分段实证：第12次提交未受理与短样例容量

第二轮`build/ms-sri006-reproduce-002`已终态，外Job74632 exit0/277.040秒，业务仍为预期失败。固定分段数值证明：前11笔写任务均在原D内查询到SdkReturned/HTTP200；第12次写任务入队等待12646毫秒、prepare7毫秒、create6毫秒，POST前还剩17341毫秒。POST耗时8毫秒，返回HTTP503、原Status.code=10（IoError）且没有原记录；后继按同一原身份1053次GET，最终HTTP404、Status.code=3（NotSupported），在剩余原D耗尽后触发unknown保护。HTTP状态与本地Status枚举分别保存，早期将10/3口述为Unavailable/NotFound的解释已沿原ProviderTypes.h纠正。此处的第12次是本地提交尝试，源端命令及SDK调用仍为11，原submission_revision12与源端11笔分别保留。该定位直接排除了本次最后一笔“SDK已完成却未收到终态”的解释：最后一笔尝试尚未进入Host命令表，前11笔已验证返回。

根SRI006配置从短SDK样例继承`max_trade_bytes=200000`与命令上限16。原Journal身份1104字节、11条命令预留196628字节，实际已用197732、仅剩2268；每条新命令至少预留17409字节，数量上限尚未达到时字节额度已经不足。真实`HostTradingJournal.submit_trade`在登记前核该额度，容量不足抛JournalFull，原HTTP层映射为503 queue_full；客户端对不含原持久受理记录的HTTP失败仍保持原身份核查，不推定未调用或重发。上述原冷事实与新分段事实分别绑定，不覆写原根未记录首次生产者错误的边界。

最小命令`.tmp/ms-sri006-capacity-001.py`调用原安装的真实Journal受理路径，零运输、零SDK：200000字节在第12次拒绝，11次受理；只将有限字节额度调整为400000后，原16条命令全部受理，原16条数上限保持。外Job58216 exit0/3.550秒、Journal均关闭，源Journal冷读前后无变化；原件`build/ms-sri006-capacity-001/RESULT.json`绑定源码及配置身份。本轮根因为完整三轮QA选择了不足的通信资源配置；当前证据支持修正该配置，不需要为容量问题修改Native或WT。

`build/ms-sri006-capacity-main-001`已经用同包原版Native重验，越过原11笔限制，实际SDK13/持仓合计12000，但首轮仍在原70秒未达目标，完整三轮、同根恢复及正常关闭未通过。最终原发布seq8/buying，Native已映射10成交、submission_revision15。全部13个Host命令均SDK返回、源端passed/清理通过；正常运行期间没有Native先退出的直接原件。停止阶段failure为recovery_drain/plugin1，对应原固定原因qmt_standard_write_admission_closed；当前分段定位继续核实际停滞及吞吐，不把停止阶段错误当作先行根因。外Job13420 exit0/315.454秒，业务run_control失败、所有子进程完整物理回收分别登记。

候选SDK容量按公开原接口一次配齐：有限256条命令、512事件、每页4096字节；Host max_records=64、max_journal_bytes=13975552、max_result_bytes=196608、max_trade_bytes=5506131。每笔最大命令4096、结果预留1024和metadata16384由原协议取得，交易预算按原规范identity加256份最大记录预留求精确字节固定点；读预算和Control bank沿原validator同步计算。原待执行并发16和各业务截止保持。这是声明三轮负载的有限配置，长期容量、真实交易配置及生产资格分别验收；当前只授容量层已验范围。

汇总容量证明（外部历史/待归仓路径：`../../build/ms-sri006-capacity-delivery-001/PROOF-001.json`） SHA `bc7b5a4e3003d03aa03890cc0eabbabb73dd8ba164b8f82c71d4dff8fde6673b`绑定38原件，明确完整主链仍失败。`CAPACITY-001.json`保存上述完整额度及预留公式；`GAP-CORRECTION-001.json`直接解码原根/两诊断/容量主链四案的原SQLite，gap均为空，旧错误JSON保留并退出结论来源。`SOURCE-TIMING-001.json`核108次SDK读取，3.6计时粒度内执行耗时均0毫秒，相邻读取中位1091毫秒；混合来源跨度195秒包含独立账户及分析，不能仅由该聚合量指认Native/HTTP/SHM的具体耗时层。

第三份诊断`build/ms-sri006-task-profile-main-003`已终态，实际安装Standard SHA `44899599bd3647e903147824ab4eeef33ff521b2700da4ff699e99c959843552`与构建一致。该次SDK16、Native映射10、submission_revision16，仍在首轮原70秒断言失败；没有Native failure.json。工具设计为实例销毁时才保存轨迹，最终未生成任务文件，因此本次不提供任务耗时结论。外Job64516 exit0/320.872秒表示控制器封存成功；业务失败及完整物理回收分别记录在原RESULT及RUN。

第四份诊断只修正QA采证：最多2048个任务的开始、完成和owner取出分别即时追加固定数值，写入E盘三个专用文件；原析构汇总保留。该副本基于同一P27，不改对象布局、公开接口、金融内容、原70/600等截止或其它产品Native。构建外Job17572 exit0/10.243秒并完整回收，源码SHA `d22a3494204f49355d7704e5ee3adf4fade7eb6b27e1a32178a4149e029758bf`。诊断副本不进入发行，当前没有新的产品或WT修改。

## 有效任务测量与下一层范围

`build/ms-sri006-task-profile-main-004`已终态，外Job60232 exit0/332.557秒；控制器与所有准备/业务子进程树零、EOF、reader join及资源关闭。完整三轮业务继续失败，当前12笔SDK、实际数量合计11000。源端12条命令均sdk_returned且sdk_entered=true、error_code为空，gap解码为空。外层控制器封存成功不授业务成功。

三份即时轨迹记录460次阶段开始、460次完成及459次普通owner取出，逐项身份一致、worker顺序无重叠、解析错误0；最终析构汇总total_tasks460/overflow0。它们对应412个逻辑task ID，其中48个ID有Query/Resolve两个阶段。原Query阶段49次，其中48次成功、1次停止后的Pending；Insert13次，其中12次成功、1次停止后的Unavailable。成功查询及队列的具体阶段保留在测量收据（外部历史/待归仓路径：`../../build/ms-sri006-task-proof-004/MEASUREMENT-001.json`），SHA `059327413921b075abf59f2a0dcb72accbe6384f549704d8ef3d62158e17f020`，21份固定绑定。

Query完整worker区间中位1342毫秒，queue中位7315/最大17919毫秒；已普通交付的Query从worker完成到owner取出中位9毫秒。Insert worker区间中位1115毫秒，queue中位3979/最大8810毫秒。首Insert开始到首个非Ok任务开始的80.084秒样本中，已完成Query占61.607秒、Insert占13.961秒；该样本沿原worker时钟定义，分别记录范围，不能冒称精确外部70秒区间。queue的各任务等待彼此重叠，不把其总和当墙钟时间。

首次写保护记录在原第360行owner `block()`。其中kind/code为0、deadline=0来自owner线程没有当前worker任务的TLS默认值，不能据此解释为Prepare/Ok或某任务截止。Native停止原件与实际完成中的Unavailable/Pending分别核对；当前未发现更早的已完成任务错误。原根无首次分支直接见证的边界保持。

当前证据把主要占用收敛到Query的完整I/O和其引起的排队，具体是create_request、submit_once内的HTTP/Source往返还是其它验证仍待拆分；本记录没有据此修改查询、认证或事件正确性规则。下一有限测量保留原安装、真实3.6 SDK替身Source、四个启动查询及65秒晚到连接，在原账户启动完成后停止；仅为诊断裁去后续三轮调仓，明确不给完整业务资格，避免重复运行尚未改变的完整失败链。

独立测量复核（外部历史/待归仓路径：`../../build/ms-sri006-task-proof-004/REVIEW-MEASUREMENT-001.json`） SHA `a1dfc8f7e1efca30027a350bd5c20bd3e935cf07813d7882fdff826badffc8cb`已核26绑定、三点/析构及原关闭原件。Query的9毫秒间隔从finish采证点到pop采证点，包含诊断写入和完成发布，按该区间解释；它不单独测纯owner调度。此前容量只读审查（外部历史/待归仓路径：`../../build/ms-sri006-capacity-delivery-001/REVIEW-EXECUTION-READONLY-001.json`） SHA `816630fe05ed3a280947e575913f0a289450bafc2a37913219f50fee21350466`核225绑定，容量根因与剩余完整主链缺口分别登记。

## 启动查询的两阶段与回调节奏对照

005沿原安装、原3.6 SDK替身Source、65秒晚到及所有原截止执行，在账户ready和原绑定检查完成后以明确QA测量标记结束。四个启动Query的create_request为5..315毫秒、中位16毫秒；submit_once为1121..1913毫秒、中位1547毫秒。后续两次刷新单列，不混入这四个初始阶段。外Job70204 exit0/171.510秒及全部子进程完整回收，SDK下撤单0；运行总结果因QA主动结束保持false，不授完整三轮业务资格。005收据（外部历史/待归仓路径：`../../build/ms-sri006-query-proof-005/MEASUREMENT-001.json`） SHA `dd28cef8c202927141b967fbbe4c97280382a928a652a1bbeffebbed5db4ab64`固定28绑定。

006使用完全相同的诊断DLL和main，仅把QA SourcePeer循环sleep从0.1改为0.01秒。四个初始Query的submit_once仍为754..1401毫秒、中位889.5毫秒；外Job62112 exit0/162.042秒、Source passed且全部物理回收。此对照说明该样本对回调等待有响应，同时仍存在其它显著成本；没有更改真实QMT timer，也不给真实QMT更快频率资格。两案原Native均closed.v2 ok/recovery_ready/exit0；对照收据（外部历史/待归仓路径：`../../build/ms-sri006-cadence-proof-006/COMPARISON-001.json`） SHA `3f49382c2948cefc2e77969da6ef594f3614995193ebeee074fc56bd91a3f840`固定49绑定并更正005原关闭schema过滤，旧计时结论保持。

当前008继续使用同一有限启动链及原0.1秒Source，只在QA冻结副本的原BoundedSignedHttp交换前后记录数字化路由类别、起止时钟、HTTP/Status及响应字节数；最多2048条，不采集正文、头或身份。基于原Native006的Standard和HTTP两个翻译单元重编，其它13原对象及库保持。007构建缺冻结Common头目录而在编译前失败，原件及完整回收保留；008只补该include路径，外Job64108 exit0/9.726秒并完整回收。该诊断不进入发行，不改变产品HTTP行为、原验证或持久化语义。

## HTTP与原SQLite提交的同次区间

008有限启动链已终态，外Job58096 exit0/166.619秒，148条HTTP数值记录未达到2048上限；SDK下撤单0、Source passed、Native正常closed.v2以及全部物理回收。绑定GET中位3毫秒；六次原请求受理POST中位259毫秒、终态结果GET中位281.5毫秒、消费确认POST中位246毫秒。四个初始Query分别按同一C++steady时钟选择其HTTP区间，后续两次刷新及启动/停止请求保留各自范围。HTTP测量（外部历史/待归仓路径：`../../build/ms-sri006-http-proof-008/MEASUREMENT-001.json`） SHA `5338d15aa6c39133d86973e725718e216b7403d65efb6154b6eea6d79d6c6362`绑定30项。

009沿相同008 Native及原0.1秒Source，仅由QA入口包装原trade_cli，在原SQLite Connection的connect/execute/commit/close前后记录固定数值。SQL、参数、同步设置、事务顺序和文件目录保持；记录留内存，原Host结束后一次写出，不在被测事务间逐条写文件。外Job26072 exit0/165.593秒，SDK下撤单0、Source passed、原Native closed.v2 ok/recovery_ready/exit0、全部子进程完整回收。

该次7482记录、913连接、overflow0且操作无失败。913个commit中位0.008毫秒；32个超过1毫秒的commit实际为57.257..327.388毫秒、中位108.904毫秒、累计4376.729毫秒。提交耗时与相关HTTP请求按实际重叠区间核对：初始deal查询的受理POST221毫秒中含commit203.443毫秒，终态GET245毫秒与commit237.155毫秒重叠，消费确认POST167毫秒中含commit142.326毫秒。这里的重叠时间已经包含在HTTP墙钟内，分别列出后不再相加。

原`BoundJournal._transaction`在持有原锁时执行COMMIT并关闭连接；`submit_bound`在派发前持久受理，`finish_bound`在源ACK前持久保存结果，`consumed`保存责任消费确认。终态GET沿同一锁取得已落盘结果，提交期间的等待会进入GET耗时。直接采证定位了这段持久提交成本；当前记录没有逐次跟踪disk flush，也没有以SQL正文或调用栈把每次提交归到具体业务表，因此完整性能根因和正确修复仍待该owner实施及全链验证。SQL同次测量（外部历史/待归仓路径：`../../build/ms-sri006-sql-proof-009/MEASUREMENT-001.json`） SHA `4e743e569e736012ec0215755ccc8b05d3d91494a2baaa4a691fb380b31bbc36`绑定31项。

共享读通信与持久化由A拥有，B已将精确消费者、原持久边界、身份/截止/容量/恢复要求及后继验收写入owner接口（外部历史/待归仓路径：`../../build/ms-sri006-io-owner-interface-001/INTERFACE-001.json`），SHA `58a25794e79a1190d8cd3431bf78cb50d88425fd67737853b2b117f2ec7230e1`。请求owner在原层修正并交配套身份；B继续消费后继，沿原65/120/70/600边界完成三轮目标/现金、同根恢复及正常关闭。当前产品变化0、WT变化0，完整B及根候选资格保持待验。

## 最终测量审查与版本边界

独立I/O审查（外部历史/待归仓路径：`../../build/ms-sri006-sql-proof-009/REVIEW-IO-001.json`） SHA `78b62ed7b31c1ce2d96b6210131d35f53c6dab10fc041b7d272ecbea58c13304`完成114项绑定复核，重新计算7482条SQL、913连接及12个原HTTP窗口；新增P1/P2为0。审查确认计时转发及原持久规则保持，同时明确观察成本、区间重叠、时钟及四查询样本的限制，完整三轮性能资格保持false。

验证交接（外部历史/待归仓路径：`../../build/ms-b-io-net-fee-delivery-001/HANDOFF-001.json`） SHA `88ae353be2ff8c48e66d221efec0306897a17a0955a0f59de82e3102e97b2d5c`保留所有原审查与原失败。历史容量225项绑定中的当前223项匹配；本文随后追加测量，A的公共restricted.py随后增加三行显式批量日线注册，二者按后继版本登记。原SRI006安装内restricted.py仍与历史审查SHA `8e208853394c01baff165a7d6db055cf65c1dda1a85e78fe88437982115de675`精确相同。固定候选的历史结论继续沿其实际输入使用，新增公共Source入口资格归A另验。

## Host持久I/O后继full003的B执行冷核

A交付`build/root-host-durable-io-001/COLD-HANDOFF-001.json` SHA `30f7230f65e63d3093b98e3ec052f032f2edfefaee2de1a9801694644e37870a`。B重新读取同次终态原件，核原70秒目标失败：20笔SDK替身委托均成交1000份、剩余0；目标50400份、实际19000份，512100/515080/589000分别还差4100/11400/15900。最后策略sequence8为buying，submission_revision20、映射15，券商持仓观察已与实际19000一致。该策略发布属于回调采样，映射15不证明停止后的Adapter永久丢失了5笔。外层exit1，整树、管道、读取线程及句柄全部回收。

B独立冷核（外部历史/待归仓路径：`../../build/ms-full003-execution-cold-001/PROOF-001.json`） SHA `f5fef1cf8afa155cd524a771ec0591bd844b72691a43b97bf707b3663895c61c`绑定19输入；读取未增加Source请求、委托或原件写入。Source订单查询首次可见与下一笔入队之间仍有间隔；原件缺完整Native应用/组退休时钟，冷核将这段保留unknown。

## 自有待执行查询积压与P29有限观察

隔离P28诊断仅在内存记录最多65536个数值时序，worker join后写文件；普通产品包及WT源码保持。实际执行切片保留50400份目标、1000份分单，独立来源Agent以100ms门控推进，省去App/历史/65秒等待。`ms-full003-execution-minimal-003`在35秒观察中执行16笔，源查询87；完整记录3402条，普通Query worker88项/30.845秒、排队中位2404.868ms。16组最终全部退休；4组在完整O后又收到迟到终态事件，原barrier清零并重新补查。停止沿原关闭，Native exit0、Host/Source及全部物理资源关闭。该独立门控的数值频率与完整Source相同，调度组成各自不同，范围单列。

[STQ-P29](../specs/native-qmt-standard-trader.md#stq-p29-查询优先回报的待执行查询合并accepted实施范围隔离开发中)候选仅改自有冻结Standard：owner SPI回调的同datatype查询共享仍在队列内且截止更早的原任务；已取出查询、普通外部调用和写保持，终态P要求原ID严格越过全部barrier。原终态迟到事件处理保持。本候选源SHA `6e035f40c6318b7c3a4a9023902d1658bea592fde0e5616689f96c35bcd6fd92`，无诊断DLL SHA `9b43b80c89db9449ce311cd84cd399c79bb54f97e708988686dc66bc14c3ef42`；live Standard及原P28包未替换。

P29带相同被动计时的独立切片在原70秒观察中执行39笔，实际已到38100份，515080/589000仍差4400/7900，完整目标门槛失败。源查询130，记录5637条；共享118次，其中112次来自回调、6次为越过barrier的终态P。逐项核共享时原任务尚未被worker取出，39组最终均退休、Native exit0及完整物理回收。基线观察35秒、候选观察70秒，输入时钟/独立来源与完整Source的区别保持；本证据不声称因果性能提升或完整目标通过。

有限证据（外部历史/待归仓路径：`../../build/ms-query-coalescing-evidence-001/EVIDENCE-001.json`） SHA `57e12bb0cacc8cb414299dbddb83c1e47e9d78c273dfece2ba4b737a6af57e50`绑定520输入，完整70秒门槛及C1银行/并发矩阵、C3恢复/发行仍false。两位既有审查者静态delta未发现确定P1/P2，运行及安装资格继续待验。此前两个最小驱动失败均在SDK前，001为生成器锚点、002为未选实际QA副本；原件和回收收据保留。

无诊断候选正在回到原完整Source、原工作量与截止验证。`ms-query-coalescing-full-001/full001/full002`两次均在Host配置阶段退出，Source未启动、SDK0、全部子进程回收；原复用控制器未包含full003实际prepare角色覆盖的问题在full002补齐，组合故障仍保留。单独配置与HPR Host实际启停已通过（2.515秒、SDK0），下一次只在原失败点增加固定类型/帧采证，完整交易资格保持false。此处记录整套启动组合缺口，不据此归因WT或放宽业务验收。

### 完整链验证装配的角色身份更正

后继full003实际首故障为TradeHostProcess配置验证，尚未创建Source。只读调用同一已安装父端验证器：原A full003材料通过，新材料拒绝；唯一身份条件差别是manifest与descriptor的Host解释器路径不同，launcher SHA相同。原复用控制器按system_paths推断旧Host路径，原受控命令实际使用另一Host角色；实际full003的prepare/finalize另有selected-role覆盖。更正QA材料生成与命令角色路由后，full004的只读预检准确拦住尚缺的finalize覆盖；原父端校验保持。

角色冷核（外部历史/待归仓路径：`../../build/ms-query-coalescing-role-proof-001/PROOF-001.json`） SHA `a9244e5059931c4ea09f7ded74309dbc69ff9d175a3e5f990f7e4aad83d85931`核19输入，full001–004均Source0/SDK0及全部物理回收。full005四个通信角色预检通过，随后SourceMarketProcess提前退出；该服务误用了精简通信Host环境。full006保持历史/采集服务原完整worker角色，只选择四通信Host的新环境，原四父端预检通过，完整九组件ready已观察，尚待原65秒后Source及真实业务目标。以上角色更正均为QA装配，原产品及身份验证逻辑未改。

### P29无诊断完整来源链full006结果

full006沿原65秒等待、同次Source/分析/CTA/原分单继续到原70秒目标断言，最终`continuous_rounds.py:66`失败。SDK37、37笔原订单全部全成、目标50400份/实际35100份/仍差15300份，最后策略sequence8为buying、发布映射29/37。Native正常`closed.v2` exit0、Source通过、输入before/after精确一致，全部树/EOF/join/资源回收。最后发布的映射数量与关闭后的最终内部状态分别表达；未记录的关闭后映射保持unknown。

完整失败冷核（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/FULL006-COLD-001.json`） SHA `51700d2520e0f1edb5b992c41e42b02e03e85f034d1b4220b23e7c18a57eebe8`核21输入。该次使用P29无诊断DLL，三轮及整个模块保持false；full007仅换同源有界内存trace，继续原目标、分单和截止，定位查询等待、订单解析与组退休后推进的具体间隔。

P29有限证据的执行独审（外部历史/待归仓路径：`../../build/ms-query-coalescing-evidence-001/REVIEW-EXECUTION-001.json`） SHA `1104d88f933e8f0f1bf94d1508b113b75e99af20619095fb85690951f8d303fd`核538绑定，协议独审（外部历史/待归仓路径：`../../build/ms-query-coalescing-evidence-001/REVIEW-PROTOCOL-001.json`） SHA `603bd6cc22cafa1748ce81908076bca9c7badf6d0b36692d5bb33bb6fad6a6b9`核547绑定；新增开放P1/P2为0。两报告限定既有静态与39单部分观察，完整C1/C2/C3均保留gap，未纳full006/007。

### full007同次原生计时与时间包含核对

完整来源full007已终态：35笔SDK替身委托全部全成，目标50400份、实际33100份、差17300份。原70秒目标失败；Native正常closed.v2、Source通过、输入before/after一致及全部物理回收。原生内存轨迹4260行、未溢出，包含初始化、业务和关闭；其总和不作为精确外部70秒区间。

普通Query的78段worker合计53.911秒、中位663.375毫秒，排队中位1561.312毫秒，完成到owner取出中位7.398毫秒。35组最终退休，退休后到同标的下一次准入的30段间隔中位91.317毫秒、最大289.552毫秒。订单身份解析26段合计3.097秒，中位110.487毫秒。各任务的排队、worker及组区间可能重叠，各项分别表达。

Source保留122次SDK查询的进入与正文结束时钟。按相同datatype及完整落在Native提交/返回区间内核对，74段唯一相容、3段多义、1段缺失；74段中提交到SDK进入中位357.106毫秒、SDK正文结束到Native返回中位267.976毫秒，SDK正文累计约1毫秒。此为时间包含匹配，没有UUID直接身份链；SDK正文结束时钟早于QA证据文件写入及返回对象构造。尾部、通信、持久化与客户端等待仍需同次拆分。最终尚留存的一项read记录execution_ms=109，其余已消费记录的完整阶段指标已回收，单项不代替全部查询。

full007冷核（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/FULL007-LATENCY-001.json`） SHA `fec57bbb20be50148e7064404f99b3994e76031d78b34bd91ac44a0445221517`绑定142输入，明确业务失败、时钟限制和当前归因缺口。full008的QA方法计时设置在业务前失败，原Source终态摘要又在空owner上失败，首设置异常类别未留存；该案保留SDK0及完整物理回收。full009改从正式正文已创建对象取得同批类，保留来源/工作量/截止，继续有限内存分段采证。无新增WT行为。

### P29真实准入函数的状态回归

同TU探针（外部历史/待归仓路径：`../../tests/integration/qmt_standard_trader/queued_query_probe.cpp`）直接包含受验Standard，调用实际enqueue和预留/归还函数，使用真实普通查询银行。P28源码的首个“共享原身份”断言实际失败exit2；P29最终17案/121断言通过exit0，覆盖四datatype共享、八项独立边界、严格大于barrier的三关系、共享与新查询混合银行及停止优先。默认路径、其他线程、不同datatype、已取出查询、Resolve/EventQuery和较早的新截止均保持独立。每个构建的640个冻结源码、14个对象及绝对库在构建前后核实；两次最终构建、红/绿实际运行均完整物理回收。

限定证明（外部历史/待归仓路径：`../../build/ms-p29-queued-query-proof-002/PROOF-001.json`） SHA `fcab63c99c48533a160401467d0dd3af048d0342e34ff6c06b9550a938ff520c`核697绑定。该探针未启动worker/HTTP/SDK；实际dequeue竞争、事件负载并发、新入队分配失败及共享预留下的回调异常继续gap。早期red-build-001因旧私有签名缺少五参而编译失败，后继用测试专用宏仅适配旧入口，正向共享断言仍负责红例；编译失败原件不计回归通过。完整P29-C1、C2、C3及模块资格保持待验。

### full009来源计时、最终A材料选择及限定交接

full009已沿完整原来源及P29普通DLL结束：37笔SDK替身委托全部成交，实际35100份、目标50400份、差15300份，原`continuous_rounds.py:66`失败。Native正常关闭、Source通过、输入before/after一致及全部物理回收。该次Source全程单次agent_tick最大234毫秒、全推回调最大78毫秒，均为本次QA实际时钟。

分方法内存记录达到16384上限；记录只覆盖前段，包括25项SDK证据写入/返回尾部，全部来源查询共129项。记录前段中SDK尾部中位0..1.007毫秒、个别176.492毫秒，业务及运输的嵌套时间分别保存。该结果提供来源前段的实际开销，完整业务区间的分方法耗时、Native/Host UUID关联、持久提交与控制帧等待仍为缺口。该计时未进入产品，未把截断前段当成全程统计。固定证明（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/FULL009-SOURCE-PROFILE-001.json`） SHA `f90d0c08e3901d7cbb72d1778d3e3f6440f6e4d7e8f61cd9ab216504b6d63176`核149输入，尚无该案独立审查资格。

full007冷核独审（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/REVIEW-LATENCY-007-001.json`） SHA `fec22441a304c6bc842dd6f697c51bf769691af03d4a06aac136ea7d4412d6aa`核151绑定；P29状态回归独审（外部历史/待归仓路径：`../../build/ms-p29-queued-query-proof-002/REVIEW-PROTOCOL-001.json`） SHA `0a0a878c0765e57f74a7c4c05a66ad3b933d1cb82dedfdc6b2b62f28b1f1c864`核706绑定。两报告新增开放P1/P2为0，完整目标、真实worker竞争和发行恢复保持gap。

B进一步消费A最终`INTERFACE-003`的Host `0.1.0a18+durableio.2`、Agent `0.1.0a12+dailybatch.3`及installation003（SHA `f72e1a835dfd383935a4d15e58660d95830a512e19f5f81285829b4e3859f03c`）。`full011 --prepare-only`修正prototype原wt角色到最终host角色，四父端配置验证通过；外Job8748 exit0/27.250秒、12个实际准备子作业及外层全部物理回收。Source未启动、SDK0，限定资格为最终材料装配及验证。早期生成器对路径形态的断言失败、缺少生成入口的进程exit2、full010错误使用B工作根查A接口的FileNotFoundError均保留，不计最终材料资格。

限定交接（外部历史/待归仓路径：`../../build/ms-p29-execution-handoff-001/HANDOFF-001.json`） SHA `bafa3321f9393f5eb654ce3b91fcde4f2aafff848a17493991b943e784e9102e`重新核1625项当前摘要；共享owner接口（外部历史/待归仓路径：`../../build/ms-p29-execution-handoff-001/TRANSPORT-OWNER-INTERFACE-001.json`） SHA `d8f5e408325ceb87e82101e38afbffa56ebc9604ed16d56655f678eb256b983a`固定客户端/Source/Host的实际事实和下一测量边界。候选Standard仍6e035f40…、无诊断DLL仍9b43b80…，原P28包及live产品保持。后继沿最终A配套把原请求UUID与派发、控制轮次、来源执行、提交及HTTP返回相连，修正具体等待层后再验原70秒及三轮；当前完整模块与根集成资格均false。

### 精确请求关联与来源同轮回包

full013已实际消费最终A的durableio.2/installation003，在原完整来源与业务链执行。QA Native仅在固定Standard和BoundedSignedHttp副本增加有界内存时钟及请求UUID的SHA，任务join后输出；其余Native006对象及库保持。Host和Source只记录真实请求端点，原正文、认证头和金融内容不进入轨迹。诊断DLL SHA `d817c78a62804d0edbd4212207518c0c3ed57433b4b3eeb39baffbb0e21c767f`，普通P29及live源码保持。

98个普通Query由同一请求SHA直接关联，缺失/歧义/overflow均0。完整worker中位574.909毫秒，其中来源执行中位4.341毫秒、来源执行结束到reply准备中位109.392毫秒；Host持久claim结束到派发中位74.957毫秒。跨进程区间保留Python3.6时钟分辨率，Native HTTP与任务使用同一steady时钟；各项包含或重叠，不相加为独立全程耗时。初始化、业务和关闭均进入这些样本，统计范围与外部70秒窗口分别表达。

精确测量（外部历史/待归仓路径：`../../build/ms-request-chain-proof-013/MEASUREMENT-001.json`） SHA `0b4adb02da44dfb6f2cc8ae9916febe372e8be0e27d0c94a6af0c249d2569d7d`核23绑定；独立复算（外部历史/待归仓路径：`../../build/ms-request-chain-proof-013/REVIEW-EXECUTION-001.json`） SHA `e3b38a7dcf9ef2f900cb290938012a05b3cba0bd804bfdc6518d196981f37de4`核47绑定并确认上述数值。31次SDK后原70秒业务断言仍失败；Native正常closed.v2、Source通过、输入前后一致及全部物理回收。

源码显示显式strategy_tick模式先接收并准备原回复，再在外层执行一次SDK；新结果等到下一轮通信才可放入回包。full014只在隔离方法副本中改变这一相位：先接收和派发，保留同一原帧，经外层原SDK步骤后准备原回复；SDK异常仍由原业务边界传播，heavy准入、TickCredit和默认线程run保持。97项完整关联样本的执行后reply等待中位0毫秒，最大2.530毫秒；worker中位493.685毫秒。另1项task494缺Host consumed端点，其余请求端点在原轨迹中，单列为不完整关联。38次SDK后原70秒仍失败，正常关闭、Source、输入及物理回收均成立。full014测量（外部历史/待归仓路径：`../../build/ms-request-chain-proof-014/MEASUREMENT-001.json`） SHA `8e4b5276b096451ae4f573604d492492c78c7625eaa773622f272249a1800587`核27绑定。独立静态审查只覆盖stage002，full014动态结论另审；吞吐样本数量不单独证明完整性能通过。

### Host本轮领取与停止窗口的隔离候选

Host候选在原异步claim已开始后，以原poll_seconds为等待上限，在准备本轮帧前再消费该future。来源执行、派发前持久领取、结果持久保存后ACK、原future退休和关闭owner全部沿原实现。共享Source/Host归A；B只修改build下提案副本和QA方法选择，尚未接入live产品。

stage003的独立审查（外部历史/待归仓路径：`../../build/ms-source-roundtrip-proposal-003/REVIEW-CONTROL-ROUNDTRIP-001.json`）发现两个P2：claim在两次检查间完成时，分支会跳过消费并发空帧；clear唤醒后仅重查done，可能清掉停止唤醒。stage004统一按scan存在进入分支，在等待后总消费结果；clear后同时重查stop/done，停止时在再次admit和prepare前退出。最终delta（外部历史/待归仓路径：`../../build/ms-source-roundtrip-proposal-004/REVIEW-CONTROL-ROUNDTRIP-002.json`） SHA `9da3fd3f4485d72ea6908d1a579b7062ff1442d562e3b62bef0a6052e4722f9a`核69绑定，两项P2关闭，当前新增P1/P2为0。

`.tmp/ms-control-roundtrip-regression-001.py`使用实际Host run/admit/progress/complete和合成Future/Peer/Session，旧stage003恰在上述两案红，新stage004七案绿；已完成、等待中完成、域失败、poll到期和入口已停止同验。外Job51832 exit1、37492 exit0，各自树零、EOF、join和资源关闭。它们验证本轮发送及停止责任，实际并发、完整业务和安装资格继续待验。

来源受控回归最终`.tmp/ms-source-phase-regression-003.py`使用实际ControlPeer、AgentControlLoop和TickAgent，配合单步SDK替身：同tick回包、heavy不准入后续执行、发送Pending保持原字节/ACK退休、SDK异常传播四案候选通过；同一脚本原版前三案红、异常对照通过。外Job35080 exit1、59460 exit0，完整回收。初版001误用Python对象identity检查，而原Batch.packet每次decode产生新对象；002修正为canonical字节身份，但旧版第二pump已重发空帧，send_pending前置断言导致报告未写及第四案未跑。003去掉该时序前提，各案单独归档，由真实回复/原字节/SDK调用数及ACK退休判定。前两版原件保留，不作最终四案红绿证据。该回归没有真实SDK/套接字，完整来源及关闭资格由实际主链另验。

来源与full014的独立动态审查（外部历史/待归仓路径：`../../build/ms-source-roundtrip-proposal-004/REVIEW-SOURCE-DYNAMIC-001.json`） SHA `b290ae085dac0b56555afd4a9f8fe7b062914db82fdaf98e0bfe2de178736b6f`核58绑定，97/98关联及task494缺consumed/owner-pop按实际范围登记。最终003四案与两项QA修正已复核，本范围新增开放P1/P2为0；Host完整动态、全业务和最终集成仍为gap。

full015仅生成、未运行。stage004完整业务full016已终态：41次SDK后原70秒仍失败；98项完整关联，另1项缺消费端点。来源执行到reply中位0毫秒，Host claim中位41.163毫秒、claim完成到派发中位64.980毫秒、worker中位484.416毫秒。固定测量（外部历史/待归仓路径：`../../build/ms-request-chain-proof-016/MEASUREMENT-001.json`） SHA `8536e525edaaf012441f3c20560c96d0b76e63ab1d995d2cd6432b586bcfe53a`核27绑定，Native正常关闭、Source通过、输入一致及全部物理回收。

实际部署control_profile.poll_seconds为0.005、io_seconds为2；stage004的5毫秒等待常在约41毫秒claim完成前结束。后继stage005继续按原poll分片等待，整个等待上限取原I/O预算的一半，保留另一半运输余量，完成即消费并准备本帧；SDK请求D、Source节奏和持久/ACK责任保持。同七案实际Host回归全部通过，Job72060 exit0/0.828秒及完整回收。该调度选择仍为A-owned隔离提案，实际并发/关闭和共享owner接受另验。

完整后继full017已启动，原Source100毫秒节奏、6982来源、SDK工作量、65秒晚到、70秒目标以及各业务截止保持；原可复用控制器main绝对预算为400秒，外层总规格600秒分别登记。当前最终普通安装、A接受与集成、完整三轮/恢复及整个B保持待验，新增WT行为和真实下撤单均0。

### 延长等待退出与ACK完整发送后的非等待准入

full017已终态：38次SDK、原70秒业务门槛失败，111项完整关联和1项缺消费端点，Native正常关闭、Source通过、输入一致及全部物理回收。测量（外部历史/待归仓路径：`../../build/ms-request-chain-proof-017/MEASUREMENT-001.json`） SHA `d3460df7600285290d5d08db57f8fd6855bad741533cb906379ddc60e56b54d4`核27绑定；claim结束到派发中位0毫秒，worker中位404.404毫秒。它说明等待段受到干预，整体业务继续失败。

stage005的最终审查（外部历史/待归仓路径：`../../build/ms-source-roundtrip-proposal-005/REVIEW-CONTROL-ROUNDTRIP-003.json`） SHA `974093262671e0e276b0ee5e8cdc3d0dc08203e0b8a2bf10dcd78424cfc96b46`核78绑定，开放P2为1：等待只看read.claim，可能拖住同轮已就绪的trade/event/ACK及其更早原D。该候选已withdrawn/not-for-integration；full017的统计与清理资格不授产品或性能通过。上段stage005在途状态由本段终态与退出决定取代。

stage006改为从A原control.py派生，唯一Host增量位于原session.send完整返回、原peer.sent(batch)完成之后：检查stop，再调用原_admit，随后立即进入原receive。该位置使用原ACK退休事实，原future/scan/job槽继续防重，没有新增等待、退休时点、D或队列。预计收益只覆盖旧ACK刚退休且下一项已进入Journal的情况，首次claim及更慢的domain不由此解决。Source两成员与stage004逐字相同。

实际Host run/admit/progress/complete与ControlPeer九案候选通过、基线四个后继领取门失败；SDK0、Domain/Session为替身。场景包含未ACK、send失败、sent收据失败、停止、重复准入、原短D已就绪CALL和原域异常。旧future以合法observations完成/ACK后用于read_future，claim返回为空，因此该九案只授通用退休/控制流资格。001误用observations参数被原grammar拒绝，002改为合法after_seq，原失败保留。Job35128 exit1/58488 exit0均完整回收。独立审查（外部历史/待归仓路径：`../../build/ms-source-roundtrip-proposal-006/REVIEW-POSTSENT-001.json`） SHA `6fd71e73249d0284ee3af42567596bab123bd9559a846c964965a4d6dc5ff756`核91绑定；005的全局等待P2在此候选关闭，当前静态与九案范围开放P1/P2为0。

随后将原44项HostTrading/SQLite/SourceTradingService及SDK替身向量运行两遍，候选仅在原Harness.cycle完整sent后插入同一_admit。最终基线和候选各44项全通过，无skip，分别50个源绑定；Job54828 exit0/25.562秒、43552 exit0/25.968秒，树零、EOF、join及资源关闭。公开测试的旧Runtime fixture与最终安装存在两项合同缺口：connection_continuity属性、observe_source的continuity关键字；QA003给默认None并严格断言continuity为None后转原方法，两组采用相同适配，原断言和产品不变。001的两组29失败、002的两组28失败保留，最终资格只沿003。该矩阵覆盖实际交易/事件/未知/关闭逻辑，原Host.run动态与完整业务性能分别验收。

stage006完整原链以新full018运行，继续相同Native诊断、A最终安装、原策略/SDK/Source100毫秒及全部原业务截止。三份共享live源码再次核同原SHA，修改仍只存在于build/QA。A接受、最终普通发行与离线搬迁、完整三轮及恢复/整个B保持待验。

### full018终态及交接选择

full018已终态：41次SDK后原continuous_rounds.py:66、70秒目标仍失败；101/102项完整关联，另1项缺消费端点。Native正常closed.v2、Source通过、输入前后一致和内外完整物理回收。测量（外部历史/待归仓路径：`../../build/ms-request-chain-proof-018/MEASUREMENT-001.json`） SHA `d05c8397551e8d1fa0277a7d5eb9c754e1067338db5aff64742fef62bbd80566`核27绑定。Source执行后reply中位0毫秒；Host受理结束至claim开始中位52.207毫秒、claim结束至派发58.537毫秒、完整worker502.413毫秒。该样本证明来源相位保持，整体性能继续失败，006额外准入的实际性能收益保持未证。

交易矩阵独审（外部历史/待归仓路径：`../../build/ms-source-roundtrip-proposal-006/REVIEW-TRADING-DYNAMIC-001.json`） SHA `fee62c149acd70a9159815c39e1bc482984cd3d5680d91a18b234b5b0b1c4560`核129绑定，最终基线/候选44/44及同一QA合同适配通过，本范围新增P1/P2为0；同报告复算016的98/99和017的111/112关联，017的退出及开放P2保持。018未纳入该报告，后继测量独审单列。

既存worker冷核（外部历史/待归仓路径：`../../build/ms-control-roundtrip-handoff-001/WORKER-COLD-001.json`） SHA `ee7539301eaa92f42a7d4166feba099eebc4525d935304452eae4278e79c3d27`只读取013/014/016/017同次轨迹，以task/kind/stage分组Query、Resolve、Insert及事件任务。例016的99段Query合计49.254秒，41段Insert合计19.093秒，97段Resolve合计5.696秒；这些包含初始化/业务/关闭，HTTP子区间已计入worker，分别保存而不冒称精确70秒或纯SDK时间。该核对把下一测量继续放在查询与写往返，不据此开发新的金融账本或改WT调度。

本轮交接选择为已验证的Source同轮回包及精确责任层数据。Host006保留限定静态/生命周期与交易矩阵证据，其性能收益尚未成立，暂不作为推荐产品增量；005维持退出。共享owner由A统一接入和发行，B随后消费固定同版候选继续原完整主链。当前没有新的产品安装包或live源提升；P29与P28既有制品保留原资格，整个模块继续active。

018的独立后继复算（外部历史/待归仓路径：`../../build/ms-request-chain-proof-018/REVIEW-EXECUTION-001.json`） SHA `b9bfa793d816c12d5a331a4de64ff8d931a1e19a1bf0b0b34159ebbcf22e3c98`核52绑定，确认101/102完整链、task493缺consumed与owner-pop，旧四轮worker分组及Query/Insert统计一致；新增开放P1/P2为0，业务性能及完整交付继续gap。本轮HANDOFF（外部历史/待归仓路径：`../../build/ms-control-roundtrip-handoff-001/HANDOFF-001.json`）与共享owner接口（外部历史/待归仓路径：`../../build/ms-control-roundtrip-handoff-001/INTERFACE-001.json`）固定两份Source候选、Host保留/退出边界、逐文件diff、全部匹配引用及冻结文档，供A按单一owner处理；本接口不授整模块或生产资格。

### 普通无诊断Source候选完整后继

上述HANDOFF封存时290引用匹配、文档检查通过且全部B业务作业终态，具体摘要沿同目录POSTFLIGHT-001和DOCUMENT-CHECK-001。其后启动full019，单独验证普通运行资格：从最终A安装的原full011控制器派生，选择P29无诊断普通DLL `9b43b80c89db9449ce311cd84cd399c79bb54f97e708988686dc66bc14c3ef42`，仅在QA的实际Source类选择三份已审方法，Host仍原实现。没有Native/HTTP/Host/Source请求计时包装；原业务Source替身、SDK工作量、100毫秒、65秒晚到、原70秒及main400秒保持。

019选择收据（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/CONTROLLER-SELECTION-019.json`）固定控制器SHA `0fadddf451d346bb4ff8968db6153784d675da78856bb01075e9b5638358c698`，Source方法载荷SHA `398443c7fae947ad220d4d7764f7b664c78e42d9a123579ea8e430a10953c184`。该业务运行是HANDOFF之后的后继，不纳入此前“全部作业终态”的封存时点；终态与完整资格继续待验，原生产/共享源码/WT和真实交易保持。
