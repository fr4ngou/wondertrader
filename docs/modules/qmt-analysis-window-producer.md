# 持续 QNA 分析窗口

类型：模块说明。范围：WT 自有日线分析窗口发布。状态：SDK 主链已运行，来源与共享装配资格分别登记。

接口要求见 [AWP](../specs/qmt-analysis-window-producer.md)、[来源纯值](../specs/qmt-analysis-window-provider.md) 和 [QAS v7](../specs/qmt-analysis-source.md)。源码入口为 [独立包](../../apps/analysis_window_producer/README.md)，操作见[运行手册](../runbooks/qmt-analysis-window-producer.md)。

`AnalysisSnapshotProvider` 通过显式原 bound 操作读取 raw 日线、原因子及共同基准 none/front_ratio 参考。每个 capture 的请求身份、实收时钟、原认证绑定及原结果都由 source 层保存。超时沿原 UUID GET；它不下载、不查询账户、不交易。来源闭合上限按上海 ETF 正常交易时段计算，实际八证券日期交集确定基准；不会填充缺日。

`AnalysisWindowProducer` 串行常驻刷新、持有最后成功与 Pending capture。每轮先验证源年龄，再把共同基准前的原价行交原 schema3/day Import 和 Helper 全值回读，原 QNA 负责因子和原生 IDataReader 前复权。`NativeRefreshJob` 沿现有 Job 和 ThreadOwner 控制整个 DLL/Probe 树；只有正常整树退出、EOF/join、句柄关闭后才允许发布。

QNA 候选、NativeRead、日线 DSB/sidecar、参考与原始收据独立保留。发布适配仅修改两个时间声明，绑定实际完整来源实收；`generated_at/published_at` 单列。其余因子、价格、量额、修订和资格原样传递。原 R24 无需新格式。缺源/过旧保持旧窗口原字节，状态说明原因；协议或原生故障转 failed。

状态文件呈现阶段、有限原因码、最后成功时间、基准、source/factor 修订及 SHA。工作根由部署独占，已生成证据保留；部署负责容量观察与历史证据归档。服务不会清理来源或历史行情数据。关闭的 `False` 表示资源尚未取得确认，owner 和 Job 保持以供续核。

唯一发布者直接复用 WT `_InstanceLease`，锁范围是工作根；OWNER.json 为持久代际记录。新代次先取得 OS 租约，再校验旧发布 SHA、恢复最后成功及 Pending REQUEST，归档旧 owner/status。竞争者取得租约失败，无法写状态；关闭未确认继续持有租约。正常结束后同配置、新控制 UUID 可使用原工作根和发布文件，来源实收时钟保持原值。

恢复先核 CONFIGURATION.json 的完整纯值投影与 SHA；来源连接/provenance、发布目标、制品路径/SHA、解释器/工作路径及所有刷新参数均在同一权威身份内。路径和数值沿规则版本1规范化。身份改变在状态/请求/发布写入和来源调用前失败，旧文件保持。直接 provider 的来源身份由调用者显式提供。秘密值不进入文件；旧 a4 无该配置身份的根不自动收养。

本模块复用原 QNA/Import、WT Reader、ProcessJob/ThreadOwner 和 R24。它没有账户归属、金融账本、数据库或观衡生命周期职责。后继 WRI 注册由系统集成者负责，当前独立 CLI/owner 可验证。

可选 `DailyHistoryPreparation` 复用原 BoundHistorySource 的 v6 binding/plan/observe 和同机 uptime 截止，在 Provider 的原 CLOSURE 与 v7读取之间运行。准备计划和每片原请求/绑定/终态留在同 capture/source/preparation，原任务未知只 GET；所有 HPR已返回后才写 PREPARATION.json 的尾日及原返回时刻。该文件只用于合并准备频率。来源实际覆盖及市场数据新鲜度仍由原 v7 读回与实收时间决定。

系统已有独立日线补齐owner时，部署省略该可选准备配置，由该owner持续更新缓存，AWP承担读取及分析发布。独立缓存更新与捕获前同步准备是两种已有装配方式，部署明确选择唯一补齐责任。未知准备回执与已读取的实际行情分别保留；切换配置使用新独占工作根及原账升级入口，Reader同步选择对应status/source_root。

首次仅补当前 closed_through 日，后续从最后已返回尾日含首尾推进，按原日历额度拆窗；同日按显式间隔再次准备以接纳修订。原 HPR 任务/Journal 容量保持，耗尽保留已派发身份及旧窗口供后继观察；模块不清理或重建来源。原证券集合来自策略输入，补齐接口范围仍由原 v6 能力表达。

显式连接声明 read_retention 时，AWP 的 retained 接缝只剥离该可选能力并核认证 profile，实际票据、内容 ID、原结果持久保存、consumed 和回收均归公共 RetainedReadClient/Host/Agent。v7 返回原四字段收据，HPR沿原截止及计划调用同一公共 prepare。AWP不删除slot或创建第二份通信Journal；所有原值、原请求与发布证据继续留存。默认省略保持a8路径，未知继续同capture等待，消费者确认失败属于原责任。

显式回收HPR的明确受理拒绝/调用前拒绝，原slot完整保留，交原owner下一业务capture继续；网络未知、404/410仍同capture/ID续核。判定只使用公共RetainedReadFailure/Pending分类。

显式回收按RR6把capture原完整binding传入公共read/prepare的expected_binding。新slot准入当前Host认证，来源换代时在POST前结束本次已确认观察，旧窗口/slot保留；下一capture重新读取。旧slot未知继续原ID，完整结果确认后才判断本capture一致性。
