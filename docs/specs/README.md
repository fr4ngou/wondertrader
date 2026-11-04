- [观衡统一WT日线消费](observer-wt-daily-consumer.md)：同一WT快照、七指标、原计划与后继历史保留，独立安装和回退。

- [策略资金独立只读消费](strategy-capital-observation.md)：原WT资金发布、当前基准、来源时间和账户/策略范围，运行恢复资格独立。

- [观察状态原子发布与失败诊断](observation-status-publication.md)：合法旧状态读者与心跳并行、原失败语义和有限安全诊断。

- [独立观衡Web生命周期](observer-web-lifecycle.md)：隐藏启动、正常停止与重启，沿原App读取与关闭流程，保持WT独立。

- [QMT分钟来源日线](qmt-minute-source-daily.md)：原WT聚合、逐日标签准入、未知量单位及保留既有日仓的只读接续。

- [独立市场更新角色的行情连接](observation-update-connection.md)：显式私有连接、凭据隔离、无凭据停止及原监督生命周期。

- [观衡人工验收修复与视觉重设计](observer-acceptance-repair.md)：OAR-01至09，搜索、历史/广度、中文金额、账户/策略/报告、运行接线和先选图后实施的UI重设计。

#- [QMT Host通信记录的持久I/O](qmt-host-durable-io.md)：DIO，同一owner连接、原事务与FULL持久确认，原截止及未知身份保持；完整调仓验收继续。

- [观衡持续公开A股来源](observer-public-ashare-producer.md)：沪深北行情事实、覆盖说明、原服务采集归档及市场观察指标。

 功能规格

- [来源三包永久源码与构建](source-package-builds.md)：Host/Agent/Core 边界、永久成员映射、可重复 Flit 构建及隔离 SDK 验收。
- [市场Python永久来源](market-python-sources.md)：版本化历史兼容源码、明确成员组装及普通Flit构建；运行步骤见[构建手册](../runbooks/market-python-sources.md)。
- [观衡永久源码与独立读取发行](observer-source-build.md)：OSB，读取变体独立源版本、永久Flit/前端离线构建、App角色及独立安装闭包。

- [账户只读结果的消费确认与有界回收](qmt-account-read-retirement.md)：AAR，v3账户/v4混合通道的进程内原值交接、原票据回收及金融证明保留。

- [已确认只读结果的有界回收](qmt-read-retirement.md)：独立只读/HPR结果持久接收确认、内容与截止绑定的身份及有限容量；交易责任保持原契约，当前实现开发中。

- [策略分析窗口的共享内存来源](qmt-analysis-source.md)：QAS，显式v7日线和原生因子读取，原策略线程及原只读结果，供WT持续窗口生产。

- [WT持续分析窗口生产者](qmt-analysis-window-producer.md)：AWP，原Import/Reader/QNA和原子发布，持续供应唯一策略窗口。

- [持续QNA来源快照合同](qmt-analysis-window-provider.md)：AWP-P，原请求身份、八证券日线/因子/参考与实收时点。

- [QMT来源运行生命周期](qmt-source-runtime.md)：SIO，显式配对选择原策略回调驱动，默认线程路径、原业务身份及截止保持。

- [独立观衡离线制品](observer-runtime-package.md)：只读App/SPA复制安装及更新回退。

- [独立观衡离线制品](observer-runtime-package.md)：ORP，只读App与SPA独立离线安装，WT运行与独立更新、回退分别验收。

- [ETF与常用指数分钟历史批量准备](qmt-etf-index-history.md)：EIH，冻结真实证券集合、按缺口准备及统一目录替换。

- [WT独立运行与只读观察接入](independent-wt-runtime.md)：WRI，WT拥有通信、数据和执行生命周期，观衡独立部署并只读消费。

- [系统候选装配与离线安装](system-runtime-installation.md)：SRI，App/Host角色、原生组件与SPA的统一候选、安装收据及升级兼容；完整M3分别验收。

- [唯一共振策略1.1.2](retained-resonance.md)：正式在用六参数、同基准前复权、实际持仓周期及完整目标接缝。

- [当前可见历史版本策略决策](current-history-decision.md)：CHD，真实批次实收后的预热与决策；C纯核、B实时桥和实际价格准入分别归属，HEM继续归历史回测。

- [真实全天原生收盘归档验收](qmt-day-archive-acceptance.md)。

- [完整App与统一行情真实缓存链](qmt-full-app-real-history.md)。

- [采集归档统一历史查询](collected-native-history.md)：CNH，原Writer归档直接接原Reader/SDK/App，免手工再导入；盘中NMR单独消费。

