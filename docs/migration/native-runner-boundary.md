# 原生运行器、行情线程与分钟关闭边界审计

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：任务研究。状态：源码审计及原 WtRunner 隔离运行完成，退出异常已复现，内部终止帧已由独立MAP和反汇编定位。日期：2026-10-21。适用基线：`08b230dd05facf6d650d949bfe51054115a2ecb1`。本轮保持框架只读；root 统一构建，在独立目录运行合成服务和空交易配置。

本记录为 [QNP](../specs/qmt-native-parser.md) 的资格边界提供依据；历史接口的正式要求仍以 [NHR](../specs/native-history-reader.md) 为准。本记录提出的宿主接口属于待决方案，不构成框架修改批准。

后续隔离证据：已编译自持原 ticker 探针（外部历史/待归仓路径：`../../tests/integration/runner_boundary_probe.cpp`），三个新目录子进程分别取得普通异常控制退出70、先stop再析构退出0、运行中直接析构触发限定terminate退出86。原始摘要为 `build/native/runner-audit/ticker-662012fae5b24cdcbfef15ffe817196c/summary.json`，探针SHA `a4ee73f2e803134d5835c2dcf63f3bdcc0bb229fd651259e79f7b2e2547d4d91`。这证明原ticker要求先stop，范围限公开ticker的独立生命周期；完整WtRunner启动、成员析构顺序和分钟门控仍属于下列待验项目。

QNP原适配投递路径的线程退出问题也已取得最小失败：原 `WTSPoolObject::allocate` 使用thread_local池，源码注释已说明retain对象跨线程池销毁的限制。新插件worker退出后，原WtDtMgr缓存仍持有tick，会访问失效池内存。修复归于自有QNP投递边界：独立堆对象沿原API和原子引用计数持有，不修改原池或框架。该证据不推广为其他原服务商插件在其既有线程生命周期中必然失败。

## 结论与证据等级

标准 `IParserApi` 工厂已把 QMT HTTP 轮询接入原 `ParserAdapter`；标准 `IDataReader` 已把同实例历史读取接入原 `WtDtMgr`。完整 WtRunner 的 pool=0/2 实验确认既有 `_ready` 保护初始化中的策略回调，Pending 时策略计算为零，补齐后计算恢复。受管退出仍有实际异常，完整范围见下方实验证据。

| 结论 | 依据与资格 |
|---|---|
| 原 ParserQMT 创建无 endpoint 的 MarketParser，持续 pump 需要宿主驱动 | 审计时自有工厂及 ManagedRuntime 源码；QNP 将承担接线 |
| 原 WtRunner 先连接 parser，再运行 engine | 原样源码确认；WtCtaEngine已有_ready策略tick门控，缓存接入与策略派发须分别实测 |
| reader Pending 后 ticker 仍推进分钟并调度 engine | 原样源码确认；NHR 原 CTA 宿主测试不包含原 ticker |
| 主 K 线没有新 closed 标记时通常不会 on_calculate，但其他调度行为继续 | 原 CTA context/engine 源码确认；需加入完整 ticker 对照测试 |
| 原完整退出链缺少 ticker/task join、parser release 和 reader delete | 原样源码确认；pool=0/2 的 SIGINT 返回后均异常终止，后续MAP定位CTA销毁未join的ticker线程 |
| 同实例补齐、旧 slice、pool 回调和 reader stop 已有隔离证据 | [NHR 验收记录](../evidence/2026-10-21-native-history-reader.md)；不扩展为完整 WtRunner 资格 |

本地只读脚本 `build/native/runner-audit/source_audit.py` 对 16 个文件执行 `git show` 并保存 SHA-256 至同目录 `source-identity.json`。15 个文件在换行规范化后与基线相同；ParserAdapter 只有已批准的 `_check_time(false)` 功能差异及末尾换行差异。该目录已被 Git 忽略。此检查证明所分析的调用链身份，不证明线程缺陷已触发。

## 原流程与所有者

入口为 [main.cpp](../../src/WtRunner/main.cpp)、[WtRunner](../../src/WtRunner/WtRunner.cpp)。main 调用 config 后未检查 bool；run 依次执行 parsers.run、traders.run、engine.run。同步 run 只轮询退出标记。WtRunner 的 engine、manager 和策略成员全部私有，公开入口只有 init/config/run。

