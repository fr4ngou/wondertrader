# 采集历史的独立补齐来源

类型：运行手册。适用范围：已归档分钟缺口与独立来源导入的只读组合。契约以[CNH-R5](../specs/collected-native-history.md#cnh-r5-独立导入的补齐来源)为准。

1. 用原Reader核实际归档日期、缺少标签和原值，保留原DSB摘要。文件包含多日时按目标日选择，证券数与完整分钟覆盖分别记录。
2. 获取有来源证据的历史记录，保存原导出清单、CSV和来源版本。已有源请求沿原ID核查；在线接口未授权的日期保持其原准入。外部已下载缓存按工具能力离线导出，QMT内置正文继续采用原无文件/网络模式。
3. 从已冻结导出选择确实缺少的记录，保留原标签及数值，不转换unknown单位和分钟边界。原Importer写入全新store，原NativeHistory按成功收据回读；原Writer目录和已有重叠分钟保持。
4. 在新候选source-collected配置中保留base与collection，添加可选supplements列表。每项使用完整原source-store/source-stores/source-catalog配置，native_reader绑定本次安装Reader及SHA，成功收据摘要绑定新store。预加载沿所选模式原契约设置。省略或空列表沿原行为。
5. 用公开history.source-query核目标标签出现、已有记录及metadata保持、分段provenance保留来源；同分钟异值应明确Unavailable。coverage仍为Unknown；按明确日历核得的选定样本覆盖单独记录。
6. 沿独立WT的SourceMarketProcess启动候选历史服务，再用公开SDK查询。关闭后核Reader、服务、WT、Job、管道与线程结果；候选数据及配置摘要固定后交运行侧按发布流程选择。观衡只读取公开历史服务。

配置及数据根是运行侧显式声明。新增store或更新补齐集合需要生成后继配置身份并重新验证，当前模块不创建定时任务或自动切换活动实例。自动源准备继续由原source-preparing负责，其在线收据与离线导入来源分别保留。
