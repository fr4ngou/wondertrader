# 执行故障核查恢复

EFR-27：query_first事件接入中，撤单调用完成或已验证业务错误通知后沿现有owner安排完整订单复查；周期刷新启用且存在活动单或原提交责任时，沿同一队列执行O→P→A。重复触发合并，在途查询不能消费入队之后的新触发；完整原结果交付后才能推进阶段。普通无未结订单的A/P及原读取恢复四查询保持。撤单明确未发出或SDK明确返回的业务拒绝继续原WT错误通知并核查原单，不写成通道首错；未知调用及运输/身份故障沿原核查。当前列表缺行不证明原单终态，跨日覆盖核实沿[专项方案](../migration/qmt-cancel-reconciliation-proposal.md)，实现和现场资格分别记录。

EFR-24：普通已报/部分成交委托属于可接续的券商事实。恢复与正常停止沿原完整O→后继P→A查询，核原命令、WT本地ID和券商身份；已知活动委托保留在原WT订单表及通信journal。停止只关闭新增提交并排空在途调用，不要求已知活动委托先成交或撤清。未知调用、缺身份、原组未返回及终态后P未同步继续沿原核查，不以超时清除责任。

EFR-25：同策略恢复保留原NSQ冻结阶段及周期，原订单表的活动委托以只读值传给数量观察；有活动委托时不把实际持仓等于目标误作阶段结清。WT继续负责余量、撤单及拆单；自有层不维护第二份订单表。历史角色替换标记只持续约束退役角色，首次角色换代才要求新角色没有旧委托。

EFR-26：股票执行器沿原expire配置启用超时撤单，0明确表示关闭。显式发行交接允许修改expire及is_cancel_unmanaged_order执行参数，持仓、资金、原策略状态和原件摘要保持。当前单策略的重启挂单由WT原check_unmanager_order与cancel入口接管，原Adapter仅暴露已核自有订单。发布检查对照预期配置、生成配置及实际初始化日志；不通过删除原生执行参数获得表面可运行状态。

EFR-23：显式同业务发行交接同时支持数量实现包guanheng_strategy_native源码及其版本元数据升级。沿原load_transition先核完整前后配置、签名材料及实际源码绑定；NSQ继续重建并校验原冻结结构、经济身份、数量向量及资金不变量。该选择仅由已核同业务transition的strategy_upgrade路径提供，普通比较及单独角色换代保持原严格行为。纯Core、解释器、账户、资本基准、金融根、策略输入与未决身份保持；不重置状态或补写正常关闭证明。

EFR-22：显式同业务发行交接允许策略实现包升级。load_transition先核前后实际配置的业务兼容、原源码绑定和当前完整源码身份，再允许guanheng_strategy_v1源码及其版本元数据变化；原纯Core、NSQ、解释器与其他受管依赖逐件保持。账户、资本基准、输入、周期参数、金融根及持仓事实沿原配置和原状态加载校验。该能力属于已有明确发行材料的实现换代，不依赖零持仓角色替换，也不增加用户策略上线审批。单独的源码比较默认保持原严格行为，角色替换仍核真实正常关闭及原零库存要求。

已绑定的 Host/Agent 通信实现也可随同业务发行升级，但同时要求原 Source 交接证明已核验。只授上述已登记通信 owner 的源码及发行元数据换代；缺任一资格仍拒绝，纯 Core、解释器及其他受管依赖保持原检查。Source 的账户、权限、投影协议、Journal 采用及未完责任继续分别由原 owner 和原版本维护验证，不由包版本变化推定。首次接入沿原完整新增资格，已接入后的正常升级复用同一组 owner 声明。

类型：规格与模块契约。状态：accepted / in-progress。适用范围：自有执行宿主、Python 配置与原状态加载；WT 核心保持原行为。主会话于 2026-11-02 确认实施。

EFR-01：显式 recovery.mode=resume_reconciled 使用同一原 O/P/A 查询、自有委托收束、输出租约、WT load_data/load_userdata 与正常关闭流程。现有 record_clean/resume_clean 保持。恢复差异集中于首次准入依据。

