# QMT SHM 独立只读连接包

新电脑部署入口：[通信架构与配对入门](../../docs/runbooks/qmt-connection-onboarding.md)。可填写模板位于 [examples/qmt-trade-config.example.json](examples/qmt-trade-config.example.json) 和 [examples/qmt-operation-policy.example.json](examples/qmt-operation-policy.example.json)，使用虚构账户并关闭交易写入；实际运行资格按对应部署验收核实。下文旧阶段版本与验收范围按各段对应记录阅读。

交易开发状态：原委托关联、原生C++客户端及显式account2.0运输已接通；STQ-P7现复用唯一金融mapper，将完整token证明恢复为WT原EntrustID/UserTag，external/unresolved保留真实金融批次。529项兼容回归、六组原生CTest（57身份与128旧金融场景）及真实共享内存闭环通过。标准TraderQMT生产Factory/SPI、消费恢复、正式独立安装及真实券商交易继续开发；已安装只读入口保持。详见[标准插件规格](../../docs/specs/native-qmt-standard-trader.md)和[账户身份验证](../../docs/evidence/2026-10-24-qmt-account-identity.md)。

控制2静态定义由终端外构建工具生成：在仓库根执行`python -B scripts/generate_qmt_trade_control.py`，校验执行`python -B scripts/generate_qmt_trade_control.py --check`。工具读取固定base1.0和差异JSON，精确保留uint64及原base摘要，生成Agent包内control_wire_trade.py；QMT运行阶段只使用嵌入源码，不读取协议文件。修改消息字段先更新QST，生成后验证默认旧版本拒绝新包及各版本原截止/ACK行为。

当前源码为Agent 0.1.0a3／Host 0.1.0a4开发候选，支持显式v3账户组合profile及QSW-R12无文件策略。独立安装、目标Python3.6.8和合成共享内存证据见[内存接入记录](../../docs/evidence/2026-10-23-qmt-memory-entry.md)；真实券商终端、账户与生产资格分别验收，order_ready=false保持。开发候选以完整源码及安装摘要区分，版本号本身不转授资格。

内部私有制品：`Private :: Do Not Upload`。保留原源码头和来源摘要；用户授权内部迁入，不推断公开再分发许可。唯一行为要求见[QSW](../../docs/specs/qmt-shm-wt-binding.md)。

`agent/`发行`guanheng-qmt-shm-agent`，Python3.6.8+、仅标准库；`host/`发行`guanheng-qmt-shm-host`，Python3.10+、独立锁定Agent及HTTP/DTO依赖。实际版本资格按冻结安装证据核实。Host在终端外运行；旧shm模式由策略从受管Agent目录加载，新builtin-shm模式由QMT加载完整生成策略正文，Agent目录只作终端外冻结/验证来源。构建、运行和维护都不依赖旧`qmt_platform`、旧`qmt_agent`、旧venv、PostgreSQL或Docker。

Agent a2 / Host a3显式允许`market.full_tick`或`market.history_1m`与base control 1.0，要求见[QH](../../docs/specs/qmt-shm-history.md)。保留原Session、SHM帧/环、ACL和可靠CALL/REPLY/ACK。账户、下载、订阅、订单、撤单及扩展control版本不可用；`order_ready=false`。运输不解释行情量/额单位，券商登录、实时性和交易资格分别验证。

full_tick-only保持原v1完整profile及原字节。启用history必须在Host配置和Agent bootstrap显式增加`read_profile_version=qmt.read-profile.v2`和`operation_profiles`，每项精确包含policy_id/policy_version/execution_timeout_ms/limits；操作集合排序唯一，global timeout等于各项最大值。history limits明确schema/max_calendar_days/max_rows/max_data_bytes，联合实际result/frame/control/HTTP/Journal额度。共用标准库read_capabilities拥有这些准入规则，返回独立普通dict；v2所有入口传实际max_result_bytes，缺少上下文拒绝。