- [真实行情与分钟进入正式CTA](qmt-real-market-cta.md)：真实QMT报价及实采分钟进入原策略链，历史/账户替身与真实来源分别标识。

- [QMT交易通信产品与WT生命周期](qmt-trade-host-product.md)：THP，复用原交易通信、事件与Journal，封装独立安装、常驻及WT托管入口；实现与完整验收中。

- [QMT账户与交易数据组合正文](qmt-account-composed-source.md)：QAC，单个正式策略正文复用原账户、交易、历史补齐及行情owner；默认身份、普通安装及完整恢复分别验收。

- [历史日线回测输入模型](historical-eod-model.md)：HEM，真实历史批次与显式单位/日末假设分离，复用唯一核及原生回测；严格可知约束保持。

- [统一可安装行情运行候选](market-runtime-candidate.md)：MRC，固定六组件身份、装配/搬迁、消费映射和有界核验；完整M3及生产分别验收。

- [App候选升级与异步来源](app-candidate-upgrade.md)：ACU，新旧独立App/SPA四代切换、原v2任务/偏好连续与最终RS14组合；数据组件降级、完整M1及生产分别验真。

- [受管策略读取原生分钟文件](native-minute-reader.md)：NMR，自有组合Reader显式选择原WtDataReader分钟路径，保留默认HTTP及受管停止。

- [ETF行情规则纯业务链](native-etf-rule.md)：NER，20根特征→规则目标/10分钟有效期→纯状态续接及NSQ数量消费。


- [独立市场观察](independent-market-observation.md)：OBI，保留指标/公式/谱系、固定快照图表导出及独立目录CAS/恢复。

- [来源日线图表](source-daily-chart.md)：模块C沿统一日线SDK提供只读图表，来源语义和策略执行准入分别说明。

- [QMT源值日线导入与原生读取](qmt-source-daily-history.md)：DSH，首真实策略9ETF原日线，复用原Helper/day DSB，日期/单位和可获知资格分开。

- [历史查询服务的旧应用托管](source-market-app-management.md)：SMA，已由WRI替代；保留原App托管开发范围，现行服务归WT管理。

- [原生来源历史查询受管进程](native-source-market-process.md)：SMP，WT拥有的历史子服务，固定配置身份、原Reader/HTTP、独立安装与创建线程关闭；观衡只读消费。

- [观衡业务与操作平台](guanheng-operator-platform.md)：COP，模块C完整业务、策略配置/运行、报告、独立安装与中文操作验收。

- [App托管执行进程](execution-app-management.md)：EAM，显式绑定B安装及原生配置，统一启动/关闭与只读生命周期。
- [QMT显式历史缓存补齐](qmt-history-preparation.md)：HPR，独立权限、原请求身份、未知结果和覆盖边界。
- [来源日线图表](source-daily-chart.md)：SDK0.14直接读取原生日线，日期标签、未知单位与覆盖分别说明。
- [策略目录](strategy-catalog.md)：参考旧QMT，仅展示名称、简介和版本，保留原生回测入口。
- [回测绩效与报告比较](backtest-performance-comparison.md)：BPC，复用已完成归档校验，展示日末净值、收益、回撤与报告条件差异。
- [中文只读运行状态工作区](operations-workspace.md)：OPS，当前进程owner与原SDK能力查询、中文故障原因及未知采集契约。

- [原生Writer生命周期与映射同步](native-writer-lifecycle.md)：accepted，显式模块选择、已受理工作排空、映射同步及全部线程结束后销毁。

- [QMT全推共享内存到原生DataKit](qmt-quote-stream.md)：独立无Journal行情流、内置全推和原生Porter接线。

- [原生 DataKit 行情采集](native-datakit-collection.md)：accepted，复用原采集/分钟/文件与时段；自有QMT批量接线及实际来源分层验收。

- [QMT 长窗历史快照与分页](qmt-bulk-history.md)：分段 accepted，原线程一次 SDK、纯值快照及有界分页实施中；运输/Host/C++与真实长窗分层验收。

- [源值分钟历史导入与原生读取](qmt-source-history.md)：accepted，原值复用 WT Helper/DSB，单位与时间标签显式返回；原标准化路径兼容，实施中。

- [QMT未知委托定向核查与取消](qmt-unknown-cancel.md)：accepted实施，按操作准入与单目标未决取消；产品实现、隔离全链和一般恢复分别验收。
- [未知取消C++实施契约](qmt-unknown-cancel-cpp.md)：accepted实施，Common私有原取消引用、Standard原身份审计、双Started保槽与精确逻辑payload预算已取得限定证据；完整恢复另验。

