# QMT 来源执行方式配置

类型：操作手册。范围：WT 管理的交易通信产品及其完整来源正文。配置契约见 [SIO](../specs/qmt-source-runtime.md)。

1. 使用已安装 Host 包的 `trade_cli pair` 创建全新私有配对；SDK manifest、许可证、原账户与市场材料继续由原 verifier 准入。选择 `--source-mode strategy_tick`，同时传入原 `--market-config` 与 `--account-read-pair`。所有文件读取和正文生成均发生在 QMT 外。
2. 运行同一安装的 `trade_cli verify`，核对 `qmt.trade-product-pair.v2`、`source_runtime`、完整源码及正文 SHA。`strategy.py` 是本配对的完整可部署正文，QMT 内只加载正文内存。
3. WT 沿原配置托管 read/HPR/trade Host、采集、历史及其他已声明组件；每个进程一个 owner。Host 等待来源，操作员启动匹配策略。观衡启动与停止不管理这些 owner。
4. 核查只注册一个 `agent_tick` timer，周期为 `100nMilliSecond`，同一原线程调用 SDK，来源运输线程为零。确认每条所需连接已认证，再沿原业务入口核验账户、行情及分钟归档。
5. 停止时沿原策略入口撤销订阅和准入，保存 WT、来源与通信库的最终状态。分别核对运输关闭、业务交接、线程/进程树/管道/句柄；未确认交易完成沿原 ID 核查，避免重新生成身份。

示例 Python 参数（字段仅表示生命周期）：

```python
source_runtime = {"schema_version": "qmt.source-runtime.v1", "mode": "strategy_tick"}
```

省略参数继续默认 thread；显式 `thread` 同样生成带身份的 v2 生命周期材料。回退执行方式需要新的配对/核验和对应完整正文，旧冻结安装及其配对保留。已有通信库和未知委托依原恢复规则处理；执行方式回退不授覆盖、重发或删除资格。

现场计时器支持和实际调用链必须单独验收。完整替身通过后，真实只读验证使用同份冻结候选，策略备份、临时部署、停止及逐字恢复由单一操作员管理。同步 SDK 占用策略线程超过原 IO 预算时，保存原超时/未知状态和同代证据。
