# 标准交易插件的事件缺字段补查

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：实现与验证记录。起始日期：2026-10-25；最新续记：2026-10-26。状态：in-progress。产品003编译、最终公开12例及纯31例277断言通过，公开批次独立动态复核通过；同版未知委托纯49例2126断言通过。原19方法兼容通过，自有产品与常驻测试已集成；正式新DLL十二例及纯31例重验通过。完整C容量/故障、启动重连交接及生产资格待验。历史续记保留各时点事实，以末尾最新续记为准。

## 目标与复用

沿[SEV-R5d-C](../specs/native-qmt-standard-events.md)把原可信缺字段事件接至真实账户查询、唯一matcher、B三阶段及原交付索引/SPI。保完整原事件、完整原查询、所选原index和历史委托证明的不同来源；WT原生维护金融状态。单worker、原FIFO与绝对D保持，不增加WT修改、金融账本、HTTP算法、线程或生产Diagnostics。

## 已核定的设计

C004（外部历史/待归仓路径：`../../build/qmt-event-query-standard-integration-contract-001/revision004/REPORT.md`）的69列项、62份源原件由根逐核当前SHA一致。独立状态full（外部历史/待归仓路径：`../../build/qmt-event-query-c-state-independent-001/revision002/REPORT.md`）发现F1：唯一Completion.status若在发布跨D时改Timeout，会丢prepare/create正常停止的原Status。后继C005（外部历史/待归仓路径：`../../build/qmt-event-query-standard-integration-contract-001/revision005/ADDENDUM.md`）增加独立delivery_status/late，各query/resolve阶段分别保留；独立delta（外部历史/待归仓路径：`../../build/qmt-event-query-c-state-independent-001/revision003/REPORT.md`）关闭F1。根重核full74和delta19份raw/实际来源，见收据（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/STATE-REVIEWS-ROOT-VERIFIED.json`）。该审查只授设计状态/API可实施，不授代码或运行。

正式规格记录QueryEvidence确切holder、正常及stop后接收、Failure先于通用deadline过滤、publish同锁关后继write、正常borrow退出后退原件、真drain/join后最终清理。新EventQuery签名只取query Remark；旧Event的OrderRef兼容边界保留。局部receipt复制/同源检查异常即使control=None也是真实本地Failure，不能只匹配typed Failure。

G3产生式研究另核到owner将任意SPI/第三方what全文复制到Status的有限性缺口。正式规格要求新事件域意外/资源异常用固定code/空reason并保已有首Failure/Unknown，旧events-disabled路径保持；这是自有Standard异常边界，不涉及WT。

## 实施与验证入口

产品作者在独占候选实现Standard事件Query、收据保存、B三阶段、签名及停止收口；独立测试作者实现正常候选DLL、真实Host/SHM及原版Adapter公开主链。根已接新探针构建入口（外部历史/待归仓路径：`../../tests/integration/qmt_standard_trader/CMakeLists.txt`）的NqpStandardEventQueryProbe，构建source快照沿原build.py目录规则。初始接线时探针候选尚未进入正式快照；后继实际编译与运行结果见下方续记，原接线身份见接线收据（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/BUILD-WIRING.json`）。

完整费用按一份实例总账分列HTTP128槽（包含active）、单worker/owner峰值、真实排队/已完成票据和单事件链；G1已封来源字段和真实sizeof，G3写/UC/event同步峰值及新字段sizeof、64/256/512MiB账单仍待闭合。状态代码与费用实现同步推进，不能以512MiB测试配置或单B cap通过代替整个C容量证明。

## 验收与剩余范围

后续按实际冻结case名单分别登记编译、主链、Failure/stop/D/资源/容量及独审；C01–C16是要求维度，不能作为已执行数量。旧B的single10263及persistent24代表点继续保[原资格](2026-10-25-qmt-profile-resource-channel.md)，不能授新Standard运行。

真实SDK调用0、终端/生产Factory保持；无新增WT框架修改。R8首次/重连的真实查询覆盖交接、未知撤单旧失败首因、完整历史/保留业务/连续运行及独立发行仍属完整目标。C补查单行成功不构成共同cut或完整迁移完成。

