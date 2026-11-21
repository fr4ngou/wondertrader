# WT日线与形成中当日K线读取

类型：模块接口正文。范围：WT数据侧读取原日线、收盘快照与既有历史；观衡继续只读消费。源码入口为`integrations/guanheng/daily_overlay.py`，图表接口沿[来源日线规格](../specs/source-daily-chart.md)。

## 职责与数据流

原WtDataWriter拥有收盘调度、`his/day`、`his/snapshot`和`marker.ini`。本适配读取其稳定输出，经原WtDtHelper/NativeHistory解码，与base历史按交易日期组合；每次后继请求检查已有输出。它不下载、不改Writer目录、不新增定时任务，App不构造日K。

原生日线对同日期优先；原快照可补当前尾部及缺日。文件自然日仅用于定位，业务日期采用CSV自身交易日；marker会话确认闭合。相同日期相同值去重，冲突或变化中/损坏输入明确不可用。原历史数值保持，范围和根数沿原请求选择；空missing_dates及coverage=Unknown分别保留其语义。

base 返回组合日线时，逐根日线沿 `provenance` 的 offset/count 绑定其原分段来源；整批 `SourceSelection` 只表示汇总身份。上层再次合并、限量截取及追加 Writer 尾部均保留原来源，最后按所选响应形态生成结果。回归入口为 `tests/integration/daily_security/test_daily_overlay_provenance.py`。

## 配置与来源身份

显式选择`mode=source-daily-overlay`，`base`沿原读取配置。`native_reader`声明原库及SHA，`snapshots`声明Writer存储根、临时副本根、原会话和证券标识映射，以及来源、许可和价量额单位。证券集合对应实际采集标识。`max_file_bytes`和`max_bars`沿有界读取资源契约，关闭由原服务owner持有。

当前已验路径为`archive=None,response_shape=dataset`：仅组合QMT来源，供原SDK读取显式派生日线批次。身份使用`wt-daily-derived-dataset`及`daily-selection:<SHA>`，版本为`wt-native-daily-derived.v1:<SHA>`；摘要绑定原值及逐段来源。该身份表示本读取侧组合结果，原DAT、原快照和实时运输会话各自保留原身份。价格、成交量、成交额保持来源声明，unknown单位继续unknown。

`segments`和公开来源archive的代码与后继验收分别管理，当前先行配置未启用公开来源。原未选择该mode的来源保持原路径，分钟查询继续base；周/月由既有图表投影按实际日线聚合。

日线日期仍是上海来源日期标签，以UTC传输；图表as_of表示该标签。闭合证据和实际可获知时点按各自契约核实，图表日期不授予策略在当日开盘已知收盘价的资格。

## 生命周期与已验范围

同一服务调用线程拥有base和原Reader；原件在有界读取前后复核，临时副本在原ABI读取结束后释放，服务close沿原owner归还两类读取资源。WT通过原SourceMarketProcess管理服务，观衡只配置只读URL及凭据。

已核300308和588170：静态历史保持，11月2日快照经原Helper/DSB完整回读，原a89安装HTTP日/周/月消费通过；当前页面及日/分钟末价一致。完整部署、制品与范围沿[日线交付](../releases/2026-11-02-wt-collected-daily-tail.md)。

上述2026-11-02先行快照读取保留其当时扫描窗口。持续收盘归档沿[原生日线采集手册](../runbooks/continuous-native-day.md)选择disableday=false后，由原StateMonitor/Writer生成day文件；长期全量覆盖依实际逐证券回读核实。指数多年商店、公开来源和背景指标接收分别登记。

## 形成中日K的显式读取

`integrations/guanheng/current_day.py`沿[SDC-R1](../specs/source-daily-chart.md#sdc-r1-盘中日k与闭合日线分离)组合当前值。采集侧DataKit自有导出调用原`DataManager::getCurTick`取得独立tick副本，读取原Writer当日OHLC及累计量额，立即释放副本；同步采集与关闭继续归原Session。启用worker的`publish_current_day=true`后，在原状态周期向唯一Writer数据根原子替换`current-day.json`。文件总量8MiB/10000证券，失败保留旧文件并回收本次临时文件，当前值和旁路诊断失败均不停止原采集。

WT查询配置`mode=source-current-day`、`base=<原读取配置>`、`current_day={path,source_license,price_unit,volume_unit,amount_unit}`。创建线程拥有base及全部Reader；HTTP批次复用原base版本域并固定一次当前值快照，批次结束释放正文。SDK0.18的日线`view=current`显式读取当日形成中行，缺省/归档保持原路径；固定snapshot_id与current互斥。原归档同日值优先，快照旧日保持旧日，尚无该证券历史时可单独返回已实际收到的当前行。

`current_day`响应字段分别保留原交易日、原tick发生时刻、WT读取时刻与closed=false；许可和价量额单位沿真实采集声明，unknown继续unknown。App请求和投影SDK结果，日/周/月沿既有图表聚合；来源时刻和未归档资格保留在native_source，策略默认闭合窗口保持原调用。

已取得真实股票300308、ETF588170、上证000001的只读QMT快照，经隔离原Writer、SDK HTTP和App日/周/月逐字段回读；这是隔离整链证据，正式进程采用另行登记。原生依据为[能力目录WT-D08](../development/wondertrader-capabilities.md)及Writer公开当前tick/收盘日线接口，没有新增WT框架差异。

正式采集、WT查询和独立观衡的形成中链现已采用，实际数据及原时刻见[线上增量记录](../releases/2026-11-05-current-day-and-hpr-live.md)。此资格与全范围闭合日线、完整收盘分钟分别核实。
