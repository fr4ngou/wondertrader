# 实时回报与完整查询双来源身份适配

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。日期：2026-10-25。状态：产品已编译、部分旧入口回归通过；新增双来源功能仍待独立测试与审查。完整迁移目标保持进行中。

## 实现与范围

依[accepted R5d-B](../specs/native-qmt-standard-events.md)，新增入口在同一原截止内保留完整原事件及完整原查询，从原下标映射一条金融对象，再沿原begin/resolve/finish恢复委托身份。历史身份依据来自实际lookup返回，当前补查结果独立保留。WT对象留在owner线程，worker只接独立值；不新增金融账本或worker。

产品修改仅QmtAccountIdentity.h/.cpp，规格同步；原mapper、matcher、Common、Standard、Host与WT行为没有在本片新增修改。根补齐AccountEventMatch链接与隔离测试目标。正式新测试仍由独立作者开发；编译快照捕获的测试草稿没有运行资格。

## 固定编译与既有状态回归

固定产品001（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-query-product-fixed-001/result.json`）含160份自有来源与323份Git原上游来源，WT commit 08b230dd05facf6d650d949bfe51054115a2ecb1。StandardTrader、LegacyTradeClientProbe、UnknownCancelStateProbe三目标首次编译通过，外层86.703秒、exit0、无强杀、无控制台、创建期Job、tree0、双EOF、读线程join及资源关闭。

同版状态回归（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-query-state-compat-controller-001/build-qmt-event-query-state-compat-controller-001/driver.log`）实际49场景、2126断言通过；其范围为原私有合成状态，未调用真实券商SDK。外层0.328秒正常回收。根复核收据（外部历史/待归仓路径：`../../build/qmt-event-query-implementation-work-001/PRODUCT-COMPILE-VERIFIED.json`）保存范围。26项已保护框架文件本轮SHA相同。

追加编译002（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-query-product-compat-append-002/result.json`）在同一快照/CMake tree编译既有八个兼容目标，未重新configure；与前三目标合计九个不同目标。工具仅重绑定固定输入SHA；独立delta审查（外部历史/待归仓路径：`../../build/qmt-event-query-product-compat-independent-001/REPORT.md`）核实原166份Python与59方法、截止和断言保持。001合同生成误把文件映射当数组，缺少owned_count，在准入KeyError终止，未进入编译；失败原件保留，002仅修复清单数量。

## 当前未覆盖

新增双来源的真实AccountClient→P8→lookup、历史proof、独立费用边界、错线程/错票据及六路逐分配失败均待验。当前编译与旧回归不能证明这些新行为。Standard实际补查I/O/FIFO/容量接线属于后继C；首次及重连查询/回报覆盖边界、完整历史、连续实时与独立发行继续未完成。真实SDK调用0，生产Factory保持原入口。

## 首轮独立审查发现（修订中）

独审核到两个新begin分支缺口：std::exception处理用长reason字符串可再次分配并把bad_alloc抛出catch；旧identity非法子限额由共用构造器返回InvalidInput，与新入口accepted要求Backpressure不同。原作者正在仅新分支修正并封002，旧Query/Event保持。独立测试增加异常输入错误路径分配点及非法预算分类。001编译和旧入口回归保留其原范围，不授002或新增功能通过。

## 固定001旧链兼容后继

同一固定001与追加八制品的Common19、Standard31、Retry9已全部运行通过，无失败/错误/跳过。三组根收据（外部历史/待归仓路径：`../../build/qmt-event-query-implementation-work-001/PRODUCT-001-COMPAT-RESULTS.json`）绑定原件：分别18.094/38.078/51.828000000095926秒，均exit0、无强杀、无控制台、创建期Job、tree0、双EOF/join及资源关闭。该59方法覆盖旧入口，不覆盖新EventQuery；资格绑定001源码，不扩大到正在修订的003。

## 修订003编译与首冒烟

full001（外部历史/待归仓路径：`../../build/qmt-event-query-identity-independent-full-001/REPORT.md`）两组P2由delta003（外部历史/待归仓路径：`../../build/qmt-event-query-identity-independent-delta-003/REPORT.md`）静态关闭；新来源错误状态统一无分配形成，旧Query/Event与无来源双空句柄边界保持。根逐核52+50原件及来源，见收据（外部历史/待归仓路径：`../../build/qmt-event-query-implementation-work-001/PRODUCT-STATIC-REVIEW-VERIFIED.json`）。

正式固定001（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-query-fixed-001/result.json`）捕获产品003和独立测试001，十目标编译通过，外层117.750秒正常回收。新探针SHA a405d9606022004d74ae6e24cdc9061260deb85cee17d72079706cd81ba1edd8。

