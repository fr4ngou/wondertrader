# 测试与端到端验收手册

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：测试操作手册。范围：测试分层、执行入口、断言和资格。当前测试盘点见[基线检查记录](../evidence/2026-10-20-native-release-upstream-testing.md)，覆盖存在与实际通过分别登记。

## 分层与用途

本地开发到master的自动检查入口为[本地CI](local-ci.md)。现有原生与软件测试按配置编排，执行相关变化追加重新构建及隔离执行链；当前实际覆盖和完整策略/真实柜台资格分别登记。

撤单复查的当前执行链入口见[标准交易链E2E](../../tests/integration/qmt_broker_context/README.md)，实际结果见[执行记录](../evidence/2026-11-06-cancel-refresh-e2e.md)。它使用真实WT执行器、标准插件及Host/WinSHM，SDK为明确替身；当前列表缺失的身份保留与完整跨日恢复分别登记。

| 层 | 目标链路 | 必要结果 |
|---|---|---|
| UT / 组件 | 计算、转换、时间、存储与单个模块 | 确定输入、边界/错误断言、可重复退出码 |
| 契约/插件 | 工厂加载、接口布局、线程/生命周期、帧/模型 | 实际生产者/消费者一致，错误与背压有依据 |
| 隔离 E2E | 固定数据 → 策略 → 已配置风控 → 执行 → 隔离后端 → 回报 → 业务读取 | 信号/目标/订单/成交及账户观察可核算；全链自动断言 |
| 故障与恢复 E2E | 原全链加断连、超时、重启、重复/乱序、存储失败 | 无盲目重复副作用，缺口/未知可诊断，恢复依据充分 |
| 实际环境资格 | 实际程序/SDK/终端、只读行情和账户 | 真实版本、身份、线程、数据完整性与时效 |
| 受控模拟/发布后验真 | 经授权场景、真实用户入口与运行组件 | 实际下游数据、正常/空/异常/恢复及适用操作 |

UT 框架内也可以包含存储或外部资源测试；按真实依赖分类，不仅看测试工程名。交互式调试工具、模拟后端和自动验收脚本分别登记，自动 E2E 需要编排、断言、清理及明确退出结果。

## 原生入口

原生回归使用本仓实际构建输入和已登记CTest。历史`qmt-readonly-fixed`及其外部旧QMT Core/Queue/Journal合成HTTP链已退出当前CI和操作范围；原8组CTest、回调门控、公开ABI及CNG资源释放断言只解释其绑定旧来源的历史证据，见[NQP历史契约](../specs/native-readonly-package.md)。原失败和通过记录保留，新共享内存实现须按自己的输入重新验收。

SDK-independent 自动流程使用 `python -B scripts/native.py test`，前提是本配置和输入已经成功构建；`all` 会顺序完成所有必要阶段。JUnit 和阶段日志保存在生成目录。当前默认选择与其余原始用例的区别见[构建手册](build.md)。

当前基础测试入口为 [TestUnits](../../src/TestUnits/CMakeLists.txt)，采用 GoogleTest。先在已验证工具链构建；使用生成的程序执行 `--gtest_list_tests`，记录实际 collection，再选择测试。

```text
<测试程序绝对路径> --gtest_list_tests
<测试程序绝对路径> --gtest_filter=<已核实的测试选择器> --gtest_output=xml:<报告绝对路径>
```

指定独立可写工作目录，核对测试内的文件、共享资源、硬编码路径及配置依赖。`TestParser`、`TestTrader` 和各 `Test*Porter` 先读源码再运行；部分程序是交互调试或具有交易副作用，exit 0 也可能只代表配置加载路径退出。

自有接入的自动入口由 adapters.cmake（外部历史/待归仓路径：`../../cmake/native/adapters.cmake`） 注册。CTest 可按 `integration.*` 选择；完整制品仍使用 `native.py all`，其包级验证从校验并解包后的目录加载。

