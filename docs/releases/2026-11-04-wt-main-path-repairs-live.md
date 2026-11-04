# WT交易主路径修正现场采用

类型：模拟账户部署及业务观察记录。日期：2026-11-04。状态：修正版已加载、账户及页面恢复；自然完整调仓、买入成交及正常停止仍待验真。

## 当前采用

服务版本`0.1.0a12+integrated.2.market.35.3.service.8`，控制代`713edbdb-6fd0-4f9a-856d-a6141999eea9`，逻辑实例保持`a309716d-1288-4328-ac57-abd6ef0bb2e9`。WRI PID15980，Native PID27616，Native控制代`f961e838-f6d1-4f6d-b636-073ed4b1ce4a`。启动/停止快捷方式均已指向本代服务配置。

自有修正包括[价格转换](../evidence/2026-11-04-qmt-price-encoding.md)、[买入组费用输入](../evidence/2026-11-04-wt-buy-fee-input.md)、[交易认证代际接续](../evidence/2026-11-04-qmt-trade-generation-stop.md)及[Host回复等待](../evidence/2026-11-04-qmt-host-reply-wait.md)。最终Standard DLL SHA为`e9a049ed256cc5eea7ebe645a616d0ef266b1ea734c1f6f2f8f917d50169519c`；实际进程模块路径已核。没有新增WT框架修改。

## 现场原件与业务结果

QA固定目录为`E:/workspace/wondertrader-qa/daily-mainline-20261103-001`。TRADE-REPAIRS-PREPARED/START、FORMAL-CURRENT、TRADE-REPAIRS-SHORTCUTS分别绑定交接、实际启动、部署及入口；前代金融文件和原Source保持，初始100万元含持仓基准SHA未变。

本轮16条通信命令中14条已由原事件token与券商完整订单/成交查询逐笔核清，累计卖出13100份。510050剩20500份，510300为0；其余三项库存保持。第9、16条价格尾差导致的失败均明确sdk_entered=false，不是未知委托，没有重复提交旧命令。

新代账户完成新四查询，预算净值997607.40元、实际持仓原价市值327525.90元、策略余额及可用670081.50元；数值来源时点分别保留。午间初始化已恢复原状态sequence154，等待首轮策略计算，未将监听ready解释为已完成调仓。Playwright使用既有Edge实际刷新策略/持仓/系统状态页，CAPITAL-LIVE-UI记录三页无前端错误，WT状态ready且策略资金可读；页面为独立观衡18143。

## 本次前代故障

前代d0618d71的账户Host于12:21附近退出；真实收据runtime_failed/runtime_closed=false，首个Timeout具体阶段尚未证明，退役runtime_close在原3秒预算内未完成。WRI执行器随后stop_timeout，实际由进程Job回收。Root核实五个原PID均已退出，使用既有record_execution_process_loss记录原Native物理退出；原pending失败原件保留，没有补写正常关闭证明。

针对账户角色的两项实现缺口已有独立回放候选：原2秒等待覆盖不了合法2.5秒SDK调用，以及已完成的持久化Timeout Future在close重复抛出后无法核清已落盘终态。候选仍在独立采用核验，不把候选机制直接宣称为本次唯一首因。当前账户角色已重启恢复，完整长期修复另随新角色采用记录。

## 剩余

下午自然行情中的完整卖买调仓、实际取消及正常关闭恢复继续验真。资料v9与完整v5正文、全市场日线同owner自动维护和永久源码闭包继续；当前角色、数据、原始证据及未合入成果保持，不进入最终清理。整体目标active。
