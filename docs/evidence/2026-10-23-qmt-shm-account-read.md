# 2026-10-23 QMT共享内存账户只读接入

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发证据。状态：in-progress；当前阶段只做静态读写，新候选尚未运行验收。

## 要求与范围

[QAR唯一规格](../specs/qmt-shm-account-read.md)与[ADR-0006](../architecture/adr/0006-account-read-source-boundary.md)已登记。复用原TraderAdapter四查询、只读插件owner和账户Scan；账户字段采用唯一mapper，通用observation=null及原三B/Journal保持。新v3显式能力可组合行情、历史、账户，来源身份与券商登录分别表达；订单/撤单保持不可用。

## 当前实施

自有能力registry新增account.trade_detail、固定policy及显式v3版本选择，旧v1/v2默认选择保留；原生客户端、映射与公开消费者尚待接线。纯配置/原线程固定SDK调用模块与回归定义正在分工编写。

新候选版本Agent 0.1.0a3／Host 0.1.0a4，Host明确依赖同版Agent；仅更改源码声明，没有构建、安装或启动。归档旧a2/a3资格保持其原来源，不授本候选运行通过。

共享合成fixture为tests/fixtures/qmt_shm_account/contracts.json；完整v3 profile为1127字节，原canonical SHA f7dd39e5d14dbb8b58e553631edb20269cadd60b885870f0d406892a4c084378。样本区分137/19持仓、200/37/163订单、原成交金额与价格乘量、账户总资产/可用/冻结现金。fixture是输入与期望定义，尚未用Python/C++运行。

## 静态核对与运行边界

根任务仅用Node文件API核对六份文档的79个本地链接，均存在；这项检查只证明该清单链接可达，未运行project.py check或Python语法/测试。记录位于build/guanheng-workspace/qmt-shm-account-implementation-001/static-doc-links.json。

用户再次报告弹窗后，本阶段停止所有新编译、测试及浏览器启动；根任务和本轮子任务只读写文件，不运行网络、终端或SDK。既有编译句柄39960已确认exit0，子任务上一轮均已结束；新子任务仅承担静态实现/审查。现场弹窗具体程序仍未逐窗口识别，已验隐藏启动范围不等于任意窗口来源已解决。

两处股票helper框架文件保持原摘要，见同目录framework-freeze.json；[最小修正](../migration/native-stock-metadata-ownership-proposal.md)仍待用户实际批准。新账户适配均在自有模块中实施。

## 后续验收

完成纯模块与接线后冻结完整源码、更新来源清单并独立full静态审查；动态运行恢复前先核隐藏及实际进程回收入口。后续逐层验证独立安装Agent/Host、C++账户客户端、原Adapter/Scan、业务HTTP和中文页。真实SDK函数/字段/单位/账户范围/缓存/登录与生产切换分别待验。旧QMT工程只作静态参考，退役终端HTTP不恢复。

## 后继：Python候选与方案独审

Agent a3／Host a4的账户data模块、纯ReadConfiguration、原线程固定callable注入和同finalizer截止已写入源码；三文件合计46个测试方法定义，另补完整配对核验与跨I/O凭证一致性的6项定义，全部未执行。新模块不读旧工程、不开放写调用。44项当前连接包来源摘要已逐项核对，差异0；完整55文件初候选身份见build/guanheng-workspace/qmt-shm-account-implementation-001/candidate-source-hashes.json。

最终方案独立full（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-spec-review-001/REPORT.md`）为complete-static-spec、gap0，根任务逐项核55份原件及manifest，差异0。该结论只授规格完整性与接口可实施性，不授产品运行。后继Python独立full静态审查正在进行，已发现verify_pair尾部残留假Agent构造及create_pair凭证别名跨文件I/O漂移，候选保持冻结待完整报告后修复；未构建/安装新候选，运行实例保持。

C++账户客户端及共用金融mapper提取已分配到自有模块，仍仅静态读写；Core完整v3/profile与固定operation校验分开，旧HTTP金融循环只保留一个实现。原生编译、完整Scan/v3观察/业务DTO2.0/页面接线、独立安装和实际SDK均未完成。两处股票框架修改仍待实际用户批准，不能从目标自动继续推导批准。

## 后继：两项Python静态修正闭合与原生候选

Python静态delta（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-python-static-delta-001/REPORT.md`）已给complete-static-closure，F1/F2静态闭合、新增gap0；根任务逐项核74份原件，差异0。verify_pair已使用纯配置validator，pair/launch/runtime入口统一捕获私有凭证标量快照；新增6项完整核验/别名回归定义。修正后56文件身份在candidate-source-hashes-fixed.json，52项新账户测试加原9项受影响历史定义共61方法，实际执行仍0。

C++新AccountClient、Core完整v3/原data跨度、明确旧版本默认及金融mapper已写成候选，字段表移到Common纯头，金融循环/helpers按归一换行逐字保持。自有CMake、旧fixture编译清单和CNG探针已指向实际共享mapper；没有运行配置/编译。完整38文件冻结输入见candidate-native-source-hashes.json，独立full静态审查进行中，已发现新v3握手后过度声明DevelopmentVerified，待完整报告后修正。新SHM→金融mapper薄门面另写新文件，现ReadOnlyTrader/Scan/UI仍未接通，不能据客户端存在报告账户链完成。

各Native负向/映射case JSON分别28/16项，仅定义，runner未完成。旧CNG的source-build模式后继需要包含当前AccountMapping的匹配源快照；旧冻结probe/报告不重写、不混用。旧构建helper的进程入口未恢复运行，新动态活动继续为0。两处股票框架文件仍保持原摘要，用户批准仍待实际回复。

## 后继：原生full静态核证与资格修正

原生full静态审查（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-native-static-review-001/REPORT.md`）已封存，唯一gap为QAR-NATIVE-F1/P2：新v3仅凭prepare就提高资格。根任务核67份原件及38份修改前当前输入，差异0；报告结论保持gap，未以候选修正回写原报告。自有Core现在区分协议支持与验收资格，三个v3操作保持supported=true、qualification=Unavailable；旧v1/v2准备结果保持。五组资格回归只完成定义，尚无执行runner或运行结果。

新增ShmAccountMapping只接同次Core成功采用值，核固定账户/阶段与原请求、结果、绑定metadata后调用唯一金融mapper(version3)；源码与15项合成定义已冻结。修正及薄接线共41项输入见build/guanheng-workspace/qmt-shm-account-native-fix-001/candidate-source-hashes.json，独立静态delta进行中；完整ReadOnlyTrader/Scan/DTO2.0/中文页、收据私有持久owner和新安装均仍未完成。没有新编译、测试、网络、浏览器或SDK执行。

## 后继：原生资格静态修正闭合

独立静态delta及薄接线full子审（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-native-static-delta-001/REPORT.md`）为complete-static-closure-and-thin-seam，QAR-NATIVE-F1闭合、新增gap0。根任务核57份原件及41份当前输入，差异0；Core除capability函数外的归一换行全文保持，旧v1/v2返回保持。28原生负向、5资格、16金融映射和15薄接线组共64组仅完成定义，实际执行0。该静态闭合不提高新v3运行资格。

| 要求 | 当前可核事实 | 尚需完成 |
|---|---|---|
| QAR-R1 | Python profile/纯配置与C++ v3准入候选静态闭合 | 黄金bytes/同fixture/安装及实际运行 |
| QAR-R2 | 固定三参数SDK callable与原线程finalizer源码已写 | 获准载入后核实际SDK函数/字段/单位/缓存 |
| QAR-R3 | 有界七字段data与原data片段校验源码已写 | 全边界及异常实际回归 |
| QAR-R4 | 唯一金融mapper提取和新SHM薄接线静态闭合 | 原Adapter整批交付及金融断言运行 |
| QAR-R5 | Core原receipt/token/单次POST/GET恢复路径复用 | Scan私有目录/根锁/额度与持久收据实际接线 |
| QAR-R6 | 新扫描配置纯准入实施中 | 受管Job、ReadOnlyTrader分支、inspection3/IPC2/DTO2.0及中文页 |
| QAR-R7 | 候选身份与静态审查原件封存 | 编译、独立安装/搬迁、旧树缺席和真实用户入口验收 |

本阶段继续仅Node文件读写。已核旧账户父进程目前为普通Popen；现有strategy_job.ProcessJob具创建时JobList接缝，后继应复用并核同一总截止/父死亡/管道排空。现历史Store已有独占临时写入、flush及原子发布机制；账户收据只借用对应持久化职责，不引入历史分页/结果存储。依据见build/guanheng-workspace/qmt-shm-account-native-fix-001/next-owner-reuse-boundary.json。

## 后继：配置静态闭合及原生扫描候选

新AccountScanConfig/schema2纯准入与双入口启动前拒绝已完成源码。独立full发现QAR-SCAN-CONFIG-F1/P2：先读调用方版本再复制可能形成混版私有树，绕过未接通拒绝。已在唯一配置owner改为先复制、再从同一私有树取精确版本和来源；独立静态delta（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-scan-config-static-delta-001/REPORT.md`）为complete-static-delta，全部28项影响复核、gap0、5项运行相关unknown。根任务核23原件及13当前输入，差异0；新配置20测试函数均未执行。

ReadOnlyTrader新qmt_shm_bound分支、AccountReceiptStore以及原生Scan schema2/inspection3/IPC2已写成未编译候选。新目录先原子持久收据再提交，旧receipt/temp只允许恢复原UUID；恢复始终不授当前快照。runtime_*三字段来自原生内存装配，其中runtime_deadline_ns保留原started+total_ms同进程绝对期限。目录实际句柄、128位文件身份及私有DACL边界已写为RecoveryBoundary，独立full静态审查进行中；Store路径上限与构造截止按原契约收敛中，组合尚未封存送审。

自有AccountScan目标显式增加advapi32及Windows8+完整FileIdInfo API声明，原WT/Nqp目标未改；新增源已由独立owned目录规则选中，QAR规格与静态定义也登记进输入身份。没有新可执行CTest运行器或运行通过记录，旧测试不得据此授新SHM资格。Python父端仍在Thread/Popen前拒绝新配置，根锁/累计额度/创建时Job、DTO2.0/中文页、新安装及真实SDK/字段/单位均未完成。旧运行实例与退役终端HTTP保持，整体目标active。


## 后继：只读账户状态必要性纠偏

必要性静态审计（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-receipt-necessity-audit-001/AUDIT.md`）已封存；根任务核36份原件及31份当前源码，摘要/字节差异0，并直接复核固定三参读取、Core move-only一次提交/原ID GET、插件四阶段/写拒绝、原Adapter使用边界及每轮新实例。作者曾实现目录边界，因此此项标为必要性自查及根复核，不冒充不同作者产品full。

