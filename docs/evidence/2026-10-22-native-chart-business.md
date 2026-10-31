# 观衡原生分钟图表接线

类型：跨仓库开发验证索引。状态：开发隔离验证通过，正式独立审查与受管运行未通过；完整目标active。

业务唯一规格及详细证据位于独立工作树`E:/workspace/qmt-worktrees/wondertrader-service-adapters`的`docs/specs/wondertrader-market-chart.md`与`docs/evidence/2026-10-22-native-minute-chart.md`。WT侧要求见[原生消费者规格](../specs/native-market-consumers.md)。本轮未改任何WT框架源码。

分钟图表已退出SQL读取、报价补线及Python5m聚合，沿SDK0.11.0的history.query读取原Reader/Factory，1.4 DTO与Console保留来源和覆盖Unknown。31项HTTP测试、428条真实来源、41项旧图表/Gateway、292项前端、正式构建及真实投影的浏览器组件切换/空/失败检查通过；原数据摘要不变，无网关调用。

HTTP测试关闭旧MarketData ASGI生命周期，不能声明完整服务已摆脱数据库。旧常驻进程仍启动Postgres池及NATS并在readiness检查store，下一步按原始行情与独有业务职责完成生命周期拆分及真实启动/健康/退出验证。

QMT prepare-review被六份旧策略制品与公共源码摘要不符阻止；制品未重登记，未启动独立Reviewer。继续核准实际输入与独立发布边界，保留development资格。未生成完整新包或发布生产；日线/复权、特征、CTA实时、真实1m补齐与交易恢复继续。

测试输出为`E:/workspace/qmt-storage/wt-chart-integration/run-edcf7896792748e1a88595e4e44f5ec3/result.json`；最终输入与核心边界登记于`build/native/business-chart/final-inputs.json`。
