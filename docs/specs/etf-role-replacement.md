# Fresh 1.2.1执行组合与永久源码闭包

类型：功能与源码交付最终规格。状态：accepted。适用范围：共振1.2.1、V1 a9、QNA resonance121.1、WT fresh.1.cash.4；运行切换继续由Root负责。

- FRC-R1：科创综指角色signal/execution同时采用589680.SH，其自身原价、前复权分析价、因子和历史进入原纯核。其余七证券和原1.1.2实际周期、初始库存、止损、预热与分配数学保持。策略版本真实表达1.2.1；V1发行0.1.0a9。柜台受理和持续运行资格由实际owner记录。
- FRC-R2：按用户最新授权，以当前真实券商持仓重新建立总预算100万元的新基准与新financial-state，含当前持仓原价市值及其余分配现金。当前真实持仓创建initial_inventory周期，新NSQ从实际持仓和新鲜价格规划。旧financial-state、资金/持仓/成交文件、原BASELINE及回测归档保持原身份。旧金额追溯、旧计划换代和旧逻辑目标清零ABI退出本轮。
- FRC-R3：券商现金原点cash_anchor归运行资金owner；实际策略现金=原点分配现金+当前账户available/frozen合计−原点账户现金。NAV=实际策略现金+实际持仓原价市值；native_pnl_cny=NAV−新基准。原CTA理论fund_pnl只以native_theoretical_pnl_cny审计。真实资金范围和可花现金沿既有账户约束，不产生第二套资金账或新收益记录。
- FRC-R4：WT原初始/状态preview及commit统一发布definition，身份来自准入配置、版本来自实际kernel、证券来自实际execution。初始等待期目标权重/收益保持缺失。独立观衡读取真实活动定义，已保存报告保留其原身份和证券；合同继续由[活动与归档规格](observer-strategy-facts.md)负责。
- FRC-R5：最终cash.4固定43模块，使用既有source_closures版本化目录、固定Git基线与必要overlay重建。27个base模块从原固定提交读取，16份差异快照进入版本化overlay；相对cash.3仅四份已审模块更新，其余39原字节保持。canonical历史account/CLI/completion/runtime及initial_inventory说明差异继续按固定角色原件封存，后继通用能力保持。完整清单声明每模块来源/摘要、元数据和参考制品身份；拒绝混入旧retired_plan或zero-target迁移实现。
- FRC-R6：普通V1 a9和QNA角色入口/pyproject进入精确源码CAS。QNA历史角色与通用源码存在差异的原件放版本化overlay，映射逐成员声明；后继通用导入算法继续保留。构建仅取永久源码，不取安装目录、历史wheel、账户文件或临时build目录作为产品输入。
- FRC-R7：版本化build.py使用显式SHA绑定的Flit 3.12后端、新work/output、固定Git来源、原Core公开重导出/RECORD实现；重建三包全部产品载荷及METADATA与最终cash.4、原V1 a9、QNA定版wheel相同，确定性Runtime wheel整体SHA保持。清单及可变源码前后核验；错误摘要/路径/模块集合或非空输出明确拒绝。字段含义和缺失语义写入源码注释或清单合同说明。
- FRC-R8：交付包含完整CAS、单命令构建、实际三包重建结果和根因回归、独立源码审查。App已采用的规格索引以当前after字节为基线，保留其活动/归档规格入口。共享源码、已运行实例、正式端口和来源保持只读；正式运行验真沿Root记录，源码闭包验证不推定行情或柜台资格。

- FRC-R9：Native初始估值完成后私有保存不可变basis，仅含原实际市值、CTA审计PnL、原估值/持仓/价格时点、来源与对应初始sequence。首帧合格账户暂缺时capital保持未知；原账户线程晚到合格NAP后沿既有observe_broker_capital与publication_lock/publish_locked恢复该初始capital，保留原时点和sequence。已有capital继续原refresh_account_constraint；缺估值/账户、绑定或原点失配、较新sequence时保持未知。账户线程不持有Native句柄、不调setter、不写金融状态。cash.3仅更新execution_configured/strategy_capital及版本，其余41模块、V1a9/QNA、预算、NSQ与页面schema保持，cash.2历史闭包原字节保留。

- FRC-R10：cash.4只合并已独审的execution_configured、execution_facts、service_control、execution_recovery四模块。报价转换统一消费实际WT品种档位，仅处理有界double尾差，按[报价金额规格](native-quote-money-boundary.md)保留原价审计及严格现金比较；每代持续日线Reader缓存由原服务owner新建，业务比较仅按[服务控制规格](wt-service-control.md)忽略经严格验证的cache_root定位，其余来源/账户/金融配置继续原比较。V1/QNA、依赖、预算与NSQ保持；cash.3历史闭包原字节保留。

本规格收敛此前未采用的ETF候选：新基准/新周期/新NSQ为唯一运行路径；原retired-plan与零目标ABI私有材料仅作已撤回历史。原Native takeover schema保留协议身份，strategy_version为真实1.2.1；自有CtaProcess解析沿已合入实现，WT框架保持原职责。

## 1.2.2 同账科创角色换代（当前增量）

2026-11-05用户授权选择相近可交易基金；正式角色改为博时科创100 ETF（588030.SH）。本节适用于已运行的financial-state-008原账，原1.2.1首次建立基准的FRC-R2继续作为其历史首次启动定义。本次保留原100万基准、capital_baseline、cash_anchor、全部金融文件、原订单成交及另七证券实际周期和止损记忆。V1包为0.1.0a10，策略/算法身份真实表达1.2.2；原Core与NSQ版本保持。

