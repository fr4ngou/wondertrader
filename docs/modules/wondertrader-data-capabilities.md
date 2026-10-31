# WonderTrader 原生行情与存储能力

类型：长期模块能力说明。固定 C++ 上游：`08b230dd05facf6d650d949bfe51054115a2ecb1`。状态：主要公共路径已按源码核实；实际来源、并发组合、故障恢复和容量按对应环境验证。下游实现单独登记；升级时复核实现与配置。

原生实现存在、配置适配后可用、明确缺口和待验项目分别列明。开发入口见[能力目录](../development/wondertrader-capabilities.md)及[复用规则](../development/wondertrader-reuse.md)。

## 原生执行链与组件职责

```text
行情供应商 → IParserApi / ExtParser → WtDtCore::ParserAdapter
                                       ↓ 标准代码、合约、快照语义
                              WtDtCore::DataManager
                                       ↓ IDataWriter
存储选择 A：WtDataStorage（DMB + DSB）
    ├─ WtDataReader（IDataReader）→ WtCore::WtDtMgr → 策略
    └─ WtRdmDtReader（IRdmDtReader）→ WtDtServo → 查询/订阅
存储选择 B：WtDataStorageAD（LMDB）
    ├─ WtDataReaderAD（IDataReader）→ WtCore::WtDtMgr → 策略
    └─ WtRdmDtReaderAD（IRdmDtReader）→ WtDtServo → 已实现查询子集

已有历史 → 来源转换 → WtDtHelper::store_bars → A 的历史 DSB 文件
```

`QuoteFactory` 是可配置的独立采集宿主，加载基础资料、Parser、Writer、时段状态机和广播器。`WtDtPorter` 另提供 `initialize/start/create_ext_parser/parser_push_quote` 等 C ABI，支持外部扩展 Parser 和历史 Dumper。`WtDtHelper` 是读写/转换工具库，`WtDtServo` 是随机读取与订阅服务库。它们各有职责，不宜统称为一个“Reader”。

来源：[QuoteFactory/main.cpp][S01]、[DataManager.cpp][S02]、[IParserApi.h][S03]、[WtDtPorter.h][S04]。

## 能力清单

