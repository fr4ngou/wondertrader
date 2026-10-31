# 模块B：正式执行入口的资金、可卖与费用规则

类型：隔离开发证据。日期：2026-10-29。状态：in-progress，完整模块B继续。关联：[模块B](../migration/module-b-delivery.md)、[标准Trader规格](../specs/native-qmt-standard-trader.md)及[R11交易规则](../specs/native-realtime-strategy.md#nrt-r11-固定业务配置的受管python入口)。本轮复用WT-T03原执行算法及原策略/组合账目；新增WT核心修改、真实券商调用及金融账本均为0。

## 原因与正确接线

原通用`WtMinImpactExeUnit`以默认`getPosition`读取可用仓位。合成账户总持仓1000、可卖200、组合目标400时，它把200当作当前执行仓位，产生买200的尝试，已由SDK替身断言拦下。现金股票/T+1使用原`WtStockMinImpactExeUnit`：它分别读取总持仓和可卖，按`max(1000-200,400)=800`形成当次可执行目标，仅卖200。原策略A0/B400的目标保持；券商未成委托和剩余600股调仓责任分别沿原事实核查。

原股票执行器以`min_order`取整，自有配置需要显式提供正整数，首现金ETF模型为100。自有`StandardExecutionHost.cpp`在创建API前统一校验所需参数；算法身份沿原Factory消费的同一Variant及原`StrUtil::split`前两段识别，额外名称段或尾点保持原兼容语义，实际股票算法均核同一参数。独立审查发现的等价名称绕过已按这一原生解析规则收敛。

## 已有实际主链

原件根为`build/ms-trade-rules-001`。正式模块与原Runtime/Factory/CTA/Local/Adapter经真实WinSHM进入明确SDK替身；价格、账户、历史与费用均为合成模型。

| 用例 | 实际业务结果 | 固定身份与范围 |
|---|---|---|
| fees-001 | A/B各买700@10.01，原交易CSV费用各7，原累计费用各7，原flag0损益-7，派生NAV49993/现金42986 | 原BUILD004 Runtime，通用执行器；同原核心及安装Appa10 |
| fees-002 | 同上；原组合CSV净买1400、费用14；独立券商查询佣金14、available15972 | BUILD-001 Runtime73fd…，原股票执行器及min_order100；完整自然关闭、Host/源/EOF/join全通过 |
| t1-001 | 当日A/B原actual各700、sellable各0，NSQ同代际收敛且净买1400一次 | 原BUILD004 Runtime，通用执行器；只授当日理论观察与该次买入，不授后续减仓/跨日资格 |
| cash-wait-002 | A/B连续原调度sequence>=2、waiting_cash/whole_buy_group_unfunded、空提交向量，源SDK尝试及调用均0 | BUILD-001 Runtime73fd…，原股票执行器；每策略理论本金50000、显式费用预留50000，整组买入等待；原源码仅在非空向量时调用setter |
| sellable-200-004 | 原exe消费A0/B400目标，券商P1000/usable200，唯一SDK side24卖200；正常完整关闭 | BUILD-001 Runtime73fd…，原股票执行器及min_order100；未宣称策略目标400已达 |

本轮费用模板为合成按量开仓0.01元/份、平仓0.02、平今0.03；只有上述买入已验证，卖出费率、最低费用及真实券商收费继续待验。理论本金和原WT损益派生的预算，与券商available是不同来源；资金等待正例不代表已经证明真实账户可用资金准入。

## 保留失败与剩余资格

`sellable-200-001`保留错误方向尝试；`sellable-200-002`缺股票min_order时退出3221225477，补min_order100的003通过，未调查框架根因。`sellable-zero-001`旧RESULT虽标passed，但源first_error记下错误SDK尝试，该资格撤回；测试现要求正例first_error/proxy_first_error为空，预期unknown-stop异常单列。

BUILD-001的`t1-002`已产生700/700收敛和原closed.ok=true，最终进程exit2，父close失败；`sellable-zero-002`关闭未通过；BUILD-002的`fees-003`在SDK买1400后只有初始化四查询，原生退出3221225477。上述均为失败，完整同版T+1、零可卖和持续运行资格保持待验，未据此重新开展WT线程调查或修改核心。

## 最终自有准入修改与当前资格

BUILD-003绑定自有StandardExecutionHost源码及固定输入，最终Runtime为`241cdba18271b4c9a3800efdb97a2750b30326c571554fb3cf86125a5445ffcd`，原BrokerQueryContext库重编为`7ebe8d3f3fcb39caba271a66489559b046b80c70601611b8e6aac3708c5ba654`。原WT对象/库、策略桥及Python wheel保持原身份；仅自有配置边界重编与重链接。

`stock-min-{missing,zero,negative,fraction}-002`及`stock-name-{extra,trailing,nul}-002`七案实际安装exe均在交易API创建前拒绝，四查询/SDK均0，无ready，原closed以trader阶段失败，父/源/Host/EOF/join完整回收。后三案验证实际选中的股票算法始终核缺失min_order，名称兼容本身保持。`native-add-001`以同版安装exe完成A600+B400→买1000一次、四查询、正常完整关闭，原通用路径兼容。

同版`sellable-200-006`完整关闭未通过，未执行其后的`stock-extra`正例。BUILD-003股票执行整链与全模块继续pending-verification，当前不提升为替代007的可运行发行候选。原007制品保持冻结；本轮未打包/发布新运行库。已通过的BUILD-001费用/等待和卖200正例按原DLL身份分别保留，当前完整同版结论继续待验。

最终矩阵、独立审查和续接清单位于`build/ms-trade-rules-001`；发行、统一A/C安装、完整下撤单、资金/T+1/费用与异常跨根责任继续主线。项目静态文档检查通过，原交易样本均为合成输入。

## 后继：当前完整App搬迁安装的三项交易规则

[当前App组合](2026-10-29-current-app-native-composition.md)交付后，继续在其003 ZIP的普通离线搬迁安装验证已有交易规则。固定Appa19/core a7/完整35发行、Runtime241cdba…及原HTTP日线Reader，生产代码和策略数学规则保持该交付身份，执行器显式为原通用MinImpact。新原件根为`build/ms-current-trade-rules-001`，不覆盖上述任何历史用例。

| 后继用例 | 实际结果 | 证明范围 |
|---|---|---|
| fees-001 | A/B各700，原交易/累计费用各7元，flag0损益各-7，理论NAV49993/现金42986；组合净买1400一次，最终8查询 | 当前完整安装的非零买入费用和后继收敛 |
| t1-001 | A/B原actual各700、sellable各0，数量阶段收敛；组合净买1400一次，最终8查询 | 当前完整安装的T+1当日买入观察；后续减仓/跨日继续待验 |
| cash-wait-001 | 每策略理论本金50000、显式费用预留50000，连续调度sequence>=2，waiting_cash/whole_buy_group_unfunded及空提交向量；4查询、SDK0 | 当前完整安装的整组理论预算等待 |

三个driver均exit0，原子端正常closed、父reaped/双EOF及reader join，Host/来源/HTTP均完整关闭，forced/pending=false，源及proxy错误为空。费用proof在最后查询前登记7次、最终RESULT登记8次，分别保留各采证时点。实际券商调用0，新增生产源码及WT核心修改0。

本段复用既有规则实现及测试，源码、当前安装、命令与原件由新根MATRIX/REVIEW/DELIVERY单独绑定。R15 CHECK-002时有四份并行新文档未索引；后继完成索引后，最新全局静态检查通过，见新根CHECK-001，各检查时点分别保留。原股票执行器同版完整退出、当日减仓/跨日、费用卖出/最低值和实际券商available准入继续保留缺口；本段通用执行器结果按实际范围授资格。框架线程调查持续停止。
