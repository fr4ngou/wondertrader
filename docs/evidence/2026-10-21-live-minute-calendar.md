# 2026-10-21 真实分钟计划公开接线核实

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：只读现场验证证据。状态：completed（调查完成；分钟计划接线及证券历史排除仍待交付）。范围为 2026-10-20 的 300308.SZ、688076.SH，观察时间 2026-10-21 17:49–17:52 Asia/Shanghai。

## 输入与步骤

使用本地 `D:/workspace/qmt/.venv/Scripts/python.exe -B` 运行源码确认后的有界 HTTP 只读探测，单请求上限 15 秒；凭证从受管配置读入内存，证据不含凭证。原 QMT、运行终端和共享源码保持原样；本轮没有下载、数据库直读、账户或委托操作。

运行 MarketData 部署 commit 为 `9374ef231ea921ad6074240e079574f285291694`，release root SHA 为 `f53b52ad6d21cceb72dfa78fb67614fe14f110c58e68412b01508d6a485501c3`。14 个源码/脚本输入 SHA 见本地 输入身份（外部历史/待归仓路径：`../../build/native/calendar-live-audit/source-identities.json`），有界调用脚本见 公开路由探测（外部历史/待归仓路径：`../../build/native/calendar-live-audit/probe_public_routes.py`） 与 日布尔观察（外部历史/待归仓路径：`../../build/native/calendar-live-audit/probe_observation.py`）。这些文件为本机证据，迁移时须另行保留。

## 实际结果

两个探测进程退出码均为 0。完整回包与 HTTP wire SHA 见 现场摘要（外部历史/待归仓路径：`../../build/native/calendar-live-audit/run-dd9766acddd14323b1cb8df54d000fef/summary.json`）。落盘 JSON 经格式化，文件摘要与原始 wire 摘要可不同。

| 公开入口 | 实际观察 | 资格边界 |
|---|---|---|
| MarketData `GET /openapi.json` | 200；日历仅列出写入路由 `/v1/market/calendar` | 分钟投影未挂载 |
| MarketData `POST /v1/market/calendar/minutes/query` | 两证券均 404 | 候选只读分钟路由尚未发布 |
| Bridge `GET /v1/internal/trading-calendar/observation?trade_date=2026-10-20` | 200；SH=true、SZ=true、state=open、trading_authority=false | 日布尔观察缺少明确版本、来源、时段和证券排除 |
| Bridge 只读 `market.trading_dates`，日周期、当天、count=5 | 两证券均返回 `["20261020"]` | 确认日历日期，不提供完整历史分钟资格 |
| Gateway capabilities | trading_dates、is_suspended_stock、instrument_detail、his_st_data 均 implemented=true、mutating=false | 能力存在，其语义仍由适配参数约束 |

日布尔回包（外部历史/待归仓路径：`../../build/native/calendar-live-audit/bridge-observation.json`） wire SHA：`fc71eb2c55cd2281f1ce75728f4748b1c760e96016642dbb3abdccdc6181c2b6`。

## 源码依据与事实所有权

原 `D:/workspace/qmt/qmt_agent/broker/adapters.py` 的 `market.is_suspended_stock` 仅接收 stockcode，没有历史日期/as_of；`market.his_st_data` 属历史 ST 信息。本轮没有将当前停牌值或 ST 信息当作历史停牌证明。原 Bridge `services/bridge/app.py` 的 `trading_calendar_observation` 读取保存的日布尔，`services/bridge/store.py` 的 `trading_date_state` 在版本冲突时返回未知；该响应仍不足以替代带版本和 provenance 的分钟计划。

候选 `E:/workspace/qmt-worktrees/wondertrader-service-adapters/src/qmt_platform/services/market_data/calendar_projection.py` 已定义分钟查询，要求明确版本、完整 SH/SZ 原始事实及来源证据，输出事实/内容 hash。其输出明确 `scope=exchange_plan`、`security_exclusions=not_applied`；请求携带证券代码不会自动赋予证券历史停牌/上市排除资格。原年度闭市配置存在，也不能替代运行时同版本完整事实的公开验证。

WT [CalendarProjectionProvider](../../integrations/guanheng_market_client/history_calendar.py) 已有只读消费契约；真实接线需要 MarketData 发布该入口、核实原始事实，再由 WT 配置受管 source calendar version 与 evidence owner。诊断用 240 网格继续保留非权威标识。

## 剩余证据与下一责任

既有真实历史共 428 根，对诊断参考网格缺 1/51 分钟。1m 与 5m 聚合一致证明数值聚合一致；缺口具体来源仍未证实，当前保留 Gaps。权威交易所计划接入后仍须保留 `security_exclusions=not_applied`，直到历史证券资格所有者提供有来源和有效区间的排除事实，或数据来源所有者提供可验证的分钟生成语义。

下一责任分别为：MarketData 按受控发布流程提供权威交易所投影；WT 消费已有 CalendarProjectionProvider；历史证券/来源所有者解释缺口资格。源稀疏行数不能反向定义应有分钟，亦不能将覆盖升级为 Complete。本轮完成只读调查，发布和完整分钟资格未验收。
