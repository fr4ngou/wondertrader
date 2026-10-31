# 原生 CTA 受管退出

状态：accepted，开发隔离验收完成；生产未发布。2026-10-21。前缀：NCS。用户授权：先重新检查现成优雅退出方法；确认完整路径缺失后允许必要修改。固定上游 `08b230dd05facf6d650d949bfe51054115a2ecb1` 中 CTA ticker 已有 stop/join，HFT 析构已有调用示例；实时 Runner 未调用，实时 Porter release 只停日志，回测 stop_backtest 属于另一套对象。既有原入口负例与所有权分析支持本次补齐。

## 目标、范围与复用

沿[原生框架](../modules/README.md)现有所有者接线，让受控 CTA 进程在正常停止后返回零，最后回调先于其依赖销毁。保留分钟调度、预热/Pending 和补齐恢复行为。沿用 ticker.stop、pool.wait、risk monitor.stop、ParserAdapterMgr.release、自有插件既有 stopParser/stopDataReader 导出。

运行器配置 `env.managed_stop` 默认 false。true 只接受 CTA、内嵌parser列表、空 traders/executers、未启用独立 risk monitor 和 notifier、支持 stop 扩展的 parser/reader。准入在启动生产者前完成；不具备能力时配置失败并清理已创建但未运行的对象。已有第三方/HFT/SEL/交易配置默认行为保持；其完整退出资格另验。该选择避免把未验证的插件释放行为当成排空证明。无数据库、订单或交易权限变更。

## 生命周期与职责

1. Runner 单实例配置/运行一次。`request_stop()` 仅原子发布请求，可从普通回调使用；普通 SIGINT/SIGTERM（Windows含SIGBREAK）只写 signal-safe 标志。控制线程观察请求并执行停止；信号处理不日志、不锁、不join。异步run调用返回后，控制侧轮询stop_requested()并执行stop；该入口同时观察信号、请求与后台任务失败；stop不允许从生产者回调调用。
2. 控制线程串行完成停止；启动与停止由生命周期锁排他，回调仅请求。首先请求 ticker 停止并唤醒休市等待，保持已接纳分钟整批回调完成；然后通过 parser.stop 扩展确认 worker/HTTP/SPI 均结束。false仅表示尚未确认完成，保留对象并可重试，禁止提前释放。
3. Parser停止后复用 ticker.stop 的 join。原有 pool 回调由生产者等待，再以pool.wait确认；此时才关闭 base task 队列并排空已接纳队列及交换出的本地批次。任务的准入、懒创建、关闭使用同一队列锁；任务和join在该锁外。重复stop安全，worker不能join自身。
4. 任务异常记录首次失败及未执行数量，不重放任务，不谎报正常排空；控制侧发现task_failure后立即请求停止，线程结束后完成资源清理，进程返回失败。正常情况 accepted=completed。
5. 生产者/任务结束后 stop reader；false保留全部依赖并重试。成功后先释放策略，再释放CTA contexts、数据缓存、parser/reader实例；保持策略析构时上下文与工厂仍存活。DLL保留到进程退出，支持最后slice/tick release；不提供热卸载资格。依赖仍由原框架对象所有者持有。
6. 主循环和析构都走相同停止实现。停止未确认时控制线程继续等待，日志标明阶段；禁止超时后离开作用域销毁活对象。正常回调可阻塞直到外部释放，本轮不承诺整体严格截止。配置阶段捕获异常、策略init=false与parser connect=false均传播为失败并清理，返回非零；普通运行异常清理后返回非零。

没有额外引擎 callback 计数门：在本次限定配置中，parser join 和 ticker join 覆盖两个实际生产者；保留原整批派生回调即可。外部自行调用引擎的第三方生产者须单独取得资格。此设计取代早期提案中的广泛回调准入门。

## 代码与兼容

14文件范围按所有权分为 Runner三文件、CTA/ticker四文件、base engine两文件、parser两文件、data manager两文件，以及策略管理器头文件一处release入口。新增非虚生命周期方法，保留 IParserApi/IDataReader 虚接口和工厂ABI。C++布局变化要求相关模块一致重编。ParserAdapter/manager.run(require_connect_success=false)保留默认调用的原返回语义；仅受管Runner传true并传播connect失败。原有 Parser `_check_time(false)` 保持；其他冻结核心差异保持原摘要。

并行接口冻结：ticker `request_stop()`、`stop()`；base `bool stop_tasks()`（完成join，返回排空是否成功）；parser/manager `bool supports_stop() const`、`bool stop(uint32_t timeout_ms)`，现有release仅在停止完成后调用；DtMgr `bool supports_stop() const`、`bool stop(uint32_t timeout_ms)`、`void release()`；CTA `request_stop()`、`bool stop()`、`release_contexts()`；Runner `request_stop()`、`bool stop_requested()`、`bool stop()`（返回是否完成，任务失败另记exit_code）、`int exit_code() const`。各stop的控制调用由Runner串行；局部ticker/task重复/并发stop也须安全。

模块持有与删除必须使用实际导出签名。没有stop扩展的旧parser release沿原API执行，新增受管入口拒绝把它当成已确认停止。data manager原析构路径的兼容行为保持，新release由已排空受管路径显式调用。

## 验收

| ID | 要求 | 验证 |
|---|---|---|
| NCS-R1 | 原触发条件在pool0/2正常exit=0，保持Pending calculate=0及同实例补齐恢复 | 真实WtRunner+QNP/NHR隔离子进程，严格断言无kill |
| NCS-R2 | ticker停止可唤醒休市等待、重复stop、请求来自回调不自等待 | 原生生命周期测试与真实信号链 |
| NCS-R3 | task并发准入/懒创建/停止，无丢失已接纳工作，异常隔离可观测 | 事件控制任务阻塞与异常回归 |
| NCS-R4 | parser/reader停止未完成保持实例/SPI/缓存；后续成功完成；最后回调先于释放 | 插件事件夹具与现有HTTP drain回归 |
| NCS-R5 | 配置失败、未启动、禁用模式、缺stop能力均有清楚结果 | 原入口配置失败及兼容回归 |
| NCS-R6 | 已接纳reader分钟整批和pool任务完成，保留结果跨停止可release | 原Reader/QNP结果生命周期回归及整链 |

独立full审查因跨模块并发/资源生命周期变化而必需。根因负例、绿色回归、制品输入分别留证。回滚使用批准前源码摘要与上一独立开发包，按一致ABI重建；生产发布另行授权。当前覆盖Windows原生构建，Linux信号/构建未验不得扩展资格。
