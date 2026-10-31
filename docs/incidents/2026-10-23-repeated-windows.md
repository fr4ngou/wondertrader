# 2026-10-23 开发验证期间反复弹窗

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：故障记录。状态：investigating。环境：Windows 本地开发；协调：当前迁移任务。用户报告反复弹窗，随后明确为“黑色命令行窗口一闪而过”。窗口所属程序、进程和触发链待核实。

## 症状与保护动作

用户确认弹出的是一闪而过的黑色命令行窗口；该描述作为控制台窗口排查线索，尚不足以确定所属进程。停止新增编译、测试、客户端、浏览器和诊断进程启动；后台三个开发与审查 Agent 已确认结束。保持国信 QMT 运行状态和账户设置。当前仅使用已存在的 Node 工具读取文件、核对源码并保存记录。

此前保留的 Python 构建进程句柄记录显示 PID 39960 已退出、exit code 为 0、OS handle 已释放。这份记录覆盖该句柄；其他进程和现存窗口尚未清点。

## 证据与根因

弹窗的 HWND、所属 PID、标题、内容和发生时刻尚缺少对应证据，根因保持 unknown。现有源码和历史崩溃记录不足以确认本次弹窗来源。

本轮对七个明确入口进行文件级核对：原生构建驱动、隐藏构建入口、构建 Job、两个历史测试脚本、应用受管 Job、账户读取原生入口。最新身份和定位保存在 `build/guanheng-workspace/popup-launch-static-20261023-001/source-refresh-20261023.json`，SHA-256 为 `fc2663b26d3dd9747e93fa0afea93cd205e99ec31c0fa636d75d680182c96912`。

早期 `inventory.json` 曾列出两个未隐藏启动入口；当前 `tests/integration/qmt_readonly_bootstrap/build.py` 与 `tests/integration/qmt_http_bootstrap/cng_lifetime.py` 的对应 subprocess 调用均传入 `native.background_process_options`。两份脚本的当前摘要与早期记录不同，早期观察保留其历史语义。当前隐藏参数的存在只能证明源码意图，实际窗口表现尚未验证。

## 时间线与修复

1. 用户报告反复弹窗；停止运行验证和新增进程。
2. 核对后台 Agent 均处于 completed 状态。
3. 读取既有证据并复核当前启动源码，纠正早期入口清单的适用范围。
4. 本轮未修改产品实现、构建脚本或 WonderTrader 框架。未启动任何新诊断程序、测试或编译。

## 恢复与验真

运行验证继续暂停。弹窗是否已经消失、是否存在此前残留进程，以及具体触发链均未验证，事件保持 investigating。项目 start/check、编译和回归未执行；静态核对不构成恢复或功能验收。

## 后续动作

由当前迁移任务继续负责关联弹窗窗口与进程身份；在明确来源后确定责任层修复及有界验证方式。保持历史证据，避免通过反复重启、重跑或修改 QMT 实例掩盖来源。整体迁移目标仍未完成。


## 后继：当前构建入口扩大静态清点

在新增进程继续暂停的条件下，静态读取scripts目录16个脚本，登记18处创建调用并保存7个来源文件。既有native入口8处已传隐藏选项；当前使用路径另有5处遗漏：固定WT Git对象探测1处、账户包编译器/CMake/Ninja版本探测3处、客户端wheel构建1处。旧qmt-readonly-fixed flow的3处、旧终端HTTP qmt_connector的1处及上游copy脚本1处分别按退休或上游边界保留原样。该清点只覆盖scripts及声明深度/文件预算，不是全部系统进程清单。

清点原件（外部历史/待归仓路径：`../../build/guanheng-workspace/popup-launch-static-20261023-002/inventory.json`） SHAdef5f844c2f173780c619ac3e6c96d760d4956aa3018174608b5e26a849fed1f；历史七入口核对保持原适用范围。新发现确立了构建创建选项缺口，没有取得实际闪窗的HWND/PID/时刻对应，事故根因仍unknown。

修正候选startup003（外部历史/待归仓路径：`../../build/guanheng-workspace/native-background-startup-003/review-package/review-input.json`） SHA8cbc133f00af0b10f3242cf8e9abc7ea3c8cdba1ab815db587017c3c27d00192，manifest 1f2a455679db721e271704d1719bfd63b5e68a3d89c746003c464ecda6c51b7e：原选项函数原逻辑搬到唯一工具owner，native公开别名保留，5遗漏共用同一策略；6个纯替身定义不生成实际进程。8项staged未apply，交另一作者独立full，261来源/6before/269制品。初始002含旧HTTP连接器的分类已撤回，002冻结且不审不apply；最终003明确排除该退休改动。

当前没有运行或证明任何窗口行为，没有恢复编译/测试/浏览器。候选静态审查、Windows窗口实际表现、完整进程树回收及业务运行分别验收；安装/真实终端和账户状态保持。


## 后继：五处当前入口静态修正落地