| 自动入口 | 实际依赖与断言 |
|---|---|
| `GuanhengmarketTests` | 真实 WtDtHelper/DSB、合成历史源；覆盖补数/发布/冻结、容量与竞争 |
| `GuanhengMinuteProbe` | 动态加载真实 WtDataStorage Writer/Reader、合成累计快照；闭合分钟与生命周期 |
| `GuanhengexecutionTests` | 隔离 Host 端点与原生 SPI；授权身份、提交/消费未知、去重和回调重入 |
| `GuanhengRuntimeProbe --self-test` | 真实 WT adapter、合成行情与交易端点；有界调度及通道恢复 |
| `GuanhengPluginProbe` | 从指定包目录加载四个实际工厂；缺少端点及裸交易明确拒绝 |
| business unittest / `package_probe.py` | 原生历史到业务门面；显式指定外部受控业务代码时验证原 DTO/策略/服务契约 |
| `wt_strategy_replay.py` | 实际 WtBtPorter 时钟驱动固定原策略核心，整段/增量及当期目标对照；不提交委托 |
| `integration.history_worker` / `package-history-worker` | 独立进程调用原 Operations 纯 DTO/内存归约器与合成 HTTP 市场/证据服务；验证锁、恢复、中断/排空和去敏。包阶段子进程仅加载已安装 wheel 与可信合成部署工厂，`-I -S` 不导入私有业务源码 |
| `integration.history_calendar` | 标准库计划消费者的严格契约、总截止、HTTP 边界、内容摘要与证据故障恢复 |
| `integration.calendar_flow` / `package-history-calendar` | 显式受控生产源码的真实只读日历路由、原 Operations 归约器和 wheel 作业链；原生 DSB 用例分别绑定源码或搬迁包的 DLL/服务模块，合成行情与证据服务的实际边界由回执登记 |

表中涉及旧外部业务核心或生产路由的oracle属于保留测试源码职责，当前source-free流程跳过或明确unavailable。旧`--qmt-source`及`--calendar-owner-source`不进入当前受支持操作，CI显式清空其两个来源环境变量。skipped/unavailable不授相应业务资格；迁入本仓的策略和服务必须通过自己的执行链验收。真实终端与已部署用户入口仍单独验收。

`TraderMocker` 可以作为仿真后端的一部分，需固定输入、处理其时间/随机性并补齐可核算断言；它本身不构成已经交付的系统 E2E。

## 观衡Python生命周期回归

