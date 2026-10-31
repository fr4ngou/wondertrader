# WonderTrader 原生交易与执行能力

类型：长期模块能力说明。固定上游：`08b230dd05facf6d650d949bfe51054115a2ecb1`。以下源码路径/行号均以该提交为准，自有ManagedTrader、TraderQMT和恢复/退出增量单独登记，不计入上游能力。版本升级复核实现、配置和行为范围。

直接支持表示固定代码已有相应路径；扩展支持表示公开接缝需要插件/装配；受限表示实现存在但有明确条件。源码能力不授予特定供应商或生产交易资格。开发入口见[能力目录](../development/wondertrader-capabilities.md)及[复用规则](../development/wondertrader-reuse.md)。

## 四种策略/交易路径

| 路径 | 原生职责与调用链 | 状态/配置条件 | 限制与判定 |
|---|---|---|---|
| CTA | `CtaStraBaseCtx` 接收 enter/exit/set_position、条件信号；`WtCtaEngine` 调度策略、汇总理论目标；`WtExecuterMgr` 路由；Local/Diff 执行器→ExecuteUnit→TraderAdapter→ITraderApi | `env.name=cta`，策略工厂、基础数据、行情、交易、执行器配置；策略 pool 与执行器 pool 独立 | **直接支持目标交易**。策略理论持仓由行情/信号演算，账户实际持仓由 Trader 查询/回报维护。两者分别拥有；目标变化不代表真实成交 |
| SEL | `SelStraBaseCtx::stra_set_position`→`WtSelEngine::handle_pos_change`→同类执行管理器；按日、周、月、年等周期调度选股/调仓 | 交易日期/交易模板/时段、策略上下文注册和执行器接线 | **引擎支持、随库宿主接线受限**。不能只把 `env.name` 改为 sel 就声明整条原 C++ Runner 可执行，见下文 |
| HFT | `HftStraBaseCtx::stra_buy/sell/enter/exit/cancel` 直接调用 TraderAdapter；订单/成交/委托/通道回报进入策略；支持 tick 和逐笔相关回调 | 策略关联具体 trader；需要相应行情插件提供 order queue/detail/transaction | **直接支持订单级控制**。没有 CTA 的组合净目标执行层；策略需要管理自身订单及 ready/lost，所需权限仍由真实 Trader/外部系统保证 |
| UFT | 独立 `WtUftRunner → WtUftEngine/UftStraContext → WtUftCore::TraderAdapter → ITraderApi`；策略直接订单 API，并保留本地成交驱动持仓 | 独立 Runner/Core、策略工厂、交易通道；共享参数功能另配置 ShareManager/helper | **独立低延迟路径**。不能把 WtCore 的全部风控、资金通知、存储或生命周期能力直接套用；UFT 多个风险调用被注释 |

源码入口：

- CTA：`src/WtCore/CtaStraBaseCtx.cpp:1121-1410,1413-1571`；`WtCtaEngine.cpp:241-408,421-472`。
- SEL：`src/WtCore/WtSelEngine.cpp:172-320,410-462`；`SelStraBaseCtx.cpp:735-784`。
- HFT：`src/WtCore/HftStraBaseCtx.cpp:183-315`；`src/WtRunner/WtRunner.cpp:321-361` 完成 trader→context 的 sink 绑定。
- UFT：`src/WtUftRunner/WtUftRunner.cpp:200-247,351-358`；`src/WtUftCore/UftStraContext.cpp:860-925`；`src/Includes/IUftStraCtx.h:89-264`。

### SEL 宿主必须单独验收

固定 `src/WtRunner/WtRunner.cpp:381-400` 会创建/选择 SEL engine，但 `234-281` 仍向 `_cta_engine` 装路由并调用 `initCtaStrategies`；`465-544` 的 Local/Diff/Dist 执行器也全部加入 `_cta_engine`。因此“SEL 类存在”与“当前 Runner 配置可贯通 SEL 执行”是不同能力。