结论：客户端磁盘receipt能找回死进程旧查询，但当前页面没有该需求，恢复结果本身也不授当前观察。账户读取无写副作用；新轮新Adapter可隔离前轮初始化统计。此前将客户端跨进程收据、私有恢复根及累计配额设为必需项属于过度设计。根任务已更新QAR-R5/R6并登记[ADR-0007](../architecture/adr/0007-account-observation-read-state.md)：活进程保留原ID核查，死进程后旧轮失败，实际回收后由明确刷新创建新观察；Host原Journal/容量、认证/三B、唯一金融mapper、一次SPI、总截止和Job回收保持。历史分页导出和真实交易未知结果职责保持独立。

新schema2目标为六顶层字段，不接收recovery或receipt-directory；旧七字段候选按额外键拒绝，不自动降级。当前代码仍有未编译的Store/Boundary及七字段配置，需要后继按新契约清理并重新冻结审查，当前新来源启动前不可用继续保持。既有静态报告仅对封存输入有效；本次文档变化不借用旧报告授新实现资格。原生main独立静态审查另有两个P2：父截止未贯穿装载/发布；输出异常可重发帧及失实关闭声明，需在自有宿主中按唯一deadline/输出出口修正。

本阶段全部子任务确认零新进程、编译、测试、Python/import、网络、浏览器或SDK；只读写文件。用户实际弹窗尚无窗口/PID对应证据，原已结束构建句柄不证明所有本机窗口来源。部署/运行/真实SDK与完整迁入仍未完成。文档纠偏前后原件、根核记录和后继实施清单位于build/guanheng-workspace/qmt-shm-account-read-state-correction-001。


## 后继：只读状态收敛、公开版本与自有宿主静态审查

ADR0007契约独立静态full（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-read-state-contract-static-review-001/REPORT.md`）无实质缺口；根核48份原件。插件已移除AccountReceiptStore及recovery-only，只沿Core prepare/create/submit_once与活进程原ID核查；Store两个自有源码已在核对普通文件、工作区真实路径、前后SHA和before副本后退役。HostJournal、历史导出恢复和真实交易边界保持。原生Scan的RecoveryBoundary/收据CLI/额外API依赖亦已退出，未删除业务文件或旧证据。

公开模型/纯配置独立full（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-public-config-static-review-001/REPORT.md`）为complete-static-full：31项中27 complete、0 gap、4 unknown；根核34原件与22当前输入。新增独立DTO2/SHM source和inspection3投影保留原金融循环及旧DTO1形状；六字段配置保留copy-before-version，父两处启动前guard返回显式DTO2不可用，HTTP按schema判别联合。20配置与13投影测试函数仅定义，全部未执行。父Job/IPC2运行仍未接通或验证；后继父端候选变更不直接复用该报告的完整输入身份。

自有main已统一原started Deadline和FrameWriter最终出口。第一次full发现输出三次I/O之间缺截止检查、summary成功判定缺类型准入；已在唯一输出owner逐次检查并保留broken，observation先准入qualified/failure/code。独立静态delta（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-native-main-read-state-static-delta-001/REPORT.md`）关闭两项、无新增实质gap；根核5原件及19当前输入差异0。38原生场景只定义，0执行。该修改均位于GuanhengAccountScan及自有构建/测试，不改WT框架，不授原生运行资格。

新DTO2中文页保留/account及/orders共用组件、50行分页及明确刷新。第一次full发现路由字符域收窄和capability停用仍展示cache两项P2，已分别恢复生产者Unicode标量域、在唯一显示派生值加入availability准入；新增两版/两路由的停用与预缓存禁用挂载定义。UI静态delta（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-console-v2-static-delta-001/REPORT.md`）已关闭两项、无新增实质gap；尚待根核原件，类型/组件/浏览器全部未执行。

插件独立full（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-plugin-read-state-static-review-001/REPORT.md`）覆盖38项，32静态complete、1gap、5unknown。唯一P2是保留旧build.py漏新SHM/Core定义，固定生产CMake闭包完整。后继候选已补足11个当前定义，并使两旧脚本的Git/编译器/probe入口使用原样后台选项；编译诊断复用原样编码安全display。29场景定义0运行，独立delta进行中。旧harness不进入安装ZIP，本轮未恢复执行；这些静态修订不证明用户实际弹窗已解决。

受管父端正复用既有ProcessJob创建时JobList/NO_WINDOW、close_job/wait/close_reaped及原总体截止，采用总预算内的有限回收预留；配置仅使用只读pin，不建收据目录/根锁/累计配额。等待未知或读取线程未退出须保留owner并阻止新轮，新来源runtime_available继续False。该部分尚未封存和独审，不授任何进程回收/用户入口资格。

全部新编译、测试、Python/import、浏览器、网络、SDK和进程启动继续为0。另已静态核Windows既存WER报告，仍未取得本次窗口/PID对应，详见[窗口记录](2026-10-23-background-process-windows.md)。新安装、真实账户字段/单位/权限/缓存及整个观衡迁入均未完成，整体目标active。


## 后继：插件构建入口与页面静态复核收口

插件构建闭包独立delta（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-plugin-build-closure-static-delta-001/REPORT.md`）关闭旧build.py漏列源码F1；49项中42静态complete、7运行unknown，未发现新增阻断gap。根任务逐项核67份原件及52份当前输入，差异0。随后仅将插件README中的场景数28校正为29，保留修改前副本及文档后继身份；没有重写独立封存结论。两个旧脚本继续停用，没有实际链接或窗口验证。

页面独立delta（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-console-v2-static-delta-001/REPORT.md`）关闭Unicode路由域及停用后缓存显示两项。根核5份封存原件及22当前输入，差异0；源码、测试定义及对应规范身份一致。类型、组件和浏览器均未运行，不授页面安装或真实HTTP链通过。

受管账户父端仍在静态封存，独立full随后开展，新来源runtime_available保持False。全部进程启动、编译、Python/import、测试、浏览器、网络及SDK继续为0；用户实际弹窗来源保持未确认。正式安装、真实来源和整体观衡迁入保持未完成。


## 后继：受管父端full发现与集中根因修正

父端独立full（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-parent-job-static-review-001/REPORT.md`）完成32项矩阵：23静态complete、4P2 gap、5运行unknown。根核39份封存原件及20当前输入，差异0。缺口是外层Thread.start失败后的未启动线程join、关闭前成员快照不足整树证明、CreateProcess晚回仍Resume、CloseHandle未核BOOL便清引用。schema1原runner区间逐字相同，31父端函数全部未执行。

Windows独立子审（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-parent-win32-static-review-001/REPORT.md`）的5封存原件已根核；除重叠的晚Resume和关闭句柄外，定位词法pin不能绑定重解析目标链到native实际读取body的身份边界。两份报告对竞态分别登记静态证明缺口与未验Win32条件，原结论保留，没有宣称实际发现残留进程。

依据QAR与ADR0007后继约束，root已改自有native入口：schema2增加每child私有--config-sha256，先对同一次read_config body核SHA再parse/装载；旧schema1维持五参数且拒新摘要。原制品文件SHA和body核验共用同一CNG RAII owner。45场景仅定义，尚无执行runner；19输入已冻结送独立原生握手full（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-parent-root-fix-001/native-review-inputs.json`），结果待封存，不借旧native报告授新源资格。

账户父端撤祖先递归pin、外层启动失败收敛，与中央Job同期限/真实活跃数归零/逐句柄关闭及原strategy_host消费者适配分别在staged编写，尚未合入live。此处修正的是观衡自有进程管理，不修改WT框架。新来源guard保持False。所有动态活动继续0；安装、真实SDK及全系统迁入仍未完成，目标active。

## 线程全调用链候选与静态审查输入（后继003）

根核整合full的66份原件、补充22份原件及35项当前来源相符。原整合报告中的两项P2仍以报告原身份保留；其发现为启动发布窗口及Host在root退出后阻塞整树wait暂停后代守卫。补审确认账户双reader及Host排空/续核同受线程证明边界影响。BacktestWorkspace原_active和completed已阻止未知启动换轮，其标准join规则在本候选统一；读取池另有构造部分启动及应用try前失败收尾缺口。

自有root-fix-003共20项候选已封存，review-inputs.json SHA `38b3995ca713c555d79e2ddebcc96f6cb3a76fd4ebe7f8705ed30450cf4e419c`，包含56项最终来源及本机CPython3.14 threading原件。候选统一ThreadOwner，保留业务Future/completed/取消事实，读取池先发布owner再启动，Host保持原截止及整树归零前持续守卫。独立full静态审查进行中，候选尚未apply。

本阶段只进行既有Node运行时的文件读取、摘要、候选写入及静态Agent审查。进程、Python/import、编译、测试、网络、SDK和浏览器执行全部0；测试为定义，不授语法/行为或安装资格。旧run_account_scan函数原文、新schema2启动前guardFalse、WT框架批准边界均保持。具体弹窗仍unknown，关联[故障记录](../incidents/2026-10-23-repeated-windows.md)。整体迁入继续active；历史真实覆盖、原执行器正式绑定、同版安装及真实用户调用链仍未完成。

## ThreadOwner完整静态结果及F1/F2后继004

