# QMT 全推共享内存到原生 DataKit

类型：功能规格。状态：accepted。范围：独立行情数据流，沿原生 DataKit 扩展接口；账户、交易和原查询协议保持。

## QST1 完整主路径

QMT 内置 ContextInfo.subscribe_whole_quote(['SH','SZ'], callback) → 内存行情队列 → 既有 builtin-shm / LocalTransport / Session → 终端外 QuoteStreamReceiver → 自有薄采集会话装配原 ParserAdapter/DataManager/StateMonitor → 原 WtDataStorage。一分钟聚合、session、DMB/DSB和广播保持原生。外部薄宿主负责运输及调用C++入口，不引入wtpy框架。不得把行情逐条放入命令Journal，不新增行情数据库。

终端内正文由既有memory_runtime在终端外构建，模块与参数完整嵌入；终端内不使用文件/网络API。沿现有GH_WT_MEMORY_VERIFY条目部署，备份、身份及运行资格分别记录。真实下单/撤单、账户查询和生产切换不在此切片范围。

## QST2 冻结数据合同

共享纯合同模块归 agent/guanheng_qmt_shm_agent/quote_stream_contract.py，Python3.6.8标准库。

settings固定字段：route、secret（私有bytes）、max_frame、transport（既有builtin-shm配置）、connect_seconds、io_seconds、symbols（排序且去重的沪深stock.market列表）、profile。profile固定字段为schema_version='qmt.quote-stream.v1'、symbols_sha256（canonical(symbols)摘要）、max_symbols（1..10000）、max_batch（1..200）、max_pending_ticks（至少max_symbols、至多65536）。settings联合准入沿现有LocalTransport固定映射/ACL/认证，profile与证券清单绑定。生产推荐max_batch=200，max_frame=4194304；所有值显式设置。

数据包固定字段：schema_version='qmt.quote-batch.v1'、kind（snapshot/incremental）、ticks（非空object，至多max_batch个已准入证券；值为time,lastPrice,open,high,low,lastClose,volume,amount八个数值字段）。time为有效epoch_ms整值；其它值有限，量额非负，价格按当前日OHLC关系合法且昨收为正。原值不改写。无效/未提供的证券以计数表达，不能补零或伪造覆盖。共享Session已拥有连续序号和HMAC，不另造命令ID/事务。

心跳包固定字段：schema_version='qmt.quote-heartbeat.v1'、callbacks、received_ticks、accepted_ticks、rejected_ticks、queue_depth、sent_ticks、latest_symbols、missing_symbols、overflows（非负整数）。I/O owner至多每秒发一次；不调用QMT API。Host读包有界，心跳与行情都不落命令Journal。

## QST3 来源与接收生命周期

Source类QuoteStreamAgent(context, settings=...)；start()由原策略线程调用原全推订阅并启动唯一I/O owner；on_quote回调只归一化纯值、按已绑定清单过滤并更新有界内存，不执行I/O；request_close()由原策略线程撤销原订阅并发布stop，close(deadline)由管理owner确认I/O关闭。start及stop严格原策略context/thread，SDK回调允许并发只改受锁保护内存。

Source离线时只保存每证券最新快照；新认证连接在同一锁内取得snapshot、清队列并开启增量准入，随后先发snapshot再发增量。在线队列受max_pending_ticks限制；溢出记录缺口并撤销本代连接，后续重新认证/快照重建，历史缺口另验，不能假装无丢失。每次连接与帧I/O有原绝对截止；常驻等待/代际重连不要求用户在60秒内手动配合。

Host类QuoteStreamReceiver(settings=..., on_batch=callable)。start()创建受管I/O worker并等待listener就绪；监听既有LocalTransport.listen(wait_for_peer=True)，空闲持续等待。认证profile必须完全一致；每包按纯合同和清单验证。on_batch(ticks, kind)在唯一接收I/O线程同步调用，完成后更新计数。断连先撤销ready、关闭原代资源，再创建新代；不同时启动两个writer。request_close/close(deadline)沿单一截止确认资源。

