# QMT 全推行情数据流

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块说明。范围：终端内报价推送、共享内存运输及原生 DataKit 接线。运行资格见具体证据。

## 职责与入口

[QuoteStreamAgent](../../connectors/qmt_shm/agent/guanheng_qmt_shm_agent/quote_stream.py) 由原策略线程订阅/退订 ContextInfo 全推；SDK 回调只更新有界纯值内存。唯一 I/O owner 运行既有 LocalTransport/Session。内置策略由构建工具（外部历史/待归仓路径：`../../scripts/qmt_quote_stream_memory.py`）在终端外生成完整正文；终端内沿既有内存运行格式，不读取外部源码、配置或建立网络连接。

[QuoteStreamReceiver](../../connectors/qmt_shm/host/guanheng_qmt_shm/quote_stream.py) 在终端外监听命名共享内存，完成 profile/HMAC 后将固定大小批次同步交给唯一消费线程。主线程负责管理关闭，接收线程退出后才释放原生 Writer。报价不进入账户/交易命令 Journal。

NativeDataKitSession（外部历史/待归仓路径：`../../integrations/guanheng/datakit.py`） 调用自有 C++ 薄会话（外部历史/待归仓路径：`../../src/GuanhengDataKit/Session.cpp`），装配原公开 ParserAdapter、DataManager、StateMonitor 及 Writer，复用 map_ticks 和 handleQuote(procFlag=1)。原生分钟切片、时段及文件格式见[原生采集模块](wondertrader-datakit.md)。薄层只拥有运输/装配与观察计数，不实现第二套聚合。

## 数据与生命周期

完整合同见[规格](../specs/qmt-quote-stream.md)。证券清单和 profile 绑定；离线仅留最新快照，新代先发快照后发有界增量。溢出标记缺口并关闭本代，清理后再连；历史缺口另验。心跳表达接受/拒绝、队列、最新覆盖/缺失及溢出。来源无报价和单位资格明确表达，缺失值不伪造。

Source 订阅/退订归原策略线程，回调持锁更新内存；I/O owner 独占运输资源。Receiver 单 I/O owner 同步交付原生消费。C++ 会话要求同步 Writer、单 producer、管理线程关闭。生产 session、基础资料、节假日、量额与 writer 参数由运行配置提供，隔离 allday 场外观察不能代替正式日间采集资格。

## 验证

主入口为真实共享内存运输夹具（外部历史/待归仓路径：`../../tests/integration/qmt_quote_stream/run.py`）与原生落盘夹具（外部历史/待归仓路径：`../../tests/integration/qmt_quote_datakit/run.py`）。数据源是明确 SDK 替身，文件由真实原生 Writer 生成并经原 Helper 回读。真实 QMT 接入、盘中完整分钟、常驻恢复及自动收盘分别登记。当前证据见[全推接线验证](../evidence/2026-10-28-qmt-quote-stream-main.md)。

## 结构与开发约束

报价包、心跳、最新状态字典/有界队列和来源分钟/标准分钟的区别，统一查[行情数据结构](market-data-contracts.md)。内置解释器、API目录和并发优化原则查[国信Python手册](../runbooks/guosen-qmt-python.md)。生产者回调只处理纯值，当前I/O owner数量为1；创建线程成功与SDK线程安全/全天性能分别验收。


## 启动与稳态性能

初始全量快照可触发原Writer逐证券创建实时文件；同证券后继更新复用已建立映射。初始交付、最新覆盖、心跳、增量吞吐、原生关闭及文件回读分别观察。外部完整规模的诊断结果见[阶段性能证据](../evidence/2026-10-28-qmt-quote-performance.md)，具体耗时与现场运行资格保留在该证据中。

## 运行观察与真实来源资格

每次状态先核采样墙钟、进程身份与创建时间、原管理owner是否仍持有进程；最后一份JSON和READY登记的PID只描述记录时刻，不能证明当前存活。将接收计数、原始源时间、原生处理计数和完整分钟分别核实：计数增长证明持续处理，源时间与墙钟差值用于判断新鲜度，心跳queue_depth仅描述自有队列，不覆盖QMT内部等待回调的队列。

源时间是SDK原数值透传。若行情滞后，依次对照同证券的QMT全推缓存、SDK回调入口时间/最大源时间、回调耗时、自有排队/发送、接收和Writer进度。原生个股行情与全推可能走不同数据中心；单个界面更新不能替代同一全推缓存的对照。首次累计快照、最后尚未结束分钟、断线缺口及缺失证券分别保留质量状态，不用文件数量判完整覆盖。

