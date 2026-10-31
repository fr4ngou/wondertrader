# 观衡完整功能迁移清单

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

2026-10-29 用户最终确认策略范围：当前只有共振市场状态ETF策略（resonance-regime-v1）运行，当前全部券商持仓都归属它。本次仅交付这一策略的最新正式在用版本；其他策略、候选和旧版本退出运行入口、页面版本选择、发行依赖及开发/验收范围。共享行情/历史、原生账户执行、多策略扩展接口和恢复能力保持。历史交易记录不迁入，历史K线保留；原券商持仓用于该唯一策略接管候选，资金预算与开仓/成本/止损初值按实际配置核准。已核旧实际启用/两份运行原件及同一配置六参数和预算，本次锁定最新已确认正式在用1.1.2；1.2.0为另一配置角色分支，不按数字静默替换规则。依据见[唯一策略证据](../evidence/2026-10-29-retained-resonance-latest.md)。旧QMT项目继续只读，已封存历史证据保留追溯，原生产及真实交易授权保持。

2026-10-29续接：下节保留10-23的静态清点与当时边界；当前运行资格及剩余差额沿[模块C交接](module-c-delivery.md)和[证据索引](../evidence/README.md)。策略资料入口已按用户要求收敛名称/简介/版本，账户/日线/运行状态、观察冻结读取及HPR App接线分别具有后继安装证据，完整保留范围继续in-progress。

## 2026-10-23 保留业务入口静态核对

本节按当前自有源码核对迁入差额，补充下文历史范围清单。依据为独立应用的app.py、backtest_routes.py、account_scan.py及浏览器main.tsx→workspace/IndependentApp.tsx实际启动链；保留的Console App.tsx不属于当前挂载入口。源码身份分别见原清点（外部历史/待归仓路径：`../../build/guanheng-workspace/retained-business-entry-static-20261023-001/source-manifest.json`）和实际入口更正（外部历史/待归仓路径：`../../build/guanheng-workspace/retained-business-entry-static-20261023-001/entrypoint-correction.json`）。本轮没有启动HTTP、浏览器、原生或SDK，以下“有入口”仅说明代码接线，不授当前安装/运行资格。

| 保留范围 | 当前源码入口与边界 | 继续完成的差额 |
|---|---|---|
| F01/F02 行情与历史 | 独立应用显式提供1m/5m图表接口；daily_chart仍不可用，1d请求返回501。历史导入、SHM历史与原Reader另有本仓入口及各自证据 | 全市场/ETF真实覆盖、来源单位与时效、实时/订阅、日线及策略/成交overlay逐项接通；不以原生Reader或分钟图局部通过覆盖全部范围 |
| F03 策略 | 原生回测工作区已有独立HTTP和中文页面；实时strategy能力仍false，包目录/算法存在不代表五个策略的实时状态全部迁完 | 所有保留策略的WT实时调度、原生状态、相同输入同核目标，以及各自规则/异常/恢复逐项验收 |
| F04/F05 原生资金/风险 | /dashboard现已复用账户只读组件接线，资金/持仓/委托/成交沿同一查询与DTO；该增量仅静态独审，页面和真实链未运行。原生回测另提供其范围的事实；策略预算及已配置原生规则沿最终复用边界 | 核实际启用规则/资金与理论状态读取链；资本拨付/多账本对账/逐单人审仍退出目标，不以重建旧服务作为前置 |
| F06/F07/F19 执行与记录 | 账户四查询承担委托/成交的只读值展示；execution能力仍false，当前App为read_only | 原生执行/补单、源端委托身份、回报/未知结果核查及实时中文记录完整链仍分别适配；下单/撤单实际运行按具体授权 |
| F08 配置与自选 | 个人观察GET/PUT及中文页已接；正式安装112后端/103前端、生产SPA真实保存/重启、CAS/单writer、异常恢复及360px核心链通过并获最终独审。默认根空关闭；配置/激活/回滚仍未接通 | 个人观察完整故障/真实TCP断连、托管CI与生产另验；其余配置读取/编辑校验、版本/激活回滚继续承接WT实际配置，保持独立事实所有者 |
| F09 回测/比较 | 已注册workspace、启动、状态、取消、记录分页/明细路由；configured/V2等资格按各自证据 | 逐策略/费用/T+1/数据来源、比较与所需晋级事实、同版独立安装及完整用户入口继续验收，代码入口不替代实际运行 |
| F18 独立市场观察 | 当前App未注册独立观察数据路由，IndependentApp仅有市场观察导航和通用未接通占位；该保留能力不因新闻/研究退役而自动完成 | 只迁独立市场观察的指标/来源质量/快照/图表与导出及必要辅助事实，沿范围准入排除新闻/研究服务 |
| F20 运营与故障 | health/healthz存在，operations能力仍false；当前独立浏览器运营入口显示通用未接通占位 | 新进程/WT输出的中文运行状态、日志与故障解释、必要任务回执和权限明确的恢复；旧Docker/Grafana退出要求保持 |
| F21/F22 独立发行与必要结果 | 本仓Python/SPA/原生分别有发行与验证入口；账户双环境源码/安装闭包继续开发 | 同版独立安装/搬迁、原生兼容/回滚与保留配置/报告的重启读取逐项核实；不引入重复行情、持仓或审计数据库 |
| F23 券商接入 | SHM行情、历史与账户按不同profile/来源资格接入；新账户schema2 guard仍关闭，终端HTTP退役 | 完整锁/wheels/安装、实际线程/Job/IPC、真实SDK字段/时点与用户入口分别验收；通达信交易继续暂缓 |

F10–F17、Grafana及研究专属工作流按既有退役决定处理；本节不恢复相关功能。当前整体迁入继续in-progress，账户测试与安装通过后仍需完成上表保留差额，不能将总体目标缩为账户smoke。


## 当前产品范围优先级

用户已明确：Grafana、新闻、研究的功能及界面均不进入WonderTrader，也不作为后续迁入与验收目标，执行[ADR-0004](../architecture/adr/0004-core-trading-product-scope.md)。下表F10–F17中新闻/研究/采集/资料/评分/证据工作流已退役；F14仅允许剥离后保留策略必需辅助事实及独立市场观察的数据接缝，不能带回研究服务。Grafana服务/大盘/Viewer/专属门禁同样退役，必要健康和日志诊断保留。

F04/F05及相关条目按用户后继决定收敛为WT原生资金/风险与显式策略预算；资本拨付、独立资本账本和逐单人工审批不列迁入门槛。23个编号及441条旧HTTP目录是历史清点索引，不能继续解释为全部必须迁入。被退役项登记退出，停止实现、部署和验收；保留项继续完整适配。旧工程和冻结历史证据保持原样。

类型：迁移范围与源码核查清单。状态：in-progress。核查日期：2026-10-22。本文登记要迁移的用户能力、原生替代点和可观察的迁入条件；具体接口要求由各功能规格维护，当前运行资格由证据记录维护。

## 目标与来源身份

保留范围的观衡业务进入本 WonderTrader 仓库，业务服务保持独立构建、安装、启动和发布。最终运行、构建、测试、制品及发布均无旧 QMT 工程或其 worktree 依赖。券商 QMT 终端仍是行情和交易接入对象；旧平台仓库与券商软件是两个不同对象。旧树只读参考，现有数据、未决操作、生产进程和下载任务保留。

本清单依据实际源码的页面声明、HTTP 装配、任务循环、存储构造及发布脚本，结合[原生能力目录](../development/wondertrader-capabilities.md)和[业务职责映射](business-adaptation-map.md)形成。固定 Console 参考为 `E:/workspace/qmt-worktrees/wt-native-console` 的 `4e5595c156731ce66f3e0a199096a863354eeda8`；其余业务参考为只读 `D:/workspace/qmt` 的 `6cf508a070392ff976b6b4d6b31b0e6219001e71`，核查时工作树干净。下文 `Q/` 指后者仓库根，`C/` 指前者根；`S/` 指 `Q/src/qmt_platform/services/`。这些绝对位置只用于追溯来源，不是新部署路径。路由附录直接由参考源码静态枚举，逐文件注明摘要；没有启动或导入旧服务。

WT 固定上游能力依据 `08b230dd05facf6d650d949bfe51054115a2ecb1`。当前工作区内已开发的自有适配属于下游实现，不能计为上游自带能力。原生核心仅使用用户已批准范围；其余差异继续冻结，新的必要修改先说明证据、替代办法、范围、风险和回滚，再由用户批准。QMT终端HTTP退役；共享内存已取得开发授权并按[QSW](../specs/qmt-shm-wt-binding.md)接入，通达信交易暂缓。现阶段真实数据开发和验收只使用 QMT，通达信已有观察退出当前缺失、精度和覆盖判据。

## 迁入的共同判据

每个功能迁入须同时满足：源码及所需非私密资产在本仓库；依赖来自受管安装包和显式外部服务；从独立安装目录启动，移走旧树并清除旧 `PYTHONPATH` 后仍能运行；正常、空、失败、超时、恢复状态在真实用户入口可见；重复写入、重启和并发的效果符合对应事实所有权。历史资料和未决命令的读取/切换另有明确输入和回退方案。只读功能不借测试授权发起委托、撤单或下载。

“原生承接”表示退出重合的旧实现；“业务迁入”表示保留用户能力并重接 WT；“券商接入”只保留外部源调用约束和可靠身份。下面各项均是迁移范围，源码存在、候选编译通过及路由返回成功分别不授予整个系统完成资格。

## 页面与用户入口

页面依据 `C/frontend/console/src/App.tsx` 的 `Routes`、`workspaceLoaders` 和实际页面源码。前端路径与服务端 HTML 路径分别核查；导航里隐藏的兼容入口仍需登记。

