# 受管分钟历史 runner

范围：显式推进 Operations 已存在的只读作业。Operations 保存唯一 job、确认检查点和 stop/resume；NativeHistoryStore 保存 DSB；原生 task 是可丢弃调度缓存。runner 不提供创建/resume/stop请求接口，仅按已有 stop_requested 确认安全停止；当前交付只经过隔离验真，没有账户/交易接口。

唯一实现在独立 SDK `integrations/guanheng_market_client/history_runner.py`，安装 wheel 后从 `guanheng_market_client.history_runner` 导入；旧 `integrations.guanheng.history_runner` 仅兼容转发。部署 owner 注入 OperationsClient、独立 SDK MarketClient、CalendarProvider、EvidenceSink 与 HistoryBinding。仅处理 `period=1m`、`policy_id=wt.history.v1`、`segment_days<=3`；dataset_version 必须等于 binding.dataset_version（wt-qmt-1m- 加完整规范绑定SHA256的前32位）。绑定保留 Qmt/agent/profile/calendar/许可、源换算与规范单位 CNY/share/CNY。

CalendarProvider.minutes(symbol,start_date,end_date,as_of) 返回 CalendarSlice。非空权威网格必须有匹配版本、排序唯一分钟，并全部处于固定 as_of 已闭合范围。空网格仅在 authoritative_empty=true、稳定非空 evidence_ref、同版本、整个日期段已在 as_of 闭合时确认；证据标记 calendar_authoritative_empty、零bars、market=null，不声明WT覆盖Complete。禁止生成工作日近似日历。

EvidenceSink.put(sha256,canonical_bytes) 返回稳定引用，get(sha256)回读原bytes；不可变内容必须与摘要一致。sink由外部受管owner实现，不是第二份可变作业账本。真实环境可适配既有对象存储；没有该owner时只具备隔离运行资格。manifest携带binding完整摘要、范围、as_of、日历/来源/覆盖/数据；checkpoint UUID为确定性逻辑请求身份，明确区别于QMT原生操作request_id与WT进程内task_id。

构造 HistoryRunner(...,budget_ms=30000)，在其创建线程调用 step(job_id,max_segments=1)。一次step限制1..64段与1..30000ms。OperationsClient/MarketClient需配置有限timeout；只有整个单调用上界可放入剩余预算才发起。Calendar/Evidence注入方必须提供有界本地调用；runner事后拒绝超预算结果，不宣称能抢占任意注入函数。不要并发调用同一runner；部署owner保证单实例，原Operations CAS提供修订保护，不提供分布式工作者租约。

推进顺序是GET原job→核绑定与旧确认manifest→query DSB→必要时task.prepare/定向work→query整网格回读→写/回读不可变证据→PUT带expected_updated_at的原checkpoint。准备/inspect/work/release始终核queue_id/task_id；已确认队列代际变化时丢弃旧短期身份并重新query；prepare回复未知或worker崩溃遗留由队列owner核查后恢复，服务中已发布DSB仍可被认领。部分数据、未知覆盖和缺日历均不确认。原Job状态 stopped/failed/succeeded只读；stop_requested在段边界确认stopped。

prepare、inspect、work 统一按已观察到的任务state准入。明确终态 Failed/Unavailable/Complete 会进入释放，当前step不再work终态；失败返回原错误码，Complete先释放并留待回查DSB，只有完整数据才确认。Pending+Backpressure保留身份而不work或release；错误空data保留未观察状态的区别。

work 回复丢失后，同一 runner 下一步先 query。DSB已完整时回收原短期任务并认领数据；仍有缺口且任务处于Active时 inspect。release 发出前进入显式Releasing阶段，保留原queue_id/task_id及已观察的终态原因。释放回复未知或背压后，下步先query，再重试同一身份的幂等release；确认成功或可信StaleSession才清身份，整个过程不回到inspect已释放id、不新增源work。释放未执行、已执行但丢回复、仍背压都保留核查依据；任意InvalidInput继续返回错误，不能代替释放成功。回收确认后，下一步按query/prepare恢复，原已确认检查点保持一次。

PUT丢回复或CAS冲突先GET；已确认相同manifest/UUID的段认领原确认，完全不同的结果保持Conflict，不盲重发PUT或改写confirmed。DSB已写但checkpoint未确认时，下一步query验证后再生成证据。最终全部段校验后写succeeded/result_ref；结果引用交由受管resolver提供给消费者，不公开主机路径或凭证。

