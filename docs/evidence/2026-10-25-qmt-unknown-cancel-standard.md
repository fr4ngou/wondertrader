# 2026-10-25 标准TraderQMT未知委托核查与定向取消

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：限定验证记录。关联[UC主规格](../specs/qmt-unknown-cancel.md)、[唯一C++契约](../specs/qmt-unknown-cancel-cpp.md)、[Common证据](2026-10-25-qmt-unknown-cancel-common.md)。Standard003的公开链、私有状态、旧回归在下列输入和范围内通过；生产首次/重连交接及完整发行仍待验证。

## 实现与责任边界

自有标准插件沿唯一worker进行原命令只读核查，owner接收结果并调用原WT SPI。未知insert保持原身份并禁止新insert；真实ORDER查询取得原委托关联后，允许对该目标取消。精确cancel_pending冲突将原申请与实际取消分别保留，后续只GET实际原UUID；双Started各保留自身在途责任、额度和原截止。

审查发现两项自有完成队列问题并完成根因修正：原deque交付可能再次分配并遗失尚未移交的责任；普通大查询增额失败仍保有未计费结果。最终在业务I/O前预留完成槽，以无分配提交移交完整责任；普通可重读载荷先真实析构，再用原512字节预留内的固定诊断交付。Insert/Cancel/Audit保有完整通信责任，超额停止worker并报告不变量故障。此处只管理通信在途状态和有界内存。WT继续拥有金融运行状态，没有另建持仓资金账本。

## 编译、复用与身份

三次固定构建都以原版上游08b230dd05facf6d650d949bfe51054115a2ecb1的323份输入为基础；原文及清单SHA逐字节根核无差异。最终003仅重编标准DLL与私有状态探针；复用002公开探针，其全部源依赖保持相同。002→003的四项差异仅为CPP规格、自有Standard.cpp、构建目标选择工具与私有状态探针。标准DLL没有Common故障注入宏或私有状态测试宏；私有测试宏仅用于专用同TU状态探针。

| 制品 | SHA256 | 使用范围 |
|---|---|---|
| 003 TraderQMT.dll | 41e7f4ac38ec0c86e4061f874bc458c77dfe81b146f290e50d691ba3b666aa7e | 最终公开链及旧标准回归 |
| 003 NqpUnknownCancelStateProbe.exe | 1ab1cb618b8ce648f5648a63d9faa2c6dacd8b37c9d249865ada7b421ec62803 | 49合成私有状态场景 |
| 002 NqpStandardUnknownCancelProbe.exe | dda430a03a2c1b7972349955dea3326110c0b67bedaa3098f14b34380d95c56b | 最终DLL的4条公开链 |

产品Standard.cpp为7e690734b5e93c91c6db6578efc2da72187ebc4d54b06223fb15abd68105d6bc；h为f518c687ed98835a6e4c29aabe5e3c468f952c9c5facdb0371381a27a048964a。主规格07cf36dcfdf0380b8263ba309f03c85d0b568ccbf70bde3ac4c3f25addf053c5、CPP规格eb265cbe811cf6bc495dba5a53407eb51208a9f333959435bf0bf3e274962960。

## 实际动态结果

| 批次 | 结果 | 实际覆盖与限制 |
|---|---|---|
| standard-runtime-003 | 4/4，0skip | 真实Factory/Host/Win32 SHM、原线程SDK替身：未知insert只读核查至正常WT查询/目标取消；取消未知与竞争409；解绑停止后续核查；预算不足保原责任 |
| state-runtime-003 | 49场景，2126条全局断言，0失败 | 编译最终Standard.cpp同TU；私有状态、双Started、原D、容量与分配异常；没有实际HTTP或券商SDK |
| standard-regression-001 | 31执行，30通过、1 ERROR，0skip，39.041秒 | 最终DLL配002原探针；旧unknown测试使用过期Source gap语义，原failed批次保留 |
| standard-legacy-fixture-002 | 原失败方法1/1，0skip，3.472秒 | 只更新旧fixture的Source v2与真实ACK关闭断言；产品与DLL保持，确认原Journal事实、SDK1、无重提及只读能力 |

旧标准回归最终按30+1覆盖31个唯一方法，原整批失败记录保持。旧Common回归另按36+1覆盖37方法，见Common后继记录。Source v2允许unknown事实保留时完成真实双ACK物理关闭；测试核对unknown_fenced、hard_fault、gap和write_admission分别成立，关闭前后原UUID/body/hash/state/source_result/resultSHA保持。真正gap、未ACK、硬错、超时和资源错误继续传播。

state-runtime-001的native45场景本身返回成功；外层错误要求各场景断言之和等于包含额外设置检查的全局计数，导致控制器失败。原批次保留；最终驱动核49唯一场景及各项总和不大于2126全局计数，没有改写旧结果。原Standard001/002各自发现的交付分配和普通结果计费问题也保留原候选身份。

## 独立审查与回收

Standard full及002/003 delta完成，两个已确认P2在最终003静态关闭，新增P1/P2为0。003独审报告位于build/qmt-unknown-cancel-standard-review-001/revision003；原20份规格/源码/规则原件逐字节核同。旧native fixture原件后继81fd由独立限定delta覆盖，保留003审查读取的旧7a20原件；旧Standard fixture后继af2977由独立限定delta另审。构建接线独审位于build/qmt-unknown-cancel-wiring-review-001，生产宏隔离、固定上游、11目标与显式目标映射均有静态依据；静态审查执行0。

