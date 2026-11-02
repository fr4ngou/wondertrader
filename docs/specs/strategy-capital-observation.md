# 策略资金的独立只读消费

类型：公开消费契约。状态：accepted。范围：观衡App与页面读取WT资金发布，不拥有运行侧计算、账户或执行生命周期。

## 来源与接口

通过已配置的WT状态文件及control/instance/configuration身份，沿WRI的execution.business_observation、同代ready.json和strategies.json读取唯一策略的capital_baseline/capital。读取路径由原发布者声明；App不扫描私有配置，不创建WT或Host。

原`/v1/ui/strategy-details`与`/v1/ui/strategy-runtime`继续原v1响应，增加可空的capital_baseline、capital；原发布无这些字段时保持原预算及未知事实。`/v1/ui/account/overview`继续账户范围，其总资产和现金不作为策略资本。所有接口继续只读。

## 值与时点

capital_baseline模式为guanheng.current-capital-baseline.v1，包含total_cny、source、baseline_at和空的historical_initial_capital_cny。本次用户确认的100万元是当前运行总资本，包含已有库存；不是旧历史本金的恢复记录。

capital模式为guanheng.strategy-capital-observation.v1，货币CNY。nav_cny、spendable_cash_cny、cash_balance_cny、market_value_cny、native_pnl_cny分别供策略总资产、可用资金、现金余额、持仓市值和本次运行盈亏展示。金额保留十进制字符串，缺可用资金及账户约束值保持null；页面不重算分配、净值或可用资金。

原observed_at是CTA估值截止，position_observed_at是券商持仓接收时点，account_observed_at是原账户批结束时点；baseline_at是原首次初始化时间。GET时间、文件mtime和页面刷新不能替换这些来源时点。

App沿原发布核验基准和金额关系；运行已停止或原账户期限过期时取消当前可用现金资格，其他已发布金额和原时间保留。历史本金与historical_return_pct为空，本次运行资金不能生成旧历史收益。

## 验收与资格

保持旧发布的详情、账户、运行和报告可读；核新字段的原值、来源时间、停止/过期语义及账户范围。App、前端合成渲染、SDK发布链、当前实际账户和交易恢复分别记录资格。独立App可接收已固定的读端文件，运行侧完整恢复及真实成交不能因读端通过而授予。

页面要求沿[OAR资金展示](observer-acceptance-repair.md#当前策略资金的只读展示)，运行侧基准与资金事实沿[原生实时策略](native-realtime-strategy.md)，具体源码与已验范围沿对应证据。
