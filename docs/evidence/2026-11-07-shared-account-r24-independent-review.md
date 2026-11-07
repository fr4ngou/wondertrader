# R24同账户份额及实际资金独立复核

类型：验证证据。日期：2026-11-07。审查范围：`43e5d98bdaa43705393d2051f700db87b583f291`至普通安装R24对应`c64377c49f3b3941f0348a7cfe1ae785149c0498`的同账户接线。结论：部分受控主链通过，旧策略退出和内部成交估值存在可复现缺陷，R24不得作为同账户并行上线证据。本轮未采用金融运行版本。

## 原生责任

WT策略ctx和原报告继续拥有理论持仓与绩效；组合按原风险、过滤和路由处理净目标，Local执行器按其scale处理目标。策略本金、组合base_amount、执行器scale和分析init_capital各有独立用途。账户available属于柜台总量；ASA补策略实际归属、挂单占款和限额。依据：[官方架构](https://wtdocs.readthedocs.io/zh/latest/docs/intro.html#id6)、[原生组合目标](../../src/WtCore/WtExecMgr.cpp)、[原生执行规模](../../src/WtCore/WtLocalExecuter.cpp)、[ASA规格](../specs/account-strategy-allocation.md)。

## 独立验证

| 场景 | 结果及影响 |
|---|---|
| 旧策略实际D无费用 | [柜台接线](../../src/TraderQMT/StandardQmtTrader.cpp)给fee_cny空值。普通R24在隔离场景中记入卖出100份后仍有900份可卖及保守可买额，旧策略回调却以`waiting_basis/account_cash_unavailable`跳过`advance_retained`。同一成交补确费后恢复推进。旧基准配置保留时触发；ASA规格要求卖出按自有可卖份额处理。 |
| 同码零净额 | 旧方减1000、新方加1000，有共同合格价时内部过户、柜台成交0；无价保持原归属。延至下周一处理时复用了周五报价，并把开仓时钟记到周五。内部过户需沿实际执行时点核报价资格。 |
| WT组合缩仓 | 原Native管理器实编将1000缩为500，R24按缩放前意图作强等校验，拒绝`attribution_merged_targets_conflict`。仅当组合缩放改变目标时触发；Local执行器scale另在合并回调之后生效。修正须消费可归属的原生执行目标，保留对无法解释差异的校验。 |
| 成交、终态及恢复 | 一个原命令的125份部分成交按100/25归两策略；终态先到后重放、重复事实单次入账；未知责任跨重启保留原命令及两笔205占款。 |

源回调与费用分别追踪，缺费用时保守占款，待有原始来源才能确认实际值；策略实际可卖控制仍须维持。观察页独立只读，真实账户是否可恢复、模拟柜台受理、两策略同一实际账户成交及收盘时点回测需各自验真。

## 证据定位

受控目录 `E:/workspace/wondertrader-qa/original-live-readiness-20261107-001/allocation-independent-review`，`run-5c40f2a60a704ae38df7eec2259ded5d/RESULT.json` SHA `7705f9afaaef0ae7560f263d40e8db8c43b2ef8dcf43a31028a045f63414187a`。使用普通安装Runtime、原Native桥契约、实编组合管理器和隔离账本；Source请求、模拟下单、撤单及生产写入均0。