| 入口 | 用户能力与源码 | 最终承接及可验证迁入条件 |
|---|---|---|
| `/`、`/dashboard` | 总览、资金/持仓/可卖/盈亏、净值、允许策略、今日执行队列；`pages/DashboardPage.tsx` | 业务迁入；账户事实来自券商插件/WT 通道，策略理论状态与损益来自WT，预算来自明确配置；分清实盘、模拟及回测数据，部分源失败保持原因和观察时间 |
| `/market` | 证券搜索、自选增删、策略范围、1m/5m/1d 图、分页、基准及策略/成交标记、实时摘要；`pages/MarketPage.tsx`、`components/MarketCandlestickChart.tsx` | 原生存储/周期/查询承接，页面与个人自选迁入；逐周期验证数据来源和时间，分钟图资格不代替日线/复权/实时资格 |
| `/observation`、`/observation/*` | 市场观察、指标切换、日期/窗口/通道参数、原始行、公式、来源质量、版本、原图、资产与导出；`observation/ObservationShell.tsx` 及同目录模块 | 业务迁入，独立只读数据服务；图、表、导出绑定同一快照，缺披露/休市保持空值，公开观察资格和可执行行情分开 |
| `/research` | 新闻、来源健康/采集窗口/重试明细、研究报告、多角色研究、机构及人物发言、正文/证据链；`pages/ResearchPage.tsx` 与 `components/NewsResearchPanel.tsx` 等 | 已退役：功能/API/页面不迁入，清理新仓库已复制实现；原源码仅保留历史参考 |
| `/strategies` | 概览、持仓与目标、调仓与补单、交易、收益回撤、回测、配置运行；`pages/StrategyPage.tsx` 七个 tab | 原生运行/理论持仓/回测承接；独有算法、规则、配置、资格及展示迁入，预算为配置，资金/损益复用WT；逐策略核对原生上下文状态和同核实盘/回测 |
| `/orders` | 命令前队列、账户执行与原生委托状态、委托筛选、因果链；`pages/OrdersPage.tsx` | WT 委托/成交记录承接基础事实，只适配源端身份与未知委托核查，不引入逐单人工审批；记录缺失、查询范围和结果未知均明确展示 |
| `/operations` | 运行概览、错误日志/指纹聚合、活动故障、服务/账户状态、对话任务回执、六个监控大盘；`pages/OperationsPage.tsx` | 业务迁入；由新进程/安装包/WT 运行输出提供状态；旧 Docker 服务名、旧发布身份与旧数据库计数退出就绪判据 |
| `/portfolio` | App 重定向 `/strategies?tab=holdings` 并保留查询参数；`PortfolioPage.tsx` 仍在源码 | 保留兼容重定向和持仓功能；未被路由引用的旧页面组件不单独算在用入口 |
| `/backtests` | 重定向 `/strategies?tab=backtests`；报告、净值、成交与持仓演进 | 保留兼容入口；报告数据绑定 WT 回测输入/模型/策略身份，完整报告与分页可读 |
| `/audit`、未知路径 | App 分别重定向系统状态/总览 | 核对服务端 HTML 能到达对应 App；服务器 `SPA_WORKSPACES` 不包含 `audit`，客户端重定向存在不代表直开 URL 已验 |
| `/legacy`、`/assets`、`/ui-assets/assets` | `S/console/app.py`、`static/` 旧页与构建 SPA 静态资源 | 登记为兼容/静态入口；最终保留或退役须有入口清单，不能让旧脚本静默调用废弃服务 |

壳层还包含连接分层状态、通知/活动抽屉、SSE、问题字典和全局投影刷新。依据 `C/frontend/console/src/App.tsx`、`hooks/useConsoleStream.ts`、`components/ConnectionDetails.tsx`、`components/ActivityDrawer.tsx`。它们属于用户功能；首批图表壳层可显式展示尚未迁入模块的状态，不能伪造完整账户/研究就绪。

## 全业务模块迁移矩阵

| 编号/能力 | 代码依据 | 原生承接、业务差额与退出实现 | 迁入验收 |
|---|---|---|---|
| F01 历史/实时行情与证券元数据 | `S/market_data/app.py`、`resonance_daily.py`、`subject_profiles.py`；`S/bridge/bar_ingestion.py`、`gateway_runtime.py` | WT-D01–D09 承接 Parser、DSB/DMB、Reader、Factory 周期；QMT 字段/时区/单位/复权、证券资料与因子映射迁入；旧 SQL bars、Python 通用聚合和重复行情存储退出 | QMT 下载样本→原 ABI 导入→同实例原 Reader/原策略→独立图表；补齐/修订可重读；实时快照和完整闭合分钟分别证明 |
| F02 缺口、导入、日历及长历史任务 | `S/market_data/app.py` 导入/quality/calendar/history-repair 路由；`S/operations/app.py` history-jobs；`S/strategy/configured_universe.py` | WT-D04/D11 承接格式导入和 loader 接缝；来源/覆盖/任务进度是最小差额；旧分钟事件数据库作为底座退出 | 真缺数、无成交/停牌/休市、源暂不可用分别可解释；已下载读取不触发主动重下载；停止/恢复、重复导入和历史修订有证据 |
| F03 策略算法与状态 | `S/strategy/registry.py`、`configured_resonance_runtime.py`、`rules.py`、`strategies/*` | WT-S01/S05/S06 承接调度、窗口、理论持仓及目标汇总；算法、配置、止损/迟滞/辅助输入规则迁入；旧通用策略 worker/目标账本退出 | 下表每个策略的状态字段逐一映射；相同冻结输入/配置的 live/replay 同核目标一致；预热/补发/重复/过期不产生额外目标 |
| F04 策略预算、原生资金和收益 | `S/portfolio/strategy_capital*.py`、`account_capital*.py`、`ownership_store.py`、`capital_history.py`、`multi_strategy*.py` | WT-S05/S06、WT-T01承接理论持仓、损益、组合统计与券商资金；策略预算为显式配置。旧资本拨付、独立袖套账本、人工持仓归属服务不列新增迁入目标 | 券商资金/持仓与策略理论状态分别展示；配置预算参与数量计算，原生状态与损益可回读；不以旧多账本一致作为新交易门槛 |
| F05 原生风控及策略自身规则 | `S/portfolio/risk.py`、`simulation_preview.py`、`simulation_operator_reviews.py`、`simulation_execution_authorizations.py`；`S/control/app.py` | WT-T07及实际插件/配置承接通用限制；策略特有仓位、止损/迟滞规则迁入策略。逐单人审、审批消费与许可工作流不列新增目标 | 每条实际启用规则有触发点及允许/拒绝回归；账户许可、接口认证与执行模式分别校验；只读入口保持无交易副作用 |
| F06 委托、撤单、订单/成交及结果未知 | `S/bridge/store.py`、`command_delivery.py`、`multi_strategy_command.py`；`Q/qmt_agent/runtime.py`、`journal.py` | WT-T01/T02/T03/T08承接查询、通道、执行及原生记录；QMT适配只补源端身份、调用和回报差额，重复旧订单库/执行器/审批链退出 | 查询/push字段、原生委托与源ID关联、超时未知核查、重复投递、断连/重启及快照/回报交接；真实写资格另验 |
| F07 调仓、补单与持仓恢复 | `S/portfolio/replenishment*.py`、`rebalance_*.py`、`strategy_fill_continuity.py`；`S/strategy/replenishment_*.py`、`mode_only_target_transfer.py` | WT执行算法承接差量、拆单、追单与撤单；策略保留必要持仓周期、目标代际、有效期和止损规则，旧调仓审批及重复执行循环退出 | 模式切换、部分成交、截止和取消不产生重复委托；原生状态与来源可核查；用户特有止损规则明确 |
| F08 配置/激活/回滚/自选 | `S/control/app.py::get_store`、`Q/src/qmt_platform/common/fact_store.py`；`C/src/qmt_platform/services/console/config_activation.py` | WT 消费配置并运行；配置编辑校验、版本diff、激活记录、回退和个人自选迁入 | 新仓库发布的配置可回读；并发激活只有一个生效版本；失败回退状态可解释；个人观察与策略交易范围隔离 |
| F09 回测、模拟、比较与晋级 | `S/replay/app.py`、`platform_backtest.py`、`fill_model.py`、`performance.py`、`comparison*.py`、`release_gates.py`、`promotion_reviews.py` | WT-B01–B03 承接回放/撮合/费用；任务、数据集冻结、报告与比较、晋级证据迁入；QMT 专属回测运行和旧通用撮合退出最终底座 | A股/ETF 费用/最小手续费、T+1、价格/时钟口径核准；报告、逐成交、持仓演进和收益指标可复算；合成模拟资格单列 |
| F10 研究评分/报告与统计校准 | `S/research/app.py`、`baseline.py`、`calibration.py`、`evaluation.py`、`news_scoring.py`、`observed_cohorts.py` | 已退役：新闻/研究及其配套工作流不进入产品；F14只允许剥离必要策略事实/独立观察接缝 | 清理新仓库专属实现、调用、测试和依赖；不再作为迁入完成条件 |
| F11 多角色研究/经理与文件执行器 | `S/research/m12_routes.py`、`multi_role/`、`executor_files.py`、`file_routes.py` | 已退役：新闻/研究及其配套工作流不进入产品；F14只允许剥离必要策略事实/独立观察接缝 | 清理新仓库专属实现、调用、测试和依赖；不再作为迁入完成条件 |
| F12 新闻接纳、治理与正文 | `S/news/app.py`、`candidate_promotion.py`、`governance.py`、`media_*.py`、`historical_extraction.py` | 已退役：新闻/研究及其配套工作流不进入产品；F14只允许剥离必要策略事实/独立观察接缝 | 清理新仓库专属实现、调用、测试和依赖；不再作为迁入完成条件 |
| F13 新闻自动采集与发现 | `S/news_collector/app.py`、`engine.py`、`retry_*.py`、`history_*.py`、`connectors/`；`S/news/discovery_*.py` | 已退役：新闻/研究及其配套工作流不进入产品；F14只允许剥离必要策略事实/独立观察接缝 | 清理新仓库专属实现、调用、测试和依赖；不再作为迁入完成条件 |
| F14 研究数据与第一方资料 | `S/research_data/app.py`、`collection_scheduler.py`、`first_party_scheduler.py`、`connectors/official/`、`connectors/first_party/` | 已退役：新闻/研究及其配套工作流不进入产品；F14只允许剥离必要策略事实/独立观察接缝 | 清理新仓库专属实现、调用、测试和依赖；不再作为迁入完成条件 |
| F15 社交来源/人物发言与浏览器采集 | `S/research_data/x_routes.py`、`statement_*.py`、`browser_capture/`、`connectors/social_x/` | 已退役：新闻/研究及其配套工作流不进入产品；F14只允许剥离必要策略事实/独立观察接缝 | 清理新仓库专属实现、调用、测试和依赖；不再作为迁入完成条件 |
| F16 按需证据计划/能力快照 | `S/research_data/evidence_*.py`、`postgres_evidence_plan_store.py`、`S/research/market_coordination.py` | 已退役：新闻/研究及其配套工作流不进入产品；F14只允许剥离必要策略事实/独立观察接缝 | 清理新仓库专属实现、调用、测试和依赖；不再作为迁入完成条件 |
| F17 外部提供方/配额/RSS/金融观察 | `S/external_provider/app.py`、`repository.py`、`ledger.py`、`rss_*.py`、`news_aggregator_*.py` | 已退役：新闻/研究及其配套工作流不进入产品；F14只允许剥离必要策略事实/独立观察接缝 | 清理新仓库专属实现、调用、测试和依赖；不再作为迁入完成条件 |
| F18 市场观察独立产品 | `S/research_data/market_observation/`；`Q/deploy/observation/`；`C/frontend/console/src/observation/` | 业务迁入：行情外的利差/宏观/期权PCR/跨市场/期货/其他目录指标、计算/来源质量/快照/导出；可用WT行情输入替换重合行情获取 | 指标目录完整、公式及来源/单位可见；图表导出同版本、原件谱系、发布CAS/并发采集锁/恢复；旧独立Docker形态只作参考 |
| F19 原生执行记录与故障解释 | `S/audit/app.py`、`order_trace.py`、`event_ledger.py`、`reconciliation.py` | 复用WT订单/成交、资金及运行日志；观衡展示来源、配置与执行关联及异常。不迁入独立审计账本、研究关联或周期多账本对账门禁 | 实际查询和原生push覆盖范围明确；未知委托可按原ID核查；展示错误与交易准入条件分别说明 |
| F20 运营、故障、资源、日志与回执 | `S/operations/app.py`、`health.py`、`log_query.py`、`runtime_issues.py`、`resources.py`、`workbench.py`、`conversation_receipts.py` | WT-O01/O02 运行输出复用；中文故障解释、资源预算/日志状态、死信重放、任务回执验证迁入 | 新进程状态与业务完整性分开；错误/恢复/空状态及原始次数保留；重放须有现行权限；不绑定旧Docker健康检查 |
| F21 独立发布/配置读取资格/回滚 | `S/operations/platform_release.py`、`coordinated_release*.py`、`deployment.py`、`maintenance_release.py`；`Q/scripts/` 受管发行入口 | 迁入版本绑定、回执、回滚及用户可见验真原则；旧Compose/源码制品登记/旧门禁实现退出，不能成为新开发前置 | WT核心/插件与观衡版本可独立发行，ABI/配置/状态兼容矩阵可检验；搬迁包离线安装/恢复；旧树撤掉后仍能构建和发布 |
| F22 必要消息、配置与回测结果 | `S/relay/app.py`、`Q/src/qmt_platform/common/{consumer,fact_store,object_store}.py`；业务各repository | WT进程内调度和通知优先承接；配置版本、回测任务/报告按已交付独立应用保存，其他持久后端须论证实际必要性 | 配置与报告重启可读；必要并发、超时和恢复可验；行情无PG副本，不引入审批状态或强制旧消息集群 |
| F23 最小券商接入与共享内存 | `Q/qmt_agent/gateway/`、`runtime.py`、`journal.py`、`security.py`；`S/broker_host/`；WT `src/GuanhengQmtBootstrap`、`src/TraderQMTReadOnly` | 必要接入归独立connectors/qmt_shm Host/Agent及原生Parser/Trader；共享内存开发已获准，按QSW实施；终端HTTP退役，TDX交易继续暂缓 | Python3.6/原策略线程、认证代际、原请求认领和资源退出；行情/历史/账户/交易分别验收，构建运行无旧业务源码依赖 |

