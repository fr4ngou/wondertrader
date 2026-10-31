# 原 WtRunner 的 CTA 受管退出提案

类型：早期生命周期修复提案。状态：**已由最终NCS规格取代，以下保留诊断与候选设计记录**。

2026-10-21 用户要求复查现有优雅退出方法，并明确“如果最后真的检查出来发现确实没有的话，那允许你进行修改”。固定上游与独立Astra复核确认：局部stop已存在，实时Runner缺少完整可达退出链。条件已满足，实施以[最终NCS规格](../specs/native-cta-shutdown.md)为准：复用既有stop、移除早期拟议的全局回调计数门，明确启用受管CTA配置；增加策略管理器一处release入口保持策略先于context销毁，共14文件。本文下方“待批准”均为早期提案状态，不代表当前授权。

日期：2026-10-21。目标：原 WtRunner、原 CTA engine/ticker 在空 traders/executers、QNP/NHR 配置下完成可观察的受管退出。A0 独立诊断已完成；当前批准覆盖只读分析和诊断产物，核心修改仍待批准。本轮候选资格收敛到 CTA 正常外部停止、空 traders/executers 和自有 QNP/NHR；严格截止、任意第三方插件与动态 DLL 卸载单列后续范围。

既有事实与实验见[运行边界审计](native-runner-boundary.md)；行情、历史契约分别由 [QNP](../specs/qmt-native-parser.md) 和 [NHR](../specs/native-history-reader.md) 定义。本次只改变停止生命周期的候选设计。保留既有分钟调度、Pending 时策略 calculate=0、同实例补齐后恢复的语义。

## 已确认事实及直接原因的定位边界

原 WtRunner 的 pool=0/2 隔离进程均观察到原 SIGINT hook 返回、测试策略析构 enter/exit，随后退出 `0xC0000409`；原栈含 `terminate/abort`。两次均未使用 driver kill。证据为 `build/native/runner-host-audit/pool0-02` 与 `pool2-01` 下的 observations.json、strategy-events.json、runner.log 和输入摘要，汇总为同目录 report.md。

当时 WtRunner SHA-256 为 `5c53211523f8252b9bcce420ba957ad83c1e39f5081699467a025a3f60a06316`。相关 Runner/CTA engine/ticker/base engine/context/WtDtMgr 源码在换行归一后与基线 `08b230dd05facf6d650d949bfe51054115a2ecb1` 相同；ParserAdapter、WTSDataDef 有既有差异。二进制来自当前工作区，冻结的其他 trader/executer 差异没有取得本实验的执行资格。

以下是原源码可达关系；A0 的新二进制/MAP/反汇编已把本次首个终止定位到 CTA 析构删除仍 joinable 的 ticker 线程：

| 所有者 | 已存在的行为 | 对退出的影响 |
|---|---|---|
| [WtRunner](../../src/WtRunner/WtRunner.cpp) / [main](../../src/WtRunner/main.cpp) | run 退出轮询后直接返回；析构为空；main 未检查 config 的 bool | 自动成员销毁前没有停止编排，部分初始化失败也缺少可靠收束路径 |
| [WtCtaEngine](../../src/WtCore/WtCtaEngine.cpp) / [ticker](../../src/WtCore/WtCtaTicker.cpp) | engine 析构直接 delete ticker；ticker 持有 std::thread；已有 stop 设置普通 bool 后 join，但 engine 没有公开转发入口 | 销毁仍 joinable 的线程具备触发 terminate 的条件；重复 stop、自等待、停止标志并发也缺少约束 |
| [WtEngine](../../src/WtCore/WtEngine.cpp) | push_task 懒创建线程；创建发生在队列锁外；task_loop 等待 condition variable；没有停止/join 入口 | 本实验已走到 enqueue 路径；即使 ticker 退出，任务线程仍有独立所有权问题 |
| [Runner 成员声明](../../src/WtRunner/WtRunner.h) | 逆序析构先到策略 manager、基础数据和 data manager，随后才到 engine/parser manager | 活线程可能访问已经销毁的依赖，需要显式停止先于自动析构 |

