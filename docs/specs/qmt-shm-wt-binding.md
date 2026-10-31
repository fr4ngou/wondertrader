# QMT共享内存与原生插件接入

账户能力及其v3组合profile由[QAR](qmt-shm-account-read.md)定义；本规格的通用observation=null、三B、Journal与wire职责保持。新增能力实现与真实来源按各自证据验收。

状态：accepted。范围：终端共享内存接入、原生插件消费及国信QMT运维材料独立归属。开发授权来自2026-10-22用户确认；实现与实际运行资格分别验收。

## 已核实的接缝

复用[原生能力目录](../development/wondertrader-capabilities.md)WT-D01、WT-T01、WT-T02的Parser/Trader扩展接口。WT-D10的ShmCaster是WT行情广播协议，与QMT已完成的认证消息协议不同。

已验证的源链为外部Broker客户端→终端外签名HTTP Host→pagefile共享内存→QMT原策略线程→原路结果。终端内使用Python调用券商API，WT侧交易插件使用C++。外部Host HTTP与已退役的终端内HTTP属于不同接缝。

源协议由交付源码`src/qmt_platform/common/local_transport_protocol.json`及对应Session/SHM实现定义。迁入时固定源摘要、许可证与生成关系；原工程路径只用于来源记录。运行、构建、配置生成和维护最终由本仓库制品承担。

## 要求

| ID | 行为及验收 |
|---|---|
| QSW-R1 | 消费已完成的代际、认证、可靠消息及结果身份契约；先复用已验证Host/Agent，原生插件消费其端点。直接C++重写共享内存内核需另有必要性、互操作及资源退出证据，不能只按结构体布局推导兼容。 |
| QSW-R2 | 初始仅开放有真实证据的`market.full_tick`；账户、历史、分钟订阅、下单和撤单逐项实现/验收，连接成功不授其他能力。当前Host的`order_ready=false`保持。 |
| QSW-R3 | C++现有终端HTTP codec要求独立capabilities路由及特定会话字段，当前Host不同；先建立版本化端点映射，再接Parser/Trader，禁止仅替换URL宣称兼容。 |
| QSW-R4 | I/O与券商调用线程分离，保留原策略线程执行、有界队列/容量/单一截止、代际隔离。退出先停止准入并唤醒/等待I/O，确认线程停止后释放view/句柄；超时保留所有权。覆盖满环、丢Event、半写、abandoned Mutex、代际变化及退出竞争。 |
| QSW-R5 | 结果未知保留原请求身份并查询原结果；不自动重发或回退旧终端HTTP。认证、私有凭证和对象ACL沿已有协议，日志/仓库仅存脱敏资料。 |
| QSW-R6 | 迁入Host/Agent必要代码、配对/安装/检查工具及国信安装、启动、停止、维护、升级回滚和排障手册。终态通信记录与WT订单/成交/理论持仓职责分别核对，不恢复旧平台完整数据库、资金账本或审批工作流。 |
| QSW-R7 | 先隔离契约/跨进程/异常测试，再以本仓库新制品进行获准只读实机验证；保留当前运行实例，真实交易及生产切换分别授权。框架核心改动继续先说明必要性并获批准。 |

## 独立连接包边界

Host包为`guanheng_qmt_shm`（Python3.10+），Agent包为`guanheng_qmt_shm_agent`（Python3.6.8+、仅标准库），分别发行wheel；Agent另导出白名单源ZIP。两包源码在`connectors/qmt_shm`拥有；Host只依赖明确版本的Agent和独立安装的HTTP/DTO库，不导入旧`qmt_platform`或`qmt_agent`。私有内部迁入保留来源/版权头及改动说明，不推断公开再分发许可。

采用源端012实际验证的SHM＋base control 1.0＋简单HostReadJournal分支：保留原Session/SHM wire、ACL、可靠CALL/REPLY/ACK、序列/信用/期限、原策略线程只读调用与必要DTO/政策。版本选择明确拒绝未支持的扩展，移除账户观察、资本/元数据/命令执行及旧平台聚合契约依赖。

HostReadJournal只拥有通信请求身份、派发阶段和原终态，维持同ID冲突、重取、重启不重发、容量及失败语义。其内嵌SQLite文件位于终端外Host，不需要PostgreSQL、Docker或数据库服务；不存策略资金账本，不作为WT订单/成交/持仓的第二套所有者。终端内Agent不读写该文件。

构造/生命周期公开接缝为`build_runtime`、`create_app`、`RestrictedReadAgent.start/tick/request_close/close`；部署接缝为离线`create_pair/verify_pair`。构造先准入配置，启动、就绪、停止与有界join分别表达；原线程stop只请求关闭，最终所有者确认线程结束后释放。配对创建使用新受控目录和受保护ACL，拒绝覆盖旧配对；生成/验证不启动终端或Host。

