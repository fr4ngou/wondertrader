# 市场数据

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块说明。所有者角色：数据维护者。状态：框架原生组件源码已存在；各数据源覆盖及运行资格分别登记。

## 职责与调用链

行情接入 → 规范化与分钟处理 → 实时/历史存储 → 数据读取 → 策略、回测或业务消费者。

Python组件的版本化来源、随包模块与历史兼容发行见[永久来源规格](../specs/market-python-sources.md)及[构建手册](../runbooks/market-python-sources.md)。原生库和普通解释器角色分别组装，实际调用路径按运行配置及模块导入证据核实。

主要入口为 [WtDtCore](../../src/WtDtCore/CMakeLists.txt)、[WtDataStorageAD](../../src/WtDataStorageAD/CMakeLists.txt)、[WtDataStorage](../../src/WtDataStorage/CMakeLists.txt)，历史扩展接口见 [IDataReader](../../src/Includes/IDataReader.h)。辅助组件包括 `WtDtHelper`、`WtDtServo`；独立运行入口见 `QuoteFactory`。

受管来源适配入口为 History（外部历史/待归仓路径：`../../src/GuanhengData/History.h`） 与 MarketParser（外部历史/待归仓路径：`../../src/GuanhengData/MarketParser.h`），分别承担原生历史准备和注入式快照接入。其来源、覆盖、文件布局、冻结与预算契约见组件说明（外部历史/待归仓路径：`../../src/GuanhengData/README.md`）。调度由[受管运行时](managed-runtime.md)持有。

MinutePipeline（外部历史/待归仓路径：`../../src/GuanhengData/MinutePipeline.h`） 将累计快照、原生 WT Writer/Reader、时段规则与分钟闭合消费者接在同一受管线程。时钟、起始基线、逐证券预热及覆盖资格分别表达；闭合回调复制原生结果，复用框架分钟计算。

来源重绑逐证券隔离尚未闭合的bucket，并重新预热首分钟，来源身份随数据维护。原DataKit、StateMonitor和Writer承担采集、时段推进、分钟生成及收盘归档；组件接口见[原生存储模块](wondertrader-storage.md)。默认Writer沿原组件，已批准的生命周期适配仅由显式WtDataStorageLifecycle配置选择，分钟算法和DMB/DSB格式继续复用原实现。日间采集与历史查询分别持有其运行实例，历史查询路径创建IRdm。

## 数据与状态

策略读取当天分钟沿 `WtDtMgr` → `IDataReader::readKlineSlice`，分钟闭合通知沿 `IDataReader::onMinuteEnd` → `IDataReaderSink::on_bar`；按范围的随机读取沿 `IRdmDtReader`。`path` 配置指向DataKit数据根，原Reader读取其 `rt/min1`；可选 `his_path` 由原策略Reader指定历史目录。调用者的交易日、分钟时钟、基础资料与切片生命期是装配条件。历史独占源Reader继续保持自身根约束，活动DMB不伪装成已冻结导入根。读取和原闭合回调的真实数据范围见[运行证据](../evidence/2026-10-29-native-live-reader.md)。

自有 `GuanhengRealtimeReader` 通过显式 `minute_native` 对象选择原 `WtDataReader`，m1读取与分钟通知交由原Reader，缺省继续HTTP，d1沿独立delegate。适配层限制返回副本条数、活动条数及切片数；受管宿主先停止调度、确认 `stopDataReader` 后删除Reader，已交切片独立持有，DLL保留到最后切片释放及进程退出。配置与路径容量约束见[NMR规格](../specs/native-minute-reader.md)。

Windows 原生历史根通过永久 `.guanheng-lease-lock` 的独占句柄串行化目录 lease 的完整生命周期，避免删除/重建竞争；仅明确文件共享/锁冲突返回背压，其他 IO 保留原错误。目录标记继续保留崩溃核查和显式恢复边界。

数据契约明确证券身份、源时间与接收时间、交易日历/时段、量额单位、精度、复权和分钟边界。实时未结束 bar、已结束 bar、补发历史及修订分别标识。输入文件、内存切片和回调对象具有明确生命周期。

数据来源和覆盖说明随数据集维护；查询返回空、文件首尾范围或固定根数均须结合适用市场规则解释。缺口补齐按已声明的数据源能力与预算执行，耗时准备使用异步任务或明确 pending 状态。

## 失败与验证

覆盖截断、重复、乱序、跨日、缺时间、停牌、上市前、数据修订、磁盘故障和慢消费者。回测输入冻结版本；资源预算、来源准入及恢复要求在对应规格定义。

框架文件格式和存储能力复用现有实现，扩展前核对接口；具体配置与命令见[构建手册](../runbooks/build.md)。

已下载 QMT 分钟历史的外部导入契约见[QMI 规格](../specs/qmt-minute-import.md)，输入准备、独立历史根及读取验证见[操作手册](../runbooks/qmt-minute-import.md)。策略按需历史、自动补齐、快照与闭合分钟订阅仍按完整目标逐项接通。

原生历史业务查询接缝见[NHQ规格](../specs/native-history-query.md)。DSB的sidecar/hash/冻结校验保留在Store，启用配置后索引和范围读取交给公开IRdmDtReader；查询不再调用Helper完整解码。基础资料从启动配置加载，修订实例的释放与页面请求分开；缓存载荷预算与进程总RSS分别解释。

本地QMT缓存入口提供inspect清点、export和convert：首末抽样清单用于选择批次和核对实际文件尾部，coverage保持unknown；export/Importer继续逐行校验并复用WT原生DSB。源码为integrations/guanheng/qmt_local_dat.py，操作见[本地缓存手册](../runbooks/qmt-local-dat.md)，全5342文件清点与三条首分钟差异后继见[实际证据](../evidence/2026-10-27-qmt-local-dat-inventory.md)。全库存与尾部状态以[模块A当前交付](../migration/module-a-delivery.md)及其输入身份对应的证据核验；文件存在、成功导入与市场覆盖完整分别表达。


## 来源历史价格质量

来源原值保存和标准OHLC有效性按[RS8](../specs/qmt-source-history.md#rs8-来源价格范围质量与原值保存)分工。DAT、QMI导入与source Reader复用[price_quality](../../integrations/guanheng/price_quality.py)的唯一分类规则，异常价格原样保存并以有限摘要绑定DSB；Reader实际重算。canonical路径继续严格OHLC；来源SDK保留原数据，标准图表明确指出异常分钟。规则不修改WT框架、源缓存、活动SHM协议或交易路径。当前真实结果见[来源价格质量证据](../evidence/2026-10-27-qmt-source-price-quality.md)。

字段、源值/标准值、全推数据流、数据根与读取方式的集中说明见[行情数据结构与读取边界](market-data-contracts.md)。内置API的版本、可调用目录及性能边界见[国信Python手册](../runbooks/guosen-qmt-python.md)。

## 已有库存与按需补齐

来源原值服务先按证券、时段和limit读取已登记成功根；自动补齐为显式source-preparing模式，复用外部HPR Host、认证SHM、原策略线程及原Importer/Helper/Reader。一次查询的读取范围与单次补数预算分别定义，旧根保持原身份，新根验证成功后登记其原始来源。接口、启用条件和当前支持的日期范围见[RS13规格](../specs/qmt-source-history.md#rs13-最近n根选择有限尾窗与分段来源)；实际接线资格见[模块A交付](../migration/module-a-delivery.md)。现有缓存读取、下载调用返回和确有新数据分别核验；空窗口保持明确待处理状态。
