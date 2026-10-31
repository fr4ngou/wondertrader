# 2026-10-25 标准Trader事件读取容量、截止与等待

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：**pass（限定 SEV-R13-D1/D2/D3 及共享夹具四项回归）**。关联规格：[标准事件消费者 SEV-R13-D](../specs/native-qmt-standard-events.md)。角色：测试作者对根线程执行原件的自查；独立审查另行登记。

## 输入与执行身份

根线程通过隐藏受管入口执行 runtime003/run.py（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-capacity-runtime-003/run.py`）。本次文档复核仅读取文件和计算 SHA，没有启动测试、编译、SDK或终端。测试链为实际候选 Factory/Standard DLL → loopback HTTP/HMAC → Host → Win32 builtin SHM → 源策略线程 SDK 替身 → 原版 TraderAdapter，真实 SDK 调用为0。

来源014清单（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-runtime-sources-014/INPUTS.json`）含165文件。本次逐个核对 frozen 原件，165/165 SHA一致；运行驱动末尾也核同一清单。清单 SHA：`2cd4a3637516718b88bc192708ba719909e6aae4fef16ae6d5bf0b9be67ccea1`。此项证明冻结身份，清单内其他模块的功能覆盖保持其原证据。

| 关键输入 | SHA-256 |
|---|---|
| 适用最终规格 | `91e5e16bc900acfa5aada379e7aa0700af34c1f6f85e43930f6ef5f0a4bf3ca5` |
| StandardQmtTrader.cpp，fixed002 owned | `222810e30113cd4e5df57e27a357076f219ea378ba19a894a65d922e76a0c7cc` |
| fifo_capacity_probe.cpp，capacity-fixed002 owned | `6e242c73f9836c7308fd18afd535f59cdc0cbaab62a4551c1dcbcf0d0448ed85` |
| test_event_read_retry_capacity.py，sources014 | `7b0f29ba1ae7845ebdd3f8761a528ff307c7b46820900d4a6bd80a27cdb1bb5e` |
| test_standard_shm_events.py，sources014 | `65721005681d725b2315767ef37beb0666d741237996806600a16d136e7bcb9b` |
| 实际 NqpStandardEventCapacityProbe.exe | `9841a1407011d21f70521712f0f9d103affc730d82b76ddf9379c07340fb6d55` |
| 实际 retry-fault-traders/TraderQMT.dll | `18ea96a217b912065ef10b331edd1ca021f195687ab14722c95871fd41c86e34` |

二进制按驱动路径重新读取计算 SHA，与三案 input.json 的 artifact_identity 一致。容量链使用专用故障 DLL 的既有 kind4 真实 session 保留接缝；共享回归使用驱动指定的普通 DLL。构建来源为 capacity-fixed002（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-capacity-fixed-002/owned/input.json`）及 fifo-fixed002（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-fifo-fixed-002/owned/input.json`）。

## 执行结果与预算

收集清单（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-capacity-runtime-003/COLLECTED.json`）、日志（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-capacity-runtime-003/tests.log`）和结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-capacity-runtime-003/result.json`）一致：**7/7，失败0、错误0、跳过0，43.093秒**。包括容量3案及共享4项：正常链、跨序号重复、回调停止、清理异常保首因。外层受管记录（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-capacity-runtime-003/build-qmt-event-read-retry-capacity-runtime-003/result.json`）为 exit0、forced=false、tree_zero/readers_joined/resources_closed=true、own_console=false。

三案 input.json 均记录 Host 读Journal **64条/2097152字节**，代理 **1024份HTTP记录**；native仍为 **max_queue=16、max_queue_bytes=268435456**。共享默认代理256、原8MiB字节及128页上限保持。Host记录、代理取证、native outstanding名额与native字节额度各自独立；256MiB用于本组隔离名额背压。

## 三案实测

### D1：满16仍到达原事件截止

D1原生结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-capacity-runtime-003/outputs/shm-event-normal-9fdeb8e0b54c4236aff22f5430e74f41/native-result.json`）：16次公开查询准入，第17次返回Capacity（-5）。queued=15、ready=0、candidates=0，另1项在真实HTTP门内执行；payload=22049488字节。事件request_ms=3000、poll=200ms。

| 原事实 | 原生steady ticks |
|---|---:|
| event D lower | 977832417224900 |
| 实际wait唤醒 | 977832657595600 |
| 空pump完成 | 977832657612300 |
| event D upper | 977832896136100 |
| 普通查询D lower | 977833407270800 |

链D没有公开诊断字段；lower/upper来自初始账户回调和真实故障观察的界限。wait返回PumpReady（1），pump(1)返回0；原检查确认事件Timeout（error=5）、原reason及写门/停止状态。完成时间比普通查询D下界早749.6585ms，普通查询自身超时没有充当本案触发器。

金融值为持仓100/可用100/undone100，账户SPI1、订单/成交SPI0，insert替身1次、cancel0次；源查询仅初始四类，代理70条。Host durable/source ACK及源acknowledged均到2，gap=null、retained=0。传输前沿与本案金融SPI0分别记录。

### D2：真实Resolve释放一槽，cadence后只追加一次

D2原生结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-capacity-runtime-003/outputs/shm-event-normal-72af5ba0cdc44a2a967c5cf06721f16e/native-result.json`）：满额时queued=14、ready=1、candidates=1，加正在HTTP中的1项合计16；第17次返回-5。pump(1)真实交付原金融Resolve，账户回调计数到2后才释放唯一credit。

| 原事实 | 实测值 |
|---|---:|
| 满额payload | 30437584字节 |
| 释放后 / cadence前payload | 22048976 / 22048976字节 |
| cadence后payload | 22049488字节，恰+512 |
| 释放后 / cadence后queued | 14 / 15 |
| 再次公开查询 | -5，事件任务已持有唯一空槽 |

