# 模块B：当前同核对照与原生状态加载

类型：隔离开发证据。日期：2026-10-29。结果：限定范围pass，模块B仍为in-progress。关联：[B-05/B-07](../migration/module-b-delivery.md)、[NRT-R11](../specs/native-realtime-strategy.md#nrt-r11-固定业务配置的受管python入口)及[STQ-P19](../specs/native-qmt-standard-trader.md#stq-p19-受管多策略产品宿主与干净停止恢复accepted开发中)。

## 当前a6回测与正式实时入口

入口为`tests/integration/qmt_cta_product/configured_backtest.py`。独立普通venv安装与R11相同的22个依赖，`uv pip check`通过；实际Appa10、corea6、NSQa1、SDK0.14。运行命令和完整日志在`build/ms-configured-bt-001/compare-003.log`，固定参数包括R11 DELIVERY摘要`98b1f02bc4664820add87bf89408165261f1f2c3c517c2780c0e31c91c1f1da2`、该交付的site-probe-001及原WtBtPorter绑定。

比较器先核冻结DELIVERY中的RT配置、DTO、业务观察和control原件；直接读取清单指定的python-binding路径。BT与RT七包完整源码集合、102个源码文件及合计110个site文件逐项匹配，关键实际导入路径和摘要在Host前后核对。原生基础资料复用RT的五份文件；回测仍由安装StrategyHost→原StrategyBacktestSession→原WtBtPorter执行，同一唯一纯核及NSQ承担算法和数量规则。

| 验收 | 实际结果 |
|---|---|
| B-07同输入/同核 | FrozenSessionInput字节相同；原生BT实际124次计算、1116根bar，最后记录与正式RT的17项算法字段（含input_sha256）一致；knowledge_cutoff单列 |
| B-07目标及成交模型 | 单策略BT原成交400+300，价格10，终态700，理论现金43000；RT两个策略各700，原净额买1400，价格10.01，各理论现金42993。两者NAV50000、PnL0；成交时序、价格及现金差额保留，不授真实收益相同结论 |
| B-04回收 | 原Host completed、exit0、pid_reaped及pipes_joined为true、forced为false；RT复用冻结R11的完整Job/来源/管道关闭原件 |
| 比较器身份拒绝 | 实际独立安装环境加入额外.py、额外.pyd、以及让已导入模块指向未绑定路径，三种均拒绝；探针文件删除、原模块路径恢复后重新核全集合通过。此边界案未启动原生运行 |

最终比较脚本SHA为`c7a3498bc0c4a9b7f53c8f18888944c2af0ad03c995ab72f2057501882ae5b8a`。原件位于compare-003：INPUTS为`3c653a09697247a3db368da84dcbceea802a44cbe8fa650a48605576c92380b1`，HOST为`f079a7bd32d695bd8e523c49e6543462d5c25bf6d8e5ef6fc917055b3aaafe47`，COMPARISON为`4fe9715b2bafe9ecd6dde1ed37e6e8ab11ea18af9b368cb9f742587609b45664`。BOUNDARIES-002为`d676796dea504b2c03f101af3d20d8596e693e349ece292a7e027dd3375296e7`。

独立审查发现并关闭源码集合/导入身份及control目录选择两个准入缺口。最终`build/ms-configured-bt-001/REVIEW.json`摘要`36736f7400a3ec2195baf7a352e7bc86cb3a5cae03c0821a99e55d41ba0a2bc1`，绑定最终源和上述原件。compare-001/002保持历史证据，最终资格使用003。

## B-05原生已有保存与加载

`tests/integration/qmt_cta_product/native_state_load_probe.cpp`直接链接P20构建的固定WT静态库；通过原engine.init→load_datas、原context.on_init→load_data/load_userdata加载此前filled-late-006正常停止文件的副本。探针不启动ticker、执行器、Trader或SDK，不调用持仓setter，也没有显式最终保存。组合观察从原加载后的内存只读取得，避开getFundInfo隐含的保存副作用。

`build/ms-native-load-002/OBSERVATION.json`实际得到A目标800、B目标400、组合1200，用户变量installed-owner分别A/B，原PnL及费用均0。进程exit0，原engine.stop返回成功。原件全部文件摘要保持；副本stradata/userdata/portfolio中的既有JSON摘要保持。原init会处理普通输出文件，因此副本全部输出字节未作不变承诺。OBSERVATION摘要`160f494a1b283ff1728c4883883608d7880c3bf7e600d3a5b85997f9c198cceb`，RESULT摘要`651ef535011bf8dd0c5026e6f91f3a798502e308e8e086ce16649ba76ed3145d`。

构建核对P20原composed清单时，唯一差额为未参与此探针编译/链接的native_realtime_strategy/synthetic_parser.cpp；RESULT明确记录原清单及当前摘要。WT与工具/公共头保持清单身份，实际链接库摘要、编译命令及新探针二进制摘要均登记。没有重编或改写WT核心，也没有覆盖旧构建原件。

该实验确认这一停止样本的原生保存/加载足以恢复上述值。B-05产品恢复仍需同根两代正式宿主、活动订单与全实例未知/未决责任核查、标记消费及异常窗口验证；当前产品仍拒绝已有状态根，recovery_ready保持false。[最终保存入口](../migration/native-clean-state-flush-proposal.md)的必要性继续待业务证据，审批请求保持撤回；[行情串行提案](../migration/native-cta-event-serialization-proposal.md)保持撤回。

独立原生加载审查`build/ms-native-load-002/REVIEW.json`摘要`112c2b7915debca0898d75100b04d226a837ae1f88d89969f399ebc9165658d7`，核25份原件、15份非系统链接库及原加载调用链。enum_position(true)返回信号覆盖后的目标，并在该进程内把信号标为triggered；未持久化此标记，也未据此声称逐项恢复全部开仓明细。副本只有两份rtchart改变，金融JSON保持。

## 限制与后继

本轮BT/RT输入为冻结合成数据、fresh现金ETF/T+0/零费用，原状态加载实验为另一份既有合成成交样本。真实资金、T+1、非零费用、所有保留策略、正常/异常产品恢复、完整委托结果及统一安装/App接线继续推进。未操作QMT界面、执行真实下撤单或发布。

A后继真实数据交付为`build/qmt-prepared-data-delivery-127/DELIVERY.json`（摘要`63d7295f1b2f7c5e9da2d5543c7f9d4faf7276b7d43818fbf56b54b5b626a7c8`）。共同401交易日九ETF齐全，实际OHLCV单位及时间边界见[源资格](../modules/qmt-source-qualification.md)。历史首次可知时间未知，本次实收为2026-10-29T01:23:25.163+08:00；后续真实日末模型回放须明确模型假设并保留实收身份，严格逐时点模式继续按原规则准入。当前比较不宣称已消费127或授真实来源资格。
