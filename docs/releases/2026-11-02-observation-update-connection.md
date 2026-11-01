# 2026-11-02 独立市场更新行情连接交付

类型：development维护角色交付。状态：已部署、正常停止恢复通过。此入口后继于a82历史交付记录中的更新控制目录；观衡页面与WT安装保持各自版本。

当前页面仍为`http://127.0.0.1:18140/observation?metric=breadth.ashare`。更新角色使用观衡App已安装的`0.1.0a82+history.1`监督程序，维护模板版本为`20261102.1`，负责显式装配本角色行情连接；它不负责启动页面或WT。实际身份及来源限制沿[部署证据](../evidence/2026-11-02-observation-update-connection-installed.md)。

## 当前操作

角色已运行，勿重复start。PowerShell状态入口：

```powershell
$updateRoot = 'C:/Users/frangou/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Guanheng/observation-update/a82-market-20261102-001'
$updateOwner = Get-Content -LiteralPath "$updateRoot/PREPARED.json" -Raw | ConvertFrom-Json
& $updateOwner.python -I -B "$updateRoot/update_owner_control.py" status --profile live
```

把status替换为stop正常停止；确认outcome=closed、实际监督者exit0与父子closed/join后，可替换为start恢复。凭据文件损坏仍可status/stop；启动会在创建运行身份前报告具体配置错误。failed或unknown先核原身份和截止结果，再处理恢复，保留同一业务根的窗口、尝试和回执。

当前只准备live profile，保持26来源、09:00北京时间及600秒预算。Windows重启后沿本入口恢复；不新增OS定时任务。观衡Web关闭或更新保持该角色和WT独立运行，WT18136沿其原独立手册管理。

## 交付和回退

维护ZIP、PACKAGE摘要及实际角色原件位于`E:/workspace/wondertrader-qa/observation-update-market-20261102-001`，不包含私有凭据。新部署按包内README及[连接规格](../specs/observation-update-connection.md)准备独立控制材料，再使用已安装监督者。私有行情文件及摘要只在本机受控部署中提供。

原`a82-20261102-001`和更早a80控制材料保持已停止，不能与本角色并行启动。需要回退维护工具时先正常停止本角色，再恢复原a82控制材料；原代码会清除行情环境，因此回退同时恢复其“WT连接未配置”的已知限制。业务快照、窗口及尝试无需转换，仍读取同一fd94及后继原事务记录。原App/WT无需随维护工具回退。

本次验证的是维护连接、SDK读取与停止恢复；全部来源刷新成功、指数单位/历史补齐及T2108新日期生产分别继续验收。