根封存目录build/guanheng-workspace/qmt-unknown-cancel-standard-final-001保存最终源码原文、SHA、三次构建原件验证、探针复用依据、审查原件核验、方法集合及控制器关闭事实。编译和本轮运行均使用创建期Job、原总截止、有限输出的隐藏执行链；子树归零、stdout/stderr EOF、reader join、资源关闭且未强制终止分别核验，失败批次同样保存关闭事实。

## 剩余工程缺口

实际网络返回点的分配注入、实际旧B到新C逐字段替换失败、完整容量/父死亡/故障矩阵还需补齐。49合成状态场景与4公开链分别授予对应范围，组合不扩展为所有竞态已验。一般未知insert跨重启解除仍未设计闭合，原unknown保留。

生产首次及重连的查询/实时成交交接、缺字段补查、真实SDK字段、2021-11-01起全量分钟覆盖、全部保留业务入口及独立安装发行继续。生产Factory保持原入口，event_consumption_complete=0。真实券商下单/撤单0，未重启终端、切换生产或改旧QMT；26项已有框架差异保持原字节，整体目标active。


## 后继：原失败四案的一次有界观察

本次四案001（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-unknown-cancel-four-case-observation-001/result.json`）沿原164冻结源、原EXE/DLL和四案顺序/断言/35秒fixture等截止，实际4/4通过、无跳过。1135条连续trace、无丢失或观察错误；8条源关闭后peer-closing OSError观察及Host.failure原样保留，逐案10项清理逆序返回，Host/Source业务关闭与外层进程回收分别有证。外层（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-unknown-cancel-four-case-controller-001/build-qmt-unknown-cancel-four-case-controller-001/result.json`）保原90/80秒与2GiB，实际23.438秒、exit0、无强杀/控制台、创建期Job、tree0、双EOF/join/资源关闭。

独立动态审核（外部历史/待归仓路径：`../../build/qmt-unknown-cancel-four-case-observation-independent-001/REPORT.md`）完成，未发现本范围新增P1/P2；根重核233份raw及对应来源、170工具来源运行后SHA，见根收据（外部历史/待归仓路径：`../../build/qmt-event-query-implementation-work-001/UNKNOWN-OBSERVATION-VERIFIED.json`）。本次分类严格为not_reproduced，旧批次3/4未关闭；观察会扰动调度，不从成功采样推断旧慢提交首因。真实SDK调用0。

后继研究（外部历史/待归仓路径：`../../build/qmt-unknown-cancel-commit-close-research-001/REPORT.md`）定位缺少“真实claim提交后业务D过期→域Future失败→公开close”的组合负向。原Journal已有提交后期限保护，failed Future保留符合既定保守合同，当前没有据此新增产品修复。下一步补确定性组合回归，保留原失败及公开close失败事实。


## 后继：提交后业务到期的确定性组合负向

新专用测试（外部历史/待归仓路径：`../../tests/integration/qmt_shm_trading/test_host_trade_claim_deadline_close.py`）沿原Harness的Runtime模拟接缝，使用真实Journal/SQLite、AccountQueryAdapter、Source服务、Domain线程/Future和公开ControlLoop.close。原insert替身进入后保unknown，经真实ORDER查询事务形成index1证明，再受理真实目标cancel；仅在该域线程该取消UPDATE的真实commit返回后推进已注入业务Clock，原SQL、I/O时钟与D不变。

一次运行（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-unknown-cancel-postcommit-close-runtime-001/result.json`）实际1/1通过、0失败/错误/跳过，方法0.855秒；外层（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-unknown-cancel-postcommit-close-controller-001/build-qmt-unknown-cancel-postcommit-close-controller-001/result.json`）2.094秒、exit0、无强杀/控制台、创建期Job、tree0/双EOF/join/资源关闭。原异常与同一failed Future、close cause、原UUID/body/hash/dispatching及原业务D保持；SDK cancel0，没有第二次claim/外发cancel。公开业务close保持false，域实际join后，测试owner沿同一D独立关闭Journal/清理临时目录，九个处置步骤真实成功，未清除失败job或硬错。根收据（外部历史/待归仓路径：`../../build/qmt-event-query-implementation-work-001/UNKNOWN-POSTCOMMIT-RESULTS.json`）分列这些事实。

此结果只证明明确故障输入下的保守保护及资源处置；Runtime接缝为合成，未授真实HostRuntime/HTTP/SHM/Standard或生产资格。原四案3/4失败的耗时来源仍unknown，成功观察不回写旧记录。79来源逐字节固定，独立后继审核正在核实际原件。

组合负向独立后继（外部历史/待归仓路径：`../../build/qmt-unknown-cancel-commit-close-independent-001/REPORT.md`）已完成，79来源/55实际模块/95raw及控制原件核同，无新P1/P2；根逐份重核raw和对应源，见复核收据（外部历史/待归仓路径：`../../build/qmt-event-query-implementation-work-001/UNKNOWN-POSTCOMMIT-INDEPENDENT-VERIFIED.json`）。本限定负向合同已验，原失败首因和完整生产资格边界保持。