`src/WtPorter/WtRtRunner.cpp:334-352` 有可用的 `createSelContext`，`739-779` 有 `initSelStrategies` 实现；然而其常规 config `656-705` 同样走 CTA 路由/策略分支，`927-1035` 执行器也仍加入 `_cta_engine`。可以通过既有 engine/context 接口的宿主装配补接，但需要完整原样链验证。此处记录静态接线限制，上游修改遵循审批规则。

## 目标合并、执行器和外部执行入口

**CTA/SEL 的目标汇总应直接复用。** CTA 在策略 pool 完成一批计算后再枚举各策略持仓，应用策略/代码/执行器过滤、主力映射、风险比例，并提交缓存目标。`WtExecuterMgr` 按 strategy→executer 路由聚合目标；未定向路由有 ALL 路径。相关源码：`WtCtaEngine.cpp:241-408`、`WtExecMgr.cpp:22-105,124-240`。

| 模块 | 已有能力 | 关键条件及边界 |
|---|---|---|
| `WtLocalExecuter` | 按品种选 ExecuteUnit；目标缩放/取整；全目标和增量目标；行情/交易回报转发；可选执行线程池、组合代码分组 | `policy` 和 default/品种项、`scale`、`poolsize`、`strict_sync`、`clear` 有实际行为。缺失配置不能视为受控默认 |
| `WtDiffExecuter` | 为独立执行目标维护 target/diff，持久化并交给差量单元 | 适合由自身差量状态管理的执行；不能与另一个自建差量账本并列拥有同一目标 |
| `WtDistExecuter` | 保存/缩放目标，输出目标变化日志 | **固定版本没有实际广播实现**；`set_position/on_position_changed` 的广播位置仅注释。不能直接声称拥有分布式可靠目标传输 |
| `WtArbiExecuter` | 有类与 Porter 装配分支 | **套利执行能力未证成**：默认 `WtExeFact::createArbiExeUnit` 返回 NULL。需要有效套利算法工厂、适配和行为验收 |
| `WtExecMon/WtExecRunner` | 不依赖策略引擎的执行宿主；`setPosition` 缓存目标，`commitPositions` 把该批全量目标传给 ExecuterMgr 并清缓存 | 可作为外部业务目标接入的原生入口。它不是自带审批/持久投递协议；批次漏项有清零影响；release 仅停日志 |
| `IExecCommand/ExecuteContext/ExecuteUnit/IExecuterFact` | 公开目标执行、市场/仓位查询、买卖/撤单、回报和工厂接缝 | 真正独有执行算法放插件；原生接口不携带旧 OrderCommand 的完整签名或审批模型 |

关键源码：`WtLocalExecuter.cpp:51-172,280-442,465-614`；`WtDiffExecuter.cpp:80-195,391-517`；`WtDistExecuter.cpp:21-71`；`src/WtExeFact/WtExeFact.cpp:45-80`；`src/WtExecMon/WtExecRunner.cpp:234-327,403-417`；`src/Includes/ExecuteDefs.h:26-276`。

特别需要写入操作文档的原行为：

- 全目标更新中，先前管理的证券未出现在新目标集合，会被设为 0：`WtLocalExecuter.cpp:383-410`。提交局部集合不能默认为“只改这些证券”。
- `strict_sync=true` 会给账户中不在管理集合的持仓设 0：`415-439`。它是可能引发卖出/平仓的模式。
- 原 MinImpact ready 发现有未完成量但本地监控无单时，会调用 cancel，再计算目标：`WtMinImpactExeUnit.cpp:144-184`。因此给消费者发 ready 可以触发交易行为。
- Local 的 buy/sell/cancel 检查 `_channel_ready`：`218-248`；HFT/UFT 直连需要自己的状态和插件准入，不能借用 Local 的保证。

## 随库算法执行能力

`WtExeFact::createExeUnit` 支持的名称有 `WtTWapExeUnit`、`WtMinImpactExeUnit`、`WtStockMinImpactExeUnit`、`WtVWapExeUnit`、`WtStockVWapExeUnit`；差量工厂支持 `WtDiffMinImpactExeUnit`。`enumExeUnit` 只枚举 TWap/MinImpact，不能用枚举结果当完整实现清单。

