# WT 持续分析窗口生产者

类型：模块入口。状态：开发验收中。唯一要求为 [AWP](../../docs/specs/qmt-analysis-window-producer.md) 和 [provider 合同](../../docs/specs/qmt-analysis-window-provider.md)。

`guanheng_analysis_window_producer.runtime.AnalysisWindowProducer` 由 WT 持有。它使用显式只读 v7 来源，持续获取当前唯一策略的八证券日线、原因子和基准参考，沿原日线 Import、原 WT Reader 和原 QNA 发布完整 v1 文件。观衡和 R24 只读消费。每轮先获取来源，Native DLL 在隐藏 Job 内运行，源或原生失败保持最后成功文件。

`create_producer(configuration)` 为后继 WRI 注册接缝；当前共享 dispatcher 保持。独立命令为 `guanheng-analysis-window --configuration <deployment.json>`，进程持续运行，部署 owner 通过其目录内 `STOP.json` 请求关闭。Python owner 使用 `start(deadline=...)`、`status()`、`refresh()`、`request_close(deadline=...)`、`close(seconds)`。

依赖：Python 3.12+；稳定接口范围为 WT runtime `>=0.1.0a9,<0.2`，显式 `bound` extra 为 Host `>=0.1.0a11,<0.2`。发行 lock 和安装收据精确固定每个 wheel 版本与 SHA，实际资格仅属于已验组合。普通 `guanheng-native-analysis-core` 将八个所需原始模块按原字节构建并绑定原 SHA。Helper、IDataReader 和 QNA Probe 由部署以路径及 SHA 注入。

同一工作根可在 WT 正常关闭后重新启动，原发布与来源时间保持，Pending 沿原请求身份续核。原 WT OS 租约保护唯一发布者，线程及 Native 资源确认关闭后释放；OWNER.json 记录代际，历史 owner/status 留存于 owner-records。

工作根 CONFIGURATION.json 保存版本化完整配置身份；来源连接声明、发布目标、Native 路径/SHA、解释器和刷新参数改变会在恢复或写状态前明确冲突。`create_producer` 自动绑定完整 source_connection/source；直接构造 owner 时须传明确纯值 `source_identity`，秘密仅以受管引用出现。旧 a4 根缺权威身份，保持旧制品处理并显式部署新根。

显式 `history_preparation` 连接原 HPR v6，在同 capture 内先准备近期日线缓存，再由原 v7 读回真实日期和内容。首次只补当前闭合日，后继按最后准备尾日推进并按间隔合并同日请求；暖机仍读取已有历史。原请求/结果保持，未知沿原 GET；返回只表示 call_returned/coverage unknown。省略该配置保持原读取路径。发行固定 core a2，原分析算法字节保持；新增 replay 接口由其独立证据负责。

辅助启用项为`producer.auxiliary_directory`和可选只读`auxiliary_seed_directory`。来源取得、修订归档、逐日重试、字段覆盖和显式研究接口见[辅助事实持续更新](../../docs/modules/analysis-window-producer.md#辅助事实持续更新)。默认省略保持原价格路径，辅助采集由WT持有，观衡只读。新配置使用新工作根及发布位置，保留原根和请求责任供回退；实时模式保留真实实收时刻，研究模式必须显式选择并由消费者拒绝流入实时。

历史补齐以可选`producer.auxiliary_history_snapshot={path,sha256}`接入核定官方快照；严格协议、容量、实际时钟及完整事实键优先规则见[固定官方历史快照接缝](../../docs/modules/analysis-window-producer.md#固定官方历史快照接缝)。快照引用进入原Owner配置身份，仅填当前缺口，持续来源错误保留，研究快照拒绝。交付仅需更新AWP普通wheel，V1公式和包元数据保持原位。

源码在本目录；[模块说明](../../docs/modules/analysis-window-producer.md)、[最终规格](../../docs/specs/qmt-analysis-window-producer.md)、[验证入口](../../tests/integration/analysis_window_producer/README.md)。真实 QMT、共享装配和生产资格沿根集成证据单列。
