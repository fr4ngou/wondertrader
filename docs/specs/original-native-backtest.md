# 原版信号的 WT 标准回测

类型：功能规格。状态：开发中，现场采用和自然运行另验。范围：冻结原版351f9d5 stable信号，沿WT原生撮合与原受管回测宿主运行；原组合ORR参考保留独立。

## ONB-1 身份与模型

策略ID为 `resonance-original-wt-351f9d5-stable`，版本 `0.1.0a1`，显示名“原版信号·WT标准回测”。信号算法ID继续为 `resonance-original-351f9d5-stable`。原BUY/SELL来自完整冻结ORR报告的 `trades_by_code`，本模块不重写信号公式。

本次WT接入使用模型A：保留冻结日线真实OHLC形状，D日闭合信号在WT `on_calculate` 提交目标，下一交易日首个原生模拟tick成交，通常为下一日开盘价。WT日线的模拟tick时间戳可能仍为15:00，不能据此描述为真实盘中或收盘成交。原CtaMocker负责pending、T+1、成交、费用和损益；适配层不自建撮合，不改变原框架，不将日线改成close-only。

初始资本固定人民币100万元；ETF数量为整数份且按100份向下取整。新BUY对当时原生已成交在仓集合与本次新买集合等权（同时去除SELL）；只有SELL时释放对应仓位，其余份数保持。目标用D日可见价格/NAV和显式费用预留计算，不读取D+1价格。末日未到下一事件的信号保留为未执行目标。

原生当日买入的T+1冻结份额以total-valid核定。SELL先减少可卖份数，冻结余额保留原意图至后继可卖；新BUY等权若需减持冻结份额，完整等权提交延后，在合法D时点用当时价格/NAV重新规划。意图元数据不代表成交或独立现金账本。信号日期/原因仍逐字保留，延后提交以status/reason说明。

WT CtaMocker资金接口报告损益，不实施证券现金账户购买力限制。适配层在D日按NAV减预留规划，记录真实已成交份数推算现金；下一日跳空或费用仍可能导致现金缺口，必须在报告逐日显式披露，后续新BUY暂停。该约束与原组合次日收盘、浮点份额、零费率的模型分别比较。

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

每条record记录trading_date/minute/status/reason、原信号、submit_vector/readback、cash_deficit和同owner无setter区间的capture。capture保存原生positions/prices/targets/funds；basis.nav_cny为100万元加WT原生净损益，cash_cny为该NAV减全部原生实际持仓估值；pending目标单独表达。收益和费用取WT事实，适配层不从ORR净值重构WT收益。

唯一validator返回 `ValidatedOriginalNativeReport`（record_count/to_dict），`project_record`提供record/evaluation_summary/report_schema。只读App薄适配此族；CNY绩效与ORR归一化对照单列。

## ONB-4 原宿主与发行

保留nsh-run-v1父请求/结果、nsh-wt-install-v1完整site/native库存、原同次总截止、OS根锁、预绑定Job、管道排空及正常退出。安装绑定明确选择本独立报告族；runner只按已准入固定schema分发。完成证明继续由父owner的nbw-completed-archive-v1发布，子结果和CSV单独存在不授完成资格。

新会话仍使用 `guanheng_wt_runtime.backtest_cli`，独立准备CLI由 `original_native_cli` 负责从两份冻结输入构造会话；不接受动态策略模块或联网loader。现有retained族保持原分发与模型。

## ONB-5 验证

先跑普通安装CLI→Host→runner→固定WtBtPorter/CtaMocker的人工OHLC例，区分D收盘、D+1开盘与D+1收盘，独立核整手、费用、SELL-only保持和最终pending。再跑冻结原报告的真实日线全样本，逐项比较原信号和源OHLC，验完整原生CSV及父完成证明。边界覆盖来源篡改、空/缺日线、代码/日期/信号异常、跳空现金缺口、未知pending、取消/预算和原retained族分发。离线测试、实际DLL、普通安装、归档读取和现场发布分别登记。
