# 账户已消费读取责任回收

类型：验证记录。唯一规格：[AAR](../specs/qmt-account-read-retirement.md)。独占原件根：`build/root-account-read-retirement-001`。固定SHA入口由该根最终接口和送审清单提供。

## 最终观衡读取停止后的最后成功发布

最终C63通过公开CLI启动单个独立只读App，读取field003中已经正常关闭的WT所保留发布。接口 `build/root-c63-retained-publication-001/INTERFACE-001.json` SHA `e46592dc894a1e9a4f8d6c818d7b5e6aa244ecad69a211e19af8b7139db3f8b3`，根接收 `build/root-independent-release-set-001/RECEIVED-C63-RETAINED-001.json`，冷核5项引用及196项冻结成员。

实际HTTP200，与原发布scan及持仓/可卖/资金/当前委托逐字段、浮点位一致；页面投影明确publication_state=stopped、runtime_state=closed，保留原数据时间2026-10-30T19:28:08.506403Z。内外8.984秒正常退出，树零/EOF/汇合/资源关闭，69项输入前后保持。额外来源请求、账户扫描及金融命令均0。该结果补足“WT停止后独立观衡读取最后成功值”子路径；原field003停止确认超时和C63两scan的第三scan缺口各自保留，最终SRI005组合业务另验。

## 真实136结果与最终观衡只读消费

2026-10-31后继field003已实际执行。原普通SRI004/Host15/Agent11/Native006由WT管理，正式QMT单正文于Host就绪65秒后启动；取得34轮四查询、136个不同成功且已消费结果，原128容量下实际回收107条过期消费结果，未知结果0。原始来源到WT发布的2278项事实、1326个ABI槽及浮点位全部一致，34轮发布与原观衡HTTP逐字段相同；停止观衡后，WT继续发布下一轮。原15613项输入前后相等，六个业务组件正常关闭，外层448.235秒、exit1、未强杀、树零/EOF/join/资源关闭成立。

整轮结果保持失败：根实际停止Probe并恢复原文的标记，比等待状态文件时间晚66.449秒，比原失败结果晚2.421秒；原60秒现场确认窗口未通过。文件时钟只记录实际先后，不替代monotonic截止。该主错误为RootStopRestoreUnconfirmed；后续“WT停止后重新打开观衡读取保留结果”分支未执行。原RESULT及停止标记完整保留，不追认整轮通过。

限定冷审 `build/root-sri004-aar-real-read-003/partial-audit-001/DELIVERY-001.json` SHA `5ad20be2a10d62b8bce89b9654b5a221b3cdb56f2ca66833ca2afae9c07d11cf`，沿原136/34及全部事实、身份、消费和回收断言核对；仅把原整体passed准入改为明确检查上述唯一现场错误、原业务关闭和其他前提。Journal与捕获证据摘要前后相同，v4业务读/金融命令0；审计正常全关闭。根冷核20项交付原件并接收 `ROOT-ACCEPTED-PARTIAL-001.json`，明确 `partial_business_evidence_only=true / whole_run_passed=false / root_stop_window_qualified=false`。该结果授真实持续账户读取与回收的有限事实证据，保留整体停止窗口和整套系统缺口。

最终观衡a63已独立接收：`build/observer-read-successor-001/INTEGRATION-HANDOFF-001.json` SHA `c73ad71d087c6c9c3fe1352c5efc3f0a0d7c1e089daa24ac8e5cdeddd7df8250`。根核194源码、4876安装成员、34引用及681冻结审查成员，沿独立只读WT read4/Native read1/Core read2，运行角色保持自身依赖。接收收据 `build/root-independent-release-set-001/RECEIVED-C63-FINAL-001.json` 保留62项观察、原800点报告和普通/离线主路径的限定资格。

同一实际WT发布的附加a63消费者取得2个不同scan，HTTP当前持仓/可卖/资金/当前委托与原WT发布逐字段和浮点位一致；额外来源请求及账户扫描0，自有App正常关闭。接口 `build/root-c63-live-publication-001/INTERFACE-001.json` SHA `b02c463506886269d4bc85a6dcac624b9f9d46c96e8caf1dc1ec96b3554b7025`；根核197冻结成员及4原件，收据 `RECEIVED-C63-REAL-PARTIAL-001.json`。该补充启动晚于原136链，未取得预定第3个scan及停止自身App后WT发布继续推进，完整补充验收仍未通过。后续在最终组合内验收这些剩余项，本轮不再重复136查询。真实下撤单、最终B整套运行及生产资格均未授。