历史只读调用固定`get_market_data_ex`的1m/none/fillfalse/subscribefalse，不加载SDK模块或下载。日期/rows/标量/实际bytes/单截止有界，饱和整批拒绝，空返回及缺分钟原因/单位/覆盖保留unknown。旧C++full_tick客户端对新profile严格拒绝；新历史阶段、多能力组合和真实终端分别验证，多个Host/Agent不构成现场并用证明。Journal终态仍保留reservation，满额拒绝；没有自动归档/删除/透明换代。

## 无文件模式与运输选择

运输选择独立于读取能力profile：旧kind=shm保留原九字段及配对v1；新kind=builtin-shm精确接受schema_version/kind/name/max_mapped_bytes/poll_seconds/windows_session_id，schema_version固定qmt.builtin-shm.v1。两者没有默认转换。新后端使用内建mmap，Host负责私有Windows对象创建；旧对象协议和旧测试资格保持原范围。

内存配对v2在终端外冻结Agent及目标CPython3.6.8完整传递源码、实际内建模块身份和CPython许可，策略正文为ASCII。终端内不读配置/外部包或加载DLL；Host仍可正常读写运行材料、认证HTTP和通信Journal。私有warnings容器与借用宿主线程记录独立，owned I/O线程仍沿原生Thread/join；该加载器只装配受信闭包，不是通用Python沙箱。MEM-G1及真实券商环境按精确制品另验。

## 安装与部署材料

使用本轮冻结wheel及其requirements.lock，在新的终端外Host环境中离线安装。Python3.6 Agent可安装单独标准库wheel，或用Host导出的白名单源ZIP安装到新的受管目录。以下是命令形状，路径由部署owner明确提供，示例均不代表当前运行实例：

```text
<HostPython> -I -B -m guanheng_qmt_shm export-agent --output <新E盘ZIP>
<HostPython> -I -B -m guanheng_qmt_shm install-agent --archive <ZIP> --output <新受控E盘目录>
<HostPython> -I -B -m guanheng_qmt_shm check --config <私有Host配置>
<HostPython> -I -B -m guanheng_qmt_shm pair --config <旧shm的Host配置> --agent-config <对应Agent配置> --installed-agent <Agent包绝对目录> --output <新配对目录>
<HostPython> -I -B -m guanheng_qmt_shm pair --config <builtin-shm的Host配置> --agent-config <对应Agent配置> --installed-agent <Agent包绝对目录> --memory-sdk-manifest <目标SDK元数据JSON> --stdlib-license <CPython许可> --output <新内存配对目录>
<HostPython> -I -B -m guanheng_qmt_shm verify --directory <配对目录> --installed-agent <新Agent包绝对目录>
<HostPython> -I -B <配对目录>/host.py
```

新内存入口的SDK元数据由外部构建/维护阶段在实际目标解释器采集，字段与qmt.memory-sdk.v1严格一致；配对生成器不自动启动解释器。许可、实际解释器/DLL和源码摘要不符即拒绝。v2额外输出CPYTHON-LICENSE.txt和memory_runtime身份；verify从当前安装及目标SDK重建全文并逐字节比较，不能只核manifest自报SHA。

配对输出含私有凭证，创建时即施加当前用户保护DACL；目录/文件独占新建，manifest最后写入。配对会冻结实际Host/Agent源、策略/Host生成字节及私有policy副本；源policy后继修改不会漂移到该配对。验证只读来源字节，生成/验证/检查不启动Host、QMT或SDK，不打开Journal。命令成功只授材料身份一致，`qualified_in_qmt=false`保持。实际加载前沿国信操作手册重新核对本轮制品与接入窗口。

以下为full_tick的v1配置基线；历史v2和账户v3的显式扩展字段分别沿QH/QAR，不从该基线推断全部能力。