EFR-02：recovery.transition={file,sha256} 引用受控发行材料 guanheng.execution-recovery-transition.v1，文件容量 1 MiB。字段 predecessor_configuration、predecessor_configuration_sha256、predecessor_control_directory 定位上代实际配置与控制收据；predecessor_installation_sha256、successor_installation_sha256 绑定前后安装；predecessor_python_binding_sha256、successor_python_code_identity 绑定前后 Python；state_files 为原 stradata/userdata/portfolio JSON 相对路径→SHA256。字段均必填，路径为绝对路径、摘要为 SHA256；材料由部署者冻结并经当前配置摘要绑定，不包含账户凭据。

EFR-03：原 owner 在上代 ready/failure/close-prepared 的控制 ID、PID、配置摘要相符，原 close-prepared.closed=true、ok=false 且上代进程已退出后，沿同根 OS 租约重验原状态集合和摘要。前后逻辑配置去掉 recovery 后保持相同；当前安装清单完整核验并匹配发行材料。上代安装身份沿已消费来源或上代核查收据核验。已就绪的原生进程在最后关闭阶段以 recovery_state 或 cta_close 失败时，可用同身份的原 close-prepared 和 lifecycle-finished 证明原生关闭。要求 close-prepared.closed=true、ok=false、recovery_ready=false，终态和原启动回执均匹配原 ready，且终态晚于启动。原 failure.json 存在时仍按原故障核验。两类故障依据共用原进程退出、状态摘要、账本租约和券商核查，保留原失败记录。独立 cta-reconciled.v1 记录单次认领，原故障与正常关闭证明保持各自语义。状态变化或相同材料已认领时拒绝。

正常关闭后的自有适配兼容发行使用同一 resume_reconciled 交接身份：完整核原 closed.v2 与 clean.v2、原文件/安装和实际退出，再沿原协议原子消费该次 clean。其收据 admission_kind=clean_transition；故障依据 admission_kind=fault_reconciled。原始正常/故障事实分别保存。每代 Native 自动保存 installation-identity.json；前代安装证据缺失时明确拒绝。

EFR-04：Python以原绑定文件集合计算前代代码身份，核后继完整绑定与显式发行身份；实现升级沿EFR-22/23，金融模型、原数量不变量和解释器保持。策略记录按版本化业务模型身份及规范编码完整读取，保存冻结阶段、原序号、周期/止损和退出记忆；部署代码身份由原绑定独立核验，INIT保留原payload并按需补齐ctx镜像；后继O/P事实交原NSQ推进。首次角色换代按角色契约退役原计划，普通同策略恢复保持原计划。

EFR-05：订单与未知责任归原通信owner。复用既有自有活动单识别、原命令核查、原WT订单表及后继P/A；已知挂单可接续，撤单沿原执行器策略，人工或其他通道订单保持原归属。产品恢复核实际未决调用，历史委托数量及普通已报单不构成启动拒绝条件。查询不完整、未知提交或终态后P尚未同步时保留原身份与核查责任；实际运行资格以对应发布证据为准。

EFR-06：首次成功恢复后原正常关闭生成现有 clean 证明，后继 resume_clean 使用本代状态身份。恢复材料和核查收据属于审计证据，WT 原金融文件与 KV 继续为唯一账本和策略状态。当前原基准及输入不重新准备。

EFR-07：主链验收先复用已有 SDK 安装场景，再沿当前只读实际来源查询、恢复与资本发布；随后补根因回归、边界和独立审查。交付绑定源码 CAS、制品、实际四身份、基准及状态前后证据。

