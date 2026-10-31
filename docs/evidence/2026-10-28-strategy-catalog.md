# 策略页目录收敛验证

类型：开发验证记录。状态：done（本次页面修正）；模块C整体保持in-progress，未发布。

## 根因与实现

原策略入口同时承担资料介绍和完整参数维护，手机整页4792px。2026-10-28用户要求停止图片设计，参考旧QMT，仅保留策略名称、简介和版本。[当前规格](../specs/strategy-catalog.md)拥有页面要求。

只读参考旧QMT的`D:/workspace/qmt/frontend/console/src/pages/StrategyPage.tsx`、`strategyPresentation.ts`及`src/qmt_platform/services/strategy/strategies/*/definition.json`。新目录登记五类策略，算法版本沿本仓保留规格；登记与宿主运行状态明确区分。App目录HTTP仅返回资料，主SPA卸载参数表单，搜索读取目录GET，回测仍单独懒加载。旧配置深链接归入目录，旧`/backtests`重定向保持。配置保存后端及旧验收原件继续保留。

生产分块验证沿入口完整依赖图核查页面，覆盖策略工作区嵌套懒加载的回测分块，避免把直达入口层级写死。

## 身份与验证

环境：本仓开发源码、Python3.12.14、Node24.18.0、已有Playwright/Edge；Browser plugin not available。当前源码清单与SHA在`build/strategy-catalog-001/sources.json`，生产SPA在同目录`dist`。App/settings显式使用空来源、空策略配置根；本轮资料页零配置写、零运行启动、零交易。

所有命令由`build/strategy-catalog-001/validate.py <phase>`调用原`native.run`，创建期隐藏Job、单一有界截止、有限输出与资源收尾。运行原件同目录：

| 验证 | 实际结果与原件 |
|---|---|
| 正式目录HTTP/额外输入/公共启动回归 | 8通过，backend.log / pytest.xml |
| 目录、搜索、失败恢复、空状态、旧链接及既有回测组件 | 14通过，frontend.log |
| TypeScript | 通过，typecheck.log |
| 生产构建及分块检查 | 通过，build.log / chunks.log；入口268.3KiB，图表独立分块 |
| 实际App HTTP/生产SPA | runtime.json / browser.json；1440×1000和390×844，标题正确、主体可见、零框架覆盖；目录零运行时错误 |
| 用户交互 | 五条资料→名称搜索→无匹配→旧配置链接→原回测→目录→旧回测链接；全部请求GET，配置接口请求0 |
| 窄屏 | scrollWidth=390，整页高度1024；原图390×4792，资料行清楚、横向溢出0 |
| 关闭 | App shutdown_complete=true，两个读取池线程0，HTTP线程join、监听关闭；外层Job/EOF/join收束 |
| 文档 | project.py check通过 |

截图位于`C:/Users/frangou/.codex/visualizations/2026/10/28/01a1827c-4d9e-7d23-b0c3-a7ddb931c0d3/strategy-catalog/desktop.png`与`mobile.png`，已人工查看手机截图。

两名独立审查者分别核用户要求与代码规范，当前目录增量均通过；后续构建检查脚本与实际SPA收尾由规范审查者delta复核通过，脚本SHA前缀07bc43a5，未发现阻断。审查资料与源码SHA清单同目录冻结。审查只授本次目录行为，旧SCW后端Unicode修正及整体安装组合保持各自证据状态。

## 验证限制

本轮回测入口使用未配置环境，历史归档GET返回503并显示既有失败说明，浏览器保留两条相同归档资源错误；目录端点与资源均200。实际回测运行、报告内容、全模块安装/升级、A/B来源及运行组合沿各自专项继续验收。本次只确认回测入口接线及原组件回归，未授予回测业务完整资格。发布与真实交易均未执行。
