# 权威日历与分钟网格接缝调查

实施更新（2026-10-21）：下文保持调查时原主树的能力快照。现已在独立观衡分支实现精确版本的分钟计划路由与共享会话转换，并由 SDK 0.5.0 串联真实 HTTP/DSB/Operations 验证；[CAL 证据](../evidence/2026-10-21-history-calendar.md)和[最终规格](../specs/history-calendar-projection.md)登记当前结果。原主树尚未合入，实际多年覆盖、历史证券排除及生产资格继续待验。

调查基线：2026-10-21；只读 `D:/workspace/qmt`，HEAD `3a2f97cbeb0127747f5f8d3cef5f8a3c467420ff`。下列结论核对当前源码与配置；没有请求运行端点、检查线上数据、运行服务/账户、读取凭证或运行 Ninja。本次仅新增此报告。

结论：现有 owner 已具备带版本的逐日交易日历、冻结归档，以及可通过 HTTP 下载的官方日历原件和规范日级资产。当前公开契约尚不能直接给 WT 提供按证券、指定 as_of 已闭合的权威分钟网格及历史停牌覆盖证明。可复用原 owner 的事实校验与证据链，补充只读投影契约后再接入 `CalendarProvider`。

## WT 消费契约

- HSA-R5 (`WT docs/specs/history-lifecycle-and-service-adapters.md:38`) 要求权威 calendar provider、binding 中的 calendar_version 和受管 evidence sink；禁止工作日近似日历。日历空段须明确 `authoritative_empty=true`、相同版本和 evidence_ref，且整个日期范围已在 job.as_of 前结束。
- CalendarSlice/CalendarProvider (`WT integrations/guanheng_market_client/history_runner.py:87`)：`CalendarSlice(version: str, expected_minutes: tuple[int,...], authoritative_empty=False, evidence_ref="")`；调用 `minutes(symbol, start_date, end_date, as_of)`。分钟为 Asia/Shanghai 右端 `YYYYMMDDHHMM`。
- runner._calendar (`WT integrations/guanheng_market_client/history_runner.py:369`) 核对版本、最多5000条、严格整数、升序唯一、日期范围及 minute<=as_of；空段另核整段闭合与证据。SDK 不拥有交易会话或证券停牌事实，调用者不能用缺 bar 推断休市/停牌。

## 现有 owner 与公开接缝

| 事实/接缝 | 当前真实契约与入口 | 对 CalendarSlice 的适用范围 |
|---|---|---|
| Market Data 逐日日历 | TradingCalendarEvent (`QMT src/qmt_platform/common/contracts.py:1802`)：market=`SH|SZ`、trade_date、is_trading_day、open_at/close_at、calendar_version、source_id、source_url、source_retrieved_at、evidence_refs。来源URL/获取时间成对，闭市日禁止时段。 | 可作逐日事实；没有午休分段、证券、停牌区间、分钟边界/网格、区间覆盖/内容摘要字段。DTO允许默认 `source_id=unversioned`，消费方还须复用更强 owner 校验。 |
| 日历写入/事实不可变 | POST /v1/market/calendar (`QMT src/qmt_platform/services/market_data/app.py:847`)，X-Internal-Token；数据库主键 (`QMT infra/postgres/migrations/0002_research_and_replay_facts.sql:30`) 为 market/date/version；save exact (`QMT src/qmt_platform/common/fact_store.py:866`) 同键完整JSON相同幂等，漂移冲突。 | 当前没有对应 GET 日历范围或分钟网格路由；POST不能作为读取适配器。 |
| 官方年度输入 | official_sources.build_exchange_calendar (`QMT src/qmt_platform/services/market_data/official_sources.py:258`) 用版本化官方休市配置生成全年沪深逐日事实、09:30/15:00开闭市与来源证据；返回规范证据SHA。多年合并拒绝重叠/版本重复。 | owner现有生成逻辑可复用，WT不重新实现 weekday/holiday推断。仓库年度配置为2023—2026；不证明十年覆盖。 |
| 当前2026年日历配置 | trading-calendar-closures-2026.json (`QMT config/trading-calendar-closures-2026.json:1`)：schema1.0、`cn-exchange-calendar-2026-v1`、SH/SZ官方URL、holiday_closures、reviewed_at。 | 具备受管年度日级依据；源码检查不等于本次重新验证官方网页或线上已导入。 |
| 冻结整包/manifest | MarketDataDatasetManifest/ImportBundle (`QMT src/qmt_platform/common/contracts.py:10743`)：dataset/version/source_kind/source_ref/object_ref/sha256/symbols/periods/计数/frozen/retrieved_at；整包含metadata/calendar/bars及可选QMT捕获/派生证明。 | 原生含日历的冻结数据载体，不能仅凭manifest计数授予整个请求区间或每分钟覆盖。 |
| manifest/quality HTTP | GET /v1/market/imports/{dataset_version} 与 /quality (`QMT src/qmt_platform/services/market_data/app.py:749`)，X-Internal-Token，缺失404。 | 返回登记和质量；当前MarketData路由未提供整包下载或版本指定日历范围读取。 |
| Bridge启动观察 | GET /v1/internal/trading-calendar/observation?trade_date=... (`QMT src/qmt_platform/services/bridge/app.py:484`)，X-Internal-Token；DTO (`QMT src/qmt_platform/common/contracts.py:1728`)：schema1.0、date、SH/SZ布尔或null、open/closed/unavailable、trading_authority=false。 | 只可启动诊断；没有版本、区间完整性、原件或分钟网格，不能独立充当CalendarSlice证据。 |
| Portfolio会话转换 | calendar_from_events (`QMT src/qmt_platform/services/portfolio/replenishment_calendar.py:9`) 校验精确版本、SH/SZ每日完整一致、来源非unversioned、获取时间<=now、证据与09:30/15:00时点；continuous生成09:30—11:30、13:00—15:00；另有策略允许的盘后时段。 | 最接近原owner的午休/来源校验接缝。它服务执行政策，尚未发行成行情分钟网格DTO；不能把其盘后执行窗口自动纳入WT的1m行情。 |
| 内部窗口证据 | TradingCalendarEvidence/TradingWindow (`QMT src/qmt_platform/common/replenishment.py:249`)：calendar_id/version/published_at/coverage_start/end/windows/evidence_refs，窗口含opens_at/closes_at/session。由repository.load_calendar (`QMT src/qmt_platform/services/portfolio/replenishment_store.py:1030`)按版本读DB再调用原转换。 | 可推动原owner公开有界只读投影；现有对象无证券历史停牌、分钟闭合边界或内容摘要字段，也未找到独立GET暴露此对象。 |

