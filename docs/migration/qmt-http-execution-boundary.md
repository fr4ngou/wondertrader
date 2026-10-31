# QMT HTTP 账户观察与 WT 执行恢复边界

类型：当前源码与只读现场调查。状态：账户观察已取得现场证据；WT 原子初始化、保留消费者恢复及写入适配仍有公开契约缺项。调查日期：2026-10-21。范围为 QMT 已有 HTTP 入口、并行 Host 的公开状态/事件接口与观衡原生执行门面；本次只读 QMT 源码和 Bridge，未修改、部署、启停服务或发出委托/撤单。

## 结论与最小可行范围

现有 Bridge 可以直接提供带会话、捕获时刻、序号和内容哈希的资金、持仓、委托及成交观察。当前现场快照已通过公共 `AccountSnapshot` 1.2 校验，可用于只读展示、诊断及来源核验。

WT [ManagedTrader](../../src/GuanhengExecution/ManagedTrader.h) 的初始化要求上游明确证明“四种冻结快照已吸收指定事件前缀”；保留消费者重连还要求原边界、精确消费游标、冻结前沿、交易日和完整性证明。当前公开 HTTP 契约没有给出这一组 WT 证明。快照 hash、snapshot_seq、Gateway generation 或 Bridge 分页追平各自有效，不能相互替代。

因此最小适配先交付独立只读账户观察入口，保留原账户字段和缺失值，保持 `ManagedTrader` 未取得 bootstrap 时的不可用状态。完整执行端点需等待上游公开语义与事实映射齐备；transport 层不推断 route epoch、事件吸收水位或单执行权。

2026-10-21后续只读源码刷新仍支持该结论：27项原QMT输入中26项与前轮相同，仅Host README变化；公共契约、账户模型和实际路由保持。Host的native bootstrap属于可信启动材料，未提供此处的执行初始化/恢复证明。新水位加强了采样稳定与持久顺序，完整吸收语义仍由原owner明确。刷新证据为 `build/native/execution-contract-refresh/report.md` 与 `input-sha256.json`；本轮未请求账户或运行期接口，资格限源码核对。

## 已核公开入口

QMT 源码根为 `D:/workspace/qmt`。公开 HTTP 权威文档为 `docs/contracts/qmt-rest-gateway.md` 与 `docs/contracts/broker-client-v1.md`；外部平台通过 Bridge，`/internal/v1` Gateway 仅供 Bridge 使用。

| 对外或内部入口 | 当前用途与边界 |
|---|---|
| Bridge `GET /v1/internal/simulation/status?agent_id=…&refresh=false&sync=false` | 读取已持久的 snapshot、heartbeat 投影、quotes 及最多 100 条命令投影；本次取证使用此路径，不调用原生账户查询 |
| Bridge `GET /v1/internal/qmt/connection-status?agent_id=…` | 读取持久连接证据，不唤醒 QMT |
| Bridge `GET /v1/internal/qmt/gateway/health`、`/capabilities` | 内部令牌保护，由 Bridge 读取 Gateway 的健康和能力 |
| BrokerClient `state()`、`events(after_seq,limit)`、`sync_snapshot(after_seq,limit)` | HTTPBrokerTransport 分别映射 Gateway `GET /internal/v1/state`、`/events`、`/sync`；本次没有绕过 Bridge 调用这些内部地址 |
| `simulation/status` 的 `refresh=true` 或 `sync=true` | 分别刷新持久状态、运行有副作用的同步入库和游标推进；本次取证保持两者 false |
| Bridge `POST /v1/internal/qmt/operations/account.trade_detail` | 当前源码显式拒绝，HTTP 403；账户事实由定时 Agent snapshot loop 拥有。能力表的 implemented=true 不解除这项入口约束 |
| Bridge `GET /v1/internal/commands/{command_id}/progress` | 对既有命令进行只读进度核查；未知命令不构成“从未受理”证明。本次未查询任何命令 |

源码依据：`src/qmt_platform/services/bridge/app.py` 的 `simulation_status`、`gateway_operation`、`replenishment_command_progress`，以及 `gateway_client.py::HTTPBrokerTransport._target`。当前 Bridge 没有供外部 WT 直接领取完整 retained-consumer 恢复证明的路由；后续增加接口须由 owner 明确版本与语义，本文不预设 URL。

## 账户观察已有事实与字段缺口

