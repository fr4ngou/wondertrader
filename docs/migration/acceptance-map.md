# 完整接入验收地图

当前跨会话交付责任、M1—M4与合入流程见[三会话并行交付与实盘就绪计划](parallel-system-delivery.md)；下列历史资格继续按实际输入保留，完整系统按该计划组合验收。

当前范围按[ADR-0004](../architecture/adr/0004-core-trading-product-scope.md)：Grafana、新闻、研究的功能与界面全部退出WonderTrader目标；下文旧范围中对应迁入和验收承诺已被本决定取代。保留核心行情/策略/回测/账户/交易、配置、必要运维和独立市场观察。清理新仓库专属实现及依赖，旧工程/历史资料与冻结证据不改。

类型：持续目标验收地图。状态：in-progress；2026-10-22 当前源码/证据核对。本文按用户完整目标记录实现与运行缺项，不以单个 SDK 或隔离测试替代整体完成。具体环境身份与最后制品见 CURRENT，最终行为以功能规格为准。

交付以WT原生能力承接重合职责。旧PG分钟接纳、outbox、同步HTTP Reader及强四快照候选保留其历史证据并暂停作为最终默认路径；这些候选的验收缺项不自动成为新架构的必需组件。独有业务的持久效果确认仍需证明实际缺口与单一owner，服务数量和旧拓扑保持可调整。

2026-10-22通信时序更新：QMT终端HTTP仅用于今晚前跑通流程，停止后续优化和新部署，表中历史HTTP实验保留当时范围，正式来源验收不再依赖其继续可用。SHM由另一对话完成且今晚实测通过确认后才开始WT接入；等待期间继续运输无关能力，详见[DEC-001](decisions.md)。观衡业务API与页面HTTP保持独立职责。