003独立full：53要求=43 complete、3 gap、7 unknown；88制品逐项根核一致，实际manifest SHA `fa340430ea68a2dbf324312cd3afd4d6157935564643886fb0281daf7168eebf`，报告SHA `ca6c3892831cf0990b217f800616c0e4e943d56d1178783de1f2e63481e75ab6`。原未发布线程窗口和Host后代守卫在该冻结源码中静态闭合；三条gap归两个P2：账户能力声明与实际guard矛盾，应用/读取池关闭异常跳过后继owner。支持版本、异步异常、OS/Job/原DLL、安装、HTTP/UI及真实SDK继续unknown。

004保留003全部原件，另在新候选修正F1/F2。账户capability使用同一runtime_available/SHM_CONFIG_UNAVAILABLE；应用逐组件续核并保留原生命周期异常及私有关闭错误；读取队列锁外执行取消回调，逐项保出队计数，全部线程同截止续核后传播原控制异常或标准异常组。新四个具名测试函数含参数化定义，无执行。

004 review-inputs.json SHA `4ea75abb42f4bc2816054d561bbc38dff04b3d8b9425f1e9120891d840015329`；58最终来源、22候选、6项相对003变化、2个本机stdlib身份。独立审查按关闭错误/生命周期细化的full受影响范围及原53项整体影响核对，不以四项测试定义替代原矩阵。候选尚未apply，原58来源冻结。新进程、测试/import、编译、网络/SDK及浏览器执行0，guardFalse，框架和旧QMT工程保持。

## 004独审静态闭合及按身份写入源码

后继完整静态复核61项=54 complete、0 gap、7 unknown；F1/F2静态闭合，无新增gap。实际artifact-manifest SHA `c3bbb974f4c37e3a29c458acd012a0aef1156edcdf579cba14f81e55ef3188fd`，77份制品已根核；报告SHA `10942b9200bd5fc74607228a8d6fd23ed5fb61e57ae8a0b512631090429fcdb6`。58最终来源、22候选、2 stdlib身份保持，52项与003相同的来源按实际影响reuse，原53项及关闭错误契约新增要求均有完整判定。148个具名函数和14个新增参数化case均为定义，执行0。

22项自有源码/测试/规格按004冻结清单写入live，原文件先核before-live摘要，写后58来源逐项匹配独审快照。apply记录SHA `1e9ed4e43b429f11be6eb18e6000618c2e2c0d25fd05da19496715afd8356d78`；post-apply静态记录SHA `7d673c11ad0b70ac91f75f595e99098f492b0d2d2931379ab3f1f73e3a6dc993`。helper先写入，全部修改限apps/docs/tests；两处未批股票helper及native main保持原摘要。旧HTTP直接run函数保持原文，未增加退役通道能力。

本轮未构建、安装、发布、重启或进行真实账户操作；所有新进程、Python/import、测试、网络/SDK和浏览器执行0。schema2 guardFalse，软件源码与实际运行验收分别登记。原七类unknown继续：支持版本/异步异常、真实Job/EOF/SDK、Host真实后代/原DLL、业务HTTP/UI、测试导入执行、wheel/安装平台、真实来源/RT/生产/交易。整体目标active，尚未完整交付。

## 自动化入口缺口及后继配置候选

入口静态调查确认新生命周期十个测试文件未接入现CI/CTest/构建suite；源码存在只代表待收集对象。原workflow未对apps/guanheng变更触发，也未准备pytest/app开发依赖。调查报告SHA `49cca449236cedd33c24ce287bfd5f79d62f88922d80d24995e7ec9b5c27b5f9`，来源与结果保存在qmt-shm-account-test-entry-audit-001。

新test-entry-fix-002冻结3项候选：workflow、应用README、测试手册。独立Windows Python3.12/3.14 job按既有flit URL/SHA与uv.lock版本约束准备全部本仓包，七组明确pytest选择涉及18个test_*.py，JUnit/临时目录独占；可手动选择python-lifecycle，仅跑Python回归。两个原native job正文保持原字节；没有改锁、包metadata、生产发布或QMT实例。test_process_information涉及真实自建Python进程/Win32句柄；native_chain缺显式安装输入的默认skip不授原生资格。

CI review-inputs.json SHA `51123e307d340e79773b666aeb8a3a8f819f6d7a2d971bed96c6039eadc79a42`，71最终来源、3候选，独立静态full进行中。新workflow SHA `2ce8994508abbfd6dcd61f07cc011d9b8066bb0ad02fed445e6bb51e90eb659d`，尚未apply或触发CI。YAML/依赖安装、pytest收集与执行均未进行；源配置、实际CI、原生安装、真实来源及生产资格分别登记。此前22产品源码已apply及58来源根核事实保持，guardFalse。


## schema2原生测试执行登记核查及CI路径候选

限定构建、CTest、搬迁与测试消费者的静态调查确认：`native-main-cases.json`的45项定义目前直接执行登记0/45；现account-scan CTest及包搬迁仍调用schema1/inspection2/IPC1 runner。复制场景JSON不形成执行器。实际矩阵为19项黑盒配置/SHM链、8项合成inspection插件契约、18项需确定故障/clock/I-O接缝。此分类描述待实现接线，未执行任何场景。

调查见原件报告（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-native-cases-audit-001/REPORT.md`），manifest SHA `620e1ba3440761f54d1063cbd8bcee6475469c30b2a7f2af4026c7162d5a0958`；根核17来源副本/live与3输出全部一致，45项id逐项同序对应。账户模块文档已按协议版本纠正入口覆盖。后继schema2 runner只在独占build/staged编写，复用现Host/Agent/SHM和三参SDK、受管Job及有界reader；原生产main、WT框架和旧QMT工程保持。当前运行guardFalse，尚未取得新安装或原生链运行资格。

CI另封存test-entry-fix-003：相对002仅将job级结果路径从runner.temp改为checkout相对build/ci-python-lifecycle，避免该层runner上下文依赖；71来源、3候选，68未修改上下文与live相同，review-inputs SHA `91f28cc30d46f9ff76b083664beb227a5d1083c0642d264b16d62030ed5f6939`，workflow SHA `7ca16cc1cb0b20663a97a6c967d842fdf896818b61b18fe4c824bf3d1118b9ee`。002独立full及后继delta尚待结果，不修改其冻结输入；GitHub实际定义接受、YAML/安装/pytest仍unknown。旧source手动CI入口与当前静态参考边界另在核查，暂不授正式交付依赖。

所有新进程、Python/import、测试、编译、网络/SDK和浏览器执行继续0；用户弹窗的窗口/PID及触发链仍未确认，运行验证继续暂停。整体目标active，尚未完整交付。


## 旧来源CI退役审查及空来源准入根因

002生命周期CI完整静审为32项=25 complete/0已确认gap/7 unknown；96制品已根核。003相对路径delta为原32项=26 complete/0产品gap/6 unknown；83制品已根核，保留平台/运行unknown。003输入继承的旧apply谱系字段未用于应用；后继输入已统一为当前files/apply，旧输入保留不回写。

旧来源调用审计根核55原件/52来源，确认手动fixed job会导入旧QMT Core/Journal；默认native无外源时使用本仓替身，旧oracle明确skip/unavailable。删除fixed job/input并清空两个专用GH_*选择器可封闭受支持CI路径，共享账户CMake/helper继续保留；本地显式历史CLI源码仍存在，文档按退役范围说明，不宣称技术删除。审计manifest SHA `e28b94c9256eac06dcb97435b1ffa9995a0ee76cab5f017be5d6ef2215f98e94`。

004独立full为46条=37 complete/2 gap/7 unknown，135制品已根核，两个gap同一P2 CI-RETIREMENT-F1：自有HTTP测试参数default读取空环境字符串，argparse执行Path转换后可能选择当前目录，再进入load_original。已核本机CPython314 argparse默认值转换及pathlib空值显示源码；未运行Python/CTest/CI，不声称已观察Windows保留空变量或实际旧源导入。004报告SHA `9c241279c4005acabf250caf60bb8cdc2ff87c8704b85b185ba6873821efa5fb`、manifest SHA `14c7ab1eeef44bb7f4aa7933ba4d614a280b0d439ffe56d1f3454c6fea9734a9`，原报告和114输入保持。

005在新staged集中修正：两自有测试入口的空环境值保留None，显式空白来源按ArgumentTypeError拒绝；纯parse_arguments保留probe及unittest参数语义。新增标准库六函数定义覆盖两入口；默认native的unittest discover会登记build_pipeline新文件，未运行。GBW-R7补充空源准入。005共115来源/10候选/2本机stdlib，review-inputs SHA `075cd85e90f06cbd3f15b2b9f39d76591a96bfea93b1d0ca47b384ffc85ae3a6`；独立复核进行中，尚未apply。

## 新schema2原生烟测候选的独立full

新候选仅为测试层run_schema2/45项registry/最终测试契约；普通插件→Host→真实SHM→合成固定三参SDK链只已定义。独立审查42来源/53制品已根核，结论gap2：F1遗漏completion worker_live/queued/error_code/elapsed及summary.failure.code等成功事实，F2复用旧裸JSON decoder不能拒重复键和NaN/Infinity。原始变体为静态定义，observed_exit=null，未执行。报告SHA `0419317503e9471de4d4f50e3b32e8e0ba9e2c0d22b6eaf6bc576d2b42814d69`、manifest SHA `545d69ea80f27bcf07c8d9dcbbb18513caa61f51ced956f26667cbe7a00afa7a`。45项pending/成功返回3仍不授full资格的范围准确；后继002独占候选修根因，live、生产main、原JSON及框架保持。

全程仅现有Node文件API、摘要和静态Agent协作；新进程、import、编译、测试、网络/SDK及浏览器0。弹窗来源未知，运行验证继续暂停；新来源guardFalse。整体迁入目标active，仍需同版安装、实际回归/原生链、真实源与用户入口验收。


## 005静态闭合并按同身份写入源码

独立复核（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-test-entry-static-review-004/REPORT.md`）为56项=48 complete/0 gap/8 unknown，CI-RETIREMENT-F1静态关闭；140制品已逐SHA/字节根核，报告SHA `5abd44ec66376220bfbb920faab91f9dfa1cde74bfad79d4124f7da32025e197`，manifest SHA `e368ef8b9de22188bd4a0d86f00fe4ccbd9be475726294da6b8024c565474cfd`。旧004矩阵局部沿用71/3措辞已在新复核独立澄清为旧谱系文字；实际004114/6和005115/10输入/报告/原件保持，不改旧封存。

