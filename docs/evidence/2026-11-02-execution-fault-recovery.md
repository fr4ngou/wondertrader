# 执行故障恢复与原生现金观察

类型：实际主链证据。状态：最终012i实际只读恢复与同进程503等待恢复已验；真实换绑、未决SDK及后继新行情决策资格分别待验。日期：2026-11-02。

## 根因与实现

实际执行退出原因摘要精确对应`qmt_http_remote_failure:503:strategy_stale`。原入口只有正常关闭证明恢复，故障后原证明已消费，留下的原金融状态缺少新的准入路径。

自有适配新增显式`resume_reconciled`，核前代原配置、收据、安装/Python身份、物理退出、原状态摘要与同根租约，再复用原O/P/A、自有单收束、WT加载和正常关闭。正常兼容发行与故障依据分别记录；已消费的旧正常证明保持原语义。无前代安装依据时拒绝，后继正常关闭继续原clean协议。见[契约](../specs/execution-fault-recovery.md)及[ADR-0023](../architecture/adr/0023-execution-recovery-admission.md)。

本轮现金资格修正复用WT原flag1已实现盈亏、flag3费用和原平均持仓成本。可选只读桥在原INIT/SCHEDULE借用期复制原值；原ABI和结构保持。现金与有效NAP保守上限分别核验，报价年龄只表达报价/估值时效。估值完成时点与可选报价事件时点分别发布。资金来源暂缺只影响capital，原KV与投影保存失败仍沿原失败边界。

## 实际运行

采用用户已确认的无真实资金模拟账户和原只读产品入口。完成故障核查恢复、原状态与资本发布、原正常关闭和后继`resume_clean`；该阶段`resume11`曾保持运行，后续故障及当前实例见012i节。原基准SHA256为`8701e1ae8e632d8e1229079b60a7137f0bc0a0663b47ceca694909da70c6eac3`，原周期/退出记忆保持，序号接续到7、恢复自6。账户完整发布5持仓、2委托、1成交、1账户。Source/Host/Trader写开关均关闭，当前正式通信金融命令为0。

受控完整证据位于`E:/workspace/wondertrader-qa/strategy-capital-handoff-20261102-001/CAPITAL-ACTUAL-HANDOFF-011.json`，包含实际四身份、原资金/状态值、当前NAP、原关闭记录、制品及私有原始快照；源码交接为同目录`SOURCE-CAS-011.json`。Root已以独立a90观衡接收该实际身份并验页面。本文不保存账户标识、凭据或原始交易正文。

WT核心源码与库改动为0。自有Native仅更换执行准入、只读HTTP等待及可选现金桥对象；其余链接输入保留冻结摘要。已保存原安装、金融JSON和KV原字节。资金读线程随执行停止取得join证明。

## 011阶段的边界

- 当前现金与初始化估值字段已实际验收。后继K线资金发布仍使用调度起点作为估值时间，实际完成时间的后继修正及真实行情决策资格待交易时段核验。
- 完整跨运输绑定持续读取尚缺ReadGeneration整体交接；账户、交易身份及事件读取需同代准入，原写收据与未知责任保持。固定类别只读绑定等待已实现，其结果不等同完整跨代资格。
- 策略当前仍消费10月30日冻结分析输入，无动态market_window；18147对8只ETF实际回读已到11月2日，但原始日线单位/资格与分析窗口契约存在差额，交Root协调生产者。
- 旧SDK测试入口的依赖可见性前置与当前WT自带Host环境不符，调整过QA副本的结果仅作诊断，不授SDK通过。按最新要求，现金修正后沿实际只读主链验收，没有新增或运行自动化测试；此前被新现金政策替代的测试工作已在受控QA目录归档。
- 完整实盘交易、未知写命令恢复和后继真实新行情决策均未获本轮资格。当前实例继续三写关闭，整体目标保持未完成。


## 012i 当前实际交付

原resume11随后出现`qmt_trade_binding_changed`，12c/12e随后出现普通HTTP503。自有读取代际统一拥有账户查询、身份核查及事件客户端；原写客户端与原回报身份保持。暂不可用转读取等待，依赖金融准入暂停，原SDK未决只续核原UUID，原SDK与旧事实交付截止保持；后继GET核查有独立有限预算。来源身份、profile与数据硬错保留故障。等待及原未决责任进入recovery unsafe，避免生成错误clean。

