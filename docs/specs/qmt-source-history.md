# 源值分钟历史导入与原生读取

状态：accepted。类型：功能实现规格；前缀 RS。适用范围：CLI 原始历史页、CSV/QMI 导入器、WT Helper/DSB 及文件读取接口。实现与实际数据验收分别登记。

## 目标与根因

现有 QMI 把“标准化股/元、右端分钟”与“原生历史文件落盘”绑定，CLI 由三个 null 字段一起阻止导出。WT 本身接受 double vol/money，存储不要求成交量已为股。改动把存储语义显式区分为 source 与 canonical：新增 source 合同成为新接入的默认选择；旧 schema=1 canonical 行为及制品保持兼容。两者复用唯一解析、预算、Helper 写入及回读实现，不新增存储引擎或第二份业务数据库。

## RS1 清单与数值

QMI 新 manifest schema_version=2，仅代表 raw-source。顶层仍为 schema_version/profile/securities；securities/chunks/path/sha256 与 v1 相同。profile 严格字段为：

`provider,instance_id,session_id,generation,dataset_version,source_license,input_kind,timezone,minute_boundary,adjustment,factor_version,value_semantics,price_unit,volume_unit,amount_unit`。

- provider=Qmt，input_kind=synthetic/qmt_export；身份、版本、许可沿原有界类型校验。
- value_semantics=source；price_unit/amount_unit=CNY 或 unknown；volume_unit=share/lot/unknown。lot 声明仅表明源单位为手，本路径不自动推导每手股数、不换算。
- timezone=Asia/Shanghai；minute_boundary=left/right/unknown。unknown 是显式信息状态，字段不得省略或用 null 混同。
- adjustment=none、factor_version 空串；此次不引入复权路径。源声明不可由价格形态推测；无可信原请求/导出出处的历史不得虚构 none。
- 来源说明沿现有 dataset_version/source_license 与原 manifest/config SHA、SourceSession 及回执身份绑定；实现交付记录 API/版本、适用资产/日期和各字段证据或 unknown。无需新增来源数据库、强制独立证书或额外实时探针。
- v2 无 volume_to_shares/amount_to_yuan，出现即拒绝，避免因子 1 冒充标准化或产生“是否已经乘过”的歧义。显式转换仍选择旧 v1，不能靠省略字段切模式。

CSV 继续七列 `timestamp,open,high,low,close,volume,amount`。源 double 以现有 max_digits10 输出，Python float 解析后直接赋给 WTSBar：OHLC 原值，vol=volume，money=amount，settle=close，其余仍零；不得乘系数、四舍五入、按金额重建、删除零量正额记录。有限数、正价格、量额非负、日期范围、排序/重复/跨片检查保持；来源四价范围异常按RS8独立记录质量，canonical继续要求OHLC一致。double 数值往返是承诺，任意原文本词法或源未表达的成交精度不在承诺内。

## RS2 时间与文件语义

v2 始终保存源标签：left/right/unknown 均不平移一分钟。WTS date/time 只编码现有带时区整分钟标签。sidecar 明示 timestamp_semantics=source_label，minute_boundary 为源声明。不得把字段名 first_right 用在 source 产物：v2 收据使用 first_label/last_label；时间标签始终带 +08:00。

未知区间可写入标准 m1 DSB、可按原标签读出，coverage 保持 unknown。闭合分钟回放、跨源对齐和涉及区间的派生聚合要求已绑定 left/right；unknown 不能冒充原生策略预期的闭合时间。已有 raw 文件不因后来确认边界而原地改写，元数据修订/规范化输出使用新版本新根。

目录、压缩编码和原 Helper ABI不变：`his/min1/SSE|SZSE/<code>.dsb`。新增 sidecar format=2，与旧 format=1 严格区分；包含原公共身份/qualification/dataset_version/source_license/adjustment/factor_version/timezone/content_id，新增 value_semantics/price_unit/volume_unit/amount_unit/timestamp_semantics，minute_boundary 如上，不含转换系数。qualification 保持 DevelopmentVerified，表示本次导入及回读证据，不提升来源事实；coverage 始终独立。

## RS3 数据集与消费者

一个 manifest 只有一个 profile，所有证券和分片受该语义及适用范围约束。来源版本、身份代次、单位、边界或复权变化应使用新 dataset_version/新根，不允许合并成同一数据集。unknown 不证明源在所有日期/证券单位一致；来源记录必须给出本批适用范围，观察到变化须拆分。导入器只能核声明和绑定身份，无法从无标签 CSV 数值自动识别隐含单位变化；不得声称自动证明源范围一致。原始输入保留 SHA 和来源回执，缺口保留，满页和空页沿既有协议处理。

原 WT DSB 不携带单位，也不会自动读取自有 sidecar。提供的自有读取结果必须同时包含 bars 与 metadata，禁止返回无来源的裸数组给既有 canonical 服务。

NativeHistory 新增 `read_source_store(root, exchange, code, *, expected_import_sha256=None) -> HistoryResult`，返回独立 `SourceHistoryBar`（原字段、带时区源标签，feature_version 不冒充 market-v1）及 `SourceHistoryMetadata`。元数据含上述单位、边界及内容身份；不增加 expected_times/calendar_version 参数，返回 missing=()、calendar_version=""；本阶段 source 结果 coverage 固定 unknown，避免赋予源标签网格完整交易覆盖含义。新 DTO 仅表达语义，底层文件 ABI/回调/有限性/哈希校验与原 Reader 共用。