实际012简单Journal没有可供WT采用的认证来源会话接口；新的认证binding及终态来源关联须在独立Host拥有，与C++消费契约一起冻结和验收。无认证诊断health只用于故障观察，不能构造来源身份或授行情可采用资格。

## QSW-R8 认证bound-read最终契约

所有新DTO拒绝未知/重复字段、非有限数、错误原生类型和不支持版本；
schema_version均为字符串 `qmt.bound-read.v1`。GET拒绝body/query，POST拒绝query。
UUID请求ID沿原v1的36字符规范；Session/Host ID沿原control的32字符小写hex。
所有SHA字段为64字符小写hex。base64使用标准字母表、规范padding、禁止空白，
先核编码长度，再有界解码，解码后重新编码相等。

### Binding B

完整复用 `control_messages.host_binding` 的七字段及原validator：

```
{"schema_version":"1.0",
 "route":{"route_id":string,"executor_id":string,"route_epoch":integer},
 "transport_generation":hex32,"host_instance_id":hex32,
 "journal_generation":null,"observation_identity":null,
 "capability_sha256":hex64}
```

绑定只从已认证Session及受管route/profile形成；simple分支两项null固定。
binding_sha256=SHA256(原protocol.canonical(B))。B只含有界文本/整数/null，
不引入跨语言浮点canonical问题。传输保留B；C++逐字段校验、完整比较并验证摘要。

### GET /internal/v1/read-binding

已握手且未关闭：HTTP200，字段精确为：

```
{schema_version, binding:B, binding_sha256,
 read_profile_body_b64, read_profile_body_sha256, limits:L, order_ready:false}
L = {max_request_bytes:integer, max_result_bytes:integer,
     max_http_request_bytes:integer, max_http_response_bytes:integer}
```

read_profile_body_b64为**完整已认证runtime.profile原canonical UTF8字节**的规范base64，
read_profile_body_sha256为这些原字节的摘要，必须等于B.capability_sha256。
源runtime在原两项read_operations/execution_timeout_ms之外还加入control_profile，
因此只对两字段投影求SHA会改变真实Session身份。此处保留完整字节，不发送重复P对象。
C++先有界解码并校验字节SHA，然后解析read_operations/execution_timeout_ms和
control_profile.schema_version=1.0；初期只准full_tick和base control 1.0。
control_profile可能含poll_seconds浮点；C++不重编码整个profile来计算摘要。
未连接/正在停止/失败：HTTP503结构化error_code/error_message，不返回可采用ready值。
不使用无认证诊断health制造身份，不附加qmt_session_id。

### POST /internal/v1/bound-operations/{operation_id}

请求四字段：

```
{schema_version, binding_sha256, request_body_b64, request_body_sha256}
```

解码体为原完整八字段v1请求字节，按同一原validator准入；路径op必须一致。
request_body_sha256是这些原字节的SHA256。保留原字节，不通过DTO重建替换。
Journal原request_sha256仍是canonical({operation_id,arguments})的语义摘要，
两个摘要分别命名、分别保存，不混作相同定义。
新bound入口同ID只有**原body字节与admitted binding均相同**才允许返回原记录；
任一变化返回409。同ID的既有原v1记录只能GET审计，不由POST补写当前binding。
客户端正常流程只POST一次，未知送达后GET原ID；此规则同样适用只读请求。

准入前当前B须完整就绪且摘要相同，否则409 source_binding_changed、零派发。
HTTP202或200返回下述同一Response DTO，不生成另一份请求身份。

### GET /internal/v1/bound-results/{原request_id}

仅查Journal，不依赖当前已连接状态。未知ID 404；原记录存在返回202/200。
这使POST回执丢失、断连、Host重启后均可按原ID核查，GET不触发派发或重发。

### Response R

202和200统一精确字段：

```
{schema_version,
 request_id, operation_id, request_sha256, request_body_sha256,
 binding_status, admitted_binding, dispatch_binding, result_binding,
 state, result_body_b64, result_body_sha256}
```

state为 queued/executing/terminal；binding_status为 recorded/legacy_unqualified。
202时result_body两字段均null；200时为原Journal最终保存v1结果字节及其字节SHA。
原v1结果中的result_sha256按原算法保留，外层字节SHA覆盖**包含该字段的全部存储字节**。
现Journal get会decode并重新canonical；新增原字节读取接口，禁止该往返改写终态。
200中的v1 request_id/operation_id必须与外层一致。

