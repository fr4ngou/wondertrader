# 上游共振原版独立还原

类型：功能规格。状态：accepted / pending-verification（离线实现及算法对照通过，完整历史数据待验）。前缀 ORR。范围：用户2026-11-06授权核对并还原 OrangesHuang/Resonance，现有策略保持独立。

## ORR-01 固定原版与隔离

原版指所给仓库 main 的固定提交 `351f9d58152e10efd2447c997b8ee4db66b5ac6a`，算法版本采用其 `stable` 路由；最早提交、beta、band分别是其他身份。独立研究策略标识为 `resonance-original-351f9d5-stable`。计算实现位于 `apps/guanheng/strategy_original/`，提供离线冻结与回放，输出保持 `execution_qualified=false`；后继只读页面接入沿ORR-06。现用策略、配置、默认选择、服务及账户保持各自身份。

直接校验并运行用户给定上游的纯计算源码，避免再次翻译复杂状态机造成漂移。来源文件逐一绑定SHA-256，在独立临时目录复制后由隔离子进程装载；完整原件保留本地研究目录，发行包保存自有接缝和来源清单。上游未声明许可证，当前范围为本地核对与运行，尚未形成上游源码再发行制品。

## ORR-02 数据冻结与准入

支持显式原SQLite路径只读事务导出 `etf_daily/market_turnover/margin_trading/trade_calendar` 的业务字段，或读取同schema冻结JSON。实际发布时刻、复权来源和版本若原库缺失，输出记录未知；数据库更新时间不能代替历史首次可知时间。输入包含来源、数据性质和单位声明，数值有限、日期严格升序且唯一，证券使用原六位代码；589680与589000保持不同证券身份。

输入上限32MiB、60000条记录、17只证券；计算由一次有界子进程完成，超时终止并返回失败。输入按完整历史预热，回测日期裁剪用于最终信号/估值；任何数据缺失、日期缺口、预热不足和未覆盖派生核对在报告明示。禁止把缺份额填零或以其他ETF替代。

## ORR-03 原算法与组合

复用上游 `router.compute_trades(version='stable')`、情绪 `enrich_turnover/percentile_series`、五灯 `compute_resonance` 和 `simulator.simulate`。默认九标的沿上游 `portfolio/api.py::ALL_CODES`，588200引用588000、159352引用510300；选择其他原监控证券需要显式代码。五灯与交易状态机分别输出。

原组合按下一交易日收盘成交、新BUY触发全部在仓等权满仓、SELL释放现金且其余仓位保持，原浮点份额和零费用模型保持。原策略统计中的信号收盘收益与组合成交收益分别标识。现有WT回测入口使用不同策略/数量/成交合同；本次离线原版结果与其报告族保持分离。若继续做可交易改进，WT-S01/S05/S06和WT-B01/B02负责调度、状态及撮合，不增加第二套实盘执行或账户账本。

## ORR-04 算法与数据检查

逐字段检查派生价格位置、量比/量概率、份额概率及重算后的方向/综合分数；只在已具备所需历史与输入时比较。原seed与后继recalc语义差异分别报告，不自动覆盖存量事实。上游自身缺陷和回填修订按原行为保存并披露。算法一致性、数据完整性、严格逐时点资格和收益有效性各自说明。

主路径先跑冻结输入→原路由→原组合→独立JSON报告，再覆盖人工可算的边界、原入口差分、源码篡改、未来/重复/错序/非有限输入、缺参考证券、空结果、失败和超时。原始测试、合成数据和真实来源分别记录；没有原作者完整数据库时，原作者收益复现保留为待验。

## ORR-05 QMT/WT真实数据研究输入

用户2026-11-06追加授权核查并获取实际来源后重跑。行情优先WT已发布日线及既有QMT历史读取/准备通道；必要补齐只涉及来源缓存与独立研究目录，活动策略、服务配置和发布CURRENT保持。保留原请求身份、实际回读与原件内容摘要；缓存准备调用返回和实际数据覆盖分别证明。

