# ADR-0017：交易业务会话与认证连接代际

状态：accepted（显式开发产品模式，运行资格按验证证据）。关联：[THP](../../specs/qmt-trade-host-product.md)、[ADR-0009](0009-trade-command-communication-owner.md)、[ADR-0013](0013-qmt-connection-lifecycle.md)。

## 背景

原交易 agent 和 runtime 面向一个认证连接。SourceTradingService 拥有原命令、SDK 完成、事件及业务 ACK；认证 binding 标识一次连接。原事件流以业务 session_id、binding_id 为键，并严格固定首个认证 binding。直接重建业务 service 会丢失内存身份，覆盖旧 binding 会改写历史来源证明。

## 决策

显式常驻交易产品将业务会话与运输代际分开。源侧一个 SourceTradingService 在原策略线程构造一次、账户订阅一次；其命令、原截止、未知、hard fault 和事件前沿跨认证代际保留。每代运输 agent 只拥有本代 SHM、ControlPeer、读队列和 I/O 线程。运输退休先确认这些资源关闭，保留业务责任，随后才建立下一代。最终策略停止另外核实业务排空和交接，运输关闭与业务关闭分别报告。

Host 复用现有常驻 manager 串行关闭单代 runtime，再打开同一路径原通信 Journal。只有新产品选择 `connection_continuity='qmt.trade-auth-continuity.v1'`。原默认入口保持精确 binding 校验，不建立附属关系。

新模式在原唯一通信 SQLite 中增加 `trade_event_auth_connections`，追加记录同一业务流的原 binding、本代认证 binding、前连接索引及接续时 durable、ACK intended、source ACK、published 前沿。认证 owner 经原 domain 调用 `events.resume`；账户、route、profile、epoch、业务 session 等稳定身份须匹配。连接索引单调，已退休 binding 不能重新成为当前连接。原流 host_binding、原事件、旧命令及旧来源证明不改写。

事件来源证明按首次持久保存时的连接区间还原。旧事件重放核对原字节；新事件后缀保留实际新连接来源。ACK 前沿继续由原事件事务和原源 ACK 决定。附属记录消耗原 event_storage.max_bytes，原身份持续保留。

原 wire profile、控制 grammar 和 receipt 字段保持。原 receipt 的 binding hash 继续指向流的创世 binding；本机 domain 另向 runtime 提供当前已认证关系的纯值证明，默认路径仍要求当前 binding 精确相等。

## 未知、关闭与回退

已执行但回执丢失的原命令继续按原 Host Journal 查询，包装层不自动发送新命令或重新调用 SDK。旧 ControlPeer 交易结果 reply 未收到 ACK 时，当前协议缺少跨代确认该结果的接口；长寿命 owner 保留未确认责任，最终业务关闭报告 unconfirmed。正常无遗失责任的两代可以完整关闭。恢复观察和最终业务关闭分别验收。

新模式通信库由显式产品继续打开。原默认模式发现附属表时明确拒绝。回退采用停止新实例、保留原库及配置后恢复受支持的产品版本；附属表、历史 binding 和未知记录原样保留。现场生产切换和真实交易沿独立授权。

## 验证

完整新安装通过 3.6.8 内存正文、Windows SHM、65 秒晚到、同业务 service 两代认证；SDK 替身核四类账户查询、下单/查询/撤单、原事件及未知不重发。必要回归覆盖默认严格路径、新库默认拒绝、未 ACK 事件跨代重取、旧证明与新来源、原截止、容量事务以及物理资源关闭。实现、独审和现场资格分别记录。
