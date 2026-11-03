# 全A等权PB月末与最新快照

类型：模块说明。所有者：观衡市场观察。范围：原`pb_all`提供方报告值的持续接纳，合同沿[OBI5](../specs/independent-market-observation.md#obi5-独立采集与来源)。

原指标来自乐咕乐股ALL公开快照，原`definition_version`、等权PB/中位数、历史分位与日期定义保持。当前来源配置此前只有指数背景关联，没有PB数值生产者；独立`pb_shsz_daily`另用沪深股票表，筛选和范围分别维护。

新增`legulegu_source.history`由原`collection.refresh`调度。原Fetcher先取得公开页面及该会话CSRF，再沿同一Cookie client读取原ALL接口；公开当日标识按上海日期生成。CSRF只用于当前请求，原主机、请求/字节/总截止及失败保旧保持。来源配置不含认证值。

字段映射：date为提供方实际观察日；equalWeightAveragePB→equal_pb、middlePB→median_pb均为原PB倍数；close→reference保留提供方原指数参考点数；available_at保持未知空值。上证背景由原统一指数表另行生成，不替换提供方reference。完整响应先存原件，再选择来源窗口，旧月末及旧最新真实观察均保留，不跨日补值或补造日频历史。

提供方页面说明等权剔除亏损、暂停上市及PB大于100的公司，中位数说明剔除亏损和暂停上市；公开接口未给出逐股成员或实际分母n。继续原提供方报告值资格，不将5576只报价、沪深重算或缺北交所净资产的股票池冒充此原序列。

一次来源更新后沿原发布及查询重算历史分位。只读上证基准重建保留采集者freshness；未选指数来源时不擦除其既有观察。这保护PB单路更新后的其余71组记录。原运行状态看实际配置及freshness，旧history_audit保留原归档审计，实际条数和末期看当前coverage/frequency_audit。

配置和维护见[观察手册](../runbooks/market-observation.md)，真实原件、安装及接收边界见[本次证据](../evidence/2026-11-03-pb-all-continuation.md)。本模块不修改WT框架、QMT、旧工程或现场owner，不新增服务。
