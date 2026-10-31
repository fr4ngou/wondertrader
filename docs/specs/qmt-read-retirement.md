# 已确认只读结果的有界回收

类型：最终功能规格。状态：accepted。适用范围：终端外只读/HPR Host、内存 Agent 与外部结果消费者。原交易、撤单及 bulk Journal 保持原契约。

## 责任与原生接缝

WT 的 Reader、Writer、策略和交易事实沿[原生能力目录](../development/wondertrader-capabilities.md)复用。本模块处理独立 QMT 通信责任：原 `BoundReadJournal` 持久结果、原 `PreparationTasks` 缓存调用身份、原 ControlPeer ACK。现有两个业务容器永久计入已完成 ID；这使持续读取在固定容量后停止。运输 ACK 已有实现，业务结果消费确认尚缺接线。

## RR1 显式兼容

独立只读/v6 HPR 部署、Agent settings 与完整认证 profile 可显式增加唯一字段 `read_retention={schema:'qmt.read-retention.v1',max_lifetime_ms:N}`，N 为 100..300000 的整数。builtin-shm/control1.0接受；显式v3账户及v4/control2.0混合通道沿[AAR](qmt-account-read-retirement.md)消费边界选择，v5 bulk继续拒绝。省略字段时，配置、profile、正文回调、Journal 及 Book 沿原行为。能力进入原 capability SHA 和配对身份；源仍由原线程、原 timer 执行固定 SDK，QMT 内无文件/网络入口或额外 SDK 线程。

## RR2 有期限、内容绑定的读取身份

新 HTTP 外层 schema 为 `qmt.bound-retained-read.v1`，字段为 `schema_version,binding_sha256,request_body_b64,request_body_sha256,ticket`。内部原八字段请求和 control `agent.read` 不变。

ticket 恰有 `schema,epoch,expires_ms`；schema=`qmt.read-ticket.v1`，epoch 为原 `binding.host_instance_id`（32 个小写十六进制字符）。Host 每个原 runtime 实例沿既有 UUID4 产生 epoch，重启/重新认证新 runtime 使用新 epoch。时间是原 `qmt.win-uptime-ms.v1` Windows GetTickCount64 毫秒；Host/Agent 使用原时钟，不用 UTC/QPC 替代。新准入须属于当前 epoch，且 `0 < expires_ms-now_ms <= max_lifetime_ms`；HPR 还须 `expires_ms == arguments.deadline_ms`。

计算 `request_id = str(uuid.uuid5(uuid.UUID(epoch), canonical({'ticket':ticket,'request':request去掉request_id}).decode('utf8')))`。canonical 使用原协议排序键、紧凑 JSON、UTF-8。correlation_id 保持原 UUID4，承担新观察的唯一 nonce。相同 ID 改动正文/截止会被拒绝；回收后原票据无法获得新的执行窗口。现存记录优先查重，原 ID 可在过期及 Host 重启后继续查询，禁止新 ID 自动重派未知请求。

## RR3 持久消费确认与回收

`POST /internal/v1/read-results/{id}/consumed` 正文恰为 `schema,request_body_sha256,result_body_sha256`，schema=`qmt.read-consumed.v1`。外部消费者先原子持久保存完整原结果和 `requested_at/received_at`，再发送 ACK；Host 不把 HTTP GET 或运输 ACK 当作消费者持久保存。Host 在原独占 SQLite 同一事务确认 body/result SHA 和 terminal，然后写消费确认；不请求来源。

仅已消费、确定完成的 terminal 责任，在原 ticket 到期或原 epoch 已结束后回收，事务删除对应 read_operations 与其一对一 retention 行并释放逻辑预算。queued、dispatching、`operation_interrupted`、`preparation_unknown` 及其他执行结果未知责任持续保留，ACK 也不能释放。原交易/撤单记录不进入此表。容量保持配置原值，状态明确统计 `queued_or_running,held_unknown,awaiting_consumer,awaiting_ticket_end`；无法回收时按真实原因拒绝新任务。

原 `GET /bound-results/{id}` 在责任回收后沿原 404 unknown_operation，404 不能推出未执行。新 `POST /internal/v1/read-results/{id}/lookup` 接受恰有 `schema,ticket,request_body_b64,request_body_sha256`，schema=`qmt.read-lookup.v1`。先校验原内容 ID；有记录返回原 200/202；无记录且票据仍有效返回 404 `read_result_unconfirmed`；已到期或 epoch 已结束返回 410 `read_ticket_ended_unretained`，仅表达该原责任不再可读，保持执行资格未知。消费者持有原持久结果时可继续读取它，缺结果且 404/410 的请求持续 pending，不能重 POST 或新 ID 重派。