## 公开探针编译与候选首轮审查

公开测试的三个正式源文件已集成，独立静审覆盖S01–S12及28份固定输入，P1/P2为0，根逐原件/当前源哈希复核一致，见根复核收据（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/TEST-REVIEW-ROOT-VERIFIED.json`）。正常公开探针在固定原上游323文件与自有165文件下实际161步编译通过，75.437秒；控制进程退出0，创建期Job、tree0、双EOF、reader join、资源关闭完整，见编译收据（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/PUBLIC-PROBE-COMPILE-VERIFIED.json`）。此构建使用旧Standard输入，只授新探针编译。169项Python运行树及runner002已冻结，独立审查确认原D、前后输入核验、首异常保留与selected/full12范围分离；执行数仍为0。

产品001仅在独占候选包冻结，正式Standard未替换。首次12目标构建在StandardEventBudget.h的119/121行触发MSVC C2398：运行时int条件值进入size_t列表时窄化，见原失败收据（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/PRODUCT-001-COMPILE-FAILURE.json`）。73.218秒控制结束，实际失败、无强杀、tree0/EOF/join/关闭完整；该次不授产品编译通过。

两路独立源码审查继续：已发现配置文字先复制后核长，以及已知operation Failure在reason复制OOM后被IoError覆盖两项P2。修正在新revision进行，001原件保留。配置采用WT公开asCString有界前缀合同，见唯一规格；不新增WT框架接口。最终修正需独审、新编译、真实合成Host/SHM/Adapter主链和容量账单通过后才可报告对应范围完成。

## 2026-10-26 续记：产品003与首场景

产品revision002实际12目标/224步编译通过（142.047秒），但独审仍确认初始化银行未在正文复制前取得。revision003把原数值总额读取及初始化费用取得移至首配置/env正文复制之前，完整static只补差额；原Status诊断复制资源异常进入独立delivery IoError，原Failure/正常Pending、原完整来源及late分别保留。两路独立delta P1/P2为0，根逐核各4份raw及当前固定来源，见复核（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/PRODUCT-003-REVIEWS-ROOT-VERIFIED.json`）。003实际12目标/224步编译通过（131.812秒），真实Job/tree0/EOF/join/资源关闭完整，见003编译（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/PRODUCT-003-COMPILE-VERIFIED.json`）。此为候选资格，正式Standard尚未替换。

首个实际S01单例执行在0.017秒报错：测试夹具将合法SHM名称覆盖为C-shm前缀，违反既有qmt-broker私有名称合同，在Host构造前拒绝；尚未启动native探针，见原失败（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/PUBLIC-S01-001-FAILURE.json`）。该次控制进程5.031秒失败退出，创建期Job及全部回收证据完整。作者仅将夹具名称改为qmt-broker-C-加UUID，协议/产品/金融断言保持。后继runtime002仍为169项，仅夹具变化；runner003仅替换固定输入清单hash，见冻结计划（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/RUNTIME-PLAN-002.json`）。原runtime001及失败记录保留，等待非作者delta后优先S01复验。

纯状态/预算测试定义31例，涵盖真实首因转交、诊断复制精确/持续OOM、原Pending与跨D、真实fence/receive、配置先限长/先计费、失败初始化持有及实际布局与费用下界。首个专用编译暴露测试中三处bool成员被当函数及main缺收束，测试revision003修正并补四个布局叶，原31断言保持；产品003不变。该专用测试尚未取得执行资格。64MiB在当前向量确定不足；256/512及整体实例所有resident组合仍须完整账单，单条链必要下界和较大总额均不能授完整容量结论。

## 2026-10-26 续记：纯31例通过与原生订单口径

纯探针修订003先因MSVC输出对象完整路径262字节失败；保持相同源码、编译选项和链接闭包，改用较短隔离目录及目标名后构建通过（69.875秒）。真实专用EXE执行31个唯一场景、277条断言通过（0.313秒），控制进程退出0，无强杀，创建期Job/tree0/双EOF/reader join/资源关闭完整；根后核167自有及323原上游快照，见纯回归收据（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/STATE-PROBE-003-RUN-ROOT-VERIFIED.json`）。