最终012i控制ID为`05e76323-4bd9-4c83-87ff-f97972398e84`，实例ID为`a309716d-1288-4328-ac57-abd6ef0bb2e9`，配置摘要`d751d43b73247e9f52e57bd18845f096e0b53fd4614bbc1d42d07957c0922d21`。原基准保持，序号14从13接续，五周期、退出记忆与原账本保持。NAP实际5持仓/2委托/1成交/1账户；现金与可用均633075.20元，市值366924.80元、总资产1000000元。资金使用当前WT现金/持仓事实及已绑定原QMT报价全文，原价格时点保持2026-11-02 16:27:49.763上海时间；新报价链由Root独立维护。

实际使原只读Host HTTP容量短时不可用3秒，最终Native PID50116保持，私有read-status记录等待false→true→false、查询计数9→13；原基准、五周期、现金与总资产均不变，正式Journal新增金融命令0。来源QMT未重启，原Source正文保持。本次此前012h正常关闭所有组件后完成兼容发行恢复；012i随后于23:54因合法未派发终态被误判退出，当前实例见013节。Root已以a92/18143实际API和页面接收本代账户与资金。短时页面投影失败与Native故障分别留证，由Root按其层核查。

受控证据为同QA根`ACTUAL-READ-RECOVERY-HANDOFF-012.json`、`ACTUAL-READ-WAIT-012i.json`、`SOURCE-CAS-012i.json`、`SPEC-REVIEW-012i.md`、`STANDARDS-REVIEW-012i.md`。双轴delta审查未发现新增阻断，已关闭终态硬错抑制、晚D票据归还及等待clean准入问题。实际未决SDK中断、真实运输换绑、等待期间关闭、投影落盘失败仍未实际覆盖；这三秒预准入503场景仅授其实际覆盖的持续主链资格。没有新增测试工程，WT框架冻结链接输入保持。


## 013 未派发终态根因及当前实例

012i在2026-11-02 23:54实际退出，原Native原因`qmt_host_native_result_invalid`。原Host Journal的最后账户请求为合法失败终态`source_binding_changed`，started_at为空、dispatch_binding/result_binding均为空、原ID/正文和结果摘要/时间合法。Common终态解码仅在retained协议接受此固定码，普通账户读取因此错误升级为坏结果。

Common现将原Host空双绑定作为派发前上下文，严格识别该固定失败。Standard只在完整原终态、固定`source_binding_changed`/`queue_timeout`及空双绑定时确认SDK未进入、结清原责任，再通过完整ReadGeneration准入新观察；该失败不交付为账户事实，原未知与真实身份/数据冲突继续原边界。没有重发原SDK请求。

新013控制ID`49279c21-195d-4933-84e4-6e6422ebe2d0`，实例ID保持原值，配置SHA`5713aa4e5dd10260d41d76c2e6157ab2d96fa856a17560c42713b14d7b01939a`。序号15恢复自14、原五周期/基准及5持仓/2委托/1成交保持，现金和可用633075.20元、总资产1000000元。Native PID58600。最终013再次通过原Host3秒HTTP503短不可用，等待恢复同PID，queries15→19，资金/周期不变，金融命令0。00:27核当前仍ready且无failure。

复用现有native_account_control.cpp公开客户端case，对同形未派发终态仅切换修正前后的Common对象：旧对象稳定失败为原`qmt_host_native_result_invalid`，新对象确认`qmt_host_native_operation_failed`并完成后继普通查询；HTTP owner均drain/join，无QMT及金融调用。测试夹具从当前普通App安装补充原ThreadOwner依赖，此针对性回归不授完整SDK组合资格，没有新增仓库测试源码。原真实报文和合成客户端回归分别留证。

当前交接`ACTUAL-READ-RECOVERY-HANDOFF-013.json`、`SOURCE-CAS-013.json`、`ACTUAL-READ-WAIT-013.json`、`DECODER-REPLAY-013.json`及`SPEC-REVIEW-013.md`/`STANDARDS-REVIEW-013.md`均在同受控QA根。双轴delta未发现新增阻断；真实业务session更换、未决SDK/停止组合继续单列，整体目标保持未完成。

