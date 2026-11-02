# 观衡量化系统移植入口

- [2026-11-02主路径接续](mainpath-closeout-20261102.md)：异常恢复、WT日线持续尾部与指数补齐、独立观衡接收；当前模块所有权和实际验收。

- [观衡验收修复并行计划](observer-acceptance-parallel.md)：八图功能缺口、开发者1/2/杂役完整模块、公共接缝及单一集成；[UI调研与截图审阅](observer-ui-design-research.md)记录组件依据和三套视觉方向。

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

- [原生账户四查询的WT只读发布接线](native-account-publication-proposal.md)：NAP-v1组件/descriptor/locator与原帧包装合同已冻结；无App生产者、两轮/失败恢复和原C投影已实跑，A公共装配与C页面按同合同接线。

- [模块A行情/历史/通信交付](module-a-delivery.md)：完整模块验收、统一SDK/原生数据候选、真实来源及剩余范围。

- [模块C交付与续接](module-c-delivery.md)：观衡业务与操作平台完整goal、验收、文件归属、A/B接口需求和当前步骤。
- [模块C完整目标审计](module-c-completion-audit.md)：COP逐项证据范围、剩余差额及当前实际阻塞修正。
- [模块B交付与续接](module-b-delivery.md)：账户交易/原生策略完整验收、产品宿主、恢复提案及M1九证券日线数据需求。
- [共振1.1.2现有持仓接管候选](retained-strategy-takeover-proposal.md)：唯一在用规则、券商数量/成本与周期初值、原WT首次加载及恢复接缝；proposed，待主链实施。

- [三会话并行交付与实盘就绪计划](parallel-system-delivery.md)：三个完整模块的负责人、文件边界、验收、集成、会话目标和实盘验真阶段。

- [QMT历史批量导入方案](qmt-bulk-history-export-plan.md)：显式只读bulk、原值分片、完整身份/恢复/容量及全量验证；proposed，普通接口默认保持。

本目录保存观衡量化系统接入 WonderTrader C++ 原生底座的设计与仓库准备资料。

- [同账户多策略的持仓、订单与统一执行](multi-strategy-account-ownership.md)：原生目标汇总、券商查询权威、自有固定集合装配及人工混用/恢复边界；proposed，交易对话负责。

- [唯一移植方案](guanheng-qmt-tdx.md)：保留观衡系统，增加 QMT/TDX Parser、Trader 和原生历史加载。
- [完整接入验收地图](acceptance-map.md)：完整目标、当前证明范围与剩余交付。
- 仓库准备基线（外部历史/待归仓路径：`repository-baseline.json`）：fork、上游、固定提交、分支与源码检出范围。

QMT/TDX 原生接入、受管运行时、历史存储和观衡兼容门面已进入实现与隔离验收，当前进度见[接入验证记录](../evidence/2026-10-21-guanheng-native-adapters.md)。原生构建、测试与开发包的已验基础见[构建规格](../specs/native-build-automation.md)和[工具链证据](../evidence/2026-10-21-native-build-automation.md)。真实端点、服务切换、账户接入与交易资格分别验收。wtpy 是单独保留的可选参考仓库，运行底座采用原生接口。

- [Reader空数据计数修正](native-reader-empty-count-proposal.md)：已获批准的一文件空返回分支；实际验收见[NRC证据](../evidence/2026-10-21-native-reader-empty-count.md)，其他核心差异分别管理。
- [原生行情接入方案收敛](native-market-integration-plan.md)：公开Reader/Factory与原CTA分钟链、来源边界、剩余验证及旧候选退出。
- [本次原生接入实现规格](../specs/guanheng-native-adapters.md)。
- [统一决策清单](decisions.md)：待定项及可继续路径。
- [CORE-004审批记录](current-approval.md)：历史最小范围、替代方式与证据；现阶段待定项以[决策清单](decisions.md)和[NOW](../roadmap/NOW.md)为准。
- [既有框架差异审阅](core-change-review.md)：CORE-001–006 必要性、替代方式、风险与待批准范围；源码继续冻结。
- [HTTP阶段历史规格](../specs/qmt-http-market.md)：终端内HTTP已退役；当前接线沿[QMT共享内存规格](../specs/qmt-shm-wt-binding.md)，外部Host的签名HTTP属于该新链。
- [历史生命周期与独立消费者](../specs/history-lifecycle-and-service-adapters.md)：长历史分窗、临时任务恢复、SDK 与原 Operations 接线；[隔离验收](../evidence/2026-10-21-history-lifecycle.md)。
- [日历 owner 接口与缺项](calendar-owner-boundary.md)：现有日级资产、分钟会话/历史停牌证据边界与可复用入口。
- [观衡业务逐服务适配地图](business-adaptation-map.md)：真实依赖、契约及服务切换退出条件。
- [观衡完整功能迁移清单](business-feature-inventory.md)：全部页面、业务模块、定时职责、441个HTTP声明及首批独立Console/分钟图的最小源码输入。
- [原生运行器边界复核](native-runner-boundary.md)：启动、分钟调度与退出的源码依据，以及插件和完整宿主的资格差异。
- [原CTA受管退出方案](native-cta-stop-proposal.md)：已批准的生命周期范围及限定验收；真实执行配置的完整停止另验。
- [QMT HTTP 账户与执行恢复边界](qmt-http-execution-boundary.md)：现场只读证据、账户字段和恢复证明的实际缺项。
- [Tushare 能力与权限](tushare-source-capabilities.md)：官方事实、单位及实测资格边界。

- [股票商品引用修改方案](native-stock-metadata-ownership-proposal.md)：用户已批准三个框架文件，显式修正版保留默认原行为；限定实施、正常恢复和制品资格见[交付证据](../evidence/2026-10-30-stock-reference-delivery.md)。

- [QMT后继安装交接与WT协议核对](qmt-successor-source-handoff.md)：最新只读安装、50项操作与现有bound协议差异、旧解释器依赖及接续验证顺序。

- [QMT账户绝对持仓研究](qmt-account-snapshot-research.md)：原生刷新语义、执行状态新鲜度与待验证的最小框架扩展；尚未采纳或实施。

- [券商订单同步到WT原表](native-order-query-sync-proposal.md)：用户已批准两个TraderAdapter文件；query_first沿券商完整查询更新原订单表，默认原路径保持，限定主链见[执行证据](../evidence/2026-10-27-qmt-native-order-query-sync.md)。

- [原生Writer关闭与映射同步方案](native-writer-lifecycle-proposal.md)：用户已批准开发及隔离验收，修正版由配置选择；限定实施及现场阶段见[后继证据](../evidence/2026-10-28-writer-lifecycle-afternoon.md)，当前整包采集资格沿最新收据。

- [干净停止状态保存接口候选](native-clean-state-flush-proposal.md)：必要性待原生停止/恢复主链验证，当前审批请求已撤回；核心保持只读，先复用已有保存和加载。

- [原组合仓位内存所有权候选](native-position-ownership-proposal.md)：候选保持冻结；按用户要求停止WT框架并发问题研究，四核心文件的新改动尚未批准，当前开发集中主路径。

- [未知提交的券商证据处置与原状态恢复](unknown-broker-evidence-recovery-proposal.md)：proposed，依据实际SDK产生成交后异常的反馈环，复用原Journal、关闭重建和WT状态；尚未新增解除实现或改变当前准入。
