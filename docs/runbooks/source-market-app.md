# WT管理历史查询服务

类型：运行手册。适用范围：独立WT运行单元中的原生历史查询服务，以及独立观衡的查询连接。当前职责以[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)和[WRI](../specs/independent-wt-runtime.md)为准；各发行实际运行资格沿对应证据核实。

## 安装与数据配置

WT发行负责安装原历史组件及运行依赖，原历史数据保留在外部数据目录。观衡分别安装Web包与SPA。更新程序、替换数据源和启动运行实例分别操作，按各原清单核对摘要及来源。

1. 准备source-store/source-stores配置；同时查询分钟与日线时使用[DSH4](../specs/qmt-source-daily-history.md#dsh4-统一公开查询与目录)的source-catalog，登记原分钟及日线收据。native_reader.library及sha256绑定本次安装原Reader；store_root和import_receipt_sha256保持实际数据身份。
2. 需要读取采集归档时，使用source-collected，base绑定原历史配置，collection按[采集归档模块](../modules/collected-native-history.md)声明storage_root、证券集合、数据集与单位。原Writer新生成的DSB按请求可见，盘中DMB及订阅沿原NMR能力。源单位、覆盖及来源分钟边界保持原语义。
3. 准备guanheng.source-market-service.v1子配置，source_configuration.path/sha256绑定数据配置；listen指定实际数字回环地址与端口，token_env保存凭据环境变量名，socket_timeout沿[SMP](../specs/native-source-market-process.md)设置。令牌值由WT受管环境注入，配置及命令行仅保存变量名。
4. 准备guanheng.source-market-process.v1部署描述，绑定pythonw、entry、configuration的绝对路径及SHA256，并设置独立control_root、启动/停止和输出预算。entry为已安装组件内integrations/guanheng/source_market_service.py。
5. 在WT实例components.history中配置kind=source_market、descriptor及原字节sha256，按[独立WT手册](wt-independent-runtime.md)启动。所有已声明组件完成构造验证后依序启动；缺失安装或配置错误按WT入口明确报告。

WT进程持有SourceMarketProcess并负责其完整生命周期。历史服务监听就绪后，使用公开SDK查询实际证券、日期和根数，核验返回数据与来源，而后接入观察页面。

## 观衡只读连接

观衡仅配置GUANHENG_MARKET_URL、GUANHENG_MARKET_TOKEN、GUANHENG_HISTORY_SEMANTICS=source；URL对应WT历史服务的实际监听。GUANHENG_MARKET_TIMEOUT_SECONDS按首次读取实测设置，沿当前settings支持范围。首次读取某证券可能解码整份历史。

WT运行观察由GUANHENG_WT_STATUS_FILE、GUANHENG_WT_CONTROL_ID、GUANHENG_WT_INSTANCE_ID和GUANHENG_WT_CONFIGURATION_SHA256定位；具体配置见[独立WT手册](wt-independent-runtime.md)。观衡读取这些公开状态，不构造历史服务或发送停止命令。旧GUANHENG_SOURCE_MARKET_CONFIG等App进程托管配置已退出当前入口。

打开行情页输入证券代码，选择分钟线或日线并读取。分钟图使用来源时间，日线按上海交易日期显示；最后来源日期、查询根数和本次观察时间分别说明。历史范围不足时保留来源返回的范围与缺口。相同查询刷新失败时沿原页面缓存保留已有成功结果及其时间，首次失败和成功空结果各自展示；部分缺失只影响对应查询。

## 观察、停止和恢复

WT ready表示基础进程初始化与监听，不代替行情时间、历史完整性或来源健康。维护人员同时核对实际进程、控制身份、配置摘要及具体查询结果。来源端离线与历史文件读取失败分别定位，不从旧状态文件推断存活。

停止观衡仅关闭其Web资源和读取池，WT历史服务继续运行。需要停止运行侧时，向WT本代控制目录提交原身份绑定的stop.json；WT按执行、采集、历史和Host逆序关闭，核对实际子树退出、双管道EOF、读线程join及原closed收据。超时或强制终止保留失败资格，原目录与数据继续用于排查。

来源查询失败后核对数据配置、原收据、组件摘要、文件权限及Reader错误，再用原查询确认恢复。未知补齐请求继续沿原请求ID核查；历史读取成功与补齐任务终态分别确认，操作见[补齐手册](qmt-history-preparation.md)。

## 独立升级与回退

WT组件在新目录安装，按新位置生成绑定路径和摘要的部署描述；按原运行状态兼容规则正常停止旧WT，再启动新代并验证实际查询。观衡独立升级Web包和SPA，不承担WT停止或重启。历史原件和未知请求身份保持原owner管理。

已有旧发行的App托管步骤仅用于其冻结历史证据；当前运行沿本手册。生产切换、恢复与回退按[发布规范](release.md)和对应候选实际资格执行。