配置持久入口由 `S/control/app.py::get_store` 返回 `PostgresFactStore`，因此新配置模块须抽取独有业务职责，避免因复制旧工厂连带引入全量事实库。

### 策略算法清单与原生接线差额

实际策略定义共有五个目录，另有通用 ETF 规则和补单规则入口。依据 `S/strategy/strategies/*/definition.json`、`registry.py`、`rules.py`、`replenishment_policy.py`；定义存在只证明注册范围，不代表五个策略都在生产启用。

| 策略 | 源码差额 | 迁入条件 |
|---|---|---|
| `resonance-regime-v1@1.0.0` | `resonance_regime_v1/{features,signals,strategy,allocation,incremental_state,configuration}.py`；原件/观察归档辅助模块 | 算法/状态迁入，通用ledger/replay由WT承接；指标窗口、因果辅助输入、预热和目标变化逐项对照 |
| `resonance-regime-v2@0.1.0` | `resonance_regime_v2/` 算法/配置及回测参数 | 同核目标及原生撮合差异报告，费用/T+1条件独立证明 |
| `resonance-regime-v3@0.1.0` | `resonance_regime_v3/{strategy,allocation}.py` 动态风险 | 风险档位/资本与状态边界逐字段迁移，不能仅复制信号输出 |
| `resonance-regime-v3-hysteresis@0.1.0` | `resonance_regime_v3_hysteresis/{strategy,allocation,prospective}.py` | 迟滞/前瞻资格和重启状态一致，停用/恢复不重复产生交易目标 |
| `resonance-regime-ai-v1@0.1.0` | `resonance_regime_ai_v1/{strategy,overlay}.py` | AI评分的可获知时间/失效规则、基础策略状态与AI覆盖分开验证 |
| 通用 ETF rule 与补单规则 | `rules.py`、`replenishment_policy.py`、`replenishment_risk_policy.py` | 保留用户规则，统一目标进入WT运行；是否激活与可下单权限按新配置事实验证 |

## 定时、事件消费和恢复职责

下列任务来自真实启动代码和循环，不以旧架构文档宣称其当前已在运行。具体时间/开关取配置；迁移不自动启用旧采集、交易或清理任务。

| 原触发与源码 | 功能归属和最终处理 | 验收重点 |
|---|---|---|
| `S/bridge/app.py::bridge_lifespan`、`gateway_runtime.py` 的同步线程、行情worker与 `_collect_scheduled_daily` | 券商读取/源恢复迁入最小接入；分钟运行/市场落地由WT承接；日线研究获取是否仍需独立任务按实际来源契约确定 | 有界队列、线程owner、停止join、单请求身份和在途结果；不增加用户未要求的重复日线/分钟底座 |
| `S/strategy/app.py::_worker_lifespan`、`_reconcile_latest_resonance_target_forever`，消费 daily.closed/history-repaired 等事件 | 重合调度/分钟窗口采用CTA；业务评分/配置等独立事件保留相应事实消费 | 补发不当实时交易、重启只恢复有效最新状态；目标/事件代际及处理效果可追溯 |
| `S/portfolio/app.py::_run_simulation_automation_forever` 与 `replenishment_scheduler.scan_deadlines` | WT执行接管通用目标执行；策略特有补单期限沿其显式配置，旧逐单人审与资本拨付工作流退出目标 | default-off资格、未知命令、部分成交和deadline恢复不重复执行 |
| `S/audit/app.py::_reconciliation_loop` | 核每个对账规则的真实职责；基础持仓查询/原生记录复用，用户追踪/异常展示迁入 | 不把旧重复账本差异原封不动带为全局交易门禁；实际阻断规则须可解释 |
| `S/news_collector/app.py::_scheduler_loop`、`_retry_recovery_loop` | 已退役：本任务循环、重试、发现与媒体dispatch均不迁入或启动 | 调度窗口、租约/重启、单源失败、重复及授权、限额保持 |
| `S/research/app.py::_m12_scheduler_loop`、`_manager_invocation_recovery_loop`；`multi_role/scheduler.py` | 已退役：研究周期与经理工作流不迁入或启动 | 可配置cutoff/交易日历、数据发布时刻、一个业务窗口一次效果、过期claim恢复 |
| `S/research_data/app.py::_collection_scheduler_loop`、`_evidence_deadline_loop`、`_evidence_plan_execution_loop` | 已退役：研究采集与证据执行工作流不迁入；保留的策略辅助事实仅沿F14明确窄接缝 | 当前权限、可获知时间、owner授权、未知效果/重启恢复，不因调度存在自动批准采集 |
| `S/research_data/first_party_scheduler.py`、`connectors/social_x/search_scheduler.py` | 已退役：第一方/X检索子调度不迁入或启动 | 共用业务窗口/配额/来源权限，隔离来源失效 |
| `S/research_data/market_observation/scheduler.py::tick`、`cli.py schedule` | 独立观察定时更新/补发迁入 | 当前实现使用PG会话锁和两日有界扫描；换介质时保留跨进程排他、窗口完成记录与原子发布，不能简单替换成内存timer |
| `common/source_acquisition_runtime.py` 的恢复/清理调用链（由 news/news_collector/research_data lifespan 装配） | 已退役：新闻/研究来源的采集恢复与正文任务不迁入；历史原件按保留要求处理 | 清理任务权限单独核准，原始内容/撤回/保留期限和失败恢复可验证 |
| `S/relay/app.py::_relay` | 旧数据库outbox→NATS重放；仅为保留的独立异步业务重建最小确认路径 | 单owner/幂等/持久效果；WT行情/策略进程内调度退出这条链 |
| WT `reader_service.py`/历史runner/分钟consumer候选 | 先按原生Reader/Factory/CTA公共能力收敛；独立任务界面和业务确认保留必要差额 | 同实例缓存更新、闭合分钟资格、队列/重入/关闭、有界资源；候选存在不预设全部进入最终默认运行 |

## 旧工程依赖位置与退出条件

| 依赖面 | 实际源码位置与已核事实 | 新仓库处理 |
|---|---|---|
| 旧服务装配 | `Q/docker-compose.yml` 的 `x-platform-service` 给普通服务共同加入 postgres/nats/migrate；各服务command指向 `qmt_platform.services.*.app:app` | 按上表业务重组独立宿主；不要复制共同depends_on作为新默认前置 |
| Python发行 | `Q/Dockerfile` 复制src/qmt_agent/config/第三方目录/SQL迁移及网关契约；`Q/pyproject.toml` 全局依赖含psycopg、nats、minio、pydantic/FastAPI/HTTP | 独立最小包只声明实际依赖；源码和资产迁入本仓库，旧源路径/importlib加载仅作迁移验证，退出最终制品 |
| 浏览器构建 | `C/frontend/console/package.json` 各pre钩子调用 `scripts/prepare-host-storage.mjs`，`vite.config.ts`及旧宿主存储规则；`frontend/console/Dockerfile*` | 保留React/路由/图表业务，改由本仓库独立前端构建和静态安装；不执行旧pre钩子或依赖旧生成目录 |
| Console运行耦合 | `C/src/qmt_platform/services/console/app.py` 顶层引入全量contracts/overview/研究投影/operations helper；`client.py` 读取旧服务URL；`common/settings.py` 有全平台默认端点 | 分功能窄模块/DTO与显式依赖；新版服务发现只指向新模块；未迁入功能明确不可用，禁止偷偷连回旧服务 |
| 行情/业务SQL | `Q/src/qmt_platform/common/fact_store.py::PostgresFactStore` 同时拥有bars、特征、新闻/评分等多类事实；`S/portfolio/*store.py`、`S/bridge/store.py` 等直接用PG | 原生行情数据退出PG；独有业务事实逐项确定最小持久后端；存在SQL不证明必须保留PG，必要数据库遵守Windows原生部署 |
| 可靠消息 | `common/consumer.py`、`event_bus.py`、`S/relay/app.py` 和各lifespan消费器 | WT调度替代的跳转退出；仍独立的任务确认按实际需要选择机制，不默认安装整个旧NATS集群 |
| 原件/报告资产 | `common/object_store.py` Minio客户端；`S/research/multi_role/object_store.py`、各archive模块 | 原件/内容SHA、版本/权限和回执继续保留；对象介质可替换，保持可读/撤回/并发发布语义，不能随代码退役丢失 |
| 市场观察专用部署 | `Q/deploy/observation/compose.yaml` 明确PG、Minio、owner及scheduler；`market_observation/storage.py` 有本地ContentStore、隔离MemoryRepository及PostgresRepository能力差异，`scheduler.py`依赖PG lease | 独立业务代码迁入；PG锁/CAS/发布窗口语义先证明替代，再决定介质；不把该Docker部署当成新目标 |
| 监控/日志 | `Q/docker-compose.yml` observability profile：Prometheus/Alertmanager/Loki/Alloy/Grafana；Operations页面嵌六个大盘 | Grafana服务、嵌入大盘、Viewer及相关门禁退役；只保留核心健康、日志及故障定位，不绑定旧监控容器 |
| 宿主发布/运维 | `S/operations/{platform_release,deployment,coordinated_release_executor}.py`；`Q/scripts/`与 `.github/workflows/` 旧流程 | 重用版本、验真、回滚和证据原则；新仓库工具独立实现，旧制品登记/策略源码漂移/开发启动预算退出迁移前置 |
| QMT终端包 | `Q/qmt_agent/` 的HTTP/策略线程/Journal、`Q/docs/contracts/qmt-gateway-operations.json` | 符合终端Python3.6的最小代码和必要契约资产进入新仓库；部署/终端重启/真实交易依明确授权；SHM由本仓库独立连接包承接，新WT绑定进行中 |
| 本地Journal与内容库位置 | `Q/qmt_agent/config.py` 默认 `journal_path` 为配置文件旁 `runtime.db`，`runtime.py` 将其交给 `CommandJournal`（SQLite）；`S/broker_host/bootstrap.py` 检查host与execution Journal分离；观察 `runtime.py` 用 `QMT_SHARED_DATA_ROOT`，默认 `E:/workspace/qmt-storage/shared-data`，内容对象按 `objects/sha256/<前缀>/<摘要>` 存放 | 需要保留的命令事实和内容原件分别清点，不因平台目录退役丢弃；默认值不代表当前生产实际路径，生产环境覆盖和Docker卷实际落盘需在切换操作中只读核实 |
| WT现有外部源码门面 | 本仓库 `integrations/guanheng/dependencies.py`、`upstream-contracts.json`、`shadow.py`、`business_flow.py`、`market_compat.py` | `ExternalQmt` 当前从明确外部源根加载原策略/DTO/Portfolio/Bridge/Console，仅证明迁移对照；最终改由本仓库自有业务包，不将“可传旧源根”当可部署迁入 |

