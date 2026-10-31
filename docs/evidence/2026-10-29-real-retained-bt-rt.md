# 真实分析窗口的原生实时首目标与回测比较

类型：模块B验证记录。结果：partial。关联NRT-R18-C1/C2/C3/C4、B-04/06/07。真实行情历史与模拟执行分别标明；完整实时运行、全周期比较及模块B继续in-progress。

## 当前结果

A最终八ETF的401共同日期、3208条原价和3208条前复权分析记录进入B安装后的正式实时入口。原Helper生成隔离DSB、原Reader逐值读取、原CTA调用唯一1.1.2核/NSQ，首轮形成完整八目标，经原StockMinImpact/标准Trader/真实WinSHM完成四笔SDK替身买入。

同一普通安装下，C正式RetainedBacktestSession调用原WtBtPorter，以相同资料、实际配置、初始flat、策略理论本金和费用预留运行末日一次计算。完整14个非来源字段相等，包含完整model_decisions及allocation_state；完整EconomicTarget和八证券数量目标相等。BT完整结果重算摘要与原报告相符，RT完整结果按其原券商观察和实际截止重构后逐值相等。

RT后继观察仍为初代空仓revision1，源端补充P查询已返回四行。源查询完成、原身份解析/SPI应用及公开观察发布是不同完成点；当前证据尚未确认后两点完成，不能据此断定公开缓存失效。运行后出现`qmt_host_native_operation_failed`，最终exit2；该场景保持失败，当前没有完整RT成功资格。

## 固定输入与安装

原件根：`build/ms-real-retained-001`。

| 输入 | 身份及范围 |
|---|---|
| A最终分析窗口 | `build/qmt-native-adjustment-module-001/main006/ANALYSIS-WINDOW.json`，SHA256 `a38386d74bda91da91cc9669ffde734cb69ba50f4d06427fe27038e0ff857859` |
| C冻结回测输入 | `build/retained-real-analysis-003/SESSION.json`；实际六参数/预算来源沿C原材料，本轮不改原参数 |
| 新Python安装 | `INSTALLATION-001.json`，SHA256 `cf245fd7a492f3c3e4922acc5bf7f1cea668b66236805c53a7fb71a80fabcd85`；C已审Appa26加恰好三个B execution文件，29发行、4731条hashed RECORD、pip check通过 |
| wheel到实装 | `WHEEL-PAYLOAD-001.json`：5个私包共139个成员与实装逐字节相等，安装器拥有的RECORD单列 |
| C消费边界 | C `build/strategy-runtime-view-001/DELIVERY-001.json`，SHA256 `ce6c7bb7abd7c1462426b6bfab57e5414bd4366fc1e46eb951ac38cf494ee05f`；本轮只验证B原生消费及BT，整个App/HTTP/SPA资格保持各自原件 |
| 原生实时库 | native004 Runtime SHA256 `a902bcc989f9881e7eb9309beac176dfb0d38ef6e71415691859f89ea281283d`，固定原WtExeFact保持；B生产源码与[R18/P24冻结](2026-10-29-retained-cta-and-close-boundary.md)相同 |
| 原生回测库 | 原WtBtPorter SHA256 `4726fdb9c48d32ec46fe0793eabb23d120aec8a536dc8dc140b57b636b533b2e`，ABI probe SHA256 `a7fdb6ecd763ebdd395d4b0d11d78a1f6d30bbb57f23a63630c2410c243b71b6` |

`input-007/INPUTS.json`绑定源SESSION及A资料。C序列化会显式输出可选空字段，QA通过同一公开RetainedInput比较完整history/analysis DTO；OHLC、前复权、单位、source/factor revision及实际known/received时点保持。只更新明确模拟flat观察的当前截止/有效时间，价为CNY/share，历史成交量保留lot，金额unknown。严格当前视图预检通过。

