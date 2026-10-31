# 观衡托管的跨夜原生行情采集

类型：运行证据。状态：真实已启动并连接；跨日分钟/收盘归档验收进行中。日期：2026-10-29。依据[QST6.1](../specs/qmt-quote-stream.md#qst61-应用托管与独立进程)、[采集模块](../modules/qmt-quote-stream.md)和[操作手册](../runbooks/qmt-data-collection.md)。

## 目标与实际调用链

保持已运行的GH_WT_MEMORY_VERIFY、当前认证配对和源端无文件/网络方式，使用普通观衡安装托管一个连续运行的采集实例，验证盘后等待、次日自动接收及WT原时段收盘归档。该实例使用独立新数据目录，原历史、今日归档和其他策略保持。没有增加定时任务；原StateMonitor继续管理时段，外层截止只限定本次开发观察。

统一候选为build/native-quote-parser-v6-scope-001/unified/relocated-001，总manifest 228cd7f9021a7396252253f733e03be44106b820cc67235a6cbe9878f0113919。普通App解释器来自build/qmt-full-app-real-history-001/runtime，实际guanheng_app从其site-packages加载；通过原create_app/lifespan启动QuoteCollectionProcess。子服务入口取统一候选history组件，原生DataKit/StorageLifecycle/Helper取collection组件，没有拼接不同原生依赖。配对从当前private deployment复制到新受控配置，秘密只在外部环境注入。

新工作根为build/qmt-overnight-collection-001，PREPARED绑定连接/基础资料/子配置/原生和解释器SHA。Writer根为该目录storage；allday=false、async=false、WtDataStorageLifecycle、archive_session=null，原SD0930 StateMonitor配置为09:15初始化、15:01关闭、15:05收盘处理。当前6982证券清单的资料日期为10月29日，上市变更及新证券仍需后续刷新清单验收。

## 本次已观察

18:55:29+08:00普通App实际启动，父PID18812、采集PID50208；18:55:35首次观察连接。外层为build/guanheng-workspace/qmt-overnight-app-control-357，原Job从进程创建前纳管、无控制台，沿已验当天完整规模使用相同2GiB外层开发观察额度。计划在10月30日收盘处理后、15:20左右收尾，原硬截止及PID/控制身份见RUNNING.json；尚未到达关闭验收。

19:01状态：同代连接true，收到6929条有效快照/35批，subscribed6982；source heartbeat latest_symbols6929、missing53、queue_depth0、overflows0，组件error和cleanup failure为空。rejected_ticks包含清单外/无效源值，沿[覆盖口径](../modules/qmt-quote-stream.md#心跳计数与证券覆盖)解释。receiver_failure保留connection_ended的历史诊断，而当前connected为true；原Receiver继续清理/等待，未另建Writer。

当前盘后原StateMonitor不将快照写成交易分钟，因此writer_processed=0；本轮没有据此声称已取得次日分钟或完整行情。普通GET /v1/ui/qmt-collection实际200，启动失败false，状态ready只表示外部listener已托管；认证连接和快照由上述子状态另证。父/采集PID已通过系统进程读取核存活，App和采集占用为几十MiB量级的盘后观察，盘中规模另核。

## 下一验收与停止

继续核10月30日实际交易时段的来源时钟、证券覆盖、队列、原生处理、三证券分钟及自然收盘DSB回读。只凭持续进程或有效快照数不授全天完整。已有回测/实时策略、统一App发行和全系统M3/M4保持进行中。

正常停止由原App寿命负责：先Receiver收束，再原生归档及关闭，最后确认进程树、EOF、读线程和Job回收。本次开发观察支持在WORK新建STOP.REQUEST请求原driver正常退出；操作前核RUNNING和实际PID。该标记只属于本次观察，不是产品业务门槛。停止后从RESULT.json、外层result和原Helper实际文件核结果。进程丢失或读取异常先核原handle/作业状态，不因观察超时启动第二个Writer。

本次准备356正常exit0且完整回收；长期作业357当前进行中。未操作QMT界面、未修改策略正文、未真实委托/撤单或切生产。另一个真实前复权读取任务仍等待QMT原运行确认，现场见build/qmt-native-adjustment-001/NEXT.json；该等待不妨碍本次已运行GH来源采集。