对旧目录执行停用/删除、变更数据库、搬移账户状态或重启券商终端均不由本文授权。

## 首批独立 Console 与分钟图的最小实施输入

首批切片交付独立宿主、原生分钟主图/基准、原页面正常/空/错误/恢复和来源说明。它是整个产品迁移的第一批；其余页面/业务继续按本清单逐项交付。源码拷贝前按下面边界抽取，不把完整旧服务作为依赖安装。

| 输入与最小源文件 | 保留内容/处理方式 | 本仓库验证入口 |
|---|---|---|
| `C/src/qmt_platform/common/native_chart.py` | `build_native_chart`、symbol准入、独立SDK查询/状态映射、右端WT→图表左端转换；迁入新业务包，调整自有DTO/设置导入 | 原真实SDK/Reader数据，1m/5m、最多N、before分页、基准与总预算、错误恢复；不读SQL/旧报价作为分钟兜底 |
| `C/src/qmt_platform/common/contracts.py` 的 `MarketChartBundle`、`MarketChartCandle`、`MarketChartNativeSource` 及字段/校验依赖；`contract_kernel.py` | 抽取实际必要DTO及严格验证，保留协议版本/字段语义；使用全量contracts只能作临时抽取输入，不能把其全部业务依赖带为运行前提 | SDK响应身份、数量/单位/复权/coverage校验；错误不伪装空数据，外部细节/凭据不回显 |
| `C/src/qmt_platform/common/settings.py` 图表相关字段与 `services/console/app.py::ui_market_chart` 的分钟分支 | 新显式图表配置和窄路由；分钟分支原主/可选预算可重用；账户/新闻/策略标记通过新接口可选注入，不复制旧client路由发现 | 独立包未配置时明确中文unavailable；配置有效走一次有界SDK；可选标记失败不阻断主行情 |
| `C/src/qmt_platform/services/console/optional_reads.py`、`market_projection.py` 图表相关函数 | 只保留必要有限worker与来源/标记投影；独立宿主拥有启动/关闭，核实取消超时后的worker真实结束 | 并发压力、截止、回调重入/异常、退出等待；多次启动退出不遗留线程/连接 |
| `C/frontend/console/src/pages/MarketPage.tsx`、`components/MarketCandlestickChart.tsx`、`api.ts`、`types.ts` | 迁入完整页面所需呈现，但api/types中只抽实际图表/观察接口；必要自选/搜索另有明确新owner，首批缺口显式标注 | 页面点击证券/周期/加载历史、空/错/恢复、来源/时间/量；对齐服务端限额及真实数据 |
| `C/frontend/console/src/{main,App}.tsx`、样式/组件/图片及其相对import资源、`index.html`、TS/Vite配置、package-lock | 页面资源按实际相对import闭包迁入；壳层剥离全局账户bootstrap和未迁业务强依赖；新包自己的npm脚本不调用旧存储pre钩子 | 新目录按lock执行npm ci/build后静态安装；深链可打开；网络只连新服务，旧树不可见仍启动 |
| `C/tests/phase4/test_wondertrader_market_chart.py`、`run_wondertrader_market_chart_integration.py`；前端相应Market图表测试 | 迁入行为断言及必要fixture并调整新的包入口；原脚本只读参考，本任务不执行旧测试/原门禁 | 独立安装SDK和批准原生DLL、真实QMT样本、HTTP/页面整链；测试不能通过旧PYTHONPATH或旧源码加载 |
| 本仓库 `integrations/guanheng_market_client/` 与自有Reader/Factory ABI及其受管配置/基础资料 | 独立SDK/原生服务负责分钟/周期；Console不直接加载WT DLL，明确版本/摘要和HTTP契约 | 搬迁后无旧仓库、QMT旧平台服务、全局源码路径、PG/NATS分钟依赖；SDK依赖来自新受管发行物 |

文件名具体存在性及相对import闭包需要在实施时固定清单：首批不能只迁一段函数而遗漏DTO校验、样式或必要资产。上述为最小职责输入，不宣称列举的少数文件足以原样运行全页。静态追踪完整 `C/src/qmt_platform/services/console/app.py` 的 `qmt_platform` 本地import（含函数内部import）的可解析闭包为296个模块，跨入research_data采集、FactStore、ObjectStore和策略算法；这是潜在依赖图，不是实际启动时296个模块全部导入的证明。该事实支持先拆职责/窄接口，避免把全量旧 `app.py` 复制为最终宿主。

## 分批验收与全量退出核对

1. 独立 Console/原生分钟图：完成上一节输入、安装和页面整链，登记未迁入模块，旧树不可见条件实测。
2. 配置、自选、账户只读/策略归属、订单与运营展示：分别用WT/QMT来源和独有业务状态接线；实际持仓读取与业务资本/审批记录分开证明。
3. 策略和回测：五策略及规则按WT原上下文/回放迁入，状态、费用、T+1、研究辅助输入逐项核对；保留独有算法，退出通用旧引擎。
4. 市场观察及保留业务运营按独立需求推进；新闻、研究及配套资料/采集/证据工作流退出迁入，不重新实现原服务。
5. 执行写链：只读查询资格与委托资格分别取得证据；新最小接入/唯一命令owner完成授权、幂等和未知结果恢复后，再按明确授权进行实际交易/切换。
6. 全量退出审核：保留范围的页面、附录业务路由与任务均有新入口、原生替代或经确认退役项；从新仓库干净安装/搬迁、旧源码不可见、旧服务全不可达时验证完整产品；核账户/未决命令/历史资料已受控交接。旧资源删除另行处理。

以下路由是业务表的范围检查索引。路径存在只证明实现入口；保留原URL、重命名或退役在对应规格决定，不要求复制全部旧HTTP跳转。旧内部协作路由中被原生同进程调用替代的部分随旧职责退出。

## HTTP 声明完整目录

静态范围：`Q/src/qmt_platform/services/**/*.py` 的非测试Python路由及三个共同路由工厂，共 441 个声明、33 个源文件。包括条件/嵌套路由；没有按实际profile启用过滤。每行给方法、拼接后的路径及函数起始行。全局工厂按模板列出，不把同一模板每次装配重复计数。未通过运行OpenAPI验证动态装配；FastAPI默认文档端点、CORS及HEAD等框架行为不在业务API计数内。

APIRouter前缀已合并：first-party leadership、social-x、statements、statement-display与Console观察代理。`{API_PREFIX|UI_PREFIX}` 分别为 `/v1/research-data/market-observation`、`/v1/ui/market-observation`；观察owner仅装配API版，独立app装配两版，`assets/{asset_id}`仅API版。共同source-health/replay的 `{prefix}` 由 `/v1/news`、`/v1/research-data`、`/v1/research-data/social-x` 或隔离 `/v1/isolated-social` 的装配点指定；各模板实际适用者以原app.include_router为准。Console/source_replay两条直接路径已展开。

### audit（12 个声明）

`Q/src/qmt_platform/services/audit/app.py`，SHA-256 `fd756b2fb4083aadc4dad0308582fb52760048af041b33f3c49562cbe30a2e20`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| POST | `/v1/audit/events` | `append_event:51` |
| GET | `/v1/audit/event-ledger` | `event_ledger:57` |
| GET | `/v1/audit/event-stream` | `event_stream:86` |
| GET | `/v1/audit/operator-actions` | `operator_action_history:101` |
| GET | `/v1/audit/event-ledger/export` | `export_event_ledger:116` |
| GET | `/v1/audit/trace` | `trace:142` |
| GET | `/v1/audit/order-trace/{correlation_id}` | `order_trace:150` |
| POST | `/v1/audit/reconciliations` | `save_reconciliation:183` |
| POST | `/v1/audit/reconcile/{agent_id}` | `reconcile_agent:239` |
| GET | `/v1/audit/reconciliations/{agent_id}/latest` | `latest_reconciliation:270` |
| GET | `/v1/audit/export` | `export_events:283` |
| GET | `/v1/audit/daily-report/{agent_id}` | `daily_report:329` |

### bridge（33 个声明）

`Q/src/qmt_platform/services/bridge/app.py`，SHA-256 `2aa6fd0434e5ad95eb93e04cffe150ea4baabf0e3048850e023171ce35003477`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/v1/internal/resonance/history-recovery` | `resonance_history_recovery_status:363` |
| GET | `/v1/internal/market-bar-workers` | `market_bar_workers:461` |
| GET | `/v1/internal/daily-bar-acquisition` | `daily_bar_acquisition:472` |
| GET | `/v1/internal/trading-calendar/observation` | `trading_calendar_observation:488` |
| GET | `/v1/internal/orders` | `order_ledger:522` |
| GET | `/v1/internal/market-executions` | `market_execution_markers:555` |
| GET | `/v1/internal/portfolio/performance` | `portfolio_performance:581` |
| GET | `/v1/internal/portfolio/positions` | `portfolio_positions:600` |
| GET | `/v1/internal/portfolio/strategy-contributions` | `portfolio_strategy_contributions:617` |
| GET | `/v1/internal/qmt/operation-latency` | `operation_latency:631` |
| POST | `/v1/qmt/heartbeat` | `heartbeat:666` |
| POST | `/v1/qmt/snapshots` | `snapshot:678` |
| POST | `/v1/qmt/quotes` | `quote:690` |
| POST | `/v1/qmt/bars` | `bar:702` |
| POST | `/v1/qmt/events` | `event:722` |
| GET | `/v1/qmt/commands` | `commands:734` |
| POST | `/v1/qmt/commands/{command_id}/ack` | `acknowledge:746` |
| GET | `/v1/internal/qmt/gateway/health` | `gateway_health:811` |
| GET | `/v1/internal/qmt/connection-status` | `qmt_connection_status:822` |
| GET | `/v1/internal/qmt/gateway/capabilities` | `gateway_capabilities:845` |
| GET | `/v1/internal/replenishment/capabilities` | `replenishment_capabilities:856` |
| POST | `/v1/internal/qmt/operations/{operation_id}` | `gateway_operation:872` |
| GET | `/v1/internal/market-data-subscriptions` | `market_data_subscriptions:926` |
| GET | `/v1/internal/qmt-history-universe` | `qmt_history_universe_status:936` |
| POST | `/v1/internal/market-data-refresh/{symbol}` | `refresh_market_chart:946` |
| GET | `/v1/internal/qmt/operation-results/{request_id}` | `gateway_operation_result:1078` |
| GET | `/v1/internal/simulation/status` | `simulation_status:1116` |
| POST | `/v1/internal/simulation/quotes/refresh` | `refresh_simulation_quotes:1284` |
| GET | `/v1/internal/commands/controlled-simulation-batches` | `list_controlled_simulation_command_batches:1323` |
| POST | `/v1/internal/commands/issue-controlled-simulation-batch` | `issue_controlled_simulation_command_batch:1337` |
| GET | `/v1/internal/commands/{command_id}/progress` | `replenishment_command_progress:1381` |
| POST | `/v1/internal/commands/issue` | `issue_command:1397` |
| POST | `/v1/internal/commands` | `legacy_enqueue_disabled:1677` |

### broker_host（2 个声明）

`Q/src/qmt_platform/services/broker_host/app.py`，SHA-256 `405c93fec78d6a07ecf50203de292efc76b8c1d20f27b882d230905e389eeebc`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/health` | `health:38` |
| GET/POST | `/internal/v1/{path:path}` | `exchange:42` |

