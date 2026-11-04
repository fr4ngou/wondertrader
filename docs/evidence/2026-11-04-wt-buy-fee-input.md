# WT策略买入组费用输入

类型：费用事实装配的根因与隔离主链证据。日期：2026-11-04。状态：自有模块及独立核验完成，角色构建及线上买入分别登记。

真实冻结策略输入明确100万元预算，买入费用及来源均为None。原Configured每次沿用该输入，原NSQ卖出完成后连续返回waiting_fee。原制品已包含并按SHA准入WT费用模板，缺口位于自有输入装配层。

实现要求见[R34](../specs/native-realtime-strategy.md#nrt-r34-显式当前策略总资本与只读资金接线)。Configured持有原已核费用原件，为每次实际目标按原NSQ份数、完整券商数量及同次原价装配正买差费用。可选纯basis装配接缝让旧经济代际推进和新代际交接使用各自目标；原NSQ、WT费用账、现金约束及金融状态格式保持。

固定证据位于`E:/workspace/wondertrader-qa/daily-mainline-20261103-001/fee-input-candidate001`。CAS绑定两份代码及规格；TEST-RESULT沿实际Configured callback→1.1.2核→advance_retained→NSQ，以冻结真实输入、原费用模板及隔离WT/券商上下文复现原selling→waiting_fee，验证候选selling→buying。该组新增买差333700份，按原0.01元/份模型预留3337元，NAV仍100万元。低账户可用、高冻结、未知NAP、未决订单与T+1不足继续等待；原waiting_fee状态可恢复，已冻结买入组保持原费用和数量。

Root独立核对费用、单位、向量顺序及原状态事实来源，重新执行原条件、资金约束、恢复与代际交接；`E:/workspace/wondertrader-qa/daily-mainline-20261103-001/FEE-INPUT-REVIEW.json`为complete/findings=0。候选只修改自有execution_configured与retained_evaluation；框架、NSQ及金融文件未改。

配置模型预留与券商实际佣金分别归属。本证据真实下单0次，当前行情和实际买入成交继续沿线上主链验真。
