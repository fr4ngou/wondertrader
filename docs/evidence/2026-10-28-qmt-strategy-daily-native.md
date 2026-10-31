# 首真实策略9ETF源日线与原生存储

日期：2026-10-28。范围：[DSH最终规格](../specs/qmt-source-daily-history.md)，[模块B精确日线需求](../migration/module-b-delivery.md)。真实源窗口、原Helper/day DSB、安装Reader完整回读通过；SDK/HTTP日线公开接入、来源补齐和标准化继续。

## 根因与实现

已导入分钟历史不等于首策略所需完整日线；分钟缓存中ETF历史较短，直接聚合会产生不完整日线。外部只读使用国信已安装qmt_api.getMarketData(period=1d, dividendType=none)取得现成日线，无订阅、下载、策略编辑、账户操作或交易调用。参数count=2000按券商已安装手册第53页“count和end_time为结束点计数”语义取尾部，再在客户端按2021-11-01..2026-10-27过滤；保留全部原返回及其SHA。

原返回日期为YYYYMMDD字符串。首轮误调用毫秒时间转换触发重复报错，受控器在65536字节上限结束该作业，树/EOF/join/资源关闭；002按原日期解析后的026只读作业0.656秒exit0并正常回收。该失败未记为来源失败或覆盖成功。

自有QMI导入/Reader增加显式schema3源日线，复用原Helper的d周期、day DSB及同一文件ABI类型23，不修改WT框架。来源日期保留00:00，原值及单位unknown保留；canonical日线的原15:00合同和v1/v2分钟路径保持。日期标签自身不授历史可获知时刻、完整闭合或实盘资格。

## 真实窗口

| 证券 | 记录数 | 首交易日期 | 尾交易日期 |
|---|---:|---|---|
|510300.SH|1205|2021-11-01|2026-10-23|
|515080.SH|1149|2022-01-19|2026-10-23|
|588000.SH|937|2022-12-06|2026-10-26|
|589680.SH|384|2025-03-05|2026-09-28|
|159780.SZ|783|2023-07-26|2026-10-23|
|510050.SH|763|2023-08-23|2026-10-23|
|512100.SH|917|2023-01-04|2026-10-23|
|510500.SH|1205|2021-11-01|2026-10-23|
|589000.SH|396|2025-03-05|2026-10-23|

总计7739行。起点是实际可读缓存起点，不冒充上市日；尾部过旧及内部缺口保持待核，不默认补成完整交易日。原始数据与响应位于build/qmt-strategy-daily-source-002；manifest及CSV在build/qmt-strategy-daily-native-001。

## 实际安装与回归

候选build/source-market-package-029/GuanhengMarket.zip，147文件，SHA256 e981c0231219aa0f1ecaa4eeefff2a9cf75ce6c35ac79e12ffb750663533a711；INPUTS SHA b736cf18f3324017fbe13e9ac4db3e965a15fdba804f29a675507a9c7f16d5ce。沿原023固定原生来源重打包，原生二进制不变。

正式可复用入口tests/integration/qmt_daily_native/run.py。035使用-I -S、先核INSTALLATION全部运行文件，再导入实际安装的自有导入器/Reader：9ETF真实CSV→原Helper day DSB→成功收据/sidecar→原ABI/NativeHistory→全部7739行日期/OHLC/量额一致；5个fresh克隆分别验证错误format、schema、period、DSB类型与非零day time的具体拒绝原因。nonzero-time先聚合全部分片并核原总量，排除记录数失败冒充布局失败。1.859秒exit0，非强停、整树/EOF/join/资源关闭。成功数据根build/qmt-daily-installed-final-035/store；VERIFIED.json含安装/来源收据和实现身份。

033导入回归46项、通过41/跳过5（环境未提供的原生入口及链接权限）；034在实际安装原DLL下已有Reader9项全部通过。032同029候选经正式服务/已安装SDK完成5真实分钟样本原值、source/单位/标签对照，17.969秒exit0并正常关闭，证明本次日线扩展后的原分钟主链仍可用。早期030 QA引用错误manifest位置失败，改成实际入参后031及最终035通过，原失败原件保留。

独立full/delta源码审查生产代码无未解决P1/P2；日线坏例覆盖按审查反馈补齐。源码审查和真实运行证据分别登记，完整系统goal保持active。

## 交付与剩余

模块B可使用029安装Reader的read_source_store(root, exchange, code, expected_import_sha256=...)消费035真实day存储。A继续同版SDK/HTTP接入、最新尾部/完整日历/单位与可获知语义；B/C继续真实算法、原生回测/实时与页面整链。当前数据可以推进算法开发，量额unknown与覆盖Unknown保持，尚未授现金ETF执行或实盘资格。本轮没有真实下撤单、生产切换或未批准框架修改。
