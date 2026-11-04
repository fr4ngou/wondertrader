# 原生实时策略接入

类型：功能最终规格。状态：accepted。前缀：NRT。依据：[NSK](native-strategy-kernel.md)、[NSQ](native-strategy-quantity.md)、[NSH](native-strategy-host.md)及用户要求的同核回测/运行和原生能力复用。实现与合成、真实来源、运行发布资格分别登记。

## 原生接缝与职责

复用 WT-S01/S02/S03 的 CtaStrategy/ICtaStrategyFact、原 WtRunner/CTA ticker/上下文；历史沿 WT-D03/D04 的原 IDataReader/WtDataReader 及已验 StrategyReader。工程基线为固定上游08b230dd05facf6d650d949bfe51054115a2ecb1，仅叠加用户已批准的 CORE-004/CORE-007；本功能新增框架修改为0。公开能力和边界按[原生目录](../development/wondertrader-capabilities.md)核对。

纯策略算法保持 guanheng_strategy_core / strategy_v2 唯一实现；C++拥有标准插件、上下文访问及原生生命周期，独立Python子进程同步调用纯算法。父宿主继续复用NSH的Job/单总期限/管道及输出预算。新增实时受信入口需显式版本与发行身份，原回测入口保持原契约。行情、持仓、资金、信号、撮合与执行器沿WT拥有，不增资金账本、审批流或数据库。

## NRT-R1 固定装配与启动准入

自有GuanhengRealtime DLL同时提供标准Factory GuanhengRealtime.Core和薄C ABI。独立子进程以绝对路径加载，原Runner从同一个cta目录扫描同一模块；运行核共同owner身份、唯一Factory/策略/ctx。固定宽度/pack8布局实际probe后才消费，禁用wtpy和裸C++对象跨语言传递。

配置/启动/最终stop由创建控制线程拥有；配置先验证managed_stop=true、CTA、poolsize=0、单一策略、空traders/executers及关闭risk/notifier。状态和输出根全新独占、无重定向，禁止加载旧positions/signals。模块集合、路径和SHA在原Runner读取配置前核实；新的算法/插件不能绕过受管发行准入。首片source_scope为synthetic，正式来源须另验，通达信交易及真实委托保持关闭。

## NRT-R2 原生回调及借用期

init/session/bar/schedule等回调由原引擎实际触发。event携带版本、阶段、epoch、context_id、Windows原生thread_id、原date/time/tdate及有限bar值。每次回调使用独立借用能力，C ABI在本次相同线程、ctx、epoch和允许阶段内读取；回调返回即失效。init与计时/行情回调可以在不同原生线程，不能借用NSB单Python线程假设。

on_init登记主m1历史及订阅；on_bar只复制通知，不读主bars清除closed标志。on_schedule读取当时完整闭合前缀，同步调用唯一业务核及NSQ，再提交。ctx、slice及tick指针不能存入Python或发送到另一线程。回调异常在两边捕获并锁存失败，后续目标提交关闭，callback只能request_stop。强引用和DLL保留到原生产者排空且进程退出。

## NRT-R3 原生历史与因果

自有标准IDataReader仅负责组合路由和生命周期：默认m1/onMinuteEnd复用StrategyReader，显式minute_native配置沿[原生分钟接缝](native-minute-reader.md)复用WtDataReader，d1复用原WtDataReader。原索引、复权、缓存与文件格式不复制；组合器提供真实stopDataReader，关闭准入并核在途调用、切片与delegate存活顺序。原Reader无stop导出不等于可空实现stop。

日线从已冻结原生文件或原IHisDataLoader读取；按原上下文当前截止核日期，排除未收盘当日及未来值，完整预热不足明确拒绝求值。QMT主动读取文件的限制只约束终端策略，WT外部读其原生文件属于正常职责。本功能不新增日线下载任务、分钟聚合器或数据库。跨日刷新、修订与完整覆盖按实际验收授予，不能靠一次冻结文件证明持续就绪。

## NRT-R4 原生事实与完整目标

ctx复制原price、funds、position/detail/valid及enum结果，明确原字段和unknown。RT enum含pending覆盖，get_position在新/已有证券语义不同；不可直接复用NSB CtaMocker事实解释。通过原ctx实际验证initial-flat、pending、actual+pending、平仓与T+1后才授对应NSQ映射资格。NAV/初始本金及手续费显式配置，算法与数量转换共用原核，不保存第二份持仓或资金账本。

setter接收已完整预验的execution向量（符号唯一、数量有限及上限、阶段和epoch有效），一次校完后沿原ctx逐项设置并回读。void setter没有跨证券事务，异常/回读不一致锁存incomplete，保持已发生事实，不做假回滚；失败后零新增setter。

## NRT-R5 并发和来源资格

pool0仍有parser与ticker计时来源，桥锁或GIL不构成原引擎全局一致性保证。首片使用标准IParserApi的测试专用合成插件，同步feed返回证明完整SPI链返回；无新feed的可观察窗口内由原ticker推进调度/采集。真实持续行情、pool2及账户执行并发分别验，合成静止交错成功不授这些资格。禁止直接调用策略schedule伪造原生分钟驱动。

正式行情沿ParserQMTHost与已核新内存策略接入；终端外HTTP与已退役终端内HTTP区分。本次合成插件不访问网络/QMT/账户，不成为正式行情回退。数据、配置、算法及源身份随每次观察保留。

## NRT-R6 正常退出及硬边界

复用已批准NCS：停止ticker准入、parser排空、ticker/pool/base任务、reader、策略与ctx按原顺序关闭。stop_pending保留完整owner，控制线程在同一NSH总截止内继续观察；回调内不join。阻塞调用由父Job硬边界回收，强杀/退出异常标incomplete。停止请求、stop返回、析构、进程退出、后代归零和管道EOF分别取证，禁止热卸载。

## NRT-R7 结果与独立发行

实时报告使用独立schema，保留算法/源码/输入身份、回调时序、可见前缀、原核decision、数量与完整target、原生回读及停止事实；有限容量达到上限停止准入，不无限累积历史前缀。复用NSB已修的共享线性历史与Decimal独立上下文。

构建冻结固定上游blob、批准覆盖、明确自有闭包和依赖锁；禁止把当前脏树中的未批准CORE-001/002/003/005/006编入候选。独立安装、搬迁、父死亡、并发、异常、HTTP/中文入口及真实来源资格均需匹配当前制品身份。

永久源码干净构建细则（NRT-R7-C1–C4）沿[执行组件构建入口](../runbooks/standard-execution-build.md)：

| ID | 要求与验收 |
|---|---|
| NRT-R7-C1 | 自有执行源码取永久目录，WT取固定Git对象和既有批准覆盖；逐文件核基线/覆盖结果/依赖锁，隔离快照中的相邻WT头来自同一固定来源。旧build源码仅作历史比对 |
| NRT-R7-C2 | 在全新输出根编译完整Host依赖及五运行组件，项目对象/库全部由本次源码生成；公共DTO变化按当前布局和实际sizeof重新核银行并同批编消费者。旧部分重编资格分别保留 |
| NRT-R7-C3 | 以实际linker显式输入收据和完整库搜索轨迹联合核项目库及对象DEFAULTLIB/响应文件；工程二进制限本次构建，系统库限明确VC/SDK根；外部编译链接选项及额外库搜索不得隐式进入 |
| NRT-R7-C4 | 入口固定本次操作截止，工具链探测、Git、依赖准备/复核和编译安装由入口在剩余截止内拥有对应Job；失败/过D后停止下一阶段并回收实际后代。全部输出E盘，物理清理与操作及时性分别记录 |

## NRT-R8 验收

实际编译/ABI/同DLL Factory owner；错模块/旧状态/非空交易配置前置拒绝；跨线程/过期epoch/错误阶段/超界数组拒绝；slice复制及释放；同ctx d1与m1主线闭合/因果；原ticker触发共享算法与完整target回读；原RT pending/actual/T+1区分；异常、callback请求停止、阻塞回调保活、Reader pending/失败；正常stop析构/进程及Job回收、父死亡/单总期限、正式安装和用户链分别验收。实现与未验差额见[当前任务](../roadmap/NOW.md)，静态接缝调查见审计原件（外部历史/待归仓路径：`../../build/guanheng-workspace/native-realtime-seam-audit-001/REPORT.md`）。

## NRT-R9 同账户固定策略集合的业务回调桥

模块B产品宿主按STQ-P20提供唯一运行DLL，Python子进程在启动前注册标准`GuanhengManagedStrategy.Core`工厂的1..64个固定回调绑定。每绑定冻结strategy_id、主m1证券、1..16个允许读取证券及1..8个完整执行证券（均属于允许读取集合）、同步callback和opaque user；配置ABI/pack8/实际layout核验后才消费。首次创建策略后关闭新绑定准入，删除只沿原Session/Factory；回调强引用、配置及模块保留至原join/关闭或进程退出。

所有配置证券在进入原CodeHelper及bar key前核2/3个非空ASCII段、整个代码小于原32字节容量；第三段单独`+`/`-`复权后缀拒绝，沿原CodeHelper实际常量避免后缀剥离后的空段读取。配置拒绝保持未创建策略、未订阅、未调用setter。

事件和值结构复用GhRtEvent/Bar/Facts/Position/Target，epoch仅在本次原OS线程/本策略原上下文有效。与原NRT共用ContextAccess值复制和全向量setter正文，读取actual/pending的资格保持原未知状态直至真实回调实验通过。策略只委托回调给唯一Python核，额外金融账本0。

原init登记读集合与主分钟事件，Python init在原上下文登记主m1窗口；bar仅复制，schedule采集完整闭合前缀并调用原业务核/数量核。原RT并发能力按NRT-R5验证，观察到重叠回调时锁存失败并关闭新setter，避免假定GIL为引擎一致性锁。失败码、活动回调数、创建/删除数、调用/setter数只用于有限诊断；health读取这些原子故障位，交唯一产品owner停止和收口。

验收沿正式产品DLL→标准Factory→原ticker→同一configured纯核→NSQ→完整向量→组合/执行/WinSHM，包含1策略和同标的2策略、错epoch/线程/阶段、错误绑定/数据、部分setter/回读失败、重复配置和回调异常。原NRT ABI1 synthetic入口逐项回归，生产准入继续受真实来源/账户/恢复资格限制。

## NRT-R10 安装Python薄适配与公开回调

`guanheng_app.execution_strategy`提供标准库ctypes薄适配，绑定同安装的GuanhengCtaRuntime及GuanhengManagedStrategy。构造先核实际ABI/layout，再冻结1..64个StrategyBinding；回调强引用保持到run返回，原工厂创建后由原生拒绝追加。调用者只给值与显式Python回调对象，产品JSON不接受动态模块、脚本或任意loader。

公开CallbackContext只在当前原OS线程/epoch/事件阶段读取facts、price、position、bars及提交完整target；每次返回独立冻结值，退出回调后立即失效。异常在Python回调边界锁存有限错误类型，返回非零给原health；它不提供成交、现金或恢复确认。position保留raw、entry、enum及原UNKNOWN标志，薄适配不自行提升实际/pending资格。health继续直接传原生原子入口，避免在owner pump增加Python调度。