新 source Reader 默认绑定本根已有成功 `qmt-import.json`，不依赖可选 `.guanheng-frozen`。有界读取收据（沿实例 max_file_bytes 上限，超限明确失败），严格解析 schema_version=2/status=passed、证券唯一条目和完整必要字段；用调用参数定位唯一 symbol/exchange/code，对应 path 必须等于本证券标准 DSB 路径、metadata_path 必须等于其 sidecar 路径，拒绝缺失、重复、越界或错配。按该条目的 sha256/metadata_sha256 校验 DSB 与同一缓冲区的 sidecar 字节，再解析这份 sidecar；核 content_id、来源/profile 和收据的对应关系。读取前后保持收据/sidecar/DSB 身份核对，继续复用原文件 ABI 对受控快照的验证；不全根扫描，也不新建索引或证书。

信任界限：默认把调用方选定的受控根成功收据作为本次预期身份，检测文件或语义相对收据的单侧修改；读前把收据和全部文件一致替换的行为，单靠该根无法证明旧身份。调用方已有独立 artifact identity 时，可传 expected_import_sha256，先对同一收据字节校验该 SHA；未传时不宣称抗整套一致替换。此可选摘要复用既有制品身份，不新增许可流程。普通 importer 生成的成功收据已经足够提供默认绑定，无须生成冻结标记。
原 `read_store/read(... HistoryMetadata ...)` 保持 canonical 合同，读 format=2 返回清楚的固定类别不兼容；禁止默认 MarketBar 容器接受 source 值。新入口同样拒绝 format=1，调用者必须明确选择。现有 HTTP/history_runner/ReaderHttpClient 和 C++ NativeHistoryStore 继续 canonical，只拒绝 raw 的明确版本，不静默解析或自动转换。

后续自有策略通过 SourceHistoryMetadata 直接看见 volume_unit/amount_unit/price_unit/minute_boundary。只用 OHLC 的策略可声明忽略量额，仍须按自身时间使用方式确认边界。每个指标按自身公式判断所需单位/区间；实际需要的语义未知时才阻止该项计算。纯价格序列或同一稳定尺度内的比例指标可按其输入合同消费 source 值，不设“所有量价指标必须确认股数”的门槛。直接使用原 WT CTA 的策略须由其自有启动入口读取并校验同一 sidecar，将元数据通过既有策略参数或自有策略初始化配置显式传入；原 WT 框架不会凭 DSB 自动传递单位。本轮交付不声称已完成所有策略参数接线，不修改 WT。

## RS4 CLI 与交付顺序

CLI 新 config schema=`qmt.history-cli-config.v2`：网络/read_profile_version、请求根、期限、容量字段不变；source_profile 精确字段集为 `dataset_version,source_license,input_kind,asset_class,timezone,minute_boundary,adjustment,factor_version,value_semantics,price_unit,volume_unit,amount_unit`，asset_class 固定 cash-equity。配置拒绝 provider/instance_id/session_id/generation 四个派生字段。构造 manifest 时 provider 固定 Qmt，instance_id/session_id/generation 取原响应的 SourceSession；其余复制上述配置字段，但 asset_class 只用于配置校验，不写入 RS1 manifest profile。该归属沿当前 QmtHistoryMain.cpp 的 export_qmi，不增加双份身份输入。新 v2 默认导出 source manifest，非空成功记录不再由单位/边界 unknown 阻止 CSV/manifest。旧 config v1 保持原行为，不把旧配置 silent 升级。正式入口示例改为 v2 source，用户显式需要股/元规范化时才选 v1。

先交付：离线 v2 importer、format=2 sidecar、source Reader 和合成原 Helper 回读；接着交付 CLI v2 同一原始页导出，复用现有请求/恢复/分页，不增加 SDK 调用。上述可用合成材料完成代码和异常验证。真实绑定只需真实来源可确认的 API/版本/身份、实际七列及时间编码、请求 none/fillfalse/subscribefalse；单位和区间尚未知时如实记录 unknown，允许 raw 落盘。确认 right/left 或股/手不是 raw 写入前置，而是对应回放/转换使用的前置。

## RS5 保留的约束与删除的自设前置

删除新 source 导入的正数换算因子必填、股/元默认解释、right 标签强制和单位未知整体跳过导出。无需新增每手精确股数、整数 volume、成交额反推、VWAP 必在 OHLC 内、完整 240 根、生产精度或完整市场覆盖门槛。

保留来源身份与模式声明、none 复权、真实字段/时间编码、有界输入与原截止、SHA 同字节解析、独占新根、原 ABI/Helper 身份、完整逐字段回读、失败不写成功收据、旧根不覆盖。保持既有 max_bars/max_input_bytes/max_total_bars；恢复原请求 ID，不新增探针、下载或交易调用。已知错误与旁路错误沿原首因和资源关闭机制处理。

## 验收最小集合

