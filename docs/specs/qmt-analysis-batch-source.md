# 批量日线分析来源

类型：功能最终规格。状态：accepted / in-progress。前缀：QAB。

## QAB-R1 来源与权限

显式 `qmt.read-profile.v8` 在原 `market.market_data` 操作中选择 `qmt.daily-batch-read.v1` policy（版本 1.0）。原 v7 单证券、账户、交易和历史准备保持原合同。v8 使用 builtin-shm、原策略线程和唯一 100 毫秒 timer；读取现有缓存，fill_data=False、subscribe=False，不下载、不打开文件或网络、不新增 SDK 线程。

原 SDK get_market_data_ex 的 stock_code 参数接受证券列表，返回证券到 DataFrame 的映射；依据[官方内置行情说明](https://dict.thinktrader.net/innerApi/data_function.html)。原 get_divid_factors 仍是单证券接口。SH/SZ/BJ 六位代码属于批量请求格式域；BJ 的实际缓存、返回及更新能力分别以实际终端证据核实。

## QAB-R2 有界批次与原值

请求沿原八字段身份和 policy、deadline、结果封装；arguments 精确为 symbols、start_date、end_date、max_rows、adjustment。symbols 为非空、不重复列表；日期及 none/front_ratio 沿原日线定义。limits 使用 qmt.daily-batch.v1，包含 max_symbols、max_calendar_days、max_rows、max_data_bytes。资源分片由外部 provider 依据结果额度和显式行数决定，证券集合由消费方原股票池提供。

每个批次实际调用一次 get_market_data_ex，count=max_rows+1；各 frame 沿原日线解码规则验证。输出 qmt.daily-batch-result.v1 的 securities 映射；各项 status 为 observed、empty、missing、invalid 或 requires_partition，data 保持原日期与六个数值。未知额外证券、超时和完整结果超额沿原失败路径；局部 frame 无效保留固定错误码。原数量、价格单位、原值和日期不作补造；复权公式由原 QNA/消费方拥有。

## QAB-R3 消费与一致性

批量提供者复用原 BoundHistorySource transport 和 RetainedReadClient。一个原 slot 对应一个实际 SDK 批次；完整原请求、binding、原结果及收到时间先持久保存，再沿原 consumed 确认回收。未知请求继续原 ID，服务换代时保持原责任，整次 capture 的完整 binding 一致。提供者不创建新运输、线程或金融账本。

消费包 schema 为 guanheng.observation-qas-batch-capture.v1。batch 保存 slot 相对路径、SHA 和原 request_id、原请求/结果摘要及时间；每证券的 none/front_ratio 记录只引用 batch 和原结果中的证券路径。各证券共同引用同一批次的执行时点，不伪造单证券 SDK 身份。公开包排除凭据、配对正文和账户配置。

none/front 的可比较基础为两者日期交集，basis 为消费范围内最新共同源日期；至少 40 期与股票池总数分别登记。源日期、received_at、包生成时刻分别保存。读成功不授当日闭合、原生复权正确或首次可知时间资格；空、缺失、无效、短历史和旧尾部分列。完整股票池可保留各证券自己的 basis；同日市场统计由消费方按其唯一基准选择。

同一 binding 和共同日期保留运输/源日期关系；SDK 未提供的全缓存修订版、跨批次同瞬时快照和历史首次可见时点保持未知。各原结果摘要与收到时间共同记录实际观察版本。

## QAB-R4 验收

先完成固定普通安装 Host/Agent → 实际 CPython 3.6.8 单正文/WinSHM → 全股票池分片 SDK 替身 → 原身份结果/消费/回收 → 可由 C 读取的包 → 正常退出。核原容量、SDK 次数、证券映射、逐数值、同线程、无策略文件网络及金融调用。随后核旧 v7/default、局部缺失/无效、原 ID 续核和跨代一致性必要情形。真实 SH/SZ/BJ、数据尾部与闭合资格沿实际回包另验，小切片准备保持零业务进程、零请求。

## QAB-R5 日更批读的常驻归属

被独立日更使用的批读Host以原WT ServiceController常驻托管，仅配置analysis_batch_host/qmt_read，复用原配对、Journal、端口及来源操作身份。该实例没有execution、trade_host或账户发布组件；金融执行退出后，日更原请求仍可沿相同来源恢复。沿原启动/停止/状态入口管理，不由临时验证进程或观衡持有。

同一配对及端口保持一个活动Host。迁移前核旧Host实际退出及端口空闲；原金融配置、旧Journal和未知请求原件保持，后继交易部署引用独立日更来源，避免重复声明同端口Host。常驻入口登记先启动该依赖再启动日更，停止时逆序处理。进程ready、来源已认证、原批次恢复及正式数据发布分别验收；外部事实缺失继续显式记录。

缺口补齐后的同一请求回读沿用已有原批次分片。只有包含本轮补齐证券的批次创建新读取，其余批次从本地已核回包续用，仍保留原请求时间、来源和 UUID。恢复时已有回读槽保持原身份。同一日线 owner 的 HPR 并行使用已有 Host 客户端工作线程，QMT 终端执行及 WT 版本发布沿各自单一 owner。

## QAB-R6 显式来源单位证据

单位解释属于批读来源接入。WT原生历史文件保留输入数值与来源元数据，缺少供应商字段量纲证明时，接入层使用显式证据补充声明；无需改变原SDK、原生行情数值或撮合。默认 `capture_profile/capture_metadata` 调用保持既有字段、顺序及三个unknown单位。合成来源、不匹配业务来源、未列证券及缺少逐证券选择继续unknown。新证据只写入新版本元数据，历史原件、旧档案及原Journal保持原字节。

唯一纯解析入口为SDK `source_units.parse_unit_evidence(raw)` 和 `resolve_price_units(evidence,symbol)`。证据schema为 `qmt.source-unit-evidence.v1`，profile固定 `qmt-contextinfo-day-etf-index.v1`；字段包括真实来源业务身份SHA、已核参考capture SHA、ContextInfo API标识、本机包装函数文件路径/SHA、五份官方原始HTML/PDF的路径/URL/SHA。官方内容及包装函数须与该profile已审证据完全核同；证据文件自身另由配置path/SHA固定。其建立与采用由受控部署所有者授权，模块不通过source_kind字符串自动授资格。

明确消费者调用 `resolve_source_price_units(evidence,symbol,packet)`，packet为已验SDK日线data；它要求非空bars的全部连续provenance均精确绑定该证据dataset_version和公开单位三元组。单一原始metadata可作为完整一段；SourceSelection须提供完整原分段。缺段、旧unknown、不同证据或其它供应商返回unknown。证券本身的profile语义与当前包的来源资格分别核实，旧指数DAT/CSI段保留旧资格。

Data侧 `analysis_price_units.load_unit_evidence(descriptor,deadline,cancelled)` 核原件；`qualify_capture_units(capture_descriptor,evidence,deadline,cancelled)` 返回不可变 `CaptureUnitEvidence` 或None。它复用原 `read_capture/capture_source_binding/_hpr_business_identity` 核完整批次、已消费原结果及同业务来源；Host和运输代允许沿原SDK规则变化。原请求须保持日线批读policy、证券/日期/复权范围及原slot身份。新的日常capture可沿同一业务来源复用该证据，capture内容SHA继续逐份绑定。格式、摘要、原结果损坏明确失败；合法的非适用来源返回None，保持unknown。检查沿调用方总截止和取消，不发来源请求。

`capture_profile/capture_metadata` 新增可选keyword-only `symbol`、`unit_evidence`，后者必须为与当前capture SHA绑定的资格结果。默认及无symbol的混合证券profile保持原输出。适用新元数据的dataset_version携profile和证据SHA，其他来源、复权参考、授权及日期语义保持原合同。

固定证券域为人民币ETF 510050.SH、510300.SH、510310.SH、510330.SH、510500.SH、512100.SH、512890.SH、515080.SH、588000.SH、589680.SH、159352.SZ、159780.SZ、159781.SZ、159919.SZ、159949.SZ，以及指数000300.SH。ETF公开price_unit=CNY、volume_unit=lot。指数公开price_unit=unknown、volume_unit=lot，纯解析结果的semantic_price_unit=index-point供明确的指数消费者采用。amount_unit继续unknown。SDK20原价格单位枚举保持兼容。ETF每手100份。新增证券仅在原QMT采集已核业务绑定下取得单位，后续归档可通过同值单位升级保留价格原值。复权价格单位的资格限于分析价格。

官方依据：[迅投K线字段](https://knowledge.thinktrader.net/docs/cloud/data_structure.html)、[ContextInfo接口](https://knowledge.thinktrader.net/docs/python/data_function.html)、[上交所ETF单位](https://www.sse.com.cn/assortment/fund/etf/question/c/c_20240118_5734754.shtml)、[深交所2026规则3.3.10—11](https://docs.static.szse.cn/www/lawrules/rule/trade/W020260424690713155663.pdf)、[中证沪深300编制方案第4/12.1节](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000300_Index_Methodology_cn.pdf)。profile固定这些官方原件及已核安装包装函数的内容摘要；可变网页后继版本经重新审查形成新profile。

必要验收包括默认原字节同一、ETF/指数分别解释、官方原件及wrapper篡改拒绝、合成/foreign来源保持unknown、同业务运输换代复用、取消和截止、原slot/参数变化、混合无symbol保持unknown。新完整原价版本采用前逐消费日核旧raw与完整当前QAB的OHLC/volume/amount差异，显式登记选择；原价旧unknown段及新known段混合仍按现有选择合同降unknown。新完整前复权版本继续同一参考整证券覆盖。候选模块完成、归档接线、实际发布分别验收。
