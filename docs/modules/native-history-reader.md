# 原生策略历史 Reader

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

后继约束：本页记录已有开发候选及其已验范围。用户要求全部复用WT重合能力后，接线按[原生能力收敛方案](../migration/native-market-integration-plan.md)重新核定；同步HTTP调用和自有窗口链继续暂缓作为最终默认架构。

类型：模块契约。适用范围：Windows 原生 CTA 的基础未复权 `m1` 历史读取和闭合分钟事件。状态：实现入口已提供；运行资格以对应源码、配置和数据的验收记录为准。唯一功能要求见[最终规格](../specs/native-history-reader.md)，启动与恢复见[操作手册](../runbooks/native-history-reader.md)。

## 职责与调用链

```text
CTA stra_get_bars(m1)
  → 原 WtDtMgr（force_cache=false、times=1）
  → GuanhengHistoryReader / IDataReader
  → 本机 reader HTTP 服务
  → StrategyMarket + 权威 CalendarProvider
  → MarketClient → market HTTP / native Store / 已配置行情来源
```

`StrategyMarket` 负责权威交易分钟、来源资格、单位、窗口合并和缺口补齐。reader 服务负责只读 HTTP 边界、统一观察时钟和响应校验。原生插件负责标准代码映射、服务身份、切片所有权和宿主分钟事件。原宿主继续拥有 CTA、策略线程池及策略事件消费。整条链不创建账户、委托或业务账本。

[WtDtMgr::get_kline_slice](../../src/WtCore/WtDtMgr.cpp) 在 `times=1` 且 `force_cache=false` 时直接调用 reader；每次策略读取因此可以看到补齐、追加和同条数修订。`force_cache` 是宿主调用 `WtDtMgr::init` 的参数，不能通过 reader 的 `store` 配置字段设置。WtPorter 的强制缓存、聚合周期和复权数据遵循各自既有契约，本模块仅声明基础未复权 `m1`。

## 实现入口

| 层 | 源码与职责 |
|---|---|
| DLL 工厂 | Factory.cpp（外部历史/待归仓路径：`../../src/ReaderGuanheng/Factory.cpp`）：`createDataReader`、`deleteDataReader`、`stopDataReader` |
| 原生 reader | [StrategyReader.h](../../src/GuanhengData/StrategyReader.h)、[实现](../../src/GuanhengData/StrategyReader.cpp)：初始化、切片、分钟基线、并发准入和停止 |
| 原生 HTTP | [ReaderHttpClient.h](../../src/GuanhengData/ReaderHttpClient.h)、[实现](../../src/GuanhengData/ReaderHttpClient.cpp)：回环地址、Bearer、截止时间和严格响应校验；当前网络实现使用 Windows WinHTTP |
| Python 服务 | reader_service.py（外部历史/待归仓路径：`../../integrations/guanheng/reader_service.py`）：单线程创建、调用和关闭 SDK，固定错误响应 |
| SDK 0.7.0 | [strategy_market.py](../../integrations/guanheng_market_client/strategy_market.py)：`tail_history_1m` 与 `history_1m` 共用日历和完整性规则 |
| 基础服务 | [行情服务模块](market-service.md)：MarketClient 对接的独立行情边界 |

基础 SDK wheel 仍是独立客户端交付，Python 要求为 3.10+。reader HTTP 服务属于观衡运行适配，随其运行目录和受管工厂交付；仅安装基础 wheel 不会启动 reader 服务或提供 WT DLL。

## 历史与时间语义

`tail_history_1m(symbol, count, *, end=None, as_of=None)` 查找最后 `count` 个权威预期分钟。日历扫描以最多三日的窗口向前回溯，共享本次 `timeout` 和 `max_windows`；来源只读取选中窗口。权威分钟不足或来源仍有缺口时返回 `Pending`，保留全有或全无语义。

HTTP `tail` 调用该能力；`range(after,end)` 调用 `history_1m(after + 一分钟, end)`，其中 `after` 为排除端点。空数学范围可以成功返回零条；非空范围的零条成功须来自 SDK 已确认的权威空网格。未确认的日历、来源缺口和异常保持失败状态。

分钟使用上海时区右端标签 `YYYYMMDDHHMM`。HTTP `end=0` 由 `market.clock` 的本次观察值向下取整得到；显式未来端点拒绝。服务的 `as_of`、SDK 查询截止和 delivery 判定共用该时钟，工厂必须提供可信且带时区的时钟。量额已经是股和元，消费者保留来源系数作为证据，不再次相乘。

| 交付标记 | 含义与事件资格 |
|---|---|
| `historical` | tail 历史预热；常规成功读取只建立基线 |
| `recovered` | range 中早于服务当前整分钟的恢复数据；更新完整历史和基线 |
| `current` | range 中恰等于服务 `as_of` 的闭合分钟；还须等于宿主本轮闭合标签才可投递策略事件 |

