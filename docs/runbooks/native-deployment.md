# 原生二进制部署操作手册

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：操作手册。范围：原生组件构建、校验、隔离验收、切换与回滚。开发候选打包与校验使用构建工具；具体生产路径、实例托管与准入控制必须进入已验证发布记录。监督/切换入口尚未交付，不能仅据本文执行生产启用。

经职责复核确需保留数据库时，Windows原生服务及迁移验收遵循[条件规格](../specs/windows-native-database.md)。原生程序包不包含业务数据库数据目录；实际选用的数据库及扩展单独锁定版本、备份恢复和管理，当前实例切换须完成隔离演练。

## 1. 固定候选与构建输入

按[发布规范](release.md)固定已审候选，记录主干集成身份、注释发布标签、工具链、OS/架构、核心库/插件 ABI、SDK、配置与状态模式。正式制品由干净、可追溯源快照构建，线上接收同一包。

版本元组为 `release_id + source_commit + upstream_base_commit + artifact_hash + config_version`；数据版本与状态模式另外登记。固定标签和校验清单确认内容，文件名中的版本只提供阅读便利。

按[构建手册](build.md)生成需要的目标。包内包括 EXE、匹配库与插件、运行依赖、获准分发 SDK、许可证和脱敏模板；私有配置/凭证和业务状态独立管理。

## 2. 清单和接收校验

使用制品清单示例（外部历史/待归仓路径：`../releases/artifact-manifest.example.json`）的字段结构；示例标记及占位内容必须在实际发行中替换，逐文件清单覆盖包中全部受管文件，摘要以文件实际内容计算。

SDK-independent 开发包的实际 manifest schema 由 [artifact.py](../../scripts/native_support/artifact.py)定义，身份放在 `provenance`，标记 development。`python -B scripts/native.py package` 复验当前构建与测试后生成开发包；接收校验使用 `python -B scripts/native.py verify --archive <包路径> --sha256 <可信外部摘要>`。示例按开发包 schema 展示；生产发行的兼容版本、配置/状态模式、受控标签和审批资格由正式发布记录另行绑定。

校验来源与预期包摘要通过已认证渠道获得。包内自带的清单用于逐文件核对，可信来源还需绑定受控发布身份；文件哈希本身不证明发布者身份。

`qmt-readonly-fixed` 开发包的清单带显式 profile、固定 WT/QMT 提交和源清单摘要。它提供 `app/traders/TraderQMTReadOnly.dll`、`validation/bin` 普通宿主和脱敏验证工具；门控 DLL、受控 QMT 源、账户配置及运行终端均不随包分发。接收端按[构建手册](build.md)选择同 profile 进行归档/二进制校验。完整原 Core HTTP 验证需另行提供固定受控来源，收据明确登记这项外部验证依赖。

此开发包用于隔离只读验收；生产切换继续核实具体宿主、实例工作目录、实际加载 DLL 身份与来源/配置资格。默认关闭示例只描述配置形状，启用真实端点和托管实例按本手册后续发布步骤授权执行。

PowerShell 校验命令示例（在已核实目录执行）：

```powershell
$packageRoot = (Resolve-Path -LiteralPath '<已接收并隔离解压的包目录>').Path
$manifestFile = Join-Path $packageRoot 'manifest.json'
$manifest = Get-Content -LiteralPath $manifestFile -Raw | ConvertFrom-Json
if ($manifest.example -eq $true) { throw '示例清单不能用作发行身份' }
foreach ($entry in $manifest.files) {
    $filePath = [IO.Path]::GetFullPath((Join-Path $packageRoot $entry.path))
    $prefix = $packageRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if (-not $filePath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw '文件超出包目录' }
    if ((Get-Item -LiteralPath $filePath).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw '包文件必须是普通文件' }
    $actual = (Get-FileHash -LiteralPath $filePath -Algorithm SHA256).Hash
    if ($actual -ne $entry.sha256) { throw "文件校验失败：$($entry.path)" }
}
```

此片段只展示路径和哈希核对，尚不承担完整清单模式、目录内全部文件、目录重解析点、包签名与发行资格校验；正式接收工具需要覆盖这些条件并受测。

## 3. 包级隔离启动

在干净实例运行：确认配置、日志、历史数据、状态路径、运行库、插件加载、资源预算及退出方式。实例工作目录固定，程序从目标包的完整路径启动。

以当前 Runner 为例，启动形状为 `WtRunner.exe -c <配置路径> -l <日志配置路径>`；先使用显式隔离后端和独立状态，验证配置没有绑定真实可写账户。上游没有统一的“只读启动开关”，资格由实际接入和配置证明。

Windows 插件搜索可能优先命中工作目录的 `parsers/`、`traders/`，再查程序目录；隔离验收应核实工作目录残留、依赖搜索和实际加载路径。稳定工作目录让默认 `generated/` 状态保留在实例侧，其他日志/数据路径也须逐项验证。

监督入口必须绑定 EXE 完整路径、工作目录、参数、环境、配置及实例互斥身份。桌面用户会话依赖经实机验证后再选 Windows 服务或用户会话托管。后台启动使用隐藏窗口；进程自动重启不会自行恢复交易准入。

## 4. 切换

1. 核实授权、旧/新包身份、状态可读性、备份恢复、实际运行实例及停止条件。
2. 通过权威控制入口停止受影响新增准入，继续回报摄取；核清在途、未知提交和当前执行权。
3. 使用该实例已验证的退出/排空入口结束旧运行，确认原写入口停止。停止旧实例不代表其订单已终结。
4. 更新受管监督配置，指向新包及适用配置，保留稳定实例工作目录与状态；确认唯一活动实例后启动。
5. 先只读核实 EXE/库/插件、配置、账户会话、数据及回报，再完成[测试手册](testing.md)规定的实际入口验真，按资格恢复对应准入。

准确的实例控制命令、排空/退出回执与 active 元数据提交方式由环境实施任务补齐，实际发布前必须演练；本手册不虚构现有服务控制工具。

## 5. 回滚与记录

保留失败现场和状态，按已验证旧包/配置恢复，继续核查所有未完成及未知副作用；状态不兼容时按恢复方案前向处理。逐项记录实际部署身份、入口数据、异常/空/恢复结果及观察窗口。

填写[发布记录](../releases/TEMPLATE.md)，制品只保留可验证发行目录，清理任务独立授权并遵守数据保留要求。
