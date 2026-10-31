# 业务集成与展示

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块说明。所有者角色：业务接口维护者。状态：集成边界；具体业务实现及部署位置由功能规格登记。

## 职责与调用链

运行边界遵循[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)：WT独立拥有QMT通信、数据采集/历史、策略及交易生命周期，观衡独立发布且只读消费。下文历史App托管接线的源码位置和既有证据保留；对应owner正按[WRI](../specs/independent-wt-runtime.md)迁至独立WT运行包，历史通过结果不代表最终部署边界已完成。

独立观衡发行沿[ORP](../specs/observer-runtime-package.md)提供App/SPA离线包，显式连接外部WT及已有归档，安装和版本切换保持职责分离；[安装手册](../runbooks/observer-runtime.md)与[六组件开发证据](../evidence/2026-10-30-observer-six-component-package.md)分别登记操作和适用资格。

将行情展示、策略配置、账户与执行观察、必要诊断和用户入口与运行框架连接。业务消费者通过明确接口读取行情、运行状态及执行事实，通过受控入口提交允许的动作。资金、目标执行和风险按[执行模块](execution.md)复用原生能力，当前范围不新增资本归属账本、资金划拨或逐单人工审批。产品不包含Grafana、新闻和研究服务及界面，范围遵循[ADR-0004](../architecture/adr/0004-core-trading-product-scope.md)。

业务源码、路由和投影位于本仓库`apps/guanheng`，与原生运行库和独立客户端分别打包发布。功能按原生能力与独有业务职责组织，通过明确接口连接。新增集成在[功能规格](../specs/README.md)登记实际代码、部署、调用方和下游。

当前迁入按[业务工作区规格](../specs/guanheng-business-workspace.md)实施；既有兼容代码（外部历史/待归仓路径：`../../integrations/guanheng/README.md`）保留其原开发证据，跨仓库动态导入不作为最终运行实现。实际切换依功能规格与运行资格登记，单项门面测试通过只授对应开发链资格。

[原生行情消费者](../specs/native-market-consumers.md)通过独立SDK读取原生历史窗口及周期结果，业务层只负责投影和独有算法；资格与覆盖按原证据展示。[分钟消费模块](minute-consumer.md)保留既有接纳候选的职责和证据，其数据库接纳链不是原生分钟图表前提。持久业务效果确认与原始行情存储分别归所属owner，最终常驻接线须按原生能力映射验收。

分钟主图与基准由Console直接调用独立SDK，共用纯投影负责时间、单位和来源；MarketData兼容路由复用同一逻辑。Console进程拥有其HTTP客户端及有界读取池；ASGI收尾与进程退出分别验证客户端、最终线程和监听端口。日线、策略特征、独立市场观察及账户视图按各自实际owner取数，某个视图的独立运行资格不替代其他业务能力的验收。

独立App通过[历史服务托管](../specs/source-market-app-management.md)拥有SourceMarketProcess，原生来源Reader与HTTP资源保持在SMP子服务，URL/token由部署显式提供。[策略配置工作区](../specs/strategy-configuration-workspace.md)使用唯一纯核验证业务参数，在App独占的本地文档中保存连续版本和请求回执；LocalDocumentIO与原个人观察复用文件机制，各自保持业务状态与CAS所有权。App保存版本、部署冻结回测输入和B实际生效配置分别命名。公开运行状态、数据尾部与数据准入分别呈现；CLI只归约App全部owner的关闭总结果。

## 后台读取与线程所有权

`guanheng_app.thread_owner.ThreadOwner`只拥有标准Python Thread的一次启动和join证明。账户外层及新来源管道、策略宿主日志排空、回测工作线程和读取池复用这一规则。业务Future、完成事件、取消、管道、Job和运行根lease仍归各自owner；本模块不增加任务调度器或恢复数据库。

启动前保存owner。启动结果未知时保留原对象，阻止换轮；目标返回与线程入口均不能代替实际join。`join_until`消费调用者的monotonic绝对截止，零等待用于下一次准入续核，有预算等待放在目标所需锁外。关闭逐个续核全部owner，取得证明后由业务层按原顺序释放依赖。读取池构造阶段不启动线程，应用发布所有owner后在受保护启动阶段显式调用start，确保部分启动失败仍经过统一关闭。某组件关闭异常时继续核其他owner，并保留关闭未确认与原异常；读取队列取消回调在锁外执行，出队计数与后继join继续。应用私有关闭错误不进入HTTP响应，账户capability与读取入口共享同一运行可用事实。

## 数据与契约

