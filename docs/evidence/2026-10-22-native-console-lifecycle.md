# Console 原生分钟进程生命周期

类型：跨仓库开发验证索引。状态：完整进程开发验证通过；正式审查/严格发行与生产继续，整体active。

业务唯一规格为独立观衡仓库`docs/specs/wondertrader-market-chart.md` R5，详细证据为其`docs/evidence/2026-10-22-native-console-lifecycle.md`；工作树为`E:/workspace/qmt-worktrees/wondertrader-service-adapters`。本轮Console分钟主图/基准直接调用SDK，共用纯投影，旧MarketData只保留兼容路由及其余业务。

实际独立安装SDK与原Console完整ASGI生命周期验证34项通过，真实源摘要不变且Gateway0。两个子进程在同一端口正常启动、live/ready、短/空/失败恢复与正常退出；MarketData/DB/NATS连接0，进程末尾读取池、日志及非daemon线程0。ASGI收尾时仍有5个进程持有的池线程，最终普通atexit实测已全部退出；不授同进程热卸载资格。最终旧图表/Gateway/稳定性45项与真实投影浏览器组件测试通过。

旧送审循环已按通用阶段职责修正：开发准备记录合法source_changed并保留完整检查，不授发行资格；严格gate、集成和部署继续拒绝旧摘要漂移。自动准备保留16个制品owner函数，唯一实际发行资格函数及六个版本断言仍由完整发行测试执行。79项阶段组合通过，旧manifest字节不变。后续审查完成才按原工具追加新build，再重新核新差异与严格门禁。

实际进程与源结果：`E:/workspace/qmt-storage/wt-chart-r5-integration/run-ee7c5057f4c24ee08dd6c17bcf1bb1ae/{result,console-lifecycle}.json`。没有修改WT框架源码、生产终端或交易。日线/复权、特征、CTA实时、真实1m补齐、交易恢复及完整发行继续总目标。