直接故障为 ticker 线程仍 joinable 时进入销毁。base task 的停止缺口由源码和已执行的 enqueue 路径确认；本次首先在 ticker 删除处终止，尚未走到 base task 成员析构。两者保持不同的证据等级。

## A0：独立诊断已完成

构建所有者复用 Release 对象文件单独 MAP-only 链接，未改 core/共享 bin。实际脚本为 `build/native/runner-host-audit/link_map.py`；诊断目录为 `build/native/runner-host-audit/map-949158fb85a94cda9b68e0e6919bf81e`。receipt.json 保存完整命令、对象/库 SHA 和新旧 PE 比较。诊断 WtRunner SHA-256 为 `8eac86ff795cd04368e8d929fbb6f3df30cbe0d70d81e5e33861029f9b0e1ed7`。

新旧 `.text` 的尺寸/RVA 相同而 SHA 不同，因此使用新 EXE 重新运行 `map-pool0-01` 和 `map-pool2-01`。两组均再次出现原信号返回、策略析构、`0xC0000409`，没有 driver kill；Pending/恢复观察保持。frames-pool0.json 与同次加载基址对应，未套用到旧 EXE。

| 新栈 RVA | 同一 MAP 的函数/偏移 | 反汇编与源码交叉验证 |
|---|---|---|
| `0x2BC79` | `std::_Ref_count<std::thread>::_Destroy + 0x19` | `0x2BC6D` 检查 thread 状态；非零时 `0x2BC73` 调用 terminate，返回地址 `0x2BC79`。MSVC thread 析构对 joinable 调用 terminate |
| `0x6B280` | `WtCtaEngine::~WtCtaEngine + 0x60` | 析构开头读取 ticker 指针；`0x6B27E` 调用其 shared thread control block 的销毁，返回到该 PC；随后才释放 ticker 内存并置空。对应原析构首段 `delete _tm_ticker` |
| `0x1DF97` | `WtRunner::~WtRunner + 0x97` | 原成员析构链进入 CTA engine |
| `0xEAF5` | `main + 0x775` | 同步 run 返回后的 Runner 自动析构 |

完整机器码片段保存于 `cta-destructor-disasm.txt`、`thread-destroy-disasm.txt`；原 `WtCtaTicker.h` 的析构为空，`StdThreadPtr` 为 `shared_ptr<std::thread>`。MAP 中 `_Destroy` 关联 `EventNotifier.cpp.obj` 是该共享模板函数的链接归属，实际 caller 与被销毁对象由 CTA 析构分支确定。此次证据不把问题归给 EventNotifier。

A0 已满足直接根因定位，当前无需追加 PDB 重编。后续任何核心修改须使用新构建及匹配 MAP 复验；原负例和诊断产物保留。

## A1：受控 CTA 正常退出链的单一批准范围

本轮请求一次完整的生命周期修复：**13 个生产源码文件，五个所有者**，具体如下表。资格限定 CTA、空交易配置、自有 QNP/NHR、callback/HTTP 能正常返回。直接终止点和已经存在的 base task 后继缺口一并修复，保留同一停止顺序和同一调用链验收。

四个 CTA/ticker 文件承载已动态确认的直接原因；Runner 三文件负责在依赖销毁前调用停止；base 两文件收束已启动的独立任务线程；parser 两文件关闭行情生产者并保留 SPI；WtDtMgr 两文件完成 reader 停止、对象和缓存释放。以上各项均有实际对象所有权，不能仅在 engine 析构增加 join 后省略其余接线。接口声明与状态归属在对应 header，行为在 implementation，main 负责传播配置/停止结果，因此当前没有可安全删去的文件。

这个范围保留原 scheduler、分钟计算、公共插件虚接口和交易实现。严格总截止、任意旧插件的停止能力准入、动态 DLL 卸载以及交易生产者排空均延后，单列 A2。测试与必要构建注册由构建所有者维护，最终停止契约先落规格再实现。

## A1 具体文件及必要性