独立市场观察沿[OBI规格](../specs/independent-market-observation.md)和[操作手册](../runbooks/market-observation.md)，代码位于`guanheng_app/observation`。显式数据根拥有不可变观察对象和SQLite事务目录，保留原纯计算、snapshot/dataset身份及usage；App沿同一有界读池提供目录、公式、谱系、图表和完整导出。采集lease独立于发布连接，CAS/current/receipt共同提交；完整采集与定时更新按后继验收。

执行进程沿[App托管执行进程](../specs/execution-app-management.md)，显式部署绑定B安装/配置并复用原owner。统一生命周期和只读系统状态已接通；策略金融事实、正式Python业务桥及自动恢复保持B的各自资格。操作入口见[托管手册](../runbooks/execution-app.md)。

行情日线沿[来源日线图表](../specs/source-daily-chart.md)，使用A的SDK0.14/source_daily_history_query与原day DSB，复用现有读取池与请求截止。公开1.6投影保留source_date及原单位；Appa7和039/042真实组合已核9ETF7739行及原分钟兼容，日期/闭合知晓与策略执行资格分别表达。

SDK0.15来源分钟沿[范围与分段来源](../specs/source-history-chart-observation.md)，App在唯一native_chart层验证并投影原Archive/Observed/Partial、实际窗口及准备状态。公开1.7保留每段原metadata和捕获身份，两行情组件复用有限中文说明；旧1.4/1.5/1.6 JSON不增加空字段。完整覆盖继续由来源资格决定，达到请求条数也保持原Partial状态。当前独立SPA入口和保留MarketPage在重读、失败期间均隐藏上次图表与来源说明。

策略页资料展示沿[策略目录](../specs/strategy-catalog.md)：名称、简介、算法版本与历史版本只读呈现；旧配置深链接进入目录，原回测tab保留。参数维护服务与页面资料展示保持明确职责，SCW原长表单已从主App入口移出。

外部状态通过集中转换映射为业务模型，保留原身份、来源、时间与资格。界面与统计属于派生视图；策略政策与允许的业务动作由明确的配置和执行所有者维护。

接口变化先核对消费者、版本与错误语义。页面将零、空、加载中、过期、不可用和覆盖未知分别表达，说明原因、影响及处理动作。展示资格与执行资格使用对应权威来源。

## 个人观察自选

[个人观察规格](../specs/personal-watchlist.md)与[ADR-0008](../architecture/adr/0008-personal-watchlist-ownership.md)定义观察偏好归属。实际调用链为main→IndependentApp→MinuteWorkspace→PersonalWatchlist/watchlistApi→应用watchlist_routes→既有BoundedReader→WatchlistOwner。GET/PUT /v1/ui/watchlists/default分别读取和按列表ID/版本完整替换，配置GUANHENG_WATCHLIST_ROOT默认空关闭。

WatchlistOwner独占安装包外的显式本地偏好目录，版本比较、原子文件写入和资源关闭由同一owner负责；跨页面待核保存由同QueryClient的有界内存owner持有，重新GET核完整目标，不自动重发PUT。个人自选与策略交易范围分别拥有，保存不订阅或下载行情；点击查看沿同一SDK/WT分钟图链。接口实现、静态审查和实际运行资格分别见[证据](../evidence/2026-10-23-personal-watchlist.md)。正式安装/生产SPA用户链的维护入口与Job、发行来源、专有目录约束见[测试手册](../runbooks/testing.md#个人观察正式安装与生产页面链)；各类故障、托管CI和生产资格分列。

## 验证与运维

[中文只读系统状态](../specs/operations-workspace.md)沿 IndependentApp→OperationsWorkspace→operations router 消费当前受管采集/Host owner 的公开 status 与原 SDK capabilities。后继通过 QuoteCollectionProcess.observe 与SDK0.13的runtime_status唯一读取器接入带control_id/PID/配置身份的采集状态；读取前后续核当前owner，过期/错实例隐藏值，断连和停止优先于累计计数。接口观察、原始源毫秒、最近接收、子服务发布及文件修改时间分别表达。页面只读取，故障原因采用固定白名单，不回显原始日志、地址或部署正文。专项状态与验证见[证据](../evidence/2026-10-28-operations-workspace.md)。

验证入口请求到真实下游与返回投影的完整链路，包括正常、无数据、依赖异常、恢复和权限拒绝。页面检查中文业务解释、核心数据和关键操作；测试结果及发布环境事实分别登记。

通用流程见[开发规范](../development/workflow.md)、[发布规范](../runbooks/release.md)和[故障处理](../runbooks/incidents.md)。
