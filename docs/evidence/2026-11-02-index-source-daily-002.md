# 50指数来源日线002后继验收

类型：独审修正与范围核实证据。日期：2026-11-02。状态：候选已修、离线原生与固定归档核实通过；Root独审、组合验收与生产接入继续。001冻结目录和既有运行服务保持。

## 根因与统一实现

量活跃度依赖当前同源量及其预热，原实现把known单位变化后的activity赋值放在value and first基价存在分支中，缺固定基日时旧activity=99残留。002在有同日value时统一赋close、原量、activity；固定基价只决定rebased列。unknown与known单位变化均按已有同单位20日预热，无单位归档口径保持。缺基价且share变lot的第21/30行回归已覆盖。

参考最终化复用REFERENCE-ORDER-CODE-001的attach_sse_reference函数，AST逐项一致。唯一责任层同时处理原cffex和四basis，首轮引用一致，重复输入保持；原主指标和覆盖外归档参考保持。Root按002的组合refresh_models接收activity和reference两项。

## 原日线路由与覆盖

001的全50短聚合仓进入base后，原factory优先返回Ok空范围，遮住旧supplement。原000300.SH从2005起5294日、000016.SH从2004起5532日；2024年一季度原服务各58日，001均返回0，002均严格恢复原58日、六字段及metadata完整相同。

002的source-preserve-existing-final.json只给其余48项加日线路由；两个原长日仓owner、原股票/ETF、分钟及collection配置保持。原factory离线逐项核50项非空，000300.SH目标期返回1207日至2026-10-30，000016.SH返回1202日至2026-10-16。完整内容、来源和范围见ROUTING-ADMISSION-FINAL.json。本轮按Root约束使用原factory/NativeReader直接调用，启动运行服务0。

replace_tables完整覆盖检查保持。固定fd94的实际旧表日期与002响应日期比较，沪深300缺0日，其余7项仍缺：上证1468、上证50 1、中证500 751、中证1000 741、科创50 581、创业板802、中证全指2630。原8项作为同一来源批次时仍会返回market_existing_coverage_missing，并完整保留旧表；本次没有接收、删表或发布快照。

当前可接入路径：独立WT只读价格查询及独立候选来源表；原8项完整替换继续等待完整历史。Root如选择单证券来源变更，可在原预算/注册/审查流程下单独接收已完整覆盖的沪深300，其余7项保留原表。跨供应商按日期混合量字段的合并需要独立规格，本批保持原准入。

## 工具闭包

新模块已移除qmt_local_dat私有函数依赖，只依赖固定tracked native_history/qmt_minute_import/models/dependencies/price_quality/qmt_dat_layout。tool-bundle含固定tracked namespace、这些源码、新模块、原50分钟DSB/metadata/收据、原DLL与许可证；MANIFEST逐文件绑定。run.py只从包内runtime导入，任意工作目录用Python3.10+执行python -I -B run.py --output-root <新绝对目录>，无需Root或Root未跟踪源码。

002独立闭包全50重新执行原生聚合和day导入，11657根；最终同一闭包入口和全部输入按MANIFEST核验，所有integrations加载位置均在runtime。工具闭包ZIP、源CAS和数据SHA沿DELIVERY-002.json；原成功001 HTTP/MarketClient证据按相同原生数据值复用。当前后继没有启动WT或App，也没有改当前owner、fd94、QMT/SHM、交易、数据库服务及框架。
