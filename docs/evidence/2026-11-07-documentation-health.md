# 2026-11-07 文档完整性问题分类审计

类型：只读审计记录。结果：partial；问题分类和本次新增文档检查完成，全仓完整性检查失败。范围：当前工作树的文档、Git 索引和 HEAD；其他分支、工作树与外部证据尚未追查。

## 结论与计数

本轮重新运行 `python -B scripts/project.py check`，退出码 1，准确报错数为 **134**。上一轮保存的检查基线同为 134；用户本轮提到的 133 与实际记录相差 1。

| 分类 | 报错数量 | 含义 |
|---|---:|---|
| 缺失目标链接 | 104 | 多个正文或索引引用的目标文件在当前工作树不存在 |
| 未索引文档 | 30 | 文件实际存在，从 `AGENTS.md` 或 `docs/README.md` 沿维护范围内的链接无法到达 |
| 合计 | 134 | 静态链接与导航问题；文档内容正确性、业务行为、部署资格另行验证 |

104 处缺失链接指向 **86 个不同目标**，重复引用产生额外报错。

| 缺失目标所在目录 | 不同目标数 |
|---|---:|
| `docs/evidence/` | 47 |
| `docs/releases/` | 37 |
| `docs/architecture/adr/` | 1 |
| `docs/specs/` | 1 |

| 发出缺失链接的文档 | 报错数 |
|---|---:|
| `docs/evidence/README.md` | 53 |
| `docs/releases/README.md` | 37 |
| `docs/roadmap/NOW.md` | 9 |
| `docs/modules/unified-daily-data.md` | 2 |
| `docs/runbooks/unified-daily-data.md` | 1 |
| `docs/runbooks/wt-independent-runtime.md` | 1 |
| `docs/specs/qmt-source-daily-history.md` | 1 |

未索引的 30 份文档中，29 份为旧验证/评审资料，1 份为研究资料。其中 16 份集中于 `docs/evidence/guanheng-native-2026-10-21/`，其内部已有 README 与互链；上层入口的可达性需要修复。

## 已确认事实与原因边界

- 86 个缺失目标在当前文件系统、Git 暂存索引和 HEAD 树中均不存在。`core.sparseCheckout=true`，但这批路径在索引和 HEAD 也不存在，当前证据支持继续调查文件提交与归档来源。
- 示例：分析窗口有效期、每笔执行数量等发布记录被多个索引和任务状态引用，产生重复报错；当前无法沿链接回查对应证据。
- 现有未索引资料已经保存在工作树；问题在上层导航图，修复时应补所属索引并保持主题关系。
- 当前检查器在 [project.py](../../scripts/project.py) 中只核验声明范围内的本地路径、导航可达性和技能清单。外链、标题锚点、正文过期、命令有效性、规格与代码一致性均缺少该命令的自动证明。
- 当时共享工作区可见的托管工作流为 `.github/workflows/native.yml`，该文件未归当前主干；其路径触发范围与步骤尚未包含独立文档变更和 `project.py check`。当前主干已有本地 CI，实际入口沿[本地 CI 手册](../runbooks/local-ci.md)。远端部署情况、本地 Git hooks 及其他外部流水线未核实。

当前症状显示文档正文、索引及当前状态的引用集合发生脱节。文件是否保留在其他分支、工作树或原始交付目录，尚需按来源追查；本轮没有将文件缺失归因于某次清理或某个开发者。

## 处理顺序

1. 优先追查当前运行手册、模块说明、规格和 NOW 引用的发布及证据目标，明确可恢复来源与适用身份。恢复原件或链接已核实的后继记录；证据仍缺失的结论标明缺口及实际影响。
2. 对历史资料按原所属主题补齐上层索引，保留历史输入、结论和后继关系。
3. 核对其余缺失目标的原件及迁移来源，保持索引和正文在同一交付单元中变更。
4. 文档完整性恢复后，将检查接入文档相关变更的 CI；若分阶段修复，基线例外需有负责人、处理计划和退出条件。

缺失记录的恢复以真实原件或可核实依据为前提；审计明细使用代码路径列举，避免明细本身成为历史资料的替代导航。

## 步骤、输入与证明范围

