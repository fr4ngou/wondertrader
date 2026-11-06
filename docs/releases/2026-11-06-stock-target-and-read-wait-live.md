# 股票目标替换与读取等待修正版上线

类型：发布及实际业务记录。状态：已部署、同账恢复及独立读取通过；新代午休等待后继自然策略计算。核实时间：2026-11-06北京时间11:38。整体目标继续active。

## 修改及审批范围

用户明确批准[目标替换方案](../migration/native-stock-target-replacement-proposal.md)。CORE-012仅修改两个股票执行单元框架文件：缺省/false保留原行为，显式true接纳新的绝对目标，再沿原执行算法处理。当前正式配置为true，原Borrowed元数据引用、订单身份、资金基准及策略数学保持。42组公开工厂回放、Host准入及恢复比较验证见[证据](../evidence/2026-11-06-stock-target-replacement.md)。

自有Native补原WTSLogger的私有轮转日志，单代4份、每份1MiB，单条原正文8KiB；真实库落盘、轮转和写失败回归及宿主独立审查通过。另自有Standard在实际查询等待期间的组门与insert许可不一致，造成-2被收口为SubmissionUnknown，再转Owner Destination/Host Queue。仅inspect/begin复用原permits(Insert)，实际未知保护保持；Root补纯值故障旁证。WT框架没有因该读取等待问题新增修改。见[日志验证](../evidence/2026-11-06-native-runtime-log.md)及[等待修正](../evidence/2026-11-06-read-wait-submission.md)。

Retained行情插件沿已审精确开盘前形状跳过投递，后继有效行情继续原worker；首次只读绑定准备按固定原因继续等待。原请求、结果和消费保持，见[解析器证据](../evidence/2026-11-06-parser-preopen-startup.md)。

## 制品及实际输入

源码提交862195d包含已批准目标修正及日志，4272c31包含自有读取等待修正；标签为deploy/stock-target-replacement-20261106及deploy/standard-read-wait-20261106。Runtime14.5永久46成员闭包仅改变版本与执行配置交接，保留14.4其它成员；实际普通安装为runtime-service-20261106-019，23包依赖兼容。见[固定闭包](../../apps/wt_runtime/source_closures/0.1.0a14+auxiliary.diagnostics.fees.5/README.md)。

完整ef5按原execution_product构建通过25文件。后继ef6完成编译、链接及安装后，原全owned检查因两份测试在编译期间更新而拒绝，原失败和冻结输入保持，未补造RESULT通过。独立核查255项编译声明、223条实际命令、203个对象头依赖及五份链接RSP，确认两测试未进入生产或自定义命令闭包；生产源码无差异，安装与链接输出逐字节一致。Root另核实际冻结生产闭包、全部固定输入、实际链接来源、后继依赖及25文件，并用最终Native入口验证无券商配置的失败旁证与关闭，单独形成ef6-qualification002/PRODUCT.json。此项独立生产闭包验收与原全owned拒绝分别记录。

Standard DLL为4aad84b292c2e5fedce295cf62c7dfa5299363982f61c037e00e3df6832d4762；CtaRuntime为2638e70cdcb9ba45cc3a1914debab72aa9b368bc1384bda0c522c0250c0612f2。Parser从原reader_product的固定Git/锁定归档重新构建，658件安装及79件组件核验通过；正式Parser SHA为d3313c509c302d856dcf57b162bae1c1b2a6ac0c389ce53fd8da80365112cd91。

## 真实主链及恢复

首次采用后的原生进程在10:58至10:59自然进入卖出/买入阶段，提交16次setter；5笔本批委托均在券商完整查询中为全数成交、余量0，与原成交查询一一匹配。原通道14项命令全部SDK已返回，48项事件全部持久确认，无缺口。本批原券商号、数量、成交及查询时点保存在受控QA的BROKER-NEW-ORDERS-DEALS.json，不导入旧历史交易或重新发出原命令。

10:59:42的实际退出由上述自有许可不一致触发。修正后的完整组件在原故障代及全部子进程物理退出后采用；保留父failure的components_closed=false及Native原故障，不把故障改写成clean。沿原ServiceController和prepare_transition/resume_reconciled恢复，金融状态根、100万元含持仓基准、原现金锚点、周期与已发生成交保持。

11:38实际WT59060、Native26424、控制代824af702-1a40-42e2-a9ee-0e3980f684c6，Native控制6ae68864-56e4-4a34-8e2a-1ec96a12b025。恢复序号157及原state_id接续，资金资格合格；新代初始化158不作为新自然计算。当前午休，策略awaiting_first_strategy_calculation，原行情连接与账户查询正常，目标setter0，未制造市场事件或人工目标。

其余五角色的PID及创建身份逐项保持。group024、稳定DEPLOYMENT及启动/停止快捷方式均已指向Runtime19和现行服务；原入口的备份保留。独立观衡18143的strategy-runtime读取ready及策略资金通过，观衡未重装或与WT合并发布。

## 日志、未覆盖与回退

新Native日志真实落盘，write_failures=0；前一代首次分钟Reader回调曾有一条错误，后继自然调度与本批真实交易已发生，其最初异常细节未留存。原未配置RiskMon和通道规则的提示按原配置解释，不把空日志当成健康。后继自然回调和本次等待分支的现场连续性继续跟踪，不能以午休ready替代。

原AWP在Host换代后保留旧30个成功原件，原流程自行建立新capture并发布9268行；无需新增恢复代码，见[既有恢复证据](../evidence/2026-11-06-analysis-binding-self-recovery.md)。四类辅助数据的真实收盘合并、最终无引用产物清理仍未完成。页面加载与资料更新问题按此前优先级在主线发布后继续处理。

QA根为E:/workspace/wondertrader-qa/target-replacement-live-20261106-001，含原安装备份、实际安装/启动、原交易原件引用、独立生产闭包资格、POSTFLIGHT及快捷方式备份。原ef6拒绝目录保留。回退先正常停止并核原命令，再采用对应已验制品及同账恢复；原缺陷版本只保留作追溯，不以回退重新暴露旧目标额外交易。
