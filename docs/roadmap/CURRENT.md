# 当前事实

类型：当前状态快照。所有者角色：相应模块与任务维护者。记录核对日期：2026-11-07。

本页按主题维护最近可核实结论及缺口。运行信息来自下列发布和后验真记录；本轮执行文档治理，实时进程、账户与数据状态尚未现场复核。目标与约束见 [TARGET](TARGET.md)，活动任务及续接见 [NOW](NOW.md)。更新方式沿[当前快照维护](../development/documentation.md#当前快照维护)。

## 最近可核实结论

| 主题 | 最近记录及适用范围 | 依据 |
|---|---|---|
| 系统职责 | WT 独立拥有 QMT 通信、采集/历史、策略和交易；观衡独立部署、只读消费。 | [架构](../architecture/overview.md)、[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md) |
| 观衡交付 | 11 月 7 日记录的 App123 / SDK20 已普通安装，列表按需读取、目标记录及旧/新报告页面已实际验真。首次完整报告冷读取仍需数秒。 | [发布记录](../releases/2026-11-07-native-target-cash-gapplan-live.md)、[后验真](../evidence/2026-11-07-native-target-cash-gapplan-postflight.md) |
| 目标记录 | 1160 行原始设置归约为 42 条首次/变化记录；目标、持仓和成交分别归属。原目标、历史权重、算法版本及原因缺字段时保持未知。 | [目标规格](../specs/strategy-target-history.md)、[后验真](../evidence/2026-11-07-native-target-cash-gapplan-postflight.md) |
| 原版回测 | 原版 a2 完成 1415 日、407 笔实际 WT 回测及独立复算，负现金日为 0；原 a1 及失败证据保留。历史 PIT、OHLC 撮合和未成交排队限制沿原模型；回测报告与正式运行策略采用分别核实。 | [发布记录](../releases/2026-11-07-native-target-cash-gapplan-live.md)、[回测规格](../specs/original-native-backtest.md) |
| 日更恢复 | Data25 已采用；原计划及 43 项 HPR 准备结果恢复已验。完整新 MSF 发布仍受原批读服务未运行阻塞，准备返回与完整覆盖分别验收。 | [发布记录](../releases/2026-11-07-native-target-cash-gapplan-live.md)、[后验真](../evidence/2026-11-07-native-target-cash-gapplan-postflight.md) |
| 数据日期 | 上述记录中的数据发布 CURRENT 指针，辅助事实日期仍为 11 月 5 日；价格层含 11 月 6 日。此日期属于数据版本，文档核对日期单独记录。 | [日线合同](../specs/qmt-source-daily-history.md)、[后验真](../evidence/2026-11-07-native-target-cash-gapplan-postflight.md) |
| 来源缺口 | 九 ETF 的 11 月 6 日价格已读、七只沪市份额已取得；两只深市份额、11 月 6 日融资、官方成交额与代理单位仍有明确缺口。历史前缀、日历完整性和活动服务采用按数据 owner 分别验证。 | [发布记录](../releases/2026-11-07-native-target-cash-gapplan-live.md)、[历史覆盖原记录](CURRENT.history-20261107.md) |
| 金融运行 | 最近后验真确认对应金融 Runtime/execution 已退出，页面未在线标记与当时状态一致，历史目标可读。本轮实时状态待核实。 | [后验真](../evidence/2026-11-07-native-target-cash-gapplan-postflight.md) |
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
