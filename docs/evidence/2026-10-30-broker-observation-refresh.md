# 等待期间券商资金与持仓自动补查

类型：模块B开发证据。状态：限定业务主链通过，完整模块继续。要求：[NRT-R23](../specs/native-realtime-strategy.md#nrt-r23-等待期间的券商pa刷新)；交付范围沿[模块B](../migration/module-b-delivery.md)和[三会话计划](../migration/parallel-system-delivery.md)。全部新增隔离环境、临时文件、缓存与制品写入E盘，C盘仅执行已安装工具。

## 根因与实现

旧正式宿主在初始四查询及订单/回报之外，没有等待期间的资金、持仓查询触发。`build/ms-retained-binding-001/cash-red-001`使用唯一正式1.1.2、真实冻结3208行日线、原Factory/CTA/NSQ/执行器及WinSHM运输；券商替身初始available0，原目标已形成且SDK0。来源改为120000后，业务观察8秒仍只有初始四查询，实际新增SDK0。最终关闭另有O/P两次查询，不能把最终六次误写成业务窗口六次。

自有标准插件增加显式根配置`observation_refresh`，沿原owner的pump/wait、任务队列、原Query/Resolve身份与SPI交付依次补查资金、持仓。每轮完成后计时间隔，完整成交查询沿原触发路径。默认关闭；新Runtime核插件版本能力后才创建API。原WT金融账本、理论持仓、净额汇总、费用、回报和线程模型保持既有实现，本次新增WT源码修改0。独立审查发现的trader非对象字段访问已改为先检类型，再访问字段。

## 固定输入与安装

原件根`build/ms-observation-refresh-001`。`native-002/BUILD.json` SHA `950c101d9e7fe3010d16951756f50676b6c975e50a31626c8a1d9d531cd22a16`；Runtime DLL SHA `68d7c415837556ff7c3e2d180250dfb1e98c4d3051a0fd4133a9e4f5a3f1d86f`，Host exe SHA `08a7d5dbceb71e7eea86ee29df0c30ff7e7281f330da7056f132ca4d05435da5`。原WtExeFact和其他WT制品沿冻结基线。native001为审查修正前成功编译快照，最终行为资格使用002。

`INSTALLATION-001.json` SHA `5179d621aa495f82c67f63b74332068b3764b614ccb9717895ab0fbc15a98163`：普通新环境六发行/721条hashed RECORD，V1包0.1.0a7，正式业务规则1.1.2；无观衡/Web。公共WTRuntime采用前版冻结A源码，仅覆盖B自有五模块，全部安装Python源与冻结源匹配。真实原价/分析窗口来自A `build/qmt-native-adjustment-module-001/main006/ANALYSIS-WINDOW.json`，SHA `a38386d74bda91da91cc9669ffde734cb69ba50f4d06427fe27038e0ff857859`；账户、行情tick、撮合与SDK明确为隔离替身。

## 实际主链与边界

| 验收及原件 | 实际观察 | 资格 |
|---|---|---|
| R23-C1，cash-green001 | 正式独立WRI→原CTA/唯一1.1.2：释放前SDK0；自动A/P查询后available120000、账户修订8，四次SDK替身买入、四周期及converged；后继实际P为4000/9100/16400/20900份 | 业务主链通过；关闭捕获c0005、root2，完整运行失败 |
| R23-C2，cash-slow003 | P/A各延迟600ms，QPC实测最小600.2581ms；资金释放前五轮A/P依次返回，下一轮从上一P完成后至少1000ms发起；释放后四次SDK、四周期、converged | 慢查询业务通过；最终48查询、关闭c0005/root2 |
| R23-C2，cash-slow004 | 同候选再消费本次冻结的Host/Agent源码及QA，逐文件SOURCES摘要；慢查询与释放后四买入/四周期/收敛再次通过 | 补强输入溯源；完整关闭仍失败，具体异常沿同次摘要 |
| R23-C2，default-off001 | 同版DLL、安装和真实历史输入，根配置无刷新字段；四次SDK/四周期、29次原查询，策略收敛、root0、原closed.v2/clean.v2及完整回收 | 原默认路径及单代完整关闭通过 |
| R23-C2，admission003 | 16案：trader的null/数组/字符串/bool、九种非法刷新对象/区间、内部保留字段、旧Runtime未知根字段、新Runtime配旧插件 | 原生受控exit1；前15案configuration阶段且状态根未创建，旧插件在trader阶段/API创建前拒绝；Python对其负责的九案前置拒绝 |
| R23-C3，c-abi001 | 安装C头/导入库与实际DLL，原P/A、成交ABI1及V2的布局/容量/Unavailable | 六个编译/链接/运行进程exit0，Job归零、EOF/join/资源关闭 |

cash-green001及slow003分别保留同次debugger附加、异常事件、转储身份、detach/join；本记录不将本次异常根因等同历史现场。两次Host/来源/server/proxy六项清理均true；外部Job回收与原生正常关闭分别登记。策略数量来自原WT及券商P，成交观察只提供周期身份和时间，补查不建立金融账本。

## 失败尝试与剩余

admission001错误地把直接exe受控失败码1断言成外层Runtime码2；002更换插件后未重写安装摘要，停于原安装身份校验。003修正QA后通过16案，失败原件保持。slow001使用GetTickCount64，slow002换monotonic_ns仍沿同一时钟，出现593至610ms量化值；`CLOCK-INFO.log`实际证明本QA Python的monotonic分辨率15.625ms、perf_counter为QPC/100ns。003以QPC测量替身等待，产品原截止时钟保持。

sellable-release001初始两轮waiting_sellable、理论有效100/总量200及SDK0正确。夹具随后直接从日内跳到次日早盘，没有形成后继策略调度，等待期间达到QA的40次查询容量并失败，SDK0；该尝试未取得跨日验收，当前QA已移除其直接跳日分支。后续应沿正式交易会话及正常停止/恢复验证次日可卖，不能用行情日期跳变代替会话生命周期，也不据此次尝试提出WT线程修改。

R23整体仍有可卖恢复、满队列/来源错误、启用刷新后的稳定正常两代及统一组合缺口；模块B完整BT/RT全周期、动态真实输入、异常/未知责任恢复和统一候选继续。真实账户下撤单、生产切换与新增框架行为均未执行。

原先运行的QA副本已冻结，Host/Agent直接读当时工作树，其构建时源码身份没有完整收据；旧证据保留该溯源边界。slow004把两方通信Python源码复制到本次夹具根后再导入，逐文件原件/副本摘要进入SOURCES，来源并行开发不会改变这份运行输入。

独立审查、文件SHA、普通安装与开发包身份沿该根的`REVIEW-001.json`、`REVIEW-002.json`、`DELIVERY-001.json`、`FINAL-POSTFLIGHT-001.json`核对；只授予各记录中的范围。公开归档排除通信私有配置、完整POSTFLIGHT和内存转储，保留允许输出的事实摘要及其原件SHA。
