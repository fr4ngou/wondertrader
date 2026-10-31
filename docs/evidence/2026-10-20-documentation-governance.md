# 2026-10-20 系统文档治理接入

类型：验证记录。状态：pass。任务范围：长期文档及独立维护工具；原生功能、账户、部署保持原样。

## 输入与来源

- 目标仓库 `E:\workspace\wondertrader`，基线 `08b230dd05facf6d650d949bfe51054115a2ecb1`；工作区已有未提交专项方案，语义整合并保留。
- 使用 repo-bootstrap 0.2.1 的 general、无 UI、含发布手册结构；先预览目标冲突，在 `E:\workspace\wondertrader-docs-candidate-20261020` 生成候选，保留已有 README 和专项文档。
- 维护脚本来自该技能的独立项目资产；保留 `scripts/project_support/LICENSE`，本地将检查范围改为 `config/project.json` 显式声明的项目文档。未复制个人技能；项目技能清单为空。
- 用户进一步要求：长期规范按整个系统编写，专项选择、临时条件和进度留在任务资料。
- Python 验证使用现有 `D:\workspace\qmt\.venv\Scripts\python.exe -B`，版本 3.14.6，仅执行本仓库维护工具；没有修改该解释器、QMT 代码、配置或其他工作树。工具声明支持 Python 3.10+，本轮仅实际验证该解释器版本。

本轮维护工具输入 SHA-256（文件尚未提交）：

| 文件 | SHA-256 |
|---|---|
| `scripts/project.py` | `937b2e23fb975932993a2c447dfb38c4724d5c94a889b0c661311ce0a6d2c708` |
| `scripts/project_support/skills.py` | `2daa7538b77f7245c936bccfe78f68199a32c84eb59f83f28fb03c4240b59d59` |
| `config/project.json` | `c93e7e176e7072dc9f114a8bbddef72b7272cee716914778e3c8abbfb8faa5f1` |

## 验证结果

| 步骤 | 实际结果 | 证明范围 |
|---|---|---|
| `python -B scripts/project.py start` | exit 0，显示任务路由及 NOW | 独立维护入口可执行，链接到实际正文 |
| `python -B scripts/project.py check` | exit 0，PASS | 本地链接、索引可达及空项目技能清单有效 |
| 隔离检查器行为：有效文档及上游稀疏资源 | pass | 配置文档范围有效，保持上游参考资料独立 |
| 注入断链、项目外链接、绝对链接、未索引文档 | 四类均明确拒绝；修复 fixture 后通过 | 错误路径有实际行为验证 |
| 长期规范范围审查 | pass，无专项词、机器绝对路径、日期或任务分支夹入 | AGENTS、开发规范、发布及故障规范面向长期系统工作 |
| 实际模块源码入口与职责人工核对 | pass | 接口、数据、策略、执行、回测及外部业务边界有据 |
| 维护脚本内存编译检查 | pass | 项目与技能清单脚本在实际解释器上可解析 |
| `git diff --check` | exit 0 | 已跟踪修改无空白错误 |
| `git diff --exit-code HEAD -- src` | exit 0 | 原生源码与原 HEAD 保持一致 |

隔离 fixture 和机器可读结果位于本仓库忽略目录 `.tmp/documentation-governance-checks/`；检查总计 12 项通过。本轮项目文档共 36 个 Markdown 文件（含既有专项材料）。README 保留上游内容与手续费说明，并接入新的规则入口。

完成后回写 NOW 与 CURRENT；没有创建提交、推送、标签、构建制品或触发部署。

## 证明范围

仅证明本轮文档组织、已核对源码入口、维护工具行为和静态完整性。新会话自动加载 AGENTS 的客户端行为、本地原生编译、SDK 和真实运行、功能验收、托管 CI 与发布均未在本任务执行。
