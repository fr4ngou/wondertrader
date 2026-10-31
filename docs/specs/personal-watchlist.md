# 个人观察自选

类型：功能最终规格。状态：accepted。前缀：PWL。范围：GBW保留业务F08中的个人观察自选切片；配置激活/回滚、实时行情、搜索目录、F18市场观察及其他F08能力各自验收。实现、独立审查、软件和实际安装页面资格见[当前证据](../evidence/2026-10-23-personal-watchlist.md)，生产资格单列。

## 目标与必要性

用户在实际/market页添加或移除自己关注的沪深证券，重新打开页面和正常重启应用后仍能读到同一列表；点击其中代码沿当前1m/5m分钟图入口查看。自选是单操作者应用的观察偏好，既不定义策略universe，也不改变执行目标、持仓、账户许可或交易配置。

当前真实链是main.tsx→workspace/IndependentApp.tsx→MinuteWorkspace.tsx。MinuteWorkspace只有代码输入/分钟图，明确个人观察未接通。保留但未挂载的pages/MarketPage.tsx和旧api.ts/types.ts已有旧自选形状，App尚无对应路由，实际落未迁入501。采用同一已有URL的GET/PUT语义，新增本仓的最小持久化owner及当前页面接线；不会把旧Control、数据库、审计服务、bootstrap或公开观察源搬回来。

原生核实见[个人观察与原生能力的边界](../migration/personal-watchlist-native-reuse.md)：固定WT08的策略userdata是策略上下文状态，按策略名保存；WtRunner配置装配策略/引擎。Servo订阅具有读取行情和改变运行订阅的语义。原生分钟查询继续使用现SDK/Reader，原生中已核实的接缝不承担独立用户自选CRUD/CAS。本差额只有小型JSON、版本比较和应用界面，不修改WT。

## PWL-R1–R3 归属、范围与配置

- 一份显式应用配置根对应一个default个人列表，当前单机单操作者模型。没有新用户账户、券商账户映射、多watchlist、云同步或浏览器localStorage权威副本。
- 新ConsoleSettings字段watchlist_root: str，环境GUANHENG_WATCHLIST_ROOT，默认空关闭；不读取.env、不猜用户目录、不探测旧工程。该根由操作员预先准备在安装包外的本地数据目录，部署配置显式保存。HTTP不接受路径、用户名、账户、策略ID或源地址。
- 首批目标为当前Windows独立应用受支持的CPython环境；不存在相应OS锁能力时仅此功能不可用。平台实际支持按运行证据登记。
- 路径必须非空绝对本地目录、UTF8<=4096B；拒相对、UNC/device路径、NUL、空白路径、根目录本身、symlink/junction/reparse及受管文件多hardlink。程序不递归创建根、不改ACL、不扫描别处。原盘符和resolve后的目标都须核绝对本地盘符、非根目录及实际本地drive类型；网络映射盘、UNC/device及未知drive拒绝。配置失效只使watchlist能力降级，行情/账户/回测和health保持各自事实。
- 状态只包含代码列表和自身版本。添加不调用QMT、SDK、原生订阅/下载、策略注册或配置激活；只在用户明确点选代码读取分钟图时使用现有图表GET。保存成功说明偏好保存，不授证券存在、行情可用或交易资格。

## 架构与实现接缝

浏览器main→IndependentApp capability→MinuteWorkspace个人观察卡片→workspace/watchlistApi.ts→同源App watchlist_routes.py→既有BoundedReader→WatchlistOwner→专用JSON根。

行情仍走既有MinuteWorkspace→fetchMarketChart→app.market_chart→build_native_chart→独立SDK/WT。两个状态owner不相互回写。

候选新增guanheng_app/contracts/watchlist.py、watchlist.py、watchlist_routes.py及workspace/watchlistApi.ts；修改app.py/settings.py/IndependentApp.tsx/MinuteWorkspace.tsx及局部样式/测试。API/全局types旧自选接口不直接接入真实链：其无严格解码且含未交付audit字段。本切片使用独立严格DTO，保留旧未挂载源码的历史归属，不把它算兼容或功能完成。

