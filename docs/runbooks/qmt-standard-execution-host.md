# 标准查询优先执行宿主

类型：开发与接入手册。范围：自有StandardExecutionHost装配、线程与安装消费契约。状态：C++模块已实现；限定SDK替身证据见[执行宿主验证](../evidence/2026-10-27-qmt-standard-execution-host.md)。原生CTA装配及其限定范围见下文，真实来源、业务策略及生产接线分别验收。

## 职责

账户查看可以在策略接管前使用独立WT的原生四查询发布入口。固定工厂、descriptor、环境变量注入和C只读定位沿[NAP-v1合同](../migration/native-account-publication-proposal.md)，实际安装及失败恢复范围见[证据](../evidence/2026-10-30-native-account-publication.md)。A在account_host之后装配该组件，C只读原帧并复用原账户投影。

[StandardExecutionHost](../../src/GuanhengExecution/StandardExecutionHost.h)是C++执行组件，组合原WT Adapter、Local执行器与自有线程交接桥。它使用原执行工厂和算法，持仓及订单读取原Adapter中的券商查询观察。外部共享内存通信Host由[常驻连接模块](../modules/qmt-connection-lifecycle.md)负责；本组件消费已配置的Standard插件，保持两者职责独立。

普通native装配保持原入口。显式选择TraderQMTStandard、order_context=query_first、position_by_query=true及执行器poolsize=0时，外层宿主才创建本组件。目标执行、自动清理及算法参数具有交易副作用，配置与真实运行按账户授权处理。

## 装配与线程

1. 外层在交易owner创建BaseDataMgr、ActionPolicyMgr、原WtExecuterFactory及owner专用IExecuterStub；可选IDataManager同样由owner访问。基础合约和会话信息先准备。依赖、配置对象和DLL至少保留至close确认；关闭未确认时保留至进程结束。
2. 从原Adapter实际使用的同一插件DLL解析find/pump/inspect/stop/deleteTrader及提交组函数，组成StandardPluginFunctions。避免同名DLL不同加载身份；原Adapter继续通过原module工厂创建API。
3. owner调用initialize，传入显式配置及有界ExecutionQueueLimits。false保留失败状态，仍执行close。初始化重复调用不产生新实例。
4. 取得共享command()交给原WtExecuterMgr或原引擎公开执行器入口。策略/行情生产者仅交付目标或行情值，原始WT对象可在回调后释放。桥的Engine stub与交易owner专用stub分别保存。
5. owner循环pump(max_events,max_commands)，先推进原插件完成，再在ready且写可用时有界交付目标。事件限1..64、命令限1..1024；返回非负完成/交付数或StandardQmtError负值。队列交付仅代表进入原执行器，委托结果由Standard继续持有。

原Local保持单线程运行；网络I/O由Standard原worker独占。本宿主不创建额外调度线程。跨线程仅允许command共享引用与request_stop；其他入口检查owner并拒绝越线程访问。status在非owner返回固定WrongOwner值。

## 执行时钟与元数据

[ExecutionEnvironment](../../src/GuanhengExecution/ExecutionEnvironment.h)实现原IExecuterStub，可供外层在交易owner创建后传给StandardExecutionHost。构造前装载原BaseDataMgr的session/品种/合约和相应日历；reference_session与所选原CTA交易时段保持一致。元数据和可选HotMgr保持稳定，生命周期沿宿主借用规则。

实时实例缺省用原TimeUtils的epoch毫秒，在owner以线程安全本地时间转换得到自然日期和HHMMSSsss，再直接调用原calcTradingDate取得交易日。它不读取另一线程的CTA可变_cur_*字段。observe返回同次样本；各get_*独立采样，不承诺两个调用的原子时点。执行时钟、策略闭合分钟和请求steady截止分别命名。主机时区及交易日元数据的来源资格属于实际部署验收。

