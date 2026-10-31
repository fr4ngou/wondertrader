# QMT 来源通信驱动

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块说明。范围：来源生命周期及通信推进。契约：[SIO](../specs/qmt-source-runtime.md)；组合业务沿[账户组合正文](qmt-account-composed-source.md)和[交易通信产品](qmt-trade-host-product.md)。

[来源运行配置](../../connectors/qmt_shm/agent/guanheng_qmt_shm_agent/source_runtime.py)只选择本地执行方式。[SourceConnection](../../connectors/qmt_shm/agent/guanheng_qmt_shm_agent/source_connection.py)持有一代连接、原握手状态、待发送帧和固定期限；`poll`、`receive`、`send` 在暂不可用时返回 `PendingIO`，不等待对端。`close` 归创建它的原策略线程。

[strategy_tick](../../connectors/qmt_shm/agent/guanheng_qmt_shm_agent/strategy_tick.py)装配原 read/HPR/trade/QST owner。它沿原队列和完成接口执行 SDK，原重连 owner 继续持有业务身份及未确认责任。新的驱动同时复用原 Framer 的校验/提交、Session 的唯一认证状态转换、ControlPeer 和行情包生成器；金融数据和交易事件没有第二套实现。

thread 是默认方式；strategy_tick 由显式 v2 配对选择，正文只装配一个 100 毫秒 timer 和一个全推订阅。Host 在 WT 管理的独立进程中运行，观衡只消费结果。不同业务连接各有明确 owner，原认证 route/binding/generation 和秘密保持隔离。

`ready` 只表明 Host 已监听，认证和业务准入沿原接口读取。回调延迟或 SDK 阻塞达到原期限时，系统保留失败和未知事实；运输资源关闭不授业务完成。退订失败仍尝试释放本 owner 的运输，订阅收据继续保持未确认。运行中运输关闭沿原 OSError/可重连分类进入原 resident 退休；同线程已经释放资源的代际也保留该分类。最终业务停止与未知交接分别沿原责任判断。

官方说明[内置 QMT 的线程和进程约束](https://dict.thinktrader.net/innerApi/user_attention.html)；现场具体调度行为以匹配配对的实际运行证据为准。安装和配置见[操作手册](../runbooks/qmt-source-runtime.md)，回归入口为 test_source_tick.py（外部历史/待归仓路径：`../../tests/integration/qmt_source_runtime/test_source_tick.py`）。
