# 观衡实际账户接入交付

类型：发布记录。日期：2026-11-02。范围：独立观衡读取 WT 实际账户发布，以及同一订单、成交和持仓的页面核对。

## 用户入口与职责

观衡版本为 `0.1.0a86+capital.1`，入口为 <http://127.0.0.1:18143/account>。委托和成交在 `/orders` 查看，策略在 `/strategies` 查看。观衡只读取 WT 发布结果；通信、账户查询和执行由独立 WT 管理。关闭观衡后，WT 继续运行。

当前维护配置为 `E:/workspace/wondertrader-data/observer-current/web-profile.json`，安装解释器、维护工具、配置摘要和进程身份记录在同目录 `DEPLOYMENT.json`。此配置与实际账户接入配置相同，别名建立时已核实维护工具可以识别原实例。

使用该收据中的 `python` 执行 `tool`，参数为 `status --profile <profile>`，即可查询观衡状态。`start`、`stop` 和 `restart` 使用相同参数；这些命令只管理观衡 Web。升级时先核对收据和目标实例，沿[独立观衡维护手册](../runbooks/observer-runtime.md)操作。

当前 Windows PowerShell 状态命令：

```powershell
$observerDeployment = Get-Content -LiteralPath 'E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json' -Raw | ConvertFrom-Json
& $observerDeployment.python -I -B $observerDeployment.tool status --profile $observerDeployment.profile
```

查询确认目标实例后，将同一命令中的 `status` 换为 `stop`、`start` 或 `restart`，执行对应维护动作。当前入口无需单独启动 QMT 通信程序。

## 实际验收结果

本轮已获用户授权的模拟账户经 WT 标准交易入口和 QMT 共享内存完成两次委托：一笔成交100份，另一笔成交0且全撤，合计一次撤单。原四只持仓保持，另有本轮成交产生的第五只持仓。账户的终端环境字段仍按实际返回保留；模拟资金资格来自本轮已确认的账户身份。

实际浏览器页面读取到5项持仓、2笔订单、1笔成交和1项账户资金。成交关联到原委托；已成交和已撤订单与实际查询相符，页面无控制台错误。本次页面验收调用券商接口、提交委托和撤单的次数均为0。

页面核对时，WT 持续账户发布为 `ready`，发布修订85，最近成功时间为 `2026-11-02T06:59:52.995502Z`，即北京时间14:59:52。该时间表达本轮取得的证据，后续运行状态通过当前维护入口核实。

受控验收材料位于 `E:/workspace/wondertrader-qa/root-actual-account-intake-20261102-001`：`CONNECTED-001.json`、`PAGE-VERIFIED-001.json`、`CURRENT-ALIAS-READY.json` 和实际页面截图。交易来源及持续 WT 身份由 `E:/workspace/wondertrader-qa/simulation-trade-20261102-001/ACCOUNT-PUBLICATION-HANDOFF-002.json` 登记。个人账户、原委托号和实际持仓明细保留在上述受控材料。

原观衡前代通过维护入口正常停止，退出码为0。此次接入沿用原个人观察目录，保持其内容摘要；独立行情服务18146、行情采集和市场更新组件继续保持各自生命周期。

## 继续开发的主路径

正式保留策略为共振市场状态 ETF 策略1.1.2。用户指定当前总资本100万元，包含现有持仓；正式策略的实际持仓初始化、报价估值和资金发布仍在接线。当前账户页展示券商全账户资金，正式策略资金展示需要独立策略发布提供实际数值。

下一步沿既有初始持仓接口和同一 WT owner 装配完成实际持仓、当前报价及策略资本接入，再验证策略页。已完成的模拟下单、成交和撤单证据沿用。新增自动化测试、边界验证和代码评审按[主路径优先](../development/workflow.md#主路径优先)安排在整体功能主路径完成后；字段注释按[注释规范](../development/comments.md#结构体与字段)同步维护。

旧版观衡安装证据保留当时事实；本记录接续其实际账户绑定及维护配置。较长行情覆盖和局限沿[独立行情记录](2026-11-02-index-long-daily.md)维护。