cadence前空pump时间977837498016300，早于lower=977839656448800；入队时间977839675607200，晚于upper=977839656482500约19.1247ms，仍早于事件D下界9914.7386ms。随后三个空pump保持同一queued/payload，无重复任务。原事件request_ms=15000、poll=2500ms。

释放真实session及响应门后完整金融链通过：持仓120/可用100/undone0、活动委托0、订单SPI2、成交SPI1、账户SPI18。源初始四查询加后续17次账户查询，共21次，均在原线程；insert/cancel替身各1。代理278条，Host及源ACK到3、gap=null、retained=0。

### D3：满额等待的owner CPU与worker HANDLE

D3原生结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-capacity-runtime-003/outputs/shm-event-normal-c275b5bb09a145128e26cf96969e1c7c/native-result.json`）：queued=15、ready=0、16个真实outstanding，额外查询返回-5。三个wait开始时已超过cadence上界324.7278ms，最后结束仍早于事件D下界13762.6957ms。

| wait(PumpReady,100ms) | 实际墙钟 | 返回 | owner CPU增量 | worker CPU增量 |
|---|---:|---:|---:|---:|
| 1 | 107.265ms | 8（本次wait截止） | 0 | 0 |
| 2 | 108.510ms | 8 | 0 | 0 |
| 3 | 109.816ms | 8 | 0 | 0 |
| 合计 | 325.591ms | — | 0×100ns | 0×100ns |

主证来自执行wait线程的GetThreadTimes，三个样本均1562500→1562500；worker补充证据为625000→625000。零增量表示该测量分辨率下未记录额外CPU。各次wait后的queued/ready/payload保持，原检查确认未报告可推进完成值。

D3通过init前后当前进程线程差分确认唯一新worker，持有真实查询/SYNCHRONIZE HANDLE，OS线程ID42876；真实join后WaitForSingleObject(handle,0)确认终止，CloseHandle成功。D1/D2没有额外打开CPU观察HANDLE，其worker_handle_closed=true仅说明该观察owner为空；三案实际worker join由原公开关闭链分别确认。

恢复后同D2：120/100/0、订单2/成交1/账户18、21次源查询、insert/cancel各1。代理284条，Host及源ACK到3、gap=null、retained=0。

## 生命周期与原失败保留

三案原生passed/closed/deleted/drained/joined、session_seen/released/cleanup及response_gate_released均true；pending_commands=0、final_payload_bytes=0。三案子进程均在resume前入Job，exit0、reaped=true、forced=false、双EOF=true、errors=[]。父端agent_close_confirmed、agent_resources_closed、host_closed、host_resources_closed、proxy_joined及server joined均true；owner_failures/proxy_errors为空。原D内真实资源收口与金融交付分别验证。

| 历史批次 | 原失败事实 | 后继变更 |
|---|---|---|
| runtime001（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-capacity-runtime-001/tests.log`） | D1通过；D2/D3分别84/81条代理记录、6次源查询后，account.trade_detail POST返回503/queue_full，native报shm_event_product_error | 容量子类Host原10条/200000字节改为有限64条/2MiB；恢复金融断言保持 |
| runtime002（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-read-retry-capacity-runtime-002/tests.log`） | D1通过；D2/D3各恰256条，源查询各21次，proxy_errors为ValueError（1/2次）；已记录响应无HTTP≥400，native恢复尾失败 | 容量代理独立1024记录；共享默认256及原字节/页预算保持 |
| runtime003 | 三容量案及共享四项通过 | 复用原生探针和产品；队列16与原D保持 |

runtime001两份失败fixture为`shm-event-normal-1c66e1c4b43b485c82f352b4b0aef3d9`、`shm-event-normal-b5ac6fe55145476bad551e93dfa61143`；runtime002为`shm-event-normal-107727f959fe4edda2704d22be6d5915`、`shm-event-normal-88cae284e9144ebe8df9744344fd503b`，均保存在对应outputs目录。正常202排队响应属于既有协议；本记录以HTTP≥400区分上述失败回包。

## 证明范围与后继

本证据覆盖同实例已知合成初始持仓后的D1-D3名额/原D/cadence/CPU及恢复金融链，并覆盖共享默认回归。D4红灯与修复另见[同实例读取恢复证据](2026-10-25-qmt-event-read-retry.md)。本组使用真实session保留/释放；旧callback门exit92失败继续保留，真实晚callback完整矩阵仍有缺口。

字节need/need-1、全部R13异常矩阵、R8首次/重连共同快照水位、跨进程恢复、生产Factory切换、真实券商交易及完整迁入保持各自未覆盖范围。本记录属于作者自查；独立审查、索引与任务状态由根线程分别登记。

## 根复核补记

根线程复核165份冻结输入、最终产品/探针身份与独审delta原字节，记录见002根复核（外部历史/待归仓路径：`../../build/guanheng-workspace/migration-slice-verification-20261025-002/VERIFIED.json`）。独立完整审查（外部历史/待归仓路径：`../../build/qmt-event-read-retry-capacity-independent-review-001/REPORT.md`）、DWORD类型修正（外部历史/待归仓路径：`../../build/qmt-event-read-retry-capacity-independent-review-001/revision002/REPORT.md`）、Host fixture预算（外部历史/待归仓路径：`../../build/qmt-event-read-retry-capacity-host-budget-review-002/REVIEW.md`）及代理取证预算（外部历史/待归仓路径：`../../build/qmt-event-read-retry-capacity-host-budget-review-003/REVIEW.md`）的静态结果各为开放P1/P2=0，执行0；动态通过资格来自本记录的实际runtime003。26框架保护文件保持既有基线。