run使用原9项argv，生命周期及关闭由原运行体/外层Job拥有；安装目录和模块摘要由ExecutionProcessConfig及同一安装清单准入，Python薄适配不另外加载来源模块或账户配置。原生ABI模型以公共头为正文、安装DLL的layout为运行核验，测试直接消费此适配，避免测试私有ABI模型成为唯一可调用入口。验收包含安装wheel中模块、原Factory/完整业务整链、同线程/过期/错误阶段拒绝、回调异常及正常/异常关闭；正式配置驱动子进程和真实数量观察按后继完整要求继续。

薄适配在加载DLL前核原配置SHA及ManagedStrategy.Core的模块/Factory/name，策略ID与Python绑定一一对应；错ID、缺少绑定或普通C++策略配置均拒绝。模块读取、实际加载及逐项注册沿同一显式monotonic启动截止；run保持配置创建OS线程。epoch约束借用期与调用线程，每次值复制不授多次读取的事务快照。按用户明确要求，行情处理及CTA调度沿WT原生方式，不增加回调期间行情冻结或跨字段事务快照要求；字段解释和策略计算结果按实际原生调用链验证。

## NRT-R11 固定业务配置的受管Python入口

模块B新增薄适配候选`guanheng_app.execution_configured`，交模块C集成；父生命周期继续ManagedExecutionProcess/ProcessJob，显式选ManagedPythonExecutionProcess。它使用同一普通安装Python的`-I -S -B`及固定bootstrap，只加入绑定site并进入`guanheng_app.execution_configured`；原配置及control身份不变，原生exe入口保持现有行为。父端将解释器/运行库/venv配置及App、core、NSQ、V2、signals、variants、tzdata七包实际源码集合绑定至本轮控制目录，子端沿父原启动截止重验并核实际导入路径后才创建策略。私有pycache路径隔离已有缓存，跳过.pth/sitecustomize，额外遮蔽源码拒绝。启动失败、原回调异常和完整关闭继续沿原收据与Job回收。

每个ManagedStrategy.Core的parameters.python_strategy固定schema `guanheng.configured-cta.v1`，只接受input_file、input_sha256、main_symbol和evaluation_seconds。input_file是已存在的有界绝对路径，内容复用现有NSB FrozenSessionInput与decode_session；其中唯一configured核、完整原生代码映射、raw日线单位/字段/来源、理论资本和费用预留均沿原DTO。此入口不接受调用方模块、脚本、工厂函数或命令。初版接configured 1.2.0；其他保留版本继续接其唯一核，完整模块资格按全部范围另验。

原Session当前只接fresh状态根。各策略init先确认原本策略无持仓/目标、entry及PnL均零，登记原主m1；每次schedule复制原tick价、完整d1并核冻结输入，再调用唯一evaluate_history和NSQ.advance，完整向量沿原setter提交。策略独有理论实际量由原raw/entry解释：有原开仓明细时取raw，无明细时取0；enum给出原目标。该解释限已确认初始flat的现金多头原CTA上下文，券商账户持仓继续由查询拥有。原生不相容观察停止本次计算；行情与原调度继续原方式，不授事务快照。策略NAV按显式理论资本加原flag0 PnL，现金按同次原理论持仓/原价派生，原费用/绩效保持WT计算；来源和费用缺项沿原NSQ等待规则，不新建账户账本。

交易规则按实际安装正式入口分别验收：R11-T1将原commodity.trademode设为T+1，核当日原理论实际量与可卖量及独立券商查询；R11-FEE配置原非零费用模板，核原策略交易文件/累计费用、flag0损益和派生NAV/现金；R11-CASH以显式费用预留形成整组资金不足，连续原调度保持waiting_cash、空提交向量与SDK零调用。上述理论预算与券商账户available分别标明来源；柜台真实可用资金、可卖边界以及卖出/跨日资格继续经正式通道验收。

子端有限strategies.json为当前决策/原值投影，WT原策略/组合文件继续承担持久金融状态。验收从安装wheel的正式模块进入，当前完整依赖check通过，双真实configured核到原净额/隔离SDK、连续后继调度、输入SHA/未知profile拒绝、回调失败与完整资源回收；恢复及真实来源/账户资格分别保留。

## NRT-R12 原用户变量中的数量决策恢复

模块B通过自有ManagedStrategyBridge转接原`ICtaStraCtx::stra_load_user_data/stra_save_user_data`，固定键为`guanheng.quantity.state.v1`，每策略上下文独立，最多32768字节可打印ASCII。新增state扩展ABI版本查询及read/write导出；原MS ABI1结构和入口保持，缺扩展的旧插件继续支持原fresh回调，显式恢复配置在创建策略前拒绝缺能力插件。读写仅在原INIT/SCHEDULE同OS线程/epoch借用期，读取复制至调用者缓冲，缺键返回长度0，写入拒绝空值、NUL、非ASCII及超额；写后回读原内存确认，持久化仍由原dirty用户变量流程承担。

正式configured入口显式`recovery.mode=record_clean/resume_clean`沿P21原交易责任、同根租约、原文件集合/摘要及成功关闭收据准入。record_clean保持原fresh空持仓检查，init登记初始空决策；schedule完整计算、setter及回读成功后，将NSQ已有StageState和观察序号登记到原用户变量。原init后的session_begin和原schedule尾部保存dirty KV，停止阶段额外保存0。缺省fresh保持既有行为。

状态使用`guanheng.configured-quantity-state.v1`固定数据schema，绑定策略ID、已核FrozenSessionInput/映射/资本policy与同一Python源码/解释器身份。内容只包含数量核的冻结决策及序号；原NSQ公开值构造器重新核验阶段、向量、basis、资本及费用不变量，禁止pickle、动态类型或第二套金融账目。单个原键及字节上限约束容量。

resume_clean在原load_data/load_userdata后读取该键，严格检查schema、完整字段、规范编码、绑定身份及NSQ state_id；缺失、损坏、错策略/输入/policy/版本拒绝且零setter。恢复None决策要求原策略仍为空。恢复已有决策后，第一轮原schedule以原持仓/目标/价格/损益观察继续调用原NSQ.advance，不推定券商成交，也不重新分配相同代际的冻结数量。观察序号接续，避免重用同一代际观察身份。部分setter、KV登记或投影失败沿原health故障停止，不授clean恢复；异常退出仍沿B-06原责任核查。

INIT中的回调或主K线登记失败须从自有策略Factory的初始化回调立即传播至既有Session启动失败边界，停止后续行情生产者启动及ready发布；失败状态、原异常身份和资源关闭继续沿原宿主链处理。

验收：R12-C1安装正式configured同根两代恢复A/B的700/700及相同冻结决策，第二代继续原调度且新增SDK0；C2缺失/损坏/错绑定或违反NSQ不变量的值在首setter前拒绝并保留原金融文件；C3原fresh/旧扩展缺失、跨线程/过期epoch/错误阶段及32768字节边界；C4回调/setter/KV失败不授clean及完整资源回收；C5独立安装、同源摘要、公共头消费和独立full审查。持续行情/所有保留业务版本和异常恢复沿原资格核验；框架多线程调查已按用户决定结束，本项新增WT核心修改0。

## NRT-R13 固定V2同核实时接线

受管Python入口增加显式`guanheng.v2-cta.v1` profile，参数集合及来源身份沿R11，只接受原`nsb-v2-input-v1`/FrozenV2SessionInput。原configured profile继续只接FrozenSessionInput，两种schema与DTO严格对应。输入、市场资料和预算复用NSB StrategyBacktestSession准入；业务直接复用原V2Binding/evaluate_v2_history、共享信号及分配核，数量复用NSQ.advance。回测与实时均保留V2原始权重与超配拒绝规则，不改写成configured算法。

本profile消费显式冻结历史窗口。每次原schedule先核原Reader实际闭合前缀及行情字段；求值截止取本次原上下文时间与冻结窗口最后日15:00的较早者，原signal核继续校验逐行可获知时间。窗口结束后的调度重复求解同一冻结业务结果，报告同时保留实际native_knowledge_cutoff；持续补充历史需另建固定输入，不从未来行补值。读取、求值、数量和投影共用本轮evaluation_seconds截止。父子安装绑定同时包含固定包内`.py`与`.json`资源，V2发行profile资源与源码共同核验，额外遮蔽资源拒绝。

原V2Binding拥有算法/config身份、完整目标和原始超配判断；本桥只将目标strategy_id绑定至本原生策略实例。超配时保留原持仓、原数量阶段及诊断，outcome为空、status=blocked_raw_total、零新增setter；既有目标与实际账户事实继续沿原owner处理。正常目标和clean恢复沿R11/R12同一实现。

观察投影沿本宿主独占的pending文件及原子替换发布。Windows读者仍持有旧文件句柄时，替换可返回原生5/32/33；发布者仅沿同一evaluation_seconds截止等待该句柄窗口，其他错误立即传播。替换未完成而到期时，保留最后原生错误、原pending及前代投影；替换已成功后才发现超时，则保留已提交的新投影。两者均沿health停止并拒绝clean，已发生的原生事实继续保留。编码、预检后setter准入、KV边界及最终投影均复核同一截止；同步原生调用内部的中断能力保持原生命周期边界。

验收R13-C1：普通非editable安装的正式受管入口，由原Factory/ticker调用两实例V2，经NSQ/完整setter/原组合净额/WinSHM SDK替身，后继调度收敛且完整关闭。C2：相同安装与冻结输入进入原生BT，逐项核完整V2业务结果、经济目标与终态数量，原撮合价格和资金差异单独记录。C3：profile/DTO错配、来源SHA/历史或预算失败、超配零setter、同根恢复及既有configured兼容；独立full审查绑定实际源码和制品。真实来源、持续窗口更新、真实交易与完整模块资格继续分别验收。

## NRT-R14 安装行情插件与原生分钟的正式宿主组合

复用WT-D05、WT-S01和WT-S06：现有CtaExecutionSession按配置加载模块A固定交付的ParserQMTHostV6与显式minute_native Reader，原ticker触发分钟及策略调度，策略/数量核、组合执行及停止继续沿原入口。WT框架调查保持停止，本项只装配已交付扩展和验证主链。

首个隔离组合明确分列输入：活动原生分钟根只读；d1与业务输入为原冻结合成窗口；FullTickV6行情及券商SDK使用显式替身。实际分钟不能给合成日线、报价、量额单位或真实交易授资格。原采集者保持唯一Writer，验证进程不启停或写入采集根。历史追赶bar只作数据事件，当前目标准入仍受原策略配置和输入资格约束。

验收R14-C1：普通安装的正式Python受管入口加载固定两DLL，原分钟事件触发configured两策略，完成目标→组合净额→SDK替身→查询/后继调度收敛。C2：回调中的真实m1副本与同次原Helper读取逐标签及OHLC/量额核对，记录来源混合范围及每项输入SHA。C3：原控制停止、Parser/Reader释放、原生进程与Job/管道、HTTP及SDK替身资源完整关闭。真实FullTick来源、全真实日线同核和统一App候选仍由后继分别验收。