## QMT重开后的实际启动与就绪等待后继

2026-10-31用户已重新打开国信QMT。根实际核对原策略列表后启动原 `GH_WT_MEMORY_VERIFY`；正文仍为 `b045353cd87ac671a91856644c92d6254ae3208a165e6cc46233c33f1d71ead7`。原WT/Host/history/collection的PID 33636/46288/60964/75000及创建时间保持，采集从disconnected恢复到connected，generation=9、心跳63900→63906、该代溢出0。闭市快照接收不作为新交易分钟生成证据；原 `QMT_METRIC_GATEWAY` 保持运行。

`build/root-sri004-aar-real-read-002` 的实际运行在启动阶段失败：QA看到WT的ready.json后直接读取尚未发布的status.json，`main.py:118` 抛出FileNotFoundError，账户探针及App均未启动，实际源结果0。原WT已经发布ready并随后正常停止；该次51.140秒、业务exit1，外层未强杀，树零、EOF、读线程汇合及资源关闭成立。15,612项运行输入前后相等；原探针始终停止并已在原窗口内逐字恢复35d020…，GUARDS-AFTER确认四个采集进程创建时间保持。实际RESULT、控制结果、现场见证和失败原件保留。

后继仅修正独占QA：在原同一个120秒启动等待中，一并等待ready及可读的完整status，沿已有FileNotFound/CollectionStatusPending暂缺处理；坏JSON继续失败，总600秒、晚到65秒、容量128及136目标保持。安装、WT产品、框架和策略协议保持原字节。该后继的实际结果见上节；本段记录当时根因与准备范围，不授整套系统完成资格。

## 最终Native006完整SDK主链接收

2026-10-31补齐最终同批制品的完整只读SDK链。接口 `build/root-native006-account-sdk-main-001/INTERFACE-001.json` SHA `d9d9ef2f8880b90a4890eb98549c76f8ec0bde2c3f108a08da69e0379df03bf0`；根冷核2115项冻结输入、全部引用及两个实际native.run控制的exit0/树零/EOF/读线程汇合/资源关闭，接收 `build/root-independent-release-set-001/RECEIVED-NATIVE006-SDK-001.json` SHA `fed598c0c20a1a2688d9db2441b1d6388d58268dacab51af4d75a2c227f8eeb4`。

同一次原完整夹具实际使用Native006的Common、Standard Factory/SPI和Scan，普通安装Host15/Agent11及实际CPython3.6.8单正文，经Windows共享内存完成Common80、Factory40、Scan4，共124次查询；四种datatype各31，v3/v4分别44/80个唯一结果均确认消费。容量保持8、原数值status高水位各2；关闭后冷库确认回收120条，余下每侧2条为已消费终态。原180/240秒、1000ms快速SDK票据和全部原断言保持，89.234秒正常结束；源原线程、单timer、策略正文文件/网络禁入口0及金融写0有同次结果。

版本更正：原main008控制原件实际选择Native004。此前正文中的Native005表示后继按未变协议部分复用，不能将其解释为同次124链实际加载005；原main009仅在006上完成16次。本次新增完整006实证，各原件和当时资格保留。消费响应中的retained是单行保留布尔，容量高水位依据原status数值，详见本次REPORT。

本次只有独占QA的制品选择、输出身份和被动计数变化，产品及WT框架修改0；QMT、原策略、原采集和18126均未操作。该结果授固定Native006/容量8/合成SDK完整主链资格，真实QMT的128容量/136目标、当前实机后继、B后续新交易DLL、跨日和生产分别待验。真实SDK5000ms配置继续沿已准备的60000ms回收方案，保持与此快速SDK夹具分列。

## 独立实机后继的离线准备接收

后继 `build/root-sri004-aar-real-read-002` 已完成离线准备。正式入口为 `ROOT-READY-001.json` SHA256 `5c9752d2d6c68401896bc51eef2bffac93c83ff2f2162cfbf8c58a20250d8204`，交付 `DELIVERY-001.json` SHA256 `9d81fdd564c17d6e3b2cad72f66590ca39d81915f0bdc4cd9f643a02998bb684`。根实际核15,611运行输入及15,695交接输入的合并集合，共15,695个唯一文件摘要相等，四个离线身份/配对/依赖/check-only进程的退出及树零、EOF、join和资源关闭均成立。根接收 `ROOT-INTAKE-001.json` SHA256 `0f069014e6cfdb8a1c9b64493cde91e36d37564703d25642d73b018fc73fe7d2`。