1. 同一 v2 合成样本含 fractional double volume、零量正额、未知单位/边界，CSV→DSB→source Reader 六个 OHLC/量额字段逐值相等；时间不平移，sidecar 与收据不出现 shares/right 伪标签。
2. v2 left/right 输入时间均原样；旧 v1 left 仍 +1 分钟并乘原系数。v1 原测试全保留；同一解析及 native 写验逻辑无第二实现。
3. v2 因子字段、错误复权、声明跨 profile 混片、无效枚举、重复/倒序、NaN/Inf、负量额拒绝；不以零量正额或分数量拒绝合法行。
4. format=2→canonical read_store/现有服务失败；source Reader 返回完整单位与来源。未知区间不被当作已知闭合时间。普通多证券成功导入根不带冻结标记也可原值读取；读取前仅将合法单位 unknown 改 share、仅改边界 unknown→right、换错证券 sidecar 或修改 DSB，均相对原收据拒绝；收据缺失/不完整/条目重复或错配、格式混同拒绝。整套一致替换的检测仅在调用方提供原 expected_import_sha256 时断言，未提供按已声明信任界限处理。
5. CLI v2 用既有合成页完成 unknown-profile 导出并复用相同原 ID恢复；不增加 SDK 次数。v1 null 行为兼容；配置 hash、字节/行/文件数/原 D 仍生效。
6. 原 Helper 失败/回读字段差、后证券失败、预算超限、已有目标、新根争用和元数据写入失败复用现有根因回归，确认无成功收据、旧根不变、owner 关闭。必要真实 sample 后只核来源/实际字段及一批原值回读；全量扩展另按证券日期库存与原有限批次覆盖报告推进。
## RS6 命令输出编码

导入 CLI 的参数错误、ImportFailure 和成功结果均输出 ASCII 转义 JSON（ensure_ascii=True）；调用方按 UTF-8 解析后恢复原 Unicode 字符串。stdout/stderr 路由、退出码和字段保持原合同，磁盘 JSON 文件仍为 UTF-8。该合同适用于 GBK、UTF-8 等 ASCII 兼容流；显式 UTF-16 流及人工 --help 输出不在此机器结果保证内。回归以真实 GBK 子进程验证三个分支，成功记录含中文及非 GBK 字符。

## RS7 显式来源值查询与图表消费

状态：accepted。为已导入source数据提供独立history.source-query；保留旧canonical action及默认配置。API仍guanheng.market.v1，新路径/api/market/v1/history/source-query，SDK增加source_history_query。request精确exchange/code/from/to/limit，沪深六位代码、闭区间标签、limit为1..2000；不接受周期聚合或日历完整网格。成功data为metadata/bars/coverage=Unknown/missing_minutes=[]/selection={period_minutes:1,limit}，取范围内最后limit根并升序。metadata完整保留SourceHistoryMetadata的来源四字段、资格、dataset_version/content_id/许可、none复权、Asia/Shanghai、单位、minute_boundary及source/source_label；每bar为symbol/minute及OHLC/volume/amount。失败沿原status/空data，不添加委托能力。

来源文件服务通过显式mode=source-store配置单受管store_root与独立import_receipt_sha256、native_reader库/SHA、max_bars/max_cache_bars及preload_symbols，复用原NativeHistory和既有MarketHTTPServer。创建线程拥有Reader，预加载完成才提供HTTP，LRU以实际bars总数受限，时间范围由原标签bisect选尾部。普通服务from_env路径不变；来源服务不需要QMT终端、SDK、Host或券商凭据。来源根的成功收据同时拥有证券清单，不新增数据库/目录索引。

观衡通过GUANHENG_HISTORY_SEMANTICS=source显式选择新SDK action；默认canonical保持原图表schema1.4。来源模式的分钟图schema1.5，仅1m；occurred_at保留来源标签，仅转UTC传输，不平移为左端，也不聚合5m。native_source显式chart_minute_boundary=source_label/value_semantics=source/timestamp_semantics=source_label及单位；中文界面说明时间/量额口径，不把unknown解释成股数或闭合分钟。标准化模型保持独立。

观衡的显式部署读取预算GUANHENG_MARKET_TIMEOUT_SECONDS允许(0,30]秒，与现有SDK上限一致，默认2秒保持。来源历史首次访问需要完整解码所选证券，离线source部署示例选择30秒；主图/基准、SDK交换及关闭继续沿原同一请求/关闭截止收紧，禁止为单次读取重新延长预算。真实验收须包含未预热的观衡首次访问。

主路径验收：真实离线DSB→原Reader→独立HTTP→SDK→观衡分钟接口→浏览器可见图表及来源标签。先完成该路径，再集中覆盖异常、恢复、默认兼容回归与独立review。独立制品/生产接线仍须按发布阶段验证。


## RS8 来源价格范围质量与原值保存

状态：accepted。本机国信官方getMarketData与DAT同分钟逐值核对确认，来源会返回open或close超出其high/low的记录。原值导入负责保存来源事实，OHLC一致性作为独立的数据质量结论；不能以不一致拒绝整只来源证券，也不能调价、补价、删行或把原值冒充标准K线。该规则作用于全部source记录，不增加09:31、证券代码或日期特判。

