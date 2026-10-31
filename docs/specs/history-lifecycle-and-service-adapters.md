# 长历史准备生命周期与独立消费者

类型：功能最终规格。状态：accepted。用户已设置持续移植目标；本规格细化[HTTP 行情规格](qmt-http-market.md)后续的容量、恢复、独立发行及观衡作业接入。保持原 QMT 主工作区只读，不切换生产服务或执行真实交易。

## HSA-R1 事实所有者与范围

DSB 与来源元数据继续由 NativeHistoryStore 持有；HistoryPreparationQueue 只持有有界、可丢弃的准备任务。观衡 Operations 继续是持久作业、已确认断点及 stop/resume 的唯一 owner。新增 runner 不建立第二份业务作业数据库，也不把 WT 内存编号当作持久任务身份。

本轮保持以权威 expected_minutes/calendar_version 判定补齐；缺少依据仍 Pending/Unknown。无网格来源采集需要单独定义源页完成目标，当前不将它包装为覆盖 Complete。共享内存、TDX 交易、账户与正式发布维持原边界。

## HSA-R2 原生准备任务

复用 inspect(id)，新增 work_one(id=0) 定向推进与 release(id) 显式释放。id=0 保留既有 FIFO work 入口。释放允许丢弃非运行任务及其未发布暂存，既有 DSB 保持；worker 运行期间统一返回 Backpressure，保护解锁后 vector index 回写。重复释放同一实例中已移除的非零 id 为幂等成功；零 id 拒绝。

只对 Pending 任务去重。终态任务的相同请求重新查询 Store 当前状态，避免 Complete/Unavailable/Failed 缓存遮蔽修订或恢复；调用者显式释放旧任务后回收容量。超过容量仍清楚背压，不暗自淘汰调用者尚需核查的对象。

## HSA-R3 外部任务身份与兼容

保留既有 history.prepare/history.work 的返回结构和行为。新增四个独立动作 history.task.prepare、history.task.inspect、history.task.work、history.task.release；对应 POST /api/market/v1/history/task/{prepare,inspect,work,release}。新 prepare 接收 request，与既有历史请求字段一致；其余动作接收 queue_id 与 task_id。

每个原生 Bridge 实例以系统随机源创建新的 32 位小写十六进制 queue_id；即使底层来源相同，也不能跨实例复用。新动作响应 data 固定 queue_id、task_id、state；state 为 Pending/Complete/Unavailable/Failed/Released。release 成功使用 Released；未知 inspect/work 返回 InvalidInput，错误 data 可为空。queue_id 不匹配返回 StaleSession 且不推进/释放任何对象。新 prepare 若 id=0 的拒绝保留失败状态，不授予有效任务身份。

客户端严格校验字段、身份、状态与结果，未知新动作由旧服务明确 NotSupported。恢复依赖重新 query DSB，再按缺口 prepare，不持久化数值 task_id，不重放旧 queue_id。服务故障、请求超时与远端已完成分别处理；无无限轮询或自动切源。

新 task 非空 data 的 code/state 一致性：Complete 仅配 Ok；Released 仅 release 动作配 Ok；Pending 仅配 Pending 或 Backpressure；Unavailable 仅配 Unavailable 或 NotSupported；Failed 配其余错误码（包括竞争时 Backpressure），不能配 Ok、Pending、Unavailable 或 NotSupported。Ok 必须对应 Complete 或合法 Released；Pending 错误码必须对应 Pending。错误 data={} 继续允许，失败 release 返回空 data，避免捏造尚未观察的任务状态。原有非 task 动作保持既有协议。

## HSA-R4 独立客户端发行

将纯标准库协议/HTTP 客户端的唯一实现放入 integrations/guanheng_market_client，独立 import 为 guanheng_market_client。原 integrations.guanheng.market_client 仅保留兼容导出，无复制实现。原生包包含同一规范实现；观衡消费者安装独立 wheel 即可运行，不需要 WT DLL、wtpy、QMT checkout 或整个观衡源码。

标准库 Operations 薄 runner 同样由该 SDK 的 history_runner 子模块唯一维护，原路径只兼容转发；独立 Operations 安装 wheel 后可直接注入原日历/证据 owner 使用。此发行包含接口适配和有界调度，不复制原数据库、状态归约、日历或交易规则。

采用标准 PEP 517/Flit 构建，构建 backend 版本及下载摘要固定在受管 lock；生成物、临时文件和隔离安装均在 E: 构建根。SDK 版本由包声明唯一维护，协议版本与包版本分别表达。验证 wheel 的清单、无私有/原生依赖、离开仓库的隔离 Python import 及实际 HTTP 消费。

## HSA-R5 Operations 薄 runner