`src/qmt_platform/common/contracts.py` 的 `AccountSnapshot`、`AccountOrderItem`、`AccountTradeItem` 为公共 schema；Agent 的 `account_snapshot_boundary.py` 统一生成语义 hash，`native_observation.py` 负责显式原生字段投影。

| 领域 | 已公开事实 | 对 WT DTO 的限制 |
|---|---|---|
| 资金 | 元计价；total_asset、cash（可用）、frozen_cash、market_value、account_market_value、day_start_asset、可选 commission_total | WT balance/pre_balance 的业务口径需显式对齐；day_start_asset 是日初资产，不能自动当上一日结算余额。冻结现金含费用，不能拆成 frozen_margin/frozen_commission；deposit、withdraw、close_profit 等未完整公开 |
| 持仓 | 股数 positions、available_positions、frozen_positions；市值、可选成本价和浮盈 | 没有 WT previous/today 及对应可用拆分。`frozen_positions=max(0,total-available)` 是不可用量投影，不能推断其全部为未撤订单冻结；T+1 和其他限制需权威语义 |
| 委托 | 柜台订单号、原生交易日、方向、数量、累计成交量、规范/原始状态、来源及可选命令/归属、可选 broker_ordered_at | 公共订单条目没有委托限价、WT entrust_id/user_tag，原生时间可缺失。不能补零价格或用捕获时间冒充柜台委托时间；`error` 也不能随意映射为全量 Rejected |
| 成交 | 柜台订单/成交号、交易日、单笔股数、可选成交价、可选柜台成交时间及其来源、费用、业务幂等键 | 缺价或 `native_trade_ordering_unavailable` 的事实可合法存在于原 schema，WT TradeRecord 则要求合法价格与日期时间；不能用到达时间补齐。完整历史覆盖范围仍需上游声明 |
| 事件 | GatewayEventRecord.seq + 原 EventEnvelope；deal_callback 为 single_deal，order callback 为 cumulative_order；event_id 与柜台成交身份分别去重 | 当前 callback payload 不保证带完整证券、方向、委托价格或执行身份。无命令关联的外部事实也可能存在；不能仅靠 seq 构造完整 WT ExecutionEvent |

当前 WT [字段验证](../../src/GuanhengExecution/ManagedTrader.cpp) 要求委托有效量、失效量与成交量严格守恒，并要求合法柜台身份和时间。DTO 默认零值只是构造默认，不能作为上游缺失字段的证据。适配必须保留 unknown/unavailable，逐字段完成现金股票口径后再授初始化能力。

## 快照、会话与水位逐项核对

| 名称 | 当前事实所有者与意义 | 不包含的证明 |
|---|---|---|
| qmt_session_id | AgentRuntime 构造时沿受管配置或生成新 UUID；health 与新版账户边界携带 | 不等于控制面的单执行 route epoch |
| Gateway health.generation | Gateway Journal 持久代际；独立 Host 使用自身观察代际 | 不等于账户 snapshot_seq，也不自动等于 WT stream_id |
| AccountSnapshotBoundary | account/agent/environment、known session、captured_at、session 内 snapshot_seq、语义 schema 与 snapshot_sha256 | 不声明某个事件前缀已被资金/持仓/订单/成交全部吸收 |
| GatewayState.last_event_seq | 旧 HTTP Gateway 当前已发布事件高水位 | 旧账户快照可以早于这个水位；没有 snapshot-bound inclusive_cursor |
| GatewaySyncCursor.page_chain_complete | 原 Bridge 连续分页恰好追到该轮观察到的 state 水位，并保存对应账户边界 | 不证明 WT 已应用哪些事件，也不证明 snapshot 已吸收这些事件 |
| broker_event_epoch | 旧 QMT incremental snapshot 内部防护：四次原生查询期间发生 order/deal/error callback 则丢弃该轮 | 内部数值未作为公共 execution route/stream 或恢复证明发布 |
| 新 Host 的源水位和 route 身份 | 受限 Agent/Host 内部已存在 callback 捕获水位、持久源游标和认证 route_id/executor_id/route_epoch | 并行工程的内部字段不自动成为 Bridge/WT 可调用的公共 bootstrap/confirm_resume 契约 |

旧 HTTP 快照采集由 `qmt_agent/qmt_strategy.py::IncrementalSnapshotProvider` 每 tick 查询 ACCOUNT、POSITION、ORDER、DEAL，回调 epoch 变化则重新采集。`runtime.py::_snapshot` 绑定账户语义 hash 后，`GatewayCore.update_state` 发布快照。`append_event` 独立更新事件序号；`sync_snapshot` 在锁内冻结当时的 state 与事件列表，但不会重新采集账户。

