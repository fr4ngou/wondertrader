# QMT 共享内存交易接入

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

状态：proposed。类型：功能候选规格。范围：在已实测的内存嵌入加载/builtin-shm Host/Agent 组合上补齐标准 WT 交易接入；正式能力要求承接[QSW-R13](qmt-shm-wt-binding.md)。本规格新增交易契约，当前真实写默认关闭；实现、替身验证、实际 SDK 验证和生产资格分别记录。当前选择继续内存嵌入生成方案，无需另建 QMT 策略产品或展开全部源码。既有[QAR](qmt-shm-account-read.md)账户查询与[QSW](qmt-shm-wt-binding.md)认证、无文件、容量和关闭要求继续适用。

## 目标与事实归属

用户需要同一正式接入具备行情/历史、账户与可用资金、持仓及可卖量、委托成交查询、下单和撤单。首个可实施交易 profile 限定单账户普通现金股票限价买卖与撤单；信用、期货、期权、组合、金额/比例下单等另有实际参数与资格后扩展，当前不宣称支持。首片限制不缩减完整产品目标。

复用能力 WT-T01/T02/T03/T07/T08/T09/T10，依据[原生能力目录](../development/wondertrader-capabilities.md)。执行目标、差量算法、风险配置、持仓/未完成量与成交归约继续使用 WT；柜台资金、持仓、订单与成交为外部账户事实；Host 通信 Journal 保存命令原文、派发/回执与恢复身份。接入层不引入独立金融账本、资金归属服务或逐单审批流程。

链路：原执行器 → 原 TraderAdapter → 自有 TraderQMT 标准 ITraderApi → 外部 Host 认证/Journal → builtin-shm → 已有内存 Agent 原线程 SDK → 回报/核查 → Host → TraderQMT SPI → 原 WT 消费。仅在原公开接缝补供应商适配；CORE-006 继续冻结，NCS 空交易资格不授正式交易宿主退出资格。

## 已核源码与官方接口

来源 S1：本机国信官方帮助 iQuant_Python_API_Doc.md.txt，文档自述 3.3.5 / Python 3.6.8 / 2021-08-18（第 3 行）。原始文件 SHA-256 为 1ad864c67e1bdfa5b84b8ec942d1cfc26edf35ba8b51e848d37c0d8417371c7e。行号来自该实际文件；安装版本与文档一致性仍须目标环境核验，文档描述不代表实机结果。完整来源路径及其他摘要记录在本次静态研究材料。

来源 S2：固定 WT commit 08b230dd05facf6d650d949bfe51054115a2ecb1 的 ITraderApi.h、WTSTradeDef.hpp、TraderAdapter.cpp，实际冻结副本 SHA 与构建 inputs manifest 一致。以下 TA 行号属于该固定版本，不引用工作树 CORE-006 差异。

| 事项 | 实际接口及含义 | 来源 |
|---|---|---|
| 下单 | passorder(opType, orderType, accountid, orderCode, prType, modelprice, volume, strategyName, quickTrade, userOrderId, ContextInfo)；返回无 | S1:3447–3449、3761–3765 |
| 股票参数 | opType 23 买入/24 卖出；orderType 1101 单股、单账号、普通、股/手；prType 11 指定价格；股票量按股 | S1:3495–3499、3581、3687、3727–3735、7360 |
| 触发时点 | quickTrade=0 受 K 线时点影响；1 仅非历史末 bar 立即触发；2 不判断 bar 状态，历史 bar 也可触发 | S1:3753–3759 |
| 关联备注 | userOrderId 对应 order/deal.m_strRemark，查询及 order/deal_callback 可取得。strategyName 仅当前本地客户端区分 | S1:3749–3761、7324、7398 |
| 撤单 | cancel(orderId, accountId, accountType, ContextInfo)，orderId 为原委托号。bool 仅表示是否发出取消信号 | S1:4324–4354 |
| 回报 | order_callback(ContextInfo, orderInfo)、deal_callback(ContextInfo, dealInfo)、orderError_callback(ContextInfo, orderArgs, errMsg)；交易主推仅实盘运行模式生效 | S1:5330、5364、5393、5451 |
| 订阅账户 | ContextInfo.set_account(account) 须在 init 设置；init 后新增不再订阅主推；passorder 空账户会采用最后设置账户 | S1:609–619 |
| 核查 | get_trade_detail_data(accountID, strAccountType, strDatatype[, strategyName])；ORDER/DEAL/ACCOUNT/POSITION，返回对象列表；get_last_order_id 只取最新号 | S1:4102–4140、4226–4258 |
| 订单身份 | m_strAccountID、m_strExchangeID、m_strInstrumentID、m_strOrderRef、m_strOrderSysID、m_strRemark | S1:7256–7288、7324 |
| 成交身份 | m_strAccountID、m_strTradeID、m_strOrderRef、m_strOrderSysID、m_strRemark；成交量价与日期时间 | S1:7330–7368、7398 |
| WT 身份 | makeEntrustID 后，Adapter 写 otp.<通道id>.<localid> 到 userTag；撤单传原 EntrustID/OrderID | S2 TA:486–500、1254–1259 |
| WT 消费 | 订单/成交依据 userTag 关联本地订单；成交 push 直接归约持仓与未完成量；四查询按序启动 | S2 TA:1688–1697、2076 起、2134 起、2229–2239、1397–1434/1588–1592/1715–1718/1798–1802 |

S1 的 orderError 示例第 5474 行误写 position_callback；本规格按第 5451 行正式签名。PassorderArguments 第 7866–7882 行仅列 opType/orderType/accountID/orderCode/prType/modelPrice/modelVolume/strategyName，最后描述为“策略名 _ &&& _ 投资备注”；没有独立 userOrderId 字段保证。禁止凭字符串分隔符猜测错误回报归属。

当前实现差额：[ManagedTrader](../../src/GuanhengExecution/ManagedTrader.cpp):229 的 init 未装配端点，:340–348 的标准写入口拒绝；:350–419 已有自有签名命令、字段绑定、重复冲突与 unknown 处理。[AccountMapping](../../src/GuanhengQmtBootstrap/AccountMapping.cpp):101/109 的只读映射 userTag 为空；[account_query.py](../../connectors/qmt_shm/agent/guanheng_qmt_shm_agent/account_query.py):22–37 尚未输出 m_strRemark。现有只读映射与中性 ABI 值保留其统计范围，正式写单必须取实际事实。

## QST-R1 准入与兼容

真实写默认 false。候选使用独立版本的 trade profile，显式声明账户/账户类型、环境、路由、源实例、允许操作/品种/价格量语义、配置身份与期限。正常writes_enabled开关、明确账户绑定、终端运行模式及当前源状态共同决定是否执行；同一现有配对可组合读写能力，旧 read profile、旧只读制品和原 order_ready=false 不静默升级。认证成功、账户字符串匹配、可查询账户均不独立证明可交易。

原 ContextInfo 在 init 按明确单账户配置订阅交易主推，所有写调用传非空确切账户；拒绝账号组、隐式默认账户及跨账户回报。读取账户/可用资金/持仓沿 QAR，交易所和证券转换沿现有合约规范；源缺值保持 unknown。账户或部署配置变化须重新建立匹配会话，禁止复用过期原会话发送新命令。整个方案不新增 SDK 导入、终端文件/外部 DLL/网络访问。

## QST-R2 最小 SDK 映射与原线程执行

首片映射现金普通限价：WT 现金 buy/sell → passorder opType 23/24；orderType=1101；prType=11；明确单证券代码、有限正价格、正整数股数，拒绝 bool、非有限数、非精确数值、未知枚举和原 WT 字符串截断。数量/价格步长按合约/账户实际规则校验，不从演示数值发明统一最小手数。其余 WT 类型在 SDK 调用前拒绝，不悄悄改成限价或现金。

候选固定 quickTrade=2，以避免排队后再次由 K 线时点决定是否触发。它具有历史 bar 也可下单的源语义，因此只允许已准入 live 环境、原线程的专用命令排空阶段调用；init、历史回放、handlebar 扫描、主推回调及重入路径均不得执行命令。实际策略定时排空路径与目标环境语义须单独验证，不能仅依赖 quickTrade。无需通过替身调用 SDK 即可验证这些前置拒绝。

SDK callable 和 ContextInfo 由生成策略既有注入边界显式提供，源端 kernel 不自行寻找全局函数。passorder 正常返回记录“调用已返回、等待柜台结果”；其公开接口未声明返回值的业务含义，因此丢弃返回对象，不产生 BrokerAccepted。cancel true 只记录“取消信号已发出”，false 只记录“本次调用未发出信号”；原订单可能并发成交或被其他来源处理，终态仍查真实订单。调用进入之后发生异常、超时、载体断开或回执丢失，保存 original command_id 并进入 unknown。

## QST-R3 命令与身份契约

原 WT entrustID、完整 userTag 和通道 id 原样保留，不能以柜台订单号覆写原 entrustID，也不能从证券/时间/价格猜测 userTag。command_id是共享内存运输内部自动生成的去重与恢复身份，由唯一Host owner在第一次受理前确定并持久保存，跨重启保持；用户无需填写或审批该身份。它不替代WT委托号、柜台订单号或成交号，不同生成代际不能重用已存在的运输命令身份。

命令包至少包含：schema_version、command_id、operation、原账户绑定身份、account_id/account_type、原业务截止、WT channel_id/entrust_id/user_tag、证券/方向/订单类型/价格/数量；下单含 sdk_user_order_id 和固定 strategy_name；撤单含 original_command_id 与确切 broker_order_id。原文及规范摘要一并保存，同 ID 同内容返回原结果，同 ID 异内容拒绝。新命令 ID 不得用来绕过旧 unknown 重下同一操作。

sdk_user_order_id 使用有限 ASCII 不透明 token；Host 持久维护 token ↔ command_id ↔ 原 WT 身份，再关联 broker_order_id 和 trade_id。token 长度、字符集及实际回显上限以目标 SDK 合格 profile 明确；本机文档未给上限，协议自定长度只限制资源，不构成 SDK 接受证明。m_strRemark 精确回显是关联证据；空值、截断、冲突或无法唯一匹配时隔离相关结果。strategyName 作为辅助过滤字段，不能成为跨客户端或跨重启身份权威。get_last_order_id 返回“最新”而非“本命令”，禁止用于命令自动认领。

订单回报恢复 WTSOrderInfo.entrustID/userTag/orderID；成交回报恢复 WTSTradeInfo.userTag/refOrder/tradeID。保持原 broker ID 及其已验证唯一作用域；如果需适配 WT 单键，则采用稳定、版本化、可反查的作用域映射，来源会话变化不得让同一既有成交成为新成交。外部手工订单只作为外部账户观察，当前候选不自动认领或撤销。

## QST-R4 命令阶段、原截止及 unknown

通信受理与业务终态分开。Host 至少保存 queued、dispatching、sdk_returned、source_confirmed、definitely_not_called、unknown，并单独保存订单/撤单观察状态；本命名为新写协议字段，现有 ManagedTrader SubmissionStage 需显式映射。dispatching 在发布到源端前持久化；命令进入 SDK 前复核原截止与准入，先记录本地 entered 状态供同会话重复抑制。Agent 无文件状态在重启后不构成持久去重证据。

