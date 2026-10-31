# QMT 持续行情插件

类型：模块说明。范围：原生 ParserQMT 的只读 HTTP 快照接入、订阅和线程生命周期。行为要求见[最终规格](../specs/qmt-native-parser.md)；运行资格依对应验证记录。

显式 `ParserQMTHostV6` 复用同一线程/SPI/去重实现，选择新 FullTickV6 客户端并完整核验来源 v6 组合能力；实际请求固定 full_tick。默认旧 ParserQMTHost 保持 Legacy；版本与安装验收见 [v6 最终规格](../specs/qmt-native-parser-v6.md)。

## 职责与接口

标准 `createParser` 返回自有 QmtPollingParser，实现原 `IParserApi`；`init` 读取配置，`connect` 接受启动请求，`isConnected` 表示端点已完成准备与连接。`stopParser(api, timeout_ms)` 是自有的有界停止确认接口，标准 `disconnect/release` 保留。`deleteParser` 只有确认停止才销毁并清空引用，超时继续保留对象及其依赖。

插件通过原签名 HTTP 客户端读取健康、能力和 `market.full_tick`，负责将合格快照送到宿主 SPI。时间、量额和累计口径沿版本化 QmtHttpProfile 投影。历史查询、下载、分钟补齐和账户执行各有独立入口；持续快照本身不证明一分钟历史完整。

## 线程与资源

一个 worker 拥有 QmtHttpClient、QmtHttpEndpoint、MarketParser 及其完整生命周期。控制线程只在短锁内交换订阅目标、版本和停止请求；网络、端点调用及 SPI 回调均在控制锁外进行。订阅目标集合和整个实例曾接收的证券水位都受容量限制。

快照去重位于本插件的端点装饰层。同来源、同证券、同时间、同字段的已接受快照表示没有新行情，跳过投递。相同时间数据冲突及倒序触发隔离；原始来源身份与数据准入仍由原端点和通用 MarketParser 负责。宿主回调失败意味着效果未知，插件停止并由外部管理者核查。

SPI 回调可以查询状态、改变订阅或请求停止。回调内停止只登记请求；外部线程继续调用停止接口，等待 worker 清理和 join 完成。宿主保持 SPI、对象、DLL 及所有被 retain 的 tick 所需代码有效至相关对象释放。宿主跨线程消费 tick 时遵循原 retain/release 所有权。

投递给宿主的 tick 使用自有堆分配派生对象，沿原WTSObject引用计数释放，允许宿主缓存跨越worker退出。通用MarketParser的线程局部池对象仅在worker内部借用。HTTP的系统回调同样属于依赖：worker在最后回调完成前持续持有客户端，外部stop超时保持依赖，确认排空后才报告停止成功。

每实例仅启动一次。连接期间重复 connect 是同一次请求，停止、准备失败或运行故障后由外部管理者创建新实例。重建必须重新核实宿主、来源和策略状态；插件不自行改变来源身份或重试未知业务效果。

## 宿主接线

显式v6宿主将Host进程就绪与认证共享内存连接就绪分别观察；在同一次启动预算内先取得read-binding，再启动单次插件连接。该GET不派发证券SDK读取，具体操作沿[启动手册](../runbooks/qmt-polling-parser.md#启动观察和停止)。

原 ParserAdapter 负责工厂加载、基础合约匹配和标准代码转换。自有宿主应先完成策略及依赖初始化，再准入行情；退出时先停止插件并确认完成，再释放原 adapter、策略、数据和模块。

原 WtRunner 的启动顺序、ticker 调度、停止入口具有独立边界，见[运行器复核](../migration/native-runner-boundary.md)。ParserAdapter 的 init/run 返回值不等于源已经可用；插件正常停止也不等于整个引擎线程都已停止。正式运行验收需覆盖真实宿主的完整生命周期。

操作及配置见[插件手册](../runbooks/qmt-polling-parser.md)。

内层断开先关闭准入并保留原因；对外Close在HTTP回调排空后统一发布。Close回调仍发生于worker内，管理线程以stop成功确认join，再按持有对象的释放顺序卸载模块。
