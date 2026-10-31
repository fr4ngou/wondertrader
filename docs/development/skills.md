# 技能与项目维护工具

长期开发入口是 [AGENTS.md](../../AGENTS.md) 和[文档路由](../README.md)，项目的 `start/check` 命令可独立执行，不依赖初始化技能的安装路径。

项目只登记 `.agents/skills/` 范围内的技能，来源清单为 [manifest.json](../../.agents/skills/manifest.json)。用户个人技能、客户端插件缓存和其他仓库技能由其各自环境维护。

新增项目技能先核实来源、许可证、维护所有者及适用范围。local 由项目维护，upstream 固定仓库、完整提交、原路径及改动说明；通过 `python -B scripts/project.py skills record --sources <来源文件>` 登记，再执行 `check`。登记摘要只证明文件一致性，来源可信性需实际调查。

本工具根据 [project.json](../../config/project.json) 确定文档检查范围，支持 `start`、`check` 和技能清单维护。保留维护工具的[许可](../../scripts/project_support/LICENSE)，本地适配的源码和验证记录随版本管理。
