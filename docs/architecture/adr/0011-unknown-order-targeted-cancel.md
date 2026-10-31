# ADR-0011 未知委托的取消沿原通信owner按操作准入

状态：accepted（架构决定）；实施和动态资格分段确认。唯一实施契约为[UC规格](../../specs/qmt-unknown-cancel.md)；当前接受源端/Host/Journal闭包，Common/Standard新增预算完成证明后再开发。本文件记录职责和取舍，不另设行为版本。

现有原命令 Journal、真实事件/ORDER 查询已能说明订单属于哪条已派发委托。unknown 既关闭 insert，也经 Standard/Common/Host/Agent 的共用布尔门关闭 cancel。Agent 更把 source_unknown 填入首 fault、关闭 kernel，并通过顶层 gap 传给 Host；后续硬故障可能被首诊断遮住。仅放开单层将留下实际派发阻断或安全缺口。

采用统一按操作准入：未知结果保留原 UUID/body/phase，整体新 insert 继续关闭；目标明确的 cancel 在真实当前 proof、原账户/开关/live、健康来源、无硬故障和关闭的条件下可执行。source/host-status.v2 明确声明此语义，旧源未知取消保持拒绝；原 profile SHA、Journal 身份与订单命令 wire 保持。状态版本是来源实现契约，不是新的人工资格。

原 Journal 在既有事务内确保每 original insert 最多一条未决实际 cancel。竞争请求返回固定 cancel_pending，新的只读 cancel lookup 可取原目标最新实际取消（包含终态）的私有已验 receipt。丢响应时自己的原 UUID 与目标实际取消分别核查；不得把一个独立观察伪装成本次请求成功。Standard 只读审计复用原 worker/队列，真实 ORDER proof 由原 Host 保存；审计不重复给 WT 投整批查询，也不建立第二订单/金融状态机。

## 持久 coalesced 别名的比较

曾考虑在 trade_commands 增加 nullable coalesced_command_id，把竞争输者保存成 definitely_not_called、host_reason=cancel_coalesced，引用实际 cancel；另需 bound-trade.v2、迁移/降级拒绝、别名完整性、双收据预算与消费者解释。

它唯一额外解决的是：响应丢失后，精确证明“未实际派发的请求 A 当时被归并到哪个 B”，进而把 A 的用户显示归并为 B 的完成。查询现有记录无法证明这个历史关联，因为 A 没有入库，而且稍后最新实际 cancel 可能已经是 C。该不可证明之处是真实的，不能用 pending/latest 查询冒充持久别名。

本目标需要保留 A 的未知与 B/C 的独立事实，并防止重复 SDK；不要求给 A 追认成功。原 UUID GET+只读目标 cancel lookup 已能保证实际记录不丢、无再 POST，且快终态仍可查。A 从未到达 Host 时即使有别名表也没有可写的关联，仍只能保留未知；别名并不能消除所有无记录窗口。

因此推荐不增加别名列/表/状态。只有将来明确要求历史请求别名审计时再提出独立需求和 ADR。此取舍降低迁移、兼容和重复状态解释成本，同时诚实保留未可证明事实。

代价：某个丢响应且未入库的 A 可能长期保持未知，即便目标订单已有其他实际取消或已经终结；诊断必须分别显示，不能为了“全部请求变成功”改通信历史。原 WT 业务订单可由真实回报终结，它与 A 的调用结果不是同一事实。

本决定不改变 WT 框架、真实交易授权、生产 Factory 或持仓基线交接。实施、替身验证、真实 SDK 验证与发布分别登记。

## 后继恢复边界

本切片unknown仍持续阻止新insert，重启不清原Journal unknown。一般恢复交易必须另按真实证据设计解除/处置，不删除原通信记录或改造SDK调用阶段。当前架构决定和限定取消实现均不代表一般恢复已完成。
