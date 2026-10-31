# QMT历史缓存补齐

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块说明。状态：开发及独立产品入口已实现，工程与实际终端资格分别验收。适用范围：显式v6、同机内置SHM、原策略线程；要求正文为[HPR](../specs/qmt-history-preparation.md)，架构依据为[ADR-0014](../architecture/adr/0014-history-cache-preparation.md)。

## 接口与执行链

Host专用入口为`guanheng_qmt_shm.history_preparation_bootstrap.build_read_service(config, credentials=..., reconnect_seconds=...)`；单代入口为同模块`build_runtime`。它们创建原Server可管理的服务，沿原read-binding、bound-operations及bound-results路由。原工厂、CLI及默认Agent保持关闭。

终端专用入口为`guanheng_qmt_shm_agent.history_preparation_agent.ReconnectingHistoryPreparationAgent(context, trusted_bootstrap=..., reconnect_seconds=..., enabled=True, download_history_data=...)`。固定callable来自策略全局`download_history_data`；I/O只验证并送原队列，原策略线程tick执行四个位置参数。所有周期共用原队列额度，每次tick最多调用一次SDK。未授交易。

`history_preparation.limits/arguments`拥有纯合同；`PreparationTasks`拥有有限进程内任务身份；`HistoryPreparationJournal`扩展原通信持久化恢复分类；原reconnecting owner拥有代际退休和关闭。它们不增加账户/订单/金融数据存储。

## 显式配置及请求

在原Host配置中显式选择read_profile_version=`qmt.read-profile.v6`，read_operations包含`market.history_prepare`及至少一个原读取操作；operation_profiles分别完整提供，control_profile保持原1.0。正式limits.v2省略证券清单，按来源支持的沪深代码接收请求；旧limits.v1继续原已签清单。周期和预算要求精确见HPR2。专用`agent_settings(config, policies, secret)`沿原装配器只设置该profile要求的max_pending，配置仍冻结后生效。

以下是合成请求arguments示例，deadline_ms必须由Host已核同机共享时钟按本次授权原D生成，示例数值不直接用于真实运行：

```json
{"symbol":"510300.SH","period":"1d","start_time":"20211101","end_time":"20211105","clock_schema":"qmt.win-uptime-ms.v1","deadline_ms":1004000}
```

原八字段request的operation_id为`market.history_prepare`，policy_id为`qmt.history-preparation.v1`、policy_version=`1.0`、priority_class=`normal`，timeout_ms不超过descriptor执行预算。先读认证binding，按其完整profile及SHA提交一次。相同ID只查询原结果；不同内容或不同来源绑定拒绝。

原policy必须单次、无retryable错误和退避；排队加执行预算不超过scope.total_timeout_ms，Host记录总数不超过scope.max_tasks。scope是全部保留身份的额度，终态也占额度；满额由维护者显式安排新的受管生命周期，运行时不逐出或自动替换请求ID。

显式 `read_retention` 后继见[已确认读责任回收](qmt-read-retirement.md)：scope 仍限制未退休责任，确定完成经持久交接后可回收；unknown 和执行中继续持有原 ID。省略该字段继续以上原保留语义。

## 结果及恢复

`ok=true`只表示固定函数在原D内返回，data.effect=`call_returned`、coverage=`unknown`。SDK返回正文和异常正文均不外传。进入调用后的失败统一为`preparation_unknown`；原队列过期及调用前关闭为`preparation_not_executed`。Host派发后失联和重启按未知保存，原Journal不重派。

补齐后另用原历史接口回读日期、数量及内容。任务成功不自动授完整日历、尾部、单位或可获知时间。发生未知时保留原ID先回读，只有新的明确人工授权才能形成新副作用请求。SDK不能强制中断，关闭超期仍持有原调用owner，待其返回后才能确认关闭或恢复新代。

## 离线配对与验证

