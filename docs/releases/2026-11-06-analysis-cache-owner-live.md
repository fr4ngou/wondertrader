# 2026-11-06 分析读取与日线补齐职责分开运行

类型：实际配置发布记录。状态：已采用，真实窗口和原账回读通过；自然市场调度继续验收。

## 根因与正确接线

全市场日线011已发布11月5日r003及真实缓存，分析发布器009仍每五分钟执行可选HPR准备。08:33第一片159780.SZ的原请求b790e860-5444-5b0f-911e-11f000301a33返回preparation_unknown；完整结果已持久保存及consumed，但可选准备继续等待该未知，后续只读捕获被串行挡住，最后成功窗口停在08:28。

部署沿已有可选配置省略history_preparation，日线服务继续唯一负责缓存补齐；分析发布器读取真实缓存、因子及基准参考并执行原年龄/共同日期/原生全值核验。原未知结果保持未知，原slot和SHA完整保留，没有重发该请求或伪造完成。缺失缓存仍按真实缺口表达。代码、WT框架、二进制、账户、策略公式和金融根均保持。

## 实际采用

新producer根为analysis-window-010/producer，原发布文件analysis-window-009/current-window.json保持；Native Reader的status/source_root显式绑定新根。采用既有prepare_transition与resume_reconciled恢复入口，原financial-state-008、100万元含持仓基准、现金及可用资金接续。现行服务为unified-analysis-service009-role/activation010/service.json，配置摘要30e4ada220664fb1487864167b823d319cc388be547b62616364e225f91c8474，WT40220/Native75496，控制代b6a682d5-4033-4b0c-9384-c456fa66f386。

第一次只改bootstrap后调用重启入口，服务按既有恢复合同继承前代运行配置，仍启动原009分析配置。逐项核实际generation后确认未采用新配置，正常停止该过渡代，再按显式升级入口准备Reader与原账transition，备份稳定CURRENT后采用010；过渡代及原件全部保留。该次误用没有改变策略或金融事实，通用检查已加入发布规范。

09:01:14实际取得新来源，09:02:51原Native/QNA核验后发布9268行、基准11月5日；第一轮新增补齐请求0。09:03正式观衡策略接口资金资格通过，原基准、现金及可用资金与切换前相等，未知原件SHA相等。其他五个角色PID及创建身份保持，六角色真实ready。group023、稳定DEPLOYMENT、启动/停止快捷方式均已更新。

按本代09:00:40真实进程起点核五个唯一日志系列，均实际记录启动/ready，新增未解释失败事件0；两个分析Host共享同一系列，按路径去重。原Native有限作业日志与全系统旧wrapper覆盖分别保留，不能据五系列声明所有角色均已升级。实际LOG-CHECK.json留在本次QA目录。

本次正式分钟恢复的后继结果也已取得：16只指数逐项公开回读240根、量额非负，SSE.000820官方历史仍空，原件保持。见[分钟发布](2026-11-06-minute-counter-quality-live.md)及QA的ROOT-PUBLIC-COUNTER006-SETTLED.json。

## 证据、回退与范围

现场证据在E:/workspace/wondertrader-qa/analysis-cache-owner-20261106-001：BEFORE.json、ADOPTION-INPUT.json、PREVIOUS-STOP.json、ADOPTION-RESULT.json和POSTFLIGHT.json。原未知结果位于原producer009捕获目录；冻结槽的SHA与新代回读匹配。新自然行情观测位于natural-mainline-trigger-20261106-002，绑定当前真实进程，09:40到期；它不生成行情、计算、目标或委托。

回退需正常关闭010并确认进程退出，从最后实际Native正常准备原账恢复材料，再恢复009分析配置、Reader引用和操作组；原未知请求继续保持，不能据回退创建重复补齐。直接调用旧服务start会继承当前运行配置，应沿显式配置升级入口处理。

当前尚无本代自然m1计算/目标/模拟业务结果，后继真实收盘的辅助合并也待市场事件。用户新报回测/观察页面专项仍按主线发布后的顺序处理，进程ready与完整自动交易结果分别记录。

启动时新工作根尚无首份发布，原Native历史核对记录market_history_mismatch；09:02新窗口已发布，但尚无m1回调重新核对。该接续的实际结果继续交自然回调验收，当前不声明原生读取与模型目标已经闭合。
