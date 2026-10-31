# QMT HTTP 原生只读交易通道接线

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：功能规格。状态：accepted，待实施。前缀：NQH。需求依据：完整观衡适配、HTTP优先、原生重合能力全部复用；实现范围仅自有插件、宿主及测试。源码、隔离开发、真实来源、运行安装与发布分别取得证据。

## 目标、复用及所有者

在已有[NQB](native-qmt-readonly-bootstrap.md)的同一个TraderQMTReadOnly中增加显式`qmt_http`来源，复用[QRT](qmt-shared-read-transport.md) Account域，沿固定原TraderAdapter的持仓→委托→成交→资金顺序完成初始化。原生能力为WT-T01/T02/T08/T09；职责和限制见[原生执行模块](../modules/wondertrader-execution.md)。被动宿主读取原getPosition、原订单统计及资金通知，不连接执行器或策略，不新增持仓归约器、订单账本或数据库。

上游固定08b230dd05facf6d650d949bfe51054115a2ecb1。构建使用原Git blob，当前脏TraderAdapter不进入输入；不修改WT接口、核心、线程或持久格式。fixture来源和Diagnostics v1保持各自原协议；HTTP新增行为由本文唯一规定。QMT源唯一规范为其仓库的`qmt-account-query-context.md`及`qmt-native-public-fields.md`；源码候选和已安装版本分别核验。

| 所有者 | 职责 |
|---|---|
| QMT原执行/Queue/Journal | 实际账户绑定、原生查询、逐请求来源/完整性及原终态 |
| QRT Account | 签名、health/capability、单POST/原ID认领、总截止、原响应及实际回调排空 |
| 自有HTTP来源适配 | 有界envelope校验、原字段到规范化记录、每批证据与可用性；不调用SPI |
| 插件worker | 独占QRT及其创建线程，锁外网络，只交付有限值结果 |
| 宿主owner/pump | init/run/API/SPI、基础资料查询、整批WTS构造、诊断和关闭；回调期间不持队列锁 |
| 原TraderAdapter | 原四查询状态、持仓合计、委托/成交统计和ready/lost；不承担来源证明 |

## NQH-R1 配置与连接

来源必须显式选择fixture或qmt_http，禁止静默回退。HTTP要求显式账户预期、environment、`currency=CNY`及`profile=cny_cash_shsz_v1`；预期账户仅校结果，不作为请求参数选择账户。profile限定普通SH/SZ现金股票/ETF、股/份数量与人民币金额；不授权信用、衍生品或其他币种。currency来自显式绑定配置，若行提供币种则必须与已核值一致，诊断区分配置声明与源行事实。

HTTP连接沿已有`base_url/key_id_env/hmac_secret_env/timeout_ms/max_response_bytes`约定；凭证从命名环境变量取得，不写配置示例、日志或诊断。所有请求由固定Account域发出，不提供任意operation/参数透传。请求只含stock、对应datatype、scope=account。

init只完成本地配置校验、注册及启动等待任务的worker；connect建立一次整轮steady_clock绝对截止并排入Prepare任务。worker在收到该任务后创建唯一Account QRT并prepare，prepare也计入整轮预算。成功后冻结SourceSession值副本，并把成功控制事件入队；失败不发成功Connect/Login。run返回后owner pump才交付Connect。原Adapter同步调用login时只排Login控制事件，后续pump交付成功Login(交易日0)，再由原Adapter触发首个query。停止或整轮超时后的成功晚事件丢弃。

登录成功只表示只读来源传输可用，实际账户与单批资格继续在查询结果核验。v1源交易日为null/unavailable，HTTP登录用0作为明确unknown ABI哨兵，诊断/展示为不可用；fixture原精确交易日规则保持。不得拿服务器完成时间、本机日期或任意一批日期补造来源交易日。

## NQH-R2 逐批完整性与身份

