# 固定原生股票查询映射调查

类型：源码调查证据。日期：2026-10-22。结论范围：普通现金股票/ETF的一次性、无执行器、无 push 的只读初始化。本文提供事实、推论与规格收敛建议，不授予实现通过、真实来源验真、持续恢复、交易或发布资格。

## 输入与方法

本次作为独立后台研究任务，按 research 技能使用固定原生源码与官方公开文档。原生源码仅通过本地 Git 对象 `08b230dd05facf6d650d949bfe51054115a2ecb1:<path>` 读取，行号取该对象全文；没有使用当前脏核心源码替代固定输入。没有读取新插件实现、开发过程、历史审查、账户、数据库或运行日志，没有运行测试、原生程序或真实 QMT 请求。

对照规格为 [native-qmt-readonly-bootstrap.md](../specs/native-qmt-readonly-bootstrap.md)，读取时状态 accepted，SHA-256 为 `5507f577aee6cbba9051bf868dca6e2e26ebdeaee652d85e3295c892df434749`。下文规格行号对应此版本；后续正式修订由规格 owner 承担。

固定输入清单直接保存在本文，未另建输入目录。下列 Git blob OID 通过 `git rev-parse <commit>:<path>` 复核：

| 固定路径 | Git blob OID |
|---|---|
| `src/TraderXTP/TraderXTP.cpp` | `b1fa0acc8402290ecaf6fd1d36639cc736262fa3` |
| `src/TraderOES/TraderOES.cpp` | `78cf22874acedef3e6a8c086a25cfa499634160e` |
| `src/TraderHuaX/TraderHuaX.cpp` | `2052f93738a51f55d517b2d89950c76c3a992a60` |
| `src/TraderATP/TraderATP.cpp` | `7611bd96ab16b45ee157eec2a15386f761748ec6` |
| `src/Includes/WTSTradeDef.hpp` | `13e88880c3b8b471a1a2eefdc855777079acdc13` |
| `src/Includes/ITraderApi.h` | `b3fb42abbba1f1302844ebccf4d1860555e823af` |
| `src/WtCore/TraderAdapter.cpp` | `bf00b139d63201127204247241eb9379cafcdbcf` |
| `src/WtCore/ITrdNotifySink.h` | `d67528c4d4524017746de5045bfd2bae5028cb88` |
| `src/API/XTP2.2.32.2/xoms_api_struct.h` | `04343b88db91fa9c5e9d172af43dd48dafca76e1` |

官方网页在 2026-10-22 05:58–06:00（Asia/Shanghai，UTC+08:00）重新检索；该时间是本次检索时间，不代表文档发布日期或当前部署版本。网页行号为本次浏览文本定位，长期定位以页面名称、结构名称及字段名为准：

- [迅投：内置 Python 数据结构][qmt-data]，Account 315–348、Position 460–497。
- [迅投：XtQuant.Xttrade 交易模块][qmt-xt]，XtAsset 528–537、XtPosition 577–592。XtQuant 是另一套公开 API，不能据此证明现有内置 Python HTTP 投影已经输出相同字段。

## 已核源码事实

### 股票插件查询投影

固定类型名为 `WTSPositionItem`。各插件通过 `ITraderSpi::onRspPosition(const WTSArray*)` 和 `onRspAccount(WTSArray*)` 交付对象；接口本身没有另设今昨冻结明细查询。[接口 145–150][api]

| 原生插件、固定行号 | 数量与可卖映射 | 成本相关槽 |
|---|---|---|
| XTP `472–535`，关键 `505–515` | `pre=yesterday_position`；`new=total_qty-yesterday_position`；`availPre=sellable_qty`；`availNew=0` | `avgPrice=avg_price`；`positionCost=margin=total_qty*avg_price`；`dynProfit=0`。[XTP][xtp] |
| HuaX `242–268` | `pre=HistoryPos`；`new=TodayBSPos`；`availPre=AvailablePosition`；`availNew=0` | `positionCost=margin=TotalPosCost`；`avgPrice=HistoryPosPrice`；`dynProfit=0`。[HuaX][huax] |
| OES `935–963` | `pre=max(originalHld-totalSellHld,0)`；`new=originalHld+totalBuyHld-totalSellHld-pre`；`availPre=sellAvlHld`；`availNew=0` | `avgPrice=costPrice/10000`；`positionCost=margin=total*avgPrice`；`dynProfit=0`。[OES][oes] |
| ATP `858–870` | `pre=init_qty/100`；`new=max(leaves_qty/100-init_qty/100,0)`；`availPre=available_qty/100`；`availNew=0` | `positionCost=margin=market_value/10000`；`avgPrice=cost_price/100`；`dynProfit=profit_loss/10000`。[ATP][atp] |