### common-shared（11 个声明）

`Q/src/qmt_platform/common/service.py`，SHA-256 `06548b7a8e797270018c5829d2c0d257028565b049ec5a24eab41c9e7540e78a`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| POST | `/v1/configuration-read-check` | `configuration_read_check:281` |
| GET | `/health/live` | `live:366` |
| GET | `/health/ready` | `ready:370` |
| GET | `/metrics` | `metrics:380` |
| POST | `/v1/internal/memory-snapshot` | `memory_snapshot:499` |

`Q/src/qmt_platform/common/source_health_routes.py`，SHA-256 `3161474237479d887224f84b5edcae7c4ecb9440b02e8ab7d3343ae42c5453d5`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `{prefix}/sources/acquisition-health` | `read:22` |
| GET | `{prefix}/sources/{source_id}/acquisition-windows/{window_id}` | `operations:32` |
| GET | `{prefix}/sources/{source_id}/acquisition-operations/{operation_id}` | `attempts:44` |
| GET | `{prefix}/sources/{source_id}/acquisition-alerts` | `alerts:54` |

`Q/src/qmt_platform/common/source_replay_routes.py`，SHA-256 `7f07263f11adb4a2ee4bee311067e4b3784a15cb32a82132b5a0790df4df29a9`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| POST | `{prefix}/source-replay/preview` | `preview:52` |
| POST | `{prefix}/source-replay/append` | `append:56` |

### console（78 个声明）

`Q/src/qmt_platform/services/console/acquisition_health.py`，SHA-256 `afed4c67a2ae97854278877e14b35fc5a0e70e5f1241f12f41aca6cf08bf9cfd`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/v1/ui/research/acquisition-health` | `read:164` |
| GET | `/v1/ui/research/acquisition-windows/{owner}/{source_id}/{window_id}` | `operations:173` |
| GET | `/v1/ui/research/acquisition-operations/{owner}/{source_id}/{operation_id}` | `attempts:191` |
| GET | `/v1/ui/research/acquisition-alerts/{owner}/{source_id}` | `alerts:202` |
| GET | `/v1/ui/research/news-discovery` | `discovery:218` |

`Q/src/qmt_platform/services/console/app.py`，SHA-256 `6a82d65a087bfa70fe402fa9b5f44a9f53f0ccbf37a6bb545396ef72c3217cb4`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/v1/ui/news/pipeline` | `ui_news_pipeline:301` |
| GET | `/v1/ui/research/m12` | `ui_m12_research:348` |
| GET | `/` | `index:504` |
| GET | `/observation` | `observation_workspace:511` |
| GET | `/observation/{path:path}` | `observation_workspace:511` |
| GET | `/legacy` | `legacy_index:516` |
| GET | `/{workspace}` | `spa_workspace:520` |
| GET | `/v1/console/overview` | `overview:528` |
| GET | `/v1/ui/bootstrap` | `ui_bootstrap:536` |
| GET | `/v1/ui/project/status` | `ui_project_status:563` |
| GET | `/v1/ui/audit/controlled-simulation-deployment-readiness` | `ui_controlled_simulation_deployment_readiness:580` |
| GET | `/v1/ui/operations/workbench` | `ui_operations_workbench:632` |
| GET | `/v1/ui/operations/error-logs` | `ui_operations_error_logs:653` |
| GET | `/v1/ui/orders/execution-queue` | `ui_execution_queue:711` |
| GET | `/v1/ui/orders/account-execution-batches` | `ui_account_execution_batches:750` |
| GET | `/v1/ui/qmt/connection-status` | `ui_qmt_connection_status:770` |
| GET | `/v1/ui/watchlists/default` | `ui_default_watchlist:784` |
| GET | `/v1/ui/problem-definitions` | `ui_problem_definitions:792` |
| GET | `/v1/ui/problem-dictionary` | `ui_problem_dictionary:813` |
| GET | `/v1/ui/market/suggestions` | `ui_market_suggestions:826` |
| PUT | `/v1/ui/watchlists/default` | `ui_update_default_watchlist:964` |
| GET | `/v1/ui/market/chart/{symbol}` | `ui_market_chart:1017` |
| GET | `/v1/ui/market/subscriptions` | `ui_market_data_subscriptions:1163` |
| GET | `/v1/ui/audit/resonance-daily-coverage` | `ui_resonance_daily_bar_coverage:1199` |
| GET | `/v1/ui/audit/resonance-shadow/latest` | `ui_latest_resonance_shadow_acceptance:1219` |
| GET | `/v1/ui/audit/simulation-acceptance/latest` | `ui_latest_simulation_acceptance:1236` |
| GET | `/v1/ui/audit/simulation-cycle/status` | `ui_simulation_strategy_cycle_status:1262` |
| GET | `/v1/ui/portfolio/replenishment` | `ui_replenishment:1267` |
| GET | `/v1/ui/market/quote/{symbol}` | `ui_market_quote:1274` |
| GET | `/v1/ui/market/public-observation/{symbol}` | `ui_public_observation:1358` |
| GET | `/v1/ui/portfolio/pnl` | `ui_portfolio_pnl:1382` |
| GET | `/v1/ui/portfolio/positions` | `ui_portfolio_positions:1464` |
| GET | `/v1/ui/strategies/{strategy_id}/capital-history` | `ui_strategy_capital_history:1487` |
| GET | `/v1/ui/portfolio/performance` | `ui_portfolio_performance:1528` |
| GET | `/v1/ui/portfolio/contributions` | `ui_portfolio_contributions:1552` |
| GET | `/v1/ui/portfolio/allocation` | `ui_portfolio_allocation:1571` |
| GET | `/v1/ui/strategies/registry` | `ui_strategy_registry:1646` |
| GET | `/v1/ui/strategies/runtime` | `ui_strategy_runtime:1656` |
| GET | `/v1/ui/strategies/eligibility` | `ui_strategy_eligibility:1667` |
| GET | `/v1/ui/strategies/{strategy_id}/versions/{strategy_version}` | `ui_strategy_workbench_detail:1711` |
| GET | `/v1/ui/strategies/{strategy_id}/versions/{strategy_version}/simulation-intent-preflight` | `ui_controlled_simulation_intent_preflight:2206` |
| GET | `/v1/ui/strategies/{strategy_id}/versions/{strategy_version}/simulation-order-preview` | `ui_controlled_simulation_order_preview:2297` |
| GET | `/v1/ui/strategies/{strategy_id}/versions/{strategy_version}/simulation-operator-reviews` | `ui_controlled_simulation_operator_reviews:2340` |
| GET | `/v1/ui/strategies/{strategy_id}/versions/{strategy_version}/simulation-execution-authorizations` | `ui_controlled_simulation_execution_authorizations:2372` |
| GET | `/v1/ui/strategies/{strategy_id}/versions/{strategy_version}/simulation-command-batches` | `ui_controlled_simulation_command_batches:2404` |
| GET | `/v1/ui/configs` | `ui_configs:2433` |
| GET | `/v1/ui/configs/activations` | `ui_config_activations:2443` |
| GET | `/v1/ui/configs/{from_config_id}/diff/{to_config_id}` | `ui_config_diff:2453` |
| GET | `/v1/ui/orders` | `ui_orders:2516` |
| GET | `/v1/ui/orders/recent` | `ui_recent_orders:2557` |
| GET | `/v1/ui/orders/{correlation_id}/trace` | `ui_order_trace:2572` |
| GET | `/v1/ui/audit/promotion-reviews` | `ui_promotion_reviews:2587` |
| GET | `/v1/ui/audit/events` | `ui_audit_events:2603` |
| GET | `/v1/ui/audit/operator-actions` | `ui_operator_action_history:2646` |
| GET | `/v1/ui/audit/events/export` | `ui_export_audit_events:2663` |
| GET | `/v1/ui/backtests/reports` | `ui_backtest_reports:2714` |
| GET | `/v1/ui/backtests/reports/{report_hash}` | `ui_backtest_report:2732` |
| GET | `/v1/ui/backtests/reports/{report_hash}/analytics` | `ui_backtest_analytics:2748` |
| GET | `/v1/ui/backtests/reports/{report_hash}/trades` | `ui_backtest_trades:2769` |
| GET | `/v1/ui/backtests/reports/{report_hash}/positions` | `ui_backtest_positions:2797` |
| GET | `/v1/ui/backtests/comparisons` | `ui_backtest_comparisons:2819` |
| GET | `/v1/ui/backtests/comparisons/{report_id}` | `ui_backtest_comparison:2839` |
| GET | `/v1/ui/backtests/datasets` | `ui_backtest_datasets:2853` |
| GET | `/v1/ui/backtests/jobs` | `ui_backtest_jobs:2867` |
| GET | `/v1/ui/backtests/jobs/{job_id}` | `ui_backtest_job:2881` |
| GET | `/v1/ui/stream` | `ui_stream:2889` |

`Q/src/qmt_platform/services/console/market_observation.py`，SHA-256 `7452d99a356728a60b3d95abfca8d4b58c51bf90b7b56b0e507ffb856ce1ddf4`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/v1/ui/market-observation/exports` | `exports:24` |
| GET | `/v1/ui/market-observation/{path:path}` | `get:54` |

`Q/src/qmt_platform/services/console/source_replay.py`，SHA-256 `be78e5d62cda3d7db36b9d365509a2d4a75897e8b8909435c7ac6c7006885978`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| POST | `/v1/ui/research/source-replay/{owner}/{source_id}/{operation_id}/{attempt_sequence}/preview` | `preview:47` |
| POST | `/v1/ui/research/source-replay/{owner}/{source_id}/{operation_id}/{attempt_sequence}/append` | `append:67` |

`Q/src/qmt_platform/services/console/statements.py`，SHA-256 `a14ddcc878125533759f1123a57d4896d79eea96790bfcb5867b4e80541f611a`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/v1/ui/research/statements` | `read:17` |
| GET | `/v1/ui/research/statement-display` | `display:31` |
| GET | `/v1/ui/research/statement-display/page` | `display_page:45` |

