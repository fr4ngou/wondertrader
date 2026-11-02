# QMT源值日线导入与原生读取

状态：accepted / in-progress。前缀：DSH。依据：三会话M1首真实策略需要9ETF闭合日线与100日预热，模块B请求见[交接](../migration/module-b-delivery.md)。本规格扩展[RS](qmt-source-history.md)自有导入/Reader，复用WT原Helper和day DSB，不修改WT框架。

## DSH1 来源与导入

现有QMI v1 canonical分钟、v2 source分钟合同保持。新增manifest schema_version=3，顶层精确schema_version/period/profile/securities，period仅1d；profile沿v2字段，minute_boundary固定unknown（日线采用交易日期，分钟边界不适用），原价none、未知单位明确unknown。输入七列CSV的timestamp必须交易日期零点+08:00；不借此声称当天00:00已知完整日线。每证券每天至多一行，排序/预算/身份/数值/原价格质量检查复用原实现。来源API返回与请求、原始日期及正文SHA另保留。

来源日线的日期支持域由四位年CSV、八位YYYYMMDD公开JSON整数、Python公历及WTSBar.date的共同表示推出，为1000-01-01..9999-12-31；零点标签固定+08:00。DAT自身仍受uint32纪元秒表示约束，固定+08零点整日可表示范围为1970-01-02..2106-02-07。canonical与分钟的原导入日期范围及IANA真实时刻路径保持。

仍由原_Native写并完整逐字段回读，原Helper period=d、WTSBar.date为交易日期、time为0，目录his/day/SSE|SZSE/code.dsb。sidecar format=3、period=1d、timestamp_semantics=source_date；成功收据schema3及period1d，其余沿RS源值收据。失败保留本次新根且无成功收据，旧根不覆盖。日线不由不完整分钟合成。

## DSH2 原生Reader与策略

NativeHistory.read_source_store识别schema3/day/format3，沿同一收据/文件/sidecar摘要核验，原文件ABI期望类型23。SourceHistoryMetadata允许1d/source_date/unknown分钟边界，SourceHistoryBar的occurred_at保留该交易日期00:00+08；同时保持原分钟source_label与canonical读取15:00行为。返回source/单位/复权/质量及coverageUnknown，原日期不授market_available_at或历史时点可获知资格。

source_date标签使用固定+08:00，1991夏令段也保持同一交易日期零点；IANA规则继续服务canonical及分钟的真实时刻，不参与来源交易日期标签解释。

B读取9证券固定真实d1窗口可直接用此安装Reader；A后继提供同版公开SDK/HTTP，沿单一路径复用原读取。15:00闭合/知晓、单位标准化、完整日历与缺口须绑定独立来源事实后才能授相应策略运行资格；不可凭原DSB已存在提升。首算法可按纯核自身需要使用源数值，真实执行准入分别核实。

## DSH3 验收

真实9ETF日线→显式CSV/manifest→原Helper/day DSB→NativeHistory→逐字段/日期/metadata一致；主链先完成，再核v1/v2兼容及重复日、错误标签/schema/类型与失败回读。独立审查、固定身份和安装交付记录必须说明真实尾部/范围，保留缺口与未核实单位unknown；已核实单位按原profile透传，不自动换算数值。真实下撤单和生产切换不在本次范围。

## DSH4 统一公开查询与目录

SDK0.14.0新增source_daily_history_query，请求exchange/code/from/to/limit，from/to为YYYYMMDD有效交易日期闭区间（范围不自动证明交易日）；action为history.source-daily-query，HTTP路径/api/market/v1/history/source-daily-query。返回metadata（额外period=1d及source_date）、bars（symbol/date/OHLC/volume/amount）、coverage=Unknown、missing_dates=[]、selection(period=1d,limit)。源日期无15:00可获知承诺。原分钟action、12位minute标签与metadata形状保持。

新增显式mode=source-catalog，顶层仍mode/native_reader/max_bars/max_cache_bars/preload_symbols/stores。允许schema2分钟及schema3日线，路由键是证券+周期；同键重复拒绝，不按配置顺序覆盖。preload_symbols在此模式为{symbol:WT格式,period:1m或1d}对象列表，旧source-store(s)仍为字符串分钟列表且保持来源实例限制。目录模式允许不同QMT实例，能力页身份为收据集合的确定性聚合；每次查询返回原收据的真实source，不能用集合身份替换原来源。

Reader、缓存、owner和关闭实现共用。LRU以证券+周期为键，总bars预算跨周期共享；一次返回最多2000行/原响应字节上限，不引入新读取池。正式受管服务允许显式目录模式；App复用原SMP子服务合同。验收必须同服务取同一ETF分钟和日线、全部9ETF日线、来源身份/原值/标签与直接Reader对照、原分钟兼容及正常关闭。

## DSH5 来源单位修订

某字段单位的提升须绑定官方接口定义、本机SDK/适配版本、证券范围、请求周期/复权/日期及原始返回身份，明确直接声明与本机接口映射的证据级别。价格、成交量和成交额独立核实，数值关系一致仅作为佐证。以新dataset_version及新manifest/数据根发布修订，旧原始响应、CSV、profile和已成功数据根保持可追溯；逐字段回读必须证明源值未变。lot的证券数量解释记录在本批证据中，不能将ETF份额统一称为股票股数。日线接口的证据不改变旧DAT或全推profile。单位完善本身不授完整覆盖、闭合/可获知时刻及实盘资格。

## DSH6 完整来源分钟标签的原生聚合

已有QMT分钟仓可以按[分钟来源日线规格](qmt-minute-source-daily.md)准入完整标签日，并调用原WT Helper按日聚合、原schema3导入及Reader回读。dataset_version明确为qmt-native-session-daily.v1，原分钟收据、DSB、chunks、profile和逐日排除原因留在独立PROVENANCE.json；QMT原日线及聚合日线分别登记唯一证券+周期路由。聚合标签完整仍保持coverage unknown、源分钟边界及量额单位，不提升实际交易日历或历史知晓时刻资格。

来源日线的unknown量单位保持原值并允许只读价格消费；观察适配器继续拒绝跨窗口单位变化。量活跃度对显式unknown日输出null并重新积累同单位预热，原量字段保持可核。既有未带单位字段的归档保持原来源口径。本规则不改账户、执行和标准MarketBar准入。
