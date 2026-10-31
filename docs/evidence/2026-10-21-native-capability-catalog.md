# 2026-10-21 原生能力目录与开发前置核查

类型：源码研究与文档验证记录。状态：主要公共路径的静态核查完成；目标环境行为、容量及完整业务接入待验。功能开发保持暂缓，下一步先验证和收敛原生方案。

## 输入与方法

- C++ 上游固定提交：`08b230dd05facf6d650d949bfe51054115a2ecb1`；使用 `git show`/`git grep` 核查原对象，当前下游代码与冻结差异分别登记。
- 官方可选 wtpy 固定提交：`9fd4cd98feaa6fa2ea084741b3bb2adbe2b6bd78`。只核能力归属，未引入运行依赖。
- 三条只读调查分别覆盖行情存储、策略回测、交易执行；主任务补查宿主、事件、部署、测试入口，并整合长期文档。执行和行情调查者交叉核查最终目录及对应模块。
- 本机研究材料：`build/native/capability-audit/{market-data,strategy-backtest,execution,catalog-review}.md`。长期结论引用固定上游源码，不依赖这些临时文件才能阅读。

## 交付正文

- [40项原生能力目录](../development/wondertrader-capabilities.md)：原生入口、配置/来源条件、限制、扩展与可选子项目分别列明。
- [开发复用规则](../development/wondertrader-reuse.md)：先证明原生缺口；重合能力采用WT，旧职责退出目标架构；核心变更遵循批准程序。
- [行情存储](../modules/wondertrader-data-capabilities.md)、[策略回测](../modules/wondertrader-strategy-capabilities.md)、[交易执行](../modules/wondertrader-trading-capabilities.md)：源码机制、调用路径、状态、并发和生命周期边界。
- [业务适配地图](../migration/business-adaptation-map.md)：用户功能承接、旧实现退出及尚待选择的接缝；迁移进度和候选取舍保留在任务文档。
- 开发流程、方案规范、代码规范和导航已连接上述必读规则；状态与消费者规格明确暂停新增接线。

## 关键纠正

1. 默认文件后端的Servo已支持最多N根和范围查询；自有exact-count条件不能归为WT限制。策略Reader与随机Reader分别核实，新增客户端候选暂缓。
2. 默认DSB/DMB与原生LMDB后端分别拥有Reader；AD随机Reader存在明确TODO。Helper的store_bars直接写DSB。缓存清理、派生周期刷新及旧切片寿命分别验证。
3. CTA/SEL/HFT/UFT及各回测mocker能力各异。UFT实盘历史切片空实现、SEL宿主接线、分布式执行占位与算法工厂返回空均精确限定到路径。
4. 原生已有订单成交记录、策略状态和执行目标；CSV推送记录、券商实际账户与未决命令身份有不同语义。独有业务事实逐项论证，不能以旧SQL表存在证明需要保留数据库。
5. 原生队列、块锁、映射和LMDB事务已列出实际范围；局部机制与完整宿主生命周期分别说明。静态待验风险不直接升级为框架故障结论。

## 文档验证与范围

交叉复核指出的执行接口命名、C ABI名称、UFT状态存储、Runner名称、后端图示和默认查询范围已修正；数据符号引用已改为有效固定源码链接。文档导航检查及最终输入摘要记录于 `build/native/capability-audit/document-validation.json`。

此次未新增功能实现，未运行构建、数据库测试或券商操作。此前Reader客户端与PG分钟链候选保留但暂缓接线、发包；生产服务和数据保持。此次源码研究不能替代全市场十年容量、同实例修订/订阅并发、实盘恢复、页面整链或生产发布验收。

下一步先用原生路径验证查询/复权/周期、缓存修订、线程生命周期和状态恢复，再按真实缺口收敛适配方案；依据尚不充分的模块继续调查。既有冻结框架差异按原批准边界处理。
