# QMT 交易通信产品与 WT 生命周期

类型：功能最终规格。状态：in-progress。前缀：THP。范围：将现有交易通信实现交付为独立安装、冻结配对、常驻 CLI 和 WT 进程 owner。原生执行器、订单计算、金融状态及 WT 框架沿现有模块。

## 事实与职责

WT 独立运行包拥有交易 Host 子进程；Host 拥有现有交易 Journal、事件分页和单代通信 runtime；QMT 策略原线程执行已实现的账户查询、下单和撤单。观衡仅作为只读消费者。

复用 `trade_bootstrap.build_trade_runtime`、`HostTradingRuntime`、`HostTradingJournal`、`SourceTradingService`、`RestrictedTradingAgent` 及原 control2/Windows SHM。配对和产品包装不另建账本、交易协议或订单算法。默认 read/HPR 产品及其 MARKET 合同保持。

当前缺口位于部署与生命周期：原交易工厂在 QA 外层调用，原只读常驻服务拒绝交易配置；源交易 agent 将业务停止与单代运输退出绑定。单代退休需要明确保留源命令、事件、未知责任，最后策略停止才完成业务关闭。本规格的连接 owner 只管理这两个生命周期边界。

## 产品接口

新模块位于 `guanheng_qmt_shm.trade_product`、`trade_pair`、`trade_control`、`trade_cli`；QMT 侧新连接 owner 位于 agent 包，兼容 Python 3.6.8 标准库。WT 父端为 `guanheng_wt_runtime.trade_host_process`。

离线配对接口：`create_product_pair(config, *, credentials, output, sdk_metadata, stdlib_license, reconnect_seconds, installed_agent=None, market=None)`。它准入原交易配置与显式写开关，冻结安装源、3.6.8 原件、policy 和正文，生成全新受当前用户 ACL 保护的目录；不创建 Journal、通信或 SDK owner。`verify_product_pair(directory, *, installed_agent=None)` 静态重建完整正文并核对每个输入字节。

配对 schema 为 `qmt.trade-product-pair.v1`，私有部署 schema 为 `qmt.trade-deployment.v1`。生成材料沿原产品形态包含 `manifest.json`、`deployment.json`、`policy.json`、`strategy.py`、可读 `host.py` 及 CPython 许可。manifest 的 `qualified_in_qmt=false`、`order_ready=false` 表示材料身份，不代替运行时能力。原写配置显式声明，原交易结果未知处理继续生效。

安装后入口：`pythonw -I -B -m guanheng_qmt_shm.trade_cli pair|verify|run`。默认显示帮助；`run` 只消费通过核验的私有配对目录。HTTP/HMAC 和 SHM 凭据只由外部 Host 持有，QMT 正文以内存形式持有配对所需参数，运行期文件和网络调用为零。

控制收据为 `qmt.trade-host-ready.v1`、`qmt.trade-host-stop.v1`、`qmt.trade-host-closed.v1`，沿原 paired-control owner 绑定 control_id、真实 PID、pair manifest/config SHA。ready 表示 Host 监听已建立；业务来源认证、账户及交易就绪由原接口分别表达。

父端 descriptor 为 `qmt.trade-host-process.v1`，字段沿原 Host 进程模型：pythonw/SHA、pair_directory/manifest SHA、installed_agent、control_root、startup_seconds、stop_seconds、max_output_bytes。`create_process(descriptor_path, expected_sha256)` 返回原 ManagedLocalProcess 协议的 `start(monotonic_deadline)`、`status()`、`request_close()`、`close(timeout)` owner。公共 WRI 由可选 `components.trade_host.kind=qmt_trade` 固定调用此工厂，原 host 继续管理 read/HPR。

## 常驻与身份

证券资料扩展显式采用v5产品：同一原策略线程在原交易、账户及可选v7/v8连接之外，追加独立v9只读owner。父端要求strategy_tick，并精确核证券资料两操作；其余原连接按存在性核原身份。完整名册/字段及版本边界沿[证券资料规格](qmt-security-reference.md)。原金融权限和未知委托职责保持。

Host 常驻等待来源，单次握手与业务请求继续使用原有限截止。来源晚于 60 秒仍可认证；运输断开后，原一代 owner 先按原绝对截止收束资源，确认后才建立下一认证代际。正常关闭收据仅在实际线程、句柄、管道、Journal 与运输 owner 均关闭后发布。

Host 使用同一原 Journal 路径，原请求 ID、command_id、命令摘要和事件身份保持。运行包装不重发已派发或未知命令，不生成替代命令 ID。源端连接 owner 在运输代际之间保留原 SourceTradingService；业务停止、未知和事件责任由该服务继续决定。运输资源已退出与交易交接已确认分别记录；关闭失败保留原 owner 和原因。

