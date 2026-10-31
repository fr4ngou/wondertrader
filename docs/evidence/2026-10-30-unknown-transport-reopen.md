# 原未知命令在Host与Source冷重开后保留

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B隔离验证证据。日期：2026-10-30。状态：原Host工厂/Source/认证HTTP/SHM冷重开限定链通过；正式WRI全组件重启、未知责任解除及完整模块继续。要求：[R27-C4](../specs/native-realtime-strategy.md#nrt-r27-未知提交后的原身份与同根重启拒绝)、[B-06](../migration/module-b-delivery.md)。新增生产和WT框架修改0，真实下撤单0，新增运行、缓存及制品均位于E盘。

## 原件与职责

上一轮[正式未知提交](2026-10-30-retained-unknown-restart.md)的main003已停止原Native、Host、Source及HTTP所有者。该实际合成SDK卖200入口一次后形成的通信SQLite作为本轮来源；不存在WAL，原RUN/POSTFLIGHT的完整回收先确认。原Journal SHA为`f4078833806cd4e94376d7fa926219392e5a6e47cf757dae0fe94cd3e07c614b`。

本轮在新隔离目录保留上述SQLite的完整逐字节副本，由原HostTradingJournal重新取得该副本的owner。原Journal及三份原WT金融JSON始终只读。route、trade identity及完整read/trade profile按原记录重建，构造前核profile SHA `b8ef48e723d0e7f34e0c0ee8bb85d90b5adcc9660ea876c8949d060adc2bd78f`相等；不重写旧命令、来源绑定或未知结果。通信Journal继续拥有命令事实，WT原文件继续拥有金融状态。

Host和Agent消费R27实际固定的177项运输源码副本，原SOURCE清单逐项核验；普通a3独立WT包仅提供已迁移的ThreadOwner胶水。原`build_trade_runtime`、HTTP服务、RestrictedTradingAgent及WinSHM实际运行。该入口是原工厂组合验证，正式WRI管理全部产品组件及当前Host安装闭包仍按其独立集成验收。

## 实际结果

原件根`build/ms-unknown-transport-reopen-001`，实际RESULT（外部历史/待归仓路径：`../../build/ms-unknown-transport-reopen-001/main-001/RESULT.json`）及RUN（外部历史/待归仓路径：`../../build/ms-unknown-transport-reopen-001/RUN-001.json`）保存最终结果。新Host/Source实际进程PID48140，外层venv启动器PID20380实际OS exit0；两种PID保持区分，48140的独立OS退出码未另行保存，Job整树归零及端内完整关闭分别核验。

- 新Source session与原session不同；认证HTTP trade-status返回200，新Source的unknown_fenced=false，Host的unknown_fenced=true，accepting_commands=false，hard_fault为空。
- 认证GET原command_id返回200/unknown，command原文与source_result原文及其两个摘要均与原Journal逐字节一致；只保留原命令身份。
- P/O/D/A各一次经真实HTTP→Host→WinSHM→新Source策略owner查询，四份原结果合同校验成功。来源明确为上一轮合成账户返回行，两个持仓各200股，委托/成交为空，资金来自原合成账户事实。
- 新进程SDK insert/cancel均0，trade-command POST0。原unknown继续保留，四查询可读，未解除未知责任或恢复新委托准入。
- 原Journal与原三份金融文件SHA保持。副本因原Host重开和新增四项读取、认证事件前沿而发生正常变化，最终副本SHA为`18e135804424d0e75842ac89748d443faed77da35002a1a22394503a13233295`；变化不改旧命令原文和结果。

Host关闭、Host I/O资源关闭、Source I/O资源关闭及双端交易关闭确认、HTTP与代理join全部成立；首错和代理首错为空。外层创建期Job、root reaped、tree0、双EOF、reader join及资源关闭全部成立，没有新建Native股票执行进程或调查线程问题。

## 限制与交接

本轮证明“持久unknown在实际Host/Source新实例认证后继续保护新写，同时允许核查和账户读取”。源端新实例的局部unknown标志不替代Host已保存的旧责任。完整恢复还需取得原命令的当前券商关联/终态事实及明确处置规则，保留原调用unknown事实；本轮没有删除、清空或伪造已成交/未调用记录。

唯一策略同根继续运行、当前正式WRI全组件重启、未知解除、稳定股票关闭、跨日T+1及全周期BT/RT继续按完整模块验收。既有[股票引用提案](../migration/native-stock-metadata-ownership-proposal.md)保持待批准，未应用或编译。独立审查、源码/原件SHA及归档按本根后继交付收据记录。
