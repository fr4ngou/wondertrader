# WonderTrader 原生策略与回测能力

类型：长期模块能力说明。C++固定上游：`08b230dd05facf6d650d949bfe51054115a2ecb1`；官方可选wtpy参考：`9fd4cd98feaa6fa2ea084741b3bb2adbe2b6bd78`。源码支持、配置条件和实机资格分别登记；下游新增实现不计入原生支持。升级时复核对应入口和限制。

本说明覆盖四类策略接口及五类回测mocker主要路径，不授予所有参数/并发组合或真实交易的运行资格。能力目录及复用方法见[开发入口](../development/wondertrader-capabilities.md)。

## 一、四种策略引擎

| 引擎 | 原生接口及运行模型 | 历史/实时与执行能力 | 已核实限制 |
|---|---|---|---|
| CTA | `CtaStrategyDefs.h` + `ICtaStraCtx.h`；初始化、交易日、tick、bar、schedule、schedule_done、条件触发；`WtCtaEngine` / `CtaStraContext` | 主 K 线闭合驱动计算，读 bars/ticks/last_tick；设置目标仓位、进出场、限价/止损条件；理论部位与执行分离 | 同一主 K 线只能登记一次；计算依主序列、交易时段和 reader 数据；计算应有界，不在回调阻塞补数据/网络。理论部位不等于券商实际持仓 |
| SEL | `SelStrategyDefs.h` + `ISelStraCtx.h`；定时重算及 tick/bar，`WtSelEngine` 注册 minute/day/week/month/year 任务 | 用目标仓位表达多标的配置；历史窗口及理论部位，适合截面/选股 | `on_schedule` 未重新发出目标的已有标的会自动生成清仓信号；一次调度应提交完整目标集合。调度截止主要约束 bars，不能扩大为所有查询的原子快照 |
| HFT | `HftStrategyDefs.h` + `IHftStraCtx.h`；tick、L2、委托/成交、通道、持仓等事件 | 直接买卖撤单；bars/ticks/L2 切片、未完成订单和持仓查询；`WtCore` 实现 | 需要真实源提供相应数据和执行能力；QMT 普通快照不等于 L2，HTTP 适配也不继承宣传中的微秒延迟。回调线程来自实际入口，不能假设全局单线程 |
| UFT | `UftStrategyDefs.h` + `IUftStraCtx.h`；独立 `WtUftCore` / `WtUftRunner`，C++ 策略工厂 | 直接执行、实时事件、参数 watch/read/sync、局部持仓 | **实盘 `WtUftDtMgr.cpp:88–110` 的 tick/L2/bar 历史切片均返回 NULL**；`UftStraContext` 暴露转发接口不能证明可用。`UftMocker` 回测可读取相应历史，是不同实现。需要历史分钟窗口的策略须选择具有实际读取实现的运行路径 |

