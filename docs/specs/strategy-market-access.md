# 策略统一行情访问与闭合分钟消费

状态：accepted。前缀 SMA，类型：现有完整目标的接口与接线规格。范围沿[当前目标](../roadmap/TARGET.md)；以自有适配代码提供按需历史、自动补齐、实时快照与闭合分钟订阅，保持 WT 框架源码冻结及原业务事实 owner。

## 根因与复用边界

现有接口拆分 query/prepare/work，策略缺少一个业务入口。历史文件的 sidecar 严格绑定来源、会话及资格：QMI 导入根与在线 QMT 根不可直接混写，跨登录会话也不能仅去掉 session 比较。既有持久 Operations 作业和共享临时队列另有职责，共享任务的某消费者 release 会影响另一消费者。

本规格复用 WT DSB、原 NativeHistoryStore 和 QmtHttpEndpoint；显式组合只读档案端点与当前活动端点，保留每段谱系。为单次策略读取新增服务内有界准备，使用独立临时队列，不向客户端暴露任务，不改 Operations，不放松既有元数据一致性。

原生分钟聚合的采样 OHLCV 仍保留观察资格。本规格首期分钟订阅以源已闭合1m OHLCV经 WT 存储后的有界拉取实现，不从报价生成K线，也不宣称推送协议或行情tick无损性。后续 adapter 可沿相同业务契约提供推送传输。

## 结构与流程

```text
策略 → StrategyMarket.history_1m / quote / subscribe_minutes
       ├→ 权威 CalendarProvider
       ├→ 显式档案源 history.query → 原生DSB
       └→ 显式活动源 history.read → 本地覆盖查询
                                  → 缺口时 QMT HTTP → 私有临时Queue → 原生DSB
       → 合并校验/保留谱系 → 历史结果或订阅批次
订阅已确认批次 → 原 MarketData bar/feature consumer（历史预热与实时投递分离）
```

## SMA-R1 单次服务内历史准备

在 `guanheng.market.v1` 增加 POST `/api/market/v1/history/read`，action=`history.read`，request 与 history.query 相同，成功/错误沿原历史响应契约。旧 query/任务/报价行为保持。新增 MarketClient.history_read(request)，请求和响应均使用统一严格验证。

原生 Bridge 先查本地；Complete 直接返回，不访问 QMT。Unknown/缺网格保留 Pending且不触发来源。Gaps 时，在同一 native 调用剩余截止预算内 prepare，并用原 HistoryPreparationQueue 的私有局部实例（容量1、page/staging上限5000）推进一次。源为 QmtHttpEndpoint，单窗最多72自然小时，完整单页后才能发布；仍缺覆盖保留 Pending或原错误，不交付部分成功。严禁推进/释放 Bridge 原共享队列里的任务，调用结束局部暂存释放；无新业务账本、无持久任务。

全部查询/准备/发布共用一次截止预算；native调用按创建线程执行。网络回复丢失后，下一次读取先查持久 DSB，已覆盖则离线成功；不会泄漏一个需要客户端释放的队列身份。原生Store发布的成功/失败及来源冲突保持原义。历史渲染与query共用逻辑，避免两条不同校验规则。过长窗口/超预算在源调用前拒绝；未知或失败响应无部分 bars。

## SMA-R2 策略业务接口与来源组合

新增基础标准库模块 `guanheng_market_client.strategy_market`；SDK升级0.6.0，显式源码清单追加该模块，storage extra及基础无运行依赖边界保持。

公开构造：

```python
MarketSource(name, client, dataset_version, provider="Qmt", allow_prepare=False)
StrategyMarket(sources, calendar, calendar_version, *, clock=None,
               minimum_qualification="NativeVerified", timeout=30,
               max_bars=10000, max_windows=128)
history_1m(symbol, start, end, *, as_of=None)
quote(symbol, *, as_of=None, max_age_seconds=60)
subscribe_minutes(symbol, after)
close()
```

sources 是有序且名称唯一的显式 MarketSource 列表，最多16个、恰可零或一个 allow_prepare=True活动源；档案只调用query，活动源只在缺口时调用read。所有源provider须一致（Qmt或Tdx），防止静默跨供应商混源；TDX以另一个明确选择的适配实例运行。各源期望 dataset_version 显式固定，查询结果核对provider及版本，资格不低于配置下限。min资格由受管调用方设置，DevelopmentVerified仅用于开发输入，不自动提升导入数据。

