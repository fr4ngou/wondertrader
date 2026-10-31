# 策略分析窗口的共享内存来源

类型：功能最终规格。状态：accepted / in-progress。前缀：QAS。范围：外部 WT 分析窗口生产者读取 QMT 日线及原生复权事件，沿现有认证共享内存和原策略线程执行。

## QAS-R1 来源与复用

显式只读 profile `qmt.read-profile.v7` 增加 `market.market_data`、`market.divid_factors`，策略来源提供者按已配置证券查询。默认旧 profile、分钟、账户和交易路径保持原行为。v7 不含交易或下载；缺缓存由历史准备模块负责，读取不假报下载成功。

SDK 调用依据[迅投内置行情文档](https://dict.thinktrader.net/innerApi/data_function.html)（核对日期 2026-10-30）：日线使用 ContextInfo.get_market_data_ex，period=1d、fill_data=False、subscribe=False；原生因子使用 ContextInfo.get_divid_factors(symbol)。不导入 xtquant，不在 QMT 内打开文件或网络，不增加 SDK 工作线程。Host 和 Agent 沿同一 read_capabilities 校验，固定 SDK callable 仅由原策略线程调用。

v7 配对要求 builtin-shm。现有配对生成器和 verify 使用同一闭包选择，将原策略 timer 驱动的单代或常驻只读 Agent 放入内存正文，登记一次 100 毫秒 timer；默认旧 profile 的正文及加载路径保持。没有单独的 SDK 线程、QMT 文件配置或终端内 HTTP 服务。

## QAS-R2 请求与原值

两操作继续使用原八字段请求、原同机预算、原结果封装及绑定。policy 分别为 `qmt.daily-read.v1`、`qmt.factor-read.v1`，版本均为 1.0。

日线 arguments 精确为 symbol、start_date、end_date、max_rows、adjustment；证券为来源支持的六位 SH/SZ 代码，日期为八位上海日期，adjustment 为 none 或 front_ratio。start≤end≤当前上海日期；日期范围和返回行数沿显式部署额度。SDK 使用 time/OHLC/volume/amount 七字段，以 max_rows+1 检测截断；超额要求调用方分段，不把部分窗口当作完整结果。结果 data 保持 `{symbol: {YYYYMMDD: {open,high,low,close,volume,amount}}}`，日期来自实际 SDK time 字段，数值只做有限类型转换，不计算复权、不填停牌或缺日、不更改量额单位。

因子 arguments 精确为 symbol。data 保留 `{时间戳字符串: 七列原生数值}`，第七列严格为正；原空映射保持为空，其含义不升级为来源确认无除权。事件范围不由运输层裁切，基准选择及累计由原 QNA 负责。

日线 limits 为 schema_version=qmt.daily-history.v1、max_calendar_days（1..40000）、max_rows（1..20000）、max_data_bytes；因子 limits 为 schema_version=qmt.divid-factors.v1、max_events（1..4096）、max_data_bytes。字节额度受原 max_result_bytes 约束。它们管理单次资源，固定八证券由唯一策略配置拥有，读能力不增加证券白名单。

## QAS-R3 时间、生命周期与验收

结果沿原 request/result identity、SDK 实际执行区间和 source binding 保存。收到时间、窗口生成时间及日线日期分列，历史数据的首次可知时间保持实际未知。当前日是否已经闭合由窗口生产者按实际交易时段判断，日线读取成功不授予闭合资格。front_ratio 的实际基准由 QNA 原生读回和参考比对核实，运输层不重标价格。

一次读取从准入、SDK、遍历至编码共用原绝对截止。SDK 本身不可抢占，晚回沿原终态记录；Host 重启及未知请求按原身份核查。服务常驻与单项请求截止分别管理。

先验证 Host → 认证 WinSHM → 原策略线程 SDK 替身 → 原结果 → 外部来源提供者的日线和因子主链，并接原 Import/Reader/QNA 发布及消费者。随后核默认旧 profile、缓存空结果、日期/容量/原截止、原线程、同日修订与正常关闭。真实 QMT 和普通安装按实际制品另验；本规格不授真实交易或生产发布资格。