八ETF策略日线窗口已沿原QMT v7、HPR、QNA/Helper/原NativeReader实际发布11月2日窗口，导入8894行，32个v7 slot全部确认消费，原MarketWindowFile读取通过。`ACTUAL-ANALYSIS-WINDOW-HANDOFF-012.json`列完整运行身份和原件；正式策略market_window仍缺省，原冻结恢复身份和Native daily输入需显式兼容接线。全A T2108使用另一路v8/MDP及完整市场池。

## 015 账户约束刷新发布超时

2026-11-03 09:14重新核验：013原执行及五组件进程均已退出，原状态文件仍记录ready；没有原closed、close-prepared或failure收据。原基准摘要保持，序号15、五周期、现金余额633075.20元仍在。正式交易Journal有2159个已结束读取、金融命令0，账户Journal有41个已结束读取；最后排队时间分别为北京时间04:46:35和04:46:17。退出原因尚缺依据，原件全部保留。历史00:32运行证据仅证明当时状态，当前完整运行恢复待验。

资金约束此前停在01:01:02来源批次，01:02:21留下CtaBridgeError及strategies.pending。根因是发布截止或Windows读句柄冲突会中断临时文件提交，账户线程在整个循环外捕获异常后永久退出。原子替换后的截止检查还可能令磁盘已提交、内存仍旧。

自有Python发布者现以专用ProjectionPublicationTimeout表达有限预算耗尽，仅资金背景循环结束本轮并在下一轮重新读取原NAP。独占创建成功后才取得临时文件清理责任，未提交时清理本轮文件，外来pending保持硬错误。原子替换成功立即推进内存状态；非共享I/O、容量及数据错误继续硬故障，原K线回调继续传播发布失败。权威来源批次、原估值及价格时间保持原语义。

受控QA根下`capital-refresh-015/REPLAY.json`提取实际函数体，用真实Windows读句柄重现旧版第一轮超时后退出/残留pending，最终修正版完成第二批同金额续发；同时通过写后截止清理、外来pending保持、硬I/O传播、K线回调传播及提交后内存一致。该回放无WT/SDK或金融调用，真实NAP与页面验收另列。最终源码SHA256为`ef558d0086190f7f101c57bcaef8add1887b0a5c28027014f8ab2cf174e15ed4`，独立wheel为`0.1.0a12+integrated.2.reconcile.1.capital.8.recovery.8.cash.4.constraint.3`，只改变execution_configured.py，其余包内运行源码逐字节保持。双轴delta审查未发现实现阻断。

原Native恢复准入要求原关闭/故障收据，当前物理退出缺此依据；015尚未部署，不能宣称账户续发和页面已恢复。下一动作是由运行集成所有者接收当前退出事实，补齐可核实的异常退出恢复流程后沿原状态交接并验真实NAP和页面。没有重建基准、伪造关闭证明、清除Journal、改Source、重启QMT或修改WT框架。市场输入014候选保持独立待验。

## 016 进程丢失故障与跨来源阻塞

主会话授权同模块继续真实恢复。独立WT入口新增显式record-process-loss，在原实例OS租约内核原ready/status/配置及原父和全部组件PID退出，记录owner-loss、faulted状态和components_closed=false的故障终态。执行恢复owner另核原Native身份、配置字节、原ready摘要及PID退出，保留关闭结果未知。Native增加第三类process_lost_reconciled依据，继续在原输出租约和当前券商责任核查之后核前后安装/Python和原金融文件。原正常/故障关闭证明保持原语义。入口对其他既有failure或错误owner-loss身份拒绝，实际原件幂等保持；见EFR-14及ADR23。

09:28实际故障核查CLI通过，旧49279已显示faulted；既有18143的wt-runtime接口实际读取runtime.state=faulted、ready=false，旧磁盘ready误报已收束。v7/v8原实例也经同一故障核查接续，新控制da9a6035-2ae7-4197-ac2c-0e5715664239、实例1648369d-628b-4124-985a-3a0ee6b2e3ab、配置摘要1efee5adafb5fe9cb14df86b69fa34154503433a8f22168d2d3643e0d0f3ccaa，61135/61136分别由2412/9120监听。原配置、配对、Journal、Source正文及Root HPR保持；服务监听与来源握手分别记录。