本次隔离反例运行原 `GatewayCore` 与公共 `GatewaySyncSnapshot` 模型：先发布合法空订单快照，再追加订单事件，sync 返回 `last_event_seq=1`、完整到 1 的事件页，同时保留原快照 hash 和空订单。公共模型接受此合法观察。这实证表明“同一 sync 响应”和“分页已追平”都不能据此生成 `CoherentBaseline.complete=true`。

Gateway 当前内存事件窗口默认 10000；原 Journal 持久事件独立存在。窗口外 after_seq 的连续性由 Bridge 校验拒绝。本次缩小到 2 的隔离实验追加 3 条事件，原 `GatewaySyncEngine` 确认缺页并拒绝，未把分页结果视为完整恢复。

## 并行 Host/SHM 工程的可复用边界

已只读核查 `qmt_agent/broker/observations.py`、`native_producer.py` 及 `src/qmt_platform/services/broker_host/{observations,runtime,app}.py`。新 ObservationBuffer 在完整原生采样前捕获 callback 水位；发布时水位变化则拒绝本轮。Host 单事务持久连续源事件和待发布状态，事件前缀提交后才公开相应状态；覆盖缺口锁存，state/sync 503，health 和历史事件仍可诊断。

该 Host 已提供使用原 GatewayState/GatewaySyncSnapshot 形状的 HMAC HTTP 读取面，并有内部 route 身份和命令许可 Journal。但目前公开面没有 `ExecutionBootstrap`、`RetainedResumeProof` 或解除 WT submission_unknown 的完整 reconcile 证明；Host 文档也明确命令 HTTP/IPC 和生产资格分别接线。调用方可等待其公开 owner 契约，复用同一 Journal，不新建平行账户或命令账本。

这部分属于当前并行源码能力核实。本次没有启动该 Host、连接 SHM、变更其配置或向另一用户聊天发送消息，当前现场账户读取仍来自原 Bridge/HTTP。

## WT 当前实现对照

| WT 接缝 | 当前实现情况 | 下一项所需输入 |
|---|---|---|
| QmtHttpClient / QmtHttpEndpoint | 已实现有界只读行情 operation、会话检查及结果领取；endpoint 只实现 IMarketEndpoint/IHistoryEndpoint | 不能当作 ExecutionEndpoint；账户 state/events 的解析与资格需独立适配 |
| ManagedTrader configure/open | 接收固定 ExecutionIdentity、预算、能力、端点和授权校验器；工厂未注入端点时 unavailable | 由受管控制面提供 account/environment/source/route epoch，不能从健康状态自行授予执行路由 |
| bootstrap | 检验四份同边界快照、stream_id、boundary_id、inclusive_cursor、complete；缺实现默认 unavailable | 上游原子吸收证明及完整字段映射 |
| events | 连续 cursor、stream_id、event_id，另按柜台成交事实去重；有限容量；未知回调隔离 | 原 Host 独立消费者读取与覆盖范围；完整 WT 事件字段；保留原 ACK 所有权 |
| confirm_resume | 必须匹配原基线、精确 after_cursor、冻结 through_cursor、同交易日、complete | 上游事务化冻结前沿及保留连续性证明；重连健康或新快照不足 |
| reconcile/execute | 显式上游恢复证明；原签名字节、原子受理、幂等及严格授权；裸下单/撤单拒绝 | 生产可信校验器与唯一 Host Journal 的公开契约、状态与许可；本调查不启用写入 |

本次源码检索在 `src/GuanhengExecution`、`src/GuanhengRuntime`、`src/TraderQMT` 与 `src/TraderTDX` 未发现生产 HTTP ExecutionEndpoint 子类。现有端点抽象及隔离 fake 验证不代表真实账户已经接入 WT 通道。

## 幂等与未知结果

原 HTTP Gateway 的 `journal.accept_command` 在 SQLite `BEGIN IMMEDIATE` 中按 command_id 与完整请求 hash 去重；HTTP 202 queued/duplicate 表示持久 inbox 接收。`mark_command_executing` 只从 queued 转移，原生执行前保存收到的命令。进度、回报及柜台订单/成交事实分别提供后续证据。HTTP HMAC 与 OrderCommand 业务签名属于不同密钥边界。

