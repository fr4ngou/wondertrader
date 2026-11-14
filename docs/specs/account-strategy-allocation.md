# 同账户策略份额归属（ASA）

类型：功能规格。状态：实现中，尚未取得Native接线或金融运行资格。实现owner为`guanheng_wt_runtime.account_allocation`；原WT/Host继续唯一拥有交易命令、订单状态与恢复核查。模块不连接来源、不发委托、不撤单、不改原Journal、不创建daemon或交易队列。

## 已确认业务与现有能力

用户确认同一既有模拟账户下旧策略和共振原版并行：旧库存及原金融基准归旧，原版新增现金100万元、初始归属库存0。WT原ctx理论账、schedule目标汇总、Local执行、原submission group/command UUID及真实成交来源继续复用。账户P/A不携带策略份额；现V2 submission_revision仅账户本地顺序，不作为多ctx归属证明。

复用依据为[原生能力目录](../development/wondertrader-capabilities.md)WT-S01及交易执行能力：[WtCtaEngine](../../src/WtCore/WtCtaEngine.cpp)继续汇总和提交组合目标，原Local执行器/Host继续决定实际child与委托状态。ASA只补原账户实际份额缺少ctx归属的职责；不复制原撮合、重挂、账户观察或订单恢复流程。显式启用ASA的coordinator接线另行验收，缺省单策略路径保持原生行为。

## ASA-1 唯一owner、存储及精度

由原执行租约持有人构造`AccountAllocation(financial_root, identity, owner_check=...)`。每次读写先调用原`owner_check`；该回调成功返回None，失去租约时抛原异常。模块独占 `account-allocation.sqlite3`。配置可用 `allocation_root` 指定已有账本的独立 D/E 盘绝对目录，缺省沿原金融目录。切盘前必须复制并核对已有账本，缺库时拒绝从初值重建。后继配置可在执行配置根声明 `shared_account_storage`，仅指定绝对账本目录，沿原共享账户描述符的身份和初始凭据核同。原冻结策略行保持原身份。其他原 Native 状态继续沿 `financial_root`，原Journal始终只由原owner使用。短SQLite事务和同进程锁串行owner/worker的不可变关联；每个入口接受原单调deadline，锁等待/SQLite等待计入该D，取消/期限异常保留原异常。所有磁盘路径位于显式E/D金融root，SQLite临时存储使用内存。

`asa-book.v3` 保留原账户、账本及基准身份。一个事务内验证 v2 的整账摘要，将订单、成交、计划、绑定和来源证明按原身份迁到独立行，保留原事件、收件、冲突和原水位。运行时仅加载相关行，策略余额、账户观察和活跃计划引用保持同一事务。升级前备份原件并先在副本执行迁移和对账。一个原账户只允许原 Native 账户租约持有人写账，进程内 SQLite 提交按同一 owner 锁串行。收到原回报先持久化收件，归属及已应用状态同批原子提交。进程在提交前退出时回滚归属并续核原收件，提交后退出时重放沿原 ID 幂等。切换数据盘要正常关闭旧 owner，使用 SQLite 一致性备份，核对全部原命令和待决责任后方可让新 owner 接管。v1 冻结原件不参与升级。

### 账本接管和回退

- 进程重启沿原 Native 账户租约接管同一账本。先续核已持久化的收件与未完委托，再以券商的实际委托、成交、资金及持仓核对策略账。沿原命令及成交身份查询，结果未知的命令继续保留原责任。
- 账本文件缺失、损坏或身份不匹配时保留现场，恢复前核对备份的账本身份、版本、未完委托、预留和来源水位。使用 SQLite 一致性备份取得包含已提交事实的完整快照。新盘写入后需要回迁时，从新盘生成最新一致性备份并对账，旧盘冻结副本仅作为切换时的证据。
- 回归覆盖多个线程重复收到同一笔成交、已收件后提交前退出、提交后退出再重放。逐项核对原委托身份、未完责任、现金、预留、持仓及收件处理状态。