source入口继续拒绝非有限数、非正价格、负量额、非法/重复/倒序时间及布局/身份变化。四价范围按同一纯函数分为consistent、open_outside_range、close_outside_range、open_close_outside_range、inverted_range。导出与导入输出有界质量摘要，异常证券的QMI成功收据项与sidecar增加price_range_quality；包含schema、checked_rows、inconsistent_rows、各类counts、至多8个first_labels。正常证券仍保持原字段形状。摘要受原SHA与成功收据绑定；source Reader根据实际读取逐行重算并核摘要，SourceHistoryBar公开计算属性price_range_status，metadata给出price_range_inconsistent_rows。旧source文件无摘要时仍按旧一致性约束读取；不能将缺少声明的异常文件视作新合格产物。

原schema1 canonical导入、MarketBar和canonical Reader继续严格OHLC一致性。格式2不自动进入旧策略/标准服务。来源HTTP/SDK既有字段形状保持，原始四价完整返回；需要标准OHLC的消费者自行使用其既有一致性检查。观衡K线图保持严格绘图，遇异常来源记录给出含分钟标签的中文质量原因，不能修价或静默删行后显示为正常。该显示限制不影响原生来源存储和原值查询。

本项先完成DAT→QMI→原Helper/DSB→SourceReader及显式来源查询；现有SHM分钟协议的严格OHLC准入保持，后继在线原值质量协议按单独版本接线，不用本项静默改变已运行协议。验收包括三个实际证券完整转换与逐行回读、异常计数/标签、原输入保持、正常旧产物兼容、canonical拒绝及来源摘要错配拒绝。


## RS9 多批来源历史的统一证券查询

状态：accepted。全库存按有限批次导入，每批已有独立成功收据和来源session；统一读取直接路由到这些WT原生store，保留原DSB、sidecar及成功收据。source-store及canonical默认合同保持。新增显式mode=source-stores，共用native_reader/max_bars/max_cache_bars/preload_symbols，stores为1..1024项{store_root,import_receipt_sha256}；无新价格存储或第二份行情索引文件。启动仅依据显式配置的原成功收据在内存登记证券，不扫描磁盘目录或追随增长中的运行日志。

所有根为独立绝对路径，成功收据SHA必须相符；各批同provider/instance_id，每证券全局唯一，重复证券或根拒绝，不能靠顺序覆盖。总证券最多10000，总收据输入最多16MiB；配置文件只有source-stores允许最多1MiB，其余模式保持64KiB。新模式preload_symbols可为空，按需加载时仍沿同一原NativeHistory.read_source_store做完整身份和字段检查，Reader由原创建线程拥有、缓存条数预算与LRU共用。清单冻结在实例创建期，新导入批次须生成新受管配置并使用新实例，不热改运行实例。

每证券返回其原store实际source/session/generation及单位/时间/质量元数据。capabilities的单一source在多个根时明确表示离线收据集合会话：provider/instance_id沿共同来源，session_id=source-stores:加排序收据SHA列表规范JSON的SHA256，generation=1；同一集合排序或物理搬迁不改变它，任何成员收据变化则改变它。该集合会话仅供能力说明，不能作为每根数据的原采集session；history.reason明确提示逐证券metadata才是原始来源。仅一个根时沿原source。混合provider/instance_id须分别建立服务，本期不虚构共同来源。

HTTP action、SDK方法及观衡source图表协议保持，原查询按exchange/code自动选择对应store。主路径先验不同原始session的两个真实成功批次，交替证券经DSB→原Reader→同一HTTP→SDK读取，核对各自metadata与值，并正常同线程关闭；整库尚未处理完时只配置已完成批次，结果不得称完整市场覆盖。之后覆盖重复/身份错配/预算、默认单根及现有Reader兼容，再独立审查。


## RS10 已完成目录生成统一读取配置

状态：accepted。提供外部离线prepare_source_config/模块CLI，从qmt.full-history-catalog.v1生成显式source-stores配置。只接受status=completed、coverage=unknown、value_semantics=source及1..10000个唯一沪深证券项；imported项使用原store/import_receipt_sha256/rows，empty项计数而不注册。running、completed_with_failures及失败项保持未完成，不生成正式整库候选配置。目录输入上限32MiB，可选expected_catalog_sha256绑定已有输入身份，输出摘要始终记录实际目录SHA；不要求新增独立证书。

按解析后的绝对store根与原收据SHA去重，同根出现冲突SHA拒绝。复用NativeSourceMarket完成根/来源/预算/收据及受管Reader依赖验证，精确核对其全部注册证券、所属根、收据SHA及条数与目录imported集合一致；多出、缺少、重复及数量错配拒绝。准备阶段不扫描价格目录、不读取增长中的progress/catalog-items.jsonl，也不重写原DSB、sidecar、收据或原CSV。没有preload时不解码全市场历史，实际每证券原文件内容仍由首次查询的Reader校验。

新配置沿调用方显式Reader路径/SHA、max_bars/max_cache_bars/preload_symbols，最多1MiB，创建新文件且保留既有目标。验证用Reader由准备线程创建并在写配置前关闭，异常保持无成功配置。配置不含token，完成不启动HTTP/QMT、不切换运行配置、不授标准单位/闭合分钟或完整日历覆盖。CLI输出ASCII转义JSON和退出码，敏感异常正文不输出。实际全库存尚在导入时，用明确标记的已完成批次切片验证生成及后继HTTP/观衡链；它不能替代全5342项最终验收。


### RS10 显式排除已失败证券

