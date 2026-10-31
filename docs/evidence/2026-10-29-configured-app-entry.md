# 正式configured入口的App组合与原生异常

类型：开发验证记录。状态：pending-verification。范围：[EAM-R5](../specs/execution-app-management.md#eam-r5-固定业务策略入口)；完整模块C/M1继续in-progress，未发布。

## 实现及身份

App原部署仅选择原生exe，B已交固定configured Python入口尚未装配。父部署v2明确runtime=native或configured-python，v1保留原native合同；App沿B唯一配置类型选择原owner，沿既有一次启动/失败保留/总截止及关闭顺序。策略目录保持名称、简介和版本；没有增加页面参数或交易按钮、算法副本、金融账本或WT核心修改。

新普通Appa11 wheel SHA `adffa18836fff7e25f8c8939bb29bed82f21ea60572e9a40bdc259c197809595`，源码快照在build/configured-app-001/app-source，安装于同目录runtime-venv。uv.lock公包hash与六份固定私包独立安装，22发行pip check通过；Starlette沿C锁为1.9.0。生产SPA复用17项原件，ZIP SHA `4b25b58b1cfe93e2f96abbdc3c32939baae1faa7a4c7f999d17c2febc2577c3e`，逐文件核匹配，原件不变。

B固定configured交接SHA `98b1f02bc4664820add87bf89408165261f1f2c3c517c2780c0e31c91c1f1da2`，原21项原生安装及69项测试闭包在本轮独占目录重新冻结。当前execution_configured/execution_strategy与B交接一致；execution_process当前新增recovery_mode及条件closed字段，已记录差异；本轮配置无recovery，未授该新增恢复资格。原Runtime DLL SHA `73d3f64519f71360b12b3ec3cc8e0c856ae67d3caf9ddbda97d7183d6a4b3c04`。

## 实际结果与故障

每阶段沿原native.run隐藏Job、有限输出、单一总D及树/EOF/join运行；测试仅显式SDK/行情替身。生产App从普通site-packages导入；QA AppProxy只把冻结B夹具的start/close转交实际App，App内部实际owner为B原ManagedPythonExecutionProcess，未替换算法或交易回调。

- main-configured-001/002：正式子端、原CTA/Factory/Local/Adapter/WinSHM取得两策略各700，SDK一次净额买1400；后继原调度两策略sequence=2且converged，原本策略actual/sellable各700、pending空。生产SPA宽窄屏/只读状态/503隐藏和恢复通过，B RESULT/POSTFLIGHT正常关闭。外层QA误要求固定8查询、再误要求后继重复deal查询，均在业务结束后失败，保留失败原件，不将其授为完整外层main通过。
- 查询事实复核：启动前四类查询齐全且SDK调用0；委托后协议刷新account/order/position，deal由实时回报提供。周期刷新使实际查询次数随时序变化，QA已改核上述事实和原后继目标收敛。
- main-configured-003：同wheel/固定Runtime重复运行，启动及两策略首目标成功、SDK买1400后子进程访问冲突，原生退出码3221225477。原source/Host资源最终关闭，App标记shutdown_complete=false，执行owner为faulted/unexpected_exit、forced=false/pending=false；没有closed成功收据。后继查询等待在原100秒预算终止，外层非零退出。
- Windows Application Error 1000在2026-10-29 02:06:10记录本案pid68992（0x10d80），模块GuanhengCtaRuntime.dll、异常c0000005、RVA000000000009cce5。尚无该次原生栈/函数级根因，当前不能归因于App接线或授稳定运行资格。该案策略投影两项均sequence=1/buying；源码/原件保持。

本轮130后端回归通过，覆盖v1/v2分流、未知runtime/额外字段拒绝、默认零Job、原owner选择、部分构造/启动失败及关闭资源。原Host关闭回归曾因Windows计时粒度在join返回时距离D仍差5ms而误失败；该案改用可控owner时钟推进至收紧D之后，再释放受阻回收，原stop_timeout/保留及资源结论保持，未改生产监督者。

原native入口通过v2部署实跑兼容：新安装App/生产SPA A600+B400只提交一次SDK1000、四查询，App shutdown_complete及原Job/树/EOF/join/读池/HTTP资源全部通过，17.125秒。configured未知profile沿实际安装子端拒绝，App只降级执行能力，生产SPA正确显示失败、PID未知，目录仍可读；查询/SDK/原Runtime调用均0，13.172秒完成预期失败及全部资源收束。28前端回归通过，策略页仍无参数表单。

安装身份复核通过：64构建文件、62 App安装成员与wheel一致，22发行1967个RECORD摘要及本次17项SPA副本全部匹配。完整configured成功主链的稳定性仍缺证据，以上兼容/拒绝资格分别保留。

## 独立审查

规格与规范两名独立审查者对C接线full及后继身份/结果delta均确认无新增C层P级问题；最终44项清单SHA `9874cbb2a9e1c9d0d46bb91505e139ac371ca1041a806f6d505295f9c814d93d`零漂移。App默认/唯一owner/旧合同、native兼容、profile拒绝及安装资源证据分别complete。规格审查将configured运行期访问冲突登记为P1资格阻断，正常稳定主链gap、原生函数根因unknown；两次业务收敛仅作为旁证，未挪用为通过。恢复、真实来源严格时效和完整M1保持未覆盖。报告及未完成交接分别在本轮reviews.json和DELIVERY.json。

## 来源、限制及续接

A同值后继133交接SHA `e977326a6edbd86991117b718bc006a201c6de2ecca58dc4d991ccd274f449b9`的76项原件已逐字节准入，9ETF9271日线、401共同交易日/3609条保持；source-admission.json明确尚未消费进本轮策略。其OHLC/量纲和历史首次可知限制仍按[源资格](../modules/qmt-source-qualification.md)。严格核仍拒绝对应收盘之后才可知的历史行，真实日末模型须在唯一输入/算法owner契约中明确，保留实收身份。

同候选随后在不启动App/SPA的standalone-001复现访问冲突（pid68564、相同退出码），仅增加Python faulthandler与有限输出tee，原SDK结果仍为一次insert，查询4次。Windows同模块故障偏移9ccc0，时间02:11:32；两次事件已脱敏归档windows-faults.json。故障栈停在execution_strategy.py:333的原Runtime调用，Host/source全部关闭；原件与摘要归档NATIVE-FAULT.json。此对照证明App接线缺席时同候选也可触发，具体原生函数/根因仍缺该次C++栈，不能以历史成功轮次授稳定资格。

后继按原生故障边界处理，并由B与主集成者消费精确原件。C继续A新交付HPR5的公共App接线及其他可独立推进范围。实际来源M1、B原生稳定性、完整撤单/恢复、全部算法及统一升级回退未完成；本轮真实QMT操作、真实交易与生产切换均为0。
