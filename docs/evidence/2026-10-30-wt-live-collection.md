# WT独立入口恢复真实行情采集

类型：现场开发运行记录。状态：ongoing。范围：WRI独立数据运行入口与实际QMT/原Writer组合；完整策略执行、观衡隔离及开盘分钟落盘继续验证。

## 触发和实际变化

现场核实原跨夜实例PID18812/50208均已不存在，`build/qmt-overnight-collection-001/LIVE.json`最后观察在2026-10-30 00:13。旧根没有可用终态收据，退出原因尚未确认；保留其全部数据和原件。操作系统及QMT仍为原启动实例，本记录不把退出归因于WT框架。

使用已完成独立审查的WT数据运行包，从普通安装原CLI启动新的采集开发实例。WT进程负责采集子进程及原生DataKit/Writer，观衡服务不参与。新数据根为`build/wt-live-collection-001/storage`，旧storage保持原样。QMT、其他策略、正在进行的历史下载及交易配置均未变更。

## 固定输入与启动

- WT普通安装：`build/wt-independent-runtime-001/installed`，环境仅`guanheng-wt-runtime`和`guanheng-market-client`。完整59文件及外部CPython身份由`INSTALLED-001.json`绑定，SHA256为`0dad7d8f8c34050587b4fb3b7f9d59187c3b689ca193729a6cfd96ed98190148`。启动前逐文件核对，观衡及FastAPI包均不存在。
- 原采集worker、6982证券QST连接及凭据沿旧实例材料复制到新受保护目录，凭据只注入进程环境；原QMT映射和报价源保持。原`WtDataStorageLifecycle`显式选择和同步Writer配置保持，新配置仅绑定新实例路径和数据根。
- 子采集解释器来自已安装HPR独立角色，入口为原行情包中的`quote_collection_service.py`。该进程运行原DataKit/Writer，既有已批准框架覆盖保持。
- `prepare.py`在QMT外准备配置；control397实际2.328秒exit0、创建期隐藏Job、整树/EOF/join/句柄正常关闭，来源调用和采集启动均为0。
- `launch.py`校验完整安装与实例材料后执行原安装模块CLI。该现场开发实例常驻运行，进程和控制身份在`STARTED.json`及原ready/status中记录；不设60秒来源启动窗口。正常停止沿本实例原stop身份，由WT归约组件关闭结果。

## 实际首轮观察

`build/wt-live-collection-001/FIRST-OBSERVATION.json`记录WT实际PID6536、collector实际PID28804，状态均ready，原collector状态为running/connected。已接收600条真实QMT报价、3批，原生delivered=600、subscribed=6982，error和receiver_failure均为null。

当前为闭市时段，原交易时段配置下writer_processed=0；该观察证明真实接入和原生投递，不授次日一分钟落盘或归档完整性。采集进程持续运行，后续检查实际状态、开盘分钟和原归档，保留来源时点、接收时点与本次观察时间。

本轮真实下单/撤单0、账户读写0、生产切换false，WT核心新增修改0。ETF/50指数补齐由《杂役》会话独立处理，已通知保护新采集实例并在原GH切换时保持QST映射和凭据。

## 剩余

主进程常驻与真实来源已连接，开盘后分钟写入、全天归档及新数据根公开查询待核。B完整执行入口仍需加入独立WT组合，C真实观衡停止/重启隔离还需实际消费者验证。完整WRI和系统目标保持进行中。

## 后继来源重连观察

CONTINUITY-002.json记录同一WT PID6536、collector PID28804及相同控制身份仍运行。期间ETF准备会话沿原GH策略更新HPR参数并重启来源，采集状态已到generation2、累计实际投递13858报价/71批；第二代来源心跳显示6929有效证券、53缺失、溢出0。来源重连保留原运行进程；receiver_failure=connection_ended是已结束连接的历史诊断，当前collection.error=null，最近连接状态为connected。该快照与实际进程存活一起使用，不把状态文件单独作为存活证明。

本次仍为闭市，行情日期为10/29，Writer处理0；新交易时段的分钟落盘继续观察，未因来源重启重做已通过的单日采集验收。来源覆盖53缺失及全日连续性保持相应边界。

## 闭市内部时间不推进的核查

历史下载会话报告接收计数及collection.observed_wall_time未更新后，根核同一实际进程和generation2的两次状态：receiver_heartbeats增加16，报价增量0，connected=true、collection.error与receiver_cleanup_failure均null。原件IDLE-HEARTBEAT-003.json。源码_on_batch仅在接收报价批次时更新内层observed_wall_time；Receiver每收到认证心跳独立累加heartbeats。旧connection_ended没有在下一代成功连接时清零，表示已发生的连接结束，不单独证明当前掉线。闭市无新报价符合此次观察；保留原实例，不以静止批次时刻重启。开盘报价及落盘仍依实际数据验证。
