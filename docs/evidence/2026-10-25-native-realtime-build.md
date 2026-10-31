# 实时CTA原生构建与输入闭包

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。日期：2026-10-25。状态：编译和纯回归通过，真实原生ticker/ABI/同核运行仍待验收。关联[实时策略规格](../specs/native-realtime-strategy.md)。

## 根因与实现

既有自有构建器允许复用work，仅核expected中的SHA；原WT CMake的GLOB可能编译work里遗留的额外cpp。修正位于tests/integration/native_realtime_strategy/build.py：work须全新，原路径祖先拒重解析，sources实际regular文件全集与expected精确一致，并逐项核SHA与单硬链接；配置前、配置后编译前、最终均使用原截止核验。依赖安装目录不受此sources单owner规则影响。

独审指出的首异常被finally末验覆盖、以及regular文件未拒多硬链接两项P2已在revision002修正：原编译/配置异常对象继续传播，末验异常独立附记；正常链末验失败阻止passed。新增真实临时os.link与首异常identity回归。修改仅自有build.py/test_build.py/README，不新增WT源码改动。

## 实际验证

| 验证 | 结果 | 原件 |
|---|---|---|
| 最终构建闭包纯回归 | 21/21，无失败/错误/跳过；Git/工具链为无进程替身，文件系统及os.link真实 | 结果（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-build-closure-pure-002/result.json`） |
| 新安装唯一策略核合成输入 | 3/3；普通安装core 0.1.0a5，125合成工作日/九读取/八执行与人工非零目标oracle | 结果（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-core-pure-001/result.json`）、安装身份（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-core-pure-001/stdout.txt`） |
| 固定上游与批准覆盖原生编译 | 199/199步骤，生成四DLL，127.578秒；399输入根逐字复核 | 构建结果（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-fixed-001/build-result.json`）、输入（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-fixed-001/build-inputs.json`） |
| 创建期Job与原D回收 | code0、forced=false、tree0、双EOF、读线程join、resources_closed=true | 受控记录（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-build-controller-001/build-native-realtime-build-controller-001/result.json`） |
| 独立静态full/delta | 两P2闭合、当前无开放P1/P2，执行0 | 最终delta（外部历史/待归仓路径：`../../build/native-realtime-source-closure-review-001/REVISION-002-DELTA.md`） |

上游固定08b230dd05facf6d650d949bfe51054115a2ecb1，仅叠加14份已批准NCS覆盖，其SHA与原reviewed-inputs相符；其余WT源沿固定commit冻结。四DLL分别为GuanhengRealtime、GuanhengRealtimeReader、ParserGuanhengSynthetic、WtDtHelper，实际SHA见构建结果；根复核（外部历史/待归仓路径：`../../build/guanheng-workspace/migration-slice-verification-20261025-002/VERIFIED.json`）核399来源和四制品。构建日志的旧CMake弃用/原版类型转换警告保留，本片未修改上游消警。

首版18项纯回归也通过，但它未覆盖最终首异常优先与真实硬链接拒绝，不授最终21项资格；原001输出继续保留。

## 未覆盖与后继

本片证明编译身份与合成纯输入，尚未证明原ticker驱动on_schedule、真实上下文Reader的d1/m1闭合前缀、借用epoch/线程、setter/pending/费用、运行中异常、正常退出及父死亡全部矩阵。已有Bridge与组合Reader将由专用ABI子进程按原规格接线；不手调schedule、不复刻算法或持仓资金账本。空交易配置/真实SDK0/生产保持；完整实时宿主与独立发行仍需后继。


## 后续实际 ABI、ticker、Reader 与同核验证

本段是上述“真实原生运行待验”的后继结果。最终 revision003 工具先通过独立 delta；根实际运行 9/9 方法、10 个错误与截止场景，再在两个独立子进程运行原生用例。工具回归使用真实 ThreadOwner 和一项自建 loopback HTTPServer 异常；其余时钟/方法替身按测试定义标识，不加载 DLL/SDK。

