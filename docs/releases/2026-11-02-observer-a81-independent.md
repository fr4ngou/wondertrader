# 2026-11-02 观衡a81独立候选交付

类型：development独立交付记录。状态：已合入、离线构建、安装并通过真实页面验收；原入口及生产保持。

版本`0.1.0a81+oar.3`，构建源码`390a625ffd6d9b151dca20181e8b354f76d0509a`。源码包含行情工作区、真实日/周/月读取和紧凑账户/状态展示。详细范围、原件摘要及未完成项见[安装验收](../evidence/2026-11-02-observer-a81-user-acceptance.md)。文档后继提交不改变该固定构建身份。

## 访问和安装

已运行入口：`http://127.0.0.1:18139/market?search=300308.SZ`。旧18122仍是旧版。

交付ZIP为`E:/workspace/wondertrader-qa/root-observer-oar-a81-003/observer-0.1.0a81+oar.3-windows-x64.zip`，SHA256为`7e2655915003ca4e8eefd446e6c2a1ddb98a4adf9c1a445352020c18ef7f5baf`。原件目录同时提供构建清单、实际浏览器结果和截图。重新安装沿[独立观衡手册](../runbooks/observer-runtime.md)，使用全新目录、显式Python与uv；运行包清单SHA256为`87b6af31014dc66cfd73529b7f6e0982a83369f0684f45852579d7c8fc61507a`。

本机安装目录为`C:/Users/frangou/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Guanheng/observer/0.1.0a81+oar.3`。外部私有读取配置和个人目录位于`E:/workspace/wondertrader-data/observer-oar-user-20261102-a81-003`。配置文件含凭据，保持本机受控权限，不随ZIP或Git交付。

## 启动与关闭

当前18139已经运行，保持该实例即可验收。未来重启观衡时，先确认旧18139实例已正常退出、端口释放，再在同一终端加载私有配置并运行已安装CLI：

```powershell
$observerInstall = 'C:/Users/frangou/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Guanheng/observer/0.1.0a81+oar.3'
$observerConfig = Get-Content -LiteralPath 'E:/workspace/wondertrader-data/observer-oar-user-20261102-a81-003/environment.private.json' -Raw | ConvertFrom-Json
foreach ($entry in $observerConfig.PSObject.Properties) {
    [Environment]::SetEnvironmentVariable($entry.Name, [string]$entry.Value, 'Process')
}
& "$observerInstall/runtime/app/venv/Scripts/python.exe" -I -B -m guanheng_app --port 18139 --static-directory "$observerInstall/payload/spa"
```

这是交互式运行入口，Ctrl+C沿App正常关闭；后台运行继续使用受管隐藏入口。当前后台验收进程与交互式示例分别记录，示例不会停止现有实例。每个个人目录同一时刻仅供一个App使用，避免自选偏好并发写入。

独立WT的18136来源沿[WT日线部署记录](../evidence/2026-11-02-daily-history-wt-runtime.md)和[独立WT操作手册](../runbooks/wt-independent-runtime.md)管理，其运行配置为`E:/workspace/wondertrader-data/daily-history-wt-20261102-001/private/runtime.json`。观衡重启、关闭和升级都不启动或停止WT、Host、采集及策略。

## 回退及剩余范围

旧版18120/18122/18123/18126及各自安装、私有配置、自选和观察根保持。本次为独立新入口，直接回到原URL即可查看旧版；正式替换时先正常关闭新版，再按旧版原配置启动。新自选目录是独立副本，如已编辑，回退前保留该副本；不覆盖原偏好。原数据根和快照没有升级，无需转换数据。

本版读到的账户是最后成功结果，真实策略最新资金基线仍在追查，较长市场历史候选尚未采用。观衡可独立验收；资金缺口和WT实际模拟交易验收继续由对应模块完成。
