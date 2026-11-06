# 分析窗口有效期600秒采用

类型：配置发布与运行证据。日期：2026-11-06。状态：用户确认、实现、验证及实际采用完成；日内价格偏离保护仍处于研究阶段。

## 依据与行为

用户确认将当前交易实例market_window.max_age_seconds由3600秒改为600秒。生产者每轮完成后等待300秒再刷新；本次核对最近12次发布，间隔240.1至384.0秒，旧视图在下一次发布前最大年龄428.7秒。600秒收紧旧视图可用期并覆盖该正常刷新样本。生产者的刷新间隔和运行预算保持。

此值约束决策截止与current_view.received_at的时间差，年龄达到600秒即过期。历史日线完整性、实时tick新鲜度、目标价格偏离与订单限价各有原职责。日内做T还需单独设计和验证实时数据与执行保护，不能据本次调整声称具备完整做T能力。

原Python/Native同账恢复把窗口时效计入严格业务配置，直接修改会被拒绝。两端现复用/对齐原1至604800秒有限数值合同，只在比较副本归一化有效期，保持窗口路径、账户、策略、金融根与完整原件SHA。前代状态使用前代窗口身份验证，后继保存本代身份，原状态和金融事实保持。

## 验证与采用

材料根：E:/workspace/wondertrader-qa/market-window-age-20261106-001。新Runtime0.1.0a18+windowage.1在原orderlots.1闭包上只改恢复模块与版本；AWP仅调整版本与固定Runtime依赖，执行代码和其它依赖逐件核同，23包pip check通过。新Native在全新build/windowage1构建，基于已验冻结输入仅改自有CtaProcess；源码CRLF与冻结LF按换行规范化完全一致，原件不可变，见SOURCE-NORMALIZATION.json。

3项时效恢复回归、13项业务身份回归、2项发行恢复回归通过。实际发布窗口冻结回放：600秒配置在599秒通过、600和601秒过期，3600秒对照在601秒通过，见BOUNDARY.json。独立delta审查覆盖两端边界、原身份链、状态身份接续及受租约保护的切换脚本。

沿原正常stop、Native完整close与实际进程退出、同账prepare_transition、新activation和CURRENT原件保留完成采用，仅替换Host/Runtime两项程序。实际Native ready，新配置age=600、lots=10000，reconciled接收的原金融状态SHA与transition一致，5个其他WT角色PID及创建身份保持。原生产者接线及刷新间隔保持，日常两快捷方式、服务组与DEPLOYMENT已接新程序和service。

当前Native配置摘要：dc87aa0363e2b8a441977e26a071cd8944b22ae52c653ddb2c8c0822db992251。POSTFLIGHT.json、START.json、TRANSITION.json、RUNTIME.json、NATIVE.json及OPERATOR-INSTALLATION.json分别记录实际身份和步骤。强制测试下单为零。

## 原生价格保护研究及边界

[原生研究](../research/wt-target-price-protection-20261106.md)确认CTA条件价约束触发时机，原生显式限价约束单笔委托；当前数量目标链未传递信号参考价的持续执行边界。价格保护阈值、参考价及超界处理须先与用户确认，本轮保持相关交易行为。

本次完成实际配置加载及原读取函数的过期边界验证；下一市场会话中的自然过期/恢复与新委托尚待触发。回退使用保留的原CURRENT、配置和native-before制品，先正常停止及核原未决责任，再沿同账恢复采用；金融根和基准保持。