源码：[四种策略定义目录](https://github.com/wondertrader/wondertrader/tree/08b230dd05facf6d650d949bfe51054115a2ecb1/src/Includes)、[CTA 调度](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/CtaStraBaseCtx.cpp#L939)、[SEL 重算/自动清仓](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/SelStraBaseCtx.cpp#L589)、[UFT 实盘数据管理](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtUftCore/WtUftDtMgr.cpp#L88)。

### 调度与并发的实际边界

- CTA `WtCtaEngine.cpp:241–313` 可在线程池并发不同上下文的 schedule，随后 `pool->wait()` 再汇总目标；tick/bar 分发也有等待屏障（约 528–653）。这给出该分发阶段的顺序，并不保证插件外部线程、任意用户线程和所有异步回报天然共享同一锁。策略共享全局对象、研究状态或跨上下文缓存必须单独定义所有者。
- 基类组合浮盈后台线程与CTA策略线程池分别拥有任务：`WtEngine::on_tick`向`_thrd_task`队列提交组合仓位浮盈和资金汇总任务；`poolsize=0`只关闭CTA策略池，基类任务仍可异步执行。`_mtx_task`协调队列，单仓位`PosInfo::_mtx`保护对象内容；查找或增加`_pos_map`属于容器结构访问，须另外核对其所有权和同步范围。`pool->wait()`的等待范围限于所选策略池，不能据此推定基类任务也已完成。源码：[基类行情任务](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/WtEngine.cpp#L151)、[队列执行](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/WtEngine.cpp#L1074)。

- SEL `WtSelEngine.cpp:220–319` 按日历/周期选任务并创建线程调用上下文；`SelStraBaseCtx.cpp:935–976` 的 bars 明确传调度时间，日 bars 传该日收盘时间；ticks/last_tick 直接调用当前引擎查询。应按方法说明截止语义，避免将官方“数据截至 T0”概述直接扩大为所有方法的强一致性保证。同策略前次计算未完、多个事件并发和停止排空的资格需专门验证；这些静态观察尚未形成并发故障复现证据。
- HFT `WtHftEngine::handle_push_order_detail/queue/transaction` 直接调用订阅上下文；`WtHftRtTicker::on_tick/trigger_price` 有直接分发路径。UFT `WtUftEngine::on_tick` 和 `UftStraContext::on_tick` 也直接调用策略；参数更新另由 `ShareManager` watcher 触发。低延迟路径不应放研究请求、磁盘归档或慢 HTTP。
- 以上是源码结构与使用约束，不是“WT 无法使用”的判断；插件选择、调用线程及适用引擎必须纳入逐项运行测试。下游CTA退出扩展与固定上游分别登记资格。

参考：[CTA 引擎](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/WtCtaEngine.cpp#L241)、[SEL 引擎](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/WtSelEngine.cpp#L220)、[SEL 查询实现](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/SelStraBaseCtx.cpp#L935)、[官方 SEL 说明](https://wtdocs.readthedocs.io/zh/latest/docs/usage/selstra.html)。

## 二、历史窗口、指标与策略状态

### CTA 策略、净额组合与交易通道

原生CTA已有三层记录，按各自职责复用：

| 层次 | 原生事实与入口 | 核对口径 |
|---|---|---|
| 子策略 | `CtaStraBaseCtx::on_tick/do_set_position/update_dyn_profit`；独立持仓明细、理论成交、费用和盈亏 | 按策略信号、行情及配置计算理论绩效；部分券商成交不会自动把各策略持仓按比例缩减 |
| 净额组合 | `WtCtaEngine::on_schedule`汇总目标；`WtEngine::do_set_position`维护组合明细、费用与资金 | 组合目标包含路由、过滤及风险缩放条件；相向策略变化净额为零时可以保持组合仓位 |
| 交易通道 | `TraderAdapter`账户、持仓、订单、成交记录；Local/执行单元读取实际持仓及未完成数量 | 目标与实际持仓形成执行差额；活动同向订单由算法等待，反向及超时订单按所选算法处理 |

策略理论账本承接独立策略绩效，净额组合账本承接组合绩效，券商事实承接实际账户核对。先统一期间、期初、估值、资金流及费用口径，再解释策略到组合的净额/费用差异和组合到实际账户的执行差异。原生已有这些记录；当前CTA接入尚无把全部实际收益差额自动分回各子策略的已验结论。采用原生记录与执行机制，保持单一事实所有者。

源码：[策略记账](../../src/WtCore/CtaStraBaseCtx.cpp)、[组合汇总](../../src/WtCore/WtCtaEngine.cpp)、[净额组合记账](../../src/WtCore/WtEngine.cpp)、[原生差额执行](../../src/WtExeFact/WtMinImpactExeUnit.cpp)。[官方Studio手册3.2–3.4](https://wtdocs.readthedocs.io/zh/latest/docs/studio/main.html)同样区分策略理论、组合净头寸理论与通道数据。当前接入的限定验证见[多策略核对证据](../evidence/2026-10-28-multi-strategy-reconciliation.md)。

### 原生可复用

`ICtaStraCtx/ISelStraCtx` 已有目标/持仓、开仓时间、成本、盈亏、资金及历史读取。`CtaStraBaseCtx` / `SelStraBaseCtx` 持久理论状态；CTA、SEL、HFT 都有 `stra_save_user_data/stra_load_user_data` 扩展。CTA 用户数据是字符串键值，写入 `ud_<策略名>.json`，在相应回调完成或会话路径落盘；回测 CtaMocker 同样保存用户 KV，并输出策略结果。可将策略自己的止损锚、迟滞状态、上一决策日等按版本序列化，逐字段映射到原上下文，而不是继续维护第二套通用仓位运行器。[CTA 用户数据实现](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/CtaStraBaseCtx.cpp#L221)

用户 KV 的文件写入与另一文件的理论仓位、外部审批和真实委托之间，在上述函数里没有统一事务。`load_userdata` 对空文件/解析失败直接返回；因此不能把“有 save/load 方法”解释成未知真实委托可完整恢复。纯策略派生状态可从冻结输入重建；已经产生的真实执行副作用仍由唯一执行事实链处理。应先定义哪些业务状态要求原子提交，再选择最小扩展，不由此预设 PG 或新账本。

指标：策略可以读取 K 线切片、抽取值数组并计算纯算法；示例 DualThrust 直接计算高低界。CTA 的 `register_index/register_index_line/set_index_value` 是图表指标登记/输出接口，不是内置任意指标计算引擎；`set_index_value` 要求在 schedule 中并已登记。原算法可作为策略库复用或移植，结果交原图表记录；无需先发特征消息再回流才能进行策略计算。[原生示例](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCtaStraFact/WtStraDualThrust.cpp)、[指标输出接口](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtCore/CtaStraBaseCtx.cpp#L1995)

### 必须写清的条件

- 原接口返回 slice 指针，示例显式 `release()`；业务代码须遵循对应引用生命周期，不能跨异步线程保留无所有权的数据指针。
- `get_bars(count)` 是窗口请求，缺数据可能返回空或不足；它不直接承诺从 QMT 下载十年或证明停牌/上市前空段。源接入和补齐应沿原 loader/store 接缝，明确 readiness，核心策略回调保持有界。
- 回测 `HisDataReplayer::get_kline_slice` 按回放游标、时段、复权因子和重采样切片，支持 extloader 和原格式/CSV 数据来源。历史质量、知晓截止及因子版本仍依实际输入；不能仅因没有未来游标就宣称任意外部研究输入都无前视。
- UFT 的参数共享机制是独立能力，`ShareManager` 加载 WtShareHelper 并监听更新；不能等同 CTA 通用用户 KV，也不能当作研究审批数据库。

源码：[回测切片加载与游标](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtBtCore/HisDataReplayer.cpp#L2170)、[UFT 参数机制](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtUftCore/ShareManager.cpp)。

### 公开C ABI与外部语言接线

`src/WtPorter`与`src/WtBtPorter`直接导出策略回调、bars读取、理论目标及用户KV接口，外部语言可以绑定这些原生函数；wtpy属于可选封装。CTA算法使用同一业务核接两类上下文时，调度、窗口、理论仓位和回放仍由对应原生引擎拥有。

两端同名导出存在签名差别：实时`register_cta_callbacks`为6个回调参数，回测为7个，额外包含calc_done。Windows头声明使用cdecl；`CtxHandler`定义为unsigned long，在Windows x64为4字节，指针为8字节。结构体沿`WTSStruct.h`的pack8；Windows x64原生头布局中WTSBarStruct为88字节/对齐8，字段time为原生时间编码，日线使用date，不能作为Unix时间解释。绑定应以实际编译的sizeof/offsetof及所用头/库身份确认，其他平台重新验证。

`cta_get_bars`通过同步多块回调返回借用数据，回调结束后原生释放slice；消费者在回调内复制并核count/isLast，不保留裸指针。用户KV返回的字符串也须及时复制。ctx_on_calc直接进入注册回调，其线程来自实际CTA调度；外部HTTP线程不能直接操作ctx，异常须在语言边界捕获。不同ctx可能在线程池并发，GIL不能代替原生所有权约束。

实时CtaStraBaseCtx会读取ud文件；固定CtaMocker有内存KV及dump输出，但其load_incremental_data路径没有证明会恢复用户KV。理论仓位和KV的独立文件也不能推出跨文件事务。版本与输入一致的派生状态可由冻结前缀重建，真实执行副作用沿执行事实链处理。

公开release函数具有各自范围：固定WtPorter的release_porter调用WtRtRunner::release，后者仅停Logger；固定WtBtPorter的stop_backtest进入可能join的回测停止链。使用方应验证完整线程、模块和文件生命周期，给宿主独立停止截止；进程被终止的输出保留中断资格。上述结论限定这些导出路径，不推导其他原生宿主缺少停止能力。

源码：[实时公开头](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtPorter/WtPorter.h)、[回测公开头](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtBtPorter/WtBtPorter.h)、[实时适配实现](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtPorter/WtPorter.cpp)、[实时runner](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtPorter/WtRtRunner.cpp)、[回测runner](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtBtPorter/WtBtRunner.cpp)。

## 三、原生回测实际调用链

固定CTA/BT的目标与实际理论仓位按查询入口分别解释：`get_all_position`用pending信号覆盖已有position；新证券尚无position记录时`get_position`也可回显pending。当前明细的first/last entry在全部平仓后归0，须结合实际原生阶段核成交。void setter没有批目标事务；固定BT实测actual100→pending200→set100会保留pending200。同一轮反复设置不能代替可靠的pending撤销。按原生观察冻结/推进的业务转换要求见[NSQ](../specs/native-strategy-quantity.md)，实际范围及输入身份见[日线/目标实验](../evidence/2026-10-22-native-strategy-kernel.md)。

`cta_get_fund_data(0)`返回策略已实现盈亏加浮盈亏减费用；理论NAV需要明确初始本金及无外部现金流条件，现金购买力还需其他估值事实。品种资料的lotstick/minlots被装载，不表示每个mocker自动按其检查整手；固定CtaMocker相关setter/撮合路径未使用这两个getter。适配边界按实际品种单位验证，费用仍由原生撮合输出拥有。

```text
WtBtRunner + 配置/策略工厂
  → HisDataReplayer（日期/交易日、证券/时段、历史与复权因子）
  → CtaMocker / SelMocker / HftMocker / UftMocker / ExecMocker
  → 同类型原策略接口/执行单元
  → 理论成交、资金、部位和日志输出
```

`src/WtBtRunner/WtBtRunner.cpp:76–139` 原生入口按 `env.mocker` 装配五类 mocker，调用 `prepare()`、`run(true)`。CTA/SEL 工厂与实盘使用相同类型策略接口；信号算法可以一份代码运行两端。上下文和撮合环境有区别，同接口不保证实盘价格、成交、时钟和恢复结果相同。[原生回测入口](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtBtRunner/WtBtRunner.cpp#L76)

回放支持 bars 路径和真实高频数据路径；bar 模拟路径会按 open/high/low/close 构造价格事件。仅有 1 分钟 OHLCV 无法重建真实逐笔顺序或订单簿。HFT/UFT/执行器回测的可信粒度取决于实际 tick/L2 输入及模型，不能以“支持该引擎”替代数据资格。[回放实现](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtBtCore/HisDataReplayer.cpp#L739)

原生入口当前只装配一个选定 mocker/策略实例；SEL 注册回测任务，CTA 另提供 `incremental_backtest_base` 加载已有输出/策略 JSON。它是特定 CTA 增量入口，不能据此承诺所有引擎通用断点续跑、分布式作业恢复或一份配置同时回测任意策略组合。入口末尾还有 `getchar()`；后台任务包装应正确处理 stdin/进程退出，不能把进程仍等待输入误报为回测仍运行。

## 四、撮合、费用与滑点

| 能力 | 固定源码事实 | 适用限制 |
|---|---|---|
| CTA/SEL 理论撮合 | mocker 按目标差及行情价格产生理论成交/部位，支持对应条件与商品规则 | 用于策略层验证；不模拟原生执行器所有追单/队列/冲击过程。回测收益不等于柜台可成交收益 |
| HFT | `HftMocker::procOrder` 使用最新价或对手一档、对手量、限价条件，并分拆成交；可配置 `use_newpx/error_rate/match_this_tick` | 不是交易所全订单簿重建。`splitVolume/genRand` 用真实时间播种，不能默认承诺不同运行逐笔结果完全一致；`error_rate=0` 也不能消除拆量随机因素 |
| UFT | 有独立 `UftMocker` 与订单/成交回调实现，匹配配置含上述三项 | 须验证该模型及对应输入；实盘窗口缺失不由回测成功补足 |
| 执行单元 | `ExecMocker` 单独使用 `MatchEngine`；后者有主动/被动成交与简化排队量 | 该 MatchEngine 不应统称所有 mocker 的共同撮合内核 |
| 手续费 | `HisDataReplayer::calc_fee` 按商品身份查费率，支持按量/成交额，开/平/平今，`minfee`，最终分币舍入 | 缺配置返回0；最低费是每次 fill 计算，分笔与每委托合计计费可不同。券商股票佣金/税费规则须显式映射，不自动保证一致 |
| 滑点 | CTA/SEL mocker 构造支持绝对tick数或比例；普通 WtBtRunner 只传整数 `slippage`，使用默认绝对模式 | 构造接口具有比例参数，不代表当前 CLI 已暴露该配置；盘口冲击或容量模型不由一个滑点参数自动覆盖 |

依据：[HFT 配置与撮合](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtBtCore/HftMocker.cpp#L699)、[HFT 随机拆分](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtBtCore/HftMocker.cpp#L47)、[ExecMocker](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtBtCore/ExecMocker.cpp#L55)、[费用](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtBtCore/HisDataReplayer.cpp#L2924)、[CTA 滑点](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtBtCore/CtaMocker.cpp#L1635)。

## 五、绩效、参数搜索、研究和任务管理的分层

| 层 | 已有能力 | 使用边界 |
|---|---|---|
| C++ 原生结果 | CTA 输出 trades/closes/funds/signals/positions CSV、用户 JSON，另有图表配置、指标和标记；其他 mocker 输出各自对应文件 | 通用成交、资金曲线和理论绩效的基础事实沿原结果消费；按不同引擎核字段，不能把 CTA 文件全集套给 UFT |
| wtpy WtBtAnalyst | 从回测结果计算统计并导出 Excel | 可选复用工具，独立于原生运行；纯C++部署时应明确选取等价结果分析实现，不继续保留旧撮合引擎来得到报表 |
| wtpy WtCtaOptimizer | 参数组合、multiprocessing 分批启动回测和汇总，代码有 C++ 策略模块/类型参数 | 可优化 C++ 策略，但优化器本身依赖 wtpy.WtBtEngine；不等于原生 WtBtRunner 自带参数搜索。是否仅使用离线官方工具需明确，不能偷偷加入必需依赖 |
| wtpy WtMonSvr/WatchDog/BtSnooper | 进程启停/守护、时间任务、运行监控及回测查看 | 属 Python 运维/展示工具。引擎内部 SEL 调度不是操作系统进程任务管理；业务系统的独立发布/任务与中文页面按各自契约接入 |
| 已退出的新闻与研究产品 | 新闻证据、AIScoreCard、候选研究、校准/漂移、多角色研究及用户报告 | 固定 WT C++ 运行模块与上述官方工具中未找到等价产品功能。按[ADR-0004](../architecture/adr/0004-core-trading-product-scope.md)整体退出迁入和验收范围；策略必要事实及因果时间约束由策略数据契约维护 |

原生：[CtaMocker::dump_outputs](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtBtCore/CtaMocker.cpp#L339)。官方可选工具：[WtBtAnalyst](https://github.com/wondertrader/wtpy/blob/9fd4cd98feaa6fa2ea084741b3bb2adbe2b6bd78/wtpy/apps/WtBtAnalyst.py)、[WtCtaOptimizer](https://github.com/wondertrader/wtpy/blob/9fd4cd98feaa6fa2ea084741b3bb2adbe2b6bd78/wtpy/apps/WtCtaOptimizer.py)、[WatchDog](https://github.com/wondertrader/wtpy/blob/9fd4cd98feaa6fa2ea084741b3bb2adbe2b6bd78/wtpy/monitor/WatchDog.py)。这些链接证明工具存在和职责，不证明本机已安装或已与本固定核心版本匹配。

