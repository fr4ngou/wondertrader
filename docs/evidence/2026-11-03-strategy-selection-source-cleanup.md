# 策略选择、回测列表与日常说明精简

类型：验证记录。状态：候选开发与隔离验证完成，主线合入及生产发布待执行。源码基线：`bdfa0b8`；候选分支：`codex/console-source-cleanup-20261103`。

## 要求与实现

2026-11-03用户要求策略页明确选择策略，先看所选策略的回测列表，再进入分析；随后要求全部页面去掉来源与口径说明。沿已展示的浅色策略页及回测列表设计，删除相应说明区块和折叠入口。产品要求维护在[产品正文](../product/brief.md#只读查看与可用性)，策略与回测流程分别维护在[策略目录](../specs/strategy-catalog.md)及[BPC](../specs/backtest-performance-comparison.md)。

选择器消费原策略目录；运行详情按所选ID及版本验证并隔离缓存。列表复用原归档和performance接口，按报告内核验身份分组，展示区间、期数、本金、收益和回撤，同策略才可比较。URL保留策略与报告选择，旧回测tab转向独立入口。未知策略及跨策略对比深链接明确要求重新选择。后台元数据、分析自动及手动绩效请求共享实际在途计数，最多两个核验请求；缓存穿插和目录重排继续受限。

账户、交易记录、策略、回测、行情、观察看板、指标说明及系统状态移除来源、方法、公式和归属说明入口。日期净值表、持仓与盈亏、成交分页、图表、导出和指标阅读帮助继续可用。数据时点、部分缺口、等待补齐、错误和缓存保留状态单独呈现。WT、后端金融计算、账户和交易执行代码没有本轮差异。

## 验证证据

隔离根：`E:/workspace/wondertrader-qa/strategy-navigation-20261103-001`。候选SPA：`http://127.0.0.1:18489/backtests`，只读代理现行观衡API；未切换正式18143服务。

- `build.txt`与`clean-build.txt`：类型检查、生产构建及chunk检查通过；按永久源码清单复制249份前端及共享文件后再次干净构建通过，入口均为`assets/index-Dt188D5K.js`。新增三份产品模块及行情状态回归文件已登记清单。
- `final-regression.txt`：60文件560项，530通过、30失败。`baseline-regression-complete.txt`在同依赖、基线源码及共享输入下为40失败；`baseline-comparison.json`确认本轮新增失败为0。本轮涉及的策略选择、报告列表、日期明细、账户、交易记录、来源说明精简及行情缺口回归通过；剩余失败分布在原IndependentApp、Boards、accountNative、OverviewWorkspace、accountPublication、ExecutionProcessCard、ObserverLayout旧用例，包含旧页面文案、金额格式及导航数量等既有断言。
- `recheck.txt`：最后三组33项通过，覆盖缓存穿插、目录插入时的两槽约束、后台核验期间分析刷新等待、跨策略对比链接、账户旧批保留及交易记录。
- `page-audits.json`：总览、账户、交易记录、系统状态、行情、观察看板和指标说明逐页检查，相关来源/口径入口残留为0，无框架错误覆盖层。`strategy-audit.json`验证实际策略选择、资金和持仓仍显示；`analysis-audit.json`验证2026-06-09日期、三项日末持仓、净值表及完整交易入口。
- 真实归档列表3份：403期100万元、400期12万元和400期100万元；选择12万元对比、进入分析、返回列表、策略到回测跳转及简介切换已实际操作。日期与盈亏继续消费原投影。最终页控制台错误/警告为0。
- `final-report-list-desktop.png`、`final-report-list-mobile.png`、`final-analysis-desktop.png`：桌面1440及手机390像素检查；手机文档宽390，表格在内部滚动，主要页面保持宽度。
- `REVIEW-SPEC-DELTA.md`、`REVIEW-STANDARDS-FINAL.md`：独立需求及规范评审，原问题均关闭，新增P1/P2为0。原完整评审记录保留对应触发条件。
- `project-check.txt`：文档检查仍被基线`stock-reference.patch`缺失引用阻断；本轮新增文档及差异链接已人工核对。共享工作区与候选原有`updatelog.md`行尾差异保留。

## 交付与限制

2026-11-04后继：Root已接收42份源码为a5865e3，并完成[观衡a106独立正式发布](../releases/2026-11-04-observer-a106-strategy-pages-live.md)。下文保留候选阶段的原交付边界，正式版本、绑定及后验结果以该发布记录为准。

源码身份、逐文件before/after摘要、当前主线比对和静态SPA制品以隔离根的`HANDOFF.json`、`SOURCE-CAS.json`及`RECEIVE.md`为准。本轮完成候选源码、构建、隔离页面验证及独立评审；正式主线合入、统一发行和生产页面验真由单一集成者继续登记。运行实例、算法、金融事实与交易权限保持各自owner。
