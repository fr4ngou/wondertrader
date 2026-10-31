# QMT账户读取责任回收

类型：模块说明。唯一要求见[AAR](../specs/qmt-account-read-retirement.md)，进程内账户观察职责见[ADR0007](../architecture/adr/0007-account-observation-read-state.md)。

原生账户客户端取得当前完整认证后，为新观察产生有限票据与原八字段请求。原QmtBoundReadCore验证原结果bytes、来源、账户DTO及截止，并由本进程有界返回值持有完整结果，随后向原Host确认消费。请求和原票据仅活在进程内；同一进程恢复原ID时使用lookup，继续原截止和身份。新扫描由业务刷新发起。

Host在原读取事务保存票据与消费确认。确定完成、已确认且票据失效的读取可以释放；未知继续保存。v4同一金融Journal保留原命令、事件、订单链接与未知责任。仍被订单链接引用的ORDER结果保持金融证明，引用自然更新后才能回收；状态显示held_financial_proof。旧无票据行显示legacy_records并继续占用。

原生receipt增加显式票据string，自有标准插件的DTO尺寸断言和有界内存银行同步。账户、历史及标准交易消费者需要同批重编；原WT框架与C接口保持。默认省略能力继续原路径。金融证明或未知责任占满原容量时保持等待，处理依据仍为原命令和来源事实。

Host/Agent的配置、票据与结果规则复用[RR模块](qmt-read-retirement.md)。[维护手册](../runbooks/qmt-account-read-retirement.md)说明显式配置与待确认处理；普通安装、SDK、真实终端和生产分别取得资格，工程证据由[验证记录](../evidence/2026-10-30-account-read-retirement.md)登记。
