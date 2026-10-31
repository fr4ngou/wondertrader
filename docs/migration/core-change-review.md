# WT 既有框架差异必要性审阅草案

日期：2026-10-21。状态：只读技术调查；建议均待用户批准，未授予实施许可。

**后继复核：**下文为首轮审阅记录。当前判断以[原样源码设计与实验复核](../evidence/2026-10-21-wondertrader-design-audit.md)为准：原样主要存储组件可用构建侧头顺序方案编译；writer 已有队列、块锁与时段归档约束；CTP/XTP 原有不同的恢复与门禁机制。下文宽泛并发/恢复表述不作为批准或实施依据。框架源码保持冻结。

## 大白话说明

这 12 个文件合起来是六类改动，文件数不等于十二个功能。这里列的是开发工作区已有差异，当前保持冻结。

| 类别 | 解决什么问题 | 当前建议 |
|---|---|---|
| Windows 编译，5个文件 | 标准库名字与 Windows 头文件名字撞车，导致编译失败；改名字写法，不改交易算法 | 先验证编译侧隔离；若确需保留，再提交最小范围批准 |
| 历史写文件，和下一项共2个文件 | 文件写失败时，原接口有机会仍报告成功 | 适配层写完再完整读回核对，评估从核心退出该改动 |
| 历史读文件，和上一项共2个文件 | 损坏或异常大的压缩文件可能解压撑爆内存 | 评估在我们自己的读取边界限制大小，避免长期依赖新增 WT 接口 |
| 行情插件默认值，1个文件 | 一条特殊加载路径没给时间检查开关赋初值，行为可能不确定 | 优先走原来的正常插件加载路径；确需修复时单独申请 |
| 实时数据写入与关闭，2个文件 | 写行情、清理旧数据、退出几个线程会同时碰相同内存，可能出现竞态或停不下来 | 涉及底座通用存储，范围大；先复现原问题、拆最小修复，不把整组当必需接入改动 |
| 交易断线恢复，2个文件 | 在原对象保留状态的情况下恢复连接，要防旧就绪状态和订单/成交重复计算 | 先验证原有完整重建与现有观衡幂等恢复；确需同对象恢复时再申请最小接口 |

当前分钟历史导入可以使用原有公开接口继续开发。最后两组影响更广，需要单独评估，不应让用户一次性批准整组 12 文件。批准前继续只读；替代方案先在自有适配层或隔离参考构建验证。

## 范围与证据资格

- 对照 Git 基线 `08b230dd05facf6d650d949bfe51054115a2ecb1` 的实际工作区差异，审查 CORE-001–006 涉及的 12 个上游源码文件。
- 核查来源：`build/native/adapter-only-core-observation.json`、`docs/maintenance/upstream-overrides.md`、当前代码及现有测试源码。此次未构建、未运行测试、未连接 QMT、未读取账户或凭证、未修改 Git 状态或上述源码。
- 现有测试源码说明哪些行为依赖差异；旧运行结果只证明当时行为，不证明架构方案已获批准。隔离 fixture 不能证明实际部署或真实交易资格。
- 本记录保留逐项必要性、替代方案与证据缺口，实施边界见[当前目标](../roadmap/TARGET.md)和[差异登记](../maintenance/upstream-overrides.md)。当前没有取得保留、扩大或退出这些框架差异的批准。

## 审阅结论

当前“已下载分钟历史导出 → 外部转换 → WT 原生 DSB → 原策略读取”可以调用原有 `store_bars` / `read_dsb_bars`、原策略和回测接口，避开实时 writer 和保留交易通道恢复。因此 CORE-005、CORE-006 不能被列为当前离线导入的先决条件。

完整实时行情、受管停止、交易断线恢复的目标仍然保留。CORE-005 和 CORE-006 解决的是底座内部问题及额外恢复语义，需要单独说明必要性和替代路径。外部串行调用或重新登录不能直接证明与现有行为等价。