新请求 admitted_binding=B。派发前 dispatch_binding 为null；完成同channel派发承诺时
记为B。真正从认证Session收到该结果时 result_binding=B。
Host自行形成queue_timeout/interrupted等终态，result_binding保持null；
不能把主机失败记录标成原生返回。保留dispatch_binding说明可能已调用。
原始无binding历史记录：binding_status=legacy_unqualified、三binding均null；
request_body_sha256可从原body准确计算，取不到原body时为null；结果字节及原摘要仍保留。
上述nullable字段须按binding_status/state执行同一validator，不以空字符串代替缺失。

C++只有在v1 ok=true、内外身份匹配、原字节摘要正确、receipt admitted binding与
dispatch/result binding全部相同、前后认证read-binding仍相同且ready时，才交给行情mapping。
旧记录或切代结果保留原件并返回StaleSession/未采用，不伪装成当前tick。

## QSW-R9 身份映射、锁及持久化

`SourceSession{provider=Qmt,instance_id=B.host_instance_id,
session_id=B.transport_generation,generation=B.route.route_epoch+1}`。
epoch+1可逆、正值且最大2**53，适配现MarketParser的generation>0约束。
完整route/profile仍保留及核验；UUID保持完整，不压缩进uint64。
这是Host/认证运输channel身份，未证明券商登录会话。每Host一次连接generation的
现约束保持；重启产生新host_instance_id，旧Journal记录不改为新实例。

runtime拥有一个binding/ready admission锁；Session握手后构造并校验深冻结B及完整profile字节，
在同锁内发布B然后ready，HTTP快照在同锁读取。关闭/失败首先同锁撤销ready；
已有B可留作诊断，read-binding不再返回可采用200。

锁顺序固定为runtime binding锁→Journal事务锁；Journal不得回调等待binding锁。
POST同锁核ready/B并事务保存原body、admitted B及摘要后返回；容量满原子拒绝。
dispatch同锁核当前仍为admitted B，事务写dispatch B/dispatching后才释放去I/O。
锁仅覆盖短校验和本地事务，不跨SHM等待/native调用。失配queued记录终态stale，
不迁到新channel。dispatch承诺后断连按原身份interrupted，重启不重派发。
结果收取携带本地Session冻结B，事务匹配原dispatch B才存原终态及result B。
终态bytes和身份元数据在同一事务提交，ACK/HTTP完成在提交后。
原终态再次读取始终返回原B，当前连接信息由独立read-binding取得。

客户端receipt在POST前先形成，包含原request_id/op/body字节SHA/语义SHA/B；
unknown/pending返回receipt；`resume(receipt, absolute_deadline)`只GET原ID。
初始调用从准入起一个steady绝对截止覆盖binding/POST/GET/末次binding，
用户另行主动resume是新调用窗口，保持原请求/原receipt，不延长原派发期限。

## QSW-R10 联合字节预算

公开硬上限：B canonical字节<=4096；完整profile原字节<=4096；原request<=65536，
同时满足原IPC `(max_frame-4096)*3//4`；原result<=既有Journal.max_result_bytes
(1024..2097152)；metadata除base64体实际编码总量<=16384。
HTTP请求仍<=runtime.max_frame且完整outer实际编码入限后才准入。
`max_http_response_bytes = 4*ceil(max_result_bytes/3)+16384`，binding响应<=16384。
解码前检查base64最大长度、解码后检查原体大小、JSON再执行既有结构/数值预算。
max_request_bytes发布联合最小值，max_result_bytes发布Journal上限；
HTTP客户端配置下限须覆盖公布响应上限，否则prepare明确拒绝而不截断。
三B副本元数据也计入Journal每条及累计通信存储预算；原max_records不删除旧记录腾位。
profile/DTO不会把额度从peer输入放大；配置来自受管安装。


Host配置另必填`max_journal_bytes`：部署owner声明可保留的通信逻辑字节总预算，精确整数、拒绝bool；至少容纳一份最大请求、最大结果及16384字节元数据，且不超过`max_records * (max_request_bytes + max_result_bytes + 16384)`。准入事务在原body实际字节之外为最大终态/三绑定元数据预留额度，达到字节或条数上限即拒绝，保留旧记录；读取旧结果不新增额度。该预算约束所声明的通信负载，不宣称限制SQLite物理页、WAL、索引、owner文件或磁盘总量。源端现有数据库及运行配置保持。

## QSW-R11 HTTP入口与整体关闭

Host的完整请求体接收同时受R10字节上限和一个`io_seconds`绝对接收期限约束，流式分块不能重置期限；超时在通信请求入账/派发前拒绝，断连和取消释放本次HTTP占位。GET的body/query限制也经过有界接收，不把慢body留在无限等待中。

