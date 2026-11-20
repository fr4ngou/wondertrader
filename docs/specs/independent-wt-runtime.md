# WT独立运行与只读观察接入

类型：功能最终规格。状态：accepted。前缀：WRI。范围：WT运行发行单元和观衡服务的启动及部署解耦。实施中，整链资格尚待取得。

## 职责与复用

遵循[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)。复用原生能力WT-O01、WT-D01、WT-S01/S02及WT-T01/T02/T03：原Runner/CTA、DataKit/Writer/Reader、Parser/Trader和执行器继续负责原生运行。自有券商共享内存Host及跨进程启动适配归WT发行单元，独立入口和Python辅助环境不依赖观衡Web安装。详细原生边界见[能力目录](../development/wondertrader-capabilities.md)。

现有观衡`app.py`实际构造QMT Host、采集、历史和执行owner，是当前职责偏离的根因。修正在运行装配层完成：提取可复用进程适配到独立运行包，观衡移除运行owner，保留只读消费者。WT核心源码及原分钟、持仓、订单算法保持。

## 完整调用链

WT独立入口读取运行实例配置，依次启动已选择的QMT通信、原生数据服务及采集、策略执行；QMT未启动时Host常驻等待，单项业务请求继续有截止。实际配置决定组件与账户模式，不从观衡配置或浏览器请求派生。原组件ready和业务就绪分别表达。

运行侧发布只读状态及已有行情/账户/策略数据接口；观衡连接这些接口，独立管理自己的HTTP服务、展示读池和缓存。关闭观衡只关闭观衡自身资源。关闭WT时，由WT原owner按依赖顺序停止执行和采集，再停止来源通信，保留原收据及未知责任。

## 模块与接口边界

- 独立包：`apps/wt_runtime/guanheng_wt_runtime`，负责可复用进程owner、配置组合和安装后的运行入口；包不能导入`guanheng_app`或要求FastAPI/SPA。
- 运行组件继续消费原部署descriptor及可信摘要，原控制ID、ready/stop/closed、Job和关闭结果沿原组件契约。安装工具仅准备制品及解析入口。
- 主会话负责通信/采集/历史装配；开发者1负责原生执行及唯一1.1.2策略入口迁出Web包后的契约；开发者2负责观衡退出运行管理并接入只读消费者。迁移共享模块前冻结清单并由单一负责人修改。
- 独立运行实例的状态、账户资料和配对材料归WT侧。观衡仅持读取所需的地址和凭据，不持执行凭据，不接管金融状态或通信Journal。
- 只读接口变化按原接口版本治理；已冻结开发包保持原件，新增发布使用新版本与摘要。

### 只读通信、查询和数据更新的组件恢复

WT 运行中检测到只读通信、历史准备、历史查询或行情采集进程异常退出时，按原停止预算确认其原进程树、线程与句柄回收，再用原描述符及 SHA 启动唯一后继。账户发布或策略数据发布线程发生运行故障时，须由原 owner 确认工作线程、扫描或刷新作业和发布租约已关闭，才可构造后继。暂时缺行情或缺来源继续按组件原等待语义处理。

每个组件的换代线程由同一 WT 独立持有，控制循环继续监控其它角色并响应停机。主动停机沿原逆序关闭，先通知对应 owner 停止，再确认同角色换代线程退出，避免两个调用者同时关闭同一资源。旧资源回收未确认或新组件启动失败时保留原故障处理。恢复不改策略、交易通信或执行器的身份和责任。

新进程监听及发布线程就绪只代表运行恢复。历史准备保留原请求身份和结果未知状态，行情采集续读持久进度，策略窗口按原捕获协议恢复，账户发布从新的有效账户快照取得业务资格。各角色验收须验证实际新结果，并核原输出、请求身份及进度保持。

### 退出诊断

WT 主进程捕获首个异常时，先将该代控制 ID、记录时间、失败阶段、标准异常类别、系统错误码和最近八处 WT 运行包内代码位置提交给有界进程日志，再进入原停止流程。代码位置仅记录模块文件名和行号。清理异常也提交同一日志，原诊断收口继续按既有格式另存首错和清理错误。受管子进程一旦确认退出，首错事件记录已知的退出码及子进程 PID，最终退出事件补齐可取得的实际进程退出码。