| 能力 | 静态结论 | 原生入口与实际限制 |
|---|---|---|
| 独立采集运行、插件加载 | 直接支持 | QuoteFactory + WtDtCore；配置 sessions/commodity/contract/holiday、Parser、Writer、广播器。宿主退出/插件释放必须单独验收。[S01][S02] |
| 实时快照、逐笔及部分 L2 接入 | 适配/配置后支持 | IParserApi 的 quote/order queue/order detail/transaction；procFlag 区分已切片、累计完整快照、极简快照。来源字段、增量和单位必须符合这些语义。[S03][S05] |
| QMT/通达信专用原生 Parser | 缺失 | 固定上游插件树没有这两个来源。应接现有 IParserApi/ExtParser，保持原生写入链；供应商插件属于接入扩展。 |
| Parser 通用历史下载 | 缺失 | IParserApi 管连接、订阅和实时数据，没有历史区间下载方法。来源下载/导出是适配职责，下载结果进入原生格式。[S03] |
| 实时 Tick、m1、m5、日线形成与存储 | 直接支持 | WtDataWriter 的 updateCache/pipeToKlines/历史转储；日线与分钟线可配置开关。输入遗漏和 skip_notrade_bar 会影响实际覆盖。[S06] |
| Tick/L2 历史、实时映射 | 直接支持 | 默认 Writer/Reader 有 tick、orderqueue、orderdetail、transaction 文件通路；供应商权限/数据完整度由来源决定。[S06][S08] |
| 历史 DSB、实时 DMB 读取 | 直接支持 | 默认 Reader 与 Helper；类型、版本、标准代码、基础资料、根目录要匹配。[S07][S08][S09] |
| 按时间范围、最多 N 根、按日期查询 | 直接支持（默认文件 Reader） | WtDtServo C ABI；有数据时get_bars_by_count返回可用尾部，允许不足N根；空历史路径可虚报请求条数而无数据块，须核对实际回调。按日期 bars 限分钟；按范围/数量支持日线。[S10][S11][S12] |
| 实时 Tick/分钟订阅 | 适配/配置后支持 | Servo subscribe_bar每次替换原bar/内部tick订阅，其回调随tick更新当前bar，包含形成中数据。策略onMinuteEnd是另一条路径；闭合、多标的和恢复语义须沿实际入口验证。[S10][S11][S13] |
| 秒线、N 分钟、N 日重采样 | 直接支持 | WTSDataFactory，Helper resample_bars，Servo 分钟倍数转换；根据交易时段聚合。周/月历法周期不由 N 日自动等价，未核实专用周/月入口。[S11][S14] |
| 股票前/后复权、连续合约拼接 | 适配/配置后支持 | 默认 WtDataReader 的 Q/H 因子处理、hot/second/custom 规则。因子及映射需配置/加载，版本时点和修订传播另验。[S13][S15] |
| 交易时段、夜盘、节假日和交易日换算 | 适配/配置后支持 | WTSBaseDataMgr/WTSSessionInfo；使用配置的时段、偏移、节假日和周末规则。没有因此自动获得权威最新节假日或逐证券停牌覆盖。[S16][S17] |
| 合约/证券、上市与到期日 | 适配/配置后支持 | WTSContractInfo setDates/getOpenDate/getExpireDate、标准代码转换。证券清单和日期需要正确来源；分钟级停牌事实不是简单日期字段。[S18][S19] |
| 已下载历史导入、CSV 转换 | 直接支持工具；来源适配后可用 | WtDtHelper store_bars/trans_csv_bars/read_dsb_bars。调用方校正时间、排序、单位、代码及重复；store_bars 写整块文件，不是通用 upsert。[S09] |
| 权威缺口识别、自动向供应商补齐 | 缺失统一实现 | Reader 返回已有记录；IHisDataLoader 是同步加载扩展，不自带供应商重试/完整覆盖证明/任务调度。来源适配可补真实缺失能力，不能再造第二套行情存储。[S20] |
| 导入后缓存刷新 | 部分直接支持 | Servo 的 clear_cache 清底层 RdmReader；策略 IDataReader 没有相同公共方法；Servo 自身派生周期缓存也须核查，详见下一节。[S12][S13][S21] |
| 进程间行情共享和 UDP 广播 | 适配/配置后支持 | ShmCaster/ParserShm、UDPCaster/ParserUDP；用于原生实时通路，不能当成持久消息确认协议，也不自动兼容任何 外部自定义共享内存布局。[S22][S23] |
| LMDB 原生替代存储 | 部分直接支持 | DataStorageAD 有 Writer、策略 Reader、随机 Reader；随机 Reader 的按数量 bars/ticks、按日期 ticks 是 TODO，不能宣称完全替代默认实现。[S24][S25][S26] |
| 原生 HTTP 鉴权/分页/观衡 JSON 协议 | 缺失于已核实 Servo C ABI | 原生提供 C ABI；服务隔离、鉴权、DTO 转换可由薄宿主承担。请求 deadline/正文上限是宿主边界，不需要第二套 bars 数据库。[S10] |
| 全市场十年容量、生产吞吐、跨进程多写者 | 未知/未验 | 源码展示格式、缓存和锁机制；没有目标硬件/来源/规模的测量，也没有据此建立多写者安全资格。 |

## 三条读取路径与缓存修订边界

### 策略 IDataReader / WtDataReader

`IDataReader` 公开 init、readKlineSlice/readTickSlice、onMinuteEnd 等；`IHisDataLoader` 允许外部返回 raw/final 历史及复权因子。final 表示外部已经完成相应处理，raw 允许内部继续复权/拼接。外部 loader 不是 WT 默认依赖一个独立数据库的证据。

`WtDataReader` 按标准代码与 period 缓存历史。`readKlineSlice` 只在 key 未缓存时走初次文件/loader 加载，随后处理历史与实时拼接；扩大 count 本身不构成重新读取 DSB 的命令。空文件/不存在文件产生的缓存状态也要按同实例重试验证。`onMinuteEnd` 推进实时分钟回调，不等价于重新装载修改后的历史文件。`IDataReader` 没有公开 clearCache，历史修订应先查该调用路径的完整重建/宿主生命周期办法。`cacheFinalBars/cacheRawBars/readKlineSlice/onMinuteEnd` [S13][S20]

