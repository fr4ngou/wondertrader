# 原成交观察与唯一策略新周期来源

类型：模块B开发证据。状态：NRT-R21/R22限定主链通过，完整模块及两代恢复继续pending-verification。新增源码、环境、TEMP/TMP、安装缓存和原件均在E盘；真实交易及现场常驻实例操作0，新增WT核心修改0。

## 实现与来源

[NRT-R21/R22](../specs/native-realtime-strategy.md#nrt-r21-原成交事实只读观察)复用原StandardQmtTrader映射、SPI、Adapter和Local。只读成交投影复制原编号、证券、user_tag、源日期时间、方向、数量、价格和金额，接收时间单列。数量、资金、成本、绩效及金融通知保持原owner，接口读取不新增交易或查询。

初版用实时回报到达序号建立零仓锚点，旧查询成交晚到时可能被误归新周期。正式方法回归已在冻结旧源复现；修正用本实例原Local正常返回的有效OrderIDs建立提交序号，沿原on_trade(localid,...)关联当前原成交，查询及回报只能匹配身份。原NSQ已有正开仓目标时保留锚点，无开仓目标的新flat P刷新，旧周期归零重建下界。容量及身份冲突降来源资格unknown，原提交返回保持。

P/A及成交ABI1保留；可选trades_v2_read及layout(3/4)在同一不可变快照中附提交来源，缺能力或未证明归属时等待。自动周期入口限定用户确认的唯一1.1.2策略，不分摊多策略成交。数量始终取券商P，买入成交只提供周期起点及出处。

## 固定输入与验收

原件根相对仓库：`build/ms-broker-trades-001`（下称BT）、`build/ms-actual-opening-001`（下称AO）。

- BT/native-005/BUILD.json SHA256 `8c8fb71bec25c1c0dbbadae5c4eff0278ece3fa244300ff310d3adf9b8602bea`；运行DLL `b3d103b7338ef887a9ce3465ef8fa0019b122cd973e2afa156158f24ce178f8f`。九个自有源文件、安装文件、链接输入均存证，安装C++头编译通过；WtExeFact保持冻结原件。
- AO/INSTALLATION-002.json SHA256 `33266ba0792ba661561e378a7b941343706f8bab81b7739727bb8bd48087681b`。六发行、720条hashed RECORD，冻结source-002/wheels-002与安装源码一致，无观衡/Web依赖；策略发行固定a6，最新发行重绑定另验。
- A真实原价/分析日线3208行、八证券，窗口SHA256 `a38386d74bda91da91cc9669ffde734cb69ba50f4d06427fe27038e0ff857859`；C固定输入。flat、盘口/tick、账户和执行均为隔离替身，真实券商调用0。

| 要求 | 原件 | 实际范围 |
| --- | --- | --- |
| R21-C1 原值 | BT/main001/TRADE-OBSERVATION-001.json；AO/main006/ACTUAL-OPENINGS-001.json | 卖200原编号/时间/数量/价格/金额及四笔买入来源；旧卖出证据绑定当时native002 |
| R21-C2 生产者投影 | BT/trade-projection-003/RESULT.json及INPUTS.json | 安装实际Adapter公开查询/实时回调，九组覆盖重复合并、乱序源时间、查询保留已交付、读取零调用、空/未知、断连、累计容量、身份冲突及换日；API/SDK为替身。顶层及依赖helper先冻结并记SHA，再编译运行 |
| R21-C3 安装ABI | BT/c-abi-004/RESULT.json | 最终native005实际DLL/安装C头/导入库，旧P/A及trades1、v2布局/参数/Unavailable；六进程exit0且完整回收 |
| R22-C1 原生主链 | AO/main006/RESULT.json、MAIN-INPUTS-006.json | 普通安装包内WRI CLI→原Factory/CTA→1.1.2/NSQ→原股票单元→WinSHM→SDK替身；四买入、29查询、四周期、sequence2/converged，原KV保存四周期 |
| R22-C2 归属 | AO/source-regression-003/RESULT.json | 冻结旧源red、普通安装14项green；旧query晚live、同秒原单、部分成交/更早回报、foreign/query-only/缺能力、flat刷新及待买锚点 |
| 来源投影边界 | BT/origin-boundary-001/RESULT.json | 安装C++实现六边界：空/无效ID不发布、有效序号单调、容量unknown保持ID、重复身份unknown；无金融SPI，不替代主链 |
| 单次完整关闭 | AO/MAIN-OUTER-CLOSE-006.json、main006原closed.json及.cta-clean.json、POSTFLIGHT.json | WRI root0、执行closed.v2/clean.v2，外层Job清零/EOF/join/资源关闭，Host/源/服务器六项回收成立；调试器无异常且detach/join |
| R22-C3 两代 | AO/main007/POSTFLIGHT.json、同次debug原件 | 首代四周期业务通过，关闭AV，第二代未执行；c0000005，栈slot0候选WtExeFact+0x1baff，属于栈候选；外层root1且Job清零/完整回收 |

main006实际P：510500.SH 4000、512100.SH 9100、515080.SH 16400、589000.SH 20900，可卖均0。四项opened_at逐一等于源成交日/HHMMSSmmm转换的UTC时间，origin为原提交1..4，数量逐一等于P，SDK替身调用保持4。

main003/004同次runtime诊断plugin_error=5（Timeout），源和代理无自身错误；四SDK返回、16查询、8回报。main004原页含6事件，整页身份/补充查询共用request_ms=8000。main005保持native004/安装002，仅把原整页预算配置为30000后业务通过，但关闭失败；main006相同预算换最终native005完整通过。HTTP单次8000、源执行预算和原超时终结语义保持。该对照支持当前四开仓场景，不构成所有规模延迟保证。

## 审查与缺口

AO/REVIEW-001保留初版P1。REVIEW-002 SHA256 `76cdc17054c0d2606a94f2d9ad50ad9144ae414e5fedc2ee117dcbc534135d14`关闭来源、空ID发布和规格问题。REVIEW-003 SHA256 `d624ad7bd47dac1ccab972f20954c07aa05f9edf523e45c1e77cc5ebea875759`核验最终native005单次业务及正常关闭、窄边界与两代失败。REVIEW-004 SHA256 `b4200970d6c5183615b5e6187eb4b1a8c14bf6fb37ebc97d9aed8473342a77b3`核验生产者002，指出helper缺构建时摘要；003已对同一源提前冻结、记摘要并重跑通过，旧运行边界保留。最终文件SHA、命令、包及清理摘要沿AO/DELIVERY-001登记。

生产者回调探针验证本层投影，没有替代真实SDK与Standard运输去重/恢复资格。稳定两代恢复、完整周期BT/RT、最新C发行及观衡消费者重绑定、完整资金/T+1/费用和最终组合继续。[股票停止最小提案](../migration/native-stock-metadata-ownership-proposal.md)保持未实施。当前不授真实交易、生产切换或完整模块完成资格。
