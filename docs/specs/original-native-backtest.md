# 原版信号的 WT 标准回测

类型：功能规格。状态：开发中，现场采用和自然运行另验。范围：冻结原版351f9d5 stable信号，沿WT原生撮合与原受管回测宿主运行；原组合ORR仅保留为WT内部信号参考和Git忽略研究材料，不作为观衡公开策略或回测。

## ONB-1 身份与模型

策略ID为 `resonance-original-wt-351f9d5-stable`，默认版本 `0.1.0a2`，显示名“原版信号·WT标准回测（现金约束）”。旧 `0.1.0a1` 保留其原模型和历史证据，读取时按版本严格分流。信号算法ID继续为 `resonance-original-351f9d5-stable`。原BUY/SELL来自完整冻结ORR报告的 `trades_by_code`，本模块不重写信号公式。

保留冻结日线真实OHLC形状，D日闭合信号在WT `on_calculate` 形成目标。a1使用零限价目标，通常下一日开盘成交；a2使用原生 `stra_set_position(limitprice)`，由原CtaMocker条件和撮合决定实际触发与后继tick成交，允许未成交和延后。WT日线的模拟tick时间戳可能仍为15:00，不能据此描述为真实盘中或收盘成交。原CtaMocker负责pending、T+1、成交、费用和损益；适配层不自建撮合，不改变原框架，不将日线改成close-only。

初始资本固定人民币100万元；ETF数量为整数份且按100份向下取整。新BUY对当时原生已成交在仓集合与本次新买集合等权（同时去除SELL）；只有SELL时释放对应仓位，其余份数保持。目标用D日可见价格/NAV和显式费用预留计算，不读取D+1价格。末日未到下一事件的信号保留为未执行目标。

原生当日买入的T+1冻结份额以total-valid核定。SELL先减少可卖份数，冻结余额保留原意图至后继可卖；新BUY等权若需减持冻结份额，完整等权提交延后，在合法D时点用当时价格/NAV重新规划。意图元数据不代表成交或独立现金账本。信号日期/原因仍逐字保留，延后提交以status/reason说明。

WT CtaMocker资金接口报告损益；源码没有本金或证券现金购买力开关。a1按D日NAV规划零限价目标，在次日跳空时产生负现金。该旧模型继续按其原MODEL读取，不能当作现金约束结果。

a2在原BUY当日用D日NAV、价格和费用预留固定等权份数计划；每个后继D日只以已成交持仓和原生损益推算的实际现金承担本批买入。全部增加份数按当日收盘价设置原生买入限价，总本金加绑定费用上界不得超过实际现金减1元舍入余量；不足时按需要金额同比缩减并向下取100份整手。绑定费用支持比例、按份与最低收费，买入费用上界另加1分舍入余量。卖出款在实际成交后才进入下一次D日现金，不预支未成交销售；卖出原生最低限价覆盖收费上界，保证卖出自身净流入非负。T+1冻结数量继续保留，所有未实现份数意图在下一原生calculate重试；原生在calculate前清理上日尚未触发条件。存在已触发pending时整体保留责任，不重叠下单或重复占用现金。新的BUY重新生成等权份数计划，SELL取消该证券剩余买入意图。

买入限价、现金分批、未成交等待和固定份数计划都会改变成交日期/数量。a2每次逐日现金负值都属于失败，不以披露风险替代约束。原生条件设置没有ack枚举接口，submit/readback仅核提交期间实际持仓不变，不能解释为已成交；成交和费用以原生CSV及后继实际持仓核对。本模型仍缺真实盘口、涨跌停队列与成交量约束，不能据其每日OHLC条件撮合宣称实盘可实现收益。

## ONB-2 冻结输入

schema=`guanheng.original-native-replay-input.v1`，字段由唯一 `original_native_replay.normalize_input` 严格准入：

| 字段 | 合同 |
|---|---|
| strategy | 固定strategy_id/strategy_version/algorithm_id。 |
| reference_report | 完整ORR报告，schema/上游commit/算法ID精确匹配；全部原信号唯一来自该对象。 |
| reference_report_sha256 | reference_report按原ORR UTF-8规范JSON编码的SHA256。 |
| source_snapshot_sha256 | 与reference_report.input_sha256一致的原完整输入规范摘要。 |
| history | code6→按日期升序唯一的OHLC、volume、amount行；最多9ETF、4096日。 |
| calendar | 升序唯一ISO交易日，主代码日线完整覆盖；其他证券上市前允许无日线，不前填造价。 |
| evaluation_window | from/to与ORR全部portfolio.history日期一致；warmup_date为此前一根真实主日线，仅供WT初始化。 |
| policy | 初始资本1000000 CNY、显式资本来源、份数单位、multiplier=1、lot=100。 |
| fee_reserve_cny | D日规划保留的非负人民币金额，明确模型输入。 |
| fee_source | 实际费用规则来自WT绑定fees资料的说明。 |
| market_manifest_source | 本次冻结日线来源说明。 |
| price_basis | 输入原始/复权价格基准说明，不把前复权自动改称原价。 |