目标实测sizeof为Impl1744、Task608、Completion1888、EventChain1360、QueryEvidence656、Identity条目160、Pending条目512、Candidate条目32、Status40字节；owner_callback1005为包含固定控制及有限文本的**逻辑费用项**，不作为单对象sizeof。给定H262144/queue16/pending16/rows4096/I4MiB向量，静态逻辑费用81717515字节，当前单链before-B必要下界105114215字节；64MiB不足，256/512MiB仅通过该必要条件，其他resident查询/写/UC组合及完整边界资格仍待验。它们均不表示allocator余量或进程RSS。

修正命名后的S01通过实际合成Host、Windows SHM及原Adapter：持仓120、可卖100、未完成80，183份嵌套原文事实SHA/长度逐项复核，原生/Host/source/proxy及控制进程回收完整，见S01收据（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/PUBLIC-S01-002-ROOT-VERIFIED.json`）。随后首次全12选择在S02的测试oracle失败并按failfast停止，S03–S12未执行，见原失败（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/PUBLIC-ALL12-001-FAILURE.json`）。

独立原上游源码复核确认：普通部分成交订单回报保存订单剩余80并通知sink，getUndoneQty由真实成交或撤单分支扣减；只有订单回报的S02仍为100，测试期待80有误。测试003仅令真实deal的S01/S03/S12期待80，其余成功场景期待100，保订单100/20/80、身份、金融ABI及sink left80断言；无新增成交、WT或产品修改。公开新探针实际编译通过（61.5秒），两组非作者delta及169源运行树/两pin运行器更新均通过，根逐核7+5份审查原件与169冻结源。新制品与runtime003的完整12例重验正在进行，不能沿旧失败批次授全12资格。长期原生行为见[WT能力说明](../modules/wondertrader-trading-capabilities.md)。

## 2026-10-26 最新续记：最终公开十二例与独立动态复核

最终测试005以同一产品003普通DLL运行完整S01–S12，12/12通过、0失败/错误/跳过；unittest 36.145秒，控制器37.875秒。原生子进程、Host、source、proxy均按原截止关闭，实际创建期Job、tree0、双EOF、reader join及句柄关闭齐备。根逐项核对2148份嵌套原文事实的Base64、字节长度和SHA，以及169项冻结源、EXE与DLL前后身份，见完整运行收据（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/PUBLIC-ALL12-003-ROOT-VERIFIED.json`）。

非作者独立复核381份原件，189项原件检查通过，本批P1/P2为0；根再次逐核381份原件与当前来源，见独立报告（外部历史/待归仓路径：`../../build/qmt-event-query-standard-tests-independent-001/public-canonical12-005-dynamic-001/REVIEW.md`）及根复核（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/PUBLIC-CANONICAL12-INDEPENDENT-ROOT-VERIFIED.json`）。S07保真实queued/executing/terminal；S08真实截断原POST回复后只GET原UUID；S09保原IoError而不被通用停止/超时覆盖；S10普通账户查询在事件lookup前终结且最终accounts=2；S11查询Remark缺失、OrderRef变化时仅一次外部SPI；S12回调release延后实际销毁，借用对象仍可读，最终完整回收。FIFO约束按worker各次任务提交顺序核验，普通查询后续resolve仍为独立任务。

此前S08父测试错误读取GET中不存在的request_id，以及S10在事件订单SPI时提前要求账户SPI数量为2，均为测试层错误，原失败批次保留。最终测试按真实POST/原UUID GET关联及各任务FIFO、最终账户回调数量核验，产品003及WT保持。原生订单累计成交字段不替代真实成交回报，长期说明见[WT交易能力](../modules/wondertrader-trading-capabilities.md)。