配置先初始化 engine、再初始化 data manager，之后加载 parser 和策略。`initDataMgr` 未传播 data manager 初始化失败；reader init 为 void。`ParserAdapter::init` 在 parser init 失败后记录日志仍可返回 true；`ParserAdapter::run` 调用 connect 后忽略返回值。因此“模块已加载/runner 已进入循环”不能充当来源就绪证据。

| 调用链 | 实际线程与同步 |
|---|---|
| parser registerSpi/init/subscribe/connect | 原 WtRunner 配置/启动调用线程 |
| QmtHttpClient/QmtHttpEndpoint 操作 | 创建线程独占，必须同线程 prepare、pump、stop、销毁 |
| MarketParser→SPI→ParserAdapter→engine.handle_push_quote | pump 调用线程同步执行；原 adapter 不排队 |
| engine.run→ticker.run→engine.on_init/on_session_begin | run 调用线程；初始化完成后才创建 ticker 线程 |
| tick 驱动分钟关闭 | parser/pump 线程；ticker 在关闭段持 `_mtx` |
| 本地时间关闭、收盘补闭合 | ticker 自建线程；关闭段持同一个 `_mtx` |
| engine.on_bar/on_tick/on_schedule | 调用线程或配置的策略 pool；原 engine 会等待 pool 完成 |
| reader readKlineSlice | 初始化线程、策略 pool 或行情/ticker 回调线程均可能调用 |
| engine 的资金等后台任务 | 首次 push_task 懒创建的独立 task 线程 |

MarketParser（外部历史/待归仓路径：`../../src/GuanhengData/MarketParser.cpp`） 在 pump 和 receive 中持 recursive_mutex，锁跨越 SPI 回调。同线程重入可以通过该锁；若 pool 回调等待跨线程 MarketParser 操作，而 pump 正等待 pool，则会形成等待环。QNP 应让控制线程只访问自己的快照状态/目标订阅，不同步跨线程调用内部 MarketParser，也不持包装锁调用 SPI。

## QNP 可直接复用的公开接法

工厂创建自有 QmtPollingParser。init 解析受管配置；connect 只受理一次运行，工作线程依次创建 client、endpoint、专用轮询 decorator、MarketParser，prepare 后应用目标订阅并连接。循环执行有界 pump 和可唤醒等待。控制侧使用有界目标集合与版本；不积压无界命令。所有 endpoint 生命周期都在工作线程。

专用 decorator 在已通过 QmtHttpEndpoint 身份、能力、时间与 OHLCV 校验的 MarketSnapshot 上处理轮询重复，随后才进入通用 MarketParser：相同源/证券/时间/所有投影字段视为无新数据；同时间不同字段与倒序保持冲突。按字段比较，不比较结构 padding。仅下游正常接受后确认水位。保留退订证券水位并限制整个实例曾见证券数，避免重新订阅重放或无限增长。该层比较的是已投影快照，不能宣称比较了 endpoint 未映射的原 wire 字段。

SPI 回调必须在工作线程，callback 前释放包装控制锁。外部 stop 关闭准入并有界等待；回调内 stop 只标记并返回 Pending，外部后续确认 join。release 和 deleteParser 需幂等配合，因为原 ParserAdapter.release 会先调用 release，再调用删除工厂。stop 未完成时对象、SPI 和 DLL 继续存活。回调内 delete 需由外部宿主延后。

这条路径完整解决公开 parser 的 endpoint/pump 接线。标准工厂 ABI 无需变化；框架源码保持冻结。

## 启动屏障的实际缺口

[IParserApi](../../src/Includes/IParserApi.h) 和 IParserSpi 没有 engine-ready 通知。原 adapter 在连接前已按配置订阅合约；订阅出现不能证明策略初始化结束。reader 的首次读取也只能证明某个 context 已开始初始化，不能证明所有 context 完成。

原 engine.run 先设置 `_tm_ticker`，随后 ticker.run 调用 on_init/on_session_begin，最后才创建 ticker 线程。其间tick可能进入ticker/缓存路径；但WtCtaEngine::on_tick已用`_ready`限制策略tick派发，on_session_begin完成策略会话回调后才置true。此前仅依据trigger_price推断初始化期间会向策略派发tick不充分，需纠正。缓存路径、执行器handle_tick和策略回调是不同接缝；空执行器隔离实验只证明对应配置，不扩大为全部初始化并发资格。固定启动延时不能证明顺序。

