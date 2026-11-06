# 2026-11-07 AI 原生项目知识方案的研究依据

类型：项目工程研究。状态：proposed。所有者角色：项目维护者。适用范围：AI 编程代理的项目上下文、任务续接、经验回写与持续演进。核对日期：2026-11-07。

## 方案归属与范围更正

用户明确要求后续 AI 开发能够读取适用知识、准确续接任务并将经验持续回写。具体采用要求、文件清单、阶段和验收统一维护于[AI 原生项目知识与持续演进方案](../specs/agent-project-knowledge.md)。本页保留一手来源和选型理由，当前规范与工具的实际覆盖由对应正文和证据说明。

上一版以传统文档分类和维护为主线。Google《Software Engineering at Google》的文档章同样主要面向人类工程师；其所有者、唯一正文和有效性原则继续作为辅助方法。新方案以代理的上下文发现、按需读取、任务续接和反馈回写为主要依据。

## 主要 AI 原生依据

| 一手资料 | 已核实的做法 | 本项目采用判断 |
|---|---|---|
| [AGENTS.md 开放约定](https://agents.md/) | 为编程代理提供可预测的项目指令入口 | 根入口保持简短，按职责提供条件指针；按实际工具核实作用域 |
| [Codex 自定义机制](https://developers.openai.com/codex/concepts/customization) | 区分项目指导、记忆与技能；纠正回写、规则配套检查、技能渐进读取 | 将稳定规则、任务状态、验证经验和执行流程分别归属；控制常驻上下文 |
| [Codex 指导发现](https://developers.openai.com/codex/agent-configuration/agents-md) | 项目指导沿目录层级发现，具有覆盖和加载边界 | 核实真实指令链；普通 Markdown 链接由代理按条件主动读取 |
| [Codex 最佳实践](https://developers.openai.com/codex/learn/best-practices) | 短而准确的指导，依据重复反馈改进，成熟重复工作提炼为技能 | 经验先在原模块验证并收敛，需要跨模块稳定适用时再进入公共规范 |
| [Claude Code 指令与记忆](https://code.claude.com/docs/en/memory) | 长期指令与经验积累分别建模，按范围组织，维护简短与一致性 | 借鉴知识分工、适用性和冲突清理；具体记忆存储与触发能力沿工具分别核实 |

这些资料属于开放约定和产品实践。完整的任务续接、知识归属、失效处理与验收机制为本项目设计，实施状态沿唯一方案登记。

## 保留为辅助的传统方法

| 来源 | 继续使用的范围 |
|---|---|
| [Diátaxis](https://www.diataxis.fr/start-here/) | 帮助区分教程、操作步骤、参考事实与解释，改善人类及代理阅读 |
| [Docs as Code](https://www.writethedocs.org/guide/docs-as-code/)与[文档测试](https://www.writethedocs.org/guide/tools/testing/) | 同变更维护、评审、版本控制及适用自动检查 |
| [Google 文档章](https://abseil.io/resources/swe-book/html/ch10.html)与[OpenDocs 清单](https://github.com/google/opendocs/blob/main/audit/checklist.md) | 所有者、权威正文、实际复核及反馈改进 |
| ISO [26514:2022](https://www.iso.org/standard/77451.html)与[15289:2019](https://www.iso.org/standard/74909.html) | 校准用户信息和生命周期资料覆盖；本次只取得官方摘要，完整条款符合性尚未评估 |

## 本地调查与采用判断

本仓已有职责、规格、唯一正文、缺陷与证据规则，适合沿现有结构完善。[文档健康审计](../evidence/2026-11-07-documentation-health.md)保存 134 项问题及来源范围；[本次设计验证](../evidence/2026-11-07-ai-native-documentation-plan.md)保存源码观察、设计检查和未执行事项。

实际重点是 NOW 的指定任务路由、CURRENT/TARGET 当前与历史分层、模块经验的适用条件、任务级续接和回写收敛。现有 `start/check` 的能力、空项目技能清单与后续工具接口在唯一方案中分别登记。

项目目录、任务记录、知识字段和验收采用渐进实施。工具可判定事项与新会话行为验证分别提供证据；完整系统效果由实际实施与实验确认。

## 来源核对与历史

传统资料在本次对话的上一轮通过 Exa 五次检索发现，共请求 25 条结果，并读取九次 URL（含重复），当时形成传统文档研究。用户进一步澄清 AI 原生目标后，已实际检索并读取上述 Codex 官方、AGENTS.md 和 Claude Code 页面，本轮复用这些已核实材料并重新对照仓库结构。

本页为尚未合入的研究候选，本次按最终任务范围重写。先前选型定位及其修正由本节说明；后续实施细节统一指向规格，保持方案唯一正文。
