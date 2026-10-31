# 策略目录

类型：功能规格。状态：accepted。依据：2026-10-28用户要求参考旧QMT，仅展示策略名称、简介和版本。

## 职责与入口

`/strategies`默认显示只读策略目录，每条包含中文名称、简短用途和算法版本。2026-10-29用户明确只保留唯一共振策略的最新正式在用版本；沿[已核实来源](../evidence/2026-10-29-retained-resonance-latest.md)仅登记resonance-regime-v1@1.1.2，historical_versions为空。其他策略、候选和旧版本退出本次目录及运行/发行范围。名称和简介参考旧QMT的StrategyPage、strategyPresentation和策略definition。登记资料与宿主实际运行事实分别拥有，登记本身不授予运行资格。

搜索匹配名称、策略身份和版本。目录采用紧凑列表；页面提供单独的原生回测与报告tab，复用原BacktestWorkspace。旧`?tab=configuration`落入目录，`?tab=backtests`及`/backtests`继续进入原回测。

页面只读取`GET /v1/ui/strategy-catalog`。固定schema为`guanheng.strategy-catalog.v1`、read_only=true、scope=registered-definitions；响应仅包含strategy_id、strategy_version、display_name、description、historical_versions。额外query/body拒绝，响应no-store。读取失败支持手动重读；空目录和搜索无匹配分别说明。

参数编辑、证券映射、预算窗口、配置校验与保存从策略页入口移出。既有[SCW](strategy-configuration-workspace.md)后端配置校验、保存和恢复语义仍由配置owner拥有；后续配置操作入口另按用户授权确定。旧参数表单及验收原件保留为历史记录。

## 验证

实际HTTP返回只读目录，额外输入拒绝；页面展示名称、简介、版本，搜索与错误恢复有效，访问目录只发GET。默认及旧配置深链接均显示目录；切换回测仍进入原页面。桌面和390px窄屏分别检查排版、横向溢出、运行错误及截图。