达到原截止只关闭新调用准入及原等待，不撤销已进入 SDK 的副作用，不将 unknown 改为未调用。跨进程沿已核的期限映射契约，不直接比较未经证明同基的裸 monotonic 值，不在阶段/重试时刷新命令 D。后续原命令核查可有独立有界查询预算，不能改变原写命令的截止或重新派发资格。

Host 重启后 dispatching 不自动重发。认证 Session/Journal 只保证本路由受理去重，不能独自保证 SDK 调用与回执保存的原子性。只有确定未进入 SDK 的路径可报告 definitely_not_called；passorder 无返回 ID、异常或缺回报均不能证明未下单。unknown 的原 ID/原文/原因保留，相关写准入关闭，读取与核查继续可用。重复 cancel 同样不自动重发。

## QST-R5 源回报与错误回报

生成策略在既有入口注册 order_callback/deal_callback/orderError_callback，保留原 ContextInfo 与明确账户订阅。回调只提取有限白名单字段为自有值快照并入有界队列；禁止把 SDK 对象跨回调保留，禁止回调内发新交易、文件或网络 I/O。文档未保证这些回调的线程或顺序，入口按并发可能处理；若字段 getter/类型/线程可访问条件不符，记录 gap 并关闭写准入，不伪造事实。

事件含绑定身份、Agent 会话、本地单调序号、类型、源字段、命令关联可用性及摘要。Host 持久受理后才确认传输；重放按相同事件身份去重，队列满/丢失/字段异常/前沿不连续必须可观察并禁止继续写。该序号只证明接入层已接收事件顺序，不冒充券商完整连续流。

orderError 只在经过验证的字段/完整备注协议能够唯一匹配原命令时，向对应 WT 委托发确定拒绝；当前官方描述不足以证明这种解析规则。未唯一关联的错误以账户/源诊断记录并触发核查，不能拒绝“最近一单”或只凭相同价量定位。回调在 passorder 返回前同步到达、成交早于订单、重复或相互冲突均须保留并按身份处理，不能丢弃早到回报。

## QST-R6 查询、资金与恢复

标准四查询通过 QAR 的确切账户原始数据，补交易所需关联字段 m_strRemark/m_strOrderRef 和已证实真实类型。可用资金、可卖量、冻结和今昨量来自真实来源并保留时点；统计 ABI 中性零值不能授写资格。

下单 unknown 以原 token、账户和原委托/成交数据核查；查询得到唯一一致的源订单/成交可确认相应事实。查不到不证明未调用；查询成功不独立解除 unknown。撤单终态由原订单状态/剩余量/真实成交确定，cancel true 不能当撤成。多笔成交、部分成交撤单及晚到成交必须由原 WT 归约一次。

查询与主推交接须避免已吸收成交再次 push；固定 WT 的四查询为顺序调用，源文档没有共同事务/水位保证。本规格不强制源提供虚构原子四快照。实现先用可验证源语义定义初始化/补查区间和吸收集合；无法证明连续性时保持无写资格。ManagedTrader 当前 CoherentBaseline/confirm_resume 不能用新造常数满足。

断线、会话改变、回报缺口或消费者应用异常先停写。CORE-006 保留消费者恢复不进入本候选；原 Adapter 实例的未知消费结果不得自动重放。受控重建新消费者前完成原命令核查、真实账户基线与查询/回报交接验证。账户来源、客户端重启后备注保留、柜台交易日/ID 作用域的未知项按能力报告，不能以重连成功置 ready。

## QST-R7 线程、停止与所有权

QMT 原策略线程唯一执行交易 SDK；内存 Agent I/O 线程只搬运认证数据。源 kernel 在构造时固定线程身份，execute 逐次核对并拒绝跨线程/同步重入；SDK 回调快照队列与执行入口分别定义并发边界。Host 独占对应 Journal，插件有界序列化自身端点状态；不能假定 WT ExecMon/执行池/回报全局串行。

TraderQMT 标准 ABI 接收对象仅本次借用，异步前复制必要值；SPI 对象 retain/release 遵守 WT 原语义，不让持有生命周期锁的调用跨入阻塞 Python/IPC 或等待需要该锁的回调。先关闭新写准入，保留已受理命令并等待/记录原结果，再停传输/回报派发、join、释放句柄和对象。停止超时保留 owner 与诊断，不伪装全清理；stop 不隐式撤所有订单。

使用已验证内存 loader 与 builtin-shm 组合及其共享模块隔离/线程资源规则；新增 kernel 不创建线程、不加载 DLL、不操作文件。现有 NCS 只覆盖空交易配置，正式交易宿主需独立完整 lifecycle 验证；产品当前默认继续禁真实写。

## QST-R8 可实施切片与源模块契约

第一切片是原线程纯适配及可观察替身回报链，不要求真实账户先授权。建议新增文件所有权：Agent 的 guanheng_qmt_shm_agent/trading_kernel.py 与 tests 的 test_trading_kernel.py 由同一作者维护；父线程负责 Host/Journal/生成策略注册/WT 插件装配及索引。最终相对目录沿 connectors/qmt_shm/agent 和 tests 实际结构确定，不同时改共享 restricted.py/pair.py/runtime.py。

源 kernel 最小边界：构造注入不可变 binding、明确写开关（默认 false）、SDK callables(passorder/cancel)、ContextInfo、clock 与 owner thread；execute(command) 同步执行一次并返回有限原始阶段事实。输入在调用前全量校验，未知键/版本/账户/操作/截止/线程/重入/容量拒绝；进入 SDK 后异常返回 unknown。kernel 不签发权限、不持久化、不自行重试，也不把 None/bool 映射为成交。Host 的受信授权/去重先于 execute，源 kernel 独立复核绑定和具体调用字段。

回调使用独立纯投影函数 snapshot_order/snapshot_deal/snapshot_error；输出有限字段或有界错误。队列、认证/签名、命令结果保存与未知核查由既有 owner 承担，不复制金融或现有 transport 算法。具体 Python 函数参数与写 schema 在实现切片开始前由父线程冻结；此候选允许先进行纯替身开发并暴露源语义事实，完整写链的资格继续关闭。

## 验收映射

| ID | 观察与判定 | 验证入口/状态 |
|---|---|---|
| QST-R1 | 默认写关闭、旧读 profile 不升级、错误账户/权限拒绝；查询继续工作 | 新纯替身准入测试 + 实际生成策略/Host 配对集成；待实现 |
| QST-R2 | 精确 passorder 11 个参数、现金限价映射、空账户/错误类型/历史阶段拒绝；passorder正常返回仅sdk_returned，返回对象不作业务解释；cancel true/false 不伪造终态 | 新 trading_kernel 纯测试，独立记录调用次数/参数/线程；待实现 |
| QST-R3 | 同 ID 同文只一次 SDK 调用、异文冲突；备注精确回显恢复原 WT userTag/entrustID；截断/空备注/多匹配隔离 | 纯字段测试、真实原 TraderAdapter 合成 SPI 链；待实现 |
| QST-R4 | 受理/发布/调用/结果保存前后故障、超时/重启保留原 ID；调用后 unknown 不重发，查无记录不解除 | 独立记录副作用的双进程替身 + Journal 故障注入；待实现 |
| QST-R5 | 同步回调、早到成交、重复/乱序/冲突、队列满及错误无法关联；原回报对象不被延长使用 | 回调纯投影/有界队列及 Agent/Host 集成；待实现 |
| QST-R6 | 四查询与推送交接、真实可用字段、部分成交撤单、消费者应用后异常、断线新会话核查 | 原 WT Adapter + 源替身完整查询/回报链；待实现，实机 unknown |
| QST-R7 | 原线程/重入、stop 竞争、关闭超时保留 owner、正常 join/释放；不自动撤单 | 原宿主/完整内存策略受控生命周期集成；待实现 |
| QST-R8 | 源 kernel 无 I/O、注入替身可验证完整方法；读链回归；无双金融 owner | 代码审查 + 精确影响测试；待实现 |

交易副作用、身份、并发和持久恢复属于首次 full 独立审查范围。当前没有真实交易证据；目标 SDK 验证按明确账户、环境、标的、数量、动作与停止条件授权后另行执行。源字段/线程/身份缺口仅阻断对应实机资格，纯替身开发可以立即推进。

## 未确定项与后续核实

1. 源端备注长度/编码/完整回显、终端重启后查询保留、客户端更换后的可恢复性：接入作者查实际源并由目标 SDK 有界验证；失败保持原命令 unknown。
2. error 回报 strategyName 的确切对象形状/拼接规则和唯一关联：当前只以正式签名和有限字段投影为准，禁止自行拆分猜测。
3. SDK 幂等性、重复 token 行为、回调线程/顺序/重放、查询与回报完整前沿：文档未提供保证；不得宣称 exactly-once 或原子快照。
4. 当前安装终端的实际 write callable、live 运行模式、quickTrade=2 专用排空调用及账户写权限：须目标环境验证；静态参数存在不能授资格。
5. WT 股票实际类型/T+1/冻结、真实交易宿主关闭与执行池重入：按实际合约/源事实和固定 WT 链验证，不扩用空交易 NCS。

兼容与回退：新写 profile 的身份/命令记录不可回滚删除；关闭新写仍可读取/核查已有命令。旧只读版本只承接它理解的只读协议，含未决写命令时不得用旧版本自动接管写路由。索引和最终采纳状态由主线程集成，本文件候选状态不等同已实现或已发布。

## QST-R9 第一源端切片的冻结接口

状态：accepted（开发接口）；完整Host/WT交易链仍proposed且真实写默认关闭。TradingKernel(context, *, binding, passorder, cancel, writes_enabled=False, clock=monotonic)构造时记录原线程。binding精确包含schema_version=qmt.trade-binding.v1、binding_id（有限ASCII受信身份）、account_id、account_type=stock、account_environment=live、strategy_name、max_commands（1..4096）及symbol_rules。symbol_rules是受信合约事实的有限映射，键为六位代码.SH/SZ，值精确包含price_tick（正有限十进制字符串）、buy_min/buy_step/sell_min/sell_step（正整数股数）；规则只描述本切片可表达的普通现金交易范围，不发明全市场统一手数，不表达的零股处置继续拒绝。构造捕获深拷贝，不保存可变外部配置引用。account_id沿QAR最多63 UTF-8 bytes；其余字符串有显式有限容量，WT字段以实际ABI可完整承载为准，拒控制字符与截断。数量规则精确语义为quantity>=min且(quantity-min)%step==0，步长来自受信合约配置。

`qmt.trade-binding.v2` 采用相同账户和通信字段，取消 `symbol_rules`。订单业务规则由 WT 依据合约执行，券商负责最终受理。QMT 源端继续校验命令协议、账户绑定、写权限、期限、SDK 数值范围和原线程。旧 `qmt.trade-binding.v1` 保留原规则校验，历史绑定按原字节读取。切换沿[原绑定迁移](qmt-trade-binding-extension.md)。

