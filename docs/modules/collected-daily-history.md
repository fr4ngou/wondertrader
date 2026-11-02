# WT闭合日线读取

类型：模块接口正文。范围：WT数据侧读取原日线、收盘快照与既有历史；观衡继续只读消费。源码入口为`integrations/guanheng/daily_overlay.py`，图表接口沿[来源日线规格](../specs/source-daily-chart.md)。

## 职责与数据流

原WtDataWriter拥有收盘调度、`his/day`、`his/snapshot`和`marker.ini`。本适配读取其稳定输出，经原WtDtHelper/NativeHistory解码，与base历史按交易日期组合；每次后继请求检查已有输出。它不下载、不改Writer目录、不新增定时任务，App不构造日K。

原生日线对同日期优先；原快照可补当前尾部及缺日。文件自然日仅用于定位，业务日期采用CSV自身交易日；marker会话确认闭合。相同日期相同值去重，冲突或变化中/损坏输入明确不可用。原历史数值保持，范围和根数沿原请求选择；空missing_dates及coverage=Unknown分别保留其语义。

## 配置与来源身份

显式选择`mode=source-daily-overlay`，`base`沿原读取配置。`native_reader`声明原库及SHA，`snapshots`声明Writer存储根、临时副本根、原会话和证券标识映射，以及来源、许可和价量额单位。证券集合对应实际采集标识。`max_file_bytes`和`max_bars`沿有界读取资源契约，关闭由原服务owner持有。

当前已验路径为`archive=None,response_shape=dataset`：仅组合QMT来源，供原SDK读取显式派生日线批次。身份使用`wt-daily-derived-dataset`及`daily-selection:<SHA>`，版本为`wt-native-daily-derived.v1:<SHA>`；摘要绑定原值及逐段来源。该身份表示本读取侧组合结果，原DAT、原快照和实时运输会话各自保留原身份。价格、成交量、成交额保持来源声明，unknown单位继续unknown。

`segments`和公开来源archive的代码与后继验收分别管理，当前先行配置未启用公开来源。原未选择该mode的来源保持原路径，分钟查询继续base；周/月由既有图表投影按实际日线聚合。

日线日期仍是上海来源日期标签，以UTC传输；图表as_of表示该标签。闭合证据和实际可获知时点按各自契约核实，图表日期不授予策略在当日开盘已知收盘价的资格。

## 生命周期与已验范围

同一服务调用线程拥有base和原Reader；原件在有界读取前后复核，临时副本在原ABI读取结束后释放，服务close沿原owner归还两类读取资源。WT通过原SourceMarketProcess管理服务，观衡只配置只读URL及凭据。

已核300308和588170：静态历史保持，11月2日快照经原Helper/DSB完整回读，原a89安装HTTP日/周/月消费通过；当前页面及日/分钟末价一致。完整部署、制品与范围沿[日线交付](../releases/2026-11-02-wt-collected-daily-tail.md)。

先行快照读取仍有扫描窗口；现行Writer缺少原生日线文件的原因、原生日线持续落盘及长窗口完整性继续核实，不能据本次尾部成功宣称长期全量日线已完成。指数多年商店、公开来源和8表背景接收单独交付。
