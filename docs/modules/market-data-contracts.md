# 行情数据结构与读取边界

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块说明。范围：现有报价流、来源分钟/日线、标准分钟和原生存储；字段定义分别以所链接源码/规格为准，不引入另一套存储或DTO。

## 完整数据路径

| 路径 | 入口与转换 | 保存/读取 |
| --- | --- | --- |
| QMT实时全推 | 原内置回调→QuoteStreamAgent→命名SHM→QuoteStreamReceiver→C++薄DataKit会话 | 原DataKit Writer生成实时DMB，原收盘流程归档DSB |
| 已下载分钟 | 外部qmt_local_dat→QMI清单/原导入器→WtDtHelper | WT DSB及来源sidecar/原成功收据，读取复用NativeHistory/原Reader |
| 来源日线 | 已核实API原始日线→QMI schema3→原WtDtHelper日线入口 | his/day原DSB、来源sidecar及成功收据；保持源交易日期与原数值 |
| 观衡来源历史 | MarketClient.source_history_query / source_daily_history_query→NativeSourceMarket | 按成功store证券及周期路由→受管Reader/LRU→来源结果 |
| WT策略原生分钟 | 原策略/数据管理器→IDataReader | 原生文件及已配置Loader；具体装配资格见对应模块 |

采集入口与线程见[全推流](qmt-quote-stream.md)，WT聚合/归档见[原生DataKit](wondertrader-datakit.md)，查询见[独立行情服务](market-service.md)。既有HTTP实验/Reader候选与最终原生复用的状态沿[原生收敛方案](../migration/native-market-integration-plan.md)登记，不能由源码存在宣布已部署。

## 日线事实的来源区分

日线周期和不复权声明共同保留，但它们不能单独证明两份日线来自同一种原件。

| 日线事实 | 生成与读取 | 时点及比较边界 |
|---|---|---|
| 券商原生日线 | `get_market_data_ex(period='1d', dividend_type='none', fill_data=False, subscribe=False)`，沿原回包归档及原生读回 | 请求结束日期与实际返回末日分别记录；前复权分析使用同源成对参考和因子 |
| WT收盘快照 | 原Writer保存缓存tick的价格、日内高低及累计量额，收盘CSV由日线适配读取 | `wt-native-snapshot-daily.v1`及内容SHA标识原件；当前CSV没有原tick动作时刻，文件修改时间不代表最后行情时刻 |
| WT原生日线存储 | 原`his/day`归档及已声明Loader读取 | 原数据来源、聚合方式和单位沿sidecar/元数据；原生文件格式本身不改变来源事实 |

两类原价出现差异时，先核实际路由、原件SHA、复权、累计字段和来源时点。原件保留各自数值；回测按同一已声明来源构建完整窗口。由快照和券商日线分别得到的收盘价、成交量和成交额，可以在回放前已经不同；精确尾tick是否缺失或供应商何时修订，需要当日带时标原行情证明，不能从收盘CSV或文件修改时间推定。

## 来源与状态

[ProviderTypes](../../src/GuanhengCommon/ProviderTypes.h)的SourceSession保存provider、instance_id、session_id、generation，表达一次源会话。Capability保存supported、qualification、reason；Status保存code/reason。连接状态、数据覆盖和运行资格分别表达。

MarketSnapshot（外部历史/待归仓路径：`../../src/GuanhengData/MarketParser.h`）把SourceSession与原WTSTickStruct组合，另含full_cumulative/source_time_verified。标准价格、单位或时间资格必须由来源profile明确；报价流的Session profile身份与该业务DTO分别有自己的合同，不能互相隐式补字段。

## QMT报价八字段