EFR-08：首次只读估值与策略行情准入分别负责。当前原 MarketClient 返回有资格、来源时间已核且价格有限为正的最后快照时，闭市报价年龄不阻止原策略状态恢复。observed_at是实际完成本次估值的时间，必须晚于所用持仓观察；可选price_observed_at独立保留该批最早报价事件时间，CTA无法提供时为None。原快照全文保存在initial_market_observation。原CTA损益、持仓接收时间与当前账户批时间分别保留。策略行情/信号资格继续沿原闭合K线和分析输入准入，报价年龄不改变已知现金账事实。首代基准准备的行情有效期保持。

现金依据复用原WT上下文flag1已实现盈亏、flag3费用和各证券原平均持仓成本，沿原借用期只读扩展gh_ms_cash_basis ABI1取得；原MS ABI和既有结构不变。CNY现货配置及实际券商数量与WT持仓一致时，现金=原资本+原已实现盈亏−原费用−原持仓成本。原资金账、完整估值关系和当前NAP账户约束共同核资格；已知现金与有效NAP可以发布原保守可用额，报价过期单独影响估值/证券交易时效。现金或估值依据暂缺时仅令capital不可用，原策略恢复和等待行情继续；原KV/投影保存失败仍沿原失败语义。资金观察成功后，账户续发使用原已知现金余额及原估值/报价时点，不按报价年龄撤销现金资格、不由页面补值。

EFR-09：只有完整响应固定机器类别 503/strategy_stale 的只读 read-binding 在原请求截止内等待原 Source 重连。读取 owner 每轮检查原停止 gate。其他HTTP错误、原ID结果读取及所有POST保持原单次身份与责任。跨来源绑定变化需要整体读取代际交接；单独账户重绑不足以获得持续跨代运行资格，当前明确保留该缺口。

EFR-10：报价暂不可取得时，resume_reconciled 可沿已绑定的前代配置/控制链读取最后合法原QMT快照。每跳核原配置SHA及相同业务配置，并限16跳与原启动截止；原观察的基准、持仓数量、周期、WT现金依据和损益须与本代原上下文完全一致。以当前数量重新估值时保留原price_observed_at及原快照全文，并记录原控制/文件SHA和原估值时刻；当前WT现金与NAP账户约束分别现取。缺原件、账/数量/周期变化或来源未合格时保留资金未知。该路径只复用原报价事实，不重建现金账，不授策略行情时效资格。

EFR-11：连续运行的只读查询或事件读取遇到明确503、运输超时或同来源运输绑定变化时，进入读取等待，暂停新金融准入并保留原策略状态及进程。已进入SDK且结果未知的查询保留原UUID、完整绑定及原SDK请求截止，旧观察交付截止保持原值；后继仅以独立有限核查预算GET原结果，不重新提交SDK请求；原结果确定后再进行新的完整O/P/D/A观察。每轮运输及观察保持原有限截止，停止沿原gate和关闭预算。来源业务session、账户、认证、profile或数据合同冲突继续硬故障。等待状态沿原进程身份的私有read-status收据记录转换，旧观察时点保持原值。该可重建收据发布失败沿固定间隔重试，执行事实及退出语义保持。读取仍等待或原UUID未收束时，恢复检查标为unsafe，正常clean准入等待原责任完成；关闭截止耗尽继续保留失败收据和原Host Journal。

材料生成器的 successor-python 必须为部署实际使用的解释器入口，绑定对应 venv 与基础解释器的实际文件摘要；CLI 的窗口模式不替代实际 owner 身份。

模块入口：Python [execution_recovery](../../apps/wt_runtime/guanheng_wt_runtime/execution_recovery.py)、原 [execution_process](../../apps/wt_runtime/guanheng_wt_runtime/execution_process.py)、[configured](../../apps/wt_runtime/guanheng_wt_runtime/execution_configured.py)、[Native 准入](../../src/GuanhengExecution/CtaProcess.cpp)。关联原 [NRT](native-realtime-strategy.md) 的 R12/R33/R34；正常恢复唯一语义保持该正文。