| 算法 | 实现能力 | 来源与配置条件 |
|---|---|---|
| MinImpact | 目标与实际/未完成量比较，报价方式、跳数偏移、固定量/盘口比例、发单间隔、超时撤单后重新计算 | `WtMinImpactExeUnit.cpp`；示例 `dist/WtRunnerCta/executers.yaml:8-17`：offset/expire/pricemode/span/byrate/lots/rate |
| DiffMinImpact | 差量执行版最小冲击算法、订单监控与回报处理 | `WtDiffMinImpactExeUnit.cpp`，由 Diff 工厂生成；输入归属以差量执行器为准 |
| TWAP | 指定开始/结束/总时长、执行次数、尾段、挂单时限、报价和最小开仓量；由行情推进定时执行与撤单 | `WtTWapExeUnit.cpp:74-99,195-259,334-503`；参数不能假定与 VWAP 同名同义 |
| VWAP | 按外部预先准备的成交量分布文件制定执行节奏，并有撤单/尾段处理 | `WtVWapExeUnit.cpp:97-144,297-444` 读取 `Vwap_<品种名>.txt`；缺分布文件时不能宣称拥有有效 VWAP 计划 |
| StockMinImpact | 现金多头目标、股票/转债最小数量、可卖数量限制、T0/T1 分支、取消未管理订单选项、最大撤单次数 | `WtStockMinImpactExeUnit.cpp:55-110,149-184,283-315,341-473`；默认 `_is_cancel_unmanaged_order=true`，`.h:170` |
| StockVWAP | 股票数量/可卖约束、VWAP 分布、时间/报价/挂单管理 | **有实现但存在待验证限制**：下文明确参数和 T1 静态问题，不能直接授生产资格 |

StockVWAP 已定位的两个静态风险：

1. `WtStockVWapExeUnit.cpp:116` 在 `119` 赋 `_total_secs` 之前计算 `_fire_span`；还需要排除 `total_times=0` 等不合法配置。普通 VWAP 的初始化同类路径应一起验收。
2. `312-335` 以 `getPosition(code)` 保存名为 realPos 的“总仓”，以 `getPosition(code,false)` 保存名为 vailyPos 的“可用仓”。而 `ExecuteContext::getPosition` 默认 `validOnly=true`，Local 实现沿此语义返回。因此这段总量/可用量使用与接口语义反向。该问题属于具体算法实现，不代表 WT 所有 T+1 路径缺失。

这些是固定源码审读得到的可定位风险；尚缺对应隔离行情/委托行为证据，未给出实际成交影响数字，也没有修改它们。

## 现金股票、T+1 和交易所规则边界

**原生直接具备基础现金股票语义。** `WTSTypes.h:65-68` 定义 `TM_Both/TM_Long/TM_LongT1`；`WTSContractInfo.hpp:47-48` 实现 `canShort/isT1`；`WTSTypes.h:216` 定义 `BT_CASH`。普通方向、开平、限价/市价和部分特定价格枚举存在，FAK/FOK 也有枚举。具体券商是否支持某枚举由对应 Trader 插件决定，不能把 enum 当 SDK 能力证明。

已有 T+1 层次：

- CTA 理论持仓按交易日冻结买入量并在下一交易日释放：`CtaStraBaseCtx.cpp:1027-1032,1441-1446,1542-1546,1826-1850`。
- SEL 设置负目标时检查 canShort，T1 时禁止目标降到冻结量以下：`SelStraBaseCtx.cpp:735-784`；次日释放见 `644-649`。
- 普通 TraderAdapter 实际持仓分今/昨及可用，非 T1 成交开仓才增加当日可用：`TraderAdapter.cpp:1537-1583,2167-2220`。
- HFT 卖出在 canShort=false 时检查可用持仓：`HftStraBaseCtx.cpp:257-270`。
- StockMinImpact 读取总量和可用量并把目标下限设为不可卖部分；T0 另处理：`341-375`。