Host配置必填`max_http_inflight`，精确整数1..128、拒绝bool，独立于IPC和Journal容量。离线配对工具、配置准入、普通run及配对启动入口保持同一值。优先使用固定Uvicorn版本既有并发/背压能力，按其实际连接、keepalive和任务计数语义说明边界；在必要的应用准入层限制完整处理中的请求，超额在读取请求体和创建通信记录之前拒绝。该参数不宣称限制OS监听积压、TCP总连接数或整个进程内存。

停止开始即撤销ready并关闭新业务准入，随后等待HTTP、lifespan及Runtime排空；停止开始至全部关闭共用一次`io_seconds+1`秒的monotonic期限，不能在graceful、lifespan或finally之间重置。普通run和配对启动必须显式设置有限graceful shutdown，并把剩余预算交给后继Runtime close。到期仍未回收须保留依赖所有权并报告失败，不用成功退出掩盖仍活跃的worker，也不重放未知请求。

实际独占进程验收覆盖：半body、持续慢分块、满HTTP占位及恢复、请求体超额、客户端断连、停止与新请求竞争、原请求已入账后的取消和原ID重取。核对退出期限、ready撤销、原线程实际调用数、Journal阶段及线程/句柄释放。禁止借验证停止、重配或覆盖现有012实例；这些约束仅适用于本仓库新连接包。

## QSW-R12 受限终端无文件启动

受限券商终端采用完整策略正文内存加载和内建mmap传输。Agent及其传递标准库源码在终端外冻结并嵌入配对策略，绑定模块/配置/许可身份；运行时通过私有模块表加载，不能用`spec_from_file_location`、外部包搜索、配置/数据库读取或动态DLL加载完成引导。QMT自身加载策略正文及SDK管理行情缓存属于平台边界，券商升级后单独实测。外部Host仍可使用文件、认证HTTP及通信Journal，保持单一所有者和正常关闭。

优先复用已交接的内存依赖打包器、builtin-shm Agent与Host安全创建端，迁入本仓独立制品；旧QMT业务包退出运行依赖。内存加载器覆盖完整传递导入、目标CPython3.6.8内置模块及许可，保持私有命名空间，避免改变QMT全局模块状态。旧Win32 SHM后端的帧/对象与新builtin后端分别进行版本、配对、预算和互操作验收，不能静默替换后端或将旧资格转授新安装。

验证必须覆盖：文件读取/网络/外部模块或DLL加载被拒绝时完整策略初始化和原线程回调；完整来源及依赖摘要；错版本/缺内建模块/篡改配对拒绝；双进程真实映射认证、半写/切代/容量/原截止与停止竞争、实际join和句柄释放；获准安装后在升级券商终端真实只读验收。旧磁盘加载与Win32后端的合成/账户QA只授其原环境资格；新内存模式保持独立制品与验收。具体来源与实施顺序见[交接核对](../migration/qmt-successor-source-handoff.md)。

### 显式运输与配对物料

新配置仅接受kind=`builtin-shm`、schema_version=`qmt.builtin-shm.v1`，精确字段为schema_version/kind/name/max_mapped_bytes/poll_seconds/windows_session_id。旧kind=`shm`保持原九字段；两类配置均无默认转换，install-008旧无版本builtin配置只作迁入来源，不能直接冒充本仓新配对。

新内存配对manifest版本为`qmt.shm-pair.v2`，原Host/Agent/政策/制品身份及qualified_in_qmt=false/order_ready=false保持，新增memory_runtime及CPYTHON-LICENSE.txt。生成器接收构建阶段从实际目标CPython3.6.8取得的`qmt.memory-sdk.v1`元数据（解释器/DLL摘要、完整内建模块列表和Lib来源）及固定许可；生成器不自行启动解释器、Host或终端。版本、字段和实际二进制/源码/许可不符时拒绝。CLI新增显式`--memory-sdk-manifest`及`--stdlib-license`，旧磁盘配对不接受这些材料。

运行物料身份`qmt.memory-runtime.v1`分别保留原文件字节SHA、实际发射UTF8文本SHA、提取/能力桥生成器SHA、完整闭包及生成正文摘要。原始CRLF与规范文本身份分别命名；生成文件按实际编码字节写出。正文仅ASCII，以Unicode转义保留原源码，避免QMT编辑器GBK保存改变中文。模块实际加载前再次核发射源码SHA；运行时核目标3.6.8及完整内建模块列表。离线verify从本安装Agent和SDK源码重建全文，并逐字节核对策略及许可，禁止只核manifest自报摘要。

私有加载器只注册自己的源码模块表，保持已有sys.modules项；解释器加载真正内建模块产生的自然缓存单独记录。该机制装配受信源码闭包，不能当作恶意Python或其他策略的完整沙箱。标准库能力桥限定os/文件入口、regex替换及inspect静态属性读取；inspect.getattr_static与其辅助从实际目标CPython原文提取。datetime保持原生精确类型，历史协议固定十四位整分钟日期由原参数边界直接构造并校验日历，不依赖原生strptime隐式全局导入。