EFR-12：原账户读取Host在SDK派发前因运输绑定变化或排队超时形成合法失败终态时，Native完整核原请求/正文摘要、固定错误码及空dispatch_binding/result_binding，确认原SDK未执行并结清原责任。随后通过原读取代际准入新观察，来源业务session及profile检查保持；有派发绑定、坏正文或未知执行继续原核查/故障边界。该固定终态解码适用于已声明的普通账户读取协议，不能只在retained票据协议识别。

EFR-13：账户资金约束线程每轮沿原有限预算读取权威NAP，即使金额相同或没有新K线也按原来源批次更新。可重建观察投影的锁等待、写后截止或Windows共享句柄等待耗尽，只结束本轮刷新；独占发布者清理本轮尚未提交的临时文件，保留最后成功投影及原来源时点，下一轮重新读取。原子替换是提交边界，成功后内存发布状态同步推进；随后到达截止不撤回已提交状态。已有外来pending、容量/数据错误和非共享类文件错误保持硬故障。原K线回调继续传播发布失败，金融保存及已发生setter保持原owner和失败语义。

EFR-14：整树退出且原owner来不及发布关闭收据时，独立WT入口以显式record-process-loss核原ready、status、配置摘要、实例身份、原父/组件PID实际退出并取得原实例OS租约，记录owner-loss故障及当前faulted状态；components_closed=false表示原Job/线程join凭据缺失。原ready、原金融文件和通信Journal保留。执行恢复owner独立核原Native ready和配置摘要、原PID实际退出，独占发布guanheng.execution.owner-loss.v1，包含control_id/config_sha256/pid、原ready摘要、固定reason=process_lost、核查UTC时间及核查者PID；该记录仅证明进程已退出，关闭结果及退出码保持未知。

普通启动与显式采用共用退出核查。原 WT 已有故障收据、但执行进程因强制终止而缺关闭收据时，先核实实际进程退出，再发布原生退出证明。后继启动在原生接账期间失败时，只有控制记录确认执行队列从未开放、未认领原交接、未发布启动收据且金融文件未变，才沿最后有效执行进程继续核查。启动错误保留初始化步骤、涉及的受控收据名及系统错误码。

持续分析窗口发布线程归 WT。其固定状态类型可省略 PID，退出核查使用已验证的 WT PID。显式 PID 须与 WT 相同。刷新工作进程由 WT 持有的终止型 Job 回收，其他独立组件仍须提供原 PID 并逐项核退出。

显式resume_reconciled可沿该owner-loss作为第三类故障依据。Native在原输出租约内重核原ready字节摘要、完整身份、进程退出、两代安装/Python、原金融文件集合和当前券商O/P/A及原自有委托/未知责任。仅缺原正常closed/close-prepared/failure时接受该依据；现有正常/故障关闭语义保持。认领收据admission_kind=process_lost_reconciled，后继正常停止仍生成原clean。活进程、缺原件、身份/状态变化或当前责任未收束继续拒绝。过程不删除锁、重建基准、重发交易或生成正常关闭证明。

EFR-15：首次Prepare/Login只读取来源绑定及事件上下文，尚未触发SDK账户/交易请求。固定暂不可用类别（完整503、运输超时）或成功完成值晚于本轮截止时，原任务名额先退役，再以同类新有界任务继续来源准备；原绑定的来源业务身份仍逐次核验，旧轮次不交付Connect/Login成功。首次客户端已经固定的绑定发生冲突时保持原硬故障，由整体启动重新核验；本项不授首次准备跨运输代际资格。启动外层总截止及停止gate继续有效，每轮保持原timeout_ms，硬身份/协议错误继续故障。已登录账户查询及已提交SDK请求继续EFR-11原ID核查语义；此首次准备续接不扩展金融重发权限。

