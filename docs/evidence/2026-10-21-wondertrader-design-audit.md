# WonderTrader 原生设计与既有差异复核

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

日期：2026-10-21。性质：原样源码研究、隔离编译和合成故障实验。本记录接续并修正[既有框架差异审阅](../migration/core-change-review.md)中的宽泛判断。框架源码修改继续等待逐项批准。

## 输入与方法

- 仓库 `E:\workspace\wondertrader`，固定上游 `08b230dd05facf6d650d949bfe51054115a2ecb1`。三名 Astra 子 agent 分别研究插件/编译、存储/并发、交易/恢复；主任务核对总体架构、原样构建及汇总证据。
- 原生事实以 `git show` 和固定提交源码为准。12 个既有框架差异仅作比较，不将修改后测试通过当成上游缺陷证据。
- 编译矩阵使用 MSVC 19.51.36248、Windows SDK 10.0.26100.0、C++17、仓库锁定依赖。矩阵输入 352 个现有文件逐个匹配 HEAD blob；稀疏检出省略 7 个 VS filters 元数据文件。
- 存储参考构建独立放在 `build/native/upstream-audit/original-build`：WTSUtils、WTSTools、WtDtHelper、WtDataStorage 源码及公共头逐文件验证 HEAD blob。单独 CMake 使用 CXX `/FIobjbase.h` 与 `NOMINMAX` 控制头顺序；没有改原样快照源码。该构建只覆盖上述组件。
- 所有实验数据为隔离生成，未连接交易账户、未启动生产策略、未下单撤单。完整命令、源码清单与日志保留在本地 `build/native/upstream-audit`；下述结果注明静态分析与实际运行的区别。

原样参考 DLL：

| 文件 | SHA-256 |
|---|---|
| WtDtHelper.dll | `da75291338ab8f9618ee3befde4c81f98dbdb6047e11d3e2cbc94ca3119bb055` |
| WtDataStorage.dll | `359782d8ba23293995727f3baa4e74aa0c7b88a7adb9a5cf9ec3114934b7d4e5` |

## 原样 DLL 实验结果

隔离 C++ harness 只调用公开 helper/writer 接口。helper、同步 writer、异步 writer 三个独立子进程均正常结束，分别设运行超时。输入为生成的二进制测试数据，未使用真实行情。详情见实验输出（外部历史/待归仓路径：`wt-design-audit-2026-10-21/storage-results.json`）、helper 日志（外部历史/待归仓路径：`wt-design-audit-2026-10-21/helper.stdout.log`）、同步退出（外部历史/待归仓路径：`wt-design-audit-2026-10-21/writer-sync.stdout.log`）、异步退出（外部历史/待归仓路径：`wt-design-audit-2026-10-21/writer-async.stdout.log`）及测试源码（外部历史/待归仓路径：`wt-design-audit-2026-10-21/storage_probe.cpp`）。

| 场景 | 实际结果 | 证据限定 |
|---|---|---|
| 正常 512 条 Bar 写 CMP_V2，再读回 | store=true，读取/回调数量均为 512 | 验证正常格式和接口路径；不验证交易时段或实际行情质量 |
| 相同数组，目标路径为已有目录 | store=true，打印“写入文件成功”，目标仍为目录 | 已复现创建失败的假成功；未实测磁盘写满/短写 |
| 将上述 6018 字节 DSB 截去最后 1 字节 | 返回并回调 68 条，原文件实际是 512 条 | 已复现忽略解码失败后将压缩缓冲按 Bar 计数；输出无效 |
| 破坏 ZSTD magic / 翻转末字节 | 分别抛 `string too long` / 解压长度不匹配异常；没有数据回调 | C++ harness 捕获；未推断所有语言宿主都能安全接住异常 |
| 使用 RAW_V2 正常布局 | 读回 512 条 | 原接口兼容范围包含未压缩布局 |
| 同步 writer init→release，宿主继续存活 | 线程数 4→5；release 0ms 返回仍为 5，11 秒后为 4 | 证明 release 返回时 checker 尚未结束；对象保留，没有制造悬空指针 |
| 异步 writer 的任务进入受控阻塞 sink 回调时 release | release 0ms 返回，回调 entered=1/exited=0，线程数 6；放行后 11 秒为 4，exited=1 | 证明 release 未等待在途 task 回调。该调度由 harness 控制，不等于生产已出现崩溃 |