当前回测只读边界沿[NBW](../specs/native-backtest-workspace.md#nbw-r5-验证)和ADR-0016执行。backtest_workspace的HTTP回归使用实际create_app、BacktestArchive与有界读池；执行owner的纯回归独立保留。test_archive_runtime.py、test_archive_retry_runtime.py及配套浏览器驱动绑定旧运行管理候选，只能复核其原冻结安装，当前只读App不执行这些历史启动/保存入口。现行只读后继的命令、安装身份和结果见[验证记录](../evidence/2026-10-30-readonly-backtest-regression.md)。

Windows工作流（外部历史/待归仓路径：`../../.github/workflows/native.yml`）可手动选择`python-lifecycle`独立运行，原生编译job按原条件跳过。独立业务回归使用Python3.12和3.14，各自安装本仓所有局部包及dev依赖。构建后端取已有依赖配置的固定URL/SHA，第三方版本约束从`apps/guanheng/uv.lock`取得；本仓目录包由同一锁文件定位，禁止把私包存在与公共索引可下载混为一谈。该入口不要求旧QMT源码或柜台配置，不启动原生编译链。

已准备相同依赖的Windows开发环境，可在仓库根执行以下选择。

```text
python -B -m pytest -q tests/integration/thread_owner tests/integration/watchlist tests/integration/backtest_workspace tests/integration/app_console tests/integration/strategy_host tests/integration/qmt_shm_account/parent tests/integration/qmt_shm_account/test_scan_config.py tests/integration/qmt_shm_account/projection/test_projection_v3.py tests/integration/qmt_shm_account/scan/test_smoke_ipc.py tests/integration/qmt_shm_account/scan/test_case_oracles.py tests/integration/qmt_shm_account/scan/test_source_capture.py tests/integration/qmt_shm_account/scan/test_fixture_runtime.py tests/integration/qmt_shm_account/scan/test_fixture_lifecycle.py
```

pytest仅自动收集所选目录中的`test_*.py`；同目录`smoke.py`、`prepare.py`及原生独立脚本分别保留其原入口。`test_process_information.py`包含真实自建Python进程/Win32句柄回归；`app_console/test_native_chain.py`缺少明确原生安装输入时会跳过，跳过不授原生资格。这组覆盖线程启动未知/晚入口/尾声/join、账户门禁/配置/投影、回测及页面后端软件行为、Job原始句柄和宿主关闭/后代守卫；schema2烟测IPC纯回归直接验证严格JSON与观察/完成成功事实，仅读取本仓固定帧及夹具。临时输出使用独占测试目录，JUnit按Python版本归档；缺少依赖、收集失败、断言失败或工作流超时均应作为未通过处理。

`scan/test_smoke_ipc.py`与`test_case_oracles.py`验证严格IPC及成功/配置拒绝/partial的独立判据；`test_fixture_runtime.py`和`test_fixture_lifecycle.py`验证有限控制值、安装身份准入和替身关闭流程。四个显式纯入口仅在精确替身中调用`scan/run_schema2.py`的main，不启动真实双环境测试流程、Host/Agent或原生DLL。双环境完整安装和原生夹具按[ATI规格](../specs/native-account-test-runtime.md)分别验收，完整45项原生资格不由纯回归授予。

CI登记与测试实际通过分别记录。受控替身和Python线程回归不替代真实原生进程/父死亡/IPC2、安装迁移、浏览器入口、实际QMT来源、实时和交易验收。schema2公开账户入口已有[真实主路径证据](../evidence/2026-10-28-qmt-account-public-main.md)，实际查询、完整故障矩阵、独立安装、浏览器及生产分别记录；静态审查通过保持其静态范围。

## 标准QMT候选的共享内存组合

测试模块说明（外部历史/待归仓路径：`../../tests/integration/qmt_standard_trader/README.md`）登记固定原版Adapter、新Native探针及SDK替身的完整事件链。严格入口4方法包含真实Agent/Win32 SHM/Host/R21至原Adapter的正常、重复和回调stop三模式，以及清理失败原件回归。它独立于默认native.py test与托管CI选择；编译、显式执行、实际环境及生产资格按各自证据确认。外层先创建独占输出根，冻结EXE/DLL/Python依赖，沿原隐藏Job与总截止执行。

## E2E 场景登记

每项登记规格要求、入口、组件和进程、依赖模式、输入/初始状态、预期输出、断言、超时/资源预算、退出码、清理/恢复、证据位置及维护者。

最低链路场景包括：历史与实时到策略可见；目标到受控委托；部分成交/撤单结果；完整账户观察；重启与状态保全；重复/乱序回报；未知提交不重发；包切换/配置回退后的真实入口。按照系统实际功能选择适用场景，缺失的组件或场景标为缺口。

运行包级测试时固定 EXE、核心库、插件、SDK、配置和数据身份。容器组件与原生组件之间的契约测试仍属于完整链路的一部分，独立单测不能代替连接处验收。

## 执行与复用

先运行受影响的轻量层，再执行必要的跨进程/持久化/恢复链。按实际影响选择场景，复用输入匹配的通过结果；失败与环境不满足分开说明。长用例登记预算，减少无独立验证价值的重复准备与样本。

记录实际测试名称、步骤/参数、输入身份、报告和退出码。只存在测试源码、只启动进程或只输出日志时，记录相应范围；运行资格还需匹配的成功断言。总体规则见[验证规范](../development/verification.md)。


## 个人观察偏好回归

`tests/integration/watchlist`包含协议值、持久owner、Windows锁转换纯替身和HTTP接线四个入口。owner组在Windows临时目录验证OS单写者锁、创建瞬间竞争、解析后UNC/device/remote拒绝、版本竞争、真实文件原子保存、晚提交核查和关闭在途；锁转换组用纯替身验证原handle/descriptor/借用stream逐阶段迟到和失败清理，未调用实际WinAPI；HTTP组以实际App路由和明确owner替身核对协议、同源guard、容量和原截止。自选不调用QMT/SDK/交易；这些测试包含文件及Python线程行为，不能概括为纯值测试。前端`workspace/watchlistApi.test.ts`与个人观察组件回归分别核严格消费、一次PUT、冲突/未知后的GET核实和分钟图调用隔离。

定义、CI登记、实际执行、正式安装与用户入口分别取证。全新正式包和生产SPA须验证真实保存→移除→应用关闭→同根重启→相同身份/版本/顺序，并覆盖坏文件、残留tmp、锁冲突、空状态、断连和恢复。各次执行结果和资格以对应证据记录为准。

账户source_capture回归只使用标准库与临时文件，核Host原始binding/profile字节SHA、同轮前后来源、跨轮拒绝、容量与同截止，以及原件发布的不可覆盖语义。它不启动真实Host/Agent；真实双安装配方由Host采集原件，parent实际tree0/EOF/join后才采用。完整45项的状态和真实执行结果分列，纯入口不能授账户原生运行资格。


## 账户输出 owner 故障单元组

账户原生 profile 的冻结 selection 可显式启用 frame_tests；它必须与 required_ctests 中的 account-frame-io 同时出现。构建入口从同一 owned-input 原 bytes 核摘要后读取选项，额外构建 GuanhengAccountFrameProbe，并要求 CTest 精确返回全部已声明用例且无 skip/failure/error。

测试模块说明（外部历史/待归仓路径：`../../tests/integration/native_account_frame/README.md`）列出14个 FrameWriter 正常/短写/刷新失败/迟到/编码异常场景。probe直接复用同一产品translation unit的输出owner，独立QA入口不调用scan、Adapter、Host、Agent或SDK；QA exe不进入产品安装。运行器沿原native.run的隐藏窗口、Job和超时清理入口，记录自身二进制摘要。

此组授予范围仅为 frame-owner-only；测试回调收窄同一Deadline来覆盖迟到后置检查，真实时钟/阻塞CRT/父硬截止、实际管道/进程树、schema2的45场景及双环境安装另验。源码、CTest登记和实际执行分别记录；当前执行资格按对应证据为准。


## 账户只读测试的双角色普通安装

[安装装配工具](../../scripts/native_support/account_runtime_install.py)的`prepare(root, work, python, uv, backend, run, *, offline=False, wheel_cache_dirs=())`构建App七个和Host/Agent两个本地wheel，再分别生成完整hash锁、wheelhouse及普通CPython3.12环境。版本及依赖来自各项目pyproject；App使用冻结uv.lock，Host按声明生成完整锁。安装沿标准依赖解析执行，完成后逐角色运行标准`pip check`及唯一runtime_identity准入；不使用产品源码覆盖或跳过依赖。

调用方提供绝对路径、完整冻结源码树及fresh工作目录；源码树必须包含此工具和固定QA源。旧冻结树缺工具时，先建立独立安装输入副本，加入工具并记录新身份，保持原制品和产品源码身份可追溯。Flit backend按构建锁核原wheel摘要。离线模式从显式缓存准备所有轮子，缺包即失败。

`run`由受管执行器提供：失败抛错，覆盖整体截止、每命令期限、有限输出、TEMP/TMP、创建期Job和每命令私有隐藏console。pip/uv可能启动后代解释器，顶层隐藏不能代替该约束。工具自身不创建进程。成功输出`installation.json`及两个角色runtime-receipt；失败保留原工作目录，不发布成功收据。

工具纯回归入口为`tests/tools/account_scan_build/test_runtime_install.py`。双安装结果、普通EXE合成场景、完整45项、真实QMT和用户入口分别登记；单配方完成保留runner非零开发资格退出，不能改为CTest成功或跳过。

Python生命周期工作流同时显式登记`scan/test_fixture_start_location.py`和`tests/tools/account_scan_build/test_runtime_install.py`纯回归。工具测试目录变化进入整个现有工作流的路径过滤：push/PR仍按原任务条件同时调度通用windows-native构建/测试/打包，以及Python生命周期矩阵；两个新增纯入口仅在后者执行。此处不调度账户schema2双环境安装或45项原生配方，其资格由各自受管入口验收。CI执行结果以对应运行原件为准。


## 个人观察正式安装与生产页面链

维护入口为Node用户链（外部历史/待归仓路径：`../../tests/integration/watchlist/pwl_user_chain.mjs`）与同目录真实App进程（外部历史/待归仓路径：`../../tests/integration/watchlist/pwl_app_entry.py`）。它补充pytest/组件层，使用真实HTTP、独立App安装、原WatchlistOwner和生产SPA；不依赖运行QMT或交易账户。

在现有隐藏、创建期受kill-on-close Job管理的执行器中运行以下内部命令，依赖取既有console的Playwright和显式Edge，不下载新浏览器：

```text
node.exe tests/integration/watchlist/pwl_user_chain.mjs --python <正式App的python.exe绝对路径> --static <生产dist绝对路径> --root <全新偏好目录> --output <全新结果目录> --screenshots <全新截图目录> --edge <msedge.exe绝对路径> --seconds 180 --source-manifest <发行源码SHA清单绝对路径>
```

源码SHA清单由发行冻结输入持有，结构为files对象：相对guanheng_app的全部.py路径映射SHA256字符串；不能从待验site-packages生成期望值自证。三个全新目录的父须预先存在。根/结果/截图目录独占，现有资料不自动删除；静态目录与App包运行前后按外层构建收据和本入口身份核对。Windows venv launcher与实际Python PID分别保留，ready/closed必须在同一实际PID及其父链上对应；外层执行器另证整树归零、EOF和资源回收。

链路覆盖有效空、添加/移除、正常退出、新进程同快照重读、同版本并发只提交一次、写锁冲突、不可用页面、锁释放后的新实例恢复及360px布局；错误或不明退出均失败。分钟/账户/回测来源显式空，保存不会触发相关请求。坏文件、临时残留、迟到提交和真实断连各沿对应实际证据登记，不由核心链代授全部故障或生产资格。执行记录见[个人观察证据](../evidence/2026-10-23-personal-watchlist.md)；托管CI调度与实跑单独登记。


## 回测完成归档的真实恢复专项

维护入口为后端专项（外部历史/待归仓路径：`../../tests/integration/backtest_workspace/test_archive_retry_runtime.py`）及真实浏览器专项（外部历史/待归仓路径：`../../tests/integration/backtest_workspace/archive_retry_browser.mjs`）。它补充pytest和组件测试，运行真实安装的App、原生回测DLL、HTTP与生产SPA。入口固定工具及输入身份，须准备匹配的冻结计划和全新工作根；具体已验身份与命令收据见[专项证据](../evidence/2026-10-26-backtest-archive-retry.md)。这些脚本不会由pytest自动启动；源码存在不等于CI已执行。

编排由隐藏、创建期kill-on-close Job执行器持有一个原总截止、首管道限额和实际进程句柄。后端内部命令形态为正式App解释器 -I -X utf8 -B 后端脚本 --run --inputs <绝对路径> --inputs-sha <SHA256> --deadline <同机monotonic绝对D>。浏览器同时接入该D和两阶段ready，实际点击唯一归档重试按钮，待context/browser关闭后分别写精确握手；第二App只读报告及配置，禁止重跑回测或再POST。Node时钟由一次Python monotonic/GetTickCount64锚转换，重试/重启不续总D。

实际文件拒绝须与超D区分；移走的失败夹具只限本次新根、已核身份的空目录并保留held，禁止递归清理既有运行。通过要求同run/request、原Native仅1次、唯一retry200、新进程Native/POST0、原报告/配置/文件树相同，以及全部App/Browser/Job回收。页面错误/越界或超D保存首因并失败；更换失配制品或修复后使用新根，保留原失败。此场景只授对应合成实验及正常重启，不授真实券商或断电恢复。


## 采集自动收盘主链

`tests/integration/qmt_quote_collection/run.py --automatic-session`在全新夹具目录使用短模拟交易时段，保持系统时钟与原StateMonitor逻辑。调用者提供原monotonic绝对截止、搬迁原生目录/采集入口、证券数与停止预算；整体预算应覆盖最多三分钟状态机等待、启动/处理及关闭。该模式与peer-delay互斥。

入口沿真实App托管、WinSHM和原Writer接收两代明确SDK替身行情，关闭前检查完整DSB/marker与实际子进程，再关闭并用Helper核首尾证券的OHLC/量额/标签及前后文件SHA。默认模式继续验证allday/显式关闭归档。合成时段成功、真实日间自动归档及全天分钟完整性分别登记。