输入基准为当前工作树，Git HEAD：`fe1b829ce84c511aeecffd59adddb147d4440070`；包含此前任务未提交改动。环境为 Windows PowerShell、Python 3.14.6。机器可读分类与原始检查日志保存在本地 `.tmp/documentation-health-20261107-001/`。

| 步骤 | 实际结果 | 范围 |
|---|---|---|
| `python -B scripts/project.py start` | 0 | 当前路由与任务读取 |
| `python -B scripts/project.py check` | 1；134 项 | 本地文档静态完整性 |
| 目标绝对路径解析、来源和目标去重 | 104 处链接 / 86 个目标，30 个未索引文件 | 分类与去重 |
| `git ls-tree -r --name-only HEAD -- docs` 与 `git ls-files -- docs` | 86 个目标在两者均缺失 | 当前 HEAD 与索引归档状态 |
| `git config --get core.sparseCheckout`、`git sparse-checkout list` | 稀疏检出开启，规则可读 | 检出配置观察 |
| 检查本地可见工作流和检查器源码 | 已完成 | 当前工具能力及文档触发范围 |
| 新增文档及导航的本地链接、锚点和 UTF-8 检查 | 16 个本地链接通过，错误 0 | 本次审计、研究和索引的增量范围 |
| 修改后 `python -B scripts/project.py check` | 1；仍为相同 134 项，新增 0 | 审计及研究文件接入未新增静态问题 |
| `git diff --check`（本次涉及文档）与原状态段落对照 | 0；共享索引和 roadmap 既有段落保留 | 本次增量与其他任务内容保护 |

本轮完成问题总结与采用方案研究；规范正文、检查器、CI、历史记录及生产环境保持当前状态。成熟标准及演进方案见[研究报告](../research/2026-11-07-documentation-standards-lifecycle.md)。

## 缺失目标明细

以下路径在本轮核对时不存在于工作树、索引和 HEAD；括号中为被引用次数。