币种固定CNY，输入金额为Decimal、精确到分；价格为Decimal、精确至0.001元。证券使用`SSE.ETF.510500`/`SZSE.ETF.159780`原WT三段身份。份额为非负整数，策略目标/BUY申报为100份整数倍；SELL保留原WT合法整数碎份，实际部分成交可为整数份。本金用整数比率ROUND_HALF_UP至分，分配余分按实际份额余数及原FIFO次序分摊，计算不依赖调用方Decimal上下文。无浮点金额输入。BookIdentity绑定账户摘要、原金融book UUID与旧基准SHA，正常重启不改这些身份。源UUID/SHA按原值核验和保存，不用当前Runtime随机身份重写经济归属。

初始化现金为非负预算，之后账内现金记录实际本金及费用的有符号余额。真实部分卖出所得不足覆盖已确认费用时，如1份×2元减实际费用5元，余额完整记为-3元，策略净值按该负余额计入成本，不转换为零或第二套应付账。该费用继续归原策略，不借用另一策略预算。可买金额始终为`max(0,账内余额-全部预留)`，BUY派发前继续检查本金/费用足额。

## ASA-2 初始化与账户观察

归属适配器以完整P/A较早接收时间的上海日期，经同一已核官方日历选取不晚于该日的最近开市日。周末接收的P/A沿此前开市日核对，T+1继续受真实可卖与交易日约束。Native的计划tdate保留给策略排程；原账户事实日期沿接收来源和日历所有。日历覆盖外或没有此前开市日返回`account_observation_day_unqualified`，原账及未来日防线保持。

`initialize(seeds, unallocated_cash_cny, account_snapshot, deadline=...)`原子创建旧/新初值，策略优先级显式给定，旧优先。StrategySeed含策略id/version、现金、完整证券池universe及OwnedPosition(quantity/sellable)；旧原现金/数量由调用方从旧owner提供，本模块不重建旧PnL。新策略使用100万元现金、空份额。券商数量减去已显式分配数量成为未分配份额，不复制到各策略。现金分配沿原金融owner的基准与新增预算证明；本模块不能由账户available重建原总现金/本金。

重复初始化必须规范输入完全相同，身份或初值冲突拒绝。`observe_account(snapshot)`仅接受递增/同值幂等来源序号：该序号由原金融owner跨正常重启持久保持，不能直接传入每代归零的扫描序号。来源交易日晚于当前上海日期返回`account_future_day`，未来观察不能提前解锁T+1。完整P数量必须等于所有策略归属与未分配数量之和；差异明确`account_position_mismatch`，不按比例修正。初版仅通过已记录买入的明确settlement_day及当前账户sellable核同解锁可卖，无法解释的冻结变化拒绝，不虚构企业行为/人工交易归属。available仅为全账户可买上限；各策略另受自己的cash及占款约束。调用方提供同一完整观察的P/A，确保已覆盖此前入账的D；不能把晚收到的旧A和新P拼接。

账户上限在上一完整P/A后按实际成交本金/已知费用调整，后继闭合P/A核同后归零该调整。同序号旧观察幂等保留本地调整，避免已支出资金再次消费。未结原组的所有预留再从该上限核验：来源available已经包含原订单冻结时会产生保守的重复占用，当前实现保持该保守性，等待原owner提供可证明的冻结抵扣明细；金额不足明确返回原因，不能自行加回未知冻结款。

正常待卖订单的原P可卖量已经扣除券商冻结。调用者可在同次完整P/O观察中给`sell_reservations:tuple[SellReservation,...]`：每项为原prepared SELL command UUID、实际剩余冻结量、原订单证明SHA。模块核其原绑定、未确定终态、剩余量界，然后验证`各归属原可卖合计-已证明原订单冻结=Source可卖量`；原归属数量和原可卖资格保持，不按比例分配P。预提交意图、未知命令、未绑定单、外部未归属冻结均不能提供该抵扣资格。缺证明仍返回具体不一致原因并保留原观察inbox。

### ASA-13 通用账户配置

