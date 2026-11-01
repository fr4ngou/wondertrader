# 日线来源的独立WT运行配置与正常关闭

类型：固定部署、独立运行和真实GET验收。日期：2026-11-02。状态：通过。

## 所有权与固定输入

本增量把已验日线组件交给原`guanheng_wt_runtime`的`history/source_market`固定工厂管理。WT实例只声明history组件；观衡只读取18136，不构造或关闭来源服务。WonderTrader框架修改、QMT/SHM调用、下单和撤单均为0。

部署根为`E:/workspace/wondertrader-data/daily-history-wt-20261102-001`。固定GuanhengMarket组件共191个文件，ZIP SHA-256为`c1744c26ede827ad48b9eb897e38600bb92df1f7574411e870613828903ab5f2`；全量日仓收据SHA-256为`9e2171c224abbf6e2e6336cc66825b6169de954a782f44a2eeb6b36a957ee2f7`。

固定配置摘要：

- source配置：`3758c450cee2c15e228b79612e4b34e63382db84b4f5452905030d3937862857`
- source-market service配置：`7a061a265a23515d3a9bf6b8e55a1dd558840a7c720f7e39f9d78db43ea1290e`
- history descriptor：`ff457af8ccf7144c4d32c2cbebaa98962ebada61914f493d34009a7c7c1d8adb`
- WT runtime配置：`016c94cee73bdacd6f03fa8b3abc24e8de8f89c2c212efa6f4a747400235270d`

WT实例ID为`01c6e51d-09e4-4d73-8058-7abc4e6818b3`，控制ID为`59f53802-2216-4aa0-a3da-81ebce03c58e`，来源子控制ID为`3fe4ddd5-9ff1-4262-80ad-5403a7c68c97`。来源监听使用独立端口18136。

私有环境文件为`E:/workspace/wondertrader-data/daily-history-wt-20261102-001/private/environment.json`。文件在创建时应用当前用户独占DACL，`icacls`只列当前用户完全控制。令牌值只存在该文件，交接与证据不输出正文。

## 实际启动、GET与关闭

已安装WT解释器通过`python -I -B -m guanheng_wt_runtime`启动。ready与status确认WT PID 72068、history PID 22856、history组件ready，18136由该子进程监听。

临时只读App在18137读取该WT来源，实际执行：

`GET /v1/ui/market/chart/300308.SZ?period=1d&limit=5`

HTTP 200，schema1.6，period/source_period均为1d，source_bar_count和candles均为5；响应SHA-256为`6fc740a5b7bd7365ae3aa3b1dcb3807ca4541584e7c440d876f52e4f5da0cecc`。GET收据文件SHA-256为`373844a51c5594376314bbc64f0b128dc06911526d3fabe1c36ba5cf17350f26`。

随后沿`guanheng.wt-runtime-stop.v1`写入匹配控制身份。WT closed确认`components_closed=true`、error_code为空；最终status中history为closed、pending=false、forced=false。来源子closed确认server_closed/native_closed均为true。父运行进程退出码0，18136与临时18137均关闭；18120、18122、18123、18130、18132持续监听。

## 交付文件

无秘密的完整文件及摘要清单位于`E:/workspace/wondertrader-data/daily-history-wt-20261102-001/FINAL.json`，SHA-256为`9e5224d626630b0ec91e7abfd828beba2766b7f9bacc9a1fed0ca84b0bd98392`。准备清单`DEPLOYMENT.json`的SHA-256为`5149eade874e76a91952975ec64367ffe0b9eee2a2bff91414f2f28bb9cc3832`。

Root后续启动同一配置时读取私有环境文件，将`GUANHENG_DAILY_HISTORY_TOKEN`注入WT进程；新UI读取同文件内的GUANHENG_MARKET及GUANHENG_WT定位字段。观衡继续保持只读消费者职责。