writer 测试有意保留 writer/sink/DLL 至子进程退出，避免将非虚析构与停止屏障混在一起；没有运行删除后访问实验。未缩短原 checker 时间、未修改原锁或队列。此次未复现 600 秒过期竞态和队列丢唤醒，也未运行 ThreadSanitizer。运行证据支持精确的返回语义结论，不能概括为 WT 正常交易无法工作。

## 六项重新判定

### CORE-001：Windows 编译

确切冲突是 Windows RPC 的全局 `byte` 与 C++17 的 `std::byte`。原 `WTSDataDef.hpp` 在全局引入 `std` 名称；先包含该头、再包含 `objbase.h` 的最小程序在 `rpcndr.h` 产生 C2872。对调包含顺序通过。单独定义 `NOMINMAX` 仍失败；它只控制 min/max 宏。

原样 `WtDataWriter.cpp`、`WtVWapExeUnit.cpp`、`WtStockVWapExeUnit.cpp` 在相同工具链下均直接编译通过；带预包含选项也通过。原样 helper/storage 参考 DLL 整体构建通过。C++17 原已存在于上游 CMake 和 VS 工程，不能归因为自有工程首次升级标准。

补充直接编译 `WtDataReader.cpp`、`WtDtHelper.cpp`、`ParserAdapter.cpp` 均通过，未使用强制预包含。这里证明这些翻译单元在该环境的编译结果；没有声称上游全部券商 SDK 和发行目标都已构建。

结论：头顺序兼容问题已复现；“当前必须修改这五个框架文件才能编译”缺少依据。优先沿构建侧验证接入所需组件，公共头命名空间清理作为独立维护议题，不与适配必需性混同。

### CORE-002：历史文件写入结果

原 `store_bars` 在合法输入下调用 `BoostFile::create_new_file`，条件块外返回 true，并忽略 `write_file` 返回值。这是具体错误传播路径；空指针、负数量等防御要求另行评估。目标为目录的创建失败已实测；磁盘满和短写仍待验证。

作者为何保留该实现：此次未找到说明该选择的官方设计记录。可确认调用逻辑，无法替作者将其解释为有意的性能取舍。适配层已有受控临时文件及完整回读，可独立判断产物是否合格。

### CORE-003：压缩大小限制

限制目的为约束解压后内存。它属于外来文件输入与资源预算要求，当前未取得真实国信数据触发此故障的证据。中断写入/复制、磁盘损坏、格式不匹配、超大输入可能产生不完整或异常内容；这些是测试场景，不是声称用户磁盘已损坏。

原生 reader 支持 raw/compressed、旧/新布局。新增限定入口缩窄到特定格式和预算，修改公共 ABI 并非唯一位置。原 reader 忽略 `proc_block_data` 的 false 与调用者希望加解压预算是两个问题，应分别验证。预算可以在受控适配边界设计，且必须绑定检查与实际读取的同一份内容。

### CORE-004：行情时间检查默认值

差异位于通用 `WtCore::ParserAdapter`，并非 QMT 插件独有。普通 `init` 在注册插件前读取配置；缺字段为 false，true/false 均覆盖构造值。原 `initExt` 与构造函数均没有给 `_check_time` 赋值，实际 handleQuote 会读该成员；上游外部 Parser 和 HFT 延迟工具也使用该入口。

显式 false 让 `initExt` 的行为确定为关闭额外时间检查；普通配置初始化保持配置语义。原检查只过滤比本机超前一小时以上的 tick。此为源码和 C++ 初始化规则确认的问题，仍须按最小一行范围单独批准，不能声称完全不涉及原有行为。

补充隔离观测：编译原样 `ParserAdapter.cpp` 对象，配合最小测试插件实际走普通 DLL 工厂路径。缺省和 false 均接受测试未来/过去 tick；true 过滤未来 tick、保留过去 tick。修改配置对象后 adapter 缓存值保持原初始化值。MSVC 类布局报告给出 `_check_time` 的字节位置；harness 通过 unsigned-char 对象表示观察预填 0/1/90 的存储，原构造及 `initExt` 后相应字节保持原值。该阶段不读取未初始化 bool，也不推送 tick。对现有修改版编译对照后，这三个字节均为 0，普通配置三组结果一致。