## NRT-R15 当前完整App安装与研究输入边界

复用WT-S01/S05/S06及既有受管入口，将C当前完整App/纯策略包普通安装与B固定原生组件组合验证，保存完整发行闭包及实际加载身份。App公共生命周期和策略数学规则保持各自owner；B只维护原三薄适配。固定configured和V2实时profile继续消费严格可知输入，沿既有同核/数量/原生账本/恢复路径运行。

共享FrozenSessionInput新增的[历史日末模型](historical-eod-model.md)保持研究资格。实时薄适配在decode、输入SHA和profile类型核验后，要求historical_model缺省或None；非空以有限原因research_only_input在构造策略阶段拒绝，发生在CtaRuntime装载/运行与券商四查询之前。研究BT入口及研究报告沿C原owner提供。缺省旧DTO保持原严格行为，研究假设不成为实时交易准入。

验收R15-C1：完整普通安装无隐式启动钩子、RECORD及wheel内容相符，当前configured/V2经正式入口、原组合及SDK替身后继收敛，原正常停止/两代恢复及已有profile兼容。C2：同一安装的原生BT/RT完整核结果与目标一致，版本/包资源及原生输入身份可复核。C3：合法研究DTO进入实时profile时零原生运行/查询/SDK并正常回收子进程，研究BT及旧严格入口继续各自语义；独立审查绑定最终代码、安装及结果。全真实来源、其他算法版本与完整模块要求继续逐项验收。

## NRT-R16 真实策略目标与账户资金拒绝的原生结果链

状态：pending-verification。当前运行包含运输超时、错误合成订单字段、未获单次报单限制及原进程访问异常，原件保留；下述为预期验收范围，完整资金拒绝/频次链尚未取得资格。

沿WT-T01/T02/T07及当前configured正式入口，分别核策略理论预算、券商available和柜台委托状态。策略仍调用唯一纯核/NSQ；券商资金查询通过原mapper/标准SPI进入原Adapter，柜台明确拒绝通过原订单回报和完整查询处理。策略理论成交与实际账户成交分别保留；本项不增加资金余额、持仓分摊或绩效账本。

隔离验收R16-C1：当前普通安装、双configured各700股理论目标，源端账户available=1000元，原组合提交1400股后收到真实运输的废单57、实际成交0及持仓空。原TraderAdapter配置order_total_limits=1、order_times_boundary=0、order_stat_timespan=3600，继续推进至少两次原策略计算和后继行情，实际两次已知废单尝试、后继SDK调用不再增加，成交0、原查询保留可用资金1000元。单独报单总量1未约束该次第二次废单尝试的原失败保留，频次参数及实际次数按固定原生版本验收。这是显式测试配置，资金不足由柜台事实给出，频次规则按实测边界解释。

R16-C2：核原策略理论持仓/冻结目标及后继收敛与账户未成交之间的差额，原查询/事件确认与未知提交责任分别保留；确定拒绝可核清，未知结果继续沿原命令身份处理。R16-C3：正常关闭及物理回收、同安装既有成交主链兼容、最终源码/配置/命令身份和独立审查。真实券商账户资金准入、跨证券共享资金约束、报单频次的其它边界和生产资格继续独立验收。

### 异常状态的恢复拒绝验收

按P21/B-06，将实际访问异常留下的stradata/userdata/portfolio原字节复制到专用隔离状态根，原异常原件保持。显式resume_clean缺少原干净停止证明时，在首次策略写入或新委托之前拒绝；完整关闭后新代SDK0、原副本及原异常金融文件摘要不变、未生成clean/consumed标记。该项核原恢复门的失败准入，完整异常责任恢复和访问异常根因分别保持各自边界，WT线程调查持续停止。

## NRT-R17 策略读取当前券商观察

状态：accepted / in-progress。复用WT-T01的原Adapter唯一账户表及STQ-P22原CNY账户观察。自有BrokerQueryAdapter记录完整P/A回调完成后的接收epoch毫秒及单调修订号，断线/空指针为未知；非空零行P是已知空仓。时间表示本地接收，源SDK采样时刻保持未知，不宣称四查询共同事务。普通native路径保持。

自有产品owner在初始四查询完成、INIT之前及后继pump后发布不可变值副本。运行DLL增加可选gh_cta_broker_abi_version/layout/read，原运行ABI1和原策略Position结构保持。Facts含size/version、各自已知标记/修订/接收时间、发布时刻及原CNY balance/available；Position含64字节标准代码、long方向、quantity/sellable，只发布非零方向持仓。完整空查询返回positions_known=true和空tuple，零量原条目不进入公开持仓集合。查询时点不随重复发布刷新。复制采用当前shared_ptr持有值，不借出WT对象；没有观察时返回Unavailable，capacity=1..4096不足返回Capacity，关闭后清除观察。跨线程复制只读副本由自有运行接线负责，WT调度及行情保持。

安装Python公开不可变BrokerObservationValue/BrokerPositionValue，CtaRuntime及INIT/SCHEDULE借用期的CallbackContext可读取。缺扩展报告broker_capability，旧运行库其余公开入口继续可用；未知资金为None，未知仓位保持已知标记。策略原Position的actual/pending继续保留原语义，券商值经独立对象提供。当前观察不推导成交归属、开仓时间或连续周期；RR112仍须接真实周期来源及原用户状态。

R17-C1：正式安装Runtime/原Factory INIT读取券商1000/可卖1000及CNY余额/可用，与策略原仓位分别断言；字段/版本/布局、值隔离、接收≤发布、重复发布接收时间不变。R17-C2：原查询由1000变800后后继调度读取800，原查询修订递增、持仓及资金接收时间独立，原策略目标/SDK差额保持；原关闭后Unavailable。R17-C3：容量/结构版本/未知及旧运行库缺可选扩展兼容，无新增真实查询/交易副作用。R17-C4：同批库/运行DLL/安装头及安装Python实际公开入口、正常关闭和独立审查。该接缝服务唯一1.1.2原生整链；数学核/预算及完整实际周期主链继续。

## NRT-R19 独立WT执行装配

状态：accepted / in-progress。按[WRI](independent-wt-runtime.md)将执行进程、ctypes与唯一1.1.2实时装配迁至`guanheng_wt_runtime`。复用WT-S01/S05/S06、WT-T01/T02、原P21/P24状态及关闭协议。业务核、NSQ、原生保存与账本保持原实现。独立安装只要求runtime、market-client、strategy-core/native/v1及tzdata，不依赖观衡包、HTTP或SPA；运行Python身份绑定改为实际独立包闭包。旧configured/V2入口作为历史兼容开发材料退出独立运行候选。

工厂`execution_process.create_process(descriptor_path, expected_sha256)`同步读取64KiB以内原字节、核SHA和严格字段，完成构造；启动沿原`start(monotonic_absolute_deadline)`，停止沿首次共享预算。部署schema为`guanheng.execution-deployment.v1`，字段固定为`schema`、`installation`（原安装根绝对路径）、`configuration`（原CTA配置绝对路径）、`configuration_sha256`、`control_root`（已有独占控制根绝对路径）、`python_strategies`（严格bool）。true选择唯一retained入口，false复用原native产品入口。配置和安装继续由原ExecutionProcessConfig加载及验SHA，descriptor不重写下层配置或建立第二份运行状态。坏身份、缺发行或错profile在创建进程前失败；构造期间不创建控制代或写金融文件。

共享业务胶水及现金ETF资料准入迁移时逐函数保留原语义与源摘要；BT消费者沿同一实现接线。迁移完成前两侧来源对应关系及退出项明确登记，暂存文件不授予同核最终资格。公共运行装配和installer由原负责人集成，执行模块只交上述固定工厂及原状态协议。

R19-C1：普通无观衡安装实际运行唯一策略、原Factory/调度/净额执行及SDK替身后继查询，原金融结果保持。C2：同安装正常两代及异常缺完整证明拒绝，原命令与金融文件身份保持，进程/Job/管道实际回收。C3：descriptor身份/字段/模式及安装错配在新增进程前拒绝；全部依赖及实际源码可复核，独立审查绑定最终制品。完整独立WT与观衡断开持续运行验收按WRI完成。

## NRT-R20 独立运行结果的只读定位交接

状态：accepted / in-progress。复用WT-S01及R17/R18既有策略/券商观察投影。执行owner的公开status增加`business_observation`，普通native入口或尚未绑定真实PID时为null；唯一Python策略入口绑定PID后为`guanheng.execution-observation-reference.v1`，固定字段为schema、control_id、config_sha256、pid、path、ready_path。path指向本代控制目录已有strategies.json，ready_path指向同目录原ready.json。control_id为本代规范UUID，config_sha256为原CTA配置摘要，pid为原ready确认的实际子进程PID；路径仅提供只读定位，没有启动、停止、命令或凭据接口。status取值不读取结果文件、不查询券商、不重算或改写金融事实。

独立Python发布端使用`guanheng.configured-cta-observation.v2`，固定顶层字段为schema、control_id、config_sha256、pid、strategies。身份取自本代固定CLI及当前进程，strategies沿既有原结果，不改变策略/账户字段。旧App历史v1发布端保留原行为；新独立消费者严格核v2身份，再将原strategies交既有project_strategy及账户DTO白名单。新schema区分新增身份语义，不静默把旧v1升级为已核身份。

WRI的`components.execution`原样携带该公开状态。只读消费者从已绑定WRI状态获取reference，核路径绝对、父目录名等于control_id、ready_path/path同目录且文件名分别ready.json/strategies.json；读取原ready及v2结果并核三项身份一致。读取在自己的原请求截止内完成，文件替换沿已有共享快照读取能力，原ready及控制目录只读。消费者不构造/继承执行owner，不调用start、request_close、close或任何查询/下撤单方法；观衡启停保持WT所有权。

券商positions_known/account_known、P/A各自接收时间、修订及发布时刻沿原broker_observation展示。已知空仓表示空集合；未知、暂缺和陈旧分别标识。broker_position_qualified=false描述交易资格，不阻断已知事实的只读展示。订单/成交明细等原投影未提供的组分别表达缺失，已有P/资金不随之被隐藏。执行故障或停止后reference可继续定位最后完整结果，消费者同时呈现运行状态和原数据时间，不把停止前数据当作当前新查询。

R20-C1：普通无App安装的实际策略入口发布status reference、原ready和v2完整结果，三项身份及实际PID一致；复用现有结果并在后继源变化后读到原P/资金新修订。C2：独立只读消费者显示实际P/资金/策略结果及各自时间、对未提供订单/成交分组表达缺失，期间WT进程与SDK调用责任保持。C3：缺文件、旧schema、错PID/控制ID/SHA/路径及替换窗口沿原D拒绝或等待，consumer启停不写WT控制/金融文件、不启动或停止执行。完整正常关闭与本项只读主链分别验收。

## NRT-R21 原成交事实只读观察