新增显式启动的受控 runner，使用原 GET history-jobs/{job_id} 与 PUT checkpoint 接口、X-Internal-Token、expected_updated_at CAS 和原 HistoryJobCheckpoint DTO。只处理 period=1m、policy_id=wt.history.v1 的显式 job_id；拒绝其他 family、周期及旧日线 runner 的结果，保持接口单次传输、无盲重试。

原生服务 binding（Qmt provider、agent_id、profile_version、calendar_version、单位/许可要求）以规范 JSON SHA-256 固定；dataset_version 必须为 wt-qmt-1m- 加该摘要前 32 位，使现有不可变 JobSpec 的 request_sha256 包含绑定身份。manifest 保留完整 binding 摘要。只处理日期段，segment_days<=3，每回合显式限制段数和时间；交易分钟来自注入的权威 calendar provider，禁止自行生成工作日近似日历。

每段先 query；缺口才 task.prepare/定向 task.work，检查 queue_id、来源、profile、日历、全部 expected grid 和归一单位。确认数据后构造规范证据摘要/确定性 UUID 请求身份，向现有 Operations 提交 confirmed checkpoint；结果引用由注入的受管 evidence sink 提供，runner 不伪造原 QMT 原生 capture 证明。CAS 冲突或丢回复先 GET 重读，不重复增加确认；已确认段保持不可改写。停止在安全段边界响应，不推进 stopped/failed/succeeded job。

每步先回查 DSB；保留的短期任务通过 inspect 确认状态。明确观察到 Complete/Failed/Unavailable 终态时释放该任务并清除短期身份，保留真实失败原因或完整数据结果，后续步重新 query/prepare；源恢复后同一 runner 可以继续。Pending 的临时背压、空错误响应及丢回复保持未知/暂态区别，不能据此推断任务已终结或盲目重发 work。

release 发出后保留显式 Releasing 短期阶段，只有确认成功或可信 queue_id 变更才清除；释放可能已执行但回复丢失时，下步先回查 DSB，再以同一 queue_id/task_id 重试幂等 release，避免退回 inspect 已释放任务。释放背压、尚未执行和结果未知分别保留重试依据；任意 InvalidInput 均不能代替释放成功证明。该阶段不创建持久任务账本，不增加源 work 次数。

权威日历空段单独处理：CalendarSlice 明确 authoritative_empty=true、与 binding 相同的版本及受管 evidence_ref，且整个日期范围已在 job.as_of 前结束时，可确认零 bars 的 calendar_only 段。manifest 保留日期范围、as_of、日历版本/引用与 calendar_authoritative_empty 完成依据；不标记 WT source coverage Complete，也不为此调用市场 prepare。空网格缺上述任一依据仍 Pending，不能根据周末或工作日猜测。

没有真实 calendar/evidence sink、原 Operations 可达性或新 family 路由保护时只提供隔离运行资格。原 historyjob.py 对子进程周期存在旧日线限制，该旧入口不能执行新 family；真实启用前由原 owner 加入正确路由/拒绝规则。此缺项不阻止新 runner 的原契约隔离验证。

## HSA-R6 业务接口适配资格

原 MarketData /bars 只保存 MarketBar、不发布特征事件，也不具备本轮来源/profile/许可/资格字段；原时间/原生量额口径与 WT 标准右端股/元分别核实。当前不直接投喂策略或伪造 QMT-only 合格分析窗口，不给纯市场快照捏造账户字段。保留真实适配断点与原 owner 的升级入口，SDK 与 Operations 接入先交付确定部分。

## HSA-R7 验证与交付

覆盖超过 64 个窗口顺序准备/回读/释放、定向工作互不推进、释放与 worker 并发、重复释放、损坏后的终态重检、服务重启旧实例拒绝、已发布 DSB 查询恢复、原 schema/只读链路继续兼容。SDK 隔离安装后运行真实 HTTP；runner 使用原 Operations 纯 DTO/状态归约和假 HTTP，不连接生产数据库或账户。异常包括部分页、未知覆盖、错误 binding、CAS/停止/回复丢失与中断恢复。完成源码后 full 独立审查，打包与模块/手册/证据一起交付；整体移植继续保持 active，实机缺项单列。

## HSA-R8 所有权

行情 Agent：History.h/.cpp 的 queue 接口及独立新 lifecycle 测试；不改其他 Store 语义。业务 Agent：独立 SDK 规范实现、旧客户端兼容导出、新 task 客户端/服务路由校验及相关 service 测试。执行 Agent：Operations 客户端/薄 runner 及其独立测试/手册。主 Agent：规格、原生 JSON ABI task 接线/queue_id、Flit 构建锁及工具、CMake/制品/隔离集成、审查和状态。共享接口先冻结，只有主 Agent 执行 Ninja。
