# 2026-11-07 开发原则与缺陷预防规范整合

类型：验证记录。结果：partial（本次增量验证 pass，全仓检查受既有问题影响）。本次规范维护任务状态：done。

## 范围与输入身份

用户确认采用本次审阅的七项建议，并明确要求写入控制过度设计、围绕已确认问题实现的原则。本次维护开发规范、入口路由和模板；业务实现、运行配置及生产部署保持当前状态。

基准提交：`fe1b829ce84c511aeecffd59adddb147d4440070`。工作树含其他任务既有改动；修改前保存本次涉及文档的逐文件原始内容和 SHA-256，按工作树快照核对本次增量。受控本地记录：`.tmp/development-principles-20261107-001/`。环境：Windows PowerShell，Python 3.14.6。

## 要求与正文映射

| 已确认要求 | 唯一规则正文或入口 | 本次落实 |
|---|---|---|
| 缺陷记录、历史检索与预防跟踪 | [缺陷记录规则](../runbooks/incidents.md#开发缺陷记录与检索) | 轻量记录、稳定引用、开发前检索及重大/重复缺陷复盘；修复与预防事项分别跟踪 |
| 根因与同类防护缺口 | [缺陷记录规则](../runbooks/incidents.md#开发缺陷记录与检索)及[故障模板](../incidents/TEMPLATE.md) | 证据、促成条件、设计/校验/测试/监控缺口和其他入口排查 |
| 语义一致的复用与控制过度设计 | [代码规范](../development/coding.md#控制过度设计) | 当前已确认需求、抽象收益与维护成本；复用核对业务语义、职责和变化原因 |
| 模块边界及新增结构检查 | [方案规范](../development/design.md#结构变化与模块边界)及[模块模板](../modules/TEMPLATE.md) | 公开接口和依赖方向、普通整理与结构变化的处理深度、迁移和旧路径退出 |
| 目标集中、完整切片的修改 | [开发流程](../development/workflow.md#实施) | 独立评审步骤；无关重构、格式整理与功能变更分别组织 |
| 主路径与必要验证共同推进 | [开发流程](../development/workflow.md#主路径优先)及[验证规范](../development/verification.md) | 更新原统一推迟测试的要求；设计前置关键风险，回归及必要测试随对应切片完成 |
| 稳定约束逐步自动检查 | [验证规范](../development/verification.md#规则自动检查) | 复用已有工具、核实符合/违反样例、登记实际覆盖和待建立项 |

[AGENTS](../../AGENTS.md)保持简短规则与触发路由，[故障索引](../incidents/README.md)链接轻量记录规则。现有索引和任务状态采用增量维护，保留其他任务正文。

## 参考依据

以下公开一手资料已于本次对话核对，适用日期：2026-11-07；采用其方法原则，具体流程按本仓职责和风险约束调整。

- [Google 代码评审检查指南](https://google.github.io/eng-practices/review/reviewer/looking-for.html)：设计归属、复杂度、过度设计和有效测试。
- [Google Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)：单一目标、自包含变更、相关测试及大型修改的拆分。
- [Google SRE 复盘指南](https://sre.google/workbook/postmortem-culture/)：系统改进、事实证据、可追踪且可衡量的预防动作。
- [Microsoft ADR 指南](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record)：架构重要性、背景、取舍、后果和决策生命周期。
- [ArchUnit 官方手册](https://www.archunit.org/userguide/html/000_Index.html)：Java 包依赖、分层和循环依赖的自动检查示例。

## 步骤与观察

| 命令或人工步骤 | 退出码/观察 | 结论 |
|---|---|---|
| `python -B scripts/project.py start` | 0；读取任务路由与当前工作摘要 | 入口完成 |
| 修改前 `python -B scripts/project.py check` | 1；134 项既有缺失链接及未索引文档 | 保存基线，日志见本地 `check-before.txt` |
| 逐文件对照修改前快照 | 13 份文档；证据索引、NOW、CURRENT 的既有段落逐项保持 | 本次增量范围核对通过；差异见本地 `changes.diff` |
| 修改后 `python -B scripts/project.py check` | 1；134 项，与修改前逐项相同，新增 0、消除 0 | 全仓检查仍失败，本次修改未新增问题；日志见本地 `check-after.txt` |
| 新增链接及标题锚点核对 | 20 个新增本地链接通过，UTF-8 正文未发现替换字符 | 本次导航和编码检查通过，结果见本地 `verification.json` |
| `git diff --check`（本次涉及文件） | 0 | 差异空白检查通过 |
| 人工核对规则及模板 | 七项要求均有正文映射；入口已同步，原统一推迟测试的表述已更新 | 文档语义与本次授权范围一致 |

## 证明范围与限制

本次为规范和模板维护，验证范围为文字一致性、本次增量、文档链接与索引。稳定约束自动检查登记为后续按实际能力建立的要求，本次未实现语言依赖检查器或公共接口兼容性工具。

全仓静态检查仍有修改前的 134 项缺失链接及未索引问题，后续需按原文档所有者补齐目标或导航再取得全仓通过结论。本次修改新增问题为 0。应用构建、业务测试、真实终端和生产验真不属于本次修改的证明范围。