每批必须同时满足QRT成功、HTTP200、terminal/remote_ok、本次request_id/operation_id匹配；envelope经有界严格JSON解析。观察版本精确qmt.account-query.v1，query精确stock/本datatype/account/strategy_name=null；data为数组、complete=true、truncated=false、reason=complete、row_count等原数组长度，ACCOUNT恰1行。None、旧无观察、错误、202或未完成认领不变成空成功。

source的agent/session/generation等于本worker冻结的QRT SourceSession；账户/environment等于显式预期。四批保持同一绑定和来源代际，执行区间分别保留，不要求共同柜台事务、同一时刻、snapshot_id或旧reconciled。行若提供account ID，须与本次观察一致。原条数在去重前核验，实际交付条数另记。

执行时刻须为合法UTC RFC3339（Z或+00:00，保留最多6位源小数秒），保留原文本与精度，只表示服务器执行及转换；不作为证券事件时间或券商交易日。不比较本机/服务端墙钟以替代steady_clock截止，也不把可能的服务端时钟回拨伪装成原生事件次序。原result_sha256保留为来源证据；未经跨语言规范化验证不宣称校验最终HTTP全文摘要。

## NQH-R3 证券、数量及持仓

证券以原m_strInstrumentID和m_strExchangeID映射，六位代码保留前导零，SH/SZ显式到SSE/SZSE，必须命中原BaseDataMgr合约。股/份整数不乘100、不要求整手；拒绝布尔、字符串数字、分数数量、负数量及超出double精确整数范围。市场/合约冲突及必需字段矛盾在SPI前失败。

持仓必需m_nVolume=V和m_nCanUseVolume=A，0≤A≤V。HTTP首版固定aggregate-only，pre=V、new=0、availPre=A、availNew=0；这些是合计ABI投影，不授真实今昨。原Adapter的total/valid四种读取与V/A独立oracle一致；V-A表示当前不可用，不称委托冻结。m_nYesterdayVolume保持昨夜原值，不据此推当前剩余昨仓。原fixture精确拆分场景继续原定义。

成本、均价、浮盈、真实冻结/在途量、市场价值各自带可用性。成本/盈亏等按字段语义接收有限有符号值，避免以一刀切非负规则丢失真实负成本。只有口径已核的均价/成本才能填其对应WT槽；缺事实用ABI中性值，展示与下游事实读取保留unknown，不宣称零。这个实例不接受成交push或目标执行，避免aggregate槽被当作真实今昨执行。

## NQH-R4 资金及可选事实

ACCOUNT必需官方m_dBalance总资产和m_dAvailable可用资金，接收有限有符号事实；不以available≤balance制造额外只读门槛。balance放当前总资产，dynProfit显式中性0，原sink的balance+dynProfit保持源总资产；源浮盈另作独立事实，不重复累计。

插件显式初始化原Adapter读取的全部资金槽，包含margin。preBalance、commission、closeProfit、margin、deposit/withdraw等只在对应源事实/适用性成立时授值，否则中性且unknown。冻结现金与冻结保证金分别保留；frozen_cash不能写入FrozenMargin。币种、前日权益、总资产的不同字段不自动互作别名。

必需字段缺失、非法或同义别名冲突使该批失败。可选字段缺失/null为unknown；非法或冲突为invalid，保留可定位原因且不取另一别名掩盖，不阻断已经满足最低要求的只读合计。原值为合法0时为present。可选事实不参与本切片执行/风控资格。有限同义表须在映射profile中唯一声明；未核准的别名保持未启用。

## NQH-R5 委托、成交及来源归属

首版使用已核原m_字段：ORDER的m_strOrderSysID、证券/市场、m_nOffsetFlag、m_nVolumeTotalOriginal=Q、m_nVolumeTraded=F、m_nVolumeTotal=U、m_nOrderStatus、m_dLimitPrice及m_strInsertDate/Time；DEAL的m_strOrderSysID+m_strTradeID、证券/市场、m_nOffsetFlag、m_nVolume、m_dPrice、m_dTradeAmount及m_strTradeDate/Time。原标识是不截断的字符串，最多63个UTF-8字节，无NUL/控制字符；ORDER ID及DEAL RefOrder直接承载原合同号，不将OrderRef/internal ID猜作券商合同号，不改变前导零。WT TradeID使用下面单一版本的派生标识，原成交ID另存观察值。