| 实际用例 | 结果及范围 | 原件 |
|---|---|---|
| initialize-stop | 原 Runner/Factory 初始化；INIT 在 controller 线程 34976，跨线程 62444 借用返回 -4；原 epoch 结束后借用拒绝；正常 stop/destruct | child（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-abi-runtime-001/initialize-stop/child-result.json`） |
| ticker-reader-core-stop | 九次同步 feed 均返回，active=0 后不再 feed；实际 BAR/SCHEDULE 在原 ticker 线程 73132，比末 feed 晚 10.032 秒，满足原 5 秒下限；主分钟线与九组各125条日线由真实 Reader 复制 | child（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-abi-runtime-001/ticker-reader-core-stop/child-result.json`） |
| 已安装唯一核 | 由普通安装的 strategy-core 0.1.0a5 求值，与同一冻结输入的纯核对照一致；CSI300 权重32/225，其余七角色0；信号/执行证券分别保留 | 总结果（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-abi-runtime-001/result.json`）、安装与工具身份（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-abi-runtime-001/input-identities.json`） |
| 错误与清理工具回归 | 9/9，无跳过；保首异常、HTTPServer.handle_error、真实join、pending保socket、最后文件与结果写入的原D | 原日志（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-driver-pure-controller-001/build-native-realtime-driver-pure-001/stdout.txt`） |
| 原生运行回收 | 两 child 均 exit0、无强杀、Job已reap、双EOF；created/destroyed各1、active_callbacks=0、setter_count=0、Reader线程join/socket关闭；外层25.094秒，tree0、读线程join、资源关闭且无控制台 | 外层（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-abi-runtime-controller-001/build-native-realtime-abi-runtime-001/result.json`） |

输入明确为合成工作日：closed_day=2026-10-23、feed_date=20261026，实际INIT自然日20261025；未改系统/WT时钟。日线经原WtDtHelper的CSV ABI生成DSB，分钟线由自建合成协议源提供；真实QMT SDK调用0。实际策略核从安装的distribution导入，收据、RECORD、模块origin和上海时区字节沿同一原截止准入。四DLL复用上述固定编译输入，没有新增WT框架修改。

实际两案都一次正常stop返回，本批没有触发原生stop_pending；对应工具pending场景不能代替原生长回调验收。实际/在途持仓与T+1、完整八目标setter执行、连续行情/pool2、正式NRT Host/安装入口、真实QMT来源及生产运行继续待验。本批 setter 始终0，不产生委托。整体迁移仍为in-progress。

独立动态复核已完成，逐项核136份原件、1125条日线及7875个业务字段、两例四DLL/九DSB、安装site九份py与完整关闭链；审查执行0。见独立动态报告（外部历史/待归仓路径：`../../build/native-realtime-abi-dynamic-independent-review-001/REPORT.md`）。根对该136份raw及对应原输入逐SHA复核一致，见统一收尾证明（外部历史/待归仓路径：`../../build/guanheng-workspace/migration-slice-verification-20261025-004/VERIFIED.json`）。错epoch/过期借用的拒绝由已执行源码必经断言证明，跨线程-4为child直接字段；两类证据分别保留。

## 后继目标测试的静态阻断与修订范围

目标/数量A/B revision001仅完成源码定义，独立审查确认F1：Bridge emit的active_callbacks归零早于原Context/Engine/ticker本轮尾部完成，不能据此准入下一轮feed。F2要求数量fixture直接消费原epoch捕获价格，常量11只作人工期望。该测试版本执行0，没有把它登记为WT框架bug或运行通过；见独立full（外部历史/待归仓路径：`../../build/native-realtime-target-independent-full-001/REPORT.md`）。

后继修订采用两个独占子进程，各只运行一次真实SCHEDULE，回调request_stop后不再feed，由控制器原stop/join确认整轮及资源退出。负向检查缺报价和完整向量前置拒绝；正向先复制8价，再读日线/唯一core并送完整8target，数量Basis始终标显式纯fixture。该方向仍须最终delta及动态验收；后续理论结算、多轮覆盖、actual/pending、T+1与正式生产保持原缺口，整体目标未缩减。

002后继实际通过：两个单SCHEDULE负向/正向子例、原默认ABI两例及共享9方法回归均通过；见[单轮八目标专门证据](2026-10-25-native-realtime-targets.md)。该结果关闭本轮测试F1/F2并验证数量到原setter的合成接线，多轮/settlement/actual-pending/T1及生产资格仍待验。