execute(command, *, deadline, phase)仅在原线程、非重入、phase=live_drain且明确写开关为true时准入；deadline为源端已映射的原monotonic绝对截止，不接受来自Host未经证明同基的裸值。命令是精确dict，公共键schema_version=qmt.trade-command.v1、command_id（规范UUID）、operation（order.insert/order.cancel）、binding_id、account_id、account_type、entrust_id、user_tag。insert额外精确含symbol、side（buy/sell）、order_type=limit、limit_price（正有限十进制字符串）、quantity（精确正整数股数）、sdk_user_order_id（1..64 ASCII token，仅为协议资源上限，SDK接受性另验）；cancel额外精确含original_command_id（UUID）、broker_order_id（有限非空ASCII）。WT字符串完整保留且拒控制字符/超限，source不生成或改写WT身份。策略名取固定binding，所有SDK调用传确切账户和原ContextInfo。

insert按R2精确映射11参数，price_tick与数量规则用独立精确计算校验，不受调用者Decimal全局上下文影响；转SDK double后仍须有限正值。cancel四参数中公开account_type=stock映射为官方明确的SDK字面值STOCK，其余原值映射；不假设SDK接受小写类型。只有进入SDK之前的拒绝授definitely_not_called；进入后异常、cancel返回类型不符或晚于原D返回授unknown，并关闭该kernel新写准入。passorder正常返回仅sdk_returned，丢弃返回对象；cancel精确bool原样保留signal_sent，不产生撤成。结果精确包含schema_version=qmt.trade-call-result.v1、command_id、command_sha256、operation、stage（definitely_not_called/sdk_returned/unknown）、sdk_entered、signal_sent（None/bool）及error_code（None或有限固定码）。参数形状/原文冲突以固定安全异常码拒绝，不带账户原文。

同会话用有限命令索引保存原canonical摘要与原结果：同ID同文取原结果副本，异文拒绝且不覆盖原项；SDK前即占用身份，触发同线程重入时不重复调用。容量满拒绝新命令，已存命令结果仍可核取；不逐出尚有副作用的身份。request_close只停新写，不自动撤单；索引是该Agent会话的重复抑制，不能冒充跨重启持久保证。Host仍负责原命令持久身份和unknown核查。

snapshot_order/snapshot_deal/snapshot_error提取官方明确的有限白名单，单字段只读一次，保留缺失/null/0及源字符串；不用证券/价量/最近委托猜关联。错误回报的策略串只作为原值，不自行按分隔符解析。完整订单/成交映射、事件队列与源端注册由后续集成承接。该模块不创建线程、文件、网络或外部DLL；测试只注入明确替身，覆盖精确参数、并发入口拒绝、同步重入、重复冲突、截止前后、异常/晚回、容量、配置冻结、Decimal上下文与回调投影。

## QST-R10 共享通信Journal的写命令开发接口

状态：accepted（开发接口）。HostTradingJournal继承现BoundReadJournal，复用同一个SQLite文件、路由身份、独占owner锁和事务算法，仅增加trade_identity与trade_commands表；旧只读owner遇新表须拒绝，不自动降级。不新增账户/持仓/资金账本。read额度保持原义，新增max_trade_commands/max_trade_bytes/max_trade_result_bytes显式独立额度，总逻辑上限为两类已声明额度之和；身份、原命令、固定结果预留和channel元数据都计入交易额度，所有终态继续占用，无自动删除/逐出。

共享trading_contract.py唯一拥有原R9绑定/命令与结果字段准入，源kernel和Host共用；提取现有实现保持原公开TradingKernelError及调用语义。公开validate_trade_binding/validate_trade_command返回无别名普通dict，command_digest对通过准入的规范原文取SHA。validate_call_result核精确字段、枚举、SDK进入/阶段/signal一致性，及原命令ID/operation/digest；Host不得把sdk_returned写作柜台受理。形状/常量只维护一份。

HostTradingJournal构造沿原read参数增加trade_binding与上述交易额度、可注入monotonic/wall时钟；真实部署仍不从Journal获得权限。submit_trade(body, admitted_binding, *, ttl_ms, deadline)、claim_trade(actual_binding, *, deadline)、finish_trade(command_id, result, received_binding, *, deadline)、interrupt_trade(command_id, *, deadline)、get_trade(command_id, *, deadline)均受调用方原绝对I/O deadline约束，事务与锁复用现owner，不在循环续期。body是完整规范JSON bytes，命令/绑定用共用契约验证；原始bytes与摘要保存。来源B复用当前受信Host绑定准入；版本化交易控制profile另行集成，存储接受B不授写权限。

首次受理前保存queued，派发前保存dispatching；同ID同文返回原记录，同ID异文拒绝，不覆盖原身份或放大预算。source token须绑定唯一insert命令，原WT身份保持；cancel须指向本Journal已知insert、同账户和同WT entrust/userTag，broker_order_id的实际归属还须上层已验来源证明。存在unknown时拒绝新命令，已有ID与查询仍可取；同一时刻最多一个dispatching，避免源队列并发重复派发。源结果只有在原dispatch来源B和ID/摘要全部一致时持久提交，重复相同结果可取原终态，冲突结果拒绝。

首次受理以now_monotonic+ttl_ms/1000独立冻结命令业务D；每次方法的deadline只约束本次Journal I/O，不截短、不刷新业务D。持久UTC过期值只描述原业务期限，不在重启或重复受理时重算。claim前复核同owner原D与实际B，过期/来源已变且从未派发的命令可定为definitely_not_called。重启将queued变为确定未调用（owner_restarted），dispatching变为unknown（owner_restarted），不自动重发；重启后SDKreturned仍是历史SDK事实，业务写就绪需上层完成重建/核查，Journal不自行授ready。原D缓存缺失时拒绝派发。

源端调用后超时/断开由interrupt转unknown；结果/事务异常保留原身份，不能用新ID补下单。中断可与持久完成竞争：同一事务只接受一个已证事实，已提交源结果不被晚到interrupt覆盖。继承事务仍独占连接/提交/回滚/关闭；交易层在connect/BEGIN返回的yield边界、交易SQL/取值前后、提交前后核同一I/O D。claim在提交后同锁复核原业务D和I/O D并计算剩余ttl，超期不返回可派发记录；晚提交保留可能已持久的原身份并锁闭该owner新写。SQLite/OS已经开始的阻塞I/O不能据此瞬时取消，这些检查保证拒绝晚回，超时仍保留owner及原身份。source_confirmed与事件/WT消费闭环留给后续源证明处理，当前切片不提供凭布尔值清除unknown的接口。验证含重启窗口、commit失败前后、重复冲突、token占用、无别名、错B/错结果、原D/锁竞争、容量与既有只读回归；真实SDK和完整发布另验。

## QST-R11 有界回报缓冲开发接口

状态：accepted（开发接口）。TradeEventBuffer(session_id, binding_id, *, max_events, max_event_bytes, max_total_bytes, on_gap)只保存当前Agent会话有限回调值。capture(kind, source, err_msg=None)调用现snapshot_order/deal/error一次，返回有限序号或拒绝；不延长SDK对象生命期，不持锁执行SDK getter或用户on_gap。捕获前在短锁内保留序号/容量，锁外投影，锁内提交；并发完成顺序变化时只发布连续完成前缀。挂起票据计入容量，未知/超限/投影失败产生sticky gap并在锁外通知停写，通知异常不擦除gap，也不重复发真实交易。

事件精确含schema_version=qmt.trade-event.v1、session_id、binding_id、sequence、kind（order/deal/error）及payload；使用共用canonical编码，单条完整bytes≤max_event_bytes，所有挂起票据和未确认事件≤max_events/max_total_bytes。page(after_seq, *, limit, max_bytes)仅复制完整连续事件，给出已确认前沿/最高发布序号/gap；返回无别名普通值或原bytes包装，字段与预算固定，不截断单条事件，不把本地序号称作券商完整水位。acknowledge(through_seq)只接受已实际发布的连续前缀，不允许跳过未完成票据或未来序号；仅此确认可回收该前缀容量。Host须先持久保存原事件再确认。

默认不创建线程/文件/网络；锁只保护内存票据和bytes账，stop/关闭不得隐式撤单。request_close仅关闭新capture，已捕获事件仍可page/ack；关闭之后到达的回调记录gap并停写，不冒充已传给Host。现有Agent/Host只读链保持，回调注册/SHM写方法/持久事件与WT消费将在同一版本化集成完成；本缓冲本身不授任何交易能力。验证覆盖实际多线程倒序完成、getter同步重入、满额、ACK前后/错误ACK、通知抛错、无别名、超限/缺失/异常、关闭竞争与字节额度。

R11精确分页契约：事件/页版本分别为qmt.trade-event.v1与qmt.trade-event-page.v1。session_id与binding_id均为1..128 ASCII bytes非空身份；max_events为1..4096，max_event_bytes为256..1048576，max_total_bytes为max_event_bytes..16777216。挂起票据预留max_event_bytes，完成后计实际bytes；失败票据保留该预留直到owner退出，不将缺口后事件伪装连续。page返回精确schema_version/session_id/binding_id/acknowledged_through/published_through/gap/events，gap为null或精确code/sequence（未保留票据则sequence为null）；max_bytes限制整个规范JSON页而非仅payload。limit为1..4096，max_bytes为1..16777216；元数据或下一完整事件放不下时拒绝，不交付截断页。after_seq须在已确认前沿与已交付前沿之间，防止跳过未交付事件；成功page推进已交付前沿，acknowledge仅可推进到该前沿，重复相同ACK幂等，旧ACK拒绝。capture失败只记录首个sticky gap并在锁外至多一次调用on_gap(无别名gap值)，后续新capture拒绝；此前保留票据可完成其原快照并继续发布缺口之前的连续前缀。request_close与新capture在同一短锁排序；关闭前已保留票据可完成，关闭后新回调触发gap。

## QST-R12 同机Windows交易期限域