### 数据服务 IRdmDtReader / WtRdmDtReader

`WtDtServo` 加载 `createRdmDtReader`，使用独立接口。默认 `WtRdmDtReader` 有范围和数量查询；有历史数据时数量逻辑使用 `min(available,count)`。空历史时，`indexBarFromCacheByCount`返回NULL但未归零引用count，调用者仍以请求数构造无数据块切片，C ABI可返回请求条数却没有数据回调；调用者必须核对实际数据块。可用不足 N 根既不自动证明缺口，也不自动失败。来源完整性和调用方是否接受不足，属于明确的业务条件。`readKlineSliceByCount` [S12]`init` [S21]

`WtRdmDtReader::clearCache` 清历史和实时映射缓存。可是 `WtDtServo::WtDataManager::clear_cache` 只调用 `_reader->clearCache()`；其为重采样建立的 `_bars_cache` 在本方法中没有清除。日志“All cache cleared”不能作为整个派生缓存已清除的证明。原样隔离实验已复现：m1清缓存后更新，预先缓存的m3仍保留旧条数/旧值，新进程重建后可得最新m3。各周期仍需按实际输入分别验收。`clearCache` [S12]`clear_cache/get_kline_slice_by_count/get_kline_slice_by_range` [S21]

### 策略 WtCore::WtDtMgr 与派生缓存

`WtCore::WtDtMgr` 再承担策略周期整理和缓存。times=1 且未 force_cache 时可直接走 Reader；其他条件可能使用本层缓存/重采样。清底层文件缓存并不能自然推出所有上层缓存已更新。所有修订方案必须列出实际 reader 类型、manager、period、force_cache、切片生命周期，按选定原生路径验证。`get_kline_slice` [S27]

## 文件格式、历史导入与数据语义

- 默认结构：实时 `rt/ticks`、`rt/min1`、`rt/min5` 等目录；文件按交易所、代码组织为 DMB。历史 bars 为 `his/day|his/min1|his/min5/<exchange>/<code>.dsb`；历史 ticks/L2 另按日期组织。部署必须以 Writer/Reader 对应配置和真实输出核对，避免凭文件后缀猜目录。[S06]
- DMB 是有 size/capacity 的实时映射块；DSB 有类型与版本头。RAW/CMP 与 RAW_V2/CMP_V2 区分旧/新结构和压缩状态；“DMB/DSB”本身不表示数据库事务或访问鉴权。[S07]
- 当前 WTSBarStruct 在显式 8 字节布局下为 88 字节（date+reserve、time、9 个 double），旧格式成交量等字段不同。分钟内部时间编码为 `(date-19900000)*10000+HHMM`；外部查询 YYYYMMDDHHMM 经过转换。date/交易日和自然日时间应分开核验，夜盘尤其如此。[S08][S13]
- 默认压缩经 WTSCmpHelper 使用 Zstandard，默认级别 1。解压先按帧声明长度分配；该辅助接口没有调用方传入的解压总量上限。下游新增读取限制须单独登记，不能计入上游现有能力。来源可信度、损坏文件边界及隔离预算需另验。[S28]
- store_bars 把给定数组压缩写入一个新文件；它不负责下载、完整性证明、排序、去重、跨文件事务，也不提供通用合并 upsert。对既有区间修订，应在单写者/停读或安全切换的边界完成正确合并并回读验证。`store_bars` [S09]
- store_bars 中 `create_new_file` 后条件写入，函数尾返回 true；这个布尔值不能独立证明文件成功、完整落盘。精确边界是该 Helper 方法的结果语义，应以生成文件和原生回读校验，不扩大解释为所有 WT 写入都失效。[S09]
- 原生分钟 K 线按交易时段分钟位置形成，分钟结束时间与段末有特殊处理；配置 skip_notrade_bar 可跳过零成交输入。不能将“没有记录”统一解释为源故障，也不能凭时钟自行填一根后声称原生事实。`pipeToKlines` [S06]