`build_input(snapshot,report,...)`先核原report.input_sha256等于原snapshot规范SHA，再提取同一OHLC行。金额字段缺失时WT加载的money=0仅作兼容值，来源金额资格保留未知；量的来源单位及历史首次可知也不因回测运行而升级。有限值、错日、重复、非法代码、非整手、费用预留或源摘要失配在DLL加载前失败。

源snapshot.calendar可以包含未来日期或2019预热期。WT评价窗口采用原report完整portfolio.history，并加入评价首日前一根真实日线供原生初始化；输出records保持全部评价日。缺少评价日价格的输入明确失败，需要相同来源的完整OHLC父原件，不能静默裁去预热缺行或补造开高低收。

固定原DLL对已缓存cursor0重复读取空slice时会访问cursor-1，框架缺陷仍存在。本族按初始化完整行情注册→原bar闭合回调确认→消费闭合前缀的单一生命周期接入，上市前不重复读空slice，原引擎在首根真实bar闭合时推进游标后即可读取；不额外增加两bar开仓规则，不修改原生框架或补造历史。当前服务器137个原信号在各证券前两根期间均无信号的独立核查只说明样本分布，不构成策略准入规则。

## ONB-3 报告与原生事实

schema=`guanheng.original-native-replay-report.v1`。顶层保留session_id/input_sha256/configuration_sha256、独立策略与信号算法身份、policy、historical_model、reference_report_sha256/source_snapshot_sha256、原生五类basefiles摘要、完整native_outputs摘要、callback_counts和records。source_qualified/execution_qualified/point_in_time_qualified均false。

a2每条record增加 `cash_control`：`available_cash_cny` 为当日实际现金减1元的本批预算；`reserved_buy_cost_cny` 为新提交全部买入成本上界；`orders` 记录证券、BUY/SELL、增减份数、原生限价和买入成本上界。它描述本批计划和成本界，不是独立资金账本。validator核版本与MODEL、非负实际现金、预算/本金界、方向/增减份数/完整目标/当日限价一致性；旧a1条目保持原字段集合。真实pending来自原生，等待时不新增条件。

每条record记录trading_date/minute/status/reason、原信号、submit_vector/readback、cash_deficit和同owner无setter区间的capture。capture保存原生positions/prices/targets/funds；basis.nav_cny为100万元加WT原生净损益，cash_cny为该NAV减全部原生实际持仓估值；pending目标单独表达。收益和费用取WT事实，适配层不从ORR净值重构WT收益。

唯一validator返回 `ValidatedOriginalNativeReport`（record_count/to_dict），`project_record`提供record/evaluation_summary/report_schema。只读App薄适配此族；CNY绩效与ORR归一化对照单列。

## ONB-4 原宿主与发行

保留nsh-run-v1父请求/结果、nsh-wt-install-v1完整site/native库存、原同次总截止、OS根锁、预绑定Job、管道排空及正常退出。安装绑定明确选择本独立报告族；runner只按已准入固定schema分发。完成证明继续由父owner的nbw-completed-archive-v1发布，子结果和CSV单独存在不授完成资格。

新会话仍使用 `guanheng_wt_runtime.backtest_cli`，独立准备CLI由 `original_native_cli` 负责从两份冻结输入构造会话；不接受动态策略模块或联网loader。现有retained族保持原分发与模型。

## ONB-5 验证

先跑普通安装CLI→Host→runner→固定WtBtPorter/CtaMocker的人工OHLC例，区分D收盘、D+1开盘与D+1收盘，独立核整手、费用、SELL-only保持和最终pending。再跑冻结原报告的真实日线全样本，逐项比较原信号和源OHLC，验完整原生CSV及父完成证明。边界覆盖来源篡改、空/缺日线、代码/日期/信号异常、跳空现金缺口、未知pending、取消/预算和原retained族分发。离线测试、实际DLL、普通安装、归档读取和现场发布分别登记。