股票买卖使用OffsetFlag 48/49；Direction不替代买卖。订单Q>0、0≤F≤Q、U=Q-F；状态49/50/51/52/55为活动，活动余量U；53/54/57为撤拒终态，活动余量0、未成量Q-F；56须F=Q。待撤不授已撤，废单的未成量不称原已撤事实；可选m_dCancelAmount按已核状态核验。未知状态或必需矛盾使批失败。原状态和派生依据保留。

成交量/价为有限正数，原金额为有限非负源值，不用price×quantity填补。订单原报价按已核字段语义保留有限非负值，不以正报价推价格类型。当前源未公开价格类型、WT无Unknown枚举：仅在本限定统计通道使用LIMITPRICE作为明确ABI占位；元数据price_type=unknown/value=null，禁止展示为真实限价或进入执行。原Adapter对无管理tag的查询统计不读取此槽，须以固定源码与实际原链验证；后续真实价格类型另由源契约授予。

日期仅接受明确YYYYMMDD或YYYY-MM-DD；时间接受HHMMSS或HH:MM:SS及可选1–3位小数秒，严格校真实日期/闰年/范围，按已核内置API Asia/Shanghai语义投WT日期及HHMMSSmmm，保留原文本和精度。不剥离任意标点猜日期，不要求事件日期等于未知查询交易日。

固定原Adapter的checkSelfMatch以WT TradeID单键记录RefOrder；空userTag仍经过该检查。HTTP统一将`(exchange, code, event_date, raw_trade_id)`映射为有明确作用域的WT TradeID：exchange为归一后的SSE/SZSE，code保留六位，event_date为已校验YYYYMMDD，raw_trade_id保留原字节。规范输入先写ASCII域`guanheng.nqh.trade-id.v1`及一个NUL，再依上述顺序对每项写4字节无符号大端UTF-8字节长度及完整UTF-8字节；取完整SHA256，使用无填充base64url得到43字符，再加`nqh1.`前缀，共48字节。账户、实例、会话、request_id、generation、买卖及order_id不参与映射。相同证券/日期/原成交ID对应不同订单时仍得到同一WT TradeID，保留原生自成交关系检测语义；该原生告警仍需来源事实解释。

ORDER以原order_id为去重键，同原ID的跨证券/日期等事实冲突整批失败。DEAL以`(derived_trade_id, raw_order_id)`为去重键，只对全部规范化事实等价的行去重；原日期/市场的等价文本保留在元数据，规范事实比较按已核规范值进行。每批另保留临时`derived_trade_id -> 完整四元组`反向索引，任何非等价映射冲突整批拒绝。v2保留原市场/证券/日期/成交ID/订单ID、派生WT TradeID及mapping_version=`nqh.trade-id.v1`，明确raw与derived身份。该批内索引不持久化，不成为账本；不放宽ORDER/RefOrder规则，不新增四查询联表。

HTTP订单/成交全部WT userTag为空，来源旧策略标签不授WT本地管理资格。历史成交只走onRspTrades，不走push；四查询不新增跨批数量/成交一致性门槛。后续push、重查、重连及跨批缓存必须沿同一映射版本并另验事件日期所有者及交接语义，本切片不授这些资格。

## NQH-R6 版本化观察及容量

保持Diagnostics v1布局、版本及原inspect语义。新增自有C接口：

```cpp
int inspectReadOnlyTraderView(ITraderApi*, uint32_t version, uint32_t view,
    uint32_t index, char* output, uint32_t capacity, uint32_t* required);
```

