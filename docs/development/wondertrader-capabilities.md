# WonderTrader 原生能力与支持边界

类型：开发必读能力目录。适用C++上游：`08b230dd05facf6d650d949bfe51054115a2ecb1`。可选wtpy参考：`9fd4cd98feaa6fa2ea084741b3bb2adbe2b6bd78`。版本升级必须复核。本文覆盖数据、策略、执行、回测、存储、运维、扩展与测试的主要公共路径；不宣称所有第三方SDK已完成实机验证。

## 如何解释“支持”

- **原生**：固定源码具有可调用实现；仍需满足相应配置、数据、插件和运行条件。
- **适配**：原生扩展接口明确，业务来源或规则需要插件/映射；扩展部分不能标成上游自带。
- **可选**：官方子项目提供，需要独立依赖；不是C++核心随包功能。
- **未实现/待验**：分别表示已找到空实现/路径缺口，或缺少足够行为证据。前者不扩大成整个框架不可用，后者不能作为重写理由。

源码能力与运行资格分开。函数、SDK目录、配置项和测试文件存在分别只证明这些事实；真实券商许可、目标平台构建、完整调用链和故障恢复需要各自证据。接入交付需补充对应运行证据。

原Helper的`read_dsb_bars`和IRdm首次加载在完整读入后解压；输出count范围不限制首次分配。文件准入预算和所验字节一致性归调用边界。原`store_bars`提供格式写出，应用发布的完整性由本次独占输出、原生回读和来源摘要共同验证。工作区扩展导出及冻结差异按实际构建输入另行标注，原生能力依据固定Git对象判定。

## 核心能力目录