### control（20 个声明）

`Q/src/qmt_platform/services/control/app.py`，SHA-256 `6a4cef9a5badb5f76410b4deb0a1966851e14e7dc1d9fe9f35b426ea2d2ef0f8`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/v1/control/multi-strategy-qualifications/exact/{identity_sha256}` | `exact_multi_strategy_qualification:161` |
| GET | `/v1/control/watchlists` | `list_watchlists:178` |
| GET | `/v1/control/watchlists/default` | `default_watchlist:186` |
| GET | `/v1/control/watchlists/{watchlist_id}` | `get_watchlist:197` |
| PUT | `/v1/control/watchlists/{watchlist_id}` | `update_watchlist:212` |
| POST | `/v1/configs/validate` | `validate_config:268` |
| GET | `/v1/configs/active/current` | `active_config:278` |
| POST | `/v1/configs` | `create_config:289` |
| GET | `/v1/configs/{config_id}` | `get_config:311` |
| GET | `/v1/configs` | `list_configs:321` |
| POST | `/v1/configs/{config_id}/activate` | `activate_config:326` |
| GET | `/v1/configs/{from_config_id}/diff/{to_config_id}` | `diff_configs:407` |
| POST | `/v1/configs/{config_id}/rollback` | `rollback_config:421` |
| POST | `/v1/control/configs/{config_id}/{action}` | `control_config_version:439` |
| GET | `/v1/control/config-activations` | `config_activations:625` |
| GET | `/v1/control/automation-gate` | `automation_gate:633` |
| PUT | `/v1/control/automation-gate` | `update_automation_gate:638` |
| POST | `/v1/control/simulation-promotions/{config_id}` | `promote_simulation:685` |
| GET | `/v1/control/simulation-promotions/{config_id}` | `simulation_promotion:777` |
| POST | `/v1/control/emergency-stop` | `emergency_stop:794` |

### external_provider（4 个声明）

`Q/src/qmt_platform/services/external_provider/app.py`，SHA-256 `1b53e1e5ac801f59d708ea459d39bfad1906c8e383bc6e8c397b139442524171`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/v1/external-providers/quota/current` | `current_quota:63` |
| GET | `/v1/external-providers/news-candidates` | `list_news_candidates:75` |
| GET | `/v1/external-providers/news-candidates/{candidate_id}` | `get_news_candidate:91` |
| GET | `/v1/external-providers/financial-observations` | `list_financial_observations:106` |

### market_data（24 个声明）

`Q/src/qmt_platform/services/market_data/app.py`，SHA-256 `9e4e8da96ab7b473ec29d76ad145a4954a464b8aa2c22a98bc886cc2c65df880`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/v1/internal/strategy-analysis-window` | `strategy_analysis_window:90` |
| GET | `/v1/internal/strategy-analysis-windows/{revision}` | `archived_analysis_window:104` |
| POST | `/v1/market/corporate-actions` | `record_corporate_action:114` |
| POST | `/v1/market/features` | `features:243` |
| POST | `/v1/market/bars` | `ingest_bar:250` |
| GET | `/v1/market/chart/{symbol}` | `get_market_chart:396` |
| GET | `/v1/market/resonance/daily-coverage` | `get_resonance_daily_bar_coverage:544` |
| GET | `/v1/market/resonance/history-recovery` | `get_resonance_history_recovery_plan:617` |
| POST | `/v1/market/resonance/history-recovery/reconcile` | `reconcile_resonance_history_recovery:633` |
| POST | `/v1/market/resonance/daily-batches` | `ingest_resonance_daily_batch:649` |
| GET | `/v1/market/resonance/daily-batches` | `list_resonance_daily_batches:665` |
| GET | `/v1/market/resonance/daily-batches/{trade_date}` | `get_resonance_daily_batch:692` |
| POST | `/v1/market/resonance/history-repairs` | `repair_resonance_history:715` |
| POST | `/v1/market/imports/validate` | `validate_import:727` |
| POST | `/v1/market/imports` | `import_market_data:732` |
| GET | `/v1/market/imports/{dataset_version}` | `get_market_data_import:750` |
| GET | `/v1/market/imports/{dataset_version}/quality` | `get_market_data_quality:762` |
| POST | `/v1/market/etfs` | `put_etf_metadata:774` |
| GET | `/v1/market/etfs` | `search_etf_metadata:786` |
| GET | `/v1/market/symbols` | `search_known_market_symbols:796` |
| GET | `/v1/market/etfs/{symbol}` | `get_etf_metadata:808` |
| POST | `/v1/market/research-subject-profiles` | `append_research_subject_profile:818` |
| GET | `/v1/market/research-subject-profiles/{symbol}` | `get_research_subject_profile_at:833` |
| POST | `/v1/market/calendar` | `put_calendar:848` |

### news（19 个声明）

`Q/src/qmt_platform/services/news/app.py`，SHA-256 `30dc3c9e94c49bd5f9274bd81bd88d79c476208fb2dc81e3706c54b6ebfeffa3`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/v1/news/sources/health-windows` | `list_acquisition_health_windows:364` |
| POST | `/v1/news/acquisition/accept` | `accept_acquisition:372` |
| POST | `/v1/news` | `ingest:407` |
| POST | `/v1/news/candidate-reviews` | `review_external_candidate:430` |
| GET | `/v1/news/candidate-reviews` | `list_candidate_reviews:453` |
| GET | `/v1/news/candidate-reviews/{review_id}` | `get_candidate_review:466` |
| POST | `/v1/news/candidate-promotions` | `promote_external_candidate:481` |
| GET | `/v1/news/candidate-promotions` | `list_candidate_promotions:510` |
| GET | `/v1/news/candidate-promotions/{promotion_id}` | `get_candidate_promotion:526` |
| POST | `/v1/news/skill` | `ingest_from_skill:538` |
| GET | `/v1/news/sources` | `list_sources:556` |
| GET | `/v1/news/events` | `list_news_events:561` |
| POST | `/v1/news/events/{event_id}/governance` | `govern_news_event:608` |
| GET | `/v1/news/event-governance` | `list_news_event_governance:626` |
| GET | `/v1/news/sources/{source_id}` | `get_source:635` |
| GET | `/v1/news/skill/sources` | `list_skill_sources:647` |
| GET | `/v1/news/status/{content_hash}` | `submission_status:660` |
| POST | `/v1/news/{content_hash}/retract` | `retract:675` |

`Q/src/qmt_platform/services/news/discovery_routes.py`，SHA-256 `3dc76cc6100bf447a353ff582deadcf301ab7cd61485191439a811c1133134f7`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/v1/news/discovery/overview` | `overview:17` |

### news_collector（9 个声明）

`Q/src/qmt_platform/services/news_collector/app.py`，SHA-256 `a8eb6e3198752e353653bf880f8e2e96037b386e36711ea39caa31a21f89ed0e`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| POST | `/v1/media-originals/{site}/run` | `run_media_original:360` |
| GET | `/v1/news-discovery/adapters` | `discovery_adapters:373` |
| POST | `/v1/news-discovery/{adapter_id}/run` | `run_discovery:378` |
| GET | `/v1/news-collectors` | `list_collectors:408` |
| GET | `/v1/internal/news-collector-statuses` | `collector_statuses:418` |
| POST | `/v1/news-collectors/{collector_id}/run` | `run_collector:431` |
| POST | `/v1/news-collectors/{collector_id}/retries` | `retry_failed_collector:447` |
| GET | `/v1/news-collectors/retries` | `list_collector_retries:491` |
| GET | `/v1/news-collectors/reports` | `list_reports:502` |

### operations（17 个声明）

`Q/src/qmt_platform/services/operations/app.py`，SHA-256 `93816eb2d48980626797f4733608be5b60ccb9b168a835aee81e3d0b49eb4e75`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/v1/operations/conversation-receipts/{receipt_sha256}/verification` | `verify_conversation_receipt_artifacts:70` |
| GET | `/v1/operations/resources/latest` | `latest_resources:228` |
| GET | `/v1/operations/memory/soak-runs` | `memory_soak_runs:236` |
| GET | `/v1/operations/log-storage` | `log_storage:245` |
| GET | `/v1/operations/error-logs` | `error_logs:253` |
| GET | `/v1/operations/dead-letters` | `dead_letter_cases:304` |
| POST | `/v1/operations/dead-letters/{consumer_name}/{event_id}/dispositions` | `append_dead_letter_disposition:317` |
| GET | `/v1/operations/storage-budgets` | `storage_budgets:336` |
| GET | `/v1/operations/archive-status` | `archive_status:341` |
| GET | `/v1/operations/workbench` | `operations_workbench:352` |
| POST | `/v1/operations/history-jobs` | `create_history_job:361` |
| GET | `/v1/operations/history-jobs/{job_id}` | `get_history_job:375` |
| POST | `/v1/operations/history-jobs/{job_id}/stop` | `stop_history_job:389` |
| POST | `/v1/operations/history-jobs/{job_id}/resume` | `resume_history_job:403` |
| PUT | `/v1/operations/history-jobs/{job_id}/checkpoint` | `checkpoint_history_job:418` |
| GET | `/v1/operations/history-jobs/{job_id}/result` | `get_history_job_result:436` |
| GET | `/v1/operations/status` | `status:450` |

### portfolio（30 个声明）