EFR-16：同账本首次接入持续分析及当前报价，可显式提供market_input_origin={schema:"guanheng.market-input-origin.v1",file,sha256,quotes?,parser?}。file为原实际execution.json绝对路径，sha256绑定其原字节；原件自身不得含该许可。quotes可选，精确字段base_url/token_env/timeout_seconds/max_response_bytes/max_age_seconds分别为既有本机HTTP报价入口、受控环境秘密引用、单次秒预算、响应字节上限和既有资金来源有效秒数；原始事件时间保持，配置不携带秘密。parser可选，精确字段module/base_url/key_id_env/hmac_secret_env分别声明ParserQMTHostRetainedV6只读适配、既有本机v6 Host和受控环境认证引用；仅替换原单个ParserQMTHostV6的模块及三项连接，原profile、符号/周期、轮询及容量保持。该适配复用原QmtPollingParser和FullTickRetainedV6已确认消费协议，WT框架及调度保持。

该许可只增加R24 market_window、同一publication的daily.publication及可选当前原价/Parser连接，准备阶段原BASELINE模板输入/账户/估值身份保持；实际Native再次严格核原takeover、模型、金融、账户和执行配置。当前capital_market及Parser连接须等于显式声明，比较原业务身份时还原原来源引用，其余字段逐项相同。

恢复材料仍绑定两代真实配置/安装/Python及原金融状态。状态模型身份按EFR-30绑定真实market_window配置；窗口配置变化时先明确迁移状态，INIT保持已迁移记录；原周期/NSQ/模型继续原owner。正常关闭证明始终校验前代原业务配置摘要，新增只读引用不改原clean事实。原分析窗口和真实原价各自核来源/单位/时间，闭合日和当前报价时点分别发布；原实时主1分钟事件触发唯一1.1.2计算，INIT只读验证不冒充决策。

EFR-17：持续行情的当前报价由原ManagedStrategy.on_tick在原WT已更新该tick浮盈后复制到本策略固定读取集合的有界槽，保持原action_date/action_time/price。新可选gh_ms_quote ABI1与layout8复制该值，沿原同线程epoch及已授权读取证券准入；尚未收到tick返回UNKNOWN，原price接口及布局1..7保持。Python quote返回独立不可变值；持续窗口模式核原事件时点/有效窗并用于估值及数量basis，日线读取改变原CTX价格缓存不改这份已应用tick观察。INIT独立报价仍分别保留来源和时点。

原WT double浮盈在转为精确十进制后，与原成本账及份数乘原价的重建值允许绝对差至0.00000001 CNY；该界限只覆盖浮点表示误差，不修正原WT浮盈/现金/份数或容许实际价格差。现金依然来自原WT已实现盈亏、费用和持仓成本；保留原数值及各原时点，超过误差界保持waiting_basis。

EFR-18：trader.writes_enabled=false的Retained运行属于只读分析：允许原1.1.2计算、原价及资金读取和观察/周期KV保存；跳过advance_retained与target setter，NSQ state/退出规则状态保持原值，发布observing/analysis_only。writes_enabled=true沿原执行调用链，仍受原账户/Host/Source权限和风险约束；只读不以WT理论账目标模拟成交。分析结果targets属于策略建议，原券商数量与金融账分开。

EFR-19：模拟只读边界故障后的原件恢复可在兼容transition增加restoration={file,sha256}，指向guanheng.execution-restoration.v1。材料绑定最新已关闭owner的原clean字节、全量原状态归档，以及既有Native成功reconciled原收据及其原transition。仅前后trader.writes_enabled=false、最新owner已正常关闭/进程退出且原自有责任收束时准入。恢复状态须逐字节等于既有Native已经接收的state_files，原模型/基准/账户/输出目录保持；最新故障理论账及clean保留归档。Native在原输出租约内再次核原clean、归档完整集合、原admission/ready/transition/原配置与Python绑定及当前恢复集合，记录restored_snapshot和原恢复材料SHA。该事实不重放旧clean，不声称最新理论账等于恢复状态。恢复后的KV/Python身份和初始估值来源沿被恢复状态的原owner；正常运行/关闭产生本代新clean。