10项自有CI/测试/规格/手册按005唯一清单写入live，逐项写前身份和before-live副本保存；写后115来源全部与独审快照一致。apply SHA `0320e744544298a86b427b4e3fce70069e4240624c6c5ef52abe60e902b70fc4`，post-apply SHA `e856e47776ab2158f1b5541f01cdd338080ede17f3314afaa3da7b913590b6c6`。清理的是旧源码执行CI路线和自有测试准入，不改变HTTP运输或延长终端HTTP路线。默认native任务正文保持，Python生命周期配置按同源写入；未commit/push/派发CI/部署。

八项unknown继续：安装/索引解析；18生命周期目标及新六定义的实际收集/import/断言；实际窗口/回收；GitHub接受/事件/矩阵；支持版本/异步异常；原生/SDK/账户/生产；Windows/CTest空环境实际传递；新语法/运行。所有新进程、Python/import、测试、编译、网络/SDK及浏览器0，弹窗来源仍未确认，新来源guardFalse。框架批准边界和旧QMT工程保持。

后继原生runner002已封存50来源/8新增测试层候选，唯一严格JSON/观察/完成准入及F1/F2回归只完成定义；独立full受影响复核进行中。root-review-package入口SHA `5aec96ba90e22acbc4bf2a1439e3c236bc7612d4826da5416dbd9e8a6b06e8d1`。当前CI005不包含该尚未apply的新增pure回归；后续同版纳入调度，不把源码存在当已调度。45原生case全pending，原生产main、原场景JSON和WT框架没有因本轮修改。整体迁入继续active，完整验收未完成。


## 后继：Native002与CI006落地、双环境安装缺口

本次仅使用既有Node运行时读写文件、核对摘要和静态源码。新程序、Python/import、编译、测试、SDK/网络和浏览器执行均为0。用户已明确反复窗口为“黑色命令行窗口一闪而过”；该描述已写入[故障记录](../incidents/2026-10-23-repeated-windows.md)，实际进程/触发链仍unknown，运行验证继续暂停。

Native002的8份自有测试新增文件已写入源码，50份来源post-apply逐项匹配；应用记录（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-native-runner-fix-002/applied.json`）SHA 4aa96dc093f9b3cd0b38d652e5f706cf3833a4373e0b65604367f3a57726f5a8。独立静态review002的65项原件根核一致，report SHA 23de0494bbde2067640327f52521111ca305365db1b3a2d04098c853db93a724，manifest SHA 033a5a17b16b581a00b1247e2a7f1dea2cb7fe7ef76ade08b16d1263c26da810。限定结论为严格IPC/关闭判据F1/F2静态关闭；45项原生场景没有执行，smoke退出3保留未完成语义。

CI006的3份自有文件已写入，应用记录（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-test-entry-fix-006/applied.json`）SHA e078ca7c7a22291d170fa4c577a81d2134017960bab6f72c9253edf75566d652；123份来源post-apply匹配。独立review005覆盖66要求：57 complete/0 gap/9 unknown，149原件根核一致；report SHA 4daa74134812ff586c43be2a2d3799f8f0407c2563b6690648958a315b5f62c0，manifest SHA c8eb600a6deb37aab418d6b3fd1b159f97a4e22834bd3ebf22cb2b651646bbbf。生命周期CI现有8 selectors/19测试文件，其中新账户IPC只为纯值测试；配置落地没有触发CI。原生、Host、SDK和实际整链资格继续未授。

安装闭包审计（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-native-install-closure-audit-001/REPORT.md`）的138原件已由根逐项核SHA/大小，无差异。report SHA d5fb700e2d45ca4f34f7ae206d524be5adb34bca592beb4ddaca61b216927a4e，manifest SHA e8e0925321daa5ab9451ab8ac016ae66de89257c2266ca7395466f18a9a7e437。确认原schema2测试在同一解释器导入Host/App，而两者Pydantic分别精确依赖2.12.5和2.13.4，完整安装约束不相容。该缺口属于测试装配；它不证明两产品独立安装分别失败。完整源清单、双角色wheel/锁/site身份、搬迁与原生资格门禁仍缺接线。

已写[ATI规格](../specs/native-account-test-runtime.md)，16要求，初版SHA 5cdb3f213032b72620837a82e572c1af487358142dd1599e1ab6de56f88053ba：两套独立安装环境、App coordinator与Host fixture两个Job、同原截止、唯一ThreadOwner QA字节派生、私有本轮marker、实际tree/root/EOF/join、可搬迁包及分层资格。产品版本/协议与WT框架保持。后继004双进程测试和源清单闭包001分文件所有权实施，均只在新staged目录；完整安装和运行待后继验收。

Native003候选保留45ID，19黑盒函数绑定中只有2项implemented-unverified，43项仍pending。它尚未应用，独立full进行中；函数存在不授45项完成。schema2 runtime_available仍关闭。两处股票元数据helper未获实施批准，原框架文件保持原样；不采用这两个单元可继续独立适配，启用前必须解决已证实引用失配并验完整生命周期。整体观衡迁入目标继续active。


## 后继：Native003逐项测试登记落地

独立full静态审查003（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-native-runner-static-review-003/REVIEW.md`）已封存，结论complete-static-only，无新P1/P2。report SHA 797f701f17526c4a3b39df2b04bd93ae1ebf01853a4d2144042fff79b4e843a5；manifest SHA 8083c3bc3a15448028e115b30fa131af8fb66b6b16aa20de79bb646447bd45cd，72原件已根逐项核SHA/长度无差异。58主源加7精确公开依赖65来源前后无漂移；实际9项自有测试变化已应用，58主源post匹配，应用记录SHA ee47e7cb2492abffca5e00cc0c6c84f9ee5f97f06bb8a2adf6b15bf83054f73f。003冻结材料中的live未改描述属于制作/审查时点，后继本段登记写入动作，原冻结报告不回写。

新增三类oracle分别处理成功、配置拒绝和partial；收集非零原生退出仍需actual root/tree/EOF/join后才判定。原45项ID与expected完整保留，19函数绑定、2项implemented-unverified、43pending，任何case不得授full_45_qualified。新增6个纯函数测试尚未CI登记，原10函数同版保留；它们的语法/收集/执行均0。已知Host/App同解释器精确pin冲突仍未解除，004双进程候选正在实现，不允许通过忽略依赖或source overlay跑旧装配。private-fields六负向未来运行须同身份的正常fixture对照以独立定位目标拒绝。

本轮零新进程/编译/测试/网络/SDK/浏览器，schema2 guard关闭；两处股票helper摘要保持原样。整体目标active，完整安装、实际45场景、真实来源、中文入口与生产分别未验。


## 后继：账户操作路线纠正

账户运行手册先前仍指向终端HTTP源端手册，已改为本仓国信操作手册和SHM连接包说明。旧HTTP手册加历史保留/退役状态，保留旧正文以解释历史证据，终端外Host认证HTTP与终端内HTTP明确区分。schema1现有构建/搬迁与新schema2/ATI/45项资格分别标识，账户运行guard保持关闭；移除账户说明中不属于当前功能的人审词条。两份手册的准确before/after和本地链接核对见文档变更（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-operations-doc-fix-001/change.json`）。本段仅操作说明纠偏，没有部署/重启/运行程序，0新进程、0测试；实际命令/安装/新来源仍未验。


## 后继：Host历史锁材料已定位，Python目标资格分开

在既有SHM历史安装材料中找到Host a3／Agent a2完整15项requirements.lock（SHA3801b9035a6c5dd63c93d7393e868b266fd2d97ab2bc24942e63e1f44089cd38），15个wheel逐SHA与锁匹配；15份已安装METADATA与历史installation封存清单逐项匹配。该installation.json本身SHA2617b62ce9a20fbd408b8934bce79a6ab59ed5031fecc987fd50ef3f57e2572d及长度与当时artifact清单一致。

历史目标为CPython3.14；pydantic_core2.41.5现存轮子是cp314-cp314-win_amd64，不能供ATI的3.12安装。其余12个第三方轮子仅标为可候选复用的universal材料，完整目标依赖仍需重新校验、实际安装和pip check。当前本地Host a4／Agent a3需从冻结源码重建；原a3/a2轮子不冒充现产品。材料计划见target-material-plan（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-host-lock-static-001/target-material-plan.json`），明确不是可安装目标锁，没有生成已安装收据。

另核到Host自身声明Python>=3.10，而固定Starlette1.9.0的METADATA要求>=3.11；因此3.10安装资格保持未具备，不据顶层声明扩授。ATI继续以3.12为测试目标，产品依赖未改。本轮仅读既有锁/轮子/metadata及写静态计划，0新进程、0网络/安装/测试；该发现提供下一安装动作的真实输入，不替代目标环境资格。


## 后继：ATI设计核证与三个候选待full

