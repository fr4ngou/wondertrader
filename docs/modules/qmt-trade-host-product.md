# QMT 交易通信产品

类型：模块说明。契约：[THP](../specs/qmt-trade-host-product.md)，持久恢复：[ADR-0017](../architecture/adr/0017-trade-authentication-continuity.md)。

本模块把现有交易通信实现安装到独立 Host 包，由 WT 管理进程生命周期。WT 与观衡分别运行；观衡停止时，交易通信继续由 WT 的原 owner 管理。

| 层 | 唯一责任与入口 |
|---|---|
| 外部材料 | trade_pair.create_product_pair / verify_product_pair：原配置、policy、SDK/许可与源码冻结，生成私有完整策略正文 |
| 外部 Host | trade_cli pair/verify/run → trade_control → 原 paired_control；监控、收据、原截止与资源关闭 |
| 常驻连接 | trade_resident → 原 ReconnectingReadService 的串行代际 owner → 原交易 runtime/Journal |
| WT 父端 | trade_host_process.create_process → 原 ManagedLocalProcess；隐藏创建期 Job、管道、线程与收据 |
| QMT 内 | ReconnectingTradingAgent 持有一个 SourceTradingService，原策略线程调用券商 SDK；每代只重建运输资源 |
| 恢复事实 | 原通信 SQLite 的命令、事件与附属认证关系；原订单/成交/资金算法继续由既有模块负责 |

ready 收据表示 Host 已监听。来源认证、账户查询、交易准入和未知委托状态沿原公开接口分别读取。Host 持续等待晚到来源；一次请求仍受原有截止约束。

父端按显式配对版本识别组合能力：v3 携带单证券日线与复权因子分析，v4 携带批量日线分析，并可同时保留 v3 的分析连接。公开 profile 与设置摘要沿 [WT 运行规格](../specs/independent-wt-runtime.md#持续策略分析数据装配)核验，完整私有配置由 Host 验证。各版本沿用同一隐藏进程 owner、ready/closed 收据和停止顺序，省略批量配置时继续原配对路径。

显式常驻模式保留同一业务 session 与业务 binding。事件附属认证关系追加在同一个通信库内，原命令、创世 binding、旧事件和旧来源证明字节保持。默认单代工厂维持原严格匹配；默认工厂发现新模式库时拒绝降级打开。

已执行但回执丢失的命令保持原 ID 与 unknown，重复提交原命令返回原记录。源端旧 reply ACK 未确认时，运输可关闭，业务关闭继续报告 unconfirmed；运维保留原来源和通信库并按原核查流程处理。完整正常关闭及未确认关闭分别登记。

同 GH 策略的显式 market 组合沿原 QST/HPR 配置与独立交易配置生成一份正文，只装配一个行情订阅、一个历史准备 owner 和一个交易 owner，使用唯一 timer。操作步骤见[运维手册](../runbooks/qmt-trade-host-product.md)。

开发验收使用 Windows 共享内存、真实 Python 3.6.8 完整内存正文和券商 SDK 替身。真实 QMT、真实委托、既有 Journal 与生产切换另记实际资格。