配置精确字段：`route,ipc_secret_env,http_secret_env,http_key_id,journal_path,max_records,max_result_bytes,max_journal_bytes,max_frame,max_http_inflight,read_operations,operation_policies_path,listen_host,listen_port,connect_seconds,io_seconds,transport,control_profile`。环境引用只在CLI解析，HTTP与IPC凭证须分角色；API显式传入`credentials={"ipc_secret":bytes,"http_keys":{key_id:secret}}`。`read_operations`精确为`["market.full_tick"]`；SHM/control配置沿原协议严格校验，不选择默认账户或交易模式。`max_journal_bytes`是原请求实际字节、最大终态与16384B元数据预留的累计逻辑预算，不是SQLite物理文件/页/WAL/索引或磁盘硬配额。

## 公开API与线程

```python
from guanheng_qmt_shm import build_runtime, create_server, run_server, HostRequest
runtime = build_runtime(config, credentials=credentials)
run_server(runtime, http_keys=credentials["http_keys"])
# 自行管理循环时使用 create_server(...)；server.request_close()建立
# 一次关闭期限，server.close()确认退出。run及配对入口共用此owner。

from guanheng_qmt_shm_agent import RestrictedReadAgent
agent = RestrictedReadAgent(context, trusted_bootstrap=bootstrap)
agent.start()       # 启动认证I/O owner
agent.tick()        # 只在原context/策略线程，最多一次显式已准入的原生读取
agent.request_close()  # QMT stop只请求关闭，不能join/native stop/release
agent.close(absolute_monotonic_deadline)  # 管理线程确认退出
```

v1 bootstrap精确字段：`route,secret(bytes),allowed_operations,execution_timeout_ms,max_frame,max_pending,max_result_bytes,connect_seconds,io_seconds,transport,control_profile`；v2再增加上述两个显式字段。构造只复制/校验内存，SDK仅由`tick()`触发。Host `build_runtime`先完整配置准入，再获取本地独占通信Journal，因而会创建/恢复该文件和owner锁；它不会启动HTTP或SHM。Host原生结果保存与请求认领属于域worker；I/O不等待SQLite事务，QMT线程不等待I/O/持久化。

`runtime.request(HostRequest(...))`支持`binding.read`、`bound.submit`、`bound.result`；HTTP三路精确DTO与预算见QSW。关闭先置统一stop准入条件并唤醒；`close(deadline)`沿同一外层截止确认ready锁、I/O和域线程收敛，超时保留Journal/channel owner供后续关闭。SHM view/句柄仍只由创建I/O owner在其finally释放。单次SDK调用及操作系统文件/内核调用自身具有非抢占边界；Python线程不会承诺硬打断SDK。

`max_http_inflight`必填且为1..128精确整数；应用ASGI入口在读取body之前非等待准入，从接收到最终响应/断连/取消占一个位置。每个路由完整body共用一次`io_seconds`接收窗口及`max_frame`字节上限，慢分块不会延长窗口。Uvicorn0.51的上游并发判断为当前连接数或任务数`>=limit_concurrency`，包含本次连接，因此服务器阈值设为`max_http_inflight+1`，应用仍严格限制N个请求。空闲keepalive连接也占上游连接计数，超时设为`io_seconds`；上游超额直接返回固定明文503，应用超额返回固定JSON503。此配置约束处理/背压，不承诺TCP总连接、监听积压、未收完header的连接或整个进程内存上限。

owned Server停止开始即关闭业务准入；shutdown hook在Uvicorn排空HTTP前撤ready并唤醒IPC，graceful/lifespan/finally共用首次`monotonic()+io_seconds+1`窗口。上游0.1秒排空起步计入同一窗口，并为后续关闭保留余量。超期保留尚未释放的owner并使CLI失败；已成功关闭的owner可重复确认。`create_app`是低层ASGI组合接口；替换owned Server的调用方须自行提供同等关闭通知和整体期限，不从单独ASGI lifespan推断提前撤ready资格。

## 请求身份与通信Journal