状态：accepted。主路径允许其余已成功证券先统一读取：prepare_source_config新增exclude_failed_symbols，CLI对应可重复--exclude-failed-symbol。默认空集合继续拒绝completed_with_failures。显式非空时仅接受已结束的completed_with_failures目录，参数须为唯一沪深证券且与该目录所有failed项精确相等；禁止排除imported/empty、漏列失败或接纳running/failed目录。仅跳过这些已失败项，原目录、失败原因和数据不改写；其余全部原收据注册集合继续精确比对，隐藏失败证券混入同一store也须拒绝。

目录允许附带tail_refresh=pending_current_qmt_download，准备结果原样返回；未声明返回unspecified，不推断新尾部完整。成功摘要增加catalog_status/excluded_failed_symbols/tail_refresh，原catalog_sha256绑定整份含失败目录，配置仍为原source-stores形状、Reader及运行实例语义保持。该输出是显式排除集的已导入子集候选，失败目录保持原终态，不能报告完整市场/全部尾部就绪。默认completed旧输入和旧CLI调用保持可用，空排除不放宽准入。

## RS11 QMT DAT有符号量额与旧制品边界

状态：accepted。在当前国信缓存版本的已核样本中，offset24按signed int32、offset32按signed int64读取与官方只读getMarketData同点相符；这是本适配布局的样本验证，不构成供应商全版本二进制格式声明。offset28..31不由本适配消费。旧无符号读取会把负量额转成超大正数；本次改用唯一qmt_dat_layout常量/Struct解码，价格千分之一编码与时间、WT ABI保持。新导出dataset_version=qmt-local-dat-layout.v2、layout=qmt-minute-cache-64.v2，区分既有制品。负量额以quantity明确拒绝当前证券，保留原DAT/partial，不调零、不取绝对值、不删行冒充成功。其他合法证券继续批量处理。

Importer与SourceReader共用local_dat_counters_valid约束已识别的v1/v2 DAT profile：量不超过int32正上界；旧v1金额double达到2**63时不能区分符号回绕和边界舍入，保持拒绝；新v2已经在整数解码阶段排除负值，允许合法int64上界的double舍入。其他来源不套用DAT范围，canonical默认保持。旧v1正数且范围明确的记录与新有符号解码等价，可在原输入SHA及逐行有符号兼容审核后复用；受影响证券所在旧store整批退出新配置候选，使用修正入口重做，旧文件保留且旧Reader路径也拒绝已识别回绕。

续作先完整回收旧owner，审核全部已完成原DAT及其捕获SHA，冻结兼容清单；新运行器只采用通过审核且整根不含不兼容证券的原成功批次，其余重新转换。冻结包显式包含新布局模块，原8小时wall/monotonic截止保持。quantity拒绝沿现有确定输入拆批，仅该证券失败，不将供应商负源值视为可交易数据。最终completed_with_failures及拒绝列表如实呈现，完整配置准备仍要求其已声明的完成集合。不得宣称本修复解决了负源数据的供应商成因、指数内存/API与DAT精度差异或原8根价格范围差异。


负源值的成因调查与我方unsigned错读修复分别验收。官方接口和DAT可能共享同一缓存，同值不能作为独立真值；供应商生成负值的触发条件未证实前，状态保持待核，不以调零、取绝对值、删09:30或修改解码类型宣布问题已解决。

## RS12 显式源值按需读取与缓存补齐

状态：accepted。本切片在自有Python来源历史层接通正式 `history.source-query` → 已安装HPR Host/原认证SHM → 原策略线程缓存读取/显式download_history_data → 原Helper导入 → 同一HTTP/SDK重读。旧source-store/source-stores/source-catalog默认离线行为保持；canonical、日线及策略闭合分钟接口保持。新增显式source-preparing部署模式，包含原base来源配置与preparation配置，只有preparation.enabled=true才允许本切片自动补齐。调用方继续使用现有MarketClient.source_history_query，不增加共享SDK协议或账户权限。

### 范围、事实与结束依据

本切片处理past-date 1m及有界闭区间，正式查询覆盖来源支持的沪深证券，按RS15省略逐只证券配置；当日最终修订或规范化沿对应来源能力处理。源profile显式声明source单位/边界/许可，unknown保留；固定请求none/fill_data=false/subscribe=false与原来源身份一起留证。不按240根、工作日、首末行或OHLC形态推断交易网格/覆盖。公开coverage始终Unknown、missing_minutes=[]，同一次query只返回同一SourceSession的原值。

原QH-R2/v6的end.date()<as_of_date合同保持，按需入口对当日及未来窗口在任何源请求/补齐之前明确NotSupported。当日断线补齐还需要独立显式版本、可信同会话源时钟及形成中边界规则，本切片不放松旧校验、不伪造as_of，也不以终端外厂商API对照授予该能力。

一次源缓存窗口观测复用原history_1m的唯一结束合同：固定窗口、每页同时满足原max_calendar_days日期跨度及自然分钟跨度不超过max_rows-1，确保所有可能的整分钟记录均容纳于页；源端仍核rows<count、整分钟、唯一有序、边界及值。按自然分钟计算的是容量上界，不授交易分钟日历。读取前后各片必须绑定同一来源，否则失败且不发布。源页结束仅证明该次缓存查询结束，不能证明缓存已有全部券商历史。