WT 原生 CTA/执行器继续提供策略上下文、路由、合并及实际订单（WT-S01、WT-S06）。观衡账户装配从 `executer.shared_account` 读取已有格式的固定 `{path,sha256}` 账本描述符，以 `strategies[].id` 对应初始化材料中的每份归属seed。每个已注册的策略实例拥有自己的编号、优先级、初始现金和执行证券池。策略实例数量沿原CTA 64实例容量，编号按Windows原状态路径验证大小写无重名。原版策略声明的 `initial_capital_cny` 是正的CNY金额，精确到分，初始账须同额及零归属持仓。旧策略本金及库存沿其原已核输入。通用初始账户的全部策略现金与未分配现金不得超过固定账户可用事实。多份执行池共用一份覆盖其并集的费用材料。

原双策略材料中原版profile持有的 `shared_account` 描述符沿旧结构可读。通用配置由账户执行器统一拥有描述符，策略行只指定已注册的算法及自己的参数。只采用已登记的profile；当前保留策略的模型合同使用原固定身份，原版profile允许按配置注册多个独立实例。实际执行集合须与每个策略的分账证券池完全相同。现有账本的初始化事件按原身份精确重放。已运行账户追加策略需要沿原原生状态接续及未分配资金入账合同，通用初始装配不以重建账本替代接续。

## ASA-3 意图、净额计划和内部转移

`record_targets(TargetIntent)`记录策略完整目标、原意图UUID/序号/来源SHA/known_at。每轮必须显式列出universe所有证券，含零目标；未知证券/重复代码/旧序号新正文拒绝。目标不是成交。策略未提交新目标时保留其最后目标，不能解释为清仓。净额计划固定保存当时各策略原意图依据，后继target不能改写旧成交归属。

每个Target可显式给出`buy_price_cap_cny`，默认None沿旧策略原价格规则。上限属于该策略该轮意图，不修改其他策略或已prepared原单。新意图变更在后继计划生效；未结原group/child仍沿原身份负责。

`plan(plan_id, prices)`按证券检查未决责任：有未结原group的证券记录`blocked_symbols/blocked_reasons[pending_group]`，其旧group/child/分配/现金预留保持，其他独立证券继续创建需求。每只可处理证券按已接受策略优先级FIFO形成固定残余需求，复用原WT净额执行。原group释放后，调用方沿最新原意图和新分配计划ID重评该证券，不重算原信号，也不给未知委托换ID。

对向意图只有在CommonPrice明确qualified、包含双方strategy_id、且价格可知时点不早于双方目标、不晚于当前时刻时才转移。只转移旧方已归属、可卖、未占款份额；买方现金足额。内部转移同时增加/减少双方cash和quantity，账户数量/现金守恒，费用0且事件为internal_transfer，不伪造券商成交。一个证券的全部内部配对原子生效；无共同合格价/价格时钟或cap不符/资金或可卖量不足时，该证券保留原归属并登记等待原因，不生成对向柜台单，不回滚其他独立证券的计划。没有次数门槛。

### 双策略实际执行

本版配置沿既有双策略接线显式启用 ASA。WT 原生继续生成风控、过滤、路由后的执行目标。ASA 读取原执行器收到的全量目标及后续增量，再按原执行器配置的 `scale` 解释账户目标。原策略意图继续承担归属和买入上界，原意图与执行目标可有合法差异。未收到本代两份完整意图及可用的原WT目标前等待，过滤掉的证券不产生新归属许可。

双策略运行关闭自动内部转移，现金和份额沿已归属的原柜台成交变化。按实际账户持仓与有效目标确定可执行净差。同向需求按原策略优先级处理；WT 风控要求更大净减仓时，从剩余已归属持仓继续分配，不动用未分配库存。相反方向净差为零时保留双方实际份额，目标与实际差异如实保留。需要让旧策略卖出先进入WT时，应在原版提交买入目标前完成时段与同码退出准入。原未决组、原指令身份和占款由已有合同接续。底层纯归属内部转移能力只保留隔离验证用途。

QMT成交手续费未确认时持续保守占款，策略实际现金和净值保留未知。观衡数量规划继续处理已冻结卖出，或目标为零且可从自有库存直接确定的退出。尚需净值决定数量的调仓继续等待；新买入继续核余额和占款。按份额卖出前仍核实自有可卖及原订单状态。旧单策略原账户资金分支保持原合同。

