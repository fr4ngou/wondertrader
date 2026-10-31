# 全市场日线缓存准备与批量捕获

状态：accepted。范围：WT外部HPR准备、v8捕获与原身份续接。
架构决策见[ADR0021](../architecture/adr/0021-market-daily-cache-preparation.md)，
接口见[模块](../modules/qmt-market-daily-preparation.md)，操作见[手册](../runbooks/qmt-market-daily-preparation.md)。

## MDP1 职责与来源

WT外部来源工作流使用原HPR `market.history_prepare` 更新QMT缓存，随后用原v8
`market.market_data`分别读取none/front_ratio。证券全集来自调用者固定版本的证券池；
证券池属于业务输入，格式准入不代表证券存在或当日应有交易。
内置SDK仍是原策略线程调用四参数 `download_history_data`，不增加策略文件、网络或线程。
官方内置API声明单证券下载；官方列表示例逐证券调用。列表读取沿原get_market_data_ex。

## MDP2 显式能力

HPR沿原v6 profile/操作/策略/结果，新增显式
`qmt.history-preparation-limits.v3`，与v2相同字段、额度、截止和单次SDK语义，证券格式接收
六位代码.SH/.SZ/.BJ。v1/v2保持原沪深准入。BJ下载资格取实际SDK回包及后续读取证据；
格式合格与已有BJ日线可读证据分别登记。旧配置和金融通道保持原语义。

## MDP3 有界与恢复

一次工作流固定原请求、证券池摘要、两来源连接身份和缓存日期窗口；每个HPR slot固定
原UUID、参数、业务截止、完整结果及consumed。重进相同目录先核配置和原请求，已有slot
只续核原ID；未知、404/410、丢确认保持原责任，禁止换ID重复下载。确定拒绝保留原件，
由操作方建立下一次明确观察。原Host Journal和票据拥有通信事实。

首次准备前通过原RetainedReadClient分别准入HPR与v8完整binding，持久保存原
HPR-BINDING及capture/BINDING；后者继续由原BatchAnalysisSource消费。暂停后续接
先核两端当前认证与固定binding，再允许任何新准备或批读。旧ID与未知责任保持原值，
来源变化结束当前工作流准入。正式CLI还固定实际连接配置；完成包离线重读不访问来源。
公开run在创建目录、slot或进入原ID等待前拒绝bool、非数字和NaN/Inf绝对D。

工作流总截止、单请求截止与每次最多处理数量分别有界；额度不足暂停原工作流，后续继续。
新slot在容量等待完成后生成原请求；容量等待与每次原结果续核分别最多使用原scope的一次
total_timeout_ms观察预算，均受同一工作流剩余D约束。旧请求的UUID、参数和deadline_ms
保持原值，后继观察预算仅限定查询等待，不延长SDK或重新提交原未知请求。
进度文件仅索引原slot，不清Journal、不制造已完成事实。并行仅在终端外使用独立客户端；
每个slot唯一工作线程。所有已提交工作在原请求截止内退出后才返回。

正式外部CLI可在原BoundHistorySource显式选择有界HTTP复用。连接仅属于该运输实例的
最外层rpc_budget，嵌套沿原较小预算，每次交换沿原绝对截止；作用域退出即关闭。每次
交换使用原认证规则，不缓存签名或nonce。异常退役连接并返回原未知/异常，连接层不
重放失败请求。服务端主动关闭后的后继交换可以新建连接；关闭失败保留连接owner和
异常链。默认单次交换关闭与金融调用继续原行为；不新增常驻池、线程或请求额度。

## MDP4 覆盖及消费

HPR call_returned仅证明原SDK函数返回。全部HPR确认后，原v8持久消费方保存原批次结果并
确认消费，输出既有C包。每个证券的none/front引用同一原批次身份和真实接收时间；不伪造
独立请求或时间。实际日期、空/缺失/无效分别保留；缓存尾早于目标日不等同数据损坏，停牌、
上市、交易日及复权/共同闭合基准由C与原QNA按实际材料核定。

## MDP5 增量与发行

初次准备使用业务日期窗口；已有成功捕获时，后继观察可显式以原实际尾日重叠更新，保持
至少40期所需的原读取窗口。工作流不创建定时任务，不逐轮强制重复多年下载。相同工作流
完成后离线重读不再调用SDK；新观察使用新业务身份。正式安装、SDK替身、真实切片与
全市场真实数据分别记录资格，合成数据不得进入真实指标。