现backtest_routes.command中的Origin/Sec-Fetch判断是已存在的本机写入口政策。抽为自有ui_origin.py纯共享guard，让原backtest和新PUT共用；合法请求接受域保持，重复Origin/Host/Sec-Fetch头统一403，畸形urlsplit也为403。其body格式/业务owner仍各自拥有，不导入Watchlist到回测，不借新功能改变原回测任务/时间/生命周期。需带回测正常/恶意Origin回归。

strategy_host._RootLock是私有且固定.strategy-host.lock，不能直接声称存在适用自选的公共lease API。自选owner通过Windows CreateFileW的share_mode=0原子创建/独占打开自身.watchlist.lock，整个生命周期保留同一handle/descriptor及借用stream；不调用WT策略状态、不复制Host启动/Job，不为本功能重构既有StrategyHost。该Windows标准OS能力同时确定首次初始化权，避免先创建文件后locking的空隙；既有StrategyHost锁及其行为保持。业务JSON只有一个owner。若实现提出公共锁抽取，须先列其独立影响，不能用本规格替该重构授通过。

## PWL-R4–R6 精确公共契约

以下为唯一新版本；旧schema_version=1.0的name/items/confirmed/audit_event_id请求与返回不作为兼容输入。

### GET /v1/ui/watchlists/default

无query，无请求正文/transfer-encoding。成功200并Cache-Control: no-store，返回完整快照：

~~~json
{
  "schema_version": "guanheng.personal-watchlist.v1",
  "watchlist_id": "12345678-1234-4234-8234-123456789abc",
  "version": 1,
  "symbols": [],
  "updated_at": "2026-10-23T01:00:00Z",
  "affects_strategy": false,
  "editable": true,
  "reason": null
}
~~~

示例身份及时间均虚构。所有顶层字段必需且闭合：

|字段|语义与边界|
|---|---|
|schema_version|精确固定tag|
|watchlist_id|应用初始化生成且持久保存的规范小写UUID4；不是用户/券商身份或认证凭据|
|version|精确int，1..9007199254740991；bool、float、非有限均拒绝；每次实际替换+1，排序变化也算替换|
|symbols|有序、无重复的0..100个规范六位.SH/.SZ字符串，单项9个ASCII字符；不是合约存在证明|
|updated_at|服务端带Z的有效UTC日期时间；仅偏好保存时间，不能解释为行情时点；版本承担因果，系统墙钟回拨不使版本回退|
|affects_strategy|必须false，缺失或true均是消费失败|
|editable|当前owner允许新保存；没有改变本列表的历史事实|
|reason|editable=true时null；false时固定中文原因，UTF8<=256B，不含路径/异常内容|

磁盘对象使用相同tag/id/version/symbols/updated_at五字段；affects_strategy/editable/reason由应用边界投影，禁止从磁盘自报运行能力。快照在进程内采用不可变tuple/独占值树，序列化给客户端时才生成新list；frozen外壳不能替代递归无alias。

### PUT /v1/ui/watchlists/default

Content-Type application/json（可带charset），无query，UTF8原始正文最多4096B，闭合对象：

~~~json
{
  "schema_version": "guanheng.personal-watchlist.v1",
  "watchlist_id": "12345678-1234-4234-8234-123456789abc",
  "expected_version": 1,
  "symbols": ["600000.SH", "510300.SH"]
}
~~~

列表按完整替换理解，客户端添加/删除形成新完整数组；没有action或命令事件。symbol准入先核精确str及原UTF8<=32B，再沿normalize_chart_symbol的strip/upper/六位.SH|SZ规则产生规范值；规范化后重复拒绝，不静默去重/推断交易所。HTTP/文件必须拒重复JSON键、未知字段、无效UTF8、错误tag、非法UUID/版本及超容量。JSON只允许本文声明的对象、symbols一层数组和对应标量；嵌套对象/数组一律拒绝，解析异常含RecursionError统一作为坏格式。入队前完成独占快照；store公开方法即使接到typed对象也重新核全字段/类型，避免构造旁路和排队期间list别名变化。

单个序列区内先检查watchlist_id和expected_version与当前磁盘快照完全相等：任一不符409且不写。随后若完整规范symbols及顺序相同，200 changed=false、version/updated_at原样；否则生成同id/version+1/服务端时间并原子替换，200 changed=true。版本到达上限时仍可GET/no-op，实际改变503并保留旧文件，禁止绕回或创建新id规避。

成功结果为闭合对象：

