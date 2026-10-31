# WonderTrader 原生行情采集

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：框架模块说明。范围：QuoteFactory、WtDtCore 和默认 WtDataStorage；来源插件与发行实例另行配置。

## 入口与调用链

QuoteFactory 是独立的 C++ 行情采集程序。它读取 dtcfg 的基础资料、行情插件、Writer 和时段状态配置，启动原生采集过程，不依赖策略引擎或 wtpy。DataKit 在上游工程中组织这些数据组件。

| 职责 | 原生实现 | 行为 |
|---|---|---|
| 装配 | [QuoteFactory](../../src/QuoteFactory/main.cpp) | 加载基础合约、session、状态机、Parser 和 Writer |
| 行情接入 | [WtDtCore::ParserAdapter](../../src/WtDtCore/ParserAdapter.cpp) | 按 code、交易所 filter 或全部基础合约调用 IParserApi::subscribe；接收 IParserSpi 行情 |
| 写入路由 | [DataManager](../../src/WtDtCore/DataManager.cpp) | 加载 IDataWriter 工厂并转交 tick、L2 和收盘转储；可挂广播器 |
| 采集存储 | [WtDataWriter](../../src/WtDataStorage/WtDataWriter.cpp) | 保存 tick、按 session 生成分钟线、映射实时文件并生成历史文件 |
| 自动时段 | [StateMonitor](../../src/WtDtCore/StateMonitor.cpp) | 根据 session 和配置推进可接收时段，执行收盘 transHisData |
| 历史读取 | [IDataReader](../../src/Includes/IDataReader.h) / [默认 Reader](../../src/WtDataStorage/WtDataReader.cpp) | 读取原生文件；Loader 扩展由调用方注入 |

这里的 ParserAdapter 属于 WtDtCore，负责采集与落地。策略引擎中的同名 Adapter 属于 WtCore，各自保持其职责。

## 原生扩展与广播

原 [WtDtPorter](../../src/WtDtPorter/WtDtPorter.h) 公开 create_ext_parser、register_parser_callbacks 和 parser_push_quote，可由外部宿主送入同一 DataKit；它是原生扩展接口，调用方可按需编写薄绑定。procFlag=1表示完整累计快照，由原链切片；0表示已切片，2表示极简快照。使用时仍须核对应来源的字段和量额语义。

[DataManager::add_caster](../../src/WtDtCore/DataManager.h) 提供原生行情广播接缝。QuoteFactory 可按 shmcaster / broadcaster 配置装配 [ShmCaster](../../src/WtDtCore/ShmCaster.cpp) / [UDPCaster](../../src/WtDtCore/UDPCaster.cpp)，将处理后的行情交给下游。采集和存储可以集中在独立 DataKit 实例；这些广播接口、原生文件及来源插件分别承担不同职责。DMB/DSB落地本身不依赖 PostgreSQL 或 Docker。

## 全市场与数据口径

原 Adapter 的全量集合来自已加载基础合约。它支持一次向插件提交全部合约；来源插件的批次、订阅额度和吞吐由该插件与行情提供方决定。证券发现、上市变更及基础资料由受管清单提供，缓存文件清点描述已存在的数据库存。上游股票配置是示例资料。

Writer 接收 tick 后按 session 计算分钟标签，以观测价格形成 OHLC，以输入的量额语义计算分钟量额。09:30 时段内数据进入右端 09:31 分钟，节末使用原生时段边界处理。行情插件负责把来源时间、合约和量额字段正确映射到原生结构。轮询插件的一次 pump 若同步调用 Writer，预算包含其落盘成本；应按批次设置工作量，订阅全集与每次处理数分别配置。

原生采集保存所接收的数据。来源官方分钟、遗漏行情后的历史修订及复权数据由相应历史路径处理；缺口查询或历史 Loader 属于独立接口。采集、历史准备、来源口径和完整覆盖分别验收。

## 文件、时段与生命周期

默认 Writer 在 rt/min1 下保存实时 DMB，在收盘转储后向 his/min1 保存压缩 DSB。disablemin1 控制一分钟线，disablehis 控制历史；其他周期及 tick 按显式配置选择。allday 模式绕过 DataManager 的状态机接收门，正常日间采集可使用原 session 状态机。收盘作业依赖程序继续运行至任务结束。

