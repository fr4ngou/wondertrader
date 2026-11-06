# 观衡量化交易系统开发入口

适用范围：本仓库的功能开发、维护、评审、运行和发布。子目录规则补充局部约束，公共规则保持唯一正文。

## 开始工作

1. 使用 Python 3.10+ 执行 `python -B scripts/project.py start`，沿[文档任务路由](docs/README.md)读取相关正文。
2. 查看 Git 状态、任务规格和涉及的[模块](docs/modules/README.md)，核实输入、状态所有者及完整调用链。
3. 以任务已授权的范围开展工作；保持其他工作区改动和正在运行的实例。分支默认使用 `codex/` 前缀。

## 共同约束

- 开发顺序遵循[主路径优先](docs/development/workflow.md#主路径优先)：先完成整体模块并跑通实际调用链，再集中处理边界、bad case和代码评审。
- 跨会话分工和目标执行[会话协作](docs/development/workflow.md#会话协作)：消息只用于完整交付、需要接收方行动的真实阻塞、共享资源冲突或必须决策的事项；普通进度留在本会话。
- Worktree开发任务合入master后，开发者按[Worktree收尾](docs/development/workflow.md#worktree收尾)手动清理临时工作树，并核对目录和Git登记已移除。
- 在负责该事实或行为的模块修正根因，以统一逻辑实现；验收包含原触发条件及受影响调用链。
- 新增次数、容量或截止限制时，遵循[限制的职责](docs/development/coding.md#可用性与限制的职责)，明确业务依据、作用范围及继续方式。
- 公共接口、持久状态、权限或恢复语义变化先更新规格；长期职责决策写入 ADR。
- 每类业务事实保持明确所有者。缓存、展示投影、策略目标和外部账户事实分别标识。
- 交易副作用遵循账户授权、风险检查和执行状态；超时或结果未知时先核查，保留原命令身份。
- 凭证、个人账户资料、真实交易数据和生产配置保留在受控运行环境，仓库只保存脱敏示例。
- 方案、代码、验证和部署分别登记完成状态。真实下单、撤单、权限变更、数据删除及生产发布按明确授权执行。

上游框架行为变更须遵循[配置分流规则](docs/development/upstream.md#框架行为的配置分流)，再按下表读取适用规范。

## 按任务读取

| 工作 | 必须读取 |
|---|---|
| 功能、修复、重构与代码评审 | [开发流程](docs/development/workflow.md)、[代码规范](docs/development/coding.md)、[验证规范](docs/development/verification.md) |
| 新增或修改接口、结构体/数据类/DTO字段、协议字段、生命周期或复杂逻辑 | [注释规范](docs/development/comments.md)，数据模型的每个字段同步中文注释 |
| 编写方案、改变模块职责或数据归属 | [方案规范](docs/development/design.md)、[系统架构](docs/architecture/overview.md) |
| 文档、模块说明、规格或证据维护 | [文档规范](docs/development/documentation.md) |
| 构建、依赖、测试工具链 | [构建手册](docs/runbooks/build.md) |
| 上游同步、核心覆盖、合并冲突 | [上游维护规范](docs/development/upstream.md)、[更新操作手册](docs/runbooks/upstream-updates.md) |
| 打包、发布、回滚与发布后验真 | [发布规范](docs/runbooks/release.md) |
| 异常、交易阻断、数据故障与恢复 | [故障处理规范](docs/runbooks/incidents.md) |

## 完成工作

运行适用验证及 `python -B scripts/project.py check`，按[证据规范](docs/evidence/README.md)记录结果，更新改变的唯一正文和任务状态。最终说明实际变更、验证证据、未覆盖范围及下一项必要动作。