- [标准TraderQMT实时事件与查询交接](native-qmt-standard-events.md)：分段accepted，原mapper/P8/有限索引与已知基线回报已限定验证；R13同实例有效页前读取恢复实施中，补查及生产首次/跨进程交接继续。

- [标准TraderQMT](native-qmt-standard-trader.md)：分段接受，先接显式交易账户投影及端到端版本准入；标准Factory、SPI生命周期和恢复继续按原生能力收敛。

- [原生QMT交易客户端](native-qmt-trade-client.md)：accepted，复用共用codec、显式v4账户读取、认证交易与原委托查询；标准Trader插件和完整发行另沿实际调用链验收。

- [QMT共享内存交易接入](qmt-shm-trading.md)：整体proposed，源端R9开发接口accepted；复用WT交易与现有SHM，默认禁真实写，SDK参数/unknown及回报逐层验收。

- [个人观察自选](personal-watchlist.md)：accepted，独立应用偏好、完整替换版本比较、原子文件保存与中文分钟页；实现及运行待验。

- [原生账户独立测试运行环境](native-account-test-runtime.md)：accepted，App与Host独立安装、测试双进程与单一期限、唯一QA线程owner及可搬迁闭包；运行资格单独验收。

- [QMT共享内存账户只读接入](qmt-shm-account-read.md)：accepted，复用原四查询、唯一字段映射和有界owner；显式v3能力、来源版本、原ID收据及独立安装/中文页分层验收。

- [共享内存历史一分钟行情](qmt-shm-history.md)：accepted，显式能力profile、唯一原线程finalizer、原ID恢复与有界分页；C++客户端复用同一认证/codec，存储和消费者复用WT，长期保留及真实来源另验。

- [V2历史行情到原始目标](native-v2-history-pipeline.md)：accepted，共用SST和NFA v2完整证据域，原始历史真实生产信号再分配；单总预算及原生执行分别验收。

- [QMT共享内存与原生插件接入](qmt-shm-wt-binding.md)：accepted，源端开发与真实行情验证已核对，开始WT接线；行情、账户、历史及交易分别验收，迁入国信QMT运维材料。

- [共用特征与信号轨迹](shared-signal-trace.md)：accepted，精确复用a5公共算法，保留V2完整前缀/评估切片起点、严格来源准入与有界不可变轨迹；完整策略和执行另验。

- [原生策略目标代际与数量转换](native-strategy-quantity.md)：accepted，复用WT仓位/损益事实，保留经济代际、卖后冻结买量与费用边界；纯转换和原生提交分别验收。

- [观衡策略业务核与原生CTA、回测](native-strategy-kernel.md)：accepted，迁入完整业务规则、复用原生C ABI同核回测/运行；独立进程、有界生命周期及来源资格分别验证。

- [观衡原生账户只读展示](native-account-console.md)：accepted，固定原Adapter一次四查询、有限产品宿主、独立业务HTTP和中文账户页；复用v2事实，不增账户数据库。

- [QMT终端只读HTTP源端](qmt-terminal-readonly-source.md)：accepted，本仓库拥有的Python3.6标准库接入、原HMAC/请求身份、三类只读操作及有界退出。

- [原生只读插件固定来源构建与开发包](native-readonly-package.md)：accepted，复用原构建/依赖/CTest/归档owner，固定来源、fresh宿主库及独立搬迁。

- [QMT HTTP原生只读交易通道接线](native-qmt-http-bootstrap.md)：accepted，复用QRT和原TraderAdapter、逐批来源、合计持仓及版本化观察。

- [QMT共用只读HTTP传输](qmt-shared-read-transport.md)：accepted，Market/Account闭合域、单一传输和完整响应保留。

- [历史行情适配使用上游公开ABI](native-history-public-abi.md)：accepted，自有预算/不可变输入边界及固定上游加NRC历史构建；移除未批Helper依赖。

- [设计模板](TEMPLATE.md)：按实际变化填写的功能与验收结构。
- [原生制品发布与上游维护](native-release-and-upstream.md)：proposed，原生发行身份、部署、上游更新与分层验收；维护角色为运行/构建/测试负责人。
- [原生构建、打包与自动化测试](native-build-automation.md)：accepted，独立构建入口、固定依赖、原生用例与候选包验证。
- 编写、确认和修订方式见[方案规范](../development/design.md)。

