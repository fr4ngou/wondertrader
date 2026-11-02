# 观衡a84市场观察与指数日线交付

状态：普通安装与本机读取验收通过。当前版本`0.1.0a84+market.1`，源码`737a0fe5857b10d09b22f0567a3dec4a78ca5ca8`。

## 使用入口

- 行情：<http://127.0.0.1:18141/market?search=300308.SZ>。
- 换手活跃度：<http://127.0.0.1:18141/observation?metric=turnover.gt5.ashare>，59个交易日。
- 盈利与回报：<http://127.0.0.1:18141/observation?metric=earnings.eps.ashare>，10期年报。

观衡、WT来源18142及市场更新角色独立运行。原18140与18136保留；新入口已接入50指数日线，沪深300、上证50原长历史保持。策略资金和模拟交易验收分别继续。

## 制品与当前事实

稳定交付目录`E:/workspace/wondertrader-qa/root-observer-a84-market-001`，ZIP为`observer-0.1.0a84+market.1-windows-x64.zip`；完整摘要、安装路径、业务current、正常停止/恢复和限制见[验收证据](../evidence/2026-11-02-observer-a84-market-installed.md)。

市场更新维护目录为`C:/Users/frangou/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Guanheng/observation-update/a84-market-20261102-001`。该目录`PREPARED.json`记录固定python和本角色配置，使用`python -I -B update_owner_control.py status|stop|start --profile live`。只操作这一角色，停止时核closed、父子均退出及监督者exit0，再启动下一代；不同时恢复旧a82角色。

WT启停沿[独立运行手册](../runbooks/wt-independent-runtime.md)，本次实际配置和控制身份位于`E:/workspace/wondertrader-data/index-daily-wt-20261102-runtime-001/DEPLOYMENT.json`。凭据留在其外部私有文件，不写入命令行。

## 升级和回退

安装沿[独立观衡手册](../runbooks/observer-runtime.md)，保持独立新目录和外部数据。新旧Web的个人目录各自独占；本次复制当前偏好，未移动原目录。当前后台Web仍是原CLI隐藏进程，正常停机控制尚未验收；需要维护时先按运行身份处理，不能把强杀称为正常关闭。

回退读取可继续使用已保留的18140及a82安装。需要回退更新程序时，先正常停止本a84更新角色，再沿a82-market原固定26来源配置恢复；原业务数据与窗口保留，角色不能同时运行。新配置的高管复核键只由新消费者读取，不复制进旧配置。回退范围是已验读取行为；新来源能力以支持该能力的安装为准。

本次公开刷新两个年报来源及T2108成功，高管网络超时保旧；其他来源权限、指数历史覆盖和后继新日产包按实际状态显示。模拟账户下撤单结果由交易验收单独交付。