优先返回原已发布根。原离线数据若实际含请求闭区间的每个自然分钟，可直接返回；此判断不改变Unknown语义。其他未观测窗口先读取来源缓存，实际自然分钟全有则无需下载；否则在部署授权下向原HPR提交一次补齐，再重新读取同一完整窗口。call_returned仅表示函数返回；只有后续实际缓存行通过原Importer、Helper写入及逐字段回读才发布。稀疏/空页保留实际事实，空页不写空DSB；不把空页或下载返回当作市场覆盖。

### 原请求恢复与不可重复副作用

每个规范化证券/窗口拥有有界采集收据目录，保存配置SHA、原binding/profile字节身份、HPR及缓存查询原UUID/原请求字节、GET终态及输入/产物SHA。通信准入/终态/恢复仍由原Host Journal拥有，不建立第二套通信或业务数据库。第一次POST前先持久原UUID及已尝试事实；超期、连接丢失、进程重启或来源重认证后只查原UUID，不换ID自动重新下载。派发与是否执行不明时保持原未知，不将404、超时或新binding解释为未执行。

HPR成功或结果未知后均可执行独立只读缓存回查，读取的新SourceSession独立标注。未知补齐保持其原收据；后续真实读到的行可作为缓存事实发布，不能把它改写为下载成功。重复已发布窗口直接通过原Reader查询，零新增补齐。失败或尚待终态返回原Pending/Unavailable且data为空；SDK预算超时不等价于服务端取消。原请求跨重启恢复只使用收据中已存在的身份，没有无限循环轮询。

### 独占新根与同一服务可见性

旧根、旧成功收据及档案身份保持。每次发布使用新独占根：CSV/QMI schema2 → 原import_dataset → 原Helper → 原DSB完整回读/成功收据。新根只含本次同一来源缓存实际读得的行，禁止把旧会话行换上新会话标签或跨谱系合并。收据明确保留HPR/读取身份和原profile。NativeSourceMarket继续负责唯一Reader/标签选择/LRU；准备层只按已观测窗口选择原根或新根，最多保留原base Reader和一个活动窗口Reader，两者缓存上限分别显式声明。更换活动根先关闭旧owner，旧返回值副本保持。

SHM运输generation是nonce字符串；QMI的数值generation不能冒用它。本入口source.instance_id取原host_instance_id，source.session_id取完整原binding的SHA摘要，数值generation=1仅表示这份固定绑定捕获。原nonce/route/capability与三B仍完整保存在采集收据；不同运输代际形成不同session_id，不宣称券商登录会话或可排序来源代次。

本地发布尝试与原来源请求事实分离。首次窗口目录在首receipt原子提交前保持无源调用，只有未提交临时文件时可恢复初始化；已存在原receipt保持原UUID。CSV/manifest半写或Importer已建根而成功收据未发布时，保留失败目录，从同一冻结缓存结果创建新独占导入尝试；显式max_import_attempts(1..16)限制每窗口尝试根和残留receipt临时文件数量。任何本地重做均不重派原HPR或改写原根，成功收据完整验证后才复用产物。

采集收据持单写者OS锁；枚举、窗口数、页数、行/输入/响应字节、文件及缓存容量均显式有界。HPR/缓存页每次只消费原总deadline剩余预算；SDK/Helper原生调用不可抢占，晚回后不得启动后续阶段或授本轮及时成功。原ManagedLocalProcess/Job拥有进程硬回收，Reader及HTTP保持创建线程所有权，关闭未知继续保留owner。

### 验收

先跑正式HTTP/现有SDK入口 → 已安装Host → 真实SHM → 实际3.6.8完整正文SDK替身 → 缓存新增行回读 → 原Helper/DSB → 同一服务/SDK看到新增分钟，并以真实既有历史样本逐字段消费。随后核重复观测零新增补齐、重启/重认证原HPR UUID、未知结果不重派、来源漂移不混写、旧根SHA保持、正常/超期资源回收及默认离线兼容。真实QMT下载、市场覆盖、单位提升、当日闭合及生产发布由主会话独立验收。


### RS11 补充：全库存续作与源更新

无异常证券先按稳定输入导入，已识别异常证券显式隔离，保留源值及失败身份。并行分片互斥覆盖原计划；仅按已有成功收据和内容SHA复用已验证历史快照，下载更新后的尾部保持pending，结束后统一核对并补入新根。转换期间源身份变化拒绝本次输入，有限重试后仍变化的证券保留failed，禁止宣布全库存完整。多个分片共享原wall/monotonic业务截止，受管隐藏运行；终态目录仅在全部分片结束且成员精确一致后生成，失败目录不得声明全市场就绪。活动配置沿独立发布步骤。


## RS13 最近N根选择、有限尾窗与分段来源

状态：accepted。继任RS12的查询选择与补齐准入；原RS12的HPR身份、独占根、原Helper/Reader、总截止与关闭责任保持。原source-store/source-stores/source-catalog响应保持；source-preparing继续显式enabled，不改App的原from/to/limit请求，不要求调用者伪造窄from。

### 选择与源端预算分离

history.source-query的from/to是允许选择的闭区间，limit表示其中实际已发布的最近最多N根。它们不构成要求密集填满的自然分钟集合。准备层先读取原base及同workspace已发布的新根；按原标签选尾部，不按整个请求跨度拒绝已有可读数据。若已有最近N根且尾标签等于to，直接档案选择，不访问Host；coverage保持Unknown。同一尾窗已有未发布原准备收据时，选择仍成功，观察保持Partial及原UUID/Unknown等原事实。组装观察时只读取本地已核原请求结果，原待定请求由历史补齐 owner 后继续核，不将其标为无准备身份的Archive，也不推进源任务。