## ASA-4 派发前关联与资金约束

`preview_group(plan_id, symbol, side, requested_qty, limit_price_cny, fee_bound_cny, deadline=...)`在原WT建组前返回GroupAuthorization。该小DTO记录原请求/可分配数量、原canonical限价、费用上界及当前账水位。该入口不消费计划需求、不增加预留、不派发命令。BUY总量向下到100份，SELL保留原合法整数碎份；0表示当前资金、限价或需求不足，等待输入变化。它不会永久禁止后继目标。

预览和`bind_group`共用唯一份额/资金分配函数。BUY按原计划FIFO，先扣全部未结/未知预留，再按各策略cash、全账户available及该策略buy_price_cap裁剪；实际限价超过某策略cap仅跳过该策略，继续其他策略需求。每个参与策略的完整费用上界也占用账户BUY额度。SELL只核本策略可卖/未占用份额，保持原WT退出规则，不增加策略或账户预存佣金门槛。计划中已完成的内部转移使用其共同合格价，买方cap不满足时明确`internal_price_cap`等待调用方重新核实计划，不能自行创造对向柜台交易。

`bind_group(plan_id, GroupBinding)`在原WT delegate前固定原group身份、证券/方向、总量、真实限价、整个group费用上界，并按原计划FIFO预留各策略剩余份额/限价本金及费用。买入本金按每份限价向上到分再乘剩余量预留，覆盖整数部分成交逐笔向分舍入；须各策略cash和全账户available扣本模块所有预留后足额。卖出须本策略可卖/未占款足额。未知订单不释放预留。

预览后的资金、需求或实际限价仍可变化。bind_group在最终事务内用同一函数重新核验，仅当完整原group.quantity仍可分配才持久；变化返回`authorization_changed`，原调用方在真实派发前重新预览。预览水位本身不授交易权限。

初版为每个参与策略记录该group完整剩余费用上界，覆盖一个部分成交可能首先只归该策略；该上界与未结BUY本金共同限制后续BUY，未知卖出费用上界超过已有现金时仍可正常读取view及退出，可买金额为零。实际费用按实际分配份额拆分且总额只记一次。该保守预留及实际上界来源由调用方显式提供，不提供隐式固定费率。费用上界须覆盖整组可能重挂的全部child，最小费不能在每个策略重复计作实际费用。

`record_wt_child(WTChild)`先在原enqueue前固定原group、entrust/user_tag完整身份、实际量价与原事件证明。策略FIFO在该原WT child阶段固定，worker跨child回报乱序不改变归属。`bind_prepared(PreparedCommand)`由原worker在取得原command UUID及原正文SHA、尚未真实提交前调用；必须与已持久原WT child的量价逐项对应，持久成功后返回DispatchPermit。原量/价格不得超过已预留范围；重复同UUID同正文返回`first_binding=False`，此时沿原ID核查，不重新提交；冲突拒绝。`lookup_prepared(wt_order_id)`只读返回持久原UUID/SHA及量价，供真实D沿原WT身份关联。模块不验证Source签名或代替原Host准入，许可只证明归属/占款已持久。

BUY首次prepared在该最终事务再次核资金与全部原预留，覆盖原group建立后收到真实费用的窗口。SELL不检查预存佣金。此前已派发且原量价均合格的真实成交完整入账；后到的真实费用导致原策略余额为负时，后续BUY授权为零，不能以预算变化丢弃原D或转嫁给另一策略。

原group绑定、原worker prepared UUID关联分别为两个真实阶段，不能用返回后的submission_revision补造派发前证明。worker仅传入不可变事实，不调用策略ctx或策略KV。

## ASA-5 实际成交、终态、费用与重启

`apply_fill(FillFact)`仅接受已绑定原command的原成交标识/证券/方向/量/价格/金额/SHA。按派发前固定的child归属分配，实际份额、金额、费用各自守恒。原fill ID沿Native稳定金融身份，跨query-result/derived-facts的证明SHA可合法不同：同经济字段只追加source_proofs，保留首份source_sha256，不重复分配份额或本金。未知费用/执行时钟可沿后继真实证明补全；两个已知值冲突时拒绝。经济冲突持久留证后抛`fill_economic_conflict`，同冲突重放仍失败，不会被当作已完成。

