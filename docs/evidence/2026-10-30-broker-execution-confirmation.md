# 实时执行按券商数量确认与分单通信容量

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B NRT-R31实现与验证记录。状态：in-progress。目标及验收沿[实时规格](../specs/native-realtime-strategy.md#nrt-r31-实时执行阶段按券商实际数量确认)，事实所有权沿ADR-0001/0003；WT账本与唯一策略算法保持。自动初始库存的[已封存切片](2026-10-30-automatic-initial-inventory.md)继续保留原身份。

## 根因及实现

根交SRI003 main002固定原件中，SDK和券商查询均为四证券3000/2000/3000/3000，冻结目标为4000/9100/16400/20900。旧RetainedStrategy把原CTA理论量作为NSQ actual，理论量到目标后报告converged/frozen_buy_actual_confirmed。原公开交接DELIVERY001 SHA1980a12f486b600bd806d1ca2bc2bc478e30a76fc1406d503527c60e0cd73468。根QA的独立数量守恒报告SHA1bc77905182f846003319a738031b1d1b1ff7da9d43bf6dc68907836628c790a已确认原11笔各1000、回报/持仓/资金一致，本模块复用该结论。

实现限定execution_configured.py：保留原_capture理论观察和WT财务basis，新增_execution_capture把本轮已验券商P的数量/可卖交原NSQ推进。原理论pending信号独立；两观察和basis绑定同次原件摘要。原报告native_observation及broker_position_qualified=false继续表示兼容理论视图，新增execution_observation/execution_position_qualified表示实际执行来源。原绝对setter、活动订单/防重、原KV和恢复继续各归原owner，不新增金融归约或WT行为。

普通开发候选build/ms-broker-execution-install-001，0.1.0a12+brokerexecution.1，沿已接收A12及初始库存.4、C V1a8，四B源和七wheel按INSTALLATION.json绑定，760摘要RECORD。Job11364 exit0/6.718秒，树零/EOF/join/资源关闭通过。尚未最终独审或纳入统一候选。

## 固定反馈环

旧普通安装的_capture和原advance_retained在同次最终快照连续两次精确复现错误收敛，原件在ms-actual-convergence-repro002/003。正式broker_execution_confirmation.py实际执行完整RetainedStrategy.callback，仅复用同次已冻结纯核结果和Context原件，覆盖原观察、NSQ、setter及KV；旧版Job24960 exit1，精确报告converged并无setter；新候选Job58220 exit0/.423秒，改为buying/frozen_buy_ready且冻结目标不变。两次全回收，SDK和新增来源查询0。

后继green003沿相同回调进一步确认：原理论数量/可卖及NAV/现金/flag0损益原值保持，实际执行观察与券商一致，保存的部分成交阶段可恢复，P未知/过期不推进或新增setter，实际数量全部达到目标后才converged。Job64460 exit0/.429秒，全回收。该项为固定原件的受控回调验证，完整原生/SDK链与恢复仍分别验收。

## 实际1000份分单链和容量证据

短链复用原phase0市场原值及相同四冻结目标，保留1000份分单和原70秒观察预算，实际运行原Parser/Reader/CTA/标准Trader/WinSHM/SDK替身。当前源模型使用已封存来源的显式7日读取窗，仅供隔离复现；旧市场事实、启用时间更新和真实源资格分别标识。

native003再次实际完成11条1000份命令，策略保持buying而未误报收敛。随后POST /trade-commands收到一次503，原ID GET随后404；源Journal的11条金融通信记录占用196319字节，原配额200000，下一条最低约17847字节，容量确已无法受理下一委托。该次外层Job65564 exit1，全物理回收；未授正常业务关闭。原根main002的同类11条记录为196627字节、下一条最低17875，同样无法在200000字节内再受理。只读SQL前后原件SHA相同，没有删除或重放金融命令。

容量根因原件（外部历史/待归仓路径：`../../build/ms-broker-execution-diagnostic-001/CAPACITY-ROOT-CAUSE-001.json`）SHA79d1eb923833f9fbbdc492559d986c2c07b9da109e5111b3250c30ce4d867d1d；Job19656 exit0/.295秒，全回收。仅核容量和HTTP状态，原SDK守恒沿根QA报告复用。源503后的保守未知身份处理继续原Common；源拒绝语义与可操作错误需要相应owner按原合同核查，不靠404清除责任或换ID重发。

新QA配置沿既有公开能力声明完整运行容量：同次四目标至少52条子委托，私有绑定/公开trade profile同取64条，金融字节由完整命令/回执/metadata预算派生；ORDER/DEAL查询容纳全部原行，Host/Source/control三处读取容量沿原验证器一起核准，保持原时间预算。显式AAR读回收同根SRI003的1000ms capability，原金融记录保持。早期QA未选择该能力及闭合tick不足的失败原件保留在临时工作记录；当前native007正在验证新完整配置，不据前置通过推定实际目标已完成。

### 2026-10-31 后继容量、持续quote与时间范围

根明确授权按完整分单上界及金融/事件保留开销修正本次自有适配配置，单笔业务D、账户权限、资金、目标及1000份分单算法保持，旧金融Journal/原ID及未知责任保留。完整源模型的私有绑定/公开profile为64条委托、128条order/deal事件；Host事件128条保留及字节按原验证器共同准入，完整P/O/D返回能力、control完整消息/七个方向槽、只读Journal额度一起派生。早期单切片16条委托/32事件的容量不再作为完整分单配置。

native007/008/009/010/011/012的原件分别保存中间配置或短QA观察范围。旧Reader替身有64次history采证上限，行情采用持续quote推动分单、每组quote后再闭合计算；不通过密集虚构分钟耗尽该夹具。源AAR capability与原SRI003相同，新增故障注入代理已从完整主路径移除，产品直接连原Host。

原70秒观察窗下尚未完成全部52笔，记录为未通过。完整功能后继恢复原SRI003已有300000ms组件运行预算，保留原30秒业务链及10秒关闭D；外层仍为200秒有限Job，工作预算150秒。native013实际完成44笔，部分数量保持buying，Job47780 exit1且完整物理回收；未授完整目标或正常业务关闭。native014改用更长的同分钟quote组减少Reader采证消耗，正在同一有界范围验完整目标，原70秒全量到位资格继续单列。源码/Native前后SHA仍随各运行保存，既有失败原件保持。

## 剩余范围

完整实际52条分单到目标、原金融根正常恢复、卖出后买入/新代际/原pending及未知责任、普通搬迁与两轴独审尚需闭合；根A负责来源配置/整套组合，C持有只读投影。原400模型不重复，历史交易不补，真实券商下撤单和生产切换0。新增WT框架行为须沿既有明确批准边界。

## 2026-10-31 当前完整回报后继

前述native014等“正在”记录为当时进度，当前原件均已终态。native015实际52条分单到全部目标，但策略只观察37条成交便被旧QA提前断言失败；native016实际34条后原插件Timeout退出。修正QA完成条件为实际目标、执行阶段和完整52条映射回报同时成立。native018在原300秒组件/工作窗完成52条实际委托及目标，最后策略观察41条，工作截止失败；外Job46060 exit1、树零/EOF/join/资源关闭。540秒显式功能/恢复见证native019并未靠等待完成：约240.940秒、51条后原插件Timeout（5）、host3/session4/native0退出，最后策略35条；外Job22860 exit1且完整物理回收。单笔30秒和停止10秒保持。两轮HTTP全部为200/202，原70秒及300秒完整时效未通过。

同次标识集合核证位于build/ms-return-chain-proof-001/RETURN-CHAIN-001.json，私有完整集合另存并绑定SHA。native018的SDK/source/Host均为相同52条成交，Host104事件且durable/source_ack均104，最后策略只观察41条；native019相同51条在Host102事件，最后观察35条。已观察成交从源时间到Native接收时间的中位/最大延迟分别69.539/149.104秒、54.912/130.934秒。旧HTTP采证仅有页行数，缺Native after_seq，因此缺失记录在Native的接收/发布细分保持unknown；不能据此认定成交丢失。后继QA记录事件页序号、下一请求游标、逐轮策略观察和同一时钟锚点。核证Job70400 exit0/.477秒，原Journal只读且SHA保持，新增查询/SDK0。

native018共7081次HTTP，其中2954次trade-order-lookup。已确认自有TradeOrderLinks.lookup的完整SDK token分支遍历全部原委托并解码，原schema已有sdk_user_order_id唯一索引。独立候选build/ms-order-lookup-stage-002只改该专用Host文件，通过原索引定位候选后仍在原事务重新验证原命令、事件/query proof及冲突；WT二元身份路径保持，schema/金融记录/缓存新增均0。当前live Host正文保持原SHA，候选需独审、固定wheel及根组合后采用。针对性原触发红绿为ms-order-lookup-red-002（Job28012 exit1）/green-003（Job444 exit0/5.022秒），未知token不读取其它原委托、已知token只验证对应原件且返回证明与旧WT身份查询完全一致。stage001的游标迭代错误及首次QA对同一原件双次验证的过严计数保留失败原件；最终QA约束实际读取的命令集合。

阶段边界受控矩阵ms-actual-confirmation-matrix-005使用已安装原完整callback，额外通过未卖完不买入、实际可卖0、原pending冲突、后续经济代际等待及完整P缺行0；QA快照和产品/安装SHA在运行前冻结并核运行后保持，Job76492 exit0/.523秒，全回收。原core值仍复用固定同次结果，不授实际SDK或原clean恢复。现有有限full审查REVIEW-PROTOCOL-001/EXECUTION-001分别43/41绑定、新增开放P1/P2为0，覆盖原8份冻结输入；新矩阵、索引候选与完整回报后继待delta。

当前native021在原300秒场景/组件预算下使用唯一Host索引候选、原Native006及相同WT候选，验证52实际目标、完整回报、正常关闭和同根恢复；每笔/停止D、事实、目标、费用及原未知ID保持。该实际结果、完整链标识/游标与最终发行仍待封存。当前库存按R30新基准起步，旧历史工作继续取消。

### 最新有效结果与执行定位接缝

native021已终态：全部52笔实际到位约203.558秒，策略完整52笔回报约262.458秒（沿同一HTTP时钟锚点），Native后继请求游标104，首代closed.v2/原close-prepared均ok/recovery_ready、exit0。该次第二代已ready，旧文件Parser重播3234条tick后没有所需新调度，QA工作截止失败；整个两代场景未通过。后继QA封存旧feed并给新代提供后继tick，不修改原金融状态/源身份。native022在进入恢复前又以原Timeout退出，36笔、策略18条；最后页33–38在129.323秒返回，退出约158.412秒。native023仅显式将原Host单页上限4096→3072，完整事件仍逐条容纳，总保留128及原30秒/停止10秒保持；40笔、策略24条后Timeout，最后页49–52在174.401秒返回，退出约205.396秒。小页配置假设未解决故障，不纳入已验证运行配置。

这两次缺口已按同次ID集合、HTTP页序列与Native下一请求游标分层核对，见build/ms-return-chain-proof-002/RETURN-CHAIN-001.json（Job46540 exit0/1.473秒，全回收）。Host持久事实、HTTP已返回、Native完成页前缀及最后策略观察分别记录；HTTP尾页返回不直接证明SPI已应用。当前Timeout码5且原reason为空，尚缺具体超时任务/边界，不能由页间时间反推全部根因。自有插件的隔离定位候选位于build/ms-native-timeout-diagnostic-001/REQUEST-001.json：仅StandardQmtTrader.cpp、显式测试编译宏，沿现有diagnostics.reason输出固定边界/任务枚举，由现有Native原因SHA和117项静态字典读取；无公共ABI/账本/WT行为变更，live源码保持，尚未编译或运行。Native/Standard owner先核固定源/符号并装配隔离诊断，再定位原任务；不继续仅增加运行等待。

Host索引候选已完成普通离线安装build/ms-order-lookup-package-002，版本0.1.0a15+orderlookup.1。原根AAR WT角色23发行仅替换Host wheel，原59个Host成员58保持/1差异，1353条摘要RECORD与依赖检查通过；Job61736 exit0/14.333秒，全回收。安装后scaling002实际预加载原Host/Agent并核__file__在安装site，原SQLite证明查询通过；QA显式附加httpx测试依赖，产品依赖不变。安装后原lookup/ORDER-query-recovery/交易Journal 112项全部通过，654项输入保持，Job53012 exit0/76.661秒，全回收。未合入live Host或统一业务候选。

原112回归中的三个失败子案归于同一测试时钟：I/O截止使用setUp冻结的业务clock+1，后继子案开始时已经到期，无法进入预定SQL/fetch注入。完全未改Host的baseline复现FFF及外超时；QA仅将该测试每个子案的I/O D改为当次time.monotonic()+1，原六边界的注入、commit0/rollback1/close1及原记录断言保持。未改Host的baseline002单方法通过，Job57864 exit0/10.628秒；前后QA原件与源身份已冻结。此为测试时钟修正，Host产品差异仍仅索引定位。

matrix007在相同已安装callback追加同目标pending等待、实量卖清后买入及实量买全后交接新经济代，Job19944 exit0/.617秒。各非空周期沿固定同次原件提供，算法值仍缓存；该项授纯执行门与KV接线的受控资格，不授新的实际SDK周期或正常两代。普通Host及矩阵后继的独立delta沿build/ms-broker-execution-review-003/SOURCES-003.json登记，完整原生恢复、搬迁、统一当前库存整链及真实来源仍待。

### 2026-10-31 安装回归独审与隔离插件定位构建

review003两轴已封：REVIEW-PROTOCOL-003.json SHA9493dc2a5b543067b10893f4f5b6c1fb9c872008ef135533763721e4b5972dfb，726绑定；REVIEW-EXECUTION-003.json SHA837a28cd6f9f42a4f5d84810bd8152315ff9908aa758a8de2799fa669877a35f，131绑定。20份冻结输入、普通安装1353 RECORD、Host59源与112回归654输入均已核验，新增开放P1/P2为0。资格限矩阵门槛、索引候选普通安装及QA时钟修正，完整原生恢复、搬迁及当前执行超时继续缺口。

隔离定位构建build/ms-native-timeout-build-001已完成。先核Native006冻结640源与原Standard SHAe97d0af41c1e493785dd1b8ad0c8e70cb95ff942d36c4b8be8c1849969da5b1f，再仅重编测试宏所在TU，链接原14对象及原库共26项；源、链接输入与live Standard在构建后保持。生成诊断DLL SHAcaca3c7f5808a9ba9aa732e7d75fa3b47eb5aef1dcc993db2b3adf4a5c90d9b4。新执行制品副本26成员仅替换TraderQMTStandard.dll，其他25成员逐字保持，WT改动0；构建两进程75036/33204均exit0且完整回收，外Job57676 exit0/36.787秒。正式源及制品保持。该构建只提供固定边界/任务定位能力，具体失败仍须同原截止实际运行确认。

### 2026-10-31 原截止调度及回报查询容量

自有插件的固定标量后继在native026取得893条同次任务计时，按实例分代核对后，build/ms-deadline-inversion-proof-001/INVERSION-001.json登记93处较晚截止任务先执行的情况。最重EventResolve排队5,304,486us，本身执行31,507us，八项较晚截止任务占4,003,280us。该证据证明原队列中存在截止倒置；历史Timeout5的同次直接原因仍按原案保留，未由排队时间推定全部故障。隔离EDF候选沿[STQ-P27](../specs/native-qmt-standard-trader.md#stq-p27-单-worker-按原绝对截止选择待执行任务accepted隔离开发中)，原单worker、ID/D、容量及WT行为保持。14项选择红绿只授选择函数资格，原预算测试的未改源同样失败及旧submission状态探针缺口继续登记，完整业务资格按后继实跑。

EDF候选的native028/029出现新的成交回调异常。native030增加私有异常SHA及队列计数，在同一EventResolve trade回调取得used=16、maximum=16、waiting=15，异常SHA55142773d3d44e7f7f1911104b2f8198d7fcbb547226f0f93bd9c0e84c2a92da精确匹配`position refresh rejected`。原查询优先Adapter在成交后同步请求A/O/P，队列满使P刷新拒绝，原SPI保护进入SubmissionUnknown；这一候选故障的直接原因已定位在自有任务准入。原因证明build/ms-event-callback-cause-proof-001/CAUSE-001.json SHA5055ba7bbf2a118634143388c9dd2173888e0cc0573315dc2c2b852a4d6771e2绑定9原件；外Job33724 exit1、树零/EOF/join/资源关闭全部成立。该诊断只有固定摘要和标量，不输出异常原文或账户资料，真实券商调用0。

容量后继stage002在每个PageReady续段前取得三份查询名额和既有ordinary_advance银行，SPI成功入队时转为原真实任务；不足保持原PageReady/D，正常推进归还未用部分。build/ms-event-callback-capacity-tests-001沿真实公开Query入口及原callback guard完成旧红/新8案绿：原候选精确A/O成功、P容量拒绝；新候选等待、恰额、三查询、外部查询防占用、未用归还和停止回收通过。外Job61344 exit0/11.223秒，内部编译及红绿进程均完整回收。隔离构建build/ms-event-callback-capacity-build-002维持640冻结源/26链接输入/原14对象、其他25Native成员不变，外Job55496 exit0/10.854秒。此为自有插件候选，live Standard和WT保持原件。

独立双轴审查在stage002发现owner私有标志的访问顺序P2：外部enqueue先读event_callback_active、随后才判owner()，与owner锁外切换标志存在竞争。stage003先判owner()再读取其私有标志，生产SHA29fe0af91ab487f836251e499956fd6aea3576ed9848d49df6312c3695859f31，原stage002及native031输入保持。并发切换回归、最终源整链、两代恢复和最终安装后继继续；stage002有限绿例不授该并发要求。全部候选只在E盘隔离副本，自有Host/live Standard未合入，旧交易历史补齐保持取消。

### 最终普通源码与搬迁安装主链

最终stage005生产源码SHAcdc500770aae4a403d8dd24544300566113f037b45dc8fa51323c9a98cd4718a；新增audit_source_bytes=4224作为原init收费及persistent_event_bytes的唯一来源。最小可推进配置计入实际静态常驻、原audit-source、partition/context/chain、三回调查询银行、原普通推进银行及事件query的来源/最低身份工作空间。tests006的旧stage004 ByteRed在真实含4224的账单、context安装及完成值退费后，精确命中空队列event_ready=false；新源need-1拒绝、need立即可读页、legacy保持。旧callback容量红例继续精确复现，最终13案及2000次外部Query并发通过；外Job9524 exit0/14.864秒，全部编译/旧红/新绿进程回收。

最终源的原submission状态14案129断言、unknown状态49案2126断言通过，build/ms-capacity-original-state-tests-002/BEHAVIOR-001.json绑定运行前后两EXE摘要及原21输入清单；外Job30136 exit0/12.442秒。该资格限原私有状态、Common真实I/O之前，原预算oracle失败仍单列。两轴review003封存：协议SHA95cdb5eb493b17ccb2843cd7270da1e34244302fa680115c8018f6bf5f970c61、57绑定；执行SHA0d050e2ffca8845d1e3da8d36baaacd55db4688c8d5068e353c92d729aa50a93、65绑定，开放P1/P2为0。前两轮报告保留其当时发现。

ordinary编译build/ms-event-callback-production-build-002直接使用相同cdc源码，关闭诊断宏，无GH_STD_输出；保持原640源、14原对象及26链接输入，26成员只改变Standard DLL，其余25成员原样，WT新增行为0。native033同一正式Factory/Parser/Reader/CTA/唯一1.1.2/NSQ/原执行器/Adapter/WinSHM/SDK替身，按原1000份分单完成四个冻结目标、52真实替身调用及52成交映射。首代正常关闭后同Source/Journal/金融根恢复，原策略周期、目标、数量、NAV/现金/损益精确保持，SDK零新增；两份closed.v2均ok/recovery_ready、exit0、资源关闭。330查询，外Job64996 exit0/280.651秒、树零/EOF/join/资源全回收，原运行300秒/单笔与事件30秒/Native停止10秒及原外WRI配置保持。完整证明见build/ms-complete-broker-native-proof-002/COMPLETE-001.json。

离线B角色build/ms-portable-broker-package-001组合原Host索引wheel、自有runtime brokerexecution.1及C V1a8，23发行和26原生成员、两份生产源/差异及hash requirements共53成员ZIP，SHA7a464dd4dde39b6943e329439c8b96ab7d6fae20c32ffb8e63604aa03d79bb66、7,111,775字节。解压到新E目录后require-hashes/offline安装、pip check、正式WRI及库存CLI通过，1332条摘要RECORD通过；外Job55876 exit0/17.534秒，全回收。所有角色从普通wheel安装，无观衡App。

搬迁native034直接加载该新目录的原生组件、runtime、Host和Agent，QA仅改运输导入搜索路径，原业务源、四查询、SDK替身、回报和清理保持。89个实际加载guanheng模块全部来自搬迁site，仓库产品源导入0。再次完成52调用/52成交映射、334查询、同根正常两代和SDK零重复；外Job52704 exit0/284.650秒，所有资源关闭，1332 RECORD、ZIP及26原生制品前后0漂移。见build/ms-complete-broker-native-proof-003/COMPLETE-001.json及build/ms-portable-broker-package-001/MAIN-POSTFLIGHT-001.json。

build/ms-full-return-chain-proof-002/RETURN-CHAIN-001.json以同次SDK token、源成交ID、只读Host原Journal、HTTP序列及策略观察核两次运行：各52成交ID集合精确相等、104持久事件，首代Native下一请求确认前沿104、策略缺失0。第二代确认前沿6/已返回12分别保留，不把HTTP尾部当成已应用事件，也不声称第二代重放完全部旧事件。合成交易日与观察wall时钟分开，该证明不计算跨时钟时延；同次行情/算法及SDK调用时间范围仍沿原运行输入。

历史native032使用ordinary stage004，已完成52/52、首代正常关闭和二代精确状态恢复，二代WRI执行组件stop_timeout/forced/pending，整个场景失败；外Job27136 exit1且物理回收完整。其具体停止阶段未取得直接证据，按原unknown边界保留；本次最终源033及搬迁034成功不重写该历史。真实交易、生产切换、新WT修改为0。当前完整B仍须沿原规格核当前库存的实际差额/新成交/可卖调度、其余完整模块及统一SRI005组合；本候选交根装配，不把R31已验部分等同整个B完成。


## 2026-10-31 最终证据delta及固定集成交接

最终协议审查004（外部历史/待归仓路径：`../../build/ms-event-callback-capacity-review-004/REVIEW-PROTOCOL-004.json`） SHA `38c246525527d5cabb2bc1b6944fd57401578a3b10e7669d0b9b9c138cceb088`与执行审查004（外部历史/待归仓路径：`../../build/ms-event-callback-capacity-review-004/REVIEW-EXECUTION-004.json`） SHA `d14f884cf7d2eec9315fde63e023919ec00e88022f774c757ed04f015b2fa8aa`独立核57份冻结输入，分别311/156项绑定零漂移，新增开放P1/P2均0。交接前再次逐一核原件与副本、两报告绑定及检查点50项身份。

固定集成检查点（外部历史/待归仓路径：`../../build/ms-broker-execution-delivery-001/INTEGRATION-CHECKPOINT-001.json`） SHA `6efe44955c47744c84dbfd2d5969fdd860c7f2608578ed1e94102d0c0f60accc`绑定23发行、生产source/DLL、Host索引wheel、Native034实际入口/descriptor/SDK替身真值及控制和RESULT原件。最终HANDOFF（外部历史/待归仓路径：`../../build/ms-broker-execution-delivery-001/HANDOFF-001.json`） SHA `4a61ddf154323530cf22d795397b9f7e9084697eb89daaeb4d93ca5b8957dcbe`固定最终审查与全部接口，供根装配SRI005。原Common/WT与参考26制品闭包精确列出；根组合较新Reader/Common时继续绑定其对应ABI cohort。

本次资格覆盖普通033和搬迁034的限定SDK主链：52分单/52映射、104条首代已确认事件、正常两代及恢复零重复；二代确认6与HTTP返回12分别记录。包控制器为终态后封，实际main控制器为运行前封，二者身份分别保留。live Standard/Host源保持原摘要，新增WT行为、真实账户操作和生产切换均0。

完整模块保持active：R30-C2库存后续差额/新成交/首个合格收盘、可卖调度、周末跨日及来源交易日组合、R31-C3后继卖出及新经济代、SRI005统一候选和真实来源资格继续。旧032具体停止阶段unknown与旧预算oracle继续保留，后继成功没有覆盖其历史事实。当前库存规则沿[唯一方案](../migration/retained-strategy-takeover-proposal.md)：保留当次数量及可卖，旧开仓/交易/周期状态不迁入；启用后记录从新基准开始，正常重启保留新状态。