| 项目 | 当前差异实质 | 建议方向 | 当前不能据此声称的结论 |
|---|---|---|---|
| CORE-001 | 头文件命名空间与连带显式 std 限定 | 保持冻结；可作为单独小范围构建兼容申请。先隔离验证编译侧替代 | 尚未证明只能改上游头文件才能编译 |
| CORE-002 | store_bars 参数检查和写失败传播 | 新离线适配以受控输入、临时文件及完整原生回读判定成功，评估退出核心差异 | 返回 bool 的修复仍影响旧测试与调用者，不能直接撤回 |
| CORE-003 | 新增有界 DSB 读取 ABI | 评估外置独立边界 shim；新离线导入使用原 ABI 读自己刚生成的受控输出 | 普通 read_dsb_bars 可以安全解析任意不可信 DSB |
| CORE-004 | ParserAdapter::_check_time 确定初始化 | 优先正常配置 init + Parser 插件；若确需 initExt，再申请这个单行初始化 | 正常 init 的替代宿主已经接通 |
| CORE-005 | 通用存储 writer 的映射、线程、停止、清理生命周期 | 从离线历史主线解耦；实时场景单独审议最小上游缺陷修复或独立 IDataWriter 插件 | 外部互斥、sync 模式、独立进程已解决内部 checker 竞态 |
| CORE-006 | 同一个 WT 投影保留式恢复、在线资格、通知重入/重试 | 保持冻结；先比较新实例完整重建与外部通知代理，确需保留式恢复才申请最小接缝 | 原生重登查询与连续补发恢复可以互换 |

## CORE-001：公共头文件命名空间

实际范围：`src/Includes/WTSDataDef.hpp` 移除全局 `using namespace std`，增加 `<algorithm>`、`wtp` 内 `using std::min/max`，将 `WTSValueArray::m_vecData` 明确为 `std::vector`；`src/WtExeFact/WtStockVWapExeUnit.{h,cpp}`、`WtVWapExeUnit.{h,cpp}` 将原隐含标准库名显式限定。5 个文件，无持仓、交易或分钟算法变更。

代码依据：`tests/native/test_header_namespace.cpp` 在 WTSDataDef 后包含 `<objbase.h>`，并静态确认 `std::byte` 存在。`cmake/native/CMakeLists.txt` 选 C++17；上游 `src/WtDataStorage/CMakeLists.txt` 自身也选 C++17，不能简单将全工程降为 C++14 即宣告等价。

必要性判断：这是 Windows 头文件声明与全局命名空间污染的构建问题，改动局部且可以解释。强制预包含 Windows 头、局部隔离 include 顺序或桥接翻译单元是候选替代，但此次未做原样上游编译对照，不能声称全部引用点都可用编译选项解决。将 `std::byte` 关闭的实现专用宏会改变编译环境，也需明确验证，不能静默作为通用解决办法。

需批准范围：若保留，仅上述 5 文件的命名空间修复；不授予改动执行算法许可。回归：原样公开头的两种 include 顺序、Windows SDK/C++17、原生实际组件编译及原 VWap 编译。回滚：以同一原生工具链重编所有相关组件，避免混用旧对象；先证明编译侧替代成功，再退出源码差异。

## CORE-002：store_bars 写入结果

实际范围：`src/WtDtHelper/WtDtHelper.cpp::store_bars` 拒绝非正数 count、空输入/路径/period；创建或写入文件失败返回 false。原有实现对创建失败仍最终返回 true，并忽略 `write_file` 结果。导出函数签名不变。

当前消费者：`src/GuanhengData/History.cpp::NativeHistoryStore::publish_impl` 在约 384 行检查返回值，随后通过 `read_native` 比对完整 WTSBar 数组，最后生成来源摘要并发布。`tests/integration/market/test_market.cpp` 173–176 行直接断言非法参数、目录/文件创建失败返回 false，因此测试本身绑定了修改后的 bool 语义。

