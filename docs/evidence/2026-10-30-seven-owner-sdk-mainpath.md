# 同一 WT 七组件与唯一策略 SDK 主路径

日期：2026-10-30。规格：[WRI](../specs/independent-wt-runtime.md)、[NAP](../migration/native-account-publication-proposal.md)、[QST9](../specs/qmt-quote-stream.md)。证据根：`build/root-seven-owner-001`。

## 实际完成

统一普通安装WT a5、Host a9、Agent a8（安装manifest SHA `31f402a9d71d021708f10f05254d71bacd00d38d95a2e0f1d85e7c12c67ffbb0`）在同一WT控制ID启动原七owner。执行器消费B固定Native和唯一1.1.2内核；原stock-borrowed/Trader通过WinSHM，在正式四owner内存正文的同一SDK策略线程调用一次模拟卖出。NAP从该同一模拟账户查询成交后的持仓、订单、成交和资金，独立a45只消费发布结果。

`main006/control-seven006` 55.047秒exit0，6865输入前后相同。SDK实际卖出200份510050；初始两项持仓变为510300一项，订单与成交各一条，原值进入NAP并与a45同scan投影一致。三份保留扫描的141事实/63ABI及浮点位通过关闭后immutable Journal原值审计。观察期其余原周期查询未扩大成已保存扫描的ABI资格。

同时保留6982证券QST、原Writer、HPR及原Reader五根历史：216442报价=两次快照+29轮在线全市场更新，Native计数相等，代际1、溢出0、队列0。App停止后WT持续发布；WT停止后重新启动独立App保留最后成功数据。所有子进程exit0，无forced，Job树0、管道EOF、线程join和资源关闭完整。正式QMT内存正文禁止文件/网络入口计数0，运输工作线程0；外层SDK夹具自行记录协调材料。真实QMT操作、真实委托和撤单均0。

## 接线与关闭

Source先等候原Host，随后WT依原公开工厂启动host→trade_host→account_host→NAP→history→collection→execution。NAP在WT进程内。所有查询与委托共用一个SYNTHETIC SDK账户状态，测试夹具沿原retained模型返回事实；算法、仓位计算、资金规则和金融恢复仍由原产品拥有。

QA关闭顺序收敛为先停止WT消费者，再停止外部SDK来源。`main005`旧协调器先停来源引发执行器runtime故障的原件保留；`main006`验证正确依赖顺序。此次没有产品、WT框架或B源码修改。

## 整体恢复尚未完成

`main007`保持同一来源、同一Native财务根和Journal，经原resume_clean尝试整个WT重启。第一代正常；第二代交易Host认证接续成立，position/order/deal/account四查询均terminal/ok，旧委托仍唯一sdk_returned，关联无错，事件各前沿均2。Native随后在trader阶段未达ready，诊断码0；WT报component_start_execution，物理资源全部回收，SDK委托数仍1。

直接原因unknown，交父会话协调原Trader启动/旧事件消费的限定复核。原失败根未重试或重开写；关闭后只读元数据位于RESTORE-COLD-001/002。该尝试不授整体WT恢复、未知委托恢复、实际券商/生产资格；B此前execution-only同根恢复与此范围分别保留。