事实结论：这些原股票插件把一个总可卖值放入 `availPre`，没有要求柜台提供今昨可卖拆分。XTP 确实读取了昨日持仓；本文没有把它描述成仅依赖总量与可卖。插件对成本槽和昨仓的处理也不同，不能据槽名建立统一柜台金融定义。[XTP][xtp] [HuaX][huax] [OES][oes] [ATP][atp]

源码推论：ATP 的公式在 `leaves_qty<init_qty` 时仍令总量等于日初量，例如按股归一后日初 1000、剩余 700，会得到 pre=1000、new=0。此为公式推演，未运行；它说明原插件不能自动成为所有边界正确的 oracle，也不构成本任务的新代码审查。[ATP 858–864][atp]

### 原生持仓槽、冻结名称与查询消费

`WTSTradeDef.hpp:523–543` 的恒等式为：`total=pre+new`，`available=availPre+availNew`，`frozen=total-available`；另两项 frozen 同样是各槽差额。该对象没有记录差额的原因。[持仓模型][trade]

因此，将 `V-A` 命名为“当前不可用数量”是与源码一致的解释；把它全部解释成订单冻结缺少依据。T+1限制、源公开冻结数量和其他不可用原因必须保持来源语义。仅凭这四槽不能分解原因，也不要求插件通过订单/成交构建第二套冻结或持仓账本。[持仓模型][trade]

`TraderAdapter::onRspPosition:1537–1594` 取合约、证券标识、方向及四个数量槽，写入运行投影，向 sink 发送四槽，随后推进订单查询；这条初始化路径没有读取成本、均价、持仓浮盈或独立冻结字段。`getPosition:425–448` 对四槽求和；`enumPosition:451–460` 仍暴露四槽。[Adapter][adapter]

`onRspOrders:1596–1719` 处理订单统计、可信 WT 活动订单及未完成量；`onRspTrades:1729–1803` 处理历史成交统计并推进账户查询。历史成交查询不能再走 `onPushTrade`，否则会进入另一条持仓更新路径。[Adapter][adapter]

今昨槽在后续执行和 push 路径有真实用途：`onPushTrade:2171–2192` 将开仓加入今仓，依 `isT1()` 决定是否增加今可用，平今减今仓，其他平仓先减昨仓；执行选择还消费今昨可用及平仓规则。因此本文的聚合投影仅用于本次无执行器、无 push 的初始化，持续回报、重连恢复、真实交易都需要另行定义和验证。[Adapter][adapter]

### 资金映射及显式初始化

XTP `545–574` 将 `total_asset→balance`、`buying_power→available`、`withholding_amount→frozenMargin`、`fund_sell_fee→commission`，并把 `dynProfit/margin/frozenCommission` 置零。HuaX `274–287` 将 `UsefulMoney→available`、`FrozenCash/FrozenCommission` 写对应冻结槽，并设置 `margin/dynProfit=0`；其 balance 使用 `PreDeposit`。这些是各插件实际行为，不能用来证明 QMT 相同名字具有相同含义。[XTP][xtp] [HuaX][huax]

固定 XTP SDK `xoms_api_struct.h:312–342` 说明 `withholding_amount` 包含预扣交易资金与手续费；`security_asset` 当时为保留零值，`orig_banlance` 标为期权字段。股票插件确有使用汇总冻结槽的先例，且柜台资产口径需要保留来源定义。[XTP SDK][xtp-sdk]

`TraderAdapter::onRspAccount:1518–1522` 向 sink 传 `balance` 和 `balance+dynProfit`，同时读取 available、margin、利润、手续费及出入金；`ITrdNotifySink.h:52` 的资金回调没有冻结资金参数。因此，源总资产已经包含盈亏时，映射 `balance=总资产` 后再填同一浮盈到 `dynProfit` 会在 dynbalance 重复加算。[Adapter][adapter] [Sink][sink]

`WTSAccountInfo` 构造器 `600–612` 初始化多数资金槽，却遗漏成员 `m_uMargin`（声明 `652`）；`getMargin:635` 返回该成员，`setMargin:623` 为明确赋值入口。插件必须显式初始化它，不能依赖对象池或构造默认值；该要求在插件边界完成，保持核心源码冻结。[账户模型][account]