股票算法还有硬编码最小数量：`WtStockMinImpactExeUnit.h:188-204` 通过标准代码第三段和品种名决定股票 100、被判定科创 200、转债 10（这里只描述固定源码，不声称是当前交易所全部规则）。代码分支 `code>=688000` 和股票/转债品种名需要匹配实际基础数据。北交所、各类 ETF、整手/零股特殊卖出、停复牌/涨跌停/集合竞价/撤单窗口、最新交易规则不能由上述简化逻辑一概覆盖。采用时应针对来源证券和委托类型核验配置与券商拒单语义。

`IStkTraderApi/IStkTraderSpi` 在本版本基本是预留空类；融资融券不能仅以其名字声称支持。`IOptTraderApi` 有附加接口，默认返回 -1；各插件实际映射需单查。原 `ITraderApi` 是有意义的统一接入点，复杂品种资格必须逐项建立。

## 风控和动作策略：已有功能与覆盖范围

| 原生能力 | 实际作用 | 使用边界 |
|---|---|---|
| `ActionPolicyMgr` | 为品种指定 open/close/closetoday/closeyestoday 的优先次序、方向限量、pure 等；TraderAdapter 按最大单笔量拆分 | `ActionPolicyMgr.cpp:29-110`、`TraderAdapter.cpp:693-710,989`。default 缺失最终 assert；这是开平动作策略，不是用户审批流 |
| Trader `riskmon` | 按品种/default 的总委托/撤单量、时间窗频率限制；越界加入排除集合 | `TraderAdapter.cpp:120-147,536-652`。需 active=true 且有匹配规则；无匹配允许。频率检查依赖调用路径，不能视为每次原生发单的统一原子配额 |
| 自成交检测 | 查询/推送成交中发现同成交号关联不同订单，记录自成交并阻断后续相关买卖 | `TraderAdapter.cpp:1806-1840,661-665`。它是基于回报的检测；不是发单前遍历挂单价格的通用预防机制；trade_id 作用域依赖来源 |
| 策略/证券/执行器过滤 | ignore/redirect、执行器禁用；CTA 每轮加载过滤配置并应用目标 | `WtFilterMgr.cpp:13-185`、`WtCtaEngine.cpp:241-245`。配置变化会改变目标；不是多用户访问控制 |
| `WtSimpleRiskMon` | 组合理论权益的日内收益回撤、多日最大回撤触发目标比例缩减或 0 | `WtSimpRiskMon.cpp:30-149`，`WtEngine.cpp:263-276,1120-1160`。以组合引擎 fund 为输入；不能等同真实账户现金风险/每策略独立止损 |
| 插件/柜台检查 | 插件登录状态、SDK/券商原生风控和拒单 | 每个插件各有实现；统一 ABI 不保证账户权限、真实交易开关和跨进程幂等 |

重要路径差异：Local 在目标设置处分支调用 `checkOrderLimits`（`WtLocalExecuter.cpp:364-368`），直接 buy/sell 入口主要检查 channel ready；HFT 在上下文多处检查频率。UFT `TraderAdapter.cpp:337-341,444-448,724-728,996-1000` 等位置的相应调用/时间缓存更新被注释。UFT 虽加载 riskmon 配置并保留检查函数，不能据此宣称实际发单路径具有普通 Core 同等保护。

应退出的重合实现包括自建通用限频、通用目标过滤、通用组合回撤执行（在业务口径等同且上述路径验收后）。应保留为策略/风控扩展的独有内容包括每策略特定止损规则、业务资金预算与跨策略授权约束。不得用 WT 通用回撤参数替换用户不同策略的不同止损定义。

## 委托、成交、账户与身份所有权

统一 ABI：`src/Includes/ITraderApi.h:104-300`，包括初始化/释放/登录/登出/生成委托号/报撤单/资金持仓订单成交查询，以及对应 SPI 回报。真实账户/订单事实来自柜台，WT Adapter 是本地交易投影。

普通 `TraderAdapter::doEntrust`（`484-511`）调用插件生成 entrustID，生成 WT localid，并写 `otp.<adapter id>.<localid>` usertag；返回码负数表示该次调用失败，非负只表示接口接收/发送阶段。最终受理、拒单、成交、撤单由回报处理。

