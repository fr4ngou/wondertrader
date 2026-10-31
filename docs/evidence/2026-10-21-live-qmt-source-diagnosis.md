# QMT 实际来源、账户接口与分钟样本读取核实

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：只读运行核实记录。结果：partial。观察：2026-10-21 16:00–16:14，上海时间。关联[完整接入地图](../migration/acceptance-map.md)及[HTTP 规格](../specs/qmt-http-market.md)。本记录更正此前将读取通道故障、适配验证缺项笼统归为“用户需提供公开契约或等待历史下载”的表述。

## 输入与边界

原 QMT 主干 `8764004089c2e0c358522fbeb12ed820d741f223`，核实前后 Git 干净。实际客户端 `D:/software/guoxin/bin.x64/XtItClient.exe`，PID 2824，08:50:49 启动；安装版 Agent 与主干源码分别核查，摘要见机器记录（外部历史/待归仓路径：`live-source-2026-10-21/gateway-diagnosis-20261021.json`）。WT 十二个已有框架差异继续冻结，本次未改框架、原 QMT、安装配置或 DAT。

使用现存 Bridge 的 `refresh=false` 只读投影；账户标识、金额、持仓明细与令牌不写入记录。未启动策略、重启终端、提交委托、下载历史、订阅行情或切换部署。SDK 和诊断工具仅隔离到 E 盘。线程采样未读取局部变量。

## 18010 未监听的实际触发链

1. 安装配置仍为 `rest_gateway`、`0.0.0.0:18010`，两次 TCP 检查失败；客户端进程存活，Docker 业务容器在运行。
2. 客户端日志记录：10:11:16 开始自动运行 AI_ETF；10:11:25 `init → server.ensure_running → start` 抛出 `Gateway server did not start before timeout`，初始化中断。
3. 对现存进程两次非阻塞采样均显示同一线程 `qmt-rest-gateway` 停在 `gateway/server.py:83 → tornado.httpserver → tornado.netutil:39 → ssl.create_default_context:502 → SSLContext.__new__:391`。代码在导入完成后才创建和监听 HTTPServer，因此当前尚未进入绑定端口。
4. 原生堆栈观察到 `_ssl.pyd → PyEval_RestoreThread → WaitForSingleObjectEx`。后续两次锁归属采样（外部历史/待归仓路径：`live-source-2026-10-21/gateway-gil-ownership-20261021.json`）均显示 MainThread（65424）owns_gil=true、无 Python frame，Gateway（30588）owns_gil=false；原生栈（外部历史/待归仓路径：`live-source-2026-10-21/gateway-native-thread-sample.txt`）显示前者停在原生 `GetQueuedCompletionStatus` 等待，后者在恢复解释器锁。这证明当前原生主线程持锁等待阻塞后台初始化；首次启动中为何超过5秒及可安全修复方式仍待隔离验证，不将采样直接提升为已修复。

复查入口为忽略工作目录 `build/native/live-source-probe/capture_gateway_diagnosis.py`；它重复 TCP、现有 Bridge 投影与线程栈检查，原始脱敏结果已冻结于本目录附件。恢复实际 Gateway 后须用相同检查确认端口、认证健康、策略心跳与账户快照一起刷新。当前无恢复成功证据；盲目增加超时或关闭 SSL 校验没有验证依据。AI_ETF 具有既有账户执行路径，本次未为采样启动它。

## 已有账户能力及适配缺项

实际 Bridge 返回四个持仓证券项，快照 `2026-10-21T00:50:33.014271Z`，心跳 `00:50:46.014239Z`，即上海 08:50；当时 reconciled=true，当前明确报告 heartbeat/account snapshot stale。可以读取已保存事实，当前新鲜事实刷新受上述 Gateway 故障影响。

当前主干与安装版均已具备资金、持仓、可卖、冻结、订单、成交、会话 ID、快照序号及内容 hash；已有 HMAC 保护的 `/internal/v1/state`、`/events`、`/sync`，同锁运输快照、事件分页、持久游标及原业务按券商 ID 幂等恢复。四轮 ACCOUNT/POSITION/ORDER/DEAL 采集在订单/成交回调改变 epoch 时丢弃重采。精确代码位置见契约核实（外部历史/待归仓路径：`live-source-2026-10-21/account-contract-audit-20261021.md`）。

因此这些接口应由开发方自行核实和复用。剩余具体工作是 WT 映射和恢复场景验证：`last_event_seq` 表示 Gateway 日志尾，不能直接当作“当前券商持仓已经包含到这里的所有成交”。优先复用原业务快照和券商成交 ID 幂等，证明同一成交不会先在快照中计入、又被回报重复加减；无须让用户编写契约或新增一套平行账户账本。

## 已下载分钟可以分批验收

用户报告历史下载约完成三分之一。16:09 目录观察：SH/60 有 2381 个文件、38,976,811,304 字节；SZ/60 有 1688 个文件、28,169,527,488 字节。SH 文件仍更新。`688076.SH`、`300308.SZ` 的代表文件在摘要读取期间稳定，身份见分钟核实（外部历史/待归仓路径：`live-source-2026-10-21/live-minute-source-summary.json`）。数量和大小不等于十年覆盖证明。

已完成证券/日期的片段足以先验实际导出、时间/单位、QMI 写读、原生策略读取及统一接口；全市场和十年完整性后续单独验收。继续下载与小样本验收可分开推进。

本次尚未取得真实 OHLCV 行：安装 SDK 的 `get_local_data()` 是 `return None` 占位；旧原生客户端连接现存 58600/58610 后返回零行且数据目录为空。E 盘隔离官方 SDK `xtquant_250807` 后，显式数据目录、local=True、server=False、100 条只读请求仍需交易日元数据；58610 返回 not authenticated，58600 返回 200005。具体失败见附件，SDK 原安装未替换。

下一条已存在的受管读取链为原工程 `scripts/marketdata.py export-qmt-bars / probe-qmt-history → Bridge → Gateway → ContextInfo.get_market_data_ex(subscribe=False, fill_data=False, dividend_type="none")`，先恢复 Gateway，再读取一个已下载证券的完整交易日。当前分钟左右端、量额单位、复权与覆盖未完成真实来源资格，未凭猜测生成 QMI manifest，也未将文件存在标为样本验收通过。

## 验证范围与后继

已完成实际端口/配置/日志/线程定位、现存账户投影读取、当前与安装版契约核查、下载目录统计及两类 SDK 只读失败复现。附件由 SHA256SUMS（外部历史/待归仓路径：`live-source-2026-10-21/SHA256SUMS.json`） 绑定。本记录没有新增真实行情导入、恢复成功、生产发布或实盘资格。后续继续查明线程启动/解释器锁根因，以真实小样本关闭来源语义，再验证 WT 恢复适配。