version精确2；view=0概要，1/2/3/4分别持仓/委托/成交/账户单行，概要index必须0。UTF-8 JSON值拷贝，required含结尾NUL。required必须非空；可写时先置0。返回码沿自有Error：成功0，长度探测或容量不足Capacity(-8)，版本/view/index/指针组合错误Invalid(-1)，异owner WrongOwner(-3)，尚未成功交付该批视图Unavailable(-2)。output=null仅允许capacity=0；非空output允许capacity=0探测。容量精确等于required成功；任何错误不写output，已知长度的Capacity写required。注册表查不到的指针返回Invalid。该裸地址接口仅适用于当前一次性实例生命周期，删除后指针失效；它不提供地址复用后的ABA身份保护。

概要和已交付行由owner冻结，worker只交值事件；两次探测/拷贝不pump、不推进状态，不直接读取worker可变视图。Closing/Closed且删除前仍可读概要及已成功交付行；失败或尚未交付的批次不能伪装成空成功。概要含profile/source_kind、单批原始/交付条数、原请求ID、独立执行区间、来源代际、交易日可用性、aggregate-only、drained/joined和只读观察资格。逐行含原身份、已核事实与每字段present/unknown/invalid/not_applicable、ABI中性承载和映射依据；无事实的值为null。账户明细不进默认日志。输出仅本轮有界内存观察，随实例销毁，不持久化第二份账户事实。旧v1不会接收到更大结构。

v2根值固定`version`整数2、`view`整数0..4。概要使用`phase`整数（保持v1编号）、`source_kind`字符串、`profile`字符串或null、`observation_qualified`布尔、`trade_date`事实对象、`aggregate_only`布尔、`batches`长度4数组（固定position/order/deal/account）、`close`对象、`failure`对象。每批含`datatype`、`delivered`布尔、`source_row_count`/`delivered_row_count`非负整数或null、`request_id`字符串或null、`execution_started_at`/`execution_finished_at`字符串或null、`source`对象或null。source精确使用源v1键`agent_id`、`account_id`、`account_environment`、`qmt_session_id`、`generation`；generation为正整数，agent_id为字符串、account_environment为simulation/live字符串，account_id/qmt_session_id保留原字符串或null，不用概念简称另造别名。close含`status`字符串`not_started/waiting/timeout/complete`、`drained`/`joined`布尔。failure含首个`code`整数（无失败为0，其余沿bootstrap::Error）及`reason`字符串（无失败为空），另以`transport_error`字符串或null保留QRT ErrorCode枚举名、`source_error_code`字符串或null保留源错误码；不同域不强制转成同一个整数。关闭超时不覆盖该首因。

行根值含`index`非负整数、`identity`对象、`facts`对象、`abi`对象。identity保留源证券/市场及适用原订单/成交ID、事件日期/时间文本；DEAL增加派生ID与映射版本。facts仅用源字段原名作键，每个事实固定`availability`枚举字符串、`value`原JSON类型或null、`reason`字符串；abi以实际承载的WT槽名作键，每槽固定`value`实际数值/字符串、`mapping`字符串（原值、aggregate、中性或派生映射版本）。只读摘要不把ABI中性值升级为源事实。字段表/键名及错误码集中在自有头和版本化schema定义，映射源码及测试从该唯一协议取值。

v1的HTTP observed_at仍占21字节，使用同一execution_finished_at时刻的秒级UTC显示投影`YYYY-MM-DDTHH:MM:SSZ`，舍去小数秒并将+00:00规范为Z；原完整文本及微秒精度留在v2。不用strncpy截取可能含小数的时间串；fixture秒级规则、v1结构size/version及phase/error编号保持。

源每批最多4096行，ACCOUNT1行；HTTP envelope上限2MiB，以容纳源1MiB持久终态和已定义附加计时。继续严格UTF-8/重复键/深度/节点/字段容量边界；新增自有观察总序列化预算默认16MiB、配置可降低且硬上限64MiB。在整批校验、视图序列化及WTS构造完成后、SPI前结算累计预算；超限使当前整批不交付并撤销全轮资格。先前已交原Adapter的批次保持部分应用事实，不重投。序列化预算与进程内存峰值分别测量，16MiB不宣称进程内存上限。协议上限集中定义，配置为唯一运行值，示例值不代表生产容量。

