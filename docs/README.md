# 观衡量化交易系统文档

- [WT统一日线角色安装与回退](runbooks/unified-daily-data.md)：固定源码/轮子、原SMP组合、原身份恢复及数据版本回退。

本索引是开发与维护的任务路由。每次从 [AGENTS.md](../AGENTS.md) 和 `python -B scripts/project.py start` 进入，按任务读取相关正文。

## 系统与模块

- [WonderTrader原生能力与支持边界](development/wondertrader-capabilities.md)：开发前必读，明确原生、扩展、可选子项目及已知限制。
- [能力核实与复用规则](development/wondertrader-reuse.md)：重合能力采用原生实现，查清能力后再开发。

- [产品目标](product/brief.md)：系统能力、角色及成功标准。
- [架构与 ADR](architecture/README.md)：职责、事实所有者、调用链和长期决策。
- [模块说明](modules/README.md)：数据、运行、执行、接入、回测和业务集成。

## 工作规范

本地持续集成：[CI与master合入](runbooks/local-ci.md)，开发分支按实际变化自动运行检查、回归及执行链E2E；源码身份匹配后合入本地master，发布独立执行。

开发验证到发布的衔接：[开发流程](development/workflow.md) → [验证规范](development/verification.md) → [本地CI](runbooks/local-ci.md) → [构建手册](runbooks/build.md) → [发布与回滚](runbooks/release.md)。相同输入复用有效结果，WT与观衡分别发布。

日常使用入口：[观衡中文操作员手册](runbooks/guanheng-operator.md)，覆盖启动、各业务页、09:00观察、停止恢复与升级回退；具体配置与当前验收资格沿各模块唯一正文。

独立WT运行入口：[WT安装、启动和只读观察手册](runbooks/wt-independent-runtime.md)，运行侧独立维护通信、数据和执行生命周期，完整组合资格沿WRI核验。

独立观衡制品：[离线安装与更新回退](runbooks/observer-runtime.md)，只读App与SPA装入全新目录，外部读取配置及个人观察目录沿用。

观衡永久源码：[离线构建App及读取侧](runbooks/observer-source.md)，显式固定工具与第三方依赖，从六永久项目及当前前端生成独立角色/ZIP。

终端外解释器：[固定运行时、角色重装与更新恢复](runbooks/python-runtime.md)，WT辅助进程、Host和观衡各自保留精确依赖及基础解释器身份。

常驻交易通信：[WT托管交易Host及完整策略正文](runbooks/qmt-trade-host-product.md)，与原行情和历史通道并存，材料、SDK替身与真实账户资格分别核对。

内置来源运行：[原策略回调驱动配置](runbooks/qmt-source-runtime.md)，显式选择来源生命周期，保留默认行为、请求身份和原截止。

同正文账户连接：[生成及维护操作手册](runbooks/qmt-account-composed-source.md)，复用原只读pair与交易/QST/HPR配置，配对准备在终端外进行，运行由独立WT管理。

历史查询子服务：[WT管理、只读连接与停止](runbooks/source-market-app.md)。服务监听与数据尾部日期、来源单位和完整性分别核实。

国信QMT终端：[日常操作](runbooks/guosen-qmt-operations.md)、[维护与升级回滚](runbooks/guosen-qmt-maintenance.md)、[SHM接入排障](runbooks/guosen-qmt-troubleshooting.md)。运行材料与工具交付状态按手册分别标注，最终运行归本仓库制品。

共享内存历史分钟：[CLI读取、原ID恢复及原生导入](runbooks/qmt-shm-history.md)。历史与快照能力、合成安装及真实来源资格分别核对。

批量日线来源：[分片、原身份与结果消费](runbooks/qmt-analysis-batch-source.md)，显式选择列表SDK能力，数据基准/复权和实际覆盖分别核实。

显式来源缓存补齐：[独立安装、组合配对与系统托管](runbooks/qmt-history-preparation.md)、[WT配置与观衡只读状态](runbooks/history-preparation-app.md)。产品只授已声明缓存副作用，未知结果保留原ID核查。

