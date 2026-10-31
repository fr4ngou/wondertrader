# A8 离线六组件真实只读准备

日期：2026-10-30。规格：[WRI](../specs/independent-wt-runtime.md)、[NAP](../migration/native-account-publication-proposal.md)、[来源回调驱动](../specs/qmt-source-runtime.md)。

本准备使用 `root-source-wait-001/release003/installed001`：WT a8、Host a9、Agent a8，SYSTEM-INSTALLATION SHA `057752dbae580caf3ba9769f582fd318b8e27069db944a291e4ee917cc60ff81`。账户工具、QST/HPR/历史入口与 Reader/Writer 均从本离线包解析，独立观衡沿已接收 a45 安装消费 NAP 原发布。配置包含六 owner，execution 缺席，双端 writes_enabled=false。

可用准备位于 `build/wt-final-real-read-002`。其新配对、正式四 owner 单正文、六组件配置和9372项运行输入已生成及冻结。原安装 WT pythonw 隐藏执行 check-only exit0，业务 owner、来源请求、真实委托和撤单均0。`DEPENDENCIES-001.json` 沿实际配置核20项入口及2个包内原生工具复制身份，包含外层与实际 fallback 的 base.native_reader；核验只读文件，没有构造 NativeSourceMarket 或查询来源。

根统一执行现场，按 ROOT-READY-001 和 ROOT-OPERATIONS 使用原600秒总截止、65秒晚来源和120秒页面预算，负责 Probe 原文备份、启停、恢复与页面实际见证。准备阶段未操作 QMT、原策略文件或旧活动服务；真实运行、账户原值、页面、新分钟持久化和归档资格由后继实际证据确认。

历史材料保持：release002 缺原生账户工具；`wt-final-real-read-001` 的初始准备漏改嵌套 base Reader 路径，现场可用资格已撤回，根确认协调器与 Probe 从未启动。002 在新目录修正准备配置，产品、WT框架、预算和权限没有变化。
