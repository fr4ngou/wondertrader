# QMT 显式历史缓存补齐

类型：功能最终规格。状态：accepted。前缀：HPR。仅本仓终端适配及认证 SHM 链，真实终端验收由模块A主会话负责。

## 正式查询范围的用户确认

2026-10-29用户确认：正式按需补齐覆盖来源支持的证券，逐只登记的测试allowlist退出正式补齐路径。原v1 limits.symbols记录既有已签配对合同；后继实现同步更新Agent/Host/客户端及部署材料，旧冻结合同保留其原语义。正式范围按已接入的沪深市场能力提供，证券真实性与来源无数据由QMT结果表达。保留按请求窗口、队列、并发和等待时间的资源管理。测试样本范围单独记录，策略证券配置继续只描述策略用途。

此项为已确认需求，实现与实机验收仍在进行；旧配对的9只ETF范围不代表全市场补齐已经完成。

## HPR1 能力、边界与选择

复用能力 WT-D11 的来源补齐接缝：WT loader/DSB 不负责下载券商缓存。源端调用 QMT 内置全局 `download_history_data(symbol, period, start_time, end_time)`；只由固定 callable 注入，外部 xtquant 同名接口不作为此实现。原 RestrictedReadAgent 队列、策略线程、认证 Session、ControlPeer、Host bound 请求/Journal/结果及 reconnecting owner 共用；不修改 WT 框架、不增加运输或终端文件/网络访问。

新显式 `qmt.read-profile.v6` 包含 `market.history_prepare` 及至少一个原读取操作，control 保持原1.0。旧v1-v5、交易profile、默认配对/工厂拒绝补齐；新专用工厂/Agent/配对入口才启用。权限为历史缓存副作用，与委托权限分开，订单实现保持。

## HPR2 固定输入与预算

沿原八字段 bound request，operation=`market.history_prepare`，policy=`qmt.history-preparation.v1`、version=`1.0`、priority=`normal`。arguments 精确为 `symbol,period,start_time,end_time,clock_schema,deadline_ms`。每请求单一六位沪深证券，period 精确1m/1d；1m标签为YYYYMMDDHHMM00，1d为YYYYMMDD，均校验真实公历日期、起止顺序、1992..2099。日期范围不证明交易日或覆盖。

该操作 descriptor 沿原 `policy_id/policy_version/execution_timeout_ms/limits`。正式按来源市场支持的limits使用schema_version=`qmt.history-preparation-limits.v2`，精确包含schema_version、periods（排序去重1m/1d子集）、max_calendar_days（1m/1d各1..36600，首尾日期均计入）、max_tasks（1..1024，保留全部任务身份，不逐出）、max_queued（1..1024）、total_timeout_ms（100..30000），省去symbols。每个请求的沪深证券代码由原参数格式校验，QMT负责证券真实性和实际数据。排队额度不大于任务额度。终端原队列max_pending由此额度装配；Host原Journal记录额度不大于max_tasks。

旧schema=`qmt.history-preparation-limits.v1`保留原symbols（排序去重allowlist，1..128）及其余字段，用于既有已签配对和冻结结果恢复。v2使用原read-profile.v6及原policy，完整descriptor参与原profile/配对摘要；新Host/Agent同批更新后建立新配对，旧Agent对新limits按版本拒绝，旧材料和原请求身份保持。

deadline_ms 是既有 `qmt.win-uptime-ms.v1` 同机共享时钟的绝对毫秒截止；Host和Agent分别采用已核 GetTickCount64 clock owner。新请求在两侧均核剩余时间大于0且不超过total_timeout_ms。执行使用该原D及原request.timeout_ms较早者；原队列期限继续生效，任何阶段不重新延长D。只接受单次 policy（max_attempts=1，无可重试错误）。

## HPR3 状态、重连及结果

Host先持久 queued/dispatching 再发送；终端共享内存任务表跨本次 reconnecting owner 的代际保留 request_id 与完整请求字节身份。相同ID/相同内容只观察原completion，不再次排队；不同内容拒绝。容量耗尽拒绝新任务，原任务保持。

