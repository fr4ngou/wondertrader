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