现场观察、长期受管采集和发行切换分别验收。限时诊断到截止后应核实际退出/资源收据及原Helper回读；重启使用独立存储或明确单写者交接，保持原数据。显式生命周期库及管理线程关闭规则见[原生DataKit](wondertrader-datakit.md#可选择的生命周期适配库)。

## WT管理采集

QuoteCollection（外部历史/待归仓路径：`../../integrations/guanheng/quote_collection.py`） 将 Receiver 与 NativeDataKitSession 组装为一个生命周期。start 所在线程负责管理；唯一接收线程同步 push，状态只读缓存。request_close 可跨线程发布，close 沿首个绝对截止先关闭并 join Receiver，再归档/关闭 Native。未知批次和已提交归档都保持原身份，不自动重放。

采集子服务（外部历史/待归仓路径：`../../integrations/guanheng/quote_collection_service.py`） 承担外部配置、单写者锁与固定状态收据。已核原生配置字节写入本实例私有输入；目录锁与未收束组件共同保留。原生 sink 的实际 Writer 错误经自有 Session 的原子闩锁传回 push、健康检查和 close；资源已释放与写入成功分别表达。分钟算法、时段、DMB/DSB仍归原生组件。

独立WT的 [QuoteCollectionProcess](../../apps/wt_runtime/guanheng_wt_runtime/quote_collection_process.py) 通过实例components.collection显式装配子服务；未声明该组件时不构造采集进程。它与Host复用 [ManagedLocalProcess](../../apps/wt_runtime/guanheng_wt_runtime/managed_local_process.py) 的创建期Job、实际PID、限额输出、原截止及资源回收证明。WT按执行、采集、历史、Host逆序关闭；观衡仅读公开状态，停止观衡保持采集运行。启动就绪表示listener可等待来源，来源可以晚于60秒启动。部署步骤见[持续采集手册](../runbooks/qmt-data-collection.md)，运行合同见[WRI](../specs/independent-wt-runtime.md)。

## 心跳计数与证券覆盖

持续分钟覆盖及恢复沿[MCC规格](../specs/continuous-minute-collection.md)。采集子配置可显式引用`maintenance={path,sha256}`；省略保持原采集路径。接收线程成功交付整包后只记录证券源毫秒、接收秒和计数。原管理循环运行`MinuteCollectionMaintenance`：消费资料owner当前指针、分批调用标准Reader、观察实际缺口，并接续原`SourcePreparingMarket`闭合日任务。原status/ready/closed合同保持，旁路`coverage.json`和`minute-maintenance.json`分别保存时间/名册差异与实际分钟覆盖；从未收到、当前未订、未知分母及不支持类别分别保留。

完整行情Source由`guanheng_qmt_shm.market_source.render_market_source`复用原冻结器生成，包含原QST/HPR/v7/v8四owner、单`agent_tick` timer及四个生命周期回调。无消费者旧交易owner在新行情正文中移除，独立账户交易/v9正文保持原所有权。开发、实际来源和正式切换状态沿[MCC证据](../evidence/2026-11-04-continuous-minute-collection.md)分别登记。

| 字段/观察 | 实际含义 | 使用边界 |
|---|---|---|
| 配置symbols | 本实例允许的证券集合，与配对profile绑定 | 板块可能含认购、到期及暂停交易代码，不能直接当作当天应有成交的证券数 |
| latest_symbols | 已被normalize_tick接受并保留在_latest的证券数 | 没有按当前交易日/时效自动清零，不代表每只证券都有今天新鲜报价 |
| missing_symbols | 配置集合大小减_latest大小 | 属于快照缓存缺失，分钟缺采须另核 |
| rejected_ticks | 非字典回调、清单外证券或数值/价格准入失败 | 包含正常范围过滤，不能整体解释为网络丢包或已受理行情丢失 |
| queue_depth / overflows | 自有待发送队列深度/溢出 | 只描述本模块队列；不覆盖厂商内部回调排队 |
| 已建DMB数/分钟根数 | 原Writer已建立文件及实际读到的分钟 | 文件存在、当日覆盖、完整闭合分钟分别验收 |

源最大时间只能说明至少一只证券推进；需要判断特定证券时，比较该证券原time、接收时刻、交易状态和实际分钟。已到期、认购用途、停牌标记、开盘前旧值与真正缺数分开记录，来源未确认时保留待核。当前批次的实际分类见[采集覆盖证据](../evidence/2026-10-29-qmt-collection-coverage.md)。


## 显式v2启动与吞吐

[QST9](../specs/qmt-quote-stream.md#qst9-显式冷初始化与在线持续流v2)把同步Writer的冷初始化与在线连续流分为两个明确阶段。冷阶段保留原离线latest，Host确认本代实际初始化集合后，来源同锁切入最新快照及原FIFO。首分钟与初始化窗口保持质量边界；在线增量继续原有界队列，溢出仍显式失败。

`QuoteStreamAgent`与`TickQuoteAgent`共同消费同一packet生成器及初始化屏障；thread与strategy_tick沿各自原运输owner收发同Session收据，未新增线程。`QuoteStreamReceiver`验证完整大帧后，按原200切交Native，原DataKit/Writer二进制保持。普通配置不能在v1中突破200；明确选v2并用正式pair/verify重新固定两端身份。默认v1与旧安装保持原资格。
