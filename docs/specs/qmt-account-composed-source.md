# 同一 QMT 正文的只读账户连接

类型：功能最终规格。状态：implemented，SDK 整链与离线新安装验收通过，独审/交付身份见证据。前缀：QAC。范围：在已有交易/QST/HPR 组合生成入口加入一个显式只读账户连接。可选账户和分析连接继续使用各自已有 Host、协议、原队列、认证与截止；不新增策略、账本或金融计算。

## 冻结接口

`render_trade_source(..., market=None, account_read=None)` 和 `create_product_pair(..., market=None, account_read=None)` 增加可选参数。`account_read` 精确包含 `agent`、`reconnect_seconds`；agent 是原 `validate_read_configuration` 准入的 trusted bootstrap（Python secret 为 bytes）。只读账户入口保持 `qmt.read-profile.v3`，含原 account.trade_detail；原声明的其他只读能力、账号和限额保持，不从交易 profile 自动转换。

正式 CLI 增加 `pair --account-read-pair PATH`。生成阶段调用原 resident read pair 验证器，在当前安装/解释器中核原 pair、所有源、policy 和完整正文，然后从同次私有快照取得原 agent settings 与重连间隔。该路径不构造 Host、不打开 Journal、不调用 SDK。原 Read pair 仍由 WRI 的 `account_host.kind=qmt_read` 独立管理。

私有 deployment 仅显式选择时增加 `account_read` 快照，agent.secret 存为 secret_hex；manifest 仅该模式增加只读 profile 和完整设置 SHA 的 `account_read` 元数据。原 config SHA、所有源 SHA、内存闭包及生成正文均参与 verify。省略 account_read 的材料形状和正文保持原行为。原私有 `_decode_deployment` 保留旧四元组准入；显式新组合使用完整 decoder，旧 decoder 遇到新模式明确拒绝丢弃。

组合准入复用原 Read/Trade/QST/HPR 验证器，核同 Windows 会话、不同 SHM 映射及不同 IPC 秘密。只读 IPC 继续与外部交易 Host HTTP 身份分离。只读及交易账号分别来自明确授权设置，组合层不改账号、不切换权限；set_account 仅由原交易 owner 调用。

## 源 owner 和调度

只读连接直接使用原 `ReconnectingReadAgent` / `RestrictedReadAgent` 和四查询 mapper，不修改 Agent 核心或 read/交易 wire。正式正文仍为一份 ContextInfo、一个原线程 timer、一个 QST 订阅。原交易 owner 优先；只读 owner 每 tick 可推进轻量连接/退休，重任务仅在交易未使用时进入；HPR 重任务仅在前两者空闲时进入，轻量推进仍继续。QST 保留原订阅/回调实现。

停止依次通知交易、只读账户、HPR、QST；失败仍通知全部已构造 owner，首因和各原关闭截止保留。运输关闭、交易业务关闭和只读完整关闭分别验证。QMT 运行期读取包/配置文件、网络入口计数必须为零；外部生成/核验和 SDK 替身夹具的文件操作分别记录。

## 验收

| ID | 结果 |
|---|---|
| QAC-R1 | 无观衡普通新安装，正式 pair/verify 固定完整四 owner 正文，原无 account_read 默认回归保持 |
| QAC-R2 | 实际 Python3.6.8、Windows SHM 和三个 Host 连接同存：交易四查及下单→查单→撤单替身；独立原生 Scan 四查，严格值保持 |
| QAC-R3 | 同一正文完成原 HPR 准备/回读和 QST→原 Writer 分钟，原历史 Reader 前后基准一致；单 timer/单订阅/原线程 |
| QAC-R4 | 正常关闭原 owner、整树/双 EOF/线程 join/句柄，文件/网络守卫调用计数 0；失败和未知保留 |
| QAC-R5 | 主链后验证独立只读连接两代认证，其余 owner 保持；复用仍有效交易续接证据，不重发未知命令 |
| QAC-R6 | 必要配置/默认/身份回归、独立双轴审查、离线安装和操作说明，清楚标记实际 QMT/生产未授范围 |

专项 fixture 入口：`tests/integration/qmt_account_composed_source/{prepare_fixture.py,source_peer.py,main_installed.py,run_control.py}`，复用原 `wt_trade_data_composition` 的正式准备/SDK/Writer/Reader 语义。根负责公共 runtime.py、最终 SRI 安装、实际 QMT 界面和现场首故障诊断。本切片不操作现场、不重复真实查询，不以组合成功授旧资金中断已修复。