| 编号 | 能力/原生入口 | 支持与条件 | 限制及开发选择 |
|---|---|---|---|
| WT-D01 | 行情插件 IParserApi/IParserSpi、ParserAdapter | 原生：连接、订阅及行情回调；按具体SDK配置 | 供应商数据权利、字段/时钟/线程由插件契约决定；下游供应商插件单独登记 |
| WT-D02 | 数据接入与落地 QuoteFactory/WtDtCore | 原生：基础数据、时段状态、Writer、广播、指数扩展 | DataKit与策略宿主的ParserAdapter职责不同；allday绕过时段状态机 |
| WT-D03 | 历史与实时 WtDataStorage | 原生：DSB历史、DMB实时映射和读取 | 文件保存不是数据库事务或跨进程并发写入承诺；历史和实时写者须明确 |
| WT-D04 | 转换/导入 WtDtHelper | 原生C ABI：格式转换、读取、重采样等 | 外部分钟直接转换，避免伪造tick；接口返回、压缩输入和写入失败需按已核边界使用 |
| WT-D05 | 策略历史 IDataReader/WtDtMgr | 原生：K线/tick切片、缓存和周期读取 | 缓存生命周期与外部文件修订分开；不能假定再次查询必然重载 |
| WT-D06 | 随机查询 WtDtServo/IRdmDtReader | 原生默认WtDataStorage：按范围、条数、日期查询；tick/bar订阅 | 有数据时count可不足请求数；空历史路径可能虚报条数，须核对实际回调；订阅包含形成中bar且替换原订阅 |
| WT-D07 | 缓存清理 WtDtServo::clear_cache | 原生：清底层随机reader缓存 | 已有派生周期缓存保留旧值；不具备全系统缓存原子刷新语义 |
| WT-D08 | 日线、多周期、秒线与重采样 | 原生各入口已有实现 | 周期支持按具体reader/servo/策略入口区分；分钟适配限制不等于WT限制 |
| WT-D09 | 复权、连续合约与基础资料 | 原生数据管理/HotMgr/reader支持相应机制 | 因子、合约规则、时段及日期资料需要维护；不自带QMT所有来源资格 |
| WT-D10 | UDP与共享内存数据广播 | 原生UDPCaster/ShmCaster、ParserUDP/ParserShm | 数据分发协议不等于可靠业务消息或QMT共享内存接入契约 |
| WT-D11 | 历史下载/自动缺口补齐 | 原生loader扩展位；来源补齐属于适配 | 原文件有数据与完整覆盖分开；查实loader行为后仅补源能力和必要覆盖判断 |
| WT-D12 | WtDataStorageAD替代后端 | 原生LMDB模块，Writer及策略Reader有实现 | 随机Reader的bars count、ticks count/date为TODO；选型须按实际查询接口验证 |
| WT-S01 | CTA同步策略 WtCtaEngine/ICtaStraCtx | 原生：行情+分钟调度、历史窗口、目标、理论状态 | 重合的旧调度、窗口和通用持仓状态由此承接；自定义策略规则迁入扩展 |
| WT-S02 | SEL截面/定时策略 WtSelEngine/ISelStraCtx | 原生引擎和调度实现 | WtRunner的SEL配置与实际接线有缺口；须选已接通宿主路径，不能仅改env宣称支持 |
| WT-S03 | HFT事件策略 WtHftEngine/IHftStraCtx | 原生：事件、主动订单、成交/委托回调 | 不套用CTA目标汇总及线程屏障；实际源延迟与许可另验 |
| WT-S04 | UFT WtUftCore/WtUftRunner | 原生独立C++运行路径 | 实盘WtUftDtMgr的bar/tick/L2历史切片返回空，回测可读不等于实盘支持；状态、风控与HFT分别核实 |
| WT-S05 | 策略状态、理论持仓、用户数据 | CTA/SEL上下文JSON/输出；UFT另有mmap状态 | 账户实际持仓与策略理论持仓分开；保存动作不证明跨文件事务 |
| WT-S06 | 组合目标、路由、多执行通道 | 原生Engine/ExecuterManager | 在已接通宿主和执行器配置下复用；重复旧目标汇总退出 |
| WT-S07 | 策略指标/图表标记 | 原生上下文及EventNotifier | 特有策略指标算法按业务要求实现；通知不是持久业务确认 |
| WT-T01 | 登录/账户/持仓/委托/成交查询 | 原生ITraderApi及TraderAdapter查询链 | 源返回字段/范围和快照回报交接由插件保证；不默认四查询共同事务。原历史成交响应累计统计，实时成交还改变持仓与未成交量；完整相同事实不能直接交付两次 |
| WT-T02 | 委托、撤单及回报 | 原生ITraderApi/ITraderSpi、TraderAdapter及Order/Trade对象 | 标准EntrustID/userTag/OrderID映射由插件保持；来源认证、跨进程防重及未知结果核查由接入层负责，正常写开关、账户及终端模式沿实际接口处理；额外逐单审批签名、生产资格等级和同水位四快照不属于WT标准前提。旧QMT默认工厂仍为受管入口；正式可选TraderQMTStandard已通过原Adapter/Local与SHM运输的SDK替身主链，正式宿主和恢复继续，见[执行模块](../modules/execution.md) |
| WT-T03 | Local/Diff执行与算法工厂 | 原生目标差量执行和ExecuteUnit/IExecuterFact | 买卖/撤单就绪、拆单改价与每项授权须一致；算法实现逐项核查 |
| WT-T04 | 独立算法执行 WtExecMon | 原生C ABI set_position/commit_positions及公开C++ WtExecRunner；原Adapter/Local/Unit工厂 | C ABI使用静态Runner，Runner.release只停日志；Adapter有显式撤销/释放、Local池有wait/join，宿主负责完整组合顺序；时钟按实际执行单元核实 |
| WT-T05 | 分布式执行 WtDistExecuter | 当前固定版本仅更新目标/日志 | 广播目标部分只有注释，不能当已完成网络执行 |
| WT-T06 | 套利执行工厂createArbiExeUnit | 公开扩展位 | 固定内置工厂返回空，不能按名称承诺内置套利执行算法 |
| WT-T07 | 组合/通道风控、人工过滤 | 原生风险插件、TraderAdapter限制、过滤机制 | 规则覆盖和触发点分别核对；人工过滤的能力不代表产品需要逐单人工审批。策略预算采用配置，资金和损益复用原生统计，职责见[业务映射](../migration/business-adaptation-map.md) |
| WT-T08 | 订单成交日志/通道快照 | 原生savedata、orders/trades CSV、rtdata JSON | 终态订单和成交推送写日志，初始化查询不回填；不是未决命令日志 |
| WT-T09 | 断线与恢复 | 各交易SDK/插件、查询链和ready/lost机制 | 不同插件保证不同；固定Close通知不重置Adapter ready状态，StockMinImpact的lost为空，新写/目标屏障由实际插件与宿主落实。成交checkSelfMatch用于自成交检查，输入去重与查询/回报交接由插件保证；同实例重查会保留缺行持仓/旧订单并再累计历史统计，不能视作状态清空；重连、受控重建和跨日分别验。详见[执行模块](../modules/execution.md)与[原生交错验证](../evidence/2026-10-25-native-query-live-counterexamples.md) |
| WT-T10 | 股票交易/T+1/股票执行单元 | 原生对象和部分股票插件/算法 | 可卖量、今昨、现金和ETF制度依合约及源字段；StockVWap等边界待验证，不能直接泛化实盘资格 |
| WT-B01 | 回放与回测 WtBtCore/WtBtRunner/WtBtPorter | 原生回放器、策略mocker及输出 | 回测主入口与各种引擎实际接通程度分别核实；不另保留重复撮合底座 |
| WT-B02 | 模拟成交、费率和滑点 | 原生mocker、费率配置与撮合参数 | 不是真实市场排队/流动性保证；时钟、价量、手续费与T+1模型逐项确认 |
| WT-B03 | 仿真交易 TraderMocker | 原生交易插件，可用行情驱动 | 仿真结果仅证明模拟环境；真实券商幂等、成交与权限另验 |
| WT-B04 | 回测分析与参数优化 | wtpy apps提供分析/优化工具 | 可选子项目；纯C++核心不自动生成所有分析报表/优化任务服务 |
| WT-O01 | 原生进程和动态插件 | WtRunner/QuoteFactory/WtBtRunner/WtUftRunner及Porter | 原生二进制可直接运行；完整制品包括依赖DLL、配置、数据/状态布局及ABI身份 |
| WT-O02 | 日志、事件与监控输出 | 原生WTSLogger/EventNotifier/WtMsgQue | 事件/日志输出可复用；不自动提供观衡网页、鉴权、审计业务模型 |
| WT-O03 | 消息分发 WtMsgQue | 原生nanomsg pub/sub、主题订阅、心跳 | confirm等待连接不是消费者持久ACK；无此证据时不能替代可靠命令/任务确认 |
| WT-O04 | Web监控、调度、进程守护 | wtpy.monitor/WatchDog/WtMonSvr | 可选官方应用层；含SQLite等自身依赖，不属于C++裸Runner。采用时单独评估应用依赖 |
| WT-O05 | 构建/部署/版本 | 原生CMake、VS工程与发布目录 | 无Docker必需；源码/ABI/插件/配置/状态分别管理，不能只看exe文件名 |
| WT-O06 | UT与接入探针 | TestUnits/gtest及TestParser/Trader/Porter等 | TestTrader含可调用真实委托；测试目录存在不证明系统全E2E覆盖。下游CTest不可计入上游能力 |
| WT-O07 | 停止/释放/热更新 | 模块局部stop/release存在 | IRdmDtReader公开delete可进入局部join；完整宿主排空、DLL热卸载和借用切片存活按路径核对 |

