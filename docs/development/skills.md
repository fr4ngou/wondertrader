# 技能与项目维护工具

设计观衡工作台、后台交互与金融图表时，可从[前端开源参考](observer-frontend-references.md)查找上游案例。

长期开发入口是 [AGENTS.md](../../AGENTS.md) 和[文档路由](../README.md)，项目的 `start/check` 命令可独立执行，不依赖初始化技能的安装路径。

项目只登记 `.agents/skills/` 范围内的技能，来源清单为 [manifest.json](../../.agents/skills/manifest.json)。用户个人技能、客户端插件缓存和其他仓库技能由其各自环境维护。

新增项目技能先核实来源、许可证、维护所有者及适用范围。local 由项目维护，upstream 固定仓库、完整提交、原路径及改动说明；通过 `python -B scripts/project.py skills record --sources <来源文件>` 登记，再执行 `check`。登记摘要只证明文件一致性，来源可信性需实际调查。

本工具根据 [project.json](../../config/project.json) 确定文档检查范围，支持 `start`、`check` 和技能清单维护。保留维护工具的[许可](../../scripts/project_support/LICENSE)，本地适配的源码和验证记录随版本管理。

可选字段 `document_snapshot_limits` 将仓库内快照路径映射为正整数 Unicode 字符预算。`check` 对这些当前快照额外核对体积和日期流水；普通文档及历史归档继续沿原链接、导航和技能清单检查。格式规则、事实复核及历史保留见[当前快照维护](documentation.md#当前快照维护)。

`python -B scripts/project.py start`默认输出文档导航及NOW最近三条状态，每页正文至多6000字符，并明确提示省略正文。按任务沿显示的路径读取相关章节；追溯需要完整入口输出时使用`start --full`。摘要仅控制入口输出量，原文、历史和`check`的完整文档检查范围保持。
