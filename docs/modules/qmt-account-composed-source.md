# 同一 QMT 正文的只读账户连接

对应规格：[QAC](../specs/qmt-account-composed-source.md)。本模块组合既有连接的生命周期，复用各自协议、账户映射和业务服务。

## 入口与数据流

外部 `guanheng_qmt_shm.trade_cli pair --account-read-pair <原只读pair>` 先核验原只读配对，再把同次只读设置快照加入交易配对。`--market-config` 继续表达原 QST/HPR 设置。`verify` 从配对中的原设置及安装源码重新生成完整正文，逐字比较策略和内存依赖闭包。

QMT 只加载这份完整正文。原交易、只读账户、HPR 和 QST owner 共享一个 ContextInfo 和原策略线程，使用独立命名内存及认证。交易 owner 调用原 `set_account`；只读查询的账户由原 read v3 profile 单独指定。组合层保持两个原账户绑定。

| 责任 | 唯一实现 |
|---|---|
| 只读设置及权限准入 | 原 `validate_read_configuration`，要求原 v3 含账户查询能力 |
| 只读配对来源验证 | 原 `_verify_pair_material`，包括解释器、安装源码、policy、正文 |
| 私有快照 | `account_read_composition.py`；IPC secret 使用原 bytes，私有 JSON 编码为 hex |
| 正式生成与核验 | `trade_pair.py` / `trade_source.py` / `trade_cli.py` |
| 只读连接、退休及重连 | 原 `ReconnectingReadAgent` / `RestrictedReadAgent` |
| 四类账户字段及 WT 投影 | 原账户 mapper、TraderQMTReadOnly 和 GuanhengAccountScan |
| Host 进程与正常关闭 | WT 的原 `qmt_read`、`qmt_trade`、HPR 进程 owner，各自单一所有者 |

`account_read` 精确包含 `agent` 和 `reconnect_seconds`。显式选择时，私有 deployment 保存该快照，私有 manifest 保存 profile 和完整设置 SHA。省略该项时保持原配对字段和策略正文；旧四元组 decoder 对新组合明确拒绝，完整 decoder 显式消费第五项。

## 调度和关闭

一个 timer 依次推进交易、只读账户、HPR。重任务优先级为交易、只读账户、HPR；每 tick 只授一个重任务，连接和退休仍轻量推进。QST 使用原一次订阅及回调。一个慢 SDK 调用会占用原策略线程，其执行及排队期限仍由原 owner 管理。

停止时先通知交易、只读、HPR、QST；一个通知失败仍继续通知其他已构造 owner。原 I/O owner 关闭自己的映射、线程和句柄。只读运输代际更替沿原 read owner，交易长期业务服务及命令身份继续归原交易 owner。运输关闭与业务关闭分别提供证据。

源码、配置、依赖和配对文件仅在终端外准备及核验阶段读取。QMT 内部所有模块从策略正文中的内存包加载；通信沿 Windows 命名共享内存。HTTP 身份留在外部 Host，组合准入核验 IPC 与 HTTP 身份分离。

## 验证与边界

专项入口为 `tests/integration/qmt_account_composed_source/run_control.py`。验收组合原生 Scanner、SDK 替身交易、HPR、原 Writer 和真实 Reader 历史基准；具体制品、运行结果、未通过原件及独审见本轮证据记录。

这一层证明组合生成、安装和通信消费。真实 QMT、真实交易、完整恢复、策略运行、观衡页面及生产发布由各自完整调用链验收。原命令结果未知时保留原 ID 与 Journal，处理原则见交易通信模块。

## 分析连接

可选 `analysis_read` 沿原 resident v7 pair 导出日线/因子设置，复用原 `TickReadAgent`。正式 CLI 使用 `--analysis-read-pair`，配对 v3 固定其 profile/设置摘要及完整正文。完整契约和兼容规则见[规格的分析扩展](../specs/qmt-account-composed-source.md#可选分析读取连接)。

交易、账户、分析和 HPR 共享同一回调调度，依次获得单次重任务；QST 保留原订阅。`account_read_composition.py` 维护只读材料编解码和原配对加载，账户与分析各自验证原能力。`analysis_read_composition.py` 只负责 v7 两操作准入，不承担数据算法或新增业务服务。

## 批量分析连接

`analysis_batch_read_composition.py` 复用同一只读材料编解码及原 resident pair 验证，只准入 QAB v8 批量日线。`--analysis-batch-read-pair` 将其显式加入交易组合 v4，原 v7 日线/因子连接继续独立存在。省略该项保持既有 owner 和权限；新发行的源码与正文身份由其新配对完整记录。

源端直接复用原 `TickReadAgent`，原 `RestrictedReadAgent` 和 QAB adapter 拥有实际 SDK 读取及结果。组合层只安排交易、账户、v7、v8、HPR 的单重任务顺序，并让全部连接推进轻量通信。QST 保持同一次订阅。批次仍是一个原请求/一次 SDK 的身份，证券投影沿 QAB；组合层不计算复权、因子或账户事实。完整 decoder 唯一消费全部设置，原 v3 decoder 对新增项明确拒绝。