## 复权、重采样、基础资料的使用边界

默认 Reader 的股票 Q/H 处理使用配置/loader 提供的复权因子；价格处理与 `_adjust_flag` 控制的成交量、成交额、持仓等字段处理分开。连续合约按 hot/second/custom 规则重组。不能拿一份未标明因子时点的缓存声称已具备任意历史时点回测一致性。`cacheAdjustedStockBars/cacheIntegratedBars` [S13][S15]

WTSDataFactory 可按会话分段重采样，分钟、日线和 tick→秒线有独立实现。Servo 对 mN 可选 m1 或 m5 作为基础。应优先复用这些算法，保持单一周期计算实现。重采样的闭合/段末、午休/夜盘、缺记录、复权先后和刷新应以选定配置的原生结果作为基线。[S11][S14]

WTSBaseDataMgr 支持加载节假日、时段、证券和交易日换算；未知模板的退化行为与本机时间函数使用提示基础配置必须准入。框架提供规则执行机制；最新交易所日历、证券生命周期、停牌资料的来源与更新仍是外部接入职责。使用一份权威输入转换为 WT 配置，观衡消费一致结果，避免两套时段运算长期并存。[S16][S17][S18]

## 并发、进程与生命周期

| 边界 | 已核实机制 | 安全解释与待验项目 |
|---|---|---|
| Writer 异步输入 | writeTick 可入队；pushTask 用 mutex/condition，工作线程交换队列；任务 retain/release | 返回成功首先代表接收，不代表持久化确认；队列未见配置容量上限。异步背压、持续慢盘、异常退出要测。[S06] |
| 证券块写入 | tick/L2/bar 的块级 SpinLock；扩容时重新映射 | 局部块锁保护相应代码段；不能推断所有 map、生命周期和跨进程共享结构均由同一锁保护。[S06] |
| Reader 切片 | slice 引用已有数组/映射，Servo 回调后 release | 原生数据指针必须在其有效生命周期内消费或复制。清缓存、重映射、释放和正在执行的回调须有宿主协调。[S10][S12][S20] |
| 原生 Servo 宿主 | C ABI 经进程内 singleton runner | initialize会启动默认Reader检查线程，即使无Parser。外部调用单所有者仅限制调用线程；检查线程遍历RT map，与插入/clearCache间尚缺共同map级锁证据。公开C ABI无stop/release，Reader局部析构join尚未接入完整宿主释放链。`getRunner` [S30] |
| Writer 释放 | release 设置 terminated，join `_proc_thrd`，销毁实时块 | 本方法未见 `_task_thrd`/`_proc_chk` join；必须结合宿主和成员实际销毁顺序复现，记录特定路径。静态可疑点不能直接升级为“整个 WT 无法使用”。`release` [S06] |
| 历史修订 | 历史压缩写入与 Reader/manager 缓存独立 | 要验证导入、缓存失效、旧切片、订阅和新查询的完整切换。原地写文件后马上清缓存的组合尚无运行资格。 |
| 默认文件跨进程 | 采集 Writer 和读取进程借助文件/映射共享 | 单一 Writer 所有权与多个读取者应明确。未发现支持任意多写者的统一跨进程事务契约；不要对同一文件启动两个写入者。[S06][S07] |
| SHM/UDP 发送 | 环形队列与索引，或 UDP 报文 | 队列容量、重启初始化、消费者落后、丢包/重订阅是协议边界；无持久 ACK/事务重放含义。可靠命令与任务确认须按各自协议单独核实。[S22][S23] |
| LMDB | WtLMDBQuery 使用 LMDB 事务、put_and_commit | 确有事务机制；事务范围取决于数据库/Query 使用，不能推断跨 tick、各周期、各证券库原子一致。[S24][S26] |

上述机制按路径列明；空历史计数和派生缓存修订已有隔离复现，RT map并发仍为静态待验风险。必要修复先以固定原生配置复现、追踪 owner/线程，再评估已有接口或宿主约束；核心修改继续遵守核心变更批准规则。