同产品003的NqpUnknownCancelStateProbe另行受控执行，49个唯一场景、2126条断言通过，0.312秒，无HTTP/SDK。场景记录1929条，记录后的49次关闭共196条及真实未用客户端drain一条构成全局2126；原need/need-1、Started、U事实与分配异常断言保持，见收据（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/UC-STATE-C003-ROOT-VERIFIED.json`）。

后继先复验原events-disabled普通12、SHM3、未知撤单4方法，保持原64MiB/2MiB夹具及截止；通过后仅集成自有TraderQMT源。完整实例同步峰值容量、全部C故障义务、首次/重连query-live交接仍独立待验。真实SDK调用0，终端、26个保护框架文件及生产Factory保持，完整迁移目标active。

## 2026-10-26 正式集成与正式制品重验

原events-disabled兼容按普通12、共享内存3、未知撤单4三个独立原截止执行，19方法/20原生场景全部通过，无跳过。控制器分别7.813、8.593、23.781秒，真实Job/EOF/join/业务资源关闭完整。根复核每个fixture和native结果、原169源及四制品前后摘要，见兼容收据（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/COMPAT-C003-DISABLED19-ROOT-VERIFIED.json`）。原64MiB普通夹具与2MiB UC容量夹具保持。未知撤单旧偶发失败仅在本次未复现，原失败首因仍未关闭。运行器非作者静审P1/P2为0，见报告（外部历史/待归仓路径：`../../build/qmt-standard-events-disabled-runner-independent-001/REPORT.md`）；实际批次的独立动态复核另行登记。

仅向自有TraderQMT集成产品003的StandardQmtTrader.cpp及StandardEventBudget.h，保留正式原源备份；31例探针按原字节进入event_budget_state_probe.cpp，CMake新增短目标NqpCState，build.py仅增加该产物登记，README说明独立EXE与短路径约束。接线非作者静审（外部历史/待归仓路径：`../../build/qmt-event-query-standard-tests-independent-001/state-build-wiring-001/FINAL-REVIEW.md`）通过；集成收据（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/FORMAL-PRODUCT-AND-STATE-WIRING-INTEGRATED.json`）核26保护框架未变、无工厂切换。长期职责见[插件模块](../modules/wondertrader-plugins.md)。

正式build.py以固定原版上游与当前自有源，在短目录cst-0001实际编译NqpStandardTrader与NqpCState通过（76.188秒）。实际选择对象29个，最大绝对路径216字符；纯目标14对象最大208，均低于240操作界限，未选择目标的生成路径不授本次编译资格。166自有与323原上游原件逐项核验；与原产品003编译相比，src产品字节全部一致，差异仅本次测试接线/探针与此前已验公开测试。见正式构建（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/FORMAL-BUILD-001-ROOT-VERIFIED.json`）及路径核验（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/FORMAL-BUILD-PATHS-001.json`）。

正式新DLL摘要61c9f81e2094dedae1c05bddbf364af1888f3a424faa779985afefb21f4d1980。沿同一已审169源运行树和公开探针，重新执行完整S01–S12，12/12通过（控制器37.453秒）；根核2172嵌套原文事实、完整Job/源/Host/proxy及native关闭、同一原D与制品，见正式整链收据（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/FORMAL-PUBLIC12-001-ROOT-VERIFIED.json`）。正式新NqpCState也实际31例277断言通过，见常驻回归收据（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/FORMAL-STATE31-001-ROOT-VERIFIED.json`）。新二进制与原候选制品各自登记，不混用资格。

完整C容量与故障义务继续；R8来源增量已把实际历史终端家族、后台缓存限制及只读后继收敛到来源研究（外部历史/待归仓路径：`../../build/qmt-query-live-r8-source-followup-003/DELTA.md`），尚无跨P/O/D查询和回报的联合覆盖证明。当前不新增WT框架修改，不据本地时间或seq伪造共同水位。全历史、保留策略/业务、连续运行与独立发行仍为active目标。

## 本轮独立验收收尾

原19方法/20场景及私有49例的独立动态复核（外部历史/待归仓路径：`../../build/qmt-standard-events-disabled-dynamic-independent-001/REPORT.md`）通过，根逐核325原件及当前来源；旧UC首因仍保留unknown，本轮只记未复现。正式两目标构建、新DLL十二例与常驻纯31例的独立delta复核（外部历史/待归仓路径：`../../build/qmt-event-query-standard-tests-independent-001/formal-rebuild-delta-001/REVIEW.md`）通过，本批P1/P2为0，根逐核879原件与当前来源，见根收据（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/FORMAL-FINAL-INDEPENDENT-ROOT-VERIFIED.json`）。原full审查与失败批次保留，不扩展资格。