~~~json
{
  "schema_version": "guanheng.personal-watchlist.v1",
  "changed": true,
  "watchlist": {
    "schema_version": "guanheng.personal-watchlist.v1",
    "watchlist_id": "12345678-1234-4234-8234-123456789abc",
    "version": 2,
    "symbols": ["600000.SH", "510300.SH"],
    "updated_at": "2026-10-23T01:01:00Z",
    "affects_strategy": false,
    "editable": true,
    "reason": null
  }
}
~~~

没有audit、replayed、approval、config_version或订单身份。旧未挂载客户端不会收到伪造的audit_event_id。该URL其他方法405，默认列表以外路径404/明确未支持，不新增/v1/control入口。

## PWL-R7–R8 单一持久化owner

根最多包含watchlist.json、.watchlist.lock、watchlist.tmp三份普通文件，主文件/临时文件各<=16KiB，锁<=16B，总<=32784B。所有原始读采用实际最多limit+1的有限读取，不能仅stat准入后无界read。坏/多余文件保留并拒新编辑，不递归读取或删除未知文件。

owner在单个CreateFileW动作中取得创建权与OS排他句柄，转换为descriptor时保留唯一所有权；stream以closefd=False借用descriptor。正常关闭依次关闭stream/descriptor，转换失败则关闭仍持有的原handle。迟到/关闭失败保留实际资源供同owner续核。owner终生持有独立OS锁stream；另一个应用/worker即使使用大小写等价路径也无法成为同根writer。锁在root独立文件上，不能锁住待replace的JSON文件。store使用自己的进程内序列锁保护GET与compare+写入全过程；没有HTTP层先读后写的竞态。两次基于N的不同替换最多一次成功，另一次409；不在冲突后自动重放或合并。版本和UUID共同防止不同根/初始化代际被误认同一列表。

初始化：显式根首次无锁文件、无主文件、无tmp时，CREATE_NEW与独占share_mode=0必须是同一OS动作，竞争者不能抢占新锁；可在已接管OS锁后原子创建version=1的有效空快照，持久保存新UUID。已有有效主文件则严格读取保留身份；已有锁/临时资料却缺主文件视为中断或资料缺失，拒绝静默重置为空。已有有效主文件但残留tmp只展示已提交主文件并editable=false，保持tmp供维护；不自动采用、合并或覆盖残留。

保存顺序：同目录watchlist.tmp独占xb创建→全量write→flush→fsync→close→提交前同D与关闭状态检查→os.replace到watchlist.json→有限回读并核原bytes/DTO→才可返回200。主文件不原位截断。所有stream先归owner/局部try-finally，再核动作晚回；每个业务动作前后同D，清理总会尝试。

正常成功replace使tmp消失；明确由本次调用创建且仍未提交的tmp可在本次异常收尾中清理。清理失败则保留且暂停编辑；启动遗留/未知文件不自动删除。replace失败前旧主文件保持；replace可能完成后错误/超期属于保存结果未知，不能声称回滚成功。普通进程重启读取原完整快照；文件fsync/同卷原子替换不宣称所有硬件掉电持久保证。备份/恢复或人工维护须停全部writer，再复制此小目录或在新显式根恢复；不提供未交付CLI命令。

## PWL-R9–R12 HTTP、预算与结果未知

共享Origin政策依据实际backtest代码：有Origin时要求无path/query/fragment/userinfo、scheme与request.url.scheme相等、netloc与Host精确相等；urlsplit异常403。Sec-Fetch-Site仅允许缺省/same-origin/none；当前本机工具无Origin且无Fetch头的请求沿既有政策允许。该政策是本机写请求约束，不是用户身份认证；现CLI仅监听127.0.0.1或::1，不新增跨域代理或对外认证服务。

正文读入、解析、排队、序列锁等待、实际文件/编码动作、提交前检查、回读及响应编码共用HTTP入口起算的monotonic绝对截止2秒。复用现BoundedReader（2worker/4queue）和取消语义，无独立线程/后台轮询服务；排队用剩余量。单次文件/OS动作无法抢占，检测迟到后停止新业务动作，仍完成清理。输出编码后同D检查且原UTF8<=16KiB。