其余允许准备的昨日及以前请求，最多推进一个显式有界尾窗口：start=max(from,to-(max_window_minutes-1)自然分钟)，end=to。该窗口仅为部署容量/副作用范围，不能解释为交易网格、N根必在其中或市场已覆盖。原history_1m仍按max_rows-1/max_calendar_days分片且固定同一binding；limit较小也不放松原rows<count结束合同。最多一个原HPR任务，先读缓存；缓存实际条数达到min(limit,尾窗自然容量)时可直接发布，否则允许原HPR一次再回读，稀疏和零行事实保持。尾窗之外缺失、预算耗尽、源不可用或数量不足时，已有可读数据仍作为Partial选择返回，准备状态和观测范围明确；空数据仍沿Pending/Unavailable等原失败合同。全请求跨度不授扩大源任务/SDK窗口的权限。

当日/未来窗口不启动源读取/下载；可读档案继续返回，观测明确NotSupported/Partial。旧QH-R2不变。原生晚回超出原总D仍不能授及时成功；已有数据不会延长截止。早期空缓存收据及未知原下载保持，不自动换ID重派；异步后续回查须在明确有界的原身份恢复合同内实现。

### 多根选择与公开证据

同一公开服务同时消费base及有限已发布新根；只注册原窗口成功收据，不扫描DSB价格目录或改写旧根。至多一个活动窗口Reader，原base和活动根继续有各自显式缓存额度。累计读取的窗口收据字节受max_bytes限制，根数受max_windows限制，合并只保留最新最多limit行。后续准备或再次注册超额时，沿本轮最近一次完整验证的选择返回Partial，保留其最新行、分段来源和已知原准备身份；此前没有完整选择才回退已核base。重叠分钟六字段相同才去重，按当前尾窗、已有新根、base的显式顺序选其真实行证据；不同原值在最终选择内返回Conflict，不凭目录顺序覆盖或修价。

单谱系选择保留原metadata。跨谱系新增data.provenance，按{offset,count,metadata}连续覆盖每一根返回bar，metadata保留该根原source四字段、content_id、版本、许可、单位、边界和资格。集合metadata.source使用精确{kind:"SourceSelection",provider:"Qmt",selection_id:<SHA256>}，不含instance_id/session_id/generation，不授统一捕获身份。集合dataset_version固定前缀source-selection.v1，content_id及selection_id绑定规范化bars和完整分段证据；公共单位/分钟边界只给共同值，否则unknown。原许可证逐段保留，集合许可字段明确指向provenance。SDK的source_history.py对集合/分段/摘要做完整严格校验，旧普通源响应继续有效；共享SDK清单及App源码保持。

source-preparing的成功data另含observation，schema=qmt.source-selection-observation.v1：state为Archive/Observed/Partial；source_window为本次有界{from,to}或null；source_rows为实际源根条数；requested_limit和selected_rows精确回显；preparation_state为NotNeeded/CallReturned/Unknown/Pending/Unavailable/NotSupported/Budget；preparation_request_id保留原UUID或null；reason说明实际观测及待补范围。Observed只在源根实际条数达到min(limit,公开闭区间自然分钟容量)时使用，仅表示这段缓存事实已回读；窄窗边界相同仍须核实际数量，不足保持Partial。所有状态均coverage=Unknown。Ok表示已有值的合法选择，不声明请求范围/市场完整或下载成功；Partial/原HPRUnknown不能改写为已补齐。

### 验收

先用固定安装Appa17的原GET（from仍为原最早标签）重现已有尾部最近5根：原SDK、正常build_native_chart/HTTP路径得到五根原值，Host新增操作0，原lifespan/两个owner正常关闭。随后同一服务公开查询触发有限尾窗，实际安装Host/认证SHM/完整3.6.8正文替身回读新增行，经原Helper/Reader发布，原App同形选择按limit返回新尾部。跨原base/新尾根的最近N根保留精确provenance；重复零新增HPR，未知/失败保留原ID及明确Partial。全部资源回收与原根SHA保持。真实QMT、当天协议、市场覆盖、App生产激活/发布由根另验。


## RS14 异步下载后的有限缓存再观测

状态：accepted，继任RS13的固定empty终点；公开SDK015形状及RS13选择、原HPR和发布合同保持。只对昨日及以前、已经有原HPR且其后读为空而尚未发布的原窗口启用。已发布根保持不可变，重复零源调用；初次非空发布沿RS13，不跟踪已发布稀疏根。

### 显式预算与身份

preparation可选新增follow_up，缺少时原行为保持；提供时必须精确声明enabled=true、max_attempts(1..16)、interval_seconds(0.1..3600)、total_seconds(1..86400)、rpc_timeout_seconds(0.1..30)、journal_records、journal_bytes。间隔须不大于总时限。每窗口原HPR规划时固定启动跟踪总截止，页面刷新/limit变化/服务重启均不延长。每次公开调用最多推进一次后续观测；每次推进（含未决原只读ID的恢复）先持久消费一次max_attempts，设置下一可运行时间；间隔内不访问来源。每次RPC另受声明上限及原服务总D限制。