本轮project.py check通过，范围为文档导航与skill清单完整性；应用编译/运行由上述独立证据授予。26保护框架与六项正式集成源摘要终核一致，真实SDK0，生产入口未切换，见收尾检查（外部历史/待归仓路径：`../../build/qmt-event-query-c-implementation-001/FORMAL-FINAL-CHECK-001.json`）。下一片先补queue16/queue1的64MiB真实初始化拒绝及完整resident费用边界，再推进启动/重连交接；整体目标保持active。

## 2026-10-26 容量后继：真实初始化负向两例

仅修改自有测试event_budget_state_probe.cpp，在原31例之外增加queue16/queue1两项完整合法配置的真实init负向；产品StandardQmtTrader.cpp、StandardEventBudget.h及WT保持。两案均使用64MiB原额度，完整解析账户、绑定、HTTP、身份与事件配置后，核Backpressure发生在结果ring和worker创建之前；核初始化费用持有、有限关闭截止及幂等release，不伪造HTTP调用计数。原31函数与断言保持，见测试集成（外部历史/待归仓路径：`../../build/qmt-event-query-c-capacity-implementation-001/TEST-INTEGRATION.json`）。

独立delta源审（外部历史/待归仓路径：`../../build/qmt-event-query-standard-tests-independent-001/capacity-two-init-delta-001/REVIEW.md`）P1/P2为0，根核13份raw和对应当前输入。正式build.py在短工作根cst-0002仅选NqpCState，实际14TU、最长对象路径208字符，66.922秒编译通过；166自有与323原上游冻结源逐份核SHA。实际新EXE摘要843abb68b569bb165a2b0f1cabcee412b83318bc442bd54378ad0905b6b2f3fc，见编译收据（外部历史/待归仓路径：`../../build/qmt-event-query-c-capacity-implementation-001/BUILD-ROOT-VERIFIED.json`）。

实际33例、378断言通过（0.328秒），旧31输出前缀逐字不变。q16/q1完整static逻辑费用分别81711000/81673079字节，均高于67108864；其中两HTTP owner共128槽（含active）费用42487744，与queue名额无关。拒绝时各持有初始化费用13152，真实release后payload=0、joined/drained/Closed且可删除，无worker/任务/ring创建。两控制器均exit0、无强杀、创建期Job/tree0/双EOF/reader join及资源关闭完整，见运行收据（外部历史/待归仓路径：`../../build/qmt-event-query-c-capacity-implementation-001/RUN-ROOT-VERIFIED.json`）。这些是逻辑额度与实际owner状态，不能作为进程RSS或256/512MiB全容量证明。

下一片的六个混合resident输入仍为计划，需把普通Query完成值尚活时的Candidate/Resolve第二份512控制费用计入；原full-bank名称不能直接充当真实过渡账单。额外嵌套字段的DOM费用疑点分别按当前Agent固定标量来源与C++公共输入域核验，目前没有真实主链超额反例，未定为产品P2、未修改产品。来源域与完整总账未闭合前继续保留unknown，避免以单子项推断整链。

两项真实初始化负向的最小动态delta独审（外部历史/待归仓路径：`../../build/qmt-event-query-standard-tests-independent-001/capacity-two-init-dynamic-001/REVIEW.md`）通过，P1/P2为0；独立核33/378、旧31前2684字节含原CRLF逐字相同、实际cfg211/210字节及fixed/HTTP/合计费用、原D与Job资源收口。根逐核25份最小原件和对应来源，见根复核（外部历史/待归仓路径：`../../build/qmt-event-query-c-capacity-implementation-001/INDEPENDENT-DYNAMIC-ROOT-VERIFIED.json`）。旧全审按匹配输入复用，本轮未复制或重跑旧全矩阵；真实SDK0、无产品及框架修改、无生产切换。
