# V2历史行情到原始目标组合

类型：功能最终规格。状态：accepted。前缀：NVT。细化[完整策略迁入](native-strategy-kernel.md)中V2的历史输入→信号→固定分配切片；原生数量、回测和实时接线继续在同一整体目标内分别验收。

## NVT-R1 接缝及复用

独立包`guanheng_strategy_v2`固定依赖SST a2与NFA a3，不修改a5、不复制信号/分配数学。唯一计算入口`evaluate_v2_history(signal_input, *, pre_risk_capacity, budget)`：输入为SST公开SignalTraceInput；显式capacity只保留原V2升级条件，原始总权重1.125照常保留，不增加归一化、资本账本或人工审批。

对应WT-S01/S05/S06和WT-B01/B02，原生负责调度、持仓、目标执行及撮合；本包只组合策略业务计算，不模拟WT上下文或包装成configured1.2.0配置。两个SST profile显式沿输入选择，来源、辅助可获知时间和不同历史起点使用其完整准入。

## NVT-R2 完整轨迹与身份

调用SST得到真实派生轨迹，再逐字段形成NFA v2输入：保持decision原顺序/值和全部证据，schema为guanheng.fixed-unit-input.v2，allocation算法及来源字段使用NFA公开常量；profile、证券集合、历史/评估范围、cutoff、source/factor及trace_sha256均取本次SST结果。不能接受外部trace替代本次计算，不能把其他profile或旧结果混入当前分配。

输出持有独立模块返回的深不可变signal_trace与allocation，允许各自按公开预算查看完整原件。组合规范JSON只保留完整分配结果、有限末特征及依赖/来源/profile/trace身份，不重复嵌入完整信号历史。pipeline_sha256覆盖加入该摘要前的完整规范结果；加入后再核完整字节预算。

source_qualified、historically_produced、execution_qualified固定false。派生收盘边界、真实历史生产、原始目标与可执行目标分别解释。改变历史/辅助/profile/capacity必须改变相应内容身份。

## NVT-R3 同一预算与错误

预算公开值精确typed且入口重新快照复验；默认/硬上限5秒、输入/输出8MiB、4096历史日、32768行/decision、8证券。唯一monotonic截止覆盖预算准入、SST计算/公开投影、字段转换、NFA准入/计算/投影、组合冻结/编码/哈希。每次向既有模块传递剩余时间和收紧的容量，不在阶段间重置期限；结果公开序列化是另一个有界操作。

每个模块继续拥有自身严格准入，联合上限先到即拒绝；合法大输入不承诺一定在5秒内成功。错误为本包固定code/去敏中文reason，保留来源模块的受控code用于诊断，不回显外部异常、路径或输入正文。无副作用、线程、数据库或恢复账本。

## NVT-R4 验证与后继

以可手算CSI三灯及其他角色BUY/SELL样本，从原始历史真正产生decision和allocation；两个profile分别与已验公共SST→NFA显式调用对照，同时核原始1.125、不丢17项/256字符、重复和Unicode证据、空信号、日期/辅助/类型/容量拒绝、不可变、哈希及一个总期限。正式独立安装及另一作者full通过后才授该组合范围。

后继NSQ数量与原生NSB/CTA消费该业务目标，按原生资金、配置预算及交易限制接线。旧离线缩权与旧runtime拒绝超额的差异必须显式选择调用语义并验收；本包不擅自统一这些差异，不据纯计算成功宣称完整V2或实盘已完成。
