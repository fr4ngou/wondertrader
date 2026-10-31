# 观衡原生账户只读展示

原生扫描的共享内存来源、inspection v3／Scan IPC v2／公开DTO 2.0扩展以[QAR](qmt-shm-account-read.md)为唯一正文。观衡现行装配按[COP独立WT读取](guanheng-operator-platform.md#独立wt状态消费)及[NRT-R20](native-realtime-strategy.md#nrt-r20-独立运行结果的只读定位交接)消费已发布业务观察和DTO3；扫描owner归WT侧或独立工具，旧App托管描述保留当时开发资格。下文固定HTTP来源及旧版本描述保留历史范围，正式新运行链不回退退役终端HTTP。

类型：功能最终规格。状态：accepted。前缀：NAC。范围：完整观衡迁入中的账户、持仓、全账户委托和成交展示；总体范围继续按[GBW](guanheng-business-workspace.md)和[完整清单](../migration/business-feature-inventory.md)推进。

## 已核原生能力与必要差额

原TraderAdapter正常init/run串联POSITION→ORDER→DEAL→ACCOUNT；既有TraderQMTReadOnly及inspectReadOnlyTraderView v2已经提供来源事实、逐批身份/时间、字段资格和只读映射。原getOrders只枚举WT管理活动单，初始化订单/成交不完整枚举给被动sink；savedata/CSV也不回填全账户历史查询。

插件requested位只接受一次初始化，原Adapter的重复查询会保留未再出现的持仓并累加统计。因此每轮采用新进程中的一个原Adapter/插件实例，复用正常四查询及v2值副本；观衡提供投影和展示。不新增持仓数据库、账户归约器或重复基础订单账本。源码依据及定位保存在`build/guanheng-workspace/account-contract-001`，适用原生行为见[只读通道](../modules/qmt-readonly-trader.md)。

## NAC-R1 原生产品宿主

新增本仓库自有GuanhengAccountScan产品目标，使用固定原TraderAdapter对象及原WTSTools/WTSUtils。不得链接当前冻结框架差异、改框架文件或把测试Probe当产品。构造BaseData、只读Adapter和被动sink，savedata=false，不连接策略/执行器/目标，不调用委托、撤单、下载、订阅或试探性拒写接口。

每进程一次初始化、一轮四查询，run返回后才由相同owner wait/pump。原生指针仅留在owner线程；跨进程只传UTF8 JSON值。业务事实来自v2 facts，ABI中性值/aggregate pre/new仅供原接口承载。单轮成功须同时满足四批delivered、原观察qualified、无失败及实际正常关闭；ready单项不足以证明完整观察。

## NAC-R2 显式绑定与输入

宿主命令行仅接受绝对--config和UUID --scan-id。配置包含独立安装根、普通只读插件路径/摘要、sessions/commodities/contracts绝对路径/摘要、来源绑定及有限预算。凭据只使用已登记环境变量名；不得回显或落盘秘密、账户原行或响应正文。核插件绝对路径与原Adapter从CWD/traders实际加载身份相同，运行目录不依赖旧工程。

source固定qmt_http，profile固定cny_cash_shsz_v1，currency固定CNY；账户/环境显式绑定。只使用已核HMAC/QRT及scope=account，不把原管理单范围当全账户。配置未知项拒绝，来源未配置不启动进程，不探测旧配置或旧服务。示例均标合成身份。

绑定JSON的顶层键固定为schema_version（整数1）、installation_root（绝对目录）、library（path/sha256对象）、base_data（sessions/commodities/contracts三项path/sha256对象）、trader（原只读插件配置对象）及budget（total_ms，1000..30000）。trader允许的键为module/adapter_id/instance_id/enabled/savedata/source/base_url/key_id_env/hmac_secret_env/request_ms/round_ms/max_rows/timeout_ms/max_response_bytes/close_ms/expected_account/environment/currency/profile/view_bytes；module固定TraderQMTReadOnly，enabled=true、savedata=false，原ABI登录user/password使用宿主设置的空值，不从用户配置取秘密。配置最多64KiB，文件及摘要核验在任何连接之前完成。配置可包含非秘密账户绑定，诊断与公开HTTP仅输出掩码。

默认request_ms=2000、round_ms=10000、close_ms=2000、max_rows=4096、view_bytes=16MiB；预算均有上界并由一个配置owner校验。父总预算默认15秒、可配置1..30秒，覆盖排队、创建、查询、复制、关闭及退出，不在每阶段续期。实际来源超过预算返回明确失败或部分结果，不隐式截断或无限重试。

## NAC-R3 有限值IPC

stdout专供两个有序帧，Windows设binary模式。每帧为4字节大端无符号长度及对应UTF8 JSON，首帧observation，末帧completion；每帧最多20MiB、两帧总量最多40MiB，stderr最多64KiB，均并发消费。长度先准入，再分配读取；JSON拒绝无效UTF8、重复key、非有限数字、过深结构和超过声明行数。超量/半帧/重复帧/乱序/未知schema/scan_id不符为协议错误，进入有界回收。

共同字段schema='guanheng.account-scan.v1'、scan_id和kind。observation包含原summary对象及rows对象；rows按position/order/deal/account分别为原v2行数组。未交付批数组为空且summary.delivered=false，完整空批数组为空且delivered=true；不得互换。单批行数严格匹配delivered_row_count，四种datatype与view1..4、index连续一致。保留每批source/request_id/execution区间/result_sha256和trade_date未知语义，不能拼成券商事务快照。

completion包含closed、joined、worker_live、queued、elapsed_ms和固定error_code；不含任意异常原文。父进程同时核退出码和完成帧，接收observation不等于成功。失败时已取得的完整批可供partial展示；未完整接收/校验的批不可见。IPC不保存订单或恢复事实。

宿主初始化前失败可只发completion，不发虚构observation；初始化成功后即使某批失败，也发实际已交付observation再发completion。退出码0表示采集完整且正常关闭，3表示已回收的来源/采集失败，4表示关闭失败；配置或内部协议失败2。父端逐项验证而不单凭退出码授资格。自有进程被父端终止时允许无completion，明确forced并保留已校验完整批。

## NAC-R4 退出与未知结果

停止先停本轮新查询，再由owner执行stop/release并有限等待。未join时保留API、DLL、sink和基础资料；不在回调中销毁，不做通用热卸载。正常进程退出交给OS平衡原Adapter未释放的模块引用，不沿用Probe的额外FreeLibrary测试逻辑。

父截止或应用关闭时停止准入，等待有限收尾，必要时终止并wait回收其自有只读子进程及管道。强制回收明确forced，不冒充正常callback drain。源端已受理原请求可能继续完成，保留已取得请求引用，不自动换ID重复POST。异常、取消和晚到结果不授新轮资格；全应用退出需实际无子进程/线程/管道句柄遗留。

## NAC-R5 独立业务HTTP与生命周期

实现归apps/guanheng，与原生宿主独立安装/发布。应用生命周期拥有一个账户采集owner：最多一个在途子进程、最多16个等待者；同一在途读取共享scan_id与结果，各等待者独立截止/断连不撤销其他等待者。超过容量立即中文繁忙。上一进程未回收完不启动下一轮；明确刷新或后续请求方可开始新轮，不后台无限轮询。

GET /v1/ui/account/overview返回当前一轮全部四类投影，顶层含schema_version='1.0'、scan_id、status=complete|partial|unavailable、read_only=true、aggregate_only=true、trade_date、close、groups和固定中文reason。四个groups均含datatype、status=complete|unavailable、rows、source、execution_started_at/finished_at、request_id、result_sha256；允许完整空数组。传输/原生异常不得包装成成功空持仓。未配置来源返回unavailable，界面可读原因；参数错误422，容量429，正常或partial观察200。

能力路由account.available仅表示独立读取入口已装配/配置，附只读、四类范围和实际来源状态，不授交易资格。旧account/execution等任意路由继续各自登记迁入状态，不通过本接口伪造其他功能完成。所有缓存仅为有界内存显示值，明确观察时间，不作为账户/审批/订单权威状态。

## NAC-R6 公开投影与缺失语义

公开行保留identity（证券、市场、broker订单/成交ID）与fields；fields每个值为availability=present|unknown|invalid、value、reason。仅登记的facts进入公开fields；数值不四舍五入成新事实，不以ABI默认0补缺。原source账号只在内部核绑定；公开source使用account_label掩码，并保留agent_id、environment、session_id/generation供关联，不输出凭据和原始异常。浏览器的数值身份须为可精确表示的安全整数；超出范围的旧DTO代际整体拒绝，避免相邻代际合并。缓存来源身份由已验证字段的固定元组构成，JSON对象键顺序不改变身份。

| 类型 | 最低公开字段及事实来源 |
|---|---|
| position | quantity/sellable←m_nVolume/m_nCanUseVolume；yesterday/frozen/onroad、average_price/open_price、position_profit/float_profit、market_value按ViewSchemaV2逐项映射；quantity-sellable不命名为委托冻结 |
| account | total_asset/available←m_dBalance/m_dAvailable；previous_balance、commission、frozen_cash、frozen_margin、frozen_commission、position_profit、float_profit各取同名已登记事实；总资产已含盈亏不重复相加 |
| order | 原broker ID、side、quantity/filled/remaining、price、原state、cancel、原日期/时间；管理归属unknown，价格类型unknown；不能借空userTag授策略归属 |
| deal | 原broker order/trade ID、side、quantity、price、amount、原日期/时间及已有派生身份说明；查询历史不重新作为成交push应用 |

可选字段保持unknown/invalid，并提供固定中文解释。交易日沿原summary未知状态；机器日期或每批执行日期不能替代券商交易日。账户资金要求原源确有一条对应账户事实；空资金批与零资产分开。

## NAC-R7 中文用户入口

在独立SPA接入账户页：显示资金、持仓/可卖、委托和成交，逐批时间、来源环境、完整/部分/不可用及字段未知可见。刷新发起一轮读取；并发点击沿在途结果认领。正常、完整空、部分失败、未知字段、未配、繁忙、超时、关闭及恢复使用中文原因/影响/处理说明。策略归属、审批及交易按钮仍按各自能力，不因账户可读而启用。

独立`/orders`交易记录入口复用同一账户读取与显示组件，默认委托，可切换成交；只展示这两类记录及各自来源/查询时间，不显示资金分配、审批队列或持久化审批账本。账户页继续默认持仓并保留全部四类展示。已配置时自动读取，能力提示未配置时仍允许用户明确重读；已有可读缓存继续展示。刷新中和失败后保留上次成功观察及原时间，显示刷新状态和重试。部分批失败时各自保留上次同来源成功批并明确标注，当前成功批（含空批）替换本类展示；来源身份变化时清除跨来源回退。缓存为页面值投影，不改原scan_id和当前轮事实，不合并行、统计或订单责任。切换委托/成交和分页只消费当前内存观察，不触发额外账户请求，不授策略归属、实时回报连续性、下单或撤单资格。日常页面只显示掩码账户、实际环境和查询时间，内部运输/会话/请求摘要保留原DTO供诊断。

## NAC-R8 构建、验证与交付

新增自有账户profile复用原native.py锁定依赖、固定WT快照、编译/安装/收据机制；新profile的源、测试和制品全部归本仓库，不要求外部QMT fixture。旧NQP制品和旧profile保持原证据，不通过关闭全部测试规避前置；新宿主不含测试门控导出。原生与业务wheel/SPA分别发行并核ABI及配置兼容。

验证正常/空/unknown/非法字段、不同批时间、来源代际冲突、必需字段失败及逐批停止；实跑原Adapter/普通DLL/新HTTP源/产品宿主/独立安装业务HTTP/真实浏览器链。验证连续两轮移除证券与统计独立、并发单进程、父取消/截止/满额/畸形IPC、退出/强制回收/同端口重启。测试源为合成时明确标注；真实QMT四查询/用户入口另取来源证据。独立full/delta闭合后才授相应开发资格，真实部署及交易分别授权，完整观衡迁入继续。

## NAC-R9 WT持续发布的账户来源

按[NAP-v1唯一合同](../migration/native-account-publication-proposal.md#nap-v1冻结合同)读取WT的account_observation定位、ready与observation.json，原binding的七字段只供内部校验；公开HTTP继续由原validate_observation/project_account输出掩码、原数值和逐批时点。读取沿原App有界读池及单次2秒绝对截止，包上限20MiB+64KiB；任何刷新、标签或分页产生的Scan/Host/券商请求为0。WT根身份、locator、ready、包装和读取后根身份共同绑定，换代时拒绝跨实例拼接。

`GUANHENG_ACCOUNT_SOURCE`显式选择`wt_strategy`或`wt_account_publication`，默认wt_strategy保持现有R20账户DTO3及策略视图。新来源继续使用同一WT只读路径和四个固定运行pin；缺组件或首轮无成功帧显示四组未知，不自动改读R20或旧终端HTTP。R20策略视图始终沿原地址独立可读。

新来源返回DTO4.0：完整保留原DTO2.0的groups/source/fields/trade_date/scan_id/close，额外publication对象字段为scope_id、state、revision、updated_at、last_success_at、runtime_state。scope_id由固定WT和发布者身份摘要构成，只隔离展示缓存，不授账户、登录或存活事实；缺定位时为空并清除跨来源回退。其余字段表达持续发布阶段、版本、发布时间、最后成功时间和WT最近状态。初始无结果使用原unavailable_account的四未知组；有成功帧时只有原completion、exit0与全部原资源证明成立才交原投影。最近attempt只表示当前查询状态，不替换上次成功帧的scan_id、close或批次时点。未知券商交易日和登录会话继续原语义。

页面分别标注等待、正在更新、更新成功、失败保留旧结果和发布停止；四组各自时间、完整空委托/成交与未知保持。刷新只重读已发布结果；失败保留旧值时明确last_success_at和当前异常，不能显示为本轮新成功。现有DTO1/2/3与各自显式来源保持兼容，DTO4使用同一金融显示组件，不新增金融归约或持久账户状态。

包装阶段与原帧保持一致：waiting没有成功帧或attempt；ready对应同一成功scan/completion/close的最近attempt且没有错误；degraded携固定内部错误，其余阶段错误为空。last_success_at覆盖该成功帧的全部批次结束时间，并且不晚于updated_at。前后根locator及组件PID复用同一严格类型、身份和路径准入；协议矛盾保持503，浏览器继续保留同查询的既有成功结果及原时间。
