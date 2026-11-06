# 原生业务日志真实库验证

类型：自有原生日志模块验证。状态：头文件/真实WT日志主链/根因回归/独立delta审查通过；CtaProcess及完整product接线由Root集成，现场资格待验。

## 实现及生命周期

[NativeRuntimeLog](../../src/GuanhengExecution/NativeRuntimeLog.h) 保持Root提供的start/status/close接口和原WTSLogger→ILogHandler→spdlog设计，修正同对象重复start及close后start仍可能替换写者的生命周期缺口：每对象仅首次start准入。status的失败计数注释收敛到实际可观察的打开、追加和刷新失败。原WTSLogger全局单次初始化，要求进程内唯一日志owner，业务生产者全部停止后close；新代由新进程持有。

动态执行器缺少单独dyn_pattern时沿原root回退，info以上通过真实原handler同步进入私有native.log。spdlog原轮转持有当前文件和3个数字备份，每文件1MiB，原正文截断到8192字节并保持UTF-8中文完整边界。规格见[SDO-R5-Native](../specs/strategy-data-and-observability.md#sdo-r5-native-原生业务日志接线)。

## 实际输入及主链

[真实库driver](../../tests/integration/native_runtime_log/run.py) 使用仓库build/ef4固定MSVC 14.51.36231、原上游头文件、spdlog/Boost依赖及真实WTSTools.lib/WTSUtils.lib，隔离编译probe，逐场景启动独立隐藏进程。原日志函数、ILogHandler和文件sink均非替身，无服务、终端、账户或正式安装操作。

最终受控证据根 `E:/workspace/wondertrader-qa/native-runtime-log-20261106-003`，RESULT.json记录命令、源码及链接库SHA；compile.rsp记录全部编译参数。真实主链先在001通过动态原日志落盘，随后集中根因与异常场景。

| 场景 | 实际观察 |
|---|---|
| 动态执行器/root/info门槛/close | 动态中文info和root error落盘，debug跳过；attempted=2、failures=0；重复start、close两次及close后start保持同代，关闭后不再回调 |
| 真实轮转 | 1001次原回调；native.1/.2/.3.log各1,045,337字节，native.log 913,693字节；四份均≤1,048,576字节，最新尾记录存在 |
| UTF-8与正文预算 | 三个越界正文均截断，实际正文8191、8190、8192字节，全部以严格UTF-8解码并与完整预期字节一致 |
| 打开失败 | 普通文件占据目标目录，原sink打开失败；attempted=2、failures=3；两步业务标记全部到达，close正常 |
| 真实轮转写入失败及恢复 | 实际Windows读句柄允许追加、拒绝rename，原轮转报错并进入error handler；attempted=129、failures=1，业务继续；解除句柄后新日志真实落盘 |

002最初用非空目录占据备份名，原轮转会移动该目录，未制造预期失败，原测试失败保留。003采用实际文件共享拒绝窗口后，故障和恢复均可观察；未修改原spdlog行为。

## 源码审查与边界

独立delta源码审查通过；头文件SHA256 `b7bca16717bad23eed8d19ec7769abbb813f77266b1ba147d985c9e95e47c467`，probe.cpp `4d5d1033807b6f3afb9e0012cf75060d098d6db20f03d6c320d55527b540fb8a`，driver `65b1e34994464dd635f885a79490e942c4053827f25167dcaacacaa605ee9e0d`。真实WTSTools.lib SHA256 `dcf15a7e946a32e5ffc85f4143532bad223374ccd334133016cb8d20c16bbe20`；WTSUtils.lib `82107604fe4da95731d57fcdb09fd65536099cbc1031594125fd2f80b07d2f1a`。

本验证覆盖真实动态日志公开调用及文件故障，实际策略/执行器业务触发、CtaProcess生产者关闭顺序、完整product构建与正式运行采纳由Root继续验收。磁盘满导致的直接fwrite失败未注入；已覆盖真实轮转写操作失败。WT框架、交易语义及现场保持原样。

## 自有宿主接线审查

独立delta审查已核CtaProcess本轮接线，P0/P1为0：单次gh_cta_run创建一个日志owner；原session/execution全部关闭后才撤销handler、停止日志；未确认关闭沿原ExitProcess责任处理。Native同业务比较与Python对称，严格校验两个股票工厂及布尔类型，比较副本归一化，实际配置保留。审查CtaProcess.cpp SHA256为f5097409876fd44fcfeb0432f02b842cb1208cafd2264a6db47cda2caa91aa34，头文件仍为上列b7bca167。完整ef5产品及正式恢复、真实业务日志触发继续pending-verification。
