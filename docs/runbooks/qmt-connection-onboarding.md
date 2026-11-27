# 新电脑配置 QMT 通信与生成策略正文

类型：入门操作手册。适用于国金 QMT 和国信 iQuant（国信 QMT）的 Windows 新机部署，覆盖账户查询和行情、历史、分析及证券资料的组合只读接入。示例关闭下单和撤单。

两家客户端在本项目的接入层共用迅投 QMT 内置 Python 策略接口、原策略回调，以及同一套 Host、Agent、Windows 共享内存和配对流程。部署时采集目标终端的实际 SDK，按现场填写安装路径和策略文件位置，并核对账户权限与行情板块。更换终端安装或账户时，为目标环境生成新配对，再做只读验收。[迅投 QMT Python 说明](https://dict.thinktrader.net/innerApi/related_instructions.html) · [国信 iQuant 操作手册](guosen-qmt-operations.md)

## 通信架构

QMT 内的 `strategy.py` 是券商接入脚本。交易策略计算、资金分配和目标执行由 WT 运行侧承担；接入脚本在 QMT 原策略线程调用券商 API，把查询结果与回报送回 WT。

```mermaid
flowchart LR
  subgraph QMT[QMT 终端进程]
    API[券商 API 与 ContextInfo]
    Agent[完整 strategy.py / Agent]
    API <--> Agent
  end
  subgraph WT[WT 运行侧：同一台 Windows 电脑]
    Host[独立 Python Host]
    Journal[(通信 SQLite Journal)]
    Plugins[Parser / Trader 接入插件]
    Core[WT 策略、风控与执行]
    Host --- Journal
    Plugins <--> Core
  end
  Agent <-->|Windows 命名共享内存 SHM| Host
  Host <-->|签名 HTTP / 127.0.0.1| Plugins
  Core -->|公开只读结果| Observer[独立观衡服务与页面]
```

| 部件 | 运行位置与责任 | 入口 |
|---|---|---|
| QMT Agent | 在 QMT 内运行完整生成正文，核对配对与权限，原策略线程调用 SDK；依赖源码和参数已嵌入内存 | [Agent 源码](../../connectors/qmt_shm/agent/guanheng_qmt_shm_agent/)、[来源运行模式](qmt-source-runtime.md) |
| SHM | 同机进程通过 Windows 命名内存对象交换认证消息、请求、结果和回报；映射名、Windows 会话及密钥必须匹配 | [连接规格](../specs/qmt-shm-wt-binding.md) |
| Host | QMT 外部的独立 Python 进程，拥有认证 HTTP 接口、共享内存对端和通信恢复；生命周期由 WT 管理 | [Host 源码](../../connectors/qmt_shm/host/guanheng_qmt_shm/)、[托管步骤](qmt-trade-host-product.md) |
| Journal | Host 保存请求身份、派发阶段、结果、回报和未知责任的 SQLite。资金账和策略账继续由各自业务模块拥有 | [交易规格](../specs/qmt-shm-trading.md) |
| WT | 原生 Parser/Trader 对接 Host；策略和执行器消费行情、生成目标、处理风控及委托回报 | [执行模块](../modules/execution.md)、[行情插件](../modules/qmt-polling-parser.md) |
| 观衡 | 独立部署的只读消费者，显示 WT 提供的事实 | [职责决策](../architecture/adr/0016-independent-wt-runtime-and-observer.md) |

HTTP、磁盘配置、包文件及 Journal 都在 QMT 外部处理。QMT 正文运行时使用内存加载与共享内存，遵守终端的外部文件和网络访问约束。本文的同机 SHM 连接需要把 Host 部署在运行 QMT 的电脑上。

一次账户查询沿“WT → 签名 HTTP → Host → SHM → QMT 原线程调用 SDK → 原路返回”完成。获准交易时，委托沿同一路径进入 SDK，柜台回报再返回；HTTP 成功受理、SDK 返回、柜台接受和实际成交是分别可核查的阶段。发生超时或结果未知时，保留原命令身份，查询原命令与柜台事实，恢复规则见[交易通信手册](qmt-trade-host-product.md#停止恢复与回退)。

常驻 Host 等待 QMT 上线，运输断开后按原生命周期清理旧连接并重新认证。WT 重启后的新连接仍须核对新 binding、递增心跳及真实业务读取；Host 的 ready 只表示监听就绪。旧未知委托继续沿原身份核查。

## 准备安装和材料

需要 Windows、Python 3.10+ 的 Host 环境以及与目标 QMT 相符的 CPython **3.6.8 / 64 位** SDK。当前 [SDK 准入](../../connectors/qmt_shm/host/guanheng_qmt_shm/memory_runtime.py)固定检查该版本、二进制、标准库与许可证；更换版本需要适配和验证。

从可信的同一源码版本安装 Agent 和 Host。已有正式安装时沿[运行时安装手册](python-runtime.md)核对版本；研究新安装可以在独立环境安装仓库项目及其锁定依赖：

```powershell
# 以下路径均为示例；程序、私有材料和配对目录分别管理。
$Repo = 'E:\workspace\wondertrader'
$HostPython = 'D:\software\qmt-host\Scripts\python.exe'
$Private = 'D:\qmt-private'

py -3.12 -m venv D:\software\qmt-host
& $HostPython -m pip install "$Repo\connectors\qmt_shm\agent" "$Repo\connectors\qmt_shm\host"
New-Item -ItemType Directory -Path $Private
Copy-Item "$Repo\connectors\qmt_shm\examples\qmt-trade-config.example.json" "$Private\qmt-trade-config.json"
Copy-Item "$Repo\connectors\qmt_shm\examples\qmt-operation-policy.example.json" "$Private\qmt-operation-policy.json"
```

主配置为 [qmt-trade-config.example.json](../../connectors/qmt_shm/examples/qmt-trade-config.example.json)，其操作策略为 [qmt-operation-policy.example.json](../../connectors/qmt_shm/examples/qmt-operation-policy.example.json)。JSON 使用 UTF-8、无 BOM，说明放在本文中，JSON 内保持标准语法。

`--config` 指向填写后的主配置。现有配对的 `deployment.json` 是包含凭据的部署快照，整个文件的格式与主配置不同；新账户使用本模板及新的独立状态目录。

## 填写主配置

模板的账户标识为虚构的 `SYNTHETIC`，只开放 `account.trade_detail` 查询，`writes_enabled=false`。交易协议和事件存储字段仍须完整存在，供正式交易配对校验器检查；这些字段存在不授予下单权限。模板使用当前支持的 `qmt.trade-binding.v2`，证券交易规则由 WT 与券商处理。

| 字段 | 含义、示例值与实际影响 |
|---|---|
| `trade_binding.account_id` 和 `operation_profiles["account.trade_detail"].limits.account_binding.account_id` | 两处同时填写新账户在 QMT 中使用的标识；必须一致 |
| `trade_binding.account_type`、两处 `account_environment` | 示例为股票账户 `stock` 与实际账户环境 `live`；应与目标账户相符；环境声明和写开关分别校验 |
| `trade_binding.binding_id`、`strategy_name` | 本次账户绑定及 SDK 调用归属名称；与本次部署约定一致 |
| `route.route_id`、`executor_id`、`route_epoch` | 连接路由与执行端身份及代次；示例身份只适合独立验证实例 |
| `transport.name`、`windows_session_id` | 本实例独立的共享内存名，以及 QMT 所在 Windows 会话 ID。用 `Get-Process XtItClient | Select-Object Id,SessionId` 核对；模板的 `1` 须按现场填写 |
| `transport.kind`、`schema_version` | 示例使用 `builtin-shm` 与 `qmt.builtin-shm.v1`，对应受限终端内存入口 |
| `listen_host`、`listen_port` | 示例监听 `127.0.0.1:18159`，供同机 WT 访问；端口须空闲，消费者使用相同地址 |
| `journal_path` | 新实例专用的通信 SQLite 绝对路径，示例为 `D:/qmt-private/communication.sqlite`；换账户使用独立新文件 |
| `operation_policies_path` | 第二份 JSON 的绝对路径，默认复制位置为 `D:/qmt-private/qmt-operation-policy.json` |
| `ipc_secret_env`、`http_secret_env`、`http_key_id` | 两个环境变量名及 HTTP 密钥 ID；主 JSON 保存引用，实际密钥在配对进程环境中提供 |
| `read_profile_version`、`read_operations`、`operation_profiles` | 当前 v4 组合协议，仅声明账户读取；账户结果按 `CNY / cny_cash_shsz_v1` 解释，policy 版本 `1.0` 是基础查询投影，费用/身份增强投影沿对应规格另配 |
| `trade_profile.schema_version`、`clock_schema`、`operations`、`binding_sha256` | `qmt.trade-profile.v1`、同机 Windows 启动毫秒时钟及协议支持的下单/撤单操作集合；摘要绑定完整 `trade_binding`，写入实际受 `writes_enabled=false` 阻断 |
| `trade_profile`、`trade_binding.max_commands`、`max_trade_bytes` | 完整协议及通信记录预算；模板保留最多 16 条交易命令、每条正文/调用结果各 4096 字节、有效期 5000 毫秒、交易域逻辑预算 200000 字节；写开关仍关闭 |
| `max_records`、`max_journal_bytes` | 读取记录上限 64、逻辑预算 1048576 字节；容量满拒绝新工作，保留已有记录，后续按[读取保留规格](../specs/qmt-read-retirement.md)选择正式保留方案 |
| `max_frame`、`max_result_bytes`、`max_http_inflight` | 帧 262144 字节、单读取结果 16384 字节、HTTP 在途上限 4；示例用于连接验证，大账户结果可能超额拒绝 |
| `connect_seconds`、`io_seconds`、`control_profile` | 连接 5 秒、I/O 2 秒；control2 中 CALL 8192、REPLY 32768、保留 300000、单周期 8 条/65536 字节、调用上限 10 秒及 4 个在途调用槽，联合预算由原校验器验证 |
| `transport.poll_seconds`、`max_mapped_bytes`、`control_profile.poll_seconds` | 共享内存和控制调度间隔 0.005 秒，映射预算 4194304 字节；影响通信调度与内存容量 |
| `event_storage`、`event_poll_seconds`、`trade_profile.limits` 中事件字段 | 源缓冲最多 8 条/单条 1024/合计 8192 字节/页 4096 字节；Host 存储最多 4 条流、32 条事件、60000 逻辑字节，每 0.2 秒轮询。容量不足会阻断业务推进，不能自动删库续跑 |
| `writes_enabled` | 示例固定 `false`；要接正式策略执行时先按目标账户确认完整配置、运行状态和执行权限 |

操作策略 JSON 对账户查询提供排队 1000 毫秒、SDK 执行 1000 毫秒、响应余量 1000 毫秒、总计 3000 毫秒，只尝试一次、并发 1。`retry_backoff_initial_ms/max_ms=0`、空的 `retryable_error_codes`、`checkpoint_scope=none`、`terminal_proof_window_ms=0` 表示此示例未声明重试、分段检查点或额外终态窗口。它描述该读取请求的预算，不代替交易重试规则。表内容量均为独立连接验证的显式示例值；投产时按业务规模评估并联合验证，保持原状态和未知请求。

修改 `trade_binding` 后，用安装包的同一规范化算法重算摘要：

```powershell
& $HostPython -I -B -c 'import json,sys,hashlib; from pathlib import Path; from guanheng_qmt_shm_agent.protocol import canonical; p=Path(sys.argv[1]); c=json.loads(p.read_text(encoding="utf-8")); c["trade_profile"]["binding_sha256"]=hashlib.sha256(canonical(c["trade_binding"])).hexdigest(); p.write_text(json.dumps(c,indent=2)+"\n",encoding="utf-8")' "$Private\qmt-trade-config.json"
```

## 生成认证材料和 SDK 清单

在执行配对的同一 PowerShell 窗口创建两份独立随机密钥，直接存入配置引用的进程环境变量。以下命令不打印密钥：

```powershell
$env:QMT_EXAMPLE_IPC_SECRET = & $HostPython -I -B -c 'import secrets; print(secrets.token_hex(32))'
$env:QMT_EXAMPLE_HTTP_SECRET = & $HostPython -I -B -c 'import secrets; print(secrets.token_hex(32))'
```

IPC 密钥用于 Host/Agent 共享内存认证；HTTP 密钥用于终端外请求签名。配对生成物含凭据，保存到访问受控的私有位置，WT 客户端须使用匹配的 HTTP 密钥。券商登录仍由用户在 QMT 中完成。

[SDK 采集工具](../../scripts/qmt_sdk_manifest.py)由目标 SDK 的解释器在 **QMT 终端外**运行，读取自身版本、内建模块和二进制身份，不导入券商 API：

```powershell
$SdkPythonw = 'D:\software\your-qmt\bin.x64\pythonw.exe' # 替换为目标 QMT 配套 SDK
$arguments = @('-I', '-B', "`"$Repo\scripts\qmt_sdk_manifest.py`"", '--output', "`"$Private\sdk.json`"")
$process = Start-Process -FilePath $SdkPythonw -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0 -or !(Test-Path "$Private\sdk.json")) { throw 'SDK清单采集失败，请核目标解释器和输出位置' }
```

采集只创建新文件，已存在的清单保留原件；换新文件名后重新采集。`--stdlib-license` 使用该已核 CPython SDK 对应的完整许可文本，放在例如 `D:/qmt-private/CPYTHON-LICENSE.txt`。已有相同 SDK 的已核配对可复用其中的许可证。当前生成器按固定 SHA 核验许可；新安装缺许可时从该 SDK 发行材料准备并核对，任意改名的文本无法通过校验。清单里写有 SDK 的实际绝对路径，搬迁后需重新采集和配对。

## 生成并核验完整正文

`--output` 使用 Windows 本机固定卷上已有父目录下的新绝对路径。只读部署的配对与通信 SQLite 放在同一个私有父目录，WT 服务只声明 `trade_host`，Host 仅监听 `127.0.0.1` 且关闭写入。现有生产部署的卷约束沿原契约。[私有持久化规则](../specs/wt-private-persistence.md#persist-01-路径与开发规则)

```powershell
$Pair = 'E:\qmt-private\pair-001' # 先准备 E:\qmt-private；pair-001 由生成器独占创建
& $HostPython -I -B -m guanheng_qmt_shm.trade_cli pair `
  --config "$Private\qmt-trade-config.json" `
  --memory-sdk-manifest "$Private\sdk.json" `
  --stdlib-license "$Private\CPYTHON-LICENSE.txt" `
  --reconnect-seconds 0.2 --source-mode strategy_tick --output $Pair
