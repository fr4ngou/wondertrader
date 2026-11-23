# 共振原版的 WT 线上运行

类型：功能规格。状态：accepted / in-progress，运行采用尚待验证。范围：用户确认的现有模拟账户中，原版独立新增人民币100万元，与既有策略并行；原持仓继续归既有策略。原版信号与[原生回测](original-native-backtest.md)分开登记运行资格。

## OLS-1 算法与数据

原版固定提交为351f9d58152e10efd2447c997b8ee4db66b5ac6a，stable路由。交易池为510300、510050、510500、512100、515080、588000、589680、159780、159352。代码身份由QMT证券资料核对，原仓库历史简称不改变代码映射。

线上按当时已收到的WT已发布事实构建截至决策日的原算法输入，并计算当前信号。冻结历史报告只用于核验。原特征字段、seed/recalc差异、单位、复权、份额折算和因果截止沿[原版数据接缝](original-resonance-reference.md)。来源缺失保留缺失；市场代理与官方成交额分别标识。各路由窗口不足的行为沿原代码，诊断窗口不另设为业务门槛。

原版运行工作目录显式指定E或D盘，临时输入、源码副本及输出沿同一工作目录管理；C盘保留系统用途。正式WT回测继续沿[统一归档入口](../runbooks/native-backtest.md#正式归档的唯一位置)。

`original_market_facts.collect_current_facts`接已安装MarketClient，显式读取观察日、历史起点、交易池、seed/recalc及official/proxy模型，返回`CollectedOriginalFacts(facts, diagnostics)`。所有查询固定同一snapshot_id；历史按最多2000自然日分段，补充事实沿原游标完整读取，收尾核发布身份。函数只读已发布内容，不调用Source或HPR。整体截止由调用者提供，单次HTTP截止由原client承担；换代、缺组或不推进游标保留具体失败。

六位代码及ISO日期薄转换保留原价、前复权和每份/指数点的区别。同一前复权参考才能构成分析输入，空历史窗口不能为后续非空窗口确定参考。旧CNY单价标签按明确ETF/指数身份规范化；混合已知与unknown单位时，整包降低为unknown并保存各段原标签，成交量跨段量纲不授连续资格。不同已知量纲或不同前复权参考拒绝组合，当前来源未明确的单位保持诊断用途。

## OLS-2 资金、持仓与运行归属

新策略独立资金基准为1000000 CNY，新策略初始证券份额为0。既有策略的原持仓、策略记忆、资金记录及已知/未知命令身份保留。账户当前可用资金用于核实分配能力，不能直接充当每个策略的资金基准。

采用同一个WT执行owner、同一账户通道及WT原生目标合并。WT各ctx拥有策略理论仓位和损益，券商账户owner拥有整账户实际资金、持仓、委托和成交。两个ctx的完整执行池分别绑定旧八证券及原版九证券；交集证券保持完整归属。

真实成交与实际份额按策略归属时，必须关联原目标意图、合并执行和原订单/命令身份。整账户同代码数量不能复制给每个策略，事后revision区间不能代替派发前的归属绑定。部分成交、对向目标、外部交易、未知命令及跨重启均保持同一规则。WT已有理论账与执行器继续承担其原职责，新增归属事实只补原路径没有提供的业务语义。

全账户信息和每策略实际份额/资金在发布值中分别标识。持仓归属尚未确认时保留具体原因和已知事实，恢复后继续原身份；不能以重置账本、重造成功回执或重新发送未知命令恢复。

## OLS-3 执行与现金约束

复用WT标准股票执行器及已有QMT交易通道，数量以ETF份数表达，按100份整手规划。买入须同时承担本金、手续费上界和已有未完成买入责任，未成交卖出款保持不可用；卖出沿实际可卖数量及原执行状态。

原版a2回测的CTA限价属于WT条件触发；线上实际委托价格由执行器生成。两层分别核验。共享证券的合并订单不能借新策略价格约束擅自改写旧策略的执行规则。线上现金控制需要在真实委托价格及责任链上成立，验证结论不能从回测条件价格推导。

BUY/SELL信号一致性、目标数量规则、实际执行时点和成交结果分别比较。若线上执行模型与a2不同，使用明确的新运行/回测版本记录；旧a1/a2报告、算法和模型身份保留。周末初始化成功只证明对应运行链，下一交易时段实际委托与成交另验。

开盘执行候选允许原版实例用 `execution_symbol_589680` 明确指定沪市 ETF 的 WT 三段代码。当前选择华泰柏瑞科创200 ETF（`SSE.ETF.588230`）。信号仍从 589680 的原始分析输入生成。替代标的使用自身的原始报价、实际持仓、目标数量、成交及费用。该配置采用 `executor-price` 和原 `next-session-first-schedule`。源信号价格仅参与原信号计算与追溯。执行标的需与其他八路证券互异，并通过 Native 合约、行情及账户归属核验。现有配置缺省时沿原交易池。

模拟启用前以同账户的柜台受理和买卖证据核准执行证券，并沿旧账续接核对持仓、未决委托和独立空仓子账。适配候选和实际启用分别登记。

策略未完成意图保存的`intent_prices`只包含该实例声明交易范围内的信号原价。指数及其他上下文价格继续留在原信号投影，不进入该实例的恢复cap集合。消费BUY/SELL和ATR退出共用这次范围投影，保存后可沿同一schema恢复，价格值、来源SHA、目标及知晓时间保持。已有越界恢复记录通过独立运维、原owner的状态CAS写入迁移；保留原件及前后摘要，不在业务读取处增加一次性兼容分支。

## OLS-4 恢复与服务组合

增加新策略沿明确的版本/配置过渡保存旧ctx资金、数量状态、目标、原文件及命令身份，只为新ID建立空仓和新增100万元基准。原单策略恢复默认保持兼容；双策略恢复核对两个ctx及共享执行责任。

独立日更数据组持续拥有批读Host及已发布WT数据。金融配置引用该数据服务，避免再次占用相同pair或端口。部署准备中的独立账户只读服务先正常停止并确认原Host/NAP回收，再由正式金融Runtime接管同一账户读取组件；金融CURRENT和观衡读取指针随真实采用更新。

## OLS-5 验收

先跑通已发布WT事实→原特征/当前信号→双ctx目标→同账户WT原净额执行→真实账户查询→观衡的完整调用链。独立核实九证券能力、旧持仓归旧、原版新增额度、部分成交/对向目标、资金费用、未知命令身份及正常停止/恢复。原策略单独运行行为与既有历史报告保持其原模型。

线上标记、每次目标变动、收益曲线、成交和持仓均绑定实际策略ID、版本、运行代及事实来源。单测、原生模拟、普通安装、模拟账户运行和自然交易时段分别留证。最终采用范围登记在发布记录，当前准备与未完成事项沿[NOW](../roadmap/NOW.md)核实。

## OLS-6 显式单账策略扩展材料

配置可选 `strategy_extension_origin` 固定为 `guanheng.strategy-extension-origin.v1`，字段 `file`、`sha256` 绑定扩展前单策略 `execution.json` 的原字节；`added_strategy` 的 `file`、`sha256` 绑定一个独立 JSON 策略行原件。所有文件在受控绝对路径下，沿原读取边界核 SHA 及大小。前代保留原 retained ctx，新增行由冻结配置声明实例 ID、策略版本及正的初始 CNY 金额，金额精确到分。策略工厂按已登记的 Original 模型版本选择实现。`state_mode=new` 和 `signals-from-activation` 继续表达空仓起跑。实例 ID 与原策略按 Windows 路径身份去重。冻结配置承担新增配置的授权边界，资金可用性及实际归属继续由 ASA 核验。

仅从比较副本移除经原件核同的新增行和扩展标记，再使用既有业务、角色、行情接入准入。其余账户、账根、原策略行、预算模型、合约和证券权限沿原约束；本扩展不增加价格、合约、Source绑定或过滤器豁免。后继双策略配置继续携带相同新增行；双策略不能沿此协议退回单策略或替换新增行。

首次 `resume_reconciled` 使用实际状态owner的原策略集合核金融文件；新增ctx的stradata/userdata必须尚不存在。全体原文件的字节SHA继续绑定在原transition中。原WT加载器为新增ctx建立空状态，不预生成金融JSON、不复制账户持仓。后继正常关闭证明包含两个ctx，`resume_clean` 对两个ctx沿原SHA逐件准入。原版有效初始化模式由已验恢复状态owner确定；配置中的固定首次new声明不使后继恢复重置意图或资金。原单策略无标记调用保持原语义。

## OLS-7 新策略依赖的显式续接

仅OLS-6标记可增加可选 `dependency_handoff:{file,sha256}`，固定 `guanheng.strategy-dependency-handoff.v1` 材料。省略保持原准入；显式材料只归一化本节列明的依赖差异。标记的原配置/新增策略行继续保持，后继可用新依赖材料绑定新安装；两代材料分别完整核验，不允许撤回已有依赖续接。

材料必填字段为：`schema`；`origin_configuration_sha256`（与OLS-6原配置SHA相同）；`previous_installation`、`current_installation`（两代实际 `execution-install.json` 的file/sha256）；`reader_additions`（九只版沿原两条映射；七只版仅159352.SZ→SZSE.ETF.159352）；`contract_addition`（159352的唯一完整Native合约行）；`contract_reference`（已准入数据owner证券资料catalog的file/sha256）；`source_extension`（未变更运输/绑定引用时为null）。完整安装文件的运行资格继续由原安装owner逐件校验；恢复比较核固定两代清单，并逐件核业务基础文件和过滤器的真实字节。

两代base_data相对映射必须相同。sessions、commodities、holidays、policy、fees及已有过滤器原件SHA相同；contracts所有旧交易所及全部旧行逐值相同，仅追加SZSE.159352。新合约的exchg/product/上市日/名称须与固定资料中的SZSE.159352 ETF一致，原品种/会话/费率沿原件。旧Reader8条顺序和值保留，仅在其后追加本profile指定映射，std_code/symbol均唯一。其它Reader字段、复权/单位/时区/日线/publication语义继续原比较约束。installation_root只在已核安装/业务文件的比较副本回投到原root，真实新安装身份不改写。

environment独立声明的fees与filters也分别按两代安装清单及实际文件字节核同；不能只比较相对文件名。未声明或空fees保持原默认路径，不擅自增设费表。既有模拟费率的业务身份保留，不将其标作真实券商费率。

新增策略行声明 `execution_symbol_589680` 时，以该行的沪市 ETF 代码替换新增 Reader 两行中的 589680 映射。信号侧继续由原数据服务读取 589680。若旧安装尚无该执行合约，续接只允许从同一份固定证券资料追加该合约和 159352。原合约已存在时按旧值保留。旧 Reader、旧策略、费表、过滤器及其它合约仍逐项核同。Runtime 与 Native 使用同一已冻结的新增策略行确定允许的变化。

`source_extension`存在时固定 `previous_version`、`current_version`、`adoption_receipt`、`plan`、`origin_deployment`、`origin_identity` 六个file/sha256及 `transport`。origin_deployment为实际原pair完整deployment原件；origin_identity由Source owner的 `reference_deployment_identity` 复用原完整decoder产生，只含schema、deployment_sha256、journal_path、trade_binding_sha256，不复制凭据。Runtime通过普通安装Source owner API从已核raw重新派生全部投影字段并逐值核同；Native从同raw的host核journal_path及trade_binding规范摘要，投影自报值不构成独立证明。Runtime此显式分支依赖普通Host0.1.0a24+deploymentidentity.1；默认无Source续接分支保持原行为。Runtime/Native核原部署字节摘要和此owner投影；plan.journal_path须等于实际原Host路径，备份Journal采用证明不能作为生产证明。plan的新identity/profile/保护摘要与采用版本核同，原权限算法仍归Source。

版本原件为原HostTradingJournal owner输出的连续完整canonical版本记录；current.parent_sha256、adoption.identity_sha256与实际原件SHA核同，version连续，plan_sha256一致且adopted为true。旧/新Native binding_sha256分别核同两版identity.trade_binding的原Source UTF8规范摘要；Native binding_id和全部账户/环境/profile/币种/预算/query字段保持。transport恰含base_url、binding_sha256、instance_id、key_id_env、hmac_secret_env五项当前冻结值，比较副本仅回投这五项。Source权限及规则扩展只由原Source owner和新当前绑定准入，Native不重写权限算法、不造Source成功事实；没有实际owner采用证明时只可验证合成候选。

plan保存原Source canonical字节，核其去除自身plan_sha256字段后的语义ID；不能改journal_path后保留旧ID或仅重算文件SHA。Native使用原canonical字节核ID，避免另一套浮点JSON格式器改变Source身份。origin_identity是受控Source owner输出，制作时调用原提取器并保留普通安装/原件身份，禁止手写投影代替该来源证明。

旧589680全局ignore过滤保持原文件SHA，本续接不授清仓、替代、内部分仓或移除过滤权限。实际旧文件/命令责任、现金基准和周期继续由原owner保存。正向验收包括合成实际Native准入及两代材料；负向验收覆盖旧业务/账户/profile/预算、旧合约/基础文件/过滤器变更、其它Reader扩展、坏SHA及缺Source采用证明。
