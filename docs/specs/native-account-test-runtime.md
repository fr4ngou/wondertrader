# 原生账户独立测试运行环境

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

状态：accepted。类型：自有测试与安装功能规格；要求前缀ATI。实现属于已授权账户适配和独立安装验收范围。实现、安装、运行资格及生产生效分别登记；动态执行按已授权的受控隐藏验证范围进行。本规格扩展[QAR](qmt-shm-account-read.md)、[NAC](native-account-console.md)及测试目录中的RUNNER-SPEC（外部历史/待归仓路径：`../../tests/integration/qmt_shm_account/scan/RUNNER-SPEC.md`）。

## 目标、根因与范围

让普通 AccountScan EXE、原只读 Trader 插件、认证 Host、真实共享内存和合成三参数 SDK 在可搬迁验证包中形成完整测试链。观衡 App 与 Host 独立安装、构建和发布；测试不能靠裸源码导入或忽略依赖来冒充安装成功。

已核实的当前声明：Host 依赖 pydantic==2.12.5，观衡 App 依赖 pydantic==2.13.4。同一解释器无法同时满足两项精确约束。原 schema2 测试在一个解释器导入两者，缺口由测试装配负责。版本的唯一来源继续为各产品 pyproject 与对应完整锁/发行输入；本规格不另固定一套产品版本。

普通安装的本地包集合由选定角色根项目的project.dependencies与tool.uv.sources共同决定，递归遍历这些本地包的声明依赖；只构建被基础依赖实际引用的闭包，不维护策略名单。角色只固定App/Host入口目录，Host可独立选取。当前支持本地基础依赖的无marker、无extra精确版本声明；registry要求及其marker由uv/pip解释。源映射须位于所给输入根内、名称/版本吻合、每个分发唯一，有界遍历且环只消费一次；冲突或缺少私有来源在构建前拒绝。

冻结旧输入沿其原声明选包：存在uv.lock时，可从其中directory/editable来源补充根项目缺少的本地映射；仍缺映射的旧孤立输入须由调用方通过local_sources按角色显式声明。声明冲突拒绝，sealed原件保持。最终收据固定角色闭包、来源选择、原输入/锁、实际wheel/METADATA/RECORD和模块来源；工具自身与生成输入同样锁定。未选角色与未引用的source声明不进入安装。此规则替代历史固定七App包和九包总表。

账户原生构建的selection通过可选installation_roles声明所需安装角色，installation_extras按角色声明选用的已定义extra；缺少roles时保持原显式文件/目录语义。account_scan.own_files调用普通安装器的纯source_inputs(root, roles, extras=...)，将同一安装闭包、元数据、锁及构建工具输入合入原生/QA源集合，读取原字节时逐项核其SHA，再沿原prepare_inputs双次身份检查冻结。当前配置选择App和Host，移除重复的App/SDK/策略目录名单；新增或退出策略由项目依赖声明驱动。公开接口只读取输入，不运行安装、Git、SDK或子进程。来源路径及快照原有校验保持。旧冻结selection及其原件保持，当前变化形成新构建身份。

调用方通过extras按角色显式选择根项目已声明的optional-dependencies组，默认各角色为空。所选组的本地要求进入同一闭包；public范围、依赖extra和marker交uv解释。带锁角色export传入所选extra，无锁角色把base及所选组的public原要求交uv pip compile。最终普通hash锁的角色根要求使用name[所选extras]==版本，使原安装器实际校验激活的完整依赖。未知组、未选角色、规范化重复及超限拒绝，选择固定在输入、角色本地清单和安装收据。任何可选业务能力均由pyproject拥有，不在安装器登记名称或包名单。

公开source_inputs(root, roles, *, extras=None, local_sources=None)纯读取同一选择与_inputs，返回仓库相对POSIX路径到原字节SHA256的映射；root须绝对Path。外层构建直接复用此输入所有者，取原字节再核摘要；不另维护许可证、模块文件或策略名单。prepare初始输入同样通过此公开接口获取。

