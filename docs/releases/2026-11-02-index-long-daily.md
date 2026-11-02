# 指数长日线接入与维护

类型：本机部署记录。状态：003已上线；本轮回退未执行。范围：独立WT行情18146及同版a86观衡18143的历史连接。

打开 <http://127.0.0.1:18143/market?search=000001.SH>。上证指数现有2015-01-05至2026-10-30共2870条真实日线，2016年244条可读。实际来源、逐字段验证及保留范围见[上线证据](../evidence/2026-11-02-index-long-daily-live.md)。本次只替换上证日线路由；旧300/16日线owner、50指数清单中的其余日线路由、股票、ETF及分钟沿原配置。旧WT18142保留，独立市场更新继续由其原owner管理。

## 观衡维护与历史连接回退

以下命令来自已安装的原`observer-web.py`，与仓库[模板源码](../../scripts/runtime_templates/observer-web.py)字节相同。维护命令只管理本Web；下列命令按需要单独执行。

```powershell
$install = 'C:/Users/frangou/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Guanheng/observer/0.1.0a86+capital.1'
$python = "$install/runtime/app/venv/Scripts/python.exe"
$tool = "$install/payload/observer-web.py"
$profile = 'E:/workspace/wondertrader-data/observer-controlled-web-20261102-a86-history-001/web-profile.json'
& $python -I -B $tool status --profile $profile
& $python -I -B $tool stop --profile $profile
& $python -I -B $tool start --profile $profile
```

正常停止要求原工具报告closed/stopped、App关闭完成、两类Reader线程为0，并确认Web和启动器退出码0；结果未知时先查询原控制身份。新profile原字节SHA256为`822bb03addd51ba0bc813320fa135e9b0ddaaddb30c5de75195267b0f3a410e4`。工具按原profile读取受控环境，个人目录保持原绑定。此次切换已验证旧Web正常关闭；文档收口未再次启停。

需要将历史连接退回旧18142时，先正常停止新profile并确认个人目录与18143端口释放，再沿同一a86安装启动旧profile：

```powershell
& $python -I -B $tool stop --profile $profile
$previousProfile = 'E:/workspace/wondertrader-data/observer-controlled-web-20261102-a86-001/web-profile.json'
& $python -I -B $tool start --profile $previousProfile
```

旧profile的历史地址为18142，原字节SHA256为`69cfd6d33cc7a822bf0b4c48ef872f6ac95f7abbf06e8f5a23949a9325932a05`。这是本次历史连接的回退入口；本轮未执行回退。个人数据沿原目录保留。后继账户与资金接线如已改变其配置，由该接线owner先核对保留要求。

## 独立WT的启动和正常停止

固定部署收据为`E:/workspace/wondertrader-data/index-long-daily-wt-20261102-001/DEPLOYMENT.json`。入口沿[原WT源码](../../apps/wt_runtime/guanheng_wt_runtime/__main__.py)和[独立WT手册](../runbooks/wt-independent-runtime.md)，采用配置、摘要、新控制目录及控制UUID四项参数。每次启动前确认同实例上一代已正常退出、18146已释放；在专用PowerShell中载入私有环境，由隐藏WT进程继承，随后关闭该专用PowerShell。私有文件保留且正文不输出。

```powershell
$root = 'E:/workspace/wondertrader-data/index-long-daily-wt-20261102-001'
$wt = Get-Content -LiteralPath "$root/DEPLOYMENT.json" -Raw | ConvertFrom-Json
Get-ChildItem Env:GUANHENG_* | ForEach-Object { [Environment]::SetEnvironmentVariable($_.Name, $null, 'Process') }
$privateEnvironment = Get-Content -LiteralPath $wt.environment_file -Raw | ConvertFrom-Json
$privateEnvironment.PSObject.Properties | ForEach-Object { [Environment]::SetEnvironmentVariable($_.Name, [string]$_.Value, 'Process') }
$controlId = [guid]::NewGuid().ToString()
$controlDirectory = Join-Path "$root/controls" $controlId
$pythonw = Join-Path (Split-Path $wt.wt_python) 'pythonw.exe'
Start-Process -FilePath $pythonw -WindowStyle Hidden -ArgumentList @('-I','-B','-m','guanheng_wt_runtime','--config',$wt.runtime_configuration,'--config-sha256',$wt.runtime_configuration_sha256,'--control-directory',$controlDirectory,'--control-id',$controlId)
```

等待本代`ready.json`和`status.json`，核对配置SHA、instance、control及history组件，再核真实行情。新代控制目录及UUID须登记到新的部署记录，并更新观衡只读WT状态定位及其profile摘要；旧代收据保留。上面的示例未在本轮执行，不会自动改写部署收据或观衡profile。

正常停止当前已登记的一代时，先核对`DEPLOYMENT.json`与该代ready/status的身份，随后向其控制目录原子发布原stop协议。若已按上段重启，应使用已登记的新代部署记录。

```powershell
$wt = Get-Content -LiteralPath "$root/DEPLOYMENT.json" -Raw | ConvertFrom-Json
$stop = @{ schema='guanheng.wt-runtime-stop.v1'; control_id=$wt.control_id; instance_id=$wt.instance_id; configuration_sha256=$wt.runtime_configuration_sha256 }
$pending = Join-Path $wt.wt_control_directory ('.stop-' + [guid]::NewGuid().ToString() + '.json')
[IO.File]::WriteAllText($pending, ($stop | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
Move-Item -LiteralPath $pending -Destination (Join-Path $wt.wt_control_directory 'stop.json')
```

要求本代`closed.json`为stopped、`components_closed=true`并确认进程退出码0。failure、forced或非零退出按原组件故障处理。停止18146后，观衡仍独立运行，行情读取显示来源离线；需要保持历史查询可用时，将连接切回保留的18142。独立18142和更新角色分别维护。当前18146的正常停止未在此次接收或文档收口中执行。

## 保留范围

003与004的原件、数据、依赖及安装摘要分别沿各自交付清单。004的399001完整8691条尾日停在10月23日，尚未替换含10月29日的旧路由。上证完整8751条及其中8条旧计数语义继续核实，当前上线仅授2015年起2870条资格；量单位继续unknown。观察8表仍按整体完整覆盖要求更新。账户原绑定在本次历史切换时保持，实际策略资金发布、后继账户接线和交易资格分别登记。
