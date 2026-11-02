# 观衡a86独立只读交付

类型：本机development版本部署记录。状态：已安装并运行；实际策略资金发布继续接入，正式生产发行单独登记。

## 使用入口与范围

打开 <http://127.0.0.1:18143/market?search=300308.SZ>。新版保留自选、默认60个交易日日线、简称/拼音/代码前缀自动下拉及既有市场观察/正式报告。策略页已接收WT的资金合同；当前来源尚未发布资金，页面保持待取得状态。账户当前展示旧发布及其原时间。

观衡只读App、独立WT行情18142与a85市场更新分别运行，观衡启停只管理本Web。安装、源码和实际验证身份沿[验收证据](../evidence/2026-11-02-observer-a86-capital-installed.md)。

## 当前维护命令

```powershell
$install = 'C:/Users/frangou/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Guanheng/observer/0.1.0a86+capital.1'
$python = "$install/runtime/app/venv/Scripts/python.exe"
$webTool = "$install/payload/observer-web.py"
$webProfile = 'E:/workspace/wondertrader-data/observer-controlled-web-20261102-a86-001/web-profile.json'
& $python -I -B $webTool status --profile $webProfile
# 需要停止、启动或同版重启时分别执行：
& $python -I -B $webTool stop --profile $webProfile
& $python -I -B $webTool start --profile $webProfile
& $python -I -B $webTool restart --profile $webProfile
```

当前控制身份为a49ec242-bb18-4e6d-a2a2-583d385aae64，配置摘要`69cfd6d33cc7a822bf0b4c48ef872f6ac95f7abbf06e8f5a23949a9325932a05`。每次维护使用原profile，结果未知时先查询原控制身份。

个人目录沿`E:/workspace/wondertrader-data/observer-controlled-web-20261102-a84-002/watchlist`；切换保留原文件，运行期间只有本实例占用该目录。私有读取配置沿新控制根的environment.private.json，维护命令仅传路径。日常操作沿[独立观衡手册](../runbooks/observer-runtime.md)。

## 回退

本次为读取字段及页面增量，未迁移业务数据格式。需要回退时先用以上命令正常停止a86，确认closed及Web/启动器退出，再用[原a84维护命令](2026-11-02-observer-a84-web-control.md)启动原profile。两代使用同一个人目录，按顺序切换。a86→a84完整回退本轮未执行；原a84正常停止及原安装保留已有证据。保留的18141仍可作为独立观察入口，其个人目录独立。

资金生产、最新账户发布和模拟下单/撤单验收分别继续。当前版本交付完成的是只读消费与界面，不授真实交易或完整恢复资格。
