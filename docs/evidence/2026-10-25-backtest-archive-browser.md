# 完成回测历史的真实浏览器验收

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。日期：2026-10-25。状态：configured九阶段及V2十阶段真实浏览器通过；完整故障矩阵与发行仍待验。沿[NBW-R6](../specs/native-backtest-workspace.md#nbw-r6-已完成回测只读归档)，前置[真实原生执行与重启HTTP证据](2026-10-25-backtest-completed-archive.md)。

## 环境与输入

Browser plugin/browser skill 未列出，使用已安装 Playwright 1.62.1 与本机 Edge headless。新普通安装App/Host、独立生产SPA spa-release-002、真实已完成configured归档；没有源目录开发服务器。动态loopback URL见浏览器原件（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-archive-browser-runtime-004/browser/browser-result.json`），1440×1000及390×844。真实原生回测输入属于隔离合成范围，真实SDK0。Node、只读App服务和浏览器均由同一创建期Job持有，服务App复用已验AppOwner；原服务D200秒/外层220秒，不续期。

本次服务fixture只放行读，三项旧owner写探针被403拒绝；这不新增产品只读模式。浏览器仅GET，未点击启动/撤单/归档写按钮。固定源、实际安装12源码、37原功能源、39项run树及8文件/2目录SPA由独立最终输入审查（外部历史/待归仓路径：`../../build/backtest-archive-browser-independent-review-001/revision007-mobile/final-inputs/REPORT.md`）核104原件，当前P1/P2=0。

## 问题、实现及回归

真实390px页面原测document/body710px。新增历史section的表格最小内容宽度660px及卡片padding传入页面隐式grid列，令全部区块横向撑开。责任层修正为.backtest-workspace单列显式minmax(0,1fr)，原表格660px及其overflow-x:auto保持；没有隐藏页面溢出来绕过断言。根因原件见runtime003诊断（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-archive-browser-runtime-003/browser/browser-result.json`），修改前后原字节见CSS差异（外部历史/待归仓路径：`../../build/backtest-archive-mobile-grid-fix-001/CHANGE.json`）。

新137输入前后核同，类型、5组76项、生产构建及chunk检查全部通过，见前端002（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-archive-frontend-002/result.json`）。旧Python归档功能37来源未变，继续保留原59项及两案真实原生/重启资格。

| 浏览器检查 | 实测结果 |
|---|---|
| 页面身份/有意义正文/无框架覆盖层 | 标题观衡量化平台，/strategies?tab=backtests，真实历史目录与冻结配置可见 |
| 历史配置与来源 | 实际原run/report SHA及冻结配置呈现；原报告5日 |
| 逐日金融值 | 2024-01-09 八证券 actual/sellable逐行与原HTTP一致；模型净值100000、现金86000，510300.SH数量与可卖均1400 |
| 只读刷新 | 同真实run可重读，无浏览器写请求，无新执行Host |
| 手机布局 | 390×844时document宽度≤390，原溢出断言保持并通过 |
| 异常与恢复 | 浏览器route明确注入一次503，中文失败可见；移除注入后读取真实归档恢复 |
| 空态与恢复 | 浏览器route明确注入空目录，中文空态可见；移除后真实目录恢复 |
| JS/console | pageerror0；唯一error为预期模拟503网络提示，其他相关错误0 |
| 生命周期 | context/browser真实close；App exit0，Host构造0，run树SHA不变，原Job tree0、EOF、join与资源关闭 |

九阶段见浏览器result；协同父入口（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-archive-browser-runtime-004/result.json`）、服务关闭（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-archive-browser-runtime-004/service-runtime/result.json`）及外层Job（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-archive-browser-runtime-004/build-backtest-archive-browser-runtime-004/result.json`）均通过，总12.157秒、未强杀。

## 原失败及证明边界

runtime001 因测试has定位器在row内部再次查找祖先article失败；移除错误祖先但保日期/证券/金融断言。runtime002/003是真实窄屏失败，原件及各自正常资源收口保留，004验证了CSS根因修正。既有合成TS回归的根临时启动器001 ESM路径、002默认Edge路径与003启动/收口70秒超时保持失败；003外层树已归零，不能据此声称该CLI回归通过。本次真实安装浏览器九阶段使用独立受验driver。

runtime004完成时，V2 roles已具真实原生及重启HTTP资格；摘要/角色向量的浏览器后继结果见下节runtime005。文件实际损坏、完整运行故障矩阵、全部策略与正式搬迁/发布仍按后继验收。模拟503/空态不冒充真实服务故障或磁盘损坏证据。

## 截图

桌面目录（外部历史/待归仓路径：`../../build/backtest-archive-browser-qa-evidence-004/screenshots/archive-desktop.png`）、原配置（外部历史/待归仓路径：`../../build/backtest-archive-browser-qa-evidence-004/screenshots/archive-configuration.png`）、每日金融值（外部历史/待归仓路径：`../../build/backtest-archive-browser-qa-evidence-004/screenshots/archive-day-detail.png`）、390px（外部历史/待归仓路径：`../../build/backtest-archive-browser-qa-evidence-004/screenshots/archive-mobile.png`）、模拟503（外部历史/待归仓路径：`../../build/backtest-archive-browser-qa-evidence-004/screenshots/archive-synthetic-error.png`）、模拟空态（外部历史/待归仓路径：`../../build/backtest-archive-browser-qa-evidence-004/screenshots/archive-synthetic-empty.png`）。六图SHA见清单（外部历史/待归仓路径：`../../build/backtest-archive-browser-qa-evidence-004/SCREENSHOTS.sha256.json`）。

## 后继：V2真实浏览器（runtime005）

同一新安装及修复SPA对真实V2 roles原生完成归档取得十阶段通过，新增核策略resonance-regime-v2/0.1.0、信号589680.SH与执行589000.SH在各自表分开，8个actual/sellable逐值与原HTTP一致；2024-03-28模型净值124587.31、现金47187.31。390px及模拟503/空态后真实恢复均通过，pageerror0、唯一预期503console。原生持仓行定位明确限定其region，避免与V2信号表同名证券混淆；未减弱金融断言。

浏览器（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-archive-browser-runtime-005/browser/browser-result.json`）、服务（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-archive-browser-runtime-005/service-runtime/result.json`）、外层（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-archive-browser-runtime-005/build-backtest-archive-browser-runtime-005/result.json`）均通过：Host0/原件不变、context/browser实际close、App自然exit0与tree0/EOF/join/resources关闭，11.688秒。独立最终delta（外部历史/待归仓路径：`../../build/backtest-archive-browser-independent-review-001/revision008-v2/revision002/REPORT.md`）核67来源，执行0、P1/P2=0。七图摘要见清单（外部历史/待归仓路径：`../../build/backtest-archive-browser-qa-evidence-005/SCREENSHOTS.sha256.json`），策略摘要截图（外部历史/待归仓路径：`../../build/backtest-archive-browser-qa-evidence-005/screenshots/archive-v2-summary.png`）。本后继补齐该V2浏览器范围，完整运行故障/发行资格继续独立验收。

## 本轮原件复核与安装身份

本轮只读核对004/005既有运行原件，未重新执行浏览器。004浏览器结果SHA为`4649f6e2a4782a2b2e3c702b803dcaf7547623c7cf4accdb8f02cdc578bb2849`，005为`afd8fd2c0bec5befd73d96a41928fdea852fcf5a709950b756f059c4d3e6e73b`；两父入口保存的browser_report_sha256均与原字节相符。两案浏览器只发GET，JS异常0，唯一console error来自显式synthetic503；context/browser实际closed。服务保留原run/report/receipt身份、新Host0、archive_unchanged=true；实际App exit0/reap/tree0、管道EOF/join、listener/control/shutdown及外层Job资源关闭均成立，无强杀或未知回收。

同一普通安装收据（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-archive-install-001/runtime/app/runtime-receipt.json`）SHA `4d2fb073b02d4fce7ba7ffbad07a28b8f90e292ffce0a746b9c70f9a086c878a`登记guanheng-app **0.1.0a3**，依赖已安装的guanheng-strategy-core **0.1.0a5**；a5指策略核版本。两个实际App的installation_identity核同一venv/site/收据，SPA均为独立spa-release-002。004六图与005七图按各清单逐一核原字节SHA通过。

真实证据覆盖原生完成归档的配置/报告读取与界面数据；503和空目录来自浏览器route的明确合成响应，随后恢复真实服务读取。这些结果保持其隔离合成回测输入范围，未新增真实服务故障、磁盘损坏、完整历史覆盖、全部策略或独立发行资格。
