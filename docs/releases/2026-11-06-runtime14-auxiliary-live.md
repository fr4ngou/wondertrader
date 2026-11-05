# 持续辅助数据与策略诊断运行版

状态：deployed / 部分验真。时间：2026-11-06北京时间01:30。范围：用户已确认的无真实资金模拟柜台及自有WT适配；观衡独立运行。依据[SDO](../specs/strategy-data-and-observability.md)、[整体实施方案](../migration/mainline-data-observability-20261105.md)。

## 发布身份

源提交6b88bc1，注释标签deploy/runtime-14-4-auxiliary-diagnostics-20261106。[永久源码闭包](../../apps/wt_runtime/source_closures/0.1.0a14+auxiliary.diagnostics.fees.4/README.md)固定46成员。Runtime wheel SHA为ddc35d76cf816b96e3fe4bf00fd69f23196c49722e3eae01ef2b069a0cd93d5a。安装位于`E:/workspace/wondertrader-data/runtime-service-20261105-018/venv`，23包依赖兼容。

同时采用V1a12、AWP auxiliary.3.integrated.1及QNA resonance122.diagnostics.1。14.4只在14.3之上增加EFR-22的同业务策略实现升级；Core、NSQ及解释器仍逐件相同。实际前后源码绑定、两项根因回归及独立delta审查通过，WT框架与Native安装保持。计算及费用源码未再变化，复用[完整原生回测证据](../evidence/2026-11-06-integrated-auxiliary-diagnostics-backtest.md)。

## 采用与原账保护

新analysis-window-009经真实QMT共享内存、原Native产出9268行后，正常关闭交WRI接管。auxiliary-live-009持续采集，旧官方原件作为只读种子，6736条官方快照固定摘要导入。QMT内置来源优先及字段核查见[来源研究](../evidence/2026-11-05-qmt-auxiliary-api-research.md)；原件实际实收时间保持，历史未知不倒填。

原WRI40320/Native47348正常关闭。financial-state-008、100万元含持仓基准、周期及订单责任保持。新service为`strategy-capital-real-20261102-001/unified-analysis-service008-role/activation008/service.json`，操作入口登记group019和wt-service/DEPLOYMENT.json。

首次切换误用了测试ProcessJob启动器，父命令结束时结束了新WRI进程树。该代停在waiting_source，未创建Native。核原clean未消费、全部已记录PID退出及三个金融状态摘要未变后，保留原记录，通过正式入口恢复同一bootstrap。未生成伪关闭证明、未重置账本或重发委托。原始失败与恢复证据为QA的RUNTIME14-ACTUAL-ADOPTION002.json、RUNTIME14-BEFORE-NATIVE-RECOVERY.json及RUNTIME14-ACTUAL-START003.json。

## 实际验真

QA根：`E:/workspace/wondertrader-qa/current-day-20261105-001`。最终结果为RUNTIME14-ACTUAL-POSTFLIGHT.json，操作入口为OPERATOR-AUXILIARY019.json。

| 调用链 | 实际结果 |
|---|---|
| 运行及执行 | 正式启动命令结束后WRI41052、Native49624真实存活，execution_ready=true；控制代be3bc2bd-78bc-4d5b-8ab9-ad5df9e4f560，Native代8f6f118d-0a83-4610-a2f4-4a7e63cb869f |
| QMT | 签名trade-status为200，hard_fault为空，无未知命令栅栏；沿原用户确认账户，未换账户。协议environment=live表示该接口模式 |
| 策略资金 | 新券商查询合格；现金/可用现金452011.10元、市值550090.70元、净值1002101.80元，原基准100万元 |
| 持续分析 | 恢复首轮后完成第2次真实发布；基准日11月5日，9268行，历史快照无错误。后继source_pending沿原ID续核并保留上一成功发布 |
| 独立观衡 | 18143的strategy-runtime读到ready、合格账户和452011.10元可用现金；wt-instances返回六角色ready；进程2772保持原版本 |
| 新日志 | Native及TradeHost的process-events.jsonl实际落盘started/ready，本次检查无process_failure；系列预算1MiB当前文件和3份轮转，队列有界 |

## 剩余与回退

策略仍为waiting_market_input / awaiting_first_strategy_calculation，sequence138来自恢复。非交易时段尚无本代自然计算→目标→模拟执行结果。辅助资料于11月5日收盘后取得，首次后继收盘生效须以真实11月6日行情确认。ready及此前成交不代替本项结果。

还需独立发布观衡新报告读取器、核全市场日线/资料余缺，并在完整在线验收后清理无引用工作树和产物。当前无新增用户决策项。

回退先正常关闭并核金融状态/未决责任，再生成当前→旧环境的显式兼容交接。V1a12回退至旧V1a10须由对应恢复实现支持，不能直接改CURRENT重放旧transition。原正常关闭代、制品、原件及基准均保留。