首次历史读取即登记所需证券和 count。若首次缺失，后续 `onMinuteEnd` 会重新尝试 tail；恢复时仅允许“末条分钟＝宿主本轮标签＝服务 as_of”的条目成为当前事件。成功预热之后使用 range；历史修订通过下一次读取可见，已确认分钟不会再次投递。

## HTTP 与身份边界

入口为 `POST /api/reader/v1/history`，协议 `guanheng.reader.v1`。精确请求与响应字段由 [NHR-R2](../specs/native-history-reader.md#nhr-r2-尾部历史与服务契约) 定义。服务校验版本、请求 id、日期、条数、OHLCV、来源引用、配置版本及资格下限，再把只读谱系容器转成 JSON；源元数据、内容版本和单位证据保持完整。

`instance_id` 在服务启动时生成；`policy_id` 显式标识受管来源和日历配置版本。原生 reader 固定期望 policy，并在首次合格成功时绑定实例。服务重启或身份变化后，宿主停止旧 reader，创建并初始化新 reader。每个 reader 按契约只初始化一次。

Bearer 由受管环境注入，来源配置和工厂导入不受请求控制。服务只绑定字面量回环地址；原生客户端接受 `127.0.0.1` 或 `::1` 的受管地址。服务拒绝重复字段、分块请求、错误认证、超大输入与未来日期，连接逐次关闭；客户端拒绝重定向和不匹配身份。失败 `data={}`，reason 使用固定脱敏文本。

## 所有权、并发与停止

服务在一个拥有线程内执行工厂、SDK 调用和关闭；HTTP 请求串行处理。请求读取、SDK 声明的调用预算、响应容量各有上限。服务不派生超时后继续工作的 SDK 线程；受管依赖必须遵守自身有界调用契约。多请求排队可能耗尽调用方预算，调用者按失败处理并在后续读取重新查询。

原生 reader 支持来自初始化、行情及策略线程的读取。等待锁和网络共用绝对截止；分钟轮次串行准入。宿主回调期间释放会阻塞历史读取的锁，因此回调及 pool 线程可以重新读取历史。每轮先取得所有证券的合格结果，再调用 `on_bar` 和 `on_all_bar_updated`，最后确认基线。数组保留至整批回调返回。

每个成功 slice 拥有独立数组，受 `max_live_bars` 和 `max_slices` 计费。调用方及时 `release()`；新读取不修改旧 slice。reader 对象销毁后，合法持有的旧 slice 仍可使用，直到最后一次 release。插件 DLL 及其依赖的加载引用必须维持到最后一个 slice 释放之后；slice 的虚表、析构及预算归还代码仍属于插件。stop 只等待在途调用结束，不等待调用方释放 slice。

停止先关闭新准入。普通调用在同一绝对截止内等待在途操作及provider的异步系统回调；调用provider排空时释放reader控制锁。批回调期间任何线程的stop都保守返回 `Pending`，由已准入批次完成flush后再确认。受管宿主须在外部再次确认stop成功后调用 `deleteDataReader`；超时或清理错误继续保留reader、sink和依赖资源。

ReaderHttpClient的并发请求在短锁内登记系统session完成事件，最多保留64个未排空session；容量满时拒绝新session，排空后复用槽位。网络调用不持此锁。provider的drain_callbacks接收绝对截止，同步实现默认无需排空，异步实现必须覆盖。直接HTTP客户端最终排空前由调用方停止新read并等在途read完成；排空自身不关闭后续read准入。旧式析构等待排空的兜底可能无界，受管宿主使用显式有界停止接口。

若 sink 抛出异常，当前批的执行结果未知，reader 隔离后续事件并保留数组。恢复必须重建 reader 与可能持有旧 bar 指针的宿主 sink，并依据事实 owner 已确认的状态恢复业务；自动重放可能已执行的当前事件会重复业务效果。

原 [WtDtMgr 析构](../../src/WtCore/WtDtMgr.cpp) 释放自身缓存，但当前未调用插件 `deleteDataReader`。因此受管宿主须明确拥有停止和插件销毁链；直接运行原宿主至进程退出，只能证明进程结束。宿主已持有的 callback/slice 和 DLL 卸载次序仍需单独验证。

## 验证边界

验证入口包括 服务测试（外部历史/待归仓路径：`../../tests/integration/reader_service/test_reader_service.py`）、原生 Store 链（外部历史/待归仓路径：`../../tests/integration/reader_service/test_native_chain.py`） 与 原 WtDtMgr/CTA 宿主链（外部历史/待归仓路径：`../../tests/integration/reader_host_flow.py`）。测试来源是隔离样本，源码中的测试入口与具体环境通过结论分别登记。

当前保守运行配置采用 `engine.poolsize=0`。[整链验收](../evidence/2026-10-21-native-history-reader.md)记录poolsize=0和2的单上下文隔离测试；多个策略并行修改原宿主订阅容器须独立验收。生产日历、服务发现、真实来源资格、发布切换和业务恢复仍按各自正式验收执行。本模块文档不表示部署完成。
