# 模块B：账户交易与策略原生运行交付

最终简版后继已通过[匹配安装与两项独立审查](../evidence/2026-11-01-simple-order-recovery.md#审查修正后的最终主链)：sf/sr2修正原截止晚返回及资金查询应用身份两项P2，实际helper四项原红新绿；正式006两代Native21240/33104各正常退出0，外46472退出0/41秒/全回收。两轴开放P1/P2均为0，最终17份源码/规格/测试/文档、25 Native组件及原23wheel沿`build/ms-simple-recovery-delivery-001/INTERFACE-001.json`交Root接收，原005检查点不改写。此后继可纳入统一候选，main003原关闭失败原因仍unknown，脏金融自动接续/跨版本重放及完整B资格继续按实际缺口登记，goal保持active。

2026-11-01简版恢复主链已形成[固定通过检查点](../evidence/2026-11-01-simple-order-recovery.md)：普通离线WT角色中的正式1.1.2卖200、成40并撤清余160；第二代保留原策略记忆，按券商当前160股重算并只提交160，再正常撤清。人工单保持，O终态→后继P/A、原clean消费及两代正常关闭均通过。外39780退出0/47.411秒/全回收，Native22844及62556退出0，QA仅查明确PID句柄、无调试器。检查点`build/ms-simple-recovery-checkpoint-001/INTERFACE-001.json`绑定12源/规格、121 Native输入、25组件及23wheel；产品源码仍在隔离候选，Root可按固定输入接收主链，delta独审及最终组合继续。main003缺正常关闭证明的同次原因保持unknown，后继通过不追认其修复；整个B保持active。

本期恢复目标已按用户要求收敛为[NRT-R33简版](../specs/native-realtime-strategy.md#nrt-r33-自有委托撤单收束与重新计算简版)：撤清能由原Host/委托表明确归属本通道的活动单，确认终态并重查券商资金、持仓和可卖，再保留WT必要策略记忆并重新计算。人工/其他系统订单保持；未知原ID保留核查；is_cancel_unmanaged_order为false。正常停止在保存前完成相同收束。本期退出尚未交付的挂单接管、旧拆单阶段接续和跨版本/全部金融KV重放，不扩展假想边界。

已验33文件未知连续性保持主干67ebb99及Root既有接收资格；当前仅用一个新的正式1.1.2 SDK独占场景验简版，之后按实际差异审查和统一交付。必要策略记忆确实无法沿现有状态恢复时，向Root提交具体最小缺口，不另建恢复体系。以下记录保留各自历史范围，旧完整恢复提案不继续作为本期实现要求。

有限恢复主链已完成[当前安装的两代查询与定向撤单](../evidence/2026-10-31-host-idle-functional-observation.md#原身份冷重开查询与定向撤单)：未知未成交、未知已成40/剩60和正常受理活动单三例，先后独立Host/Source进程使用同一Journal，安装G3 Standard从真实ORDER取回原身份并撤单一次，后继终态O→P保持0/40/0持仓，新增insert均0。最终matrix003同三案六阶段/三原生实例全部正常关闭及物理回收，外69664 exit0/97.206秒；两项独立delta审查绑定121/117项，QA原D检查P2已修复，开放P1/P2均0。最终精确交接（外部历史/待归仓路径：`../../build/ms-finite-recovery-closeout-002/HANDOFF-001.json`）记录源、安装、制品与已完成/缺项/阻断。未知原调用/body/result与禁新单围栏保持；新生产源/数据库结构/准入门/WT行为均0，原011正常恢复已经完成。先前QA文件名冲突和一次运输超时失败原件保留。该限定支持Standard查询/撤单恢复，正式CTA活动单自动续接和unknown解除后自动重开交易仍缺实现，UDR保持提案；完整B保持active，最终系统由Root据固定输入接收。

首次启用继续采用用户确认的[当前库存新基准](retained-strategy-takeover-proposal.md)：保留当前数量、可卖与资金，不导入旧开仓历史或交易流水；新交易、费用和绩效从启用时开始。以后重启接续本系统自己的记录。旧开仓历史补齐工作已经取消，当前恢复验证使用的53笔均为本系统SDK替身运行产生的记录。

永久源码干净重建已通过[NRT-R7-C1–C4](../runbooks/standard-execution-build.md)：clean009在全新目录完成五执行组件及依赖的编译、真实链接来源核验、25文件安装和源码/依赖复核，旧项目对象与库输入0。外25464 exit0、445.007秒、完整回收；两轴最终审查开放P1/P2均0。源与实际输入沿[最终构建后继](../evidence/2026-10-31-host-idle-functional-observation.md#永久构建与原目录恢复的最终结果)，Root已用该候选及39份WT Python源组合integrated.2，新版本SDK业务由Root独立验收。原金融目录恢复沿其原安装身份，两者分别授信。WT工作树及历史失败原件保持。

来源会话容量的[显式扩展方案](trade-event-storage-expansion-proposal.md)已实施并通过源码与关闭独立审查。原SDK Journal已沿公开维护入口将max_streams从2增到16，只有一条容量身份记录变化，原53命令、106事件和全部其他行保持；首次库存与原生金融文件未重建。Root已从永久Host源码完成0.1.0a22+mdphttp.3.tes.1的普通安装候选及源码集成，同版三wheel逐字相同。该容量仅用于本次明确SDK候选，正式环境预算沿其配置另定。

原金融目录的[resume011完整恢复已通过](../evidence/2026-10-31-host-idle-functional-observation.md#永久构建与原目录恢复的最终结果)：正式1.1.2重新计算，序号21接续20，执行输入与当次券商SDK持仓50400逐证券一致，原53委托/53成交及资金模型保持，新增SDK0；Root74988九组件正常关闭，Native63680生成真实新clean，旧60400精确消费。外42800 exit0、83.708秒、完整回收，全部不可变输入一致。600秒新鲜度及60/90秒原验证预算保持，首次启用和53笔未重跑。当前无B业务运行，最新63680证明沿后继实际消费更新。010误用兼容资格字段的QA失败、009具体HTTP失败请求缺证及010采集关闭故障均保留各自范围。未知正向Native、活动单冷恢复、自然跨夜、报告HTTP和新版本整套资格继续分别登记，整个B保持active；真实交易及生产均0。下方旧进度按各自时点保留。

当前完整恢复：[full046](../evidence/2026-10-31-host-idle-functional-observation.md#full046恢复入口与qa凭据字段修正)完成三轮/53成交/50400、App停止后WT继续发布、首代正常关闭及第二WT入口ready；原生恢复后计算尚未进入。中断已定位为QA混用closed与ready的组件字段，真实凭据红绿及独立delta通过，44554项冷封存保留失败原件。047仅改单个字段来源，当前沿同版实际主链继续。产品、WT及真实金融写改动均0，完整B保持active。

最新完整组合：[full042](../evidence/2026-10-31-host-idle-functional-observation.md#full042三轮与九组件正常关闭)已完成正式1.1.2三轮converged、53笔SDK替身全成/50400及九个WT组件正常关闭，Native66776恢复证明有效，26944业务输入前后完全一致、43961项冷封存。随后报告HTTP断言失败，准确位置与原因仍unknown，App停止后发布与同根恢复未进入；整体保持false。后继046保留五项HTTP断言及全部原D，先验原同根恢复再核报告，当前运行中。未知恢复[设计两项P2已在要求层关闭](../evidence/2026-10-31-host-idle-functional-observation.md#未知恢复设计独审与后继修订)，具体实施合同和正向Native实例继续gap，产品实现尚未开始。完整B active。

当前组合准备：[Root关闭修复接收](../evidence/2026-10-31-host-idle-functional-observation.md#root关闭修复接收与完整组合准备)已核WT integrated.1/AWP closestop.2的精确普通安装和执行逻辑保持，B以P30 Native组合验证完整三轮及同根恢复。Root main005的自有退休超时按实际原件保留，完整B继续active。另已实跑[未知调用正向券商证明反馈](../evidence/2026-10-31-host-idle-functional-observation.md#未知调用取得正向券商证明的实际反馈)：SDK1/POST1/查询8，原unknown及防重复保持；1423项冷核封存。[恢复方案](unknown-broker-evidence-recovery-proposal.md)为proposed，实施与准入变化均为0。

最新P30：[自有停止结果分类](../evidence/2026-10-31-host-idle-functional-observation.md#p30-停止事件读取的分类根因与普通候选)已确定复现原实现把正常停止记为错误的问题，候选以唯一规则统一普通及最终退休。普通及搬迁完整11矩阵、两端各两代恢复和7项拒绝均通过；108绑定源码/执行独审和112绑定搬迁delta独审均无新增P1/P2。后继组装入口（外部历史/待归仓路径：`../../build/ms-final-p30-root-handoff-002/HANDOFF-001.json`）已封，23个WT wheel、65成员包及26个Native保持同版。同账户Root实例实际退出后才启动搬迁矩阵，未修改账户键；普通121/搬迁124查询，SDK各18insert/3cancel尝试。新增WT行为0，共享live源码和P29原件保持。三轮正式算法/50400及Root负责的整套停止恢复继续沿下段；未知恢复职责接口（外部历史/待归仓路径：`../../build/ms-unknown-recovery-owner-interface-001/INTERFACE-001.json`）已定位跨owner缺口，完整B保持active。首次库存按当前券商事实建立新基准，新记录从启用开始，重启接续。

当前主线：[完整三轮与原生关闭](../evidence/2026-10-31-host-idle-functional-observation.md#完整三轮通过原生正常关闭与系统停止缺口)已在full034完成同CTA三轮、账户投影/HTTP、App停止后WT继续发布，53笔SDK替身全部成交、实际/目标50400。执行进程closed.v2正常且原clean证明存在；系统关闭先报component_close_analysis_window，采集随后stop_timeout，恢复尚未开始。[最终正式矩阵、恢复和独立候选](../evidence/2026-10-31-host-idle-functional-observation.md#最终正式矩阵恢复和独立候选)已取得11入口、普通安装两代恢复及7项拒绝的实际证据和独立审查；61成员候选ZIP已在新目录离线安装23个发行包。搬迁恢复001的第二代关闭失败仍保留，12轮诊断未复现，原候选002两代及7拒绝也实际通过；具体失败检查和根因继续unknown，整体安装恢复资格仍待。冷unknown只读重开已独审，原未知责任和新单禁入保持。完整B保持active。首次以当前库存起步，旧开仓历史及交易流水不迁入；启用后记录从零累计，后续重启接续本系统记录。下方在途描述均为其各自历史时点。

最新[Host空闲候选与完整功能观察](../evidence/2026-10-31-host-idle-functional-observation.md)：普通019已经终态，41SDK/39100对50400，70秒失败且正常关闭/全回收。007隔离候选通过28案、正式A003原版/候选44交易向量和默认read/bulk三链；普通full022仍35SDK/33100对50400，正常关闭/全回收，未取得完整性能收益。后继优先完整功能，按NRT-R31-C5另设QA每轮240秒/主1200/外1500，正式A003原Host/Source不带007，保留所有产品请求/关闭D和原70秒失败。首版full024遗漏独立QA actual_deadline70，原件/正常关闭和25绑定冷核已保留；同步该QA赋值后的025已取得首轮53SDK/50400逐证券实际到位、converged和53映射，QA冻结首次发布SHA而误拒绝后继状态，原件/正常关闭和25绑定冷核已保留。只修QA精确发布收据匹配后，当前full026/job027 exec83939为唯一业务句柄，完整三轮/资金/同根恢复及原件收口继续；当前库存新起点、旧历史不迁、首次之后重启接续保持。WT新增行为、真实交易和生产0，完整B active。

当前普通full019已终态，41SDK全成、39100/50400份、差11300，原70秒仍失败；Source/Native正常、输入一致、全回收。冷核（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/FULL019-COLD-001.json`）固定25绑定。A已接入前次限定Source交接并开始正式普通发行整合；B继续自有Host责任层，按[空闲读领取候选](host-idle-read-claim-proposal.md)只在peer无任何保留通信时推进原claim，等待中继续原准入/确认并沿同一D。候选仅build隔离，独立审查及完整主链后交A；WT/共享live/真实交易保持，完整B active。

当前[普通无诊断完整后继full019](../evidence/2026-10-31-sri006-execution-failure.md#普通无诊断source候选完整后继)已启动：最终A installation003、P29普通DLL9b43b80…，仅Source三份已审方法选择，Host原实现；原100ms/SDK工作量/65秒晚到/70目标/main400s保持。该轮直接验证普通候选，终态待取。此前限定HANDOFF（外部历史/待归仓路径：`../../build/ms-control-roundtrip-handoff-001/HANDOFF-001.json`）封存290引用/0漂移及文档检查，来源相位改动已验，Host006收益和完整B资格仍未证；full019为该封存时点之后的新增业务作业。

最新[full018终态与交接](../evidence/2026-10-31-sri006-execution-failure.md#full018终态及交接选择)：41SDK后原70秒目标仍失败，101/102请求完整关联，Source同轮reply中位0ms；Host受理后claim等待52.207ms、claim后派发58.537ms，完整worker502.413ms。Native/Source正常关闭、输入一致和全物理回收。129绑定独审确认006的44/44交易矩阵，性能收益与完整资格继续未证；本轮推荐共享owner接入已验Source两成员，Host006保留验证材料、005已退出，live三源与现有包保持。下一动作沿原请求身份核通信调度与查询/写往返，消费A最终固定配套后完成原70秒/三轮/恢复；没有用户当前必需操作，整个B active。

本轮HANDOFF（外部历史/待归仓路径：`../../build/ms-control-roundtrip-handoff-001/HANDOFF-001.json`）及Source owner接口（外部历史/待归仓路径：`../../build/ms-control-roundtrip-handoff-001/INTERFACE-001.json`）固定源码/逐文件diff、全部本轮审查与冻结文档。018/worker冷核52绑定独审完成；交接明确Source限定可复用、Host非推荐和完整70秒仍失败，最终统一候选资格false。

最新[非等待准入后继](../evidence/2026-10-31-sri006-execution-failure.md#延长等待退出与ack完整发送后的非等待准入)：stage005全局等待会阻塞已就绪交易/ACK的原D，78绑定独审判P2并退出；其full017为38SDK/70秒红，正常关闭/全回收。stage006从原Host唯一增加完整send/peer.sent后的stop检查和原_admit，使可领取后继与原receive重叠；Source同轮回包保持。实际Host/ControlPeer九案及91绑定独审通过，原44项HostTrading/SQLite/SourceTradingService向量基线/候选各全通过；旧测试fixture仅在QA对齐默认continuity合同，001/002失败均保留。完整full018已启动，原工作量/100ms/65晚到/70目标及D保持；共享live三源SHA不变，A接受/普通发行/完整三轮恢复和B资格继续待验。

[精确请求与同轮回包基线](../evidence/2026-10-31-sri006-execution-failure.md#精确请求关联与来源同轮回包)：最终A durableio.2/installation003实际full013完成98个UUID直接关联，来源执行后等回包中位109.392ms；Source-only full014把该段降到0ms，但原70秒仍红、SDK38。Host阶段004 full016为41SDK/70秒红，已正常关闭、输入一致和全回收；实际claim中位41.163ms，原poll5ms候选不足以省轮次。来源实际peer四案最终红绿及58绑定独审已封；默认线程、持久确认/ACK、原future退休和WT保持。阶段005延长等待已由上段非等待后继取代，当前完整B/根集成false。

当前[完整执行耗时后继](../evidence/2026-10-31-sri006-execution-failure.md#full009来源计时最终a材料选择及限定交接)：P29无诊断完整Source full006及来源计时full009均为37SDK全成、实际35100/目标50400、仍差15300，原70秒失败；Native/Source正常关闭、输入一致和完整物理回收。full007的35SDK时序已完成151绑定独审，Query worker中位663毫秒、owner取出约7毫秒，UUID链与具体等待机制仍待核。full009来源全程单tick最大234毫秒，分方法记录到上限后截断，前段25个SDK尾部样本不作为全部129查询结论。最终A durableio.2/installation003的四父端配置预检及全部准备回收通过，Source/SDK尚未启动；1625摘要的限定交接（外部历史/待归仓路径：`../../build/ms-p29-execution-handoff-001/HANDOFF-001.json`）及共享owner测量接口已封，下一步沿最终配套定位原UUID的通信推进等待，再验完整目标。WT与live产品保持，完整B/根集成false。

P29[真实准入函数回归](../evidence/2026-10-31-sri006-execution-failure.md#p29真实准入函数的状态回归)已取得P28旧共享断言红例及新候选17案121断言通过，核原身份/D、独立查询、严格barrier、原银行转移/归还和停止；697绑定证明及706绑定独审已封，新增开放P1/P2为0。实际worker竞争、负载并发与异常银行、完整原70秒/三轮及最终发行恢复仍gap；538/547绑定历史独审继续适用其39单有限观察，当前完整模块和统一候选资格false。

最新[受管次会话日历模型](../evidence/2026-10-31-initial-inventory-evolution.md#受管次会话日历模型后继)已沿实际WRI/工厂/原ticker完成两代：原生可卖100→200，券商仍100时等待/SDK0，原来源补查确认200后卖200；SDK1/映射1/Host事件2、费用4、两代正常关闭和完整物理回收通过。独审1010绑定、新增开放P1/P2为0；旧QA摘要误标已以来源成交修正，原结果保留。日历为显式QA模型，自然跨夜及自动新分析仍gap。根Host持久I/O候选full003保留原70秒失败、20笔SDK全成/最终映射15、目标50400/实际19000；B当前优先冷核查询/事件/组退休与后续分单推进，保持原工作量和原截止，完整模块资格false。

最新[两处prePOST窗口](../evidence/2026-10-31-unknown-write-stop.md#两个prepost恢复停止窗口)沿原P28检查及Native006配套完成公开query_first关闭提交：两处均POST0/明确拒绝1/pending0，相同gate继续放行的对照各POST1/接受1。最终build005/run007四案正常关闭及物理回收通过；796输入证明与803绑定独审已封，开放P1/P2为0，QA析构与链接身份缺口已修正，普通发行DLL保持。限定窗口已完成，后继回到完整三轮、正式次会话及自动首分析主线；共享持久记录链性能修复由A接手，B消费其精确配套后复验原70秒，不新增外围bad-case。

最新验证交接（外部历史/待归仓路径：`../../build/ms-b-io-net-fee-delivery-001/HANDOFF-001.json`） SHA `88ae353be2ff8c48e66d221efec0306897a17a0955a0f59de82e3102e97b2d5c`已封存15份原件及651项摘要引用的复核。历史容量审查的225项中，223项当前匹配；另两项为持续追加的证据文档及A新增显式批量读取入口的公共源码，原安装源码仍精确匹配历史审查。本交接保留该版本边界，未将新Source入口纳入旧资格。I/O独审114绑定、费用独审56绑定及任务独审26绑定全部匹配。完整三轮、跨日与异常恢复矩阵继续待验，根集成资格和整个B资格保持false。

最新[SDK净费用后继](../evidence/2026-10-31-flat-theory-availability.md#独立sdk净费用与资金观察后继)沿原P28搬迁包完成卖200买200：源端独立扣4+2，账户100000→99994/available79994，原WT配置预算120000→NAV119994/cash99994/PnL-6，两种口径本期变化均-6且保留预算差额。等原账户查询更新后正常同根两代、SDK2/映射2/事件4及零恢复重复，外Job12292 exit0/51.895全回收。产品/WT变化0；费用独立审查已完成，真实券商费与完整B继续待验。

最新[HTTP/SQL同次测量](../evidence/2026-10-31-sri006-execution-failure.md#http与原sqlite提交的同次区间)已把部分Query成本定位到原持久提交：009的deal查询受理/终态GET/消费HTTP为221/245/167ms，内含或重叠COMMIT203.443/237.155/142.326ms。原SQL/同步/事务及65秒晚到保持，SDK下撤单0；两有限启动案Native正常closed.v2、外层及所有子进程完整回收，分别148 HTTP与7482 SQL记录均未溢出。完整三轮性能修复仍待，已通过owner接口（外部历史/待归仓路径：`../../build/ms-sri006-io-owner-interface-001/INTERFACE-001.json`）交A的共享读持久层，B保留P28配套并负责原完整主链复验；原WT和持久确认规则保持。费用净额模型已完成上述独立QA与审查，完整B active。

最新[有效任务测量](../evidence/2026-10-31-sri006-execution-failure.md#有效任务测量与下一层范围)已在同包004封存460任务/零overflow和完整物理回收，业务首轮继续失败。12笔SDK对应48次成功Query；Query worker中位1342毫秒、queue中位7315毫秒、owner取出中位9毫秒。原worker定义的80.084秒样本中Query占61.607秒；该范围与外部70秒分别标识。停止后的Insert Unavailable/Query Pending及owner block的TLS默认0分别保留，当前未证明更早任务错误或具体运输子阶段根因。下一有限诊断保留原3.6来源/65秒晚到及启动四查询，拆分create_request/submit_once后停止；产品、WT及真实调用0，完整B active。

当前[容量层修正后的完整主链](../evidence/2026-10-31-sri006-execution-failure.md#分段实证第12次提交未受理与短样例容量)已用原Native越过11笔，但SDK13/Native映射10/seq8仍未满足原首轮70秒，完整三轮与恢复未授资格。所有13个Host命令SDK返回，停止时仅有recovery_drain/plugin1（write_admission_closed），没有正常期先退出的直接证据；自有任务分段诊断继续核具体吞吐/停滞。容量证明38绑定及64读记录/13975552读字节/196608回包/5506131交易字节和预留公式已封；原SQLite gap字节经JSON解码均为null，旧bool误判已另封更正，原件保持。真实调用及WT新增0，完整B active。

最新[SRI006容量根因](../evidence/2026-10-31-sri006-execution-failure.md#分段实证第12次提交未受理与短样例容量)已由同包分段计时和真实Journal最小红绿确认：前11笔均已查询到SDK返回，第12次本地尝试POST503、同ID GET404直到原D；原200000字节额度已用197732/剩2268，下一条最少17409，尚未达到16条数上限就已字节满。仅调整有限字节额度的最小绿例可受理原16条，零SDK/运输。当前按完整三轮资源合同一次配齐命令/事件/账户回包/Journal预留，用原版Native跑完整主链；原65/120/70/600等边界保持，未为容量问题开发新Native/WT行为，有限三轮与长期资格分别登记。

最新[SRI006同包诊断复现](../evidence/2026-10-31-sri006-execution-failure.md#同包实际复现与首次写保护)已在新独占根重现SDK11/数量10000/seq8/Native成交7，并直接捕获自有Standard的Insert在原30秒D后11毫秒首次进入unknown fence。该复现插件码9，原根码0/空原因仍保留其证据边界。11原命令最终SDK返回、不同ID及原件均保持；279.891秒外Job和全部子进程完整回收。当前第二轮仅增加有限分段计时，核入队/准备/POST/原ID查询耗时；诊断副本不进入产品，没有改WT、金融账本、真实账户或原截止。

当前主路径优先：[SRI006首次执行失败冷核](../evidence/2026-10-31-sri006-execution-failure.md)已固定同次原件，实际使用.2+c050+ef04；11命令在原Host最终均sdk_returned，Native当时映射7成交，首次Native stage=runtime/plugin_error0/host_fault3/session_fault4且reason为空。实际数量10000/目标50400及70秒断言只表示未完成；首次关闭写准入的具体任务仍待动态见证。B优先核该主链，自有P28交付保持独立身份；没有据本次现象归因WT或延长截止，完整B active。

当前[STQ-P28未知委托停机后继](../evidence/2026-10-31-unknown-write-stop.md)已完成普通/搬迁实际两代：各SDK1，首代在原停止截止内以recovery_drain已知失败关闭、无clean，pending/forced=false；第二代原四查询后CTA拒绝，原命令/body/result与金融SHA保持、SDK/POST零增量。根因是自有写轮询占据唯一worker，使恢复查询无法推进；最终8e339源沿已有关闭写准入状态结束等待并唤醒，WT行为保持。普通/搬迁正常卖200买200和正常双代、费用6均通过。58成员ZIP911889…、62冻结输入及两审查996绑定已封，新增P1/P2=0；HANDOFF001（外部历史/待归仓路径：`../../build/ms-unknown-write-stop-delivery-001/HANDOFF-001.json`） SHA0f8c974f…及检查点002提供精确配套。两处prePOST精确抢停动态覆盖、完整次日/新日分析、Host/Source冷重启及unknown解除仍gap；完整集成/模块资格false。本段优先于下方历史，旧.2超时原件保持；当前持仓新起点、WT新增0、真实交易0、全部新写E盘。

最新自有薄桥后继已完成[清仓后财务可卖回归](../evidence/2026-10-31-flat-theory-availability.md)：最终inventorysession.2普通/搬迁均查询确认可卖200后卖200，1SDK/1映射/2Host事件、原WT费用4和正常两代零重复；原清仓同次raw_valid=-100保留，空仓财务可卖0。原显式首参考价三边界模型及最终.2收盘前消费者/恢复通过；自动真实新日分析和完整次日原生会话解冻保持gap。57成员新包、全部8执行Native及独立Scan2来源已绑定，65冻结输入的三份独立审查已封存，新增P1/P2为0。最终HANDOFF（外部历史/待归仓路径：`../../build/ms-inventory-reference-delivery-001/HANDOFF-001.json`） SHA d74f3cf8…供根开发装配，ready_for_candidate_development=true，完整集成与模块资格均false。额外最终unknown重启实跑已经SDK1/unknown保留，第一代原10秒关闭超时，未进入第二代；自有关闭链继续定位，外层物理回收完整。本段优先于下方历史。当前库存起步、不迁旧历史，新增WT及真实交易0，完整B active。

当前库存后续主链已有[新差额与会话日证据](../evidence/2026-10-31-initial-inventory-evolution.md)：普通及搬迁均实际卖出初始200、买入新目标200、2回报/4Host事件/新成交周期、原WT费用6元与同根两代恢复无重复；受限200/可卖100完成实际调度及两代waiting_sellable/SDK0。自有自动初值改由原生会话owner取得账本日期，修正周六自然日与原生交易日失配；v1显式日期保持严格核对。新23发行普通1355/搬迁1332 RECORD、56成员包已封，源码full及搬迁delta四报告共1164绑定复核、新增P1/P2为0。最终HANDOFF-001（外部历史/待归仓路径：`../../build/ms-inventory-session-delivery-001/HANDOFF-001.json`）及检查点（外部历史/待归仓路径：`../../build/ms-inventory-session-delivery-001/INTEGRATION-CHECKPOINT-001.json`）供根组合，旧broker交付保持。首合格分析收盘/下一会话释放/真实休市来源及统一候选继续gap，完整B active。

当前[R31/P27自有执行后继](../evidence/2026-10-30-broker-execution-confirmation.md)已封HANDOFF-001（外部历史/待归仓路径：`../../build/ms-broker-execution-delivery-001/HANDOFF-001.json`）和固定集成检查点（外部历史/待归仓路径：`../../build/ms-broker-execution-delivery-001/INTEGRATION-CHECKPOINT-001.json`）：最终普通source cdc500…与DLL ef04da…，ordinary033及搬迁034均完成52笔SDK替身分单、52笔成交映射、104条Host事件、同根正常两代和恢复零重复；搬迁23发行、1332条摘要RECORD、89个实际安装模块来源通过。两轴最终delta004分别核311/156绑定，新增开放P1/P2为0。根可据固定身份装配SRI005，完整B保持in-progress；当前库存后续差额、新成交/卖出经济代、可卖调度及周末跨日组合仍待验。旧032停止具体阶段unknown和旧预算oracle原件保留；live Standard/Host保持，新增WT修改与真实交易均0，全部新写入E盘。当前持仓作为新系统初始库存，旧开仓历史、旧交易流水和旧周期记忆补齐已经取消；启用后记录正常保存，重启接续。

当前自动库存固定后继为HANDOFF-002（外部历史/待归仓路径：`../../build/ms-inventory-auto-delivery-001/HANDOFF-002.json`）及INTERFACE-003（外部历史/待归仓路径：`../../build/ms-inventory-auto-delivery-001/INTERFACE-003.json`）：普通0.1.0a12+initialinventoryauto.4、C V1a8及Native006，四源/七wheel/17成员ZIP明确绑定。当前库存数量与可卖保留，旧开仓/旧交易/旧持有及退出记忆不导入；收益费用从有效现价的新基准开始，正常重启沿本系统新状态接续。原生SDK替身自动两代及实际查询中停止均通过，普通760/离线搬迁753摘要RECORD通过。两轴full/delta已封，顺序晚回收及并发收紧D两项停止问题均经同触发红绿关闭，当前增量开放P1/P2为0；当前只授该启动切片，受限可卖调度/新差额/真实来源及完整B另列。根2026-10-30新交SRI003主链实际SDK/券商数量与NSQ收敛投影失配，后继优先核该次完整链与短真实复现，自动库存剩余边界随后继续。无新增WT框架行为或真实交易。

自动库存首次主链已跑通，见[新证据](../evidence/2026-10-30-automatic-initial-inventory.md)。WT固定工厂自行取得原四查询和HTTP标价，使用C新V1a8明确initial_inventory/baseline_at，原P23/CTA/NSQ两代完成已有库存加载、计算后正常恢复；16次SDK替身查询/金融写0，来源和原生分层全部关闭。源码新增initial_inventory_execution.py，并接原initial_inventory/execution_process/execution_configured，运行侧V1 pin精确a8。首.1普通候选记录主路径；.2含不可变配置/准备停止/Scan续回收的后继正在验，非沪深300可卖受限、独审/最终制品及整套资格继续。当前无新增WT行为，旧400模型保持封存。

WT12初始库存增量已封存交接：HANDOFF-003（外部历史/待归仓路径：`../../build/ms-initial-inventory-delivery-001/HANDOFF-003.json`）绑定14成员ZIP、普通759/搬迁752摘要记录、两类原生两代及两轴delta审查，开放P1/P2为0。下一主路径由B完成当次事实自动装配：原ManagedAccountScan四查询及原行情SDK有效标价→prepare_initial_inventory→原P23加载→唯一策略；用户无需手写库存JSON、观衡无需运行。预计只在B新增initial_inventory_execution.py并接execution_process.py，WRI runtime.py、根行情等待/Host及C页面保持；该文件归属先在此交接。当前封存包仅授已验准备入口与库存模型，自动启动功能尚在实施。

初始库存的WT12组合后继已完成普通安装、公开CLI、原计算后/首次调度前两代及离线搬迁，见[当前证据](../evidence/2026-10-30-initial-inventory-baseline.md#已接受wt12上的单模块组合与搬迁)。运行包仅在根已接受a12的原成员外增加initial_inventory.py，原行情等待成员逐字保持；开发版本0.1.0a12+initialinventory.1，固定目录build/ms-initial-inventory-wt12-install-002与package-001。最终接口/制品/审查登记在build/ms-initial-inventory-delivery-001/INTERFACE-002.json。A12原基线不含R7两份回测后继模块，旧R7/R28封存材料保持其资格，统一组合归根。当前事实自动装配及后继差额/可卖调度仍继续。

当前库存主路径固定接口已登记在build/ms-initial-inventory-delivery-001/INTERFACE-001.json：唯一生产新增initial_inventory.py SHA d6db04…，原公开核/P23/Configured不改，普通.2的761 RECORD、原计算后与无调度两代均12查询/SDK0且正常关闭，协议delta的最终回读P2已关闭。根可按接口在已接受WT12冻结stage添加该单个模块，保留其execution_market_window等待行为；WT12组合wheel/搬迁与对应审查后继单列，本地WT11开发wheel只保留其原限定证据。真实事实自动装配及后续边界继续，不阻住根按固定接口进行整链验证。

2026-10-30初始库存实施后继：[NRT-R30](../evidence/2026-10-30-initial-inventory-baseline.md)已沿C现有公开周期边界实现自有准备入口，不新增C数学或WT行为。原旧历史失败输入改为新管理基准后，当前数量/可卖保持、年龄0、旧退出为空；普通七发行761 RECORD及公开CLI通过。原SCMR/Factory/CTA/NSQ/标准Trader/WinSHM SDK替身两代零下单、原KV与同根恢复通过；非沪深300/可卖受限、后续差额、独审与最终包继续。开发本地版本a11+initialinventory.1只覆盖原R7新增入口，A的a12及Reader等待候选保持分开，实际事实自动装配和统一候选另验。

用户2026-10-30最新决定：[当前持仓作为初始库存](retained-strategy-takeover-proposal.md)，旧开仓时间、历史流水、旧持有天数/峰值/退出状态全部不迁入。旧开仓历史补齐请求已取消，后继按启动时券商数量/可卖/资金/活动委托及有效标价建立新运行起点，新增交易/费用/绩效从此开始；行情K线继续用于模型。新运行后的正常恢复保留自身状态，重启不再次归零。B接原P23/Configured，C衔接唯一核初始库存合同；当前是规格调整，完整安装验收仍待。决定与精确交接见build/ms-initial-inventory-baseline-001/DECISION-001.json。

自有[报告读取开发检查点](../evidence/2026-10-30-report-read-performance.md)：原5秒HTTP本轮原版及新源码均通过，原C失败保持；原24万次逐值编码成本已定位，report_values.py源码候选6ed30e…f5通过精确字节/隔离合同及三次双400 HTTP/409恢复，完整读取耗时仍有波动。本候选尚未普通发行、全面回归/独审或纳入统一候选，原a11材料保持；不得将源码检查点视为C超时已解决。

历史记录（旧周期补齐要求已被当前库存新起点取代）：[较早开仓的历史输入边界](../evidence/2026-10-30-holding-history-boundary.md)曾在普通安装核复现opening_history_missing。原逐证券8,870对raw/front及完整因子核证通过，原共同矩形窗口从2025-03-05截断了旧周期历史。build/ms-takeover-opening-source-001/C-INTERFACE-REQUEST-001.json已取消，后继开发及验收采用[初始库存唯一方案](retained-strategy-takeover-proposal.md)，不再补旧开仓历史。原报告读取问题与后继资格沿其[单独证据](../evidence/2026-10-30-report-read-performance.md)维护。

2026-10-30完整历史CTA对照后继：[NRT-R28-C5](../evidence/2026-10-30-native-cta-historical-comparison.md)的最终main003已用固定原CTA/普通安装正式1.1.2完成400期、302正式计算、65笔原生模型成交及400次原日结，正常回收且Reader缓存消失。compare003的全部核心结果SHA重建、原RT NSQ重放、语义/数量/成交/财务与终态比较通过，未解释差异0；时间/来源身份及最大1e-11元的double差异保留原值，金额比较容差1e-8元。金融计算沿原WT，输入发布/broker/时钟为明确历史模型。原冻结版审查问题和修正前原件保留；独审/制品沿该证据最终收据。本项不授真实AWP/ticker/WinSHM、完整统一候选或整个B完成资格。

工作盘约束：按用户明确要求，模块B新增隔离安装、运行状态、编译产物、临时文件、依赖缓存和验证制品统一写入`E:/workspace/wondertrader`下的`build/`或`.tmp/`。已有C盘工具仅按需读取或执行；本任务不在C盘新建项目隔离根。当前逐日回放使用`build/ms-per-date-replay-001`，其安装与运行驱动已显式将TEMP、TMP及工具缓存指向E盘。

2026-10-30原完成证明后继：[NBC-R7](../evidence/2026-10-30-wt-backtest-completion.md)沿原NBW/ADR-0012补WT父责任层到观衡只读归档的缺口，显式archive-label发布completed-archive.json，沿同一总D和原件身份。七发行新安装760条RECORD及39源闭包已验，实际400期/400投影/12原输出和原父证明已成功、内外正常回收，12发布故障通过；默认CLI保持。C源码配置可读，原5秒绩效三次超时，当前消费性能与普通App/HTTP/页面继续，C生产文件未改。R6制品已封存208成员、ZIP SHA `aa75b07b9fee1cefc3c9e7db82562f80ce3a762f587f4463da43fd0500f29e39`，两独审604绑定复核且仅共享索引后继，详见`build/ms-per-date-cli-001/POSTFLIGHT-001.json`。本次后继源码/规格身份与R6冻结包分别登记，完整B目标继续。

2026-10-30逐日产品CLI后继：[NBC-R6](../evidence/2026-10-30-per-date-native-cli.md)接入A固定corea2公开ReplayCatalog，原SDK0.15保持。最终七发行ZIP搬迁/require-hashes安装与六发行默认角色各完成实际CLI400期及400报告投影、内外正常回收；原Porter/账本/NSQ保持。审查父D准入P2已在runner修正，同慢open/构造触发旧2失败/当前10通过。最终python006/007、105文件离线材料及搬迁752 RECORD已验；独审、制品/C归档、完整RT/BT及整个模块继续。C新外层输入接缝已按原文件SHA交接，C源码保持。新增WT核心、金融账本和真实交易均0。

2026-10-30持续原生日线后继：[NRT-R29](../evidence/2026-10-30-continuous-native-daily.md)按根团队交接负责自有RealtimeReader/发布输入/策略执行接缝。最终native008的同一原CTA已完成4轮8标的、实际因子变值及32旧slice/停止后保持；窗口缺失/错修订/未闭合拒绝、切换和停止文件占用重试、投影清理均通过。最终main009运行唯一1.1.2四窗口，完成4买2卖SDK替身、同账户/Source/Journal/金融根两代恢复8→9、SDK仍6；106查询无503，内外全部正常关闭，原件0漂移、缓存清除。生产变更限Factory.cpp和新增PublishedDaily.h，不改AWP/Host/Common/WT；源码审查开放P1/P2为0，执行审查与增量交接按本根最终收据。下一工作日和次会话可卖为明确模型，普通最终组合/搬迁、实时九组件、真实跨日、400期RT/BT和整个模块继续。

2026-10-30认证后缀与未知后继：[P25-C3](../evidence/2026-10-30-native-event-suffix-unknown.md)副本整套两代新增原委托/成交回报已通过；独审指出首版观察锁内文件IO后，observer003改内存观察并在009完整重验：Native至4、后继策略序号4、券商/原生数量200、SDK仍1，24查询及14正常关闭。真正进入SDK后抛错的另案已完成整套WT/Host重启，原unknown/命令/结果摘要及三金融文件保持，二代四查询后CTA拒绝、SDK零增量；物理回收完整，业务排空和clean继续拒绝。007另有账户只读Host关闭失败，Native正常，原件及内部原因缺口交公共owner继续。A已接入两份公共生产源；正式发行/搬迁、Source冷重开/未知解除、400期RT/BT及跨日继续，独审与交接分别登记。

2026-10-30整套恢复后继：[STQ-P25](../evidence/2026-10-30-native-event-auth-recovery.md)定位自有事件页创世收据与新认证连接合同缺口，沿ADR-0017原关系补齐只读证明。E盘副本已完成七组件同Source/Journal/金融根两代、三次观衡读取及全部正常关闭：SDK/order/deal各1，原Native状态恢复、原3885安装文件保持；18原生向量、原34事件向量及33 Journal回归通过。013/014后段QA预留截止失败保留，015外层420秒完整225秒通过，各产品截止保持。Common/Host共享生产文件尚未改，公共合入、正式安装/搬迁、后缀/unknown及完整模块继续，WT新增行为0。

2026-10-30逐日原生后继：[NRT-R28](../evidence/2026-10-30-per-date-native-replay.md)已消费A的401日/13组原生窗口，复用原Porter/财务/周期/NSQ完成400次逐日回放及原最终批次400次回归；错误raw前缀和单位在财务写入前拒绝，原red/当前green保留。六发行737 RECORD安装的正式报告读取接受逐日族，两种各400期及18失配拒绝通过，两轴审查按各自SHA授限定资格。两种BT的不同基准导致输入及后继状态差异，完整400期RT/BT、配置CLI和观衡新族消费继续；新增WT行为和金融账本0。

2026-10-30封存后继：[显式股票引用候选](../evidence/2026-10-30-stock-reference-delivery.md)已完成限定业务矩阵、两轴独审及735成员ZIP封存；真实1.1.2成交/正常两代/搬迁恢复通过，预期故障保持拒绝及原身份。源码、包SHA和实际安装/回收按新证据交接。完整400期BT/RT、正式跨日及unknown解除继续；A逐日401窗输入已由B实收，当前没有用户必需操作。

2026-10-30股票引用修正已获用户明确批准：原回复与授权范围（外部历史/待归仓路径：`../../build/ms-stock-reference-fix-001/APPROVAL-001.json`）。沿[唯一方案](native-stock-metadata-ownership-proposal.md)修改StockMinImpact.h/.cpp及WtExeFact.cpp，并接自有Host/唯一桥准入；显式WtExeFact.WtStockMinImpactBorrowedExeUnit选择配对路径，原name保持原行为。已同批重编并通过[正式两代、订单结果及搬迁矩阵](../evidence/2026-10-30-stock-reference-fix.md)：唯一1.1.2成交→后继账户/收敛→正常停止→同根恢复成立，原名/适配名引用与量价对照、费用和unknown原身份拒绝已验；最终审查和制品继续收口，完整BT/RT及正式跨日仍在主线。以下历史“待批准/未实施”段落保留当时状态；本次开发授权不扩大到真实下撤单、生产切换或其他WT文件。

2026-10-30原生T+1后继：[R26-C4原会话接口](../evidence/2026-10-30-native-t1-session-recovery.md)使用正式两代已停止的三份金融JSON副本及R23同一原WtCore，完成同日200/100、次日200/200、重复通知及原session_end保存后新进程加载；成本/盈亏/费用/周期/整个数量阶段保持，原件保持，查询/SDK0。原合成登录日期20261022与策略已保存日期20261030分别记录；首轮混用日期的QA失败保留，最终003通过。正式WRI跨日的日期注入、恢复身份、次日券商刷新与后继执行继续待验，WT修改0。

2026-10-30未知责任冷重开后继：[R27-C4原Host工厂/Source](../evidence/2026-10-30-unknown-transport-reopen.md)在独立新进程使用R27实际Journal完整副本及相同route/trade identity/profile，通过认证HTTP读取同一unknown原命令/原文及结果SHA，并经WinSHM取得P/O/D/A四查询。新Source本地unknown=false、Host持久unknown=true且新委托准入false，SDK写0/命令POST0，原Journal及原三金融文件保持，内外完整关闭。正式WRI全组件重启与未知解除继续gap；本轮没有新建股票Native运行实例，生产/WT修改0。

2026-10-30未知责任后继：[R27正式WRI同根重启](../evidence/2026-10-30-retained-unknown-restart.md)在普通a3/730 RECORD、原R23制品运行唯一1.1.2：SDK替身卖200入口进入后异常，原unknown的命令/原文/结果摘要保持；首代recovery_drain失败且无clean，第二代四查询后CTA拒绝，SDK及POST零增量、金融原件保持。最终main003完整验证9查询/SDK1，整个三案27查询/SDK3；001阶段预期错误、002未知卖出摘要字段错误及两次关闭AV分别保留，物理回收齐全。Host存续的Native跨进程边界已验，Host/Source整体重启与未知解除继续gap，产品/WT改动0。

2026-10-30可卖恢复后继：[R26同日正式等待](../evidence/2026-10-30-retained-sellable-recovery.md)在普通a3六发行/730 RECORD、原R23制品完成一条同根两代：200/100、整个NSQ状态及周期保持、序号2→3、12查询/SDK0和完整正常回收。main003第三代原生摘要拒绝另由同次原件核实；原QA定位失败及最终修正入口未完整通过分列。main002/004关闭c0005各6查询，离线各42帧直接返回同原股票商品释放指令；四案40查询/SDK0，全部物理回收，稳定关闭与次日解冻继续gap。产品/WT核心改动0，原最小引用方案保持提案。

2026-10-30正式账户生命周期后继：[a3正式WRI与C原定位消费者](../evidence/2026-10-30-native-account-wri-lifecycle.md)完成初始两轮、运输同凭据重新认证、来源失败保旧、成功空P/O/D清旧及SDK查询在途停止，共21次SDK替身查询/0写；C五状态schema4/原时间/掩码/行数与读取期间SDK0增量通过。普通安装CLI正常exit0，Host/Scan/来源及Job/EOF/join/句柄完整回收，1367输入前后精确、18源码物理冻结；四生产源保持，独审交付按后继收据登记。a3父死亡/超时、C HTTP/页面、真实来源、并行策略及完整恢复继续。

2026-10-30账户生命周期后继：[NAP-P3/P4四条隔离链](../evidence/2026-10-30-native-account-publication-faults.md)在原005/a2及四份生产源保持同SHA下，完成原常驻Host/Agent重新认证、Native暂停后原D杀树/恢复、在途停止排空和父Python退出7后的实际子树回收/同根新代读取，共54次SDK替身查询/0写；C原发布投影九状态通过。父退出证明分清WT实际PID、launcher及Native，树零/EOF/join先于外层空Job终止，不授全程API零调用。四案229共同输入已物理冻结；a3统一候选、C实际HTTP/页面、真实组合及交易恢复继续。

2026-10-30账户发布后继：[NAP-v1](../evidence/2026-10-30-native-account-publication.md)迁移原Scan纯配置/IPC与单轮监督到独立WT，固定工厂发布原四组帧和关闭证明，金融投影仍由C原实现负责。最终普通005安装六发行736 RECORD，无App/Web；main009两轮各50项原事实精确、失败保旧、成功空P/O/D恢复，共13 SDK替身查询/0下撤单、正常关闭及同根竞争通过。十种错配置、busy资源结构及两个首停D回归通过；A公共runtime注册与C实际HTTP/页面、认证换代/父死亡矩阵和真实组合继续，完整模块active。冻结合同与安装交接沿[唯一规格](native-account-publication-proposal.md)。

2026-10-30费用后继：[NRT-R25](../evidence/2026-10-30-retained-native-fees.md)已用旧R24安装复现minfee7而实时原账仅记4的正式反例；自有实时准入拒绝正minfee及缺品种费用，BT不变。普通六发行/732 RECORD，唯一1.1.2按金额卖出费3.60及完整关闭，按份费4业务收敛但关闭c0005；原CSV/fund/flag0/NAV/现金及源P/A分别一致。13边界与正minfee前置0查询/0SDK已验，实时最低费用/平今/跨日及稳定恢复继续。真实四组观察的[WT发布提案](native-account-publication-proposal.md)明确生产者→原帧发布→C原投影，公共合同待冻结，生产尚未实施。

2026-10-30真实精度后继：复核根[修正制品真实四查询](../evidence/2026-10-30-wt-native-account-fixed-real.md)最终DELIVERY-001 SHA ea5edd9cbe79910e1f5408a58a08e48b4502c0112c7ad7271723af33df2b5a9f；22份原件、两个实际原生制品及三生产源摘要全部匹配。4P/0O/0D/1A，67事实/39ABI槽/24浮点逐位一致，22.002秒及正常关闭、原探针恢复；B复核SUCCESSOR002（外部历史/待归仓路径：`../../build/ms-real-account-consumer-001/SUCCESSOR-002.json`）新增查询0。该实源使用Host诊断包装，普通无包装修正版及同一四owner真实现场、标准v4执行/唯一策略发布仍分别待验。旧资金中断根因unknown，原Journal保持。

2026-10-30持续窗口后继：[NRT-R24](../evidence/2026-10-30-retained-market-window.md)接入A原发布窗口，原C解码/策略核及原Reader/NSQ保持唯一。普通六发行732 RECORD，正式入口缺源0SDK后发布真实3208行窗口，四买入/四实际周期/29查询并收敛；两日及同日修订等17个模型边界通过。关闭仍c0005、clean未发、外部/Job完整回收；A后继公共源和C状态候选、真实持续新日发布、稳定两代及完整模块继续待验。全部新增写入E盘，WT核心实施0。

类型：模块实施与交接正文。状态：in-progress。完整目标按[三会话计划模块B及M1–M4](parallel-system-delivery.md)执行；本对话活动goal覆盖本模块全部要求，无token预算。真实交易和新增WT核心行为按原批准边界处理。

2026-10-30关闭故障后继：[正式同次释放链](../evidence/2026-10-30-stock-close-release-trace.md)已从rt-main002原转储及COFF定位自有close→原Local/工厂→股票单元商品release失效虚调用；相同原工厂的两单元最小红例在同位点c0005，无行情/策略/SDK，引用1→1→1代替应有3。正式首次释放的完整引用历史仍unknown。当前[三框架文件方案](native-stock-metadata-ownership-proposal.md)已重新绑定R23原生及NBC六发行/15模块，仅生成候选，生产未应用或编译；稳定关闭/恢复及完整模块资格继续。所有新增工具、运行和符号目录均在E盘。

2026-10-30真实来源消费者后继：A已完成[独立WT原生四查询](../evidence/2026-10-30-wt-native-account-consumer.md)与[同一WT/Host两代读取](../evidence/2026-10-30-wt-native-account-reconnect.md)，B复核两交付52份原件SHA、4/0/0/1计数、原完成帧、运输换代及旧终态保留，收据为`build/ms-real-account-consumer-001/SUCCESSOR-001.json`。此前私有配置与联合接缝（外部历史/待归仓路径：`../../build/ms-real-account-consumer-001/CONSUMER-REQUEST-001.md`）保持准备历史，v3窗口不重复申请。持仓数量/可卖及资金ABI槽精确，四项浮点事实1 ULP缺口沿A统一JSON修正继续；当前标准交易插件要求v4账户/交易上下文，v3只读证据不替代该产品链。完整策略接管与资金/周期初值继续分别核准。

2026-10-30独立回测后继：[NBC-R5](../evidence/2026-10-30-standalone-native-backtest.md)把唯一1.1.2原回放/Porter/NSH及报告链迁入WT候选，普通六发行/731 RECORD，实际安装CLI完成401日输入/400次闭合、原userdata/12输出及内外完整回收。安装writer两项审查缺口已用旧源red/当前回归闭合，89项边界通过。最终同安装RT完成四买入/四周期/收敛，关闭c0005仍失败；末日14字段/目标一致仅授单时点，完整BT/RT继续。C原文件保持，五个兼容别名为待owner集成候选；开发包身份沿新证据。全部新增写入E盘，WT核心修改0。

2026-10-30等待恢复后继：[NRT-R23自有P/A自动补查](../evidence/2026-10-30-broker-observation-refresh.md)已复现资金0释放后原宿主不补查，并通过显式配置在原owner/队列/SPI中补查。普通六发行/721 RECORD、唯一正式1.1.2完成资金释放后四买入/四周期/收敛；慢查询五轮及16案准入、安装C ABI通过。默认关闭同候选完成单代正常关闭；启用刷新两次成交运行在关闭捕获c0005，完整恢复仍待验。跨日可卖实验未形成有效会话，保持gap，未据此改WT。新写入全部位于E盘，开发包和审查身份沿新证据登记。

2026-10-30成交与周期后继：[NRT-R21/R22原提交来源](../evidence/2026-10-30-actual-opening-source.md)已普通安装六发行、720 RECORD，最终native005/WRI实际完成真实3208行输入后的四笔替身买入、四个实际周期、原1.1.2/NSQ继续收敛及单次正常关闭。旧成交晚到误归属已用原OrderIDs→原on_trade身份修正，原数量/成本/绩效账本保持；旧源red、安装14项归属回归、六项C++来源边界、九组实际Adapter投影及安装C ABI通过。后继两代尝试在首代关闭捕获AV，第二代未执行；稳定恢复、完整BT/RT及最终组合继续。原件、SHA与各失败范围沿新证据登记，全部新增写入使用E盘。

2026-10-30只读交接后继：[NRT-R20实际WRI CLI](../evidence/2026-10-30-execution-readonly-handoff.md)已在无观衡/Web普通安装完成唯一1.1.2卖200及收敛；root公开reference、原ready与v2三身份一致，取得P revision2/资金82000/剩余200份，读取期间SDK调用不变。main005整链正常关闭，WRI成功closed、执行父证明closed.v2/clean.v2及两层Job树0/管道/句柄回收齐备；该单次结果与历史股票故障分别记录。main006两代尝试首代成交后提前exit2，未进入二代，完整恢复继续gap。C沿同证据中的实际root配置消费既有DTO，P/资金与未提供的订单/成交分组表达；C HTTP/页面及错误身份矩阵待其接线。六wheel固定安装及准确版本/SHA在新独占根，当前未切换生产。

该片开发包`build/ms-execution-observation-001/B-EXECUTION-OBSERVATION-001.zip` SHA `754195f8457079d13fc2ce053a84bc7cad04a9860e6e408ccdd15e1990cac1d9`，116成员摘要/字节数全验；包含六wheel、未改的native005、冻结源码和实际/失败证据。DELIVERY-001 SHA `29630a370db04d66a6555e2d05c4f7e3f9a5cfa726be3c60f31bbd1b7e0db91b`，REVIEW-001/002已覆盖生产及实际CLI切片，开放P1/P2为0；搬迁后整链、统一组合及完整B模块继续待验。包内股票提案为封装时的历史草稿，准确当前候选以[唯一提案正文](native-stock-metadata-ownership-proposal.md)及其独审记录为准。

正常两代后继main007已完成同样的策略/券商观察交接，关闭时捕获c0005、slot0候选为原WtExeFact商品release位置；没有受控交错，完整关闭及第二代仍失败。最小提案已收敛为3个WT文件及2个自有准入文件，通过原factory name显式选择借用引用配对，原名保持原行为，StockVWap排除；批准前不应用/编译。实际新周期来源、全周期同核比较及完整资金/T+1/费用仍可独立推进，框架提案不替代这些模块缺口。

2026-10-30独立执行后继：[NRT-R19迁移及P24最终证明](../evidence/2026-10-30-standalone-execution.md)已迁出五个执行/共享胶水模块，提供WRI固定工厂；普通无App/Web安装六发行/720摘要记录匹配。真实资料main-010已核P revision2/四证券发布，随后exit2暴露旧提前clean问题；native005改由父监督者确认实际退出/回收后发布最终证明，独立组件七案通过。自有QA可卖字典覆盖根因已修；retained-006/008在无App/Web目标环境实际卖200并收敛，股票退出仍失败，008取得同次c0005及原商品release栈候选。最终成功证明均未发布；unclean-001用008实际5份金融状态副本验证Ready前拒绝、4查询/SDK0、源/副本SHA不变与完整回收。正常两代、C共享胶水消费者统一及完整恢复继续；所有新产物/缓存均在E盘，新增WT源码修改0。下文旧候选事实按各自冻结输入保留。

真实资料后继：[A最终窗口进入B正式RT及原BT比较](../evidence/2026-10-29-real-retained-bt-rt.md)已消费A最终原价/前复权3208行和C已审Appa26，当前普通安装29发行/4731 RECORD/139私wheel成员一致。真实资料产生完整八目标，经原执行链完成四笔SDK替身买入；与同安装C正式原生BT末日flat单次的14完整非来源字段、EconomicTarget及八数量一致。主RT仍失败：源端P补查四行而后继公开观察仍初代空，尚未确认身份解析/SPI/快照发布完成，后继原操作失败/exit2；该现象不能直接归为缓存错误。下一主线核该交接及实际新周期，当前完整RT/全周期/股票退出资格仍gap，新增WT修改0。

当前后继：[R18唯一实时桥与P24关闭边界](../evidence/2026-10-29-retained-cta-and-close-boundary.md)已消费C Appa23唯一1.1.2及共享决策核，正式原CTA完成八目标、一次卖200、后继收敛；旧候选完成两代。当前native004关闭仍失败，已捕获原股票商品资料release处的实际异常，独立计数实验证明借用引用缺额。自有宿主已把Local/单元销毁纳入完整close，在其后释放依赖并生成clean；最新失败无clean/成功closed，实际5份金融状态副本在Ready前拒绝恢复、4查询/SDK0且源/副本SHA不变。当前完整股票退出、最终同根两代、完整同输入BT/RT、真实新开仓周期与动态真实输入仍gap，模块继续。

用户后续明确要求追查已经发生的异常退出。下文“停止WT调查”保留当时暂停潜在线程专题的背景；实际故障沿[单一现场记录](../incidents/2026-10-29-retained-cta-access-violation.md)继续，归因按各次原件分别说明。原股票组件的借用引用错误、运行中持仓条目搬移机制和QA HTTP容量错误已有各自证据；首次自然访问异常的同次根因仍有边界。新增框架源码修改0，既有提案保持原审批状态。

[R17券商只读观察](../evidence/2026-10-29-native-broker-observation.md)已接原P/A表到安装C/Python公开入口：同根两代1000份、成交后原查询800份、多证券1000/400、已知空仓及旧库缺扩展兼容通过，运行前后Unavailable和安装C头/导入库消费通过。最终native-002与INSTALLATION-002记录实际输入；接口不计算成本或成交归属，不修改WT核心或调度。该隔离Appa19 API候选保留历史依赖资格；下一主线消费C唯一1.1.2同核接缝，连接真实周期、策略预算及A前复权来源，完整模块继续。

[P23存量接管](../evidence/2026-10-29-native-holding-takeover.md)已在自有Session根租约内生成原WT初值，正式Runtime读回1000份/周期/原KV，保持目标SDK0、减到800仅卖200；最终同根两代12查询/SDK0、接管记录原字节及完整关闭通过。符号容量/原环境日期校验已补，指定拒绝矩阵通过。当前为合成单证券目标，C唯一1.1.2核/真实初值/多证券及完整交易规则仍继续；WT调查与核心提案保持停止。

[首账户资金接线P22](../evidence/2026-10-29-first-account-execution.md)已在自有Adapter收敛最近完整CNY查询观察，向延后创建的原执行单元重放；最终通用资金等待/恢复、负值观察保留、空资金源明确失败通过。原安装公开CtaRuntime直接调用最终运行DLL的A600+B400净买1000及完整关闭通过；旧exe另列兼容证据。运行DLLf3049cd1…与两头/自有库为隔离候选，股票最终退出仍失败、不提升发行资格。该项只影响买入委派，没有只读查看门槛或资金账本，WT调查保持停止。

2026-10-29后续用户范围已明确：唯一迁移策略为“共振市场状态 ETF 策略”（resonance-regime-v1），当前全部券商持仓均归它；运行目录、注册表、页面、发行依赖和验收只保留它的最终最新正式在用规则版本。主会话已由两份实际运行与同一配置核准最新正式在用1.1.2、六参数和预算，依据见[唯一策略确认](../evidence/2026-10-29-retained-resonance-latest.md)；1.2.0可配置角色分支分列封存，B/C按实际周期及止损语义衔接。其他策略及历史版本停止开发/验收并退出本轮运行和发行，已写源码、包和证据封存可追溯，旧QMT仓库保持只读。下文历史全策略承诺以本段覆盖；公共行情/历史、账户/订单、多策略底座、数量/费用/T+1及必要恢复继续。R15完整35包和旧configured/V2专用资格作为历史开发记录，统一候选由C唯一最新核和B唯一profile重新组成。

当前持仓采用用户确认的唯一归属，券商数量/可卖及资金保持实际账户事实，策略预算沿实际配置。历史交易、旧开仓时间和旧峰值/退出记忆不迁入；历史K线继续用于模型。[初始库存方案](retained-strategy-takeover-proposal.md)和[自动启动后继](../evidence/2026-10-31-initial-inventory-evolution.md)已经覆盖当次查询、当前标价、新管理起点、原WT加载、后续卖200买200及同根正常恢复。新运行后的交易和状态正常保存；首次初始化与恢复分别沿原责任准入，整个统一候选资格继续按上方最新交接登记。

[实际异常状态后继](../evidence/2026-10-29-abnormal-state-admission.md)已用0xC0000005实例留下的5份原金融文件副本验证resume_clean缺干净证明拒绝：4查询、新SDK0、原件/副本摘要不变且完整回收。自有QA补实际进程存活检查，正常configured兼容各700/净买1400/8查询通过；资金拒单及频次四次运行仍未完成资格，失败与访问异常均保留，WT调查继续停止。A真实quote+自然分钟整块DELIVERY `be13aa7d06c5ce8cd60fabf3cab68327aae1d7ca1155197e0d1b7701fa7eeaf1`已交付，按[原证据](../evidence/2026-10-29-qmt-real-market-cta.md)复用，无需重复实源；全真实日线预热及准确持仓策略由A/C后继契约衔接。

2026-10-29最新用户决定：停止WT框架多线程相关调查与[NPO候选](native-position-ownership-proposal.md)推进，已有实验仅保留记录，未来实际故障按现场处理。当前回到模块B主线，优先完成R12原用户KV中的策略决策阶段恢复及自有启动失败传播、异常/兼容和安装验收；继续复用原生持仓、绩效、调度及保存加载。

R12后继已形成[007开发候选](../evidence/2026-10-29-configured-quantity-recovery.md)：正式两代700/700恢复、四类状态拒绝、容量/线程/阶段及旧桥兼容、三个指定应用异常、安装C/C++头与22依赖离线搬迁均有原件。原setter向量中途/实际KV和文件I/O异常仍待验。正式订单结果与五组合已在同版产品入口完成所列范围，下一主线继续资金/T+1/费用、保留算法及异常跨根责任，不将框架调查作为前置条件。

[V2原生后继](../evidence/2026-10-29-v2-native-bridge.md)已连接原V2Binding/NSQ到正式Factory/ticker/净额执行，同核BT/RT完整结果及1200股目标一致；BUILD005两代恢复序号2→3、净买2400后恢复零新增SDK通过。自有投影Windows句柄窗口及预编码后截止在原薄适配内修正，核心改动0；002为本片开发包，冻结007保持。其他保留版本、完整交易规则及统一Appa18接线继续。

[R14正式组合](../evidence/2026-10-29-native-market-cta-composition.md)已将A固定原生分钟Reader及ParserQMTHostV6接入同一正式Session：实际137分钟只读，原自然13:40/13:41调度，configured双策略各700→净买1400→后继converged及完整关闭通过；6份分钟回调与原Helper精确相等并保留副本SHA。日线、FullTick及券商仍为显式替身；下一主线继续全真实输入资格、统一Appa18与其余保留版本，框架调查保持停止。

[交易规则后继](../evidence/2026-10-29-execution-trade-rules.md)已实际核原非零费用各7元、NAV49993/现金42986、整组费用预留不足时waiting_cash/零SDK，以及原股票执行器按P1000/usable200仅卖200。自有宿主增加原股票min_order正整数准入，沿原Factory解析统一识别身份；最终BUILD003的七类拒绝及原通用A600+B400买1000通过，股票执行完整退出待验，当前不替代冻结007制品。T+1及零可卖的完整退出、真实账户预算和其余交易矩阵仍为缺口，框架调查保持停止。

## 验收与现状

| 验收ID | 完整业务结果 | 已有证据与下一段 |
|---|---|---|
| B-01 | 券商资金/持仓/可卖/委托/必要当日成交四查询准确进入原Adapter及公开观察 | 最新[精度实源](../evidence/2026-10-30-wt-native-account-fixed-real.md)已4P/0O/0D/1A、67事实/39ABI/24浮点逐位一致，正常关闭及原探针恢复；B复核（外部历史/待归仓路径：`../../build/ms-real-account-consumer-001/SUCCESSOR-002.json`）绑定22原件/2制品/3源，新增查询0。旧1ULP失败保留历史。原生Scan/只读Trader已验范围与v4标准执行、唯一策略接管/公开发布及无包装修正版分别登记；统一候选继续 |
| B-02 | 正式入口完整委托/撤单/部成部撤/迟到回报及终态后继续 | [P30普通及搬迁11矩阵](../evidence/2026-10-31-host-idle-functional-observation.md#p30-搬迁完整矩阵及资格收口)授其固定安装的O1–O5、原价格/迟到去重/终态后仅补200资格；当前Root005/G3安装的三例冷查询撤单（外部历史/待归仓路径：`../../build/ms-finite-recovery-closeout-002/HANDOFF-001.json`）各一次SDK撤单、原身份保持、终态O后P及零重买通过。当前统一候选新金融根主链（外部历史/待归仓路径：`../../build/root-final-new-sdk-002/INTERFACE-002.json`）实际53分单/53成交、九组件正常关闭通过；该主链只运行一轮，不替代P30多轮/异常矩阵的原范围。真实下撤单未执行 |
| B-03 | A600+B400、A退出保B、相向净额、买1000部成500/未成500 | [最终P30两安装五组合](../evidence/2026-10-31-host-idle-functional-observation.md#p30-搬迁完整矩阵及资格收口)均核净买1000、仅卖600保B400、相向净额0/SDK0、在途400和部成500防重；原Factory/CTA/WinSHM及Native账本保持。Generic目标矩阵与唯一1.1.2正式WRI、真实来源分别授证 |
| B-04 | 配置驱动受管宿主、隐藏启动、独立安装与完整资源回收 | 永久G3构建（外部历史/待归仓路径：`../../build/ms-permanent-execution-root-handoff-001/HANDOFF-003.json`）完成全新五执行组件/25安装文件及实际链接闭包，两轴独审通过；Root005普通组合安装（外部历史/待归仓路径：`../../build/root-final-runtime-005/COMBINED-INSTALL-001.json`）已使用同批G3，独立角色及完整九组件SDK启动/关闭沿实际主链（外部历史/待归仓路径：`../../build/root-final-new-sdk-002/INTERFACE-002.json`）授证。旧P30普通/搬迁11矩阵、两代/七拒绝及65成员包保持其原安装范围；新版本搬迁/同根恢复分别核，不用旧安装结果直接覆盖 |
| B-05 | 同根干净停止后恢复策略/用户KV/组合并防重复提交 | 原金融resume011（外部历史/待归仓路径：`../../build/ms-existing-financial-resume-checkpoint-005/SUCCESS-001.json`）已在原同版安装完成正式1.1.2计算序号20→21、券商实际50400及原53订单/成交保持、新增SDK0、九组件正常关闭和新clean证明；此前来源容量阻断已由该后继闭合。P30普通/搬迁A800/B400及KV接续、两端七拒绝保留。当前G3新金融根的同版恢复由Root原owner验证，本行不预授其结果。活动单Standard冷查询/撤单已验；正式CTA在活动单仍存时自动续跑及unknown后自动恢复交易继续缺实现。新增save接口0 |
| B-06 | 异常退出/未知命令保留原Host/Journal身份并准确决定准入 | 当前有限恢复交接（外部历史/待归仓路径：`../../build/ms-finite-recovery-closeout-002/HANDOFF-001.json`）已沿同一实际Journal跨进程重开，未知未成交、未知部分成交及正常受理活动单三案保原UUID/body/raw result/stage，新Standard真实O恢复身份后各定向撤单一次，终态O→P及可卖核对通过；unknown继续禁新insert，没有原insert重POST。238直接绑定两轴delta无开放P1/P2。已授查询/撤单及保持保护的判断资格，正式1.1.2异常金融/周期续接和unknown解除后自动交易继续未实现；[UDR](unknown-broker-evidence-recovery-proposal.md)保持proposed，当前有限收口范围未新增该架构 |
| B-07 | 真实业务算法同核原生回测/实时目标一致；资金/T+1/费用明确 | 唯一正式1.1.2的[逐日原生BT](../evidence/2026-10-30-per-date-native-replay.md)及[400期CTA历史对照](../evidence/2026-10-30-native-cta-historical-comparison.md)在声明模型/金额容差下完成302计算、65模型成交、0未解释差异，Root已接收。当前Root005的一轮正式1.1.2/AWP/ticker/WinSHM整链已验；全历史对照和该现场范围分别保留。[净费用](../evidence/2026-10-31-flat-theory-availability.md#独立sdk净费用与资金观察后继)4+2模型及正常两代通过；次会话模型（外部历史/待归仓路径：`../../build/ms-managed-next-session-proof-002/PROOF-001.json`）验证原ticker可卖100→200、券商仍100时等待、来源补查200后才卖200。自然跨夜/默认时钟一致及真实费税尚未授证，模型证据不替代实源资格；原生账本保持唯一 |
| B-08 | 模块交付可纳入统一候选，主链/坏例/review/制品/源身份完整 | 永久G3及原011、当前有限异常恢复均有固定SHA/两轴独审与回收证据，Root005已纳入实际独立安装并通过新金融根53成交/九组件关闭；本模块可据对应交接接收这些已验能力。新G3同版恢复、整模块最终逐项审查及原声明的自动异常续跑缺口仍各自登记，whole_module和生产资格继续未达成；旧P30多轮/搬迁/拒绝证据保留其安装范围 |

## 精确文件边界与集成交接

B独占生产入口：`src/GuanhengExecution/{main,CtaProcess}.cpp`及CtaProcess.h、既有`src/GuanhengExecution/{CtaExecutionSession,StandardExecutionHost,ExecutionEnvironment,BrokerQueryContext,OwnerExecCommand,QueryFirstSubmission}`；交易插件`src/TraderQMT`、只读插件`src/TraderQMTReadOnly`、`src/GuanhengAccountScan`和原生策略桥`src/GuanhengRealtime`按既有规格推进。专用测试在`tests/integration/qmt_cta_product`及既有各交易测试目录。P20/R9新增ManagedStrategyBridge及共用ContextAccess；全部实际改动按冻结SHA清单登记。

此前受管任务已经新增`apps/guanheng/guanheng_app/execution_process.py`，本段作为交给C的薄适配候选；按新分工App公共接线由C集成，B保持`managed_local_process.py`、settings/lifespan/路由及业务算法原状。共享`cmake/native/qmt_standard_product/CMakeLists.txt`中GH_STANDARD_CTA_HOST、产品exe及原工厂安装是给A的明确接线片段；锁、Common协议、总构建和其他公共文件保持A集成。

NRT-R10的`apps/guanheng/guanheng_app/execution_strategy.py`由B新增并交C集成，范围为同安装运行DLL/标准Factory的ctypes、冻结值和回调借用期，不改公共App生命周期、HTTP或唯一业务算法。

NRT-R11候选`apps/guanheng/guanheng_app/execution_configured.py`由B负责固定业务配置及原上下文到唯一核/NSQ的装配；`execution_process.py`增加显式ManagedPythonExecutionProcess。C集成App配置/生命周期，公共应用文件及算法保持C所有。接口见[NRT-R11](../specs/native-realtime-strategy.md#nrt-r11-固定业务配置的受管python入口)。

公开接口交错实验确认同一epoch期间quote能推进本策略原理论信号并冻结T+1；该实验尚未证明正式业务算法因此产生错误目标或委托。用户明确要求沿WT原有行情及CTA调度，已撤回[事件串行提案](native-cta-event-serialization-proposal.md)，多字段事务快照及行情冻结退出运行要求。原字段语义、策略归属、数量和执行结果继续按原生主链验证，已安装接口缺少证明的actual/pending保持UNKNOWN。

新增WT核心文件修改0。当前输出根租约覆盖原生文件，产品账户mutex覆盖同时运行的本产品账户owner；异常恢复和跨根持久责任没有据此取得资格。

## 给C的运行接口

按ADR-0016，当前C消费入口为[NRT-R20只读定位交接](../specs/native-realtime-strategy.md#nrt-r20-独立运行结果的只读定位交接)及[实际安装样本](../evidence/2026-10-30-execution-readonly-handoff.md)。运行、启动和停止归独立WT包，C不持有执行owner。下文App构造/托管接口记录历史已验候选，不作为当前观衡装配方式；旧App共享胶水消费者迁移仍需C按R19完成。

2026-10-29[当前Appa19组合](../evidence/2026-10-29-current-app-native-composition.md)已完成完整35依赖普通安装、configured/V2正式两代、同安装BT/RT及离线搬迁。B严格实时profile在构造阶段拒绝非空historical_model，保留HEM研究BT。固定依赖沿C INSTALLATION-003，core-a7/signals-a5/v2-a4及core wheel SHA bbc5465fca0fe41d5c0379f237e548ecdeb5f2af2ccf9824edc09ebc5e44de56。公共`guanheng_app/v2_package_profiles.json`根文件仍选a6/a3/a2并归C，B保持原字节；独占build/ms-app-current-001/integration-overlay-002提供精确before/after及REQUEST，保留旧档案、新增并选择a7/a5/a4，已在同候选通过。由C/A纳入统一App资源后核公共入口，公共版本校验保持严格。003开发包74成员/35wheels，冻结007及V2开发002保留。

候选`ExecutionProcessConfig.load(installation, configuration, control_root)`消费实际安装清单、显式JSON配置、固定启动/关闭预算及源码身份；`ManagedExecutionProcess(config)`复用原ManagedLocalProcess/ProcessJob。`start(absolute_monotonic_deadline)`返回完成就绪与否；`request_close()`只发布请求；`close(seconds)`沿原首个关闭D确认整树、双管道和句柄；`status()`只返回生命周期/固定错误和pid，不携带凭证、持仓明细或策略收益。

原生配置schema为`guanheng.cta-execution.v1`，固定策略集合及原Parser/Reader/算法参数由B消费。ready/closed/stop各为`guanheng.execution.*.v1`，绑定control_id、pid及配置SHA。fresh及未获恢复准入的profile保持closed.recovery_ready=false；010显式原生record_clean/resume_clean仅在P21完整责任准入及成功关闭后返回true，完整P21及模块资格仍未完成。003历史候选保持原固定false合同。实际来源、账户事实、理论绩效及执行差额各沿原owner接口，页面接线由C负责。

原生产品可通过安装wheel中的`python -m guanheng_app.execution_process`启动；长期受管生命周期由C显式构造上述对象，不要求额外Shell/服务进程。凭证只沿原环境变量契约传入，不进入argv或公开状态。

fresh交接候选在`build/ms-product-003/DELIVERY.json`及`GuanhengExecution-fresh-dev-candidate-003.zip`；组件逐文件、App安装闭包及20份B变更SHA已冻结，实际归档搬迁主链通过。候选App wheel为构建时0.1.0a4；C当前开发版本已推进0.1.0a5，统一候选须由C保留薄适配重新打包核验。完整模块B继续，后继同核桥从新候选根开发，003原件保持。

## 给A的数据与集成需求

需要固定身份的可安装Parser/Reader、session/商品/合约/交易日资料、统一历史与闭合分钟接口，并保留来源/接收/发布时间和实际单位、可用范围。真实QMT四查询沿现有已授权只读接入；B不操作QMT界面或启停行情策略。公共运输/认证需要变化时先列专用契约与文件，由A合并。

M1首条真实算法与C一致，选择`resonance-regime-v1@1.2.0 configured`，复用`guanheng_strategy_core`唯一纯核及NSQ数量核。准确数据请求如下；源值读取通过与标准化资格分别记录。

| 项目 | B消费要求及来源缺项处理 |
|---|---|
| 信号证券 | `510300.SH,515080.SH,588000.SH,589680.SH,159780.SZ,510050.SH,512100.SH,510500.SH`，八角色来自现有configured配置 |
| 执行证券 | 前述集合中`589680.SH`映射`589000.SH`，并集9只；证券名称/上市日/停牌及交易日历提供真实事实，缺日保持缺口 |
| 周期与预热 | 完整闭合d1 OHLCV/amount；默认至少当前日前100个完整交易日，MA100、价格位置60、量比20，连续EMA20从首次ready前缀递推。首个固定真实候选请求2021-11-01至2026-10-27；较晚上市保留实际起点，不补造100日 |
| 原价及单位 | 首NSB/NSQ现金ETF profile为raw CNY/share、volume份、amount CNY、整手100；factor_revision明确标识raw。源单位unknown保持unknown并阻止该profile执行准入；读取结果不可改标签授资格 |
| 时间与覆盖 | Asia/Shanghai交易日15:00闭合标签、逐行market_available_at/来源SHA、source_revision/factor_revision、已知完整交易日与实际缺口。实时时间/重连补发资格独立，历史补发不直接触发新实盘目标 |
| 辅助事实 | shares_delta_yi、share_probability、turnover_percentile、margin_percentile及available_at/source_dates/sourceSHA按原DailyObservation保留可选缺失；禁止用分钟量额替代。缺失导致的策略分支与权重由唯一纯核解释 |
| 数据接缝 | A先交固定真实d1窗口及显式身份/单位/覆盖收据（SDK/HTTP），再交可安装原Reader相同窗口；实时Parser/Reader按原CTA回调提供闭合事件。B不复制聚合或另建行情数据库 |

A已交接统一SDK0.14.0的`source_daily_history_query({exchange,code,from,to,limit})`，候选为`build/source-market-package-039/GuanhengMarket.zip`和`build/daily-sdk-wheel-042`。同一SMP可注册原335分钟store与`build/qmt-daily-installed-final-035/store`的9ETF7739根日线，源收据为qmt-import.json。A的[公开读取证据](../evidence/2026-10-28-source-daily-public-sdk.md)已核来源与直接原Reader逐行一致；B后继消费此统一接口，原单位unknown、尾部及内部日历覆盖unknown、date非market_available_at继续阻断现金ETF实盘准入。B尚未授本策略真实来源/同核运行资格。

后继固定交付127已补齐：`build/qmt-prepared-native-121/daily-store`含9ETF9271条，20250305..20261028共同401个交易日齐全，510300原缺两日已补回；同039组件/042 SDK的安装读取已由A验证。OHLC为CNY/份、volume为lot（100份/手），amount未知；真实单位及日历依据以[源资格](../modules/qmt-source-qualification.md)为正文。首次历史可知/修订未知，本批实际实收2026-10-29T01:23:25.163+08:00。后继先明确日末模型回放的假设与真实实收分别保留，再消费同一原Reader/SDK；严格15:00逐时点模式保持原准入，不伪造历史available_at。当前纯核未使用amount计算特征，金额未知保留为来源限制，进入有量纲资金/成交额业务时再核资格。127交付摘要及本轮消费状态见[后继证据](../evidence/2026-10-29-configured-bt-and-native-load.md)。

## 当前下一段

1. 永久G3、原金融011恢复和有限未知/活动单查询撤单均已交付；Root005已实际完成新金融根53分单/成交及九组件正常关闭。复用这些固定原件，保持P30多轮/搬迁及历史失败的各自身份，不重跑原53笔或重设本系统基准。
2. 新Root005金融根的同版恢复由Root原owner完成；B接收实际恢复后计算、零重复及完整关闭证据。原011使用原P30安装，继续保持其已通过资格，跨版本恢复单独核实。B保持Root的analysis_window/collection源码和实例。
3. 按总方案B五项要求及当前八项验收表完成整模块证据复用和资格审查，明确模型/真实来源、保护性查询撤单/正式CTA自动续跑的边界。当前有限收口沿Root要求保持原保护，不开发UDR新增架构、数据库或准入机制；自动异常续跑等已有缺项如实保留，不能从Standard探针推定整个CTA恢复。自然跨夜和真实费税分别登记其证据范围，真实下撤单与生产切换继续按明确授权执行。

根组装可使用固定B入口（外部历史/待归仓路径：`../../build/ms-final-p29-root-handoff-001/HANDOFF-001.json`），SHA 2fcdae0dd56e84a294216ed314ab08872ecb147ccf5f0894c9a94b387910c2d3。WT单角色ROLE-ARTIFACTS（外部历史/待归仓路径：`../../build/ms-final-p29-root-handoff-001/role-artifacts/ROLE-ARTIFACTS.json`） SHA 6a4a9b7252a40db7326e430a910535ce15c1b1a41a0a8acf41a8cdd7ebc16e5a，23个wheel与已验WT安装/候选ZIP完全相同；Native描述（外部历史/待归仓路径：`../../build/ms-final-p29-root-handoff-001/EXECUTION-DESCRIPTOR.json`）绑定26个原P29成员，诊断Runtime排除。App/Host分别使用C/A自己的角色制品，保留不同Core/read版本；新安装使用已完成并固定的CPython锚点。该入口允许准备组装，whole_module_qualified和production均false；后继执行修改须以新制品和新资格交接。

后继选择P30组装入口（外部历史/待归仓路径：`../../build/ms-final-p30-root-handoff-001/HANDOFF-001.json`），SHA 601f49059fcd66a3c3cc2d977c3e940c8a12d8a11fe52cf7c882e4ef6c5fd151；其Native描述（外部历史/待归仓路径：`../../build/ms-final-p30-root-handoff-001/EXECUTION-DESCRIPTOR.json`）选择65成员P30包内26个Native成员，Standard DLL为694dc60b…，WT角色继续精确复用上述6a4a9b72…制品。独审f088e406…及安装后限定资格（外部历史/待归仓路径：`../../build/ms-final-p30-qualification-001/QUALIFICATION.json`）318fb7e7…随入口绑定。Root可据固定角色引用和Native描述准备组装；整体模块、完整WRI及生产资格仍false，P29原入口作为历史来源保持。

搬迁完整矩阵及delta完成后，选择P30后继002（外部历史/待归仓路径：`../../build/ms-final-p30-root-handoff-002/HANDOFF-001.json`），SHA f54b7ebed8f6ec38645f426779f50afd85715ea67920da295354eb7b50293b0c；资格v3（外部历史/待归仓路径：`../../build/ms-final-p30-qualification-003/QUALIFICATION.json`） SHA a29035efeef39db8ec335b3ca4fb943c1fc4f44168e9b4c0d157dce4557d86da明确普通/搬迁各11矩阵及各两代/七拒绝完成，准备整套测试，完整模块资格仍false。制品字节与001相同，仅新增实际搬迁资格和112绑定独审（外部历史/待归仓路径：`../../build/ms-p30-portable-matrix-001/REVIEW-EXECUTION-001.json`）。

### 未知恢复的跨owner缺口

职责接口（外部历史/待归仓路径：`../../build/ms-unknown-recovery-owner-interface-001/INTERFACE-001.json`） SHA 21d54d828014ab4099c668a846f865c74e94b7c1b2a3741f9c17127f7d79ce5d固定五个实际A003公共模块及Native准入位置。Journal沿原unknown记录保持阻断，Runtime/control、Source service/kernel及Standard各自锁存；只修改一处不能形成完整恢复。五模块所选方法与当前live语义一致，原源码保持。现有订单关联proof说明命令归属，业务效果、调用阶段和Native金融状态恢复分别需要明确合同。

下一实施须继续使用原Journal、原UUID和原始结果，依据当前正向券商证据定义按操作的责任处置，保留硬故障和未决责任；缺行、换Source代际或人工布尔值不能证明未调用。A负责通信/Source生产者，B负责Standard消费者及Native恢复准入，C只读呈现。当前接口登记缺口和验证要求，尚未新增解除实现或改变恢复规则，不重置新系统记录。

以上沿全部B-01至B-08和原并行总方案推进；当前库存从新基准开始，旧开仓与交易历史补齐已经取消。既有400期原生对照复用其有效证据。

### 历史故障与恢复续接

2026-10-29原生故障后继：[仓位条目生命期证据](../evidence/2026-10-29-native-position-lifetime.md)已将固定库原浮盈任务与容器增长缩小到8条目，64独立进程14次同函数故障，包含同次寄存器/6帧栈与错误回收；历史C同次根因仍待核。独立审查形成的[四核心文件历史候选](native-position-ownership-proposal.md)已按最新用户决定停止推进，实施0；旧事件串行提案保持撤回，原保存及行情调度保持。完整模块继续，既有实验记录保留，后续实际故障按现场处理。

该诊断已冻结为011诊断交付（外部历史/待归仓路径：`../../build/ms-runtime-fault-011/DELIVERY.json`），ZIP含231项，SHA为`030b060276c0edc59de8e5b7647873042744345a348797aca9865c36f0022f4c`；清单（外部历史/待归仓路径：`../../build/ms-runtime-fault-011/DIAGNOSIS.json`）绑定固定组件、原件、持久化诊断源及两份独立审查。归档校验逐项通过；该包用于复现既有组件故障，修复实现与产品稳定性仍待验。

此前已补齐[P21原生读取共享冲突贯穿首预算](../evidence/2026-10-29-native-stop-read-deadline.md)：固定安装exe使用1000ms原生预算，句柄实际拒读仍保持时约1.140秒发布stop_read失败，随后原物理关闭/双EOF及Host/source资源回收，无forced/pending；生产源码保持。其余P21失败场景及R11恢复继续。

该负例经独立审查（外部历史/待归仓路径：`../../build/ms-recovery-001/lock-through-deadline-002/REVIEW.json`）无P级发现，85项输入均在交付复核（外部历史/待归仓路径：`../../build/ms-recovery-001/lock-through-deadline-002/DELIVERY.json`）中重新匹配（SHA `1d66d00ccfb1a9889d2eefb0774dd0772192d1ab7b3ae8b4fd463c8d9f9e4677`）。测试父预算6秒并写入stop收据，只取得尚未解码阶段的原生读取首D负例资格，成功停止和父/原生相同截止另按各自原件验证。

2026-10-29后继：[P21隔离候选](../evidence/2026-10-29-native-clean-recovery.md)已完成安装产品同根两代A800/B400/用户KV/组合1200恢复且无重复SDK、活动单/真正SDK unknown阻断clean、七类恢复拒绝及当前五组合/正式configured兼容，独立审查绑定BUILD-010。沿原业务保存/原init加载，额外save及新增WT核心行为均0。公共控制读取器修正在独立App候选/精确patch内，仓库C源保持；须由C保留当前App合入后核消费者。P21其余异常、R11状态恢复、跨根责任和完整模块继续。C已报告的原Runtime访问冲突缩小到组合浮盈任务的仓位对象访问，实际寄存器/原生栈仍待捕获，原件及资格见同一后继证据。

当前a6的BT/RT比较及身份拒绝已验并独立审查，B-02/B-03所列正式结果链和五组合已有同Runtime后继；其余保留算法、完整资金/T+1/费用及B-05/B-06剩余恢复继续。P21原生两代及R12正式Python决策恢复保留各自固定身份，异常跨进程责任继续。保存接口审批请求已撤回，行情串行方案保持撤回；原交易责任、真实来源质量和统一A/C安装继续主线，框架多线程调查已结束。

## B-07原生同核桥实施顺序

以下保留R28此前实施顺序。当前400期对照结果沿上方B-07验收表及对应最终证据，当前下一动作沿上一节。

当前完整周期续接：A已交付逐日原生窗口主路径（外部历史/待归仓路径：`../../build/qmt-native-replay-001/MAINPATH-HANDOFF-001.json`），B使用本次六发行WT安装的原RR112类型，实际接收401个日基准、644808对raw/analysis并核所有交接文件/manifest；B接收收据（外部历史/待归仓路径：`../../build/ms-native-replay-consumer-001/INTAKE-001.json`）保持逐窗摘要及原historical_first_available/revision_history的unknown。该输入依赖已到位。原BT显式final-batch基准20261028与逐日current-view模型分别保留；下一步用相同日基准和原生状态/时钟接线完成400期完整决策/目标比较。B消费这些原生窗口，核相同计算时点的完整决策/目标，并单列BT日线与RT分钟调度、当前可见重建及最终批次模型的差异。B不重算复权OHLC、不把最终基准改标签充作逐日基准，也不把末日flat单点比较授为全周期通过。该交接保存在本正文，当前没有向其他会话发送消息或操作真实来源。

现有NRT使用Python子进程的ctypes同步回调和标准CtaStrategy Factory，原Runner首版限定空交易、单策略与synthetic；现有NSB直接消费configured纯核及NSQ。P20/R9已连接正式交易Session与标准Factory，R11进一步完成安装wheel中的固定业务配置入口/current a6/NSQ及原后继调度收敛。首profile为fresh现金ETF，完整恢复、所有保留算法及真实账户/来源资格继续独立验收。

1. 冻结本次STQ-P19 fresh制品后，将同一原生运行实现提供给受管Python子进程调用；生命周期继续原Session/Host/Job，复用现有ctypes回调方式连接唯一Python业务核。避免在C++重写算法或另外引入嵌入式Python运行时。
2. 从NRT自有代码收敛原上下文借用期、bars/price/fund/position复制及全向量setter接缝；保持原NRT synthetic/空交易入口兼容。正式产品显式选新的受管桥配置，回调配置在原策略工厂创建之前固定。每策略身份和允许读/执行集合分开，1..64策略共用原Session。
3. R11已在fresh现金ETF模型下沿原raw/entry/enum解释，实测初始flat→目标→原理论持仓700/可卖700/pending空并由原NSQ收敛；普通公开position的UNKNOWN标志保持。平仓/T+1/恢复各按同一原生语义另验，不把信号回显当作券商成交事实，也不因多次观察变化要求冻结行情。
4. C的[SCW配置版本合同](../specs/strategy-configuration-workspace.md)提供唯一configured配置、版本及冻结输入/目标样本，A提供上文9证券数据。原生BT和正式Session调用同一纯核/数量核，核完整目标、原生费用/理论损益与账户可用资金/可卖边界；缺辅助事实/单位/覆盖沿原资格拒绝，真实只读来源与隔离成交分别记录。
5. 完成实际策略配置→原历史/分钟→目标→隔离下单/撤单→原状态/绩效投影→App动作接口，再收恢复/异常和所有保留算法版本。候选新桥的公共接口、安装身份和实际同核结果形成后交C接线，不授未完成的实时状态。