买入明确settlement_day；卖出只消费本策略可卖份额。成交事实晚于目标更改仍归原计划。unknown child仍可接收经原owner核同的真实D。CNY/份价及金额格式在本模块保持严格Decimal合同；Source double尾差的可证明规范化归接收适配器，原raw JSON及Source SHA保留在inbox，明显非档价格或亚分金额不能普通舍入。

真实手续费None保持unknown，保留费用上界占款，实际cash/NAV资格不冒充已知；`apply_fee(FeeFact)`随后沿原fill补入确定费用、恰好一次扣款。零费用必须显式Decimal('0.00')。手续费/实际成交超原资格上界时拒绝并保持原绑定与占款，调用方继续持有原Source事实进入核查，不可丢弃或认定未发生。

下一次自然发生的实盘成交为手续费接入验收窗口。用当前启用的 QMT 内置成交查询读取该笔费用及成交编号、柜台委托号，与最终结算逐项核对字段含义、金额单位、小数精度、确认时点和逐笔/整单粒度。逐笔结算按该笔实际成交份额归属分摊，整单结算按各策略实际成交金额分摊，分摊合计精确到分，最低费用按券商实际收费计一次。覆盖重复回报、部分成交、合单及明确零费用。确认前保持待确认；验收使用自然成交，不为验证发单。

`apply_terminal(TerminalFact)`沿原事实记原command的filled/cancelled/rejected/not_called/unknown。unknown只记录来源并保持占款；取消受理不当终态。确定child终态必须给原累计filled_quantity并与已入账D完全一致，O先到时返回`terminal_missing_fills`，原inbox保留pending，D到后重放原事件；filled还须全量。该正常事实异序不应直接让Native整体失败。跨query重到的同原command/确定状态/累计filled只追加原proof，组已closed也接受经济幂等；后来较弱unknown只留证明，不回退已知终态。两个确定状态或确定累计量冲突时持久留证并返回`terminal_economic_conflict`。

`record_group_end(group_id,accepted_children,proof_sha)`仅记原delegate退出及原接受数量；commands为空不足以收口。`record_child_not_called`只能沿正面的本地NotSent/dispatch_not_entered或原确认未调用证明结束尚无prepared的WT child。统一`_close_if_resolved`在group_end、child not_called及原command终态后组合证明：delegate已结束、`prepared子数<=accepted_children<=全部已记原WT child数`、所有已记child均已prepared确定终态或明确not_called。每个accepted在enqueue前已持久WT child的原因果保证排除未记accepted；accepted原计数不改写、不猜具体名单。该条件完整成立才自动收口，显式TerminalFact group_closed仍沿同一严格逻辑核验。

组收口时未成交需求回原计划FIFO，未知费用继续占款；撤后原WT再次调用会建立原生后继group。旧UUID/child永久保留，不自行重挂或把缺回报改成未执行。

`view(strategy_id)`返回该策略自有份额/可卖/占用、有符号账内cash、非负spendable、未知费用计数、未结原group及持久水位。未知实际费用时cash_cny为None且保留账内已知值；已知实际费用导致负余额时cash_cny/ledger_cash_cny明确显示负数。上界预留超过余额保持可读，不以该状态阻止卖出退出。原目标/计划/绑定原件由单一SQLite事实owner保存，不在view复制mutable账。账户全P仍为账户事实，策略调用方必须消费此归属view，不能只放宽原broker_scope。SQLite损坏、身份冲突、丢租约、来源数量不一致、截止/取消均明确失败；不重置旧账或消费原Journal ticket。

## ASA-6 原事件inbox与投影水位

`lookup_wt_child(wt_order_id,deadline)`只读原child的完整group、原WT身份、已关联command UUID、明确not_called及持久terminal_state。缺原child返回None；未prepared与未确定终态分别保留None。该接口沿现有children/commands事实读取，不改变表结构、派发许可或状态，用于原prepared收件恢复及排除迟到旧active O。适配器只在内存投影尚有责任的自有SELL冻结，全部历史O仍保存在inbox。

