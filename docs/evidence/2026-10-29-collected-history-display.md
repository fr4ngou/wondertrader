# 原生自然归档在当前App/生产SPA的实际展示

类型：模块C消费验证。状态：主链、普通安装、消费者回归和浏览器通过；独立审查及精确交付中。关联[CNH](../specs/collected-native-history.md)、[HCO](../specs/source-history-chart-observation.md)、[COP](../specs/guanheng-operator-platform.md)。

## 根因与接线

A已交付自然Writer归档→原Reader→SDK/完整App接口；本轮补当前C安装/生产SPA实际绘制与交互。沿原SourceMarketProcess装配A最终161文件组件，绑定新的entry/native_reader路径和摘要；保持source-collected/base source-catalog与外部335分钟store/9ETF日线store/137归档根。App、SDK及现有页面公共合同保持，产品代码修改0，不新增导入/采集任务或服务。

## 固定安装

原件根`build/collected-history-display-001`。A交付DELIVERY SHA `10e0b5d984d0f6d226cfe783be6a50941020e0bc90ceed94647eef885c81d5b5`；组件INSTALLATION SHA `225791a042473d5aa669bf8f56aa09a3ed2d3e06cb3d8864db4270e102167903`，复制后161文件逐项相等。保留HEM最终Appa19 wheel `be7440829a714177d2f1acc5c73544be9a05de81014fd9ae79a35f30b15fd31c`及其余策略包；SDK替换为A最终216/0.15.0 wheel `34579862be4dc777bf2f10cceff64d0df2a242a7ee78f368c06e9a4c744287ab`。

本根INSTALLATION SHA `8b07b794df66d667547d7c325879f54cd81f570a81d1873113e9d6da23f9e3cb`：35发行4789 RECORD与11私wheel payload逐项核验，依赖检查通过。独立标准库venv无启动hook，App/SDK实际导入归属核安装site；生产SPA沿HEM009原18成员/ZIP精确SHA复用。

## 实际页面主链

`main-005`经普通完整App→原SourceMarketProcess→新组件→原Writer历史/原ABI→SDK→App HTTP→生产SPA/Edge，两个App代际：

- 600000.SH、000001.SZ、510300.SH各2000根，尾部2026-10-29当天240根的time/OHLCV与A app005原件逐字段相等；每份均为schema1.7、两段来源。600000为旧1760根至10月27日15:00及今日240根09:31至15:00，缺口保持，页面已有断线说明。
- 分段dataset/content/来源实例/会话/代际及三种单位保持原metadata；未知单位仍标尚未确认，不推断CNY或股。`main-006`补充真实来源详情1440×1000/390×844图证，LA浏览器继续按上海/北京时间显示，零横向溢出。
- 2020截止的真实空查询HTTP200/data_available=false，显示暂无权威K线；一次受控GET503后隐藏旧图/来源并手动重试恢复。第一代保持同一浏览器页面，在QA请求标记后由父端真实关闭其来源owner，HTTP200业务不可用、candles空、旧图/来源及最后时点均隐藏；第二代重新启动原App/来源后重新读回三证券同值。
- 两代浏览器各仅一条注入503资源错误，零其余error/warning；补充来源截图无错误。两个App及补充实例均shutdown_complete、线程join、来源/应用端口关闭，来源status=closed、forced/pending=false。各外层原native Job/tree/EOF/join完成，停止验证线程也已join。
- 106安装消费者回归通过，覆盖来源观测/分段、日线与SMA父owner，所有App/SDK模块归安装site。QA两条已导入anyio rewrite及一条Starlette/httpx弃用警告保留；未扩展策略算法测试。

## 尝试与边界

main001在启动服务前误认base为source-stores，实际为source-catalog；002手机resize后同步检查早于图表settle；003对空态错误使用heading角色，实际为status中的strong；004误把停止后业务不可用HTTP200视为必须HTTP失败。均为QA假设/检查错误，原脚本/失败/实际关闭保留；005按真实公开语义验证，产品未加特判。002后补geometry确认document/viewport均390、越界元素0。补充006重新截图来源详情，避免用图表截图替代来源图证。

不重复今日采集、不请求QMT业务接口/下载/账户/交易、不切生产或改WT。注册6982范围不授全市场完整、连续覆盖或策略准入；原厂分钟对照、旧10月28日缺口和未知单位保持。策略迁入按根核实的实际启用且有策略归属持仓清单，当前回测/算法候选不推定进入清单。完整M1、统一运行候选及升级/回退继续。