状态：accepted / in-progress。复用WT-T01/T02、原StandardQmtTrader身份/金融映射及去重后的SPI交付。自有BrokerQueryAdapter在原onRspTrades与onPushTrade之外保存有限值投影：原成交编号、关联订单编号、标准证券、原user_tag、成交日/原HHMMSSmmm、买卖方向、数量、价格及金额。这里只复制既有事实，不累计持仓/现金、不计算成本/收益、不分摊组合成交，也不重发查询或成交回报。初始完整查询与后继已交付实时成交按原scoped trade ID合并；相同身份保持同一事实，后继查询不能消除已交付事实。日期和时间来自原映射，接收时间单独标注。

投影沿源max_rows（1..4096）有界，保存query_revision/query_received_ms、整体revision/received_ms及live_revision。每个原实时成交首次交付时记录其first_live_revision；历史查询行不伪装实时事件。重复事实保持原first_live_revision，交易日期变化或容量/冲突使本投影unknown并给出固定错误状态，原金融回调继续由WT消费。断线时已知性清除。查询初始未完成与已知空成交分别表达。

自有运行库增加独立可选ABI1的gh_cta_broker_trades_abi_version/layout/read；原P/A ABI及布局保持。使用同一个owner在pump后发布的不可变值快照，query计数或原成交观察revision变化均触发发布；新发布不延长原P/A接收新鲜度。调用参数、容量、布局与原broker_read一致，零交易副作用。Python Context.broker_trades()只复制本快照，旧DLL明确缺能力，原broker_observation()行为保持。v2策略结果可增加broker_trades独立组，C分别消费其已知性、源时间及可用范围。

R21-C1：普通安装原正式入口从空成交查询推进至实际SDK替身买卖回报，观察取得原成交/订单ID及源时间、数量/价格/金额，券商P与原绩效保持原实现。C2：同一事实查询/实时重复、乱序及已知空/未知/断连、源容量与错误边界分别验证；观察读取不新增SPI、SDK或查询。C3：安装C/Python布局消费、旧库兼容、独立审查及实际资源关闭分别核验。此接口提供R18真实新周期必要的源成交事实，周期消费者完成之前仍保留actual_opening_source_required。

## NRT-R22 唯一策略的新开仓成交来源

状态：accepted / in-progress。仅用于用户已确认全部账户持仓归唯一1.1.2策略的R18 profile；构造要求运行配置只有这一策略。R21仍为账户级事实，不为多策略分摊成交。当前broker P已知空仓时，以本实例原Local实际返回的委托提交序号及P修订/接收时间建立零仓来源锚点。首次初始化、已核旧周期变为空仓以及尚无原NSQ开仓目标时更新锚点；已提交的新开仓目标保持同一锚点，P先到、成交回报后到时持续等待。提交序号仅由本实例原base返回的有效OrderIDs建立，查询和回报只能匹配，来源时间或回报到达顺序均不能代替该身份。

自有Local沿原on_trade(localid,code,buy,...)通知关联本次原成交与原提交身份，不改WT私有解析器或账本。身份投影只含原编号、证券、方向及单调序号；容量、分配或身份冲突使来源资格unknown，原提交返回和原金融通知保持。原P/A和成交ABI1保留；独立可选trades_v2_read及layout(3/4)在同一不可变快照中复制原事实和来源序号，缺能力时仍可查看原成交，自动建立新周期保持等待。

P转为非零而缺周期时，从同证券、原提交序号大于零仓锚点且已由原实时通知关联的实际买入成交中选择最早源时间；query历史行的first_live_revision=0及缺本实例原提交身份的成交不能生成新周期。opened_at由源成交日/HHMMSSmmm转换上海时区后取UTC，须不晚于本次P接收时间及决策截止；实际数量始终取P，不累加成交数量。cycle_id绑定零仓锚点，source_sha256绑定原成交事实及锚点。源能力缺失、未知或缺匹配回报继续waiting_actual_cycle。原理论entry、模型目标和查询时间继续只担其原职责。

实际部分增减沿同一周期；同进程迟到的更早买入回报只修正新建周期的最早源时间及来源摘要，cycle_id保持。已知周期及退出沿原用户KV三字段和C CycleExit保存/恢复，原quantity-state格式保持；零仓锚点是本代来源元数据，干净恢复已完成所有未决责任后以新代事实建立新锚点。异常退出仍沿P24拒绝不完整证明，已有持仓缺原周期时保持等待并要求已核接管来源。

R22-C1：正式无Web入口从flat买入、P与成交交接后自动进入held周期并继续原1.1.2/NSQ调度，八目标及原KV可核；数量与P一致、来源时间等于真实SDK替身回报，新增委托保持原NSQ及查询优先责任。C2：P/成交两种先后、部分买入及加仓、已知空仓后新周期、重复/迟到更早回报、foreign/query-only/缺能力/未来源时间分别验证。C3：同根正常两代恢复、完整BT/RT周期及独立审查仍分别验收；合成来源结果不替代真实券商交易资格。

## NRT-R23 等待期间的券商P/A刷新

状态：accepted / in-progress。正式受管根配置可显式提供`observation_refresh: {interval_ms: 1000..60000}`；缺省保持原查询触发路径。旧Runtime拒绝未知根字段；新Runtime在交易API创建前核标准插件的`standardQmtObservationRefreshVersion()==1`，再把配置交同实例标准插件。根字段、区间或插件缺能力在初始化前拒绝，不能默默忽略启用意图。

刷新复用原queryPositions/queryAccount工作任务、身份解析、SPI与Adapter表；不新增金融事实、资金预留或调度线程。创建owner在既有pump/wait中按间隔发起账户、持仓两阶段，每次只有一个本刷新任务在途，其原task ID贯穿query/resolve，在原SPI返回后才交接下一阶段。完整初始四查询完成后开始，间隔从上一完整周期完成计时；排队满时沿下一间隔等待，来源失败/超时沿原交易错误责任停止。原事件、提交查询可独立在原队列交错，不据其他查询完成冒充本阶段结束。完整成交查询继续初始化及原回报触发，周期刷新不重复喂入历史成交统计。

unknown命令的只读查询保持原权限，刷新不解除责任、不重发订单。恢复关闭新增提交后停止新刷新，已有刷新沿原任务实际排空；实际P/A接收修订和各自新鲜度保持。来源Journal与队列容量沿原配置，刷新没有自动删除或另建存储行为。

R23-C1：普通无观衡安装、唯一正式1.1.2实际入口，券商available0时原目标等待且SDK0；源资金释放后无外部主动查询，原P/A补查交付，再沿同目标买入并由真实周期来源继续调度。C2：可卖不足及后继P更新、默认关闭、慢查询不重叠、容量/错误、错配置及旧插件分别验证；理论预算和券商available保持独立。C3：正常/失败关闭、同根恢复、安装头及实际版本SHA、独审和最终模块组合分别验收，合成结果不替代真实账户授权。

## NRT-R24 已发布分析窗口的持续消费

状态：accepted / in-progress。目标沿模块B的持续真实策略运行；复用WT-S01/S02/原Reader、QNA原分析窗口和唯一1.1.2/NSQ。原始日线及前复权生成归A，实时桥只消费已发布值、核原生raw窗口并调用同一纯核。当前SDK只有原始日线查询，QNA提供冻结文件；持续生产及新基准的真实发布由A提供，本项实现不授予该生产者资格。

唯一Python profile可显式提供`market_window: {path: <绝对路径>, max_age_seconds: 1..604800}`，两字段精确，有限数值拒绝bool；缺省保持启动input_file/SHA固定窗口及原严格匹配路径。path由部署owner指定为QNA既有`guanheng.qmt-native-analysis-window.v1`的只读发布位置，发布者负责完整写入后原子替换及文件写权限。运行侧每次原调度用同一计算截止读取最多32MiB的单次文件快照，不启动线程、HTTP请求或下载，不写该源文件，也不另存行情缓存。

已有账本首次增加该只读引用时，按[EFR-16](execution-fault-recovery.md)显式原配置/SHA兼容许可，金融和纯模型配置继续严格保持。自有Reader可选daily.adjustment=none（缺省）或front_ratio，后者仅将逻辑日线代码委派到WT原前复权后缀；分钟、实时报价、金融代码与原价估值保持原身份。策略d1窗口与QNA前复权输入必须逐字段配对，日线DSB/因子及复权仍归原Reader负责。

消费只取该schema的history/analysis/current_view和原units，完整wire解码及策略验证仍交C原RetainedInput/唯一核。固定配置、策略资本、费用、周期和退出状态仍取各原owner，文件不能覆盖这些事实。原接收/可知时间和单位保留，未来输入拒绝；max_age_seconds按current_view.received_at与实际决策UTC比较，不推导交易日或改变原时间。缺文件/暂不可读、过期或原生raw尚未配对时发布`waiting_market_input`及固定原因，不提交本轮新目标；格式/协议/单位错误沿原health失败，不能把坏输入当作空成功。

新模式按原Context的有限d1尾部核完整声明窗口，最多多读一条，按声明首末日期选择后逐字段精确比较，原生4096条上限保持。窗口之外的在途日线不参与纯核；窗口内部缺行/值冲突保持等待。窗口出版摘要、source/factor revision、basis_date及原时间只作为本轮来源元数据进入既有观察；NSQ和原WT KV继续持有目标/周期状态，不增加持仓、资金、成交或来源进度账本。源数据按发布者当前值重新读取，修订由其原revision表示。

正常恢复仍锚定原启动input/SHA、原KV及相同源码/运行配置。显式market_window路径/年龄配置进入状态身份，实际出版内容可以更新；来源窗口的更新不重写首代持仓/周期包，不清空金融状态。计算和提交仍沿原一次D、预检/完整setter/原KV及P21关闭准入。

既有观察v2在本选项启用时增加策略status=`waiting_market_input`，固定原因`market_window_unavailable`、`market_window_stale`或`market_history_mismatch`，可附market_window来源元数据。C只读消费者增加该状态的中文等待说明，不持有源文件或运行owner；旧配置及其他状态保持。新选项的整套用户链须在C消费兼容后验收。

R24-C1：普通六发行安装，实际A发布文件→正式WT/Reader raw配对→唯一核/NSQ/Factory/原Adapter/WinSHM SDK替身；缺文件时无新增目标，发布后继续计算、查询优先执行及实际开仓周期，来源摘要随原文件更新。真实窗口接收与完整跨日发布分别登记。

R24-C2：两个有不同闭合日的窗口、同日修订、缺/旧/未来/坏schema/重复字段/错单位、原生匹配滞后和窗口外在途bar，逐项核目标、原周期/NSQ及无错误提交；静态缺省继续原路径。模型数据、Context替身与正式原生整链各自记录范围。

R24-C3：相同新模式同根恢复保留原状态和在途责任；不同配置/源码仍按原身份拒绝。普通安装、C消费候选、原料/制品SHA、关闭回收及独立审查齐备。完整实时关闭和全周期BT/RT继续按各自要求验收，核心方案未批准时保持未实施。

## NRT-R25 原生实时费用能力与策略资本

状态：accepted / in-progress。复用WT原商品calcFee、策略原fund/交易CSV及原Adapter账户查询；B只核配置实际可执行能力及派生资本，不记另一份佣金、持仓或资金账。

