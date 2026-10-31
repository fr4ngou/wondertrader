# 多批来源历史统一证券查询

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证记录。日期：2026-10-27。状态：多批原生文件→单一HTTP/SDK→观衡分钟接口主路径通过；整库导入、统一配置最终发布和生产切换继续。要求见[RS9](../specs/qmt-source-history.md#rs9-多批来源历史的统一证券查询)。

## 根因与实现

原NativeSourceMarket固定一个root和同一批次source，无法由一个入口消费全库存导入产生的多批原生文件。新增显式source-stores，启动按各原成功收据登记唯一证券，按证券路由原NativeHistory.read_source_store；一个Reader、一个按实际bar总数计费的LRU归创建线程拥有。原DSB、sidecar、收据和原始session保持。能力页标识明确的离线收据集合，数据响应继续提供原批次source。

仅新模式允许1MiB配置，原单根和native模式保持64KiB与原分流。多根限制1024、累计收据16MiB、全局证券10000；重复根/证券拒绝，不按顺序覆盖。跨provider/instance分开配置。空preload按需加载，实例创建时清单冻结，新增批次使用新受管实例；无新数据库或持久价格索引。

实现限于自有source_market.py/market_service.py及测试。WT核心、原生DLL、QMT策略和活动生产配置保持。

## 实际主路径

使用正在导入任务中已完成且不再写入的两个批次：002/batches/batch-0000/store与003/batches/resume-003-batch-0000/store，证券000001.SZ及002027.SZ，来源session不同。固定NativeBarFile SHA=4f5e2696559011d755edfac1d58296626fdedb6ba46c6d6a0fafc0203eebe62c。启动单一loopback服务，SDK交替查询000001、002027、000001，每次两根。时间/OHLC/volume/amount与原收据绑定CSV尾部逐字段相等；每条metadata.source保持对应原session，能力集合会话独立。首次两只实际核查各约3—4秒，再次缓存命中；计时含CSV身份及尾行对照，不能作为纯网络延时基准。

之后使用本仓库create_app及真实SDK，通过ASGI TestClient调用/v1/ui/market/chart/000001.SZ和002027.SZ：各返回schema1.5、两根、data_available=true、unknown量额、source_label，尾部2026-10-21T07:00:00Z对应原上海15:00，未平移一分钟。该步使用前序已加载缓存及显式5秒预算，不证明默认2秒冷加载全市场均可完成。App.shutdown_complete、reader线程0；服务及原Reader在owner线程关闭。此为真实HTTP后端+应用HTTP入口开发验收，本轮未重新做浏览器及安装包验收。

第一次应用探针缺本仓库独立strategy_core包源路径而失败；补齐本仓库各策略包路径后重试通过，保留原失败和清理证据。没有导入旧QMT项目。

物料：SDK实际双批（外部历史/待归仓路径：`../../build/qmt-source-stores-001/REAL-HTTP-SDK.json`）、观衡实际双证券（外部历史/待归仓路径：`../../build/qmt-source-stores-001/REAL-HTTP-APP.json`）、独立full审查（外部历史/待归仓路径：`../../build/qmt-source-stores-001/REVIEW.md`）。配置模板及冻结实例步骤见[手册](../runbooks/market-service.md#同一服务读取多个成功批次)。

## 兼容、边界与剩余

新增8项通过：来源路由/缓存、集合身份排序稳定及收据变化、旧单根、重复根/证券、错误SHA/跨实例、LRU逐出、超容量/关闭、仅新模式放宽配置。既有服务16项中15通过、1缺GH_MARKET_LIBRARY/GH_QMT_SOURCE_ROOT的旧Gateway资格skip；不为此执行旧QMT工程。当前真实source整链另有上述两组证据。独立full静态complete，无实质gap；实际源码SHA匹配受审身份。

完整回读与来源质量继续由原NativeHistory负责；未改Importer/Reader或已运行导入任务的六份冻结源码。所有短进程整树/EOF/join/资源核验见收尾（外部历史/待归仓路径：`../../build/qmt-source-stores-001/POSTFLIGHT.json`）。全库存长作业仍运行，其最终资格另见[导入记录](2026-10-27-qmt-full-history-running.md)。

剩余为全库存结束后的配置生成/全清单注册、尾部补齐、来源单位/分钟边界与标准策略资格、完整恢复/真实连续来源及独立发行。冷读仍按整只证券校验，预算依实际历史长度和缓存设置；本轮不授全市场冷读延时保证。未真实下撤单、未启停QMT策略、未切生产，当前无用户必需操作或待批准项。
