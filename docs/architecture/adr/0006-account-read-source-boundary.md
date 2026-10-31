# ADR-0006 账户只读来源与原生查询职责

状态：accepted。所有者：接入、原生运行及独立观衡应用维护者。

后继：[ADR-0007](0007-account-observation-read-state.md)替代下文客户端持久收据及累计额度要求；其余来源与原生职责决定保持。下文保留原决定记录。

## 决定与依据

账户观察沿原TraderAdapter的四查询和统计推进，ReadOnlyTrader保持owner线程映射及SPI、worker有界运输的单一生命周期。共享内存账户源扩展封闭只读能力registry，在独立data DTO携带账户参数绑定、范围、执行区间及返回list完整性；通用observation=null、认证三B、原请求Journal和SHM协议继续复用。

账户金融字段由运输无关的唯一mapper转换为WTS对象与事实视图。通信绑定只证明认证运输连接；券商登录会话缺证据时保留unknown。新来源通过明确inspection/Scan/公开DTO版本消费，旧字段不改义。查询原ID收据只由受管通信owner保存，不增加账户余额、持仓或资金账本。

原生查询不需要ManagedTrader的四批共同基线或新增资本/逐单审批服务。来源配置和只读callable显式注入；外部请求不选账户，不注入函数。数据、账户读取及写交易能力分别登记，order_ready=false保持。

## 代价与恢复

新增能力需同版Agent/Host/客户端/公开消费者共同准入，已有行情版本保持原行为。四批为不同执行区间，不能推成柜台原子快照。SDK缓存与登录状态需真实来源证据；未知请求只核查原ID。收据容量由部署owner声明，满额拒绝新派发并保留旧件，清理另有受控流程。

完整行为、字段、额度、版本及验收由[QAR唯一规格](../../specs/qmt-shm-account-read.md)定义。运行能力与原生复用边界分别见[原生能力目录](../../development/wondertrader-capabilities.md)和[账户只读展示](../../specs/native-account-console.md)。
