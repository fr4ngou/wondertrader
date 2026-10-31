# WonderTrader 原生交易、并发与恢复

类型：长期模块说明。范围：原生 `ITraderApi/ITraderSpi → TraderAdapter → 执行器/策略`；柜台选取 CTP 与证券 XTP 说明插件差异。状态：固定版本源码核实；具体券商实盘、断电持久性和多线程竞态资格须按部署输入验证。

本文源码基线为 WonderTrader `08b230dd05facf6d650d949bfe51054115a2ecb1`。引用固定提交，工作区自有改动的语义另见[交易执行与账户观察](execution.md)。原生框架采用柜台查询、流重传、身份缓存、状态门禁和分层锁来管理交易；这些机制各自有明确作用域。

## 职责与事实所有者

| 层 | 原生职责与状态 | 保证范围 |
|---|---|---|
| 券商/交易所及 SDK | 受理、拒单、成交、撤单结果、账户与持仓；SDK 提供连接及流恢复契约 | 提交函数返回与最终交易结果分别确认；例如 XTP 非零订单号表示发送成功，之后由订单回报确认，编号按交易日唯一 [S1](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/API/XTP2.2.32.2/xtp_trader_api.h#L570-L575) |
| `ITraderApi/ITraderSpi` | 插件调用/回调 ABI：登录、查询、报单、撤单与推送 | 接口未定义跨四查询事务、快照版本/游标、统一错误状态或回调线程调度 [S2](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/ITraderApi.h#L104-L300) |
| CTP/XTP 插件 | 柜台字段、委托身份、日内 usertag 缓存、查询分包聚合、连接和流恢复 | 保留原 SDK 的条件与语义；具体插件具有不同重登路径 [S3](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderCTP/TraderCTP.cpp#L609-L724)[S4](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderXTP/TraderXTP.cpp#L754-L818) |
| `TraderAdapter` | 通道持仓/可用量、未完成数量、活动 WT 订单、日内交易统计、风控及 sink 分发 | 账户投影由查询初始化和回报更新；WT usertag 区分本框架委托；业务执行由上层触发 [S5](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L1537-L1594)[S6](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L1596-L1803) |
| `WtLocalExecuter` / 执行单元 | 组合目标、当前仓位差额、拆单、追单/撤单、活动订单监控 | 通道 lost 时停止其买卖和撤单入口；ready 可以重新计算，部分执行单元会撤掉自身未管理的活动委托 [S7](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/WtLocalExecuter.cpp#L218-L248)[S8](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtExeFact/WtMinImpactExeUnit.cpp#L144-L192) |
| `WtDiffExecuter`、CTA/HFT 上下文 | 差量目标、策略理论持仓、用户状态等 | 各自恢复自有数据；券商账户投影与策略理论状态分别拥有 [S9](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/WtDiffExecuter.cpp#L80-L195)[S10](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/CtaStraBaseCtx.cpp#L221-L315) |

这里的“原子性”必须注明对象：单次柜台命令的受理/执行规则由柜台定义；原子计数器只保护编号增量；互斥锁只保护持锁临界区；文件缓存只提供其实现声明的恢复数据。多笔交易、策略目标、WT 内存与远端账户之间没有由该 ABI 承诺的共同提交。正常交易系统可以采用异步状态机与对账完成恢复，无须以跨系统数据库事务作为可交易前提。

## 初始化、断线、重登录与重启

初始化链为 `run → registerSpi → connect → WTE_Connect → login → onLoginResult(true) → queryPositions → onRspPosition → queryOrders → onRspOrders → queryTrades → onRspTrades → queryAccount → onRspAccount → AS_ALLREADY → on_channel_ready`。每个阶段由上一阶段回调推进；`onRspAccount` 仅在 `AS_TRADES_QRYED` 发 ready。正常在线账户刷新仍更新资金观察，保持原初始化语义。[S11](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L1397-L1435)[S12](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L1506-L1534)

正常`init`保留配置引用、读取`savedata`并加载动态交易工厂；`initExt`接收现成API，强制开启保存且没有设置`_cfg`。原`WTE_Connect`处理会从`_cfg`读取登录参数，因此两入口的配置和事件条件须分别核对。直接注入API的宿主需要自行满足该路径条件；正常动态插件接入可以通过完整配置明确控制保存行为。源码：[两个初始化入口](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L95-L231)。

`run()`在`connect()`返回后才写`AS_LOGINING`。插件若在connect调用栈内同步完成登录及四查询，最终ready状态会被该写入覆盖；单纯把回调放到另一个线程也缺少先后保证。宿主与插件需要明确建立run返回之后的回调准入，例如同一owner线程后续排空结果队列；队列交接使用实际同步，解锁后才调用SPI，支持回调同步排入下一查询。该条件来自原调用次序，不能根据SDK回调通常较慢推定成立。源码：[run与release](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L401-L423)。

原release先解绑SPI，再调用插件release；插件负责其worker、在途请求与回调排空。Adapter析构只显式释放`_stat_map`，动态库、API实例、配置引用及其他原生对象的长期释放范围需要结合宿主实际生命周期验证。一次进程内初始化并退出的证据，只覆盖该进程范围；同进程无限重建、热卸载和持续恢复各自需要验证。源码：[析构](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L90-L94)、[释放调用](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L417-L423)。

CTP 先认证/登录、保存 FrontID/SessionID/MaxOrderRef，核实或确认当日结算后报告登录成功。查询工作线程按队列和节流条件发送请求；查询回调累计到 `bIsLast` 后交付数组，订单/成交查询数组交付后清空，持仓聚合容器交付后释放。[S3](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderCTP/TraderCTP.cpp#L609-L724)[S13](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderCTP/TraderCTP.cpp#L799-L1023)

CTP 的正式同实例恢复路径为 `OnFrontDisconnected → WS_NOTLOGIN + WTE_Close → sink.on_channel_lost`；再次收到 SDK `OnFrontConnected` 后调用登录并重新走结算及四项查询。`orderInsert` 检查插件自身 `WS_ALLREADY`。Adapter 的 close 处理通知消费者；该版本 close 不修改 `AS_ALLREADY`，所以其 `isReady()` 单独表示的是已完成的初始化阶段。Local/Diff 执行器另有 `_channel_ready`，在 lost 时改为 false 并阻断其交易入口。解释断线保护应同时检查这几层，不能单独读取 Adapter 状态后推断整个系统仍允许交易。Local 执行器门禁的状态切换见[ready/lost处理](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/WtLocalExecuter.cpp#L526-L569)，CTP发送检查见[orderInsert](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderCTP/TraderCTP.cpp#L334-L340)。[S14](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderCTP/TraderCTP.cpp#L574-L584)[S7](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/WtLocalExecuter.cpp#L218-L248)

HFT 直连路径把 ready/lost 回调交给策略，买卖/撤单直接调用 Adapter；该路径需要核对策略的通道状态处理和插件准入，不能套用 Local 执行器门禁。见[HFT调用入口](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/HftStraBaseCtx.cpp#L183-L315)及[策略通知](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/HftStraContext.cpp#L95-L132)。

CTP 使用账户专属 flow 目录；`quick=false` 时订阅 `THOST_TERT_RESUME`，`quick=true` 使用 `QUICK`。随库 CTP 头文件把 RESUME 定义为从上次收到的流位置续传，QUICK 为登录后流。具体 SDK 缓存文件、连接重试和服务端保留期仍受部署 SDK 契约约束。见[CTP流定义](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/API/CTP6.3.15/ThostFtdcTraderApi.h#L466-L481)。[S15](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderCTP/TraderCTP.cpp#L170-L197)

证券 XTP 采用另一条正式路径：断线发 lost，再向 `_asyncio` 投递延时 `doLogin`；首次登录初始化缓存并投递 `onLoginResult(true)`，后续同对象登录只恢复插件 `_state=TS_ALLREADY`。其 [SDK断线契约](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/API/XTP2.2.32.2/xtp_trader_api.h#L37-L45) 明确说明断线后直接 Login 的数据与断线前连续；`logout→login` 和直接重登的流语义不同。另外，该头文件把 `XTP_TERT_RESUME` 标为预留未支持，不能仅凭枚举名称宣称可用的跨进程断点续传。[S4](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderXTP/TraderXTP.cpp#L754-L818)[S16](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/API/XTP2.2.32.2/xtp_trader_api.h#L517-L549)

这也留下可核实的消费者边界：该 XTP 重登分支未再次给 Adapter 发 `onLoginResult` 或 ready，`WtLocalExecuter` 接到先前 lost 后的重新就绪接线需要针对使用方式验证。保留投影连续补流属于原生已有设计思路；插件恢复状态与执行器恢复资格需要分别检查。[S4](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderXTP/TraderXTP.cpp#L754-L818)[S7](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/WtLocalExecuter.cpp#L218-L248)

进程重启会新建 Adapter 的内存容器，重新查询柜台账户事实；CTP/XTP 在交易日缓存文件中恢复 entrustID/orderID 到 usertag 的映射。CTA 上下文从自己的 JSON 恢复理论持仓等，差量执行器从自己的 JSON 恢复 target/diff，[HFT上下文](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/HftStraBaseCtx.cpp#L721-L784)提供用户数据恢复。上述文件不构成共同提交，策略重启资格需要核对策略、执行器和账户三者。[S17](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderCTP/TraderCTP.cpp#L1230-L1359)[S9](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/WtDiffExecuter.cpp#L80-L195)[S10](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/CtaStraBaseCtx.cpp#L221-L315)

## 身份、去重、持仓与查询语义

Adapter 创建 `localid` 并编码到 usertag，插件创建柜台 entrustID；[CTP发送前](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderCTP/TraderCTP.cpp#L354-L369)保存 entrustID→usertag，订单回报建立 orderID→usertag，成交回报据此找到 WT 订单身份。[`localid`增量](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L41-L50) 使用原子计数；启动初值来自时间。它承担本地关联，源码未承诺跨账户、跨日、任意并发首次初始化及重启后绝对唯一的业务幂等键。[S18](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L484-L511)[S17](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderCTP/TraderCTP.cpp#L1230-L1359)

`_orderids` 对订单“第一次出现”做识别，避免重复执行首次报单统计与平仓可用量扣减。`_trade_refs` 用成交号关联订单做自成交检测；同成交号、同订单的注释称重复推送，但这个检查发生在持仓/成交统计和 sink 回调之后，返回值也未用于跳过这些更新。因此它不提供任意重复成交回报的整体幂等应用。取消统计等也不能直接扩展为所有状态回报去重。[S19](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L1806-L2251)

历史`onRspTrades`同样逐笔调用`checkSelfMatch`，空userTag仍经过该路径。该索引的键只有TradeID，未包含交易所、证券或事件日期；同键指向不同RefOrder时会记录自成交关系并告警。来源成交编号的唯一作用域须与这个原生解释相容；适配器使用派生标识时，需保留来源原值、固定映射及同一事件的跨订单关系，并另外验证碰撞与重复语义。此处说明原索引范围，不据索引命中单独认定真实自成交。[历史成交查询](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L1722-L1840)

查询持仓逐合约逐方向覆盖对应字段；Adapter 不先清空整个 `_positions`。查询订单清空 `_undone_qty` 后按活动 WT 订单重建，但查询统计在现存 `_stat_map` 上累加；成交查询也累加日内统计。查询成交不直接再加账户持仓，这是初始化时“持仓快照负责持仓、成交列表负责统计”的职责分工。[S5](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L1537-L1594)[S6](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L1596-L1803)

需要区分三类条件：

- 新 Adapter 首次完整查询，从空投影初始化，按上述职责恢复；单看累加操作不能判定首次初始化错误。
- 同 Adapter 再次拿到相同全量订单/成交列表，现存统计会再次累计。CTP 的正式重登可以进入该路径；触发要求是先已有统计且再次返回重叠全量历史，具体影响取决于重登数据及风控消费者。XTP 的保留重登分支不进入该四查询路径。
- 券商实际持仓已经归零、本地旧持仓条目仍非零，且新查询完全省略该合约/方向，又缺少相应成交回报时，本地旧字段会保留；新查询显式返回零行可以覆盖相应方向，连续成交回报已正确归约时也可先归零。不能由“没有 clear”推出每次重登都保留错误持仓。

四查询按流程依次完成；各批查询与实时订单/成交推送来自不同请求和事件。`ITraderSpi` 未带统一快照世代或事件水位，也没有查询期缓冲并以共同边界提交的约定。该事实限定了新插件能够承诺的快照一致性；它不能单独证明某个柜台正常运行时必然错账。新接源须说明查询时点、推送起点、重复范围和空/错结果区别。[S2](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/ITraderApi.h#L104-L300)[S13](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderCTP/TraderCTP.cpp#L799-L1023)[S20](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderCTP/TraderCTP.cpp#L966-L1054)

## 股票持仓与资金字段的解释

原`WTSPositionItem`有今昨持仓和今昨可用四个槽，`getTotalPosition/getAvailPosition`分别对两槽求和；原Adapter的`getPosition`也只返回合计。证券插件已有不同的槽分配约定：XTP按来源拆总持仓，却把全部`sellable_qty`放入昨仓可用槽；OES、HuaX也把合计可卖放入一个槽。四槽有值不能独立证明券商提供了精确今昨可卖。来源需按实际插件契约解释，消费者按所用粒度取得资格。[固定XTP映射](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderXTP/TraderXTP.cpp#L472-L535)、[原合计读取](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L425-L448)。

`getFrozenPosition`返回总量减可用量。在股票账户，该数可包含T+1等不可卖限制，展示名应表达“当前不可用”；委托实际冻结数量须取来源对应字段。只读合计投影与实时成交更新具有不同要求：原`onPushTrade`会按今昨与平仓方向修改分量，接入连续回报或执行器前必须核准对应分量和证券制度。[原数量定义](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/WTSTradeDef.hpp#L523-L543)、[成交更新](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L2167-L2195)。

原账户sink把`balance+dynProfit`作为动态权益。XTP以总资产填写balance并把dynProfit设0，避免再次叠加盈亏。插件应显式初始化所有交付的数值槽，按来源可用性解释中性值；该固定版本`WTSAccountInfo`构造函数没有初始化margin，不能依赖默认构造取得确定值。冻结资金保存在账户对象中，原`on_account`回调未转发冻结槽；展示该事实需核所用观察接缝。[XTP资金映射](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderXTP/TraderXTP.cpp#L545-L574)、[账户构造](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/WTSTradeDef.hpp#L596-L613)、[原sink调用](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L1506-L1534)。

## 线程与锁的具体范围

| 入口/状态 | 源码中的实际保护 | 范围与接入条件 |
|---|---|---|
| CTP 查询发送 | 独立 worker；请求入队及出队处 `m_mtxQuery`，一秒节流，`m_bInQuery` 控制在途 | 锁管理查询队列部分操作；worker 的 empty/front 和 plain bool 检查不在同锁中。查询发送线程不负责统一串行化回报 [S21](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderCTP/TraderCTP.cpp#L199-L229) |
| SDK 回报→Adapter | CTP `OnRtnOrder/OnRtnTrade` 和查询末包直接调用 sink；XTP 推送也是直接调用；XTP 登录通知由 asio worker 投递 | 回报的线程/先后关系继承相应 SDK；`ITraderSpi` 没有通用串行调度器。在所读接口中未找到可推广到全部插件的“所有回调同线程”契约 [S20](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderCTP/TraderCTP.cpp#L966-L1054)[S4](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TraderXTP/TraderXTP.cpp#L754-L818) |
| Adapter 订单集合 | `_mtx_orders` 包围 getOrders 枚举、按 localid grab、插入/移除 | 不覆盖所有 `_positions/_stat_map/_undone_qty/_orderids/_state` 访问；按合约批量 cancel 的枚举也未持该锁 [S22](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L1263-L1321) |
| 执行器→执行单元 | `poolsize>0` 时 schedule 任务，0 时直接回调；Local 的 `_mtx_units` 保护单元容器若干操作 | 多工作线程下提交顺序不等于完成顺序；即使 poolsize=0，行情线程与交易回报线程仍可能不同 [S23](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/WtLocalExecuter.cpp#L442-L570) |
| 最小冲击执行单元 | `do_calc` 内 `_mtx_calc`，活动订单监控 [`WtOrdMon`递归互斥锁](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtExeFact/WtOrdMon.cpp#L1-L62) | 原源码注释明确 tick 与目标变化可来自两线程，锁用于防重复计算/下单；这个单元锁不能视为 Adapter 所有读写的共同锁 [S8](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtExeFact/WtMinImpactExeUnit.cpp#L144-L192)[S24](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtExeFact/WtMinImpactExeUnit.cpp#L268-L309) |
| 原子编号与缓存 | `std::atomic` 编号增量、缓存新增/扩容锁、SpinMutex acquire/release | 独立字段/临界区同步；缓存读及已存在键更新未统一持锁，不能宣称整个缓存 API 任意并发安全 [S18](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L484-L511)[S25](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Share/WtKVCache.hpp#L116-L225) |

上游 Issue #259 的提问直接涉及 `_stat_map` 并发访问；collaborator 在 2025-09-30 建议为高并发场景详细测试共享区域并增加锁保护。它是维护者对范围的反馈，不是本版本所有路径已发生竞态的实盘证据。[Issue #259](https://github.com/wondertrader/wondertrader/issues/259)

新插件应显式定义谁串行执行查询完成、事件应用和失联/恢复通知，以及行情/执行器读写如何协调。只将交易回调放到一条队列，仍需核对行情驱动、执行池和策略直连的访问。锁顺序、持锁回调、同步重入、关闭期间在途回报与对象生存期分别验收。

## 持久化与事务边界

原生已有持久数据：交易/订单 CSV、通道 `rtdata.json`、CTP flow 文件、日内 usertag mmap 缓存、CTA/HFT 用户数据以及差量执行目标。Adapter 运行时 JSON 采用创建文件后写入；其初始化路径没有从该 JSON 重放账户投影。`WtKVCache` 重新打开日内映射、跨日重置、重建索引并检查部分文件尺寸异常。[S27](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L234-L385)[S25](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Share/WtKVCache.hpp#L116-L225)[S10](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/CtaStraBaseCtx.cpp#L221-L315)

这些机制支持审计和常规重启恢复。已读调用链没有把发送券商命令、更新 WT 内存、写 CSV/JSON/mmap 和提交策略目标包成一项可回滚事务，也没有证明任意断电时缓存键值和计数同步落盘。`BoostMappingFile` 虽提供 `sync()`，`WtKVCache::put` 未在每次写后调用它。普通关闭可回读、进程崩溃和机器断电是三个独立验证条件。[S25](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Share/WtKVCache.hpp#L116-L225)[S28](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Share/BoostMappingFile.hpp#L30-L48)

## 插件复用与验证接缝

优先复用 `ITraderApi/ITraderSpi` 插件、原四查询初始化、柜台唯一订单号、usertag 映射、活动委托查询和原生执行单元。源端已拥有可靠提交/幂等/回报日志时，沿源端原身份消费其事实，新增前先核实唯一所有者。QMT/HTTP 接入若要求提交未知核查、账户/流世代匹配、精确事件游标、同实例连续补发及消费者异常隔离，这些是接入契约需要映射的条件，必须与原柜台能力逐项比较。[S2](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes/ITraderApi.h#L104-L300)[S18](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/TraderAdapter.cpp#L484-L511)

原接口能完成新实例全查询和普通失联通知。需要在保留内存投影上补流并重新通知消费者时，应比较外部 SPI/sink 代理、宿主统一门禁、受控新实例重建和最小框架接缝；比较时绑定现有执行器指针、委托监控、策略状态和回报切换边界。只有最终所需行为无法由原有接缝完成且有完整回归时，才形成框架修改必要性。

上游 [`TestTrader`](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TestTrader/main.cpp#L1-L100) 是可连接真实插件并发单的交互测试程序，调查时只读；`TestUnits/test_kvcache.cpp` 覆盖基本缓存读写和跨日重置。本次检索未找到上述完整断线/重登/事件交错的自动化资格证明。交付验证应覆盖首次空/非空快照、同实例重登、新实例重启、SDK 重传、查询与实时回报交错、部分成交、查询失败、并发计算与关闭、未知提交核查、状态文件故障。真实交易权限和账户验收按具体任务授权执行。[S29](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/TestUnits/test_kvcache.cpp#L9-L39)

## 固定源码与一手资料

上游发布说明还记载执行器使用线程池以减少网络线程占用，及后续 CTA 并发回调选项；它们解释性能设计背景，不能替代具体共享状态的同步契约。见[固定版本更新记录](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/updatelog.md)。