## 2026-10-29 用户页面纠正后继

用户指出main-006来源详情堆砌内部信息。根因为SourceHistoryStatus直接枚举API provenance，页面将验收/诊断身份当作用户内容。HCO-R3及COP已按明确要求修订：共享组件停止渲染数据集、内容哈希、实例、会话、代际与逐段单位详情；正常Observed/Archive无需面板。Partial/补齐异常只说明数据缺失影响及重读动作。两个行情入口的资格术语统一换为简短读图说明；独立App去掉不可用叠加层的技术提示，时间按北京时间或最新交易日展示。API原metadata、实际值和准入规则保持。

本轮源码、QA、SPA及截图原件位于外部可视化根`C:/Users/frangou/.codex/visualizations/2026/10/28/01a1827c-4d9e-7d23-b0c3-a7ddb931c0d3/market-readable-001`。前端33项定向回归、TypeScript、正式Vite编译和分块检查通过。Browser plugin not available，沿现有Playwright/Edge验证，1440×1000及390×844、LA时区；页面身份、非空、无框架覆盖、内部字段不在DOM、实际三证券各2000根/当日240根与A原件逐字段一致均核。第一轮007通过后，追加移除“附加证据”提示，以008及干净spa-final重验相同真实调用链；后继结果以final/RESULT.json和main-CLOSURE.json为准。

原main-005/006截图只证明当时来源链，main-006技术详情已被用户撤回，不作为当前页面验收样式。新UI不改变行情owner、源SDK、生命周期或交易边界；本切片独立审查范围none（纯展示收敛），由当前源码、既有组件回归及实际浏览器验证绑定。完整模块独审/发行/唯一策略主链继续分别登记，当前未部署生产。

后继008最终通过：两代App各三证券2000根，当日240根逐字段相等；实际同页停止与新App恢复、一次503重试、真实空查询全部通过。实际页面内部身份及“附加证据”文案均未渲染，console仅各一条主动注入503、warning为0，进程/线程/端口和原Job完整关闭（40.047秒）。12份相关源码/规格与18份干净SPA成员已固定，`guanheng-console-readable.zip` SHA `f5de034f489077cfbc4a2f60f1d610875148c270296ee075a4d12ff73f30d99b`，原件同外部可视化根DELIVERY.json。`project.py check`通过；当前仅本地修正和验证，未切换生产。

## 同查询刷新保留与用户展示复验

依据最新[只读查看与可用性](../product/brief.md#只读查看与可用性)及HCO-R2/R3/R4，MinuteWorkspace和保留MarketPage使用原React Query按证券、周期和截止条件保存的成功结果，刷新中或失败时保留图表、简短说明和原数据时间；首次失败显示重试，成功空结果更新为空。能力状态提示不再阻止用户主动读取已有行情。原生HTTP200业务失败投影缺native_source，读取适配层将其归为错误；真正成功空查询保留native_source，按空结果处理。沿现有查询缓存实现，无额外缓存或持久状态。旧005/008“失败隐藏”观察仅证明当时版本。

外部原件根`C:/Users/frangou/.codex/visualizations/2026/10/28/01a1827c-4d9e-7d23-b0c3-a7ddb931c0d3/read-only-refresh-001`。34定向回归、TypeScript、正式SPA和分块检查通过，覆盖刷新中/HTTP失败/业务失败保留、查询切换、成功空和恢复；来源内部字段不在DOM。Browser plugin not available，复用既有Playwright/Edge及原安装源/App实跑。首轮009的QA按symbol匹配响应时接到了前一次刷新回复，空查询断言失败；同次九项回收状态全部true，errors为空，无保留owner。后继010改为精确匹配截止条件并等待刷新完成，原失败及脚本保留。当前生产部署与完整模块交付沿各自状态。

后继010两代完整安装App/真实来源主链通过，三证券各2000根、当日240根与原件逐字段一致，1440×1000/390×844及LA浏览器时区保持北京时间，无横向溢出和内部来源字段。HTTP503和真实停止来源后的HTTP200业务不可用均保留同查询图表、说明及原时点；2020截止查询成功为空，恢复原截止与重启App重新读回。console仅各一次注入503，warning为0，所有App/来源/线程/端口及原native Job关闭。`project.py check`通过；该切片沿HCO的只读缓存语义复验，独审范围none（纯展示状态，无持久/交易/发布变化）。AccountWorkspace及ObservationShell的同类状态改进继续按各自任务验收，本条仅授予两个行情入口及共享来源提示的资格。
