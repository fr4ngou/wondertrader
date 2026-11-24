# 当前事实

类型：当前状态快照。所有者角色：相应模块与任务维护者。观衡市场观察最近核对日期：2026-11-25；交易结论沿对应主题证据日期。

本页按主题维护最近可核实结论及缺口。运行信息来自下列各主题的发布和后验真记录，金融R24核验为隔离运行。目标与约束见 [TARGET](TARGET.md)，活动任务及续接见 [NOW](NOW.md)。更新方式沿[当前快照维护](../development/documentation.md#当前快照维护)。

## 最近可核实结论

| 主题 | 最近记录及适用范围 | 依据 |
|---|---|---|
| 市场观察历史与原图对齐 | 154正式18143已验收破净合图、板块直接切换/多选、PB两按钮及市值/GDP合图；破净与沪深PB近三年726日完整读回。原观察根和38路采集接续154，新增破净派生；换手展示撤下，历史保留。全A日频PB及2026-10-16以前全A市值历史待补，下一自然窗口待验。此前科创承接、小盘弹性及IPO供给回购三图保持撤下、停止推导，原数据保留。 | [154发布](../releases/2026-11-25-observer154-market-observation.md)、[IPO撤图](../releases/2026-11-22-observer148-remove-ipo-board.md)、[前两图撤下](../releases/2026-11-22-observer147-remove-unverified-boards.md) |
| 系统职责 | WT 独立拥有 QMT 通信、采集/历史、策略和交易；观衡独立部署、只读消费。 | [架构](../architecture/overview.md)、[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md) |
| 交易恢复核查 | 11月24日费用暂记已采用；后继读取发行在INIT将收盘可卖差异升级为异常，交易WT当前faulted，两策略尚未恢复。原账九表摘要及零执行证明保持。启动与当前交易资格分离、同权限初始化失败接续正在验证，完整恢复和自然计算待验。 | [当前发行及初始化失败](../releases/2026-11-24-wt-current-fees.md#后继读取发行失败与初始化修复) |
| 数据恢复与诊断 | unified60于19:14采用，归档失败沿原回执保留来源安全诊断；九ETF原价及前复权18项重新回读11月23日通过，原价发布保持；原价7955证券、916547根，588030为769根。11月11–13日九ETF正式回读各720根，中证500新增13日240根，其他原值保持；来源失败诊断已自然验真。辅助事实仍标明11月20日，今日早段分钟待次日来源开放。QMT历史61笔核实旧方向差异及原17笔入账一致；用户确认没有结算单，18笔最终费用继续待确认。 | [数据及历史核对后继](../incidents/2026-11-20-trading-recovery.md#11月23日原价与前复权后继发布历史成交核对) |
| 观衡交付 | App154已正式采用原18143，Web及观察更新器ready、稳定入口与实际静态资源已核；原读取配置和个人观察目录接续。152冻结目标展示与153费用能力沿原发布验收保留，本轮实际验收市场观察。交易WT运行资格沿交易主题单独核实。 | [154发布](../releases/2026-11-25-observer154-market-observation.md)、[152展示](../releases/2026-11-24-observer152-published-target-view.md)、[153费用](../releases/2026-11-24-wt-current-fees.md) |
| 市场广度 | 正式一年窗口内沪深五项与沪深北广度、RANA、MSI、推力各有 242 个有效值。沪深北 TRIN 有 240 个有效值，T2108 保留 47 日。 | [备用来源补采与验真](../evidence/2026-11-08-observation-breadth-alternative-sources.md) |
| 原模拟账户运行 | 11 月 12 日 18:51 沿原账恢复，七角色及执行器就绪。18:51:43、18:52:16 两轮账户快照可读。发布时策略等待新分析窗口，自然调度和券商回报待后续交易窗口验证。 | [WT 发布](../releases/2026-11-12-wt-strategy-return.md)、[独立采集与分析发布](../releases/2026-11-12-wt-data-retry.md) |
| 目标记录 | 1160 行原始设置归约为 42 条首次/变化记录；目标、持仓和成交分别归属。原目标、历史权重、算法版本及原因缺字段时保持未知。 | [目标规格](../specs/strategy-target-history.md)、[后验真](../evidence/2026-11-07-native-target-cash-gapplan-postflight.md) |
| 原版回测 | 原版 a2 完成 1415 日、407 笔实际 WT 回测及独立复算，负现金日为 0；原 a1 及失败证据保留。历史 PIT、OHLC 撮合和未成交排队限制沿原模型；回测报告与正式运行策略采用分别核实。 | [发布记录](../releases/2026-11-07-native-target-cash-gapplan-live.md)、[回测规格](../specs/original-native-backtest.md) |
| 归档存储 | 受控STORAGE为active，D盘9run/252文件；E原件保留，前后SHA及九报告投影一致，ACL沿原基线。C候选从未采用，清理自动审查拒绝后已停。 | [运行手册](../runbooks/native-backtest.md#正式归档的唯一位置)、[后继发布](../releases/2026-11-07-observer125-data-update-and-d-archive.md) |
| 日更恢复 | Data28/Source19沿同一任务越过历史五字段计划校验并实际进入辅助事实回读；四个只读服务自然自启通过。完整辅助事实尚待确认。 | [日更发布](../releases/2026-11-07-data28-natural-recovery.md) |
| 数据日期 | 11月6日自然价格CURRENT d22074fd…已发布；已核历史原价单位在合并中被旧档覆盖，前复权保留资格。 | [日更发布](../releases/2026-11-07-data28-natural-recovery.md) |
| 来源缺口 | 已发布辅助事实仍有2只深市份额、融资和官方成交额各1项缺口；全目录5758事实/412缺口。自然后继以最新日更发布为准。 | [前次事实发布](../releases/2026-11-07-observer125-data-update-and-d-archive.md)、[日更发布](../releases/2026-11-07-data28-natural-recovery.md) |
| 金融运行 | R25已普通安装并通过原生与隔离归属验证，实际模拟未启用。未知费用可继续已定卖出，接收WT风控目标，双策略不自动划转。替代ETF、收盘限价与匹配WT回测继续核实。 | [R25证据](../evidence/2026-11-07-shared-account-r25-execution.md) |
| 研究资格 | 原版、因子及金融条件研究已有资料和限定验证；原作者收益、完整 PIT、真实挖掘效果与正式生产采用分别核实。 | [研究入口](../research/resonance-research-guide.md)、[原版规格](../specs/original-resonance-reference.md) |
| 开发规则 | 根因回归、控制过度设计、语义复用及随完整切片验证已写入规范；规则工具化程度按各入口的实际实现登记。 | [规范整合证据](../evidence/2026-11-07-development-principles.md) |
| AI 知识治理 | AKN 方案已设计；当前快照治理切片已采用，结果见本轮证据。本地 CI 已执行文档检查；任务选择、项目 skill 及新会话行为实验仍待实施。 | [AKN](../specs/agent-project-knowledge.md)、[本轮证据](../evidence/2026-11-07-roadmap-snapshots.md) |

## 已确认参数与待核实范围

- 分析窗口 600 秒和每笔数量 10000 份已有[窗口采用](../releases/2026-11-06-market-window-age.md)与[数量采用](../releases/2026-11-06-stock-order-lots.md)原件。它们证明当时采用与验证，现场配置变化仍沿实际输入核实。
- 正式策略目标沿[当前目标](TARGET.md)的 1.2.2 后继范围；原版 a1/a2 属于独立历史回测身份。生产运行采用与原版回测结果分别登记。
- 文档完整性问题已按[后继修复](../evidence/2026-11-07-documentation-health.md#后继修复与合入核对)关闭；原统计与失败日志保留其当时范围。

## 历史与追溯

[迁移前完整 CURRENT](CURRENT.history-20261107.md) 按原字节保留；其中“当前”“在线”和授权均对应当时任务与输入。旧 App121/Data23 及 11 月 4 日 ready 记录保留原观察，当前摘要使用现存 11 月 7 日后继依据。

原文 SHA-256：`2f81ecb75ee7667950a25310e3de3c5e203b2c40c798b848b0a0ab1e5d8e3910`。迁移完整性及主题核对见[本轮证据](../evidence/2026-11-07-roadmap-snapshots.md)。

[主干此前对应记录](CURRENT-history-20261105-before-runtime14.md)保留该阶段原身份，当前结论沿本页及后继证据核实。