`guanheng_qmt_shm.history_preparation_pair.create_pair(config, agent_root=..., credentials=..., output=..., sdk_metadata=..., stdlib_license=..., reconnect_seconds=...)`复用原冻结memory runtime和常驻回调，只额外注入固定全局download函数。它只生成新E盘私有目录，不安装/启动终端；SDK元数据及CPython许可沿原冻结器核身份。新manifest schema为`qmt.history-preparation-pair.v1`，qualified_in_qmt与order_ready保持false。该开发配对不接入旧CLI verify，加载前由操作owner核新manifest完整文件、来源清单及配置身份。

可复现隔离入口见测试说明（外部历史/待归仓路径：`../../tests/integration/qmt_history_preparation/README.md`）。真实HTTP/WinSHM主链只使用合成Context及下载替身；回读保持原History1mAdapter，下载替身是新增bar的唯一写入者。真实全局函数、目标QMT实例、1d历史回读及完整来源覆盖由主会话实际验收。

## HPR5独立产品入口

产品使用`history_preparation_product.create_product_pair/verify_product_pair/build_product_runtime`及专用`python -m guanheng_qmt_shm.history_preparation_cli pair|verify|run`。新schema为qmt.history-preparation-product-pair.v1，包含同条目QST+HPR完整正文；上述旧开发配对不混入此schema。组合生成唯一实现是Host包的`quote_stream_memory`，旧脚本只是CLI转调，quote-only/diagnostics默认正文保持。

产品verify不执行host.py或策略。它核固定文件全集、原policy无类型强转/额外权限、部署/凭据角色、实际两端安装源、目标SDK/许可/闭包及完整重建正文。核验结束再次读取固定材料以拒绝重建期间的漂移。正式Host从该次私有快照启动常驻服务；原policy不再打开第二次。两个映射及IPC secret分角色，组合只注入固定download全局函数。

产品Journal按全部声明max_records的最坏请求、结果及元数据完整预留。满额返回503/journal_capacity_exhausted，原结果仍可读。原普通Host错误与默认行为保持。产品ready/closed完整写入私有临时文件并原子发布；复用原paired-control监控/原关闭D，避免父端读取正在创建的收据。ready只授HTTP监听，来源可以长期晚到。

父层薄适配为`guanheng_wt_runtime.history_preparation_process.HistoryPreparationProcessConfig/HistoryPreparationProcess`，直接复用原ManagedLocalProcess。无配置为disabled；start(absolute_deadline)、request_close()、close(seconds)、status()保持同一父层合同。配置只含pythonw/manifest/安装路径SHA及有限启停预算，父端不导入Host或凭据。独立WT在components.host选择qmt_history_preparation，负责原进程生命周期；观衡仅读取公开状态，运行合同见[WRI](../specs/independent-wt-runtime.md)。

独立构建、配对与托管步骤见[产品手册](../runbooks/qmt-history-preparation.md)，安装/搬迁/完整3.6正文工程验收见产品测试入口（外部历史/待归仓路径：`../../tests/integration/qmt_history_preparation_product/README.md`）。

### 与原行情条目组合

`scripts/qmt_quote_stream_memory.py` 的 `render_strategy/generate` 接受显式 `history_bootstrap` 和 `history_reconnect_seconds`。提供时，同一正文装配原 QuoteStreamAgent 和本模块 ReconnectingHistoryPreparationAgent；固定注入仅增加 download_history_data。报价回调与历史队列各守原职责，下载仍由原 run_time 回调线程执行。两个独立认证映射要求同一 Windows 会话、不同最终名称；配置只允许行情、分钟读取和历史补齐。

未提供该参数时保持原纯行情正文路径。组合与诊断分别选择；部分启动失败或 stop 时两个 owner 都收到停止请求，启动根因和清理失败分别保留。真正资源关闭由各自原生命周期管理。合同见[QST8](../specs/qmt-quote-stream.md#qst8-原行情条目的可选历史补齐装配)，完整冻结正文及目标解释器验证见组合测试入口（外部历史/待归仓路径：`../../tests/integration/qmt_quote_stream/README.md`）。终端内不新增文件、网络或交易能力；安装、实际下载与持续采集分别验收。