建议本次映射使用 `balance=来源当前总资产`、`available=来源可用资金`、`dynProfit=0` 作为防止重复累计的 ABI 中性值，并显式 `setMargin(0)`。普通现金股票的保证金槽可在已证账户/产品适用性契约下标为不适用；XTP/HuaX 的现金股票映射置零是兼容先例。仅有“字段没返回”时仍标 unknown，数值零只是确定性初始化，不声称来源确认零。QMT 官方 Position 将股票保证金列为不适用，此依据属于持仓字段，不能自行推广成所有账户类型均无保证金。[XTP][xtp] [HuaX][huax] [官方结构][qmt-data]

## 官方公开字段事实与未核部署事实

内置 Python 官方分别列出当前持仓、可用数量、冻结数量、昨夜拥股；成本使用 `m_dOpenPrice`，若干期货成本字段对股票不适用。Account 列有 `m_dBalance` 总资产、`m_dAvailable` 可用金额及独立冻结资金字段。“昨夜拥股”的简短定义不足以证明当日卖出后的剩余昨仓。[官方结构][qmt-data]

XtQuant 官方分别列出 `volume/can_use_volume/frozen_volume/yesterday_volume`，资产列出 `cash/frozen_cash/market_value/total_asset`。这些文档支持字段区分；当前 HTTP 白名单、真实回包、券商语义与部署版本未在本次核验。[官方 XtTrader][qmt-xt]

## 推论与建议：聚合只读 ABI 投影

建议适用前提是：新进程一次初始化；普通现金股票/ETF；合约、方向、单位、源身份与本批完整性成立；只有被动 sink；没有执行器、策略触发、下单撤单或 push 归约。来源确认总量 V、当前可卖 A，均为有限、非负、符合源单位与数值范围的数量，且 `0≤A≤V`。

```text
direction = LONG
prePosition = V
newPosition = 0
availPrePos = A
availNewPos = 0
```

这是建议新增的聚合 ABI 承载约定，不声称 pre 是真实昨仓，也不声称 new=0 证明没有今日买入。它依据原求和消费路径，并沿用原股票插件把总可卖放一个槽的模式；它并非上述插件完全相同的输入公式。[Adapter 425–448、1537–1594][adapter]

### 源码推导的 getPosition oracle

对于只有该证券多仓、空仓为零的新实例，下表是原源码直接推导的 oracle，本次没有执行验证：

| 调用 | 预期 |
|---|---|
| `getPosition(code, false, 1)` | V |
| `getPosition(code, true, 1)` | A |
| `getPosition(code, false, 2)` | 0 |
| `getPosition(code, true, 2)` | 0 |
| `getPosition(code, false, 3)`，含默认 flag | V |
| `getPosition(code, true, 3)`，含默认 flag | A |
| flag=0 或未知 code | 0 |

`flag` 是多空方向位，`bValidOnly` 选择总量或可用量。一般情形 flag=3 是多减空的净值；本建议以普通现金长仓为边界，不能借这个表声称已支持融券或衍生品。合成例 V=1000、A=600 应分别得到 1000、600；A=0、A=V 和 V=A=0 都有明确预期。[Adapter 425–448][adapter]

### presentation 约束

- 对外准确展示总持仓 V、当前可卖 A；可选展示 `V-A` 为“当前不可用数量”，不标作委托冻结。独立源冻结值有资格时按源定义另展示，缺失保持未知。
- 今仓、昨仓、今可卖、昨可卖的来源 presence 为 unknown，四个 ABI 数值不用于填充这些业务栏目。原 `on_position/enumPosition` 的参数和原日志 pre/new 标签注明属于聚合槽，不把它们当历史归属证据。
- 成本、均价、独立浮盈、冻结明细没有来源时显示“不可用/未提供”，不显示确认零；有来源时保留口径，不能把市值代替成本。它们不是该总量/可卖初始化的必需输入。
- `dynProfit=0` 和未知 margin 的数值初始化保留“ABI中性值/来源未知”标识。结构性不适用与来源确认零分开；只在有适用性依据时输出“不适用”。
- 资格元数据沿现有单批 presence/投影模式携带；插件不保存跨批持仓账，不按历史成交回放出另一份今昨仓或冻结量。