if ($LASTEXITCODE -ne 0) { throw '配对失败，保留输出并检查输入材料' }

$Agent = & $HostPython -I -B -c 'from pathlib import Path; import guanheng_qmt_shm_agent as a; print(Path(a.__file__).resolve().parent)'
& $HostPython -I -B -m guanheng_qmt_shm.trade_cli verify --directory $Pair --installed-agent $Agent
if ($LASTEXITCODE -ne 0) { throw '配对核验失败' }
```

`0.2` 是本示例采用的断连重试间隔（秒），接受范围为 0.1～60 秒。`strategy_tick` 显式采用原策略回调驱动，省略时使用默认 thread 模式。切换模式时生成新配对及对应正文，原配对和通信库继续保留。具体线程要求见[来源运行手册](qmt-source-runtime.md)。

成功后生成 `strategy.py`、`host.py`、`deployment.json`、`policy.json`、`manifest.json`、`CPYTHON-LICENSE.txt`。`pair/verify` 只生成/读取材料，保持 Journal、共享内存、HTTP 服务和 QMT SDK 调用未启动。核验成功证明材料一致性；真实连接、业务数据和交易能力要在对应环境分别验证。

本模板产生账户查询接入正文。完整系统需要按[组合账户手册](qmt-account-composed-source.md)及[交易托管手册](qmt-trade-host-product.md)另行配置行情、历史准备、分析、证券资料与执行通道；已有运行正文应保留原件，按完整能力组合生成后再替换。

## Windows 首次安装

国金和国信共用下面的命令。在克隆后的工程根目录打开 PowerShell，创建本机部署配置并保存实际路径。工程根由当前目录取得。Git 忽略工程下的 `.qmt-runtime/` 和旧的 `.qmt-first-install/`。[部署配置模板](../../connectors/qmt_shm/examples/qmt-deployment.example.json)

```powershell
$ErrorActionPreference = 'Stop'
$Repo = (Get-Location).Path
$LocalRoot = Join-Path $Repo '.qmt-runtime'
$DeploymentInput = Join-Path $LocalRoot 'deployment-input.json'
New-Item -ItemType Directory -Force -Path $LocalRoot | Out-Null
if (!(Test-Path -LiteralPath $DeploymentInput)) {
    Copy-Item "$Repo\connectors\qmt_shm\examples\qmt-deployment.example.json" $DeploymentInput
}
notepad.exe $DeploymentInput
```

| 字段 | 填写方法 |
|---|---|
| `qmt_directory` | 目标 QMT 安装中包含 `XtItClient.exe` 和 `pythonw.exe` 的实际 SDK 目录，通常是 `bin.x64` |
| `python312` | 终端外 Python 3.12 x64 的绝对路径。命令展开模板中的 `%LOCALAPPDATA%` |
| `runtime_root` | 新部署的运行根绝对路径，使用支持持久化 ACL 的本机固定卷。`null` 使用工程下的 `.qmt-runtime/`。自定义目录可放在仓库外，或放在工程内被 Git 忽略的 `.qmt-runtime/` 下 |

QMT 的安装卷、工程卷和运行卷可分别选择。私有配对、通信库和控制文件由 `$Base` 派生。保存配置后执行以下读取命令。另开 PowerShell 窗口时，也从工程根运行这一段。

```powershell
$Repo = (Get-Location).Path
$DeploymentInput = Join-Path $Repo '.qmt-runtime\deployment-input.json'
$Paths = Get-Content -Raw -LiteralPath $DeploymentInput | ConvertFrom-Json
$Qmt = $Paths.qmt_directory
$Python312 = [Environment]::ExpandEnvironmentVariables($Paths.python312)
$Base = if ($Paths.runtime_root) { $Paths.runtime_root } else { Join-Path $Repo '.qmt-runtime' }
$Private = Join-Path $Base 'materials'
$HostPython = "$Base\host\Scripts\python.exe"
$WtPython = "$Base\wt\Scripts\python.exe"
```

在运行 QMT 的同一 Windows 用户和会话中安装终端外环境。当前生成器要求用 QMT 配套的 CPython 3.6.8 x64 采集 SDK 和运行终端策略。

```powershell
New-Item -ItemType Directory -Force -Path $Private | Out-Null
& $Python312 -m venv "$Base\host" "$Base\wt"
if ($LASTEXITCODE -ne 0) { throw '虚拟环境创建失败' }
& $HostPython -m pip install "$Repo\connectors\qmt_shm\agent" "$Repo\connectors\qmt_shm\host"
if ($LASTEXITCODE -ne 0) { throw 'Host 或 Agent 安装失败' }
& $WtPython -m pip install "$Repo\integrations" "$Repo\apps\wt_runtime"
if ($LASTEXITCODE -ne 0) { throw 'WT 安装失败' }
foreach ($python in @($HostPython, $WtPython)) {
    & $python -m pip check
    if ($LASTEXITCODE -ne 0) { throw '依赖检查失败' }
}
```

按前文的 SDK 步骤采集 `sdk.json`，把 `$SdkPythonw` 改为 `Join-Path $Qmt 'pythonw.exe'` 的结果。把对应的 CPython 许可证放在 `$Private\CPYTHON-LICENSE.txt`。缺少许可证时，可从 [CPython v3.6.8 的 LICENSE 原件](https://raw.githubusercontent.com/python/cpython/v3.6.8/LICENSE)下载并使用 `Get-FileHash` 核对 `b9a6d9320b8f2693e8d41e496ce56caadacaddcca9be2a64a61749278f425cf2`。

如果 Windows 无法连接下载地址，在可联网的电脑下载该公开许可证，复制到上面的文件路径，在部署电脑上重新核对 SHA256。SDK 清单仍用目标 QMT 的内置 Python 现场采集。

[准备脚本](../../scripts/qmt_prepare_readonly.ps1)读取仓库的脱敏模板、提示输入 QMT 股票资金账户标识、获取实际进程会话、生成两把随机密钥并执行 `pair → verify`。脚本还生成 `trade-host.json`、`runtime.json` 和 `service.json`。使用尚不存在的 `$Root` 和空闲的本地端口。

```powershell
$Root = Join-Path $Base 'account01'
$Port = 18159
$Strategy = 'GH_WT_MEMORY_VERIFY'
& "$Repo\scripts\qmt_prepare_readonly.ps1" `
  -Root $Root -QmtTerminal (Join-Path $Qmt 'XtItClient.exe') `
  -HostPython $HostPython -WtPythonw "$Base\wt\Scripts\pythonw.exe" `
  -SdkManifest "$Private\sdk.json" -License "$Private\CPYTHON-LICENSE.txt" `
  -Port $Port -ReconnectSeconds 0.2 -StrategyName $Strategy
