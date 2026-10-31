# QMT交易通信开发切片验证

日期：2026-10-24。类型：实现与验证证据。范围：[QST-R9/R10/R11](../specs/qmt-shm-trading.md)与[ADR-0009](../architecture/adr/0009-trade-command-communication-owner.md)。完整Host/Agent/WT写链、真实SDK与生产资格仍待验证，真实写默认关闭。

## 实现与边界

继续已测嵌入加载/builtin-shm，停止正文改写。memory_runtime.py与pair.py摘要仍为d1d740f73c759dea4ea7d9c7f7609a55d114c64cb557818affd93d79edf8f8d4和f8acf48b66720c97dcb8ddd6633150eb72478a25a84674dc4a512163cac46301。新增共享纯契约，源kernel复用同一准入；回报缓冲仅拥有有限普通值bytes，短锁保护票据/连续前沿/容量，SDK getter与on_gap在锁外。Host扩展同一通信SQLite及原owner/事务，保存命令、派发和调用回执，不保存持仓资金账本、不新增数据库服务；WT继续负责执行和消费。

模块尚未注册正式写profile、源回调或标准TraderQMT/SPI；实际部署order_ready=false。本轮未执行真实SDK、终端重启、策略切换或生产发布，旧QMT工程只静态参考，WT框架无本轮新增修改。

## 源端与回报验证

47项测试（原kernel21、共用契约9、回报缓冲17）在开发Python3.12与国信Python3.6.8分别通过，覆盖真实测试线程倒序完成/同步重入/关闭竞争、值与页无别名、额度、粘性gap、交付后ACK、MemoryError/KeyboardInterrupt页构造故障。控制收据位于build/guanheng-workspace/account-runtime-install-001/build-qmt-trading-events-unit-002与build-qmt-trading-events-sdk-unit-002。两次正常退出，非强杀，树归零、EOF、reader join与资源关闭均通过。

84模块私有嵌入探针qmt-trading-memory-probe-003在目标3.6.8通过：下单/撤单SDK替身各一次，同ID重复不增加调用，事件capture/page/ack及关闭后gap可观察。验证区builtins.open、_io.open、FileIO及外部导入被拒绝，尝试0；实际SDK0。准备/结果文件由终端外验证工具读写；本探针没有进入QMT策略或SHM真实写链。对应memory-prepare-002与memory-target-002控制收据正常退出，原probe001/002按各自输入保留。

回报首次full静态审查发现P2：页构造前推进交付前沿。修复为完整页成功后再推进，17项测试含两类异常前沿不前移与原事件恢复。qmt-trading-events-review-002/REVIEW.md闭合原P2；SCOPE-R10.md确认后续Host期限规格变化不改变R9/R11结论。静态审查不冒充动态或SDK证据。

## Host期限审查与验证

第一轮27项trade Journal测试定义有6项Windows清理错误：测试with sqlite3.connect仅完成事务而未close；另根driver错误地按top-level导入包测试。修复7处测试连接关闭与driver包导入后，27项交易+12项既有BoundReadJournal共39项通过。原失败control qmt-trading-journal-unit-001与原通过002保留，不覆盖。

独立full仍发现TJ-F1/TJ-F2两项期限P2：I/O D截短business TTL，及SQL/commit晚回未后检、claim剩余TTL陈旧。39项通过只证明当时输入，不能覆盖错误oracle。首次报告qmt-trading-journal-review-001/REVIEW.md和输入清单保留，已按独立业务D、同I/O D前后检查与commit后TTL收敛修正，修正后的003运行47项，发现原有“业务时钟坏后原ID仍可读”回归1项失败：新增I/O检查借用了business clock。原失败收据保留，继续将I/O检查沿继承事务的实际monotonic域，业务时钟异常只关闭新交易。004候选新增测试字符串损坏，实际语法收集失败；独审同时识别claim末次业务时钟动作后的I/O复核缺口，两个中间输入和收据均保留，最终结果另记下节。

## 最终Host候选运行

产品trading_journal.py SHA c40a6ffea83386c64beaadffaa2cda8713da6290c241ad1888b4e6705917629c，测试SHA 8d27585506b25d049024638b5709f26a1c9d217c175bb95ad0fdb9d6cb77b6b9。37项交易Journal与12项既有BoundReadJournal共49项在005运行通过（5.340s）。包含原坏业务时钟后原ID仍可读、已保存SDK回执领取、I/O期限与业务期限分别推进、connect/BEGIN/SQL/fetch/提交晚回、末次业务时钟动作跨I/O截止、原身份保留/写闭锁及重启不重发；未修改继承BoundReadJournal或其事务算法。

对应控制收据qmt-trading-journal-unit-005：退出0，非强杀，父子树归零、stdout/stderr EOF、reader join及资源关闭通过。SQLite/OS阻塞无法瞬时取消；检查拒绝晚回并保留owner/原记录，不宣称硬实时中断。最终独立delta complete-static，TJ-F1/TJ-F2闭合且无新增P1/P2；报告qmt-trading-journal-review-002/REVIEW.md SHA a4d6a9ae3b72b951aa18abe1d01b057d169e04e25cc74809b13d7e13bd2864c9，16最终来源前后0漂移，两个interim原件及此前001至004输入/失败均保留。静态范围不授完整写链或SDK资格。源码清单与5组最终控制收据汇总位于qmt-trading-communication-001/SOURCES.sha256.json和result.json。

## 当前未覆盖

交易控制协议/profile版本与旧读兼容、源SDK注入及同策略回调注册、回报持久保存后ACK、原WT标准Trader/SPI消费、查询与主推交接、unknown实源核查、正式交易宿主停止与独立安装均待接通/验收。柜台备注回显/ID作用域/实际权限与真实下单撤单需具体授权及目标实测；本轮替身不授实盘资格。完整迁入目标继续active。