新规格使用稳定功能名称及要求前缀，在本索引登记状态、所有者和正文链接。原需求修订同一正文，替代文档保留关系。

已有任务性研究与方案见[任务资料入口](../migration/README.md)，其内容不构成长期开发规范。

- [观衡原生数据与执行接入](guanheng-native-adapters.md)：accepted，多 Agent 实施与隔离验收；真实后端待定项统一汇总。
- [QMT HTTP 行情与独立业务接口](qmt-http-market.md)：已验临时流程规格；HTTP退役时序与共享内存接入前提见[DEC-001](../migration/decisions.md)，独立发行边界保持。
- [长历史准备与独立消费者](history-lifecycle-and-service-adapters.md)：accepted，任务释放/实例身份、独立 SDK、Operations 薄 runner。
- [历史证据对象存储接线](history-evidence-storage.md)：accepted，复用 MinIO SDK、受管内容地址与真实 HTTP 故障恢复。
- [独立历史执行与排空](history-worker.md)：accepted，独立进程入口、OS 单作业锁、有限执行及可核实关闭。
- [历史进程部署工厂](history-deployment-factory.md)：accepted，受管配置组合既有客户端、日历和证据存储，保持原作业所有权。
- [权威分钟计划消费](history-calendar-projection.md)：accepted，原日历 owner 只读 HTTP、存证与历史完整调用链，服务独立发布。
- [已下载 QMT 分钟历史导入](qmt-minute-import.md)：accepted，显式导出分片、原生 DSB 回读、新根及原生分钟策略读取。
- [策略统一行情访问](strategy-market-access.md)：accepted，服务内有界补齐、档案/活动组合、快照及闭合源分钟订阅。
- [原生策略历史可见性](native-history-reader.md)：accepted，统一行情服务到原生reader的同实例历史更新、切片所有权与分钟事件适配。
- [观衡原生行情消费者](native-market-consumers.md)：proposed，原生能力核实期间暂停开发；已写reader候选与原WtDtServo接缝比较后决定取舍。
- [QMT 原生持续行情插件](qmt-native-parser.md)：accepted，标准插件工厂、受管HTTP轮询、快照去重及线程退出。
- [Gateway 启动取消](gateway-startup-cancellation.md)：隔离候选规格，启动超时、取消、清理及重启的同步边界；现场首因与生产修复另验。

- [原生CTA受管退出](native-cta-shutdown.md)：accepted，复用现成停止原语，限定配置的完整生命周期接线。
- [独立分钟消费者与持久接纳](retained-minute-consumer.md)：accepted，独立安装、来源扫描、接纳确认、恢复及完整业务链验收。
- [Windows 原生数据库部署](windows-native-database.md)：proposed，先复核数据库必要性；确需保留时原生运行，避免Docker/WSL。

- [原生随机Reader空历史计数](native-reader-empty-count.md)：accepted，NRC-R1–R4；单一空返回分支、中文注释及红绿回归。
- [原生历史查询接入](native-history-query.md)：accepted，NHQ-R1–R5；原Reader查询、来源预算与有界代际释放，沿现有服务接口接入。
- [原生历史窗口与周期查询](native-history-window.md)：accepted，NQW-R1–R5；最多N根与原DataFactory周期、同实例修订，沿原history.query扩展。

- [独立客户端网络截止](client-transport-deadline.md)：accepted，CTD-R1–R5；显式连接IP、TLS身份、累计网络预算及异常资源回收。
- [QMT原生只读初始化](native-qmt-readonly-bootstrap.md)：accepted，NQB-R1–R9；固定原TraderAdapter、四查询与owner pump，字段/失败/退出验收，交易副作用关闭。
- [原生历史准备时间分片](native-history-preparation-shards.md)：accepted，NHP-R1–R7；源预算、固定活动窗口、逐片原生发布与覆盖，保持同会话及现有容量。

- [观衡业务迁入与独立应用工作区](guanheng-business-workspace.md)：完整功能迁入、独立源码/依赖/发布及原生分钟页面接线。
- [策略同核与原生回测会话](native-strategy-backtest-session.md)：NSB-R1–R5，冻结前缀、原生事实采集、纯核/数量组合和完整execution提交。
- [V2原生隔离回测](native-v2-backtest-session.md)：NVB-R1–R5，复用同一Session/NSQ/NSH，显式V2身份、原始超额目标阻断及完整共享报告；实现进行中，真实来源与实盘另验。
- [隔离策略受管父宿主](native-strategy-host.md)：NSH-R1–R5，固定入口、Job预绑定、单一期限、有限结果与实际回收。
- [原生回测操作员入口](native-backtest-cli.md)：NBC-R1–R4，复用受管宿主、有限文件准入、同期限取消和明确运行回执。