根目录、角色入口及source映射在resolve之前，沿调用方词法路径逐级拒绝symlink/reparse；映射保留原路径直到实际选择时再做严格检查，随后才规范化为根内项目。输入读取共用同一路径校验，防止目录别名被提前解析后丢失身份，导致冻结pyproject无法重放。普通无链接源的相同相对输入名称/原字节摘要在新根保持。

影响范围限定自有 tests、native_support、account-scan 构建配置及自有 CMake 测试安装接线。复用[原生能力目录](../development/wondertrader-capabilities.md) WT-T01/T02/T04 的原 Adapter、账户查询及执行边界，保持普通生产编译单元和既有 schema1 CTest。读取和观察复用 QAR 的唯一 DTO、mapper、SHM codec 及严格 IPC 解码。本规格不修改 WT 框架、不新增交易/资金/持仓模型，不改变 Agent 协议或终端运行方式。

## 设计与所有者

App 已安装解释器运行 coordinator，持有 Host fixture Job、native Job 及所有输出 reader。Host 已安装解释器运行测试专用 host_fixture，使用已安装 Host/Agent 的公开 build_runtime、agent_settings、create_server 接口，fixture 主线程独占合成 SDK 和 agent.tick。两者通过原 Host 认证 HTTP 与 SHM 链提供合成值。终端 QMT HTTP 继续退役。

测试夹具的准备与停止沿用既有 fixture_service/http_budget_service 的私有 ready/stop/closed 文件模式，修正原入口的固定仓库路径、原始 Thread 和各自延长关闭期限。该控制仅存在于测试 coordinator 与合成 fixture 之间；真实 QMT Agent、原策略线程和产品通信不读取这些测试文件。

~~~mermaid
flowchart LR
    C[已安装 App coordinator] --> HJ[受管 Host fixture Job]
    C --> NJ[受管 AccountScan Job]
    HJ --> H[已安装 Host 与 Agent]
    H --> S[真实共享内存]
    S --> F[fixture 主线程 合成三参数 SDK]
    NJ --> W[普通 EXE 与原只读插件]
    W --> H
    W --> I[严格 IPC 与逐项 oracle]
    I --> C
~~~

## 生命周期与配置

1. 完整验证输入先准入：原生制品、测试源码、两套 wheelhouse/锁、解释器和已安装模块身份、QA helper。任一不匹配在启动前失败。
2. coordinator 创建从未存在的 UUID 私有工作目录，准备仅属于本次合成 fixture 的配置和凭证；先持有两个 Job 对象及各 reader owner，再启动对应程序。所有受管程序创建时加入 Job，并使用隐藏窗口入口。
3. 在原始总截止内等待本轮 fixture ready。Host 自己启动 HTTP、握手并执行合成 agent.tick；coordinator 不导入 Host/Agent 生产模块。
4. native Job 运行后持续检查两个子树和输出容量。native 退出后，取得真实 root wait、tree=0、所有管道 EOF 与 reader 实际 join，才能将原 bytes 送给 oracle。
5. coordinator 请求 fixture 停止；fixture 依既有 server.request_close → Agent.close → HTTP join → server.close 顺序完成。所有操作取原 parent deadline 剩余量，允许 child 内部更早停止，禁止据此延长 parent 截止。
6. closed marker 仅是 fixture 自报；coordinator 仍须取得 Host root、整树、双管道 EOF/join 的独立证明。异常也尝试关闭全部已持有 owner；未知 owner 保留，不授 closed，不开始下一轮。

原始测试总预算沿当前 runner 的60秒边界，工作截止至多为总截止减去5秒；多 case、就绪、原生工作、oracle、停止和回收共同消费预算。参数必须显式有限；时间值单一来源，不另创建每轮60秒或无限关闭重试。每轮停止预留必须覆盖 Host 现有 I/O 关闭窗口。编译、安装和外层测试进程分别具有显式预算；不能把内层预算当外层父死亡回收证明。

这里的“私有目录”指本轮专用的fresh UUID隔离测试目录及alias/成员/身份边界；目录DACL及抵御同用户篡改的性质尚未验证。

