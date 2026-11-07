# 2026-11-08 观衡129 策略版本和回测对照候选

状态 candidate verified。观衡 `0.1.0a129+comparison.1` 源码 `a3e27e2c07d2a03217689e9202836e30b6e4dad2` 已合入本地 master。ZIP SHA256 为 `61a8a695b03542073ee7f1cc39996e18063acf12579e19cfeaa3a83bd47636a8`，普通安装收据 SHA256 为 `edff147a1defdae61c502a6abb2344bede16e722aa4a73071253b25c33a8f524`。正式端口继续运行[自选恢复版](2026-11-08-observer128-watchlist-recovery.md)。

- 策略与版本两级选择共享轻量归档目录，保留旧 URL、稳定名称和精确版本归属。版本与报告条件见[策略目录](../specs/strategy-catalog.md)。
- 回测按需叠加五个价格指数，展示与回撤同步的日末仓位，日期详情可分别核主报告及对比报告。来源及缺失语义见[回测规格](../specs/backtest-performance-comparison.md#bpc-r6-指数基准与日末仓位)。
- 本地 CI 的 284 项回归、51 项后端相关回归、36 项前端相关回归、类型检查、离线构建、普通安装及依赖检查通过。用正式归档的只读入口逐点核对了 11 份报告的 6,144 条日末估值。
- 隔离 Web 在 18187 验收 1500×1100 和 390×844。浏览器核五个指数勾选、旧链接、点击和键盘切日、对比报告仓位，控制台错误与写请求均为 0。使用自选与策略历史副本，候选验收后正常关闭。
- 构建及页面收据位于 `D:/wt-build/observer-backtest-comparison-20261108-001`，CI 收据位于 `D:/wt-build/observer-backtest-comparison-ci-20261108-001/RESULT.json`。正式切换沿[独立 Web 手册](../runbooks/observer-runtime.md#隐藏-web-的启动查询正常停止与重启)，复用已恢复的独立历史与自选配置。
