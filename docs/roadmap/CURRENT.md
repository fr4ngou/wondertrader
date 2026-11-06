# 当前事实

类型：当前状态快照。所有者角色：相应模块与任务维护者。记录核对日期：2026-11-07。

本页按主题维护最近可核实结论及缺口。运行信息来自下列发布和后验真记录；本轮实际核实App125、四角色数据组及日更发布，金融进程和账户未重新现场复核。目标与约束见 [TARGET](TARGET.md)，活动任务及续接见 [NOW](NOW.md)。更新方式沿[当前快照维护](../development/documentation.md#当前快照维护)。

## 最近可核实结论

| 主题 | 最近记录及适用范围 | 依据 |
|---|---|---|
| 系统职责 | WT 独立拥有 QMT 通信、采集/历史、策略和交易；观衡独立部署、只读消费。 | [架构](../architecture/overview.md)、[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md) |
| 观衡交付 | App125 / SDK20普通安装并在18143采用D归档；实际列表3704ms、完整报告2911ms（含350ms延迟），悬停HTTP为0、点击30ms。冷读取仍需数秒。 | [后继发布](../releases/2026-11-07-observer125-data-update-and-d-archive.md) |
| 目标记录 | 1160 行原始设置归约为 42 条首次/变化记录；目标、持仓和成交分别归属。原目标、历史权重、算法版本及原因缺字段时保持未知。 | [目标规格](../specs/strategy-target-history.md)、[后验真](../evidence/2026-11-07-native-target-cash-gapplan-postflight.md) |
| 原版回测 | 原版 a2 完成 1415 日、407 笔实际 WT 回测及独立复算，负现金日为 0；原 a1 及失败证据保留。历史 PIT、OHLC 撮合和未成交排队限制沿原模型；回测报告与正式运行策略采用分别核实。 | [发布记录](../releases/2026-11-07-native-target-cash-gapplan-live.md)、[回测规格](../specs/original-native-backtest.md) |
| 归档存储 | 受控STORAGE为active，D盘9run/252文件；E原件保留，前后SHA及九报告投影一致，ACL沿原基线。C候选从未采用，清理自动审查拒绝后已停。 | [运行手册](../runbooks/native-backtest.md#正式归档的唯一位置)、[后继发布](../releases/2026-11-07-observer125-data-update-and-d-archive.md) |
| 日更恢复 | Data25沿原任务恢复并发布，原43项身份保持；独立批读脱离金融生命周期，历史补齐/资料/批读/日线四角色数据组均ready。进程级定时拉起未授资格。 | [后继发布](../releases/2026-11-07-observer125-data-update-and-d-archive.md) |
| 数据日期 | 完整CURRENT日期为11月6日，full ID c2af732f…；九ETF原价/前复权18项均读至11月6日，补充事实绑定同一快照。 | [后继发布](../releases/2026-11-07-observer125-data-update-and-d-archive.md) |
| 来源缺口 | 11月6日总份额7事实/2深市缺口，融资与官方成交额各1缺口；QMT代理单位unknown。全目录5758事实/412缺口，supplement_complete=false；09:00修订未在本轮触发。 | [后继发布](../releases/2026-11-07-observer125-data-update-and-d-archive.md) |
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