`receive_event(event_id,kind,raw_json,source_sha256,deadline)`先持久原UTF8 JSON字节及payload_sha256；原Source SHA另存，Native本地NotSent没有Source结果时明确None。JSON保持原字节，重复key、非有限值、坏UTF8拒绝；单事件2MiB沿NAH原事件上界。kind为原类型的字符串，不是新业务状态。收件和幂等投影分别确认，不用inbox替代原Host Journal或命令队列。

`receive_broker_event`在同一收件事务内按原WT标识查已绑定命令。缺归属时同步记录固定原因，保留原字节和待处理状态。查询、实时事件与重放采用相同查法。重放批次优先读取已有原委托绑定的柜台事件。历史外部回报仍可从完整收件记录读取，之后补齐原绑定的事件会在后续批次纳入重放。首次成交分配返回是否改变实际数量，由回调据此更新账户观察时点。重复回报继续核对经济事实并追加证明。有关联时仍走原成交或终态校验，收件本身不改变经济事实。全账户查询在原件收件提交后按同批投影，用一次事务提交已归属成交、终态和投影结果。经济事实冲突继续留证并沿原回调报错。私有回调收据同时保留原失败和失败原因落账异常，并记录阶段、事件摘要和时间预算。

已确认收件后，归属事务遇本地账本处理超时，回调仅确认原件已接收。原 Native 来源截止仍有效。执行器保留本轮待核状态，暂停新委托授权。后继账户观察使用新一轮预算按原收件与原委托身份续查，核对通过后恢复授权。收件提交前超时继续沿来源原责任和现有恢复处理。经济事实冲突、损坏和租约失败保留原故障路径。回归验证提交前、提交后、重复超时及重放幂等。

`pending_events(limit=100,after_sequence=0,max_bytes=2MiB,deadline)`按原收件顺序有界分页；`mark_event_failed(event_id,固定原因)`保原件供原owner重放，`mark_event_applied`只说明归属投影已提交。柜台成交时钟领先本机至多一秒时记录 `fill_clock_pending`，保留原时钟和原成交，后续原调度在该时间已到后按原身份重放。更大时钟差仍沿原拒绝和故障规则。没有daemon、自动发单或Source请求。归属提交后进程退出而尚未mark时，重放按原金融ID幂等完成；取消/截止保持原异常，已提交事实不删除。明确未调用后的旧prepared失败事件应沿正面NoCall证明完成处置，不能重新取得派发许可或换UUID。

## ASA-7 策略观察与原开仓周期

`current_targets(deadline)`一次事务返回各策略原TargetIntent或None；None保持尚无intent，调用方沿自有实际份额处理，不能解释为零目标。该只读投影不复制可变目标账。

`strategy_observation(strategy_id,deadline)`同一事务返回StrategyView、account_revision/account_source_sha256/trading_day及标准symbol到OpeningCycle或None的映射。它不含账户接收时钟；Native原broker_observation仅补来源/新鲜度核验，账户P/D不再用作策略份额分配。

初始旧持仓周期由StrategySeed.opening_cycles显式保留原cycle_id/opened_at/原SHA；缺证明为unknown/null，不能用今天重建开仓。实际FillFact.executed_at为原真实trade_time的含时区时刻，可选None。flat到正数首次真实增量BUY建立稳定周期ID，缺执行时钟保持unknown；后继同fill真实时钟证明可补全。原同证券全部卖完清除当前周期，后续再买建立新周期。内部转移买方原flat时沿原plan/配对身份及共同价known_at建立新周期，卖方flat自然结束。周期只引用原分配D及原证明，不另建一份D账或用P/price猜开仓。

### 策略内存读取和账本持久化

共享账户的单一写入者由原 Native 账户租约约束，跨线程账本事务使用同一写锁。资金、持仓、可卖、预留、未完委托、开仓周期和目标按同一账本版本生成快照，提交成功后一次发布。策略读取已核快照时无需打开 SQLite，也无需等待写锁。持仓、资金查询版本或冻结依据改变时仍同步核对账本。首次启动、原待处理回报及交易授权继续经过原执行链。

