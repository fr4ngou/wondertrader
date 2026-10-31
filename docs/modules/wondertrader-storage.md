# WonderTrader 原生存储设计

类型：长期模块说明。范围：原生 `WtDataStorage::WtDataWriter`、`WtDtHelper`、官方数据宿主及其存储扩展边界。状态：源码设计已核实；并发故障是否实际触发，须由对应版本的运行证据单独证明。

本文以官方源码提交 `08b230dd05facf6d650d949bfe51054115a2ecb1` 为基准。源码链接固定提交和行号；本地同名文件可能包含下游差异。这里描述该版本可观察的执行逻辑，不推测作者动机，也不将新增宿主要求自动归类为上游缺陷。

## 职责和正常调用链

官方数据组件接收行情、保存实时数据并形成基础分钟线；策略的数据读取模块读取落地数据。官方 [WtDtServo 文档](https://github.com/wondertrader/docs/blob/main/source/docs/tools/wtdtservo.md)说明随机读取接口服务于研究以及相关组件；该说明为滚动文档，具体实现以下述固定源码为准。

`QuoteFactory` / `WtDtPorter::WtDtRunner` 装载基础资料、状态监控器和 Parser，`WtDtCore::ParserAdapter::handleQuote` 补齐合约资料并调用 `DataManager::writeTick`。`DataManager` 加载配置指定的 writer DLL，取得 `createWriter/deleteWriter`，把自身作为 `IDataWriterSink` 传给 writer。输入先经过交易时段准入，然后更新最新 tick 缓存、写 tick、合成分钟线，最后广播。

源码依据：[ParserAdapter](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtCore/ParserAdapter.cpp#L337-L367)、[DataManager 工厂和转发](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtCore/DataManager.cpp#L43-L145)、[procTick](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataWriter.cpp#L362-L409)。

实时 `.dmb` 使用内存映射，包含容量、有效条数和数据；历史 `.dsb` 使用块头及压缩数据。块版本区分旧/新结构与原始/压缩数据，具体布局由 [DataDefine.h](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/DataDefine.h#L10-L184) 定义。`WtDtHelper::store_bars` 是直接历史转换入口，使用这一入口不需要启动实时 writer 或行情线程。

## 接口和配置

| 接缝 | 原有行为与调用要求 |
|---|---|
| `IDataWriter::init(params, sink)` | sink 提供基础资料、时段准入、交易日和广播；writer 初始化缓存与后台 checker。调用方先完成基础资料和配置初始化 |
| `writeTick/OrderQueue/OrderDetail/Transaction` | 同步模式在调用线程执行；异步模式将对象 retain 后放入任务队列。返回受理结果不等于已持久化，tick 的 true 也可能对应时段准入后跳过 |
| `getCurTick` | 在 tick-cache 锁内查缓存并创建新的 tick 对象；返回对象由调用方按引用计数约定释放 |
| `transHisData(session)` | 将 session 的合约及 `MARK.session` 排入归档队列；专用归档线程消费 |
| `add_ext_dumper` | 登记 `IHisDataDumper`，由归档阶段调用其历史输出回调；它不接管实时映射和输入队列 |
| `release`、工厂 `deleteWriter` | 官方 `DataManager::release` 依次调用二者；writer 的具体停止范围见生命周期章节 |
| `WtDtHelper::store_bars` | 同步读取调用方的连续 `WTSBarStruct` 数组；周期为 `m1/m5/d`；输出 CMP_V2 历史文件 |
| `WtDtHelper::read_dsb_bars` | 同步读取整个文件并解码，先 count 回调，再数据回调；数据指针指向局部缓冲，调用者须在回调内消费或复制 |

接口依据：[IDataWriter](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/IDataWriter.h#L27-L116)、[读写 C 接口](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtHelper/WtDtHelper.h#L27-L64)、[getCurTick](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataWriter.cpp#L1414-L1431)。

`async` 缺省经 `WTSVariant::getBoolean` 得到 false；官方 QuoteFactory 示例显式配置 true，并注明期货推荐同步、股票推荐异步。两者分别是代码缺省和示例值。`WtDtRunner::start(bAsync)` 控制宿主是否阻塞，是另一项开关。源码依据：[writer 初始化](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataWriter.cpp#L113-L170)、[布尔缺省](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/WTSVariant.hpp#L363-L370)、[官方配置](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/dist/QuoteFactory/dtcfg.yaml#L15-L24)、[宿主 start](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtPorter/WtDtRunner.cpp#L42-L84)。

writer 还读取 `path/cache/savelog/groupsize/skip_notrade_tick/skip_notrade_bar/disablehis` 和各数据类型禁用项、`minbar_price_mode`。`cache` 为空时使用 `cache.dmb`。配置应提供正数 `groupsize`：init 无条件覆盖构造值，缺省 UInt32 为零，而 tick 日志分组会取模。原版映射过期阈值固定 600 秒、检查间隔固定 10 秒；不存在 `mapping_expiry_secs`、`mapping_check_interval_ms` 配置接口。

## 线程、状态与同步边界

| 执行方 | 工作与共享状态 | 已有同步或时序约束 | 证据及边界 |
|---|---|---|---|
| Parser 回调线程，`async=false` | 直接更新 cache、tick/minute/L2 映射与广播 | cache 使用 `_lck_tick_cache`；块内容写入、扩容使用各块 `_mutex` | 同步开关决定执行线程，接口未声明任意多线程调用的整体安全保证 |
| Parser 生产者，`async=true` | `_tasks` 入队，懒创建唯一 `_task_thrd` | `_task_mtx` 包住入队和线程创建；对象 retain 保持任务内生命期 | 输入队列将处理串到一个 task 消费线程 |
| task 消费线程 | 换出任务批次，按顺序执行四类 `proc*` | swap 在 `_task_mtx` 内，业务执行在队列锁外；块/cache 锁继续适用 | `empty()` 在锁外，随后锁内无谓词 wait；有待队列实际调度验证的丢唤醒窗口 |
| checker `_proc_chk` | 遍历六类映射，超过 600 秒未访问则释放映射 | `releaseBlock` 用块锁清空指针和映射；getter 刷新 `_lasttime` | 每 10 秒检查；首次发现 `_proc_thrd` 非空便退出。map 查找/插入及 `_lasttime` 的同步须独立核查 |
| StateMonitor 线程 | 按 session 收盘时刻改变接收状态，并请求归档/清缓存 | `canSessionReceive` 仅允许 `SS_RECEIVING`；归档请求发生在 `SS_CLOSED→SS_PROCING` 后 | `allday` 不安装状态机，接收恒允许；自行在收行情时调用归档扩展了正常时序 |
| 归档 `_proc_thrd` | 消费合约/marker/清理任务，转存 DSB、调用 dumper、关闭映射 | `_proc_mtx` 保护入队/出队；读取块与归档输出使用块锁；清 cache 使用 cache 锁 | `empty→wait` 同样存在锁外观察窗口；checker 退出条件缩小归档重叠，但未构成两个线程的 join 屏障 |
| 查询线程 | `getCurTick` 读最新快照 | 与更新共用 `_lck_tick_cache` | 不应因存在全局 cache 锁就推断所有 map/生命周期都已串行 |
| 宿主退出线程 | `release` 写 `_terminated`、join 归档、删除六类块 | 原版仅 join `_proc_thrd` | 原接口没有公开 drain、重复 init、停止期限或线程亲和性契约 |

关键源码：[异步队列及 tick 块锁](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataWriter.cpp#L574-L645)、[映射 getter](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataWriter.cpp#L948-L1049)、[块释放](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataWriter.cpp#L1295-L1305)、[归档准入与 checker](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataWriter.cpp#L1541-L1667)、[时段准入](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtCore/DataManager.cpp#L155-L162)、[收盘状态机](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtCore/StateMonitor.cpp#L371-L449)、[归档消费](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataWriter.cpp#L2140-L2168)。

块锁确实覆盖写入和映射释放，分析并发时应从完整时序判断剩余空窗。例如分钟路径先在锁外检查 `_block`，随后取得块锁并解引用；若 checker 已判定过期、在这一空窗完成释放，块锁串行了两项操作，但锁前检查无法代表取得锁后的状态。该交错需要过期检查与行情恢复恰好相遇，静态可达性与现场发生次数应分别报告。反复输入普通活跃证券不会自然覆盖 600 秒闲置后的这一条件。源码：[分钟写入](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataWriter.cpp#L1082-L1099)。

## 宿主与生命周期

`QuoteFactory` 使用全局 DataManager 和 Parser，初始化后持续运行。Windows `CTRL_CLOSE_EVENT` 路径调用 `g_dataMgr.release()`；它未先调用 `g_parsers.release()` 或 `g_stateMon.stop()`。主循环的信号退出路径则跳出循环并返回。`WtDtPorter` 保存静态 runner，公开 initialize/start 和外部 Parser/Dumper 接缝；该版本 C API 未提供成对的 stop/release。依据：[控制台关闭](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/QuoteFactory/main.cpp#L30-L47)、[主循环](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/QuoteFactory/main.cpp#L295-L328)、[Porter API](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtPorter/WtDtPorter.cpp#L47-L143)。

原 writer `release` 设置普通 bool `_terminated`，唤醒并 join 归档线程，再删除六类块对象；它没有唤醒或 join task 线程、没有 join checker、没有清空这些 map。`deleteWriter` 通过 `IDataWriter*` 删除对象，而接口没有虚析构。这些是固定源码事实；它们使“释放后宿主继续长期运行”“并发 release”“重复 init”“等待所有输入持久化”需要额外设计与验证。尤其工厂经非虚基类析构的 C++ 未定义行为，不能从程序通常在随后退出推导为语言层面的合法行为。当前生产环境中是否触发可见损坏，则需要原样运行证据。依据：[release](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataWriter.cpp#L173-L212)、[工厂](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataWriter.cpp#L37-L53)、[IDataWriter 定义](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/IDataWriter.h#L78-L116)。

清缓存删除实时目录失败时，原归档线程最多尝试五轮，每次失败睡眠 300 秒。因 release join 该线程，不能从现有接口得到秒级停止保证。该等待体现原清理流程，调用方提出有界取消属于额外运行要求；具体修复位置需先明确该要求。依据：[清理重试](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDataStorage/WtDataWriter.cpp#L2280-L2312)。

## 历史文件的故障语义

`store_bars` 对 count=0、非法周期返回 false。对合法数组和周期，它构造完整压缩块后创建文件；创建失败后仍走到 true 与成功日志，写文件的 bool 也被忽略。因此该版本 true 不能证明目标文件已写入。这一行为可与正常输入、目标目录不存在/不可创建的 I/O 故障一起验证；空指针、负 count 等属于额外防御要求，须与正常 I/O 错误传播区分。依据：[store_bars](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtHelper/WtDtHelper.cpp#L1021-L1073)、[底层文件返回值](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Share/BoostFile.hpp#L38-L44)、[write_file](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Share/BoostFile.hpp#L141-L149)。

`read_dsb_bars` 读取整个文件，检查最小头长度，然后调用 `proc_block_data`；它忽略该函数的 false。压缩头体长度不符时，解码函数返回 false 并保留原 buffer，调用方仍可能把原文件按 Bar 大小计数并回调。长度匹配时，解码器直接按 ZSTD frame 声明大小分配解压缓冲；没有调用者指定的解压预算。ZSTD 解压长度不符抛 C++ 异常，C 导出入口没有本地捕获。依据：[读取入口](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtHelper/WtDtHelper.cpp#L730-L762)、[块处理](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtHelper/WtDtHelper.cpp#L32-L116)、[压缩辅助](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WTSUtils/WTSCmpHelper.hpp#L29-L37)。

该读取 API 兼容旧/新布局以及 raw/compressed 文件；仅允许 CMP_V2、规定最大 Bar 数的入口提供更窄的外部边界。应用需要处理外来 DSB、磁盘损坏或有内存预算时，应明确输入校验、受控文件身份、异常隔离和解压预算。仅凭需要这些边界，不能推导必须新增到 WtDtHelper 的公共 ABI，也不能宣称所有官方自生成 DSB 都会触发问题。

## 扩展接缝和设计判断

1. 离线历史转换使用原 `store_bars/read_dsb_bars`；适配层可验证输入、写受控临时文件、完整回读比对，再决定发布。它能避免仅依赖原 bool，无法改变原 API 向其他消费者的报告语义。
2. 外来文件边界可位于独立适配模块；预检与读取须绑定同一受控内容，文件长度预算、解压预算和数据语义分别校验。回调内复制是原接口已有用法。
3. 实时接入使用 `IDataWriter` 插件及正常 Parser/DataManager/StateMonitor 链，配置异步输入和时段准入。`IHisDataDumper` 适合历史输出目的地扩展。
4. 独立进程可隔离 writer 故障并沿进程生命周期运行；持久化完成、归档恢复和退出结果仍需独立验收。外部串行调用只约束宿主线程，对私有 checker 不形成共同锁。
5. 对已有同步机制的不足提出修改时，分别证明正常配置下的触发交错、实际影响和最小责任层；有界停止、在线热重建、测试缩短过期时间分别列为新增要求。宽泛互斥改造与新增配置应独立评价其吞吐、回调重入和升级代价。
