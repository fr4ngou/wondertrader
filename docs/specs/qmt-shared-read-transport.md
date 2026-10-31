# QMT共用只读HTTP传输

类型：最终规格。状态：accepted。前缀QRT。授权依据：用户确认QMT HTTP优先、数据与交易来源抽象、复用原生接口并继续完整适配。范围为自有HTTP传输与原消费者兼容，WT vendor保持原件；实际账户与生产资格分别验收。

## 目标与位置

现有GuanhengData/QmtHttpClient已拥有签名、WinHTTP、总截止、health/capability、一次POST及原ID认领和回调排空，但只允许market操作且返回仅data。账户接线复用该实现，收敛到GuanhengCommon的只读传输；原QmtHttpClient保留行情调用面。金融字段/完整性验证和原TraderAdapter投影继续分别由领域边界及WT承担，不新增账户库、对账器、网络栈或写操作。

完整调用链：Market包装器或Account限定域→同一传输owner→签名HTTP→原QMT Queue/Journal→完整envelope→对应领域验证。Account契约为qmt.account-query.v1，源端唯一规格位于QMT仓库docs/specs/qmt-account-query-context.md；本规格只使用其版本/范围，不重复实现源端逻辑。

## QRT-R1 公共接缝与兼容

新增自有GuanhengCommon/QmtReadTransport.h/.cpp，QmtReadDomain固定Market/Account，构造显式选择域，不开放自定义operation注册。公共方法保留prepare/session/capability/last_source_time/read_operation/drain_callbacks，线程与截止契约沿原实现。QmtHttpConfig移至共用声明，旧Data头包含它，命名和既有成员默认值保持。

原JsonResult的首两个成员status/data_json及聚合初始化兼容；附加envelope_json、request_id、operation_id、http_status（unsigned，未取得响应为0）、terminal（bool）、remote_ok（bool），均有确定缺省值。envelope_json保留受容量约束的原响应文本，不以重新编码的data或追加字段冒充原摘要输入。原market成功data与错误状态保持；新增完整结果供账户消费者使用。

原QmtHttpClient成为Market薄包装器，签名、网络、结果关联、截止和回调排空只保留一个实现。共用模块不链接行情Store/Reader、交易执行器或WT core，领域调用者不复制传输。固定原生接口与旧实验制品目录均保持。

## QRT-R2 闭合准入和来源准备

Market仅允许原market.full_tick及market.market_data_ex，原精确参数、无下载/订阅、预算保持。Account仅允许account.trade_detail，参数精确account_type="stock"、datatype为position/order/deal/account之一、scope="account"；不接受账户ID、strategy_name、其他键或写操作。

Account准备须看到implemented=true、mutating=false以及query_contract：schema_version="qmt.account-query.v1"，scopes包含account，default_scope为strategy，account_types包含stock，datatypes包含四查询。来源缺版本或范围明确Unavailable，不回退旧策略筛选。remote capability只能缩小本地集合。Market兼容忽略其他域的契约扩展，保持原重复ID/非法文档拒绝边界。

前后health和原SourceSession继续筛选源会话漂移；它们不替代账户observation，不授金融资格。last_tick_at继续只表示Host回调存活，不能变成市场时钟或交易日。

## QRT-R3 完整响应、错误和原ID认领

在一次总steady_clock截止内，沿原一次POST及GET原request_id处理202/未知交付，不重投POST或生成猜测性新ID。请求生成后，不论成功、远端失败、HTTP拒绝或超时，返回保留原request_id/operation_id；提交前参数/准备失败可无ID。

取得响应时在原容量保护内保留HTTP状态与原body。200成功继续严格核request/type、ok、completed_at、data、末次health及截止后才交成功data。远端ok=false保留原envelope，status仍失败；202保留进度，未完成不授成功；非200/202的结构化拒绝正文也作为诊断保留，禁止误变成成功。未知/格式错误/关联错配保持原失败语义。terminal仅在有正确请求/类型关联且合法终态（200及bool ok、合法completed_at）时为true；remote_ok仅表示已核合法终态的原ok，不表示当前来源/金融就绪。错误响应或未完成body不填成功data。

原error_code/message、result_sha256及存在的计时/observation通过原body保留，不创建另一套错误或结果持久存储。结果SHA只是原证据，未按源端稳定投影验证前不能宣称核验完成；整个最终响应与原Journal摘要投影不等同。诊断不自动写日志或暴露凭证/账户明细。

## QRT-R4 所有权、回调与停止

创建线程独占prepare/read/session/capability/drain。原WinHttpSessionDrain及最多64个待排空session约束继续；请求结束不等于回调结束。显式drain预算耗尽保留事件/依赖，调用者继续持有client和DLL；析构等待为最后资源保护，不能冒称有界stop成功。

两个域共用同一排空实现。移动代码时，专用GH_QMT_HTTP_DRAIN_TESTING门控仍只编入专用fixture DLL，生产没有该导出/门控。旧Parser/Reader关闭与响应初始化异常回归继续有效；不改原Reader/Parser/WT线程机制。账户worker未来须独占客户端并在释放前实际drain/join，本切片不以只读请求成功授原生插件关闭资格。

## QRT-R5 构建、测试与资格

从已有固定Git历史profile复用原工具链、唯一NRC及构建侧Windows兼容，不引入冻结未批core。新增共用源纳入正式CMake、独立历史profile及专用HTTP/drain fixture实际编译清单；原冻结NHA build/suite/review目录保持，不重标成新制品。记录实际源、依赖、DLL/exe、测试与输入摘要。

必要验证：旧market/协议/总截止/关闭实际WinHTTP组；Account准备的正确/旧/缺失/错契约；两个域互相拒绝与写/下载/订阅0调用；四查询精确请求；原envelope/错误保留；202及丢失POST响应只GET原ID；超时保留ID、HTTP拒绝、关联/重复键/容量/非法JSON、会话变化；显式drain、owner错误、晚回调与生产无测试导出。隔离loopback可使用原QMT源端模块作为服务，保持零真实QMT/账户/数据库/部署操作。

源端契约、领域映射、NQB四查询实际HTTP、持续回报交接/恢复、HTTP跨进程ticket、真实账户及生产分别验收。成功测试按实际输入复用，首个公共契约/并发重构采用独立full审查。回退恢复旧market包装器及原单实现，停用Account域，保留原请求结果和已有数据。