测试私有文件使用精确白名单、版本和 fixture_run_id；仅接受对应 UUID 本轮值。ready/stop/closed 每份最多4096字节，各自产生一次，通过同目录临时文件原子发布；停止轮询服从单截止及固定间隔。消息不携带真实账号或生产凭证。有限 SDK 调用明细进入有限测试结果，不把 marker 作为账户事实或跨轮恢复收据。各 marker 的精确字段由同一 test-only 控制模块定义，双方与纯测试共用，禁止在 Host/App 产品包新增控制端点。

## 要求与验收映射

| ID | 要求 | 验证入口与合格证据 |
|---|---|---|
| ATI-R1 | App 与 Host 使用两套独立普通安装 CPython3.12环境，各自满足完整 Requires-Dist、锁及 pip check；无 --no-deps 或 source overlay | 独立离线安装报告、依赖冲突负向、解释器/site/分发与模块来源收据 |
| ATI-R2 | coordinator 只导入安装的 App；fixture 只导入安装的 Host/Agent，模块来源须在各自 site 内；foreign cwd 下用显式 Python -I -B，依赖包入口不用 -S | 两环境 module.__file__/METADATA/RECORD/文件摘要，原仓库移走或不可见时的搬迁运行 |
| ATI-R3 | 唯一 ThreadOwner 算法仍由 App 的 thread_owner.py 拥有；fixture 使用构建派生 QA helper，记录来源及字节SHA。单次读取有限 helper bytes，校验后从同一 buffer 编译加载；不维护第二份算法或安装残缺 App | helper 生成/单读加载正负向，缺失、超限、替换、摘要冲突、同次bytes绑定 |
| ATI-R4 | 测试 fixture 复用原 Host/Agent 公开能力及合成三参数 SDK；SDK 和 tick 均在 fixture 原主线程；无真实终端、交易或旧工程导入 | 四 datatype 原参数与线程证据、真实 SHM handshake、零写调用 |
| ATI-R5 | Parent 在启动前持有 Host/native Job 和 reader owner；Job 创建期绑定、隐藏窗口；父死亡清理由外层受管 Job 验收 | 创建失败、start 未返回、输出溢出、父异常/死亡、实际 tree/root/EOF/join 证据 |
| ATI-R6 | 所有等待、各 case、读取及关闭沿同一原始 deadline；超时不开始下一轮、不追加独立成功窗口 | fake clock 跨阶段、迟到 ready/closed、预算耗尽与多轮停止定义；实际超时与资源回收另验 |
| ATI-R7 | 私有 fresh 目录与本轮 marker 身份/大小/字段/有限发布受限；旧 marker、重复键、错误身份、超限及坏形状拒绝；关闭 marker 不能代替退出证明 | test-only 控制值单测和完整双进程故障测试 |
| ATI-R8 | 异常仍关闭全部 owner、保留未知依赖，HTTP request_close/Agent close/thread join/server close按已核顺序；任一关闭未知不得成功 | 逐组件关闭异常、BaseException、重复关闭、下一轮拒绝及独立生命周期审查 |
| ATI-R9 | 保留 schema1 资格、schema2 smoke pending 和45项 full qualification 三种范围；exit3 明确未完成，禁止 CTest SKIP_RETURN_CODE 或退出码转换使其变绿 | registry 与 summary纯测试、CMake/打包门禁负向及未来完整45项实际结果 |
| ATI-R10 | 所有45项保留逐项ID、oracle、状态与缺口；函数绑定、JSON存在和合成 smoke 均不证明完成。拒绝、成功及 partial 各沿原 IPC 严格解码，先实际回收再判定 | 原 native-main-cases.json不变、逐case数据/expectation、原 raw IPC、严格反例 |
| ATI-R11 | account-scan input fingerprint 包含 SHM源端完整已登记闭包、选定角色声明的本地发行闭包、构建backend锁、support及全部runner/fixture/helper/cases；原native输入保持固定上游语义 | source manifest与 owned source实际集合、输入变化失配、无旧工程运行依赖 |
| ATI-R12 | 复用既有 Flit backend校验与独立发行所有者，分别生成普通非editable wheels、完整离线wheelhouse/精确锁/摘要清单；完整Host锁缺失时安装不准入 | 缺wheel、缺锁、错版本、错误Requires-Dist/METADATA、额外源码等负向；完整离线安装另验 |
| ATI-R13 | 可搬迁包包含验证源码、QA helper、两套wheelhouse/锁和原生制品/CRT；全部路径相对包root，--owned-root指向包内validation。Python为显式受管前置，不暗带未知解释器 | ZIP成员/摘要/路径准入、foreign cwd、原repo不可见、安装目录身份与运行摘要 |
| ATI-R14 | CMake保留现schema1 CTest；新的schema2仅在完整依赖和运行输入具备时显式启用。未启用显示未验收，不拿legacy green授新来源资格 | profile/CTest清单与门禁单测、新来源独立结果 |
| ATI-R15 | 任何启动链不满足隐藏与创建期绑定前置时停止，运行恢复另按故障处理；静态文件检查不声称弹窗消失 | 启动来源/flags/parent/console证据及现场窗口复验；当前弹窗归属仍unknown |
| ATI-R16 | 测试软件、合成来源、真实SDK、中文业务页与生产切换分别登记；schema2严格准入后接受管owner，实际来源资格以本轮查询及匹配证据确定；未配置或缺少owner明确拒绝 | 模块/证据/current状态一致；真实用户链单独验收 |

