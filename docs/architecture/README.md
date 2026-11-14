# 架构与决策

- [ADR-0029 已结清阶段接纳最新经济目标](adr/0029-settled-stage-target-handoff.md)：阶段序号用于诊断，最新目标在实际结清后接续；旧报告保留原数学与失败。

- [ADR-0028 中断缓存查询的后继观察](adr/0028-interrupted-cache-read-observations.md)：显式日线只读观察与原失败责任分别保存，金融及下载语义保持。

- [ADR-0026 日线计划与HPR通信代分别恢复](adr/0026-daily-hpr-transport-generations.md)：原请求保持原代，新任务在同一业务身份下接续当前认证代。

- [ADR-0022 年末成员事实与财报更新分责](adr/0022-admitted-year-end-membership.md)：复用已准入成员及原件身份，财报刷新与成员修订分别拥有。

- [ADR-0016 WT运行与观衡只读服务独立部署](adr/0016-independent-wt-runtime-and-observer.md)：WT拥有通信、采集、策略与交易生命周期，观衡独立发布和只读消费。

- [ADR-0015 独立观察快照与目录所有权](adr/0015-observation-snapshot-owner.md)：本地不可变对象、事务CAS及跨进程采集lease。

- [ADR-0012 已完成回测归档](adr/0012-backtest-completed-archive.md)：复用原生运行目录与报告，以最终完成收据支持重启后的只读查询。

- [ADR-0011 未知委托定向取消](adr/0011-unknown-order-targeted-cancel.md)：保留原unknown，版本化分离故障，原通信事务收敛取消；源/Host先实施，完整恢复另验。

- [ADR-0010 当前订单查询的通信关联证明](adr/0010-order-query-communication-proof.md)：沿原通信记录恢复委托身份，查询来源与事件来源分别保留，实际撤单及完整恢复按相应验证确认。

- [ADR-0008 个人观察自选归属](adr/0008-personal-watchlist-ownership.md)：accepted，个人观察偏好与策略交易范围分别拥有，原生行情/策略职责保持。

- [ADR-0007 账户观察的进程内请求身份与重新读取](adr/0007-account-observation-read-state.md)：原ID仅活进程内核查；新轮新Adapter，账户展示不增加客户端恢复目录与累计配额。

- [ADR-0006 账户只读来源与原生查询职责](adr/0006-account-read-source-boundary.md)：原生四查询、运输身份与券商会话分别表达，字段映射和通信恢复各有唯一owner。

- [ADR-0005 显式只读能力与版本绑定](adr/0005-explicit-read-capabilities.md)：统一能力准入、明确profile升级、固定C++业务门面及原线程结果所有权。

- [系统架构](overview.md)：职责、执行链和事实边界。
- [原生能力目录](../development/wondertrader-capabilities.md)：数据、策略、执行、回测、运维与测试的支持范围和配置边界。
- [WonderTrader 原生框架与并发模型](wondertrader-framework.md)：宿主、引擎、上下文、插件、同步机制与生命周期。
- [领域用语](../../GLOSSARY.md)：账户事实、目标、基线、水位及两类未知。
- [ADR-0001 执行事实与运行投影所有权](adr/0001-execution-fact-ownership.md)：单一权威与连续消费边界。
- [ADR-0002 独立行情接口与业务发行](adr/0002-independent-market-interface.md)：公开服务版本、原生资源与独立业务发布。
- [ADR-0003 原生运行状态与独有业务事实](adr/0003-native-runtime-and-business-state.md)：复用原生存储和运行职责，按用户功能确定剩余持久化。
- [部署与运行身份](deployment.md)：原生包、容器组件、配置及持久状态的目标组织。
- [ADR 模板](adr/TEMPLATE.md)：长期架构决策的记录格式。

新增 ADR 使用递增编号与主题命名，并登记在本索引。已被替代的决策保留原文，链接到后继决策。

- [ADR-0004 核心交易产品范围](adr/0004-core-trading-product-scope.md)：Grafana、新闻、研究功能及页面退出产品与迁入目标，保留核心交易与必要诊断。

- [ADR-0009 写命令通信归属](adr/0009-trade-command-communication-owner.md)：复用单一通信Journal，WT保留金融事实归约，unknown不自动重发。

- [ADR-0013 QMT连接生命周期](adr/0013-qmt-connection-lifecycle.md)：常驻等待、单一代际owner、旧请求保留及重新认证。

- [ADR-0014 显式历史缓存补齐权限](adr/0014-history-cache-preparation.md)：缓存副作用的独立能力、原队列/通信事实及未知结果保留。

- [ADR-0018 已确认只读责任的有界回收](adr/0018-confirmed-read-responsibility-retirement.md)：运输确认与消费确认分别拥有，终态回收保持原身份、截止与未知责任；交易账本保持。

- [ADR-0019 Native报价快照消费](adr/0019-native-quote-snapshot-consumer.md)：进程内完整快照后确认消费，原身份未知保持。

- [ADR-0020 批量分析来源身份](adr/0020-batch-analysis-source-identity.md)：单原SDK批次与证券投影分别记录，复用原认证、截止及消费回收。

- [ADR-0023 执行恢复准入](adr/0023-execution-recovery-admission.md)：正常/故障依据及兼容发行分别核验，原金融owner与命令身份保持。

- [ADR-0024 Host HTTP read retirement](adr/0024-host-http-read-retirement.md): Host/Native lifetime ownership and immutable terminal accounting.

- [ADR-0025 WT统一日线和定日事实归属](adr/0025-unified-daily-data-owner.md)：WT拥有来源采集、缺口补齐、原生落盘及版本发布，观衡只读同一版本并保留原指标公式。

- [ADR-0026 日线HPR通信代接续](adr/0026-daily-hpr-transport-generations.md)：原补齐计划、旧槽和新通信代分别持有身份。
- [ADR-0027 日线批读通信代接续](adr/0027-daily-batch-transport-generations.md)：原批读SDK保持，数据owner显式选择跨同业务来源的通信代接续。
- [ADR-0030 WT 私有持久化](adr/0030-wt-private-persistence.md)记录私有目录、策略扩展、提交与去重的归属。
