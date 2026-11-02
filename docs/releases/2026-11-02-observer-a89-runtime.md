# 观衡a89独立交付

类型：部署及实际页面记录。日期：2026-11-02。状态：观衡已独立上线；WT账户/策略实例恢复继续。

## 使用与维护

打开 <http://127.0.0.1:18143/strategies>，当前版本为`0.1.0a89+runtime.2`。个人观察和独立WT行情连接保持。前代Web及启动器正常退出，退出码均为0；本次只启停观衡，未操作QMT、WT、行情采集或市场更新组件。

稳定维护入口是`E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json`，保存当前解释器、工具、profile及实例身份。状态命令如下；核对目标后将status替换为start、stop或restart执行观衡维护。

```powershell
$observerDeployment = Get-Content -LiteralPath 'E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json' -Raw | ConvertFrom-Json
& $observerDeployment.python -I -B $observerDeployment.tool status --profile $observerDeployment.profile
```

本代实体profile为`E:/workspace/wondertrader-data/observer-controlled-web-20261102-a89-runtime-001/web-profile.json`，SHA256为`ed7402c18177b2ae031cd16c6379e2f7d18c0855e307a7e75a6f02ad56ba53cf`。Web PID47892，启动器33364，control为`275affd1-8100-499d-9d9c-cf68335381ed`。安装目录是`C:/Users/frangou/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Guanheng/observer/0.1.0a89+runtime.2`。

前代a87安装及实体配置`E:/workspace/wondertrader-data/observer-controlled-web-20261102-a87-capital-003/web-profile.json`保留。需要回退时先用当前工具和当前profile正常停止，确认关闭后，以a87安装的`payload/observer-web.py`和该实体profile启动；实际读取验真后再更新稳定入口。回退观衡与恢复WT分别操作，本轮未执行回退。

## 功能与实际页面

策略总资产按WT原发布显示100万元，包含已有库存；持仓市值366,924.80元、现金余额633,075.20元、本次运行盈亏0元。估值来源时间仍为北京时间17:07:24。账户保留5项持仓、2笔委托、1笔成交及1项资金结果；账户全额资金继续独立展示。当前5项包含模拟成交产生的510300持仓，其可卖为0，原四项持仓保持。

首次初始化资金尚无decision_at，页面沿策略原状态显示等待所需行情；只有取得实际决策时间后才显示已发布计算结果。自有执行器新增可选生命周期回执，App已支持沿同代执行引用读取实际开始、停止和运行时长；Native候选已编译，当前旧实例尚无回执，页面保持未知，资金基准和文件时间分别解释。字段契约见[详情模块](../modules/observer-strategy-details.md)。

Root接收时resume6实例已于北京时间18:00:27进入faulted。开发者2从本次诊断确定QMT读取通道返回`503 / strategy_stale`，心跳中断触发原因和接续继续由运行侧处理。该事实只适用于本次退出；此前只保留原因摘要的旧故障仍缺精确状态证据。

新版正确显示策略运行失败，保留原资产、现金、市值与来源时间，取消当前可用资金资格。系统状态分别显示账户WT失败，以及仍可响应的独立行情/历史WT；观衡上线不授予策略持续运行或自动交易资格。实际桌面和390px页面已核对，移动端无横向溢出，浏览器无脚本或控制台错误。

搜索、自选五日图、默认60交易日日线及周/月窗口、市场观察和报告入口的源码保持，沿[前代主路径记录](2026-11-02-observer-actual-account.md)和本轮受控`MAINPATH-VERIFIED-001.json`复用有效证据。较长指数覆盖及缺口沿[指数交付记录](2026-11-02-index-long-daily.md)；当前覆盖限定于实际来源，未用空白或推测值填补。

## 源码、制品与证据

- `2839754f4c2612953f9f954efe4aa4d686612dee`合入已实际运行的首次资金发布、同进程账户约束刷新及受限HTTP诊断；三份Python文件与开发者2冻结006候选逐字节匹配。HTTP诊断源码仅恢复仓库原LF格式，语句与已验候选一致。
- `d4bd0e53455c4fa9959ee012e3813fb2f3108d9e`增加自有执行器生命周期事实、App只读消费及版本元数据。新增WT框架改动为0，原ready/closed协议及Python金融状态身份保持。
- 独立ZIP：`C:/Users/frangou/AppData/Local/Temp/root-observer-a89-runtime-build-001/observer-0.1.0a89+runtime.2-windows-x64.zip`，SHA256为`0625f2e4d7638cdad319df246e1b6bc756bbeee532d7be94c287119f28d274de`。
- 包清单SHA256：`f0bc5374c786c3e549468dbfce0654e630eb12f3da4f2b90a2a0161e76aaae5e`；普通离线安装收据SHA256：`c4a205aeee4cc94b4c5239f41acb792dbf9fbc772c34d5d4fc304731cc6fdcf7`。
- 实际验收：`E:/workspace/wondertrader-qa/root-observer-a89-runtime-20261102-001/ACTUAL-DEPLOYMENT-001.json`、`PAGE-VERIFIED-001.json`、桌面/手机截图和原Web关闭回执。
- 运行来源：`E:/workspace/wondertrader-qa/strategy-capital-handoff-20261102-001/CAPITAL-ACTUAL-HANDOFF-006.json`；Native生命周期候选：`E:/workspace/wondertrader-qa/root-native-lifecycle-20261102-001/BUILD.json`。

本轮未新增自动化测试；实际入口验收和普通构建/依赖检查已执行。新增测试、异常扩展及评审沿[主路径优先](../development/workflow.md#主路径优先)后续安排。接收后继WT身份、核实际启动回执和持续资金更新仍待完成；保持现有资金基准及恢复状态，不重复模拟下撤单。