详细数据、策略/回测和执行边界分别见[数据能力](../modules/wondertrader-data-capabilities.md)、[策略回测能力](../modules/wondertrader-strategy-capabilities.md)、[执行能力](../modules/wondertrader-trading-capabilities.md)。线程框架见[原生并发模型](../architecture/wondertrader-framework.md)。

## 运行、观测与部署的明确边界

WtRunner从配置装配基础资料、Parser、Trader、引擎、策略工厂和执行器；它不等于一个包含全部业务服务的应用安装包。QuoteFactory独立处理行情落地与广播；WtExecMon可独立承接目标；Porter是C ABI封装，调用者仍要承担生命周期。配置的active/module、路径、交易日历和合约元数据是实际运行条件。

EventNotifier提供LOG、GRP_EVENT、TRD_ORDER、TRD_TRADE、图表指标/标记等通知。WtMsgQue的confirm逻辑检查连接数量并等待；代码没有将它升级为消费者已持久处理证明。因此监控通知可以复用，审批和任务的可靠确认按业务语义另定。

官方wtpy子项目提供监控Web、自动启停、回测查看与优化等能力。固定参考版本的DataMgr使用SQLite保存用户、组、调度和操作记录，并读取WT的CSV/JSON。它说明官方应用层本身区分运行文件与管理数据，也说明“官方有监控”不等于“C++核心自带全部运维服务”。保持原生C++运行选择，复用对应输出；可选组件的采用单独核需求和依赖。

Windows/Linux构建入口已在上游存在，但各供应商SDK、编译器、依赖和架构需要匹配。Docker属于部署选择。升级和回滚应绑定核心/插件/策略二进制、配置契约及状态兼容，不能只替换一个exe。下游构建、打包及搬迁验收与上游能力分别登记。

## 采用与退出原则

原生重合能力全部采用WonderTrader：行情存储/查询、分钟运行、通用策略状态、目标聚合、执行算法、基础风控、回测撮合和原运行记录分别落其原模块。旧系统相应设计退出目标架构；现有事实通过受控切换保留。独有策略算法、接口及账户权限、产品配置及保留范围的业务页面只保留原生未覆盖部分，依[复用规则](wondertrader-reuse.md)证明缺口。逐单人工风险审批、独立资本归属服务按[业务映射](../migration/business-adaptation-map.md)排除在当前范围外。Grafana、新闻及研究产品按[ADR-0004](../architecture/adr/0004-core-trading-product-scope.md)退出迁入范围。

每项需要新增代码的需求先引用本目录编号，说明实际原生入口及未覆盖语义。源码边界尚不清楚时先调查，停止基于猜测的开发。原生有能力但宿主接线不足时优先原公开宿主/扩展；核心改动仍按批准范围执行。

## 来源及版本核实

- [固定上游源码地图](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/README.md)与各模块实现共同核对；该README的部分模块/后端描述需以源码纠正。
- [WtDtServo公开接口](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtDtServo/WtDtServo.h)、WtRdmDtReader::readKlineSliceByCount及WtDtServo::clear_cache。
- [原宿主](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtRunner/WtRunner.cpp)、QuoteFactory/main.cpp、WtCore/EventNotifier.cpp、WtMsgQue/MQServer.cpp、src/CMakeLists.txt与各Test入口。
- [官方项目介绍](https://github.com/wondertrader/wondertrader)、[官方wtpy说明](https://github.com/wondertrader/wtpy)用于功能线索；能力、性能、后端和生命周期最终按固定代码及匹配实验说明。
- 可选wtpy固定版本的`wtpy/monitor/{DataMgr,WatchDog,WtMonSvr}.py`和`wtpy/apps/`已核目录/关键入口。是否采用按产品需求与运行依赖评估。