## NQH-R7 请求、回调及关闭

原有限队列/锁外回调沿NQB。每实例仅一项查询在途；owner同步触发下一query只入队。HTTP不再走fixture的模拟202状态机；QRT在单次read_operation内完成POST/原ID认领。Task在owner准入时带插件instance_generation、stage、本地task_token及steady_clock绝对deadline；本地token仅关联队列，不冒充QRT请求ID。QRT在内部health后生成真实UUID，结果只在QRT返回后绑定其request_id，提交前失败合法为null；不另造UUID、POST或认领状态机。停止后旧结果丢弃计数。回调异常后不重投半应用批次，整实例失去观察资格。

stop关闭准入和标记停止；现QRT没有跨线程cancel接口，停止等待受当前请求剩余总截止约束，不声称立即中断。worker独占QRT，停止新I/O后按自身owner循环执行每次至多100ms的实际drain，只有drained后才能销毁客户端并发布worker完成事件；正常和异常路径共用这个关闭尾段。owner只在真实完成事件到达后join；worker_live=0、空结果队列或一次wait超时都不作为排空证明。

release准入与最终删除资格分离。正确owner且不在pump/SPI回调栈内时，Created、init失败、Initialized、Connecting、Querying、Observed、Failed、Closing均能请求关闭：先注销find ID、关闭准入并解绑SPI，保留objects注册项供已持借用指针观察和再次关闭，然后按close_ms绝对截止等待。正确owner在回调中release只stop后返回，栈退回后再关闭；错误线程不修改实例。fresh、init失败及无线程/客户端按已知空资源直接关闭，不读取尚未验证的close_ms。原void release返回不表示成功，完成证明为v2 close及实际join状态。

close_ms耗尽时phase=Closing、close.status=timeout，drained/joined如实保留，首个领域失败原因保持；继续持有worker、客户端、插件、DLL与必要依赖。后续owner release可再次有界等待，并在真实完成后join。工厂deleteTrader先请求release，仅在Closed、drained、joined、无joinable worker且不在pump/回调栈时delete并置空引用；错误线程、回调中或超时均保留原指针。析构只接收已关闭对象，不能承担可能超预算的首次关闭。禁止detach或以回调注销充当屏障。

宿主先按父NQB完成owner的WTE_Close通知，再调用原Adapter.release；持续保留借用API、DLL、Adapter/sink/BaseData等依赖直至可删除。单次release有界；晚回调持续不排空时，对象与依赖持续保留。宿主只有确证drained/joined才报告正常退出；监管终止属故障清理，退出码及证据区别记录。fixture有限等待行为与旧用例保持。

request_ms取1..30000，round_ms取request_ms..120000，close_ms取1..120000，均显式配置。timeout_ms只是既有HTTP阶段上限；request_ms覆盖QRT前后health/POST/GET总请求；round_ms从connect一次起算并覆盖Prepare、排队和owner交付。owner准入时的Task deadline=min(准入时刻+request_ms, round_deadline)，worker调用prepare/read前重新计算剩余毫秒并向下取整；<=0不发新I/O。完整响应在round截止后也不交付SPI，排队不能重新取得完整request_ms。owner等待使用事件/条件变量及绝对截止，不busy spin。所有失败均保持只读，无下单/撤单/命令/下载/订阅能力。

### 宿主事件等待接口

