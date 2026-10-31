# QMT HTTP 行情接入与独立业务边界

类型：功能最终规格。状态：accepted。依据：2026-10-21 用户确认优先实现 HTTP 连接 QMT；共享内存绑定和通达信交易暂缓；QMT 主历史来源、TDX 可选辅助；观衡服务独立受管发布。上位规格为[原生接入](guanheng-native-adapters.md)，本规格对其当前实施范围作明确细化。

2026-10-22最新时序按[DEC-001](../migration/decisions.md)：本文HTTP-R1/R2/R3中的QMT终端HTTP通道仅用于今晚前跑通流程，后续停止优化及新部署；共享内存须等另一对话开发完成且今晚实测通过确认后才开始接入。HTTP-R4的观衡到自有原生行情服务接口属于独立业务边界，继续开发和验收；QMT终端HTTP退役不要求移除观衡内部HTTP。历史源证据保留原身份，不能直接授予新传输的真实来源资格。

## HTTP-R1 连接与权限

原生 Windows HTTP 客户端复用现有 QMT Gateway 线上 JSON/HMAC 契约，不复制 Gateway 的策略线程队列、账户事实或执行 Journal。仅开放 health、capabilities 和两类只读操作 market.full_tick、market.market_data_ex。历史参数固定 1m、none、fill_data=false、subscribe=false、normal 标准读取策略；其他操作拒绝。同步 POST 最多一次，202 只按原 request_id 有界查询结果。拒绝响应身份不符、坏 JSON、超大体、重定向及过期会话。完整调用使用同一截止预算，失败原因脱敏。

HTTP 明文仅允许显式本机回环地址；远端需要正常验证的 HTTPS。关闭自动代理和重定向，凭证由运行环境传入，缺少凭证明确 unavailable。原生 handle 限创建线程；客户端为同步有界调用，不授予可抢占任意 SDK 的能力。

HTTP请求截止与异步回调清理分别建模。每个WinHTTP session在注册回调前配置系统UNLOAD_NOTIFY_EVENT；客户端以固定64项容量保存待清理session的事件，只有最后回调完成的系统通知到达后才关闭事件并回收。容量满时拒绝创建新session。新增owner线程 `drain_callbacks(timeout_ms)` 使用总截止，0表示立即检查；未排空保留状态，调用者继续保持客户端与DLL有效。该方法仅等待已有回调，不改变后续读取准入。

客户端析构作为最后保护必须等待已有回调排空，不能提前丢弃系统仍持有的事件；存量void销毁接口因此不提供有界关闭确认。需要有界停止的宿主使用独立worker和显式drain，在截止到达时保留依赖，后续继续确认。[QNP](qmt-native-parser.md)的stop成功包含这项证明。独立MarketBridge及Reader的关闭确认按各自模块补齐，不从请求deadline推导析构deadline。

## HTTP-R2 来源与解析

prepare 明确取得 Gateway health 与 capability 并固定 agent_id/qmt_session_id/generation，不从连接成功推断可交易。读取前后核对身份；会话改变丢弃结果并要求重新准备。行情适配端点实现已有 IMarketEndpoint/IHistoryEndpoint，策略和 WT 接口沿用既有类型。

单位、源时间编码、分钟左右边界、累计快照语义和数据许可由显式版本化 profile 提供；缺少 profile 保持不可用。历史只接受带明确 time 的记录，禁止按返回顺序猜时间。源端若仅序列化 DataFrame records 丢失索引，则如实报告缺少时间；后续由源端契约所有者补齐。未结束分钟禁止发布为闭合历史。闭合依据同一会话下该证券 market.full_tick.time 的已验证源时间；health.last_tick_at 是 Host 回调存活时间，不能授予闭合资格。没有源时间证据不声明当前分钟已结束。源结果完整性和交易分钟覆盖分别返回，预期网格及版本缺失仍为 unknown。

`epoch_ms` 的 tick 与历史 time 使用相同数值准入：接受 JSON 整数及整值浮点数（包括 DataFrame records 的 `.0` 表达），要求已解析数值有限、非负、为整毫秒且转换无损，并满足既有 2004–2099 日期范围。拒绝字符串、布尔、分数、非有限数值及越界值；历史继续验证整分钟格点、profile 左右边界、顺序、请求范围和源时间闭合依据。源单位及分钟边界由 profile 决定，JSON 数值存储类型不改变这些语义。

## HTTP-R3 原生存储与补数

复用 NativeHistoryStore、HistoryPreparationQueue、MarketParser 和 WT 分钟实现，不新增行情数据库或持仓账本。查询读取 DSB；缺口准备进入有界队列，由显式 worker 推进 HTTP 获取、解析、合并发布及回读。源完整性无法证明时保留 pending/unavailable，不把有限 count 截断的页判定完成。单次证券、请求体、返回条数、字节和执行时间均有上限。

