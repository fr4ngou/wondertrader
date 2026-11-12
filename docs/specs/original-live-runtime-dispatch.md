# 原版线上固定profile与后台信号

类型：接口规格。状态：implemented / candidate；未普通安装或金融采用。所属要求为[OLS](original-live-strategy.md)，Native归属沿[NAH](native-strategy-attribution-hooks.md)，实际账户分配沿[ASA](account-strategy-allocation.md)。

## ORD-1 入口与职责

隔离`strategy_runner/strategy_porter`继续只承担冻结WT回测。线上沿`execution_process`的固定Python包绑定与`execution_configured.main`装配，固定接受旧`guanheng.retained-cta.v1`单profile，或该旧profile与`guanheng.original-live-cta.v1`双profile。固定分发不接受任意模块/loader。旧单profile的Python包集合保持原值；双profile只增加固定原版纯包及MarketClient。原版线上模型版本固定`0.2.0a1`，不改变现有a1/a2回测身份。旧单策略调用默认行为与原输入/恢复/资金展示保持。

旧策略和原版各有WT ctx；新原版ctx初始理论证券份额0，显式新增基准1000000 CNY。原版算法身份仍为351f9d5 stable，线上执行模型独立版本。原历史model_state只用于原路由预热及展示，激活模式固定`signals-from-activation`：首次仅消费最新闭合日实际BUY/SELL，随后消费新决策日信号；不把历史模型held转换为账户持仓或自动买入。新BUY时按新实际组合持仓与新BUY集合等权规划完整九证券目标，实际资金/归属/可卖/费用/未知订单全部由ASA与WT原owner管理。

## ORD-2 后台准备与回调

后台单一ThreadOwner拥有已安装MarketClient，读取Data已发布CURRENT的日期/完整身份，再按同一SDK快照读取原价、前复权与辅助事实，复用`collect_current_facts`和`build_current_signal`。不触发Source/HPR、不运行在Native回调内。CURRENT/descriptor只读，配置原件按SHA绑定；沿同快照官方日历原件SHA与SDK `exchange_calendar.official_calendar(cal,check=同原D)`验证完整`verified_open_dates_sha256`、覆盖和开市行后确定下一交易日，未知保持未知。禁止自行复制weekday/closed_dates替代原owner准入。源读写者、快照ID与时间仍归原数据owner。

每轮工作分别具有原发布/事实查询、纯计算、计算后发布重核三个有界阶段；所有临时目录显式E/D。只在整轮成功、同发布身份后替换小型不可变内存投影，保存signal/facts/snapshot身份及原qualified状态；失败保留最后成功值并标明本轮不可用，不能继续授旧结果交易资格。关闭先停止新轮，再沿原ThreadOwner取得join证明；未退出返回pending并保留原owner，不新起替代线程。

Native回调只读已准备内存、原ctx报价及ASA策略观察。原桥on_tick只缓存quote，set_targets仅允许SCHEDULE；本接缝承诺下一交易日首次具备完整条件的分钟调度，通常09:31，成交仍归执行器与市场。price_policy明确选择`executor-price`或`signal-close-cap`，后者只把原决策日原价收盘上界交ASA，不将CTA条件价伪称券商限价。用户最终执行模型采用前不改生产配置。

## ORD-3 归属与元数据

双profile必须显式提供Root AttributionCoordinator；`strategy_observation(strategy_id,deadline)`取得StrategyView、原账户revision/source/trading_day与精确分配opening_cycles。旧Retained实际P和开仓周期在双profile时改用该观察，退出整账户P与submission_revision区间推断。原账户观察只承担来源/新鲜度核对；理论WT仓位与ASA实际份额分别发布。

在完整set_targets前调用`prepare_intent(strategy_id,epoch,source_sha256,known_at,buy_price_caps,common_prices,deadline)`；kind1才持久完整目标。CommonPrice使用本轮真实读取quote的观察时点，摘要同时绑定原action_date/time、价格、新鲜度和捕获时点；不改写原tick首次发布时间。缺少双方共同接受价格时对应证券暂缓内部转移，不扩大成全证券交易门槛。新模块不复制ASA分配、FIFO、储存或委托队列。双profile的Original配置必填`shared_account:{path,sha256}`，引用原`guanheng.shared-account-allocation.v1`受控材料。main仅调用惰性factory并将bridge交CtaRuntime；ASA首次初始化沿原Native账户租约内INIT/SCHEDULE借用，后台和main均不读取或写入ASA。

各具有执行权限的ctx在首次合法SCHEDULE即宣布原完整保持目标：优先原WT枚举目标，其次ASA自有份额；新Original首次为9个0。元数据标明初始化/保持来源，不构造BUY信号。局部市场输入等待仍完成此声明，使原双intent合并核验可就绪；后续等待保留原目标/未完成意图及price cap。只读绑定保留计算/发布及原Native target_submission_disabled权限约束，不调用保持或其他setter；此时整个共享运行无交易写权限。旧单profile完全不进入该可选声明。原100份完整目标准入保持；无法表示的碎份保持目标明确失败并保留原责任，不能擅自四舍五入改变旧仓位。

