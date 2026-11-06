# WT目标参考价与执行价格保护核查

类型：原生能力研究。日期：2026-11-06。状态：源码与官方当前版本核查完成；未修改配置、程序或服务，未执行下单和撤单。范围：WT-T03/T07、WT-S01/S03。

## 结论

WT具备CTA条件触发、显式委托限价和执行单元扩展能力。当前CTA数量目标→Local→StockMinImpact链没有携带目标生成时的参考价及最大允许偏离，所核内置单元也未提供该参考价的持续价格保护。买入限价能约束该笔委托的最高成交价；为每次拆单及撤后重报保持同一个目标价格边界，需要执行层持续校验。

2026-11-06通过官方GitHub API读取的master HEAD为08b230dd05facf6d650d949bfe51054115a2ecb1（提交时间2026-09-01）。它与本仓库声明的固定上游相同。官方master raw页面也已浏览；结论以固定提交的源码为准。[官方HEAD API](https://api.github.com/repos/wondertrader/wondertrader/commits/master)、[固定提交](https://github.com/wondertrader/wondertrader/tree/08b230dd05facf6d650d949bfe51054115a2ecb1)。

## 原生能力及保证范围

| 入口 | 已核行为 | 对本问题的作用 |
|---|---|---|
| ICtaStraCtx::stra_set_position的limitprice | 增仓条件为最新成交价≤阈值；减仓为≥阈值 | 可复用作策略目标的触发条件 |
| 同接口stopprice | 增仓条件为最新成交价≥阈值，减仓为≤阈值 | 属于反向条件触发，不能当买入最高成交价 |
| CTA条件触发后 | append_signal仅保留数量、信号价、时间及标签；后续处理按数量目标汇总 | 信号价保留用于记录，执行接口不接收该价格边界 |
| ExecuteContext::buy/sell与ITraderApi | 显式price创建委托，0的接口语义为市价 | 单笔显式限价可约束该笔成交；供应商映射、订单类型与终态需沿实际通道验证 |
| IHftStraCtx::stra_buy/stra_sell | 接受明确price、数量、normal/FAK/FOK标记，经HftStraBaseCtx送TraderAdapter | 原生直接下单路径；采用需明确订单生命周期和当前QMT支持，不等于给现有CTA加一个开关 |
| ExecuteUnit/IExecuterFact | 原生执行单元及工厂插件扩展接口 | 可在原执行边界增加策略特有价格保护，继续复用原下单、撤单和实际订单表 |

CTA条件实现位于固定[CtaStraBaseCtx.cpp:797及1354](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/CtaStraBaseCtx.cpp#L797)。触发后append_signal与后续理论仓位推进是两个步骤，期间市场仍可变化；条件阈值不会作为交易限价传入执行单元。数量接口位于[ExecuteDefs.h:178](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/ExecuteDefs.h#L178)，显式限价接口见[ExecuteDefs.h:85](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/ExecuteDefs.h#L85)及[IHftStraCtx.h:75](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/IHftStraCtx.h#L75)。

## 当前股票执行器及内置风控

StockMinImpact使用当前tick和pricemode定价；撤单后可按cancel_times追加报价档位，随后受涨跌停价约束。start_price只出现于初始化/赋值，没有参与相对信号参考价的偏离判断。改pricemode、offset或expire可改变执行风格，覆盖不了用户所述“旧目标产生后行情已大幅变化”的持续边界。对MinImpact、DiffMinImpact、TWap、VWap、StockVWap的所核配置和定价实现，也未发现接收目标参考价/最大偏离的字段。[股票执行器固定源码](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtExeFact/WtStockMinImpactExeUnit.cpp#L480)、[内置工厂](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtExeFact/WtExeFact.cpp)。本结论限所核内置实现，第三方插件分别核实。

TraderAdapter的checkOrderLimits/checkCancelLimits处理报撤单次数和统计时段，检查自成交等通道规则也有原生入口；这些规则缺少策略生成时参考价。RiskMonDefs明确将原组合风控职责放在资金风险，WtSimpleRiskMon以资金回撤触发数量倍率调整；打开该模块不能直接获得信号价偏离保护。[TraderAdapter.cpp:536及601](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L536)、[RiskMonDefs.h](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/RiskMonDefs.h)、[WtSimpRiskMon.cpp](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtRiskMonFact/WtSimpRiskMon.cpp)。

## 当前自有接线与最小缺口

本机src/GuanhengRealtime/ContextAccess.h:83调用stra_set_position(code,qty,"gh_rt",0,0)，当前桥没有使用原生条件价格。src/GuanhengExecution/OwnerExecCommand.cpp:17的Target只有code/value；WtLocalExecuter.cpp:303把数量传入ExecuteUnit::set_position。原公共接口确认的是数量目标，持续执行保护需要目标参考价、目标身份、生成时间及允许价格边界的明确传递和所有者。

可以先复用CTA条件触发避免不合价格条件时生成目标；完整保护还需要在每笔新委托和撤后重报时核买入最高价/卖出最低价，并处理已经挂出的订单、新目标替换、部分成交和同账恢复。保留原WT执行、订单及撤单能力；扩展工厂优先，动态目标价格边界如何传递须先设计，尚无依据直接改核心接口或切换HFT架构。

所有参考价格、偏离阈值、有效时间以及超出边界后的等待/重算/终止选择，先由用户确认。研究没有设置任何具体阈值，也没有声称已有真实价格保护验收。
