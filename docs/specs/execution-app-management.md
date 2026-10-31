# App托管原生策略执行进程

类型：历史功能规格。状态：superseded（进程所有权部分）。前缀：EAM。原App托管WT执行的方案由[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)和[WRI](independent-wt-runtime.md)取代。以下保留已实现入口与原验收的身份；可复用进程适配迁至WT独立运行包，观衡只读消费运行结果。原EAM-R3/R6的数据语义继续适用，消费者改接WT侧公开接口；App生命周期不再承担执行启动或关闭。

## EAM-R1 显式部署与职责

默认关闭；维护人员显式提供GUANHENG_EXECUTION_CONFIG及GUANHENG_EXECUTION_CONFIG_SHA256。父部署JSON schema=guanheng.execution-app.v1，精确字段为schema、installation、installation_manifest_sha256、configuration、configuration_sha256、control_root。路径均Windows本地绝对路径，控制根预先建立于E盘；部署文档上限16KiB，内容与来源摘要一致，重复/额外字段拒绝。加载绑定execution-install.json和原生配置原字节，消费B的唯一ExecutionProcessConfig.load；加载前后绑定摘要及实际artifacts集合保持一致。启动仍由原ManagedExecutionProcess复核工件/配置；无新监督者、动态loader或交易账本。

App只消费显式部署；SCW保存配置与此部署分别拥有，浏览器不提交路径、不自动激活配置。实现及本次实际验收只启动明确隔离的SDK替身场景。真实券商写、生产启用和核心行为变化仍按原明确授权执行，安装清单或进程ready不授这些资格。

## EAM-R2 启动关闭

App在启动前发布execution_process owner，复用现有BoundedReader和_start_process绝对截止；Host/采集/来源先启动，再启动执行进程，配置错误保持其他能力可用。启动失败/未知保留原owner，不自动换身份重启，一个App生命周期最多一次。

所有owner共享一次关闭截止。先关读取消费者及任务准入，然后执行进程，再关闭来源、采集与账户Host。按各原owner声明停止窗口预留预算；单组件关闭失败仍继续关闭其他已发布owner。执行关闭纳入shutdown_complete及CLI成功/失败归约，保持原Job/EOF/join/未决责任。正常关闭不授自动恢复，已有状态根继续沿B规则拒绝。

## EAM-R3 只读状态

GET /v1/ui/execution-process只读内存owner快照，无query/body。响应schema_version=guanheng.execution-app-status.v1，read_only=true、observed_at、process（沿OPS白名单）、configuration_sha256（无有效配置时null）、execution_qualification=not_checked、recovery_ready=false，no-store。ready中文解释为进程已启动，实际策略目标、成交、资金/费用/收益及恢复事实待B各自接口提供，不能推导。系统状态页独立显示执行进程状态及来源资格说明，刷新只读；策略页保持名称/简介/版本目录。

## EAM-R4 验收

父部署/原生配置/安装清单摘要与路径拒绝；默认关闭零Job、启动失败保留owner、部分构造失败和原总截止内关闭顺序/异常继续/CLI归约回归。正式App→B已安装原生产品→原Factory/CTA/组合/执行/WinSHM→明确SDK替身，核实际数量及资源回收；浏览器只读状态、错误/恢复与窄屏。App wheel/原生候选分开冻结SHA。当前验收不把B测试固定策略当迁入算法完整资格，不代替后继业务核、撤单/恢复及M1最终证据。

## EAM-R5 固定业务策略入口

2026-10-29沿B的[NRT-R11](native-realtime-strategy.md#nrt-r11-固定业务配置的受管python入口)补齐正式App接线。父部署v2使用schema=guanheng.execution-app.v2，包含R1全部字段和必填runtime；runtime只允许native或configured-python。v1保持原字段集合及native语义；任一版本额外字段或未知runtime拒绝。加载分别调用B唯一ExecutionProcessConfig.load或PythonExecutionProcessConfig.load，核同一安装清单/原配置及前后摘要；Python额外解释器/完整源码集合绑定继续由B负责。

App依据已准入配置的确切类型选择ManagedExecutionProcess或ManagedPythonExecutionProcess，沿R2同一owner发布、一次启动、绝对截止、失败保留及关闭顺序；默认关闭不触发Python安装扫描或子进程。固定业务输入由B原配置拥有，页面不提交运行脚本或路径。WT能力复用WT-S01/S02、WT-T02/T03及WT-O01/O07：原CTA/Factory/Local/Adapter承担策略/组合/执行，App只补部署分流，不增加算法、订单或金融状态owner，不改WT核心。

验收先覆盖新安装App→原B正式固定业务子端→原ticker→同一configured核/NSQ→实际隔离SDK结果及下一轮收敛，并核公开HTTP/生产SPA与原总关闭链。新旧入口分别验；未知profile、安装/输入身份错误保持B原拒绝行为，异常状态页面读取/恢复沿R3。合成输入、真实来源日末模型、严格可得时间、账户和恢复分别登记，入口接通不提升数据或交易资格。

## EAM-R6 策略业务结果只读消费

C在B的ManagedPythonExecutionProcess之上提供只读观察子类，沿原owner私有控制目录读取B已发布的guanheng.configured-cta-observation.v1/strategies.json。B的运行桥、发布格式和状态持久化保持原所有权。只支持唯一1.1.2 profile；不扫描目录、不接收浏览器路径、不从历史文件恢复运行状态。读取前后核原owner控制身份、配置摘要、pid及ready状态，并调用原ready收据校验；文件沿原受控读取器，最多4MiB，读池排队和读取共用2秒绝对截止。

GET /v1/ui/strategy-runtime仅接受GET，无query/body，no-store。返回guanheng.strategy-runtime.v1、read_only、observed_at、state及strategy。默认关闭或原生入口未提供业务发布时strategy=null；已配置且尚未发布时waiting。成功结果只投影固定中文名称、版本、原状态的中文解释、原决策时间、原理论持仓/可卖/未决绝对目标、本轮策略目标比例、原数量阶段目标及宿主券商查询的数量/可卖和原接收时间。数量均为股/份；比例由唯一核原值提供。未决目标、数量阶段目标、券商持仓和最终经济目标各自区分；目标与原setter读回不能解释为成交。券商positions_known=false时数量为null，完整已知且无该证券时为0；不将理论持仓补入券商事实。策略名/简介/版本目录保持原范围，运行结果置于总览独立卡片。

读取失败、超时、文件身份变化或停止竞争返回固定中文503，公开响应不包含原文、路径、哈希、会话/代际或算法明细。总览运行卡与账户查询并行、局部失败分别展示；同App查询刷新中/失败保留上次成功结果及原决策/读取时间，成功空响应清除旧值。正常、未知周期/陈旧券商状态、成功空、失败/恢复和停止竞争分别验。冻结B自有桥输出仅证明消费者合同；最终M1仍需B正式原生运行与A真实同基准历史合并验证。
