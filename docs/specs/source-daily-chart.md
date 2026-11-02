# 来源日线图表

类型：功能规格。状态：accepted。范围：模块C沿A的[DSH4](qmt-source-daily-history.md#dsh4-统一公开查询与目录)接通只读日线及自然周/月投影；策略执行准入独立验收。

## 调用与职责

沿既有`GET /v1/ui/market/chart/{symbol}`、BoundedReader和绝对请求截止调用SDK0.14的source_daily_history_query。显式source语义连接支持`period=1d|1w|1mo`；canonical分钟连接保持既有1m/5m合同。`limit=1..2000`表示返回周期根数，日线省略时默认为60，分钟省略时默认为240。周/月可用`daily_limit=1..2000`先选最近N根真实日线再聚合；`years>=1`按最后实际来源日回溯公历年，适用于日/周/月，并与daily_limit互斥。证券、带时区before和响应容量沿现有图表边界；日线查询上界取before与本次观察日期较早者，使用上海交易日期YYYYMMDD。历史起点沿原生2004-01-01。每次查询只读，来源缺口保持实际状态。

## 图表合同

日线读取兼容SDK0.16已核的公开指数提供者BaoStock、Tencent、CSI及分段组合Mixed，原Qmt/Tdx身份保持。图表仅转交SDK核验后的来源、集合内容身份及未知单位；公开提供者扩展仅适用于来源日期日线，原分钟和快照合同保持。复合来源的逐段提供者、原件身份及数值资格由SDK与数据侧归档持有，不能统一标成QMT。来源单位unknown继续unknown。

日线采用schema1.6、period/source_period=1d、derived=false，source_bar_count为返回条数。周/月采用schema1.8、period=1w或1mo、source_period=1d、derived=true，source_bar_count记录实际参与本次聚合的日线根数。自然周按ISO周分组，自然月按公历年月分组；每组open取首根、high取最大、low取最小、close取末根、volume求和，标签使用该组最后一个实际交易日。首尾不完整周期按实际覆盖保留，不生成缺失交易日。native_source明确value_semantics=source、timestamp_semantics=source_date、chart_minute_boundary=source_date、source_minute_boundary=unknown，保留provider、dataset_version、content_id、qualification、coverage=Unknown、timezone、原价/量/额单位。沿原date逐日构造上海00:00的标签再以UTC传输；as_of表示末条来源日期标签，用户界面显示最新交易日，实际闭合/可获知时间归内部诊断与策略准入。源status非Ok、身份/周期/顺序/数量/时间/非有限值/OHLC范围错误、未知响应和来源断开均返回去敏中文不可用结果；期间无旧图或旧末日期。

1.4 canonical分钟和1.5 source分钟保持各自时间边界；1.6绑定日线来源语义；1.8绑定日线来源及自然周期派生语义。日线原metadata period、source_date、selection与请求一致；空missing_dates不证明完整日历覆盖。金额单位原metadata保留，现有图表仍只展示OHLC与成交量。

## 页面与验证

行情页提供统一搜索、自选、主动刷新、日/周/月周期及交易日/公历年范围，交互沿[行情工作区](../modules/observer-market-workspace.md)。带时区截止查询继续由公开API支持。来源日期按Asia/Shanghai显示，浏览器其他时区保持同一交易日。单位与缺失提示沿[面向用户的行情说明](source-history-chart-observation.md#hco-r3-用户说明)，内部来源身份保留在接口。策略详情与资金事实沿独立策略投影读取。

验收：正式HTTP/SDK参数与1.6/1.8投影、分钟兼容、空/错误/恢复、请求截止与关闭；实际目标证券分别读取60/5根日线，周/月逐字段对照同一批日线，另覆盖ETF或指数；年份窗口按末来源日计算。新App/SPA及锁、固定依赖来源分别登记，全部运行资源有界收束。
