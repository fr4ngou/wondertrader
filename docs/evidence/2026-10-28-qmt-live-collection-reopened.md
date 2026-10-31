# 2026-10-28 QMT重启后只读采集恢复

类型：现场证据。状态：真实全推接收/原始记录已恢复；WT连续分钟、完整覆盖及收盘关闭待验。

## 实际操作和输入

用户重新打开并登录国信QMT后，当前版本仍为3.12:1.2.26.150。GH_WT_MEMORY_VERIFY已从原停止中恢复为可启动；本次仅点击该行运行，其他两个已有运行策略保持现状。正文SHA b91ada8d10f8c60a9ea0ed1f75c1dd7ca585d7505445569374ff28395cb5c7f2，与已登记全推正文逐字相同；未新增策略、未修改QMT正文或WT框架、未下撤单。

终端外接收采用现有QuoteStreamReceiver、原私有SHM配对和6982证券清单；策略内仍为内存正文及内建mmap。终端外隔离捕获文件记录原八字段与snapshot/incremental种类，供原NativeDataKitSession消费，未实现另一分钟聚合。此记录属于本次开发观察，尚未登记为正式发行/长期架构。

## 当前结果

接收STATUS在2026-10-28T04:07:38.313264+00:00记录：generation=1、connected=true、unique_symbols=6922、ticks=7030、bytes=1061841；源心跳queue_depth=0、overflows=0、missing_symbols=60。文件存在且批次记录增加。60缺失成员的停牌、无报价或校验拒绝原因尚未逐一核实；不能据此声明6982完整覆盖。

原始记录位于build/qmt-live-quote-capture-20261028-001，受控根qmt-live-quote-capture-20261028-main-002；首个启动因选用了不含FastAPI的Python而失败，终态及整树回收已保留，第二次选择已有项目依赖环境，无安装或运行包变更。

另以固定未修改原WtDataStorage启动原生消费，材料build/qmt-native-live-20261028-001，受控根qmt-native-live-20261028-main-001。当前已确认原入口create和至少200条processed；尚未确认分钟DMB，不能以接收条数推断分钟完成。午休时收到的来源时间、节外记录的原生处理和下午完整分钟分别验。首个累计快照/中途启动不授完整分钟量额，仍保持raw source units标签。

## 生命周期和未覆盖

两进程均通过隐藏、创建期Windows Job的既有受控入口运行，无计划任务。接收总预算12600秒，原生消费12300秒，均于当天收盘后结束；这是当日有限观察，不代表登录自启或下一交易日常驻已交付。接收8GiB容量上限，达到则停止并保留失败。

WT默认Writer已证实的关闭后台线程问题仍未修改；原生消费运行、归档marker、close返回和全部线程退出分别登记。候选数据不进入正式历史目录或交易路径。下午完整分钟、源时间/量额单位、缺失60证券、收盘DSB回读/关闭和上午缺口仍未完成。

## 午间后继覆盖检查

从实际已写入批次求清单差集：6922已接纳、60缺失，缺失由7只股票及53只ETF组成，逐成员清单存build/qmt-live-quote-capture-20261028-001/MISSING-OBSERVATION.json。缺失原因尚未判定，不统一标记停牌或无成交。原生消费已观测到7158条processed；尚无分钟DMB，不把计数当作已产出分钟。后继只读两代试验期间，全推仍connected/queue_depth0/overflow0，独立采集进程保持。