ATI独立设计审查（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-native-test-runtime-design-review-001/REVIEW.md`）已complete-design-static，无新增阻塞P1/P2，report SHAbca1a652d0e1c89fc2facf4adfd3136f323dcb95c10e6c589ad172a3ba83eb2e，manifest SHAdf8d0d6537a1f51d3cc80dec0185a2f4db62e02618282f98c1ab58152e2ac461；50原件根核无差异，43来源保留run_schema2后继003的唯一已知live漂移，未冒充全源不变。依建议在ATI补一句测试目录DACL/同用户抗篡改未验证，16要求不变，现SHAeb9da76d2ea708432cef98597bb8ae67fd340180ce2ceda234252d7e24dad200；原设计输入和报告保持原样。

三份最终候选已按文件所有权封存并分别送独立full：Native004测试双进程58份最终输入/9apply，入口SHAef8e4e172851fbc6f4959a69f2aa09bc33fb90341d68879d841914c182e25f44；源清单闭包001的270份最终输入/3apply，入口SHA842249be265cb1981f69a9e4512cf03b2a5bd08929a42e0d95ab760297afc1df；CI007的134份最终输入/3apply及004的9项incoming前置，入口SHA7c16dfbdc83f3fc114c94089395be7990e988ddaaa61084da2b3bac15e95c97b。作者源闭包292原件、262来源根核无差异；这不是实际Python选择器运行、wheel或安装通过。三候选尚未apply。

004的两个新增纯测试仅定义，CI007准备显式登记连同003 oracle共11 selectors/22测试文件，实际集合仍由独审核实；没有触发CI。完整Host锁/双环境安装/QA helper生成/外层受管启动/CMake重定位与全部原生场景继续未完。所有动态执行0，窗口归属unknown，运行guard关闭，整体迁入active。


## 后继：源闭包修正落地，004发现与CI条件核证

源闭包001独立full已complete-static-only，report SHA23acb7d70a0172610546f9cdf3fd661c00bfa7c032c431e5a955a9d2a946a594，manifest SHAf347ea74686d9d8fe9b7ff041f7d94c631d138134b8681c5b8fd3c1ec32fa944；270份审查来源副本及6份摘要原件已根核一致。3项自有配置/选择器/测试已应用，269份真实路径post匹配（额外final-source-selection-contract不是仓内目标文件），应用记录SHA7a4fe3ecd124feaa091f6c4dab9ccca7c8ba010983e0158cb85add7f08c6922a。262选中来源仍是静态清点，Python选择器与25新函数未执行；root canonicalize后的边界不等于拒绝原root alias。原prepare之后逻辑、WT08/11TU/schema1保持。

Native004独立full（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-native-runner-static-review-004/REVIEW.md`）结论gap-static，3项P2：安装准入缺必需产品发行及模块实际RECORD归属；HTTP线程错误在stop/close竞争下可被遗漏；实际发行/metadata/requires枚举缺逐项原截止和数量限额。report SHA665047463677db8f5db9a0db2c2bd69b8116d2406239c2931ec23ade22e53ac9，manifest SHA144445da58d44b66de076633663a1dbb93f83d8e1d41f9dd2f98cddf270298ce，71原件根核匹配。004继续冻结未apply，作者在新005统一修根因与反例，尚未授闭合。