日志不保存异常正文、路径、局部变量或账户数据。日志磁盘写入与监督分离，容量及写入状态沿原进程日志机制。突然断电、强制终止或磁盘不可写时，仍可能缺少最后记录，此时用已存的进程事件、原退出收据和 OS 证据核对。

## 要求与验收

### WT运行配置及公开接缝

独立wheel为`guanheng-wt-runtime`，模块`guanheng_wt_runtime`；普通安装入口为`pythonw -I -B -m guanheng_wt_runtime --config <原字节配置> --config-sha256 <SHA256> --control-directory <新的运行目录> --control-id <UUID>`。入口使用固定组件工厂，运行环境不导入观衡包或Web依赖。

基础安装闭包为WT运行包与独立行情SDK。完整执行选择本包声明的`execution`安装extra，包含既有唯一策略v1、原生数量模型及传递的core/tzdata，形成六发行闭包；普通角色安装器沿原extras参数解释声明。省略extra保留基础闭包，安装依赖选择不提升交易权限或启动策略，所有运行动作继续由显式组件配置决定。

配置schema为`guanheng.wt-runtime.v1`，字段为`instance_id`（规范UUID）、`startup_seconds`（整套启动共享预算，0.1–600秒）、`stop_seconds`（首次关闭共享预算，0.1–120秒）、`components`（已选择组件）。组件名字固定为`host`、`trade_host`、`account_host`、`analysis_host`、`analysis_batch_host`、`account_observation`、`history`、`collection`、`analysis_window`、`execution`，每项字段为`kind`、`descriptor`（原部署描述文件绝对路径）、`sha256`（原字节摘要）。`host.kind`为`qmt_read`或`qmt_history_preparation`，分别复用原只读Host及HPR组合；trade_host.kind为`qmt_trade`；account_host、analysis_host和analysis_batch_host的kind为`qmt_read`，沿原只读Host工厂；account_observation.kind为`native_account_observation`，依赖同实例account_host并沿[NAP-v1](../migration/native-account-publication-proposal.md#nap-v1冻结合同)固定工厂；其余kind为`source_market`、`quote_collection`、`analysis_window`、`execution`。配置选项表示实例装配，不作为证券查询或账户的产品允许清单。

全部组件配置完成构造后才按Host→可选交易Host→可选账户Host→可选账户结果更新→历史→采集→执行启动，逆序关闭。声明account_observation而缺account_host时，在构造任何owner前拒绝配置。`RuntimeConfig.from_path(path, expected_sha256)`只读取配置；`Runtime(config).start(monotonic_deadline)`、`status()`、`check()`、`request_close()`、`wait_close_request(timeout)`、`close(timeout)`分别负责一次启动、安全状态快照、原owner健康核对、停止通知及有界关闭。`status`不查询来源，沿原组件进程状态表达ready，业务可用由原接口另报。原组件请求身份、未知结果和Journal不由运行装配层重建或重发。

执行模块单一工厂为`guanheng_wt_runtime.execution_process.create_process(descriptor_path, expected_sha256)`，返回同`start/status/request_close/close`协议的原执行进程owner；声明execution但接缝或部署不完整时明确启动失败。该工厂和执行适配由开发者1负责，运行装配不复写原执行算法。

### 执行来源晚到的启动装配

`components.execution.wait_for_source`为可选布尔值，缺省`false`保持直接启动原执行owner。显式`true`适用于同实例声明`trade_host`并连接其本地数字回环HTTP地址的装配，由WRI薄owner先完成本地等待线程的启动，持续读取原`GET /internal/v1/trade-status`；交易Source认证及事件通道就绪后才调用原执行owner的`start`一次。读取地址、凭据环境变量名、单次HTTP超时和响应容量全部沿原执行配置的`trader`，等待不发账户查询或下撤单，也不另建Journal。原直接执行工厂的HTTPS等既有路径保持。QMT内部正文和WT框架保持。

本地等待没有总配对时限；每次状态GET及原执行初始化各自沿原截止。状态读取失败中的连接失败/单次超时、以及原Host明确报告来源未就绪，进入下一轮等待；认证拒绝、协议不符和Host报告的硬故障使组件失败。来源失去后已经启动的执行owner沿其原有故障/恢复责任处理，WRI不重新创建或重发。

显式等待模式的组件`ready`只表达本地owner可监督，`execution_ready`单独表达原执行进程的真实ready；`source_wait_state`依次为`waiting_source`、`starting_execution`、`execution_started`。等待时原生PID和业务结果定位为空；状态快照不向来源发请求。关闭先通知等待线程及原执行owner，在首次共用停止截止内join等待线程并关闭原owner；在来源到来前停止也应正常退出且执行调用数为零。

显式采用后继时，如果配置的执行进程在交易初始化或初次委托核对阶段退出，可沿上一已准入代继续恢复。服务核对同一子进程的启动、退出、原生失败及关闭收据，确认执行队列从未接受或派发委托、交接未领取、原策略状态与交接摘要一致，再沿原金融身份准入。已准入或启动证据不完整的代继续走原对应恢复流程。

WRI-R4的完整执行组合还须验证：普通安装的同一七组件WT先启动，超过65秒后才启动同正文SDK Source，随后原1.1.2策略→执行器→SHM→SDK→NAP→独立观衡完整成立；等待期间停止的组合没有执行副作用。接口替身与真实QMT的资格分别记录。该增量实现及验收中。

执行公开状态的`business_observation`按[NRT-R20](native-realtime-strategy.md#nrt-r20-独立运行结果的只读定位交接)交接既有结果文件及本代control_id/CTA配置SHA/实际PID，WRI状态原样保留。观衡只读消费者验证原ready和结果身份后投影现有策略、P及资金，未提供的订单/成交分别标缺失，不持有执行owner。执行故障/停止及业务观察时间分别呈现，本接缝不改变交易或恢复责任。

### 执行下单开关的只读投影

WRI-R8：观衡沿本次已解析的 WRI 运行身份与原 NRT-R20 `business_observation` 定位本代执行目录。`execution.json` 是 WT 原 owner 在该目录保存、由引用中的 `config_sha256` 绑定的不可变 Native 配置；消费者在原两秒读取截止内核原 ready 的控制 ID、SHA 和 PID，沿现有共享删除读取器取得最多 256 KiB 原配置，校验完整摘要及 `schema_version=guanheng.cta-execution.v1`，仅选择 `trader.writes_enabled` 精确布尔值。随后复核同代 WRI 的 PID 和执行引用，换代或不匹配时本字段未知。配置读取不触发账户查询、写盘或执行 owner 操作；不读取交易 Journal、账本、凭据文件或环境变量。该读取量与累计交易历史无关。

`/v1/ui/wt-runtime` 与 `/v1/ui/wt-instances` 的执行组件新增可选 `execution_control` 对象：`state` 为 `available` 或 `unavailable`，表示本代配置是否核实；`writes_enabled` 为已核实布尔值，未知时为 null；`label` 为固定中文说明。关闭与未知分别表达。该值只描述所引用执行代的配置，实例停止、来源连接、账户权限和风控分别沿原状态展示；开启不保证当下能够成交。原始配置、路径、账户和异常正文不进入公开 DTO。缺引用、旧版、无效配置或局部读失败只降级该字段，原生命周期及业务观察保持可读；总请求超时仍沿原 503。

验收覆盖开启/关闭、旧发布者缺引用、损坏与摘要错误、非布尔值、错误 ready/路径/PID、读取期间引用换代、共享替换等待与原截止，以及实际 HTTP 两入口的局部降级和私有字段隔离。读取前后文件及请求数量不产生修改。页面继续沿已确认设计实施；接口验收与页面正式交付分别登记。

同一控制根及`instance_id`使用OS独占锁；控制目录保持每代唯一。ready/status/stop/closed的身份均绑定`control_id`、`instance_id`、配置SHA，发布者额外带真实PID。状态schema为`guanheng.wt-runtime-status.v1`；停止文件为`guanheng.wt-runtime-stop.v1`。最终`closed.json`仅在全部原owner实际关闭、线程/Job/管道核实后发布；失败写`failure.json`，不把连接ready或“已请求停止”当成完成。正常来源等待不设60秒窗口。交易执行器、交易通信与其它组件的故障保持原停机和恢复语义。

| ID | 要求 | 实际验收 |
|---|---|---|
| WRI-R1 | WT可独立安装、启动和自动运行 | 无观衡包/SPA的普通安装，实际Host、采集、历史、唯一策略及隔离执行完成 |
| WRI-R2 | 观衡独立只读 | 启停观衡不创建/关闭运行侧进程、不发下撤单或历史下载；保留个人展示偏好操作 |
| WRI-R3 | 观衡故障不影响WT | 同一WT实例下观衡正常关闭、重启及异常退出，核实际进程/连接和采集、策略持续推进 |
| WRI-R4 | 来源等待及重连保持 | 独立WT入口完成超过旧60秒窗口的晚到连接和两代认证；旧请求不重发 |
| WRI-R5 | 原数据和执行语义保持 | 同一真实历史及SDK替身输入，原Reader/策略/执行结果与已验组件相同；WT框架新增修改0 |
| WRI-R6 | 生命周期和恢复责任单一 | 每个子进程只有WT侧owner，实际关闭收据与物理退出一致；未知委托保留原身份 |
| WRI-R7 | 独立发布及可观察运维 | 两侧分别安装/启动和替换候选，明确命令、配置及只读状态；不切现场生产实例 |
| WRI-R8 | 下单开关按原执行配置只读展示 | 原身份、配置摘要和布尔值已核；关闭与未知区分，局部失败保持其它状态，页面及正式发行分别验收 |

顺序：先完成独立WT完整主链及观衡断开仍持续运行，再集中异常、独立审查、包与文档。现有跨夜采集保持原实例，切换到新入口另行验证，不将本规格修改当成已完成部署。

## 当前工作和边界

交易通信组合增加可选`components.trade_host`，固定`kind=qmt_trade`并沿相同descriptor/SHA结构，工厂为`guanheng_wt_runtime.trade_host_process.create_process(path, sha256)`。原`host`继续拥有只读/HPR通信，交易Host与HPR独立配对和Journal，支持在同一WT配置中并存；省略trade_host时完全沿原组件路径。状态components可包含trade_host，只读消费者以“交易通信”展示该组件。此扩展不改变原QMT协议、委托身份、未知结果或金融计算；完整安装及同正文多owner仍按THP/WRI联合验收。

账户组合增加可选`components.account_host`，固定`kind=qmt_read`，复用原`QmtHostProcess`及其descriptor、私有配对、凭据和Journal。当host已承担HPR、trade_host承担v4交易时，原v3账户只读消费者仍可连接由同一WT管理的原只读Host。它没有账户计算、交易能力升级或新通信协议；生命周期归WT。可选`components.account_observation`沿NAP-v1工厂拥有原Scan四查询单轮、原帧发布与物理回收，观衡只读取其结果及只读locator。完整依赖顺序为host→trade_host→account_host→account_observation→history→collection→execution，原配置省略新增项保持原相对顺序；共享原启动/停止总截止。状态消费者将account_host显示为“账户通信”、account_observation显示为“账户结果更新”。新增项的源码装配、普通安装、多Host业务链、实际源端及页面共存分别验收，开发配置不表示已切现场实例。

ETF历史由用户指定的《杂役》会话承担独立补齐、转换和查询模块，先复用缓存，再按ETF清单调用来源接口；活动下载文件稳定后再转换。主会话继续本规格的独立运行主线。模拟盘下撤单已获用户授权，实际执行前确认终端模拟账户；实盘及生产切换授权保持原边界。跨夜采集只观察现有实例，不重做已通过的单日采集验收。

## 持续策略分析数据装配

可选 `components.analysis_host` 的固定 kind 为 `qmt_read`，复用原 Host descriptor、常驻配对和进程 owner，增加对显式 v7 日线/因子读能力的识别。`components.analysis_window` 的 kind 为 `analysis_window`，消费 `guanheng.analysis-window-deployment.v1` descriptor：精确包含 schema、stop_seconds（0.1..120秒）和 configuration；configuration 沿 [AWP](qmt-analysis-window-producer.md) 的 source_connection/source/producer 三项配置。摘要绑定完整部署正文，凭据继续通过环境变量注入。

analysis_window 必须与本 WT 的 analysis_host 一起声明；两项省略时原路径及原相对顺序保持。可选 analysis_batch_host 使用批量 v8 原 Host descriptor/SHA，复用 qmt_read 工厂和独立配对；它可单独配置，也可与 v7 analysis_host 共存。完整顺序为 host→trade_host→account_host→analysis_host→analysis_batch_host→account_observation→history→collection→analysis_window→execution，逆序关闭。省略新增项时所有原组件相对顺序保持。启动只建立常驻 owner，不等待第一份行情；status 的 ready 表示 owner 可工作，data_ready、published_count 和 last_success 分别表示数据发布。缺源或旧源继续等待并保留已有窗口，不把通信等待当作 WT 整体故障；发布者实际失败才传递组件错误。执行原 R24 对来源新鲜度和等待的处理保持。

薄适配直接组合原 AWP producer，复用其线程、请求身份及 Native Job 回收，不重写导入/复权/窗口计算。WT 停止时先关闭执行，再在同一整套关闭截止内关闭发布者，最后关闭 analysis_host；观衡不创建上述 owner。新增普通安装组合及完整有身份读取主链分别验收，源码装配不授予现场部署资格。

analysis_window 状态沿既有组件公共字段 state/ready/pending/forced，额外包含 phase/data_ready/published_count/last_success/source_error/closed。state 表示服务生命周期，pending 表示停止后的资源回收尚未确认；薄适配本身不强杀线程，forced=false，原 Native Job 的强制关闭事实继续保存在原作业收据中。独立观衡应兼容新增合法组件并以中文显示，服务 ready 与数据新鲜度分别呈现。

同一 QMT 正文显式包含 analysis_read 时，交易配对为 `qmt.trade-product-pair.v3`。父端交易 Host owner 复用原 v1/v2 路径，并识别该 v3 的原 source_runtime=strategy_tick、分析 profile=v7、原两种分析操作及设置摘要；完整源码、配对、权限和私有设置仍由原 Host 子进程唯一验证。此版本识别不改变交易权限、命令身份或默认配对。

显式包含 analysis_batch_read 时使用 `qmt.trade-product-pair.v4`，沿用同一 strategy_tick 运行方式及原进程生命周期。父端核验批量分析 profile=v8、唯一只读操作 market.market_data 及设置摘要；同时声明 analysis_read 时，继续按上述 v7 契约核验。v4 必须具备批量分析身份，原 v1/v2/v3 准入保持。完整批量设置仍由 Host 验证，新增身份识别只让 WT 托管已配置的组合通信，不增加交易权限。

## 显式Source依赖的Python源码绑定

OLS-7源码绑定：显式dependency_handoff的source_extension非null时，PythonExecutionProcessConfig与configured的隔离子加载使用同一固定集合，在原双profile七包后增加guanheng_qmt_shm和guanheng_qmt_shm_agent。选择器先核材料原字节SHA及固定结构，完整Source业务准入继续由本节原owner执行。省略材料或source_extension为null保持原单策略五包/双策略七包，无Source分支不要求安装这两个owner。

import包guanheng_qmt_shm的真实发行名为guanheng-qmt-shm-host，guanheng_qmt_shm_agent对应guanheng-qmt-shm-agent。每个固定owner均绑定完整.py/.json源码和恰一份真实发行METADATA；父端核METADATA的Name，子端核原字节SHA及目录闭包。Host普通发行所声明的第三方依赖继续由原安装闭包提供，pip中仅存在Host/Agent不构成configured源码已绑定证明。额外源码、缺元数据、源/元数据字节变化沿原启动拒绝；不扩展模块选择、权限或交易能力。

已完整核验的同业务恢复中，Source续接可把原绑定缺失的上述两个owner源码及对应真实METADATA补入；前代任一源码或METADATA已出现即视为已绑定owner；该owner新增源码、第二METADATA、补全半绑定、变更及移除均继续拒绝，其余Core、解释器及账户边界保持原约束。文件数、单文件/总字节及隔离启动边界保持原值，属于安装资源保护；它们不形成新的交易次数或标的配额。验收包含实际Native配置加载→Source原部署身份API→父端清点→真实-I-S子端核验，以及Host/Agent源码和元数据各自篡改拒绝。此读取验证不启动Native金融进程或Source SDK。
