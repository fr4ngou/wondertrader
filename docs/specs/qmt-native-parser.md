# QMT 原生行情插件持续接入

类型：功能最终规格。状态：accepted，落实已确认QMT HTTP优先与原生公开插件适配；前缀 QNP。目标是原宿主加载ParserQMT并连接后，持续接收来源合格的快照。既有通用MarketParser、HTTP协议、原WT框架及交易权限边界保持。

## QNP-R1 接口与职责

ParserQMT工厂创建自有QmtPollingParser，实现原IParserApi。init读取配置，connect启动一个拥有线程；该线程创建、prepare并持有QmtHttpClient/QmtHttpEndpoint与MarketParser，连续有界pump，再通过原IParserSpi向宿主发送行情。标准DLL加载入口及deleteParser保持ABI。通用显式pump路径继续供ManagedRuntime使用；持续运行能力由本插件提供。来源仍为Qmt，只调用原只读health、market.full_tick及结果认领，不发委托、撤单、行情下载或订阅QMT推送。

每实例一次init与一次connect；重复connect在同一次运行期间幂等接受，已停止/失败实例须外部管理者销毁并创建新实例，不静默重连或接纳新会话。connect返回启动命令受理，isConnected仅在来源准备、订阅与MarketParser连接成功后为真。运行错误停止新行情并向宿主报告Close及固定脱敏诊断；来源代际变化沿原HTTP校验拒绝。完整业务恢复及持久状态由既有owner负责。

## QNP-R2 受管配置

原宿主配置id/active/module/check_time/filter/code保留；新增qmt对象为唯一插件配置，未知字段拒绝。qmt字段：base_url、key_id_env、hmac_secret_env、timeout_ms、max_response_bytes、poll_interval_ms、batch_limit、subscription_limit、profile。凭证通过合法环境变量名读取，禁止明文配置。profile字段与QmtHttpProfile一致：version/source_license/time_encoding/minute_boundary/volume_to_shares/amount_to_yuan/full_tick_cumulative，完整验证后生效。只接受HTTP字面回环或正常验证HTTPS根URL；不使用启动延时替代宿主就绪证据。

timeout_ms默认5000、1..30000；max_response_bytes默认16MiB、256..16MiB；poll_interval_ms默认1000、10..60000；batch_limit默认32、1..200；subscription_limit默认200、1..200。订阅明确到SSE/SZSE与六位证券，支持原MarketParser认可的STK/ETF/IDX标准代码映射；非法/超额整批拒绝，原集合保持。init无网络，未配置connect失败。凭证、异常原文和源账户身份不输出日志。

## QNP-R3 轮询与快照

worker是所有HTTP和MarketParser生命周期的唯一调用线程。控制线程持有受限目标订阅集合，worker在每轮边界应用当前集合；更新使用集合替换/版本，无无限命令队列。没有订阅时等待控制变化。每轮网络最多batch_limit个证券、共用timeout_ms；返回后用可唤醒等待控制轮询间隔。

轮询接入层按证券保存当前来源下最后接受快照。同一来源、同一时间且字段相同属于无新数据，不重复投递，也不导致断线；同一时间字段冲突或倒序明确报错隔离。比较按字段而非含padding的结构体字节。新的时间经过原MarketParser验证成功后才能确认水位；未知回调效果停止接收，不重放。订阅移除后不新准入该证券回调，已进入宿主的回调允许完成；重新加入保留本实例水位，防止同快照重放。水位表受配置订阅容量限制，不能靠不断换证券无限扩张。

## QNP-R4 并发与退出

worker不持控制锁调用HTTP、MarketParser或宿主SPI。SPI回调固定worker线程；回调可查询状态、改变目标订阅、请求disconnect/release，不能同步等待自身线程。其他线程的stop(timeout_ms)关闭准入、唤醒间隔等待并有界等worker清理与join；回调中的stop返回Pending，外部线程随后确认完成。停止期间既有快照回调可完成，返回之后不再启动新回调；终态Close属于生命周期收尾。

宿主可以retain行情对象并在插件worker停止后读取和release。向宿主投递的对象必须拥有独立于worker线程内存池的存储；通过自有WTSTickData派生对象及原WTSObject原子引用计数实现，保持原API和框架源码。通用MarketParser产生的线程池对象仅在worker内部借用，适配边界负责转为跨线程生命周期对象。

HTTP异步回调属于停止依赖。WinHTTP请求返回、HANDLE_CLOSING通知进入或插件worker准备退出，均不能替代最后回调返回的证明。客户端使用系统session完成通知，保留有界清理状态；QNP停止成功必须包含该依赖已排空。外部停止截止到达而系统回调尚未结束时，返回未完成并保持worker、客户端、对象和DLL有效；之后继续确认，禁止通过固定sleep或永久pin掩盖清理缺口。订阅临时集合也受容量约束，输入批次逐项校验并在越界时立即整批拒绝。

内层MarketParser断开时立即关闭QNP准入并保留错误码；QNP只在HTTP依赖排空后向外发布一次终态Close。Close回调自身仍在worker内，完整join确认以外部stop成功为准。

