# QMT Host业务回复等待窗口

类型：根因、原条件回归及候选角色证据。日期：2026-11-04。状态：自有两模块已独立核验，新角色及WT描述离线准入通过，线上采用另行记录。

真实账户订单查询在派发后2013.466ms中断，原请求SDK预算5000ms，旧Host运输I/O预算为2000ms。旧收据证明中断时间及缺少原数据，具体底层异常正文没有保留。独立使用原策略线程SDK替身耗时3秒，原协议和内存帧路径复现过早退出，确认等待职责不匹配。

修正位于自有`guanheng_qmt_shm.control`和`read_retention_journal`。已送出调用沿原业务D等待；多个责任取最早D，停止进一步收紧。空闲仍为2秒，帧发送预算保持。只读领取在Journal域中核原ID/正文及票据，冻结单调时间上界；跨域保留原None/四元组接口和原ID。实现没有放大源端SDK预算、重发命令或延长原票据。要求见[THP-R9](../specs/qmt-trade-host-product.md#验收)。

固定目录：`E:/workspace/wondertrader-qa/daily-mainline-20261103-001`。

- `TRADE-IO-CAUSE.json`：真实原请求、四层预算和旧收据身份，区分已证预算缺口与缺少异常正文的范围。
- `host-read-wait-candidate002/TEST-RESULT.json`：原策略线程、原Control/Session和内存帧走通3秒SDK调用；原D超时和stop沿原责任退出，SDK调用恰好一次。
- `host-read-wait-candidate002/DELTA-TEST-RESULT.json`：普通/Bulk空与非空领取、完成前后close、元数据异常原ID收束、UTC前跳和回拨60秒等24项定向核验。
- `HOST-READ-WAIT-REVIEW002.json`：独立delta审查complete、findings=0；早期候选的关闭四元组与时钟问题均已修正，早期角色没有采用。
- `host-read-wait-role002/ROLE.json`、`PAIR.json`：从原安装RECORD闭包构建，其余62个Host文件及Agent/SDK字节保持；版本`0.1.0a22+host.httpretention.2.readwait.2`，wheel SHA `83efc63017ff1c7c7d217ed6b1dc0090706a51d31b361a93e95ceff7d62ed9fc`。
- `HOST-READ-WAIT-DESCRIPTOR.json`：原WT父端完整安装/manifest公开能力准入通过，未启动新Host或改CURRENT；完整Source正文SHA仍为`b581bf707281290465201b0964d9ef2c6a224935131f160fd13047d1f47f90d9`。

代码身份：control `f6b6e089786699527f2e2da5a5926eba9f6e4de09801cb2e6237e90ba22efcdc`，read_retention_journal `fcb8d8b14d2e16a6b1c3255c7ea1e4ec6ebf9fa1cc708eeec02a0d3c82477cc1`。

未提供内置非阻塞SHM接缝的旧运输继续原I/O行为。实际长期连接与停止恢复资格由线上采用证明；本证据不代表完整调仓、正常撤单或全市场数据交付已完成。
