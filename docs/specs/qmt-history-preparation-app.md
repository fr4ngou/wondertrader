# App托管QMT历史补齐产品

类型：功能最终规格。状态：accepted。前缀：HPRA。适用范围：观衡App对[HPR5产品](qmt-history-preparation.md#hpr5-独立产品离线配对和系统托管)的公共配置、生命周期和只读状态；Host/协议/冻结正文仍由原HPR规格拥有。

## HPRA1 配置与默认

ConsoleSettings新增qmt_history_preparation_config_file与qmt_history_preparation_config_sha256，环境为GUANHENG_QMT_HISTORY_PREPARATION_CONFIG及GUANHENG_QMT_HISTORY_PREPARATION_CONFIG_SHA256。无配置继续disabled，不构造Host连接、Journal或配对材料。路径与SHA共同准入，由原HistoryPreparationProcessConfig.from_path核原字节及qmt.history-preparation-process.v1；凭据继续在私有pair内，父App不读取或公开。原其他进程配置保持兼容。

## HPRA2 生命周期与隔离

App lifespan独占HistoryPreparationProcess实例，沿原ManagedLocalProcess启动、隐藏Job/PID归属、观察和关闭。start只等监听就绪；来源可以晚到，App不设置60秒终端总启动窗口。停止消费者后再关闭HPR，原首个关闭截止及owner保留语义保持。部分启动/非法配置/子端失败只降级此能力，其他来源/账户/采集能力沿原合同运行；自身资源实际未闭合不得标记closed或整个App shutdown_complete。父层不得复制Host或运输实现。

## HPRA3 只读入口与中文说明

GET /v1/ui/qmt-history-preparation返回配置/启动错误及原status安全投影。已有运行状态/总览沿现有页面表达默认关闭、启动中、监听就绪、失败/停止等生命周期，并明确监听就绪与实际来源连接分开；qmt_connection=not_checked继续未知。原始异常、路由/内存映射名字、凭据、私有路径及内部原文不出现在公开页面。此项不新增真实下载、订单/撤单或权限按钮；缓存副作用由已有显式HPR请求准入。

## HPRA4 安装与验收

2026-10-29用户展示纠正：总览仅显示历史数据更新状态、原读取时间和重读按钮，刷新失败保留上次成功结果及时间。运行状态卡移除进程编号、资源收束及强制回收明细；内部生命周期字段继续保留于原API和诊断资料。系统状态页提供必要故障原因、影响及处理说明。

普通App安装包含薄适配，Host继续独立安装/版本；App不依赖导入Host包。验收默认disabled、配置错误隔离、部分启动/正常关闭、公开状态去敏及中文页面；实际App lifespan管理独立安装Host，晚到SDK替身执行原组合正文、断开重认证及原结果读取，沿原HPR工程证据复用未变部分，核本次App安装身份与资源闭合。生产SPA入口验证监听/未知来源的真实表达。真实QMT、全天采集、业务完整和生产发布资格分别记录，不由工程ready或测试数授予。
