# 原生 DataKit 行情采集

类型：功能规格。状态：accepted。范围：独立行情采集进程、原生分钟线生成与落盘；来源接线和现场资格分别验收。

## 目标与职责

使用 WonderTrader 原生 QuoteFactory / WtDtCore / WtDataStorage 接收行情、生成一分钟线和保存数据。采集进程持续运行，由原生 session 状态机推进交易时段及收盘归档；对话提醒与唤醒任务不承担采集职责。用户要求从 2026-10-28 开始自动采集全市场分钟线，日常流程由系统完成。

默认范围沿当前系统的沪深股票与 ETF。缓存库存只表示本地已有证券，证券全集和变更来自明确的来源清单；未验证的北交所、期货及其他品种不得混入已验范围。

## DTC1 原生构建

独立 native profile 构建上游 WtDtCore 和 QuoteFactory，使用同一锁定依赖、编译器及运行库。自有 CMake 接入可以选择源码及安装目录，保持上游组件源码与行为。QuoteFactory 使用原 main.cpp 和 Windows 转储源码，不依赖 wtpy；采集发行包含实际加载的 Writer、行情插件、基础资料、时段配置及依赖 DLL。编译、安装及现场采集资格分开登记。

## DTC2 接收与全市场

原生调用链为行情插件 IParserApi → WtDtCore::ParserAdapter → DataManager::writeTick → IDataWriter。基础合约、交易所及 session 在启动前加载，原 adapter 决定订阅集合。隔离验证覆盖全库存大小的合约订阅以及实际 tick 进入原 Writer；合成来源通过只证明原生链和容量。

QMT 是主要来源，传输沿现有共享内存适配。QMT 内部保持无外部文件、无网络访问。实际行情来源的订阅方式、批次限制、字段及吞吐分别验证，不将自有轮询插件限制归因于 DataKit。来源插件提供行情；DataKit 保持分钟生成与存储职责。

### DTC2.1 既有 full_tick 的批量接线

沿既有 market.full_tick 的 stocks 列表合同，每次最多200证券，不扩充Agent操作或放宽协议。自有原生共享内存行情端点按显式批量配置把订阅集合分组，单次pump沿同一截止读取，逐证券映射后交原SPI。默认配置继续原逐证券路径及200订阅上限；显式批量配置支持最多10000沪深证券，单次原请求仍最多200。沿原单位/profile/来源身份检查及原插件停止责任。缺失或非法来源值明确失败，不补造tick。完整结果只解码一次再逐证券映射，避免对同一批结果重复解析。旧HTTP插件、旧生成策略和账户/交易协议保持原合同。

先验证真实共享内存协议替身的多证券原请求、DataKit原Adapter全量订阅和原Writer落盘，再接实际QMT来源；相同快照去重继续归原parser。原生全市场采集与历史分钟修正的验收分开，快照聚合不授官方分钟全字段相同的资格。

### DTC2.2 来源接线资格

来源的每批证券数、原策略回调频率、传输批次和 Writer 工作量分别核实。每个 pump 的同步 Writer 成本包含在原预算内，采用小批持续轮转，不能以扩大订阅数替代真实吞吐验收。现有全量合成验证与实际 QMT 全市场验证分别登记。

原协议的只读请求用于有界查询。持续报价流先核实来源全推能力与原生 parser/porter 接缝，再确定共享内存接线，避免把小型命令 Journal 测试配额用于全天高频行情。新增公共流协议先形成独立契约；默认查询路径保持已有版本。正式来源须实际观察时间推进、覆盖和分钟生成，不能只凭 SDK 存在、连接成功或订阅函数名称认定可用。

## DTC3 分钟线与存储

一分钟线使用原 Writer 的 session 分钟归属及原始输入聚合，不另写分钟聚合器。启用 min1 与历史归档；tick、min5、day 等按显式采集配置选择。盘中保存 rt/min1 下的 DMB，原生收盘转储生成 his/min1 下的 DSB，Reader 沿现有原生文件接口读取。

来源量额口径须与插件配置相符，合成测试使用明确口径；实际口径缺失保留其待验状态，不用示例倍率冒充事实。原生快照聚合得到观测分钟，来源官方分钟、复权及历史修订保持各自身份。

## DTC4 自动运行与缺口

常驻采集过程接收当时可用行情，按 WT 原生 session 自动进入、退出交易时段并完成收盘作业。启动、重连、时段和最终文件结果分别可观察。断线缺口由历史准备路径负责补齐，采集和历史回补分别验收；原生采集主链先跑通。

现场未运行、来源未认证、证券清单或实际新分钟未确认时，不报告明日采集已就绪。采集进程、只读 Host、历史导入和策略/交易保持独立职责，真实下单及撤单不在本规格授权范围。

## DTC5 生命周期与验收

隔离输出使用新根，保留历史导入及其活动 Writer；各根明确单写者。自有验证入口显式停止行情生产者，再完成原 adapter / Writer 关闭，记录进程实际退出及资源结果，不以文件存在或 session marker 独立判定成功。

主路径验收：原生构建和 QuoteFactory --help → 当前库存大小的原 adapter 订阅 → 明确合成 tick → 原 Writer 生成 DMB → 原收盘转储 → 原 Helper/Reader 回读 DSB 并核时间、OHLC、量额。随后接真实 QMT 来源，核全市场订阅、新分钟实际出现、盘中及收盘文件；合成验收不能替代现场资格。

原生依据：[QuoteFactory](../../src/QuoteFactory/main.cpp)、[ParserAdapter](../../src/WtDtCore/ParserAdapter.cpp)、[DataManager](../../src/WtDtCore/DataManager.cpp)、[StateMonitor](../../src/WtDtCore/StateMonitor.cpp)、[Writer](../../src/WtDataStorage/WtDataWriter.cpp)。能力边界沿 [WT-D02/WT-D03](../development/wondertrader-capabilities.md)。