```text
docs/architecture/adr/0027-daily-batch-transport-generations.md (1)
docs/evidence/2026-11-04-continuous-minute-collection.md (1)
docs/evidence/2026-11-04-current-strategy-cash3-postflight.md (1)
docs/evidence/2026-11-04-current-strategy-restart.md (1)
docs/evidence/2026-11-04-daily-gap130-release.md (1)
docs/evidence/2026-11-04-daily-gap130.md (1)
docs/evidence/2026-11-04-minute-daily-adoption-candidate.md (1)
docs/evidence/2026-11-04-minute-projection-capacity.md (1)
docs/evidence/2026-11-04-minute-startup-runtime-repair.md (1)
docs/evidence/2026-11-04-observer-current-joint-acceptance.md (1)
docs/evidence/2026-11-04-observer-sdk017.md (1)
docs/evidence/2026-11-04-observer-wt-daily-consumer.md (1)
docs/evidence/2026-11-04-strategy-closed-day-input.md (1)
docs/evidence/2026-11-04-unified-daily-categories-candidate.md (1)
docs/evidence/2026-11-04-unified-daily-full-scope.md (2)
docs/evidence/2026-11-04-wt-runtime-service7-source-closure.md (1)
docs/evidence/2026-11-04-wt-runtime-service9-permanent-source.md (1)
docs/evidence/2026-11-04-wt-runtime-source-closure.md (1)
docs/evidence/2026-11-05-auxiliary-and-process-log-intake.md (1)
docs/evidence/2026-11-05-daily-and-collection-recovery.md (1)
docs/evidence/2026-11-05-document-index-lifecycle.md (1)
docs/evidence/2026-11-05-hpr-compatible-closure.md (1)
docs/evidence/2026-11-05-hpr-control-rejection.md (1)
docs/evidence/2026-11-05-native-buy-fee-budget.md (1)
docs/evidence/2026-11-05-process-log-retention.md (1)
docs/evidence/2026-11-05-qmt-auxiliary-api-research.md (1)
docs/evidence/2026-11-05-service-preexecution-recovery.md (1)
docs/evidence/2026-11-05-strategy-auxiliary-gap.md (1)
docs/evidence/2026-11-06-analysis-binding-self-recovery.md (1)
docs/evidence/2026-11-06-backtest-rerun-stage-block.md (2)
docs/evidence/2026-11-06-cancel-refresh-e2e.md (1)
docs/evidence/2026-11-06-cancel-refresh-integration.md (2)
docs/evidence/2026-11-06-full-market-daily-source-facts.md (1)
docs/evidence/2026-11-06-integrated-auxiliary-diagnostics-backtest.md (1)
docs/evidence/2026-11-06-live-auxiliary-warmup.md (1)
docs/evidence/2026-11-06-local-ci.md (2)
docs/evidence/2026-11-06-mainline-online-acceptance.md (2)
docs/evidence/2026-11-06-mainline-preopen-followup.md (1)
docs/evidence/2026-11-06-mainline-requirements-audit.md (1)
docs/evidence/2026-11-06-minute-retained-closure.md (1)
docs/evidence/2026-11-06-native-runtime-log.md (1)
docs/evidence/2026-11-06-parser-preopen-startup.md (1)
docs/evidence/2026-11-06-quantity-target-handoff.md (2)
docs/evidence/2026-11-06-read-wait-submission.md (1)
docs/evidence/2026-11-06-stage-block-layers-and-cash.md (1)
docs/evidence/2026-11-06-stock-target-replacement.md (1)
docs/evidence/2026-11-06-working-order-recovery.md (1)
docs/evidence/current-auxiliary-consumption-20261106.md (1)
docs/releases/2026-11-04-bounded-runtime-cleanup.md (1)
docs/releases/2026-11-04-cash4-unified-runtime.md (2)
docs/releases/2026-11-04-daily-gap130-unified7.md (1)
docs/releases/2026-11-04-daily9-live-inputs.md (1)
docs/releases/2026-11-04-observer-a107-wt-current-live.md (1)
docs/releases/2026-11-04-observer-a108-wt-daily-live.md (1)
docs/releases/2026-11-04-observer110-sdk017.md (2)
docs/releases/2026-11-04-source-reference-and-clean-stop-live.md (1)
docs/releases/2026-11-04-unified-daily-full-scope-live.md (2)
docs/releases/2026-11-05-cash5-live-and-event-frontier.md (1)
docs/releases/2026-11-05-cross-date-trade-candidate.md (1)
docs/releases/2026-11-05-current-day-and-hpr-live.md (2)
docs/releases/2026-11-05-daily-read-and-minute-recovery.md (1)
docs/releases/2026-11-05-independent-wt-control-and-observer111.md (3)
docs/releases/2026-11-05-resonance122-role-recovery.md (1)
docs/releases/2026-11-05-source-binding-and-afternoon-recovery.md (1)
docs/releases/2026-11-06-analysis-cache-owner-live.md (1)
docs/releases/2026-11-06-current-auxiliary-automatic-live.md (1)
docs/releases/2026-11-06-daily21-full-market-published.md (1)
docs/releases/2026-11-06-daily21-r003-settled.md (1)
docs/releases/2026-11-06-daily21-reference-resume-live.md (1)
docs/releases/2026-11-06-market-window-age.md (3)
docs/releases/2026-11-06-minute-counter-quality-live.md (1)
docs/releases/2026-11-06-minute-retained-resume-live.md (1)
docs/releases/2026-11-06-native-read-transport-live.md (1)
docs/releases/2026-11-06-observation115-publication-recovery.md (1)
docs/releases/2026-11-06-observer114-diagnostics-live.md (1)
docs/releases/2026-11-06-observer116-reading-live.md (1)
docs/releases/2026-11-06-observer117-runtime-live.md (1)
docs/releases/2026-11-06-observer118-current-live.md (1)
docs/releases/2026-11-06-qualified-worktree-cleanup.md (1)
docs/releases/2026-11-06-runtime14-auxiliary-live.md (1)
docs/releases/2026-11-06-stock-order-lots.md (3)
docs/releases/2026-11-06-stock-target-and-read-wait-live.md (1)
docs/releases/2026-11-06-target-handoff-partial-release.md (2)
docs/releases/2026-11-06-working-order-recovery-live.md (2)
docs/releases/2026-11-06-worktree-cleanup-and-cancel-branch.md (1)
docs/specs/qmt-security-reference-source.md (1)
```

## 未索引文档明细（30 份）

