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

WRI-R4的完整执行组合还须验证：普通安装的同一七组件WT先启动，超过65秒后才启动同正文SDK Source，随后原1.1.2策略→执行器→SHM→SDK→NAP→独立观衡完整成立；等待期间停止的组合没有执行副作用。接口替身与真实QMT的资格分别记录。该增量实现及验收中。

执行公开状态的`business_observation`按[NRT-R20](native-realtime-strategy.md#nrt-r20-独立运行结果的只读定位交接)交接既有结果文件及本代control_id/CTA配置SHA/实际PID，WRI状态原样保留。观衡只读消费者验证原ready和结果身份后投影现有策略、P及资金，未提供的订单/成交分别标缺失，不持有执行owner。执行故障/停止及业务观察时间分别呈现，本接缝不改变交易或恢复责任。

同一控制根及`instance_id`使用OS独占锁；控制目录保持每代唯一。ready/status/stop/closed的身份均绑定`control_id`、`instance_id`、配置SHA，发布者额外带真实PID。状态schema为`guanheng.wt-runtime-status.v1`；停止文件为`guanheng.wt-runtime-stop.v1`。最终`closed.json`仅在全部原owner实际关闭、线程/Job/管道核实后发布；失败写`failure.json`，不把连接ready或“已请求停止”当成完成。正常来源等待不设60秒窗口，运行故障不自动创建第二代进程或重发命令。

| ID | 要求 | 实际验收 |
|---|---|---|
| WRI-R1 | WT可独立安装、启动和自动运行 | 无观衡包/SPA的普通安装，实际Host、采集、历史、唯一策略及隔离执行完成 |
| WRI-R2 | 观衡独立只读 | 启停观衡不创建/关闭运行侧进程、不发下撤单或历史下载；保留个人展示偏好操作 |
| WRI-R3 | 观衡故障不影响WT | 同一WT实例下观衡正常关闭、重启及异常退出，核实际进程/连接和采集、策略持续推进 |
| WRI-R4 | 来源等待及重连保持 | 独立WT入口完成超过旧60秒窗口的晚到连接和两代认证；旧请求不重发 |
| WRI-R5 | 原数据和执行语义保持 | 同一真实历史及SDK替身输入，原Reader/策略/执行结果与已验组件相同；WT框架新增修改0 |
| WRI-R6 | 生命周期和恢复责任单一 | 每个子进程只有WT侧owner，实际关闭收据与物理退出一致；未知委托保留原身份 |
| WRI-R7 | 独立发布及可观察运维 | 两侧分别安装/启动和替换候选，明确命令、配置及只读状态；不切现场生产实例 |

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