|状态|HTTP与固定中文行为|
|---|---|
|有效空/正常/no-op|200；空只来自有效已初始化快照|
|版本/列表身份冲突|409，观察列表已在其他页面更新，请重新读取后确认|
|未知字段/格式/重复/非法代码/超100|422，不回显原输入|
|入站正文超4096B|413|
|异源/恶意Origin/Fetch/重复身份头|403；JSON类型不符415|
|未配置/未启动/正在关闭|503，个人观察尚未配置或暂不可用；分钟查询仍可使用|
|有效主文件且残留tmp|GET返回200完整已提交快照、editable=false；PUT返回503，保留tmp供维护|
|坏文件/锁冲突/满队列/超期/权限或I/O失败|503，固定说明并保留原文件/owner；无法确认提交时提示重新读取核实|

成功PUT与客户端收到响应是两件事。HTTP取消/断连只取消尚未运行的Future；已运行任务仍由读池/owner持有，未结束前阻止同owner新写交错。浏览器超时或连接失败不自动重试PUT；重新GET，比较完整目标symbols及id，再告知已确认保存或让用户重新确认。409也只GET，不自动覆盖他页更新。此自然替换语义不需要持久命令日志。

capabilities增加features.personal_watchlist={available,editable,max_items:100,scope:'personal-observation',affects_strategy:false,reason}；从同一owner状态投影，不能只看配置字符串推断可编辑。顶层read_only:true继续表达券商/交易操作关闭；UI改用“交易只读”，明确“仅个人观察偏好可编辑”。自选不可用不伪报整个应用失败；自选可用也不使strategy/execution/operations变为完成。

## PWL-R13–R15 中文页面及消费边界

MinuteWorkspace内新增“我的个人观察”卡片，不挂载旧MarketPage，也不读取旧bootstrap、策略配置/订单历史/Control/search等多源。现分钟输入、周期、before、错误隐藏旧图和来源资格原行为保持。

- 页面只在personal_watchlist.available时GET；能力字段缺失时零自选API，并显示“个人观察尚未配置，仍可直接查询分钟线”。完整合法能力available=false时同样零GET，显示“个人观察暂不可用，仍可直接查询分钟线；请检查本机配置或偏好资料”，避免把锁冲突或坏文件解释为未配置。market能力关闭不妨碍本地列表读取/编辑；只禁用图表读取。
- 有效空显示“个人观察列表为空；输入完整证券代码加入，仅供本页观察”。输入规范化同分钟代码；添加重复/超过100由本地预检提示且零PUT，服务端仍复验。移出按钮明确代码与作用；不加人工审批或多步骤确认。
- 加/减生成当前完整列表并发送一次PUT，pending禁用相关保存按钮、不做乐观更新；提交无行情请求。点击“查看{code}分钟线”才沿原图表参数和fetching门禁读取，不自动取首条/不订阅。移除当前图代码时图仍可作为手工查询显示。
- 中文状态覆盖读取中、保存中、保存成功、有效空、冲突、结果未知、不可用/坏格式和重试恢复。保存成功说明“已保存个人观察；策略交易范围不变”。错误不回显底层地址/文件路径/异常内容。
- 新watchlistApi独立严格校DTO/tag/闭合字段/false/ID/版本/有序唯一列表。PUT返回必须与请求完整目标、同id、changed对应版本关系一致；矛盾不可作为已保存。较旧GET不得覆盖同ID较新版本；不同ID重新进入确认状态，不合并两个列表。
- Query key使用independent-watchlist/default，和未挂载旧1.0缓存分开；至多当前一个快照，不存版本历史。复用既有fetchReadJson读取调度/取消及6500ms浏览器等待预算，PUT沿现commandBacktest式AbortController+固定中文边界并retry=false。服务端保证16KiB编码输出，前端校100项；现read helper不提供恶意同源超大响应的硬内存隔离，本切片不据DTO条数宣称这项能力。
- 保存结果未知时暂停编辑，先允许GET核实；读取失败不把旧缓存标成当前成功列表。可以显示上次确认偏好及其updated_at，但必须明确“尚未确认/暂不能编辑”。错误与恢复都不影响独立分钟手工查询。
- 标签、关联label、按钮name、键盘提交/焦点、aria-live状态、可访问移出按钮；360px无横向页面溢出，代码列表自动换列/单列，不引入100行整页横向表。