断线诊断随既有采集状态发布，保留最近 32 次已认证行情连接的异常。每条包含失败代、接收端 Unix 毫秒、初始化或接收阶段、进行中的动作、固定原因码、异常类型和可用的 Windows 错误码。正常停止和空闲监听超时不记作一次断线。新代建立后仍保留前代诊断，采集异常退出时最后快照同步进入 failure.json。QMT来源在原策略日志记录结束原因及两个报价回调间的单调时延。两端使用同一已认证运输代摘要关联。遥测仅在发生异常时产生，不参与行情准入、重连和 Writer。

## QST4 原生消费

原WtDtPorter提供create_ext_parser/register_parser_callbacks/parser_push_quote，但其C导出未提供聚合close。受管宿主采用原C++公开ParserAdapter/DataManager/StateMonitor组合，分别调用既有run/stop/release；自有IParserApi输入薄层只转交数据。自有C++薄导出复用qmt_mapping::map_ticks映射最多200证券，并调用原handleQuote(procFlag=1)，不重写分钟聚合、时段状态机或存储。价格/量额profile显式提供，来源值与单位资格分别登记。原生基础合约由真实沪深股票/ETF清单生成，已知清单6982与有报价6938分别记录。

## QST5 主路径验收

先跑真实WinSHM运输+明确SDK替身→接收回调，确认数量、字段和关闭；随后原生Porter/Writer合成分钟实际落盘回读；最后同一QMT条目实际全推→SHM→原生存储，记录接收覆盖、来源时间及文件。场外可验启动/快照；盘中时间推进、新分钟和自动收盘继续取证。正常主路径完成后再补故障/容量/独立审查。新框架修改先按用户批准要求办理，本规格仅涉及自有模块和构建接线。

## QST6 受管原生采集入口

QuoteCollection是终端外的单管理owner装配：QuoteStreamReceiver→NativeDataKitSession→原WtDtCore/Writer。报价直接同步交付，不以raw文件、命令Journal或第二套聚合器转接。构造不启动资源；start在唯一管理线程创建原生会话、启动常驻listener，返回只证明listener可等候，不要求60秒内启动QMT。既有Receiver独占收发线程、沿原代关闭后重连；同一实例保持一个Writer。

request_close可跨线程只发布停止；close沿首个绝对单调截止，先确认Receiver线程/运输关闭，再由原管理线程归档并关闭原生会话。接收未收束时保留原生资源；原生I/O阻塞由外层进程owner沿同一截止处理，不伪称Python超时已中断C++。显式关闭归档复用已批准生命周期库；默认WT原DLL继续原行为，采集配置明确选择。归档返回/进程退出和Helper实际文件回读分别验收。

公开状态仅含固定阶段、来源时间/观察时间、接收与原生计数、代际及固定错误，不含凭证、完整配置或逐笔价格。source_heartbeat仅投影原合同COUNTER_FIELDS，receiver_heartbeats表示接收数；快照覆盖、源端接受和缺失分别按原心跳计数解释。来源缺口、来源单位、全天覆盖仍保留未知；消费者写失败停止该流，不自动重放未知批次。自有Native接缝通过原IDataWriterSink的LL_ERROR闩锁传播真实Writer失败；push和管理线程check_health均检查，原合法时段过滤保持。close分别表达资源已释放和Writer失败，不发布业务成功收据。核心配置、时段、数据根由受管实例提供，长期收盘继续复用原StateMonitor，不用对话定时任务。CLI/应用托管及安装身份分别以实际交付证据登记。

验收先完成真实WinSHM替身→该正式装配→原生DSB→原Helper回读和管理关闭，再验证同一实例断开后新代重连；随后补停止/部分启动/消费失败等覆盖并独立审查。现场来源、日间自动归档和应用系统托管仍须各自实测，限时开发实例不能记作已上线。

## QST7 来源时延诊断正文

既有正文生成器的diagnostics缺省关闭，默认正文及协议不变；显式启用仍使用同一GH_WT_MEMORY_VERIFY条目与memory_runtime。代理回调只在有界内存保存原SDK最大源time、入口墙钟、回调/锁阶段耗时及计数，SDK回调不print、不新增I/O。诊断输出由原init/handlebar/agent_tick管理上下文沿QMT既有stdout产生，每10秒至多一次固定白名单GH_QST_DIAG记录；同一原策略owner至少间隔60秒调用固定三个证券get_full_tick作来源时间对照。

