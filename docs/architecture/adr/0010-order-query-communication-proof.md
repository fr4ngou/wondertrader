# ADR-0010：当前订单查询沿原通信owner恢复关联

状态：accepted实施决策；运行验证独立登记。

原R21保存真实callback来源。Host/Agent换代后，当前订单查询可以重新观察原完整token和brokerID；仅允许旧event来源的取消校验会持续拒绝这项已有外部事实。

采用[QST-R21Q](../../specs/qmt-shm-trading.md)的独立AccountQuery证明类型。原HostTradingJournal/BoundReadJournal在一次现有事务内保存query结果与有限关联引用；金融解释、WT订单与持仓仍归原层。新reference.v2显式描述query原request/result摘要/原行/B，旧event证明及v1结果保持。

查询证明与原完整通信记录共同保留，数量、字节和截止沿原owner。来源B变化要求新实际查询；重启读取旧记录只恢复历史身份。查询不获得event session、快照水位、金融提交或最终取消成功的含义。

原read.finish在take前预分配完整持有槽并冻结现I/O预算的保守绝对D；take成功后先保存完整原reply再解析payload，后续异常仍保有原reply。背压、锁等待、来源关联、commit和关闭收尾沿同一D。提交前超时回滚；提交返回晚保留实际原事实并阻止源ACK。当前取消恢复切片适用原insert已sdk_returned且正常写通道可用；unknown的受限取消仍需后继完整准入契约。

该决定增加一种已有通信事实的可验证来源，取消依赖新callback才能恢复的自有限制，不增加人工资格、四查询原子门、第二金融账本或WT核心接口。代价是关联引用必须参与原记录保留与恢复完整性验证，生产者和消费者需一起接受v2契约。