显式Clock provider可注入冻结epoch做模拟验证。格式无效时钟、未知reference_session及非owner调用抛明确错误；2/3段代码先核原定长容量和非空段再交原CodeHelper。品种/时段查询保持原语义，未知品种返回空，成功不单独证明合约存在。其他来源格式扩展分别验收。要求见[STQ-P15](../specs/native-qmt-standard-trader.md#stq-p15-交易owner的原生执行环境accepted开发中)。

## 券商查询观察

受管CTA根配置可显式设置`observation_refresh: {"interval_ms": 1000}`，有效范围1000至60000毫秒，用于等待资金或可卖量变化期间继续取得券商P/A事实。完整初始四查询后，标准插件在原owner循环中依次补查资金、持仓；完整周期完成后再计时间隔。缺省沿原查询触发路径，启用时要求同批插件提供版本能力，旧插件在API创建前拒绝。配置及失败语义沿[NRT-R23](../specs/native-realtime-strategy.md#nrt-r23-等待期间的券商pa刷新)，实际安装和运行范围见[刷新验证](../evidence/2026-10-30-broker-observation-refresh.md)。该设置更新券商观察，跨交易日的策略会话及恢复资格分别核验。

query_orders/query_positions的0表示异步受理，后续pump推进响应。position/undone/orders读取原表的最近有效观察，不授本次同步刷新。orders返回新的WT容器，调用者按原约定release。查询失败、断开与未ready分别检查status及插件诊断；未知委托原身份留Standard，不按旧快照重发。

cancel(local_id)沿原Local及Adapter入口访问同一订单表。SDK替身验证与真实撤单授权分别登记。券商持仓、可卖数量和订单余量保持来源值，宿主不新增金融账本。

现金股票/T+1执行按原股票算法区分总持仓和可卖量，显式配置`WtExeFact.WtStockMinImpactExeUnit`及正整数`min_order`（现金ETF首模型为100）。自有宿主沿原工厂解析核参数，缺失/零/负数/小数拒绝；原通用MinImpact的已验范围限总量与可用量相等。可卖200只允许当前减仓200，策略目标及后续未完成调仓责任保持，完整退出和发行资格以[交易规则证据](../evidence/2026-10-29-execution-trade-rules.md)当前身份为准。BUILD003尚未替代冻结007候选，勿据配置示例直接切换真实交易。

## 停止与释放

外层先停止生产者；任意线程可request_stop关闭目标新准入。owner调用close，先确认桥无目标回调在途，再停止插件、detach SPI并等待原worker，核Closed/joined/drained后沿原deleteTrader销毁API。0表示确认完成，1表示仍待原owner完成，负值表示线程/关闭失败。重复close在Closed状态返回0。

未确认时保持借用依赖及DLL，由监督器沿同次进程截止处理；析构保留Impl避免悬空回调。原Standard已受理或未知命令保持原责任。关闭后的共享桥可拒绝迟到生产者值，不能再进入已销毁Local。原WT进程级存储与工厂卸载行为保持。

## 构建与安装消费

构建入口为[独立CMake工程](../../cmake/native/qmt_standard_product/CMakeLists.txt)，输入须为已核定、含input.json的固定上游及自有源码快照，依赖沿[构建手册](build.md)锁定。配置GH_FIXED_UPSTREAM_ROOT、GH_FIXED_OWN_ROOT、WT_DEPS_DIR及原Python依赖。

正式产物包括TraderQMTStandard DLL、GuanhengBrokerQueryContext静态库及GuanhengExecution/TraderQMT公共头。消费端还须提供同一原WT SDK的头、对象/库、匹配MSVC ABI和锁定依赖；该静态库不是独立WT SDK。

GH_STANDARD_CONTEXT_MAIN=ON构建限定主链驱动GuanhengExecutionHostMain。该探针显式使用ExecutionEnvironment的冻结Clock，仅供SDK替身验收；实际owner时钟和元数据按上文配置。实际安装后将GH_STANDARD_INSTALLED_INCLUDE_ROOT设为安装include绝对路径，构建GuanhengInstalledHostHeaders；它仅从安装目录取得自有头，验证公开头依赖完整。

范围及要求以[STQ-P14](../specs/native-qmt-standard-trader.md#stq-p14-标准执行宿主装配accepted开发中)为准。完整恢复、正式策略宿主、统一发行和真实来源资格继续分别验证。

## 原生CTA装配

显式创建[CtaExecutionSession](../../src/GuanhengExecution/CtaExecutionSession.h)才使用本组合；普通WtRunner入口保持既有行为。支持单策略入口及1..64个固定策略的集合入口，CTA poolsize=0，1..16个Parser及一个Reader；插件提供原stop/delete导出。当前装配不启动独立riskmon/notifier，连续来源和业务策略同核分别验收。

1. 进程宿主在首次WT插件初始化前独占新建生成根，调用原WtHelper::setGenerateDir。原目录getter缓存进程路径；同一进程保持同一根。Session要求尚无stradata/userdata/portfolio/outputs，原理论状态迁入另行验收。
2. 同一控制线程准备原BaseDataMgr/HotMgr、工厂及已Ready且未停止的StandardExecutionHost。Session必需非空HotMgr；无切换规则的现金股票可用原WTSHotMgr空实例。策略由原ICtaStrategyFact创建，Session构造成功后独占策略，关闭时仍经原工厂删除。
3. initialize传environment/data对象、Parser数组、策略参数和同一生成根。session/module/id等必需字符串、整数零poolsize、公共Boolean及嵌套对象先统一校验，所有活动Parser的id唯一；错误按Configuration拒绝并执行close。缺省active/check_time/align_by_section为false。插件私有配置由相应插件负责验证。
4. start先调用原engine.run，原上下文同步执行on_init，随后启动原Parser。原ticker/Reader闭合回调驱动on_bar/on_schedule及目标汇总；调用者保持owner pump。事件计数用于诊断，完整栈退出须最终join确认。pump观察原后台任务异常，关闭新准入且不重放失败任务。
5. 任意线程request_stop只发布停止请求并关闭执行桥。owner close先请求ticker停、确认Parser已停，再join原ticker/pool/tasks，确认Reader停，原工厂删除策略，释放contexts及插件，最后关闭执行宿主。0为完整收口，1为pending，负值为失败；策略删除false/throw不重复删除。依赖、配置和DLL保留至确认，未确认时保留至进程结束。

原engine.stop可能等待在途原回调，因此局部timeout_ms并非整个关闭时限。外层受管进程沿原截止和Job回收。Parser/Reader pending、删除异常、回调重入关闭和原任务故障等具体异常资格按证据分别登记；插件热卸载不在本组合范围。

多策略时，向构造函数传vector<CtaExecutionStrategy>，逐项提供strategy、factory与可空Object参数；随后调用四参数initialize(environment,data,parsers,output_directory)。旧五参数initialize只适用单项集合。全部策略共用同一执行宿主，生命周期内保持参数存活且不改写。策略ID的ASCII/Windows名称约束及失败所有权见[STQ-P17](../specs/native-qmt-standard-trader.md#stq-p17-同账户多策略固定集合accepted开发中)。程序初始化期间更改策略ID会按Initialize拒绝；同进程第二Session在接管策略前拒绝。多个进程使用同账户仍需由部署入口保持唯一执行责任。

策略退场先由该策略将自身目标归零，原引擎仍把其余策略目标相加；本接口的集合在启动后固定。继续拒绝已有CTA状态根，完整恢复另验。相同标的混有手工持仓时先明确保留量与管理责任；外部订单未计入当前本通道原执行订单表，原MinImpact的启动取消也需单独核查，混用安全性保持待验。

GH_STANDARD_CTA=ON仅构建可安装的GuanhengCtaExecution静态库和公共头，缺省关闭。GH_STANDARD_CTA_MAIN=ON另启隔离主链驱动、确定性Parser/Reader及同输入原算法工厂。实际安装的CtaExecutionSession.h按GH_STANDARD_INSTALLED_INCLUDE_ROOT参与公共头消费编译；链接仍需匹配的WT原库/SDK，本安装不是完整独立SDK。

主链入口为tests/integration/qmt_cta_execution/run.py，显式传exe/dll/factory/parser/reader/output和deadline-uptime-ms。--configuration-case用于同一实际Ready宿主的错误配置拒绝，四查询、零提交且行情插件未加载。正向以真实WinSHM运输连接SDK替身，执行时钟冻结在模拟账户日，原ticker行情日期另行显式注入；结果仅证明组件流转和正常关闭，真实交易日一致性、连续行情、业务策略、多轮恢复和正式发行继续验收。详见[限定验收](../evidence/2026-10-27-qmt-cta-execution-session.md)。

原JSON加载器省略null字段，因此可选Boolean的JSON null沿缺省false；Session无法区分已被省略的null和缺省。Parser.active为空时按未活动处理，全数组无活动Parser仍拒绝。当前装配要求带类型的WTSVariant配置；原YAML加载器把标量转成字符串，未取得本装配资格。

输出根的`.cta-session.lock`只由Session持有Windows独占句柄，文件存在本身不表示占用。OutputBusy表示另一个句柄仍占用，应保留原实例并核查生命周期；初始化拒绝仍须close。完整close后可由下一进程取得租约，目录中的原CTA状态仍触发Configuration拒绝，禁止以删除JSON或换空目录绕过未决交易责任。接口与验收见[STQ-P18](../specs/native-qmt-standard-trader.md#stq-p18-输出根单写者与两代停止边界accepted开发中)。

专属生命周期验证通过--session-case选择output-busy、reader-pending、parser-pending或schedule-inflight。两代验证先用--portfolio net产生原状态，再用--session-case restart-state与--restart-generated指向首代generated目录；夹具核全部原文件哈希保持、实际下撤单替身调用0及第二代资源回收。插件停止阻挡导出只存在CTA专属合成插件，GH_STANDARD_CTA产品库及普通native入口保持独立。

## 配置驱动产品入口

`GH_STANDARD_CTA_HOST=ON`构建并安装`app/GuanhengCtaHost.exe`、`app/traders/TraderQMTStandard.dll`和`app/executers/WtExeFact.dll`，复用同一Session/Host及固定原库。原Parser/Reader/业务策略DLL、基础资料、匹配Windows x64运行库和实际来源另按各自已验身份装配。隔离Target策略属于验收夹具，真实业务同核接线继续按NRT及模块B推进。

原生配置schema为`guanheng.cta-execution.v1`，字段固定为installation_root、output_directory、base_data、trader、executer、environment、data、parsers、strategies、budget和queue。installation_root指实际安装app绝对目录，全部模块及base_data使用其内部相对路径；base_data显式含sessions/commodities/contracts/holidays/policy。strategies每项包含id/module/factory/name/parameters，固定1..64项。启动/关闭预算各1000..60000ms，运行预算1000..86400000ms。账户、凭证环境名及执行授权仍沿原Standard配置。

后继P21候选增加可选`recovery:{"mode":"record_clean"}`或`resume_clean`，缺省沿上述fresh行为。query_first且savedata=false的固定配置可选，同根恢复绑定相同业务配置/安装/原金融文件及上一代成功关闭收据。停止沿原业务事件已保存的状态，不增加最终save；活动单、unknown或未决责任均不授clean。显式模式成功时closed.recovery_ready才可为true，缺省仍false。后继R12已接通正式configured策略：通过原用户KV保存原NSQ冻结决策，当前固定配置同根两代恢复A700/B700且二代新增SDK0；缺少state扩展的旧策略桥保留fresh兼容，显式恢复在gh_cta_run及策略创建前拒绝。DLL装载与运行入口调用分别记录。候选App公共reader只在隔离wheel验证，须由C合入；具体验收/缺口见[P21证据](../evidence/2026-10-29-native-clean-recovery.md)与[R12证据](../evidence/2026-10-29-configured-quantity-recovery.md)，完整恢复资格继续in-progress。

App薄适配候选为`guanheng_app.execution_process`；先由打包步骤对完整安装写一次`execution-install.json`，再使用同一安装的wheel调用：

```text
python -B -m guanheng_app.execution_process --installation <绝对安装根> --make-manifest
python -B -m guanheng_app.execution_process --installation <绝对安装根> --config <固定配置JSON> --control-root <已存在私有控制根> --seconds 60
```

`ExecutionProcessConfig.load`冻结配置SHA和逐工件摘要，`ManagedExecutionProcess.start(绝对monotonic截止)`启动原生exe，request_close/close沿原ManagedLocalProcess/ProcessJob。安装树加载及运行期间冻结，变更后通过完整停止和新代安装交接；库集合在加载与实际创建进程前均复核。输出每管道256KiB，超额停止并继续排空；关闭后清除私有缓冲。

产品ready/closed收据绑定control_id、配置SHA和实际pid；ready仅证明本代装配启动。closed的ok、固定error_code阶段及recovery_ready分别表达运行结果与恢复资格。fresh及未获恢复准入的profile保持false；010显式原生record_clean/resume_clean仅在P21完整责任准入及成功关闭后返回true，完整P21及模块资格仍未完成，003历史候选保持原合同。父进程另核树归零、EOF/join/句柄关闭，父错误如unexpected_exit与子收据阶段分别保留。缺省已有状态根继续拒绝；显式resume_clean沿P21核验并消费证明。原文件及命令身份保留，禁止删除状态或更换空根绕过未决责任。产品账户mutex仅证明同一账户/环境/profile的当前进程互斥，跨根持久恢复仍待验。

实际安装隔离入口为`tests/integration/qmt_cta_product/run.py`：显式传installation/app-package/strategy/parser/reader/output及deadline-uptime-ms；portfolio选择add/exit/net/pending/partial，startup-case选择existing-state/account-busy/trader-container。它从安装wheel导入App、复制实际安装、走原Factory/ticker/执行与真实WinSHM运输；业务和SDK来源均明确为替身，不授实盘或自动恢复资格。

P20将exe正文收敛为同安装的`GuanhengCtaRuntime.dll`，公开头CtaProcess.h；exe传空health调用同一运行C ABI。标准`GuanhengManagedStrategy.Core`及ManagedStrategyBridge.h在原Factory创建前冻结固定回调表，原epoch内复制上下文值，生命周期保持至原close/join。原NRT ABI独立入口保持。

隔离业务验收加`--python-callback --business-core <固定原NRT构建根> --fast-clock`，当前Python必须已安装原configured核0.1.0a5/NSQ0.1.0a1/tzdata2026.3。该模式复用原输入生成器、Helper/day Reader和分钟HTTP夹具，双策略各显式50000元合成预算，原净额买1400份。`--python-callback --callback-stop-failure --fast-clock`重现停止等待期间回调失败。它们属于专用验收装配，正式安装子进程配置入口继续开发，详见[证据及限制](../evidence/2026-10-28-managed-cta-business-kernel.md)。

## 固定业务Python入口

实时费用模板应为每个配置品种显式声明byvolume及open/close/closetoday。当前实时商品只支持这些费率和原到分规则，minfee缺省或0保持原语义，正值在自有资料准入时拒绝；BT最低费用保持其原能力。按份和金额的实际卖出费用、原WT损益及源账户查询分别核实，见[NRT-R25证据](../evidence/2026-10-30-retained-native-fees.md)。真实券商费率和策略费用预留由部署明确给定，账户commission与原WT费用分别呈现。

当前唯一保留1.1.2使用`guanheng.retained-cta.v1`，具体输入/恢复范围沿[NRT-R18/R19](../specs/native-realtime-strategy.md)。可选`parameters.python_strategy.market_window`为`{"path":"E:/controlled-runtime/analysis-window.json","max_age_seconds":3600}`，数值由部署按来源接收时效明确选择，范围1至604800秒。缺省保持冻结输入路径。文件格式沿A的QNA v1，发布者负责完整原子换名和有界共享冲突重试；桥每轮读取一代，仅替换三个市场输入字段，原周期、本金、配置及持仓保持原owner。

日线Reader容量应覆盖声明窗口及一条窗口外bar，桥单次上限4096；连续增长窗口应提前配置足够容量。缺文件、接收过旧或原Reader未匹配时观察为waiting_market_input，零新增目标；校验失败继续沿原health停止。观察包含原发布SHA、来源/因子版本、基准日和known/received时间。C消费方需合入同批状态白名单候选。安装运行范围及真实持续发布缺口见[窗口消费证据](../evidence/2026-10-30-retained-market-window.md)。

需要读取当前券商数量时，安装Runtime的可选R17扩展配合同版execution_strategy：CtaRuntime.broker_observation可复制当前冻结值，策略INIT/SCHEDULE内也可通过CallbackContext调用。返回独立的已知标记、持仓/资金修订及本地接收时间；balance/available未知时为None，完整空持仓查询为已知空集合。读取没有查询或交易副作用。broker_unavailable表示当前没有可发布观察，broker_capability表示所装旧DLL缺扩展，不能把任一错误替代成零持仓。该值与原策略理论Position分开使用；实际安装及能力边界见[R17证据](../evidence/2026-10-29-native-broker-observation.md)。

正式受管调用使用安装包的`PythonExecutionProcessConfig.load`及`ManagedPythonExecutionProcess`，保持原执行安装清单、账户配置、Job、停止预算和收据。父端自动以隔离Python进入安装的execution_configured模块，JSON不接模块路径或任意脚本。每个ManagedStrategy.Core的parameters.python_strategy包含schema、绝对input_file、input_sha256、main_symbol和0.1至5秒evaluation_seconds。

`guanheng.configured-cta.v1`只接原FrozenSessionInput/configured1.2.0；`guanheng.v2-cta.v1`只接原nsb-v2-input-v1/V2 0.1.0。两者沿同一领域owner准入、原Reader闭合输入、NSQ及原策略账本。V2首域为显式冻结历史窗口；跨窗口更新、持续实际来源与资金/T+1分别验收。恢复显式选原record_clean/resume_clean，同根原责任准入及原用户变量保持，额外save为0。

当前002开发包需外部CPython3.12 Windows x64。用普通`python -m venv --without-pip`建立新环境，再由受控安装器沿包内requirements-lock.txt和wheels按SHA离线安装；回测安装拒绝隐式.pth/pyc。固定发行、两种profile的搬迁两代及完整边界见[V2后继证据](../evidence/2026-10-29-v2-native-bridge.md)。固定Appa10切片与当前统一Appa18接线分别登记，真实交易及生产切换继续按明确授权执行。

[当前App003开发包](../evidence/2026-10-29-current-app-native-composition.md)提供Appa19及完整35个锁定wheel，沿相同普通环境和离线安装流程，configured/V2搬迁两代已验。包内V2资源为交C集成的精确候选，旧002及冻结007仍保留。两个严格实时profile均在原生装载前拒绝非空historical_model；显式研究BT继续用HEM入口和研究scope。实际观察版本的历史预热沿C后继领域契约接线。

原生分钟/新行情插件的隔离组合在上述run.py正式configured装配上增加三项显式参数：`--native-minute-reader <A固定DLL>`、`--native-minute-root <原生分钟只读根>`、`--native-quote-parser <A固定ParserQMTHostV6.dll>`。三项同时提供，继续声明`--configured-python --business-core`及原安装/截止参数；验证使用实际分钟、冻结合成日线与FullTick/券商替身，等原自然分钟触发调度。首代声明210秒总测试预算及原生产停止预算，不使用fast-clock替代自然分钟。切片结果及源数据身份见[R14组合证据](../evidence/2026-10-29-native-market-cta-composition.md)，全真实来源与生产切换分别验收。