`WtEngine::regEventListener` 是已有公共接口，但原 WtRunner 不暴露 engine 或 listener 注入。on_initialize_event 位于所有 context 初始化及初始 targets 提交之后，仍早于 on_session_begin 和 ticker 线程创建。自有宿主直接持有 engine 时可注册 listener；更强的准入屏障应由宿主在 engine.run 返回后打开。原 WtRunner 需要显式可达的启动完成通知，才能把 QNP 启动受理、来源已连接、允许向策略派发这三个状态分开。

## 缺口与分钟推进

[WtCtaTicker](../../src/WtCore/WtCtaTicker.cpp) 的数据驱动、计时器驱动和收盘补闭合三条路径均执行：

1. 先修改 `_last_emit_pos`。
2. 调用 void `IDataReader::onMinuteEnd`。
3. 无条件调用 engine.on_schedule；收盘时继续 on_session_end。

reader 没有返回值告诉 ticker 本轮 Pending。NHR 保持自己的事件游标不推进，但 ticker 的时间游标已推进，两者是不同状态。后续分钟可以从原 reader 游标恢复完整历史；恢复条目不会伪装 current。当前分钟错过后的历史补齐不会自动重放旧 on_calculate。无新 tick 时 ticker 也不会持续重试已经关闭的同一标签。

[CtaStraBaseCtx::on_schedule](../../src/WtCore/CtaStraBaseCtx.cpp) 根据主 K 线 `_closed` 决定 on_calculate；没有主线新标记时通常跳过计算，但仍先 save_data，末尾仍 `_last_barno++`。该标记只有 bool，context 本身不检查它对应的分钟标签。`stra_get_bars` 首次 Pending 时不建立本地 KlineTag；engine 已登记 bar 订阅，后续合格 on_bar 可以创建标记，因此 NHR 首次 Pending 的恢复路径仍成立。

[WtCtaEngine::on_schedule](../../src/WtCore/WtCtaEngine.cpp) 忽略 context 返回的计算 bool，仍刷新过滤器、汇总策略持仓、生成 targets/signals、排入资金刷新任务、commit_cached_targets 和保存状态。`on_tick` 路径也继续运行。此处描述代码路径，不代表现场产生过交易；无 trader/executer 的隔离配置与实际交易授权另行区分。

因此规格应明确选择所需保证：NHR 已保证“完整合格的当前 bar 才产生分钟事件”；“缺口时整个运行时不推进、不执行目标”需要宿主级准入和独立执行授权检查。该更强保证还需要定义 tick、会话结束、已存在条件信号与恢复分钟的处理，不能仅给 reader 加一个 bool 就声称完整冻结。

如增加 typed 分钟结果，应绑定本轮标签、请求/结果身份及 Readiness，不能在回调后读取一个会被并发历史查询覆盖的 last_status 来判断。分钟游标仅在准入结果与回调确认后提交；未知回调结果保持隔离，不重放。日历、覆盖、来源与缺口原因仍由既有 StrategyMarket owner 提供。

## 原并发与退出边界

ticker 的 `_mtx` 覆盖分钟回调段，无法覆盖所有状态访问：`_date/_time/_cur_pos` 在 tick 和 timer 中有锁外访问，`_stopped` 为普通 bool；`_next_check_time` 和 `_last_emit_pos` 为原子变量。关闭条件在锁外判断，锁内未统一复查。on_tick 的 prevMin/minutes 等函数静态变量也由多个 ticker 实例共享。以上为源码级并发风险，尚未通过本轮故障注入证明具体重复/错序。QNP 控制锁或 reader 内部锁不能统一串行化原 ticker 两个调用源。

退出链源码事实：