X-Internal-Token 的服务校验在 auth.py (`QMT src/qmt_platform/common/auth.py:8`)。本次只读鉴权代码，未读取任何配置值。

## 两条对象存储证据链

### Market Data 冻结包

archive.py (`QMT src/qmt_platform/services/market_data/archive.py:18`) 仅接受 `minio://replay-datasets/<object-name>`，路径校验禁止空段/穿越等。归档上限50MiB；archive/verify (`QMT src/qmt_platform/services/market_data/archive.py:115`) 同对象内容不同即拒绝，写后回读并解析/比对完整bundle。日历派生绑定父dataset、父对象、QMT捕获与bars，并保持metadata/bars不变。

注意两种摘要：manifest.sha256 (`QMT src/qmt_platform/services/market_data/imports.py:26`) 绑定规范metadata/calendar/bars和存在的捕获/派生字段；`verify_archived_bundle` 返回整包原字节SHA。二者不能互换，也不能替换成DSB SHA。质量校验 (`QMT src/qmt_platform/services/market_data/imports.py:299`) 检查已有bar日期对应开市日；空bars仅warning，未证明所请求区间、缺分钟或停牌。

当前复用需要原owner提供受管的整包读取/证据交付接缝，或由现有受管作业交付冻结对象；不应为了读取日历而给WT SDK授予数据库/MinIO配置权限。

### Research Data 独立市场观察资产

这条链已有可直接复用的只读资产HTTP，但事实仍是日级比较日历：

