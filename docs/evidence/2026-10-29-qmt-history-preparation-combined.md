# 显式历史补齐与原行情条目组合

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：partial。关联要求：[HPR1–HPR4](../specs/qmt-history-preparation.md)、[QST8](../specs/qmt-quote-stream.md#qst8-原行情条目的可选历史补齐装配)。隔离业务主链通过，真实终端/独立安装及产品整体继续。

## 输入与实现

源码分支 codex/qmt-migration-plan，存在其他模块未提交修改，本次只改变自有通信/生成器/测试/文档，无新增 WT 框架修改。HPR 沿既有签名 HTTP、Session、ControlPeer、原队列、结果 Journal 和 reconnecting owner 增加显式 v6 的 market.history_prepare。旧构造拒绝该能力；新专用入口才启用。

每个请求单证券、单周期、明确范围及原同机 uptime 截止，单次派发，保留原请求身份；进入下载后失联/异常/超期为 unknown，先回读核查。成功只授 call_returned、coverage=unknown。完整约束由规格拥有。

原行情正文生成器通过显式 history_bootstrap 将历史能力装配到同一条目。原纯行情回调正文 SHA 保持 413f982b0efbfa929a3a4bbdaa34e68d82e94fb65d9962cc0dd3e71416de166d；诊断与组合分别选择。组合仅注入固定 download_history_data，无下单、撤单或账户函数。

## 实际步骤与观察

| 结果包 | 实际结果 | 证明范围 |
|---|---|---|
| build/hpr-synthetic-005 | 284项适用检查通过，0失败/错误/跳过 | 合同、实际签名HTTP/认证SHM/原线程下载替身/回读、重复/未知/存储重启/重连及旧读/交易回归；其96份Agent/Host源码已逐份核对仍匹配 |
| build/qmt-combined-memory-main-063 | 首次完整组合通过，3.781秒、exit0、未强制结束 | 国信实际3.6.8解释器执行完整生成正文，同时收到报价快照、增量、1d/1m调用终态和分钟字段回读 |
| build/guanheng-workspace/qmt-hpr-combined-regression-064 | 18项中1错误 | 旧心跳测试漏了已有latest_symbols/missing_symbols/overflows字段；生产合同保持，更新测试完整样本并新增缺字段拒绝 |
| build/guanheng-workspace/qmt-hpr-combined-regression-065 | 18项通过，1.046秒、exit0 | 原行情/诊断及组合配置、所有权、部分启动、双停止；启动与清理同时失败时保留启动根因 |
| build/qmt-combined-memory-main-066 | 最终组合主链通过，3.562秒、exit0、未强制结束 | 修改后的完整正文在3.6.8运行；两路真实认证SHM、原Host/Journal，全部资源正常收束 |

066正文 SHA 为 fa3e1470f8c842ac6e2622eb19f4793cb6eefcf9a0aa6b0497618fe3d7485b55，大小1539420字节。实际SDK替身调用为 timer、subscribe、download:1d、download:1m、history、unsubscribe，均在创建线程；重复1m请求没有额外下载。回读新bar为 time=1635730260000、OHLC=4/5/3/4.5、volume=120、amount=540，快照价格4、下载时增量价格4.5。原值逐字段匹配。

SOURCE.json 明确 Python=3.6.8、forbidden_attempts=0、resources_closed=true；RESULT.json 的 receiver/history_host/http_thread/source_owner 均关闭。外层受管结果另核树0、双EOF、reader join、资源释放；不是仅依据脚本exit0。复现入口和夹具边界见测试说明（外部历史/待归仓路径：`../../tests/integration/qmt_quote_stream/README.md`）。结果包的具体源文件摘要保留原样，后继文档更新不追写原报告。

## 限制与后继

本次下载为明确替身；前一轮589680内置真实下载证据见[单位与补齐](2026-10-28-qmt-daily-units-backfill.md)，不能代替本组合在真实QMT内的验收。当前未替换或重启QMT正文、未开新真实下载、未切活动App/采集配置。独立安装/受管产品接线、首策略其余缺口、真实分钟连续采集与自动补回继续。历史单位、完整日历、闭合可获知时间和交易资格分别保留原限制。

## 后继：独立审查与真实QMT组合

独立full审查完成，P1/P2为0；审查方另执行20项隔离测试通过。build/hpr-independent-review-001保存report.md、verification.json和50份输入SHA，根已逐份核当前身份一致。静态/隔离范围保持，真实终端资格由以下结果单独表达。

根仅启停现有GH_WT_MEMORY_VERIFY，其他策略保持。068/081均由原已验全推设置与HPR离线生成；原文逐字备份SHA fb10247053776adc1fc0e700a22d9672d4053c224128a12f40e90615d2831239保存在068/original-strategy.py。先备份9只日线及510300分钟缓存，再提交有限请求，没有全市场下载。

| 结果包/步骤 | 实际结果与判断 |
|---|---|
| qmt-hpr-real-main-070 / control-071 | 真实v6认证和600条报价通过；首159780补齐为preparation_not_executed，后续未派发；9日线和1分钟缓存摘要均未变化，7.641秒正常收束 |
| qmt-hpr-real-read-072 / control-073 | 同源普通full_tick也queue_timeout，说明不能只归因下载函数；800条报价，全部外部资源关闭 |
| qmt-hpr-read-budget-074 / control-075 | 只读排队6秒不满足原control的queue/native/I/O合计准入，启动前拒绝；没有实机调用 |
| qmt-hpr-read-budget-076 / control-077 | 只读排队5秒通过准入，但HTTP503，7.281秒正常关闭；单独延长排队没有解决连接问题 |
| qmt-real-budget-inspect-078 | 从此前通过的真实配对静态提取白名单：queue20秒、full_tick执行2秒、账户执行5秒、io2秒、control40秒；确认本轮初始2秒排队来自合成夹具，不能视为已验生产配置 |
| qmt-hpr-real-material-079 / control-080 | 离线材料执行预算两侧不一致，被原准入拒绝；未安装。081/control082改正并通过，queue20秒/native5秒/control40秒/io2秒 |
| qmt-hpr-real-main-083 / control-084 | 真实认证后首补齐丢失连接，HTTP503；原Journal已派发并终态保存，原request_id=d051a244-3a21-46fa-b60c-b17e9e0ad535继续保留，未用新ID重发。缓存摘要均未变，不能据此授未执行或成功 |
| qmt-hpr-real-health-086 / control-087 | 只读诊断见strategy_stale，Host runtime.failure=OSError、retiring，1400条报价；正常关闭 |
| qmt-hpr-owner-observe-088 / control-089 | 普通full_tick真实成功，随后history_1m期间strategy_stale；Host原失败为TimeoutError，1000条报价。原策略线程11秒内完成12次回调，未见停止调度，外部资源正常关闭 |

081后追加的临时观察正文SHA 751da46aaf7ae3031f984bd378e68163b925c87d1ff70a6d9b4368480d94c1dd，大小1631148，只在原tick每10秒打印固定线程/代际/错误类别/队列数，不增加SDK调用、文件或网络。普通full_tick已实际执行且execution_ms=0；历史查询失联的原请求由同081 Journal保留，不能用新请求身份重试历史副作用。

当前已确认：定时回调仍推进、普通行情可返回；2秒运输等待与允许5秒原生调用的实机配置存在冲突。尚未证明：具体哪一段持有GIL或占用I/O超过2秒，不能将预算差异宣称为已证根因。090/control091已准备io10秒、queue20秒/native5秒/control40秒的下一候选（SHA 6be3b6e5d9b41fc6861b40972192e31d7aae72bc73933ca65bddad7ed0a9b89b）；它尚未安装。

界面随后检测到用户输入，根让出QMT，不继续点击。当前运行体仍是081的临时owner观察正文，其他策略保持；所有外部有限Host/Receiver作业已终结，不存在本轮遗留下载作业。真实1m补齐和9ETF补齐均未通过，未将其登记为交付完成。原数据、失败原件与Journal保留；下一步先完成单ETF历史/补齐及实际回读，再扩大覆盖并纳入产品受管启动。整体goal保持active，无当前新增核心批准或用户必须先处理事项。

调度API依据：官方[系统函数](https://dict.thinktrader.net/innerApi/system_function.html)将run_time定义为周期回调，并提供schedule_run/cancel_schedule_run；本轮没有为掩盖未定位问题改换调度API，也没有把非交易时间推断为失效原因。

最终核查：092文档检查exit0，0.703秒；093以SQLite只读打开原081 Journal，确认首补齐d051a244-3a21-46fa-b60c-b17e9e0ad535已terminal/preparation_unknown。普通快照6ba6ebea-7162-4772-8c07-31d8d082468c已terminal/success，后续a3868d48-a84c-4dce-b0ed-ddf390e51351为queued的只读分钟请求，没有转换为新的补齐身份。外部071/073/075/077/084/087/089逐份核forced=false、tree_zero/readers_joined/resources_closed=true；业务失败与资源收束分别登记。

## 后继：真实补齐、原生导入及安装SDK主链

090正文已在同一GH_WT_MEMORY_VERIFY条目编译并重启，SHA256为6be3b6e5d9b41fc6861b40972192e31d7aae72bc73933ca65bddad7ed0a9b89b、1630366字节。仅调整私有配对预算：io10秒、queue20秒、native5秒、control40秒；保留原全推设置，移除临时owner诊断包装。其他策略保持。以下结果取代上一节“090未安装/真实补齐未通过”的当前状态；旧失败原件及Journal保留。

| 实际结果包 | 业务结果及范围 |
|---|---|
| qmt-hpr-real-main-095 / control096 | 实际full_tick、history1m及510300的1d/1m下载完成；原生下载61/108ms，6600条报价同时到达。最后10根请求因原有rows>=count截断保护拒绝，完整作业业务失败、正常回收；未放宽保护 |
| qmt-hpr-real-reread-097 / control098 | 将同一10分钟分成两个5分钟只读窗口，完整5+5条；包括14:59零量零额。1600条报价，正常回收 |
| qmt-hpr-native-reread-099 / control100 | 实际510300缓存14580根经原Exporter/Importer/Helper/Reader，全部日期及六字段相等；SHM尾10条数量精确、价额仅表示产生的1 ULP差异，保留原值 |
| qmt-hpr-etf-fill-101 / control102 | 其余5ETF日线下载成功；第6项未准入，原合成Journal300000字节已占299519。失败为测试容量，保持原准入器 |
| qmt-hpr-etf-final-103 / control104 | 提议2MiB超过原max_records联合上界，启动前拒绝、无SDK调用 |
| qmt-hpr-etf-final-107 / control108 | 589000新明确任务成功；Host容量400000字节、max_records16，满足原验证器，未重启QMT |
| qmt-hpr-etf-reconcile-109 / control110 | 核对159780实际仍缺尾部后，在用户原历史补齐授权内明确创建一次有限新任务并成功；原081的unknown记录/ID保留，非自动重发，RECONCILIATION.json保存判断与输入摘要 |
| qmt-prepared-daily-source-111 / control112 | 原安装qmt_api只读取得9ETF9269日线，全部尾到20261028；510300仍缺21/22 |
| qmt-prepared-native-113 / control114；qmt-prepared-sdk-main-115 / control116 | 9ETF9269日线原DSB逐字段回读；更新510300分钟纳回原16证券批次，其他15份DSB SHA不变；5338证券1390295077根/335store配置与9日线合成336store经039组件/042 SDK整链通过 |
| qmt-hpr-etf-complete-window-117 / control118 | 对510300原授权完整日线窗口显式补齐，新增20261021/22，成功返回；原分钟根保持 |
| qmt-prepared-daily-source-119 / control120 | 最终9ETF9271日线；仅510300相对111增加两条，其余8份rows字节完全相同 |
| qmt-prepared-native-121 / control122；qmt-prepared-sdk-main-123 / control124 | 最终9271条原Helper/day DSB/Reader逐字段一致；复用113分钟根，147安装文件身份与独立SDK0.14、336store、全部日线及5分钟样本主链通过；SDK整链20.906秒exit0，listener及owner正常关闭 |
| qmt-prepared-source-qualification-125 / control126 | 复核交易所公告日历：20250305..20261028共401日，9ETF每天齐全，3609条连续共同源值；全9271量额推导零例外，金额单位仍unknown |

源资格正文见[QMT源日线资格](../modules/qmt-source-qualification.md)。更早512100的20220902相对本批日期仍缺，2021–2024完整日历、历史首次可知时间未知；不将日线午夜或15:00制造成实收时刻。分钟DAT单位保持unknown，三个指数继续隔离。

所有以上有限外部作业均已终结，外层Job核对实际树0、双EOF、线程join及句柄释放；业务失败不混同回收失败。实际下载调用47–156ms，不足以证明此前GIL阻塞；仅确认io10候选在本轮实机可完成。当前原策略090运行，外部持续采集服务未在本轮启动，真实全天分钟、HPR产品安装与B/C同候选组合继续。未改WT核心、旧QMT项目，真实下单/撤单0、生产配置未切换。

## 后继：同一090策略与App托管采集组合

qmt-current-collector-real-129以原最终搬迁005的采集入口/原生库、当前观衡App lifespan和原6982来源配对连接同一090策略；未修改或重启QMT。130准备阶段独占复制旧私有配置到新根并绑定实际策略SHA，止停预算启动前固定60秒。132原240秒父截止内50.578秒自然exit0，正常关闭listener/Receiver/Native/Job，实际整树0、双EOF、线程join及资源释放均核对。

收到35包/6928有效快照，source heartbeat缺54、队列0/溢出0，原生delivered/writer_processed均6928；其广播计数只证明Writer处理入口，不证明分钟落盘。最新源时间1793176617000（上海2026-10-28T16:36:57），当前为休市观察；本次native_min1_files=0，三个固定证券文件均不存在，full_minute_qualified=false。原日间session保持09:30–11:30、13:00–15:00，allday仅绕开管理时段而不改变Writer的报价时间过滤。原全体快照16点段依据及来源边界见[源时间调查](2026-10-28-qmt-source-time-delay.md#内置历史补齐后原行情桥的完整时间观察)。不能将最大时间推定为所有证券当前时间，也不能将累计广播数当作分钟完整性。

本次确认当前App与090组合的只读运输/原生入口及正常停止；没有授盘中持续分钟、全天完整性或生产运行资格。外部有限采集已停止，QMT原策略保持。HPR独立产品与统一App接线继续。
