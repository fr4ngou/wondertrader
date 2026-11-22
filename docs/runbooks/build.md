# 构建与验证手册

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：运行手册。范围：仓库维护命令、实际构建入口及支持环境登记。命令结果与待验证范围见[当前事实](../roadmap/CURRENT.md)。

## 本地持续集成入口

日常开发与本地master合入使用[本地CI手册](local-ci.md)。入口在本机编排文档检查、已登记的软件回归及按改动追加的执行链构建/E2E，保存源码身份、日志和RESULT.json；不依赖托管工作流。完整构建、打包、部署和发布后验真分别沿本手册及[发布规范](release.md)执行。

执行链CI复用已验证的工具链、依赖源码缓存和批准的WT快照，为当前候选冻结源码并重新构建原生产品；测试使用独占目录和SDK替身。本机路径写在忽略的`.local-ci.json`，账户和生产配置不进入CI设置。

## 构建、安装验证与测试产物清理

每次构建、安装验证和测试的执行者负责在本次任务收尾时清理自有临时产物。适用范围包括 `--work`、CI `--output`、执行临时根、pytest 临时目录、安装验证目录及其解压副本、虚拟环境、冻结源码、编译中间文件和重复候选包。本机历史临时根 `D:\wt-build` 同样适用；目录名或执行成功本身不代表已经完成清理。

清理范围以本次实际生成和使用的绝对路径为准，包含盘根、仓库外部和未登记为Git工作树的目录。批量排查先列出相关卷根与工作区下的物理目录，再核对Git登记、目录内容及实际引用；逐项区分临时产物、独立源码仓库、正式安装、业务数据、发行制品、共享依赖和保留证据。交付说明列出已经检查的根目录及未覆盖范围。目录名称和Git登记分别作为调查线索，最终按事实所有者和依赖判定清理范围。

1. 执行前登记本次专属输出目录及用途，复用输入仍有效的构建和验证结果；共享工具链、依赖缓存、正式安装及业务数据分别放在长期受控目录。
2. 验证完成后，将后续核验必需的源码身份、命令、结果摘要、`RESULT.json` / receipt、关键日志及独有故障证据存入任务的长期受控证据目录，并在已有交付记录中写明位置。已交付制品和指定回滚包存入制品目录，核对摘要与读回；按用途保留必要材料，随后清理可重建的大体积内容。含账户资料的原件留在受控环境，仓库只保存脱敏摘要。
3. 失败或中断时先保留复现所需的最小输入和首错证据；问题解决并完成回归后清理余下现场。任务仍在进行时记录目录、所有者、用途及解除保留的条件，续接者继续完成收尾。
4. 删除前解析并核实每个目标绝对路径位于本次明确指定的临时根内，逐项确认独有文件、目录联接/符号链接和其他任务占用。从实际启动入口递归检查进程、服务/计划任务、角色配置、子进程工作目录、解释器、DLL、虚拟环境基础解释器及重启依赖；同时检查启动时注入的环境文件、配置文件路径及嵌套配置。私有正文只投影本次需要的路径、摘要和状态，凭证保持在受控环境。已结束任务遗留的测试进程先核实身份与实际调用者，再按原任务范围关闭；运行依赖先迁到长期受控位置并按原授权验真，共享缓存继续由缓存所有者管理。
5. 对核实后的自有叶目录使用原生文件操作清理；Windows 使用 `Remove-Item -LiteralPath <已核实的绝对路径> -Recurse`，保持路径核验和删除在同一 PowerShell 操作链中。递归删除逐项显式选择目标，普通删除保留文件系统保护；遇到未知内容、链接、文件保护或占用错误时保留该项并查明原因。其他任务目录、正式数据与安装按其所有权和授权处理。
6. 清理后核对目标已消失、磁盘空间变化、归档材料可读，以及受影响的既有入口可用；交付记录列出清理范围、保留项、原因和后续动作。文档中的旧临时路径只用于追溯，当前复核沿转存位置读取。