`Q/src/qmt_platform/services/portfolio/app.py`，SHA-256 `a7c6e9edd6736e08d674c02b5abc8e255ee2f2fe8799d8c5e4feba6d181c0c76`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/v1/portfolio/ownership-source` | `ownership_source:773` |
| GET | `/v1/portfolio/replenishment` | `replenishment_status:822` |
| GET | `/v1/portfolio/replenishment/capabilities` | `replenishment_capability_status:831` |
| GET | `/v1/portfolio/replenishment/migration-preview` | `replenishment_migration_preview:859` |
| GET | `/v1/portfolio/replenishment/{episode_id}/history` | `replenishment_recorded_history:918` |
| GET | `/v1/portfolio/strategy-target-replacements` | `strategy_target_replacements:926` |
| GET | `/v1/portfolio/replenishment/{episode_id}/basis-recovery` | `preview_basis_recovery:950` |
| POST | `/v1/portfolio/replenishment/basis-recovery` | `commit_replenishment_basis_recovery:975` |
| GET | `/v1/portfolio/simulation/automation-status` | `simulation_automation_status:1618` |
| GET | `/v1/portfolio/account-capital-observation` | `account_capital_observation:1643` |
| GET | `/v1/portfolio/account-capital-reconciliation` | `account_capital_reconciliation:1662` |
| GET | `/v1/portfolio/account-capital-execution-readiness` | `account_capital_execution_readiness:1682` |
| GET | `/v1/internal/strategy-execution-context` | `strategy_execution_context:1709` |
| GET | `/v1/portfolio/strategy-capital-history` | `strategy_capital_history:1734` |
| GET | `/v1/portfolio/strategy-capital-current` | `strategy_capital_current:1782` |
| GET | `/v1/portfolio/strategy-capital-day-opening` | `strategy_capital_day_opening:1804` |
| GET | `/v1/portfolio/account-execution-batches` | `account_execution_batches:1830` |
| GET | `/v1/portfolio/execution-queue` | `execution_queue_projection:1859` |
| GET | `/v1/portfolio/strategy-eligibility` | `strategy_eligibility_projection:1913` |
| GET | `/v1/portfolio/strategy-rebalance-review` | `strategy_rebalance_review:2022` |
| GET | `/v1/portfolio/shadow-risk-coverage/{batch_sha256}` | `shadow_risk_coverage:2046` |
| POST | `/v1/portfolio/simulation/strategy-intent-order-preview` | `controlled_simulation_order_preview:2068` |
| GET | `/v1/portfolio/simulation/operator-reviews` | `list_controlled_simulation_operator_reviews:2097` |
| POST | `/v1/portfolio/simulation/operator-reviews` | `record_controlled_simulation_operator_review:2111` |
| GET | `/v1/portfolio/simulation/execution-authorizations` | `list_controlled_simulation_execution_authorizations:2147` |
| POST | `/v1/portfolio/simulation/execution-authorizations` | `authorize_controlled_simulation_execution:2161` |
| POST | `/v1/portfolio/simulation/manual-orders` | `submit_simulation_manual_order:2192` |
| POST | `/v1/portfolio/position-ownership/transfers` | `transfer_position_ownership:2211` |
| POST | `/v1/portfolio/evaluate` | `evaluate:2235` |
| POST | `/v1/portfolio/simulation/approvals` | `approve_simulation_order:2447` |

### relay（1 个声明）

`Q/src/qmt_platform/services/relay/app.py`，SHA-256 `960ecabe5981a88c5e8e46466c5f14b6d8665d4e641f65eb3a9bb283fe52c15a`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/v1/relay/status` | `status:59` |

### replay（42 个声明）

`Q/src/qmt_platform/services/replay/app.py`，SHA-256 `d2582b72ea6ebfdcb0eace3402b9f818f24ea38c172e31d81601c6895e04decd`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| POST | `/v1/replay` | `replay:402` |
| POST | `/v1/replay/shadow-report` | `shadow_pipeline_report:409` |
| POST | `/v1/replay/shadow-acceptance` | `shadow_acceptance_report:418` |
| POST | `/v1/replay/resonance-shadow-acceptance` | `save_resonance_shadow_acceptance_report:447` |
| GET | `/v1/replay/resonance-shadow-acceptances/latest` | `get_latest_resonance_shadow_acceptance_summary:487` |
| GET | `/v1/replay/resonance-shadow-acceptance/{result_sha256}` | `get_resonance_shadow_acceptance_report:504` |
| POST | `/v1/replay/simulation-acceptance` | `simulation_acceptance_report:519` |
| GET | `/v1/replay/simulation-acceptances/latest` | `get_latest_simulation_acceptance_report:604` |
| POST | `/v1/replay/datasets` | `register_dataset:618` |
| GET | `/v1/replay/datasets` | `list_datasets:629` |
| GET | `/v1/replay/datasets/{dataset_version}` | `get_dataset:638` |
| POST | `/v1/replay/runs` | `run_frozen_replay:648` |
| POST | `/v1/replay/event-acceptance` | `event_replay_acceptance:676` |
| POST | `/v1/replay/qmt-results` | `import_qmt_result:764` |
| GET | `/v1/replay/qmt-results/{result_id}` | `get_qmt_result:793` |
| POST | `/v1/replay/backtest-jobs` | `create_backtest_job:832` |
| GET | `/v1/replay/backtest-jobs` | `list_backtest_jobs:846` |
| GET | `/v1/replay/backtest-jobs/{job_id}` | `get_backtest_job:855` |
| POST | `/v1/replay/backtest-jobs/{job_id}/stop` | `stop_backtest_job:870` |
| POST | `/v1/replay/resonance-difference-reports` | `create_resonance_difference_report:888` |
| POST | `/v1/replay/config-snapshots` | `register_replay_config_snapshot:996` |
| POST | `/v1/replay/fill-model-results` | `import_fill_model_result:1034` |
| GET | `/v1/replay/fill-model-results/{result_id}` | `get_fill_model_result:1059` |
| POST | `/v1/replay/performance-reports` | `create_performance_report:1074` |
| GET | `/v1/replay/performance-reports` | `list_performance_reports:1191` |
| GET | `/v1/replay/performance-reports/{report_hash}` | `get_performance_report:1214` |
| GET | `/v1/replay/performance-reports/{report_hash}/analytics` | `get_performance_analytics:1245` |
| GET | `/v1/replay/performance-reports/{report_hash}/trades` | `get_performance_trades:1264` |
| GET | `/v1/replay/performance-reports/{report_hash}/positions` | `get_performance_positions:1290` |
| POST | `/v1/replay/platform-results` | `import_platform_result:1309` |
| GET | `/v1/replay/platform-results/{run_id}` | `get_platform_result:1354` |
| POST | `/v1/replay/difference-reports` | `create_difference_report:1369` |
| POST | `/v1/replay/platform-difference-reports` | `create_platform_difference_report:1394` |
| GET | `/v1/replay/difference-reports/{report_id}` | `get_difference_report:1427` |
| GET | `/v1/replay/comparison-projections` | `list_comparison_projections:1440` |
| GET | `/v1/replay/comparison-projections/{report_id}` | `get_comparison_projection:1467` |
| POST | `/v1/replay/release-gates` | `create_release_gate:1626` |
| GET | `/v1/replay/release-gates` | `list_release_gates:1659` |
| POST | `/v1/replay/release-gates/readiness` | `release_gate_readiness:1669` |
| GET | `/v1/replay/strategy-release-artifacts/{strategy_id}/{strategy_version}` | `strategy_release_artifact:1687` |
| GET | `/v1/replay/promotion-reviews` | `list_promotion_reviews:1702` |
| POST | `/v1/replay/promotion-reviews` | `create_promotion_review:1715` |

### research（61 个声明）

`Q/src/qmt_platform/services/research/app.py`，SHA-256 `faf2374a564f426c96abb36692df4f590a59e21211970ebd3f560c7108b39d49`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/v1/research/scorecards` | `list_scorecards:177` |
| GET | `/v1/research/scorecards/{scorecard_id}/content` | `get_scorecard_content:194` |
| GET | `/v1/research/schedule/status` | `get_m12_schedule_status:350` |
| POST | `/v1/research/schedule/run-once` | `run_m12_schedule_once:360` |
| POST | `/v1/research/score` | `score:725` |
| POST | `/v1/research/causal-datasets/readiness` | `causal_dataset_readiness:744` |
| POST | `/v1/research/prospective-candidates/readiness` | `prospective_candidate_readiness:779` |
| POST | `/v1/research/causal-datasets/freeze` | `freeze_causal_dataset:827` |
| GET | `/v1/research/causal-datasets/{dataset_version}` | `get_causal_dataset_archive:879` |
| GET | `/v1/research/causal-datasets/{dataset_version}/content` | `get_causal_dataset_content:902` |
| POST | `/v1/research/external-financial-datasets/freeze` | `freeze_external_financial_dataset:924` |
| GET | `/v1/research/external-financial-metric-registry/validation` | `get_external_financial_metric_registry_validation_report:955` |
| GET | `/v1/research/external-financial-datasets/{dataset_version}` | `get_external_financial_dataset_archive:966` |
| GET | `/v1/research/external-financial-datasets/{dataset_version}/content` | `get_external_financial_dataset_content:986` |
| POST | `/v1/research/artifacts` | `register_artifact:1002` |
| GET | `/v1/research/artifacts/{provider_id}/{input_hash}` | `get_artifact:1016` |
| POST | `/v1/research/calibration` | `calibrate:1031` |
| GET | `/v1/research/calibration` | `list_calibrations:1048` |
| GET | `/v1/research/calibration/{report_id}` | `get_calibration:1057` |
| POST | `/v1/research/drift` | `detect_drift:1071` |
| GET | `/v1/research/drift` | `list_drift:1093` |

`Q/src/qmt_platform/services/research/file_routes.py`，SHA-256 `0e2a6b9500103298e63156cf2b476ed3ba173a2962d09d782c674b22335aa791`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| POST | `/v1/research/files/from-causal/{dataset_version}` | `from_causal:34` |
| POST | `/v1/research/files/from-news` | `from_news:53` |
| POST | `/v1/research/files/derive` | `derive:63` |
| POST | `/v1/research/files/from-history-coverage` | `from_history_coverage:73` |
| GET | `/v1/research/files/{file_id}` | `read:92` |

`Q/src/qmt_platform/services/research/m12_routes.py`，SHA-256 `e10f6c31636984344c7ef42a88fa915a3a7b1b27122fd9534182ef57e4e9569e`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/v1/research/cycles` | `list_cycles:228` |
| GET | `/v1/research/cycles/{trade_date}` | `get_cycle:238` |
| POST | `/v1/research/evidence-bundles/freeze` | `freeze_bundle:251` |
| GET | `/v1/research/evidence-bundles/{bundle_id}` | `get_bundle:312` |
| GET | `/v1/research/evidence-bundles` | `list_bundles:322` |
| POST | `/v1/research/runs` | `create_run:329` |
| GET | `/v1/research/runs/{run_id}` | `get_run:363` |
| GET | `/v1/research/runs/{run_id}/news-lineage` | `get_run_news_lineage:373` |
| GET | `/v1/research/runs` | `list_runs:393` |
| GET | `/v1/research/workflows/etf-directional-committee-v1` | `get_workflow:400` |
| GET | `/v1/research/runs/{run_id}/attempts` | `list_attempts:404` |
| GET | `/v1/research/runs/{run_id}/outputs` | `list_outputs:411` |
| POST | `/v1/research/runs/{run_id}/claim` | `claim_run:446` |
| POST | `/v1/research/runs/{run_id}/resume` | `resume_run:454` |
| POST | `/v1/research/runs/{run_id}/stages/{stage_id}` | `submit_stage:555` |
| POST | `/v1/research/runs/{run_id}/stages/{stage_id}/fail` | `fail_stage:560` |
| POST | `/v1/research/runs/{run_id}/manager/evidence-intent` | `submit_manager_evidence_intent:579` |
| POST | `/v1/research/runs/{run_id}/evidence-gaps` | `freeze_evidence_gaps:610` |
| POST | `/v1/research/manager-invocations/{invocation_id}/heartbeat` | `heartbeat_manager_invocation:625` |
| POST | `/v1/research/evidence-collection-results/consume` | `consume_evidence_collection_result:640` |
| POST | `/v1/research/evidence-intent-outbox/{event_id}/replay` | `replay_evidence_intent_outbox:654` |
| GET | `/v1/research/runs/{run_id}/trace` | `trace_run:668` |
| POST | `/v1/research/executor/runs/next` | `executor_next:679` |
| GET | `/v1/research/executor/runs/{run_id}` | `executor_status:689` |
| POST | `/v1/research/executor/runs/{run_id}/claim` | `executor_claim_alias:704` |
| POST | `/v1/research/executor/runs/{run_id}/resume` | `executor_resume_alias:712` |
| POST | `/v1/research/executor/runs/{run_id}/stages/{stage_id}/submit` | `executor_submit_alias:725` |
| POST | `/v1/research/executor/runs/{run_id}/stages/{stage_id}/fail` | `executor_fail_alias:734` |
| POST | `/v1/research/executor/files/{file_id}/context` | `executor_file_context:759` |
| POST | `/v1/research/executor/files/{file_id}/release` | `executor_file_release:764` |
| POST | `/v1/research/executor/files/{file_id}/result` | `executor_result_seal:769` |
| POST | `/v1/research/executor/files/{file_id}/result/read` | `executor_result_read:776` |
| POST | `/v1/research/executor/files/{file_id}/receipt` | `executor_receipt_read:781` |
| GET | `/v1/research/executor/runs/{run_id}/traces/{file_id}` | `executor_trace_read:786` |
| POST | `/v1/research/executor/runs/{run_id}/stages/{stage_id}/submit-file` | `executor_result_submit:792` |