诊断不创建SDK后台线程、网络/文件入口、交易能力或新协议。默认路径渲染身份保持；诊断输出失败不改变行情接纳/发送，停止沿原request_close。真实快照结果与回调入口源时间共同用于定位SDK之前的延迟、SDK回调调度和自有处理耗时，缺失证据保持未定位。启用/备份/实机运行单独登记。

### QST6.1 应用托管与独立进程

观衡通过显式qmt_collection_config_file/sha256启用独立采集进程，缺省关闭；应用启动/关闭统一管理，用户不另开Host窗口。原QmtHostProcess的创建期Job、stdout/stderr限额、ready/closed收据、真实PID句柄及原停止截止监督逻辑抽为自有通用ManagedLocalProcess，原只读Host的配置/控制schema/默认行为保持。采集与账户Host为独立进程/独立路由，业务应用不直接持有Writer DLL。

采集进程部署文档qmt.quote-collector-process.v1固定字段：schema、pythonw、pythonw_sha256、entry、entry_sha256、configuration、configuration_sha256、control_root、startup_seconds、stop_seconds、max_output_bytes。路径为显式绝对路径；配置及入口摘要由部署身份绑定；startup_seconds沿0.1..120、stop_seconds沿0.1..60、max_output_bytes沿1024..1048576。原首启动截止/首停机截止和真实资源证明继续复用通用owner。

子进程参数--config/--config-sha256/--control-directory/--control-id。子配置qmt.quote-collector.v1固定字段schema、connection、native、archive_session、status_interval_seconds；connection为path/sha256/secret_env（settings文件不含secret），可选secret_encoding取utf8/base64，省略为utf8；base64严格解码还原原任意bytes秘密，配对身份保持。native为configuration/configuration_sha256/directory/session_library_sha256。archive_session为显式sid或null，interval为0.1..60秒。只在终端外读取配置和环境，敏感值不进入argv/日志/控制收据。子进程显式Writer选择和原生实例能力保持一致。已核原生配置字节写入独占私有控制目录的实例输入，再交Native读取；原部署文件替换不改变本实例Writer模式/数据根。同数据根受管实例使用byte-range单写锁，锁与collection由同一服务资源owner强引用；关闭未确认时保留至实际收束或父Job终止。

ready.json固定字段schema=qmt.quote-collector-ready.v1、control_id、pid、configuration_sha256、listener_ready=true；closed.json固定字段schema=qmt.quote-collector-closed.v1、control_id、pid、configuration_sha256、status=stopped、receiver_closed=true、native_closed=true、error_code=null。这里closed描述组件收束，历史数据结果仍用Helper回读。stop.json固定schema=qmt.quote-collector-stop.v1、control_id、deadline（原跨进程单调截止）。子状态可包含QuoteCollection的固定纯值快照，不能凭旧状态文件判断活进程。控制目录独占创建并使用既有私有目录/文件工具。服务正常持续等待；没有默认60秒业务寿命，异常进程不自动重放未知批次。

ready/closed/failure均先完整写入私有临时文件并关闭句柄，再以独占rename发布最终名称，父只观察完整收据。status由唯一publisher调用replace_status：首次独占rename，Windows已有目标使用ReplaceFileW，其他平台os.replace；不删除旧目标、不轮询重试。所有本入口status消费者使用read_status有界单句柄读取，Windows共享READ/WRITE/DELETE但只授GENERIC_READ访问权限；读取旧完整快照合法，仍核PID/配置/控制身份。同句柄前后元数据检查就地修改；publisher合同要求完整临时文件替换。failure.json固定schema=qmt.quote-collector-failure.v1、control_id、pid、configuration_sha256、stage、exception_kind、winerror、components_closed；仅固定阶段、异常类型和有限系统错误码，原异常文本/输入保持私有。失败诊断写不成时仍保原失败结果，不转成功。

公开/v1/ui/qmt-collection展示托管状态；无配置时disabled，单项配置/启动失败仅降级该能力。应用关闭先收束业务消费者，再关闭采集，最后关闭账户Host；各自预算从同一个应用关闭总截止分配。原Host兼容回归、独立采集真实WinSHM/原生主链、App实际启动及正常关闭均须验证；实际安装/生产切换另验。

Windows ReplaceFileW发布过程中，读者在取得首份句柄元数据前遇到系统共享冲突32时，read_status返回明确CollectionStatusPending；消费者沿原业务截止获取下一份快照，不延长截止。缺文件仍按原FileNotFound处理。权限5、取得首份元数据后的异常及内容/身份校验失败继续报错；helper内部不重试。

