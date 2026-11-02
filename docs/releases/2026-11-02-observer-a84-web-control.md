# 观衡a84独立Web维护工具交付

类型：a84后继维护工具及运行接线。状态：本机真实正常停止/重启及页面验收通过。App版本保持0.1.0a84+market.1；本次没有重建App或改写原ZIP。

## 当前入口

使用 <http://127.0.0.1:18143/market?search=300308.SZ>。行情默认60日日线，简称、拼音和代码前缀输入后自动出现候选。市场观察、策略、账户、报告及状态沿左侧导航进入。

当前账户为保留的上次成功发布，资金与模拟交易结果继续验收；市场更新进程11:02退出的故障另行恢复。页面与独立WT18142的读取仍可用。事实和验证范围见[后继验收](../evidence/2026-11-02-observer-a84-web-controlled.md)。

## 启动、停止与重启

本机工具为 `E:/workspace/wondertrader-qa/root-observer-a84-web-control-002/observer-web.py`，配置为 `E:/workspace/wondertrader-data/observer-controlled-web-20261102-a84-002/web-profile.json`。读取配置和个人观察目录在该运行根，配置原件保留供停止使用。

```powershell
$python = 'C:/Users/frangou/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Guanheng/observer/0.1.0a84+market.1/runtime/app/venv/Scripts/python.exe'
$webTool = 'E:/workspace/wondertrader-qa/root-observer-a84-web-control-002/observer-web.py'
$webProfile = 'E:/workspace/wondertrader-data/observer-controlled-web-20261102-a84-002/web-profile.json'
& $python -I -B $webTool status --profile $webProfile
& $python -I -B $webTool stop --profile $webProfile
& $python -I -B $webTool start --profile $webProfile
# 同版重启：
& $python -I -B $webTool restart --profile $webProfile
```

隐藏启动返回`ready`；正常停止返回`closed`，包含App清理及两个OS退出码证明。`unknown`保留原运行代，沿原控制身份查询，不重复启动。详细操作沿[独立观衡手册](../runbooks/observer-runtime.md)。Web停止和升级只影响本实例，WT与市场更新角色保持独立。

## 回退与原实例

原18141保持原直接启动方式，新18143使用独占个人目录，初始内容从18141逐字复制。回退时正常停止18143，可继续打开保留的18141；分别保留各目录后续的个人观察修改。既有18141的停止继续归原Owner，本工具不附着到旧PID。

App原安装、ZIP及摘要沿[前次发布](2026-11-02-observer-a84-market.md)。维护工具源码为f8d81ed；后续源码构建的安装包包含该工具。市场更新故障恢复、策略资金及模拟交易沿各自交付继续，不依赖观衡Web运行。