`onRspPosition` 初始化今昨/可用持仓；`onRspOrders` 初始化统计、活动 WT 标签单与未完成量；`onRspTrades` 初始化成交统计；`onRspAccount` 通知资金和最终 ready（`1506-1803`）。外部单及本系统单有明确差异：活动管理依靠 usertag，外部成交也可能影响账户持仓/通知；不能将账户总仓推导成某一策略归属。

活动订单的 `getVolLeft()` 与 Adapter 的 `getUndoneQty()` 由各自的回报路径更新。普通部分成交 `onPushOrder` 保存订单对象并把剩余量传给 `on_order`，其中只有撤单分支扣减未完成量；实际 `onPushTrade` 扣减成交量。以新买100股为例，只收到已成交20股的订单状态时，订单对象剩余80股、`getUndoneQty()`仍为100股；对应20股成交回报到达后，未完成量才变为80股，实际持仓增加20股。接入方保持订单与成交的原事实，不根据订单累计成交量另造一笔成交。源码：`TraderAdapter.cpp:2082-2121,2227-2235`。此例描述固定上游普通Core的内存更新语义，不能代替查询与增量覆盖证明。

普通 onPushTrade（`2134-2251`）直接增减持仓、未完成量并通知回调。其 `checkSelfMatch` 位于更新之后，因此同成交号重复推送不能依靠该函数自动免重。订单重复取消也有重复更新可用量/统计的路径（`1883-1935,2026-2067`）。新 QMT 插件要依据来源语义解决重复事实和查询/推送交错；无需为此另造完整账户数据库。

**扩展支持而非上游公开协议**：QMT HTTP、命令签名、跨进程原 command_id 幂等、快照已吸收回报的边界、消费者冻结恢复证明。现有自有 `ManagedTrader` 的 `bootstrap/confirm_resume` 是其中一种实现选择，不是 WT 要求所有柜台具备的接口。

## 启动、断线、重连与重启

普通新实例顺序是：`connect → login → positions → orders → trades → account → ready`，由各查询回调串联。实例内空持仓查询不会自动清掉此前未返回的品种；统计查询也会累加。所以不能将“重复发四查询”笼统等同于幂等重建。

- CTP：`TraderCTP.cpp:170-197` 根据 quick 选择 SDK RESUME/QUICK；断线通知 lost，再连接登录、结算确认、四查询。`633-646` 初始化日内 usertag 映射。SDK flow 语义属于该 SDK，不外推给 QMT。
- XTP：`TraderXTP.cpp:754-818` 首次登录通知 Adapter 并建缓存；后续同对象登录只恢复插件状态。Local 收到先前 lost 后是否重新 ready 必须按真实接线验收。XTP SDK 的 RESUME 枚举还需按随库声明解释，不能凭名字保证跨进程补流。
- 新进程：重新建立 Adapter 内存，取柜台账户事实；策略理论状态、执行目标、plugin 身份缓存分别恢复。
- UFT：与普通 Core 分开的查询/回报实现；`onRspAccount:1206-1215` 只推进 ready，没有普通 Core 的逐项资金 sink 通知。`UftStraContext::on_channel_ready:626-650` 在交易日变化时恢复本地 mmap 状态，先报本地持仓再报 ready。

可以选择更小的首期恢复：连接/回报异常后禁写，保留原命令身份与账户事实，受控重建完整消费者。这样可以避免新增“保留同一 WT 内存消费者并自动恢复 ready”协议；但仍需来源提供可靠查询/增量交接，避免漏算/重算，不能跳过事实边界。

HTTP超时后保持原命令身份并核查受理结果；最新账户快照或CSV文件不足以证明该命令未受理。这项语义由接入路由的唯一命令owner承担，通道观察与命令受理分别确认。

## 原生持久状态：可复用与不可误认

