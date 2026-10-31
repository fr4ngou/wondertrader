# 原生历史准备的有界时间分片

类型：功能规格。状态：accepted，待实施。前缀 NHP。承接[原生行情方案](../migration/native-market-integration-plan.md)、[准备生命周期](history-lifecycle-and-service-adapters.md)、[原生历史查询](native-history-query.md)与[原生窗口](native-history-window.md)。

## 目标与根因

从 QMT 已下载的 1m 缓存补齐一个有限请求内的多个时间分片，并把已完成源页交给既有 Store 发布到 WT 原生 DSB。策略和查询继续复用原 Reader/Factory；后台获取不进入策略 ticker 回调。

当前 HistoryPreparationQueue 将所有缺口的首尾交给一次 fetch。QMT 单次窗口最多 72 自然小时、count 最多 5000；跨窗请求会反复背压。仅缩小 count 可能取得尾部行并漏过早期缺口；仅按剩余缺口重新计算 partial 页范围又会改变正在收集的源页身份。本切片在自有准备队列建立固定活动窗口及逐片扫描，复用源端上限、原发布和同实例查询刷新。

## NHP-R1 范围、所有者与兼容

NativeHistoryStore 继续拥有 DSB、来源元数据、单写者发布及覆盖判定；IHistoryEndpoint 拥有源页及其结束声明；HistoryPreparationQueue 仅拥有有界、可丢弃的内存任务、活动窗口、暂存和扫描位置。持久作业、来源请求跨重启恢复与逐次采集 provenance 分别由后续规格处理。

本切片限定相容的同一 SourceSession。原 sidecar 的 provider/instance_id/session_id/generation、dataset/profile、单位、许可及同分钟内容冲突保护全部保留。QMT 会话变化不得把旧行标注成新会话，跨会话补洞保持原冲突结果。已经发布的旧缓存继续按原离线查询契约读取。

保持 MinuteRequest、现有 HTTP/SDK wire、任务 queue_id/task_id、release 及现有输入容量：外部 expected_minutes 最多 10000；内部容量和 page/staging 预算保持既有校验。十年数据通过调用者逐片、多次有限请求处理，本切片不接受单次任意大网格、不增加第二行情库、不启用主动下载或订阅。原 history.read 的 72h/5000 准入及一次临时队列推进语义保持；长区间使用已有显式 task.prepare/work/inspect/release 接缝。

不修改 WT core、原 Reader/Writer 插件虚接口或策略调度。新增虚方法仅位于自有 IHistoryEndpoint；相关自有 C++ 生产者/消费者需一起构建，不声称跨旧自有二进制 ABI 可混用。SDK 现有源码及发行版本不因本切片修改。

## NHP-R2 来源上限与纯时间规划

自有 IHistoryEndpoint 增加可选 `fetch_limits() const`，返回 `HistoryFetchLimits`，含可选 `max_rows` 和可选 `max_elapsed_minutes`：未指定代表源没有额外声明上限；max_rows 指定时为正整数，max_elapsed_minutes 为非负整数，0 明确表示单一时点。默认实现两项均未指定，使既有非 QMT 来源不必新增限制。方法只返回固定能力，无网络、文件读取、下载或状态推进。

QmtHttpEndpoint 明确声明 max_rows=5000、max_elapsed_minutes=4320。队列在开始一个新活动窗口前核实能力和上限，并计算：

```text
effective_limit = min(queue.page_limit, queue.staging_limit,
                      source.max_rows（指定时）)
elapsed_limit  = min(effective_limit - 1,
                     source.max_elapsed_minutes（指定时）)
```

未指定源跨度时仍使用队列实际行数预算约束闭区间。effective_limit 必须至少为1；limit=1时跨度为0，一个窗口只允许一个整分钟。fetch 实际传入 effective_limit，禁止使用较大的名义 page_limit 形成不可兑现的窗口。

新窗口从本轮尚未扫描范围内最早的实际缺失 expected minute 开始；结束时间为请求末端与起点加 elapsed_limit 的较小者。活动窗口的 expected_minutes 为原权威网格在此闭区间内的子集，保留 calendar_version。包含夜间、周末和休市自然分钟的跨度同样受限，不能用 expected 根数代替真实跨度。

时间计算按已准入的 Asia/Shanghai 右端整分钟、现有合法日期范围进行无主机时区/DST影响的自然分钟加减；禁止直接对 YYYYMMDDHHMM 整数加减分钟。复用或最小抽取自有日期准入/转换为唯一辅助实现，覆盖月末、年末、闰日及溢出。不得为此更改 WT 时间或交易日历算法。