证券为六位.SH/.SZ。start/end为带时区、整分钟 datetime，转上海右端时间；范围闭区间，start<=end<=as_of，不读未来。clock默认为带时区当前UTC时间，可注入用于回放；as_of须带时区。每次请求按最多3个交易日期跨度的自然日期窗拆分，日历每窗调用既有CalendarProvider.minutes。日历版本必须匹配，分钟唯一有序且在日期与as_of范围内，切到用户范围；超过max_windows/max_bars明确Backpressure。预算须验证类型/有限值和上界（max_bars<=1000000,max_windows<=10000,timeout<=300秒）。

日历全窗 authoritative_empty+evidence_ref 才可确认整窗零分钟；当前尚未闭合分钟或无可证明网格时 Pending。非空日历过滤后无用户所需分钟，可以依据已验证网格确认该子范围为空；不得按240根、工作日或首末行自行生成交易网格。日历/网络调用前后检查同一总deadline；每次低层有界调用只有其已声明timeout不超过剩余预算才准入，不能启动超过剩余预算的等待，也不宣称可抢占任意注入代码。

先查询所有显式源，记录原元数据和标准化bars；Unavailable视作该源无可用数据，其他原错误显式返回。只接受未复权、右端、上海时区的合格结果。按请求网格选取bars；同分钟重复值完全相同才合并、优先早列来源，相异OHLCV/量额返回Conflict，禁止发布部分结果。缺口仅向配置活动源调用history.read，再合并校验；仍缺失返回Pending及missing_minutes，不把部分bars交付策略。跨来源不修改DSB及其metadata，不把原资格/会话合并成虚构单一来源。

活动源 read 返回 Pending/data={} 时，可能已发布部分分钟；在同一剩余预算内执行一次 query 并按相同资格/来源/冲突规则合并。query 仍为 Pending 或 Unavailable 时保留此前已验证数据，按权威网格计算剩余缺口；其他错误显式返回。后续窗口继续有界处理，最终 missing_minutes 汇总全部窗口的已知缺口。此回查不循环等待，不放松全有或全无的交付语义。

结果 HistoryResult 为不可变业务值，包含 status（沿原Status代码）、reason、bars、missing_minutes、provenance、calendar_version；仅Ok包含完整bars，其余bars空。MinuteBar为不可变(symbol,minute,open,high,low,close,volume,amount,source_name,delivery="historical")，minute为右端YYYYMMDDHHMM；provenance按source_name保留只读元数据，源系数仅作证据、量额不重复乘。长区间各窗结果原子返回，任何窗失败都不返回部分成功。

注入的calendar和各低层client必须声明正有限timeout秒，作为调用准入上界；现有CalendarProjectionProvider/MarketClient沿自身timeout遵守此契约，替身同样声明。该接口为创建线程独占，close后新调用拒绝；无后台线程、隐式任务数据库或账户参数。异常转换为固定安全状态/原因，不输出凭证、源行或底层异常文本。

## SMA-R3 实时快照与闭合分钟订阅

quote只调用配置活动源（没有则Unavailable），返回严格验证的独立快照投影，保留源时间、会话及资格；使用源date/action_time与as_of比较，超max_age_seconds或未来时间标记不可用，接收时间不刷新源数据。行情量额已为股/元。输出QuoteResult为不可变，status/reason/data；data可为递归只读的原标准化快照+元数据。

subscribe_minutes返回MinuteSubscription，公开poll(*,as_of=None,until=None)、ack(batch_id)、close；无后台sleep或tick聚合。after为整分钟带时区已持久消费游标。poll从after之后到until（默认as_of向下取整）的已闭合网格调用history_1m；until必须为带时区整分钟且不晚于真实as_of，不替代判断current的时钟。沿原source1m资格与历史补齐，返回MinuteBatch(status,batch_id,bars,delivery,reason,provenance,after=None,through=None,calendar_version="")；成功的可确认扫描批次携带整数右端after/through及绑定日历版本，新增字段置于尾部保持构造兼容。批次大小受max_bars约束。pending/异常/超预算不推进游标；同一个未ack批次再次poll返回同一批次与稳定ID，不再访问源。ack只接受当前batch_id，成功后推进至已确认扫描through；错误ack不推进。没有待扫描范围时不创建批次；有范围且权威日历确认无分钟时仍创建可确认空批次，缺日历证明继续Pending。批ID绑定证券、after/through、日历版本、分钟和来源内容；结果用户修改不能污染重投。

delivery=`closed-source-poll`明确表示此订阅方式；恢复从原事实owner已提交的after重建，语义为至少一次。close幂等、丢弃本地未确认投递但不修改外部数据；关闭后poll/ack拒绝。策略业务不处理作业或队列编号；受管消费adapter负责在原事实存储/消息持久化成功后ack。

