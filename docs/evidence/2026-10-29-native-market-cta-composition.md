# 安装行情插件与真实分钟进入正式CTA宿主

类型：隔离组合验证记录。结果：pass（所列混合输入主链）；完整模块B及全真实策略资格继续pending-verification。关联[NRT-R14](../specs/native-realtime-strategy.md#nrt-r14-安装行情插件与原生分钟的正式宿主组合)、[模块B](../migration/module-b-delivery.md)及M1。

## 输入身份与职责

原安装的ManagedPythonExecutionProcess → GuanhengCtaRuntime → CtaExecutionSession → 原Factory/ticker/Local/Adapter → WinSHM SDK替身保持。WT-D05/S01/S06由原生组件承接；本次只增加测试装配和数据核对，WT及生产源码修改0。用户决定停止框架多线程调查继续生效。

| 输入 | 固定身份及实际范围 |
|---|---|
| 分钟Reader | A的candidate-002安装DLL，SHA `f5f7efecf0648c425d4c7d85f217ea670be372c95465f07081564b5db30da122`；显式minute_native读取137/storage，保持唯一活动Writer |
| 行情Parser | A的final-install/ParserQMTHostV6.dll，SHA `2d422159b21647fa18feed0e3020c735033502e8bbf40bd346b9c53c7bf6c059`；本次接签名FullTickV6 HTTP替身 |
| 原Runtime | 交易规则BUILD003安装，SHA `241cdba18271b4c9a3800efdb97a2750b30326c571554fb3cf86125a5445ffcd`；既有批准覆盖保持，本次未重建 |
| Python及业务 | V2 BUILD005的普通非editable Python3.12/Appa10闭包；本次选择原configured a6/1.2.0及NSQ，两实例各50000元显式合成预算 |
| 日线/报价/账户 | 既有125日冻结合成d1、10.01报价、WinSHM SDK替身；这些输入的实际来源继续独立标识 |
| 原Helper | SHA `50a106a44d7dcaa1c60c0c4f1b766dce69bf1738c86f914d13a240f963986c0f`，仅读同一活动分钟文件 |

本次生产文件均保持原字节。新增QA为native_market.py，run.py显式选择组合模式；缺省旧路径保持。原始配置、运输及行情副本保存在独占build根，公开记录只给计数、摘要和时间标签。

## 主链与原件

固定根为`build/ms-native-minute-001`。最终主用例为main-004；其启动前输入/QA快照在main-004-input.json和test-source目录。最终数据身份补充为verification-001，保留实际Helper副本、列名、163行、读取区间及SHA，并绑定原callback trace。两次读取各自保留原件，补充核对不改写原主用例证据。

| 验收 | 实际观察 | 结论 |
|---|---|---|
| R14-C1正式入口 | 两策略初始化后，原自然13:40、13:41分钟调度调用唯一configured核；各目标700股，组合只买1400股一次，11查询后两个策略sequence2/converged | pass |
| R14-C2实际分钟 | 两个初始化副本及两个闭合分钟的两策略回调，共6份；原Helper后置读取163根，与原trace逐date/time/OHLC/volume/money精确相等 | pass；数据副本与trace均保留SHA |
| R14-C3完整停止 | 原closed ok/closed均true；父进程closed、pending/forced均false；Host/source/HTTP/proxy、双EOF、Reader/Parser及Job回收完成 | pass |
| FullTick替身 | 实际313次full_tick、628次binding读取，签名及v6原codec进入实际安装插件，HTTP主线程和请求线程均关闭 | pass；真实行情来源另验 |

main-004/RESULT.json SHA `d890b362423f54560a5f3c94f18ca956db8ba3210785d4c2181c90367709d7e4`；POSTFLIGHT SHA `6849eba9625794ddb400287000f6f26334ae660f109e2c9b416f0b82f2c77e85`。verification-001/native-market-proof.json SHA `07f27cc888ad566657ac07610c47d570d70ec87b9ee706a59b49a15b0c7d6115`。

原生及验证子进程沿native.run隐藏Job执行。测试观察器只复制原callback值，主周期由业务原init登记一次，未调用schedule或人工推进引擎时钟。夹具为自然分钟等待事先声明64条journal及相匹配字节额度、128条进度记录；业务算法与生产容量保持原配置。

## 修正、审查与限制

main-001：观察器重复请求主周期触发原桥拒绝；已改普通只读窗口。零请求时附加线程列表断言也已改沿stdlib server_close/join完成语义。main-002：原10条快速用例journal额度不足，已有一次替身买入，运行正常报告runtime失败并完成物理关闭；后继使用明确有界额度。main-003：业务、逐值分钟和原关闭成功，父测试保存超过2MiB原件时失败；后继复用既有POSTFLIGHT摘要逻辑，完整fixture原件保留。上述用例各保留失败状态，main-004通过结论只授本次最终输入。

独立审查按full组合范围核R14，原冻结组件按身份复用。发现一项P2为分钟副本缺少可复核输入摘要；后置只读验证已保存完整Helper副本并绑定trace，不启停或修改Writer。最终报告和交付摘要位于同根REVIEW-001.json及DELIVERY-001.json，审查与实际运行范围分别登记。

本次真实部分为活动分钟读取。全真实9证券日线/报价、历史available_at与单位准入、统一Appa18、跨日/重连、持续运行及真实交易继续后继验收；A独立Parser真实来源证据不自动授本组合实盘资格。现有冻结007及V2开发002未切换。完整模块B保持in-progress，未操作QMT界面、137/140启停、真实下撤单或生产发布。