| 任务 | 读取 | 验证及回写 |
|---|---|---|
| 功能、修复、重构、审查 | [开发流程](development/workflow.md)、[代码规范](development/coding.md) | 相关测试与调用链；原规格和模块说明 |
| 接口与复杂逻辑说明 | [注释规范](development/comments.md) | 语义、线程、生命周期与实现一致 |
| 编写/维护文档 | [文档规范](development/documentation.md) | `project.py check`、唯一正文、索引及事实依据 |
| AI 开发知识与任务续接方案 | [AKN 方案](specs/agent-project-knowledge.md)、[研究依据](research/2026-11-07-documentation-standards-lifecycle.md) | 按采用切片登记；任务选择及行为实验仍待实施 |
| 功能设计、职责或状态变化 | [方案规范](development/design.md)、[规格索引](specs/README.md) | 要求与验收映射；原规格及适用 ADR |
| 测试、审查与运行资格 | [验证规范](development/verification.md)、[测试手册](runbooks/testing.md) | 输入有效的测试及[证据](evidence/README.md) |
| 策略编写与验证 | [策略编写入口](modules/strategy-runtime.md#策略编写入口)、[策略开发与回测交付](development/workflow.md#策略开发与回测交付)、[因子研究流程](research/2026-11-11-factor-research-workflow.md) | 核对原生接口、策略版本、冻结输入和交付范围 |
| 因子素材、研究与演进 | [因子素材目录](research/factor-materials.md)、[因子研究全链路方案](specs/factor-research-lifecycle.md) | 核对公式、时点、证据与版本，沿 WT 正式回测验收 |
| WT 回测与报告 | [回测手册](runbooks/native-backtest.md)、[NBC规格](specs/native-backtest-cli.md) | 研究结果用 WT 查看；指定报告核对正式完成凭证及观衡读回 |
| 构建、环境和工具 | [构建手册](runbooks/build.md)、[维护工具](development/skills.md) | 实际目标命令、工具链与环境证据 |
| 历史分钟计划与证据消费 | [日历消费者](runbooks/history-calendar.md)、[独立 SDK](runbooks/client-sdk.md) | 原 owner 契约、存证回读、完整补齐链与发行身份 |
| 历史进程部署接线 | [部署工厂](runbooks/history-deployment-factory.md)、[HDF规格](specs/history-deployment-factory.md) | 配置准入、凭据隔离、已登记作业及独立服务整链 |
| 闭合分钟消费进程 | [分钟模块](modules/minute-consumer.md)、[部署手册](runbooks/minute-worker.md) | 安装wheel、owner持久确认、空范围/未知结果恢复与有界关闭 |
| 原生策略历史读取与分钟事件 | [Reader 操作手册](runbooks/native-history-reader.md)、[模块说明](modules/native-history-reader.md) | 同实例补齐/修订、回调并发、切片与插件生命周期 |
| QMT 持续快照接入 | [插件操作手册](runbooks/qmt-polling-parser.md)、[模块说明](modules/qmt-polling-parser.md) | 默认工厂、轮询去重、原 adapter/CTA 和线程停止 |
| QMT 全推持续采集 | [WT采集手册](runbooks/qmt-data-collection.md)、[全推模块](modules/qmt-quote-stream.md) | 独立进程、WinSHM、原生分钟/归档、来源新鲜度与关闭 |
| 历史终端HTTP连接包参考 | [历史手册](runbooks/qmt-terminal-source.md)、[源端模块](modules/qmt-terminal-source.md) | 保留原转换与验证证据；当前终端使用SHM，不部署终端内HTTP |
| 查询优先执行宿主 | [C++装配手册](runbooks/qmt-standard-execution-host.md)、[执行模块](modules/execution.md) | 原执行器、交易owner、券商查询及有界关闭分别验收 |
| 账户资金与持仓展示 | [账户手册](runbooks/account-observation.md)、[模块说明](modules/account-observation.md) | 产品宿主、逐批事实、独立安装页面与真实来源分别验收 |
| 已下载分钟历史导入 | [本地DAT直读](runbooks/qmt-local-dat.md)、[QMI导入手册](runbooks/qmt-minute-import.md)、[导入规格](specs/qmt-minute-import.md) | 显式导出、单位/时间、原生回读和原策略文件读取 |
| 发布、回滚 | [发布规范](runbooks/release.md)、[原生部署](runbooks/native-deployment.md) | 真实用户入口、数据和操作；[发布记录](releases/README.md) |
| 系统候选离线安装 | [安装手册](runbooks/system-installation.md)、[SRI规格](specs/system-runtime-installation.md) | App/Host、原生组件和SPA统一候选；实现与验收中，完整M3另列 |
| 上游更新、核心覆盖、冲突 | [上游规范](development/upstream.md)、[更新手册](runbooks/upstream-updates.md) | 双基线、语义整合、回归及[差异登记](maintenance/upstream-overrides.md) |
| 故障、交易阻断、恢复 | [故障处理规范](runbooks/incidents.md) | 原条件回归与业务恢复；[故障记录](incidents/README.md) |

## 状态与任务资料

- [TARGET](roadmap/TARGET.md)：活动目标、用户确认约束与完成条件。
- [CURRENT](roadmap/CURRENT.md)：当前可核实事实及证据边界。
- [NOW](roadmap/NOW.md)：活动任务、验收与续接点。
- [验证记录](evidence/README.md)：实际步骤、结果与限制。
- [既有专项方案](migration/README.md)：单项工作的研究、准备与设计资料。

长期规则维护通用工作方法，任务和环境事实维护在相应实例中。上游参考、接口源码及项目规范的适用范围分别说明。

## 上游参考

WonderTrader 官方文档地址：<https://wondertrader.github.io/#/>；源码及历史环境介绍见 [src/README.md](../src/README.md)。外部说明的适用版本需在使用时核实。

### 回测手续费模板

回测手续费模板的每个品种可以增加可选的 `minfee` 字段，表示每次实际成交（fill）的最低手续费金额。缺省或设置为 `0` 时保持原有按费率计算的行为；只有正费率且成交数量大于零时才应用最低值。示例：`"minfee": 5.0`。

国信内置开发：[Python环境、API与性能手册](runbooks/guosen-qmt-python.md)、[148项函数/属性索引](modules/qmt-native-api-index.md)、[行情数据结构与读取边界](modules/market-data-contracts.md)。[官方更新核查](evidence/2026-10-28-guosen-qmt-official-runtime.md)与[本机版本证据](evidence/2026-10-28-qmt-installed-runtime.md)分别维护。

- [共享内存当前报价](modules/qmt-shm-quotes.md)：WT受管报价、原历史组合及显式消费回收；[装配手册](runbooks/qmt-shm-quotes.md)。

- [共振策略研究指引](research/README.md)：本地研究资料、原版复现、数据每日更新和WT回测。
