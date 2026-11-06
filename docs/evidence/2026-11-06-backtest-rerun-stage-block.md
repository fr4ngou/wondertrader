# 共振1.2.2重跑与阶段阻断

类型：真实原生回测重跑及失败定位。核实时间：2026-11-06北京时间14:50。状态：原生运行和报告读取完成；策略完整执行资格未通过，原因尚未修复。5.8912%等原始数值保留，暂不用于评价策略完整区间表现。

## 输入与实际运行

- 区间2025-03-05至2026-11-02，100万元、原费表及原冻结行情/辅助历史；配置采用当前线上588030及实际config_revision，其余业务参数逐项相同。
- 从Runtime21复制六个实际发行至独立环境，Runtime0.1.0a15+currentaux.1/V1a13；754件源码/依赖前后摘要一致，原生WtBtPorter及基础资料沿原固定绑定。
- 安装后的正式CLI完成404日原生回放，Native及父owner退出0、非强制、进程/管道已回收；约556秒。run_id=373d106856464caea0d443131316952a，完成证明SHA256=e25f881331ebc94e6fdfa693af6aad63bbc76593ff32c7231d04721184b35af2。
- 404个评估日的7项必需辅助字段全部非空；历史可获知时间仍沿research-next-common-session-0925-v1假设，没有用盘中当前值回填历史。
- 原始绩效：收益5.8912%，日末最大回撤27.361356127280384%，末值1058912.00000000003元，费用16484元，原生成交105条。与上次同区间数值相同。正式App及实际Edge页面能打开新报告、原生成交和比较，控制台错误0。

## 业务失败及复现

逐日状态为buying5、converged48、selling44、waiting_cash19、blocked288。2025-08-21至2026-11-02连续288个交易日因stage_budget_exhausted阻断；最后成交停于2025-08-21。原ca52c01505d34ab680f0dbeef23807c9也有相同288日问题。技术完成证明与正常策略执行分别判定，收益/回撤的一致性不授予正确性。

原触发日公共值经过已安装的实际advance_retained接缝，0.1秒内重现blocked；断言命令为本QA的reproduce_stage_block.py，实际exit1。上一日卖出阶段sequence16，旧allocation为6月26日，当前新目标为7月31日；当前原生actual已全部达到旧冻结卖出向量，pending数量0。将纯计算对照Limits改为64后，返回selling且仍推进6月26日旧目标；未修改源码或部署。

因此已确认的触发链为：自有retained_evaluation优先让旧经济目标完整converged，原数量阶段在新post-sell价格/NAV下继续残余卖出，最终达到16阶段预算并永久阻止后续新目标。旧阶段卖出完成和整轮旧目标收敛被接续层绑定；简单扩大预算仍继续旧目标。具体应如何接纳已结清阶段后的最新目标，需要在唯一接续合同中修正，并核原未决、T+1、现金和恢复事实；不能绕过原未决委托保护或改原策略信号。

原生WT源码修改0；线上安装和金融状态修改0。该接续函数由实时与回测共享，属于主线需处理的自有适配风险；本次尚未更新线上。报告读取器也按同一接续函数重放验证，后续修正需同时区分旧/新报告语义，保持旧原件。

## 证据与用户入口

QA根E:/workspace/wondertrader-qa/backtest-rerun-20261106-002：PREPARED/ISOLATED-INSTALLATION/RESULT、INPUT-COVERAGE/EVALUATION-COVERAGE、PERFORMANCE/TRADE-STATISTICS/COMPARISON、SOURCE-AND-LIVE-AFTER、BUSINESS-VERDICT及STAGE-BLOCK-REPRODUCTION.json。完整原报告、CSV和完成证明保留，正式归档新增一条原件、原五份文件未变。

浏览器RESULT及截图在browser/，正式入口为http://127.0.0.1:18143/backtests?strategy=resonance-regime-v1%401.2.2&run=373d106856464caea0d443131316952a。该页面展示原始数值供诊断，不作为本轮业务正确性证明。前述发布操作器最初误用2MiB控制写入器处理大行情会话，首次准备失败且未启动；后继沿原16MiB会话合同完成，原失败目录保留。

下一步为接续语义修正、实际触发快照及必要未决回归，再完整重跑；修正尚未实施，新的有效绩效尚未取得。