1. config/market-observation-sources.json:63 (`QMT config/market-observation-sources.json:63`) 的 `models.calendars.cn`：`id=cn.official-trading-days`，覆盖2020-07-27—2026-12-31，`verified_through=2026-10-16`，方法 `sse_szse_annual_schedule_crosschecked_provider_dates`，evidence含沪深官方原件URL、SHA、大小和获取时间。
2. official_calendar (`QMT src/qmt_platform/services/research_data/market_observation/calendars.py:7`) 校验验证截止日前开市日列表摘要；版本为配置规范内容SHA，输出仅 `{date,is_open}`。comparison固定cn→sh000001；超覆盖、已观察区间内部缺日fail-closed，缺官方配置的provider-days路径明确降级。输出metadata含coverage、verified_through、method、evidence、official_history_verified。
3. admit_calendars (`QMT src/qmt_platform/services/research_data/market_observation/calendars.py:67`) 要求原件已入库，回读SHA并核字节数；登记original和规范parquet父引用。refresh (`QMT src/qmt_platform/services/research_data/market_observation/refresh.py:223`) 后调用register_standard_assets (`QMT src/qmt_platform/services/research_data/market_observation/admission.py:123`)，使 `source.cn_official_calendar` 成为可下载资产，dataset_version=parquetSHA，asset_id另绑定内容和parents。
4. 前缀 `/v1/research-data/market-observation` (`QMT src/qmt_platform/common/market_observation.py:6`)。GET /assets (`QMT src/qmt_platform/services/research_data/market_observation/routes.py:109`) 可按snapshot分页，定位source_ref；`GET /assets/{asset_id}?snapshot_id=...&download=true` 下载登记对象，`GET /lineage/{asset_id}` 查父对象；snapshot固定后再取资产。UI router没有下载入口。未知资产404。
5. owner_routes.authorize (`QMT src/qmt_platform/services/research_data/market_observation/owner_routes.py:18`) 支持独立 `X-Observation-Read-Token`，或原内部 `X-Internal-Token`；独立app (`QMT src/qmt_platform/services/research_data/market_observation/app.py:29`) 使用前者。未配置reader时503。
6. ContentStore (`QMT src/qmt_platform/services/research_data/market_observation/storage.py:26`) 按SHA寻址，MinIO位于 `research-raw|research-evidence/market-observation/v1/objects/sha256/<sha>`；读取/镜像恢复复算SHA，缺失/损坏503。资产资格 `verified_content` 证明受管内容完整性，不等于WT `ProductionQualified`。

这里只核实源码发布链；线上当前snapshot是否已有对应原件/规范资产、读令牌是否配置及运行可达性均未核实。2026-10-16之后 `official_history_verified` 的降级分支必须保留，不能把年度计划覆盖和历史逐日核验混为一项资格。

## Gateway 日历/停牌操作的能力边界

原操作注册表 (`QMT docs/contracts/qmt-gateway-operations.json:36`) 注册只读 `market.trading_dates`，同表52注册 `market.is_suspended_stock`；Broker adapters (`QMT qmt_agent/broker/adapters.py:443`) 确有实现映射：

- `market.trading_dates` → `get_trading_dates(stockcode,start_date="",end_date="",count=500,period="1d")`。
- market.is_suspended_stock (`QMT qmt_agent/broker/adapters.py:505`) → `is_suspended_stock(stockcode)`，没有历史区间参数。
- Gateway HTTP (`QMT qmt_agent/gateway/http.py:138`) 为 `POST /internal/v1/operations/{operation_id}`，鉴权使用原HMAC请求头 (`QMT qmt_agent/gateway/auth.py:22`)：key-id、timestamp、nonce、content-SHA256、signature。HTTP Handler排队交原owner执行，能力登记不代表运行时实际实现已资格。
- 原平台的Bridge代理入口 (`QMT src/qmt_platform/services/bridge/app.py:869`) 为 `POST /v1/internal/qmt/operations/{operation_id}`，X-Internal-Token及同一Request/Result DTO；校验path/body动作一致、normal priority，市场读取交market coordinator，受限历史读取另交history coordinator。此既有代理也不补充日历语义字段。
- GatewayOperationRequest/Result (`QMT src/qmt_platform/common/contracts.py:3821`) 有请求身份、operation、arguments、timeout/policy；返回ok/completed_at/result_sha256，但 `data: Any`。注册表和adapter未给出历史交易日结果的版本化行schema、完整覆盖、午休/分钟边界或停牌生效区间证据。

因此这些操作可作为后续原owner采集原料；当前停牌布尔不能回溯历史，`get_his_st_data` 的ST属性也不能解释为停牌。WT市场v1没有任意操作透传；本次不扩接口、不调用上述操作。源码src及qmt_agent范围内未找到证券历史停复牌区间的独立DTO/存储/HTTP读取契约。

## 可继续确定的接线与必要缺项

1. **证据资产消费**：后续accepted规格可让独立适配器使用现有observation读API，固定snapshot/asset_id，校验下载SHA/大小与parent lineage，保留原owner的coverage/verified_through/method。只安装WT wheel并通过HTTP消费，保持QMT源码路径与私有业务包在运行依赖之外。当前日级资产不能直接授予分钟Complete。
2. **分钟owner投影**：由原日历owner公开有界、版本固定的只读会话/分钟投影或受管冻结证据包，复用其日历来源/冲突/覆盖校验。需明确market/symbol映射、period=1m、右端闭合点、午休/集合竞价/盘后范围、as_of时点、发布/修订版本、完整区间及证据摘要。适配器只把已验证owner结果转成CalendarSlice，不复制执行政策与日历生成规则。
3. **证券覆盖**：owner须明确所请求证券的上市/退市有效范围、历史停牌区间及“不停牌/无例外”的完整证明；缺证据时保留Unavailable/Pending或缺口。交易日、零成交、缺bar和停牌是不同事实，不能互相代替。也可提供保守交易所计划网格，但必须明确它不能证明证券缺bar合理或完成。
4. **空段**：只有明确覆盖整个已结束日期段的闭市/证券排除证据才能返回authoritative_empty和受管evidence_ref；不存在对象、空列表、provider缺数据、超覆盖、版本不符均不能确认零bars。当前Bridge单日closed观察缺版本/原件，不能独立满足此条件。
5. **十年范围**：当前查到2023—2026年度事实配置与2020-07-27起的observation官方比较资产。更早年度、全证券停牌/上市沿革和实机完整覆盖仍是独立缺项，不能用重复分窗代替来源覆盖资格。