## PWL-R16 生命周期

WatchlistOwner构造只做纯配置和值分配；应用先挂到state，再在既有lifespan受保护阶段初始化/接管锁与文件。初始化走同一读池且有单独原2s截止，无新线程。部分失败降级本功能，仍保留未确认owner，app finally继续关闭所有已发布owner。

每个实际store操作先在短准入锁中确认accepting并计入在途，再在锁外等序列锁/做I/O；出错也在完整stream清理后的finally归零。在途结束前不可释放OS锁。关闭先停准入，再让既有reader取消队列/回收；排队晚任务见closed后拒绝，不打开文件。只有实际在途为0且未确认资源全部关闭后才释放锁/标closed；未知/close失败仍保留强引用，重复close可续核。禁止在业务锁内有预算等待或把Future.cancel当已运行操作完成。应用GBW-R6同一关闭窗口/异常继续其他owner规则保持。

## PWL-R17–R18 实施与验收

契约冻结后分后端owner/DTO/route及前端MinuteWorkspace薄消费实施。首批仅标准库JSON/files/locks加现FastAPI/Pydantic，不增加数据库、消息总线、服务依赖或改uv.lock以引入额外平台。包构建沿现Flit/本仓七包与Vite，不从旧工程运行/动态导入。状态根不打入wheel/dist，显式配置不随安装移动。

要求和验证映射见本文附录；以下列验收要求，各次实际状态见当前证据：

1. 新tests/integration/watchlist的纯store/协议/HTTP定义：有效初始空、完整替换/移除最后项、100边界、重复/invalid/Unicode/typed alias、同N竞争、wrongID/重启、坏文件/残留/短写/权限、各动作晚回、提交前后失败、启动/关闭未知及其他组件继续收尾。
2. 同源guard覆盖原回测合法/畸形/异源及新PUT严格参数；确认旧backtest行为和市场/账户响应保持，不把read_only解释成交易授权。
3. 新watchlistApi与MinuteWorkspace组件/API定义：正常/空/disabled零请求、PUT一次、重复点击/本地无效零PUT、矛盾响应、慢旧GET/冲突/未知/恢复、键盘/窄屏；点击列表才沿原分钟GET，保存/移出不触发行情、策略或账户API。
4. 经后续明确恢复动态授权后，用新noneditable正式包+生产SPA+实际私有JSON根完成真实用户链：添加两个代码→移除一个→关闭并确认owner回收→重启同根→同ID/版本/剩余代码→浏览器重新读取。该链的偏好HTTP/持久化使用真实实现，不用mock替代保存；原生分钟保持可用/空/异常与资格标识，不启动真实QMT/账户交易来验证个人偏好。
5. 同版本source/wheel/site/dist/配置身份、实际错误/退出/关闭、所有原件与独审分别封存。规格、测试定义、软件、安装、SDK和生产资格分别登记，以匹配最终身份的实际原件为据。

回滚程序前备份根且停止writer；旧程序未识别新tag时保持文件不动并显示功能不可用。不能靠降版本清空数据；显式恢复备份或新数据根由维护者另授权执行。状态归属见[ADR-0008](../architecture/adr/0008-personal-watchlist-ownership.md)；设计状态与实现、运行资格分别记录。

## 附录：要求与验收映射