实际可执行QA仅改独占路径和已接收的Pending处理；SRI004安装、SDK5000、Native12000/26000/5000/3000、总600/晚到65、AAR60000、原128容量、NAP5和136目标保持。正式新配对已核，尚未创建Journal、FIELD-GUARDS或现场启停标记；来源/业务进程/界面及金融命令均0。旧24项成功结果和原失败完整保留，旧未知请求不重放。晚到65秒是验证常驻等待的测试条件，日常系统连接按原resident生命周期运行。

该接收仅授离线可执行材料资格。用户当前关闭QMT，待用户重新打开后由根重新核现场、独占策略及保护进程身份，再安排实际只读运行；当前没有真实136次回收、v4回收或新连接资格。操作顺序沿同目录 `ROOT-OPERATIONS.md`，原失败和晚收尾保持。

## 真实field001及离线QA修正

根已独立接收离线诊断/QA修正，收据为 `build/root-sri004-aar-diagnostic-001/ROOT-ACCEPTANCE-001.json`，SHA256 `082e64078e12ca512161885d55d9c174da6dda207f374ebc35adfd1bb490a56b`。25项冻结输入当前摘要相等，原补丁仅把SDK已有暂缺状态交回原截止内轮询；Windows独占句柄回归的exit0、整树/EOF/join/资源关闭已核。接收范围为离线修正，field001失败、真实回收及原停止窗口缺口保持；当前用户关闭QMT，后继仅离线准备。

2026-10-31根使用SRI004相同安装Host15/Agent11/Native006、显式60000ms回收配置及原128容量，实际运行独占 `build/root-sri004-aar-real-read-001`。SDK5000、Native12000/26000/5000/3000及总600/晚到65秒预算保持，NAP刷新5秒、浏览器关闭，execution与金融写关闭。原15611固定输入及ready绑定已核，根源端启动见证保持。该轮继续失败，未授跨容量或真实回收资格。

完整冷审和修正交付为 `build/root-sri004-aar-diagnostic-001/DELIVERY-001.json` SHA `4c397d3f90df367527974b9440690408e5547e6ddbb9306ee5439333baa938f1`。确认首因在独占QA main.py:139直接读取publication，原SDK将首stat前Windows错误32映射为可等待CollectionStatusPending，新增持续采样未处理该状态。实际占用冲突句柄的进程未知，原Host/Native未观察到首个失败，不据此修改WT或存储组件。

原v3冷库24个请求，position/order/deal/account各6，全成功且consumed；UUID/ticket/请求和结果身份、5000ms、绑定、Host epoch和运输代际已逐一核对。QA捕获2扫描/8结果，最后现场采样占用20/128、awaiting_ticket_end20、unknown/awaiting_consumer均0；关闭期间完成的额外请求不追认为首错前已捕获。3份完整发布逐值核201事实、117ABI、78对浮点位，2份HTTP投影相同；v4实际读取和金融命令均0。目标136及票据结束后原行回收尚未观察。

WT/App及六组件正常退出0、全部树/EOF/join/资源关闭；业务控制器退出1，根包装50612退出2。根在原60秒等待结束后才实际停止Probe并恢复规定原文SHA35d020…，晚收尾单列，未补授原停止窗口成功。原失败、Journal及原ID保持；根恢复见证和 `ROOT-FIELD-OUTCOME-001.json`（SHA `f10834d37bea7577fcbddb22a9cc1844613e43865db578f71f410a7fd72a1141`）记录实际边界。原四采集PID与创建时间已在根会话核对相同，该冷审包未补造停止后机器快照。

离线QA后继统一处理原两个暂缺类型并返回等待，沿原绝对D继续；坏JSON等真实错误继续拒绝，领域分支AST相同。实际Windows独占句柄复现原红/候选绿、释放后可读，持续冲突按原测试D结束；隐藏Job回归exit0、树零/双EOF/join/资源关闭。首次断言脚本下标错误及原失败收据保持。产品、WT框架、旧QA/Journal修改0，诊断新增来源/金融调用0。

