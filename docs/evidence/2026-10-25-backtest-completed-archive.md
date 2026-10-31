# 已完成回测重启只读归档

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。日期：2026-10-25。状态：最终修复后端/前端隔离回归通过；新安装、真实原生回测完成后重启及浏览器用户入口尚待验收。

## 实现与根因

沿[NBW-R6](../specs/native-backtest-workspace.md#nbw-r6-已完成回测只读归档)与[ADR0012](../architecture/adr/0012-backtest-completed-archive.md)，复用原NSH运行目录、冻结请求、原报告及WT输出。Workspace取得原Host真实completed/exit0/reap/join并通过唯一NSB准入后，在原请求截止内发布不可覆盖完成receipt。重启后的历史GET只读原件，归档状态与执行完成状态分开，显式重试只写归档证明，不重新运行Host。

独立full发现：已有receipt认领及历史读取跳过整run容量/类型检查。最终将实际目录项/文件/总bytes检查收敛到统一_capacity，供list/read/新publish/已有证明认领复用；首次新写才预留2项及16KiB，恰好实际额度的只读与幂等认领保持可用。新增outputs外文件、目录、字节增长和硬链接等6个参数化场景。

最终37来源见清单（外部历史/待归仓路径：`../../build/backtest-completed-archive-001/FINAL-002/SOURCE-SHA256.json`），SHA 6abc73a92cc3eae572b92be543e1e275e2bc021a3801c582e44fcda6cdb56959；Archive SHA 34fda5baec5488e458fdaae88d7e9e49115b7265c436e03b50560a75ce42add7。本片不改StrategyHost/runner、WT框架或交易模块。

## 实际验证

| 验证 | 结果与身份 | 原件 |
|---|---|---|
| 新归档及全部原工作区回归 | 59/59；新31、旧28，无skip；198项冻结输入运行后逐字核同 | 结果（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-archive-tests-004/result.json`） |
| 前端类型/五组受影响测试 | 类型通过；5组76项通过，137输入前后核同 | 结果（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-archive-frontend-001/result.json`） |
| 生产SPA与原chunk检查 | 构建及chunk检查均退出0 | 构建日志（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-archive-frontend-001/build.stdout.txt`） |
| 独立full/delta | 容量P2静态关闭，开放P1/P2=0，执行0 | full（外部历史/待归仓路径：`../../build/backtest-completed-archive-independent-review-001/REPORT.md`）、delta（外部历史/待归仓路径：`../../build/backtest-completed-archive-independent-review-001/revision002/REPORT.md`） |

首次两次53例运行均51通过、2个V2失败：根冻结驱动依次缺模块路径、包内固定上海时区数据；已沿异常链确认并补齐冻结输入，产品及V2测试未为此更改。第三次59通过但根驱动误记录0项输入；第四次增加198项强制计数并完整复验。原失败和记录缺口保留。Vite提示未来native configLoader对无扩展名import的兼容警告，当前构建通过；本片未掩盖警告或改工具链。

根复核37份审查原件，见复核记录（外部历史/待归仓路径：`../../build/guanheng-workspace/migration-slice-verification-20261025-001/VERIFIED.json`）。最终受控运行均实际tree0、EOF、读线程join及资源关闭，真实SDK调用0。

## 未覆盖

仍需全新App/SPA安装，使用同一受验原DLL完成真实configured/V2回放，正常退出后以新进程同归档根读取原配置和报告，并验中文页面、异常/空状态、旧owner拒绝、零新Host与独立搬迁。当前测试中的合成HostResult不能代替该链。原目录无receipt保持未归档；容量满保留原件；原件损坏明确失败。整体迁移与生产发行尚未完成。

## 后继：独立安装与真实原生回放、重启读取（2026-10-25）

新离线普通安装已完成 App 与 StrategyHost 双角色安装，安装输入157文件前后固定，使用独立安装内生产 SPA（8文件、2目录），未使用源目录开发服务器。安装报告见installation（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-archive-install-001/runtime/installation.json`）。本轮完整产品37来源、runtime独审38来源、容量delta7原件及26框架保护文件已由根逐字核对，见后继根复核（外部历史/待归仓路径：`../../build/guanheng-workspace/migration-slice-verification-20261025-002/VERIFIED.json`）。

实际 configured 与 V2 roles 两案均经新安装 App 的真实 HTTP POST 调用原 StrategyHost 与受验 WtBtPorter，取得 completed/available 后正常关闭，再以新 App 进程读取同一原目录的配置、分页记录与每日报告。各案首次 Host 构造1次、重启新增0次，原 run 逐文件 SHA 保持，旧 owner 写请求拒绝；重启查询没有重新回放。configured 为5条日记录，roles 为4条，首次和重启报告分别逐字一致。见真实两案结果（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-archive-runtime-002/result.json`）及外层进程关闭（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-archive-runtime-controller-002/build-backtest-archive-runtime-controller-002/result.json`）。四个 App 均 exit0、未强杀、原 Job 整树归零、launcher 已回收、管道 EOF/读线程 join、监听/控制资源关闭。真实 SDK 调用0。

首次真实运行停在测试错误前提“ready PID 必须等于 venv launcher PID”：Windows 实际由启动器创建另一个 App 进程。保留 runtime001 失败原件及正常关闭事实；最终 fixture 以只读 Win32 查询核 ready PID 属于原创建 Job、实际 image 与固定安装基解释器相符，并核实进程前后存活与查询句柄关闭。新增11身份纯例与原6清理纯例共17/17通过；revision004独审（外部历史/待归仓路径：`../../build/backtest-archive-runtime-independent-review-001/revision004/REPORT.md`）静态 P1/P2=0。该修正仅影响测试身份检查，归档产品37来源保持。

当前已补齐新安装、真实 configured/V2 执行及重启历史 HTTP 链证据。浏览器中文入口、空/错/恢复及窄屏操作正在继续；完整原生制品搬迁、全部策略、实时 CTA 与生产发行仍待各自验收。

真实运行后独立证据复核（外部历史/待归仓路径：`../../build/backtest-archive-runtime-independent-review-001/runtime-evidence-002/REPORT.md`）重新计算138份原件、24个原生输出及逐日金融值；configured5日/2原生成交、roles4日/7原生成交与HTTP一致。根线程已逐份复核该清单，见上述002根复核。

后继[真实浏览器九阶段](2026-10-25-backtest-archive-browser.md)已通过 configured：新SPA修正390px布局，真实金融值/只读刷新及显式模拟空错恢复通过、Host0与原件不变/正常回收。V2浏览器、完整搬迁及发行继续。