以下按五个生产代码所有者和一个验收接缝列出 A1 的完整范围；强截止/热卸载等扩展在后节单独列出。保持原 scheduler、原分钟回调、原策略计算逻辑。

| 接缝与精确文件 | 必要职责与边界 |
|---|---|
| Runner 编排（3）：`src/WtRunner/WtRunner.h/.cpp`、`src/WtRunner/main.cpp` | 增加非虚 request_stop/stop 入口及单实例生命周期；信号只发布退出请求，控制线程执行 stop。传播 config/start 失败并初始化所有参与清理的指针/标志。成功后才允许自动成员析构；超时保留 Runner 及依赖供再次等待 |
| CTA 回调/ticker（4）：`src/WtCore/WtCtaEngine.h/.cpp`、`src/WtCore/WtCtaTicker.h/.cpp` | 关闭新 tick/timer 回调准入，计数并等待已接纳调用；请求 ticker 退出并唤醒等待；外部完成 join。保留 reader 完整 batch flush 和已接纳 callback，清理 context 在策略工厂/基础数据仍存活时完成。初始化 `_cfg` 等清理所需状态 |
| base 任务线程（2）：`src/WtCore/WtEngine.h/.cpp` | 同一队列锁保护准入/懒创建/停止状态；predicate wait；生产者收束后排空已接纳任务和已换出的本地 batch，再确认 worker 完成并 join |
| parser 持有与停止（2）：`src/WtCore/ParserAdapter.h/.cpp` | 加载时保存模块句柄和现有可选 stopParser 扩展；先通过既有 stopParser 停止并等待 QNP worker，再修改 adapter 的停用状态并 release/delete。失败保留 api、SPI、adapter 和 DLL；manager 不提前 clear |
| reader 持有与停止（2）：`src/WtCore/WtDtMgr.h/.cpp` | 保存模块句柄、stopDataReader/deleteDataReader 扩展，分开 stop、缓存释放与实例删除；在引擎生产者结束后 stop reader，完成已接纳批次；所有 slice/tick 仍依赖对应 DLL |
| 资格与验收：既有 `tests/integration/runner_host/*`，新增独立生命周期回归 | 从真实原入口验证启动失败、正常 SIGINT、并发停止、回调内请求、网络/回调阻塞、持有结果跨停止。共享 CMake/scripts 由构建所有者按最终批准范围接线 |

ParserAdapter 当前 release 先写普通 `_stopped` 再调用插件 release；有 stopParser 扩展的 QNP 路径须先确认 stop 成功，避免与正在执行的 SPI 竞争。manager 保留尚未结束的成员。本轮不改变旧插件 init/connect 的准入条件、不增加强制能力字段；缺少扩展的插件保留既有 API 行为并运行兼容回归，其完整受管停止资格留在 A2。新增停止编排位于 CTA 分支，复用可用的停止扩展并保持旧插件原 API 语义；本轮实测资格仅覆盖 QNP/NHR，不能向未验证配置自动扩大资格。

WtDtMgr 当前只保存 reader 裸指针，模块句柄局部化，析构只释放缓存。NHR 已提供 `stopDataReader` 与 `deleteDataReader`。runner 接线需要持有这些能力，并把 reader 对象删除和模块卸载分成两次所有权判断。

现有 `stopParser` 和 `stopDataReader` 返回 bool：true证明该扩展完成，false仅表示尚未证明完成，不能从false推断插件内部是Pending、Timeout或Failed。宿主保留对象并报告停止阶段及未知原因；只有自己的检查/异常提供证据时才能细分失败。工厂调用按实际ABI定义：`deleteParser`接受指针引用，`deleteDataReader`接受指针值；保持原导出签名。

### 停止顺序与同步规则

拟议状态为 Created → Configured → Running → StopRequested → Draining → Stopped；配置失败仍进入同一收束路径，部分完成由显式初始化状态判断。单实例使用一次配置/运行周期。stop 失败保留 Draining 和阶段原因，允许控制线程后续等待；不在未退出时重新 start。