恢复材料的schema固定guanheng.execution-restoration.v1；current_clean_sha256绑定最新owner原clean字节，archive_directory为原clean.json及全量原金融/用户状态归档绝对目录。snapshot_admission={file,sha256}绑定既有Native的reconciled.json，snapshot_transition={file,sha256}绑定该收据已经采用的原transition；两个引用均为绝对文件和SHA256。被恢复的原Python绑定和当前绑定使用与最新前代相同的纯模型/解释器不变规则。当前发行直接复用原Reader raw日线接口；兼容核验可还原历史候选的只读adjustment引用，不赋予当前Reader新配置能力。

只读Retained绑定向原ManagedStrategy明确提供空execution_symbols；新可选gh_ms_read_only_abi_version=1确认execution_count=0的读取专用能力，布局1..8保持。Python和Native target入口均拒绝空执行权限集合，原读取集合和订阅保持。发布native_setter_count复制原gh_ms_status的累计setter调用数，用于核只读零提交，不作为券商成交或账户事实。

EFR-20：已准入原状态、在发布ready前启动失败的后继，可在transition显式增加initialization_abort={file,sha256}，绑定该故障owner原reconciled.json。只读双方、原failure.stage=cta、close-prepared.closed=true/ok=false/recovery_ready=false、原PID物理退出及ready不存在时适用。原admission须为clean_transition；原接收状态、当前状态及本代transition集合逐字节相同。核原transition、被接收的正常关闭owner配置/Python/closed及consumed clean；本代记录initialization_abort_reconciled。KV和初始化观察沿原被接收状态owner，最新前代生命周期保留故障身份，接续后生成本代正常状态。拒绝状态变更、缺少原件或身份冲突；原失败记录和已消费证明保持原件。

原接账类型为 `process_lost_reconciled` 时，初始化中断接续继续核原退出证明、完整认领收据、原状态摘要、就绪前零执行队列及后继交易配置。若失败代从原写入模式切为只读，允许后继继续使用该失败代的同一只读配置。原权限证明须直接绑定真实来源配置的路径和摘要，柜台配置只允许 `writes_enabled` 从 `true` 变为 `false`。借此恢复写权限或更换账户均拒绝。

原准入为process_lost_reconciled时，同一账户和交易权限可沿原异常退出材料恢复。失败代须缺ready和启动回执，CTA故障必须带完整的零活动执行队列，关闭收据须证明该代退出。须核原接收记录与原认领标记逐字节相同、两代实际退出、源ready/owner-loss/安装/Python身份、原状态摘要和完整业务配置，并通过本轮O/P/A查询。现场采用前核原交易Journal无新增或变更的命令且未知结果均已收束。输出租约内以失败代控制ID独占记录一次后继接收，保留此前每代回执。该入口沿原有账户和执行权限，现有只读clean分支继续按原证据准入。


## INIT同账估值恢复

恢复INIT先按原持仓数量读取已声明的MarketClient快照，再与原资本基准和券商现金原点合成估值。恢复代的当前快照读取至多用掉估值剩余时间的三分之一，为前代来源校验和账户读回保留时间。当前快照不可用时，在原截止内核对前代同账、同持仓数量、同周期的估值。QMT快照与原CTA已应用价格各自保持来源和原价时点；CTA原价须为raw CNY/share、关联原窗口，持仓价格完整，重建市值沿1e-8 CNY既有表示容差核对。账户约束继续核实际NAP及时效，过期保留可用金额未知。恢复估值只服务资金展示，不触发策略计算、目标setter或交易命令。


EFR-21：同账权限交接显式提供execution_permission_origin={schema:"guanheng.execution-permission-origin.v1",file,sha256}。file为实际前代execution.json绝对路径，sha256固定其原字节；两代writes_enabled须为不同布尔值。兼容比较仅将trader.writes_enabled/base_url/binding_id/binding_sha256/instance_id/key_id_env/hmac_secret_env七项还原到前代。其余业务字段、账户、模型、费用、资本基准和金融根逐项保持。原启动截止内最多16跳，支持后续停写及兼容发行。Native独立复核同一归一化，含该标记的record_clean模式拒绝。原进程退出、正常关闭或故障核查、金融文件摘要、当前券商查询、未知命令责任、准确安装与实际解释器入口身份继续核验。标记只表达兼容来源；Source、Host和Trader的写权限及风险检查各守原职责。

