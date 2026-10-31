# 2026-10-23 后台编译与测试窗口

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：故障与验证记录。状态：开发入口已修正，实际弹窗类别仍待确认。

## 原因及实现

用户报告开发期间反复弹窗。已查见部分编译和测试通过普通 Windows 子进程入口启动，没有显式指定无控制台；隐藏父窗口、加入 Job 均不能替代每个子进程的创建选项。这条路径具有控制台闪窗风险。程序错误框或权限框的来源尚未获得对应窗口证据，本记录保持该边界。

`scripts/native.py` 集中提供 `background_process_options()`：Windows 使用 `CREATE_NO_WINDOW` 和 `STARTF_USESHOWWINDOW/SW_HIDE`，受管命令保留原有 suspended → Job 绑定 → resume 次序；编译环境探测、工具身份及 Git 子命令也使用该入口。历史 Reader 合成链的两个直接子进程显式使用 `CREATE_NO_WINDOW`。历史 C++ CLI 和上游执行器对照的各自测试入口由其作者逐级核实。

根任务的顶层命令通过 Node `execFile/spawn` 的 `windowsHide: true` 启动。需要创建控制台的真实 CtrlBreak 测试单列手工场景，普通自动化批次不再运行它。上述变化均位于自有工具或测试，未改 WonderTrader 框架。

## 验证

实际执行 `tests/build_pipeline/test_native_background.py` 两项回归：受管命令、显式后台父子进程均返回 `GetConsoleWindow() == 0`，stdout 完整、退出码 0，Job 回收完成。最新一次两项通过，0.464 秒，输出保留于 `build/guanheng-workspace/background-window-check-001/latest-test-output.txt`；各实际命令日志在同目录的独占 UUID 子目录。

这两项证明已覆盖入口的控制台创建行为，其他入口仅在其闭包核实后恢复动态执行。原本停止的 Agent 没有因此自动获得新建可见控制台测试的许可。

## 后继：构建器间接子进程