$Pair = Join-Path $Root 'pair'
$Service = "$Base\wt\Scripts\guanheng-wt-service.exe"
& $Service start --service-config "$Root\service.json"
& $Service status --service-config "$Root\service.json"
```

在目标 QMT 的策略管理界面（例如「模型研究」）中新建同名 Python 策略，保存条目并关闭编辑器。下面的 `$Target` 使用国金的实测布局。国信或其他版本以客户端保存的新策略文件为准，按实际路径调整 `$Target`。先确认文件属于专用新条目，再备份模板、复制配对原件并核验摘要。策略含 IPC 密钥，文件权限沿源文件 ACL。

```powershell
$Source = Join-Path $Pair 'strategy.py'
$Target = Join-Path (Split-Path $Qmt -Parent) "python\$Strategy.py"
$Backup = Join-Path $Root 'qmt-new-strategy-template.py'
$Manifest = Get-Content -Raw "$Pair\manifest.json" | ConvertFrom-Json
if (!(Test-Path -LiteralPath $Target -PathType Leaf) -or (Test-Path -LiteralPath $Backup)) {
    throw '请核对新策略文件和备份位置'
}
if ((Get-FileHash -LiteralPath $Source).Hash -ne $Manifest.files.'strategy.py') {
    throw '配对策略文件摘要不符'
}
Copy-Item -LiteralPath $Target -Destination $Backup
Set-Acl -LiteralPath $Target -AclObject (Get-Acl -LiteralPath $Source)
[IO.File]::WriteAllBytes($Target, [IO.File]::ReadAllBytes($Source))
if ((Get-FileHash -LiteralPath $Target).Hash -ne $Manifest.files.'strategy.py') {
    throw '目标文件摘要不符'
}
```

重开编辑器，确认正文包含 `_memory_entry_name`，使用终端内策略回调模式运行。客户端若显示「启动本地 Python」或「独立 Python 进程」选项，保持未勾选。国金实测界面显示 `start simulation mode`，其他版本按各自的运行日志和下面的签名探针核验。QMT 运行时可能重存策略文件，配对目录中的原件作为生成身份保留。

```powershell
Invoke-RestMethod "http://127.0.0.1:$Port/health"
& $HostPython -I -B "$Repo\scripts\qmt_account_read_probe.py" $Pair
```

检查 `status=available`、`lifecycle=connected`、`order_ready=false`。资金、持仓、委托和成交应分别返回 `OK`。完整返回 0 条是有效结果。需要关闭实例时，先在同一策略编辑器点击「停止」，再执行 `& $Service stop --service-config "$Root\service.json"`。同一实例再次启动沿用原配置、配对和库。

首次安装可用目标 QMT 的内置样例验收历史回测，国金实测使用的是「指数增强回测示例」。设置回测参数后记录区间、基准、模拟初始资金、净值和模拟成交。日志中的缺行情及按停牌跳过属于数据覆盖问题。同一终端切入历史回测可能停止原编辑器运行的 Agent。回测结束后如需继续只读查询，重新运行原配对的策略并用探针确认。项目自有策略沿 [WT 原生隔离回测](native-backtest.md)使用冻结历史和独立输出。

## 单盘组合只读部署

适用于已经完成上节安装与 SDK 采集的国金和国信 QMT。组合配对在一个 QMT 策略正文中启用账户查询、行情全推、快照、分钟读回和补齐、分析及证券资料。WT 托管账户 Host，终端外脚本独立运行四个行情与资料 HTTP Host 及实时行情接收器。各角色保持独立凭据与通信库，HTTP 只绑定 `127.0.0.1`。

### 准备组合实例

将[行情与资料示例](../../connectors/qmt_shm/examples/qmt-readonly-market.example.json)复制到本机私有目录并按现场调整。

| 字段 | 部署时填写 |
|---|---|
| `ports.history`、`ports.analysis`、`ports.batch`、`ports.reference` | 四个不同的空闲本地端口，另外为账户 `-Port` 留出独立端口 |
| `quote_symbols` | 实时接收的沪深证券列表 |
| `history_prepare_symbols` | 允许显式补齐分钟缓存的沪深证券列表。补齐限定单证券、同一自然日内的分钟窗口 |
| `security_source_groups` | 示例采用国金实测的沪市和深市 ETF 板块。两家均用目标 QMT 的 `get_sector_list` 核对目录节点和板块名，再填写对应的市场和证券类型 |

列表预算为每类最多 128 只，供首次安装和小范围接入。换证券范围、端口或 Windows SessionId 时，用新实例重新生成配对和正文。准备失败时保留原材料，重新选一个尚不存在的 `$Root`。共享盘可搬运脱敏配置模板及源码，账户材料和运行库放在本机私有目录。

在与 QMT 相同的 Windows 会话执行。沿用上节的 `$Repo`、`$Base`、`$Private`、`$Qmt` 和 `$HostPython`，按现场替换下列新实例路径、策略名称和端口。现有服务占用示例端口时，应先在私有配置中另填端口。

```powershell
$Root = Join-Path $Private 'market-readonly-01'
$Strategy = 'GH_WT_MARKET_READONLY'
$MarketProfile = Join-Path $Private 'market-profile.json'
Copy-Item "$Repo\connectors\qmt_shm\examples\qmt-readonly-market.example.json" $MarketProfile
# 编辑 $MarketProfile，再运行准备命令
& "$Repo\scripts\qmt_prepare_readonly.ps1" `
  -Root $Root -QmtTerminal (Join-Path $Qmt 'XtItClient.exe') `
  -HostPython $HostPython -WtPythonw "$Base\wt\Scripts\pythonw.exe" `
  -SdkManifest "$Private\sdk.json" -License "$Private\CPYTHON-LICENSE.txt" `
  -Port 18159 -ReconnectSeconds 0.2 -StrategyName $Strategy -MarketProfile $MarketProfile