显式模式按[ADR-0017](../architecture/adr/0017-trade-authentication-continuity.md)追加同一通信库内的认证关系。旧默认入口不建附表、不接受跨 binding 续接；新模式库被旧默认打开时明确拒绝。原流 binding 和历史事件不改写，事件来源按首次持久区间核对。

当前 control2 的交易结果 reply ACK 属于原认证代际。丢失原 reply ACK 的场景保留长寿命业务未确认责任，最终 business close 报 unconfirmed；物理运输资源单独关闭。正常无遗失责任的两代验收完整业务关闭。

## 同一策略的共存接缝

现有 QST/HPR 正文由 `quote_stream_memory` 生成，其中只有一个 QuoteStreamAgent 和一个 ReconnectingHistoryPreparationAgent。交易产品保持独立合同；组合正文绑定各产品配对身份，在同一 ContextInfo 和原策略线程中装配这三个原 owner。QST 实例及其订阅只创建一次；HPR 延用原 MARKET-only 配对，交易使用独立明确的 control2 配置。

纯生成接口为 `trade_pair.render_trade_source(trade_bootstrap, *, agent_root, sdk_metadata, stdlib_license, reconnect_seconds, market=None)`，返回完整正文 bytes 与一次冻结的内存身份。显式 market 只含原 quotes、preparation 和 preparation_reconnect_seconds，Python 值的两个 secret 均为原 bytes。正式配对 `market` 参数沿同一接口冻结；CLI `pair --market-config PATH` 读取外部私有 JSON，quotes/preparation 字典将 secret 表示为 secret_hex 小写十六进制。私有 deployment 加入可选 market 快照，manifest config SHA 覆盖它；verify 还原 bytes 并重建完整正文。省略 market 保持原部署字段形状和单交易回调。文件读取只发生于 QMT 外的材料准备阶段。

组合沿三种原准入核验同 Windows 会话、独立映射和独立 IPC 秘密；只注册一个 timer，原策略线程先处理交易，再让 HPR 推进轻量连接或取得空闲重任务时隙，QST 保持原回调订阅。停止分别通知三个 owner，保留首个失败和原截止；运输及业务关闭分别报告。公共部署配置由集成者冻结后接入。

## 验收

| ID | 要求与业务结果 |
|---|---|
| THP-R1 | 无观衡普通新安装，实际 pair/verify/run CLI 与父端 owner 完整启动关闭 |
| THP-R2 | Windows SHM 和真实 3.6.8 完整内存正文，SDK 替身完成账户、持仓、订单、成交查询及单笔下单→查询→撤单、事件原身份 |
| THP-R3 | 来源晚到 65 秒、两代断开/认证，Host PID 保持，原查询/命令身份可查；未知原命令再次提交不产生第二次 SDK 调用 |
| THP-R4 | QMT 文件/网络调用计数为零，SDK 全部在原策略线程；凭据不进入日志和报告 |
| THP-R5 | 原截止内正常关闭，实际整树清零、EOF、线程 join、句柄/Journal 关闭，失败原件和未确认责任保留 |
| THP-R6 | 默认 read/HPR 及原 B 单代交易工厂保持，必要回归、独立双轴审查、离线搬迁安装和操作手册完整 |
| THP-R7 | 交易常驻服务保存本次首个已认证 HTTP 404 的固定操作类别、允许的错误类别、原读取ID、正文摘要及同机单调时间；至正常或异常关闭后，在原私有控制目录附属发布 missing-response.json。保持原HTTP响应、请求身份、截止、关闭资格及金融准入；诊断正文保留单条记录，不保存账户、凭据、任意URL或业务明细 |
| THP-R8 | 账户读取HTTP外层的可选execution_deadline_uptime_ms仅收紧首次排队期限；重复原ID/正文/B沿原事务返回同一记录、不续期。Source原正文和能力不变，金融命令沿原准入，具体再投递边界按[QAR-R5](qmt-shm-account-read.md) |
| THP-R9 | 内置SHM已经发出的业务调用等待原业务截止，多个未完成责任取最早截止；空闲及单帧发送继续原I/O预算。只读原排队上界与原保留票据在Journal域内冻结成单调截止，跨线程和UTC跳变不续期；停止只能收紧。领取结果保留原None/四元组契约与原请求身份，普通和Bulk关闭均收束原责任。见[等待窗口修正](../evidence/2026-11-04-qmt-host-reply-wait.md) |

| THP-R10 | 账户只读结果保存超期后，继续核同一原查询与持久结果；核查本身超期时沿原 Host 节拍重查，停止后受原关闭截止约束。原结果保存截止不续期，校验冲突保留故障，金融命令不重发。私有日志按请求摘要记录队列、验证、锁、事务处理、提交和核查耗时及失败阶段。 |

实施顺序：整体产品主路径、必要恢复与异常、独立审查、离线制品与交接。真实 QMT、现场 Journal、现有采集及 ETF/HPR 任务保持原运行状态。合成交易资格与真实委托、生产切换分别记录。
