# 指数观察背景更新

类型：模块说明。所有者：观衡独立市场观察。范围：`wondertrader.indices`来源及其已有指数背景消费，合同沿[OBI5](../specs/independent-market-observation.md#obi5-独立采集与来源)。WT统一历史继续拥有原始行情，本模块只读其公开SDK。

## 调用链及字段职责

原独立更新owner→`collection.refresh`→`wondertrader_source.history`→`MarketClient.source_daily_history_query`→原WT历史Reader。每729自然日查询最多2000根，原响应先存内容对象；请求、字节和原总截止保持。原8表输出、原单批次采集lease、修订记录和CAS发布继续唯一拥有更新。

来源配置的tables/datasets决定写入归属。`market.sh000001`在源表及广度只读投影中同名，更新先读取和写回配置声明的源表，再由原`attach_benchmark`更新投影；源表和投影的生命周期与谱系各自保持。

七张`market.*`表消费OHLC与原成交量，保留price原值、provider_volume及其原单位。完整旧日期覆盖后才替换当次截止范围，已接纳更晚行保持；缺失旧日期或量单位变化保留原批次失败，unknown单位继续使量活跃度为空。

`source.csi_all`只供`spread_and_bond`按同日中证全指收盘作参考：date为来源交易日，close为实际收盘点数，available_at为历史首次可知时间，未知时为空。适配器只投影这些字段；原生OHLC覆盖缺口不使已核官方收盘失效。`prepare_table`按日期合并实际返回与已接纳表，保留缺失旧日期及原表父对象，成功回执`retained_dates`按表ID列这些ISO日期，缺省表示没有保留缺口。保留记录继续携带旧谱系，不重标为本次新采集。

## 背景投影与日期

上证源表仍为`market.sh000001`。原`attach_sse_reference`统一更新期货、基差和估值同日参考，`attach_daily_context`维护利率与市值/GDP独立日期，`attach_benchmark`向广度页提供统一指数基准。原System C日/周及港A比较沿同一既有模型。主指标、参考线和来源时点分别保留原方法；来源覆盖外的已核旧参考保持，缺日期不跨日补值。

本模块维护消费侧字段准入，原生日线OHLC合同、WT框架、源端采集、其它观察来源及部署生命周期保持各自owner。将仅收盘的旧行补造为OHLC或将unknown量额换成真实单位均超出合同。

## 构建与接收

源码接缝为`apps/guanheng/guanheng_app/observation/wondertrader_source.py`及`collection.py`。按[永久源码构建](../runbooks/observer-source.md)和原更新角色安装闭包接收；Web继续只读已发布目录。新版本先在E盘隔离根运行原刷新和发布，再核原API、图表字段与历史日期。现场current变化时由Root在最新快照重放该来源，保持其它来源后继结果。

实际18148、隔离发布、背景对齐与未支持范围见[本次证据](../evidence/2026-11-03-observation-index-background.md)。该模块修复现行自动更新入口，真实采集缺项继续按原来源资格展示。