原价、供应商前复权和复权事件分别保留；指标按交易日期精确匹配ETF与沪深300参考。来源price/volume/amount单位、供应商分析基准日或历史首次可知仍未知时，在研究输入source显式登记假设及未合格状态，目标协议units不单独提升来源资格。已取得的价格预热日期上的份额参与后继第一条派生日的份额计算；未知日期不能补零、前填或用当前总份额代替。

历史ETF份额与市场融资/成交额属于补充事实，现有WT价格bar及股票daily_facts不包含这些业务字段。本次以独立研究适配器连接已核公开来源；生产WT事实接口和持续采集发布属于后继范围。官方股票成交额、原版使用的双指数amount代理各有完整独立身份；缺失官方日期不会由代理隐式补齐。缺份额的九证券实验和份额完整的七证券子集分别记录，证券集合改变不当作同条件绩效比较。

完整回放保持原组合初始现金及持仓推进；2026年或6—11月结果从同次全程净值按前一日权益截取，不重新启动模型/组合。评价起点前若已有原模型持仓而组合从现金开始，报告明确其数量及原API语义。结果沿原次日收盘、零费用模型，继续保持研究诊断及逐时点未合格。

<a id="orr-06-观衡只读目录与报告导入"></a>

## ORR-06 观衡公开范围（非WT对照已撤回）

用户2026-11-06后继指令撤回非WT“原组合对照”的策略和回测展示，观衡仅公开 `resonance-original-wt-351f9d5-stable@0.1.0a1` 原版WT条目及原有WT正式策略。App动态目录继续采用WT发布的身份和版本，未知保持None；撤回的 `resonance-original-351f9d5-stable` 不作为公开策略重新登记。该字符串仍可作为WT内部 `signal_algorithm_id`，不能据算法字段生成第二个策略。

App移除ORR完成证明的读取、summary、绩效/曲线/成交/信号分页与比较投影，移除ORR导入CLI和专属页面/客户端合同。正式归档若仍含 `orr-completed-archive-v1`，两个目录接口均略过它，直接详情请求返回410（该非WT报告族已退出），不返回其原件或金融投影。原仅供ORR的 `/archive/{run_id}/signals` 路由退出，未知内容沿404。WT原版及既有WT报告的nsh/nbw完成证明、CNY模型、原生CSV和严格读取保持。

归档根可读而所选run目录缺失时，详情、绩效、记录、曲线、按日摘要、成交和比较入口统一返回404，说明报告不存在或已移出。根目录缺失/不可读、现存run内receipt或原件缺失/损坏继续返回503，固定receipt摘要冲突保持409。410仅由现存的明确退役报告族证明触发；移走全部原件后按缺失目录404处理，不按run名称推定退役。

WT信号计算所需的固定上游参考算法、原冻结输入、内部 `reference_report` 和摘要绑定保持；原组合结果仅作Git忽略研究目录中的内部核对材料，不进入App角色或公开目录。此前ORR-06公开导入/展示合同已由本要求替代，已发行阶段证据保留当时身份，不改写旧验收结论。

正式WT模型和原生边界沿[ONB](original-native-backtest.md)。移除回归需证明：目录及直接HTTP不枚举/响应ORR金融数据，已撤导入模块不存在，WT内部参考仍可加载，旧7份WT报告与新WT原版的目录、绩效、曲线及原生成交保持。

## 导航

运行入口和数据格式见[独立包说明](../../apps/guanheng/strategy_original/README.md)，研究记录沿[研究指引](../research/resonance-research-guide.md)，适用[验证规范](../development/verification.md)。具体来源摘录、冻结输入和诊断结果保存在Git忽略的 `research/resonance-20261105/`。

## ORR-07 当前日事实与原信号

