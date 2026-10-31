# WonderTrader 原生插件与宿主契约

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：长期模块说明。范围：原生 Parser/Trader 接口、动态库工厂、宿主管理、回调线程和构建边界。状态：已对照上游基线 `08b230dd05facf6d650d949bfe51054115a2ecb1` 源码核实；具体服务商连接、生产资格和当前适配完成度从[服务商接入](providers.md)及[当前事实](../roadmap/CURRENT.md)读取。本地源码链接用于导航，可能包含下游差异；关键原生行为链接到固定上游提交。

## 职责与公开接缝

| 层 | 原入口 | 责任 |
|---|---|---|
| 行情插件 | [IParserApi / IParserSpi](../../src/Includes/IParserApi.h) | 连接来源、订阅/退订、将源数据转换成 WT tick 或逐笔对象并回调 SPI |
| 交易插件 | [ITraderApi / ITraderSpi](../../src/Includes/ITraderApi.h) | 连接/登录、查询、订单提交/撤销、委托与成交回报；返回值与异步回报分别处理 |
| 实盘行情宿主 | [WtCore ParserAdapter](../../src/WtCore/ParserAdapter.cpp) | 基础合约查找、交易所过滤、可选时间检查、标准代码转换，调用引擎 IParserStub |
| 实盘交易宿主 | [TraderAdapter](../../src/WtCore/TraderAdapter.cpp) | 登录状态、初始查询链、WT 持仓/订单/成交统计、交易风控和下游通知 |
| 数据组件行情宿主 | [WtDtCore ParserAdapter](../../src/WtDtCore/ParserAdapter.cpp) | 将行情及 `procFlag` 交给数据组件处理；与实盘宿主是独立实现 |
| 外部语言接入 | [WtPorter WtRtRunner](../../src/WtPorter/WtRtRunner.cpp)、[ExpParser](../../src/WtPorter/ExpParser.cpp) | 使用原 `initExt` 和 C 导出回调桥，接收外部推送 |

接入优先实现原接口，并复用原加载器。源会话、数据质量、鉴权与业务资格由接入层负责；需要改变上游内部状态或语义时按[上游维护规范](../development/upstream.md)提交明确的变更范围。

## 动态库工厂与配置加载

Parser 动态库导出 C 链接符号 `createParser()` 和 `deleteParser(IParserApi*&)`；Trader 对应 `createTrader()` 和 `deleteTrader(ITraderApi*&)`。创建器返回 C++ 虚接口对象，符号采用 C 链接只解决入口名字问题，接口本身仍遵循 C++ ABI。示例见 [ParserCTP](../../src/ParserCTP/ParserCTP.cpp) 和 [TraderCTP](../../src/TraderCTP/TraderCTP.cpp)。

普通 Parser 配置包含 `module`、`id`、`active` 及插件参数。Runner 选择 `active` 项并创建 adapter；adapter 通过 [DLLHelper](../../src/Share/DLLHelper.hpp) 组装模块名，先查当前工作目录的 `parsers`，再查模块目录的 `parsers`。Windows 模块后缀为 `.dll`；其他平台按 helper 规则使用 `lib` 前缀和 `.so` 后缀。Trader 使用同样的定位方式，目录为 `traders`。