- FRC-R11：唯一显式接缝为顶层`role_replacement={schema:"guanheng.zero-position-role-replacement.v1",file:原execution.json绝对路径,sha256:原配置SHA256}`。引用原1.2.1实际配置并核输入原件SHA；只允许589680.SH→588030.SH、相同策略/账户/资金/费用/预算、同一金融根。新输入使用新基金真实raw/front/factor和完整自身历史，不复制改名旧ETF价格。另七周期及初始库存声明逐项相同，新旧基金在原基准输入均为flat/0。信号、执行、实际周期、成本和历史使用同一新证券。
- FRC-R12：首次换代必须沿原正常关闭证据、原金融文件摘要和原Python绑定交接，原自有挂单先由既有收束流程撤清并查询P/A。故障、回档和未就绪中断材料不能借角色替换接缝改变金融模型。新代逐单恢复与未知提交责任继续原流程；旧589680实际P必须为0，两基金无未成交委托。588030若已有本轮WT模拟验证买入，必须以原flat基准、完整券商D和当前P证明真实开仓来源与净量；原成交时间、订单/成交ID保持，现金变化沿原cash_anchor进入。
- FRC-R13：原WT在on_init会将所有旧理论目标重新交执行器。沿其原生`code_filters`为`SSE.ETF.589680`设置`action=ignore`，在恢复目标前生效；只阻止退役证券目标进入执行，不清改原理论账，不生成假平仓。发行app内`retired-role-filter.json`正文仅`{"code_filters":{"SSE.ETF.589680":{"action":"ignore"}}}`；`environment.filters`指定该相对路径，文件必须进入原execution-install与Python artifact闭包。默认无role_replacement配置继续原路径。
- FRC-R14：原quantity状态先按前代原输入SHA、原8证券、原算法/配置和代码身份验证完整规范编码。随后整体退役旧冻结NSQ计划，七证券周期/退出记忆及sequence保留，原账文件由原owner正常加载；本代以券商P、真实原价及原资金基准重新调用公共NSQ。退役基金周期不移植到新基金。后续同1.2.2正常重启按新输入/身份验证，不再次把新基金当作零库存。
- FRC-R15：发布仍由Root负责，先同批构建自有CtaProcess、Runtime新模块与V1 a10，准备真实588030基础合约、前复权历史/因子和新QNA窗口。`data.store.symbols`仅替换一条物理映射；原资金发布账户及其余七证券保持。换代允许变更的源定位限input引用、daily自有数据/因子/publication、market_window路径、报价服务定位及Trader同账户运输引用；TTL、单位、风险规则和账户约束保持。新Source的完整D须包含本轮候选100股实际成交。

- FRC-R16：恢复seed保留原cycles_captured_at/cycles_valid_until、周期来源和真实新市场known_at/received_at。明确resume_clean/resume_reconciled初始化只验证公开配置规则并按原canonical编码计算config_id/algorithm_id，用于核验恢复状态；不把旧周期与新市场拼成一次可执行决策，不修改周期期限或伪造重查。首次自然回调先沿原新鲜P/D装配当前周期、实际接收时间和有效期，再完整调用evaluate_retained及原Reader一致性检查，之后才可推进NSQ/setter。record_clean首次启动继续完整seed决策与原时钟检查。
- FRC-R17：Native角色输入读取沿原16MiB文件界限，完整RuntimeInput的raw/analysis数组使用同一JSON解析器并显式按正文长度设置节点预算，每个节点至少占一个正文字符，因此上界有限且覆盖公开输入容量。普通配置/收据继续默认32768节点；UTF-8、重复键、16层深度和有限数值检查保持。真实3,563,160字节输入含151,326节点的原红/新绿及默认路径保持验证，见`tests/integration/qmt_cta_product/role_input_json_budget.py`。
- FRC-R18：WT原账可继续保留退役理论仓位及其订阅。自有ManagedStrategy的tick缓存和ContextAccess理论目标枚举只投影声明reads；声明外数据不进入缓存、读取返回或新执行集合，声明内的价格/时间/有限数/容量/重复项检查保持。物理券商P/O账户范围与执行权限继续原校验。原code_filter只负责执行过滤，两项投影属于原账恢复的读取边界。已有ready/newKV后发生本代故障，沿该真实前代配置、python-binding、failure/close-prepared及当前金融文件摘要准备resume_reconciled，使用既有fault_reconciled入口；不回档旧KV，不伪造initialization_abort或owner-loss。

验收主链：读取原buying状态并验证原身份→正常关闭/撤清→同根恢复实际P→退役旧NSQ→新基金真实开启恢复→新1.2.2目标进入原NSQ→原WT标准执行入口。定向回归见`tests/integration/wt_runtime/test_role_replacement.py`；原业务身份与周期来源回归继续复用。真实新基金历史、Native编译及正式部署结果由本轮实际发行证据分别证明。

## 调用链与所有者

角色配置→真实八证券raw/front/factor→QNA同基准窗口→MarketWindowFile→RetainedRuntimeInput与initial_inventory→原实际周期纯核→原NSQ→原CTA/查询执行器。账户现金/实际数量归券商，资金原点/周期/目标/委托归运行owner；观衡只读投影，关闭观衡后WT仍由其独立owner运行。

## 验收与源码重建

复用已封存纯核/新八证券真实窗口、初始资金/晚到账户、报价金额和原服务缓存后继主链及对应Root独审；cash.4只核固定四模块组合、39模块保护及完整制品闭合，沿原构建入口重建43模块与元数据，不另扩测试/审查。伴随V1/QNA保持原件，Native与现场采用由Root负责。固定版本的源码、清单字段和构建命令见[最终版本化闭包](../../apps/wt_runtime/source_closures/0.1.0a12+integrated.2.market.35.3.service.9.resonance121.fresh.1.cash.4/README.md)。