状态：accepted（开发接口），实际写仍默认关闭。首个交易profile显式选择clock_schema=qmt.win-uptime-ms.v1，仅限同一Windows启动周期、实际已核的GetTickCount64计时来源。当前Host3.12.14与国信3.6.8冷探针均报告GetTickCount64()/monotonic=true/adjustable=false，源16个毫秒样本落在Host独立GetTickCount64前后界；这不是QMT策略/SDK写资格。CPython3.6.8的[官方实现](https://raw.githubusercontent.com/python/cpython/v3.6.8/Python/pytime.c)在pymonotonic的Windows分支调用GetTickCount64；目标二进制/运行语义仍以实际配对证据为准。

trade_clock.py共用于Host与Agent，导入不读取时钟、不启动线程/I/O。SharedUptimeClock(monotonic=None,get_clock_info=None,platform=None)默认builtin time与sys；注入仅是受信测试/组合接缝。构造核win32、GetTickCount64()精确实现、monotonic/adjustable字面值true/false和有限正resolution<=1s，未知来源/QPC不回退UTC。milliseconds一次读取有限非负<=2**32秒的源值，按已证整毫秒计数round恢复；离整毫秒>0.01ms拒绝，以覆盖表示误差且拒不符计数。seconds返回同一整数计数/1000，无跨线程完成顺序缓存。deadline_milliseconds按floor(seconds*1000)保守转换有限正期限；deadline_seconds只接受精确正整数毫秒<=2**32*1000，拒bool/非有限/越界。错误TradeClockError仅带固定安全码。

Host首次受理以此业务clock冻结原D，Journal I/O仍沿其本地绝对monotonic预算，各自职责保持R10。wire只携原deadline_ms和clock_schema；源kernel使用同一已核SharedUptimeClock，不以receive时刻+TTL或UTC剩余重新起算。profile/源实例改变先停写；重启沿R10 queued/dispatching恢复，不沿重启后的启动计数重建旧D。以后不同OS/计时实现须独立版本及证据，当前主动拒绝。所有普通RPC的已映射本地截止继续由原ControlPeer拥有；交易队列只能收紧到原D与该本地RPC截止，不重新映射刷新。

## QST-R13 显式交易control grammar开发接口

状态：accepted（开发接口）；组合业务profile v4及runtime装配仍proposed。base control1.0的JSON、常量与既有只读配对行为保留；新2.0 grammar显式继承固定1.0 canonical SHA，仅新增Host发起的agent.trade、agent.trade.status、agent.trade.events和agent.trade.ack，复用原CALL/REPLY/ACK、窗口/容量与超期未知语义。control_versions只按精确1.0或2.0选择；1.0拒交易方法/2.0包，未知版本拒绝，不静默升级。

agent.trade payload精确kind/body/clock_schema/deadline_ms，kind=trade、body为原规范命令bytes的base64、时钟沿R12；字段业务类型与body验证由交易owner执行，grammar层仅核操作字段集与方向。agent.trade.status payload为空；其后续源session/准入回复不授ready。agent.trade.events精确session_id/after_seq/limit/max_bytes；agent.trade.ack精确session_id/through_seq，事件/确认沿R11，Host先持久提交再确认。RPC ACK仅回收控制缓存，不能替代事件的持久确认或SDK事实。旧agent.read/agent.observations/host.binding.read在2.0保持字段与方向；所有常量与预算复用原base唯一实现。

公开local_control_protocol_trade.json为版本差异定义，明确extends与base_sha256。构建工具生成静态control_wire_trade.py，终端不读JSON；--check验证当前制品与定义一致。仅ControlProfile能选择grammar不代表旧只读configuration、Host或C++已接受组合v4。读权限/descriptor继续复用原schema字段准入而非伪造v3/control1；组合profile和C++真实消费者在同版装配完成前明确拒绝且order_ready=false。

## QST-R14 组合读写profile开发接口

状态：accepted（开发接口）；实际Host/Agent/C++装配待验。首片v4完整profile精确六字段：read_profile_version=qmt.read-profile.v4、read_operations、execution_timeout_ms、control_profile、operation_profiles、trade_profile。读能力有序无重复且必须包含account.trade_detail，可组合已有full_tick/history；control版本精确2.0，读descriptor/请求继续沿原唯一字段和policy/limits逻辑核实际v4，不伪造v3/control1。旧三/五字段profile与build_read_profile仍仅1.0控制、原v1/v2/v3选择。新增build_trade_read_profile(read_operations,execution_timeout_ms,control_profile,operation_profiles,trade_profile,*,max_result_bytes)创建六字段profile并经同一validate_read_profile准入。

trade_capabilities.py唯一拥有公开交易descriptor。validate_trade_profile(value)返无别名普通dict：精确schema_version=qmt.trade-profile.v1、binding_sha256（私有validate_trade_binding规范全文SHA）、clock_schema=qmt.win-uptime-ms.v1、operations（精确有序[order.cancel,order.insert]）及limits。limits精确max_commands(1..4096)、max_command_bytes(1..65536)、max_command_ttl_ms(100..300000)、max_call_result_bytes(1024..2097152)、max_events(1..4096)、max_event_bytes(256..1048576)、max_total_event_bytes(max_event_bytes..16777216)、max_event_page_bytes(max_event_bytes+1024..4190208)。validate_trade_profile_binding(profile,binding)另核共用私有绑定摘要与max_commands一致；不把配置字符串当券商权限。私有账户/规则不复制到公开descriptor。

完整profile规范bytes仍<=4096；read schema负责读descriptor，trade schema负责交易descriptor，数据源/交易职责保持单一。联合control预算在完整configuration准入时必须容纳完整base64命令、SDK结果与至少一条最大事件的完整页，并保留read/trade/event/reverse方向固定credit，不借空闲方向额度；配置/工厂尚未装配时模块校验成功不授交易能力。第一切片测试覆盖旧bytes不变、错误版本/字段/限额、真实v4读请求和私有摘要不符，不运行QMT或真实SDK。

R13内部调度接口：ControlPeer.take_call_with_deadline()返回None或(call普通dict,原本地monotonic绝对deadline)。deadline是receive首次准入时已映射并存储的原值，同锁取得wire字节与该值后在锁外解码；重取/时间推进均不重算。原take_call()仍只返回原wire dict或None，两个入口共用一个taken标记，无双派发；过期或已回执调用不再交业务owner。此新增Python内存接口不增加wire字段，不授SDK调用权限。

R13交付失败语义：ControlFuture.take与两个CALL取出入口共用“领取中→完整构造成功→taken”内存状态。锁只预留领取，原bytes/原D在锁外解码并构造完整返回值；失败释放领取而不消耗未交付值，不开放ACK。成功后同锁提交taken，并发/同步重入不能双交付；close/expire可停止或退休条目，迟到领取不得重建已退休状态。ACK仍须领域结果已成功交付并由其owner完成应有持久提交。

## QST-R15 完整交易配置准入

状态：accepted（开发接口），真实写默认关闭。新增显式validate_trade_configuration，旧validate_read_configuration及原Host只读工厂继续拒绝v4。两个配置入口共用read_configuration的纯预算/运输准入实现；不把v4暂时改成v3/control1进行验证，不构造假Agent或SDK探测配置。

Agent私有bootstrap精确包含旧11个required字段route/secret/allowed_operations/execution_timeout_ms/max_frame/max_pending/max_result_bytes/connect_seconds/io_seconds/transport/control_profile，再包含read_profile_version（精确v4）、operation_profiles、trade_profile、trade_binding、writes_enabled。trade_profile及私有trade_binding沿R14和R9唯一validator；writes_enabled要求精确bool，是正常部署写开关；源端继续检查终端运行模式、账户一致性、源连续性与停止状态，不另设实盘资格开关。此配置值不证明柜台受理或WT order_ready。缺失开关拒绝，原kernel默认false保持。准入结果的公开value不含secret、trade_binding及writes_enabled；私有binding保存规范bytes、属性返回无别名副本，开关与secret保存同次准入快照。profile是完整六字段v4；账户读取descriptor的account_binding.account_id/account_environment必须与私有交易绑定一致，币种/financial_profile仍由QAR负责。

联合额度使用原ControlProfile、TransportBudget和运输profile。最大原命令N需4*((N+2)//3)+message_overhead_bytes<=max_call_bytes，保留base64完整三字节组；max_call_result_bytes和max_event_page_bytes分别加message_overhead_bytes<=max_reply_bytes；原读结果仍经require_native_budgets。最大业务TTL/1000+io_seconds<=max_call_seconds，所有预算在创建Journal、运输或SDK前拒绝不一致配置。至少max_pending_calls>=4、require_directions(7)、call_slots(host)>=4和call_slots(agent)>=1，以原固定角色份额容纳read/trade/event-page/event-ack及反向binding查询。不得借用另一角色空闲额度。

四个Host槽只证明在两个较早请求悬挂时，一次event-page持久后仍能发送一次业务ACK。原ControlPeer连续退休前沿保持：RPC ACK的发送与future.retired不独立释放被更早序号阻挡的gap，后续事件页须等实际can_submit。有限窗口不承诺悬挂前缀下无限轮询；运行owner须分别限制在途类别、沿原期限退休和背压，不以重建peer、跳前沿或丢弃事件换取进展。

Host显式validate_trade_launch复用原managed配置校验、凭证快照、policy加载、逐项roundtrip和只读Journal额度；旧validate_launch保持旧字段及版本。新配置精确包含原Host字段及read_profile_version/operation_profiles/trade_profile/trade_binding/writes_enabled/max_trade_bytes。trade_agent_settings从同次私有配置产生R15完整bootstrap。max_trade_commands及max_trade_result_bytes从descriptor唯一派生；交易身份原文和逻辑额度沿HostTradingJournal同一预算函数验证，并要求max_trade_bytes至少容纳identity原文、max_command_bytes、max_call_result_bytes与原MAX_METADATA_BYTES之和；拒绝超小或超大预留，不新增金融存储。纯launch校验只可读取终端外policy文件，不打开Journal/共享内存/SDK或启动线程。公开build_runtime在完整交易runtime接通前仍拒绝新配置，不能用新的配置validator成功授运行资格。

验证覆盖：旧validator拒绝完整v4与缺失/多余字段；旧配置和profile原值保持；读写账户不一致、bool/越界/不足base64组、完整页/结果开销、寿命、角色窗口及运输额度拒绝；公开配置无私有泄漏与输入别名；实际ControlPeer四槽/连续gap对照；Host policy与凭证快照及Journal预算同一实现。测试使用合成账户和SDK替身，不执行真实委托或切换运行策略。

## QST-R16 现有策略的源交易装配

状态：accepted（开发接口），实际Host/WT整链及目标SDK行为继续待验。沿现有内存策略模板增加显式交易渲染入口和RestrictedTradingAgent；旧只读模板、字段及工厂行为保持。受管读Agent提取已准入初始化和control创建接缝，读写Agent共用原运输、账户/行情适配及I/O资源owner，不复制认证、布局或读执行算法。交易只支持builtin-shm无文件模式。

新增SourceTradingService(context,admitted,*,passorder,cancel,clock=None,monotonic=None,session_id=None)。admitted为R15 TradeConfiguration，私有SDK callable显式注入；clock默认SharedUptimeClock.seconds，monotonic默认本地time.monotonic，测试接缝只接受受信调用方。session默认新uuid4.hex，构造时固定，早于账户订阅及握手。源在原线程只读取一次ContextInfo.do_back_test，仅精确False与正常writes_enabled开关共同启用kernel；缺值、读取异常或其他值均保持关闭。账户配置及终端实际权限沿正常SDK/WT接口处理，不新增独立实盘资格或用户审批。实际初始化与回报交接继续另验，source status不替代WT order_ready。

service拥有同会话有界命令队列/身份与TradeEventBuffer，复用TradingKernel及共同契约。enqueue(payload,rpc_deadline)只验证并投递，返回MemoryCompletion，其成功值为规范结果bytes。payload沿R13，base64及解码后bytes在展开前后受max_command_bytes限制，必须为规范原命令；clock/deadline_ms及原账户绑定沿既有validator。相同ID/原bytes共享既有完成，不刷新D或重执行；异文拒绝，最多max_commands条身份。新调用收紧到原业务D与首次映射RPC本地D：先读业务now再读local now，一次投影剩余时间并冻结有效业务D；tick还分别复核两个原D，绝不在排空时重起TTL。未知或坏时钟停新写。源队列满/关闭在SDK前明确拒绝，结果发布失败保留身份并停写，不用新ID重试。

tick(phase='live_drain')只在原构造线程、非重入的live_drain执行最多一条命令，SDK与任何回调不持service锁。init、handlebar、I/O及源回调不调用交易SDK。request_close只关闭新写并将未进入执行的排队命令发布为definitely_not_called/admission_closed；已执行命令保留原owner收尾，不隐式撤单。status返回固定版本qmt.trade-source-status.v1，精确字段为schema_version/session_id/binding_id/binding_sha256/writes_enabled/source_mode_live/write_admission/closing/gap/queued/executing/commands/completed/events。write_admission表示正常开关、终端模式和当前源状态允许写，队列容量仍由enqueue实际占用；不含账户原文、命令正文或凭证。session_id是源接入代际，不冒充券商会话。

TradeEventBuffer新增可选account_id和纯status接口，旧默认语义保持。指定账户时，在唯一snapshot投影后检查order/deal的m_strAccountID、error的order_args.accountID；缺值或不匹配触发sticky gap并停写，不重新读取SDK getter。status包含closed、inflight、retained、used_bytes、published_through、offered_through、acknowledged_through、gap及session_id/binding_id的普通副本。capture仍先占票据再锁外读getter，关闭前在途可完成；当前status.inflight以尚未完成票据计，不把关闭通知等同回调排空。service.on_order/on_deal/on_error先核确切原ContextInfo，回调可来自其他线程，只进行有界捕获；错误Context不接触SDK对象并关闭新写。无法唯一认领的orderError保持原观察，不拒绝“最近一单”。

service.events(payload)/acknowledge(payload)在I/O线程只处理普通值，精确核本session及R13字段/额度；page沿R11，事件业务ACK仅来自Host持久提交后。service.local_drained只在closing、无正在执行命令、无排队、全部命令完成已发布、事件owner实际closed且inflight/retained均为0、无gap时为true；此属性不独立证明RPC结果已被Host持久接收。所有并发状态用短锁，getters/SDK/时钟和控制reply在锁外。

R16最终关闭提交使用专用非阻塞查询：SourceTradingService.try_local_drained()先以acquire(False)获取service锁，忙即返回False；只检查closing、无executing/active/queue、无fault且所有保留命令均completed，再以固定service→event顺序最后调用TradeEventBuffer.try_drained()。后者以acquire(False)获取event锁，忙返回False，仅检查closed、tickets为空且无gap；tickets包含尚在投影、失败及待ACK票据。两者均在finally释放已取得的锁，不生成status副本、不调用时钟、SDK、任意getter或外部callback，不清身份、票据或改变状态。正常观察属性local_drained保持原语义，最终关闭提交采用新的锁内事实查询。

最终close先在锁外读取now，再非阻塞取得关闭owner锁，核当前原D、失败及交接确认状态，最后调用try_local_drained()并提交verified。不得复用读时钟之前的drain/status快照；锁忙或事实不满足均不能提交成功。线性化点是service与event两owner锁内共同观察到排空的时点；之后晚到callback仍产生可观察gap，该查询不证明未来回调终止。已verified的重复close不再读clock或发送关闭通知，只按当前失败、确认及try_local_drained事实决定幂等返回。

R16事件封口顺序：request_close先关新命令。若已有SDK正在执行，事件buffer保持捕获，允许该调用在关闭通知后同步触发order/deal/error回报；原tick finally确认执行已结束后再封buffer。没有正在执行SDK时立即封buffer。已经占票据的getter仍可完成并等待业务ACK，不能因停止通知丢弃在途SDK回报。封口后异步晚回报仍产生可观察gap并使正常交接失效；券商回调整体终止需真实宿主生命周期证据，不以瞬时计数推断。

TradingControlLoop继承原AgentControlLoop，只新增交易、status、events和ack分派。原读队列及结果算法保持；交易从take_call_with_deadline取得原映射D。SDK结果须实际保存在原REPLY缓存中，再等待该trade CALL被对端RPC ACK退休，才能计为源关闭交接。原peer.reply到期时会缓存call_expired且仍可能返回true，因此新增retained_reply_matches(call_seq,payload)纯查询，原锁捕获reply bytes、锁外核ok=true/error=None及规范payload相等；不能只以reply返回值判定SDK结果已交付。ControlPeer另增has_incoming(operation)纯查询，原锁捕获尚保留CALL原bytes、锁外核操作，不改变窗口/退休算法。缓存不匹配、迟到SDK结果或运输异常时记录handoff_failed；source结果仍由原内存owner保留，Host按原ID保持unknown，不能报告正常交接。

RestrictedTradingAgent使用同一已准入读初始化，I/O仍由原_read._run/finally拥有；只覆盖control创建和原线程tick入口。subscribe_account只能在构造原线程且初始化阶段调用一次ContextInfo.set_account(明确账户)。生成init先构造并发布_agent，再subscribe_account，以捕获同步早到回报，最后沿原run_time/start。生成agent_tick核原context/thread，handlebar只核身份而不执行交易；三个交易回调只核context并交service，不要求策略线程。stop核原context后只request_close，允许来自管理线程且不join。

交易关闭分两阶段：首次request_close先固定本地关闭D为now+max_call_seconds+io_seconds，再调用service.request_close关闭新命令并发布未执行命令的原拒绝结果；源端结果发布的耗时计入该原D。重复通知保持原D，管理close(deadline)只可收紧，不能续期。I/O继续有限轮询以交付已证SDK结果及事件，确认排空时须同时核当前时间仍早于原D、local_drained、无待完成交易future、无保留trade CALL且handoff_failed=false，才标记trading_close_confirmed并沿原读owner停止/释放。首次资源close完成后、成功返回之前再次核原D及实际交接状态；超过原D保留失败，不能因稍后排空或资源回收完成而补授成功。源拒绝结果发布异常、坏时钟、达到原关闭D、断连或回复无法交接时停止I/O并保留内存owner及未确认状态，close报告失败；线程/句柄已回收不能代替交易结果交接，stop不清索引。无worker的构造/启动失败沿同一原D和交接条件处理。已经在原D内完成交接与资源关闭并成功返回的close可幂等重复，无需因后来时间流逝重新判超期或重复关闭资源；随后出现的新gap或交接失败仍保留可观察失败状态。真实QMT回调生命周期和宿主整体退出仍需目标实测。

R16交接查询的并发约束：retained_reply_matches锁外构造后回原锁，复核peer未关闭且当前保留reply仍为同一原bytes；close不能让旧快照授正常交接。has_incoming在锁外解码前后核peer仍打开及CALL集合未变，关闭或所有权变化抛固定错误。只有原I/O owner正常receive对端ACK后、peer仍打开且无失败时，CALL缺席可作为退休依据；异常close同样清空集合，必须先锁存handoff_failed。交易future不能沿只读清理路径cancel/clear；MemoryCompletion.publish后核原规范bytes可取得，失败保留命令身份且停止新写。

render_trade_strategy为显式纯生成入口，先经R15完整准入，只接受builtin-shm及冻结内存源码，沿原渲染实现注入passorder/cancel/get_trade_detail_data并导出原四入口与三交易回调。生成入口传递正常writes_enabled配置，终端模式由原ContextInfo提供；替身使用相同接口验证SDK调用链，不增加独立许可参数。旧create_pair及build_runtime在完整Host写运行器接通前仍拒绝新配置，纯渲染不构成可启动正式交易配对。

验证覆盖完整服务/策略替身调用链：命令I/O入队→原线程唯一SDK→同步/并发回报→有界页/持久替身确认→RPC ACK→正常关闭；同ID重复/冲突、原D耗尽、跨线程/handlebar/重入、坏/跨账户getter、队满/gap、关闭竞争/SDK晚回/回报未确认、断连及关闭超期；旧读取/生成字节/运输回归。目标3.6.8内存禁文件/网络导入验证与独立审查分别登记，不调用真实下单撤单。

## QST-R17 Host 实际绑定版本与共用运行接缝

状态：accepted（开发接口）。Host 的绑定验证版本取自同次完整准入 profile 的 control_profile.schema_version，冻结为 owner 属性 binding_control_version。仅既有未声明 control_profile 的旧只读 profile 使用原 1.0。不得从传入 B 自行选择验证器，也不得用改写 v4/control2 为 v3/control1 的方式准入。bound.binding(value, *, control_version='1.0') 和 bound.validate_response(value, *, max_result_bytes, control_version='1.0') 显式将可信版本传给唯一 control_messages.validate_host_binding；旧调用默认语义保持。

BoundReadJournal 的 submit_bound/claim_bound/finish_bound/get_bound 与 HostTradingJournal._source、保留记录回读使用同一个冻结版本。正确版本的 B 仍须具有真实 route、transport_generation、host_instance_id 和完整 profile 原字节摘要；版本选择不改变原绑定内容。错误版本及保留事实与新 owner 不匹配时拒绝，禁止给旧记录改标签。该变化不增加账户或交易审批条件。

HostReadRuntime 在真实 Session 握手后，由 _channel_binding(session) 生成并核验同版本 B；公开 claim_bound 使用同一冻结版本。原 _run 的连接、绑定发布、异常与 finally 资源 owner 保持；通过 _make_control(session, actual_binding) 和 _interrupt_control() 内部接缝选择组合交易控制模块及异常中断处理。原读实现仍创建 HostControlLoop、执行原 interrupt_read；HostControlLoop 以 _make_domain() 创建原唯一域 worker，组合交易实现可在该接缝扩大联合消息额度并复用同一个 worker。共享主循环、读派发、事务、ACK 与停止算法不复制。

验证以实际 v4/control2 profile、真实 HostBinding 构造、BoundReadJournal/HostTradingJournal 的 SQLite 读写与恢复为依据：匹配版本的读和命令终态可往返；跨版本 B 拒绝；owner 配置/输入副本不改变版本；保留事实不被重写；原 control1、旧读工厂拒绝 v4、当前运输/生命周期回归保持。内部接缝以明确替身验证实际 _run 的动态分派及原关闭调用链。该切片只完成版本与复用接缝，不宣称 Host 写派发、持久事件 ACK、C++ 写入口或真实交易已完成。

## QST-R18 同一通信 owner 的回报保存与源确认

状态：accepted（开发接口）。WT 原生归约与日志只覆盖已经交给 WT 的回报；QMT Agent 到 Host、再到 C++ 插件之间仍有交付窗口。Host 只保存原通信事件及交付前沿，用于确认前后断连恢复；不计算持仓、资金、盈亏或订单业务状态，不授 WT 已应用，不建立第二套交易账。实现沿 ADR-0009 的同一 SQLite 文件、进程 owner、RLock 与每事务连接，由原域 worker 调用。数据库锁内不运行运输、SDK、WT 或外部回调。

HostTradingJournal 新增可选 event_storage 参数；显式选择后提供唯一只读属性 events（TradeEventRecords），缺省为 None，保持原命令接口。TradeEventRecords 不拥有数据库或线程，initialize(db) 由该 Journal 的交易初始化事务调用，位于恢复 trade_commands 之前；旧命令/读记录保留。schema_tables 增加 trade_event_identity、trade_event_streams、trade_events；缺少显式事件配置时拒绝包含这些表的库，旧只读 owner 继续拒绝新表。三张事件表必须同时存在或全部首次创建，精确列集合、配置身份与保留原文/前沿在启动时检查；配置身份冲突拒绝，禁止清库或静默改预算。

事件配置通过纯函数 validate_trade_event_storage(profile,trade_binding,event_storage,*,max_result_bytes) 统一校验并返回私有 storage/limits/identity_bytes/profile_sha256；运行工厂与 TradeEventRecords 构造共用该函数，后者也显式接收 max_result_bytes。完整账户 profile 的联合预算使用同次部署的确切 max_result_bytes，不从 profile 推测。Journal 在打开文件/获取 owner 前冻结 profile 并完成事件配置纯校验，随后原初始化事务建立/核查事件表。不构造假 Agent、SDK 或运行 owner 来探测配置。

event_storage 精确包含 max_streams（1..4096）、max_events（1..1000000）、max_bytes、max_page_bytes。源单条事件及页格式上限复用完整 v4/control2 profile 的 trade_profile；private trade_binding 摘要必须匹配。max_page_bytes 在 max_event_bytes+1024 与源 max_event_page_bytes 之间，完整 base64 域消息加 MAX_METADATA_BYTES 不超过 4194304；只有实际请求的页大小可小于源最大页预算。每事件逻辑占额为原 bytes 长度+512，每流预留 MAX_BINDING_BYTES+1024，另计事件 identity bytes。max_bytes 至少容纳一流一最大事件，最多为配置所有流和事件预留之和。逻辑额度独立于读/命令额度，声明总体为三者相加；SQLite 页、索引与事务日志的物理空间另计。无自动逐出或删除，源 ACK 不释放 Host 原事件额度。重复原事件和已有流 ACK 在满额时继续可用。

已停止owner的显式容量维护沿[TES-C1–C6](../migration/trade-event-storage-expansion-proposal.md)另行实施：原租约、验证与事务共用，原容量身份CAS、新容量声明和其余事实保持分别证明。普通构造保持精确身份匹配。维护期间任何命令阶段/旧schema补写均拒绝，提交未知沿原/新身份核查；测试预算与正式运行声明分列。当前自有维护接缝实施中，完整恢复和安装资格沿模块B证据核验。

内部 source 是精确普通对象 {host_binding, session_id}：B 必须经本 owner 冻结的 control2 验证，route 及完整 profile 摘要匹配；session_id 沿 R11 有限 ASCII 身份。binding_id 与账户取本 owner 私有绑定，不由 source 再声明。首次流固定 (session_id,binding_id)、原 B；同 session 的新 B 拒绝自动续接并保留原流，新 session 单独建流。首版不把新 transport generation 当旧流来源，后续可靠重连另定。

TradeEventRecords 的接口为 ingest(source,page_bytes,*,after_seq,limit,max_bytes,deadline)、state(source,*,deadline)、acknowledge(source,ack_bytes,*,through_seq,deadline)、read(source,*,after_seq,limit,max_bytes,deadline)。输入 deadline 是从本操作入域队列前固定的绝对 monotonic I/O D，沿 _trade_transaction 贯穿锁、SQL、取值和提交前后；不得在域线程开始时续期。事件操作不调用新命令 _admission，unknown 后仍可接收和核查原回报；存储错误/原 D 耗尽仍传播且不能据内存值 ACK。

ingest 接受原规范页 bytes，限制实际 bytes<=max_bytes<=event_storage.max_page_bytes、事件数<=limit<=源 max_events。核 R11 精确页/事件字段、版本、身份、精确整数（拒 bool）、序号、完整单条预算与账户。payload 共用 snapshot_order/snapshot_deal/snapshot_error 的普通 JSON 值验证并须规范值相等，不读取 SDK getter。页 acknowledged_through<=after_seq<=published_through；事件必须从 after_seq+1 连续且不超过 published_through，空页在 published_through>after_seq 时拒绝。published_through 只记观测，不能替代本页实际事件推进持久前沿。

单事务保存所有新事件、连续 durable_through、ack_intended_through 与首个 gap。重叠事件逐条比较原 bytes 与摘要；同身份异文、Host 缺前缀、错来源、超额整页拒绝，既有记录不变。首次流必须从 after_seq=0 且源 acknowledged_through=0 开始；源 ACK 超过 Host durable_through 拒绝。旧页较低水位不回退已保存事实，gap 不能被后续 null 清除，同流冲突 gap 拒绝。保留 gap 前的连续有效事件仍可保存并确认。

state 返回 None 或无别名 qmt.trade-event-receipt.v1：session_id、binding_id、host_binding_sha256、durable_through、ack_intended_through、source_ack_through、observed_published_through、gap。各前沿精确整数，0<=source_ack<=ack_intended<=durable<=observed_published；本实现 ingest 把 ack_intended 推进到实际 durable。receipt 不包含账户原文、金融状态或 WT 应用字段。ingest/acknowledge 返回同形 receipt。重复页仍复核原来源及重叠事件，前沿或 gap 变化时才更新流记录，新增流或事件时才在事务内复核全库占额。同一有效 ACK 重放直接返回已提交确认前沿。read 返回规范 bytes，精确字段 schema_version=qmt.persisted-trade-events.v1、receipt、events；after_seq 不超过 durable，limit 和总编码 max_bytes 有界，输出原完整事件，无截断。尚无流时 state/read 返回 None，read 不创建流。

只有收到原 agent.trade.ack 回复后调用 acknowledge：ack_bytes 精确为 qmt.trade-event-ack.v1/session_id/through_seq，须匹配原请求 target、source 与已持久意图，source_ack<=target<=ack_intended；相同 target 幂等，旧 target 不回退，未来/错源/错值拒绝。发送成功、RPC ACK 或 Future retired 均不独立推进 source_ack。本切片不从 page 的 ACK 水位推断源确认事实。

运行器同流只允许一个业务 ACK 在途：页回复→事件事务成功（含 pending 意图）→RPC ACK 页→发送 agent.trade.ack→源确认回复→确认事务成功→RPC ACK 确认请求。崩溃后从持久 source_ack<ack_intended 发现待确认，按相同原 target 重试，不重发交易；源 session/B 更换保留旧流，不能继承前沿。Host 持久接收、源回收与 WT 消费为三项独立事实。

验证须覆盖真实 SQLite 原页/前沿/待确认事务、重放/异文/缺口/错账户与版本、分页前缀、满额重复与 ACK、unknown 后回报、原 D 锁/SQL/提交晚回、提交前后异常、重启重建待 ACK、字节/摘要/前沿损坏、新 B/session、旧读命令表保持及旧 writer 拒新表。所有 SDK 使用替身；原生 WT 应用、正式部署和真实交易另验。

## QST-R19 显式 Host 组合交易运行器

状态：accepted（开发接口）。使用 HostTradingRuntime 继承原 HostReadRuntime，HostTradingControlLoop 继承原 HostControlLoop；沿 R17 接缝共用 _run、Session、绑定发布/finally、run 的 send/receive、原读派发和一个 HostDomainWorker。禁止新增第二套 SHM/I/O/SQLite worker 或复制读主循环。旧 build_runtime/create_pair 继续拒绝 v4；新增显式工厂先纯校验再取 Journal owner。

新 Host 配置在 R15 完整字段上增加 event_storage（R18）和 event_poll_seconds（有限正数，0.01..60 秒，且不超过 control max_call_seconds）。旧 validate_trade_launch 仍可校验 R15 纯配置；显式运行工厂要求两项都存在，同次值进入 runtime。源 Agent 配置保持 R16 字段，不把 Host 保留预算注入终端。工厂复用原 policy/凭证快照；构造唯一 HostTradingJournal，business clock 注入 SharedUptimeClock.seconds（同 Windows 启动周期 GetTickCount64），SQLite I/O 仍用原 time.monotonic 域。事件配置、读/命令/页/域消息联合大小在开库前校验。

HostTradingRuntime 的新增构造 keyword 为 writes_enabled、event_storage、event_poll_seconds、business_clock（可信秒 callable）；正常配置默认写关闭。它公开 trade_limits/event_storage 的副本、event_poll_seconds、business_seconds()，以及 validate_source_status(value)、observe_source(status,receipt,unknown)、note_trade_record(record)、claim_trade(B,*,deadline)、advance_trade_shutdown(drained) 的内部控制接缝。accepting_commands 是当前连接、配置写开启、源正常可写、已核流状态、无已知 unknown/关闭/gap 的实际运行状态，不是审批或验收等级。单一 _binding_lock 保护发布事实，锁不跨运输等待；原请求身份仍由 Journal 唯一持久保存。

源状态必须经精确 qmt.trade-source-status.v1 与其 events 子对象字段验证，session/binding/descriptor 摘要及请求写开关匹配同次配置；bool/int/容量/前沿分别核实并复制。queued 与 completed 互斥，executing 表示整个原线程 tick 尚未完成收尾，允许与当前已发布结果的 completed 重叠；分别核 queued+completed<=commands 和 queued+int(executing)<=commands。status 更新不自动清除已知源 gap 或 unknown。首次 status 后通过同域任务读取 journal.events.state(source) 与 has_unknown_trade(deadline)，核 source ACK 未超过 Host durable；新空流只接受源 ACK=0。只有实际取得并核对来源状态后发布可写状态；读取能力继续沿原 owner。源会话变化或冲突按明确错误停本代际，不伪造身份。

控制循环拥有至多一条 trade claim/active/future/commit，并用同一有界域队列派发。claim_trade 持久 dispatching 成功返回后才发送 agent.trade；原 command bytes、clock_schema、原业务 deadline_ms 沿 R13。RPC expires_at 固定为记录原 expires_at 加 io_seconds（受 control max_call_seconds 约束），不会刷新原业务 D。源结果领取后先保存原普通值，再投递 finish_trade；队列满保留已领取值和首次 I/O D，后续同操作不续期。finish_trade 提交成功后才 RPC ACK。错误回复/断连按原 ID 持久 interrupt 为 unknown，不发送新命令替代。

为保留 C++ 首次操作截止，submit_trade 增加可选 business_deadline；缺省保持 R10 首次受理 now+ttl_ms，显式值沿同业务 clock 域，在事务内核实未过期且不超过 ttl_ms 上限并原样冻结，包含锁/SQL等待消耗。相同 ID/原文仍领取原记录，不改原 D；HTTP/域排队不能重新授完整 TTL。has_unknown_trade(*,deadline) 只读现有 unknown 或 owner 提交失败事实，读取/事件/确认不通过新命令准入门。note_trade_record 记录已观察的 unknown，使后续新命令停止，保留已有查询和回报处理。

回报轮询按 status→事件页→持久 ingest→业务 ACK→持久确认运行，一轮完成后再等待 event_poll_seconds。status、页和业务 ACK 只按 can_submit 分配；保留已退休缺口的原窗口和两层 ACK。首次状态 RPC 与其源事实读取完成后，再使用 status 会话读取页；后续每轮更新状态。任何时刻只保留一个页、一个该页业务 ACK；未完成原 ACK 前不发送更高 target。四 Host 槽允许读/交易/页/ACK 并存，status 不与该页流水并发占第五槽；缺口不允许无限开启后续轮询。

域任务操作固定为 trade.claim、trade.finish、trade.interrupt、trade.stream、trade.events.persist、trade.events.ack。每次入队前固定绝对 I/O deadline，并随有界 payload 携带；页和确认原 bytes 用规范 base64，不在域线程重新起 D。trade.stream 同一原 D 读取事件 state 与 unknown；其余任务分别调用现 Journal 方法，禁止调用 SDK。域 max_pending 为 8；max_payload_bytes 必须覆盖原读结果、最大交易结果/命令，以及 4*ceil(max_page_bytes/3)+MAX_METADATA_BYTES，并不超过 HostDomainWorker 4194304 上限。已领取的回复与未受理域任务保留到提交或明确关闭失败；BufferError 不丢一次交付值。

正常关闭先冻结 shutdown D 为首次 now+max_call_seconds+2*io_seconds+1，停新业务准入，保留 I/O 完成已受理结果/已捕获回报的已知交接。advance_trade_shutdown 在已知待办排空或原 D 达到时才调用原物理 request_close；晚新回报可能继续存在，瞬时空页不承诺券商未来无回报。持久 unknown 可以作为已保存的待核事实随进程退出，关闭不声称其交易终态已知。首次 D 不续期，超期未保存事实报告未确认并保留 owner；已 join 的线程不能替代持久交接。

异常与 close 必须覆盖尚未领取的 claim future：domain drain/join 后若它已提交 dispatching，按原 command_id 保存 unknown。优先核已提交 finish，已保存源结果不被中断覆盖。已领取但尚未入域的源结果/页/确认保留，关闭管理线程沿原 owner 及各自原 D 完成最后事务；错误或原 D 超期不清事实、不假报成功。I/O finally、域线程、Journal owner 仍按原顺序释放，重入只发关闭通知，不能自 join。

物理 control.request_close/交易中断进入本地收尾态，停止新 status/page/ACK 观察；runtime.request_close 的逻辑停止准入阶段仍推进原末轮观察与交接。收尾时，若某观察 Future 仅交付 ok=false、payload=null，且该观察没有已入域或待入域的持久任务，则可以退休该本地失败观察；运行期同样错误仍作为运输/来源失败处理。退休不产生事件receipt、不推进source_ack、不宣称源排空。ACK回复未成功交付时，保留已持久的ack_intended/source_ack差值供原身份后继核查；成功领取的页/ACK/status及已入域Future仍沿首次I/O D提交或明确报告失败，SQL/原D/提交异常保留原字段及owner。独立交易派发按原ID持久unknown，成功源结果优先保留。全部本地持久事实完成交接后允许Host释放owner；这一事实独立于源未来回调终止与业务ACK是否已确认。

父读域收尾失败与交易收尾分别记录：read.finish/read.scan 的 Future 异常不能跳过同域已经 join 后的独立交易、页与 ACK 交接。父关闭抛错后，交易控制器通过公开 domain.close 接口、仅用原绝对关闭 D 的剩余时间再次确认域已退出；确认前保留 owner 和所有原字段，禁止同步抢写 Journal。确认成功后，已领取事实继续沿各自首次 I/O D 与关闭 D 的较小值收尾，late claim 按原 ID 保存 unknown；最终仍以原父读失败为主异常，保持关闭未完成。再次确认失败时直接保留原父异常与 owner，不运行同步交易收尾，也不重新授予关闭或持久化预算。

验证通过实际 ControlPeer 与 SourceTradingService/TradingControlLoop、SDK 替身、真实 SQLite 构成读/写/回报/ACK闭环；记录进入 SDK 的次数、原 payload/D、提交与 ACK 顺序、重复冲突、队列满/取值异常、RPC过期、late claim/finish、原关闭 D、关闭期间回报及恢复 unknown。再以实际 Win32 builtin-shm 和认证 HTTP 做隔离 Host/Agent 验证。源端账户/行情四查询继续工作；标准 C++ 消费、真实委托与生产发行仍单独验收。

### 断连后的主动持久收尾

状态：accepted，自有Host已实施，原样双场景、101项关联回归及真实SHM源进程故障后继已通过并独审；各自范围见断连证据。断连按原ID持久interrupt的既有义务，在Host仍存活、管理端尚未调用close时同样成立。原I/O finally先撤连接准入，再经内部_finalize_control接缝完成已派发交易的有界交接，最后请求关闭域与运输；只读基类接缝默认空。交易控制的finalize_interrupt只由原I/O owner尝试一次，复用现有域线程和队列，不从管理线程创建新交易事务。

首个interrupt D冻结后保持；新中断任务使用该D，已创建任务/已领取结果保留各自原D。已有成功reply/finish优先保存，late claim只有返回明确原record才按该ID中断。队列背压保同槽与D；submit可能已入队但未交付Future时，保原payload/owner/首错并明确失败，禁止重提、删除claim或猜ID。该范围不新增domain API。read通知/观察失败分别记录，不能跳过独立交易交接；原I/O原因保持。

管理close先join原I/O与域，仅收取原Future和物理owner；已交接完成可幂等关闭，首次中断失败保原异常/身份和Journal责任。晚close不重新起持久化D、不创建新的trade.finish或trade.interrupt补做。结果未知不代表源SDK未调用；源业务ACK/排空与本地持久交接分别报告。

验收包含外部close前原UUID按首次D持久unknown、晚close不增加事务、成功reply/finish优先、late claim、真实submit交付未知、背压/存储超期及read失败独立收尾。当前原样反证与来源见[断连证据](../evidence/2026-10-26-qmt-host-interruption.md)，精确三文件实现合同见冻结设计（外部历史/待归仓路径：`../../build/qmt-host-interrupt-fix-candidate-001/DESIGN.md`）。

## QST-R20 复用认证 HTTP 的交易出口

状态：accepted（开发接口）。交易出口位于现有 app 与 HMAC/nonce/body/并发限制内；终端内保持 builtin-shm，无 HTTP、文件或新网络访问。只有显式 HostTradingRuntime 的 trade_requests_enabled=true 才注册能力选择，旧读 runtime 对新路径返回 capability_unavailable。HostTradeRequest 是 Host 内部冻结值对象，operation/body/command_id 形状校验，并在构造时记录只读 received_at=本地monotonic；body 与时间不进入 repr。app 在进入线程池前构造，该请求 I/O D 固定为 received_at+io_seconds，排队不能续期。

GET /internal/v1/trade-status → trade.status；POST /internal/v1/trade-commands → trade.submit；GET /internal/v1/trade-commands/{UUID} → trade.result；POST /internal/v1/trade-events → trade.events。所有路径不使用 querystring；GET 不带 body。新的 DTO/编解码位于 Host 的 trade_bound.py，原读 HostRequest 与路由保持。lookup/WT应用确认不在本切片开放，不用临时端点冒充原委托关联恢复。

decode_trade_submission(raw,*,max_http_bytes,max_command_bytes) 精确接收 schema_version=qmt.trade-submit.v1、binding_sha256、command_body_b64、command_body_sha256、clock_schema、deadline_ms。原命令 bytes 必须规范并经共同 validate_trade_command，摘要/base64及 metadata 额度复用 bound 工具。clock_schema 只能为 R12；deadline_ms 经共同 deadline_seconds 校验，原样代表 C++/调用方首次业务 D。Runtime 在同一共享业务 clock 域核 deadline 未过期且最多提前 max_command_ttl_ms，将绝对值交 R19 business_deadline，不在 HTTP 或数据库排队后重新起 TTL。相同 ID/原文只领取原记录；源 B 摘要不匹配返回409，新写关闭返回403，来源未就绪返回503。重复未知命令使用 GET 原 ID 核查，不另分配身份。

encode_trade_record(record,*,max_command_bytes,max_result_bytes,control_version='2.0') 返回规范 qmt.bound-trade.v1 bytes，精确字段为 schema_version、command_id、command_sha256、command_body_b64、state、admitted_binding、dispatch_binding、result_binding、source_result、result_sha256、host_reason、queued_at、expires_at、started_at。原 body/hash/命令与源结果按共同契约核实；三个 B 按可信 control_version 核实，不自行从数据选版本；源结果与 B/阶段相符。metadata_bytes 排除 command_body_b64 后仍受 MAX_METADATA_BYTES 限制，完整编码受 4*ceil(max_command_bytes/3)+max_result_bytes+MAX_METADATA_BYTES 限制。queued/dispatching 返回202，其余已保存阶段返回200；GET 未知 UUID 返回404。unknown 为结果未知事实，HTTP200不表示柜台已接受。

decode_trade_event_request(raw,*,max_http_bytes,max_page_bytes,max_events) 精确接收 schema_version=qmt.persisted-trade-events-request.v1、source、after_seq、limit、max_bytes。source 是 R18 的完整 {host_binding,session_id}；范围沿 R18，精确整数拒 bool，整封套有界。只读取已经保存的原事件，Runtime 不要求当前写开启或当前 B 相同，Journal 核其保留来源。输出沿 R18 read 的规范 bytes，无流返回404。此出口不向源发 ACK，也不宣布 WT 已应用，不能被调用者用来回收未持久源票据。

trade-status 是 qmt.trade-host-status.v1 的认证运行快照：binding、binding_sha256、read_profile_body_b64、read_profile_body_sha256、source_status、writes_enabled、accepting_commands、closing、failure、limits。未连接或尚未核源状态返回503且可用字段保持 null；断连时 source_status 一并返回 null，历史查询仍按保存的原记录提供。已核来源返回200，即使配置正常关闭写入。limits 包含 max_command_bytes、max_call_result_bytes、max_command_ttl_ms、max_event_page_bytes、max_events、max_http_trade_response_bytes。该快照不替代每次委托的实际检查，健康诊断仍不提供来源授权。

Runtime 每次 Journal 调用沿请求原 I/O D，提交持久后才唤醒 control.notify_trade，不在 HTTP 线程派发 SDK。错误区分参数400、旧来源409、正常写关闭403、过期408、未知404、容量503与存储故障503；错误去敏，保存原身份核查。配置开关不解除 unknown，不引入逐单签名审批、production_trusted 或实盘资格等级。HTTP/持久/SDK/WT的完整结果各自以实际调用链验收。

## QST-R21 原委托关联与认证查找

状态：accepted（开发接口）。复用HostTradingJournal原文件/事务/命令元数据预留，增加有限trade_order_links；每条insert至多一行，仅保存原command_id、broker_order_id与证明其关联的原源事件session/sequence/SHA及association_error。原账户、WT EntrustID/userTag、token均由原命令派生，不建订单业务状态或财务账本。行/文本额度由max_trade_commands与每命令原MAX_METADATA_BYTES覆盖，源事件仍属于R18事件预算。

同Host私有绑定内，insert的WT entrust_id只能归属一条通信命令，原user_tag完整保留。重复同command/body继续领取原记录；相同WT号换UUID或内容拒绝，不能从重新分配通信身份产生第二次SDK调用。cancel继续复用原insert的WT身份，且broker号必须由本owner持久源事实证明属于原insert；SDK token与account完全匹配才允许认领。broker号允许在不同原委托/交易日重复，禁止仅凭裸broker号全局认领。

R18 ingest在原事务内识别order/deal的完整m_strRemark、m_strAccountID、m_strOrderSysID，token与已保存insert精确匹配且原insert已有持久dispatch_binding后，才保存关联证明；存在的symbol/exchange也须与原命令一致。queued及未派发的definitely_not_called只保留原事件，未知或空token同样不猜关联；后续派发、重复页或重启均不能追认此前事件。原派发B与当前观察源B可不同，派发事实证明原命令已交接，关联source记录此次真实回报的观察来源，允许原订单跨Host恢复后由新真实回报建立当前证明。已知且已派发token的broker冲突、WT64字节槽不可表示或标的冲突作为固定association_error保留原文并阻止新写；原事件仍持久、可ACK。has_unknown_trade与新写_admission纳入这些已知故障。

初始化在一次原事务内验证原命令/关联/原事件前沿与SHA；已有R21表继续验证既有证明，broker或association_error还必须具有原命令曾派发的事实。首次迁移无关联表时，仅为现有原insert建立空索引，broker和source均保持未知；旧R18事件没有可验证的命令与事件先后证明，禁止扫描过去事件补认，即使其token、账户和B现已匹配。原事件原文完整保留，之后新的真实回报仍可按上述规则建立证明。

事务失败回归必须将故障注入精确包围实际events.ingest事务，页准备及state读取在注入前完成；提交前失败应同时缺少事件、关联和前沿，提交已生效但返回异常应同时保留这三项，并以原事件SHA和重启读取核实。

GET/POST仍由原HMAC/容量/HTTP D拥有。新增POST /internal/v1/trade-order-lookup，对应HostTradeRequest('trade.lookup',body)，精确请求为schema_version=qmt.trade-order-lookup.v1及identity；identity仅允许{entrust_id,user_tag}或{sdk_user_order_id}，字符串沿共同契约的精确UTF8/ASCII限额。账户/绑定固定取本Host私有配置，不允许每请求选择；不提供裸broker号查询。匹配一条原insert返回200，未找到404，冲突409，原截止408，存储故障503。

返回规范qmt.trade-order-reference.v1，精确字段：schema_version、insert（R20 bound-trade完整原insert记录）、broker_order_id、source（R18完整B/session或null）、source_sequence、source_event_sha256、association_error。broker与source证明字段同时存在或同时null；association_error是固定安全码或null。无broker时仍能核查原委托，但不能据此撤单。source代表原关联的实际观察来源，不能替换为当前B；新cancel受理要求证明来源与本runtime当前B/source_session相符，否则503等待当前真实回报/查询证据。此规则保留关联实际范围，不新增人工恢复审批。

### QST-R21Q 当前订单查询观察恢复

状态：accepted实施契约，实际验证另登记。本后继复用WT-T01/T02/T09与原Host通信owner，补齐Host/Agent换代后真实订单查询已经返回、原事件证明仍属旧来源的撤单恢复。决策见[ADR-0010](../architecture/adr/0010-order-query-communication-proof.md)。

Host在原BoundReadJournal.finish_bound成功终态保存的同一事务内，只认领本次实际完成的account.trade_detail、policy2.0、datatype=order结果。原终态DTO/摘要及投影版本验证继续生效，关联层另核可信账户范围、完整列表声明和原行身份。每条原source row使用完整m_strRemark匹配唯一原insert；原insert必须已有持久dispatch，账户与证券必须对应，broker身份沿原有限文本校验。查询开始前后的本机UTC不充当柜台水位。历史GET、重启扫描、旧policy或其他datatype不建立新证明。

关联保存于原trade_order_links的query_request_id/query_row_index/query_result_sha256三个可空列，指向原read_operations完整原文；全部为空或全部存在。一个insert最多保留一个查询观察，查询失败不替换原证明，身份冲突沿原association_error锁存并保留触发冲突的查询引用。源row_index是原结果rows的零基下标，不能使用mapper去重后的下标。原query记录已有数量/字节上限且没有自动删除入口；此引用与原记录共同保留，后继清理须保持引用完整。索引元数据计入原每命令MAX_METADATA_BYTES预留；超过现额度时事务整体失败，不发布半证明。

每次lookup/恢复重新验证所引用的原request、完整成功result、原result摘要、policy/datatype、账户范围、dispatch/result B相同、原行身份与原insert派发事实。原查询原文持久校验成功后才发布query observation。query中的transport B代表实际读连接代际；trade event session和券商登录会话仍独立，不给query填事件序号或事后贴当前session。

没有query观察时，原reference.v1精确字段与bytes保持。有query观察时返回qmt.trade-order-reference.v2，保留v1全部字段并增加唯一query_observation对象，其精确字段为request_id（原UUID）、result_sha256（原native结果摘要）、row_index（0..4095原行下标）、host_binding（原result B）。原source/source_sequence/source_event_sha256继续仅代表真实历史event，三者同时null或同时存在；broker可由真实query建立。查询归属冲突仍返回409及原安全错误，不能把它当可用broker证明。

Common显式区分QmtTradeBrokerProofKind::None/Event/AccountQuery。QmtTradeOrderFacts保留原字段，尾部增加broker_proof_kind、query_request_id、query_result_sha256、query_row_index。AccountQuery表明真实query来源可用；source_sequence/source_event_sha256继续保留原event事实，没有event时为0/空。reference私有保存query B，create_cancel必须核原owner/insert/冲突，并满足“真实query B等于刷新后的当前B”或“真实event B/session等于当前值”之一。Host提交在同一当前binding锁下重新lookup并核同样条件。当前B变化后旧query只保留身份解释能力，新的真实ORDER查询才能刷新观察；GET旧结果和当前status不能刷新。

这份证明只说明本次观察的订单属于原已派发命令，不承诺alive、订单终态、持仓吸收、查询/回报共同水位或撤单成功。原WT根据实际订单状态决定是否撤单，SDK结果沿原bool信号/回报语义。P7根据具体Event或AccountQuery分支核原证明后恢复身份，不能仅凭has_broker_proof布尔值省略来源检查。

本切片取消恢复适用原insert已sdk_returned、正常写通道可用的范围。原unknown/提交未知仍受QST-R6/R19及Standard已有写关闭约束；查询可以解释其身份，当前实现没有绕过全局关闭去发送受限取消。unknown下的受限取消需要后继完整准入契约，不能把本次查询证明验收写成所有已派发命令均可恢复取消。

结果持久D：原HostControlLoop在take之前预分配含全部字段的持有槽，并冻结monotonic+现runtime.budget.io_seconds的保守截止；take返回完整reply后先写入已有槽，再解析native payload及入域。take返回空值时沿原未取出路径；已取出后的解析、取时或入域异常保留完整原reply与原D，interrupt/close不得改写为源中断。这是来源执行结束后的持久I/O预算，不续来源业务执行TTL。队列满保留同一结果及D；域线程、Journal锁、SQLite等待、来源/行验证和原事务提交共享它。提交前超时回滚，提交期间或提交返回后超时保留提交结果未知、源不ACK、原owner继续保有；后继按原query身份核查。close对未入队原结果沿min(原持久D,close D)处理，不能授新期限。旧直接调用finish_bound保留可省deadline签名，生产read.finish链必须传入冻结D。

适用回归：新B无新callback、同token/broker的真实ORDER查询后恢复取消；无历史event的已派发insert；未派发insert不认领；错账户/证券/token/broker、旧policy/其他查询、查询失败、旧B、历史GET、查询结果篡改、事务提交失败、重启及元数据预算；原v1正常/冲突bytes与event取消保持。验证完整Host通信链与Common真实HTTP消费，SDK用有界替身，真实交易另按授权。

lookup结果可在写关闭或当前断连时读取，供原ID核查；不自动解除unknown。WT消费确认及完整查询/推送交接另有验收范围，lookup成功不能证明持仓快照吸收了某条成交。


## 未知委托定向取消后继边界

[UC规格](qmt-unknown-cancel.md)及[ADR-0011](../architecture/adr/0011-unknown-order-targeted-cancel.md)按明确v2状态语义承接本规格unknown整体停写的受限取消后继。当前只接受源端/Host/原Journal实施；普通v1路径保持，Common/Standard新增审计预算和完整用户链尚未完成。新Agent/Host版本不得提前切生产；unknown原记录不改，一般恢复新下单的解除机制继续单独闭合。


R19观察失联收尾补充（2026-11-03）：原peer已关闭、Future已retired且成功观察reply已完整领取时，status/trade.stream、page/trade.events.persist、ack/trade.events.ack三个非金融poll阶段可在明确未入域且原D到期，或域Future已经结束并返回TimeoutError时放弃本轮观察调度。完整原job/reply/Future保留在本代，不发送运输ACK或源业务ACK、不重做事务、不改首次D；事务提交结果以原Journal为准，原持久ACK意图及源端未确认事件保留供同Journal认证连续性接续。_poll_drained保持false，不授源排空。提交未知、运行中、其他错误和金融trade槽继续原保护；管理关闭仍join域/I/O，晚截止继续失败。此规则不改变读命令、委托或撤单的结果保存与核查边界。


## 只读终态持久超时后的原身份关闭核查

原只读finish任务必须保留完整payload、Future和原持久截止。正常路径在持久确认后沿原ACK推进；发生TimeoutError后，关闭线程先join唯一域，再在同一原关闭截止内查询该原UUID/请求正文摘要/operation/dispatch binding。Journal已经保存完整一致结果时保持原字节；仍为executing时仅沿原interrupt_bound转为原请求中断终态。原请求、SDK和持久截止均不延长，不重新提交finish，不补源ACK。Future和原值仍由关闭对象保留作证据。

持续运行的 `account.trade_detail` 在原 finish Future 已结束并返回 `TimeoutError` 后，可在同一域单独核账一次。原域队列繁忙导致入队前超期时，同样先按原 D 拒绝写入再核账。检查原请求身份与原终态；如原事务未提交，沿原只读中断结果关闭责任。只有核账已持久完成，活跃传输才退休该原 RPC，后继由账户查询正常调度。停止期间只在原关闭 D 内核账，不补 ACK；核账事务晚回时识别已保存的同身份中断。诊断记录原请求摘要、核账阶段和固定结果；核账失败、身份冲突及非只读业务保持原故障语义。

该核查只接受完成且未取消的只读finish TimeoutError，并保持原peer已退役。运行中、非Timeout、身份/原终态内容冲突及未核清的结果继续保留原owner并报告关闭失败。交易claim/finish/unknown及Source事件ACK路径保持原有责任。常驻服务只有确认整代物理资源和Journal关闭后才接续同Journal的新运输代际。故障快照分别记录只读commit是否存在、是否完成及固定异常类别，避免仅凭交易jobs=0误判域已无只读责任。
