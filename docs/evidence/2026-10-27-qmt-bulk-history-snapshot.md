# 2026-10-27 QMT 长窗历史快照与 SDK 边界

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：partial；BS1–BS5、BA1–BA3 的纯核心及 SDK 替身验证通过，运行接线与真实长窗继续。关联[功能规格](../specs/qmt-bulk-history.md)及[完整批量方案](../migration/qmt-bulk-history-export-plan.md)。

## 根因与实现

普通历史受5个日历日/2000行和单次结果字节限制；直接放宽窗口会继续受整包结果、QMT原线程及复制峰值限制。新增自有 BulkSnapshot 与 BulkHistory1mAdapter：原策略线程一次 SDK、count=max_rows+1哨兵、Frame/NumPy在同线程转换为独立内建tuple；工作线程只分页纯值。普通 history_1m 与 bulk 共用唯一 validated_row，原参数、输出、预算和默认能力不变。没有新增 WT 核心修改、数据引擎或账户账本。

range/session/snapshot/证券/原窗口固定，单个未ACK页同bytes/SHA重传；行数、行编码、快照、完整页和累计首次发出字节都有额度。ACK不重新调用SDK；最终ACK才完成。SDK、iterator、标量或编码在途时，关闭/到期保留真实owner责任，原线程返回并释放供应商引用后才pending=false；失败原因锁存为固定枚举。快照/页逻辑字节与Python堆、Frame及进程RSS分别说明。

## 输入与证据

- 核心 bulk_snapshot.py 最终 SHA：46113273a704a1312ffd62b9b288da0fa5d55727ecfb9d297e82e78f3bd67cd5。
- 原 history_1m.py 公共校验提取 SHA：4ecef8d5bff3bc1b52bfe0a4519bbbc75359a55f111bec21b198fef14eb5fc46。
- SDK 适配源码与21核心/14SDK/9原历史方法全部身份见 PINS-003（外部历史/待归仓路径：`../../build/qmt-bulk-history-validation-001/PINS-003.json`），SHA f9f3122c7d25b54ac55dc0df5ef458117e94aafb58579b1973ad3d85c9d956c6。冻结41个Agent模块，同一核验缓冲区加载；前后源码/测试相同。
- 测试入口（外部历史/待归仓路径：`../../build/qmt-bulk-history-validation-001/run.py`） SHA 246f5841d3a1a53f7d4c51912fa6490eb286653f824df30ec0210e3eb3b35d92。采用-I -S -B，无旧QMT工程导入，无SDK包导入，无新增存活线程。
- 作者revision001/002/003分别保留；最终003只把核心业务注释译中文。根对最终输入重新运行全部44方法。

| 实际运行 | 结果 | 原期限与回收 |
|---|---|---|
| Python3.12.14 结果（外部历史/待归仓路径：`../../build/qmt-bulk-history-validation-001/MODERN-003.json`） | 44/44，0失败/错误/skip | root23120自然exit0，0.652秒；外Job60秒、传入原D55秒、rootguard70秒；无forced、tree0、双EOF、join和资源关闭 |
| 国信实际Python3.6.8 结果（外部历史/待归仓路径：`../../build/qmt-bulk-history-validation-001/TARGET36-003.json`） | 44/44，0失败/错误/skip | root15432自然exit0，0.807秒；同上原预算；无forced、tree0、双EOF、join和资源关闭 |

两个协调器own_console=false，子进程创建前已加入原Job、2GiB进程树预算与双路64KiB捕获。3.6.8实际exe SHA49cfc2336b4386b851d575d97e649a1c2bf6f18f339b172386423820e2026c85。Root句柄记录（外部历史/待归仓路径：`../../build/qmt-bulk-history-validation-001/ROOT-HANDLES-003.json`）含原PID/guard/退出/耗时，SHA acb2d5ed56346c2793150cf7e58b097cc8cff19a3e45c6da3c83540077f93c2c。完整协调器原件保存在同名 guanheng-workspace/qmt-bulk-history-modern-003 与 target36-003 目录。

## 证明范围与审查

覆盖一次SDK及只在原线程、长日期参数、count饱和、Frame列重排/空/实际行数不符、内建数值及跨页时间、原Frame变异后快照不变、供应商对象弱引用释放、iterator晚回到期、worker分页不访问SDK/Frame、同页不重新编码、错误ACK不丢页、重复ACK/空最终页、无限producer有界消费、各容量、忙/关闭/超时竞争、generator finalizer在途及首因保留。原九项历史回归包括普通profile字节、既有来源校验、原线程finalizer与执行截止。

并发及公共状态触发独立full。首轮审查发现分页返回包装尚未构造就解除owner、失败码状态与异常投影不一致，以及峰值措辞过强；责任层修正及精确窗口回归已在最终输入通过。最终报告见独立审查（外部历史/待归仓路径：`../../build/qmt-bulk-snapshot-independent-001/final003/REPORT.md`），SHA0ca9824859014e2ef9deec0a2474427054eec9ceddd7032f7ac3363d7f0155cd。规格后仅补原生能力依据段，由文档delta（外部历史/待归仓路径：`../../build/qmt-bulk-snapshot-independent-001/documentation004/REPORT.md`）核正文BS/BA及代码/测试不变，当前规格SHA604e0d8f3a066a56b2869e41c0d8a9d7a4d015b610e1d0cc5bd98f070d47cfc4、报告SHA2c64393a2195f7c5dbf24b9f735292fe868c239a1a8929ceaeb144f3518de444。必要P1/P2=0，资格仅纯核心/SDK替身及目标解释器，不扩展真实来源或发布资格。

## 限制与下一步

新bulk尚未接入运行registry、签名能力profile、ControlPeer及Host/C++。SHM slot ACK只表示运输复制；Host持久CSV/Journal后的业务确认、明确ACK退休观察、同代恢复及最终artifact封口仍待实现。Host将直接生成原QMIv2 chunks并复用原Importer/Helper/DSB/sourceReader；原Importer每证券仍物化有限数组，需计外部峰值。

真实SDK Frame/内部内存峰值、长窗SDK不可抢占时间、复制与页落盘吞吐没有通过结论。后继先接完整运输和落盘，再对同一小窗逐值核对普通接口，测一证券月窗及完整历史，按证券库存/固定20211101起日扩展并登记ETF覆盖。真实常驻超过60秒及实际两代断开重连、查询优先完整交易恢复、策略/保留观衡和独立发行仍保留在总目标中。

本轮没有启动/停止终端策略、下单、撤单或生产切换；现有终端正文SHA4034e03e12be1ee219ce828829ba76eb64a3843e1c3871e7d278ceb3707bd09d保持。两份获批TraderAdapter源码摘要仍匹配既有批准身份。当前无用户待决策或操作阻塞。

文档检查：`python -B scripts/project.py check` 实际root30932 exit0，0.611秒，导航/技能清单PASS；45秒原外D内tree0/双EOF/join/资源关闭。该工具不验证应用构建、运行、UI或发布。测试runner末落证/print后无再次子D核查，此限制沿独审保留；本轮两个外Job实际提前正常终结，只支持本次有限运行结论。