排程在原独占窗口收据v2内保存；原before/prepare/after和每次后续只读capture保持原bound/profile/UUID/attempted/终态，Host Journal仍唯一拥有通信/执行事实。后续阶段只调用market.history_1m，原HPR Unknown/CallReturned及原UUID保持，任何断开/404/超时不授第二个下载。未决只读capture沿原UUID查询；下一次独立缓存观测只有在前次完整读到空缓存后才产生新只读UUID。后续原pages仍按max_rows-1/max_calendar_days且同一次捕获固定binding，跨再观测可换新binding并保留新profile谱系。闭合日保留模式若认证路由、能力和其余来源身份相同，且仅Host实例或传输代变化，则保留原HPR和各代页面，沿原后续观测预算从当前代重新只读整个窗口。旧未完成页面继续由原请求交接任务核查，当前代不拼接旧页或重新下载。

闭合日换代回查后仍缺数据时，如果窗口尚无下载计划，或者只有本地计划且原保留槽文件和Host ID均未生成，可以在当前已核绑定下执行第一次下载。沿原窗口与后续总截止，下载终态仍走原after全窗回读。原保留槽或Host ID一经产生即保留并按原身份处理。

保留客户端按原票据查询得到明确的 `read_ticket_ended_unretained` 时，分钟读取 owner 保存原分页ID和结果无法领取的证明。闭合日全窗可在原节拍与原预算内创建独立的只读观察。原分页证据保留，未知下载继续按原ID核查；临时404和网络超时仍只续查原ID。

跟踪时限使用持久Windows uptime毫秒；同时保存墙钟减uptime的锚，倒退、系统重启或墙钟跳变超过5秒时停止后续来源调用并明确Budget。恢复始终使用原deadline，固定运行次数与间隔；原生晚回不能授及时成功。已经完整核验并冻结的非空只读结果可在原本地导入责任下恢复发布，不产生新源请求；每次调用仍遵守原D。

journal_records/journal_bytes声明该workspace需要的Host配置容量，不能代表动态空余额或自动预约。最坏任务记录数为max_windows*(1+(2+max_attempts)*max_pages)，字节下界按每条(bound max_request_bytes + max_result_bytes +16384)计算；首次原HPR准入前及后续绑定变更时核本声明足够，实际Host同配置及共享占用由部署独立核验，Host原背压保持。原配置不自动扩容/删除Journal。

### 发布和公开结果

原HPR返回后原after仍按原合同读一轮；空缓存保存empty且等待下次公开查询。保留客户端已持久交接终态且原HPR结论为preparation_unknown时，仍用同一下载请求及原回执，直接进入只读after；尚未交接完整终态的原请求继续查询原ID。排程间隔内/未决结果时，无档案返回Pending；已有值返回Partial，原preparation_request_id保留。跟踪次数/总期限/时钟/容量耗尽时停止后续来源调用，已有值继续Partial并说明预算原因，无可读值返回Backpressure。下载原Unknown继续Unknown，不能为表示预算而改写其终态；reason说明跟踪已耗尽。

后续实际读到非空行时复用原Importer/Helper/DSB/Reader逐字段验证和独占导入尝试，成功才注册原窗口的新根；旧空观测/原HPR/早期根与其文件不改写。空结果不造空DSB。发布后不再启动后续观测，重复只读原已发布根。新版本收据仅由显式follow_up配置创建，不读取旧005或218的私有工作根迁移配置。

### 验收

固定SDK015与metadata-only Appa18普通依赖安装，完整原App GET/lifespan→安装Host e→认证SHM→实际3.6.8完整内存正文SDK替身。download立即返回且after仍空，随后原owner定时回调才使缓存出现；同一公开GET先Pending/Partial，再取得新增分钟，标签及六字段与真实离线样本一致。原下载一次，有限只读次数、重复零源调用、原根SHA及所有资源关闭。

继而核原下载Unknown仍可只读发布、服务重启沿原排程/UUID、间隔与次数/总截止耗尽不延长、不换ID派发、未决只读恢复、已冻结非空结果本地发布恢复、旧默认及日线兼容；真实QMT下载效果与生产激活仍由根独立验收。


## RS15 来源支持范围与补齐配置

状态：accepted / in-progress。依据用户2026-10-29关于全市场按需补齐及清理自行添加限制的要求。正式source-preparing配置省略preparation.symbols；沿原请求exchange/code校验后，沪深证券直接进入原读取、缺数补齐和发布流程，证券真实性与实际缓存情况由来源表达。旧配置含symbols时保留原范围和收据恢复语义，旧实例不热改。

来源Host/Agent沿[HPR2](qmt-history-preparation.md#hpr2-固定输入与预算)的limits.v2，保留原profile.v6、policy、请求与结果格式、任务去重、队列和时间资源管理。新profile和完整QMT正文由原产品配对生成，既有策略名称/回调与内存SHM运输保持，终端内不新增文件/网络访问。

验收先覆盖旧测试清单外ETF及沪深股票请求进入认证SHM/原策略线程下载与历史回读，再覆盖独立安装来源服务→SDK→原Helper/Reader的缺档补齐、重复读取零新增下载及重连。真实QMT新正文安装和真实下载结果分别记录；替身验证保留其实际范围。