清理是每次任务的交付步骤，与[Worktree收尾](../development/workflow.md#worktree收尾)一同完成。共享临时根按各任务所有权逐项处理，按日期整根删除会丢失在用依赖和独有证据。当前要求由执行者手动落实，现有构建与 CI 命令的成功返回仅表示相应执行完成。

## 文档检查

独立 Host/Agent/Core 的永久源码构建、普通安装和合成 SDK 验收见[来源三包手册](source-packages.md)。

在仓库根目录、Python 3.10+ 环境执行：

```text
python -B scripts/project.py start
python -B scripts/project.py check
```

维护工具仅使用 Python 标准库。原生运行环境、服务商 SDK 所需解释器与文档工具环境分别管理。

## 可执行的原生流程

入口为 `python -B scripts/native.py <阶段>`；Python 3.10+，原生 profile 选择 SDK-independent 核心及模拟组件。Windows x64 工具发现使用 vswhere、MSVC 开发环境和已安装 CMake/Ninja，不修改全局环境；真实支持版本通过 CURRENT 证据登记。

```text
python -B scripts/native.py doctor
python -B scripts/native.py all --jobs 4
```

完整流程是固定依赖 → configure → build → 独立客户端 wheel → CTest → 流水线负向用例 → staging/install → manifest/ZIP → 解压校验 → 搬迁后 Runner 冒烟和原生回放。各阶段失败返回非零码并停止依赖阶段。

独立客户端使用单独锁定的 Flit backend，详见[SDK 手册](client-sdk.md)。原生包携带同一 wheel；隔离安装后在独立 Python 进程通过 HTTP 验证，消费者无需 WT 动态库或业务源码目录。构建前后重新核对显式源清单，未登记文件、构建期间输入变更或 wheel 内容不符均停止交付。

原生 profile 同时构建 ParserQMT/TDX、TraderQMT/TDX、受管 Runtime 与历史导入探针。开发包检查实际 DLL 工厂、真实 WT adapter 注入、LC1→原生 DSB→Python 业务模型，并用包内模块运行；默认工厂缺端点时明确不可用。

当前默认构建和CI使用本仓库实现与显式依赖，不导入或运行旧QMT工程。默认native在未选择外部源时，对保留的旧业务/日历oracle返回skipped或unavailable；该结果只说明对应旧oracle未验，不能代替本仓业务功能验收。独立业务应用及其生命周期回归按[测试手册](testing.md)运行。

历史`--qmt-source`、`--calendar-owner-source`及对应环境变量仍保留在工具源码中，用于解释既有构建和回执；当前受支持操作不使用它们。CI显式清空`GH_QMT_SOURCE_ROOT`和`GH_CALENDAR_OWNER_SOURCE`，避免继承旧外源选择。本仓迁入后的策略、日历和业务由各自模块及安装链验收。

历史部署工厂的构造回归使用实际 storage 依赖；构建解释器须安装 `config/python-build-dependencies.json` 中的 `client_optional_dependencies.storage`。CI 从该清单安装；基础 SDK 消费者仍可省略 extra。历史外源日历链使用的`GH_HISTORY_FACTORY_STORAGE_SITE`仅说明原隔离依赖绑定；旧来源验证已退出当前操作范围。运行方法见[历史部署手册](history-deployment-factory.md)。CI 此步骤只锁定清单列出的直接依赖，完整传递依赖锁定属于发行环境验收。

默认生成目录为仓库的 `build/native`，可通过 `--work <生成目录>` 指定；TEMP/TMP 同样放在该目录。阶段入口包括 `deps/configure/build/test/package/verify`。离线使用已缓存依赖时添加 `--offline`，完整依赖源码复核添加 `--audit-deps`，清理生成的编译目标后重新构建添加 `--clean-first`。

依赖定义：[锁定清单](../../config/native-dependencies.json)；上游基线：集成身份（外部历史/待归仓路径：`../../config/upstream-baseline.json`）。归档先校验再解压，缓存源码按原字节与变化文件验证，构建配置和源输入绑定到 receipt。

输出包括 `logs/`、`receipt.json`、`ctest.xml`、`packages/<开发包>.zip` 和外部 `.sha256`。每个包记录实际编译器/CMake/Ninja、上游/下游、未提交状态、源码指纹及文件清单。此入口生成开发候选，不自动发布或启用运行实例。

## 后台构建的窗口与日志

研究、文档提取、依赖探测和其他辅助命令遵循同一进程执行边界。任务限定不启动进程时采用纯读取或明确保留unknown；技能、库和“静态研究”标签不扩大工具权限。命令退出、顶层隐藏、Job归属及后代资源回收分别留证。

后台批次由明确的进程所有者启动，顶层使用无窗口选项。普通直连命令统一使用`native_support.process_startup.background_process_options`，`native.background_process_options`保留为同一函数的公开入口。当前原生流程的源码Git探测、账户制品工具版本探测与客户端wheel构建同样使用该选项；构建driver需要供第三方后代继承的专属隐藏控制台时，使用`native.run(..., private_console=True)`。无窗口标志属于单次进程创建参数，不能假定Ninja或其他构建器会替后代继承；已有可见用户终端保持原状，不调用全局隐藏窗口操作。

`native_support/hidden_build.py`负责在既有受管Job中启动隐藏driver，要求绝对可执行文件、工作目录和日志路径，以及有限的`--seconds`。调用方在bootstrap运行前完成Job归属，并拥有整个批次的绝对截止、内存/输出预算和父死亡回收；成员身份检查不会替调用方配置这些限制。各类窗口、真实第三方后代和退出行为按实际工具版本验收。需要可见控制台或人工CtrlBreak的测试独立运行，普通自动批次不包含这些场景。

构建日志文件使用UTF-8保存全文。控制台展示依实际目标流编码将不可编码字符转义，命令的成功、失败及超时仍按原进程结果处理；日志文件或管道的真实写入错误保留。源码变更后的运行资格及未覆盖窗口类型见[后台工具证据](../evidence/2026-10-23-background-process-windows.md)，未验候选不作为正式发行依据。

## 退役的固定来源验证

历史`qmt-readonly-fixed` profile会导入固定旧QMT源码执行合成HTTP/Core/Journal验证，已退出当前CI和受支持构建步骤。其源码、旧开发包和[NQP历史契约](../specs/native-readonly-package.md)保留以解释原始证据；旧命令和旧通过结果不授新共享内存账户或当前安装资格。

新共享内存接入使用本仓独立Host/Agent及原生插件，行情、历史和账户分别按对应模块登记构建、安装、搬迁和真实来源验收。默认native与Python生命周期CI不检出旧工程、不提供旧source/token输入。当前源码中尚存的历史profile与外源参数按上节退役边界处理，不能作为当前交付依赖。

## 上游原生工程入口

当前总入口是 [src/CMakeLists.txt](../../src/CMakeLists.txt)，使用 C++17；上游环境说明见 [src/README.md](../../src/README.md)。该说明记载历史参考环境，实际支持矩阵以已验证证据为准。

总工程包含多个服务商 SDK 和共享依赖。依赖、编译器、架构、生成器、运行库、插件 ABI 和输出路径按目标配置冻结；实际安装及运行证据登记后再声明支持。

以下为构建步骤模板，尖括号参数必须替换为已核实的环境值：

```text
cmake -S src -B <构建目录> -G <已验证生成器> <对应架构及依赖参数>
cmake --build <构建目录> --config <已验证配置> --target <受影响目标>
```

Windows MSVC 分支在当前 CMake 中读取 `MyDepends141`，其他平台依赖路径由 CMake 定义。服务商库可能需要额外部署许可与匹配二进制；源码齐全、配置成功及可运行分别记录。

## 测试入口

行情采集可通过 `scripts/writer_lifecycle.py --work <全新构建目录> --baseline <固定上游基线> --install-prefix <全新安装目录> --deadline <绝对单调截止>` 构建并显式安装 `GuanhengCollection`。driver核固定批准覆盖、源码快照、工具链及同一截止，`BUILT.json` 与 `INSTALLED.json` 分别记录构建及安装文件身份；原默认安装不包含该可选组件。安装包包括原生会话/Writer/Helper、必要运行库、终端外采集Python源码闭包和许可证，观衡App保持独立发行。运行参数、秘密编码及单写者交接见[采集手册](qmt-data-collection.md)。

正式采集主路径入口 `tests/integration/qmt_quote_collection/run.py` 实际调用App lifespan、创建期Job子进程、WinSHM与Native Writer，再经Helper回读；源端为明确SDK替身。`native_failures.py` 在全新隔离目录制造文件障碍，核真实Writer错误传播和资源回收。纯生命周期测试与真实终端来源资格分别登记。

原生基础测试工程为 [TestUnits](../../src/TestUnits/CMakeLists.txt)，其他 TestParser/TestTrader 等工程可能连接外部环境。运行前核实测试源码、配置、账户权限及是否具有真实副作用。

默认自动原生用例来自 `test_codehelper/test_fmt/test_session/test_wtsvariant/test_replayer_fee`，其余依赖外部资源、专用环境或性能负载的用例另行登记；原有交互式交易调试工具不进入默认流程。

上游全天用例的隔离状态与恢复条件见[当前构建证据](../evidence/2026-10-21-native-build-automation.md)；启用测试和 Disabled 数分别报告。新增分段日间时段回归覆盖午休及收盘，头文件依赖测试检查 Ninja 的真实依赖记录。

CTest 还验证 Runner `--help` 和实际 WtBtPorter 回放/CTA/模拟持仓/CSV 结果；测试脚本直接调用原生 C 接口，无 wtpy 依赖。流水线用例验证依赖、子进程及制品失败路径。具体通过结果和未覆盖范围以对应执行回执为准。

测试分层、GoogleTest collection、交互工具与系统 E2E 的区别见[测试手册](testing.md)。独立入口已注册 CTest；上游总入口的原始测试注册状态按其源码核实。

## 依赖与环境记录

每个有效环境记录 OS/架构、编译器、CMake、依赖/SDK 版本与来源、哈希、构建命令、制品位置和运行参数。机器绝对路径、私有端点及凭证引用保存在相应受控环境记录，示例保持脱敏。

更换工具链或依赖后复验相关 ABI、插件加载、接口生命周期与目标测试。发布操作见[发布规范](release.md)。


## native.run 输出额度与原总截止

自有工具调用native.run时，默认max_output_bytes为8MiB原字节，显式值限1..64MiB。
额度在真实目标第一层stdout/stderr合并pipe上、UTF-8解码前计算；恰额度允许完整成功，
超额保留有限前缀并失败。日志保持UTF-8 replace与universal newline口径，替换字符的
UTF-8编码可使日志正文大于原字节额度，最大按固定倍数加有限marker约束。
成功返回仍为完整文本和耗时二元组；有限前缀永远不作为成功输出。

原timeout在入口固定单调总D，工作D预留min(5秒,timeout/5)给同次树回收、pipe EOF、
reader真实join及日志；取消超时后另加15秒。异常先锁存，后续日志/显示/清理失败作为
有限次异常保留。极短预算或OS调用晚回可使结果/日志缺失，整次按失败及未确认处理；
不得延长原D或用仅root退出推定整树关闭。

Windows复用原挂起启动和nested Job，恢复前核成员与原D。受控构建入口仍须先归入
创建期外层Job，覆盖Popen创建到inner Assign的间隔及常规第三方后代；hidden_build
仅确认身处某个Job，具体原Job身份/创建期归属/整树回收由外层控制器实际证据证明。
private_console及已有隐藏控制台继承规则保持，普通第三方后代才能继承隐藏控制台。

本段只覆盖native.run，不给environment/git/toolchain等直接subprocess调用、第三方
自行保存的输出、任意GUI/远程服务或完整进程RSS授予同样额度。工具修改后重新冻结
实际构建输入；既有冻结快照保持原件。必要回归入口为tests/build_pipeline中的
bounded-output/process-job、execution、native-display、native-background及process-startup。

## 共享内存报价目标

`cmake/native/qmt_shm_quotes.cmake`由自有adapters入口注册`GuanhengShmQuotes`。
目标同批编译自有Common、原QmtTickMapping和报价桥，沿锁定原生依赖与MSVC环境。
完成原`native.py configure`后，可执行：

```text
cmake --build <本次已配置目录>/cmake --target GuanhengShmQuotes --parallel 2
```

安装入口将DLL放入app；Python backend与原服务入口从integrations安装。
部署/停止见[报价手册](qmt-shm-quotes.md)。实际产物及SDK资格见
[构建证据](../evidence/2026-10-31-shm-quotes-repository.md)；数据源和未知请求资格分别验收。