`build_current_signal(source, facts, *, work_directory, timeout_seconds=120)` 是纯事实计算接缝：不请求行情、不发布数据、不接账户、不产生订单。原包旧入口保持兼容。上游源码仍由用户显式提供，固定351f9d5；现有manifest保持原身份，新增feature_source_manifest仅登记shares_adjust/recalc纯函数来源。执行在独立子进程，全部临时输入/源码/输出归显式D/E绝对work_directory，退出回收，禁止使用默认TEMP。

输入schema `guanheng.original-current-facts.v1`：

|字段|定义|
|---|---|
|profile|`causal-current`为当前日；`historical-final-oracle`仅作历史最终版差分，资格始终未提升|
|decision_date / decision_at|交易日YYYY-MM-DD；决策截止为含时区UTC时刻。未来日期及截止后收到/发布的事实排除|
|feature_stage|seed/recalc明确采用原方向口径，必填|
|snapshot_id / description|发布快照64hex及来源中文/英文描述，原事实身份由调用者沿WT reader核验|
|codes / calendar|原九ETF的显式子集；升序唯一交易日历，跨证券引用需实际输入|
|analysis / raw|六位code→行情包；包内bars(date/open/high/low/close/volume)、source_sha256、received_at、available_at(null允许)、price_unit（ETF为CNY/share，指数为index-point；unknown保留未知）、volume_unit、price_basis、factor_version。analysis为同reference前复权，raw为原价；缺失保留诊断|
|shares|行date/code/value/unit/share、source_sha256/received_at/available_at；value份数，null是未知；转换亿份|
|turnover / margin|行date/value/unit(CNY或unknown)/source_sha256/received_at/available_at；成交额另有kind=official/proxy，整次输入保持单一kind；融资仅供应商原报表语义，转换亿元。未知单位仅诊断，不混用official/proxy|

所有日期及行顺序校验在过滤前执行；缺失值保留，有限非负数才准入，行情OHLC为正且高低包络正确。来源摘要必须64hex；它绑定调用者提供的原件，当前接缝不重新读取外部ContentStore。输入沿原32MiB/60000行容量，有界子进程超时回收。输出schema `guanheng.original-current-signal.v1`，绑定完整facts_sha256、prepared_sha256和manifest摘要；`prepared_snapshot`为原DAILY_FIELDS，`reference_report`复用固定原路由；`signals_today`只取decision_date原信号，`model_state`记录最后BUY/SELL形成的模型仓位，实际账户持仓另属执行owner。模型持仓不是每日BUY。

特征复用原analyze_single_etf，基准固定000300并按ETF日期精确对齐；前19条行情保留供量价及份额预热。份额按日历相邻日求变动，缺失不前填。当前日折算仅查事件日和前交易日raw/front因子；两侧ETF价格均须已声明CNY/share，同维度才允许相除并调用原find_factor_jump/detect_share_adjust。原价未知或错误维度保持诊断，候选不确认折算、暂缺份额评分，signal_qualified=false。历史对照profile可复现研究重建±30自然日窗口，并可沿原研究显式保留未知单位数值假设；factor_pair.historical_unit_assumption与事件basis=historical-unit-assumption逐项标识，source.split_unit_assumptions列出证券，事件不作为已核官方折算，信号资格始终false。未来事件窗口保持future-relative-event性质。recalc仅提取固定原源码_t5_return/_idx_t5_return两纯函数，复用原DP/CP/level，不导入scheduler/store。

输出`diagnostics`披露排除事实、缺基准/份额/原价、窗口和折算事件；`signal_qualified`要求来源单位/同复权reference/当前数据齐备、真实收到时刻与所需辅助事实齐备，仍独立于执行资格。任何候选结果始终`execution_qualified=false/point_in_time_qualified=false`。上游最短长度guard及历史修订可能改变旧信号；本接口按本次已知前缀计算并绑定输入，不把历史最终报告信号直接作为未来实时信号，也不设统一270日交易门槛。调度/部署策略是否接受缺辅助事实由后继owner显式决定。