进一步核实本机Ninja版本为1.13.2；其[对应官方源码](https://github.com/ninja-build/ninja/blob/v1.13.2/src/subprocess-win32.cc#L97-L104)创建普通命令子进程时设置进程组，未替后代设置NO_WINDOW。因此前两项直接子进程检查不能外推到完整编译链。当前尚未获得用户实际弹窗类型，本段只修正已确认的工具启动覆盖缺口。

自有`native.run(..., private_console=True)`以SW_HIDE建立构建driver专属隐藏控制台，`background_process_options`识别现有隐藏控制台并让后代继承。普通直接命令继续使用NO_WINDOW，可见用户终端的控制台保持原状。新增`scripts/native_support/hidden_build.py`要求入口已经属于外层Job；外层创建时绑定、同一总截止、内存/管道限制及父死亡回收仍由调用方负责。该bootstrap内部启动构建driver，原环境发现、CMake和Ninja继续在同一隐藏console及外层Job内，不推断NO_WINDOW自动继承。

四项实际回归全部通过，0.988秒：原两项直连、普通CREATE_NEW_PROCESS_GROUP后代、**本机真实Ninja rule**。后两者均观察到console存在且`IsWindowVisible == false`，stdout与退出码保持正确；Ninja使用普通命令池，未运行手工CtrlBreak或可见控制台测试。原件`build/guanheng-workspace/background-window-check-001/deep-test-output.txt`。后继独立工具审查进行中，编译器自身内部派生与故障报告窗口不由此一次普通Ninja规则无限扩授。

上述工具变更晚于QH C++ d1d候选构建。9个QH产品源码及安装EXE/CRT保持原摘要；独立C++审查已先核1791原件，并保存原构建工具`native.py` SHA `253ca4115c59222b28f1b1ec2fc0509649df6173fab4cb0f9403f7b92769c351`快照。当前工具的后继身份与该已编译候选的来源分别登记，旧制品没有重新编译或被替换。

## 后继：独立审查与显示编码

独立full已封存于`build/guanheng-workspace/background-window-review-001`。21项主矩阵中20项完成，剩余F1/P2为默认GBK显示失败：子命令实际exit0、UTF-8全文日志存在，但输出尾部含U+FFFD时展示抛编码异常，bootstrap误报exit1。普通后台命令console=0、私有driver及真实Ninja后代不可见、既有外层Job的期限/内存/输出/父死亡回收按报告范围通过；实际无Job环境及可见用户终端未动态执行。根任务已逐项核203份封存原件，零漂移。审查入口SHA `65e50b677cb2505e84640ea6f307c2134f2c526de27007bbbdb9da67f3f22367`。

F1后继候选在自有`native.display`统一按目标stdout/stderr编码展示；无法编码字符用反斜线转义，完整UTF-8文件、子命令退出状态及真实写入错误保留。命令展示、输出尾部和外层结果/错误使用同一边界。已新增六项回归定义，覆盖GBK成功、原失败原因、UTF-8全文、独立错误流、无编码流及真实写入错误。当前仅实施与静态检查，尚未执行后继回归，F1运行资格保持待验证。候选身份及原源码见`build/guanheng-workspace/background-window-fix-002/candidate.json`，独立静态delta另行收口。

用户再次报告弹窗后，暂停新编译、测试和浏览器启动。本轮后继检查仅读写文件；静态证据整合任务确认没有活动自有子进程。实际弹窗类别仍未取得逐窗口身份，既有Ninja隐藏不足与GBK误报分别记录，不能将两个发现混作同一现场原因。

## 后继：小型隐藏回归

独立静态delta已核18份原件，无新增静态发现。随后恢复仅小型软件验证，未启动编译、Ninja、浏览器或券商终端。原源码的两项GBK命令显示回归原样失败；新候选六项通过，启动器实际console=0、visible=false、stdout编码GBK，完整UTF-8日志及原退出7保留。首次新测试中一项将Windows默认CRLF误作LF，已仅在测试流显式设置newline，产品不变；原失败原件保留。

作者原件见`build/guanheng-workspace/background-window-fix-002/verification.json`及`candidate-final-result.json`。后继独立行为delta另行封存，尚未以作者通过替代独审。此前“仅静态、尚未执行”为该阶段观察；本段登记后继小型测试资格，不恢复大型动态批次。

## 后继：显示软件delta关闭

独立行为delta（外部历史/待归仓路径：`../../build/guanheng-workspace/background-display-delta-review-001/REPORT.md`）已complete，11项场景通过，F1在显示软件范围内关闭。实际默认stdout/stderr均GBK且utf8_mode=0，命令及输出尾部正确转义；子命令exit0/7、完整UTF-8日志、TimeoutExpired、真实断管及单独flush故障均保持原语义。顶层与worker实际console=0/visible=false，创建时Job归属、自然收口和管道排空通过。

审查入口SHA `3904b6b39a762afaac488390072fddbb197dc3910b7d6306d721b62c1a815a35`，33原件manifest SHA `dc610a5e902ab968fedf525625635a90a24ebb5031317d99da6bf4115848aee3`。根任务逐项重核33份原件及当前两份源码身份，差异0；收口记录（外部历史/待归仓路径：`../../build/guanheng-workspace/background-window-fix-002/closure.json`）。原窗口/Job机制按相同源码复用此前full对应证据；大型编译/Ninja/浏览器批次继续暂停，实际无Job/可见用户终端及任意第三方GUI的未知范围保持。实际用户弹窗类型仍未逐窗口对应，此项不授任意弹窗已消除的结论。

## 后继：再次投诉后的静态盘点

本阶段停止全部新进程启动，仅读写文件及读取既有ChildProcess句柄属性；句柄pid39960现exitCode=0、signalCode=null。该观察证明该句柄对应进程已经退出，不证明本机所有进程或窗口已经消失。当前没有取得用户弹窗的HWND、PID、类型或时间对应证据，现场根因保持unknown，未恢复动态复现或宣称修复。

静态盘点确认旧tests/integration/qmt_readonly_bootstrap/build.py的Git/编译器调用及tests/integration/qmt_http_bootstrap/cng_lifetime.py的编译/探针调用仍含未显式传窗口选项的subprocess入口；这是未覆盖入口风险，不能据此认定本次弹窗由它们触发。现有native.py统一隐藏入口及此前受限证据保留其原范围；这两个旧脚本继续停用。库存源码摘要及行号保存在build/guanheng-workspace/popup-launch-static-20261023-001/inventory.json；本阶段没有启动编译、测试、浏览器、网络或SDK，也没有操作运行国信QMT。


## 后继：已有Windows错误报告静态核对

仅用文件API读取4个默认WER目录；系统Queue有5个Kernel目录，系统Archive共278个目录名，其中18个名称匹配开发程序，按文件mtime取最近8份有限Report.wer的白名单元数据。用户级两个默认目录不存在。本次实际读取的报告有Python、probe及WtRunner较早崩溃，最新匹配事件时间为2026-10-22 08:43:30 UTC，仍无对应用户本次窗口的HWND/PID/时间证据。记录不能证明当时显示了窗口，也不能排除未留WER的控制台闪窗或其他来源。

原件路径、所读报告SHA及范围见build/guanheng-workspace/popup-launch-static-20261023-001/wer-static-inventory.json与wer-relevant-reports-static.json；未复制内存转储或原始私有报告。系统Archive初次metadata检查限256，后继相关报告选择已覆盖全部278个目录名并对18个匹配项取mtime。没有启动诊断程序、读取活动窗口/进程、编译、测试、浏览器、网络或SDK，实际弹窗归因保持unknown。


## 后继：暂停后静态补查当前工具入口

重复闪窗事件仍在[调查](../incidents/2026-10-23-repeated-windows.md)，新增进程继续暂停。扩大静态清点识别当前工具5处创建调用未传现有窗口选项；原native函数内的8处选项不覆盖这些独立调用。静态候选将选项owner收敛为native_support.process_startup并保留native公开入口，修正Git/账户版本探测/客户端wheel的5处遗漏；旧终端HTTP、退休flow及上游copy脚本不改。

最终startup003审查入口（外部历史/待归仓路径：`../../build/guanheng-workspace/native-background-startup-003/review-package/review-input.json`） SHA8cbc133f00af0b10f3242cf8e9abc7ea3c8cdba1ab815db587017c3c27d00192，8项未apply，独立full进行中。6项纯替身只是定义，语法/import/收集/执行均0。候选未证明历史闪窗实际来源或隐藏效果；旧已运行记录仅覆盖其绑定来源，新唯一owner与所有受影响安装/入口需后继实测。


### 后继：startup003静态闭合与源码落地

独立full已complete-static，报告（外部历史/待归仓路径：`../../build/guanheng-workspace/native-background-startup-static-review-001/REPORT.md`）无新增P1/P2/P3；根核278原件后应用8项，261主源及额外包init post匹配。唯一选项owner、native公开alias和当前工具5调用已落源码，应用身份见回执（外部历史/待归仓路径：`../../build/guanheng-workspace/native-background-startup003-apply-001/apply.json`），SHA7f9c29c019a288c83181acc99908800b50d4ae4dc4679b4dc707c2c04a7cd63e。

6个纯替身测试、实际Windows窗口、子孙进程/Job、构建安装及业务链均未执行。原控制台选项函数完整逻辑保持，native.run/display/environment/source_identity主体保持；旧通过记录继续只授其绑定输入。闪窗实际归属unknown，动态暂停保持，详见[事故后继](../incidents/2026-10-23-repeated-windows.md)。

## 后继：恢复验证诊断准备，尚未执行

本轮继续使用既有Node的文件/摘要API，新增进程、模块导入、语法检查、测试、编译、网络、SDK和浏览器均0。目标保持active；实际闪窗的HWND/PID对应及触发链仍unknown。

已准备私有build诊断父端与观察器。002完整独立静态审查封存为gap-static，3项P2分别涉及现存Node宿主不支持node:process、墙钟回拨延长预算、准备耗时误计完整hook观察；另有晚到close后准入槽释放P3。根核29制品、入口及报告一致，见完整审查（外部历史/待归仓路径：`../../build/guanheng-workspace/window-validation-resume-static-review-001/REPORT.md`）与根核回执（外部历史/待归仓路径：`../../build/guanheng-workspace/window-validation-resume-root-001/full-integrity.json`）。原002保持冻结，未运行。

后继003具体操作（外部历史/待归仓路径：`../../build/guanheng-workspace/window-validation-resume-003/PLAN.md`）及唯一输入（外部历史/待归仓路径：`../../build/guanheng-workspace/window-validation-resume-003/review-package/review-input.json`）已封存，entry SHA bf37b08c3267e33601699fab2a3e12db31f8b665c2cfce98b41c290945d0be13，manifest 7b78a63542383259394ff49c5634fe1d07aacf04ad2f5efa44e286c9995a638b。18来源/24制品及实际GUI EXE静态身份匹配，独立delta进行中。固定GUI解释器的pyvenv声明3.12.14，EXE SHA31f94a3e52c47c4c8ed22433f9689cce29584ba93381f4a18d6c881ce6e79a4e；尚未执行确认版本或整个环境。

新候选移除node:process依赖，由诊断自身限定隔离temp；相对预算使用performance.now；hook成功后另起完整20秒窗口并要求实际进入消息循环，父端30/35秒继续覆盖全过程；晚到close仅在原调用返回后核同owner释放，无自动重启。六项创建选项与新增三项采样纯替身共九项仅有定义。诊断只读窗口类/窗口owner PID/程序basename/时刻，不取标题、命令行、环境、屏幕或账户；新事件/错误/未完成观察即停止，不操作外部窗口或QMT。

独立delta及直接人类恢复范围尚未确定，运行暂停保持。此方案不是实际闪窗根因证明；即使之后采样无事件，也只覆盖指定类与采样区间。诊断不进入产品安装，产品schema2继续关闭，真实账户/交易、历史覆盖及完整业务发行资格分别待验。

另核三个共享文档/CI后继来源链（外部历史/待归仓路径：`../../build/guanheng-workspace/source-apply-chain-audit-20261023-001/result.json`），前后摘要连续且最后版本匹配live；个人观察原回执后的三项差异由已登记来源/Frame后继应用形成。已校正[当前接入决策表](../migration/decisions.md)四行旧状态，历史论证后缀保持原bytes，19本地链接存在。项目start/check因当前运行暂停未执行。

### 后继：003最终静态复核闭合，等待明确恢复范围

独立delta002（外部历史/待归仓路径：`../../build/guanheng-workspace/window-validation-resume-static-review-002/REPORT.md`）已完整封存，结论complete-static-delta；WVR-F1/F2/F3/C1全部closed-static，无新增发现。报告SHA b027bdcde6953741b9e330fc94c5dbd8a5d5635ec088a6cc88e095c7aa0ca90f，manifest c515dd95b1f7ec9346cbd0cd8d110cf94881a1a343c7447c74b8b64e6454a146。根核38审查制品、24候选制品及18当时current来源匹配，见根核回执（外部历史/待归仓路径：`../../build/guanheng-workspace/window-validation-resume-root-001/delta-integrity.json`），SHA540de1d38e5738e15d47b7e1d2c8e64408fb3f97ecf86ce444f79e32932760b4。

固定003操作（外部历史/待归仓路径：`../../build/guanheng-workspace/window-validation-resume-003/PLAN.md`）已足够具体，已向人类询问恢复范围，选项为受控隐藏验证、仅一次20秒只读诊断或保持运行暂停。恢复授权尚未取得；自动目标续接或本记录不能代替真实答复。先核实际答复，再按原封存entry及launcher SHA进入明确scope。仅诊断为测试0；受控范围先20秒观察，正常后九项纯替身，再按实际收口结果继续必要隐藏回归/构建/只读联调。任何窗口、错误、未知或超时停止新启动。

本段是静态复核闭合和待人类范围确认；实际模块加载、Python版本、WinAPI/采样、九项结果、来源归因和全部产品运行资格继续unknown。零事件采样不关闭历史闪窗根因。所有新进程、解释器/import、语法、测试、编译、网络、SDK、浏览器及CI仍0；QMT运行现状保持，账户schema2仍关闭，完整业务目标active。后继状态文档更新不改变封存诊断执行源码或旧报告。

### 后继：人类授权恢复受控隐藏验证，首次诊断通过

用户明确答复“恢复受控隐藏验证（推荐）”（questionItemId call_632668e5e2034a38ad79ce9b3ade629a/0）。原进程启动暂停按此固定范围解除：先执行已审003，后续逐步进行必要隐藏回归/构建/只读联调；窗口、超时或异常先停止该轮并调查，QMT现状与原交易/生产授权边界保持。自动目标续接仍不替代真实人类授权。

实际GUI child PID38428，原20秒hook采样完成、own_console=false，baseline1个现有控制台，新匹配events=[]、errors=[]；九项纯替身全通过，失败/错误/skip0。parent实际close、exit0、signal null、空stdout/stderr、源码后核匹配，elapsed22.024秒，active owner已释放。实际开始UTC2026-10-23T07:57:17.758Z，结束07:57:39.787Z。此结果只证明本次有限观察和九项纯替身，不关闭历史闪窗归因，不授产品、账户或真实SDK资格。

采样结果（外部历史/待归仓路径：`../../build/guanheng-workspace/window-validation-resume-003/runs/748881ee-e5ae-4c00-8e97-560dcb1835d2/result.json`） SHAbe410f2b9c94f4f4bae665001cee9bb09ea1d9223d64a2dcf5095415fb460bdd；父端回执（外部历史/待归仓路径：`../../build/guanheng-workspace/window-validation-resume-003/runs/748881ee-e5ae-4c00-8e97-560dcb1835d2/parent-receipt.json`）保留真实授权与关闭事实。接续先验当前Python/账户软件，再执行有界原生构建与组合链；账户schema2继续关闭。

### 后继：恢复后的账户软件与自有 Job 绑定回归

实际已有 venv 为 Python 3.12.14。账户两文件原运行150通过/2失败，原因分别是测试中的旧2/43登记断言，以及Windows对合成RECORD执行二次换行转换；产品身份核验实现保持。修正后152通过，exit0、own_console=false、源码后核一致。原始轮的stdout/stderr曾由Node var闭包合并到stderr文件，内容完整而流归属丢失；解释回执（外部历史/待归仓路径：`../../build/guanheng-workspace/account-resumed-software-001/log-interpretation.json`）保留该限制，后继使用const独立流。

两测试独立静态delta（外部历史/待归仓路径：`../../build/guanheng-workspace/account-fixture-regressions-static-review-001/REPORT.md`）complete、无新增发现，33制品逐项根核一致；根核回执（外部历史/待归仓路径：`../../build/guanheng-workspace/account-fixture-regressions-root-001/result.json`）。新账户登记仍为45项中的3 implemented-unverified/42 pending，原生45项实际执行0；152个纯替身结果不提升原生或真实账户资格。项目start/check实际执行通过，Git状态保存于build/guanheng-workspace/resumed-project-workflow-001/git-status.txt，保留原dirty树。

原生构建预检发现自有strategy_job.py的UpdateProcThreadAttribute ctypes声明遗漏第七参数PSIZE_T。实际失败在CreateProcess之前，原调用栈（外部历史/待归仓路径：`../../build/native/account-scan-resumed-001/control/warmup-diagnostic/result.json`）保留。按[微软七参数ABI](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)补齐声明与中文注释；纯WinAPI替身增加声明参数数量校验，原声明复现18失败/5通过。扩展测试另查见lease故障替身对每个新实例重复故障，已限制首轮原owner并核后继lease正常关闭，产品host逻辑保持。

修正后39软件回归（外部历史/待归仓路径：`../../build/guanheng-workspace/process-job-abi-green-002/receipt.json`）全部通过；真实创建成功/API返回前中断（外部历史/待归仓路径：`../../build/guanheng-workspace/process-job-abi-real-001/receipt.json`）三场景通过，分别KeyboardInterrupt/SystemExit/RuntimeError，实际句柄净增0及原owner回收断言通过。仅本机受控源环境资格，正式安装与完整宿主矩阵另验。修正已送独立限定静态审查。

真实隐藏构建暖机（外部历史/待归仓路径：`../../build/native/account-scan-resumed-001/control/warmup-fixed/result.json`）exit0，member_before_resume=true，隐藏console存在且不可见，整树零、管道EOF/线程join及资源关闭均确认。新的原生账户profile在独占目录以单线程、2GiB Job总内存及300秒总预算离线构建；当前尚未完成，不能授编译或14帧单元资格。以上不关闭历史闪窗归因，不涉及旧QMT执行、WT新增框架修改、终端重启或交易。

### 后继：自有ABI独审关闭、原生构建与开发包搬迁通过

ABI独立静态delta（外部历史/待归仓路径：`../../build/guanheng-workspace/process-job-abi-static-review-001/REPORT.md`）complete、无新增发现；25制品及14当前final来源根核0漂移，根核原件（外部历史/待归仓路径：`../../build/guanheng-workspace/process-job-abi-fix-001/root-review-integrity.json`）。最终strategy_job.py SHA91cc52596b09d9042d298c8a3c8ed2134fe8fe0c8354b34366fc90fc1689c133。另有来源捕获/双owner关闭/IPC纯回归139通过，账户父端/唯一投影110通过；这些与原152、39和3实际创建中断分别保存，不换算成原生45场景资格。

首轮300秒构建在依赖验证后进入CMake配置触及外层290秒截止，整树零、线程/资源关闭已确认；原件保留。沿缓存开启独立900秒轮，169.844秒完成，编译131.578秒；三个目标均构建成功，无forced，exit0、创建期成员/整树零/EOF/join/关闭通过。原生输出见身份清单（外部历史/待归仓路径：`../../build/native/account-scan-resumed-001/control/build-output-identities.json`），构建使用固定WT提交08b230dd05facf6d650d949bfe51054115a2ecb1及同版owned源码，不采用dirty框架树。

原生FrameWriter 14场景实际通过；独立精确CTest（外部历史/待归仓路径：`../../build/native/account-scan-resumed-001/control/frame-ctest.xml`）保留每项结果与QA exe SHA360179b2fa0ed74d4e2f7018b243706dce487a99fe061a35e2bec90bcf1d4fa0。当前14只授frame-owner-only，不涵盖原main/SDK/SHM/硬抢占。随后canonical test阶段两组CTest和64项工具检查通过。

独立package调用被validate_provenance拒绝：该调用新建receipt没有同次build/native-dependencies/native-link-commands记录，即使现存built-source已匹配，provenance仍缺项。未伪造/拼接收据，旧失败staging保留。现有all全流程已实际执行通过，configure/build/实际编译依赖/链接命令、两组CTest、64工具测试、install、ZIP校验及搬迁均在同一收据。独立阶段间的构建证据衔接仍为工具缺项；当前可验证开发包沿完整all入口生成。

完整流程原件（外部历史/待归仓路径：`../../build/native/account-scan-resumed-001/control/build-all-001/result.json`）exit0、43.234秒、Job整树零/管道排空/线程join/资源关闭确认。开发ZIP dev-account-scan-20261023T084616Z-eba83ab5.zip为2530702 bytes，SHAa22e546c319cbcba41a5b8fd43b320967a6f38b37b97a5d36cbf64c085d0a49f，根再次核ZIP一致。107包成员通过原manifest验证；QA exe留build，不进入产品包。隔离CWD、收紧PATH、包内普通生产DLL及固定原Adapter的23个合成schema1场景全通过，forbidden_calls=0、source_closed/port_closed=true、旧工程运行依赖false。实际原件搬迁摘要（外部历史/待归仓路径：`../../build/native/account-scan-resumed-001/relocation/d9868ff8650345409963c04cb874d603/results/run-5016a2f6-9e41-4cd7-8d7d-1687789c3a39/summary.json`）。

该包为development/synthetic-owned-qts-product-chain；MSVC/UCRT对外再分发许可仍gap。尚未取得schema2双环境独立安装、45原生矩阵、真实QMT账户或中文业务入口的同版资格，新门禁继续关闭，未生产发布。

另静态核对另一对话最新交接与旧Host路由，并对现有18017外部Host仅GET /health，200/available/order_ready=false；没有SDK调用、终端HTTP18010访问、QMT操作或配置修改。其50项只读能力、通用operations协议及旧venv依赖，与本仓bound来源协议的差异和后续步骤已记入[交接核对](../migration/qmt-successor-source-handoff.md)。本轮仍不关闭历史闪窗的现场归因。