## 七只 ETF 回调收复确认

`resonance-kc50-pullback-confirm@0.3.0a1` 使用 510300、510050、512100、515080、588000、159780 和 159352。份额特征使用上一交易日，A500 用自身行情与份额运行沪深 300 规则。科创 50 只在原策略空仓且两个宽基的半衰期五日日收益指数平均均为负时，把牛市回调底转为观察。固定首次信号日高低点，后续收盘高于高点确认，低于低点取消，其他原买点优先并清空观察。

组合在新买入时分配资金，成长或红利状态对相应在仓及买入标的按 3 比 2 分配，其余等权。成长相对红利、沪深 300 和中证 1000 的半衰期五日日收益指数平均同正为成长、同负为红利。ATR14 以预热期 ATR/价格中位数校准 10% 参考距离，用已成交持仓的最高收盘与当日 ATR 更新保护线，保护线只升，触发全退。正式研究窗口沿原回测暖机，策略启用日为 2021-11-01。

日线、基准及份额、成交额、融资沿 WT 已发布日更快照读取。上一交易日缺份额时保留空值，原分支按原有缺失规则处理。回放冻结同一批行情及特征，原生 WT 负责撮合、费用和资金。观衡登记沿策略目录。

## ONB-6 次交易日收盘回放候选

状态为隔离原生验证通过，正式会话、报告和发布接线待实现。原版闭合日信号保留分析证券及原因。执行证券用明确的一对一映射，589680 的候选执行证券为 589000。执行定价、持仓、数量和费用均读取执行证券。采用原生 BacktestPorter 分钟主时钟与 CtaMocker 条件撮合，日期按信号的下一个有效交易日。初始资金和费用覆盖及未成交的退出边界由回放模型显式声明。

隔离模型使用当日 14:57 闭合分钟近似限价参考。撮合仅消费原始 15:00 单一价格、正成交量 bar，14:58 至 14:59 的源记录保留在冻结原件，不作为集合竞价成交事件。主时钟可来自独立实际行情，且该证券可声明为只读；即使个别执行证券缺失收盘撮合行情，仍核当日最终时钟。对缺失、非单一价格或无已记录正量的收盘事件给出具体原因。估值与是否具备撮合事件分开，收盘估值可读取同证券的已闭合日线。原生 CtaMocker 每次 calculate 前清除未触发条件，回放适配在同一窗口只保留已冻结目标和限价，已成交或原生 pending 保持原身份，收盘后不延续。实际柜台仍按原委托核回报。

验收核原生 trades.csv 的时间、执行证券、数量、限价和费用，并逐日复算现金和份额。现有隔离模型不模拟集合竞价队列和参与率。正式发布需独立模型身份、可重放冻结输入、父完成证明及只读报告消费验证。[实证记录](../evidence/2026-11-07-etf-minute-and-shared-account-checks.md#次交易日尾盘-wt-隔离回放)

## ONB-7 次交易日开盘正式回测

`0.2.0a1` 沿原生回测 CLI、宿主与父完成证明发布，沿用同一原版策略 ID。信号读取原报告，589680 分析证券映射至实际执行证券 588230。冻结会话在原输入字段之外增加 `opening_bars`（执行代码、日期、上海闭合分钟、原始量价）、`execution_map`（分析至执行代码）及 `fee_mode`（区分按份费表和双边万三）。`history` 此版按执行代码保存原价日线。完整原报告 SHA 保持不变，评价日期可选原报告连续子区间，包含一根预热日作为上一信号日。

评价日 09:31 读取实际闭合报价，在有效份额和实际现金内提交 WT 原生限价目标。未成交卖出不增加买入预算。09:32 原始分钟用于撮合；缺该证券的撮合行情时不提交该证券的当日委托。目标意图可在后续开盘再次评估。收盘时以执行证券原始价格记录持仓、资金与累计费用。日记录区分原信号日、开盘委托预算快照和收盘绩效快照。按份买入 0.01 元/份、卖出 0.02 元/份；对照为双边成交额 0.03%，两者均绑定各自原生费表且无最低收费。样本以 100 万元、空仓起步。

隔离脚本直接调用原生撮合时不会产生父完成证明。正式入口使用当前 D 盘归档根与报告名称，正常完成后自动发布；观衡按策略 ID 与版本读取，并从同一原件展示费用、收益、持仓及成交。旧版本保留各自的报告口径。分钟 OHLC 撮合不包含真实盘口排队和成交容量，历史信号首次可知及实际柜台费率待核实。
