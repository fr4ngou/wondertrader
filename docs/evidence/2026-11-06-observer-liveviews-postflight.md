# 观衡121真实页面与Data23运行后验真

类型：delta证据。状态：只读App已部署并完成实际入口验真；本轮新补充事实发布待观察。

唯一机器结果位于 `E:/workspace/wondertrader-qa/observer-liveviews-release-20261106-001/FINAL-POSTFLIGHT.json`；构建 `observer-build004/SOURCE-BUILD.json`、普通安装 `APP121-INSTALL.log`、干净导出回归 `APP121-ORDINARY-TESTS-r2.log`、真实浏览器 `actual-app121-postflight001/UI-PREFLIGHT.json`，均在同根。浏览器使用已存在的Playwright/Edge，Root已实际核看桌面与390px截图，未安装测试工具或改变代理。

36项安装态回归通过。模块均来自App121普通site-packages，SDK20/纯读取13身份匹配，无源码App注入。test-only后继消除外部本地夹具依赖，525项产品源码输入逐件保持；首次失败日志保留。档案查找另有31项源码相关回归：缺run404、现存ORR410、缺根/原件或坏receipt503及摘要冲突409。

真实页面通过线上标记、实际NAV/持仓/账户范围成交与未知收益/归因、切策略清空、8份WT目录、1415日/255成交、悬停0请求、日期点击/键盘/手机操作。日切113/108ms，复访14ms0HTTP，图上点击113ms；首次冷整页11.970秒。公开范围和实际数据限制见[发布记录](../releases/2026-11-06-observer121-daily23-live.md)。

App切换收据位于 `E:/workspace/wondertrader-data/observer-web-a121-liveviews-20261106-001/SWITCH-RESULT.json`，旧App120正常关闭，原两读池线程归零，进程和launcher退出0，新App121 ready，原环境字节保持。稳定部署来源绑定产品commit07304d28/不可变r3标签。另项金融WT发布造成原金融PID变化，实际新CURRENT及新运行代ready由 `WT-ACTUAL-AFTER.json` 单列；本任务金融启停和交易调用0。`ACTUAL-RUNTIME-TRANSITION.json`明确两次后继读取scope相同，不能作为现场跨代持久性证明。

Data23安装、service013采用及旧22停止证据位于 `E:/workspace/wondertrader-data/resonance-daily-auto-20261106-001/`；独立只读进展检查位于本项目忽略研究目录 `daily-auto-development/DATA23-READONLY-STATUS.json`。后验真再次读原CURRENT/INDEX：公开日期仍11/05，11/06 price_state=preparing，已运行日更和新数据已发布分别记录。没有重置任务、删除槽、改代理、重启QMT或补造价格/金额事实。

源研究、原始比较、失败尝试和具体金融材料继续位于Git忽略的 `research/resonance-20261105/`；研究入口新增第16专题。公共正文仅记录功能合同、来源资格及发布证据。项目文档/导航检查在正式集成目录执行，主开发目录既有未索引文档问题由原任务保持。