显式交易开发API为`guanheng_qmt_shm.trade_bootstrap.build_trade_runtime(config, credentials=...)`，请求值为`guanheng_qmt_shm.trade_bound.HostTradeRequest`。Host配置在完整v4私有配置上另给`event_storage`与`event_poll_seconds`；源策略继续使用原交易配置，不接收Host存储预算。工厂默认采用已核GetTickCount64时钟，构造只取得通信存储owner，启动和关闭仍由同一Server负责。旧CLI run/check/pair及旧build_runtime继续拒绝v4，交易安装材料尚待另行贯通。

交易认证出口为GET `/internal/v1/trade-status`、POST `/internal/v1/trade-commands`、GET `/internal/v1/trade-commands/{UUID}`、POST `/internal/v1/trade-events`及POST `/internal/v1/trade-order-lookup`。提交保留原业务截止；相同命令重取原记录，写开关正常关闭不影响原结果查询。原委托查找只接收原WT二元身份或完整token，撤单使用已持久真实回报证明，不提供裸broker号全局认领。源结果未知、柜台接受与WT实际应用分别记录，HTTP200仅表示成功读取已保存事实。事件原文保存在同一通信SQLite，源确认不删除记录；无第二套账户、订单或持仓账本。字段、预算、阶段和错误以[QST-R18至R21](../../docs/specs/qmt-shm-trading.md)为准。

使用签名`GET /internal/v1/read-binding`取得实际Session绑定和完整profile原字节；来源SHA包含原control_profile。POST只提交一次，未知送达保留原request_id并GET原结果。Journal持久保存原body、语义摘要、准入/派发/结果三绑定和原终态；发送前先提交dispatching，原终态与result_binding提交后才ACK。重启不重发dispatching；旧queued不能迁到新Host/channel，旧终态继续保留原身份。无绑定旧记录为`legacy_unqualified`，GET可审计、POST不补当前绑定。

此SQLite只拥有通信去重/派发/终态，不保存资本账本，不作为WT订单、成交、账户或理论持仓的第二个owner。容量满拒绝新工作并保留已有结果。结果查询不依赖当前连接；当前ready资格由另一次认证binding快照确认。无认证`/health`只有诊断用途。

## 来源与验收

`source-manifest.json`记录精确旧文件SHA、改动类别及新增模块；旧路径仅是静态来源，不是运行依赖。`protocol/`保留原两份公开协议JSON，原生成器只作为来源摘要，不在新包安装/运行时执行。

测试入口为`tests/integration/qmt_shm_package`及`tests/integration/qmt_shm_builtin_transport`。隔离测试使用新wheel、新安装和合成Context，包含真实Win32映射/故障、HTTP全链及独立Python3.6.8。真实源012原件保持，只授当次源端full_tick；本仓新制品真实终端、WT C++接线、实际单位、账户、历史、RT、交易与生产分别验收。运维正文由仓库国信操作/维护/排障手册拥有。


## 显式常驻只读API

QSW-R20提供开发中的build_read_service(config, credentials=..., reconnect_seconds=...)及ReconnectingReadAgent(..., enabled=True, reconnect_seconds=...)。它们复用原单连接实现、同路径通信Journal和原ContextInfo线程；首个对端可以晚于原连接窗口到达，运输断开后仅在旧owner关闭确认后重建并重新认证。

原build_runtime、CLI与pair/verify仍保持单连接生成方式。本API的合成测试不表示现有磁盘策略、安装包或系统登录自动启动已切换；后续需接入生成器、独立安装与统一启动入口，实际终端常驻另外验收。只读恢复不启用交易自动恢复，明确识别的认证/资源故障停止重试。完整职责和源码接缝见[常驻模块](../../docs/modules/qmt-connection-lifecycle.md)。

显式历史缓存补齐使用独立v6开发入口，固定注入QMT全局download_history_data，复用原认证SHM、队列、Host bound Journal及常驻owner；原默认入口保持关闭。接口、预算、未知结果和离线配对见[历史补齐模块](../../docs/modules/qmt-history-preparation.md)，实际终端资格由操作owner另外验收。
