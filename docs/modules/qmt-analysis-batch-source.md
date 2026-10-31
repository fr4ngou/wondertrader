# 批量日线来源模块

类型：模块说明。功能正文：[QAB](../specs/qmt-analysis-batch-source.md)。

WT 通过现有 qmt_read owner 持有 Host。显式 v8 在原共享内存来源上执行列表形式 get_market_data_ex，分别读取 none/front_ratio；原 v7 的单证券日线和因子保持。终端内部只有原策略线程和 timer，原有缓存补齐 owner 管理更新。

Agent 的 analysis_batch.py 负责批量 SDK 和各证券状态；原 DailyHistoryAdapter 通过返回值内存视图解码已经取回的 Frame，保持原数值/时标检查。Host 的 analysis_batch_source.py 注入 BoundHistorySource，复用 RetainedReadClient 处理原身份、先保存后 consumed 和容量回收。

BatchAnalysisSource.capture 接受调用方的证券池、日期、行数及 capture 身份。外部资源分片不改变证券池。一个捕获目录保留 REQUEST/BINDING/slots/manifest，继续相同目录时只续核原 slot；新的业务观察使用新的目录和身份。read_capture 核原批次摘要与来源身份，C 沿 batch_id 投影证券，不把投影当成独立 SDK 回包。

时间分别是源日线日期、原结果 completed_at、外部 received_at 与包 generated_at。比较日期交集只给源共同基准，完整闭合/实际复权/首次可知时间沿原分析与业务资格。局部状态明确展示 observed/empty/missing/invalid/requires_partition；资源不足时缩小显式批次/日期窗口继续。

公开SDK依据：[迅投行情函数](https://dict.thinktrader.net/innerApi/data_function.html)。stock_code 列表和 dict→Frame 返回是官方接口；BJ 的实际返回、缓存覆盖及更新路径按终端证据分别核实。
