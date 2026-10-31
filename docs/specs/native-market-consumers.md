# 观衡原生行情消费者

类型：功能规格。状态：accepted，前缀 NMC。依据：统一策略行情、观衡独立发布及重合能力全部复用原生实现。能力核实后历史窗口采用[原生历史窗口](native-history-window.md)的公开Reader/Factory组合；图表使用独立MarketClient，旧ReaderClient候选不作为本条读取入口。业务路由的唯一精确规格由观衡仓库的`docs/specs/wondertrader-market-chart.md`维护。实现、常驻生命周期和生产用户入口分别取证。

## NMC-R1 单一原始行情存储

QMT 主来源、TDX 可选来源通过既有接入和归一化进入 WT 原生行情存储。观衡查询、图表和特征窗口消费同一份数据及来源身份。旧 PostgreSQL `market_bars`、分钟接纳收据和 outbox 不是新行情读取的前置条件；不得用假成功的 save_bar 或静默读旧库实现兼容。业务效果确认与原始行情持久化分别由其所有者承担。

复用已有 MarketBridge、StrategyMarket、reader HTTP 和原生 IDataReader。客户端不复制日历、补数或来源合并算法，不加载 WT DLL、wtpy、QMT 私有源码或数据库驱动。保持框架源码审批边界。

## NMC-R2 独立 Python 行情客户端

复用独立SDK的`MarketClient.history_query`，消费`guanheng.market.v1`公开窗口和周期选择器。一次调用一次有界HTTP交换，无重试、代理发现或重定向；HTTP明文仅数值回环，HTTPS校验证书；网络端点与绝对截止遵循[CTD规格](client-transport-deadline.md)，HTTPS域名显式配置connect_ip，原域名保持Host/SNI/证书身份；凭证不进入错误文本。客户端不导入WT DLL、wtpy、QMT或数据库；安装的wheel独立于业务与原生进程发布。

请求使用交易所、代码、上海右端分钟闭区间、原生period_minutes及最多limit根。空和不足limit是合法结果；选择器响应必须回显匹配，覆盖保持Unknown，不因返回若干行宣称完整。 SDK验证请求关系，原生Reader和Factory继续拥有数据读取及交易时段周期转换。

响应严格验证版本、状态、选择器、分钟范围、OHLC/量额及完整来源metadata。业务每请求构造客户端，连接在单次交换finally关闭；不共享可变连接或native对象，下一次请求可读取新内容代际。原策略Reader订阅/恢复契约继续由其原规格维护。

图表仅投影未复权/空因子版本，业务暴露必要来源及内容身份，实例/会话和凭据不进入浏览器。客户端不提升源资格，只读历史不拥有策略确认游标。

## NMC-R3 图表读取接缝

保持观衡MarketChartBundle和Console路由，Console分钟主图和基准直接经独立SDK读取原生窗口，MarketData兼容路由复用同一纯投影。退出recent_bars、报价补线及Python五分钟聚合；图表读取无需启动旧MarketData、数据库或消息总线。右端减所选周期映射为图表起点，股/元不重复换算；5m直接使用原Factory结果。来源、覆盖未知、短/空/失败用中文说明；主查询和基准共享既有Console绝对预算。1d/复权、特征与策略分别映射；完整Console进程的启动/就绪/正常退出与最终线程释放须实际验证，不以关闭ASGI生命周期的测试代替。

此条要求仍待实现；先交付 R2 不能报告图表已切换。冻结图表 at-most-count、跨窗修订与分页规则后再修改门面，禁止用逐次递减 count 的盲重试绕过缺口。线上读单一政策来源；旧行情仅作为切换期归档和回退依据。

## NMC-R4 特征、策略与恢复

特征计算直接使用 WT 取得的完整窗口和既有纯算法。历史预热、迟到和恢复分钟不自动升级为当前交易触发。策略身份、配置版本、输入修订与业务效果确认由最终策略状态 owner 统一处理；SDK内存ACK和最大行情时间都不等于持久确认。先逐字段映射 WT 策略上下文与观衡自定义状态，再切换调度、意图提交及恢复；旧分布式服务拓扑不是必须保留条件。任何交易权限保持现有授权边界。

## NMC-R5 验收与发行

R2必验实际MarketHTTPServer→独立安装SDK→业务API→Console、正常/空/短/失败/恢复和有界并发。篡改字段/单位/时间/来源、超大/截断/慢响应及连接释放须按影响验证。公共契约及生命周期按适用开发门禁和独立审查取证；被门禁拒绝时保留开发状态，不能登记已审查或发行资格。

完整交付继续要求真实 QMT 样本→WT存储→原MarketData API→Console→中文图表，以及特征/策略和回测实盘统一调用链；独立SDK测试只授予该接缝开发资格。PG分钟候选及其历史证据保留但暂停接线，现有生产数据、账户与未决命令保持。数据库若仍有必要，按[条件部署规格](windows-native-database.md)处理。