实现与本轮边界见[模块说明](../modules/qmt-account-composed-source.md)、[操作说明](../runbooks/qmt-account-composed-source.md)及[验收证据](../evidence/2026-10-30-qmt-account-composed-source.md)。SDK 组合运行中保留一次交易 Host 超时失败，具体首因仍待证实；其原命令及 Journal 保持。本规格的功能验收与该恢复风险分别记录。

## 可选分析读取连接

`render_trade_source` / `create_product_pair` 增加 `analysis_read=None`；CLI 使用 `--analysis-read-pair PATH` 核原 resident v7 pair。快照精确包含 `agent` 和 `reconnect_seconds`，仅含原 `market.market_data` / `market.divid_factors` 两种分析只读操作。原 QAS profile、额度、数据和复权语义保持；下载、账户与交易仍归各原连接。

选择分析连接时明确设置 `source_runtime.mode=strategy_tick`（CLI `--source-mode strategy_tick`）。同一正文共享一个 ContextInfo、原SDK线程、一个100ms timer和一个QST订阅。重任务依次为交易、只读账户、分析、HPR；每tick最多一个重任务，所有已选owner仍推进轻量连接和退休。关闭依次通知交易、账户、分析、HPR和QST，保留原关闭责任及首因。

新组合使用 `qmt.trade-product-pair.v3` / `qmt.trade-deployment.v3`，固定分析设置/profile摘要、全部安装源码及完整正文。唯一完整decoder消费全部字段，旧decoder明确拒绝新增分析项；省略analysis_read的原字段、正文和行为保持。原验证器核同会话、独立映射、不同IPC身份及HTTP角色隔离。所有文件仅在QMT外准备和核验，终端运行仍为完整内存正文。

验收使用实际3.6.8/Windows SHM、普通离线安装，同正文交易/账户/HPR/QST及新增分析→Native Import/Reader→QNA→R24，核原线程、单timer/订阅、禁止文件网络0及完整关闭。SDK结果、真实QMT、交易恢复及生产分别保留资格。

分析扩展验收：QAC-A1 为 v7 原配对/两操作/IPC隔离及旧路径逐字兼容；A2 为实际3.6.8/WinSHM的五通道单正文与单重任务调度；A3 为原Native/Reader/QNA/R24三轮原值消费；A4 为普通离线安装、全部owner正常关闭与明确资格边界。当前SDK结果见[分析组合验收记录](../evidence/2026-10-30-qmt-analysis-composed-source.md)，独立审查由根会话统筹。

## 可选批量分析连接

`render_trade_source` / `create_product_pair` 增加 `analysis_batch_read=None`；CLI 使用 `--analysis-batch-read-pair PATH`。该参数沿原 resident read pair 验证器取得同次已核设置，精确包含 `agent` 和 `reconnect_seconds`。只接受 [QAB](qmt-analysis-batch-source.md) 的 v8、`market.market_data` 和 `qmt.daily-batch-read.v1`。原 v7 `analysis_read` 继续承担单证券日线及因子，两条连接各自保存原 profile、映射、身份、容量和截止。

显式加入批量连接时使用 `qmt.trade-product-pair.v4` / `qmt.trade-deployment.v4`，manifest 固定批量 profile、完整设置摘要、安装源码与完整内存正文。唯一完整解析器消费全部连接；原七项 decoder 拒绝新增批量项，继续处理原 v3。省略批量项保持旧配置形状、owner、权限与调度行为。新发行源码及内存闭包按其实际版本生成，原冻结配对由其原安装复验。

批量连接要求显式 `strategy_tick`，复用原 `TickReadAgent`。同一 ContextInfo、原策略线程、唯一 100ms timer 和一次 QST 订阅共同推进全部连接。重任务顺序为交易、只读账户、v7 分析、v8 批量、HPR；每 tick 最多执行一个重任务，所有连接的轻量通信及退休仍推进。停止按同一顺序通知业务 owner，再关闭 QST；各 owner 保留原请求身份、未知结果和资源责任。组合层继续核同 Windows 会话、独立映射、不同 IPC 秘密及外部 HTTP 身份隔离。

QAC-B1：普通离线安装通过正式 pair/verify/CLI 生成及验证六连接正文，默认与原 v3 路径的兼容范围明确。QAC-B2：实际 CPython3.6.8/WinSHM 同正文完成替身交易下查撤、账户四查、v7 日线/因子、v8 多证券 none/front_ratio 两批、HPR 准备/回读及 QST，原 Reader 基准保持。QAC-B3：原请求与结果/消费身份、批次证券映射及原值一致，原线程、单重任务/单 timer/单订阅、终端内文件/网络调用 0，全部 owner 正常关闭。SDK、实际 QMT、长期运行和生产资格分别记录。