```

原准备脚本在本机生成账户和各市场角色的独立认证材料，沿用 `strategy_tick`，核验单一组合 `$Root\pair`，并把 WT 的服务描述符绑定到它。`$Root\market-readonly\market-host.json` 保存终端外角色的私有配置和 HTTP 密钥，随实例受控保存。`-Synthetic` 用于隔离的材料与监听验证，真实业务回读用已授权账户和匹配的 QMT 模型。

### 启动、查看和停止

在一个 PowerShell 窗口启动 WT 账户 Host，再在另一个窗口前台运行市场角色。两个窗口都使用 QMT 所在的 Windows 会话。

```powershell
$Service = "$Base\wt\Scripts\guanheng-wt-service.exe"
& $Service start --service-config "$Root\service.json"
# 另一个窗口从工程根载入 deployment-input.json，再选本次实例
$Root = Join-Path $Private 'market-readonly-01'
& $HostPython -I -B "$Repo\scripts\qmt_readonly_market.py" serve --root $Root
```

沿上节的策略安装步骤，把 `$Root\pair\strategy.py` 安装到对应的新策略条目，核对摘要，再在 QMT 中启动该 Python 模型的模拟运行。在终端外查看状态和账户查询。

```powershell
& $HostPython -I -B "$Repo\scripts\qmt_readonly_market.py" status --root $Root
& $HostPython -I -B "$Repo\scripts\qmt_account_read_probe.py" "$Root\pair"
```

`status` 使用各角色的私有 HTTP 密钥为 `read-binding` 请求签名。收到 HTTP 200 后，核对回包的来源路由和完整能力是否与本次配对一致，通过时显示 `available/connected` 和 `binding_verified=true`。`reachable` 表示端口有 HTTP 响应，配对一致性尚未确认。逐项业务资格以请求和回包为准。`quotes.fresh` 表示接收器状态在最近五秒更新，交易时段要另核 `incremental_ticks` 上升及 `last_source_at_utc.incremental` 随新行情更新。

完成观察后，先停止发新请求并核清在途补齐，停 QMT 模型，再在市场角色窗口按 Ctrl+C 并等待退出。使用 `& $Service stop --service-config "$Root\service.json"` 停止账户 Host。相同 Windows 会话内可用原材料和原通信库重启。原状态文件、缓存补齐时的请求身份和旧实例保留以供回读。市场四个角色使用原保留读协议，每角色最多同时保留 96 条记录，历史角色内快照、读回与补齐共用该额度。原结果先由客户端保存并确认消费，原票据结束后由 Host 回收。未知、未确认或仍在途的结果保留原 ID；满额时先续核原请求或等票据到期，随后在原实例继续。此前采用旧非保留配对的实例通过新目录生成和切换，旧配对及通信库留存。

### 业务验收

四个市场角色使用匹配的 Host 端口和私有 HTTP 凭据，通过原 `RetainedReadClient` 提交带票据的请求，保存和确认原结果。现有历史准备消费者需启用 `retained_reads`。账户探针沿原账户协议。小样本先核证券、日期、时间窗及覆盖。

| 角色 | 核验 |
|---|---|
| 快照与实时行情 | 调用 `market.full_tick` 核对快照证券及源时间。实时接收器独立看到心跳、快照和盘中新鲜的增量后，分别记录这三项 |
| 历史 | 参照[分钟历史读取](qmt-shm-history.md#首次读取)核对证券、过去交易日和小窗参数，通过保留读取客户端提交。需要补齐时沿[历史补齐](qmt-history-preparation.md)对已允许的证券发一次请求，核原回执后复读同一时间窗。结果未知时按原 ID 查询 |
| 分析 | 核单证券日线 `market.market_data`、复权因子 `market.divid_factors` 以及[批量日线](qmt-analysis-batch-source.md)的逐证券状态。两种日线读取都使用 QMT 已有的日线数据。样本返回空时，换用目标终端已有数据的证券和日期复测，分别记录接口响应和实际数据覆盖。组合实例的缓存补齐只适用于分钟线 |
| 证券资料 | 沿[证券资料](qmt-security-reference.md)读取 `market.security_details` 和 `market.security_universe`，核同一 catalog 的分页、组状态及成员计数 |

## 启动、验真和故障定位

1. 按[独立 WT 手册](wt-independent-runtime.md)及[交易 Host 手册](qmt-trade-host-product.md#wt-一次启动)登记此安装的 Python、Agent、配对目录和摘要，WT 管理 Host；隔离直启只用于明确的验证实例。
2. 在目标 QMT 登录账户，按前文步骤保存并运行匹配的完整 `strategy.py`，核对实际入口身份。国信界面操作见[国信操作手册](guosen-qmt-operations.md#策略保存与执行方式)。
3. 先核本代 Host 监听，再核认证 binding、来源心跳及账户查询实际成功。签名请求由正式客户端构造，`/health` 和进程存在分别只表示中间状态。
4. 换账户使用新路由/绑定、密钥及独立通信库和策略账。旧库、旧未知委托及原始回报保留在原账户归属下。

| 现象 | 检查 |
|---|---|
| 缺少 config | `--config` 必填；将示例复制为私有 JSON，确认它和 `operation_policies_path` 指向的文件均存在 |
| `admission_or_operation_failed` | CLI 统一错误码。依次核文件绝对路径、两个密钥环境变量、账户两处一致性与摘要、容量联合约束、SDK 原件、许可证以及本地卷与新目录条件 |
| Host ready、QMT 未连接 | 核实际策略运行、Windows SessionId、映射名、配对身份和认证；继续按[SHM 排障手册](guosen-qmt-troubleshooting.md)检查 |
| 资金查询已受理，结果返回 503 | 保留原请求 ID，核 Host 代际、QMT 日志和通信库终态。该现象在国金新机的默认 thread 配对中出现过，现场另用 `strategy_tick` 配对后完成了四项只读验收 |
| 账户查询成功、行情未就绪 | 本模板声明账户查询；沿完整组合流程加入所需行情能力并验真 |
| 离线 verify 成功、真实终端报错 | 保存该配对身份和脱敏错误，核券商 SDK/回调和实际解释器兼容性；实机加载与离线核验分别验收 |

仓库回归入口为 `python -B tests/integration/qmt_shm_trading/test_config_examples.py`，使用 Host 锁定依赖。配置准入测试只核配对材料。设置 `QMT_EXAMPLE_SDK_MANIFEST` 与 `QMT_EXAMPLE_LICENSE` 为已核材料路径后，测试会使用合成账户和测试密钥执行 CLI `pair → verify`。测试默认使用 Windows 临时目录，也可将 `QMT_EXAMPLE_PAIR_PARENT` 指向本机固定卷上已有的私有父目录。
