# 中文操作员材料与安装入口核验

类型：文档及接口形状验证。状态：done（当前手册入口与四CLI help）；全系统安装/升级演练继续。手册正文为[观衡中文操作员手册](../runbooks/guanheng-operator.md)，配置格式沿原组件手册，资格沿[COP](../specs/guanheng-operator-platform.md)和[模块C交付](../migration/module-c-delivery.md)。

材料覆盖独立安装/启动、总览/行情/账户/策略资料/回测比较/市场观察、09:00更新解释、停止/恢复和升级回退。策略资料保持名称/简介/版本，实时隔离维护和配置服务职责分别说明。全系统统一安装器、实际升级恢复和生产切换继续保留待验状态。

使用provider-completion当前普通安装解释器，原native.run/private_console/20秒有限预算，实际执行-I -X utf8 -B -m的guanheng_app、backtest_cli、execution_process和observation的--help。四入口均exit0，实际参数与手册引用相符；证据在build/operator-materials-001/*-help-002.log及HELP-VERIFIED.json。文档本地导航检查通过。

首次工具配方把观察命令误写为adopt，实际已安装命令为import-frozen/restore；旧工具源码及日志保留，后继按真实restore核验。首次-I输出沿Windows本地代码页，002增加-X utf8后原UTF8日志可读。该变更只作用于QA解释器命令，产品和运行实例保持。

本轮审查范围为none：手册汇总既有已登记流程、参数和资格，未修改公共接口、持久状态、权限或恢复行为；四个安装help和文档检查只证明入口形状与链接，业务资格分别复用其原证据。整体模块最终独立审查仍需覆盖统一候选的实际操作。