私有闭包保持解释器已有 warnings 过滤器、注册表及宿主线程退出哨兵。warnings 使用目标CPython源码自带的纯Python状态分支，私有加载白名单排除共享 `_warnings`。加载闭包的宿主线程按CPython原生 `_DummyThread` 记录借用身份，不能认领其退出哨兵；私有新建I/O线程仍沿原 `Thread` 启动、退出及join语义。线程源码仅在生成阶段精确变换模块级主线程记录，保留原文件与变换生成器双身份。私有线程模块不注册到解释器全局模块表或退出回调，闭包拥有者显式关闭并join自己创建的线程；借用线程由平台负责，私有main_thread为借用记录，禁止对其join或调用私有 `_shutdown`。验收在独立目标解释器的真实宿主Thread内加载完整生成策略，确认宿主原退出锁释放、join完成；同时覆盖私有新线程正常join与warnings过滤优先级/内容保持。

源复用发现的连接成功出口原截止复核及异常关闭资源保活在本仓自有连接层修正；跨线程只发停止请求，同I/O owner收尾。线程join成功和资源完整释放分别核实，部分连接失败也保留owner，不能靠关闭标志跳过剩余资源。双进程发布原子性、实际复制实现与目标内存模型必须由对应制品证据证明，架构字符串和HMAC不能替代。

## 实施与交付

1. 固定实际协议、已验操作与源码/制品身份，迁入运维正文并登记工具缺口。
2. 迁入最小独立Host/Agent与端点适配，消除旧业务仓库运行依赖；纯通信与业务职责分开。
3. 原生C++ Parser首先接行情；账户四查询和执行分别沿原TraderAdapter扩展。
4. 独立审查、独立安装、实际只读来源和异常恢复逐项归档，最后更新发行手册。

源端与WT接线的实际资格分别见[接入核对记录](../evidence/2026-10-22-qmt-shm-development-entry.md)和[独立安装/联调证据](../evidence/2026-10-22-qmt-shm-native-connector.md)。历史扩展另按[QH](qmt-shm-history.md)，共享信号/分配纯计算验证与本通信资格分别验收。

## QSW-R13 正式入口的完整业务能力

正式交付必须包含行情/历史、账户资金（含可用金额）、持仓及可卖数量、委托和成交查询，以及下单与撤单。只读探针是阶段验证工具，不能以行情连通代替正式交易接入。账户查询沿[QAR](qmt-shm-account-read.md)的四类精确读取；交易适配复用WT原生ITraderApi、TraderAdapter及订单/成交/持仓职责，命令身份、未知结果核查和异步回报契约先明确再实现。不得只把白名单或order_ready改为true来宣称具备交易能力。

正式能力可由同一受管策略/Host按显式版本组合承载，不要求为每项功能长期多开策略。本条确认完整产品范围，不改变原只读版本及运行配对，也不授权真实委托测试；真实测试按明确账户、环境、标的与数量执行。WT框架新增修改仍须先说明必要性并取得批准。

## QSW-R14 正文展示方式的用户决策

状态：superseded。此前用户希望沿同一策略采用可读正文；核实原交接策略也使用嵌入加载后，用户决定以最快完成为准，继续已有实测方案。可读正文转换停止，R12现有加载器及其精确版本证据保持。正式能力仍按R13补齐账户查询、下单及撤单；当前只授已验行情快照和账户四查询，下单/撤单未接通、未获真实测试资格。此记录不要求新的策略名称或转换模块源码，不扩大真实委托授权。

## QSW-R15 策略回调的命名空间发布

生成的内存策略同时支持普通模块执行和 Python 的 exec(code, global_namespace, local_namespace) 分离执行。声明的每个回调均须以原函数对象进入调用者可见的局部和全局命名空间；只读入口四个回调、交易入口七个回调共用同一个生成 owner。显式顶层别名只发布既有函数，不包装、不再执行回调正文，保持函数私有 globals、原 ContextInfo 与策略线程检查、首次初始化、timer 注册、订阅、关闭和异常语义。原磁盘加载入口的生成字节保持。

合成回归须通过真实公共生成器构建正文，在相同与分离命名空间执行，并模拟执行正文后先合并 local_namespace 到全局、随后从 local_namespace 绑定回调的公开 SDK 消费路径；分别实际调用 init、timer、handlebar、stop，核同一函数与上下文身份、重复 init 拒绝和初始化失败的原关闭路径。目标 Python 3.6.8 只执行由终端外生成的纯合成正文，不导入现代 Host 源或执行实际 SDK 入口；文件、网络、真实账户及委托调用保持零。

