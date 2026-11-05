# 独立观衡报告读取版114

状态：deployed / 报告与账户API已验真。时间：2026-11-06北京时间01:54。范围：已开发报告读取适配的独立发行；本次用户截图中的市场观察慢、数据未自动更新及页面长期加载，按用户要求待主线完成后专项处理。

## 源码及制品

提交3e6f5a4，注释标签deploy/observer-a114-diagnostics-20261106。App为0.1.0a114+diagnostics.1，V1读取版0.1.0a7+resonance122.diagnostics.1、WT读取版0.1.0a11+read10.diagnostics.1。按[OSB-R7](../specs/observer-source-build.md)采用已验纯模型和五个报告读取模块；控制/生命周期及report_values性能实现保持。独立delta源码核查无阻断，元数据、锁和V1来源声明一致。

从永久源码离线构建，31包普通安装及依赖检查通过。ZIP SHA256为8493180ac587d0a06feb210765c2a80e002194bedad2fce20470021a8038db4e，制品manifest SHA256为049673bc0baa83263e2b4bf6c98ad173fee4751015e3c40a152572d984b00402，安装收据SHA256为e543a6aca33a44c361c6dfdca8019d14cf8fb6774a501206c31ac080fc30e91d。新安装为`E:/workspace/wondertrader-data/observer-programs/a114-diagnostics-20261106-001`。来源和配置由原构建/安装清单逐件绑定，未读取运行环境源码构建。

## 完整读取与独立采用

普通安装实际读取本轮404/401条新归档及三份旧报告的配置和末条，新报告的绩效也通过。随后将两份原生已完成run逐字节发布至WT正式回测根，原始完成收据及全部源文件摘要保持；旧三份报告的84个文件逐件未变。

旧观衡2772正常关闭，exit0、读取线程归零。通过正式独立维护入口启动新观衡76596，控制代027c7739-9314-4e09-b768-af2a4be660f7；启动命令结束后真实存活。稳定web-profile及DEPLOYMENT更新，地址保持18143。个人观察、市场观察根、WT连接和其余外部配置值全部保持；WT及QMT未启停。

线上正式API实际返回5份归档、invalid_receipts=0，目录约0.11秒；两份新报告配置约3.2秒、绩效约1.4秒，诊断可用。策略资金查询合格，实例接口返回六角色ready。该结果证明已发布模块的API调用链；用户截图里的页面加载及观察自动更新根因仍待后续核查，不把它们统一归因为未发布。

## 记录、回退及余项

QA根为`E:/workspace/wondertrader-qa/current-day-20261105-001`，普通安装验证OBSERVER114-INSTALL-READ.json、正式归档发布和配置OBSERVER114-PREPARED.json、线上结果OBSERVER114-ACTUAL-POSTFLIGHT.json。旧配置与部署元数据分别保存在OBSERVER114-PROFILE-BEFORE.json及OBSERVER114-DEPLOYMENT-BEFORE.json。

回退先正常停止114，使用保留的113配置/程序恢复，WT保持独立运行。113缺少新诊断读取资格；新原生归档与旧报告继续保留，不修改收据使旧版准入。

主线已开发模块的代码发行均已完成。本代自然计算→目标→模拟执行和真实后继收盘的辅助生效仍待交易时段，整体目标保持active。页面专项及最终无引用产物清理继续按主线顺序推进。
