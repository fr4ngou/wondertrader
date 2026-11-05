# 独立QMT SHM Agent

内部私有标准库包，Python3.6.8+。受管入口在原策略线程执行显式准入的market.full_tick、market.history_1m和account.trade_detail；原认证Session/SHM/base-control及有界关闭保持。full_tick-only使用v1 profile，历史使用v2，账户使用v3完整descriptor，能力组合必须与Host/客户端同版配对。

内存模式使用已冻结依赖闭包与builtin-shm；终端内不读取外部包、配置或数据库，不建立网络。外部Host拥有通信Journal、认证HTTP及持久回执。来源时间、单位、覆盖、真实终端与正式发行分别取得证据；Journal容量满拒绝新工作，原终态保留，不自动删除。

省略`read_retention`保持以上默认保留语义。独立只读/HPR显式启用后，源Book按原真实ControlPeer ACK交接确定完成责任，ACK缺失时原D结束可释放确定结果；未知和运行中继续保留。SDK仍在原策略线程/单timer，纯内存retention_status提供计数。完整要求见[RR规格](../../../docs/specs/qmt-read-retirement.md)。

v3账户/control1和v4混合/control2可按[AAR](../../../docs/specs/qmt-account-read-retirement.md)显式附加同一`read_retention`能力，进入完整认证profile；固定账户查询及交易权限保持原来源所有者。该字段只选择外部Host的读取结果消费生命周期，金融命令、事件与源端SDK调用规则继续沿原路径。

trading_kernel.py提供[QST-R9](../../../docs/specs/qmt-shm-trading.md#qst-r9-第一源端切片的冻结接口)原线程交易开发接口：显式注入SDK与固定账户/合约规则，默认禁写，有限同会话重复抑制和unknown隔离；不拥有金融账本或跨重启保证。当前生成入口/Host尚未注册它，模块存在不代表配对具有下单撤单能力，实际部署order_ready仍为false。完整SDK与WT交易链、回报、恢复和退出必须分别验证。

_provenance.py保存固定来源摘要，原版权头保留；用户授权内部迁入不推断公开再分发许可。完整部署、预算和来源边界见上级连接包README及QSW规格。

开发切片补充：trading_contract.py为Host/Agent共用的绑定、命令与SDK调用结果准入；trade_events.py按[QST-R11](../../../docs/specs/qmt-shm-trading.md#qst-r11-有界回报缓冲开发接口)保留有限白名单bytes，处理并发完成、连续发布、交付后确认及sticky gap。它们尚未在正式回调/共享内存写协议注册；已通过替身验证的源码模块与实际部署能力分别登记。

交易协议开发接口见[QST-R12/R13/R14](../../../docs/specs/qmt-shm-trading.md)：trade_clock提供受检查的同次Windows启动毫秒时钟，control2显式扩展交易消息，read_capabilities提供v4组合描述。旧builder保持control1及原v1/v2/v3字节；新描述不自动启用运行工厂、SDK或真实写。ControlPeer两个CALL领取入口共用唯一lease，完整构造后才确认交付，失败保留原值与原截止。验证及未覆盖范围见[控制协议证据](../../../docs/evidence/2026-10-24-qmt-trade-wire.md)。

完整私有配置使用显式`trading_configuration.validate_trade_configuration`，沿[QST-R15](../../../docs/specs/qmt-shm-trading.md#qst-r15-完整交易配置准入)。它共用原读预算/运输准入，核账户关系和交易联合额度；旧只读validator继续拒v4。返回的公开value排除secret/trade_binding/writes_enabled，私有binding属性每次返回副本。四Host槽覆盖一次事件页到业务ACK的进展，连续gap继续占额；配置不授无限轮询或SDK权限。实际策略注册及运行接线仍待验。