规划范围之间不重叠，后续搜索从已结束窗口末端之后开始；缺口稀疏时可以跳到后面的最早缺失分钟。跳过的范围须已有本地覆盖，或没有本请求 expected minute；不能由最高返回 bar 推断该范围完整。

## NHP-R3 固定活动窗口与每次一步

每个任务最多持有一个活动窗口。其 from/to、expected_minutes、calendar_version、effective_limit 与适用源身份在第一次 fetch 前固定。后续 partial 页仍请求这个相同窗口，不因新增暂存、最高时间或本地缺口变化改写范围。

每次 work_one 最多调用一次源 fetch、最多结束并发布一个活动窗口；结束后即返回，下一次 work_one 才处理后续分片。禁止在一次调用内循环拉完整任务。任务内原 staging_limit 限制实际合并暂存；每片清理后可复用容量。页面返回仍须校验条数、实际时间范围、顺序、字段、来源及相同分钟内容；来源重复返回同内容可幂等合并，冲突明确失败。

`page.complete=false`：保留固定窗口及其有界暂存，返回 Pending，不发布、不推进扫描位置。即使暂存已包含全部 expected minutes，也不能由队列替代源声明 complete。partial 空页仍为 Pending，不内部重试。输入不可信或来源身份变化沿原错误矩阵处理。

`page.complete=true`：有暂存则使用既有 Store.merge_bars，成功后清理本片暂存；无暂存则不写空 DSB。只有源页已结束且需要的发布成功，才能推进本轮扫描位置。源页结束与原请求覆盖完成分别判定。

Store 发布背压时保留活动窗口、source_complete 和暂存；下一步先重试该发布，不重新 fetch。失败前已有 DSB 保留，发布恢复沿原 Store 的摘要/previous/fail-closed 行为；本切片不改变多文件发布原子性承诺。

本地独立写者可能先完成原请求；没有活动 partial 页时可按原 Store 已验证 Complete 直接完成。已有 partial 页时保持源结束约束，调用者也可按原 release 语义明确丢弃未发布暂存。不能把局部暂存当成已发布覆盖。

## NHP-R4 源结束、空片和重复扫描

QMT 原 `rows < count && requested_to <= same-session full_tick.time` 结束条件保留。为支持 limit=1 和 exact-limit 的有限窗口，QMT 源 owner 可增加一个结束依据：所有实际行经过整分钟对齐、唯一、严格有序和边界校验，且其时间集合覆盖该闭区间**每一个自然分钟**，同时 requested_to 不晚于同会话源观察时钟。实现须验证实际时间集合，禁止仅凭行数相等或 expected_minutes 齐全推定结束。

该条件不要求证券在休市时生成行情；存在休市/稀疏记录时通常仍沿 rows<count 判断。未覆盖全部自然分钟且恰好达到 count 的页继续 partial；未来 to、会话不稳或源时钟缺失保留现有 Pending/Unavailable，不能授予结束。两类源页结束依据均不证明分钟最终修订、停牌状态或证券覆盖。

一片已经结束且成功发布后，即使该片仍有 expected 缺口，也推进本轮扫描到后续窗口。已结束的空片同样推进；早期未下载分钟不能永久挡住后面的已下载缓存。

本轮剩余范围没有未扫描缺口时，重新查询原请求覆盖：Complete 才将任务标为 Complete；仍有 Gaps 则保持 Pending，记录本轮已结束，下一次 work_one 从当前最早缺口开始新的有界扫描。Unknown 保持 Pending 且不联网。扫描结束不代表覆盖结束，不输出伪造零 bar、不自动发下载、不在当前调用内开始无限下一轮。

本切片没有新增“已证明无数据”状态。原 expected_minutes/calendar_version 才是覆盖依据；空网格继续 Unknown，不因日期看起来是周末而标记 Complete。权威空日历仍沿既有上层事实owner处理。

## NHP-R5 失败、并发与生命周期

保留现有 task 状态/错误矩阵和显式释放：Backpressure/Pending 保留可继续的活动状态；其他源失败、StaleSession、元数据或内容冲突沿原 Failed/Unavailable 结果处理。失败不得推进当前扫描位置或发布未经结束的页。新的可重试任务由调用者按原终态释放/重新查询流程创建；此切片不添加隐式网络重试策略。

队列仍只允许一个 work 执行，取任务及回写在原 mutex/running 协议下完成，网络期间保持既有解锁边界；并发 work/release 使用原背压保护，不能使解锁后任务位置失效。新增 active window/cursor 仅由这个 worker 推进。inspect 不发源请求，release 不删除 DSB，非零已释放任务幂等行为及 capacity 计数保留。