当前固定实时原生商品费用只有byvolume及open/close/closetoday费率，按份或成交金额计算并按原规则到分。当前回测重放器另外支持minfee最低费用；实时入口不把该回测能力当成实时能力。实时配置中的minfee缺省或0保持原语义，正值在自有原生资料准入时明确拒绝，尚未构造CTA运行实例或初始化账户插件；负值、未知字段、非有限值及错误类型继续原拒绝。BT的原最低费用功能保持。支持实时最低费用的实现仍是完整费用边界缺口，若涉及WT框架行为，另按原批准规则处理。

每个配置品种须有显式费用项；缺失费用项在实时准入时拒绝。原WT理论费用计入策略fund及flag0损益；理论NAV仍由明确本金加原生损益导出，现金从该NAV减完整理论市值派生。券商账户commission、balance和available保持原查询事实，费用预留由策略模型明确给定，不能用券商费用覆盖原WT理论账或调整源事实来掩盖两者差异。

R25-C1：普通无观衡六发行安装、唯一正式1.1.2、原Factory/CTA/NSQ/股票执行器/Adapter/WinSHM到SDK替身，在明确持仓接管后完成卖200、完整P/A后继和收敛；按份及按金额两种非零卖出费用分别核原交易CSV、fund累计费用、flag0、理论NAV/现金、查询commission/available及源身份。已确认只读精度制品按原件复用，不重复现场查询。

R25-C2：同一正minfee配置在旧实时桥可进入原生而费用忽略的反例，修正后在账户插件初始化前拒绝；缺省、0、负值、bool/字符串/非有限数及错键矩阵，BT正minfee继续沿原重放器；源码/原DLL/安装身份与副作用计数分别核实。最低费用、平今与真实券商收费只在具备实际链证据后授资格。

R25-C3：本轮完整关闭、正常/异常恢复、独立审查、源码/原件/制品SHA与统一候选交接分别记录，既有关闭失败不由费用模型结果覆盖。

## NRT-R27 未知提交后的原身份与同根重启拒绝

状态：accepted / in-progress。沿B-06、P21及WT-T02/T09验证唯一1.1.2的正式WRI入口。复用现有Host/Journal的command_id、命令原文与结果摘要、Source未知围栏及原生恢复准入；新增金融账本和WT框架行为均为0。首代SDK替身实际进入后抛出明确的合成异常，来源保留unknown。关闭和第二代继续使用同一Host、Journal、账户配置与金融目录。

R27-C1：首代原Factory/CTA/NSQ/股票执行器实际发出卖200股，SDK替身只进入一次；原Journal保留同一command_id/body/command_sha256/result_sha256及unknown，不发布clean。R27-C2：首代物理回收后，以resume_clean重新启动正式WRI，原生在策略运行前拒绝；原命令、金融文件及SDK调用数保持，POST不得增加。R27-C3：逐层记录实际启动/关闭、失败阶段、原命令与查询次数及Job/管道/资源回收，原生关闭异常单独保留。该项只验证Host存续时Native跨进程拒绝及原身份保留；Host/Source整体重启后的继续核查和解除未知责任仍需独立验证。

R27-C4：从上述已完整停止的实际合成Journal保留副本，在独立新进程重新构造原Host工厂和Source，使用原route、trade identity及完整profile，原件保持只读。经真实认证HTTP读取原命令及新来源的P/O/D/A；原命令字节/结果/unknown保持，Host关闭新委托准入，Source新实例的unknown初值与Host保留责任分别表达。新Source的SDK写0、trade-command POST0，新认证身份及四组查询可用、完整关闭分别取证。此项为原工厂/HTTP/SHM的冷重开验证，正式安装WRI管理全部组件和未知责任解除继续单列。

## NRT-R26 唯一策略可卖等待的同根恢复

状态：accepted / in-progress。复用R18/R12/P21原实现，在明确接管的原持仓、可卖和周期初值下验证等待状态的完整正常恢复；产品接口与保存行为保持。

R26-C1：普通无观衡六发行WT安装，正式WRI/唯一1.1.2/原Factory和NSQ在同交易日观察原理论200/可卖100及独立券商200/100。完整目标因可卖不足保持waiting_sellable，提交向量为空。干净停止后同根resume_clean沿原WT金融JSON及用户KV恢复，原周期和整个数量阶段对象保持，观察序号接续，下一原调度继续等待、SDK新增0。两代原closed.v2/clean.v2、内外Job及Host/来源回收分别留证。

R26-C2：在上述正常两代之后，仅对本次合成用户KV文件追加空白造成摘要漂移，同根第三代在原策略初始化前拒绝。初始四查询独立保留，SDK0，未生成该代成功closed，原clean及consumed证明不变，原金融文件在QA恢复后逐字节一致。拒绝阶段没有业务locator时，QA依据本次新增控制目录及原failure三身份定位，不要求产品发布业务成功引用。

R26-C3：QA显式feed-date使行情日期、原CTA交易日与接管交易日一致；缺省维持既有次工作日夹具行为。首代成功与后继股票关闭失败分别保留。WT在原on_session_begin中处理跨日冻结释放；同日恢复不授次日解冻、成交后稳定关闭、完整异常责任恢复或全模块资格。新增框架行为仍按原批准边界处理。

R26-C4：在R26已成功停止的三份金融JSON副本上，使用同一原WtCore静态库及冻结头文件调用原上下文load、同日session_begin、下一交易日session_begin和session_end，再由独立新进程load。核同日总量200/可卖100、次日总量200/可卖200、同次日重复通知幂等；成本、盈亏、费用、周期及整个数量阶段状态保持。保存仅由该探针实际调用的原session_end完成，原件及原clean不变。该项覆盖原生公开会话接口，尚未覆盖正式WRI跨日启动、自动ticker事件、次日券商可卖刷新及后继下单；探针状态不复制clean证明，不取得产品恢复资格。交易插件登录配置日期与原策略金融文件日期分别记录，解冻日以原策略已保存交易日为起点。

## NRT-R18 唯一1.1.2当前决策实时接线

状态：accepted / in-progress。自有execution_configured增加guanheng.retained-cta.v1，消费固定input_file/SHA、main_symbol、evaluation_seconds和broker_max_age_seconds。单实例ID固定resonance-regime-v1；同一运行配置禁止混入旧profile。父子Python身份只要求本profile实际的App/core/native/V1/tzdata，旧profile的历史组合保留独立兼容入口，不进入唯一策略发行要求。

当前验证：R21/R22已在独立安装完成真实输入、四笔SDK替身买入、实际开仓周期及后继收敛；最终六发行/731 RECORD同版完成400次BT与末日flat比较，RT关闭c0005仍失败。[同次关闭释放链](../evidence/2026-10-30-stock-close-release-trace.md)已由原转储/COFF与原工厂两单元红例定位商品release失效虚调用，正式首次释放完整历史仍unknown；三WT文件修复继续提案，未应用或编译。早期自然事件及受控交错的[实际异常记录](../incidents/2026-10-29-retained-cta-access-violation.md)保留原范围，不把后继释放链用于追认历史根因。完整实时、同根恢复及全周期BT/RT继续逐项验收。

输入guanheng.retained-cta-input.v1包含C原RetainedInput、NSQ原QuantityPolicy、fee_reserve_cny/fee_source及market_manifest_source。明确策略本金和来源，沿原比例核准后提供；桥不从账户可用资金推定本金，不再次缩放C完整权重。拒绝历史回放model及未知字段，原基础资料/费用/现金ETF单位准入复用strategy_replay_facts.admit_native_files。完整raw日线与原Reader逐字段核对，计算共用C的evaluate_retained；当前决策截止取本次实际UTC时钟，原调度日期时间作为独立原生观察保存，分钟HHMM不冒充带秒的来源接收时刻。

现金ETF执行沿原`WtExeFact.WtStockMinImpactExeUnit`，默认及覆盖规则统一使用该单元，`min_order=100`，`is_cancel_unmanaged_order=false`。该原生单元分别读取券商总量和可卖量；通用单元的默认有效仓位不能替代现金ETF总持仓。Local保持`scale=1`、`strict_sync=false`、无groups二次目标变换及无主动clear，显式本金与原NSQ只应用一次数量规则。错选执行单元或上述配置不符在装载Runtime前拒绝。前代交接和NSQ推进直接复用C的`advance_retained`，实时桥不保留第二份阶段逻辑。

首次接管时，原P23加载已核数量/可卖/开仓时间；原用户键初值为guanheng.retained-init.v1及本input SHA。INIT分别核原理论状态、R17实际数量与已核周期，建立只含cycle_id/opened_at/source_sha256的周期元数据；数量始终来自当次券商查询。正常恢复沿原同根clean准入及原用户KV，携带NSQ阶段、周期元数据和C退出状态。部分增减保留已核周期，已知空仓清除该证券周期。当前没有已核新开仓起点时，发布waiting_actual_cycle并停止本轮新目标，等待实际来源；禁止从原理论entry、当前查询时刻或模型BUY生成真实起点。新开仓源的自动接入仍是本项完整验收的必要部分。

用户2026-10-30后继决定由R30更新首次初始库存语义：现有持仓建立新的运行基准，旧实际开仓时间及旧周期状态不再作为启动材料。上述R18现行实现与历史验收保持其原件身份，后继实现须按R30接线；新运行后的真实新开仓来源和正常恢复责任继续沿原规则。

首代周期包的有效窗只用于record_clean首次接管。resume_clean复用相同输入身份、原clean证明及已保存周期，业务计算使用本代新P观察的接收/有效窗；首代包自然过期不要求改写输入或重建空状态。输入本身未来决策或不合法周期仍在原生加载前拒绝。

每轮P观察有独立接收/有效期，过期或未知保持等待；纯核实际周期数量使用券商值。当前唯一策略的全部管理库存已由用户指定归属该策略；实时NSQ的actual/sellable使用本轮完整券商查询，pending信号沿原策略上下文独立表达，执行阶段与恢复遵循后继R31。原生理论NAV继续由显式本金加原flag0损益导出，现金按完整理论持仓市值派生；精确金额沿共享Fraction编码，原查询资金保持独立字段。完整目标经NSQ原阶段与原setter/组合执行；上一经济代际实际未收敛时先沿NSQ推进原代际。周期/退出/数量阶段编码及观察预检消费同一截止，预检完成后才调用setter和原KV，失败沿既有health拒绝clean。

验收R18-C1：普通安装唯一依赖，真实1.1.2八目标经正式受管入口/Factory/ticker/NSQ/原执行器/WinSHM SDK替身完成已有持仓保持及实际周期退出，并继续后继调度。C2：同一输入与C原回放接缝的完整目标/稳定经济身份一致，费用及实际/理论差异明确，停止/同根恢复延续原状态且无重复委托。C3：新开实际周期来源、flat/held/unknown、部分增减与退出延续，过期P及错初值/研究输入在新增setter前拒绝或等待；完整新开仓来源缺失继续列gap。C4：安装身份、资源完整关闭、独立审查及精确交接；真实调整来源、当前实际周期和完整App按各自owner接入。


## NRT-R28 逐日基准的原生回放与完整比较