首冒烟（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-query-smoke-001/result.json`）运行B01两个变体，原生均exit0且passed/drained；父断言decode(data_json)把JSON读取所得str交给只收bytes的protocol.decode，实际2 errors，完整方法failed。两案Native Job均正常回收，Source线程/listener关闭，无源首异常；外层1.875秒exit1且无强杀/tree0/双EOF/join/资源关闭。失败收据（外部历史/待归仓路径：`../../build/qmt-event-query-implementation-work-001/SMOKE-001-FAILED.json`）保持；独立测试作者修复类型和其他静审问题后需重新冻结运行。原生通过不能替代父oracle完整通过。

## 测试002首批运行

功能002（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-query-functional-002/result.json`）按原D且遇错停止，前B01—B28方法通过；B29.order.financial-boundary原生exit2，实际29方法1失败，后继B30—B33与两fixture未执行。fixture把manual-boundary当external，但它满足真实SDK token规则，引发额外lookup，既有server不接受该token而抛ValueError。首版本没有保存已捕获的bounded stderr原字节，诊断取证也须修正。作者正仅改B29手工备注语义并补有限原管道/Handler异常取证，原金融极限和产品保持。002失败及其18.360秒正常外层回收原件保留；尚无35方法或全点通过结论。

## 产品003旧链兼容

产品003三批结果（外部历史/待归仓路径：`../../build/qmt-event-query-implementation-work-001/PRODUCT-003-COMPAT-RESULTS.json`）：Common19、Standard31、Retry9全部实际通过，0失败/错误/跳过，原D内正常回收。对应固定产品003及八个同树制品；工具数据delta（外部历史/待归仓路径：`../../build/qmt-event-query-product-compat-independent-003/REPORT.md`）的663raw与源由根逐份重核，原166运行源/59方法/8targets/预算保持。该结论覆盖当前产品旧入口，不能替代新B30分配计量及后继C/R8。

## 测试003的后继失败

功能003（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-query-functional-003/result.json`）前B01—B29已通过；到B30.order.measure-begin失败，实际30方法1失败，原生stderr已完整保留为allocation_all_owned_values_released。该断言同时检查live、contract引用与drain，原件不能区分哪个子条件失败，也不能区分warm或measure轮次。独立诊断（外部历史/待归仓路径：`../../build/qmt-event-query-b30-warmup-independent-001/REPORT.md`）确认warm路径同样开启追踪，与注释outside measured不符；真实分配owner尚未有证，不据此认定产品或WT泄漏。下一步独立有限诊断分别记录phase/point/live/refs/drain及有限残留；保持严格释放断言、原失败和当前产品不变。

## 对象池诊断与正式004

单次有限诊断（外部历史/待归仓路径：`../../build/qmt-event-query-implementation-work-001/ALLOCATION-DIAGNOSTIC-OBSERVED.json`）实测失败发生在warm：live=1、引用前后均1、drained=true；残留12816字节块包含一个真实公共WTSOrderInfo对象。释放该对象后池块仍保留。原上游thread_local对象池会复用后备存储，原测试却在预热时启用跟踪。独立动态复核（外部历史/待归仓路径：`../../build/qmt-event-query-allocation-diagnostic-dynamic-independent-001/REPORT.md`）及729原件由根逐份核同。该结论仅解释这块实际分配，不扩大为其他路径的泄漏或完整无泄漏证明。

正式004沿完整同route预热且不启用跟踪，后续测量/故障仍严格检查live=0、引用恢复、drain及窗口计数；未清追踪表、未豁免池块。delta审查（外部历史/待归仓路径：`../../build/qmt-event-query-identity-tests-independent-004/REPORT.md`）37原件根核同，无新增P1/P2。新固定编译（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-query-probe-fixed-004/result.json`）通过，探针SHA 68f1f984b61c3f7e617babd71b6e88fe945aa86b9dd4c148cfa810d881c6126a；外层65.656秒、无强杀/控制台、tree0、双EOF/join及资源关闭。产品003与323上游输入保持。新38方法正在运行，全部分配点尚未测量/验收；冷启动池增长与物理allocator失败继续未验。

