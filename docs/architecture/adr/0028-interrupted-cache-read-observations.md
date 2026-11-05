# 中断缓存查询与后继观察分别保存

状态：accepted。所有者：WT日线数据owner。范围：显式批量日线缓存只读操作。

market.market_data的qmt.daily-batch-read.v1 policy使用fill_data=False、subscribe=False读取既有缓存。一次观察中断后，原执行结果可能不确定；该纯查询没有委托或下载副作用，后继读取可以独立观察同一参数的当前缓存。

日线owner仅在原SDK完整核验、结果已持久消费且终态明确为operation_interrupted时选择后继。原失败槽、请求ID和结果保持，后继为同一slots目录下batch_id.rN.json。已存在后继沿其原ID恢复，成功manifest准确引用实际成功槽；跳过的每个中断槽仍核原anchor/generation、profile、limits和业务来源身份。

SDK提供默认原路径的受保护选槽接缝，自有DailyBatchAnalysisSource显式采用此规则。缺终态、未消费或其它错误沿原读取责任；通用默认消费者、订单、账户和HPR保持。该决定补充[ADR-0018](0018-confirmed-read-responsibility-retirement.md)的消费恢复职责，不把中断改记为SDK未调用，不删除Host尚持有的原责任。

原分片、相同绝对截止、来源数值和供应商复权资格保持。一次capture不因此获得全缓存同瞬时或历史PIT资格。唯一功能正文见[UDI-R53](../../specs/qmt-source-daily-history.md)，来源只读约束见[QAB](../../specs/qmt-analysis-batch-source.md)。