订阅批次中的每个MinuteBar.delivery按本次as_of上海整分钟边界标记：恰等于最新闭合分钟为current，更早为recovered；历史history_1m结果保持historical。未ack批次的分类随原批次冻结，重投不把旧bar重新授予current资格。

历史读取仅返回数据；订阅补发需保留 recovered/current 分类，不能把十年历史作为当前分钟事件发布。原分钟策略timely gate未限制历史年龄，不能依赖它阻挡补发触发。原业务预热复用save_bar保存历史、不生成feature/outbox；当前闭合才进入原bar→feature链。右端到原起点事件时间在消费边界转换一次，单位保持源已规范化股/元，独立feature_version用于隔离原QMT原始单位历史。

业务薄适配放在 `integrations/guanheng/minute_consumer.py`：`RetainedMinuteConsumer(store, market_bar_type, publish_current, feature_version)`，warmup(history_result,*,as_of) 和 consume(subscription,batch,*,as_of)。market_bar_type为原MarketBar构造器，store沿原save_bar，publish_current(original_bar,provenance)由受管宿主注入原消费者/发布入口。feature_version为显式稳定非空口径，不能使用逐次变化的content_id。历史及recovered只save_bar；current仅在消费时仍为as_of上海最新闭合分钟时调用publish_current，迟到重投降为预热。先验证整个输入批次、全部字段/时间和资格引用，再产生存储/发布效果；bar值和provenance保持原件。消费全部成功后才ack，失败保留未ack批次；有范围证明的空批次也必须确认，旧式无范围空结果保持无效果；不新增业务日志、状态库或特征公式。原生右端在此处减一分钟构造原MarketBar，正常/重投验证转换一致。

## SMA-R4 故障与兼容

新服务内history.read不与旧Operations共享临时任务，旧worker/CLI行为保持；0.5客户端继续可用旧路径。原数据format=1保持、DSB编码继续WT唯一实现；会话漂移/资格差异的merge冲突不放松。跨会话活动历史根轮换及生产服务目录/端点发现由受管运行方案后续实现，当前端点清单显式配置，不宣称一个活动根跨会话自动融合已完成。

来源许可、内容身份、复权及日历缺失保持未就绪。读到归档与活动相同分钟冲突时停在事实比较，不按优先级丢弃矛盾事实。当前档案原生reader热缓存问题通过服务Store逐请求读取解决Python外部读取链；原WT运行策略同实例热刷新仍另验。

## SMA-R5 验收映射与分工

| 要求 | 验证 |
|---|---|
| SMA-R1 | 实际HTTP→NativeMarket→临时准备→QMT协议fixture→DSB→重读；未知回复后重读；并行/多消费者无互相释放；Unknown无源请求、超窗/截止及已有共享任务原样 |
| SMA-R2 | 跨窗口/档案+活动缺口、资格/版本/单位、重复相同/冲突、未来/空网格/预开盘、有限预算、全有或全无；QMI合成档案真实端点读 |
| SMA-R3 | 源时间新鲜度、有界until与真实时钟分离、权威空扫描确认、未证明空范围不推进、订阅未ack重投/正确ack/错误ack/重建/关闭；历史补发与当前分类、原分钟feature消费者预热/当前各一次 |
| SMA-R4 | 旧协议/runner/worker/导入/回放回归；12框架源码SHA不变、旧冻结证据保持；真实来源与跨会话运行明确待验 |
| SMA-R5 | wheel只含声明六源码、离仓仅wheel运行；实际搬迁包全链；独立full审查、源身份/制品绑定 |

所有权：native Agent仅自有MarketBridge.cpp及新增原生服务测试；SDK Agent仅新strategy_market.py及其单元测试；消费Agent负责minute_consumer.py及其单元测试、完整HTTP链测试；主Agent负责本规格、低层协议客户端/版本/构建清单和打包、调用链组合；独立reviewer只读最终规格与源码。任何WT框架修改均先按用户审批规则执行。

## 完成边界

本规格实现业务统一入口及已闭合源数据订阅，不替代全系统迁移验收。真实国信样本、实际18010端点、生产日历/存储/目录监督、跨会话根发现、同实例WT策略热刷新、完整业务页面及交易恢复仍按[完整地图](../migration/acceptance-map.md)推进。原持仓、委托、审批和Host通信契约保持原owner；共享内存绑定、TDX交易继续暂缓。
