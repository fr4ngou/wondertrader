# 模块导航

- [WT闭合日线读取](collected-daily-history.md)：原Writer日线/收盘快照、统一历史与独立图表消费；持续原生日线配置后继单独核实。

- [观衡行情工作区](observer-market-workspace.md)：单搜索、自选五日小图、日周月范围与偏好状态。

- [证券目录与检索](security-search.md)：中文、拼音、代码前缀候选及规范行情身份。

- [策略与报告详情](observer-strategy-details.md)：实际账户资金/持仓、正式报告及分实例只读状态。

- [完成回测报告只读准入](backtest-report-reading.md)：原领域验证、有界规范纯值、深不可变快照及独立读取发行。

- [QMT账户读取责任回收](qmt-account-read-retirement.md)：原Native账户消费确认、原容量持续查询与金融证明保留。

- [持续策略分析数据](analysis-window-producer.md)：QMT日线/因子共享内存、原Native复权、持续QNA发布与WT生命周期。

- [独立WT运行装配](wt-runtime-owner.md)：固定组件工厂、来源晚到的执行等待、本地监督与原组件关闭职责。

- [QMT来源通信驱动](qmt-source-runtime.md)：同一原timer推进四类连接，共用认证、帧和业务owner；配置及实际资格分别核实。

- [同一QMT正文的只读账户连接](qmt-account-composed-source.md)：QAC复用原账户、交易、历史和全推owner，单策略线程、原生消费者及独立WT管理。

- [QMT常驻交易通信产品](qmt-trade-host-product.md)：普通Host/WT安装、正式配对、两代认证、未知委托责任及与QST/HPR同正文接入。

- [原生采集归档历史查询](collected-native-history.md)：原Writer的闭合DSB直接接统一SDK/App，实际内容更新无需手动再导入。

- [WonderTrader 原生行情采集](wondertrader-datakit.md)：QuoteFactory/WtDtCore/Writer的原生职责、文件、时段及来源接线。

模块说明记录职责和公共边界；行为要求以对应功能规格为准，实现证据在[证据索引](../evidence/README.md)登记。

| 模块 | 读取条件 |
|---|---|
| [WT数据能力与限制](wondertrader-data-capabilities.md) | 原生存储/Servo/Reader、周期、复权、缓存及扩展选择 |
| [WT策略与回测能力](wondertrader-strategy-capabilities.md) | 四引擎、宿主接线、调度、状态和回测撮合边界 |
| [WT交易与执行能力](wondertrader-trading-capabilities.md) | 原生目标/执行算法、风控、现金股票、持久状态及恢复 |
| [WT 原生插件](wondertrader-plugins.md) | 原生 API/SPI、加载与外部注入、配置默认值及编译边界 |
| [WT 原生存储](wondertrader-storage.md) | writer 队列与锁、时段归档、DSB 读写和线程退出 |
| [WT 历史数据可见性](wondertrader-history-visibility.md) | reader/引擎缓存、加载器与同实例历史补齐的公开扩展边界 |
| [原生历史文件适配边界](native-bar-file.md) | 原Helper公开ABI、容量、不可变文件读取与原store结果验证 |
| [原生历史 Reader](native-history-reader.md) | 独立历史服务、同实例刷新、切片生命周期、分钟事件与退出 |
| [QMT只读HTTP传输](qmt-read-transport.md) | 固定行情/账户域、完整响应、原ID认领、截止与回调排空 |
| [QMT共享内存连接](qmt-shm-connector.md) | 独立Host/Agent、认证bound-read、C++原生行情工厂、线程/关闭、离线工具与能力边界 |
| [QMT原生只读通道](qmt-readonly-trader.md) | 原TraderAdapter四查询、HTTP字段映射、版本化观察与owner关闭 |
| [QMT终端读取源](qmt-terminal-source.md) | 终端策略线程、有界只读结果、HMAC HTTP及独立源包 |
| [账户只读观察](account-observation.md) | 原Adapter一次四查询、有限产品宿主、值IPC及独立账户页面 |
| [QMT 持续行情插件](qmt-polling-parser.md) | 默认工厂配置、HTTP 轮询去重、订阅容量、回调与停止 |
| [WT 原生交易执行](wondertrader-execution.md) | 券商查询、回报、执行器、去重和各插件重连语义 |
| [服务商接入](providers.md) | 新接入、字段映射、SDK、连接与回调 |
| [市场数据](market-data.md) | 行情、历史读取、分钟处理、数据质量与存储 |
| [策略运行](strategy-runtime.md) | 时钟、调度、策略状态、组合目标与重启 |
| [交易执行](execution.md) | 委托、撤单、账户观察、执行状态与恢复 |
| [回测](backtest.md) | 数据回放、撮合、成本与结果复现 |
| [业务集成](business-integration.md) | 独立业务页面、策略配置、原生能力映射与外部消费者 |
| [原生工具链](native-toolchain.md) | 编译、锁定依赖、CTest、开发包与校验 |
| [受管运行时](managed-runtime.md) | 行情/回报调度、WT 外部插件注入、线程与退出 |
| [独立行情服务](market-service.md) | 观衡 HTTP 消费、原生 JSON ABI、源端连接与独立发布 |
| [历史作业](history-jobs.md) | Operations 持久任务、原生临时准备、日历证据与恢复 |
| [分钟消费](minute-consumer.md) | 安装wheel、历史预热、MarketData收据/游标、恢复与同线程关闭 |

新模块使用[说明模板](TEMPLATE.md)，在本索引登记。只有接口或依赖证据明确的关系才写入调用链。

- [QMT常驻只读连接](qmt-connection-lifecycle.md)：单一代际owner、旧请求保留与两端恢复；系统启动/实际终端资格另验。

- [QMT全推数据流](qmt-quote-stream.md)：内置全推、有界共享内存与原生DataKit薄装配。

- [行情数据结构](market-data-contracts.md)：报价/心跳、来源及标准分钟、文件与读取职责。
- [国信内置API索引](qmt-native-api-index.md)：随安装手册148项名称/页码及共享内存接入区别。

- [QMT历史缓存补齐](qmt-history-preparation.md)：显式缓存副作用权限、固定全局函数、有限任务身份及原历史回读。

- [QMT源日线资格](qmt-source-qualification.md)：安装API、单位证据、交易所日历、上市与缺口、模型时钟和实收时间。

- [原生前复权适配](qmt-native-adjustment.md)：QMT原生事件接原WT Reader，保留日期、基准与接收时间。
- [持续分析窗口生产者](qmt-analysis-window-producer.md)：WT 常驻来源刷新、原 Import/Reader/QNA 和 R24 原子发布。
- [QMT 已确认读责任回收](qmt-read-retirement.md)：源 Book、Host 原通信 Journal 与外部结果消费方的有界交接。

- [共享内存当前报价](qmt-shm-quotes.md)：报价Native、历史组合及读取责任交付。

- [批量日线来源](qmt-analysis-batch-source.md)：固定股票池资源分片、原SDK批次结果和C只读消费包。

- [全市场日线准备](qmt-market-daily-preparation.md)：原HPR缓存更新、v8回读、长工作流原slot续接。