## 正式004功能实际结果

功能004（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-query-functional-004/result.json`）38方法、77个不同原生输入全部通过，无失败/错误/跳过。根逐案核首错为空、cleanup无错、子进程exit0/未强杀/已回收、创建期Job、双EOF，Source线程和listener关闭。外层19.875秒正常关闭。八路预热actual start/attempt/injection增量为0，实际引用和drain恢复。

实测global-new点数：ORDER begin1889、resolve1941、finish0、begin-exception1331；DEAL begin1861、resolve1942、finish0、begin-exception1299，合计10263点。它们是计量值，逐点故障注入尚未完成；finish0如实记录，不虚构故障点。根收据（外部历史/待归仓路径：`../../build/qmt-event-query-implementation-work-001/FUNCTIONAL-004-RESULTS.json`）绑定004 EXE和167运行源，未授Standard后继接线、冷池增长或生产资格。

## 首批故障注入与实际分类根因

首批八点（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-query-allocation-smoke-004/result.json`）在DEAL begin-exception的1..8计划失败，完成点数0；原stderr为allocation_begin_resource_kind。外层4.281秒正常回收，Source无首错、子进程已回收，原失败完整保留。runner独立full未发现新P1/P2；该结论不授本批通过。

最小分类诊断（外部历史/待归仓路径：`../../build/qmt-event-query-implementation-work-001/BEGIN-CLASSIFICATION-DIAGNOSTIC-OBSERVED.json`）以同一八点输入实测point3：1次注入后返回Backpressure(6)，合同要求IoError(10)，candidate/plan为空、引用1→1、drain完成。profile validator将bad_alloc转为Backpressure并再分配34字节reason；直接传播或经其他调用者的.ok()/bool后会丢失原资源类别。48字节追踪块属于当时仍活着的Status.reason，不认定为资源泄漏。静态完整调用链调查（外部历史/待归仓路径：`../../build/qmt-event-query-resource-path-inspection-001/REPORT.md`）列出准入、Shm mapper、Trade prepare/receipt消费者及修正选项；共用层资源异常契约正在收敛，正式产品尚未因此改变。新38/77基本功能结果保持其范围，全部故障点继续未通过。

## 共用资源通道后继

实际point3根因已在自有Common/Identity统一修正并注释，正式004探针与修正产品的新38/77、原8点及旧59均已通过；直接profile196双模式、选行1592全点也已实跑通过。源码、构建回执更正与资格范围见[独立资源通道证据](2026-10-25-qmt-profile-resource-channel.md)。原失败及旧冻结结果保持，全10263点后继仍在进行。

## 资源后继全点完成运行

同一正式资源修正制品的single10263点、1286片已实跑全过，根逐核无缺漏/重复及真实回收；另24个persistent代表点通过。详见[后继资源证据](2026-10-25-qmt-profile-resource-channel.md)，原003/004失败保留。独审最终封存和Standard C接线继续，生产及R8资格未授。