自有C导出`int waitReadOnlyTrader(ITraderApi* api, uint32_t events, uint32_t timeout_ms)`提供同owner的阻塞观察。集中声明事件位：PumpReady=1（controls/results非空）、WorkerDone=2（实际drain及客户端销毁完成）、StopRequested=4；events须为非零且仅含1|2|4。返回当前满足且被请求的位集合，并在Connecting/Querying的既有Task/round截止到达时自动加入DeadlineReached=8。0表示调用方有限等待超时；负值沿Invalid(-1)、Unavailable(-2)、WrongOwner(-3)、Reentrant(-7)。非法/未注册指针Invalid，错误线程不修改实例。

timeout_ms允许0..120000，0只检查当前条件；正常宿主使用正值。Created或未成功init为Unavailable；成功init后可在Initialized/Connecting/Querying/Observed/Failed/Closing/Closed调用，Closed的WorkerDone立即满足。pump或SPI栈内等待返回Reentrant。

等待不pump、不调用SPI、不发布owner_drained或改变可见视图、原截止及删除资格。沿既有cv通知结果、控制事件、停止和worker完成；wait_until固定本次开始时刻+timeout_ms与适用Task/round绝对截止的最早值，重复通知与伪唤醒沿同一截止。Failed/Closing/Closed不使用旧round唤醒；只请求WorkerDone时，StopRequested不使等待提前返回，避免关闭阶段忙转。WorkerDone仅提供worker完成事实，实际join及owner发布继续由release拥有。原WT虚接口、v1及现有导出保持兼容。

## NQH-R8 验收与运行资格

| 要求 | 证据 |
|---|---|
| R1/R2 | 合成实际HMAC HTTP四类原生对象经当前源编码/上下文→QRT→原Adapter；唯一账户/会话/范围/条数/旧终态错误拒绝，合法空及ACCOUNT唯一行 |
| R3/R4 | 原getPosition四组合等V/A；缺拆分/成本仍合计可用，V-A不冒充冻结；原sink各资金槽显式初始化，未知不展示0，总资产不重复加盈亏 |
| R5 | 状态49–57及数量守恒、买卖、前导零、日期/精度、重复等价/冲突/跨日；命名空间固定字节向量、同证券同日同成交ID跨订单保留原检测、跨市场/证券/日期不串键、反向映射冲突拒绝；未知价格类型仅统计，全部HTTP管理tag空，历史query无push |
| R6 | v1宿主加载新库及秒级时间投影；v2精确错误/长度探测/等容量/非法指针组合/关闭后概要，未交付行Unavailable；字段可用性及原条数/交付数，峰值与累计超限无部分交付且撤资格 |
| R7 | run前SPI=0；prepare超时/stop、队列耗尽预算不发I/O、真实ID成功/超时/提交前unknown；round晚响应拒绝；fresh/失败init/未connect/prepare/read/POST/GET/各查询/SPI回调/错误线程工厂删除；首次关闭超时保留→晚回调退出→再次release真实join→delete/卸载；实际线程/耗时/重入 |
| R7等待与最终准入 | 映射/WTS构造后的确定性跨截止及同pump慢Connect回调阻止后续成功SPI；wait非法位/超时范围/零等待/错误owner/回调重入/结果通知/停止/实际WorkerDone/Closed，伪唤醒不续期且观察视图不因等待改变；HTTP延迟期间实际阻塞等待 |
| 全部 | 原fixture全套保持、固定原Git构建及实际编译/依赖/链接输入、原核心无新漂移、首次HTTP领域接线独立full审查 |

隔离合成验收后，再核实际安装源版本、只读真实四查询、已配置原合约及真实界面。合成通过不授真实QMT、执行器、持续push、同实例重连、跨进程ticket或生产资格。配置关停/正常释放是回退路径，来源原终态、账户与命令事实均保留。

调查依据：HTTP字段接线研究（外部历史/待归仓路径：`../../build/native/qmt-http-bootstrap/research-001/research.md`）、[原股票查询语义](../evidence/2026-10-22-native-stock-query-mapping.md)、[源候选及组合](../evidence/2026-10-22-qmt-source-build-review.md)。研究中的建议在本文形成明确选择；真实部署的别名、币种表示与日期字段仍按实际证据扩展profile。