可替代路径：外部 adapter 校验参数，使用独占临时输出，调用原 `store_bars` 后以“文件存在、原生完整回读数量与逐字段/字节一致”授予发布资格。当前 `publish_impl` 已有回读，说明成功判定可以在适配层收敛。原函数仍可能返回假成功，适配层必须不把该 bool 单独当成功证据。若外部使用者仍依赖准确 bool，应明列该核心修复申请。

建议：新离线导入不新增该依赖；旧消费者改为适配层完整成功判断后，评估退出。回归需覆盖创建失败、目录当文件、磁盘/短写失败、残留临时文件、原回读不符和无发布；不能只更改原测试预期。回滚是恢复上游 store_bars 并同时切换完成回读的消费者，不单独撤回错误检查。

## CORE-003：有界 DSB 解码

实际范围：`WtDtHelper.h/.cpp::read_dsb_bars_limited` 新导出；原 `read_dsb_bars` 抽出公共 `deliver_dsb_bars`。新入口在读入和解压前检查文件长度、块签名/类型/版本/体长度、ZSTD 声明长度、Bar 数量，预算上限 1,000,000。

当前消费者：

- `src/GuanhengData/History.cpp::read_native` 约 216–225 行调用新入口；query、publish 回读、freeze、recover 均经这个函数。
- `integrations/guanheng/native_history.py::NativeHistory.__init__` 107–108 行必须找到该符号，220 行调用，导致原样上游 DLL 不能直接满足现有 Python reader。
- `tests/integration/market/test_market.cpp` 189–205 行验证预算与大声明拒绝。

必要性判断：对外来或损坏文件，压缩文件大小预算不能代替解压预算，解压后才检查也太迟。这个安全行为应保留，但安全边界不必天然位于上游 WtDtHelper。

外置候选：独立 Guanheng native shim 使用上游块定义及现有 ZSTD 工具，严格预检后调用原 `read_dsb_bars`。必须将受检文件复制到私有受控快照后再读，或证明同一个句柄/字节源不变，防止“检查路径之后被替换”的 TOCTOU；shim 不能只先 stat 再调公开读取。ABI 和私有依赖应在自有模块登记，不能重写完整 WT 存储算法。尚未实现或证明等价。

新离线导入可仅对自己刚生成的、数量受控且受管的临时 DSB 使用原 `read_dsb_bars`，这不构成通用不可信文件读取资格。旧 `NativeHistory` 仍有 CORE-003 依赖，必须迁移后才能撤回。

需批准范围：若继续保留，新增 ABI 加原函数公共化的实际两文件差异。回归包含压缩声明超限、损坏/未知长度帧、头体不符、零预算、回调失败与文件替换；验证原 ABI 正常数据兼容。回滚先迁移 C++/Python 符号消费者，再以匹配整包替换 DLL，禁止先撤导出再让服务启动失败。

## CORE-004：ParserAdapter 外部初始化默认值

实际范围：`src/WtCore/ParserAdapter.cpp::ParserAdapter` 新增 `_check_time(false)`。`initExt` 约 46 行没有赋这个成员；`handleQuote` 约 306 行读取它。普通 `init` 约 102 行从配置读取它。

当前直接依赖是 `tests/integration/runtime/runtime_scenarios.cpp` 的 `adapter.initExt(...)` 两个场景。上游 WtRtRunner、Latency 工具也有 initExt 路径，所以该未初始化问题并非 QMT 独有。`src/ParserQMT/Factory.cpp` 已有原 `createParser/deleteParser` 插件工厂接缝，正常配置 init 具有明确赋值路径；但当前工厂实际端点注入仍需接通，现有 initExt 隔离验证不能证明普通插件链已工作。

建议：生产适配优先正常 `init` 加配置插件；保持 initExt 的需求需提交这项确定初始化修复。单纯在 MarketParser 校验时间无法改变 WT adapter 内部读取未初始化 bool 的事实；用覆盖内存或预置对象存储绕过属于不合格替代。

