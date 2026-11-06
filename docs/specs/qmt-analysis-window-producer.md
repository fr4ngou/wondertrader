# WT 持续分析窗口生产者

类型：最终规格。前缀：AWP。状态：accepted / implementing。目标为唯一 RR112 1.1.2 持续供应原 QNA v1；source-provider 沿[来源快照合同](qmt-analysis-window-provider.md)。

## AWP1 主链与复用

WT 独立持有常驻生产者，观衡只读；提供独立 `start/status/request_close/close` owner 及 CLI，并由 [WRI 可选组件](independent-wt-runtime.md#持续策略分析数据装配)组合管理。每次刷新由来源 provider 形成有身份/真实时钟的八证券快照，选最新闭合共同日，裁切原 raw 日期，沿原 `qmt_minute_import.import_dataset` schema3/day DSB 导入和逐值回读，再调用原 `qmt_native_adjustment.prepare_inputs/read_native/assemble_window`。所有复权 OHLC 只由固定原 WT Reader 计算，不新增复权公式、金融账本或数据库。日线输出根/因子/参考/请求/NativeRead/候选窗口完整存证。

Native Import 和原 Reader 子进程处于现有隐藏 ProcessJob 的刷新工作进程树中，单次绝对截止有界；正常退出分别证明 Job树0/EOF/join/句柄。服务持续运行直到显式关闭；来源暂缺继续等待，不以一次刷新截止结束整个服务。源未知 capture_id 保持，后续只核原读取身份。

## AWP2 发布与消费

每轮使用新根。八证券逐证券原始日线可有不同尾日，先按来源 closed_through 限制并求共同日期；所有导入尾日裁至同一最新共同 basis，以符合原 QNA 最新日约束。QNA至少100日与32768行容量保持。

在同目录完整写入临时文件后原子替换部署选定的 QNA v1 文件。时间适配仅沿 AWP-P3，原候选另存；同日内容/因子修订必须产生新发布身份，不能仅按 basis 去重。完全同内容且同实收身份可保持原文件；实际重新接收的成功快照保留新时间和身份。发布最多32MiB，原 R24 `MarketWindowFile` 可直接读取并交原 RetainedInput/1.1.2。

status 分别呈现 `source_oldest_received_at/source_received_at/generated_at/published_at/basis_date/source_revision/factor_revision/publication_sha256` 及当前阶段/有限错误码/最后成功。缺源、缺闭合共同日、源过旧及原共享换名冲突转等待，保留最后成功字节；坏协议、身份或原 NativeRead 失败明确失败。每轮开始和发布前均检查截止/关闭/源年龄。

## AWP3 验收

首次真实 SDK 方法替身捕获→原Import/day DSB→原Reader因子复权→QNA→原子发布→原R24消费；接着新增闭合日、同日修订均更新并被读取。SDK日线/因子/参考实际调用单独计数，默认省略补齐时下载调用零；显式补齐沿 AWP5 单列副作用。所有输出只写隔离根，不操作 QMT/账户/GUI/活动实例，不用真实交易。

完整主链后做必要缺源/过旧保留、同ID未确认、原子发布、关闭及默认/时间语义回归，再普通安装/独立审查。真实来源 profile、实际 QMT、WRI 组合和最终生产整包由根统一接入，模块不自行切换现场。

## AWP4 同配置重启与唯一发布者

WT 正常退出后，新 control UUID 使用同一配置、工作根和发布文件启动。来源未上线时服务 ready 并持续等待；已成功发布文件及原实收时间保持。已生成的原请求、Native 与发布收据保留。

发布者复用 WT 已有 `_InstanceLease` 的 OS 文件锁机制，以工作根作为互斥范围；租约由同一 owner 持有到发布线程已 join 且 Native Job/管道/句柄均已确认关闭。未确认关闭继续持有租约，新 owner 不写当前状态或发布文件。正常释放及进程退出由原 OS 锁生命周期允许下一代取得租约。OWNER.json 只作代际留证，历史 owner/status 归档；不删除哨兵来绕过唯一 owner。

重启依据上代 STATUS.current_capture_id 和原 REQUEST 恢复未确认 capture；已确认成功的 capture 不重复发布，原读取收据保持 UUID/绑定/实收时间。同配置校验冲突明确失败。旧成功状态仅在发布 SHA 相符时恢复，不改写旧实收时间。验收先同配置 WT 正常两代启停，再实际 Source→Import/Reader/QNA→R24；随后核同根竞争 owner、关闭未确认租约保留及 Pending 原身份恢复。

工作根先持久保存 `guanheng.qna-producer-configuration.v1` 的权威配置投影及 SHA。规范化规则版本为1：路径 resolve/normcase，刷新数值统一为浮点，其余纯值原样保持。投影包含显式来源连接声明与 provenance、工作根/发布目标、全部 Native 制品路径及 SHA、Python/worker 路径、刷新间隔/预算/源年龄、日期/行数参数。只绑定 secret_env 引用，秘密值由受管环境提供，不进入身份文件。

每次取得 OS 租约后，先核配置身份，再恢复旧 capture、归档 owner/status、写状态或调用来源。冲突返回 `analysis_configuration_conflict`，旧配置/OWNER/STATUS/请求/发布字节保持。直接 provider 调用者必须传入明确的 `source_identity` 纯值；工厂由完整 source_connection/source 自动构成，不使用类名或对象地址替代来源身份。已有状态且缺配置身份的旧 a4 工作根明确拒绝自动接管，操作方保留原根，沿旧制品处理其未确认读取后再显式部署新根。

## AWP5 可选日线缓存准备

部署可显式增加 `history_preparation={connection,refresh_interval_seconds}`。connection 沿原 BoundHistorySource 四字段，连接原 v6 `market.history_prepare`；v7 连接仍仅执行原分析读取。完整补齐配置进入 AWP4 权威身份，刷新间隔沿运行时已校验值统一为浮点，因此合法等值的 `1` 和 `1.0` 允许同根恢复；真正不同的间隔仍在来源调用前拒绝。默认省略保持原读取及零补齐行为。

原 a7 已落盘的整数准备间隔身份保持原件，沿原制品处理其已有请求；本版本不自动改写旧权威配置。新部署根持久保存归一后的身份，版本间接管旧身份须有独立的配置迁移依据。

同 capture 先固定原 CLOSURE，再沿原 HPR 原八字段请求/绑定/结果留证准备八证券的 `1d` 缓存，成功返回后才由原 v7 日线、因子和参考读取形成原快照。每个请求独立原 UUID，派发前保存原 envelope 所需信息，结果未知只 GET 原身份；预算同时消费该 capture 的绝对业务截止、原 HPR 至多30秒及原 RPC 至多30秒，不重置总截止。终端原策略线程和 v6 SDK 调用路径保持。

首次准备仅选择当前 closed_through 日，已有暖机历史沿原 v7 start_date 及已下载缓存读取。后继从上次全部 HPR 已返回的尾日（含该日）到新 closed_through，兼顾跨日及同日修订；同日仅在显式刷新间隔到期后再次准备，多个 AWP 轮询可合并为一次准备，避免反复下载全部历史。最后准备记录只表达原调用已返回、coverage unknown，无法替代 v7 原日期/内容回读或证明完整暖机。旧历史缺少时保留旧窗口并等待，不擅自扩大初始下载范围。

同 capture 的准备计划/原请求/原结果保持，未确认准备不换 capture 重派；显式回收模式已确认未执行的失败沿 AWP6 交原 owner 开始下一观察；全部已返回后持久记录准备尾日与返回时刻。该时刻仅用于准备频率，分析数据年龄仍取原 v7 实收。补齐返回不保证新增日线，实际 basis 仍由原八证券日期交集与闭合上限决定。验收用真正改变缓存的 SDK 替身，经正式 HPR/v7 入口及原 Import/Reader/QNA/R24 完成首轮、新闭合日与同日修订，并核默认省略、原ID不重发及合并间隔。

日期窗口沿原 HPR `max_calendar_days.1d` 含首尾日额度拆片，每片独立原 UUID并依次完成，第一片保留原文件名以续核已落盘请求。原 observe 的单段观察用尽后，在同一 capture 绝对 D 内继续原 GET；耗尽 D 后保留原请求等待后继观察。原 HPR 的任务/Journal额度保持，耗尽时保留已知请求与旧窗口，不删除记录、重派未知或自行重建来源。

## AWP6 可选已确认只读结果回收

`source_connection` 与 `history_preparation.connection` 可独立显式增加与[公共回收协议](qmt-read-retirement.md)一致的 `read_retention={schema:'qmt.read-retention.v1',max_lifetime_ms:N}`。该声明进入原完整配置身份；AWP 适配器剥离此扩展后构造原四字段 BoundHistorySource，并核认证 profile 与声明相等。未声明时保持 a8 原读取路径与配置形状。

显式模式使用公共 `RetainedReadClient.read/prepare`，不创建第二份 Journal、后台线程或运输。每个原 slot 在 POST 前保存内容绑定 ID/票据；完整原结果与 requested_at/received_at 先持久，再 consumed。AWP 继续保存所有 slot、原快照及发布证据，Host/Source 仅回收它们各自已确定并满足公共条件的责任。来源年龄仍取原结果实收时刻。

HPR 原日期/SDK绝对D与分片保持，先准备后原v7回读；成功调用和覆盖继续分列。公共 Pending 保持原 capture/slot/ID，确定读取失败沿原 Unavailable；HPR 的 RetainedReadFailure 仅来自公共客户端已持久确认的受理前400拒绝或固定调用前拒绝，映射原 SourceUnavailable；原 capture/slot/请求/拒绝或终态记录保留，原 owner 下一业务轮开始新的独立 capture。RetainedReadPending、网络未知及原ID的404/410保持原 capture/slot/ID/截止，仅续核原责任；不能据缺记录换ID重派。Host/Source 重启时已有结果原值可重读，缺原结果的未知责任继续核原 ID，禁止删除 slot、换ID或重 POST 绕过容量。未完成快照继续绑定原认证，不把不同认证的读取混成一份。

验收先在固定小容量中跨越多个完整周期：SDK实际更新缓存→HPR/v7→原Import/Reader/QNA/R24，记录真实调用/结果先保存/消费确认/原容器最大占用与全部关闭。随后仅核必要 Pending/未知/重启续核及默认回归。普通WT角色及 Host/Agent 精确制品共同绑定；真实QMT、跨日常驻与生产分别验收。

显式回收模式的每个新slot沿公共RR6准入当前认证；AWP固定本capture首次BINDING并传完整expected_binding。新slot确认认证不同，在任何新请求受理前转原Unavailable，旧窗口及capture原件保持；下一业务capture重取认证。旧slot先核原责任；未知保持原ID，确认后再核capture来源一致。分析raw/factor/reference与HPR各自原连接的认证保持一致，不把重连前后的v7行拼成合格快照。


## AWP7 来源读取期间停止

发布者 request_close 把同一个首次绝对关闭截止交给工厂组合的分析读取与可选 HPR owner。每个 slot 开始读取前检查停止；原 retained/legacy 的内部轮询及新请求计划均检查停止。已经准入的当前 slot 保留一次原首次 POST 权利，覆盖公共客户端先持久 attempted 后尚未调用运输的窗口；其余交换停止准入，避免把确定未派发的读取制造成不可续行的未知责任。关闭后保留已有 capture、slot、UUID、原请求截止、终态和未确认责任。正在执行的 HTTP 继续沿原 RPC 截止返回；下一观察/轮询交换停止准入，发布线程按原关闭截止 join，原 Native Job 仍由原 owner 取消和回收。

每次组件关闭分别保留正常、pending 与失败证明。实际 HTTP 超过更短关闭预算时返回未确认；关闭预算、请求/SDK预算和线程强制终止策略均保持。自定义同步 client/provider 继续原接口，若实现 request_close(deadline=...) 则参与停止通知，其自身有界返回责任保持。

验收先在普通安装、固定解释器与正式 SDK/WinSHM 链中完成一轮原分析发布与策略消费，在活动分析读取期间请求停止，核停止后不再准入后续 slot、当前已准入首次 POST 原责任及 slot 保留及分析/采集/Host 正常收尾；再核原读取失回执、关闭期间等待、首次截止不延长、默认省略准备及已有回归。原 full034 错误原件保持，WT 上游新增修改零。

## 当前辅助视图发布

沿[SDO-R3-current](strategy-data-and-observability.md#sdo-r3-current-当前决策辅助视图)，启用辅助的AWP使用唯一派生函数，在原窗口上增加可选current_auxiliary。视图包含实际行情basis_date、派生版本、最多32个证券/字段值；每值保存统计日、全部依赖日期、真实known_by与来源摘要，sha256只由数据和行情基准形成。历史observations、分析价、逐bar辅助生效和原接收时刻保持原值。当前视图与历史富集报告分别输出，enriched_rows=0仍可拥有完整当前辅助值。

默认省略辅助配置时原窗口保持旧形状；Runtime新消费者接受旧窗口并清除请求中残留的当前视图。新生产者须和支持当前视图的V1/Runtime精确组合发布，旧消费者的严格窗口字段检查保持原拒绝行为，采用/回退沿Root统一角色恢复。

本发行普通包依赖精确固定guanheng-wt-runtime==0.1.0a15+currentaux.1、guanheng-strategy-v1==0.1.0a13及guanheng-native-analysis-core==0.1.0a3+currentaux.1，依赖解析不得保留旧严格窗口消费者。