`signal_qualified`保留为纯模块全输入诊断汇总，不直接用作全证券交易门槛。后台另生成逐证券`route_qualification`：核该证券及路由引用证券的ETF原价/分析单位、当前特征、完整基准日期、未解决折算与原报告可重建性；159352明确引用510300。000300以index-point核必要价格维度。份额/融资/成交额缺失或unknown继续由纯模块转换为None，原stable路由guards决定是否产信号；MA250/270行数只作诊断。每证券合格空信号或BUY/SELL分别登记消费日和SHA，不合格证券不消耗其日期，也不阻挡其他证券。本候选回放的冻结旧档9证券价格/成交量单位仍unknown，逐证券保持data-unqualified；本候选不宣称已具备线上交易资格。

## ORD-4 恢复和验证

原版策略KV只保存意图/逐证券已消费信号日和SHA/目标计划/原信号known_at/原价上界及源身份，不保存账户余额或成交账本。初次new模式严核空KV/零ctx持仓及ASA空仓100万元来源，resume沿原KV/原ASA责任；跨安装`resume_reconciled`只复用原`load_transition/state_origin_configuration`核前代代码身份，模型参数（除new/resume）相等后接受前代KV身份并改写当前身份；每证券当日合格信号首次消费后更晚修订只展示差异，不重复消费旧日。尚未合格的证券可在同决策日完成证据后首次消费。未完成意图跨会话沿原来源和cap继续，不借新日结果替换旧买价上界。原未知group/command由原owner继续核查。

先验已发布事实→后台纯信号→固定profile→Native回调→ASA元数据→完整九目标的主链，再验无数据/失效身份/非交易日/重复信号/关闭未确认与旧profile兼容。恢复/ServiceController采用由原owner统一；本模块测试不启停生产、不执行真实委托。


## ORD-5 候选验证边界

已验证源码候选实际ThreadOwner→固定351隔离计算→冻结实际已发布事实回放，并取得join证明；查询Source、HTTP和委托均0。完整结果沿最终当前信号实现，原signals/model_state与此前实际数据结果逐值一致，新增单位诊断不冒充新市场事实。

真实Native Factory/CtaStraContext验证旧ABI1八证券与新ABI2九证券在同一Runtime的独立ctx/完整setter。该主链账户/信号/报价为显式合成夹具，未启动执行器或券商。真实ASA SQLite联动另验证Original等待信号仍宣布完整零目标，旧ctx实际SELL意图可通过原合并/authorize，原库存和新增资金归属继续分离。普通安装、自然交易时段与账户采用由后续OLS发布验收承担。


## ORD-6 可选单位证据

`signal_source`旧白名单字段保持；唯一可选扩展为`unit_evidence:{path,sha256}`，允许省略或null。descriptor严格仅两字段，path为D/E绝对路径，SHA为64位小写十六进制。后台首次轮询前沿原query_seconds绝对截止读取最多1MiB、核固定原件SHA，再调用普通SDK `guanheng_market_client.source_units.parse_unit_evidence(raw)`取得唯一UnitEvidence DTO；该DTO传给`collect_current_facts(unit_evidence=...)`，来源资格逐SDK响应provenance由原reader和SDK resolver核同。默认省略仍不提升unknown。

Native回调不读取证据、不解析DTO；不复制ETF/指数官方映射、不另读官方文档或运行包装源码。当前worker只在整个生命周期初始化时解析一次，证据文件发生后继变化须用新固定descriptor重启/过渡，不能悄然刷新原SHA。坏SHA/坏协议使后台明确不可用，保留最后成功投影的展示身份。

## ORD-7 七只 ETF 收复确认线上 profile

`guanheng.original-live-cta.v1` 的显式 `resonance-kc50-pullback-confirm@0.3.0a1` 走七证券独立 ctx 和原 ASA 执行路径。后台沿同一已发布快照计算七只信号、风格、原价 ATR14 及校准倍数。原版继续按原配置选择。读回价单位按同一 SDK 响应的来源区段核对。拆分复核按事件前一交易日和事件日的双价单位分别核对，保留未证实日期。

新实例从空仓启动，只有实际归属持仓才生成 ATR 保护线。保护线和高点沿实际开仓周期保存在原 ctx 意图 KV，决策日更新一次。错过调度时从已核闭合日序列补算，保留首次跌破日。单位证据不足或开仓周期未知时保留原线和归属，原路由合格卖点仍独立消费。旧档的单位资格不足时暂缓新增风险。新买点触发时按已发布决策日风格调整目标，沿 ASA 及原生执行核资金和权限。无写权限时只发布模拟目标与保护状态，不提交 Native 目标。