## DataStorageAD 选型边界

DataStorageAD 已经提供 LMDB Writer 和 Reader，属于 WT 原生可选模块。Writer 对 tick 与各周期 bars 用原生 key 和事务写入；默认 tick mapsize 16 MiB、kline mapsize 8 MiB，可配置。mapsize 是映射容量配置，既不是实际磁盘占用，也不是容量实测；自动扩容行为尚待实测确认。[S24][S26]

固定基线的 `WtRdmDtReaderAD` 有三处明确 TODO 返回 NULL：`readTickSliceByCount`（73 行）、`readKlineSliceByCount`（251 行）、`readTickSliceByDate`（257 行）。范围查询有实现；策略 `WtDataReaderAD::readKlineSlice` 有实现。两个 Reader 的能力不能互相替代声明。[S25][S29]

因此默认 DSB/DMB 是当前覆盖 Helper/Servo 查询更完整的原生基线。是否选择 AD 应由明确的运行/修订需求和实际测试决定，不能为“有事务”直接替换全部原生存储，存储选择以所需原生接口和验证结果为依据。

## 容量依据、性能未知项与验证清单

88 字节 × 实际 bars 条数只是新结构的未压缩数据体估算。以纯计算示例 240 分钟/日 ×250 日/年 ×10 年 =60 万根，数据体约52.8 MB/证券；该数字没有计入压缩率、上市时长、停牌、Tick/L2、m5、索引、预分配、复制与缓存。全市场规模必须使用实际证券/日历清单和样本压缩结果测量。[S08]

默认历史文件整块解压；Reader 历史向量和多周期缓存占内存。Servo 派生周期初次可读取全部基础历史（UINT_MAX）形成缓存；当前核查未确认统一全局 LRU/内存上限。Writer 异步队列也不能当成背压机制。没有本机吞吐/延迟数字，不能由 C++/mmap/Zstd/LMDB 名称推出“满足全市场”。[S06][S12][S21]

最小验证矩阵：

1. 固定上游原生 Helper 写入→默认 Servo range/count/date 回读；包含不足 N 根、空记录、多个交易日，记录真实返回区间。
2. A 股午休、段末、零成交、上市边界；供应商快照增量语义用合成数据先验，来源实测单独标资格。
3. 同进程历史补齐/旧值修订→原始 m1、派生 m15、策略 Reader 各读一次；把三层缓存和旧切片寿命逐项列明。
4. 复权因子更改、Q/H/不复权、成交量口径、连续合约规则分别验证，拒绝双重加工。
5. 单 Writer/多读进程、回调期间清理、映射扩容、慢盘、采集暂停与正常退出；每例给出线程 owner 和完整停止顺序。
6. 损坏/截断/超大压缩头、源字段异常及写入失败；核验原生返回、宿主隔离和原文件保留语义。
7. 按真实证券数量/十年历史/明确硬件测启动时间、峰值 RSS、查询 P50/P95、并行读写与收盘转储；统计缓存和每个派生周期的增量。
8. 原生 Servo→调用宿主→产品图表/分析的连续测试；真实、异常、空态分开，不以 synthetic 测试声称 供应商实盘已验。

本说明登记源码与接口边界。上游 `src/TestUnits/test_session.cpp`、`test_codehelper.cpp`、`test_lmdb.cpp` 等需按功能挑选复用，这些入口尚不足以证明其具备以上整链/生产规模覆盖，也没有声称上游不存在测试。

## 公开Reader所有权与原生组合

`IRdmDtReader`公开create/delete工厂、范围/count与clearCache。宿主可以显式拥有Reader，在调用结束且所有借用切片释放后，经原delete进入默认Reader析构/join。sink、基础资料与库保持有效至删除完成。Servo单例宿主的释放接线与这个公开工厂是不同层级。

原`WTSDataFactory::extractKlineData`接受基础K线切片与时段，生成派生数据；调用方可以在当前输入上重新生成，避免使用另一宿主的旧派生缓存。完整周期/因子/输入代际的选择仍需契约，不能通过无效计数切片构造成功结果。[S14][S31]