模板变化形成新的生成字节与源码身份。旧安装、旧配对、私有正文和运行实例保持各自冻结版本；新 verify 仍按其绑定的实际安装和生成器重建全文。不能为了套用旧配对而放宽逐字校验。合成回调绑定通过只证明该公开加载模式兼容；实际券商终端的加载路径、限制和只读联调另行验收。


## QSW-R16 受限解释器的函数模块身份

内存策略在执行 runtime 与回调正文前，先建立合法的脚本模块名：继承宿主全局字典中已有的非空字符串 `__name__`；缺键时使用标准脚本名 `__main__`；值为非字符串或空字符串时在加载前明确拒绝。runtime 所在宿主全局与私有 entry 全局共用该模块身份，使所有在其中定义的函数（包含内部校验函数）在创建时即具有合法的字符串 `__module__`。模块身份由函数定义环境拥有，禁止逐个回调事后修补、修改券商 DLL 或放宽终端权限。

验证包含正式生成器和正式只读／交易回调正文、目标 CPython 3.6.8、宿主已有模块名及缺键、非法值加载前拒绝、内部函数与回调的字段、原初始化／定时／停止／重复初始化约束。隔离元数据回归与终端真实恢复分别记录；策略重新生成后继续执行原完整字节身份与配对核验。QSW-R15 的回调局部发布保持独立，不能据此修改冻结安装。


## QSW-R17 真实账户持仓的券商查询权威

真实账户持仓总量、可卖数量及资金采用券商查询事实。QMT正常交易接入必须显式选择已批准的 `position_by_query` 模式；成交、委托和撤单回报保留WT原生策略通知及统计职责，并请求刷新券商查询，禁止对账户实际持仓表执行增减、冻结或解冻算术。完整有效持仓查询在原WT持仓所有者中整批替换；查询异常或非法批保留原观察并呈现未刷新状态。成功空批与查询失败分别表达；源登录、账户一致性、缓存时效和空结果资格必须由真实来源证据核实，不能用连接健康代替。

该要求保持WT原生持仓唯一所有权，不新增资金持仓账本或人工实盘资格。WT策略目标、策略原生状态与未完成委托继续各守其职责，不能作为券商真实持仓写入。现有默认模式兼容保留，正常QMT接入配置与完整接线须分别验证；已批准两文件模式的隔离通过不代表生产已启用。

此要求来源于用户2026-10-26再次确认，复用[已批准持仓模式](../evidence/2026-10-26-native-query-position-mode.md)。订单剩余量、订单统计及待确认委托沿QSW-R18的独立职责与已批准范围执行；持仓模式的批准不扩大到其他框架行为。


## QSW-R18 订单查询优先与已批准框架边界

用户2026-10-26决定优先采用券商订单查询结果；先验证现有Parser／Trader／ExecuteContext扩展接缝能否让正常执行消费真实订单状态与剩余数量。查询是最新已取得的券商观察，成交回报继续交付WT策略；不得在同一累计剩余量上再次扣同笔成交。未完成提交与未知结果沿已有命令所有者核查并保留原身份，不推导空查询等于委托不存在。

用户2026-10-27已批准[券商订单同步原表方案](../migration/native-order-query-sync-proposal.md)中TraderAdapter.h/.cpp两个框架文件。显式order_context=query_first且position_by_query=true时，完整成功ORDER查询发布到WT现有活动订单表、未完成数量和订单统计；重复查询按本批刷新，迟到成交保留原通知及成交统计，并请求后继查询，查询余量保持券商值。原getOrders/getUndoneQty/cancel使用同一原表，自有派生上下文删除独立订单投影；cancel/doCancel正文和原频率控制保持。缺省/native继续原路径，模式初始化后固定，非法组合在初始化拒绝。

已实现主路径与替身验证见[订单同步证据](../evidence/2026-10-27-qmt-native-order-query-sync.md)。本批准覆盖上述两文件和对应自有接线、测试；完整恢复、真实终端交易与生产启用分别验收。新增其他框架行为继续先提交实际问题、已核原生接缝、必要性、最小范围及配置分流，再取得用户批准。

适配继续复用WT原生执行、订单、成交与持仓职责；不构造第二资金持仓账本，不通过修改成交量、备注、查询行或虚构包含标记使测试通过。订单查询原始观察与执行器实际采用结果分别验真，单次查询成功不证明执行判断已正确。


## QSW-R19 框架行为的配置分流