1. 控制侧原子发布 StopRequested；拒绝新的外层 tick/timer 调用准入并唤醒 ticker 等待。已接纳调用持有在途计数，其派生的 reader batch、on_bar、strategy 回调继续完成；停止标志不在这些批内回调中逐条丢弃事件。信号路径和策略回调只请求停止，不执行 join。本轮管理的普通停止信号在已列Runner文件内接入仅发布请求的处理路径，绕开原SignalHook先调用日志再通知退出的顺序；共享SignalHook和故障信号行为保持原范围。信号处理只操作经平台验证可安全使用的停止标志，日志、唤醒和等待由控制线程完成。仅将旧_to_exit改原子不足以满足此项。
2. 请求所有 parser 停止，等待 QNP worker、WinHTTP 完成和最后 SPI 返回。等待不持有 adapter、engine 或策略 callback 所需锁。parser callback 内提出的请求由控制线程完成。所有 parser 成功前保留 adapter/SPI/plugin。
3. 等待 ticker 和已接纳 engine 回调结束。进入 reader 的 onMinuteEnd 必须完成整批 on_bar/on_all_bar_updated；NHR stop 不截断已接纳 batch。pool=2 已接纳策略任务同样完成，禁止 pool callback 等待自己的外部调用链。所有策略、reader 和基础数据此时继续存活。
4. 关闭 base task 队列准入并排空。懒启动与关闭由同一锁线性化；worker predicate 为“有任务或关闭”。任务体在锁外执行；关闭后执行完已接受队列及已交换出的本地 batch。正常路径不丢弃资金/状态任务。异常保留未知效果，记录失败任务和未执行数量，隔离剩余任务，进入失败停止结果；不重放可能已生效任务，也不报告正常排空。
5. 调用既有 stop reader 扩展，等待其在途调用/HTTP drain。回调入口、timer、task 全部结束后，释放 CTA contexts 与 data manager 缓存；策略工厂、基础数据、reader/parser 模块此时仍保持存活。
6. 删除已停止的 parser/reader 实例，随后销毁其余拥有者。只有所有保留输出的最后 release 已完成，才具备卸载相关 DLL 的条件；进程结束不构成独立热卸载证明。

停止结果至少区分阶段与 Stopped/Pending/Failed。QNP/NHR 的有界 stop 使用剩余预算，未完成时保留对象供控制线程继续等待。A1 的全链资格是正常完成；整体严格 deadline 属于后续范围。控制锁只保护状态/计数/快照，所有 HTTP、SPI、reader、策略调用和 join 在锁外。完成通知先于外部 join；并发 stop 由单一完成者序列化，已完成可重复返回。计数准入必须与 StopRequested 在同一同步协议下判定，避免检查后新增调用。

超时意味着对象仍在使用。控制线程可继续有界等待并报告阶段；main 不能因一次超时离开作用域，让 stack Runner 自动销毁活动依赖。用户决定隔离进程的强制结束时，证据记录为强制终止；detach、永久泄漏、跳过析构不能作为受管停止实现。

### 发布级剩余边界

- **线程池最终析构**：现有 pool 有 timed wait，但默认 shutdown 随后 `terminate_all_workers(true)` 仍做无期限等待/join。首阶段可以证明受控回调已排空后的正常结束；严格的整体 deadline 还需要池的最终退出确认契约。若它阻断验收，再单列该依赖的具体受批改动，避免把 task wait 的超时包装成整个析构有界。
- **外部保留 slice/tick**：NHR slice 可跨 reader 对象销毁，自有 QNP tick 可跨 worker/parser 销毁；最后 release 需要对应模块代码。当前工厂 ABI 没有统一的跨模块外部引用计数/lease。受管退出需明确宿主所有已知持有者释放顺序；任意外部插件热卸载资格需要单独的模块 lease/关闭确认契约。保持模块到进程生命周期末端可以保留执行安全边界，不能代替热卸载验收。
- **任意策略线程/交易路径**：测试策略的异步信号线程已自行 join。通用策略工厂接口没有外部线程的有界停止承诺。真实 trader/executer、订单在途和账户回调没有本轮授权或资格；本提案的空交易配置通过后仍须单列这些生产者的关闭协议与验收。
- **ABI 与非 CTA**：优先新增 C++ 非虚入口和已有工厂扩展，保持 IParserApi/IDataReader 虚表及导出签名。增加类成员仍改变 C++ 布局，所有直接链接这些类的 runner/core 消费者要一致重编。base task 与两个 manager 被 HFT/SEL 共享，应运行其配置/退出回归；HFT/SEL ticker 的完整受管资格另列，不从 CTA 推广。
- **原并发问题**：ticker 日期/分钟字段、双关闭竞争及函数静态状态的更广泛一致性仍按原审计登记。本次准入/停止同步只覆盖对象销毁所需边界，涉及正常分钟语义的重构另行立项。

