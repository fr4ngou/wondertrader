# Gateway 启动取消候选及跨代恢复审查

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：隔离修复证据。日期：2026-10-21。范围：[GSC-R1–R6](../specs/gateway-startup-cancellation.md)。状态：隔离实现及独立full/delta通过；原QMT源码与现场保持原样，未合入或部署。

原[确定性红测试](2026-10-21-gateway-startup-isolation.md)证明，启动超时未登记取消、stop在无IOLoop时提前返回，后台导入恢复后仍开始监听。私有候选统一表达取消，并在第三方初始化阶段间核查；每代独立事件与结果，资源由后台线程清理，确认旧线程退出后才可重启。原Tornado网络实现和async drain保持。

独立full进一步发现：旧ensure_running读取线程后，未将stop绑定所观察代次，另一调用者重启后会被旧恢复误停。原竞争已在Python3.6.8复现。最终修复把资格/代次观察以及条件停止/条件启动绑定同一生命周期锁；代次已变化时明确报错并保持新代，公开stop继续作用于取得锁时的当前代。

最终候选SHA-256：`e6f2d2d0208e9cf2987e761ab2b5a12642f8b931bf3b494ab849c003f3c5626f`。开发矩阵23个有界子进程通过；独立delta在真实Python3.6.8/Tornado6.0.2中执行24个隔离进程全部通过，覆盖6类跨代交错各3次、原竞争复现、启动各阶段取消、清理异常与同实例恢复。独立实际HTTP排空验证保留pending ticket、返回202、结束线程和后续重启，未改变原业务任务事实。

取消与退出仍是不同状态：卡住的导入/第三方调用须等待返回，线程存活期间禁止新启动。listen已准入后发生取消时，可能短暂建立TCP监听，返回后清理且禁止就绪发布；候选没有线程强杀或自造socket实现。

用户重启AI ETF后现场端点已经恢复，真实历史通道可继续验收。恢复来自用户操作，候选没有被用来恢复现场。该候选只证明启动取消和跨代恢复缺陷的隔离修复，现场首次SSL/GIL阻塞首因未被这个实验解释。后续若集成回QMT，须在独立工作树对齐最新代码、完整调用者及项目审查/发布流程，避免覆盖并行开发。

附件：最终候选源码（外部历史/待归仓路径：`gateway-cancellation-2026-10-21/candidate-server.py`）、开发验证（外部历史/待归仓路径：`gateway-cancellation-2026-10-21/candidate-results.json`）、原竞争红对照（外部历史/待归仓路径：`gateway-cancellation-2026-10-21/red-baseline.json`）、独立full（外部历史/待归仓路径：`gateway-cancellation-2026-10-21/full-review.json`）、独立delta（外部历史/待归仓路径：`gateway-cancellation-2026-10-21/delta-review.json`）。原先候选源码及结果留在 `build/native/gateway-startup-audit/candidate/baseline-61199ccec5c0/`，新实验位于 `generation-bound-v2/`。这些附件用于审查复现，未加入WT发布清单。
