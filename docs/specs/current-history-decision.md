# 当前可见历史版本的策略预热与决策

类型：跨模块功能规格。状态：accepted / pure-kernel-in-progress。前缀CHD。依据模块C完整M1及真实批次127。C拥有历史版本领域值和唯一算法；B拥有原生实时桥、数量状态、委托/撤单及恢复；A拥有来源批次和实际接收事实。

策略范围已锁定唯一正式在用resonance-regime-v1@1.1.2，沿[RR112](retained-resonance.md)。CurrentHistoryView/evaluate_current_view先由最新V1纯包公开消费完整RetainedInput，包含analysis和原生cycles；configured候选退出当前实时输入。原初通用接口设想由本段及RR112专属合同细化；实际前复权来源、原生实时/数量/恢复和完整M1另验。

## CHD-R1 事实与使用时点

收到过去完整日线后，策略用当前可见版本重建记忆，供之后的实时决策使用。127实际实收为2026-10-29T01:23:25.163+08:00，历史首次发布时间与修订未知，行market_available_at=None保持；过去逐时点无前视资格独立核实。

新增不可变CurrentHistoryView，精确字段为schema=`guanheng.current-history-view.v1`、dataset_sha256（等于FrozenHistory.source_revision）、received_at（实际实收，带时区）、history_basis=`current-visible-reconstruction`、historical_first_available=`unknown`、revision_history=`unknown`、source_amount_unit=`unknown`、amount_usage=`unused`。解析和typed消费均重验枚举/SHA/时间并隔离原对象。首版明确消费127的历史可知时间未知profile，已有严格已知时间入口保持。

每行闭合时间≤received_at≤decision_cutoff。未来行、未来实收、批次失配、空/重复/乱序/不完整证券及预热不足拒绝；禁止先裁掉未来行或伪填过去available_at。辅助事实沿原逐帧因果校验，缺失继续灰灯。

## CHD-R2 单一计算与输出

公开evaluate_current_view(config, history, view, decision_cutoff, *, budget)复用原features/signals/allocation与预算/合作截止；完整当前版本重建记忆和末个经济目标。view、批次及决策cutoff参与输入摘要，输出明确current_view和当前决策时间；历史信号/分配日期标为算法重建日期，保持最后分配身份，禁止给旧目标换今日信号日期。

旧evaluate_history保持严格可知，HEM evaluate_historical_model保持历史日末假设。CHD声明当前可见版本重建，历史逐时点资格未证实；账户授权、真实价格、预算、T+1/可卖和未决命令沿原owner。

amount保留原数值/unknown单位。当前features/signals/allocation未使用amount，其仅经过有限非负校验；公开amount_usage=unused。volume的lot100→share由来源适配显式完成。B使用当次真实quote的CNY/份价格和原NSQ换数量，历史amount与当前交易价格分别准入。

## CHD-R3 B接缝与恢复

B使用显式独立实时profile及固定输入文件/SHA，把config/history/current_view交C公开计算入口；原策略映射、数量政策、费用依据和基础资料/执行文件身份检查保持。该profile采用当前决策专属准入，解除以严格StrategyBacktestSession DTO作为唯一实时输入验证器的耦合；HEM historical_model在实时profile前置拒绝。

source profile、view/input/config/code/policy身份纳入原state_identity，原NSQ/CTA消费同一经济目标。恢复沿原持久代际/序列，改批次或view须经原代际交接；历史日期相同不足以认领旧状态。真实报价/自然分钟、历史预热、策略重建状态与券商事实分别记录来源。C提供普通安装core公开函数、版本/manifest和真实127样本，B交付自有实时桥和二进制，A唯一Git集成。

## CHD-R4 验收

先用真实127的9证券401日形成8角色历史，在实际实收后的cutoff计算完整末结果/目标；与同历史/配置HEM数学部分一致，来源资格、使用时点和摘要分别断言。再接B真实快照/分钟、原CTA、隔离券商委托撤单及恢复、实际App页面，完成M1主链。

回归覆盖实收前决策、未闭合/未来行、unknown冒充CNY、typed突变/原引用、身份变化、旧严格/HEM保持、未来辅助、目标日期保持；修改amount保留算法目标，来源/完整输入摘要改变。实际普通安装和加载归属、原native有界关闭、独立双轴审查、精确SHA交付。真实交易、生产切换和WT核心行为保持既有授权边界。


## CHD-current 独立当前辅助视图

当前视图沿[SDO-R3-current](strategy-data-and-observability.md#sdo-r3-current-当前决策辅助视图)实现：RetainedInput的可选current_auxiliary与FrozenHistory分开，省略时规范输入及原求值保持。AWP只交付冻结事实；唯一V1核核验实际行情basis、依赖日期及known_by<=真实decision_cutoff，历史模型与命名研究模型继续隔离。历史完整逐bar验证保留，当前终端投影复用原信号机的state/start_index接缝，原价格、公式、阈值、实际周期、年龄和退出规则保持。

当前结果独立报告实际消费值、来源身份、行情基准及真实decision_at；原diagnostics-v1继续表达历史帧覆盖，当前消费不冒充已富集历史。完整结果沿Runtime既有core_result公开，读取层不重算。相同事实和真实行情的后继轮询不构成新业务数据修订，Runtime继续由原NSQ目标投影维持同权重的经济代际。