EFR-21a：同一 `ParserQMTHostRetainedV6` 仅迁移本机 HTTP 端口时，兼容比较归一 `http://127.0.0.1:<端口>` 的端口部分。仅接受 1–65535，允许末尾斜线，来源认证、解析器配置和其它业务字段逐项保持。实际新旧配置、配对和接续材料仍按原摘要绑定，解析器仍认证当前来源。

原账离线准备器保持原output_directory、initial_inventory.state_root和资本声明，固定实际前代control/configuration，生成独立通信配对及启用写权限的候选。准备器只写新候选目录，owner启动、Source替换、原金融状态写入、现场transition生成及新基准创建均由各自真实生命周期拥有。现场transition在实际正常关闭后，以后继角色解释器及已审Native安装生成。NAP新鲜度、自然交易窗口与SDK替身证据分别登记资格。


## EFR-22 单账新增原版ctx

显式策略扩展材料、固定新增行与比较边界见[OLS-6](original-live-strategy.md#ols-6-显式单账策略扩展材料)。恢复准入保留所有原金融文件SHA和原命令责任；首轮只要求原状态owner的ctx文件，并拒绝新增ctx已有stradata或userdata。后继关闭及恢复核原金融文件完整摘要。已初始化的原版 profile 在首次调度前可以只有已绑定的初始 userdata，且序号为零、无信号消费和目标意图。此时允许缺省 stradata，仍恢复原策略状态和原归属账。其他已运行策略继续要求原目标文件。新增依赖仅在显式扩展已核合同时接纳原版纯策略和行情SDK的安装文件，原Core、解释器和既有包约束继续保持。

## 分析发布目录接续

正式启动从当前分析发布器的已核摘要描述符读取工作目录。原生持续日线读取器同时接入该目录的 `STATUS.json` 和来源根。公开窗口路径、来源父目录和交易业务身份继续参与恢复比较。原生读取器按实际配置核状态回执、公开窗口摘要和来源目录下的原生输出。接续只允许切换同一来源父目录下成对的工作目录及状态文件，跨来源目录或更换窗口路径需要对应的来源变更准入。

## 已结束账户读取的回收结果

显式账户票据的原ID lookup收到认证Host完整410/read_ticket_ended_unretained时，Common返回Unavailable/qmt_read_ticket_ended_unretained。Host对在途、未知及未消费结果仍保留原记录；该状态只结束旧读取责任，不提供账户数据。标准交易插件归还该原读取的槽和内存，沿既有刷新流程发起新一轮账户查询。其它410、绑定冲突、无法确认的原结果以及全部交易命令继续沿原核查／失败语义。

原账户查询的首个准入 POST 收到完整 HTTP 400 和固定 `invalid_arguments` 或 `read_ticket_ended` 时，原轮次在准入前结束。Native 不交付账户数据，也不保留待续核的已准入请求。已登录实例进入现有只读等待流程，期间暂停新增交易准入，完整恢复资金、委托、成交、持仓后再开放。仅首个准入 POST 可凭该响应结束责任。原结果查询、消费确认、事件及交易命令沿各自的错误和核查规则处理。HTTP 参数类失败保留固定路由类别及允许的错误码供关联，诊断不复制报文和账户资料。

本进程已验证并持有原终态后，consumed收到完整410/read_result_unretained表示消费交接已完成。先校验该业务回复，再解释通用HTTP错误；正文不完整、错误类别或形状不符均保留真实失败。读取回收不会清理历史行情、金融状态或未决委托。

原生执行控制目录的轮转 `native.log` 保存已完整收到的 HTTP 拒绝。每条固定字段包含 `route`、原 `request_id`、本地 `exchange_id`、协议 `phase`、响应 `origin`、`http_status`、固定 `error_code` 及 `journal`。事件页无原请求 UUID，使用本地交换 ID。`admitted` 来自已核原ID、原正文和来源绑定的进度或终态。`not_admitted` 只用于符合固定协议的首发账户拒绝。无法取得入库证据时保存 `unknown`，无入库语义的查询使用 `not_applicable`。可识别的 HTTP 解析器固定拒绝与 Host 业务错误分别归类。诊断不保存报文、密钥、账户或任意远端错误文字，不改变恢复决策。

验证状态见[账户读取回收状态修正](../evidence/2026-11-03-account-read-ended.md)，现场恢复与隔离验证分别登记。


同账后继使用已经核对的前代实际配置，直接交原ManagedPythonExecutionProcess；其中takeover及输入文件摘要沿原库存基准保持。首次initial_inventory准备器仅负责尚未物化库存引用的准备配置，同账后继descriptor省略initial_inventory，继续保留原金融根、基准根及Native恢复核查。避免重复准备既有持仓或创建新基准。现场状态见[模拟自动执行启用](../releases/2026-11-04-wt-simulation-enabled.md)。


## 股票执行器分单数量换代

用户显式调整原股票执行器的 `lots` 时，Python与Native在同账恢复比较副本中统一校验其为有限正数并归一化该字段。适用工厂为 `WtExeFact.WtStockMinImpactExeUnit` 和 `WtExeFact.WtStockMinImpactBorrowedExeUnit`。原完整配置及SHA、账户、策略模型、目标、金融状态根、倍率、byrate和min_order继续逐项核验。该参数同时用于买卖；实际发单继续受目标余量、整手、可卖和资金约束。正常关闭后沿原transition启用新配置，旧挂单及未知命令保留原身份。


## 分析窗口时效配置换代

用户显式调整 `market_window.max_age_seconds` 时，Python与Native在恢复比较副本中按原窗口配置合同校验1至604800秒的有限数值，仅移除有效期字段；窗口路径、账户、策略、目标和金融根仍严格绑定。原配置SHA继续按原件核验；状态身份按EFR-30处理，采用新时效前明确迁移相应状态身份。新时效约束决策截止与current_view.received_at的差，等于上限时已过期。配置采用通过原正常关闭、transition和同账恢复完成，原发布者及其刷新间隔保持。该配置独立于逐单限价、盘口行情新鲜度和信号参考价偏离保护。


## 策略状态模型身份

EFR-30：自有状态通过 `StrategyStateRecord.model_identity` 的 `guanheng.strategy-state-model.v1` 合同绑定记录schema及业务模型。OriginalLive绑定实例、模型版本、除state_mode外的完整参数与实际证券映射；Retained绑定实例、输入摘要、证券映射、数量policy、配置身份、算法契约及市场窗口配置身份。空状态同样校验算法与配置。部署源码、安装路径和启动代号各由原Native绑定与发行transition核验，不进入策略状态身份。

恢复INIT校验原记录及实际账户后，原ASA payload保持逐字节不变，只在需要时同步NativeKV镜像。独立NativeKV恢复也保留原payload。真实业务状态变化继续沿原CAS/目标提交；第一次空状态创建和已核NativeKV向ASA迁入仍由原owner处理。先一只策略INIT成功、后一只失败，或ASA提交后NativeKV保存前中断，均不得仅因更换部署程序而丢失恢复资格。

旧代码摘要身份由一次性运维迁移。迁移前备份并核原配置及被接收状态来源，使用ASA公开CAS，逐项确认资金、持仓、委托、目标、cap、来源、时点、序号、周期及退出记忆保持。独立NativeKV模式在原租约内迁移并重新生成恢复材料，未迁移时明确拒绝。业务参数、映射或算法契约变化需要明确迁移；市场窗口时效等已允许的配置采用也须同步处理相应状态模型身份。产品不保留猜测旧代码身份的过渡分支。完整部署校验继续执行原EFR-04。