用户随后要求关闭QMT并先处理其他任务，真实查询、界面和自动启动暂缓；仅准备新的独占可执行QA和离线材料。下一现场窗口须待用户重开确认，核当前Probe/编辑器和进程身份后由根安排；原24成功不替代后继136/回收/停止验收，也不授v4、跨日或生产。

## 已运行的完整主路径

`main008`使用普通安装Host a15 / Agent a11，实际CPython 3.6.8执行正式strategy_tick正文，经Windows共享内存连接v3账户与v4混合交易Host，再由原生Common、原Standard Factory/SPI和原AccountScan/Adapter消费。原生80查询、标准插件40查询、扫描4查询，共124次账户SDK替身调用；金融写调用0。原容量8，实际观测高水位均为2；一个原timer、原SDK线程、禁用文件/网络入口触发0。两个Host、来源及外层进程树、管道、句柄均正常关闭。实际源为合成SDK，未连接真实QMT。

主路径绑定Native004。最终Native005保留相同Common行为，仅在两个既有账户查询字节计数枚举中补齐新增receipt票据string；全部受影响消费者同批重编，来源和产物身份逐项登记。该差异通过源码/构建身份及最终默认回归复用主链，未将Native005描述为另一次124查询运行。

## 必要恢复与保留验证

`recovery001/run003`包含v3/v4各六例：消费确认503、确认断开、operation_interrupted、lookup404、lookup410及删票据。前两例沿同ID/同原截止lookup后确认，只有一次提交；unknown和缺失结果保留原receipt，unknown零确认，删票据被拒绝。该QA链接Native004原八个Common对象，SDK调用0，实际Host业务未运行，HTTP使用明确替身。全部端口和进程资源正常关闭。

`defaults002`直接加载最终Native005的QA控制库，覆盖原31个账户控制场景及测试夹具生命周期，正常结束。`host/REGRESSION-002.json`固定131项Host/Agent回归：固定容量持续读、原默认路径、旧金融Journal启用和重开、交易命令/事件逐行不变、ORDER金融证明保留及后继自然更新等。Host纯回归、实际3.6.8SDK主链和Native恢复替身分别标识其资格。

## 制品及边界

`packaging/INTERFACE-001.json`固定全新普通WT角色安装：23个发行，替换Host a15、Agent a11，其余21个wheel保持；安装执行离线依赖检查、RECORD与隔离导入。最终Native组件、账户/历史工具及来源证明由独占Native包装接口交付，保留P26标准插件原代码。

早期QA参数、配对和最终遥测失败原件保留，成功结论分别绑定上述实际完整运行。真实QMT、开市金融操作、Source冷重启、跨日及生产资格尚未取得；本模块独立审查由根会话安排，结果独立于这些运行记录。

## Native006资源顺序后继

首次独立Standards/Spec审查均发现同一P1：UUIDv5的CNG hash仍使用backing内存时，局部vector已经释放。原Native005及首次接口保持冻结，该候选的生命周期验收被阻断。Native006只将该段改为同一RAII owner持算法、hash和vector，析构体先销毁hash再关闭算法，成员缓冲随后释放；UUID编码、请求、业务截止及Host/Agent代码保持。

`cng-red001/run`和`cng-green001/run`直接编译各固定快照的实际Core翻译单元，通过原CNG API观测成功、HashData失败、Finish失败和异常退出。旧版四例均观测delete在destroy前；新版四例均为create→destroy→close→delete，固定UUIDv5相同。红例仅在QA中延迟物理free，以保存真实调用次序并安全完成原CNG清理。

Native006全部受影响自有消费者同批重编。`main009`沿原公开完整夹具只将Common和Factory各缩为一轮，正式3.6.8/单正文/WinSHM→Host15/Agent11→原Native完成16次SDK查询：Common8、标准Factory/SPI4、Scan4；全部正常退出，输入前后相同。`defaults003`对最终库再运行31个原场景及夹具生命周期；`recovery002/run001`对最终Common再运行原12个同ID恢复场景。首次124次运行继续仅证明其实际版本及未变化协议/回收部分。

后继交接使用本根`INTERFACE-002.json`、`REVIEW-INPUTS-002.json`和`native-packaging/final002`，首次所有报告与制品保持原件。完整新SRI、实机及生产范围继续独立验收。