| 要求 | 当前可证明范围 | 完整交付还需证明 |
|---|---|---|
| 开发前原生能力核实 | [能力目录](../development/wondertrader-capabilities.md)、数据/策略/执行模块及[复用规则](../development/wondertrader-reuse.md)已核固定源码/可选组件/自有增量；公开Reader/Factory限定行为有原样实验 | 对每一后续接缝核实其实际配置、状态/并发与运行资格；重合旧实现退出目标架构，逐项以原生模块承接 |
| 适配与核心边界 | 既有插件、加载器、原生存储及策略读取入口已核查；框架修改经说明必要性及用户批准后实施，批准前只读；12 个已有差异冻结 | 对既有差异逐项完成必要性、替代方式、范围、风险及验证/回滚审查，提交用户决定，架构审查仍待完成 |
| 国信 QMT 已下载分钟导入 | [QMI隔离验收](../evidence/2026-10-21-qmt-minute-import.md)及[真实428条样本](../evidence/2026-10-21-real-qmt-native-history.md)：显式分片、原版helper写读、sidecar/收据、原CTA分钟回调和历史窗口均已验 | 源精度及全天覆盖保持DevelopmentVerified/unknown；大范围真实下载档案和生产日历继续验收 |
| WonderTrader 原生底座 | Runner、回测、插件、DSB、模拟组件已编译，开发包搬迁运行；无 wtpy 运行依赖 | 原生受管常驻进程/监督、正式发行身份、升级与回滚运行验真 |
| 完整原Runner启动与退出 | [NCS复查与修复](../evidence/2026-10-21-native-cta-shutdown.md)按用户条件授权完成14文件接线；复用原停止/等待方法，133启用CTest与4个搬迁包退出场景通过；受管模式限定CTA与空交易配置 | 真实交易/执行器、其他引擎、生产监督与完整发布生命周期另验；任意回调无限阻塞不具严格整体截止保证 |
| QMT原生持续行情 | [QNP验收](../evidence/2026-10-21-qmt-polling.md)：默认DLL、原adapter/CTA投递、12原生/8宿主/4回调排空场景、搬迁包和真实18010收盘后短窗口读取通过；独立delta开放问题0 | 真实盘中持续更新、HTTP分段延迟、完整WtRunner就绪/分钟准入/受管退出；ReaderHTTP另验 |
| QMT HTTP 行情 | [真实18010直连428条](../evidence/2026-10-21-qmt-numeric-time.md)完成读取、归一化、DSB与重复query；同源1m/5m桶对照，保留临时流程资格 | 停止HTTP路线优化和新部署；历史量额精度、覆盖及正式来源恢复在后继获准通道取证，未验项不转为延长HTTP的要求 |
| 按需历史 1m 与补齐 | DSB/定向任务与原 Operations CAS 复用；SDK 0.5.0 接真实原日历路由，实际原生 HTTP/DSB 的 240 分钟、空段、故障恢复/确认回查及搬迁包通过；原日线 family 前置拒绝已按 HFA 验收 | 真实十年日历/历史证券排除、生产配置/监督与队列 owner 崩溃回收、真实长区间导入 |
| 历史进程部署组合 | [HDF验收](../evidence/2026-10-21-history-deployment-factory.md)：SDK0.8.0正式factory、11项构造与4项实际wheel整链、同worker故障恢复、包级搬迁及独立full通过 | 生产端点、存储namespace/ACL、独立监督和实际Operations/Console入口 |
| 原生同实例历史与分钟事件 | [NHR隔离整链](../evidence/2026-10-21-native-history-reader.md)：SDK0.7尾部日历查询、独立HTTP reader、原WtDtMgr/CTA同实例补齐/修订、旧切片、pool0/2回调重读与stop；独立full开放问题0 | 完整WtRunner ticker常驻、多个策略并行修改原宿主容器、生产退出和DLL卸载、真实日历/来源及业务效果；强制缓存和重采样另验 |
| 可选证据存储 | HES MinIO SDK适配及丢回复恢复有原限定证据，作为可选storage extra保留 | 先证明独有业务的对象存证需求；采用时再验namespace/ACL/保留及回读。WT原生行情读写不依赖MinIO |
| 实时快照与闭合分钟订阅 | 原生 Parser、Runtime、MinutePipeline 与真实 WT adapter/writer/reader 隔离验证 | 实际源完整 OHLCV/时间/基线资格，常驻调度及消费者恢复验真 |
| 分钟业务接纳与恢复 | 原生Ticker→Reader→DtMgr→CTA调度已核；公开Reader/Factory、同实例修订与原CTA限定实验已验。旧SDK0.9/PG接纳候选保留历史资格并暂停接线 | 使用真实闭合分钟沿原CTA驱动独有策略，验证恢复/迟到不重复触发当前交易、同实例窗口更新及业务效果owner；先核原生策略状态的承接，必要增量再定契约 |
| QMT 受管交易与回报 | 原Trader API/SPI与TraderAdapter职责已核；[HTTP只读接线](../evidence/2026-10-22-qmt-http-bootstrap.md)后继248项及第二次full关闭原三项，唯一新P1 CNG资源顺序三红/三绿已获delta-003通过；HTTP两条目标被早期超时遮挡的本轮结果仅授fail-closed，原针对性证据保留；源端315/打包52及两任务门禁通过并本地整合dc854b60d | 继续正式固定来源构建/目标故障CTest/搬迁与真实只读查询。沿[真实HTTP边界](qmt-http-execution-boundary.md)核初始化、query/push交接、重复/乱序与未决委托；强原子基线不预设为框架要求，交易副作用另按明确授权 |
| TDX 可选来源 | 抽象端点、LC1→DSB 导入与明确 profile；来源独立登记 | 实际辅助行情端点绑定与样本验真；TDX 交易按用户决定暂缓 |
| Tushare 基础辅助 | 已做指定端点的小样本与拒绝权限验证，保留来源/配额诊断 | 仅接实际授权数据产品；不得推定股票/ETF 分钟与实时完整能力 |
| 观衡独立服务 | [Console→独立SDK→原生Reader/Factory](../evidence/2026-10-22-client-transport-deadline.md)的1m/5m图表、37项整链、四次完整Console进程及浏览器组件已通过；原始行情无需旧MarketData/DB/NATS。SDK0.12修正自有网络截止，独立复审继续 | 正式审查/发行、真实受管用户入口及升级回滚；日线/复权和策略等保留用户功能分别按原生能力承接，独有业务独立发布，正常/空/异常/恢复逐项验收 |
| 策略回测与实盘一致 | 实际 WT 回放→原纯策略核心→影子目标对照；固定输入/时钟/预热 | 当前策略版本完整状态、原执行上下文、分析窗口与增量 checkpoint 全链，再验同一实例单目标发布者 |
| 事实与持仓归属 | [WT原生执行](../modules/wondertrader-execution.md)区分券商实际持仓、策略理论状态和订单回报，保留原账户事实；强四快照候选不作为WT必需 | 沿原TraderAdapter查询/回报交接核实QMT真实端点，验证重连、重复/乱序及未决委托；需要增量保证时先说明原生缺口，不建立第二套实际持仓或命令账本 |
| 开发/注释/文档/发布/故障规范 | 仓库全系统长期规范、模块与规格索引、源码身份/证据工作流已建立 | 后续每个功能/发布继续按规则执行，CI 托管运行与实际用户入口资格分别登记 |
| 上游更新 | 固定 upstream 基线、差异登记、更新/rebase/冲突及回滚手册 | 在实际待升级版本执行依赖/ABI/回归/恢复演练；不能用手册存在代替一次运行证据 |
| 原系统与并行通信工作 | 旧QMT只作静态参考；SHM由另一对话开发，当前未开始WT绑定 | 等开发完成且今晚真实验证通过确认后，依据最终公开契约接入；探针部分成功不作为启动依据 |
| 策略纯核与数量 | [纯核a5与NSQ独审](../evidence/2026-10-22-native-strategy-kernel.md)通过，各自有冻结包及反例回归 | 全部策略族、真实输入及完整用户入口继续验收，纯模块通过不替代完整迁入 |
| 原生回测会话与运行宿主 | 薄Porter43场景独审通过；NSB实际组合通过已测小样本，full发现历史重复保留和Decimal上下文两项问题 | NSB修正原触发与完整结果重建；NSH固定安装、全Job退出、单期限、容量及独审，最终接业务入口；当前候选不授整包或生产资格 |

[HFA 原执行器准入](../evidence/2026-10-21-history-family-admission.md)已完成隔离开发验收，原 Operations 继续持有共享作业与 CAS。HSA/HES/HW 冻结证据保留当时结果，最新分钟投影/跨仓/发行结果见[CAL 证据](../evidence/2026-10-21-history-calendar.md)。逐服务入口见[适配地图](business-adaptation-map.md)，原日历事实与当前增量见[owner 调查](calendar-owner-boundary.md)。环境/来源缺项与明确用户决策在[决策清单](decisions.md)分开记录；可独立实施的必要功能继续开发。
