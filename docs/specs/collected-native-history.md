# 采集归档进入统一历史查询

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：功能最终规格。状态：accepted。前缀CNH。范围：三会话计划A-03/A-04/A-06的原生采集归档→统一SDK/App，复用WT-D03/D05/D06；不修改WT框架、分钟算法或采集owner。

## CNH-R1 单一数据链

现有source-store(s)/source-catalog只读成功导入收据；新采集DSB由原Writer归档，独立配置source-collected显式绑定同一storage根、来源声明和证券清单。适配器按请求读取his/min1的原文件，不生成假QMT导入收据，不重写/复制另一套全量行情库，不添加定时任务或服务。统一来源服务及App原owner继续拥有生命周期；既有配置默认行为保持。当前模块提供已归档闭合分钟，盘中DMB/闭合订阅沿原NMR，不借归档查询声称盘中完整。

## CNH-R2 来源与读取

配置固定base（原source-store(s)/catalog）、collection（storage_root、source身份、source_license、价/量/额单位、symbols）、native_reader及有限max_bars/max_file_bytes/响应预算。来源身份明确为采集数据集身份，不能冒充逐tick原会话；dataset_version标明WT分钟聚合及文件SHA。price/volume/amount单位独立保留unknown，分钟标签沿WT右端，真实源快照与原厂分钟一致性分别核。

每次读取同一原DSB内容身份，调用原NativeHistory/文件ABI/Helper；成功必须完整回调、标签排序唯一和数值有效，文件变化/正在归档时返回明确不可用。新增显式read_source_file入口允许未知预期条数，以原ABI实际条数及既有max_bars限制；原导入收据继续要求精确count。缓存不冻结旧文件：每次按当前内容身份读取，新文件或追加归档无需重启服务。允许符号最多10000，单文件/行数/响应沿已有上界。

## CNH-R3 合并与接口

现有分钟action/SDK/字段不变。归档与base使用原select_sources保留原metadata与分段provenance，取请求范围最近N根；同分钟异值明确冲突，不按顺序覆盖。日线和其他未支持动作沿base，不从不完整分钟合成日线。源文件不存在时保留base实际范围；存在但读取失败时明确Unavailable，不能伪称已更新。coverage维持Unknown，缺文件/稀疏不能补0。可作为source-preparing的本地base，网络补齐及未知任务仍归原owner。

## CNH-R4 验收

先以已有真实DSB及新独立配置→原Reader→SDK/HTTP完整主路，验证base旧段/采集新段/原字段精确/重复读取不变、同实例新归档可见及正常关闭；然后消费137在自然15:05产生的三证券归档，条数/标签/六字段与原Helper一致。主链后补无文件/形成中/修订/重复冲突/容量/配置/旧模式兼容并独立审查。普通安装和最终发行单独验证，当前未授实盘或生产切换。

## CNH-R5 独立导入的补齐来源

`source-collected` 可显式提供 `supplements` 列表，每项沿原 `source-store`、`source-stores` 或 `source-catalog` 完整配置和成功导入收据准入；省略及空列表保持原行为。此列表描述独立原生数据来源，原 base 的证券注册和历史范围保持。补齐记录使用原 Importer 写入新根，原归档及已存在分钟保持原字节。

分钟查询按归档、base、补齐来源的顺序调用原 `select_sources`，取范围内最近 N 根。同分钟原值相同去重，原值不同沿原 Unavailable，禁止顺序覆盖。每段原来源身份、标签、单位和 content_id 进入原 provenance；`unknown` 保持原值。未登记该证券的补齐来源跳过，已登记来源读取失败明确返回不可用。缺口来源可在采集文件尚不存在时单独返回真实已有数据。日线和其他动作继续原 base。

创建线程拥有各原 NativeSourceMarket/Reader，构造中途失败关闭此前已创建资源；正常关闭逆序释放全部 owner。SDK、HTTP、来源协议和 WT 框架保持。本地补齐来源不伪造 `source-preparing` 的在线先读/补充/后读收据，也不更改在线来源日期权限。

验收覆盖真实导出缺口→原生新根→原公开查询240标签、原239根逐值/SHA保持；另核默认、空列表、同值重叠、异值冲突、未登记证券、缺归档、partial构造释放及普通组件消费者。

实现入口为采集归档适配器（外部历史/待归仓路径：`../../integrations/guanheng/collected_history.py`），接口复用来源服务（外部历史/待归仓路径：`../../integrations/guanheng/source_market_service.py`）及[原生历史](../../integrations/guanheng/native_history.py)。

## CNH-R6 原生日线持续落盘与指数动态尾部

沿WT-D03/D05/D06复用原DataKit、同步Writer、StateMonitor、DMB/DSB及`DailyOverlayMarket`。日线持续归档显式配置`writer.disableday=false`；同一数据根保持唯一Writer。常用指数集合由`config/market-collection-indices.json`维护，新增订阅合并到原QST集合，源端与接收端同步使用同一symbols及profile摘要。原股票、ETF、运输身份、队列预算、原值乘数和历史资料保持；指数品种标为IDX/category=90、禁止交易。完整GH源端正文由原源端所有者合并，QST配置增量不能替换其它通信路由。

统一历史在原50指数静态归档外层显式启用`snapshots`，其symbols只含50指数；股票/ETF内层读取配置保持。每次查询按原收盘marker选择闭合日线，优先读取`his/day`中严格晚于静态归档末日的记录，缺日沿原有界快照读取。原生day历史不受64份快照扫描窗口限制。动态DSB在E盘私有临时副本解码，不取得Writer原文件写入权；文件变化返回明确Unavailable。一次配置切换后新增闭合日线按请求可见，后续每日运行沿原生命周期，无需每日打包或重启读取服务。

固定归档的逐段来源、Mixed及原数量保持；动态尾部标明QMT累计快照派生来源，价格/量/额单位沿实际资格声明unknown。Tencent兼容金额0保留原来源，不能转称真实成交额。当天未闭合数据、缺失交易日与来源覆盖保持明确范围。

验收：原固定制品加载原6982+50订阅并正常关闭；全部50原归档解码；使用真实历史原值，在同一Reader及运行中的隔离Writer下发布闭合日线后直接读到新增日期，逐值及Mixed分段保持；原股票/ETF配置保持，源端profile联合准入。自然开市50指数回调、当日收盘Writer落盘及后继日持续读取由现场所有者接收，隔离文件可见性证据分别标识。实施及命令见[持续日线手册](../runbooks/continuous-native-day.md)。