这些约束是建议契约。它们保留原 `on_position` 和账户通知的数值安全，又限制下游对原槽名的过度解释。[Sink 32、52][sink] [Adapter][adapter]

## 建议修订的 NQB 条款

以下为给规格 owner 的修订建议；本次没有改规格。条款行号对应本文记录的规格摘要。

| 现条款 | 建议收敛 |
|---|---|
| 字段契约持仓行 `116` | 最低输入改为可信 V/A、证券/市场/方向/单位，增加上述聚合投影模式及 `0≤A≤V`。精确今昨归属与分项可卖属于单独 presence/资格，不再阻断聚合只读观察。 |
| 账户行 `117`、presence 段 `122` | 保留当前总资产和可用资金最低要求；显式初始化实际消费槽，特别是 margin；规定总资产与 dynProfit 的中性映射；冻结、期初资金、利润/费用细目缺失仅限制对应输出。 |
| Observed `45`、历史成交与持续事件 `94` | 为本模式明确一次性、无执行器、无 push、无连续归约；ready/Observed 不授持续恢复或交易资格。 |
| NQB-R3 `156` | 增加 flag=1/2/3 与 valid=false/true 的原 Adapter oracle，检查被动 sink 按聚合语义输出，历史成交保持统计路径。 |
| NQB-R4 `157` | 区分最低必需字段缺失与可选字段缺失；后者维持限定观察，不能将已知 V/A 的查询转换为失败或伪空。错误/截断/身份失败等既有边界保持。 |
| NQB-R5 `158` | 验证源 V/A 保持、T+1不可卖不误标委托冻结、不同ETF直接采用源可卖；有可信今昨/冻结/成本时检查对应映射，没有时检查 unknown；避免新增本地推算账。 |
| NQB-R8 `161` | presence约束从资金扩展到持仓今昨、成本及冻结原因；确认执行器/push/写调用为零。 |
| NQB-R9 `162`、待核事实 `178` | 分开记录聚合观察资格、精确今昨资格、真实部署资格；源需补字段只针对对应缺口，不把完整金融模型槽当全部只读功能的前置条件。 |

### 后继正向与负向验证边界

正向应在固定原 Adapter 的隔离 fixture 中验证：V=1000/A=600、全可卖、全不可卖、合法空持仓；上述 flag/valid 矩阵；当前资产 100000、可用 70000、独立源浮盈 1000 时 ABI dynbalance 保持 100000；margin 显式赋值；缺少可选今昨/冻结/成本仍完成限定观察；真实存在的可选事实及 unknown presentation 分别核对。示例数值均为合成测试输入。

负向应覆盖：负数、非有限数、A>V、最低 V/A 缺失、未知证券/单位/方向、身份或完整性失效；未知成本/今昨/冻结被显示为确认零；把 V-A 标为委托冻结；把源“昨夜拥股”未经定义直接当剩余昨仓；总资产重复叠加浮盈；margin遗漏显式赋值；将历史成交再次作为 push 投入；聚合模式接入执行器、连续回报或恢复路径。失败或拒绝只针对实际违反的资格，不要求另造持仓对账器。

上述为待执行的验证要求。本次只完成源码核查与官方资料阅读，未执行这些案例；没有证明当前 QMT 编码器字段齐备、真实账户/ETF制度与部署一致、真实网络查询可用，也没有授予生产资格。

## 来源

[xtp]: https://github.com/fr4ngou/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderXTP/TraderXTP.cpp#L472
[oes]: https://github.com/fr4ngou/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderOES/TraderOES.cpp#L935
[huax]: https://github.com/fr4ngou/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderHuaX/TraderHuaX.cpp#L242
[atp]: https://github.com/fr4ngou/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderATP/TraderATP.cpp#L858
[trade]: https://github.com/fr4ngou/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/WTSTradeDef.hpp#L523
[account]: https://github.com/fr4ngou/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/WTSTradeDef.hpp#L600
[api]: https://github.com/fr4ngou/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/ITraderApi.h#L145
[adapter]: https://github.com/fr4ngou/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp
[sink]: https://github.com/fr4ngou/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/ITrdNotifySink.h#L32
[xtp-sdk]: https://github.com/fr4ngou/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/API/XTP2.2.32.2/xoms_api_struct.h#L312
[qmt-data]: https://dict.thinktrader.net/innerApi/data_structure.html
[qmt-xt]: https://dict.thinktrader.net/nativeApi/xttrader.html