共享账户运行时启用 SQLite WAL 和 FULL 同步。原运行进程持有一个写连接，后台只做 PASSIVE checkpoint。进程异常退出后由 SQLite 重放已提交事务，原 Native 账户租约接管前后保持唯一，原收件及委托身份可重放、可对账。正常关闭先回收历史读取和 checkpoint 线程，再关闭连接。数据盘损坏时按账本接管和回退流程使用一致性备份及券商事实恢复。

成交展示由后台通过 SQLite 只读事务刷新，沿当前账本身份和版本匹配后附到策略报告。此切片保持既有最近成交展示窗口，独立分页接口未接入。原市场计算、策略状态保存、提交新目标、券商新水位对账与原回报持久化的时延分别测量。

热读目标为 p99 不超过1毫秒。验证覆盖写事务未提交、提交前后进程退出、原回报重放、checkpoint 和同一账户策略并发读取。整批回报、正式无下单启动及生产接管需要各自证据。

2026-11-13 在 D 盘使用正式账本的 SQLite 一致性副本。在写事务保持打开约 2.5 秒、后台 checkpoint 按正常节拍运行的窗口，分时段测量 10,000 次 `strategy_state`，p50 0.0028 毫秒、p99 0.0064 毫秒、最长 0.19 毫秒。该测量包含内存状态读取及调用方副本，使用隔离租约替身。另用冻结券商账户回报，重复执行已核来源检查及内存读取 10,000 次，p99 0.015 毫秒，未计入 Native 桥复制和策略计算。另在同类型副本追加 10 万条模拟收件与已结记录，每次回报批量上限为 64 行，每类测量 60 批，成交回报 p99 26.6 毫秒、委托回报 p99 37.6 毫秒。压测使用已存在的经济事实及其重复证明，交易策略完整回调、真实柜台及生产切盘另验。

## 验证与资格

先验证人工初始化、同向部分成交、单次最低费用拆分、内部净额守恒、冻结份额拒绝、目标改变后的晚成交及重启幂等。随后覆盖重复/冲突、未知费用、派发前资金不足、prepared越界、终态释放、账户对账、租约/截止/线程和持久格式异常。模块测试不授Native挂钩、原UUID派发路径、模拟账户运行或交易资格；该接线由原宿主另验。

本模块所需外部证明仍由原金融owner提供：初始化的旧现金/库存及新增预算、跨代稳定账户/基准身份、完整一致的P/A及递增观察水位、真实费用或明确未知、settlement_day、共同价资格、group后继已结束证明。模块不从行情/账户全量推算这些缺失归属。


## ASA-12 观衡只读归属投影

`strategy_observation(strategy_id, deadline=...)`沿原owner_check和同一SQLite事务读取，不调用 `_save`，不新增持久账或金融命令。StrategyObservation附加可缺字段：book_scope_sha256（原BookIdentity规范摘要）、observed_at（owner读取UTC时刻，仅展示不参与经济DTO相等性）、targets（原已提交意图的完整数量，未提交None）、fills（真实D已有allocations的本策略部分，旧发布None、完整空tuple）、fills_truncated（最近2000条展示截断）。原字段、原状态格式及所有交易算法保持。

每条OwnedFillObservation保留原fill_id/证券/方向、已记账分配数量及金额、原价、原交易日及可缺的真实executed_at、原来源SHA。费用使用原 `_split` 与原allocations次序；原fee未知仍为None，内部转移不加入实际成交。UI公开成交ID由策略和原D身份摘要化，不公开原订单号。投影的2000条是发布容量，原历史不删除、不限制后续交易；观衡明确显示截断。NAV/价格估值及投资收益不由此接口创建，相关公开读取和兼容约束见[LSP-5](live-strategy-performance.md#lsp-5-同账户多策略归属读取)。


`allocation_projection`缺省严格保留原五字段，供既有金融输入指纹使用。仅原两个profile的三处报告发布显式传 `include_read_projection=True`，追加展示字段；读取clock及最近D窗口不会进入原金融指纹。该分流由LSP源码回归核验，不改变原策略数学、目标、权限或金融账。