- WtRunner 析构为空，run 退出循环后没有 parsers.release、engine.stop 或 reader stop。
- ParserAdapterMgr 无自动 release 析构；ParserAdapter 析构为空。显式 release 会先设置普通 bool `_stopped`，再释放插件；该标记不能替代先停止并 join 行情调用线程。
- WtCtaEngine 析构直接 delete 私有 `_tm_ticker`；ticker 析构为空。ticker 有 public stop/join，但 engine 不提供访问或转发入口。
- StdThread 是 std::thread。若执行该析构链时 ticker 的 thread 仍 joinable，std::thread 的销毁规则会导致 terminate。完整进程已出现 terminate/abort；具体析构帧仍需符号证据，不能将该静态推导直接当作唯一动态根因。
- WtEngine 没有公开 stop/析构 join；后台 `_terminated` 仅初始化为 false，循环可能等待 condition variable。直接销毁也缺少线程收束。
- WtDtMgr 析构释放缓存，没有调用 reader 删除工厂。模块句柄/删除入口没有形成完整持有、停止、卸载生命周期。
- WtRunner 成员逆序析构会先销毁策略 manager、基础数据和 data manager，再销毁 engine、parser manager。仍运行的线程可能继续访问这些依赖。

受管退出所需顺序是：关闭新调用准入；停止行情派发与 timer 并确认在途回调；让已经投递的 reader 批完成 on_all_bar_updated；停止/清空或确认 engine 后台任务与 pool；停止 reader；释放 contexts、adapters、reader 和基础数据；最后在所有保留 slice/tick 都释放后卸载 DLL。callback 内停止应延后完成，禁止线程等待自身或等待正在反向等待自己的 pool。

## 自有宿主替代与最小受批范围

自有宿主可以直接组合公开的 base data、WtDtMgr、ParserAdapter、CTA contexts 与 engine，持有 parser/reader 控制接口，注册事件 listener，并在 engine.run 返回后开放行情闸门。该路径无需修改上游，适合继续验收 QNP 与 NHR 的组合；调用原 engine.run 仍会创建私有 ticker，故它单独不能解决完整受管退出或分钟准入。

另一个无需改源码的选择是自有 scheduler/派生 engine：公开 virtual run、handle_push_quote、isInTrading、transTimeToMin 可由自有实现承担调度，再调用原 context/engine 公开入口。它需要自行定义统一线程和会话生命周期，处理 inherited task 线程；属于新的运行宿主，不等于原 WtRunner/ticker 的完整验收。复制原 ticker、使用 private 访问技巧、强杀进程或仅永久泄漏对象，均不能形成已要求的受管退出证据。本轮不实现该替代。

下表保留静态研究中的候选职责，尚未形成批准请求。实际 Pending 实验已证明计算抑制与同实例恢复，因此全局分钟冻结、typed 关闭返回值和更强启动闸门属于额外需求，不纳入当前退出修复。先定位实际终止帧，再收敛必要文件和接口：

| 接缝 | 可能涉及文件 | 最小目的 |
|---|---|---|
| 就绪/失败传播和生命周期编排 | WtRunner.h/.cpp、main.cpp；必要时 ParserAdapter 返回值 | config/start 失败可见，run 完成初始化后显式开放行情，退出调用 stop |
| ticker 可停止及统一分钟准入 | WtCtaEngine.h/.cpp、WtCtaTicker.h/.cpp | 可达 stop/join；先取得 typed 关闭结果再提交游标/调度；统一两条线程的状态同步 |
| engine 后台线程停止 | WtEngine.h/.cpp | 关闭任务准入、唤醒等待、完成/明确终止任务并 join |
| reader 生命周期持有 | WtDtMgr.h/.cpp | 保存删除入口/模块句柄，stop 与 slice/DLL 生命周期由宿主管理 |

上表是必要职责清单，尚未确定修改每个文件。优先使用新增非虚扩展或独立 typed 适配，保留 IParserApi/IDataReader 既有 ABI；若最终必须改变公共虚接口，应单独列全体插件消费者并统一重编。每项变更分别记录上游差异及退出条件，回滚使用原基线和前一开发包。当前批准仅覆盖既有 ParserAdapter 初始化行，其余项目保持 proposed。

## 下一轮隔离验证入口

使用原 WtRunner 可执行程序、原 ticker 和公开 DLL 配置启动独立子进程，连接本机协议替身与既有 reader 服务，配置空 traders/executers 并保持现场服务隔离。记录事件来源线程、源/宿主分钟、reader 状态、on_bar、on_calculate、schedule、session 和 stop 顺序。

验收矩阵包含：延迟 on_init 时来源快速返回；首次历史 Pending 后补齐；中途缺口与下一分钟 recovered；同标签双关闭竞争；pool=0/2 回调重入读/停止；source 会话变化；网络超时；callback 异常；Ctrl+C/正常 stop/启动失败退出；持有 slice 跨 reader 停止。原行为负对照应在限定时长子进程执行并记录退出码，必要的停止修复仅在批准后形成正对照。

