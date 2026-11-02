# 市场指标更新角色a85交付

类型：独立更新角色发行。状态：普通安装、实际恢复及连续心跳通过。版本`0.1.0a85+update.1`，源提交af6a955。

本次修正Windows状态读写重叠时的文件替换，并保留有限失败诊断。观衡页面继续使用a84及 <http://127.0.0.1:18143/market?search=300308.SZ>，WT18142独立运行。实际结果、缺陷和原历史异常的证据边界见[恢复验收](../evidence/2026-11-02-observation-a85-recovered.md)。

## 维护命令

```powershell
$updateRoot = 'C:/Users/frangou/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Guanheng/observation-update/a85-update-20261102-001'
$updatePython = 'C:/Users/frangou/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Guanheng/observer/0.1.0a85+update.1/runtime/app/venv/Scripts/python.exe'
& $updatePython -I -B "$updateRoot/update_owner_control.py" status --profile live
& $updatePython -I -B "$updateRoot/update_owner_control.py" stop --profile live
& $updatePython -I -B "$updateRoot/update_owner_control.py" start --profile live
```

状态、正常停止和重启沿原监督者维护工具。仅在当前代已closed、父子实际退出后再start；unknown保留原身份查证。外部私有行情绑定及27来源由本目录PREPARED及其摘要引用，凭据值保持在外部文件。09:00北京时间与原窗口记录保持。

稳定制品目录为`E:/workspace/wondertrader-qa/root-observation-a85-update-001`。该发行只启用更新角色，原a84安装没有热修改。

## 回退

保留原a84失败代用于诊断，它存在已确认的共享读写缺陷。需要停用本次修正时，先正常停止a85更新角色；观衡和WT仍可继续读取已发布结果。旧版本保留供诊断或隔离复现，恢复旧程序前需评估同一写入缺陷。数据、completed_windows和attempts均保留，避免重采已完成窗口。Web版本回退沿[独立Web交付](2026-11-02-observer-a84-web-control.md)，与指标更新角色分开执行。