来源及准备线程仍遵守 QmtHttpClient/QmtHttpEndpoint 创建线程独占，构造和规划不进行 I/O。每步源截止、回查与发布约束保留；同步本地原生工作没有可抢占执行截止，HTTP超时不能当作服务端取消。

进程结束后内存窗口/暂存/扫描位置丢失，已发布 DSB 可由新任务重新查询。当前 QmtHttpClient 函数内同 request_id 回查不等于跨超时或重启恢复；本切片不宣称解决该缺口，不因内存任务丢失就推断旧源请求未执行。原请求身份持久恢复与跨会话 provenance 必须独立完成后再授予持续自动补齐资格。

## NHP-R6 原生发布及查询复用

源结束后的每片使用原 Store.merge_bars → Helper store_bars → 原生完整回读校验 → DSB/sidecar 发布，不增加手工编码、全量查询索引或聚合器。新内容仍以 content_id 驱动同一 Store 内的 IRdm Reader 代际更换；m1和Factory派生周期复用 NHQ/NQW 的查询、缓存预算、最多一个退休实例及背压重试。

验收必须在同一查询对象上观察发布后的基础和派生更新，以及旧返回副本稳定。该证据限历史-only受管根；不扩大到DMB混读、原CTA所有上层缓存、全市场性能或生产资格。对 `.guanheng-frozen` 根、来源profile变化和跨session合并继续拒绝。

## NHP-R7 验收要求

测试先复现原跨窗卡住和小limit页永远partial，再实现。合成源必须标明身份；真实缓存验证另行在获准的只读条件下进行，不能在测试中触发主动下载/订阅。

| 验收项 | 必须观察的结果 |
|---|---|
| 原触发长窗 | 同一个现有容量内expected请求跨多个72h；旧实现不能推进，修正后多次work逐片发布并最终以Store覆盖Complete |
| 无重漏与日期边界 | 跨周末/月末/年末/闰日；每片闭区间符合有效跨度/行预算，原expected恰属一片；稀疏expected跨度不能绕过72h |
| 有效行预算 | page_limit、staging_limit、源max_rows不同组合取真实最小值；limit=1为单分钟，源无额外限制的默认实现仍可工作 |
| exact-limit与源时钟 | QMT实际逐分钟集合完整时允许页结束；相同行数但重复/乱序/漏时点/越界/未对齐拒绝；稀疏集合及未来to不能误获结束 |
| 固定partial窗口 | 连续partial、空partial、重复同内容、最终complete；每次fetch窗口完全相同；expected已齐也等待sourcecomplete；不超暂存预算 |
| 早片缺口不饿死后片 | 早片complete但空/缺部分，后片有数据；后片在有限次work内发布，整任务仍Pending；下一轮重查早缺口且每work最多一fetch |
| 无依据与本地已有覆盖 | Unknown/空网格不联网；本地Complete无需fetch；已结束空片不写空文件、不把未知改成Complete |
| 源异常与恢复边界 | Timeout/Unavailable/StaleSession/内容冲突不推进当前片；原终态处理保持；Backpressure保留窗口；新任务回读已发布DSB |
| 发布背压/故障 | 源complete后发布背压保留暂存，下次不重取源；发布故障保留旧数据及原恢复证据；成功后才移动扫描位置 |
| 并发与释放 | 受控阻塞fetch期间第二work/release背压、inspect不变异；原worker回写正确；释放partial和已完成任务回收容量，重复release保持原语义 |
| 来源兼容 | 同session多片允许；会话/profile/单位变化与同分钟不同内容保持Conflict/StaleSession；旧缓存仍可离线query |
| 同实例原生读取 | 真Helper/IRdm/Factory验证分片追加后m1及5m更新、旧副本稳定，快速代际变化背压后成功；保持历史根和原数据身份 |
| 公共接线与兼容 | 原task.prepare/work/inspect/release完整链；旧history.read单窗及旧接口测试通过；超10000网格在源请求前拒绝，不以单次请求宣称十年支持 |

复用入口：`tests/integration/market/history_lifecycle.cpp`、`qmt_http_endpoint.cpp`、`tests/integration/http/test_qmt_http.py`、`tests/integration/service/test_history_read.py`及任务测试；原生查询/周期集成测试覆盖发布后可见性。新增文件及受管构建测试登记在实施时按仓库规则完成。

## 交付与资格

已完成维护者技术自查，按本accepted规格实施。交付记录实际源码/二进制/测试输入、红绿证据、每片调用次数、发布与覆盖结果；通过独立审查后仅授本切片开发资格。原生核心与旧冻结候选保持原样。原请求跨重启恢复、跨会话多来源合并、真实覆盖规则、十年全市场容量、实时CTA与生产发布分别继续验收。