## 替代方案与实际能力

自有宿主能直接持有 base data、contexts、公开 parser/reader 扩展，并控制这些自有对象的停止顺序。调用原 engine.run 后仍由 engine 私有 ticker 和 base task 持有线程，现有公开接口不足以完整收束它们。该宿主可继续提供插件/历史组合证据；实现原 WtRunner 受管退出仍需原所有者可达的停止契约。

隔离子进程提供真实崩溃证据和有界试验清理。OS 进程终止会回收进程资源，留下的结果只能证明隔离边界；其本身没有确认 callback、队列、reader batch 或业务状态完成。自建 scheduler、复制 ticker、绕过私有成员及永久保留活动对象扩大了职责或隐藏了退出事实，本提案沿用原调度器和原入口。

## 逐项批准及验收

| 项目 | 下一步产物/批准范围 | 可观察验收 |
|---|---|---|
| A0，已完成 | 独立 MAP 链接及双 pool 重跑；core 只读 | 已定位 ticker shared thread 销毁调用 terminate；匹配输入证据保留 |
| A1，受控 CTA 正常退出链 | 上述 13 个生产源码文件及根因回归，一次完整实现，待批准 | pool=0/2 原 WtRunner 正常返回 exit=0；无 terminate/kill；parser/ticker/task/reader/pool 均完成；最后 callback 早于依赖销毁；ticker 与 task 两处线程所有权一起验收 |
| A2，发布级扩展 | 严格总截止、任意插件、外部保留/热卸载和交易路径各自另批 | 匹配其拥有者的并发、deadline、异常和副作用验收；范围外配置不会被误标受管可用 |

A1 的根因回归至少包含：延迟 on_init 后正常停止；Pending 两分钟 calculate=0 和补齐恢复保持；外部停止发生于 QMT HTTP、reader 完整 batch、pool callback 和 base 本地任务 batch；重复外部 stop；无 tick/休市等待可唤醒；配置中途失败；由测试持有的 slice/tick 跨插件实例销毁后读取/释放且模块保持；来源失败后停止。callback 内请求只验证请求返回和外部完成，不在 callback 内 join。使用显式事件观察阶段，禁止固定 sleep 充当就绪证明。可控阻塞通过事件释放后确认同实例 stop 完成；QNP/NHR 扩展的 Timeout 必须同时证明拥有者仍存活。无限外部 callback 的全链强截止留在 A2，测试 watchdog kill 仅作负例清理。

正常路径验证队列 accepted/completed 数量一致，异常路径验证失败/未执行数量及未知效果状态；整个过程保持空 traders/executers、本机随机端口和合成服务。停止成功后的观测窗口无新 callback，策略析构和模块释放顺序有证据。每轮输入摘要覆盖二进制、实际源码、服务夹具和配置。回滚以批准前输入及独立构建包恢复；核心差异登记到上游维护清单，生产部署仍需单独授权。

当前交付为 A0 已完成后的具体提案。核心源码保持未改；下一项为批准 A1 的 13 文件正常 CTA 停止范围，更新最终停止规格后一次完成所有者接线并按原入口验收。A2 维持独立待决，不作为本轮正常 CTA 停止的捆绑授权。