此辅助实验只保证所测 ParserAdapter 翻译单元和头为原样；链接辅助符号来自现有构建的 WtCore/WTSTools/WTSUtils/Boost，不能称为全库原样构建。最终 harness 没有 private/public 宏替换，也未改框架文件。见原样日志（外部历史/待归仓路径：`wt-design-audit-2026-10-21/parser_probe_run.log`）、对照日志（外部历史/待归仓路径：`wt-design-audit-2026-10-21/parser_probe_modified_run.log`）、观测源码（外部历史/待归仓路径：`wt-design-audit-2026-10-21/parser_probe.cpp`）。

### CORE-005：实时存储并发与退出

原有保护包括：异步输入队列、cache 锁、块级锁、StateMonitor 会话准入、归档队列，以及 checker 在检测到归档线程后退出。普通 `async=false` 与官方股票示例 `async=true` 必须分别说明；同步输入也仍有 checker。

因此，“写入、清理、归档会毫无约束地同时操作内存”的旧表述需要更正。正常会话关闭后才请求归档，块锁覆盖写入/扩容/释放；这些都是实际设计。

剩余静态风险包括：队列 empty 在锁外观察后无谓词等待、映射 getter/map/访问时间与 checker 的交错、分钟块锁前检查和锁内使用之间可能失效。它们必须按具体条件复现；普通高频输入通过也不能覆盖原固定 600 秒闲置阈值。

原 `release` 设置普通 bool，唤醒/join 归档线程，再删块；task/checker 的停止等待不在该函数中。对象销毁、进程退出、同进程继续运行和重复初始化须分别验证。此前新增缩短过期时间配置、有界取消、重复 stop 和大范围互斥改动应拆成独立需求，不能作为整体“修复”直接纳入。

### CORE-006：交易断线恢复与事务

原有机制包括 CTP 断线重登后的四查询、SDK 流恢复、XTP 保留连续回报、委托标签缓存、订单首次识别、Local/Diff 执行器失联门禁、计算及订单监控锁，以及策略/执行器状态保存。应撤回“原框架没有恢复保护”的概括。

CTP 正式重登会再次进入四查询；XTP `_inited` 分支采用保留投影的另一条路径。因此原生已经存在保留恢复设计，接入须匹配具体插件契约。

按源码条件推演：同 Adapter 已有统计且重新收到重叠全量列表时会重复累加统计；券商实际持仓归零、本地仍非零、新查询省略对应方向且缺失成交回报时可能保留旧字段。这些是带前提的源码结论，本次未连接真实 SDK 复现。成交查询累计统计，不直接再增加账户持仓。

原子编号、局部锁、持久缓存和柜台订单处理分别保护不同范围；公共接口未承诺横跨四查询、实时回报、策略文件与远端委托的一项 ACID 事务。原框架通过异步状态机工作，新接入需验证来源的快照/事件边界。现有下游新增 bool/pending 状态也不能自动提供任意跨线程保证。

上游 [Issue #259](https://github.com/wondertrader/wondertrader/issues/259) 直接讨论 `_stat_map`，collaborator 于 2025-09-30 建议对高并发场景测试共享状态并增加适用锁。该反馈支持按实际线程拓扑核验，不能替代本项目的竞态复现。

## 文档与继续条件

已形成[框架与并发模型](../architecture/wondertrader-framework.md)、[插件](../modules/wondertrader-plugins.md)、[存储](../modules/wondertrader-storage.md)、[交易](../modules/wondertrader-execution.md)四份长期文档。框架总览由三名研究者按各自源码范围交叉核查。

当前不批准任何框架源码修改。后续如确需变动，应分别提交原样复现、正常路径影响、原有插件/构建侧替代、最小范围、性能与死锁风险和回归结果；已有 12 文件保持冻结。并发方案继续检查行情、交易回报、执行池、查询和关闭的完整线程拓扑。

收尾核对：12 个框架差异文件 SHA-256 全部匹配原冻结登记；文档导航与技能清单检查通过。原 QMT 工作区本轮仅读取，结束时观察到另有任务登记及事实附件变化，保留其他会话工作，不将其报告为干净工作区。未执行源码集成或发布。实验附件说明见附件索引（外部历史/待归仓路径：`wt-design-audit-2026-10-21/README.md`）。
