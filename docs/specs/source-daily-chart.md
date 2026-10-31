# 来源日线图表

类型：功能规格。状态：accepted。范围：模块C沿A的[DSH4](qmt-source-daily-history.md#dsh4-统一公开查询与目录)接通只读日线；策略执行准入独立验收。

## 调用与职责

沿既有`GET /v1/ui/market/chart/{symbol}?period=1d`、BoundedReader和绝对请求截止调用SDK0.14的source_daily_history_query。显式source语义连接支持日线资料展示；canonical分钟连接保持既有1m/5m合同。证券、limit1..2000、带时区before和响应容量沿现有图表边界；日线查询上界取before与本次观察日期较早者，使用上海交易日期YYYYMMDD，不宣称查询时已经闭合或可获知。历史起点沿原生2004-01-01。每次查询只读，不下载或补造行情。

## 图表合同

日线采用schema1.6、period/source_period=1d、derived=false，source_bar_count为返回条数。native_source明确value_semantics=source、timestamp_semantics=source_date、chart_minute_boundary=source_date、source_minute_boundary=unknown，保留provider、dataset_version、content_id、qualification、coverage=Unknown、timezone、原价/量/额单位。沿原date逐日构造上海00:00的标签再以UTC传输；as_of表示末条来源日期标签，用户界面显示最新交易日，实际闭合/可获知时间待核归内部诊断与策略准入。量价保持原值；原日线直接读取，与分钟聚合分别表达。源status非Ok、身份/周期/顺序/数量/时间/非有限值/OHLC范围错误、未知响应和来源断开均返回去敏中文不可用结果；期间无旧图或旧末日期。

1.4 canonical分钟和1.5 source分钟保持各自时间边界；1.6必须绑定日线来源语义。日线原metadata period、source_date、selection与请求一致；空missing_dates不证明完整日历覆盖。金额单位原metadata保留，现有图表仍只展示OHLC与成交量。

## 页面与验证

行情页增加日线周期按钮，沿原证券输入、自选、主动刷新、截止查询及图表组件复用。来源日期按Asia/Shanghai显示，浏览器其他时区也保持同一交易日。单位与实际缺失提示沿[面向用户的行情说明](source-history-chart-observation.md#hco-r3-用户说明)，内部来源身份保留在接口。策略目录仍沿用户要求只展示名称/简介/版本。

验收：正式HTTP/SDK参数与1.6投影、分钟兼容、空/错误/恢复、请求截止与关闭；实际固定039数据组件+042 SDK+9ETF原值→App/生产SPA，逐字段及来源日期对照A原件；浏览器周期切换、截止、窄屏与停止隐藏旧值。新App/SPA及锁、固定依赖来源分别登记，全部运行资源有界收束。