Bridge 的 `command_delivery` 保存 accepted/not_accepted/unknown 尝试；仅完整否定链且没有相反事实才能建立未受理证明。未知 command progress 不等于未提交。operation 超时领取原 request_id 的终态，不重新生成身份重发；这与交易命令的恢复流程分别维护。

WT 的 SubmissionUnknown、consumer delivery_unknown 与 QMT 原执行失败状态不可直接一一替换。尤其回调可能已应用时，保持 WT 隔离并重建消费者；Host reconcile 只能证明上游事实，不能证明 WT 回调应用范围。新连续竞价命令还允许 Agent 在原许可内定价，不能直接用 WT 预先填写的普通限价字段改写签名正文。以上均需 owner 明确契约后适配，本次未执行任何命令。

## 最小适配方案

1. **立即可实施的只读观察层**：通过现有 Bridge GET 获取原 AccountSnapshot，验证账户/环境、会话、捕获新鲜度、schema 与 semantic hash；输出原字段和 optional 缺失值。对资金、持仓、委托和成交提供统一观察及诊断，错误不输出空成功。此层不触发 WT 归约器或设置 consumer_ready。
2. **由上游 owner 明确执行观察契约**：公开冻结账户边界与事件吸收前缀、stream 生命周期、route/executor/epoch、交易日、历史覆盖/保留范围，以及从原基线和 after_cursor 到冻结 through_cursor 的完整证明。定义缺口、旧会话、换日和 Journal 重建后的恢复语义。只读证明由同一个事实/Journal owner 生成，接口路径和版本以其后续正式契约为准。
3. **补齐现金股票 DTO 映射**：明确资金口径、昨仓/今仓与可用拆分、订单价格/身份/源时间、成交字段缺失与外部人工来源。不在 WT 适配层猜值，也不为了获取缺失字段绕过 Bridge 的 account.trade_detail 禁用规则。
4. **实现自有 QMT ExecutionEndpoint 并保持只读资格**：真实 HTTP 预算、分页、身份和内容校验复用成熟传输原则；bootstrap/confirm_resume 缺证时保持 unavailable。以原 WT 消费者验证四快照一次初始化、事件连续补投、同成交多包络、缺口/换日/换流、未知回调和退出。该阶段不需要修改冻结框架。
5. **后续写入独立验收**：原签名传输、单执行许可、跨进程幂等、未知受理核查、真正恢复及账户授权分别形成证据。只读快照成功不能提高写入资格。

## 本次证据与可重跑入口

在 2026-10-21 10:23 UTC（18:23 上海时间）的只读观察中，四个 Bridge GET 均为 HTTP 200。snapshot 为 known session、语义 schema 1.2，通过当前公共模型及 hash 验证；取证时捕获年龄约 4 秒，账户与受管配置匹配，会话与 Gateway health 一致。资金和持仓字段存在，委托/成交数组为空，因此本次现场只证明空订单/成交状态，非空映射仍需独立样本。

`simulation/status` 的 PostgreSQL heartbeat 投影省略 qmt_session_id 与 account_boundary_capability；本次记录为缺字段，不能据此判定会话冲突。会话核对使用单独的 Bridge Gateway health。该 health 未提供 deployment_commit，本次源码 SHA 与线上二进制的完整对应关系未获证明；现场结构和公共模型兼容已获证明。

调查脚本和脱敏结果位于 ignored `build/native/execution-live-audit/`：

```powershell
D:/workspace/qmt/.venv/Scripts/python.exe -B build/native/execution-live-audit/read_bridge_boundary.py
D:/workspace/qmt/.venv/Scripts/python.exe -B build/native/execution-live-audit/prove_http_boundaries.py
```

第一条仅读取现有受管配置中的目标身份、现有内部令牌及四个允许的 Bridge GET，不打印或落盘账户标识、持仓明细、金额、凭证、原始异常或响应正文。输出 `bridge-readonly-observation.json`，仅含字段、计数、时间、校验结果及源码 SHA。第二条使用原 GatewayCore、公共模型和 SyncEngine 运行隔离内存反例，输出 `isolated-http-boundary-proof.json`，4 项断言通过。

完整源码身份清单保存为同目录 `input-manifest.json`；现场测试不证明当前工作树的部署身份。未调用 refresh/sync、原生 account operation、Gateway 私有 HMAC 路由或任何交易入口；未修改 QMT 文件、启动/停止服务、构建共享产物或部署。进一步现场读取若需要同步持久游标、原生账户查询或变更服务，只能按具体动作与权限另行确定。