[原生普通 Parser 初始化](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/ParserAdapter.cpp#L85-L257)顺序为：

1. 设置 stub、基础数据管理器、热合约管理器和 id，保留配置引用；读取 `check_time`。
2. 加载动态库、查找创建器、创建插件、记录删除器。
3. 读取 `filter` 交易所列表和 `code` 代码列表。
4. `registerSpi(adapter)` → `init(cfg)` → 根据 `code`、`filter` 或全部基础合约建立订阅集合 → `subscribe`。
5. 加入 ParserAdapterMgr；`run()` 调用插件 `connect()`。

因此配置和基础数据须在 `init` 前就绪。`check_time` 在插件注册及初始化前已经复制到 adapter；初始化后修改原配置对象不会自动更新该字段，公开接口没有重新配置它的 setter。插件应在 `init` 准备资源，在 `connect` 开始实际连接；CTP 示例在 `init` 注册 SDK SPI/前置地址，在 `connect` 调用 SDK `Init()`。

上游 ParserAdapter 对插件 `init` 失败记录日志后仍可能返回 true；`run` 调用 `connect` 后直接返回 true，未传播插件的 bool。上游 Runner 的 `initParsers` 也未核对 adapter 的初始化结果。宿主必须依据实际连接事件、数据和错误状态判断可用性，不能用这几个返回值替代端到端准入。

## `init`、`initExt` 与时间检查

[`WtCore::ParserAdapter::initExt(id, api, stub, bdMgr, hotMgr)`](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/ParserAdapter.cpp#L29-L83) 接收已创建的插件对象，设置依赖、注册 SPI，调用 `api->init(NULL)`，成功后订阅全部基础合约。它跳过动态库加载和配置解析，因此插件必须支持空配置；普通 ParserCTP 的 `init` 会访问配置，不能直接把它套入空配置路径。

`initExt` 是原有公开入口。上游 `WtRtRunner::createExtParser` 创建 ExpParser 后调用它；[HftLatencyTool](../../src/WtLatencyHFT/HftLatencyTool.cpp) 也用它接 TestParser。WtUftCore、WtDtCore、WtDtServo 各有自己的同名 adapter，须按实际链接组件核实行为。

[`check_time` 的原判断](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/ParserAdapter.cpp#L277-L322)语义如下：

| 路径/取值 | 实际语义 |
|---|---|
| 普通 `init`，缺少字段 | [WTSVariant::getBoolean](../../src/Includes/WTSVariant.hpp) 返回 false，关闭额外时间检查 |
| 普通 `init`，false | 关闭额外时间检查 |
| 普通 `init`，true | 当 tick 的 `action_date/action_time` 比本机当前时间超前 **超过 3,600,000 毫秒** 时丢弃 |
| 原基线 `initExt` | 构造函数和此函数均未给 `_check_time` 赋值；首次有效 tick 读取该成员没有确定的 C++ 行为 |

检查只针对未来超前，过去 tick、恰好超前一小时的 tick 不因这一判断被丢弃。无论开关如何，零 action date、零 trading date、缺失基础合约等前置条件仍会拒绝 tick。

[上游头文件](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/ParserAdapter.h#L86-L99)说明该选项默认 false，但原 `initExt` 实现缺少对应初始化。构造函数显式赋 false 会使该路径确定地关闭此项检查；普通 `init` 会在任何插件回调前用配置覆盖它。此修改改变了外部初始化路径中原先未定义的行为，不能描述为“所有路径原行为完全相同”。当前保留/退出状态从[差异登记](../maintenance/upstream-overrides.md)读取。

## 回调、对象寿命和线程

IParserApi/ITraderApi 没有统一的调度线程或队列契约。原 ParserAdapter 的 `handleQuote` 直接调用 stub；ParserAdapterMgr 的 `addAdapter/getAdapter/run/release` 操作普通容器，未提供并发锁。管理调用的串行化和对象存活范围须由宿主保证。

ParserCTP 在 SDK `OnRtnDepthMarketData` 回调中直接调用 SPI `handleQuote`，随后释放 tick；这里的线程由 SDK 调用方决定。WtPorter 的 `on_ext_parser_quote` 则在调用它的外部线程中创建 tick、调用 adapter、再释放 tick。插件应把回调对象视为借用对象；需要跨回调保存时遵循 [WTSObject](../../src/Includes/WTSObject.hpp) 的引用计数约定，不能保留已释放裸指针。adapter 还会将 tick code 改写为标准代码，应避免把同一个可变对象同时投递给多个宿主。

CTA/HFT 的 `handle_push_quote` 继续直接进入对应 ticker 的 `on_tick`。ticker 的独立线程负责时间推进和分钟闭合；tick 链中仍有同步 `trigger_price`/引擎回调，因此“有 ticker 线程”不能作为“所有行情已切到策略线程”的依据。原 Runner 在 `run` 中依次启动 parsers、traders，随后启动 engine，插件开始连接与引擎就绪之间存在启动顺序边界，接入层需验证该阶段的到达数据处理。

ParserAdapter `release` 先设置 `_stopped`，再调用插件 `release`，随后调用 DLL 删除器；`initExt` 没有删除器时直接 `delete` 插件指针。IParserApi 具有虚析构。将外部栈对象或另有释放所有者的指针交给此路径时，必须与 adapter 的释放行为协调；不能让双方分别销毁同一个对象。其析构函数本身不替代 `release`。

`_stopped` 在原实现中是普通 bool，提供业务上的停止检查，不提供跨线程同步。插件 `release` 应停止来源、等待在途回调结束并解除 SPI；宿主须保证 callback 不会与 adapter 销毁并行。CTP 示例通过 `RegisterSpi(NULL)`、SDK `Release()` 完成断开。自有插件的等待、回调重入、锁顺序和释放幂等需独立验证。

Trader 的顺序与 Parser 有差别：普通 `init` 创建插件后先 `init(params)`；`run` 创建统计对象、`registerSpi`、`connect`，随后设置登录中状态。交易插件不能假定 `init` 时已经取得 SPI。原 `release` 注销 SPI 并调用插件 `release`；该路径未调用已经加载的 `_remover`，其对象销毁管理必须按实际宿主核实。保持同一 adapter 重连时，原登录后的全量查询会再次进入原统计逻辑，恢复约束见[原生交易执行](wondertrader-execution.md)。

## 构建与 ABI

固定基线的 [src/CMakeLists.txt](../../src/CMakeLists.txt) 使用 C++17；Windows 的 WtCore/WtDataStorage VS 工程同样声明 `stdcpp17`，历史工具集为 v141、Windows SDK 10.0.17763.0，[src/README.md](../../src/README.md) 记载 VS2017/Windows 10。这些是上游工程声明；当前机器与历史工具链的实际支持资格由[构建手册](../runbooks/build.md)及证据登记分别给出。

原 [WTSDataDef](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/WTSDataDef.hpp#L10-L30) 在全局声明 `using namespace std`。当它先于 Windows COM/RPC 头进入同一翻译单元时，C++17 `std::byte` 与 RPC 的全局 `byte` 可能使 SDK 头中的未限定名字解析冲突。先包含 COM/RPC 头与改变公共命名空间是两种不同处理位置，实际受影响文件须按编译命令和包含顺序复现。`NOMINMAX` 只控制 Windows 的 min/max 宏，不能消除 `byte` 二义性；关闭 `_HAS_STD_BYTE` 改变标准库可用接口，降到 C++14 也会违反当前 `unordered_dense` 的 C++17 要求。

Parser/Trader 对象、STL 容器、结构体与引用计数对象跨 DLL 边界，构建和分发应绑定体系结构、编译器、运行库、结构布局、依赖版本和头文件身份。提供创建/删除器时，优先在创建模块内对称销毁。任何 ABI 或类布局变化均需重新编译有关宿主和插件，并验证真实工厂加载、初始化、连接、回调、断开与释放；独立接口编译成功只证明编译资格。

当前接入模块的工厂导出位置是 ParserQMT（外部历史/待归仓路径：`../../src/ParserQMT/Factory.cpp`）、ParserTDX（外部历史/待归仓路径：`../../src/ParserTDX/Factory.cpp`）、[TraderQMT](../../src/TraderQMT/Factory.cpp) 和 TraderTDX（外部历史/待归仓路径：`../../src/TraderTDX/Factory.cpp`）。工厂存在、DLL 加载成功与生产来源已经接通分别登记，具体适配生命周期见[受管运行时](managed-runtime.md)。

## QMT标准交易适配职责

自有[StandardQmtTrader](../../src/TraderQMT/StandardQmtTrader.cpp)实现原ITraderApi/SPI接缝；查询映射、委托身份及实时交付复用同一组金融映射与身份组件。WT原TraderAdapter拥有持仓、活动订单、未完成量和成交统计，插件保留的有限请求、收据、事件交付索引用于通信与去重，不构成第二份金融账本。生产工厂的实际选择与可用资格从[当前事实](../roadmap/CURRENT.md)读取。

owner调用API、pump和SPI；唯一worker处理有界队列中的来源请求。事件缺必需字段且具有完整定位信息时，worker按原事件截止查询相同数据类型，保留原事件与完整查询，唯一匹配器选取原行后进入同一金融映射。真实queued/executing结果继续领取原请求，POST回复丢失沿原UUID查询，不能再提交新的委托或补查请求。查询失败、冲突或来源不完整时保持明确失败，不构造订单或成交。具体字段与C状态约束由[事件规格](../specs/native-qmt-standard-events.md)拥有。

查询补充事实后的新事件签名只使用查询Remark作为管理标签，OrderRef保留诊断用途；已有完整事件走其既有兼容路径。来源操作结果、交付错误与是否超过原截止分别保存，停止与诊断文本分配异常保留已有操作首因。SPI在锁外调用，回调内release延后实际join与删除；完整原文和借用对象持有到真实使用结束。

[StandardEventBudget](../../src/TraderQMT/StandardEventBudget.h)集中计算逻辑额度：初始化、HTTP槽位、worker与owner峰值、排队及完成结果、单事件链与实际交付索引共用实例总额。新事件域在复制配置正文前取得初始化额度，退还发生在对应值实际销毁之后。逻辑额度说明准入上界；进程RSS、分配器余量和所有同步驻留组合须分别验证。补查能力解决单条缺字段回报，首次登录及断线恢复的查询/增量覆盖另按[原生交易能力](wondertrader-trading-capabilities.md)核验。