CI007独立full006（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-account-test-entry-static-review-006/REPORT.md`）70项=62 complete-static/0 gap/8 unknown，160原件根核匹配；report SHAe61609cfb032989fa2a3650163f9e1c2b3d11b45dab0658ca362b1c88d40438e，manifest SHA02737d10ecdb50659d566fd3036df1374d2006e25bcb74590b1b2c8a6d69fb2e。11 selectors/22文件/169具名函数是定义和静态入口数量，不是运行case数。结论以9项incoming004先落地且hash匹配为前置；由于004自身gap，该CI未apply，待005最终来源重冻组合后重新复核。来源清单001应用属于后继输入变化，旧CI007冻结结论不回写。

安装下一切片继续既有CMake/artifact/flow的validation源码与唯一QA helper派生，双角色wheel、完整实际安装、外层受管启动和45项运行仍后继。全程0新程序/解释器/测试/编译/网络/SDK/browser；schema2 guard关闭、窗口归属unknown、整体目标active。

## 后继：保留业务实际入口、只读总览与原生夹具005

已沿index.html→main.tsx→workspace/IndependentApp核对当前浏览器入口，旧Console App.tsx不属于实际挂载链。保留业务入口清点与更正原件位于build/guanheng-workspace/retained-business-entry-static-20261023-001；整体清单继续包含实时策略、执行、配置/自选、独立市场观察、运营及发行等差额，账户测试通过不等于完整迁入。

总览只读账户切片已通过不同作者full静态审查：审查入口282a3e0394a3e95a339397bb58331ac2aa1895f770f0d2ed93b3adaaf7e0bca5，报告bb9d86ee5a9bdf6d3131261d4c604884cc90edb2e52dfad2c09808045b8ad621；46原件与29最终输入根逐项核证匹配，阻塞P1/P2为0。已落地IndependentApp、AccountWorkspace、GBW-R4及OverviewWorkspace.test四文件，29post身份匹配，apply收据cf3268818c5319adfa68c3d8855ef76687d9091248d88c42773fd3cbc9127142（build/guanheng-workspace/native-overview-account-reuse-001/applied-001/apply.json）。唯一审后差异为C1注释改写为稳定测试意图，测试可执行内容保持审查原样。/dashboard沿同账户query/API/DTO，不增账户账本或后台接口；策略状态与收益曲线仍明确未接通。新增2项测试只有定义，未运行类型/构建/DOM/浏览器或真实来源，不授F04/总览整体完成。

Native004三项P2的后继005已封存，根核179制品匹配；最终入口fe811ef6f6b41b74229c0e70f51b97ff7a99405a99b0fda21c5f2a4ca66f0a66，67最终源/9实际候选修改，尚未应用，已交不同作者full静态复审。产品发行/RECORD归属、HTTP线程尾声异常、所有实际枚举步骤的原绝对期限由该复审独立判定。validation-layout001四项安装源码接线候选已封存，根核36原件，正由不同作者静态full；不授完整wheels/安装/搬迁或CTest运行。

CI008重新组合最终005前置并保留原CI三项接线，入口96b924ad7a4675336683659a70e5f82b5b6f6d2301774d321427d0f3b78701c2，160来源；预期11选择器/22文件，未应用。它依赖005自身独立审查和精确落地，旧004/CI007及历史审查保持冻结。当前原生45场景依然2项implemented-unverified/43pending、运行0；schema2 guard继续关闭。

两处股票算法helper保持原SHA，修正继续暂缓，作为对应算法启用前检查项；行情/历史/回测/账户适配继续推进。全部新增进程、Python/import、编译、测试、SDK、网络和浏览器维持暂停；黑色命令行闪窗的实际归属仍unknown。

### 安装来源校验独审后继

validation-layout001独立full最终为gap-static：58项中48静态符合、2项同根因缺口、8未执行边界，报告a026956a0141b562b7fa56a98eea3837591ad1e2678dfe0ab36f888b7ffb0e27，manifest67f34b83c4c423632a40597d1f409947e699f3ed5a73d7d7c98b885e00b74212；根逐项核48原件匹配。唯一P2为旧格式提前返回绕过产品overlay及新namespace大小写准入。001未应用，根制作002后继：4项完整携带、2项实质后继，产品目录/同名模块禁入归到新旧格式共用入口，namespace按casefold识别后仍按精确来源映射，新增3个有效控制包反例定义（共19函数、执行0）。最终入口ecb0cff8929588a47bb18f0b3a3d2c19d7bca0d4caa6a47d2f857bbb09f35309，21源根核匹配，已交不同作者审查；本候选还须与经独立审查的同版账户consumer共同落地，完整安装资格仍未授。

Native005独审已保存期限残留P2 N005-F1：open或上下文进入迟到后仍开始read；同根因关联动作表继续完整复核，005尚未应用，CI008保持冻结停审，等待完整发现后统一后继。此处是已保存静态发现，不代表真实运行已发生；动态仍0。

### 安装来源后继002静态复核完成

不同作者对002完成根因delta和同名模块策略full子范围复核：68项60静态符合、0gap、8运行未知，原ATI-LAYOUT-F1静态关闭。报告24c1d039ddb86d69f70b18cdaa29ce2b7ceedc3f30d9f9abd14ecacf5849bca1，artifact-manifest52a38ac70352b593e9e4b6ab20ff6ec5c27cb279a683aa0b5def5bc2cc0bc9d4，根核39原件匹配。19函数执行0，候选仍未应用，必须等同版账户consumer后继独审通过后联合落地；不授完整安装、005功能或原生运行资格。CI008继续冻结。

## 后继：逐动作期限统一修正006已冻结

Native005独立full最终gap-static，仅N005-F1一项P2。67最终、31before及5补充共103来源对象零漂移，报告d3f46d4a7dde22f7b7a5250b7e0115dffd7b25dcaee009441368aa85d051a096，manifest745d9a6b04316659e9df135e557a53227ea13ddcfa6fd4df02dd2693d1da2394；根逐项回核115原件匹配。原发行/RECORD/模块归属和HTTP异常恢复达到静态要求，剩余同原截止的14组动作关联表作为后继触发。

006已完整编写并冻结送不同作者复核：fixture_control统一Deadline，有限短stream在open/enter/退出异常下清理，目录/marker/枚举和base_data沿同原D；Managed、Suite和Host对长期factory先接管再核D，保留原关闭/reap/异常恢复主体；父CLI有限读取registry、逐项容量拒绝及超时结果失败出口。72最终源、18携带、相对005九项变化、相对live003十项实际候选修改，23before与20协作原件根核匹配，context变化0。最终入口25f905b5d9a699b0c1dde91d36b855f8e1a8dfe506d05af8531ef438c32ec966，候选138制品manifest8eab880aab94e970da3b88663aa6b0ca830904bfafb2e0db8e3232ba55a459cb，SEALf87ab03b057dd6c6e45c5c99dba41c4f94cde8674c4fa5776c1070a21f60824e。

四个纯入口共有93具名函数定义（51 runtime、26 lifecycle、10 IPC、6 oracle），不代表参数化收集或执行数；全部执行0。原45场景JSON仍c730933bcf52b1c8db83438c2032313ee4d8d8c130dd61d5cef1ce7efd10f3bf、registry43eeccbca7951244e6aeb3a159ea47f8f61a5c98d4416ca5c2add3ea626fe88a，2 implemented-unverified/43pending、运行0，schema2 guard关闭。

006独立复核已先保存N006-F1/P2：新增晚准备测试把receive统一替换成ready形状，关闭读取closed时KeyError覆盖原超时异常。006原候选保持冻结、未应用，完整审查继续；007草稿已按kind分别提供规范ready/closed值，并显式核原异常对象及全部Job关闭尝试，尚未封存/未应用，等待006完整发现后统一后继。该问题在测试替身内，尚未进行动态复现。

目标cp312材料定位在三个明确子范围完成：历史wheelhouse、E盘pip/http-v2缓存和本仓build/cache，未找到pydantic_core2.41.5 cp312 wheel；该结论限所查有界范围，不是全盘缺失证明。报告入口1e1fc3dc6c0068cd5db3581a688dfbda58a50c0aea5800c875af70be79ee5915，manifest2720cb6e226bafd83a5b49a69fbf8e155faea453ed7059af297af9a4e458112e，根核7原件匹配；未下载、安装、解压METADATA或生成目标锁/收据。布局002与CI008继续待合格同版consumer联合接线，动态仍全暂停。

保留业务另行推进F08个人观察自选的源码必要性及最终契约候选，独立于策略交易范围和账户夹具；尚未修改live业务或WT框架，不能以此缩小整体迁入目标。

### 006全影响复核及007单项后继

006不同作者完整影响复核已结束，唯一N006-F1/P2位于测试替身；原N005-F1的14组配方期限边界静态收敛，发行/HTTP异常组合及旧清理主体保持。报告e916970b39c393509c6266a1ec810332fd89d758cde032fe638d221b5a0c6d91、manifest277eb7ab5a6a461c533c92502587e78e004dcb50b3d72ae12c48b4b2a1b8fd7a，根核105原件匹配。没有将静态结论授实际运行或安装。

007按阶段构建规范ready/closed替身，显式核原超时异常对象及关闭尝试；只有test_fixture_lifecycle一个来源变化，其余源码/合同与006逐字相同。最终入口bf40bbdc883c524825b78fb580cee735d6b8e5b7917ca130965b5d5e58882019，72来源与23before根核匹配，18携带/10相对live候选修改，已送不同作者delta/影响复核。93具名定义与45场景状态不变，均未执行、未应用，schema2 guard关闭。一次冻结工具将新增文件before=null错当缺失而中断，仅影响自有候选目录，原尝试按检查后的绝对路径保留在root-review-package-attempt-001；上面最终入口是唯一审查输入，未动live/原006。


## 后继：007与布局002联合落地及进度核对

Native007独立delta/影响静态复审通过，报告be4b720774be97897e4a2431284ac03419c6f57e981091d554682f7a4ca516f7、manifest242302592dd51730a8d0f2d50f068253f6013016ffbc5f5ea7a6976236f18881，103审查原件已根核；与已审布局002联合落地14项自有文件。应用回执为build/guanheng-workspace/native007-layout002-apply-001/apply.json，SHA3a56f0fa2d4899afdfb7d6019173a754136c53a59a3ced70cc02bd6c97c836f4，登记78项组合post匹配和唯一CMake上下文替换。此次再次读取14项实际落地文件，after摘要全部匹配。静态审查和源文件落地分别成立，运行、安装和原生资格继续待验。

CI009按联合落地后的168份真实当前来源和3项候选继续独立审查；已收到的阶段核对确认11选择器对应22现存文件，最终报告尚未封存，未应用/未调度CI。原生45场景仍2项implemented-unverified、43pending、执行0；schema2 guard关闭。实时策略/执行、全市场真实数据覆盖、配置/自选、独立市场观察、运营及同版独立发布差额继续按完整清单推进。闪窗来源仍unknown，新增程序和动态验证保持暂停；没有生产切换、真实委托或新增框架修改。


## 后继：CI009静态接线落地，个人观察完整切片继续

CI009不同作者独立full静态审查complete、无P1/P2，入口b47c64e6f750bbd3b93c37395588d51b531315e734e0e297455934de325fb838，报告3f6e8fa4d0769f7e21ed5b884c0551ad36f52eb92e979aadb1b0592995ddd50d，manifestb3245d476037581d1762c1f0c3a4ef98c7c0c9274fbc02f4404a188e3d7f7609。根逐项核211制品及168主源+30补充依赖当前原件后，落地workflow/README/testing三项。应用回执build/guanheng-workspace/qmt-shm-account-ci009-apply-001/apply.json，SHA6822f366094b3338d668b5a5886f545bd98cb1a2dd55d858b2b5d7da8d2406a1；198组合post匹配。唯一审后差异为独审C1/P3建议：testing澄清四个纯入口允许精确替身调用main、不会启动真实双环境流程，测试/工作流执行代码保持审查输入。11选择器对应22现存文件属于入口登记，未触发CI/安装/测试；新账户guard关闭，45项状态保持。

保留业务F08另行推进：个人观察自选18要求及7文档候选封存在build/guanheng-workspace/native-watchlist-spec-002；入口b8ab5c1a4fd07123f6874e2b6242f80bb917d9e9d3938b36472685808b41170b，manifest6aec8d922ed3bdaa290589c8f3ceacedf7acf7d5ef803934a0c6c713d789a4f5。44实际来源与副本无差异、61制品及82相对文件链接已核，交不同作者full设计静态审查。WT策略userdata随上下文及策略名保存，Servo订阅承担行情接收；应用偏好owner、完整列表版本比较和小JSON只补此用户能力差额，策略/行情/账户归属保持。设计文档尚未应用，不授F08完成。

自选协议不可变DTO、前端严格解码/一次PUT与两侧回归共4文件已写入独占build/guanheng-workspace/native-watchlist-implementation-001的staged目录，身份见其STATUS.json。16个Python测试函数、16个TS it语句仅定义，语法/类型/收集/执行均0。持久owner、OS单写者锁、HTTP/配置/生命周期、中文页面和正式保存→关闭→重启整链仍待实现/验收；当前业务源码和WT框架未因此改变。其他完整保留范围继续active，运行暂停及闪窗unknown保持。


## 后继：个人观察设计接受与完整后端静态候选

自选设计独立full静态复核18/18 complete-design、无P1/P2，入口87804bce656b793b86442029c62010ab94d923183ba2743905ba55aa2f0f039c，报告e9ed63faad873f3c7d29943ca4ab036081ba995f19f086564491a943fd23428f，manifestab0be2426b5ac47a319539faba8d346ff5faa54588e6d9072bc4f006e1fc61a1；根核71原件、47主上下文与5补充来源。7项文档已落地，回执native-watchlist-spec002-apply-001/apply.json SHA16f1db184dea8ae35b4329565912eeb201f9fdc7cc59f5c3e2c74f0016423d25；仅状态接受和独审C1/C2说明收口。后继展示澄清区分缺能力与完整不可用，均零GET/固定中文，无协议字段变化；唯一规格当前SHA4ba3c3331a6a3f162b7ed71e948fcfbe0ca95735d1a078d00daf85213df5c786，原报告保持冻结。

根后端15项完整staged候选封存送另一作者full静态审查：独占native-watchlist-implementation-001/root-review-package/review-input.json SHAacc9c72af237e63676e8b44c49a1ef5c1802f9710e408e6dc7ca5a75dfa0b269，manifestbb0440887a772b2ad19cf694b076d731d52892007b933b9bcf444e1d6ba3e765；根逐核248制品和240最终来源/6before匹配，source漂移0。包含单写者OS锁/原子替换/锁内版本比较、首次初始化竞争保护、坏文件及残留tmp、提交后超时重新GET、所有权保留与并发关闭、HTTP同D/取消及共享Origin、设置/应用装配、根API和测试/CI/说明。只在staged存在，未应用业务实现或修改WT框架。

41个Python具名测试函数、16个TS it定义均未语法/类型/收集/执行；12选择器对应25静态测试文件，CI未调度。另一作者完成页面实现候选并独立封存，根对UI另行审查；不能以根后台自查授UI或完整F08资格。正式包/真实文件保存→关闭→重启/中文页面、全市场真实源和整体迁入继续待验，闪窗unknown和动态暂停保持。


### 个人观察UI独立full静态审查后继

另一作者UI七项最终候选入口native-watchlist-ui-001/review-inputs.json SHA770cfbf6a95b690254ceec14281dcf824ed8ffb3fe3f093f5f2e559b205dc73f，38作者制品、19上下文与7live/absent根核匹配。根另读四份实际CSS/图表/时间/品牌依赖，完成独立full静态审查：入口native-watchlist-ui-static-review-001/review-inputs.json SHA064dfe4788cd0759f9dcd703b098cdba1e41c12897206af86e184650af6cf752，报告68bdc989cd642744ecc5488825a76f98cda2fee512d0326172f5fdc712d1668a，manifest6c288515c716e8b37b8f3b00ec4d76da4deb60aedf1105a266c6b8fdc4457f20；审查原件逐项post匹配，原七项仍未应用。

唯一P2 PWL-UI-F1为待定/未知保存的phase与完整目标只在组件局部state/ref。保存后切换路由会销毁它们，卸载后异常被mounted分支跳过；重挂载GET同ID列表后没有原目标可比较就恢复编辑。此处为源码路径静态发现，未动态复现，未证明文件损坏或交易副作用。要求以跨路由存活的有界UI owner持有唯一待定目标/阶段，先GET核ID/完整顺序/最低版本后恢复或请用户确认，不增加持久日志或自动重放。另C1/P3建议恢复列表时同步能力，或明确整页刷新说明。

作者继续先完整完成根后端full并统一封存发现，之后在ui-fix-002修正；禁止边审边改根后台和原UI。26个UI test/test.each语句仅定义，TS/构建/安装/HTTP/浏览器均未执行。本轮实际变化为七份设计文档接受、15份根后端候选和7份UI候选及独立审查，产品实现未应用、WT框架未改。完整目标active，账户45/guard、真实来源与弹窗动态暂停边界保持。


### 后继：个人观察后端full与UI修正静态结论

后端001完整独审已封存两项P2/一项P3，根核261原件；修正002的19项候选、242来源/8before/252制品已送独立复核。UI-fix-002由跨路由有界owner修正原待核目标丢失，根独立delta complete-static、F1/C1静态关闭。详见[独立个人观察证据](2026-10-23-personal-watchlist.md)。这些业务实现尚未应用，所有动态0；账户45/guard、真实来源及整体迁入范围保持，闪窗unknown和新进程暂停继续。

## 后继：独立Host原始来源比对候选

个人观察前后端已按两份独立静态结论联合落地26项，完整身份与边界见[个人观察证据](2026-10-23-personal-watchlist.md)。账户新来源guard继续关闭，实际45场景清单仍2 implemented-unverified/43 pending、执行0。

账户验收另在独占native-account-source-oracle-001实施16项staged候选，未应用。新source_capture仅属测试层：Host在扫描前和stop后request_close前各捕获一次公开read_binding原bytes，核binding/profile两层原SHA及前后同B；父端在实际Host/native tree0、双EOF、reader join、Host exit0后才采用同轮有限capsule，成功和partial已交付批次逐字段匹配独立Host来源。期望来源不从native observation反推，未交付批次仍null/空/unavailable，无生产账户文件或新数据库。

唯一审查入口（外部历史/待归仓路径：`../../build/guanheng-workspace/native-account-source-oracle-001/review-package/review-input.json`）SHA48f92ee746d992e4d49b60015e802818b29438eee53cf4f15a5219a89fe9b19f，manifestf5efab5a265ba8feb64a8ad09daf3e37e78c88ba986da5ec944fa8f4788d0987。247最终来源、14before、263制品及16项live/缺失状态已根核0漂移，交不同作者独立full/影响复核。原45 case定义SHAc730933bcf52b1c8db83438c2032313ee4d8d8c130dd61d5cef1ce7efd10f3bf保持；registry唯一拟变化为partial-summary-source-null的完整可执行断言定义，候选3 implemented-unverified/42 pending，当前live仍2/43。原recipe成功exit3/失败4/full45=false保持。

五个scan纯入口共有107具名定义：runtime51、lifecycle26、IPC10、oracle8、source_capture12；新的单一成功前缀反例先通过原投影形状准入，再核独立Host身份拒绝，避免以形状正确代替原始来源。Host资源工厂纯替身补前/后采集及发布迟到，普通测试安装manifest增加必需source_capture.py；CMake原目录安装自然携带，无CMake修改。新CI候选13选择器/27文件，未调度。语法/类型/收集/执行、真实Win32/双环境/Host/Agent/SHM/SDK/用户页均0/unknown，尚未授该修正静态通过。

所有操作限现存Node的文件/文本API，闪窗归属unknown及新进程暂停保持；cp312材料、其余43场景、完整策略/执行、真实覆盖、配置/观察/运营与独立发行差额继续。整体目标active。


## 后继：来源闭包兼容修正与输出故障单元候选

账户来源001独立静态full已封存：一项P2 ASO-F1，根核275审查原件无漂移。问题位于正常回归资料：新增source_capture后，manifest正常读取有15项，断言仍写14；producer→consumer跨契约正常夹具也缺该模块。实际完整目录安装可自动携带新文件，报告没有认定当前完整产品包必然漏装。独立报告见Source full（外部历史/待归仓路径：`../../build/guanheng-workspace/native-account-source-oracle-static-review-001/REPORT.md`），SHA d6a99b50384f9a454d127efa538935022fb900cd951418bc51e183651a713e37。

兼容域补充（外部历史/待归仓路径：`../../build/guanheng-workspace/native-account-source-required-set-audit-001/REPORT.md`）的14制品根核匹配，明确producer的source-identity-only最低集合与当前runner运行闭包分属两种资格。保持生产最低集合，既有无新namespace的schema1和带source-only记录的旧归档均沿原规则；当前consumer仍拒绝缺新增运行模块的资料。

后继fix002已封存送独立delta，17项staged候选未应用；相对001只改两份测试资料/断言。正常原件新增source_capture及精确SHA正向，独立定义“旧最小集producer/archive接受、当前consumer因test closure missing拒绝”的反例；正常读取同时核路径集合和数量，late解析仍零成员读取。唯一入口fix002（外部历史/待归仓路径：`../../build/guanheng-workspace/native-account-source-oracle-fix-002/review-package/review-input.json`） SHA 4181d2eb6bdf8236963ea7779067ec52cf6e4d34ba883c844089f2dfe0846556，manifest abeb5f234808c57475e9f0cb796521cc5d696198006da48f981884a2d46069c6；247来源/15before/264制品逐项核对0漂移。21个来源安装回归具名定义属于待执行入口，原scan107定义及45场景状态不扩授。

自有FrameWriter另有9项staged候选，状态见候选身份（外部历史/待归仓路径：`../../build/guanheng-workspace/native-account-frame-io-001/STATUS.json`），SHA be806c5f681119df5696599068ac98607bbb7958430903ccdad011941835a2f8。借用I/O回调默认仍调用原CRT；产品生命周期后半段原bytes保持。QA probe直接复用同一产品translation unit，只调用输出owner，定义14个有限故障/正常场景，新增6个构建来源回归定义。CMake与冻结selection负责显式启用、构建和CTest，QA exe不进产品install。迟到通过测试回调收窄同一Deadline，仅覆盖后置检查；不证明真实时钟、阻塞CRT可抢占或父进程硬截止。该候选尚待独立full审查，未改live或WT框架。

本轮为静态进展：新增进程、Python/import、语法/类型/收集/测试、编译、网络、SDK、浏览器及CI调度均0。项目start/check因现有闪窗故障暂停，动态及安装资格保持unknown；账户schema2 guard仍关闭，实际registry仍2 implemented-unverified/43 pending。整体迁入active，继续账户运行资格及完整保留业务差额。


### 后继：来源fix002静态闭合并落源码，Frame候选送独立full

Source fix002独立delta结论complete-static-delta，ASO-F1两条触发链closed-static，无新增P1/P2；报告（外部历史/待归仓路径：`../../build/guanheng-workspace/native-account-source-oracle-static-review-002/REPORT.md`） SHA455c6eae361a3d2f120f687482ad7c4b68c73ef04e364066a28ca8fc99191532，manifest e5ab876063340f7191550c32ec1f7f6e1b049b8e41259d84d4763f084f3a3c8c。根核270原件匹配后，将17项候选落源码；247来源按实际路径post核匹配。应用回执（外部历史/待归仓路径：`../../build/guanheng-workspace/native-account-source-fix002-apply-001/apply.json`） SHA2eac879bc34f03edeb2e601e0471a4ab83e05d28f6d10333c8188f4065962280。固定上游参考从其声明实际来源核对，未把虚拟fixed-WT08索引当工作树路径。

当前账户registry为3 implemented-unverified/42 pending、执行0；45 ID/expected和source2 guard保持。该状态只反映已编码断言，未授原生通过。Source安装身份最低集合不变，两种旧归档兼容域及当前consumer缺新增源拒绝边界已静态复核，真实解释器/安装/运行另验。

Frame输出候选已补测试模块说明与测试手册，最终10项staged未apply；唯一审查入口（外部历史/待归仓路径：`../../build/guanheng-workspace/native-account-frame-io-001/review-package/review-input.json`） SHA5d79104d73cf3f523158f97d7fe10af93edfbd3aeca0ff6733b5d551b1c44683，manifest 024e36c6cd24fb8a456d076b7ceb6a4bac84c07fdde473571b668553a31cb508；251来源/7before/260制品根核无漂移，交另一作者独立full。此前STATUS九项快照是加入测试手册前的历史身份，最终入口以本包10项为准。14个单元场景与31个构建来源具名测试（其中新增6个）全部未执行；原生45资格保持分列。C++产品main当前SHA1935762ee3da653fe28cc41f8c0d0b46eaa4cfae5e6523dcfed0fd115aa4aa95及两处冻结股票helper未改。

本轮新增进程/解释器/import/语法/测试/构建/网络/SDK/浏览器/CI仍0，闪窗归属unknown，整体迁入active。


## 后继：Frame输出单元与关闭后来源采用回归落源码

Frame独立full结论complete-static，无新增P1/P2/P3；报告（外部历史/待归仓路径：`../../build/guanheng-workspace/native-account-frame-io-static-review-001/REPORT.md`） SHA0ac4ac58f4cce0ff4c8083e3c3c59ea890bd554e4342d554c7755f416b8d50b6，manifest 2e258f61ed432a5bf4bd936ad0fdee5a537676b3a2465198ba6b69c7e0697cc5。根核267审查原件后，10项源码/构建/测试/说明已落地，251组合post匹配；回执（外部历史/待归仓路径：`../../build/guanheng-workspace/native-account-frame-apply-001/apply.json`） SHAac82227745eb47dce7ade9b995d20622f7d6e8946655cc0696b3d60824a33b8d。14项是frame-owner-only单元定义，31个构建来源回归具名定义均未执行，不能替代真实时钟/硬截止/进程/native45/SDK/安装资格。

关闭后来源采用新增4个lifecycle回归，包含非空record正向、9项单独缺失关闭事实、坏capsule及原过期D。独立001发现ADOPT-F1/P2：原过期测试目录无capsule，错误续期也会因缺文件失败，掩盖目标条件。后继fix002先用已有原件生成器和真实publish/read验证同轮binding/SHA，再用记录真实调用的薄wrapper核原D和original deadline异常；有效原件使错误续期可被区分，不改生产codec。独立delta 报告（外部历史/待归仓路径：`../../build/guanheng-workspace/native-account-capture-adoption-tests-static-review-002/REPORT.md`） SHAb29f699a97c300cd0e8bbd9038938afcc8e3bb5de82e5b1a2df88766059fe25a，manifest fc7ff68fd4e31f0387e1b44312d33a6e9ca4e6f1d666f1656fe4da01d8a332b1；根核37制品后落1项，28来源post匹配，回执（外部历史/待归仓路径：`../../build/guanheng-workspace/native-account-capture-adoption-fix002-apply-001/apply.json`） SHA9fae1bf19101fd503f517b4d95801d26bea98e4eceee0ef145eb0a99c49b859d。

当前lifecycle文本定义30、scan合计111；参数数和定义数均不等于执行数。进程/Job/Thread仍是显式stub，期限反例使用真实临时文件/硬链接，文件头已准确区分。实际registry仍3 implemented-unverified/42pending、执行0，新schema2关闭。产品/fixture的实际采用逻辑未因这些测试变化；旧QMT只读、WT框架冻结边界保持。

后台启动另有startup003候选：仅补当前工具5处隐藏选项遗漏并收敛唯一选项owner，8项staged、261来源/6before/269制品交独立full；独立客户端工具及本仓Git/版本探测不延长终端HTTP路线。旧HTTP qmt_connector、退休flow及上游copy脚本未改。详情见[窗口记录](../incidents/2026-10-23-repeated-windows.md)。该候选未apply，历史闪窗根因仍unknown；新增进程、Python/import、语法、测试、编译、网络、SDK、浏览器及CI均0，整体目标active。


### 后继：当前后台创建选项修正已落源码

startup003独立full complete-static、无新增P1/P2/P3；报告（外部历史/待归仓路径：`../../build/guanheng-workspace/native-background-startup-static-review-001/REPORT.md`） SHA1987fa50b4a31281f0f64cca6d32f55517f692a6829dc3d724828000bacf1d4c，manifest 0e4b724097964530b3185c4ec3c35e58cf28c943eab735282dbc13ffca0aaef2。根核278审查原件（含docstring-only包init依赖）后落8项，261来源及额外init原件post匹配；应用回执（外部历史/待归仓路径：`../../build/guanheng-workspace/native-background-startup003-apply-001/apply.json`） SHA7f9c29c019a288c83181acc99908800b50d4ae4dc4679b4dc707c2c04a7cd63e。

唯一process_startup owner完整选项函数与原native函数规范化行尾后相同，native公开入口为同一函数别名；五处当前Git/账户工具版本/客户端wheel创建调用已共用策略。账户源快照仍由scripts/native_support目录拥有新增helper，Frame包装器继续原native.run与工具Job，不另造启动或清理逻辑。旧HTTP qmt_connector、退休flow及WT框架保持；SDK/终端发行白名单不含helper。6个新增纯定义均未语法/import/收集/执行，CMake/Ninja版本探测原本无timeout的行为未在本轮修改。

实际闪窗所属PID/HWND和触发链继续unknown，此静态修正不授运行恢复。新进程、编译、测试、网络、SDK和浏览器仍暂停；账户schema2继续关闭，45状态与完整迁入范围保持。

## 后继：明确恢复授权后的实际软件与原生开发验收

用户已批准受控隐藏验证。账户原152、来源捕获/关闭/IPC139、父端与唯一投影110纯软件回归通过；自有中央Job七参数ABI已修、独立delta complete，39软件及3真实创建中断回收通过。固定WT基线和同版owned原生账户/只读DLL已构建，14帧单元、两组CTest、64构建检查及开发ZIP隔离搬迁23个schema1合成场景通过。完整原件、SHA与失败轮保留见[恢复证据](2026-10-23-background-process-windows.md)。

上述软件、Frame单元、旧schema1兼容链与新schema2的45原生场景分别计量：45仍3 implemented-unverified/42pending，实际执行0；新公开门禁仍False。真实账户四查询、同版App/Host双独立安装、真实来源、用户页和完整发行继续。最新既有18017交接安装只开放行情读取，通用Host协议与本仓bound协议有差异，见[核对](../migration/qmt-successor-source-handoff.md)；健康200不授账户或WT接通资格。


## 后继：独立安装准备与测试启动目录根因修正

App公共依赖按冻结uv.lock完整hash导出并下载14个wheel。准备进程实际exit0，整树0、双EOF、reader join及资源关闭已核，见控制结果（外部历史/待归仓路径：`../../build/guanheng-workspace/account-runtime-install-001/control/build-public-001/result.json`）。安装工具候选正在完成两个普通CPython3.12角色环境，App与Host依赖分开，尚未授安装通过。

静态核对发现自有managed_fixture统一用每轮结果目录启动native，但自有原生main要求cwd等于安装目录。独立路径回归原代码得到native失败/Host通过，已将native工作目录改为其EXE父目录；Host继续使用结果目录。旧迟返回假进程夹具补必需host参数。214项路径/身份/关闭回归实际通过，身份和原失败轮见修正回执（外部历史/待归仓路径：`../../build/guanheng-workspace/account-fixture-start-location-green-002/fix-identity.json`）。本轮只改测试装配，WT与产品原生main保持；双安装真实运行及45完整场景继续待验，schema2公开门禁保持关闭。


## 后继：普通双安装、11轮原生断言与编码边界

新增双角色装配工具已完成独立full静态审查，无开放发现；27份原件根核匹配。实际runtime-002普通安装成功，随后修正App订单投影后runtime-003从完整wheel缓存全离线重装成功：App21项发行/pydantic2.13.4，Host15项发行/pydantic2.12.5，两者标准pip check通过。133源、55生成输入及角色1222/525文件摘要逐项根核；见安装根核（外部历史/待归仓路径：`../../build/guanheng-workspace/account-runtime-install-001/runtime-003/root-verification.json`）。首轮Flit CRLF/LF误拒及其失败原件保留；修正只允许规范换行后完整元数据等价，16项纯回归通过。安装器源与CI分离，不启动真实终端。

普通EXE/普通DLL与两独立安装已完成partial-summary-source-null四轮和private-fields-public-config-rejected七轮，共11轮；原SDK调用数、独立Host来源、真实双Job整树0、EOF/join及关闭断言通过。原配方和外层保留退出3、full45=false，见本轮汇总（外部历史/待归仓路径：`../../build/guanheng-workspace/account-runtime-install-001/controlled-slice-result.json`）。后者包含一次四查询正常控制；六次配置拒绝SDK均0。

运行暴露的两处自有测试装配遗漏已修：native cwd归安装目录；目录守卫列入正常Host Journal .owner旁文件。215软件回归及独立delta通过，12原件根核。第三轮partial曾发现App strict行key漏列原mapper已有order.price_type，现按逐类精确结构接通，unknown/null元数据继续未知，不采用ABI中性值。59投影/oracle、119父端影响回归及独立delta通过，14原件根核；WT和唯一金融mapper均保持。

账户UTF-8配方尚未完成：ASCII63字节合法控制通过，中文21字符/63UTF8bytes控制在准备请求前失败，SDK0、实际closed/joined；原失败及诊断原件保留。独立源审定位固定WT Windows loader转换CP_ACP与自有UTF8消费边界不一致，根受控读取本机ACP=936。自有Scan已用共享序列化骨架在WT交界生成标准ASCII Unicode转义，原IPC encode保持UTF8；WT源码/CLI/原输入digest/期限/金融规则保持。新身份account-scan-utf8-001完整all正在构建，修正运行资格仍待封闭，不能授Unicode已通过。

完整scan输出故障QA有静态staged候选，纯oracle9项通过；实际QA C++尚未编译/装配/运行，不能替代关闭链资格。45原定义不变：2项配方已完成本轮原生断言，第3项编码失败正修复，另外42项接线/资格继续；公开schema2门禁False。真实券商账户、真实交易、中文入口与完整迁入继续active，QMT终端运行现状、旧项目静态只读及框架审批边界保持。


### 编码修正的同版原生回归已封闭

新身份account-scan-utf8-001完整all实际exit0，未强制终止；整树0、双EOF、reader join及资源关闭已核。固定WT与同版owned三目标编译、两组CTest（含14项Frame owner单元）、80项构建工具检查、开发ZIP及隔离搬迁23个schema1合成场景全部通过。ZIP 2534513B，SHA fef728b9a052d530414583c3ce85360373751ab6fe82079313416bd2fff6e5ab；根重新计算匹配。main SHA ce7b5d75f3ae44e5e4217ed45bb7e34b7656900cbdd393ad110efa0e2e627eee，普通EXE SHA5b83554210f30626eee5582f11edfcb4531dadda0b81590d3e379d80a006825e，普通DLL SHAe1ca60be8e3d7fcced23264bc0dab428b02349f4dd23b2d332013f04e7449aad。

同一新包与runtime-003两角色独立安装，实际完成编码11轮、partial4轮及私有字段拒绝7轮，共22轮。合法ASCII63与中文63字节控制各SDK四调用并成功关闭，九种非法/越界输入SDK0；四类中途失败仍核独立Host来源；六次私有字段拒绝SDK0。三个原配方均assertions-completed、双Job实际闭合，入口和外层保留exit3/full45=false，原件见最终汇总（外部历史/待归仓路径：`../../build/guanheng-workspace/account-runtime-install-001/controlled-slice-result-v2.json`）。原45 ID/expected及registry定义未改，仍有42项完整资格缺口；不得把22轮当22项或完整45成功。

真实固定WT loader的配置边界probe（外部历史/待归仓路径：`../../build/guanheng-workspace/account-config-encoding-probe-001/result.json`）四组通过：ASCII63、中文63、含补充平面字符63字节及反斜线/引号混合。ASCII转义载体经原loader后全部恢复原UTF8 bytes，bool/int和原runtime_deadline_ns类型/值保持；原UTF8载体在ACP936下中文63→42字节且非合法UTF8，直接补齐根因证据。probe独占二进制，仅配置边界资格，不授SDK/45；创建期外层Job及隐藏编译/运行整树回收通过。

编码独立delta complete无开放发现，14最终源+before逐项根核；CI002明确接受现有通用native作业调度并修正文档，原001发现/原件保留，新两个纯入口仅生命周期矩阵执行，未新增账户双环境/45调度。最终本地文档检查通过。全scan QA继续仅静态候选及9项纯oracle，C++尚未编译/装配；下一步统一复用受管角色/制品准入入口再验真实输出故障关闭。真实账户/交易、真实历史全覆盖、中文入口和完整独立发行继续active，公开schema2门禁保持False，WT框架与QMT运行现状保持。
