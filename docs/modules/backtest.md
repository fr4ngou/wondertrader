# 回测与模拟

类型：模块说明。所有者角色：回测维护者。状态：原生回测源码已存在；具体模型适用范围按测试登记。

当前运行职责沿[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)：独立WT包负责回测进程和原生运行，观衡负责只读报告消费。[NBC-R5](../specs/native-backtest-cli.md#nbc-r5-独立wt运行侧回测)的唯一正式1.1.2入口为[backtest_cli](../../apps/wt_runtime/guanheng_wt_runtime/backtest_cli.py)，经独立[strategy_host](../../apps/wt_runtime/guanheng_wt_runtime/strategy_host.py)、runner、[retained_replay](../../apps/wt_runtime/guanheng_wt_runtime/retained_replay.py)及Porter进入原WtBtPorter；安装绑定由[backtest_installation](../../apps/wt_runtime/guanheng_wt_runtime/backtest_installation.py)复用同一运行验证器生成。普通六发行安装已完成400次闭合与原生输出验证，见[独立回测证据](../evidence/2026-10-30-standalone-native-backtest.md)。原观衡路径及下文旧族工作区描述保留历史兼容依据，C只读迁移和全周期BT/RT比较继续验收。

## 职责与入口

负责历史回放、模拟上下文、撮合与成本模型，以及可复现实验输出。主要入口为 [WtBtCore](../../src/WtBtCore/CMakeLists.txt)、[WtBtRunner](../../src/WtBtRunner/CMakeLists.txt)；公共回放接口由对应核心接口及配置定义。

观衡适配通过原公开C ABI进入[WtBtPorter](../../src/WtBtPorter/WtBtPorter.cpp)，原生引擎拥有回放时钟、理论持仓、目标撮合、费用与原生输出。业务层接缝分工如下，运行资格按对应证据登记：

| 模块 | 职责与边界 |
|---|---|
| [策略纯核](../../apps/guanheng/strategy_core/guanheng_strategy_core/kernel.py) | 输入固定配置和因果行情前缀，计算完整策略结果；不持有原生上下文或调用交易接口 |
| [数量阶段](../../apps/guanheng/strategy_native/guanheng_strategy_native/planner.py) | 根据经济目标、明确资金/费用和同次实际观察推进数量阶段；不拥有持仓或现金账本 |
| [薄Porter](../../apps/guanheng/guanheng_app/strategy_porter.py) | 固定ABI、回调缓冲、线程及阶段约束，完整目标向量预校验和读回；保留原生数值，不自行推断actual/pending |
| [回测会话](../../apps/guanheng/guanheng_app/strategy_session.py) | 冻结前缀校验、限定模型事实采集、纯核和数量组合、完整结果表示；真实柜台事实不从本模块恢复 |
| [受管父宿主](../../apps/guanheng/guanheng_app/strategy_host.py) | 固定安装入口、独占进程及Job、一次总期限、有限输入输出和结果核验；正式产品资格仍需对应独审 |

接口要求分别见[NSK](../specs/native-strategy-kernel.md)、[NSQ](../specs/native-strategy-quantity.md)、[NSB](../specs/native-strategy-backtest-session.md)和[NSH](../specs/native-strategy-host.md)。这些模块组合原生能力，不另建撮合、行情数据库或持仓数据库。

唯一保留1.1.2沿[RR112-R5/R6](../specs/retained-resonance.md)提供[历史接缝](../../apps/guanheng/guanheng_app/retained_replay.py)。它使用显式最终批次假设和原userdata周期状态，完整八目标交原NSQ，撮合及资金归原CtaMocker。既有会话与新入口共用[strategy_replay_facts](../../apps/guanheng/guanheng_app/strategy_replay_facts.py)原值采集和基础资料准入。新报告族guanheng.retained-replay-report.v1与旧报告分别处理；受管runner/工作区消费者接入状态沿[限定证据](../evidence/2026-10-29-retained-resonance-replay.md)登记。

[HEM历史输入模型](../specs/historical-eod-model.md)沿同一纯核、原生回放和报告owner处理事后最终日线；严格逐时点可知模式继续保留。工作区与归档投影显式区分报告schema，现有回测页面显示来源/模型限制。实现及独立安装证据见[历史日线回测验证](../evidence/2026-10-29-historical-eod-model.md)。

V2按[NVB](../specs/native-v2-backtest-session.md)复用同一会话及宿主，输入/报告schema显式区分策略族；算法、信号轨迹及原始分配由各独立计算包拥有。报告准入核共享历史、每日边界和全部前缀摘要；公开完整重建与[工作区](../specs/native-backtest-workspace.md)轻量投影共用已准入不可变值。调用方check的截止/取消异常沿公开出口保持原对象，报告层只重新分类自身数据错误。

## 原生事实与生命周期

原CtaMocker的fund0为模型损益，业务NAV须以明确初始资本加该值派生；现金再扣同次实际持仓原价市值。目标、挂起目标和实际持仓各有语义，原生position枚举可能呈现目标，不能直接当作真实成交数量。会话中的actual/pending采集只适用于已验证的初始空仓、单上下文、现金多头、绝对目标setter模型；细节与例外由NSB限定。

一个子进程只承载一个原生上下文。owner线程执行原生调用和回调，借用缓冲在回调返回前复制；on_calculate读取闭合前缀，on_bar处理已交付值。callback异常锁存并阻止后续提交，callback内不执行stop、release或join。同步run缺少通用抢占中断保证，由外层父宿主以Job及期限管理整个进程；库保持进程期装载。

## 实验边界

冻结数据版本、代码版本、策略参数、证券规则、时区/交易日历、成本模型、随机种子（若使用）及回放范围。回放时钟是策略在实验中的时间来源，输入按当时可见性提供。

回测资金、理论持仓和模拟成交仅属于对应实验。撮合模型对涨跌停、流动性、部分成交、费用、复权和证券交易制度的覆盖逐项说明。策略计算复用程度与真实成交一致性分别验证。

## 验证与结果

逐角色输入覆盖、信号与不交易原因沿[SDO](../specs/strategy-data-and-observability.md)核实。正常结束和其他标的成交只证明对应范围；报告声明输入缺失和知晓时间假设。旧原件保留，新输入重跑生成新记录。

使用可人工计算的小样本验证撮合与成本，再对冻结样本做策略结果回归。覆盖预热不足、未来数据、跨日、数据修订、缺口及恢复。

结果与配置摘要、数据清单和已知模型限制一起保存；证据组织见[证据规范](../evidence/README.md)，运行命令见[构建手册](../runbooks/build.md)。

完整增长历史采用共享表示，各日保存完整前缀重建所需的当日字段和边界；展示读取按需重建，避免逐日重复保留整个累计结果。资金精确转换独立调用线程的数值上下文。空间准入发生在目标setter之前；超期、部分提交、原生未回收或结果身份失配保持不完整状态，不能以进程exit0或旧文件存在作为成功依据。

会话消费冻结输入，不在原生回调中请求数据源。QMT终端通信替换与回测模块分别推进：来源适配形成经验证的输入后才进入同一会话接口；通信决定不改变原生撮合或业务核。真实数据覆盖、模型适用范围、同核一致性和生产资格分别取证。

## 业务工作区

[回测业务owner](../../apps/guanheng/guanheng_app/backtest_workspace.py)接收受管冻结配置，只在独立线程调用受管父宿主。请求身份在当前进程epoch内复用，活动名额、线程、取消及完成确认由同一entry持有；未知启动与未确认关闭保留owner。运行目录和最终原生输出仍由父宿主拥有，业务层只保留有限展示索引及一份深不可变报告缓存，不建立新撮合或持仓事实。

HTTP及浏览器消费当页记录头、当日完整原生观察/数量阶段和核摘要；完整增长前缀经NSB公开重建接口按需读取，来源和模型资格同时呈现。部署文件、路径和安装身份来自服务器受管配置，用户请求只携带当前owner/request及有限分页选择。操作步骤见[回测运行手册](../runbooks/native-backtest.md)，接口见[NBW](../specs/native-backtest-workspace.md)。

## 完成报告的重启只读入口

[NBW-R6](../specs/native-backtest-workspace.md#nbw-r6-已完成回测只读归档)与[ADR-0012](../architecture/adr/0012-backtest-completed-archive.md)复用原UUID实验目录。BacktestArchive只拥有父完成receipt、有限只读目录及原件校验；Workspace取得真实最终HostResult/NSB准入后，在原请求D内落证。不会复制报告、引入数据库、重新执行或接纳无证明旧目录。GET历史配置/分页/详情复用现backtest_reader与唯一NSB投影；纯文件归档重试显式绑定当前owner/request，执行状态与归档资格分开。安装/源/实时/生产运行资格仍以匹配输入的证据登记，标准进程重启可读不授断电持久性。

当前归档恢复的端到端证据见[文件失败与页面重试](../evidence/2026-10-26-backtest-archive-retry.md)：同一实验经真实文件类型拒绝、页面显式重试及新App读取，原生回测只执行一次。专项脚本按固定安装身份受管运行，具体资格和未覆盖范围随证据登记。