[公开Reader实验](../evidence/2026-10-21-native-reader-ownership.md)提供历史-only正常销毁、重新读取后原生重采样的限定运行依据。RT map检查线程、异常清理、跨进程写入及热卸载另验。

## CTA闭合分钟与来源条件

策略`stra_get_bars`注册数据和主K线；`stra_sub_bar_events`开启相应通知，本身不代替成功的数据注册。原Ticker在跨分钟、本地期限及收盘兜底处调用Reader.onMinuteEnd，再调用Engine.on_schedule。默认Reader扫描每个已缓存证券的未读DMB条目，按bar结束时间筛选、推进游标，最后由DtMgr统一通知。原Engine在on_bar和on_schedule的线程池路径分别wait；策略主K线已经闭合时才计算。[S13][S27][S32][S33][S34]

默认实时读取需要原Writer形成DMB；数据先写、再广播/触发策略是完整拓扑。稀疏快照聚合只代表已观察样本，不能因此证明供应商真实分钟OHLC。IDataWriter无通用writeBar；已形成分钟源应核公开Reader等接缝，避免伪造tick。[S06][S35]

本地时钟可闭合已观察分钟，无源时不制造连续行情。Reader可能一次补发多条bar，之后的一次调度与每条历史逐次计算有不同语义。证券之间也没有自动提供全市场同步快照；组合策略按输入契约判断时点和覆盖。恢复后当前交易触发与研究回放分别处理。[S13][S32][S33]

## 固定版本源码索引

下列 S 引用均固定在 C++ 上游提交，符号名见正文，可直接通过 `git show 08b230d:<path>` 复核。

[S01]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/QuoteFactory/main.cpp
[S02]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtCore/DataManager.cpp
[S03]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/IParserApi.h
[S04]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtPorter/WtDtPorter.h
[S05]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtCore/ParserAdapter.cpp
[S06]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataWriter.cpp
[S07]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/DataDefine.h
[S08]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/WTSStruct.h
[S09]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtHelper/WtDtHelper.cpp
[S10]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtServo/WtDtServo.h
[S11]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtServo/WtDtRunner.cpp
[S12]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtRdmDtReader.cpp
[S13]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataReader.cpp
[S14]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WTSTools/WTSDataFactory.cpp
[S15]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WTSTools/WTSHotMgr.cpp
[S16]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WTSTools/WTSBaseDataMgr.cpp
[S17]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/WTSSessionInfo.hpp
[S18]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/WTSContractInfo.hpp
[S19]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Share/CodeHelper.hpp
[S20]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/IDataReader.h
[S21]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtServo/WtDataManager.cpp
[S22]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtCore/ShmCaster.cpp
[S23]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtCore/UDPCaster.cpp
[S24]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorageAD/WtDataWriterAD.cpp
[S25]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorageAD/WtRdmDtReaderAD.cpp
[S26]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WTSUtils/WtLMDB.hpp
[S27]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/WtDtMgr.cpp
[S28]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WTSUtils/WTSCmpHelper.hpp
[S29]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorageAD/WtDataReaderAD.cpp

[S30]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtServo/WtDtServo.cpp

## 配套行为证据

[原生Servo历史与生命周期实验](../evidence/2026-10-21-native-servo-behavior.md)记录固定源码构建、真实样本回读、空路径和缓存修订结果。历史子进程正常退出仅证明该隔离范围；实时候选、插件停止、DLL热卸载及跨线程资格需分别验证。

[S31]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/IRdmDtReader.h
[S32]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/WtCtaTicker.cpp
[S33]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/WtCtaEngine.cpp
[S34]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/CtaStraBaseCtx.cpp
[S35]: https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/IDataWriter.h

## 下游单项覆盖

上述支持边界按固定上游列明。随机Reader空历史count输出在本系统有用户批准的[CORE-008最小修正](../specs/native-reader-empty-count.md)：空分支归零历史数量并说明原因；正常查询、实时混读并发和派生缓存各自资格继续分列。行为及验证见[修正证据](../evidence/2026-10-21-native-reader-empty-count.md)。
