# 2026-11-02 观衡a82历史补齐独立交付

类型：development候选。状态：已合入、安装、采用真实历史并通过实际页面验收。

入口：`http://127.0.0.1:18140/observation?metric=breadth.ashare`；行情页为`http://127.0.0.1:18140/market`。版本`0.1.0a82+history.1`沿用a81完整界面，增加59交易日沪深北广度和日更历史来源保留。详细身份、数据区间和实际验证见[接收证据](../evidence/2026-11-02-observer-ashare-history-installed.md)。

## 安装与页面启动

ZIP位于`E:/workspace/wondertrader-qa/root-observer-a82-history-001/observer-0.1.0a82+history.1-windows-x64.zip`，SHA256为`649cddbdd59d91a2e7c24cd2af4b50d5cc79e2d0b000b802f9d514e892df1051`。重装沿[独立安装手册](../runbooks/observer-runtime.md)，原运行包清单SHA256为`7aad1660ab17c8c7a51830a43095f82297f9ff23e02a7a895062c6c35c4af5eb`。本机安装目录为`C:/Users/frangou/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Guanheng/observer/0.1.0a82+history.1`。

私有环境配置及独立个人目录位于`E:/workspace/wondertrader-data/observer-oar-user-20261102-a82-001`，保持受控权限。当前18140已运行，勿重复启动。未来正常关闭旧实例、确认端口释放后，采用下列交互式入口：

```powershell
$observerInstall = 'C:/Users/frangou/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Guanheng/observer/0.1.0a82+history.1'
$observerConfig = Get-Content -LiteralPath 'E:/workspace/wondertrader-data/observer-oar-user-20261102-a82-001/environment.private.json' -Raw | ConvertFrom-Json
foreach ($entry in $observerConfig.PSObject.Properties) {
    [Environment]::SetEnvironmentVariable($entry.Name, [string]$entry.Value, 'Process')
}
& "$observerInstall/runtime/app/venv/Scripts/python.exe" -I -B -m guanheng_app --port 18140 --static-directory "$observerInstall/payload/spa"
```

Ctrl+C沿App正常关闭。页面入口不启动或停止WT、QMT通信、采集或独立市场更新服务。新个人目录复制自a81本次实际偏好，旧目录保持；并行使用时各目录独立保存，后继升级前保留用户最新偏好。

## 独立市场更新服务

实际更新者为已安装的原`guanheng_app.observation_supervisor`，下列维护命令执行后退出，不持续持有调度循环。角色使用原26来源、北京时间09:00窗口及600秒预算，不新增Windows定时任务。

```powershell
$updateRoot = 'C:/Users/frangou/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Guanheng/observation-update/a82-20261102-001'
$updateOwner = Get-Content -LiteralPath "$updateRoot/PREPARED.json" -Raw | ConvertFrom-Json
& $updateOwner.python -I -B "$updateRoot/update_owner_control.py" status --profile live
```

将status替换为stop可沿原有限截止正常停止；确认outcome=closed、父子关闭、实际OS退出码0后，将其替换为start恢复。维护返回failed/unknown时保留原身份并查状态，避免重复启动。角色仅配置live，Windows重启后沿该入口恢复。WT行情18136由WT独立管理，按[独立WT手册](../runbooks/wt-independent-runtime.md)启停。

## 回退与剩余

原a81及此前页面继续运行，可直接打开原URL。它们读取同一业务根，因此也会读到本次已验兼容的历史快照。旧a80更新器会丢失新增来源说明，保持已停止状态；恢复页面旧版时继续使用a82独立更新角色。

若需整套数据回退，先正常停止新更新owner，沿原观察CLI restore及expected-current把业务指针恢复为保留的`6dbc64f012ccefc115ecf58c27d8efb5c5c150a178e5d582552f57367b2d99ea`。保留新fd94快照、原调度/尝试和回执；核实数据指针后，旧owner才可沿原身份恢复。回退命令未在本次实际运行，当前新快照和服务继续运行；原restore协议资格沿既有操作手册。

策略资金真实基线、T2108持续更新及部分公开来源缺口继续处理；本次没有操作QMT或启用交易。