startup003独立full静态complete、无新增发现；报告（外部历史/待归仓路径：`../../build/guanheng-workspace/native-background-startup-static-review-001/REPORT.md`） SHA1987fa50b4a31281f0f64cca6d32f55517f692a6829dc3d724828000bacf1d4c，manifest 0e4b724097964530b3185c4ec3c35e58cf28c943eab735282dbc13ffca0aaef2。根核278制品后落8项，261源和额外无副作用包init匹配；应用回执（外部历史/待归仓路径：`../../build/guanheng-workspace/native-background-startup003-apply-001/apply.json`） SHA7f9c29c019a288c83181acc99908800b50d4ae4dc4679b4dc707c2c04a7cd63e。

当前源码已统一窗口创建选项owner并补5处遗漏，完整函数逻辑保持原样；旧HTTP/退休flow/上游copy和WT框架未改。原native.run与其Job/输出/等待/退出/日志保持原代码，未增加父死亡或完整进程树回收资格。6个隔离替身定义只登记待执行；实际Windows选项、窗口和子进程行为未运行。

事故状态继续investigating。实际窗口HWND、PID、标题与发生时刻仍未关联；不能将本次源代码修正视为历史闪窗根因已查清或已消失。新增进程/诊断/解释器/编译/测试/网络/SDK/浏览器继续暂停，运行实例和账户保持。

### 后继：003最终静态复核闭合，等待明确恢复范围

独立delta002（外部历史/待归仓路径：`../../build/guanheng-workspace/window-validation-resume-static-review-002/REPORT.md`）已完整封存，结论complete-static-delta；WVR-F1/F2/F3/C1全部closed-static，无新增发现。报告SHA b027bdcde6953741b9e330fc94c5dbd8a5d5635ec088a6cc88e095c7aa0ca90f，manifest c515dd95b1f7ec9346cbd0cd8d110cf94881a1a343c7447c74b8b64e6454a146。根核38审查制品、24候选制品及18当时current来源匹配，见根核回执（外部历史/待归仓路径：`../../build/guanheng-workspace/window-validation-resume-root-001/delta-integrity.json`），SHA540de1d38e5738e15d47b7e1d2c8e64408fb3f97ecf86ce444f79e32932760b4。

固定003操作（外部历史/待归仓路径：`../../build/guanheng-workspace/window-validation-resume-003/PLAN.md`）已足够具体，已向人类询问恢复范围，选项为受控隐藏验证、仅一次20秒只读诊断或保持运行暂停。恢复授权尚未取得；自动目标续接或本记录不能代替真实答复。先核实际答复，再按原封存entry及launcher SHA进入明确scope。仅诊断为测试0；受控范围先20秒观察，正常后九项纯替身，再按实际收口结果继续必要隐藏回归/构建/只读联调。任何窗口、错误、未知或超时停止新启动。

本段是静态复核闭合和待人类范围确认；实际模块加载、Python版本、WinAPI/采样、九项结果、来源归因和全部产品运行资格继续unknown。零事件采样不关闭历史闪窗根因。所有新进程、解释器/import、语法、测试、编译、网络、SDK、浏览器及CI仍0；QMT运行现状保持，账户schema2仍关闭，完整业务目标active。后继状态文档更新不改变封存诊断执行源码或旧报告。

### 后继：人类授权恢复受控隐藏验证，首次诊断通过

用户明确答复“恢复受控隐藏验证（推荐）”（questionItemId call_632668e5e2034a38ad79ce9b3ade629a/0）。原进程启动暂停按此固定范围解除：先执行已审003，后续逐步进行必要隐藏回归/构建/只读联调；窗口、超时或异常先停止该轮并调查，QMT现状与原交易/生产授权边界保持。自动目标续接仍不替代真实人类授权。

实际GUI child PID38428，原20秒hook采样完成、own_console=false，baseline1个现有控制台，新匹配events=[]、errors=[]；九项纯替身全通过，失败/错误/skip0。parent实际close、exit0、signal null、空stdout/stderr、源码后核匹配，elapsed22.024秒，active owner已释放。实际开始UTC2026-10-23T07:57:17.758Z，结束07:57:39.787Z。此结果只证明本次有限观察和九项纯替身，不关闭历史闪窗归因，不授产品、账户或真实SDK资格。

采样结果（外部历史/待归仓路径：`../../build/guanheng-workspace/window-validation-resume-003/runs/748881ee-e5ae-4c00-8e97-560dcb1835d2/result.json`） SHAbe410f2b9c94f4f4bae665001cee9bb09ea1d9223d64a2dcf5095415fb460bdd；父端回执（外部历史/待归仓路径：`../../build/guanheng-workspace/window-validation-resume-003/runs/748881ee-e5ae-4c00-8e97-560dcb1835d2/parent-receipt.json`）保留真实授权与关闭事实。接续先验当前Python/账户软件，再执行有界原生构建与组合链；账户schema2继续关闭。