- [原生回测工作区](native-backtest-workspace.md)：NBW-R1–R5，复用受管宿主的单轮启动、状态、取消及中文分页报告。

- [V2固定单元纯分配器](native-fixed-unit-allocation.md)：NFA-R1–R5，固定旧算法来源的独立原始权重计算、不可变输入/输出与有限预算；原生数量/执行另接。

- [V3动态风险与迟滞纯业务链](native-risk-history-pipeline.md)：NRH-R1–R4，完整历史复用同一特征/信号核，保留原动态风险与三日预算确认规则；原生桥与真实来源另验。

- [AI叠加纯策略事实与冻结回放](native-ai-overlay.md)：NAI-R1–R4，外部评分窄事实、原叠加预算/失败延续、明确可知/失效与独立纯库；研究服务保持退役。

- [原生实时策略接入](native-realtime-strategy.md)：NRT-R1–R8，标准CTA Factory与受管Runner、同核算法、组合Reader、实际分钟驱动及原生事实/生命周期；开发中，真实运行另验。

- [QMT显式历史缓存补齐](qmt-history-preparation.md)：HPR1–HPR4，固定内置函数、显式v6权限、原队列/认证SHM及未知结果恢复。

- [App托管QMT历史补齐产品](qmt-history-preparation-app.md)：HPRA配置、独立进程生命周期、只读状态、中文表达与普通安装。
- [V1历史版本纯链](legacy-v1-history.md)：LVH，1.0.0/1.1.0/1.1.1真实信号证券、起点和原分配，实际持仓周期版本分项接线。
- [来源历史范围与分段展示](source-history-chart-observation.md)：HCO，SDK0.15 Archive/Observed/Partial、实际窗口/补齐状态与跨谱系来源进入App图表及两个行情入口。

- [QMT v6 原生实时行情插件](qmt-native-parser-v6.md)：NPV6，显式v6完整能力准入、原full_tick/SPI和安装验收。

- [观衡候选升级与回退](app-candidate-upgrade.md)：模块C独立候选切换、已有数据和补齐任务连续性验收。

- [QMT因子与原WT前复权分析窗口](qmt-native-adjustment.md)：QNA，原生事件、累计因子和真实日线读回，供唯一1.1.2当前可见决策。
- [持续分析窗口生产](qmt-analysis-window-producer.md)：AWP，源实收、有界原生刷新、同日修订及原子发布；[来源合同](qmt-analysis-window-provider.md)。
- [已确认只读责任回收](qmt-read-retirement.md)：RR1–RR5，票据内容身份、完整结果消费确认、固定容量持续读取及未知原 ID 恢复。
- [完成回测报告的有界读取性能](backtest-report-read-performance.md)：BRP，原5秒HTTP双报告消费、等值规范化及深不可变快照。

- [WT共享内存当前报价](qmt-shm-quotes.md)：SQQ/SQR，原full_tick映射、Native快照消费及默认有限v6。

- [批量日线分析来源](qmt-analysis-batch-source.md)：QAB，显式v8、原列表SDK、批次身份/证券投影及已消费责任回收。

- [全市场日线准备](qmt-market-daily-preparation.md)：MDP，显式HPR v3、原缓存更新与批量捕获续接。

- [原生 Reader 离线构建](native-reader-offline-build.md)：固定 Git 与批准覆盖、同批 WT 依赖、原版/NRC/WLC 显式选择及普通安装读取验证。
- [原生数据组件固定源码构建](native-data-offline-build.md)：选中非交易原生组件的版本化源码、同批依赖及可搬迁原生组件切片。

- [沪深北日终广度与换手](observer-ashare-day.md)：同日原件、统一stock_day、停牌换手资格、固定包消费与持续来源边界。

- [执行故障核查恢复](execution-fault-recovery.md)：自有恢复准入、固定前后发行身份交接、原状态及资本观察。
- [WT日常启停与当前实例发现](wt-service-control.md)：正常启停、同账接续、显式持续运行及独立观衡跟随当前代。

- [Source证券名册与资料](qmt-security-reference-source.md)：全类别只读分页、逐组未知、详情原值及原请求恢复；Root维护来源实现，统一数据owner消费。

- [观衡活动策略与归档身份读取](observer-strategy-facts.md)：WT实际定义、逐份历史报告、独立只读发行。
