# WT 管理 QMT 交易通信

类型：操作手册。范围：独立安装材料和受控开发实例，契约见[THP](../specs/qmt-trade-host-product.md)。

新电脑部署先读[通信架构、完整配置示例与配对步骤](qmt-connection-onboarding.md)，其中提供可填写的主配置、操作策略和 SDK 清单采集工具。

## 安装与准备

沿独立角色安装器离线安装 host 与 wt，使用普通复制安装后的文件。Host 包依赖固定版本的 agent、Pydantic、FastAPI、Starlette 和 Uvicorn；WT 包只依赖市场客户端。观衡 App 和 SPA 均为独立制品。

准备原交易配置与原 operation policy，使用新私有目录保存通信 SQLite、配对材料与控制收据。明确配置 SDK profile、账户业务绑定、允许操作、写开关、预算以及原金融规则。IPC 和 HTTP 凭据由配置中声明的环境变量传入外部准备进程；报告仅保存配置摘要和字段定义。

在实际安装的 Host Python 下执行：

```text
pythonw.exe -I -B -m guanheng_qmt_shm.trade_cli pair --config <私有配置> --memory-sdk-manifest <已核3.6原件清单> --stdlib-license <CPython许可> --reconnect-seconds <间隔> --output <全新私有配对目录>
pythonw.exe -I -B -m guanheng_qmt_shm.trade_cli verify --directory <配对目录> --installed-agent <本次安装agent包目录>
```

这些步骤在 QMT 外读取源码和配置。生成的 strategy.py 为可直接放入 QMT 编辑器的完整正文，依赖及参数位于正文内存载荷中。QMT 运行期调用 Windows 命名共享内存，不读取外部文件或建立网络连接。

需要同一策略同时提供行情、历史补齐和交易时，在 pair 命令加入 `--market-config <私有JSON>`。该 JSON 仅含 quotes、preparation、preparation_reconnect_seconds；前两项沿原已准入配置，将 secret bytes 写成 secret_hex 小写十六进制。正式 pair 将它冻结进同一个部署摘要；verify 必须能重建完全相同正文。HPR 的 MARKET-only 合同保持。

## WT 一次启动

建立 `qmt.trade-host-process.v1` descriptor，记录本次 Host pythonw 路径及 SHA、pair manifest SHA、installed_agent、control_root、启动/停止预算与输出上限。将 descriptor 路径和 SHA 放入独立 WT 的 `components.trade_host`，kind 固定为 qmt_trade。原 `components.host` 继续管理 read/HPR。

独立 WT 按 host → trade_host → history → collection → execution 启动，按逆序关闭。操作员使用 WT 安装入口启动整个声明运行配置，Host 由 WT owner 带起。QMT 登录后运行已核的同一份策略正文；Host 会持续等待来源，来源晚于 60 秒仍可认证。Host ready 只表示监听成功，业务就绪以原 trade-status 和账户查询为准。

## 停止、恢复与回退

正常停止走 WT 的 request_close/close，保留 closed 收据、进程树清零、EOF、线程 join 和资源关闭证据。超时或关闭异常保留首因与原 owner 状态。状态中的 qmt_connection=not_checked 是父端未主动查询业务来源的声明；来源健康由原业务接口取得。

运输重连沿同一 SourceTradingService，账户订阅一次，旧 command_id 和事件原身份保持。发现 unknown 时，查询原命令和券商事实。通信产品重复提交同一身份返回原记录；新的自动重发需要原业务层明确决定。

丢失旧 reply ACK 时，源端可能报告 transport_closed=true、business_closed=false、handoff_unconfirmed=true。该状态保留未确认业务责任，按原命令核查；记录物理关闭与业务未确认两个结果。

回退前停止新实例并保存原配对、源码/制品 SHA、通信库及未知命令记录。显式连续模式库需要支持该模式的产品打开；旧默认工厂会明确拒绝。保持原库和附属认证关系，按已核版本恢复。重新生成配对材料时核对实际安装路径及 SDK 原件，旧配对保持原件以便审计。

SDK 替身验收与实际账户资格分别记录。开发验证步骤不授予真实委托、现场策略替换或生产发布资格。
