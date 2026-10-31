# 2026-10-22 原生回测工作区接线

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发证据。状态：in-progress。范围：[NBW-R1–R5](../specs/native-backtest-workspace.md)，当前仅configured1.2.0冻结合成输入。源HTTP、SHM、实际柜台和生产分别验收。

## 实现与职责

新业务owner、路由与部署配置位于`apps/guanheng/guanheng_app/backtest_workspace.py`、`backtest_routes.py`、`app.py`、`settings.py`。浏览器位于`console/src/workspace/BacktestWorkspace.tsx`及`backtestApi.ts`，沿独立策略页和/backtests兼容路由。

原宿主/Job拥有进程和完成判定；原WtBtPorter拥有回放/撮合；NSB拥有唯一报告准入、深不可变值与前缀重建。业务只增加单轮请求索引、显式取消与有限报告投影，不创建持仓、行情、订单或任务数据库。进程重启更换owner身份，原实验目录保留。真实QMT数据与合成报告资格分开。

## 作者验证

- 后端13项新边界与原分钟/账户适用回归共78项通过，见pytest-003（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-workspace-001/pytest-003.xml`）。覆盖同ID并发只执行一次、繁忙/旧epoch拒绝、取消/关闭、缺报告/未回收不能完成、摘要变化、报告缓存别名与期限扣减。
- 前端新10项API/组件通过；含原账户/读取影响共25项通过。最终类型检查与生产build通过，入口267.2KiB，分钟/账户/回测3个独立lazy分块。
- 项目Playwright/Edge首轮7项通过，覆盖新回测及原分钟/能力的正常/空/失败/恢复；最终中文呈现调整后重跑新回测场景通过。桌面1440×1000、手机390×844，无横向页面溢出、框架overlay或应用JS异常。唯一报告503为故障注入的预期网络错误。
- 浏览器路径选择：Browser plugin not available（本会话未列Browser plugin及browser skill），沿仓库Playwright执行。mock报告明确为合成；真正的原DLL→安装应用→业务HTTP→静态浏览器链正在独立验证。

初次pytest因新输出父目录尚未存在停于setup，原XML保留；建立目录后正式执行。原自查发现报告头浅拷贝别名，责任层已返回独立记录头并加入根因回归；首轮强制时差断言因Windows时钟分辨率失败，后改为真实延迟读取验证已耗时扣除，未修改产品时钟。调试原件与正式通过结果分开。

## 冻结与独立审查

后端独立审查冻结源包SHA `c129816684c064f3fb6db635d3dabcd170d03c06180c99b6c406aa6f938d985a`，NBW规格SHA `d68ac143d00ec65e9da4b6819c55fe377aa6f89462148b0e7bd4490f0288301a`；当前后端4模块保持冻结，full进行中。新正式Flit安装已建立，开发/安装/审查/生产资格各自登记。

前端审查输入（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-workspace-001/frontend-final-001/review-inputs.json`）SHA `7f47c13c07b57a7ec54c6707ace9df4081892d8b86e7d68cfd6ec6a94d62dc08`，source ZIP SHA `44c5c0cfe9ebd327c769836e9b126a57f090d74d612c0772f2fd94ec4528b223`，187文件manifest SHA `434b8af485d06d6127f96e8702dd5502f57e6b66d27b9f5534cf0d6342b819de`。full由未实现本轮页面的审查者执行，包含实际安装原DLL链；报告待封存。

## 剩余范围

本次不授整个观衡完成：其余策略/版本、真实ETF历史和辅助来源、原生CTA实时同核、配置/资本归属、新闻研究、运营及执行写链按完整迁入清单继续。终端HTTP仅今晚前流程，停止优化和新部署；SHM须待另一对话开发完成并取得今晚实测确认后再接WT。没有修改WT核心或发起真实交易、终端重启与生产切换。

## 后继：独审发现与责任层修正

NBW后端full-001（外部历史/待归仓路径：`../../build/guanheng-workspace/reviews/native-backtest-workspace-backend-full-001.md`）结论gap，报告SHA `0b955dbe06a7ee165de78ae706880d08fe4484c7a0c237011b8c745b2007e0bf`；4375项manifest SHA `2a4d312f32734a1097147296b290bb0d2d979742e8856ffd6cd5b9716586a1a5`，根任务已逐项回核一致。三项P2分别为线程已启动后的异常释放slot/覆盖原owner、畸形Origin逸出500、Porter AdmissionError未在配置责任层转换。均位于自有工作区，未发现或改动WT框架。

原样10条根因反例全红；修正后23条工作区回归通过，再加入真实线程尾声尚存活的准入/关闭反例，连同原分钟/账户合计89项通过。新实现每entry在start前持有线程/完成事件，启动异常发cancel并保留slot，worker最终出口登记完成；新准入另外核实际thread退出，close按共同截止核全部entry。启动仍未知时保持未确认与名额，进程重启更换owner恢复。Origin畸形归403；配置时间准入转换为工作区不可用，行情/账户/health入口保留。

新后端候选（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-workspace-001/backend-final-002/review-inputs.json`）SHA `1e95b81e01832bb169162a2fc36fb5242f4f8ba2f351ceab89fc9f38be7c7cef`，source ZIP SHA `fe3d04486b00c65e518f431e945b1c7aedf200544ed7583925438ac907fff152`，独立delta正在新正式安装复核。full原件和旧安装保持。前端full另发现写请求原始JSON/网络异常未统一去敏及身份字段String强转接纳数组，已独立实证并保持原冻结，后继修正/报告继续，当前未授发布资格。

## 后继：独立delta完成及产品范围收缩

后端delta-002（外部历史/待归仓路径：`../../build/guanheng-workspace/reviews/native-backtest-workspace-backend-delta-002.md`）已complete，报告SHA `451b5c5d8c986c2fa6084c34827f30b23d3e3206e24159721f30ad08dcba0487`，1624项原件根回核一致；89项及实际新安装原DLL/HTTP、取消、重启与关闭通过。资格绑定该轮源码，后续app范围调整另验。

前端责任层已统一写异常去敏、严格校验身份/摘要/状态原始类型。独立delta-002（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-workspace-frontend-review-002/REVIEW.md`）complete，无剩余发现，报告SHA `f4f3a1ffda7363860b4ba9fd7194932bc0bc43c2f10837c76ee1540c0ed0f147`；36项manifest（外部历史/待归仓路径：`../../build/guanheng-workspace/backtest-workspace-frontend-review-002/manifest.json`）SHA `75d54212283485f074fd7253976b7fd53e44d573336f623c42da2f10c824d331`，根逐项回核一致。18项最终测试和45项实际Edge故障/类型/页面场景通过，未知写结果不自动重发，刷新仅GET，显式再次认领沿用同ID；不延伸后端、原DLL或生产资格。backtestApi源码SHA `fb607de575b44ce29cdb43c060c688f02b51c043156e3f111fce816f3358fb8c`。

用户最新[ADR-0004](../architecture/adr/0004-core-trading-product-scope.md)将Grafana、新闻、研究功能及界面整体退出目标。上文旧“剩余范围”中的新闻研究迁入要求至此撤销；[清理验证](2026-10-22-core-trading-scope-retirement.md)单独登记新app/静态制品和独立安装资格。其他策略版本、真实来源、实时/执行接线和生产仍按保留范围继续。