调用仅在创建Agent的原策略线程执行，I/O线程只准入和投递同一队列。排队过期/尚未执行的关闭可确认未执行；进入SDK后异常、超期或断开均为 `preparation_unknown`，不得解释成未执行，不自动重试。Python不能抢占原生调用，运行owner保持到实际调用返回；管理关闭超期保留owner。新代不得重做原ID。

成功终态 data 精确为 schema=`qmt.history-preparation-result.v1`、symbol/period/start_time/end_time、effect=`call_returned`、coverage=`unknown`。只声明原函数在D内返回，不采纳其返回正文，也不宣称下载成功、无缺口、最新尾部或策略可用。终态经原finalizer、Host持久化及原bound-results查询。中断/重启恢复沿原Journal，只将已派发的补齐解释为结果未知，禁止重派。

### HPR3-R1 合法控制拒绝与原请求收束

Host消费经原ControlPeer验签、顺序和全文校验的`agent.read`失败回复时，将原固定错误码与delivery作为本次控制交付事实；它不等同于原生SDK结果。Host不构造原生结果或未调用证明，沿原请求ID、正文SHA及dispatch binding调用原Journal中断规则。已派发HPR仍为`preparation_unknown`，已有完整原生终态或原未执行证明保持原值。未知请求不重新排队、不建立替代ID。只有同一原请求的持久状态已核实后才ACK该控制回复；同一Host owner继续处理后继独立请求。

完整原生成功回复仍走原finish_bound。缺少错误字段、未知错误码、非法delivery、成功载荷损坏、认证/顺序/Session协议错误继续故障；不宽泛吞ProtocolError或重连。拒绝结果和持久截止在take后一次固定，域背压及关闭复用同一对象；中断/关闭不重复take或反复将合法拒绝解释为协议错误。持久化失败继续保留原owner及原截止，关闭后的核查只确认原Journal，不重发来源或补ACK。

诊断仅保存最近一次控制拒绝的固定code、delivery、持久状态及有界计数；不含请求正文、证券、凭据或异常文本。该只读快照可进入原Host首故障诊断，ready/closed、公开HTTP/wire及QMT正文保持。验收先跑同一真实HostControlLoop、ControlPeer和SQLite Journal的“合法拒绝→原ID未知→后继原生成功→关闭”，再覆盖拒绝类型、背压、提交失败/恢复、重复交付及真正协议损坏。

## HPR4 验收与部署

### HPR4-R1 固定来源兼容发行

既有HPR采用旧Host及原Agent时，修正发行以实际原配对的Host源码全集为基线，保留已固定诊断overlay；仅接入HPR3-R1及其持久完成/关闭责任所需直接前置。精确依赖原Agent发行，原Agent源码、协议、QMT正文、原业务配置及Journal定位保持原值，主干交易SDK升级单独采用。兼容源码和普通Flit项目永久归仓，正常构建及安装通过成员SHA与精确依赖验证；历史安装路径只用于溯源。

原配对绑定原Host安装路径，保持只读。新安装环境通过原create_product_pair/verify_product_pair生成并验证后继配对，原策略逐字节一致；原manifest不改写。验收使用正常安装模块跑同owner合法拒绝→后继成功→正常关闭，核全部Host/Agent成员、依赖和原材料保持。该工程资格不代表实际QMT来源/线上运行验收，实际采用由运行owner单独执行。


专用配对生成冻结memory runtime，额外只注入全局download_history_data；保留原回调/线程/关闭机制。原配对工具默认行为保持。部署为新受管候选，不安装/启动QMT，不热切运行策略，不操作交易。

主链：真实Host runtime/Journal → 认证内存SHM Session → 原Agent队列 → 下载替身在策略线程增加缓存bar → 原终态查询 → 既有market.history_1m回读新bar。先完成此链，再核1d/1m、沪深清单外证券及旧v1兼容、窗口/预算、重复/内容冲突、队列、超期晚回、断开/重连、不可中断与旧读/交易回归。真实原函数、副作用和完整覆盖由主会话独立验收。