回归：普通 init 的 check_time 两值、真实 Parser 工厂加载与连接、initExt 最小缺省时间路径。回滚以正常 init 接通为前提，不直接退回使用未初始化值的宿主。

## CORE-005：通用 writer 生命周期（重点）

实际差异约 238 增/162 删（cpp）加 7 增/1 删（h），影响整套 `WtDataStorage`，范围显著超过 QMT 插件：

1. 六类 tick/min1/min5/trans/orderdetail/orderqueue 映射的取得、扩容、写入、过期释放、归档，共用 `_mapping_mtx` 递归生命周期门；块指针在保护内检查。
2. `_terminated` 改原子；`release` 关闭准入、唤醒、在门外 join task/proc/check 三线程，再清理映射、队列和 cache。用 `_release_mtx` 协调重复停止。
3. 两个队列改谓词等待，避免 empty 检查/入队/唤醒错位；清理缓存的 retry 在门外可停止等待，每轮重关映射。
4. 新增并严格解析 `mapping_expiry_secs` / `mapping_check_interval_ms`，改变可配置面。
5. 工厂 `deleteWriter(IDataWriter*&)` 改为删除具体 `WtDataWriter*`；当前 `IDataWriter` 无虚析构，原 `delete writer` 无法保证派生成员析构。

当前消费者：`src/GuanhengData/MinutePipeline` 只通过原 `IDataWriter/IDataReader`，要求创建线程独占、同步 writer。`tests/integration/minute/minute_scenarios.cpp::native_chain` 经 DLL 工厂使用实际 writer/readers；另有 `writer_expiry_and_shutdown`、`async_and_archive_stop`、`clear_cache_and_stop`、`mapping_budget_validation` 直接覆盖通用 writer 行为。新预算还被这些测试用于缩短实际 checker 周期。

外部包装为什么不充分：

- `WtDataWriter::init` 总是启动私有 `check_loop`，`async=false` 只关闭输入 task 异步，不会关闭 checker。创建线程独占不能约束 checker 的 map 遍历/释放。
- `check_loop`、`releaseBlock`、映射集合和内部 proc 线程都是 `private`；公开 `IDataWriter` 没有外部取得其生命周期锁或停 checker 的接缝。给 writeTick/release 套外部锁，checker 仍并发运行。
- 独立 writer 进程可以隔离崩溃影响和地址空间，不能修复进程内部写入/过期竞态。强杀退出会带来未完成归档/缓存持久性问题，不能当优雅退出的等价证明。
- 使用 `IHisDataDumper` 只替换历史输出接收方，无法替换实时映射/检查器内部生命周期。
- `WtDataStorageAD` 是另一个原 `IDataWriter` 实现，但采用 LMDB 与不同 cache 路径，不能仅凭它存在就声称原 DMB/minute reader 可无缝替换；需独立语义与存储验真。

可以隔离的位置：**完全离线历史导入用 WtDtHelper，无需实例化 writer**。实时管线也可在原 `IDataWriter` 插件边界选择自有实现，但这会承担 OHLCV、累计差分、映射、归档的维护成本；复制整套 WT writer 并非自动更优。当前源码大量已有算法被复用，尚未证明可将内部 bug 完整收敛为一个薄 wrapper。

建议将审批拆成可复核项：映射生命周期互斥、线程停止/等待、工厂析构、可配置过期预算四组；先在原样上游隔离参考构建复现各根因，再提出最小修复。可配置过期预算大部分用于测试提速，不能与生产安全根因捆绑成为“全部必须保留”。当前 `_mapping_check_interval_ms` 默认 10 秒且 check_loop 使用 sleep，停止耗时仍可能受 sleep 支配；测试用 1/5ms 不能证明默认配置的停止时延。

