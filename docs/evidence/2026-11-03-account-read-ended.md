# 账户读取回收状态修正

类型：故障核查与隔离验证。状态：源码实现和隔离验证完成，现场恢复待QMT重新登录。

## 触发与责任

Full37原Native故障收据记录plugin_error=10；reason_sha256对应固定诊断qmt_http_remote_failure:410。原通信库检查为零交易命令，保留原故障、原持仓与原金融状态；精确失败端点没有被当时收据记录，现场复验继续核对。

Common将账户票据lookup的已结束状态和consumed的已回收状态先归为通用I/O错误。客户端继续核查原读取时，这条路径会导致标准交易插件退出。Host只回收已消费、已结束且未被金融证明引用的终态，在途、未知和未消费读取仍保留。

## 实现

[Common](../../src/GuanhengCommon/QmtBoundReadCore.cpp)核验认证Host完整业务回复，区分原票据结束与成功账户数据。[标准插件](../../src/TraderQMT/StandardQmtTrader.cpp)归还已结束原读取的票据和容量，沿既有刷新发起新账户查询。持有完整原终态后的重复消费确认可接受Host已回收回复。其它错误、绑定冲突和交易命令保持原处理。代码补中文生命周期注释；WT框架、QMT正文及金融状态均未修改。契约见[执行恢复规格](../specs/execution-fault-recovery.md)。

## 验证与界限

使用真实Common、WinHTTP及HMAC，依次验证原票据结束、已持有原结果的消费确认、其它410保持失败。六次前后对照通过：旧版均锁存I/O错误；新版分别返回可结束的旧读取状态、成功消费确认和原错误。Native DLL已编译。来源为隔离HTTP替身，QMT调用和金融命令均为零。

私有原证据位于受控QA的daily-mainline-20261103-001：ACCOUNT-READ-410-CAUSE.json、READ-END-REGRESSION.json、read-end-native/BUILD.json。QMT已由用户退出，修正版尚未现场部署；策略自动执行尚未启用，完整目标保持进行中。

## 收尾范围

已登记八个worktree。运行、构建和交付引用核对完成后，清理多余工作树、遗留进程及打包产物。当前阶段保留运行数据、唯一金融账本、原始故障和他人未合入成果。