## 源码与安装布局

源码本地依赖选择按所声明`==`版本匹配项目支持的规范版本：公开版本pin接纳同公开版本的合法local修订；含local的pin要求完整版本一致。实际源版本、wheel、METADATA、完整组合锁及摘要仍固定到所选发行；运行时依赖准入沿[纯策略身份规范](historical-eod-model.md#hem-r2-原生消费)。不同公开版本、非法修订、私有来源缺失和文件身份变化分别拒绝，原角色隔离及完整普通安装要求保持。

扩展既有 account-scan profile 的 owned source 与 artifact/flow 所有者，复用现有二进制准入、固定源清单、CRT、打包和搬迁校验。测试源码放 validation/tests，QA helper 放 validation/helpers；App 与 Host 的 wheels、锁和安装收据分别放独立角色目录。安装环境与源码验证根分别标识，解释器不能依赖测试进程 cwd 自动挑选。生成helper的来源是本次 input fingerprint 中唯一 App 文件；原件、生成件摘要必须一致。

解释器本身不默认打入 ZIP：已有二进制白名单、发行许可和 Python 基础安装归属保持。验证器必须记录 base executable、venv.cfg、版本/位数、site root、wheel/dist-info/METADATA/Requires-Dist及需要的RECORD身份；任一外部前置缺失标为未具备运行资格。Windows Python3.12为这条新测试链的验收环境，不扩大 Agent3.6.8 或 Host3.10 的兼容证明。

## 验证、交付及回滚

实施按测试双进程装配、安装闭包、可搬迁门禁三个互相接线的切片推进。每个切片先核静态完整链和反例，再执行其适用动态验证；不同资格不可互相替代。首次涉及安装角色和生命周期变化需 full 独立审查；后继局部修订按实际影响范围审查。自有实现按已授权范围开发，受控隐藏动态验证以主路径为先，完整安装及场景资格独立记录。

回滚恢复明确的自有文件清单和制品身份，保留原schema1入口、历史证据、已有数据及产品依赖。无需终端重启、生产部署或账户操作。新增 fixture marker 仅是隔离测试临时资料，清理仍遵从已授权的测试根边界。

## 待核实与实际边界

完整 Host 锁/离线 wheels、独立解释器与安装收据、Windows隐藏启动行为、实际Job/线程回收和45项原生场景均需后续证据。源码中的现成 marker 模式提供可复用接缝，其旧固定路径、线程及预算代码不可原样复制。本规格定义的目标仍为完整账户只读链及整体验收；先完成静态切片不会将目标缩成smoke。

已核源码和安装缺口见静态闭包报告（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-native-install-closure-audit-001/REPORT.md`）。该报告覆盖124份来源/138原件，动态执行为0，提供设计依据而非安装通过证据。
