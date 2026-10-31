# 模块B原生交易结果与同核回测核验

类型：隔离开发证据。日期：2026-10-29。状态：STQ-P19-O1/O2限定验收通过；完整模块B为in-progress。关联：[模块B](../migration/module-b-delivery.md)、[STQ规格](../specs/native-qmt-standard-trader.md)及[已冻结业务桥](2026-10-28-managed-cta-business-kernel.md)。

## 固定输入与实际路径

本轮交易结果链继续消费`build/ms-business-001/install`中原GuanhengCtaHost、Standard交易插件、原Local/MinImpact执行器和Adapter，经原WinSHM运输连接明确的合成券商SDK。产品原生工件与`DELIVERY-002.json.native_install`逐文件核验；新增代码限专用测试与文档。本轮新增WT核心行为、真实券商调用和金融账本均为0。

测试策略`tests/integration/qmt_cta_product/strategy.cpp`保留原标准Factory；显式配置followup_target_file时，下一次原主K线调度读取测试目标。没有直接调用调度或撤单接口。实际加载DLL为`build/ms-outcomes-001/fixtures-002/InstalledSynthetic.dll`，SHA256为`e2c27d4626412bc3e02befa5df842f523402d673c18f87fb9a32ee8233e6fe7d`；源文件SHA256为`c94c5b340ca92f1abe5ef37e5064d106decfe86d3a7cf31329c65c89c9244afd`，编译来源在同目录BUILD.json。

Python使用已冻结普通runtime-001的3.12.14环境、Appa6薄宿主安装；本组合复用旧corea5/NSQa1。它覆盖下述原生结果链，当前声明依赖的完整新版本组合继续单独验收。

## 账户查询、迟到成交与终态后继续

| 验收 | 实际观察 | 最终原件 |
|---|---|---|
| STQ-P19-O1 | A600+B400原生净额买1000；先发成交400回报，等待券商查询返回持仓1000及订单全部成交后，再发迟到600及相同TradeID重复回报。来源确认到4后，下一次原生调度A800+B400，实际仅补买200；最终券商查询1200、确认到6，16次查询、2次insert、0次cancel | `build/ms-outcomes-001/filled-late-006/{RESULT,POSTFLIGHT,execution-outcome-proof,fixture}.json` |
| STQ-P19-O2 | 原买1000部成500，MinImpact按原1秒超时实际撤余500并重新买500；持仓查询1000后收到首单迟到100及相同TradeID重复回报。来源确认到8后，下一次调度同样只补买200；最终查询1200、确认到10，27次查询、3次insert、1次cancel | `build/ms-outcomes-001/partial-cancel-replace-005/{RESULT,POSTFLIGHT,execution-outcome-proof,fixture}.json` |

两案RESULT均passed、进程正常closed且forced=false；POSTFLIGHT保留原查询、SDK调用、来源确认、宿主资源、进程回收、双管道EOF/join和运输线程关闭证据，first_error及proxy_first_error为空。各策略原文件最终为A800/B400，账户事实仍来自合成券商独立查询。迟到成交没有形成重复仓位或额外委托。

长链原始fixture完整保留；`guanheng.cta-outcome-postflight.v1`将五组重复运输明细投影为记录数与canonical SHA，并绑定完整fixture的字节数/SHA/路径，原证据文件大小上限保持。早期失败尝试保留在同根对应编号，未授通过资格。

连续行情使用递增时间，按原分钟闭合自然计算。人为回调交错实验的观察变化不再构成冻结行情或修改调度的要求；[串行提案已撤回](../migration/native-cta-event-serialization-proposal.md)。

## 原生BT与实时同一业务核

`build/ms-bt-compare-003`实际执行已安装StrategyHost→隔离原Runner→StrategyBacktestSession→原WtBtPorter，并绑定`build/ms-python-003/public-business-forward-001`已通过实时主链。两侧复用同一安装corea5/NSQa1，9证券×125闭合日合成输入逐字段比较，完整17项算法输出字段一致，包含input_sha256；共同输入摘要为`aef97250042982041f8eb2219b6a159f6f0e39b38190a5bb12c128a378307a3c`。

BT实际124次计算、1116次bar回调，原trades.csv按10元先买400再买300，终态原仓位/可卖700、费用0、净值50000、现金43000。RT以新实例对同一已闭合历史计算，A/B各目标700，原执行器按tick10.01净额买1400。知识截止分别为2026-10-27收盘与2026-10-29 10:01，单独记录；成交时序、价格及两实例合计收益未授相同资格。

BT的HOST为completed/exit0/reaped/pipes_joined、forced=false。最终文件SHA256：INPUTS.json为`9947bb9fcc43fabb63a0cce3dabb1e6c20e4b86eef4c1d547682fd492d8bebef`，HOST.json为`4e3853ce0a02fab8bba3c37a2bab9fbcc2f8195067c4fbe25b11af19a7403619`，COMPARISON.json为`5ab2d6953c91ccf940268710986fcb75db0d10583d0057fb799b6dea4f8f33fb`。

## 身份、审查与未覆盖范围

本轮专用源码、原生安装和实际证据身份汇总于`build/ms-outcomes-001/DELIVERY.json`，独立审查见同根REVIEW。源码和原件按独占目录冻结，旧P19/P20制品保持原身份。静态项目检查只证明本地文档完整性。

全撤、撤单拒绝、未知提交及完整跨进程恢复仍待正式入口验收。正常恢复先核WT已有文件的保存/加载及自有准入；[新增保存入口的必要性仍待验证](../migration/native-clean-state-flush-proposal.md)，当前审批请求已撤回。资金/T+1/实际费用、所有保留算法、实际来源单位/时间资格、正式配置驱动Python业务子进程、当前完整依赖安装及模块统一发行继续in-progress。两案和BT比较均使用合成数据/隔离券商；未操作QMT界面、执行真实下撤单或发布。