状态：accepted / in-progress。当前实施和逐项资格见[逐日原生证据](../evidence/2026-10-30-per-date-native-replay.md)，完整CLI和BT/RT比较继续。

B消费A已核ReplayCatalog的逐日原生窗口，保留manifest、逐窗SHA、basis/factor及实际known_at/received_at。A拥有原价/分析值；B只解码、裁切由A提供的窗口，不重算复权或补造历史首次可知时点。401日输入及400次原生计算分别验收。

原RetainedBacktestSession继续提供最终批次历史模型。自有逐日回放类复用其原Porter/CtaMocker、原NSQ、周期/退出userdata及财务capture，通过同一个市场请求接缝为每次闭合选择该日窗口。每次历史计算使用已有RetainedHistoricalModel绑定该次窗口的真实来源/因子/基准/接收时间；声明为按该日基准重建的回测假设，历史15:00可用属于模型，真实首次可知及修订保持unknown。每次原生回调先核窗口SHA和完整raw前缀，再调用唯一核，目标和财务处理保持原实现。

逐日API输入包含固定RetainedReplayInput、由A公开API打开的只读market_source，以及完整日期/窗口摘要和catalog manifest身份；窗口数量上限4096、每次编码/计算沿原总截止及容量。初始全量原价/分析值必须与目录末窗一致。调用者创建provider，回放类不接受代码路径或动态导入参数。配置驱动CLI和报告消费接线在本API主路通过后接同一合同，不能把直接调用验证授为CLI交付。

新报告族guanheng.retained-per-date-replay-report.v1明确per-date-front-ratio、每次历史模型/来源身份和原输出摘要，原最终批次报告族及validator保持其原范围。逐日BT与实时current-view的实际接收/决策时间、日线/分钟调度和成交模型分别记录；同输入比较须覆盖完整决策、EconomicTarget和数量状态，实际周期/资金/可卖不同导致的差异逐项对应原生事实。只有输入接收、纯核重复调用或末日flat一致不能授完整BT/RT资格。

逐日报告读取沿原backtest_reports.validate_report_dict和project_session_record，按明确schema选择准入，共用原财务、NSQ、周期和原生输出校验。逐日顶层historical_model为空；每条记录须绑定目录manifest、日期/窗口摘要、factor及实际known_at/received_at，并与该条决策的历史模型相符。报告快照、取消/截止及独立投影保持原边界；未知schema和失配字段明确拒绝。报告读取可独立验收，配置CLI和完整BT/RT继续分别登记。

验收：R28-C1原401窗/644808对接收及原类型解码；C2安装后逐日原生400回调及财务/用户状态文件、原外层Job回收；C3固定批次原路径回归及身份/窗口失配前置拒绝；C4配置驱动CLI/报告消费；C5完整400期BT/RT决策/目标及数量/成交模型差异核对。每项按实际证据登记，完整模块继续。

R28-C5的有限历史对照使用固定原WtCtaEngine、CtaStraContext、ManagedStrategyBridge和同一正式RetainedStrategy/唯一核/NSQ。测试宿主只调用原公开日期、会话、行情、bar和调度接口；原持仓、成本、可卖、费用、KV及文件仍由原WT生成。A ReplayCatalog拥有逐日原价和分析值，历史接收时间保持；比较适配器显式选择原RetainedHistoricalModel和历史时钟，不把当日15:00假设授为实际首次可知。原实时部署继续当前接收时间/新鲜度规则。

原实时Reader只提供当前日期之前的闭合日线；对照显式以每个基准日的下一原交易日期触发一分钟主调度，前一日收盘报价与后继原价成交分别标明模型及时间。原m1调度输入由冻结日线生成明确的单分钟模型，经原Helper落盘/回读；原d1读取继续原Reader，不自行产生复权价格。有限broker观察/成交来源只用于该模型并与原生持仓和提交来源绑定，不授真实Source/SDK/WinSHM或存量接管资格。每期保存完整决策、经济目标、数量状态及原生财务，并按时间、价格、成交/T+1和状态身份逐字段解释差异；全400期原CTA对照、正式WRI/持续AWP组合及真实来源分别验收。此接缝不增加WT核心行为或金融账本。

历史验证的Reader输入采用显式发布替身：A原逐窗raw数值经原Helper写入及完整回读为当期原价DSB，原因子文件、原分组native输出和目录元数据保持原字节，原Reader按已有publication入口切换并负责缓存清理。替身输入、收据和发布使用专用model schema并登记原窗SHA；该证据不授真实AWP生产者资格。INIT只读取当前已闭合的单分钟模型归档，后续分钟事件逐期调用原公开入口；整段未来归档进入原Reader被拒绝的试验保留为测试输入错误。

该历史模型在后继原交易日09:31使用前一闭合窗口计算并以后继原价开盘成交，随后按原HisDataReplayer的开/高/低/收四价模型更新原理论账本，15:00完成收盘标价和原session_end，下一轮才把该收盘窗交算法。末期没有后继原价时保留末日价格并明确标记；末期新增提交缺少可匹配原生结果时保持比较缺口。成交来源字段复制原WT模型成交CSV；原d1 Mocker记录的15:00与CTA的09:31分别保留。比较包含全部核心输出、完整NSQ状态、逐期计算前及日结后原生数量/资金、原生成交文件和最终金融文件。BT摘要省略的完整核心输出由原Porter已存观察重建输入，再调用同一原纯核；原input_sha/full_result_sha均相符后才进入比较。RT完整NSQ结果以原观察沿同一advance_retained重放核实。只归一已核时钟、周期与来源身份：按标的保持成交顺序、原C目标日期fallback与下一会话的日期映射、空仓/空条件记录及原生double金额在0.00000001元内的表示差异均须保留说明；份数、成交价格/数量/费用和其他差异继续逐项比较，未解释差异阻断完整一致结论。父完成证明与实际run/request/install/result/report原件交叉绑定。

可卖量差异始终进入未解释差异并阻断一致资格；数值形态或T+1原因标签不授自动豁免。容差内的逐期资金差异同样逐项保存原值与绝对金额差，保持可核对性。

## NRT-R29 持续发布的原生日线读取

状态：accepted / in-progress。对应 WT-D03/D04/D05/D09、R3/R18/R24。AWP 每轮生成新的只读 DSB 和原生因子目录；自有 RealtimeReader 的原 WtDataReader 委托当前固定于初始化目录。原 WtDtMgr 在基础周期倍数1且 force_cache=false 时直接调用 IDataReader，此公开接缝承担同一 CTA 的日线更新。实现限自有 Reader、配置与验证，WT 框架源码保持。

显式配置 `daily.publication={status_file,publication_file,cache_root}`，可选 `source_root`。路径均为绝对规范路径；status_file、publication_file 是可原子替换的普通文件，cache_root 是父目录已存在、由本 Reader 新建且独占的输入投影根。省略 publication 对象保持冻结目录读取。source_root 缺省为 status_file 的父目录；显式值只改变被授权的来源读取根，支持发布定位与不可变原件分开放置，保持路径后代准入。status_file 消费 AWP 已发布的 guanheng.qna-producer-status.v1/last_success，publication_file 为原 QNA 窗口。AWP 拥有目录、身份和发布时机；Reader 消费 last_success.work 下原 NATIVE-READ.json、request.json、prepared/INPUTS.json 及其声明的原 DSB、因子、原输出和元数据。窗口、输入、原输出及实际原文件 SHA、来源/因子修订和基准必须相符；每次读取仍核当前可变窗口和本次闭合截止，命中缓存只复用原件与委托。新来源目录限于 source_root；原生配置及符号与已准入映射一致，单文件4MiB（原输出/窗口32MiB）、每代固定与复制字节总计64MiB、句柄1024、切片和原总截止有界。目录按根到叶固定并核实际句柄的重解析属性，原文件在委托存活期固定为只读。可变 status/窗口采用可替换的短期读取，不阻碍生产者原子发布。

每次日线或因子读取在原 daily_mutex 下选择发布代际。新身份通过准入后，原 DSB 和因子按已核原字节复制到本 Reader 独占代际目录；原 WtDataReader 只读取此投影，源目录中的未声明 +/- 复权缓存或 RT 文件不进入输入。原 DSB 解码、因子查询和复权计算继续由原实现完成；同日修订按完整身份切换，基准日期相同仍能更新。旧 DailySlice 持有独立原输出副本，其 retain/release 和容量预算保持。缺发布、发布交接中或新身份失配返回不可用，由 R24 原生历史核对使策略等待。旧委托释放后只清理本 owner 创建的副本和空目录，意外新增文件保留供诊断；停止沿既有准入/排空/委托销毁顺序，无新增线程、金融状态或调度行为。

R24 的显式 market_window 消费者将原生 d1 的 CtaBridgeError(`native_read_failed`) 纳入原历史核对不匹配结果，沿既有 `waiting_market_input` / `market_history_mismatch` 投影等待。转换前仍核本轮原截止；数量状态和目标 setter 保持，下一回调重新核当前发布。`native_operation_failed`、其他异常和截止超限继续上抛；未配置 market_window 的原路径保持。

R29-C1：同一 Reader/原 CTA 实例观察首次发布、新共同闭合日、同日原价及因子修订，和原 Reader 对各代的输出逐字段一致；持有的旧切片在切换及 Reader 停止后仍保持原值。R29-C2：持续 AWP→原 Import/Reader/QNA→同一 CTA d1→唯一1.1.2/NSQ→原执行器/WinSHM SDK替身的完整主路径。R29-C3：身份/路径/字节漂移、发布交接、截止和停止分别验证，冻结路径保持；旧金融文件与未知责任恢复按原合同回归。R29-C4：普通独立安装、源及制品SHA、实际回收、独立审查与接口交接；完整系统候选和真实来源另由根集成。

## NRT-R30 当前持仓初始库存与新的运行基准

状态：accepted / in-progress。用户明确要求当前持仓保留，历史开仓记录、历史交易和旧周期全部不迁入，新增交易从新系统启用时开始。复用WT-S01/S05/S06/T01/T02、原P23初值加载和原R18/R24运行桥，具体设计沿[唯一初始库存方案](../migration/retained-strategy-takeover-proposal.md)。本项更新首次运行的状态起点，新增WT核心行为为0。

首次输入只要求当次有来源的持仓/可卖、资金、活动委托与有效标价及唯一策略配置。初始库存数量完整进入原WT策略及组合；本次标价成为原生新运行成本/绩效基准，起始历史费用及收益为0。原券商平均价仍可只读呈现。原生初始明细时间标识新运行起点，不称历史真实买入，不生成任何历史成交或SDK买入请求。行情日线继续供模型预热和信号计算。

自动准备的事实合同`guanheng.initial-inventory-facts.v2`包含原v1的数量、可卖、标价及来源/有效期，移除装配层推定的`trading_date`；相应`guanheng.cta-takeover.v2`由原生CtaProcess在首次加载时沿同一ExecutionEnvironment观察及WT原会话日历取得初始账本交易日。该日期在载入收据中明确登记为原生会话日，券商来源交易日的known/unknown保持原事实。原v1显式交易日输入继续严格核对原生会话日；重启消费原已保存状态及基准。此变化位于自有准备/初始化层，WT日历、金融格式和费用计算保持。