唯一纯合同为[quote_stream_contract.py](../../connectors/qmt_shm/agent/guanheng_qmt_shm_agent/quote_stream_contract.py)，版本/容量以[QST2](../specs/qmt-quote-stream.md#qst2-冻结数据合同)为准。

| 字段 | 语义与消费方式 |
| --- | --- |
| time | 来源epoch毫秒；与接收墙钟分开保存，转换上海日期/时刻后进入原WT tick；作为交易所成交时刻的资格须另核 |
| lastPrice | 本次最新成交价，Writer据观测tick形成分钟价格 |
| open/high/low | 来源当日开高低；不是当前一分钟的OHLC |
| lastClose | 来源昨收 |
| volume/amount | 来源累计量/额，保留原数值；换算因子必须显式声明，1也不证明已是股/元 |

每包为schema_version、kind、ticks；ticks键为六位.SH/.SZ，值严格八字段。kind=snapshot表示该代最新状态，incremental表示后续回调更新；最大批次200，同证券同包不重复键。输入校验数值有限、量额非负及当日价格关系；拒绝/缺报价反映在计数，不能以补零通过。

Source的_latest是每证券最新纯值字典，_pending是有界(symbol,tick)队列，_condition保护快照交接和队列；SDK回调与I/O owner分离。离线不积压全部旧事件，新认证代先发最新快照，再发增量。在线溢出触发代际重建并记录缺口，缺口分钟另行恢复。对象及字段语义沿源码，序号和HMAC复用原Session。

证券配置清单是显式订阅范围。供应商宽泛ETF板块可能混入认购、认购款等业务代码，板块成员数不能直接作为可交易证券数；应保留具体证券资料与身份依据。场外IsTrading=false、没有报价、原始报价未通过校验各有不同含义，不能只按其中一个现象推断停牌或完整覆盖。原始回调缺行与纯合同拒绝尚未分别取得证据时，缺失原因保持未知。

心跳qmt.quote-heartbeat.v1含callbacks、received_ticks、accepted_ticks、rejected_ticks、queue_depth、sent_ticks、latest_symbols、missing_symbols、overflows。latest_symbols是已接收有效快照的证券数，missing_symbols是清单差额，二者都不是历史缺分钟数。Writer delivered/broadcast计数只证明走到相应阶段，分钟文件与完整覆盖另验。

采集status外层observed_wall_time是本次发布时刻，collection.observed_wall_time是最近报价批次到达的本机时刻，latest_source_time_ms是报价中最大的来源时刻。无新报价时后二者可以保持；用receiver_heartbeats的连续增长核对认证运输仍在收包。receiver_failure保留上一次连接结束记录，重连成功后仍可能为connection_ended；结合当前connected、generation及cleanup/error字段判读，不能只据这一旧字段认定掉线。进程是否存活另核实际PID和控制身份。

## 来源历史与标准分钟

| 对象 | 时间/量额 | 已有责任层 |
| --- | --- | --- |
| SourceHistoryBar | 源标签occurred_at及原始OHLC/volume/amount；周期由metadata声明为1m或1d | [native_history.py](../../integrations/guanheng/native_history.py)；元数据拥有单位/边界/复权/内容身份 |
| SourceHistoryMetadata | source、dataset_version、content_id、source_license、资格、周期/数量、单位、minute_boundary、timestamp_semantics、none复权/Asia/Shanghai和价格质量计数 | 同一来源Reader核sidecar/收据并保留原值 |
| MarketBar及HistoryMetadata | 已证明的股/元、上海右端分钟及复权/换算版本 | [models.py](../../integrations/guanheng/models.py)、History.h（外部历史/待归仓路径：`../../src/GuanhengData/History.h`） |

来源分钟允许minute_boundary、price/volume/amount单位为unknown，不能直接标成标准MarketBar。来源OHLC关系异常按已有质量规则原样保存/标识；标准路径继续严格价格关系。负量额、无穷或非法时间按既有合同拒绝；不能通过取绝对值、裁剪或补零修正。DAT布局与有符号计数字段只有[qmt_dat_layout.py](../../integrations/guanheng/qmt_dat_layout.py)维护，改格式先核原记录与官方输出。

来源日线采用period=1d、timestamp_semantics=source_date；occurred_at为交易日期00:00+08:00，原day DSB的date保存交易日、time为0。这是日期标签，不能作为当天收盘数据已可获知时刻；完整闭合、可获知时刻和交易日历另由对应来源事实证明。具体导入布局与公开合同见[DSH](../specs/qmt-source-daily-history.md)。

该source_date的+08:00固定标签覆盖公开八位有效公历日期域1000..9999年，历史夏令时不改变标签。来源分钟及canonical继续原时刻/IANA语义。DAT导出可按显式来源标签日期闭区间选择，收据保留全原件SHA及扫描/选中/按日期排除数；无窗口仍完整导出，原负量拒绝规则保持。历史日线计数语义按同源验证范围登记，已核分钟布局不自动授全部日线历史的字段解释资格。

来源单位由具体接口、安装版本、证券类别及数据批次的证据决定，price_unit、volume_unit、amount_unit分别核实；一个字段已确认不隐式补齐其他字段。lot表示来源“手”，每手多少股或基金份额由证券规则决定；消费端换算必须明确目标数量单位。以新profile修订单位时生成新的manifest/成功数据根及dataset_version，保留原根；API单位证据不能直接升级旧DAT布局或实时全推的单位资格。

服务请求history.source-query的exchange/code/from/to/limit为显式闭区间，limit=1..2000；返回区间内最新至多limit根并升序。响应metadata/bars/coverage/missing_minutes/selection由[source_history](../../integrations/guanheng_market_client/source_history.py)校验。每bar是symbol=SSE.六位或SZSE.六位、minute=YYYYMMDDHHMM及OHLC/量额。该分钟标签不移位；coverage=Unknown与missing_minutes=[]不能解读为数据齐全。

日线请求history.source-daily-query复用exchange/code/limit，from/to使用8位YYYYMMDD有效日期；每bar返回date及原始OHLC/量额。metadata显式period=1d和source_date，selection含period/limit，coverage=Unknown与missing_dates=[]同样不证明区间完整。SDK严格校验日期/周期及元数据，不从分钟查询返回值猜测日线。

## 文件组织与读取

原Writer管理rt/min1实时DMB和his/min1历史DSB。离线导入根沿原QMI布局、sidecar及成功收据，不能把目录结构相似直接认作可以混写的实时根。每个数据根保持明确单写者；采集归档与导入/修订不能同时覆盖同一根。

NativeSourceMarket共用Reader和按实际bar数计的LRU；source-store(s)保留分钟模式的证券唯一路由，source-catalog显式按证券+周期唯一路由，允许同证券的分钟和日线共存。同键重复不会靠配置顺序覆盖，LRU总容量跨周期共享。准备新目录配置后冻结新实例，不能修改活动Reader的来源身份。C++ Reader/API切片及SourceHistoryBar返回副本的所有权按原接口释放，源SDK对象不跨共享内存传递。

策略按需历史/补齐、实时快照及分钟订阅的业务入口见[统一行情规格](../specs/strategy-market-access.md)。来源缓存可读、采集完整、分钟闭合、日历覆盖和策略已消费是不同验收结果。实际进度与数据范围放[证据索引](../evidence/README.md)，模块文档保持上述职责与字段解释。


## QMT原始日线、分析价与复权来源

QMT内置ContextInfo.get_market_data_ex支持dividend_type=none及front_ratio（等比前复权）；ContextInfo.get_divid_factors返回除权除息事件，键为时间戳，值含每股红利、送转、转赠、配股、配股价、股改标志和复权系数。接口及字段以[迅投内置行情函数](https://dict.thinktrader.net/innerApi/data_function.html)为依据；外部XtQuant与内置ContextInfo分别按实际安装版本核实，函数同名不代替实机数据证明。

行情适配器保存本次请求、原返回值及实际接收时间，再将原始日线、同一基准日的分析价和因子来源配对。原始价格继续供WT原始历史和交易参考使用，分析价由策略计算合同消费；两者保持各自精度。因子事件及每日分析倍率分别标识，通过同日原始/调整价格和基准日核查后再生成策略输入，缺少真实因子资料时保留来源缺项。不会把假定全1序列标为原生复权资料。

当前取得的历史资料按current-visible-reconstruction声明实际known_at/received_at，历史首次可见时间及修订历史未知；它支持收到数据之后的当前决策，严格历史时点回测继续按其独立输入资格验收。来源适配器负责证券、日期、单位、分析基准和内容版本；策略核心复用这些事实，WT持仓及账户事实保持原职责。


实际QMT事件、原始价格与前复权价格的交叉验证沿[原生复权实机证据](../evidence/2026-10-29-qmt-native-adjustment.md)。事件倍率和逐日累计倍率分别保留：供应商事件系数经日期累乘后交给原生Reader，由Reader按分析基准换算价格；实际空事件表及原价/前复权相等的验证范围单独说明。历史原始日线、当前可见分析窗口与严格历史时点回测分别标识。