OperationsClient只允许GET `/v1/operations/history-jobs/{uuid}` 和PUT `.../checkpoint`，X-Internal-Token从进程配置注入；HTTP仅字面回环地址，远端使用正常证书验证HTTPS，无代理/重定向/自动重试，错误不回显服务端正文。WT MarketClient使用自己的Bearer；认证材料不放job、manifest或输出。

原 owner 分支已完成[日线执行器准入验收](../evidence/2026-10-21-history-family-admission.md)：`historyjob.py run` 只接收精确日线策略/周期及请求 UUID，分钟任务在恢复、文件和子进程前明确拒绝；其通用 status/stop/resume 继续管理共享任务。分钟任务由独立 worker 推进。当前部署还需安装 owner 候选、绑定真实权威日历/存储、确认 Operations 可达性，并提供正式 runtime 工厂与进程监督。WT 结果继续保留自身证据身份，原 QMTHistoryCaptureProgress 与 Gateway 终态证明由原链路提供。

隔离验证：

```powershell
python -B tests/integration/history_runner/test_history_runner.py
```

可选设置 GH_QMT_SOURCE_ROOT 后，额外使用该源根的原纯DTO与 InMemoryOperationsRepository 跑同一真实loopbackHTTP链；缺少源根仅skip该oracle用例，其余标准库测试照常执行。测试不连接真实数据库、服务或账户。

独立受管执行入口（SDK 0.4.0 起）遵循 [HW 规格](../specs/history-worker.md)。部署者安装自己的可信 Python 模块，公开零参数工厂，在调用线程仅构造尚未推进的 HistoryRunner。工厂从受管环境注入凭据、固定服务地址/binding、权威日历与受限证据 sink；job 中的数据不能决定工厂代码或远端地址。没有合格的分钟日历实现时保持隔离资格。

下面的名称、UUID 与路径均为部署形态示例，实际资源由运行 owner 提供，锁目录须预先创建：

```text
python -B -m guanheng_market_client.history_worker --job-id 00000000-0000-4000-8000-000000000001 --factory managed_history:create_runner --lock-dir E:/managed/history-locks --max-steps 100 --max-seconds 300 --wait-seconds 1 --max-segments 1 --drain-attempts 3 --drain-seconds 35
```

操作参数有固定上界，关闭总窗口默认 35 秒、上限 60 秒，必须严格大于所注入 runner 的单次预算；相等或更小在调度前拒绝。完整 step/close 预算能装入剩余总预算才准入。SIGINT/SIGTERM 停止新增调度，在本步返回后排空；运行 supervisor 负责不可抢占依赖的硬截止。信号退出保持原作业状态，控制台用户 stop 仍由 Operations 请求并在安全边界确认。进程锁持有到排空结束；同一可靠本机锁目录可阻止同 job 重复进程，跨机器的分配/单副本仍由部署方保证。残留一字节锁文件不表示活动工作者，不要按文件存在判断锁状态。

运行诊断 stdout 仅输出 started/step/drain/exited 或配置/启动错误的固定 JSON 事件，保留 UUID、状态及计数，不输出远端 reason、result_ref、异常文本或凭据。`--help` 是独立的固定帮助文本入口，不加载工厂或访问远端。退出码 0 表示已观察原终态且排空，原作业是 succeeded/stopped/failed 仍应查 Operations；2 为配置/锁冲突，3 为本地有界暂停且排空，4 为回收未确认，5 为不可继续的步骤错误且排空。4 优先报告，不能以普通重启消除该诊断。

`HistoryRunner.close()` 在当前线程关闭新 step 受理，每次最多 release 一个已知短期任务；重复调用可以完成未知回复/背压后的同身份释放。返回 CloseResult 的 status、pending_task、recovery_required 分别表示本次观察、已知任务与队列 owner 恢复需求。close 不查询或写 Operations，也不推进 work。准备可能已受理而回复未知时，编号可能已丢失；后续发现 DSB 或新编号不能证明旧终态对象已回收。该风险以保守内存标记保留，交给独占队列的受管回收流程。崩溃遗留同样由队列 owner 处理；启动器不重启共享市场服务、不建立 task-id 账本。

启动/进程恢复测试入口为 `tests/integration/history_worker`；可设置 `GH_HISTORY_WORKER_SITE` 指向独立 wheel 安装目录，子进程使用 `-I -S` 且仅注入该目录和合成部署工厂，验证离仓实际作业调用链。