C唯一核明确初始库存的运行起点/来源与真实新成交周期的区别：初始年龄0，旧峰值/退出记忆为空，参考价格从新起点之后首根合格分析价形成；原角色规则保持唯一实现。B只装配初始事实及原KV状态，不补造旧开仓日，也不开发已取消的逐证券旧周期补齐。后续新买入按原真实回报建周期，部分增减及清仓按原规则处理。正常停止恢复延续本系统生成的基准、原持仓和数量/周期状态，重启不能再次清零。当前活动/未决/unknown责任继续原命令身份核查。

R30-C1：完全不提供旧开仓日期和旧交易流水，普通安装仍加载非空初始库存，数量/可卖与当次券商一致；零初始化买入，原生起始收益/费用0，库存市值与本金不重复计算。R30-C2：唯一核初始年龄/参考价/退出状态、新运行首轮目标、实际差额执行及启用后的真实成交周期通过；日内/盘后启动分别核首分析价。R30-C3：同根正常停止恢复保持原基准及新交易，既有未决/未知责任、T+1/费用与缺当次标价/观察分别按原语义处理；不要求旧历史材料。R30-C4：独立安装、源码/制品SHA、完整关闭、独立审查与C只读交接，真实启用另按授权。

R30-C1的系统启动入口由WT执行owner自动装配当次事实：使用原账户四查询和有效行情标价，调用既有initial_inventory.prepare_initial_inventory，再将原输入交P23和唯一策略。配置声明原账户/行情来源、策略模板、工作根与预算；操作员无需手写库存JSON，观衡不参与启动。原P23仍在加载前重新核当前券商及活动/未决责任。首次生成的基准和输入身份随原状态延续；resume_clean重用本系统原输入，原生重新查询当前事实，禁止每次启动重新准备新基准。四查询共同完成仅授各批来源与有效窗，沿原语义保留当前责任和非事务快照边界。自动生产者、非空库存原生主链及恢复按实际入口验收后，才授当前库存的系统自动启动资格；单独准备CLI的已验范围保持。

C已交付guanheng-strategy-v1==0.1.0a8的显式PositionCycle合同：初始库存使用status=initial_inventory、opened_at=null及baseline_at=本次启用时点；首分析参考价严格晚于该基准。B后继准备入口、原Configured提取和原KV保持该类型，部分增减继续原基准，空仓后新买入回到实际held/opened_at。原真实held周期的三字段KV保持其编码；初始库存KV含status、cycle_id、baseline_at、source_sha256，原state schema和clean文件所有者保持。原P23明细时间仅作原WT初始账本载入时间，策略核按baseline_at识别库存，禁止把它解释为迁移前真实开仓。a7上已封候选保留原限定资格，运行侧精确依赖更新到a8，观衡冻结读取包分别保持。

自动选择位于原guanheng.execution-deployment.v1的可选initial_inventory对象，包含schema=guanheng.initial-inventory-start.v1、state_root、account_observation={descriptor,sha256}、market={base_url,token_env,timeout_seconds,max_response_bytes}、max_age_seconds；仅限python_strategies=true。state_root为首次独占创建的新E盘准备根，保存基准和原输入摘要，不持有账本；原控制目录每代保存实际原生配置。已有完整准备材料在resume_clean中只读核同源模板/来源配置/摘要后复用，原金融目录和未决责任仍由原P23及clean协议准入。读取、准备、生成配置和启动共享原启动截止；账户单轮资源沿原ManagedAccountScan回收，原监督者继续拥有停止、Job和证明。省略此对象保持既有执行工厂。

准备Scan一经准入也受首次停止截止约束，即使执行进程尚未启动。超期后续close继续核资源回收并保持停止超时；原截止内确认完整关闭后允许幂等成功。验收覆盖Scan在首次短close超期后才完成，以及原截止内正常完成的重复close。

## NRT-R32 原命令待核查期间的执行连续性

状态：accepted / implementation-in-progress。沿原query_first路径处理原命令结果暂不明确的情况，默认native路径保持。QMT passorder合法返回None表示SDK调用返回，不要求同步返回券商订单号；原完整token及后继O/成交关联继续识别原委托。

自有Standard新增可选只读C入口`inspectStandardQmtAwaitingObservation(ITraderApi*)`：同owner返回1仅表示query_first的unknown等待且无hard_fault、关闭或独立入站/owner错误；返回0表示该等待资格不成立，负值表示调用错误。旧diagnostics/recovery布局保持。宿主从原同DLL可选解析该入口，缺能力沿原失败路径；有能力时单独的待核查保持账户查询、行情/目标队列及原订单定向撤单，原新insert仍由提交组及原通信准入保护。硬故障优先于等待，不靠首错文本推定健康。

原命令的GET/审计沿原UUID及轮内原D继续，不重POST原insert。首次写回复进入待核查后立即安排原ID只读审计，单请求request_ms继续约束该请求，后继未核清审计仍按原有限间隔推进。完整O及后继同来源P仍交原SPI和原Adapter，不自行计算持仓。原调用后来明确SdkReturned，或按下述独立证据核清券商终态，且该原组已通过终态O→后继P、原pending移交完成后，才可退役该组及仅由它形成的本地等待；Journal或源端尚有未核清责任、硬故障时继续保留等待/保护，不伪造成功或clean。正式活动单重启继续按实际实现验收，不从只读接口存在推定完成。

Common私有friend接缝有两个调用时点：审计期在原查询reference已存在后重核当前Host/Source独立终态资格，此时Standard仍保留原提交组和新insert的fence；全部旧组经原WT O→P退役后，在新insert之前再次重核当前准入。两阶段分别消除客户端已核清的本地锁存并保留Standard实际应用责任。该入口不对外公开，不接受人工“已确认”布尔值，不清硬故障/关闭。服务端仍未知时返回SubmissionUnknown；重核发生HTTP/运输/截止失败时恢复保护并保留实际Status，意外异常锁存固定硬错，不将读取故障伪装成订单未知。普通Common消费者和默认native路径保留原语义。query_first遇到Unknown先保留收据并交还原worker，后继只读审计继续原身份；原Queued/Dispatching沿原D等待。

SDK实际进入后异常的原结果继续保留unknown。自有接入层允许独立核清该原insert的券商处置：原账户ORDER完整查询须以完整token唯一匹配原账户、证券、方向、原数量、限价及有效券商订单号，并明确为终态。Source原线程仅据自身实际查询解除该命令造成的等待，Host仅据原Journal已保存且重新验证的查询证据解除对应等待；其他unknown、硬故障、关闭与事件缺口继续独立阻写。查询空表、活动/部分成交订单、字段缺失/冲突均不授此资格。原SDK阶段/原文/截止保持，原insert仍禁止重发；不新增金融账本或数据库。

Standard仍按原UUIDGET及原ORDER查询核查，在原Host与Source均确认当前准入后，单独记录该原命令的券商终态已核清，保留SDK阶段unknown；随后完整O和后继同源P交原WT，才退休原组、允许实际后继差额。自有观察只决定通信责任是否核清，持仓、成本与绩效仍由WT拥有。未知cancel保持原定向核查及保护，不能用本项insert证据清除。

验收R32-C1：合法None/无同步订单号，原token查单并由WT消费P/剩余O，原SDK一次。C2：运输未知后原UUID核实SdkReturned，终态O和P后实际后继目标只提交真实差额，原insert不重发；未查明继续等待。C3：原SDK真正unknown的insert在实际终态ORDER核清、原WT应用O/P后实际继续；缺记录、活动/部分成交、冲突及后继硬故障分别保留身份和保护，定向撤单仍核真实原单。C4：正式CTA计算/数量阶段、原周期/账本、完整关闭和普通安装分别验真；新增WT框架行为0。

## NRT-R31 实时执行阶段按券商实际数量确认

状态：accepted / in-progress。对应R18/R24、NSQ-R3/R4及ADR-0001/0003。SRI003同次SDK完整主链中，券商和SDK持仓一致，原CTA理论持仓已达到目标；薄桥把理论数量作为NSQ actual输入，产生converged/frozen_buy_actual_confirmed。原件与固定交接位于build/root-continuous-system-003/qa-main-001/preparation002/main002，11条1000份委托与实际成交守恒，后续目标差额尚未形成实际委托；执行继续推进的直接原因须沿同次目标/订单责任另验。新实现限自有桥、原数量模块及已公开券商观察，WT框架和算法数学保持。

R31-C5的长场景夹具将原公开`budget.run_ms`显式配置为1200000，与主场景1200秒同量级；原短夹具300000毫秒会在场景结束前正常走关闭准备，监督者随后按原合同报告unexpected_exit。此项只改变新隔离场景的运行寿命配置，原启动、单请求、排队、SDK、策略计算、来源新鲜度和停止截止保持。账户发布读取复用已安装App的原NAP大帧读取器及其缺文件、pending和Windows32/33重试分类；子进程监督、重试、读取及解码共用该次最早观察截止，协议错误立即失败。历史短场景与失败原件保持各自身份。

实时桥在同一回调内分别构造原CTA理论观察和券商执行观察。原理论持仓、价格、flag0损益及理论现金继续用于策略财务basis；执行观察的actual/sellable来自本轮已验证新鲜度与完整覆盖的券商P，零行证券为明确0。当前唯一策略拥有全部管理库存，映射范围与原启动校验一致；其它策略或人工混用沿原归属要求另验。pending_target仅沿原CTA尚未执行信号，不从目标与券商数量差额猜测活动委托。实际订单防重和剩量继续归原执行器/Adapter，薄桥只提交原绝对目标。

财务观察按有开仓条目的原生实际持仓形成。空仓的财务可卖量为0，原始raw_valid要求数值有限并原样保存在raw_positions；有持仓时继续核非负整股份数及可卖不超过总量。空仓未消费的理论可卖字段不参与执行判断，也不阻断已确认的券商清仓；当前P仍是执行观察的唯一数量/可卖来源。原WT持仓、冻结量、费用和损益保持原值。

两份观察及basis绑定同一次理论/券商来源摘要，NSQ实际消费券商执行观察；未达到冻结目标时保持原buying/selling/waiting阶段，禁止用理论到位交接新经济代际。报告保留native_observation表示原CTA理论账本，broker_position_qualified=false继续限定这一兼容字段；新增execution_observation及execution_position_qualified明确实际阶段来源。完整账户P未知/过期时沿原waiting_broker_position，不增加查询、持仓归约或金融账本。正常恢复复用原KV/clean及代码身份，重新确认本代实际P；历史旧版状态与冻结模型按原身份保留。

R31-C1：固定同次部分成交/理论全量输入驱动实际完整回调，旧版复现错误收敛，新版保持buying并保留全部冻结目标、实际数量及原理论财务值；SDK调用和新增来源查询0。R31-C2：短原生/SDK主链按相同目标、分单及查询/回报推进到实际数量相等；若仍停留部分数量，继续定位原绝对目标/活动订单链，阶段不得误报完成。R31-C3：卖出未完成与后继买入、原pending、新代际到来、未知/过期P及同根恢复均按实际数量与原订单责任核验。R31-C4：普通安装及搬迁、源码/wheel/Native身份、两轴独立full/delta、接口交接与受影响读取消费者分别登记，完整系统与真实券商另验。

