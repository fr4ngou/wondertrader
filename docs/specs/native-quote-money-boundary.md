# 原生报价到精确金额的输入边界

类型：功能最终规格。状态：accepted。适用范围：自有configured交易运行层的当前未复权报价、初始/恢复估值和NSQ basis。现金来源算法、策略数学、WT框架、Source/QMT、历史账及UI单位沿原owner保持。

- MB-R1：报价档位来自本代已准入且SHA绑定的WT commodities，按实际原生代码的交易所/品种映射。该文件也是WT parseCommodity/getPriceTick及现有StandardQmtTrader price_text的事实来源。本代保存不可变档位快照，单位CNY/份；不按ETF代码或统一三位小数猜测。
- MB-R2：单一canonical_raw_price仅用于WT/QMT原未复权double报价，或原报告保存的同一报价十进制文本。以精确Fraction寻找整数档位；同时通过现有委托转换的double判定与精确档位误差判定，只吸收距该档位不超过4×double epsilon×价格尺度的表示误差，误差界严格小于1/4档、档数处于现有double精确整数范围。归一化集合属于既有委托边界的子集。真实离档、非有限、非正或档位无法区分的输入给出明确错误。错误不进入估值、份数或资金放行。
- MB-R3：原QMT snapshot初始估值、原CTA basis恢复估值与正常_capture统一消费规范报价。实际市值、理论仓位估值、Basis.Price及原NSQ原价共用同一Fraction/十进制值；NAV继续等于原策略现金加实际市值。旧估值来源/原时点、旧报告和原现金anchor保留。
- MB-R4：原快照、raw_positions、native_clock及原报价参与的捕获审计身份保持原值。正常观察增加可选raw_prices：按execution顺序保存业务证券及本帧原未复权double，单位CNY/份、时点沿同帧basis/报价来源，仅审计；quantity_basis.prices保存规范未复权经济价格。初始观察继续保留原initial_market_observation。App现有字段/中文单位和资金public schema保持。
- MB-R5：报价档位不作用于成交/持仓平均价、原CTA审计损益、费率、佣金或券商现金。金额继续Fraction精确运算；整数持仓及原整手规则保持。允许原合同下的小于一分金额，资金比较继续严格大于/等于，无新增现金容差、账户授权或金额粗略取分。
- MB-R6：先用实际已发布三持仓/原报价与合格NAP现金沿原构造器、初始/恢复估值、capture和NSQ做离线回放，核现金+市值=NAV。再覆盖合法档位及有界表示误差、真实离档、超过既有误差界、原价资金恰好满足/少一分和整数手边界；实际源时点/资格与离线假设分开登记，禁止真实下单。
- MB-R7：交必要源码CAS、清晰diff、字段注释和主链/根因证据。此次保持包版本、构建闭包、现金来源模块和UI原样，后继统一构建由Root负责；不引入新账本或价格执行器。共享源码及线上实例保持原owner集成与验真。

原能力分工继续沿[Fresh执行组合](etf-role-replacement.md)：WT负责行情与交易事实；本层将已声明报价事实转换为经济计算的精确输入；原NSQ决定份数和资金阶段，原执行链处理实际委托。此转换不授Source、账户或交易资格。