| 要求 | 可观察约束 | 计划验证 |
|---|---|---|
| PWL-R1 个人偏好独立归属 | 一个显式配置根的default列表只供/market个人观察；不读写策略universe、配置/目标/持仓/资金或QMT接口，不自动订阅/下载。 | 依赖/调用静态检查；保存前后策略配置摘要及SDK调用计数不变。 |
| PWL-R2 原生复用和最小差额 | 沿既有分钟图SDK/WT读取；个人自选仅小JSON持久化，不滥用策略userdata，不启动WT引擎/新增数据库或Control服务。 | 原生能力核实正文与实际import/安装闭包。 |
| PWL-R3 显式配置和单操作者模型 | GUANHENG_WATCHLIST_ROOT默认空关闭；仅本机Windows应用配置，单根一个默认列表；配置路径不由HTTP传入。 | 未配置/错误/权限失败时仅自选降级，其他功能和健康保留。 |
| PWL-R4 来源和类型准入 | 闭合版本DTO；snapshot ID/版本/UTC/规范symbols严格验证并递归独占copy，拒未知/重复JSON键、bool版本、非有限/无效UTF8/重复symbols和越界。 | 原始JSON、typed绕过/后续alias、UTF8和容量纯反例。 |
| PWL-R5 公开GET | GET /v1/ui/watchlists/default 无query/正文，返回同源确认快照；无配置/坏文件不是空成功。 | 真实HTTP正常/有效空/未配置/损坏/恢复；GET无行情或交易调用。 |
| PWL-R6 完整替换PUT | 同URL PUT完整symbols+watchlist_id+expected_version；锁内先核ID/版本，精确相同顺序no-op不变，否则原子保存且版本+1。 | 新增/删除/清空/重新排序/重复提交/旧版本/不同ID完整替换。 |
| PWL-R7 并发和持久写者 | 同配置根终身OS排他锁，进程内序列锁，compare+write同事务区；第二进程不得成为writer。 | 同N两个不同列表仅一提交、另一409；别名/重启/多进程并发未来验证。 |
| PWL-R8 原子文件和失败 | 16KiB原件、同目录固定xb临时文件、全量写+flush/fsync+close+replace+回读；不原位截断主文件，不自动采用残留tmp或坏文件。 | 每动作失败/短写/崩溃窗口/临时残留/主文件完整性/旧值保护。 |
| PWL-R9 同源写入口 | 复用现backtest Origin/Sec-Fetch策略，共享纯guard；application/json、正文4KiB、无额外query；固定中文错误。 | 同源/无Origin本机工具规则、异源/畸形/userinfo/path/重复头/超量/慢body。 |
| PWL-R10 单次截止和容量 | HTTP入站起同一2s D涵盖body/排队/锁/读取/编码/提交前/回读；原BoundedReader及100项/16KiB/3文件配额；不因排队续期。 | 虚拟钟/慢动作/增长文件/超额/满队列/取消；单步不可抢占边界明确。 |
| PWL-R11 写结果未知 | 断连/迟到replace不能推定未保存；不自动重放PUT，重新GET比较完整目标列表；版本冲突不自动覆盖/合并。 | 提交前后丢响应/超时、late worker、GET核实、连续两页并发。 |
| PWL-R12 公开能力和只读语义 | capability取同owner available/editable/reason；read_only保持交易关闭，个人偏好可编辑单独披露；退役功能不恢复。 | 能力关闭零watchlist请求；health/market/account/backtest互不伪造完成。 |
| PWL-R13 真实页面链 | main→IndependentApp→MinuteWorkspace增加个人观察卡片；独立严格watchlistApi不加载旧MarketPage/bootstrap/Control/audit。 | 实际SPA入口、bundle/import、路由deep link与零旧API验证。 |
| PWL-R14 用户添加/移除/查看 | 仅输入完整代码添加、按钮移除、列表点击沿同一分钟查询；空、保存、错误/恢复中文；保存/删除不自动拉行情，当前图保持。 | 键盘/重复点击/分页不适用/当前图/分钟禁用和列表编辑独立。 |
| PWL-R15 缓存与矛盾拒绝 | 不乐观发布新列表；响应严格校ID/版本/完整symbols、changed；旧GET不得覆盖较新版本；异常期间暂停编辑并允许GET恢复。 | 慢旧GET/异ID/虚假changed/响应错版本/格式错/恢复组件API测试。 |
| PWL-R16 生命周期和依赖保留 | owner先发布再启动；复用原读池不自建线程。close关准入、池取消/实际回收、在途归零后释放OS锁；未知继续保留owner。 | 部分启动/stream晚回/关闭异常继续其他owner/重复close/后续实例准入。 |
| PWL-R17 重启/搬迁/恢复 | 正常重启保留ID/版本/顺序；显式根不随安装搬迁丢失；坏/未知新格式保留文件拒写；备份恢复先停止全部writer。 | 正式非editable安装+生产SPA真实保存→进程重启→读取，旧源码隔离；故障恢复。 |
| PWL-R18 独立验收和资格 | 先同版本完整软件/HTTP/浏览器/安装/真实文件独审；原生分钟、SDK、生产各按原资格，不以规格/mock计通过。 | 测试入口/原始结果/源安装dist身份与运行证明分列；各次执行状态见当前证据。 |