通过条件分别声明插件接入、历史可见性、完整宿主调度与受管退出，不以某一项替代其他项。矩阵中的其余场景仍需分别验收。

## 原 WtRunner 实际运行结果

使用 公开策略夹具（外部历史/待归仓路径：`../../tests/integration/runner_host/runner_probe_strategy.cpp`） 和 回环驱动（外部历史/待归仓路径：`../../tests/integration/runner_host/runner_host_flow.py`），直接运行当前工作区构建的 WtRunner.exe。pool=0/2 分别保存在 `build/native/runner-host-audit/pool0-02` 与 `pool2-01`；汇总为同目录 report.md。两组未配置 trader/executer，没有真实账户或行情请求。

| 观察 | pool=0 与 pool=2 的共同结果 |
|---|---|
| 延迟 on_init，行情已进入原缓存 | 可读 last_tick，初始化期间策略 tick 为 0 |
| 首次历史 Pending 后两次数据驱动分钟关闭 | 保存的 lastbarno 从 0 到 1，策略计算为 0 |
| 同实例历史补齐 | 当前标签 202610211930 产生一次 bar/计算，回调重读得到 2 根历史 |
| SIGINT 原处理返回后退出 | 策略析构 enter/exit 已观察到，进程退出 0xC0000409，原栈含 terminate/abort；driver 未强杀 |

这里的 lastbarno 是该轮递增前保存的值。初始化缓存更新、context 调度推进和策略计算次数分别取证。现有 ready gate 在本场景生效；多策略初始化、无 tick 时钟关闭、收盘和双关闭竞争尚未覆盖。

本次 Runner/Engine/Ticker/context/WtDtMgr 源码换行归一后与基线相同，ParserAdapter 和 WTSDataDef 含既有差异；整个二进制属于当前工作区开发构建。两例 Runner SHA-256 为 `5c53211523f8252b9bcce420ba957ad83c1e39f5081699467a025a3f60a06316`，其余输入摘要随每例保存。完整退出已证实存在故障，修复范围仍待动态根因收敛与用户批准。

## 独立 MAP 诊断定位

后续使用相同 Release `.obj/.lib` 单独链接 MAP 诊断产物，未修改源码或已验包。目录 `build/native/runner-host-audit/map-949158fb85a94cda9b68e0e6919bf81e` 保存链接命令、输入摘要、MAP及反汇编。诊断exe SHA-256 `8eac86ff795cd04368e8d929fbb6f3df30cbe0d70d81e5e33861029f9b0e1ed7`。原产物和新产物的.text摘要不同，因此重新运行 `map-pool0-01`/`map-pool2-01`，分别用各自日志的加载基址解析新栈；未用新MAP推断旧地址。

两组均再次出现相同退出异常。新MAP显示调用链为 `main → WtRunner::~WtRunner → WtCtaEngine::~WtCtaEngine → std::_Ref_count<std::thread>::_Destroy → terminate`。关键RVA为`0x6b280`（CTA析构+0x60）及`0x2bc79`（线程共享所有者销毁+0x19）。反汇编确认前者处于ticker成员释放段，后者在线程标识非零时调用终止；当前MSVC标准库thread析构在joinable时调用terminate。MAP中折叠函数的EventNotifier对象文件标记只表示链接符号来源，线程实际所有者由调用者和成员释放位置确认。

该动态证据将本例直接根因收敛为CTA析构释放尚未join的ticker线程。原Runner结束循环后先进入成员逆序销毁，缺少销毁依赖前的统一停止编排；单在较晚的CTA析构中补join，仍不能证明更早销毁的策略/缓存与在途回调安全。最小候选需明确停止位置、行情和timer收束及后台任务处理，再交用户批准。其他并发推测保持各自证据等级。

独立复核位于 `build/native/reviews/runner-exit-map-review/`：review.md、22项输入摘要、两次ASLR地址换算、链接输入核对及独立反汇编共同确认此调用链。joinable只表示线程对象尚未回收，不证明操作系统线程当时仍在执行。[正常CTA退出提案A1](native-cta-stop-proposal.md)已列出13个生产源码文件及对应回归，方案审查与用户批准、实现及最终运行资格分别记录。