规格不授业务15:00可获知、标准单位、完整日历或真实交易资格。数据更新之后仍须用原历史接口回读日期、条数与内容；未确定的范围保留unknown。

## HPR5 独立产品、离线配对和系统托管

新产品配对schema为`qmt.history-preparation-product-pair.v1`，专用create/verify/run入口与旧v3及普通只读工厂分开。产品必须包含同一GH_WT_MEMORY_VERIFY条目的QST全推和HPR补齐；两个不同认证内存映射、同一Windows会话、同一原策略线程，禁止账户/交易能力。组合完整正文由Host安装包的唯一生成实现拥有，原qmt_quote_stream_memory.py转调它，默认quote-only正文保持原字节。

产品配置无合成容量默认：max_records、max_result_bytes、请求/控制额度、历史max_rows及窗口由部署显式声明。产品Journal按max_records×(实际准入max_request_bytes+max_result_bytes+16384B元数据)完整预留，确保声明任务数不会先被较小的隐式字节额度耗尽；容量不足时返回503/journal_capacity_exhausted拒绝新任务，原结果继续可查。控制、排队、执行及I/O各自预算明确绑定；不把SDK调用耗时等同于完整往返耗时。

离线create先严格准入配置、原policy快照、两端安装源身份、目标3.6.8 SDK/CPython许可及全部预算，再独占创建私有目录；manifest最后封存。manifest及其固定文件集合、声明字段、配置/凭证角色、完整Host启动正文、完整组合策略、内存依赖闭包/许可、Host/Agent安装源清单均由verify从已核输入重建并逐字节比较。重新计算manifest自报SHA不能授权正文修改。create/verify不构造服务、不打开Journal、不执行生成入口或SDK；验证返回只含安全身份。所有读取有上限，并拒绝链接/重解析点/硬链接、额外文件、缺失、类型、版本、重复键及身份漂移。

专用运行入口从同一次verify的私有快照构造正式HPR常驻Host，不执行host.py或重读可变policy。复用原Server/paired-control的唯一监控及关闭实现，采用独立HPR ready/stop/closed schema；ready绑定控制UUID、实际PID、配对manifest/config摘要及监听地址，仅表示HTTP监听就绪。来源可以无限晚到；Host不按60秒总窗口退出，重新认证沿原有限单代连接预算。关闭共用父传入原绝对D，确认Server、runtime、monitor及资源均关闭才发stopped；未知owner保持并返回固定去敏失败。

App新增`HistoryPreparationProcessConfig/HistoryPreparationProcess`薄适配，默认无配置为disabled，复用原ManagedLocalProcess隐藏Windows Job、PID归属检查、stdout/stderr限额、原子stop、闭合收据和资源确认。只接受新产品schema，启动前核pythonw/manifest/安装路径身份，不导入Host包或私有凭证；不修改App settings/lifespan/路由。本次交付提供父层接口，由主会话合入公共App接线。

独立候选包含Host/Agent安装包、明确锁定依赖及许可证、薄App适配和完整文件清单；新目录安装及搬迁后逐文件SHA核验，安装代码来源与仓库解释器隔离。隔离验收实际运行隐藏Job下的已安装Host、晚到3.6.8来源完整正文、1m/1d下载替身及原历史回读、来源断开/新认证、原ID终态查询、禁止重发、正常停止及全部进程/管道/Job资源确认。真实QMT、真实下载、账户/交易、WT框架和生产启用均不在该产品工程验收范围。

严格读取由产品显式注入原冻结器首读接缝：SDK根及源码路径在resolve前检查，正文与来源身份消费同一受限字节快照；旧生成默认接缝保持。源清单在第一遍枚举时执行1000项上限，第一遍文件读取即受2MiB约束。两个SHM的独立性按原运输验证器计算出的最终映射名判定，相同前缀与不同route可以组成合法产品。