```text
docs/evidence/cal-2026-10-21/calendar-consumer-independent-review.md
docs/evidence/guanheng-native-2026-10-21/business-delta-review.md
docs/evidence/guanheng-native-2026-10-21/business-review.md
docs/evidence/guanheng-native-2026-10-21/execution-delta-review.md
docs/evidence/guanheng-native-2026-10-21/execution-final-review.md
docs/evidence/guanheng-native-2026-10-21/execution-isolation-delta-review.md
docs/evidence/guanheng-native-2026-10-21/execution-runtime-review.md
docs/evidence/guanheng-native-2026-10-21/integration-delta-review.md
docs/evidence/guanheng-native-2026-10-21/integration-encoding-delta-review.md
docs/evidence/guanheng-native-2026-10-21/integration-final-review.md
docs/evidence/guanheng-native-2026-10-21/integration-style-delta-review.md
docs/evidence/guanheng-native-2026-10-21/market-delta-review.md
docs/evidence/guanheng-native-2026-10-21/market-lease-delta-review.md
docs/evidence/guanheng-native-2026-10-21/market-minute-final-review.md
docs/evidence/guanheng-native-2026-10-21/market-minute-review.md
docs/evidence/guanheng-native-2026-10-21/market-review.md
docs/evidence/guanheng-native-2026-10-21/README.md
docs/evidence/hes-2026-10-21/hes-independent-review.md
docs/evidence/hes-2026-10-21/hes-sdk-independent-review.md
docs/evidence/hsa-2026-10-21/hsa-lifecycle-sdk-review.md
docs/evidence/hsa-2026-10-21/hsa-runner-independent-review.md
docs/evidence/hw-2026-10-21/hw-independent-review.md
docs/evidence/hw-2026-10-21/hw-sdk-independent-review.md
docs/evidence/live-source-2026-10-21/account-contract-audit-20261021.md
docs/evidence/native-build-2026-10-21/review.md
docs/evidence/native-history-reader-2026-10-21/full-review.md
docs/evidence/qmt-http-2026-10-21/independent-review.md
docs/evidence/qmt-http-2026-10-21/README.md
docs/evidence/wt-design-audit-2026-10-21/README.md
docs/research/2026-10-29-market-observation-indicators.md
```

## 后继修复与合入核对

本节为同日后继收尾；前文 134 项属于修复前共享旧分支输入，保留原统计和失败范围。固定集成基线为本地 master `47ce2c4a580a1140e4eaa4bd810f4a255d27519d`。

- 104 处失效引用的 86 个目标全部存在于该主干。共享工作区恢复原 Git blob，并沿引用补齐 31 项后继依赖，共 117 项；原已存在文件保持，恢复材料的提交身份及 SHA-256 已登记。
- 29 份孤立 Markdown 属于 10 个原已标为外部历史的 QA 材料目录，全部为未跟踪原件。236 个原文件完整移入受控 QA 目录，逐文件 SHA-256 核对通过。仓库保留已有验证摘要和材料来源，原始日志继续归 QA 所有。
- 另 1 份市场观察指标研究正文已接回研究索引；其原文状态和证据范围保持。
- 共享工作区的 `python -B scripts/project.py check` 已由 134 项失败变为通过。主干基线本身原已通过；本次集成使用其完整来源，并带入本轮经审查的文档规则、知识方案和快照工具。

本地材料清单位于 `E:/workspace/wondertrader-qa/documentation-integrity-20261107-001/RECOVERY-MANIFEST.json`。它记录每个恢复源 Git 身份、归档前后路径及原文件摘要；文件名列表和实际原件保留在受控位置。

合入审阅同时发现旧分支目标仍引用正式 1.1.2，主干已确认后继 1.2.2 范围。集成 TARGET 保留主干有效目标、100 万元含持仓账本、后继真实成交周期和操作边界；旧分支约束仅作为历史追溯。CURRENT 使用现存采用原件，600 秒窗口、10000 份数量的原缺证已恢复，当前进程状态仍限定为最近记录的观察。

最终检查覆盖闭环、维护量、失效与后继、跨分支语义冲突及原件归属。普通小改按现有载体留结果；日常更新使用 Git 历史，完整快照用于明确迁移需要。正式结果以本次本地 CI 和独立审阅收据登记，合入前全部适用检查需通过。