HTTP 补数单次范围最多 72 小时，以自然分钟上界约束 QMT count 尾部截断；源 count 上限 5000。超过范围明确 Backpressure 并由受管作业分窗。全库单证券存储预算一百万条，单次外部查询最多一万条。该限制约束单次请求，不缩短源数据的历史保存期。

## HTTP-R4 观衡独立接口

新增版本化外部行情接口 guanheng.market.v1。WT 发行包提供原生 JSON C ABI 和独立运行的薄 HTTP 服务；观衡只依赖该版本化 HTTP，不引用 WT 发布目录、C++ 类布局或私有 QMT 源码。服务可独立重启，观衡独立部署、升级及回滚。此服务仅承载行情，不提供交易、账户、任意 Gateway 透传或自动源切换。独立服务的真实业务逐项适配另见业务适配地图。

原生 ABI：gh_market_create(config_json) -> handle；gh_market_call(handle,request_json) -> UTF-8 JSON（有效至该 handle 下一次调用/销毁）；gh_market_destroy(handle)。创建失败返回空，异常不跨 ABI。全部调用在创建线程，销毁前停止 HTTP 服务，调用者复制结果。配置由受管环境组装，不接受远端更改凭证、文件根或 profile。

请求顶层固定 api_version 和 action，可用动作 capabilities、history.query、history.prepare、history.work、quotes.query。响应固定 api_version、status {code,reason}、data；来源统一 {provider,instance_id,session_id,generation}。资格、单位、闭合边界、覆盖及缺口原样保留。历史 request 字段 exchange、code、from、to、expected_minutes（可空）、calendar_version。证券查询使用 symbols 数组。history.prepare 返回 task_id/state；history.work 显式推进一项。查询无自动网络副作用，策略按查询→准备→查询使用。

后续兼容增量为[策略统一访问](strategy-market-access.md)定义的 `history.read`，POST `/api/market/v1/history/read`：沿原历史响应、服务内私有有界准备、完整缓存离线返回。旧query及任务行为保持，策略可通过新统一SDK隐藏准备流程。

quotes.query 成功包含 snapshots 和批级 metadata。metadata 固定 qualification、profile_version、source_license、timezone=Asia/Shanghai、price_unit=CNY、volume_unit=share、amount_unit=CNY，以及源换算依据 volume_to_shares/amount_to_yuan；返回数值已经归一化，调用者不再次乘系数。全部请求证券各返回一项、无重复且处于同一源会话；空/缺项成功响应拒绝，避免静默授予完整快照。

HTTP 路径 /api/market/v1/{capabilities,history/query,history/prepare,history/work,quotes/query}，GET 仅 capabilities，其余 POST，Bearer 必填且限定本机回环绑定。无凭证/错误版本/超大输入/原生失败清楚返回受限错误，不回显配置。Python 客户端只依赖标准库及此公开契约，无 wtpy 和原 QMT 包依赖。

## HTTP-R5 Tushare 与辅助来源

QMT 为主、TDX 为显式可选辅助，数据集保持各自来源与语义，不静默混源。Tushare 作为独立可选能力研究和权限探测；基础 token 不推定分钟、ETF 或实时权限。凭证不进入版本库、包、日志及文档。仅在已验证 TLS 端点探测真实凭证，不自动降级明文。官方事实与实际 token 授权分别记录。

## HTTP-R6 暂缓项与执行边界

本轮不开发共享内存客户端绑定与通达信交易，也不执行真实下单/撤单、账户操作或生产发布。既有受管交易前端保持关闭；HTTP 查询连通不能补出原子快照已吸收游标和恢复连续性证明。HTTP 实盘交易接线需要该契约后续专门补齐。

## HTTP-R7 验收与分工

通过真实本机 HTTP 服务验证 HMAC 原字节、202 结果领取、截止预算、恶意/坏响应、身份更换、只读参数；原生端点→DSB 查询/准备→独立 HTTP 服务→标准库客户端链路使用隔离数据实际运行。保留已有原生/业务测试和可搬迁包校验。若实际 QMT listener 不存在，记录实际连接失败与原因，隔离通过不提升实机资格。接口/认证/恢复影响触发 full 独立审查。

所有权：执行 Agent 负责 QmtHttpClient 与 HTTP 协议探针；行情 Agent 负责 QmtHttpEndpoint 与解析测试；业务 Agent 负责独立 HTTP 服务/客户端与其测试、适配地图；主 Agent 负责本规格、原生 JSON ABI、CMake/打包、跨模块运行、审查与证据。公共头变更先通知消费者；只有主 Agent 执行构建。
