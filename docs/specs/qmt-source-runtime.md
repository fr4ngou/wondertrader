# QMT 来源运行生命周期（SIO）

类型：功能规格。状态：accepted。范围：内置 QMT 完整正文的执行方式、认证运输和原 timer。金融能力、权限、Journal 和 WT 框架分别沿原契约。

## SIO-R1 配对和默认路径

正式 `create_product_pair`、`render_trade_source` 和 CLI 接受可选 `source_runtime`。省略时保留 thread 模式及 v1 deployment/manifest 形状。显式对象仅含 `schema_version=qmt.source-runtime.v1` 和 `mode`（`thread` 或 `strategy_tick`）；材料使用 `qmt.trade-product-pair.v2` / `qmt.trade-deployment.v2`，绑定部署摘要、清单、源码闭包和完整正文。verifier 逐字重建。原 v1 材料维持其严格身份。

执行方式属于来源生命周期，read/trade 金融 profile 与 wire/MAC/seq/ACK 版本保持。现有 read、HPR 和 QST 配置由各自原准入器核验。

## SIO-R2 原策略线程推进

strategy_tick 对 read、HPR、trade、QST 使用同一个 `SourceConnection` 实现，每个业务 owner 独占自己的连接实例。沿同一个原 `agent_tick` timer，以 `100nMilliSecond` 在原 Context/线程上推进。thread 默认周期 `1nSecond` 保持。该周期使用 [QMT 官方 run_time 支持的毫秒单位](https://dict.thinktrader.net/innerApi/system_function.html)，适用版本以完整配对 SDK 身份及现场验收为准。

策略回调中只处理已经就绪的完整帧，缺少帧或 ACK 时立即返回。每个 owner 每 tick 最多四帧；单帧仍受原 max_frame 约束。连接、握手和每次 IO 的原绝对截止只建立一次，跨 tick 保留。首次实际连接推进建立连接 D，构造与首个回调之间的间隔不计作已经进行的连接尝试。

Session 认证只保留一个状态转换实现；blocking 与 callback 驱动共用它。Framer 两种入口共用原认证、序号、提交和 ACK 校验，未确认槽不能覆盖。待发帧保持原身份，模式不授请求重发资格。

## SIO-R3 业务责任

原队列、AccountQueryAdapter、HPR task owner、SourceTradingService、ControlPeer 及交易事件/ACK 责任保持唯一。原 SDK 仍在策略线程调用；每次 tick 按交易、只读账户、HPR 顺序最多执行一个重任务。QST 全推订阅一次。新模式在来源中创建零运输线程，不创建其他 timer、进程、文件或网络连接。

## SIO-R4 停止、失败和恢复

同一策略线程创建、使用和关闭该模式的运输资源。停止撤销原准入和订阅，并关闭运输。已执行但缺少真实 ACK 的完成保留在原 resident/service 中，继续报告业务未确认；运输关闭与业务关闭分别验收。清理失败保留 owner，完整 close 沿原绝对截止核实已有事实。thread 默认关闭行为保持。

原请求业务截止与未知不重发规则保持。SDK 同步调用占用策略线程超过原 IO 期限时，连接按原期限失败并保留原身份；Python 驱动无法强制终止券商 SDK。回调服务频率、完整恢复和生产运行分别需要实际证据。

## SIO-R5 验收

普通离线安装、实际 Python 3.6.8 和 Windows SHM 执行完整正式正文。确定性回归覆盖原认证后后台 worker 缺少独立推进时的 Host-first 超时/SDK0，以及新模式在相同业务与 IO 预算下完成原四类账户读取。该回归验证调度职责，不单独确认 QMT 内部 GIL/公平性机制。

完整主链覆盖交易 SDK 替身、原生 Scan 四查、HPR 补读、QST→原 Writer、真实历史 Reader；必要恢复覆盖重新认证后的原身份与同 Host 消费。验证默认路径、期限、坏身份和停止失败的原责任。源码、wheel、安装、正文、配置、DLL/EXE、结果和物理回收均绑定 SHA。真实 QMT 验收与 SDK 结果分别登记，真实下撤单另按授权执行。