016/017两次财务启动均在trader纯绑定准备阶段出现qmt_standard_completion_deadline，原恢复认领和SDK账户POST尚未发生，原金融文件逐字节保持。新增EFR-15仅在未登录Prepare/Login的完整503、运输超时或晚D成功时退役旧任务再续新有限GET轮次；首次固定绑定冲突保留原硬故障。018在原60秒总启动截止内等待来源，随后按原故障关闭，保留三代失败原件；未生成ready或恢复认领。正式Journal仍为2159个终态、金融命令0。当前财务恢复及真实NAP→资本→页面续发尚未验收。

09:44对同一QMT PID27136进行三次py-spy非暂停采样，无locals/native字段：线程63800三次均持GIL，调用含get_market_data_ex、_refresh、render、handlebar及Pandas iterrows。函数与行号匹配当前“一目均衡表.py”，SHA256为20e551475c4a74f9e06e6bcd5ab2cc5dc06ab6eb7240a9773c0956b272d34abc；该指标最新bar每次count=-1读取全部历史并全量逐行转换。终端交易图表实际显示该主图叠加及VW_MACD副图。Root另独立观察09:30起采集/HPR/v8及账户准备同时失去来源握手，支持共同来源回调受阻判断。因此前UI范围只明确覆盖VW_MACD，已请求用户确认暂时停用一目均衡表，当前等待答复；尚缺停用前后实际对照。

016受控目录保存RUNTIME-DELIVERY.json（owner.3，仅015包上的入口及恢复两文件增量）、Native/Standard冻结链接输入、OWNER-BOUNDARY.json、SOURCE-STACKS.json、SOURCE-ROOT-CAUSE.json、ANALYSIS-RESTORED.json、CURRENT.json和双轴审查。三项入口边界验证通过，两个P2已修；首次准备跨运输能力明确保持原硬故障边界，完整未知SDK/停止组合未授资格。最终Native候选已安装但当前没有财务执行进程；继续等待指标停用确认，随后沿原13账本交接并做实际账户、资金持续刷新及正常停止/恢复验收。Root继续拥有Git、页面绑定及全局采用。

### 用户停用指标后的实际恢复

用户确认已停用一目均衡表，并要求后续使用策略及接口核查。02:09 UTC同PID非暂停采样出现来源agent_tick/共享内存发送，原全历史指标栈消失；v7/v8原绑定GET均为200（0.172秒及不足0.001秒），没有新增SDK或HPR准备。后续核验保持策略、状态与只读接口方式，未再次打开交易图表页。

原13账本经process_lost_reconciled实际恢复到019：控制2587a596-1459-43d2-b68a-3ed605d614bf、Native PID66612、序号16恢复自15，100万元基准及五周期保持。实际5持仓/2委托/1成交，现金和可用均633075.20元；同PID、序号及估值时点保持，账户来源从02:12:02推进到02:12:32 UTC，验证无新K线/同金额时仍更新真实NAP约束。

019随后正常停止，WRI closed.components_closed=true，Native原closed.v2确认ok/recovery_ready/resources_closed均true、exit0；原clean证明产生。沿该原clean的显式兼容接续恢复到020，admission_kind=clean_transition。本次验证的是正常关闭后的显式兼容接续，resume_clean直连模式未作为本轮路径。

当前020控制fd4f3dd4-05c2-4760-bbcb-9cd84d862126、实例a309716d-1288-4328-ac57-abd6ef0bb2e9、配置SHA425d7f1e9017cbfd30fbf78ccfb1510855da80a79fcab6d2f5f246ab0c5e2935；Native控制8c9fc161-e537-4119-bed3-6c9d6a56407b、配置SHA41065dc93fa7ba032884964d2acfef6712569458395340a286a208a60e4dd940、PID14104。全部五组件ready且execution_ready=true，序号17恢复自16、五周期和基准保持，5/2/1事实及633075.20元可用正常。仍使用原2026-11-02 16:27:49.763上海时间报价事实，价格时间与当前账户批次分别保留；未授该旧价格实时交易资格。

实际证据为同016目录ACTUAL-19-CONTINUOUS、CLOSED-reconciled19、ACTUAL-20-FIRST及后继连续记录。当前金融命令0、三写关闭、无pending投影及资金刷新线程failure。Source正文和其他数据owner保持。最终Source/安装CAS和运行身份交Root绑定既有18143；本文的实际资金恢复证据与Root新页面绑定验收分别登记，整体目标仍未全部完成。