R31-C5：完整功能链与性能观察分别验收。现有SDK场景`continuous_rounds.run`的`until(observed,70,...)`为QA单轮总体观察窗口，原70秒失败、对应输入及清理证据保持。新的SDK替身完整功能场景使用每轮240秒观察、主场景1200秒和外层1500秒总预算，覆盖连续三轮卖出/买入、券商实际数量确认、正常停止和同根恢复。该总预算只约束QA观察；单笔请求、队列、SDK调用、未知提交处理、计算、来源新鲜度、关闭及资源回收继续沿原产品配置和原绝对截止，代码/输入身份分别绑定。来源回调100毫秒、6982证券工作量、65秒晚到模型、目标数量、分单、资金/T+1/费用和原业务断言保持。未知委托保留原身份且禁止重新提交。新场景结果授相应功能范围，70秒性能资格独立保留待验，不改写历史失败或把更长QA观察宣传为产品时延收益。真实QMT和真实交易资格继续按明确授权验收。

持续分析发布者按原来源接收时间生成多份合法窗口。QA对每次决策核其精确publication_sha256对应的原PUBLICATION收据、原候选与Native摘要和capture身份，按生产者原时间赋值与canonical编码重建发布摘要，再核本轮expected的basis/原价末行。首份发布之后的同轮合法更新继续参与状态核验；原策略收敛、逐证券实际数量、提交修订、全部成交映射和账户投影断言保持。缺匹配收据继续等待，摘要冲突直接使QA失败。此核对仅在隔离验收工具读取原发布证据，产品发布和金融状态继续由原owner承担。

## NRT-R33 自有委托撤单收束与重新计算（简版）

状态：accepted / development-qualified。主链与定向回归、两轴独审及Root源码接收完成，既有开发记录保留在外部历史归档（原路径：`docs/evidence/2026-11-01-module-b-development-completion.md`）；本次实际只读恢复范围见[恢复记录](../evidence/2026-11-03-strategy-readonly-recovery.md)。按用户最新要求，本期采用停止新增提交、撤清已核归属的自有活动单、查询确认终态、重查券商资金/持仓/可卖，再由正式1.1.2重新计算。复用WT-S01/S05/S06、WT-T01/T02/T09及原P21/P24正常保存入口、Host Journal身份查询和原定向撤单。此前已合入67ebb99的R32未知连续性保持。本节替代尚未交付的活动挂单接管、中间拆单阶段续接和全量金融/KV重放计划。

自有宿主在正常停止时先停止策略/目标生产者，只暂停新insert，继续原查询和定向cancel；沿原完整ORDER查询表取回本执行通道的已映射本地订单ID，逐个调用现有cancel。每单只提交一次，重复观察继续核同一原命令。原SDK或身份/撤单结果不明时保留原ID和保护，截止内未核清则报告原责任，不产生成功恢复证明。原表未归入本执行通道的人工/其他系统订单保持。is_cancel_unmanaged_order始终为false，不扫描撤销整个账户。

原自有单均为终态、原组/命令已核清后，执行后继完整POSITION和ACCOUNT查询，使用券商总量、可卖、可用资金，再沿已有WT正常保存/关闭流程保存必要策略记忆。账户中仍有人工活动单不等于本执行通道有未完单；原表和原责任共同判定本通道收束。已确认关闭的原文件仍按既有clean入口恢复。状态损坏或缺少现有必要恢复依据保持明确拒绝；本期不增加跨版本修复或全部状态重放体系。

重启前复用相同查询/定向撤单/后继P和A流程。保留WT原策略账本、绩效、周期/止损及退出记忆；原NSQ未完成执行计划从当次券商事实重新计算，不续接旧拆单数量阶段。唯一受管1.1.2使用已有gh_ms_status/setters观察首次新目标计算完成，在此之前暂停新insert，原行情及查询继续；暂停解除不清除未知/硬错误保护。此过程复用现有用户状态格式，不增加金融账本、持久恢复阶段或WT核心行为。

原start/close截止贯穿收束：每次O/P/A查询或定向撤单入队前，以及每次pump返回后，都重新核同一原截止；晚返回已满足观察条件时仍禁止越过截止发起后继动作。A与O/P共用原任务序号语义，只有P之后新发起的完整ACCOUNT经原SPI应用并返回后，才满足资金刷新。StandardQmtRecoveryV1追加last_account_query，零表示尚无已应用A；sizeof从64变为72，仍严格核version和size后写出，旧大小组合明确拒绝。宿主、Standard及使用该结构的消费者同批重编，持久文件格式保持。

R33-C1：仅运行一个全新SDK独占主场景：正式1.1.2产生一张明确自有200份卖单、实际部成40，另有一张未归本通道的人工单；停止时只定向撤原剩160，完整O确认终态，后继P确认160及可卖、A确认资金，再正常保存；重启以新事实重算并只执行所需差额。核原单不重复、人工单未撤、必要周期/止损记忆保留，最后正常撤单收束与完整回收。相同字节的既有正常调仓、未知连续性、构建和审查证据直接复用；只重验本节实际改变的主链。源码/制品SHA、普通安装、同批消费者和必要独立审查沿原规范交付，真实QMT下撤单和生产切换分别保持未授权。
R33-C2：针对独立审查发现的截止晚返回和旧A交付，使用实际收束函数做定向红绿回归；随后沿匹配Native组件运行原R33-C1，不重复未受影响的53笔、R32与回测主链。

## NRT-R34 显式当前策略总资本与只读资金接线

状态：accepted / in-progress。用户2026-11-02明确指定正式共振市场状态ETF最新版当前总资本1,000,000 CNY，包含已归属该策略的库存；旧资金恢复停止。复用WT-S05/S08、WT-T01、原QuantityPolicy、R30初始库存及R33正常恢复，新增WT框架行为为0。

首次启动的initial_inventory可显式配置capital={total_cny,source}，本次候选值为1000000及用户决定来源。准备owner据此生成原QuantityPolicy.initial_capital_cny和capital_source，并保存独立capital_baseline：新运行基准时间、当前总资本、声明来源、historical_initial_capital_cny=null。原字段名承担本次运行的资本起点；旧模板金额不当作历史本金。库存已包含在该总额，初始化不把库存市值再次加到本金上，不生成买入或历史收益。正常重启复用相同输入/SHA及原WT损益；新基准不再次归零，配置变化按原身份拒绝。

原账户观察owner在既有独占根内原子发布current.json当前引用，金融正文、账户绑定、完成资格和各批原时间继续由原NAP文件拥有。当前资本路径要求同一Runtime配置该账户观察owner及相同Scan配置；策略只读此引用和原帧，无新增查询、账户资产分配、成交流水或金融账本。引用换代允许正常恢复；静态路径/Scan绑定参与原配置身份。

NAV=当前资本基线+原WT flag0损益；现金余额=NAV−完整券商P持仓按当次原CTA价格计价的市值；持仓、价格和账户约束分别保留原时点，不宣称共同事务。原理论观察继续单独发布，实际执行持仓/阶段仍沿R31券商P。可用现金=min(max(0,现金余额−原账户m_dFrozenCash),原账户m_dAvailable)。m_dFrozenCash作为账户级保守现金约束，不声明它归该策略，不与保证金或冻结佣金重复相加；NSQ继续独立核新增买入组费用预留。账户总资产不进入上述公式。缺少/过期/失败的账户冻结来源令本轮可用未知并沿原waiting_basis等待，最后成功账户值及其原时间可只读保留，缺项不得默认为0。

新增买入组的费用预留由执行owner装配。冻结输入已显式提供fee_reserve_cny及fee_source时保持其原值；缺显式预留时，从本代已按制品SHA准入的原WT fees.json取得开仓费率，复用原NSQ target_quantities计算本次实际消费目标相对完整券商P的正买差，并按同次原价估计费用。按份费率直接作用于份数，按金额费率作用于原价乘份数；每股向上取到CNY分，累计成可覆盖整数股部分成交舍入的保守组预留。来源明确标识原费用文件SHA及估计规则；显式零费率可产生有来源的零预留。该预留是策略预算的配置模型值，不代表券商实际佣金或额外现金；原WT仍按真实新成交和原模板独立记账，费用资料缺失/无效保持原准入拒绝，NSQ收到未知预留时继续waiting_fee。卖出结清后使用新basis重新装配；旧经济代际先推进和新代际交接分别绑定各自实际目标，NSQ原份数、阶段、冻结状态和全组现金约束保持。

费用装配的原条件、旧代/新代交接及资金约束验证见[买入组费用输入证据](../evidence/2026-11-04-wt-buy-fee-input.md)。

初始化估值与正常回调共用上述预算公式。WT理论目标与券商实际数量在执行、部分成交和重启时可以不同；该差异不构成账户现金未知。资金观察保留WT损益、完整券商数量、原价估值及账户现金约束各自来源；恢复材料保留原基准、金融文件和成交身份，不据理论目标推定实际成交，也不新增现金账本。

原策略结果新增capital_baseline及capital白名单，明确NAV、持仓市值、现金余额、可用现金、原WT新运行损益、账户约束来源/时间和当前资格。原账户约两亿总额仍只属于账户展示。观衡GET沿原WRI→ready→策略结果读取此发布；当前总资本与旧历史本金、历史收益分别显示，旧本金及旧收益保持未知。页面布局由Root集成，本模块交付只读可消费字段。

现金余额为负且账户来源完整时，可用现金按上述公式为0，仍保留已知负余额。账户来源不可用时，由自有Configured层在调用原NSQ前发布waiting_basis，保留原阶段、未决目标和退出记忆，本轮不提交新目标；后继有效来源继续原NSQ。引用和正文读取共用本次回调原截止，过期停止后继读取并释放已开句柄。只读金额等式沿精确有理数核对，保持生产者原金额及原时间。

R34-C1：普通安装配置1,000,000总资本，已知非空库存进入正式1.1.2/原NSQ，人工可核的NAV/市值/现金一致，无初始化重复买入；账户总资产约两亿不影响目标或策略资本。R34-C2：SDK替身完整九组件主链正常停止并同根恢复，资本输入、原损益、现金、持仓及后继目标一致。R34-C3：非零冻结、账户可用低于策略余额、缺冻结/过期/错误绑定、同时间来源保留、输入资本漂移和现有无capital路径分别回归。R34-C4：只读消费者实际GET、独立候选、来源/制品SHA及CAS清单、原框架0变更与独立审查交付；QMT/实际下撤单和生产发布不在本次范围。

持续分析接入沿EFR-16/17：原QNA history原价与原PublishedDaily Reader逐字段核验，前复权分析值由原QNA独立提供。当前估值读取原ManagedStrategy已应用tick的有界副本及其原事件时点，日线读取使用框架既有行为；trader.writes_enabled=false只发布分析/资金观察，不调用NSQ推进或目标setter。原模型、金融账和五周期沿原接续材料核验。
