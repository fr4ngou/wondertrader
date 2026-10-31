# 权威交易所分钟计划消费

类型：功能最终规格。状态：accepted。保持完整历史/业务适配目标；本规格负责 WT 独立消费者和跨发行调用链。生产者权威规范为观衡 `docs/specs/market-minute-calendar-projection.md`，公开 DTO 在 `qmt_platform.common.market_calendar`。当前开发生产者位于 E: 独立服务适配工作树，主工作树保持源码不变。

## CAL-R1 公开契约与唯一事实

SDK 通过 POST /v1/market/calendar/minutes/query 读取原 MarketData 日历 owner，X-Internal-Token 从部署配置注入；生产运行不导入 QMT/Portfolio 或数据库。schema_version 分别 guanheng.calendar.query.v1 / guanheng.calendar.minutes.v1；请求显式 symbol、calendar_version、start_date、end_date、as_of，日期区间1..3天。响应字段、大小512KiB上限、SHA和事实来源依照生产者公开 DTO。

source calendar_version 与 projection_version=cn-a-share-continuous-right-1m-v1 的规范对象 SHA 派生 cal-min1-v1-<64hex>，用作 HistoryBinding.calendar_version。时间投影是连续竞价窗口每分钟右端、午休剔除和<=as_of的闭合点。SDK只消费/验证该计划，交易日、会话和假期规则继续由原 owner 唯一生成。

## CAL-R2 保守覆盖与空段

response scope=exchange_plan/security_exclusions=not_applied，客户端要求精确这些枚举并保存原证据。历史停牌和上市/退市排除仍待权威事实；缺 bar 继续 Gaps/Pending，不推断排除。满计划网格存在时可验证该网格覆盖；该计划不授真实市场来源资格。权威空段须完整两市场闭市事实与已结束范围；开市前尚无闭合分钟的空网格保持false并由runner返回Pending。

## CAL-R3 传输、验证与证据

新增标准库 `guanheng_market_client.history_calendar.CalendarProjectionProvider`，注入 base_url/token、原 calendar_version 与既有 EvidenceSink。提供 `calendar_binding_version(source_version)` 和 CalendarProvider.minutes(...)；返回既有 CalendarSlice。timeout为该复合调用声明的总秒预算，1..30；http_timeout<=timeout。整个HTTP交换、解析/规范校验、证据put/get必须在该单调截止内，启动有界调用前核剩余可容纳其完整上界，完成后再核截止。任意阻塞依赖的硬停止继续由外部监督承担。

仅受管TLS或字面回环HTTP，不使用代理/重定向/自动重试；请求/响应有限额，异常与非2xx固定去敏。校验严格字段、证券/区间/as_of身份、源/投影/派生版本、时间/日期/排序/重复/bool整数、完整两市场事实及其源时间，facts_sha256与响应sha256。SHA均为规范JSON而非传输格式。拒绝非有限值/重复JSON键。失败前不写证据；已验证响应规范内容按其完整字节SHA写/读既有sink，返回稳定evidence_ref。响应sha256排除自身，存储SHA包含完整响应，两种摘要分别命名。

## CAL-R4 完整历史链

部署工厂显式将 provider 与同一 EvidenceSink 注入既有HistoryRunner，按派生日历版本形成binding/dataset。消费流程读取原日历owner→存证→query原生DSB/缺口→定向准备/work/回读→不可变segment/result→原Operations CAS。日历503/损坏/版本漂移不得触发市场prepare或确认；恢复后同一作业可继续。已有确认回查同一日历/证据，不改写确认。

## CAL-R5 独立发行与验证

新history_calendar纳入显式SDK源码清单与0.5.0发行，基础客户端保持标准库，HES storage extra不变。覆盖独立客户端的错误/空/恢复/截止与泄漏回归；真实HTTP跨进程使用当前实际原producer/FactStore/共享会话模块及原Operations纯归约器，工作进程只装wheel不导入私有包。验证开市整240分钟、午休/右端/as_of、闭市零bar确认、缺事实/未来/错误版本/篡改/体积及回复异常。原converter兼容回归与生产路由由原项目规则单独验收。原生包搬迁后安装同wheel再验，无源权限时明确拒绝而不skip伪过。

## CAL-R6 发布资格与实施归属

原服务改动独立分支/独立发布；当前只做隔离开发，不切换生产或合入原主树。真实日历入库/十年覆盖、历史证券排除、可达端点和对象ACL/保留/resolver、原日线family保护、真实业务页面仍按全量验收地图推进。共享内存与TDX交易暂缓。

主Agent维护公共规格/DTO、跨仓联调、发行/源码身份与文档；生产者Agent只维护独立观衡工作树的store、共享会话提取、MarketData路由与测试；SDK Agent只维护history_calendar与独立测试。公共契约先冻结，模块路径分工，独立full/delta审查与最终制品绑定源码。