状态：accepted；依据2026-10-26用户要求，框架行为改动由配置选择原路径或适配路径。实施遵循[长期规范](../development/upstream.md#框架行为的配置分流)。本要求补充QSW-R17/R18，不扩大框架修改批准范围。

现有已批准持仓模式使用position_by_query：缺省/false保留原路径，true采用查询持仓模式，初始化后固定，禁止运行期热切。普通配置入口和公开外部初始化入口分别验收。已批准订单模式沿QSW-R18由order_context=query_first显式选择，要求position_by_query；缺省/native保留原生行为。插件、工厂和宿主必须实际传递该配置，并与同批重编的TraderAdapter组合验收；自有接缝单路径通过只证明该次组合。新增框架行为的配置键、状态恢复、双路径验证和回退仍需按对应必要方案获得批准。

验收：缺省与显式原生行为分别对照固定上游；显式适配通过对应券商查询完整链；非法配置明确拒绝；重启后按记录的同模式恢复，未决委托保持原身份。已批准其他框架差异逐项核配置覆盖，调整前登记范围及必要性。


## QSW-R20 常驻连接与系统统一启动

状态：accepted；依据2026-10-26用户确认。实现及现场资格分开登记。

- R20.1 系统统一管理终端外Host；QMT未登录或策略未运行时持续显示等待连接。Host创建映射和认证各有有限期限；等待首个对端不要求用户在60秒内操作。WT-O01/WT-D01/WT-T01原生运行及插件接缝保持；WT-O04可选wtpy不作为依赖，自有券商协议生命周期由连接包负责，不修改WT核心。
- R20.2 显式常驻只读入口组合原HostReadRuntime、RestrictedReadAgent、原认证Session/控制协议及通信Journal。原单连接入口默认行为和已有配对字节保持。配置选择在构造时固定，拒绝隐式开启交易；首切片只授只读恢复。
- R20.3 Host是单一代际管理者；旧HTTP准入撤销后，等待已进入的调用完成，原I/O和域worker退出、view/句柄及Journal关闭确认后，才能建立新代。关闭失败保留原owner并报故障，禁止同时持有两个活动映射/Journal写者。新连接重新生成nonce、认证并产生新binding；客户端重新获取binding。
- R20.4 QMT Agent恢复只在原ContextInfo线程的tick推进；原实例的队列取消、I/O退出及资源关闭确认后，按显式间隔创建新实例。stop关闭恢复准入；QMT回调不等待存储或跨线程释放映射，不读取外部包/配置、不联网。
- R20.5 常驻等待只改变连接生命周期。单请求的队列/执行/I/O/关闭预算及原请求身份保持；旧请求结果沿原通信Journal查询，旧命令、未知委托和SDK调用不自动重放。已明确识别的认证/配置/Journal/资源故障显示faulted，普通运输断连允许重新连接。原Connector把未认证的空或陈旧映射作为有限等待处理，等待超时无法识别全部错误密钥/错误配置；保持等待不授认证成功，部署必须另行核配对身份。已认证旧对端占用属于暂时运输不可用，不覆盖其nonce/关闭位，等待原Host换代。
- R20.6 验收覆盖：超过原连接期限后首次连接；QMT/Host先后启动；至少两代真实WinSHM认证与原线程读取；旧binding拒绝、新binding变化、旧终态可查；断连及关闭并发中无重复源调用、无旧代准入；资源未释放禁止重连；等待状态退出有界。单元、合成WinSHM、实际QMT、常驻安装与登录自动启动分别登记，不能以API存在代替系统入口交付。

长期连接所有权见[ADR-0013](../architecture/adr/0013-qmt-connection-lifecycle.md)。系统启动器及最终策略生成/安装的接线，在具备对应实跑证据前保持pending-verification。


### R20.7 常驻配对与独立安装

显式connection_lifecycle精确为{schema_version: qmt.read-resident.v1, mode: resident-read, reconnect_seconds: 有限非bool的0.1..60秒}。None保持原v1/v2单连接生成路径和原回调字节；resident仅builtin-shm只读，manifest固定qmt.shm-pair.v3，增加connection_lifecycle及memory_runtime，config_sha256覆盖Host配置、去秘密Agent配置和lifecycle。v3策略闭包根为guanheng_qmt_shm_agent.reconnecting_read，回调仍保持原ContextInfo/run_time/线程和函数模块身份。

verify只从受保护材料读有界原字节，AST解析唯一字面量，不exec策略或Host正文；重渲染并逐字节核v3 Host与策略，核manifest及lifecycle/profile/policy/凭证角色一致。重算files SHA不能使不匹配的生命周期正文获得资格。v3的build_paired_runtime由同次验证快照构造，返回(runtime,http_keys,identity)，identity仅pair_manifest_sha256/pair_config_sha256；构造不启动线程/SHM/SDK。原policy字节经统一纯准入，不在构造阶段重读变化的配置。

CLI pair/run/check增加显式生命周期材料，新增run-pair只接受v3；旧命令默认行为保持。复用固定Flit/hash requirements/离线wheel安装/pip check及独立角色身份；Host-only只构建Host/Agent，安装器缺省仍两角色，依赖不在启动时解析。工程测试安装、正式独立发行与实际终端装载分别留证。

### R20.8 观衡统一管理独立Host进程

所有权修订：本节观衡App托管Host的要求已由[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)取代，后继实施见[WRI](independent-wt-runtime.md)。原Host descriptor、控制收据、隐藏Job和资源验证继续复用，运行owner归WT独立部署单元；以下App接线保留历史实现语义，不作为最终部署目标。

观衡显式配置独立部署descriptor及外部可信SHA，默认空值关闭。descriptor schema=qmt.host-process.v1，仅包含pythonw/pythonw_sha256/pair_directory/pair_manifest_sha256/installed_agent/control_root/startup_seconds/stop_seconds/max_output_bytes；路径、SHA、预算和只读v3身份严格准入。App不import Host包，复用原ProcessJob创建期Job及隐藏进程、ThreadOwner和App lifespan。既有Journal owner锁及Host mutex持唯一写端，不新建实例账本。

Host外部控制目录独占新建且从创建即私有DACL。ready.json schema=qmt.host-ready.v1，含control_id/pid/pair_manifest_sha256/pair_config_sha256/listen_host/listen_port，必须原listener及HTTP实际就绪才写；它只授Host就绪，不授QMT连接/账户/交易资格。venv转发器的ready PID可与Job root不同，必须保有实际ready进程句柄并核本Job成员，不能用PID快照替代。

stop.json schema=qmt.host-stop.v1，含control_id及同机绝对monotonic deadline；Host在QMT外读取，验证有限结构和原身份后沿同一最早截止停止。closed.json schema=qmt.host-closed.v1，含原control_id/pid/两pairSHA、status(stopped/failed/incomplete)、runtime_closed/monitor_joined/error_code固定分类。父必须同时核正常closed、实际exit0、Job树0、双EOF、真实join及句柄关闭，才授优雅退出。首管道日志仅私密有限前缀，超额继续排空并触发停止；公共投影不含原字节或异常正文。

App先停止账户消费者，再在同一个应用关闭D内给Host保留其显式stop预算。启动中取消接管晚返回owner，禁止第二Host；意外退出显示故障并保留其他观衡功能，不盲目重启或接管陌生端口。关闭失败保owner；TerminateJobObject及父死亡KILL_ON_JOB_CLOSE只作异常收口，不记为优雅退出。Windows登录自动启动留待安装及真实终端验收，不因CLI存在而擅自设置系统任务。


### R18.1 同实例整次提交组准入（首片 accepted，完整生产恢复未完成）

显式 order_context=query_first 的自有派生上下文在调用原 WT Local/base.buy或sell前，通过自有StandardSubmission固定POD接口认领整次同步group。缺省/native继续原路径；配置在init固定，禁止热切。group覆盖一次base拆出的全部真实Entrust，下一次tick/重入在base前得到明确Blocked；错线程拒绝，不持管理锁跨WT/SDK/SPI。查询getUndoneQty仍采用完整真实ORDER，空批保持0，不生成虚拟挂单或金融账本。

Standard原Identity保留group及AwaitBrokerObservation。SDKReturned只退休通信阶段：原Insert收据在settle_write/settle_audit同锁统一move至对应Identity并转移原charge；Unknown只有原Pending拥有收据。先到的真实ORDER/event证明不能被SDKReturned回退。只有精确NotSent/DefinitelyNotCalled可解除该子责任；空查询、超时、SDK返回及未闭合的终态成交包含性不解除。部分子单已受理后，后继失败或返回vector异常必须保留已受理身份和原UUID，不能重新POST。没有group的query_first raw orderInsert明确拒绝；旧normal/stock中直接raw insert的query_first证据需重新通过组门验证，不能沿旧输入转授。

实例只保一个同步ActiveGroup，历史关联来自原有界Identity表。实际sizeof/原bytes计费；超过原额度在准入或实际子单边界背压，不能声称整个base调用为原子交易。组内stop只撤后继准入；同线程release不等待尚未返回的base调用，end归还引用后继续原drain/join。Closed保未决Identity收据费用至真实destroy；资源退出与金融责任分别表达。

首片仅授新临时真实Journal的合成链：原S4、多子单、部分失败、重入/错线程、真实cancel身份与Pending/Unknown回归。初始空Identity/空ORDER不构成启动恢复证明。完整一般部署仍须原Host有界命令恢复清单、单活动writer、重启GET原UUID及终态成交包含性合同；本片不新增Host未知协议，不授真实交易或恢复完成flag。接口/责任细节固定于build/qmt-order-gap-group-contract-001/CONTRACT.md，后继实现须保持该边界。
