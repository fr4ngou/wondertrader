# QMT常驻只读连接

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块说明。范围：自有连接包的显式只读生命周期、v3配对及独立WT受管Host。当前进程所有权沿[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)：WT拥有通信，观衡单独部署并只读；模块工程/真实来源证据按实际调用入口与版本分别使用。

## 原生复用和职责

WT-D01/WT-T01继续提供原生Parser/Trader公开接缝，WT-O01保持原生进程；可选WT-O04应用层守护不作为本模块依赖。券商专有共享内存协议由本连接包拥有，当前切片不改变WT核心、持仓归约、交易算法或原金融事实。

Host的read_service.ReconnectingReadService组合原HostReadRuntime、原Session/base control和同路径通信Journal。bootstrap.build_read_service采用显式入口，构造时冻结配置、凭证及操作policy，start时才取得资源；原build_runtime及单连接配对保持。变更配置须重建整个服务，不随重连读取变化的policy文件。

QMT端reconnecting_read.ReconnectingReadAgent组合原RestrictedReadAgent；enabled=True和恢复间隔显式传入，原start只启用调度，原ContextInfo线程的首次tick创建首代。所有SDK仍沿原Agent.tick，包构建时才从磁盘准备源码；运行策略内部保持正文内存加载及内建mmap，不读文件、不联网。

## 线程、代际与关闭

| 所有者 | 职责 |
|---|---|
| Host单一管理线程 | 创建/启动原runtime，撤销旧代准入，等待HTTP调用租约归零，沿原绝对D关闭，再创建新代 |
| 原Host I/O及域线程 | 认证、控制传输、原请求持久终态；原I/O释放自身映射/句柄 |
| HTTP工作线程 | 在管理锁内认领当前runtime引用及计数，锁外请求/诊断，finally归还租约 |
| QMT原策略线程 | tick推进恢复、执行已允许的SDK读、确认旧I/O退出后原close(now)/join(0) |
| 原Agent I/O线程 | 连接/认证/传输，finally释放本代资源 |

常驻仅放宽尚无对端时的空闲等待；受保护映射创建、握手、每个请求及关闭仍有原期限。停止唤醒等待。旧owner释放不确定时保留owner并显示故障，禁止再建一代；同步start/SDK错误保首因且停止自动推进。Host关闭失败不以第二次退休延长原D。

已认证的旧对端仍占通道时返回暂时运输不可用；未选中的到达者不替换nonce或写原对端关闭位。明确识别的认证错误停止恢复；空/陈旧未认证映射和无对端超时不能识别所有错误配置，配对身份校验仍必需。

## 请求和事实边界

恢复复用同一通信Journal文件与原结果。旧binding准入拒绝，新代重新认证及取得新binding；旧queued按原owner规则结案，旧终态按原ID可查。没有自动重放旧读请求或未知委托，也不创建第二个持仓/资金/订单账本。

本入口只接只读profile和builtin-shm。交易Agent的事件缓冲、unknown及跨binding交接保持独立验收。常驻API、v3策略生成、独立安装、WT进程管理、实际券商运行和部署自启分别核验。旧App管理进程的工程结果保留为历史证据。

验收见[QSW-R20](../specs/qmt-shm-wt-binding.md#qsw-r20-常驻连接与系统统一启动)，运行步骤见[国信操作手册](../runbooks/guosen-qmt-operations.md)，实际结果见[本轮证据](../evidence/2026-10-26-qmt-resident-read-service.md)。

## 配对与统一进程管理

v3配对把connection_lifecycle纳入配置摘要。Host和QMT正文采用同一恢复间隔；verify以同一次有界材料快照核Host/策略全文、policy及角色身份，build_paired_runtime直接消费已核policy字节。原v1/v2默认生成字节保持。

独立WT通过components.host显式装配[QmtHostProcess](../../apps/wt_runtime/guanheng_wt_runtime/qmt_host_process.py)，使用qmt.host-process.v1描述。描述含独立Host pythonw及SHA、pair目录及manifest SHA、installed_agent、control_root和启动/停止/输出预算；具体入口沿[独立WT手册](../runbooks/wt-independent-runtime.md)。Host包由它的独立进程导入。观衡旧GUANHENG_QMT_HOST_CONFIG环境变量已退役，当前[ConsoleSettings](../../apps/guanheng/guanheng_app/settings.py)不消费这些值。

WT的QmtHostProcess复用ManagedLocalProcess的进程Job和线程所有权。Host run-pair核v3后创建本代控制目录；ready授监听就绪，真实QMT认证/账户仍由binding及业务请求证明。关闭沿首次单调截止，先关闭依赖消费者，再收Host，同时核closed、实际进程退出、树零、EOF、线程join和句柄关闭。观衡关闭仅读取自己的资源。

构造失败也有资源归属：常驻工厂预留Journal单槽，取得后先登记，成功移交Runtime或close确认后清空。双异常保构造首因，槽内仍有owner时健康显示pending、关闭保持未确认，并停止再建代际。启动成功和关闭成功出口均核原最早截止；晚观测事件和晚返回I/O不会延长原窗口。

WT所有权及组件顺序沿[WRI](../specs/independent-wt-runtime.md)。原App托管的[系统管理验证](../evidence/2026-10-27-qmt-managed-host.md)保留历史资格，当前WT与只读观衡组合见[独立历史服务验收](../evidence/2026-10-30-native-history-observer-composition.md)；每份证据按其固定版本及范围使用。

## 历史App入口的完整内存正文验收

跨解释器与独立安装的可重复主入口见run_installed_memory（外部历史/待归仓路径：`../../tests/integration/qmt_shm_reconnect/run_installed_memory.py`）。验收包括观衡实际管理Host进程、两代认证及五类查询、旧终态读取、旧binding拒绝、SDK无自动重放及源/Host/App收尾。合成SDK和真实平台分别登记，实际结果见[安装组合证据](../evidence/2026-10-28-qmt-resident-installed-two-gen.md)。

## 历史App入口的真实终端两代连接

实际观衡管理同一个独立Host，两次运行同一完整内存正文后，绑定改变且每代账户四查询/行情查询成功；旧终态保持、旧binding拒绝，Host与App正常关闭。范围和输入身份见[实机两代证据](../evidence/2026-10-28-qmt-resident-real-two-gen.md)。该结果仍与C++交易/账户消费者、长时运行及正式登录自启分开验收。调用者从认证read_profile读取每项操作的执行预算及policy身份，在该上限内构造请求；Host队列预算与来源SDK执行预算分别遵守，避免将账户允许时限套给行情。