## 验证入口与本次证据等级

本次为源码/配置只读调查，未运行以下测试。后续实现应复用既有owner测试与原始样本，并增加adapter异常/空状态回归：

- tests/phase12/test_official_market_sources.py (`QMT tests/phase12/test_official_market_sources.py:159`)：全年沪深日历、固定取得时间摘要、多年合并及重复拒绝。
- tests/phase4/test_market_data_import_api.py (`QMT tests/phase4/test_market_data_import_api.py:294`)：幂等、冲突无部分写、摘要/归档不一致、capture回读及不可覆盖；同目录quality测试覆盖闭市bar等。
- tests/phase38/test_market_evidence.py (`QMT tests/phase38/test_market_evidence.py:33`)：缺半市场或未知交易时段拒绝；tests/test_bridge.py (`QMT tests/test_bridge.py:52`)：启动日历open/closed/missing/disagreement。
- tests/phase40/test_observation_official_calendars.py (`QMT tests/phase40/test_observation_official_calendars.py:17`)：官方日级日历/半日仍开市、规则摘要漂移、缺价格日、超覆盖、原件缺失和parents；test_market_observation.py (`QMT tests/phase40/test_market_observation.py:227`)：读鉴权、空范围、snapshot篡改、镜像恢复/损坏、资产分页。
- 新适配器需覆盖迟于as_of的分钟/来源、午休/端点偏一、版本漂移、原件/parent缺失、不同snapshot混用、停牌未知、闭市空段和日历服务恢复；真实数据资格须另做受管HTTP/对象回读验真。

QMT工具入口边界：`scripts/development_workflow.py:7307`的lookup及start/read会保存session记录；`scripts/doc_navigation.py:272`的导航也可能生成磁盘索引。此次为保持QMT只读，读取入口、相关组件正文及源码，未运行写记录CLI，也未读取历史报告。

## 本轮核实文件身份

以下QMT文件在调查结束时相对HEAD无dirty标记；SHA256绑定本次源码事实，不代表线上部署身份：

| QMT相对路径 | SHA256 |
|---|---|
| src/qmt_platform/common/contracts.py | `9b91b25fb5f751beee44cfaf146f00b7b1678488893da79f91682fdf3de22b34` |
| src/qmt_platform/services/market_data/official_sources.py | `14baaa899ae94852db292f5e612878ccbc0e75d254503660f4f4ce3e1b44db45` |
| src/qmt_platform/services/market_data/app.py | `9e4e8da96ab7b473ec29d76ad145a4954a464b8aa2c22a98bc886cc2c65df880` |
| src/qmt_platform/services/portfolio/replenishment_calendar.py | `4dea2491a322c84f8279a9d3130199ed13b2888160a138417f6470f907af8851` |
| src/qmt_platform/common/replenishment.py | `c60262df96b4ba9f633ad076606f74b042b8b65c60fff0276546d450991fcff8` |
| src/qmt_platform/services/research_data/market_observation/calendars.py | `c6afcf48b7403c2b99bc99c54d0035ab25b86c0ee66e11d832d599d165e92d9a` |
| src/qmt_platform/services/research_data/market_observation/routes.py | `4f9505cc65ce3830956244d60d051577f5a61c9ba9bf57d56044c91ef14b45b4` |
| qmt_agent/broker/adapters.py | `247577abdb2fc685bffd13cb4702e2e68d0f6a1de42d300ad600802307fcb573` |
| docs/contracts/qmt-gateway-operations.json | `e137334106a4eedbb6ebd8760d66cc2cf2f05484e54fea9ac527b47d9898b96c` |
| config/trading-calendar-closures-2026.json | `2106fb44406f6e1c7936980d154a4161db01b3931ee6fc3b4aa8d8dbf4f678bf` |
| config/market-observation-sources.json | `12a72a62f38124c1deba1ee975ba0ca89ebdfe299afd0045133a4ec3acb5e46c` |