## QST8 原行情条目的可选历史补齐装配

原正文生成器增加显式history_bootstrap及history_reconnect_seconds输入，将[HPR](qmt-history-preparation.md)装配到同一GH_WT_MEMORY_VERIFY条目。未提供history_bootstrap时沿原纯行情正文/身份路径；诊断模式与组合模式分别选择。组合仅允许HPR的market.full_tick、market.history_1m及market.history_prepare，不注入账户、下单或撤单函数。

两种能力复用同一冻结memory runtime和原加载器；私有嵌入settings包含quotes、preparation及preparation_reconnect_seconds。两份设置分别完整准入，运输均为builtin-shm、Windows会话相同，计算出的命名映射必须不同。外部collector与补齐Host各自管理自己的原有listener/认证代，组合不另造运输或业务协议。

init由原策略线程构造QuoteStreamAgent及ReconnectingHistoryPreparationAgent，注册原run_time的agent_tick，然后启动两者；部分启动失败仍分别request_close。原全推SDK回调及报价I/O职责保持，agent_tick仅沿HPR原队列执行最多一次有界业务请求；handlebar不额外启动下载。stop按原context/thread核验，向两个owner都发布request_close，单个关闭失败仍收束另一项。SDK调用超期/未知与真正资源关闭分别沿原owner，不用新线程调用券商API。

组合正文仅额外注入固定download_history_data全局函数，QMT内部仍无外部文件/网络读取。补齐返回表示调用返回，覆盖必须回读；报价初始快照、历史回填与实时分钟资格分开。验收先完成同一展开正文→真实认证SHM报价与HPR Host→原owner下载替身→原历史回读→两端关闭，再验证默认正文一致、原线程/ContextInfo错误、部分启动、停止及不新增交易权限。真实QMT安装/运行由模块A单独验证。


## QST9 显式冷初始化与在线持续流（v2）

默认 `qmt.quote-stream.v1` 保持原字段、1..200批量与原生命周期。显式 `qmt.quote-stream.v2` 沿同一五字段profile、4MiB等已声明帧预算、最多65536在线队列及原连接/I/O截止；max_batch可在1..max_symbols内选择。实际全市场候选采用1000，原生入口仍固定每次最多200证券。证券集合、profile及源/Host安装身份一起进入原配对摘要，旧manifest保持原语义。

冷初始化阶段沿原离线latest语义，尚未接收在线增量。源以最多 `min(200, max_batch)` 证券的原snapshot批次交接，同时遵守原Native上限与本profile容量；Host唯一接收owner同步调用原Native。全部已有报价证券已实际消费后，源发送 `qmt.quote-warmup-complete.v1`；Host核本代实际消费集合后，沿同一已认证Session回复 `qmt.quote-warmup-ready.v1`。两种收据固定字段为schema_version、symbols_sha256、symbol_count；摘要是排序且去重证券列表的原canonical SHA256。缺失、重复、错集合或未知消费不通过屏障，原MAC/seq/ACK和原I/O截止保持。

确认后源在同一锁内重新捕获当时最新快照、清空离线队列并启用原在线FIFO，随后沿原snapshot→incremental顺序发送。初始化窗口只保留每证券最新值，连续增量资格从该原子切换点开始；首分钟及历史缺口另核，初始化不授完整逐tick连续性。进入在线后的已受理更新继续原顺序/容量/overflow撤代，禁止以合并更新隐藏在线丢失。第一份心跳在重新取得的最新快照交付后发出，未完成冷初始化不能凭心跳宣称在线。

Host完整验证大帧以后，由唯一接收线程按原序切成最多200证券的子批，交既有Native入口。原数值、价格/量额、分钟算法、同步Writer及文件格式保持。子批失败仍保留已发生的部分效果并停流，整帧不自动重放。该分片只属于接收适配边界，不新增Native/WT核心行为、数据库、运输线程或定时器。

验收覆盖6982证券冷写入、初始化期间持续全量回调、确认后的全量增量及心跳；源在线受理数与发送数、Native实际消费数分别核对。保持同一完整四owner正文、原NAP/独立观衡及正常有界关闭。固定源码/安装/策略/数据与SDK、真实QMT资格分别记录。