release在有界停止成功后清理SPI；停止尚未确认时保持对象和SPI依赖，deleteParser仅成功stop后删除并清空引用，否则保留引用。直接C++销毁须满足外部停止已完成；回调内销毁禁止。DLL和依赖保持至worker结束、对象及所有宿主仍持有的相关对象释放。原宿主销毁顺序及其内部ticker线程另行举证，不把插件stop成功等同整个WtRunner安全退出。

## QNP-R5 完整接线与验收

验证真实回环HTTP协议→默认ParserQMT工厂→原ParserAdapter→原CTA宿主，包含配置正常/缺失/错误认证、同快照轮询、新时间、同时间冲突、倒序、源身份变化、源超时、容量、并发订阅、回调停止、外部stop等待与多次释放。原完整WtRunner加载及ticker分钟事件单独验证，结果同时记录来源、历史就绪、on_bar与on_schedule；缺历史时不得推定原ticker已暂停策略计算。运行器核心不足以完成预期时提供原样复现、具体影响与替代方案，再按用户边界申请最小修改，批准前不改核心。

所有终端/账户保持原状态；隔离测试可启动独立子进程。新增编译目标、配置说明、模块/操作文档、独立full审查及搬迁包需要交付。生产常驻、正式来源资格、交易恢复与真实业务入口按总验收地图继续，不能用本插件测试替代。

## Retained v6 开盘前轮询与准备等待

显式 ParserQMTHostRetainedV6 在已有 worker 内保持两类安全等待。prepare 尚未取得绑定时，仅原只读 read-binding 的固定超时类别（`qmt_host_source_reconnect_deadline`、`qmt_http_deadline`、`qmt_host_deadline`、`qmt_http_exchange_failed`）以及 `IoError/qmt_http_exchange_failed` 沿 poll_interval_ms 重试准备；每次沿原 timeout_ms，停止可中断轮询等待。准备不派发 SDK，不迁移已准入会话；其它准备错误原样终止。

完整原快照在来源北京时间09:30前、open=0、volume/amount=0、lastPrice>0、high=low=lastClose>0，表示当日 OHLC 尚未形成。完整证券范围、必需字段、数值有限性和时间仍须校验；该行保持原始字段且本轮不交付WT tick，其它已形成行正常投递。原结果完整持有及消费ACK保持，后继按原轮询请求读取有效行情。其它非法OHLC、缺字段、负量额、非零成交配零open均硬失败。

retained v6 轮询器自身发现证券时间倒退或同一时间的完整快照内容变化时，发布行情断开事件并保留原已交付水位。原只读结果已消费且端点释放后，worker 沿原轮询间隔重新认证和建立端点。只有同一来源会话的冲突证券出现严格更新并通过原校验的报价后，才重新发布连接并恢复行情投递。等待期间隔离整轮报价；同时间冲突不覆盖水位。上游身份冲突及下游结果未知仍保持终止。行情端点恢复不重建策略、账户或执行账本。

已登记的本地 `qmt_host_pump_deadline` 只结束当轮：此分支尚未派发本批读请求，或已确认消费且剩余行情未送出。retained worker 沿原间隔在同一端点继续，保留已接受水位。原读结果和消费确认的等待仍由端点持有，下一轮仅续核原请求。

retained Host端点在返回值没有收据时，Common保证尚未进入本批POST。此时容量Pending沿同一端点等待；已登记的运输超时、运输故障及500/502/503暂不可用转换为提交前Pending，保留固定原原因。已持有收据则继续原结果或消费ACK，不能重发新请求。轮询装饰层识别这些明确等待类别，不让通用MarketParser断开；等待按原poll_interval_ms继续，停止可打断，原请求期限不延长。身份冲突、坏数据、下游SubmissionUnknown及其它未登记错误保持终止。

运输故障导致Common的ready失效时，已完成初次准备的端点继续进入原读取方法，精确匹配原绑定后恢复ready。提交前发现同一路由、执行方、路由代际和能力摘要下签名传输换代，可接续新传输。成功结果的最后绑定检查发现同样的换代时，原请求的派发绑定、结果绑定、结果正文和摘要必须先通过原核验；原端点仍按旧来源校验快照字段，成功后丢弃该笔旧行情。保留原收据确认消费，确认前不提交新读。消费已提交但响应丢失时，沿同一原编号和摘要重确认；只有完整的专用已回收响应可结束原责任。换代保留各证券已交付时间水位，合格且更新的报价才恢复连接。路由、能力或原结果证明冲突按原错误处理。

运行阻断在清理依赖前记录 ERROR，包括阶段、固定原因、错误码、来源代际、订阅/已接收证券数、原轮询预算和处置。报价冲突附证券及前后时间、价格、累计量额；同一等待按原因变化记一次，重新收到合格行情记录恢复。日志只包含允许的诊断字段，源报文、凭据、账户和任意异常文本保持隔离。验收使用冻结开盘前/有效快照经过原C++映射、原HostEndpoint和原PollingParser，SDK客户端为无网络替身，验证本代先0后8行情、诊断字段、消费责任及有界停止。