async 配置选择 Writer 写入方式。行情回调、Writer 工作线程和收盘任务各自沿原生实现运行；停止入口应先确认行情生产者停止，再释放其依赖和 Writer。文件存在、session marker、进程退出及完整字段回读代表不同证据。原生映射文件使用明确的写者，实例切换和历史导入避免同时改写同一数据根。

## 构建与适配

本仓独立 native profile（外部历史/待归仓路径：`../../cmake/native/CMakeLists.txt`） 构建 WtDtCore 和原 QuoteFactory 入口，安装实际选择的行情插件和 Writer。上游 SDK 专用插件的构建后复制由自有安装配置选择，原生采集算法及存储实现保持。

QMT 采集适配使用 ParserQMTHost（外部历史/待归仓路径：`../../src/ParserQMTHost/Factory.cpp`） 和终端外 Host；来源通过共享内存到达 Host，C++ 插件按原接口交付 DataKit。终端内的受限运行规则见 [SHM 模块](qmt-shm-connector.md)。运行参数及证据见 [采集规格](../specs/native-datakit-collection.md)；真实来源、全市场持续运行和自动收盘资格以具体发行证据登记。

全推来源接线见[QMT全推数据流](qmt-quote-stream.md)。它以原公开C++组件装配薄会话，共用原Writer；原轮询插件是另一路来源适配，吞吐与来源资格分别记录。


## 后台检查与关闭边界

固定上游08b230dd的默认Writer在init启动独立check_loop，按10秒间隔检查映射；release设置终止标志、等待收盘proc线程并释放映射，未等待检查线程。检查循环在睡眠前判断终止，睡眠后继续检查。因此公开release返回与全部后台线程退出分别核实；同步async=false也保留该检查线程。实际关闭后的检查线程访问反例及函数机器码身份见[原版Writer后继证据](../evidence/2026-10-28-qmt-quote-performance.md#后继完整规模关闭后原生根因已定位)。原收盘任务启动后检查循环有自行退出分支，其完整停止资格需按实际宿主验证；扩展宿主保持先停生产者再收束后台依赖，新增框架修正沿既定审批规则。

## 可选择的生命周期适配库

显式配置 `writer.module=WtDataStorageLifecycle` 选择独立构建库；缺省或 `WtDataStorage` 保持原库。统一差异由固定上游生成，仅涉及Writer两文件，原分钟聚合和格式继续复用。注册表保护稳定块身份，块锁覆盖映射使用/扩容/过期；关闭先拒绝新工作、排空已受理存储顺序，唤醒并等待检查/工作/归档线程，再销毁映射。检查线程释放的是闲置内存映射及句柄，行情文件继续保存在磁盘。

自有NativeDataKitSession由管理线程关闭外部输入，再提交原收盘归档并排空。Python `archive_and_close(session_id)` 只供显式适配库；调用者随后使用原Helper验证历史文件的实际字段和条数。归档错误可能保留实时DMB等待处理，接口返回和session marker各自不能证明数据完整持久。metadata/casters/dumpers须在首次工作前串行装配且寿命覆盖release；普通广播可查询/同步重入，归档dumper不能同步等待后续工作或关闭。跨进程写相同根及强制中断I/O另外管理。

自有Session的ObservedDataManager通过原IDataWriterSink::outputLog记录Writer实际LL_ERROR原子闩锁，保持原日志输出。原ParserAdapter的void回调不传递writeTick返回值，因此自有push在每次原回调后检查该闩锁；原合法时段过滤不按广播数差额判断失败。counter 4及管理线程check_health覆盖无后继批次的后台失败。C接缝close返回0表示已释放且无Writer错误，+1表示已释放但Writer曾失败，负值保留句柄；Python先记录实际释放，再报告业务错误。受管服务在失败时停止接收且保留错误，不发布归档成功收据。

此模式的发行资格按最终候选身份记录；实现、合成验证、真实来源及生产切换分别登记。详见[生命周期规格](../specs/native-writer-lifecycle.md)和[本轮实施证据](../evidence/2026-10-28-writer-lifecycle-afternoon.md)。
