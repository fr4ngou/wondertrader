# 2026-11-12 交易 Host 账户结果持久超时

北京时间 14:27:16，交易 Host 在只读账户结果 `read.finish` 上收到域 Future 的 `TimeoutError`。旧 owner 直接抛出异常，随后在 `retirement_unconfirmed` 退出，WT 因 `component_runtime_trade_host` 收尾，执行器停在 `recovery_drain`。原 Host 的 `failure.json` 记录 `read_commit_done=true`、`read_commit_failure=TimeoutError` 和域队列为零。旧日志未记录原 SQLite 事务内的具体超期位置。原 Host `io_seconds=2`，属已有只读持久预算。

原 Runtime 和组件进程物理退出后，以原执行进程退出收据和同账接续启动。14:44:30 核到新代执行就绪、行情已接收、策略已调度、观衡已读回原账户；分析窗口仍因原来源时效等待。同代交易 Host 在 14:44 再次出现相同的 `read_commit_failure=TimeoutError`，后续停机。原账本 `quick_check=ok`，101 条交易命令均为 `sdk_returned`，无 queued、dispatching、unknown。最后一轮完整券商查询的 42 笔委托均为终态。连续重启旧版无法修复此故障。

修复将运行期的已结束 `account.trade_detail` 结果持久超时交给同一个域核查原账。原终态已存在时验证原结果字节；原请求仍在执行时仅持久标记原只读请求中断。核账确认后才退休原运输结果。原请求、原持久截止、委托和撤单继续沿原责任，未知交易结果按原命令核查。诊断记录超期阶段、请求摘要和处置；核账无法确认时保持失败。

全链复查同步覆盖行情批次预算与游标、报价冲突现场值、分析刷新 Job 超期与回收、服务状态短暂共享冲突、交易 RPC 拒绝的固定诊断及观衡源读取。原模拟成交和观衡市场观察各自沿原读取确认。故障保留原回执，候选上线资格沿[发布规范](../runbooks/release.md)办理。

独立行情采集角色 14:30 另有一次 `minute_maintenance` 异常退出，旧回执只留下 `exception_kind=other`，并确认组件关闭。该角色已沿原入口重启。源码已复现窗口收据扫描 `SourcePending` 会跳出维护循环的缺口，并让该证券和日期进入原重试队列；旧现场回执缺少更细证据，具体异常仍待确认。分析端原文件核到 `market.market_data` 首次准入返回 `400/read_ticket_ended`，该读取沿已有新捕获机制重试，源码增加首发准入分类供定位。
