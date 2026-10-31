# QMT标准账户批次与WT委托关联验证

类型：开发验证。日期：2026-10-24。范围：STQ-P7，自有账户mapper、原委托lookup及有限身份覆盖。状态：本切片通过；标准TraderQMT Factory、SPI投递与恢复交接继续开发。

## 根因与实现

账户原始字段运输完成后，标准交易接入仍需将原始备注中的完整token与WT原委托关联。唯一金融mapper会合并重复金融行，原输入行与输出对象数量可能不同。AccountBatch现由同一mapper的原去重分支给出source_to_output，每个原行对应最终WTS数组下标；金融判断、对象顺序及旧version2/3金融views保持。覆盖层按这份关系先核重复行的原身份字段，避免按行号错贴管理身份或静默丢掉冲突。

新增QmtAccountIdentity沿原SignedHttpDeadline，调用显式v4/account2.0的共用metadata入口和唯一金融mapper。每完整token最多lookup一次，保留有限原回复和派生诊断；源字段的缺失/null/空串/整数/浮点/bool分别核实。OrderRef只保留诊断，不作为关联token。

QmtHostTradeClient在原lookup唯一校验处暴露私有reference的只读事实，完整proof或关联错误须有原dispatch记录。采用身份前再次prepare，核当前Host绑定和会话与账户原结果及首次准备一致；所有查询、转换、lookup和最终检查使用同一个原D。

owned逐项核完整token、账户、证券、原委托和broker proof，再写Order.EntrustID/UserTag或Trade.UserTag。external和unresolved保留真实金融批次，管理身份为空并说明原因；不增加整批Pending、额外审批或四查询原子门。冲突、运输失败、预算或原D失败释放整个数组。真实OrderID、TradeID、RefOrder和金融值保持原mapper输出；成交诊断的entrust_id为空，原insert仍保留在lookup原回复中。

## 实际运行

全部目录位于build/guanheng-workspace。实际券商SDK调用为零，测试复用WT数据对象头文件及自有mapper，不链接WtCore/WtRunner；本轮新增WT框架修改为零。

| 验证 | 实际结果与原件 |
|---|---|
| 最终原生构建 | qmt-account-identity-build-003/identity-build-result.json：Common、codec、真实SHM探针、故障DLL、新身份DLL及既有金融矩阵EXE六目标通过，输入无漂移。 |
| Python兼容回归 | qmt-account-identity-regression-001：529通过、32跳过，25.18秒。跳过的6个原生场景、11个故障方法、8个字段投影方法及7个身份方法均另由下列CTest执行。 |
| 六组原生CTest | qmt-account-identity-native-002：全部通过，45.57秒，源码快照无漂移。 |
| 新身份矩阵 | integration.qmt_account_identity：7方法、57场景通过。真实认证HTTP→AccountClient V4 POST/原receipt GET→唯一mapper→实际lookup/身份覆盖；覆盖owned、外部单、unresolved、重复对应/冲突、同token缓存、完整/坏404、409、账户/证券/broker冲突、历史proof、容量、原D及最终prepare切代/晚回。失败断言无部分数组，旧金融views与金融槽保持。 |
| 实际共享内存闭环 | integration.qmt_native_trade_client：7方法通过。account2.0场景沿真实C++、认证Host、通信SQLite、Win32 builtin-shm及原策略线程取得四查询，再调用实际身份覆盖。order/deal各含owned与external对象；原data字节SHA和标量原值保持，WT原EntrustID/UserTag及金融views核实。原下撤单替身各一次、三条回报/源ACK及关闭断言保持。 |
| 旧金融矩阵 | integration.qmt_account_financial_mapping：复用原currency_probe.cpp，version2/3×四类型×16币种/账户场景共128通过；原金融mapper、来源空币种和部署币种的不同职责保持。 |
| 旧协议与故障 | codec、11方法/27原故障场景和8方法/47原字段投影场景全部通过，包含完整409引用、V3/V4空币种及原D/receipt校验。 |
| 目标Python证据复用 | 当前66项Source/Host Python文件与上一段冻结摘要逐一匹配，未修改终端代码。复用167项目标3.6.8回归及91模块禁文件完整策略证据，原件qmt-trading-memory-projection-002；本轮不重复授予真实终端资格。核同记录见qmt-account-identity-final-001/PYTHON-EVIDENCE-REUSE.json。 |

最终交易探针SHA-256：c1cff517159f83f4737fac5d0d89cc6bbf601892d9dea4bdca5b2d850a8d06c5；故障DLL：f7f6a8170e716a36d42c08ff385360759ea7c0466b8ad39ed499b0d5ace4054e；新身份DLL：024e541c231fcee1fe9c7d98364c8eb7ce1d227218bfae3af2e9f31332b5af20。完整原件、首次失败、最终汇总及控制器分别保留，见qmt-account-identity-final-001。

运行由隐藏、有期限的控制器管理，进程在恢复执行前加入Windows Job；最终成功收据核进程树归零、管道EOF、读取线程join及资源关闭，无强制终止。DLL回调owner的drain由原生矩阵和真实SHM场景分别断言。

## 发现、修复与审查

首次构建发现测试目标缺src头文件根；静态审查同时发现夹具从公开profile读取不存在的私有binding_id。已分别补自有CMake include及固定可信测试配置，产品行为保持。原失败见qmt-account-identity-build-001。

首次五组CTest有两组失败，根因均为新lookup提前以Status非Ok拒绝完整HTTP业务回复。BoundedSignedHttp在EOF时将404/409分别映射为NotSupported/Conflict；完整EOF也可能在原D检查后转为Timeout。现lookup只允许Ok，或与本次404/409的signed_http_error(code)精确code+reason一致的业务状态进入正文准入，继续核完整EOF和原D。合法unknown_order的404可判为external，完整409仍保留原关联错误及引用；坏正文、断流与超时继续失败。原失败见qmt-account-identity-native-001，修复后六组重新通过。

独立full审查位于qmt-account-identity-review-001/NOTES.md与SOURCES.sha256.json，明确记录上述HTTP状态P2及最终修复，静态最终P1/P2=0；39项来源根逐项核同。审查者执行为零，动态结论来自本记录列明的实际运行。源码、运行及状态文档分别保存身份。

固定上游的线程/关闭调查另封存qmt-standard-trader-design-002：run返回前后、执行单元锁、Close通知、成交应用与checkSelfMatch顺序均按08b230dd快照核对。相应边界已补入[执行模块](../modules/execution.md)，后续标准插件沿自有owner推进，不据此擅改框架。

## 仍需完成

当前生产TraderQMT Factory仍返回旧ManagedTrader，标准委托/撤单入口固定拒绝；本切片尚未替换它。下一步接通标准ITraderApi/SPI及同owner pump，退出旧自有SignedCommand、production_trusted与CoherentBaseline前置；再验证回调重入、停止/join、独立安装和真实用户调用链。

事件消费与查询恢复仍缺来源共同水位和跨进程应用提交证明。历史proof可解释原身份，当前可撤由现客户端和Host另核；本轮不证明任意重启无重复应用。真实SDK新增字段的回显、实时CTA、历史覆盖、完整观衡业务入口及正式发行分别继续验收，整体目标active。