专用 Journal 具有独立 schema 身份，拒绝把既有非空旧 Journal 静默迁入。账户通道的显式附加metadata准入、旧金融identity与proof保留由[AAR3](qmt-account-read-retirement.md#aar3-host回收与金融隔离)唯一规定；该接缝不改变HPR/独立读取原准入。Host 重启恢复原 queued/dispatching/terminal 规则；dispatching 转未知、仅查原 ID。保存完整结果的消费者状态位于终端外 slot；Host 可重连，新 epoch 不修改原 slot/收到时间。不同来源/参数复用 slot 明确拒绝。原生账户消费者沿AAR2的进程内完整值交付确认，无客户端slot目录；金融写继续原Journal。

## RR4 源端 HPR 缓存

显式模式复用 ControlPeer `observe_reply_ack`：Host 原 finish_bound FULL 同步提交后发送的原 ACK 到达源端，才可释放源端确定终态 Book；unknown 和运行中保留。ACK 丢失时，仅确定完成且原 HPR deadline 已结束的 Book 可回收；旧请求原 D 失效，不能再次进入 SDK。跨连接保留同一个 resident Book；终端进程重启后恢复责任归 Host 原 Journal，禁止自动重派。原 `_Completion` 的迟到 publish/cancel 在已确定退休时仅保持其原值，不能再插入条目。

`ReconnectingHistoryPreparationAgent.retention_status()` 提供纯内存观测，schema=`qmt.history-preparation-retention-status.v1`；默认返回 enabled=false，显式模式返回 enabled=true、capacity/retained/queued_or_running/awaiting_handoff/held_unknown/high_watermark/acknowledged/expired_confirmed 的整数计数。状态不触发 SDK、来源请求、回收或文件/网络访问；调用方可在原 SDK 替身循环采样。高水位由 Book 准入事务自身记录，跨同一 resident 连接代保持。

## RR5 外部调用接口与验收

`RetainedReadClient(transport,*,clock=None,lifetime_ms=...,poll_seconds=...)` 使用既有 transport.exchange/plan/rpc_budget；`read(operation,arguments,slot,*,deadline)` 返回原 `request_id,requested_at,received_at,reply`，`prepare(...)` 为同一读取调用的别名。slot 在 POST 前落盘，原完整结果在 consumed 前落盘；每个 slot 只代表一个原请求，后续业务周期使用新 slot。显式已拒绝准入可返回同 ID 待重新提交；任何通信未知后只查询原 ID。

公共纯函数 `guanheng_qmt_shm_agent.read_retention.result_confirmed(reply)` 为 Host 和消费者唯一分类：`ok=true`，或固定调用前拒绝码 `preparation_not_executed,queue_timeout,source_binding_changed,queue_full,invalid_arguments,capability_unavailable`。其他失败全部保持未知。Client 未确认/未知抛 `RetainedReadPending`，明确失败抛 `RetainedReadFailure`；完整终态仍先持久保存。AWP 与 HPR 将未知、Pending 及原 ID 查询的 404/410 映射原 SourcePending，保持原 capture/slot/ID。对于已明确未执行或拒绝的失败，原业务 owner 可结束本次观察并开始下一次独立观察；Client 自身不创建替代 ID，也不自动重派原请求。

原 POST 若得到 Host 明确的受理前 400（固定码 `invalid_arguments` 或 `read_ticket_ended`），Client 在同一 slot 保存独立 `admission_rejection`：恰为 `schema,request_id,request_body_sha256,status,error_code,observed_at`，schema=`qmt.read-admission-rejection.v1`、status=400、observed_at 为外部实际收到该拒绝的 UTC 时间。该记录属于外部消费方，不伪造原生 result；原 result 保持 null，调用抛 RetainedReadFailure。以后重读同 slot 继续该失败，不再 POST。Host 对新票据原 epoch 结束或原期限结束细化返回 read_ticket_ended。网络未知、其他无法确认受理的响应、原 ID 的 404/410、未知终态仍保持 Pending；不能从无记录推未执行，不能反推补写旧失败 slot 的拒绝记录。业务 owner 决定下一次独立观察，Client 不创建替代 ID。

先跑完整 SDK 替身 HTTP→WinSHM→原队列→HPR→原历史读取→结果落盘→消费确认→回收主链。容量 8、16 各完成超过容量十倍的连续周期，记录实际 SDK 次数、Book/Journal 最大占用、正常关闭；随后覆盖 ACK 丢失、未知保留/不增加 SDK、Host/Source 重启原 ID、变体身份拒绝、旧默认回归。普通 wheel 安装与同正文消费者独立绑定。真实 QMT、生产、长期跨日资格按对应证据另验。

## RR6 新观察与来源换代

新slot每次沿原GET read-binding取得当前完整认证，在原rpc_budget及业务deadline内构造新票据/原八字段请求。父目录BINDING.json归业务capture，不作为新请求的当前准入缓存，也不由公共Client覆盖。每个slot自身继续完整保存原binding/profile/limits/ticket。

read/prepare可显式传expected_binding（原bound完整binding纯值）。新slot当前认证与期望不同，创建slot/plan/POST之前抛RetainedReadBindingChanged（RetainedReadFailure子类）；此时没有新业务受理。旧slot先沿原ID/原binding/原result恢复，不GET当前认证或改写原票据；未知、404/410继续Pending。旧责任已确认且持久消费后，再核expected_binding，差异抛同类以交业务owner处理，原slot完整保留。

AWP的v7与HPR分别固定各自capture的原BINDING并传expected_binding。同capture换代时保留已成功旧窗口，已确认责任沿Unavailable结束该capture，下一capture重新准入；旧ID未知仍原capture等待。禁止把不同完整认证的行拼成合格快照。默认未声明回收能力的旧路径保持。验收包括原缓存短红、新业务slot跨实际Host epoch、旧slot原值/未知恢复及后继原Native/QNA/R24。

## RR7 持久回执与只读快照并存

每个slot由原业务owner单写。完整回执先写独占临时文件，flush、fsync、关闭后才提交；原请求身份、完整结果和消费顺序保持。Windows已有目标使用`ReplaceFileW`，首次发布使用独占rename；POSIX保持原replace。只读观察器共享READ/WRITE/DELETE并及时关闭，提交期间可持有完整旧快照，下次打开固定路径获得完整新快照。

发布错误保留原目标、完整临时文件及原异常，交原调用owner处理。文件提交不生成新业务请求、不自动网络重发、不跳过slot、不删除目标或改变权限。验收使用真实Windows共享删除/Node读句柄跨提交，以及不共享删除读者的确定拒绝，核实旧快照完整、新快照可见、原请求与结果不变；SDK链中核实持久消费确认与正常关闭。