实时tick价格是该批真实raw末日收盘的明确回放，分钟事件、基础资料、flat账户、资金及成交均为模拟。策略理论本金120000和reserve20沿C显式模拟policy，券商替身available独立为82000，未模拟成交后的账户资金扣减或完整费用对账。不得将它解释为真实当前账户或全真实实时行情。

## 运行、差异及失败原件

| 原件 | 观察及结论 |
|---|---|
| prepare-001 | 字面JSON比较遇到C显式可选默认字段失败；未进入原生。改为同一公开DTO比较完整源值 |
| main-002 | 原日线夹具仍限125根，读取401根时在bars入口失败，SDK0；上限现沿冻结输入容量配置 |
| main-003 | 生成真实资料首目标，夹具等待买入前没有送新tick；保留失败，不计委托成功 |
| main-004 | 转储观察下进入一笔替身买入，后继HTTP交换失败；Host/Source协议关闭未确认，物理资源关闭及server/proxy join为true。观察开销与首因尚未完全分离 |
| main-005 | 撤掉转储后完成四笔买入；新夹具给多单复用了broker.1，原映射失败。后继改为每单独立券商号及成交ID |
| main-006 | 四笔买入，首后继理论converged但公开券商观察仍初代空；QA过早要求新周期等待而失败。后继继续原调度等待公开事实，不把source查询返回当成SPI应用证明 |
| main-007 | 当前Appa26/B安装：6次源查询、4笔SDK替身买入，四份决策公开券商P均revision1/空；源端P补查四行，后继原操作失败/exit2。未完成新周期等待或整链关闭资格 |
| bt-001 | 旧Appa23回测尚未接受lot单位，构造阶段拒绝；未运行原DLL。消费C已审Appa26能力后保留原lot单位继续 |
| bt-002 | 当前普通安装→C正式Session→原DLL，末日单次回测及14字段/经济目标/数量比较通过 |
| bt-003 | 为绑定外层资源原件重验同条件，比较再次通过；原回放内部release/7输出核验，外层Job/EOF/join事实已采集 |

已完成的bt-003使用`native.run`隐藏独占Job；`BT-OUTER-CLOSE-001.json`通过只读profile采集返回帧白名单事实：实际root exit0/reaped、Job树归零、reader join、EOF、资源关闭、resume前已入Job及已resume均为true。辅助函数行为保持原状，报告绑定helper/driver SHA。该原件与C内部finally release分别验证。

main-002/003/005/006/007的Host关闭、Host资源关闭、Source资源关闭、Source关闭确认、HTTP server及proxy join六项均true；main-004两项协议完成为false，保留命令及异常原件。所有已执行外层调用均终态，本轮真实下撤单0、新WT源码变化0。

## 比较范围与剩余工作

`bt-003/COMPARISON.json`逐项比较所有14个非provenance字段，完整模型决策/分配状态也在其中。7项schema、input_sha256、decision_cutoff、current_view、historical_model、source_qualified、execution_qualified分别保留BT历史模型与RT当前视图的原身份；两者整个wire输入与资格声明不同。此次只证明同资料/flat/配置/预算的末日首目标一致，没有改写完整同输入、全周期或持仓周期验收要求。

当前已补真实资料消费及末日首目标比较。下一步沿source补充P结果→原身份解析/原SPI→Adapter→公开观察的同命令链核对完成点，再连接有依据的实际新开仓周期。当前股票完整关闭、异常责任恢复、完整全周期BT/RT及统一系统候选继续；股票引用故障沿原审批边界单列处理。

独立审查、最终文件SHA、语法/文档检查及原件清单由同根`DELIVERY-001.json`绑定。新验证源码只在B专用QA目录，没有新增金融账本、复制策略数学实现或改C生产模块。

三份验证源码语法检查通过。文档检查前两次外层调用分别在45秒、120秒超时，保留原日志及第二次完整回收收据；第三次同一`project.py check`入口增加只读故障栈定时输出后exit0，日志明确本地导航/技能清单检查通过，未触发故障栈输出。该静态检查覆盖范围及既有超时均保留在`CHECKS-003.json`，不作为实时业务成功证据。