风险：递归总门覆盖日志/广播/归档和文件操作，可能扩大阻塞、重入及吞吐影响；类布局改变，必须整包一致；所有 writer 用户受影响。需核查 sink 回调重入、默认预算停止、归档长 I/O、线程异常、锁顺序及市场全量吞吐，不能只以小合成数据通过代替。

需批准范围：上述 2 个上游文件及明确四组行为；如选择自有 IDataWriter 则另给维护成本与格式兼容方案。回归至少保留六类映射过期/重映射、同步和异步写、归档与停止、文件外部占用、清理后重开、默认周期停止上界、并发负载。回滚先停止接入、保留可恢复缓存/DSB，切换匹配的 writer/reader/native 全包；恢复未修复 writer 时须撤去对应并发资格，不能保留相同安全承诺。

## CORE-006：保留投影恢复与通知资格（重点）

实际范围：`TraderAdapter.h/.cpp` 新增 `_channel_online`、`_invalidating_channel`、`_lost_pending`；`isReady` 从 `_state==AS_ALLREADY` 扩展为同时在线；Close 改统一撤销及 lost 确认；初始 ready 用快照列表分发；新增 `restoreRetainedChannel` / `invalidateRetainedChannel`。

当前直接消费者：`src/GuanhengRuntime/ManagedTraderAdapter` 继承原 TraderAdapter，通过这两个新增非虚入口实现自有 `RetainedConsumerRecovery`。`src/GuanhengExecution/ManagedTrader.cpp::begin_resume/finish_resume` 约 456–499 行要求 Host 原边界、同交易日、账户/流一致、连续回报推进到冻结前沿后，恢复同一个 WT 消费者；没有重放初始持仓/订单/成交快照。Host 证明仍是外部真实依赖，此处 fixture 没有证明线上满足。

原公开接口为何不能直接替代同实例恢复：

- 原 `onLoginResult(true)` 置 AS_LOGINED 并发 queryPositions，再链式查询 orders/trades/account，最终 ready。
- `onRspOrders` 约 1640–1760 行对 `_stat_map` 中 `b_orders/s_orders`、数量和撤单统计执行累加；`onRspTrades` 约 1772–1845 行对成交统计累加。对保留原统计的同一实例重复快照不能视为无副作用重建。
- `onRspPosition` 用返回记录更新 `_positions`，没有先清空整个集合；缺失记录归零需要完整重建契约，不能假设普通查询自然清掉旧投影。
- 原 `onRspAccount` 仅 AS_TRADES_QRYED 时发 ready；仅给 AS_ALLREADY 再调用一次账户响应不能恢复 lost 通知。
- `_state/_sinks/_positions/_stat_map` 私有，`isReady` 非虚；派生类无法通过公开方法完整撤销内部 ready。原 WtLocalExecuter/WtDiffExecuter/WtArbiExecuter 初始化会直接 `_trader->isReady()`，约各 cpp 48/54/48 行，外部状态变量无法自动替换这些读取。

外置候选和限制：

1. **新 WT channel / trader 实例完整重建**：走原登录和全快照链，不在保留实例上重复归约；由宿主停止旧投递、封闭订单门并切换消费者。可避免新增内部恢复 API，但执行器中旧指针、原未决委托、唯一订单标识、事件切换边界和策略状态都要明确。不能用“重新建实例”一句话省略迁移和防重证明。
2. **外部通知 proxy + ITraderApi 写入门**：只有代理被 addSink，代理控制真实下游 ready/lost 与重试，ManagedTrader 控制提交。能够隔离部分通知行为，但原 isReady 非虚并被执行器直接读取，原 `_state` 也不等同在线；所有入口、晚加入 sink、执行器构造与重入行为均需验真。尚不能断言无需改核心即可完全等价。
3. **仅注册普通 Parser/Trader 插件，沿用原断线重登**：可减少接入复杂度，但同实例重复查询的统计行为及丢失回报来源保证仍需核验；不能降低用户要求的对账/恢复正确性。

