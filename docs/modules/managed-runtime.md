# 受管运行时

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块说明。所有者角色：运行维护者。范围：外部线程内的有界行情与回报调度；源端连接、交易授权和持久事实分别由对应模块持有。

## 职责与入口

ManagedRuntime（外部历史/待归仓路径：`../../src/GuanhengRuntime/ManagedRuntime.h`） 接收 MarketParser、ManagedTrader 的非拥有引用。外部单线程服务循环调用 start、poll_once、stop，运行时交替推进行情和回报，分别报告来源状态与调度状态。

行情实例经 WT ParserAdapter.initExt 注册 SPI 和订阅，由 WT adapter 持有并最终删除。Runtime 先停止，adapter 再释放；回调期间保持所有引用对象存活。WT adapter.run 返回成功与端点可用性分别检查。

ManagedTraderAdapter（外部历史/待归仓路径：`../../src/GuanhengRuntime/ManagedTraderAdapter.h`） 将受管交易前端接入原 WT 持仓/委托/成交归约器。初始完整快照交付一次；同消费者断线后保留原投影，依据 Host 连续性证明补投至冻结前沿，再通知原 WT 通道就绪。缺少证明、跨日或消费者应用未知时保持降级。账户事实、原始执行账本和恢复证据继续由执行端点提供。

## 线程、预算与失败

创建线程独占调度；同步重入被拒绝，回调内 stop 在当前调用返回后完成。轮次限制批次及总时间，向端点传递剩余预算。同步第三方调用超时通过降级状态上报；进程内调用的可抢占取消需端点自身提供。

行情故障时继续推进既有交易回报。停止与重连遵循来源代际规则，执行恢复状态保持所属端点及 ManagedTrader 的原语义。

## 验证

`GuanhengRuntimeProbe --self-test` 使用合成端点经过真实 WT BaseDataMgr、ParserAdapter、TraderAdapter 与 SPI，断言快照、轮询、故障、通道失联/恢复及消费者隔离；`--status` 在缺少合格端点时返回 unavailable 和退出码 2。Probe 是开发及制品检查入口，正式服务绑定以对应部署契约和资格为准。

验证代码见 runtime 场景（外部历史/待归仓路径：`../../tests/integration/runtime/runtime_scenarios.cpp`），预算和参数说明见组件说明（外部历史/待归仓路径：`../../src/GuanhengRuntime/README.md`）。