### research_data（62 个声明）

`Q/src/qmt_platform/services/research_data/app.py`，SHA-256 `69e316652feedcae4f367b1f3120cb2891572616e211e386cddee99fe793b101`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| POST | `/v1/research-data/evidence-capability-snapshots` | `append_evidence_capability_snapshot:1372` |
| GET | `/v1/research-data/sources` | `list_sources:1460` |
| GET | `/v1/research-data/sources/health-windows` | `list_acquisition_health_windows:1465` |
| GET | `/v1/research-data/sources/status` | `list_source_statuses:1473` |
| GET | `/v1/research-data/public-market-daily/status` | `get_public_market_daily_status:1518` |
| GET | `/v1/research-data/official-collection-checkpoints` | `list_official_collection_checkpoints:1530` |
| GET | `/v1/research-data/public-market-schedule-checkpoints` | `list_public_market_schedule_checkpoints:1542` |
| GET | `/v1/research-data/schedule/status` | `get_collection_schedule_status:1551` |
| POST | `/v1/research-data/official-collections` | `collect_official_source:1565` |
| GET | `/v1/research-data/observations` | `list_observations:1580` |
| GET | `/v1/research-data/narratives` | `list_narratives:1595` |
| POST | `/v1/research-data/evidence-plans/compile` | `compile_supplemental_evidence_plan:1607` |
| POST | `/v1/research-data/prediction-market-snapshots/collect` | `collect_prediction_market_snapshots:1636` |
| POST | `/v1/research-data/evidence-plans/{plan_id}/claim` | `claim_supplemental_evidence_plan:1687` |
| GET | `/v1/research-data/evidence-plans/{plan_id}/trace` | `get_supplemental_evidence_plan_trace:1705` |
| GET | `/v1/research-data/evidence-owner-requests` | `list_evidence_owner_requests:1720` |
| GET | `/v1/research-data/evidence-owner-requests/{request_id}` | `get_evidence_owner_request:1739` |
| POST | `/v1/research-data/evidence-owner-requests/{request_id}/authorize` | `authorize_evidence_owner_request:1754` |
| POST | `/v1/research-data/evidence-result-outbox/{event_id}/replay` | `replay_supplemental_result_event:1774` |
| GET | `/v1/research-data/evidence-plans/metrics` | `get_supplemental_evidence_metrics:1788` |
| POST | `/v1/research-data/evidence-plans/{plan_id}/heartbeat` | `heartbeat_supplemental_evidence_plan:1799` |
| POST | `/v1/research-data/evidence-plans/{plan_id}/authorize-side-effect` | `authorize_supplemental_evidence_side_effect:1820` |
| POST | `/v1/research-data/evidence-plans/{plan_id}/question-results` | `append_supplemental_question_result:1842` |
| POST | `/v1/research-data/evidence-plans/{plan_id}/terminalization` | `reserve_supplemental_terminalization:1864` |
| POST | `/v1/research-data/evidence-plans/{plan_id}/finalize` | `finalize_supplemental_evidence_plan:1893` |
| GET | `/v1/research-data/browser-captures/current` | `get_current_browser_capture:1919` |
| GET | `/v1/research-data/browser-captures/engagement/latest` | `get_latest_browser_capture_engagement:1929` |
| POST | `/v1/research-data/browser-captures` | `append_browser_capture_fact:1938` |
| POST | `/v1/research-data/first-party/collect` | `collect_first_party_source:2008` |

`Q/src/qmt_platform/services/research_data/browser_capture/app.py`，SHA-256 `4144b01a4aa687e8bc7c0e78f6e11c62b77f393fc5afebae7900e8dd008a3781`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/health` | `health:21` |
| POST | `/v1/captures` | `submit_capture:33` |

`Q/src/qmt_platform/services/research_data/first_party_routes.py`，SHA-256 `4bb77bf948c93228f03d3311cd0bb2b5dd8f358fdd0f2855a06eb45535b38aed`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| POST | `/v1/research-data/first-party/leadership/collect` | `collect:37` |
| GET | `/v1/research-data/first-party/leadership/{window_id}/candidate` | `candidate:43` |
| POST | `/v1/research-data/first-party/leadership/{window_id}/register` | `register:49` |
| POST | `/v1/research-data/first-party/leadership/reviews` | `append_review:55` |

`Q/src/qmt_platform/services/research_data/market_observation/app.py`，SHA-256 `0c755c1ceb090b3aabd8dca3e9a83f5658658170e6799bfa1677880dd1b70a00`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/health` | `health:39` |
| GET | `/ready` | `ready:41` |
| GET | `/{path:path}` | `shell:53` |

`Q/src/qmt_platform/services/research_data/market_observation/routes.py`，SHA-256 `4f9505cc65ce3830956244d60d051577f5a61c9ba9bf57d56044c91ef14b45b4`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `{API_PREFIX或UI_PREFIX}/catalog` | `catalog:32` |
| GET | `{API_PREFIX或UI_PREFIX}/definitions/{metric_id}` | `definition:36` |
| GET | `{API_PREFIX或UI_PREFIX}/reference/{metric_id}` | `reference:41` |
| GET | `{API_PREFIX或UI_PREFIX}/series` | `series:54` |
| GET | `{API_PREFIX或UI_PREFIX}/history/{metric_id}` | `history:58` |
| GET | `{API_PREFIX或UI_PREFIX}/quality/{metric_id}` | `quality:74` |
| GET | `{API_PREFIX或UI_PREFIX}/updates` | `updates:82` |
| GET | `{API_PREFIX或UI_PREFIX}/snapshots/{snapshot_id}` | `snapshot:87` |
| GET | `{API_PREFIX或UI_PREFIX}/lineage/{asset_id}` | `lineage:93` |
| GET | `{API_PREFIX或UI_PREFIX}/assets` | `assets:110` |
| GET | `{API_PREFIX或UI_PREFIX}/exports` | `exports:139` |
| GET | `{API_PREFIX或UI_PREFIX}/assets/{asset_id}` | `asset:130` |

`Q/src/qmt_platform/services/research_data/statement_display.py`，SHA-256 `b9454f38966b2578f343d7dde5d36564c18a1b07b3db4924ef2c48fd2859c112`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/v1/research-data/statement-display/page` | `statement_display_page:179` |
| GET | `/v1/research-data/statement-display` | `statement_display:196` |

`Q/src/qmt_platform/services/research_data/statement_routes.py`，SHA-256 `5629e6d85f7e9f60d46c4237520e1643a29ef90d1d6f0237319007f40807193a`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/v1/research-data/statements` | `statements:15` |

`Q/src/qmt_platform/services/research_data/x_routes.py`，SHA-256 `4e23b5825efe8a47b2ac9e81d0bf2642402aee9473ea6f7594c7321e76ecaf75`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| POST | `/v1/research-data/social-x/profiles/collect` | `collect_profile:58` |
| GET | `/v1/research-data/social-x/profiles/candidates/{payload_id}` | `read_profile_candidate:67` |
| POST | `/v1/research-data/social-x/accounts/register` | `register_account:76` |
| POST | `/v1/research-data/social-x/accounts/reviews` | `review_account:85` |
| POST | `/v1/research-data/social-x/lookup` | `lookup:95` |
| POST | `/v1/research-data/social-x/statements/collect` | `collect_statements:106` |
| POST | `/v1/research-data/social-x/statements/search` | `search_statements:115` |
| POST | `/v1/research-data/social-x/compliance/submissions` | `register_compliance_submission:124` |
| POST | `/v1/research-data/social-x/compliance/apply` | `apply_compliance:133` |

### strategy（16 个声明）

`Q/src/qmt_platform/services/strategy/app.py`，SHA-256 `35e3314788104988b00d058e2de8938f2735aaf99256181d5a318a2a6057d815`。

| 方法 | 路径 | 函数/行 |
|---|---|---|
| GET | `/v1/strategy/resonance/shadow-status` | `resonance_shadow_status:704` |
| GET | `/v1/strategy/runtime-states` | `strategy_runtime_states:721` |
| GET | `/v1/strategy/intents` | `list_strategy_intents:751` |
| GET | `/v1/strategy/current-target/{strategy_id}/{strategy_version}` | `current_strategy_target:777` |
| GET | `/v1/strategy/current-state/{strategy_id}/{strategy_version}` | `current_strategy_state:802` |
| GET | `/v1/strategy/execution-inputs/{revision}` | `strategy_execution_input:840` |
| POST | `/v1/strategy/runtime-states/{strategy_id}/{action}` | `control_strategy_runtime:859` |
| GET | `/v1/strategy/registry` | `get_strategy_registry:909` |
| GET | `/v1/strategy/replenishment/definition` | `get_replenishment_definition:916` |
| POST | `/v1/strategy/replenishment/review` | `review_replenishment:921` |
| GET | `/v1/strategy/market-data-universe` | `get_active_market_data_universe:950` |
| GET | `/v1/strategy/qmt-history-universe` | `get_active_qmt_history_universe:973` |
| GET | `/v1/strategy/registry/{strategy_id}` | `get_strategy_definition:1001` |
| POST | `/v1/strategy/registry/validate` | `validate_strategy_configuration:1015` |
| POST | `/v1/strategy/intents` | `create_intent:1022` |
| POST | `/v1/strategy/rules/etf` | `create_rule_intent:1045` |

### 券商终端HTTP路由（独立于FastAPI声明）

依据 `Q/qmt_agent/gateway/http.py::make_application` 的Tornado路由表：`/internal/v1/health`、`capabilities`、`state`、`events`、`sync`、`commands`、`commands/{uuid}`、`history-universe`、`operation-results/{uuid}`、`operations/{operation_id}`。读写方法、签名、队列及终态结果契约分别由对应Handler和Core核验；路径存在不扩大写许可。

受限host `S/broker_host/app.py::create_app` 的 `/internal/v1/{path:path}` 为GET/POST入口，内部显式分发health/state/events/sync、operation.submit/result和command.submit/progress；它属于并行受限传输工程参考，不能以通配路由推断支持全部券商能力。