建议：原样接口优先，先确定需要“同一投影保留式恢复”还是“新实例完整恢复”，以实际订单/执行器契约证明。若完整需求确需保留式恢复且候选均不能等价满足，再申请最小明确接缝；不以抽象层美观或 fixture 已通过作为理由。不可仅退出新增方法而保留调用者继续恢复。

风险：新增状态无自身互斥，当前安全性依赖 owner 线程/受管重入约束；其他调用方必须声明。lost 异常后会抛出 runtime_error，改变原 Close 的异常传播；成功通知不重送、未知通知重试要求真实 sink 的 lost 幂等。类布局改变，原 ITraderApi/Spi ABI 不变也不能证明现成 WtCore 二进制可混用。

需批准范围：2 个上游文件的在线资格、初始 ready 分发、lost 重试、受约束恢复四组语义；真实来源连续性仍归接入层，不授予实际账户/下单权限。回归覆盖 initial ready、lost/ready 重入、两 sink 部分成功/异常、连续补发、同日和跨日、新/旧 Host 流、未决委托、防重及并发调用拒绝。回滚先关闭写入与恢复、冻结旧投影证据，再切换匹配全包及选定重建流程；禁止把 stale AS_ALLREADY 作为恢复完成。

## 需提交用户的审批包

每项批准应绑定：精确基线/源码摘要、范围、根因复现、原公开接口替代验证、行为回归、架构影响、回滚。批准“某项必要行为”不自动批准当前整组实现或未来扩大范围。

当前可继续实施的确定工作：外部分钟导入、明确格式/时间/单位契约、使用原公开 ABI 的真实分钟策略回放、独立服务接口。现有 12 文件保持冻结；重构、退出或保留改动也应由主任务先告知用户，再依批准执行。

## 冻结源码身份

以下为本次只读审阅绑定的现有文件 SHA-256；任何拟实施变更须重新绑定范围和批准记录。

| 文件 | SHA-256 |
|---|---|
| src/Includes/WTSDataDef.hpp | 96b5ea63beddb3eee3bae4f86107bdb7c4cf1192d1cb5a18ce751b4e79180d3f |
| src/WtCore/ParserAdapter.cpp | 66fd3f5d23347f5d45c67699d284f4cd90b0b6fa9ed206a5b1fb47906c597631 |
| src/WtCore/TraderAdapter.cpp | 5eccc0629741977056296df6990fd75365f6e125f1ddd448645d0e26a5fe9cbb |
| src/WtCore/TraderAdapter.h | f5c07051f528bea3e59ebee07a14f66482f39d3f94d35b611421fe056de21c6e |
| src/WtDataStorage/WtDataWriter.cpp | 2c6ffeaac444299da5f0b1986e8e8203b9e13435af882ad06183e848eb30cca2 |
| src/WtDataStorage/WtDataWriter.h | 1d28b15c234a08c1bc8dab4a748df83ed0ec3f4e85511d0b02a8cf1bcd51cddb |
| src/WtDtHelper/WtDtHelper.cpp | ba840920289323cea93deecd4375798e9196c5a39c1032389a2893ddf7cc8ab2 |
| src/WtDtHelper/WtDtHelper.h | 2ee62235448087426ac1c478a3e0ca0e80e4fa8b4e2721fb412d4a7c6cb2830a |
| src/WtExeFact/WtStockVWapExeUnit.cpp | 25a059d6c29c2bc83892b800cfe730b7ed5ddab126194d654276b3d6d5d80ad6 |
| src/WtExeFact/WtStockVWapExeUnit.h | e9a1093f71d5cb4850a1c168a7ad1d683959d612d25d978fef6878cf31a428aa |
| src/WtExeFact/WtVWapExeUnit.cpp | 6da1023afa0052f8632abdb5cc30fe697e3959af2da1fb6aa741154ab89116dc |
| src/WtExeFact/WtVWapExeUnit.h | b59f36a75b522a5fc67e49c7fe0fa3dce6d7ae6e8b45d08d5f9a10206a74554e |