| 状态 | 固定上游真实行为 | 适用归属 |
|---|---|---|
| 普通 Trader `orders.csv` | `savedata` 下，终态订单推送才追加；含外部单，初始化查询不补全历史 | 终态运行记录/展示，不能替代完整命令审批/投递证据 |
| 普通 Trader `trades.csv` | 成交推送追加，初始化成交查询只更新统计 | 收到的成交记录；覆盖范围和重复语义需声明 |
| Trader `rtdata.json` | 资金查询时覆盖持仓和资金；没有从该 JSON 重新加载账户投影的路径 | 运行快照，不是账户重放总账 |
| CTA/SEL 策略 JSON/用户 JSON | 理论持仓明细、冻结、盈亏/费用、信号/条件单、用户状态；明确 load/save | 采用相应引擎后同类策略状态直接归 WT |
| Engine 组合数据 | `WtEngine::save_datas/load_datas` 持有组合持仓/资金/信号/风险比例等 | 组合状态归 WT；其权益是理论组合口径 |
| Diff 执行器 JSON | target/diff 的 load/save | 差量执行目标唯一归执行器 |
| CTP/XTP eid/oid mmap cache/SDK flow | 委托号/柜台单号映射日内 usertag，具体流恢复 | 插件身份恢复，不含跨系统命令事务 |
| UFT `position/order/trade/round.membin` | 策略本地持仓、订单、成交、回合的 mmap；按交易日重用/清理，持仓保留未平明细；支持 `mannual.yaml` 覆盖导入 | UFT 自身成交驱动账务，采用该路径可替代同类重复本地账本；不能与 CTA 理论账簿混为一种 |

源码：`TraderAdapter.cpp:234-385,2124-2127,2241-2243`；`CtaStraBaseCtx.cpp:221-645`；`SelStraBaseCtx.cpp:171-480`；`WtEngine.cpp:363-585`；`WtDiffExecuter.cpp:80-195`；`UftStraContext.cpp:1026-1345`。

UFT `on_trade` 先检查自身 localid，再按实际成交更新净持仓和回合盈亏（`118-588`）。UFT 与 CTA/SEL 的状态含义有实质差别，不能选最丰富的字段并拼成一个“WT统一账户数据库”。

文件/mmap 的存在证明原生状态已实现；不证明机器断电、多文件提交、发送柜台命令与文件更新具有共同事务。普通 JSON 用创建文件再写；WtKVCache 的 put 没有逐次 sync。生产仍要按实际恢复目标验证文件损坏/部分写入/崩溃，但无需先引入 PG 才能进行 WT 开发。

## 线程、退出与正常释放能力

- CTA 策略池等待一批回调结束后汇总目标；执行器有独立 pool；SDK 插件可能有自己的网络/查询线程；`poolsize=0` 不等于整个进程单线程。
- MinImpact/StockMinImpact 的 do_calc 有局部互斥；订单监控有自身锁；Adapter 的活动单锁不能外推保护所有仓位/统计 map。
- SEL 定时任务在 `WtSelEngine.cpp:311-318` 创建 thread 调度上下文，未在该局部路径看到 join/detach；实际线程生命周期需要隔离验证，不能从“有定时器”推断稳定后台调度已全部验收。
- Trader 公开 `disconnect/release`，普通 Adapter release 先 registerSpi(NULL) 再 plugin release。CTP disconnect 有 worker join；XTP release 解绑 SDK 再 Release。各插件仍需验证迟到回报及对象寿命。
- 固定 `WtRunner`/`WtUftRunner` 没有一项完整对外受管 stop 串联；`WtPorter/WtRtRunner.cpp:1135-1138` 与 `WtExecRunner.cpp:403-406` 的 release 只停止日志。引擎/ticker/risk 的局部 stop 与宿主完整退出是两种能力。
- 目标要求有界停止、服务重启、DLL 卸载时，先查现有 stop/release 接口并由宿主编排；必要缺口单项说明。不能把工作区已经增加的关闭行为写成固定上游固有能力。

上述并发判断基于固定源码职责和调用点，具体路径仍需竞争检测、崩溃注入或退出行为证据，因此具体并发故障发生率和生产停止资格为**未知**。

