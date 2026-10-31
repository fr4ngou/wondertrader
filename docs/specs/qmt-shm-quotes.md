# WT侧共享内存当前报价

类型：功能规格。状态：accepted。适用范围：WT管理的共享内存当前报价与原历史组合。

规格前缀 SQQ；显式模式提供当前报价并组合既有历史服务。retained 路径的补充合同见 SQR。

## SQQ1 入口与所有者

新增显式 `source-shm-quotes` 后端；使用既有 SourceMarketProcess/SourceMarketService 和 `guanheng.market.v1` 的 `quotes.query`、MarketClient。WT 拥有服务的创建、ready、停止和关闭；观衡、初始库存等客户端只消费。WT框架、原交易插件、initial_inventory、页面均无改动。

该模式组合 `quotes` 和 `history` 两个显式配置。quotes 为固定 SHA 的 GuanhengShmQuotes.dll 与独立本地 Host 连接；history 为原 source-store/source-stores/source-catalog/source-collected。旧模式继续原路径；全部历史动作和原元数据委托原后端。

## SQQ2 来源与值

新 C ABI 复用现有 Common QmtHostReadClient(FullTickV6)，复用原 QmtTickMapping。原 Host v6 标准读取、原 bound 绑定/请求/结果、FullTick 能力及原单位校验保持。累计成交量、金额和时间只由原映射转换一次；来源时间保持 SDK 时间，生成时刻不替代来源时刻。

一次调用沿原 quotes.query 最多 64 个合法且唯一的证券。证券集合来自请求；验收的八个 ETF 是合成样本。价格/昨收/OHLC/累计量额、源身份和 profile 元数据保持原接口。NativeVerified 仅表示本适配经过隔离 Native/SDK 验证；真实 QMT 可用性及价格时效分别验收。

## SQQ3 截止与未知

一个调用总截止覆盖准备、提交/原ID恢复、值投影。SDK timeout 沿原 Common 在业务总截止内收敛，重试查询原ID不会修改旧请求正文/SDK截止。未确认 receipt 由创建线程的同一 Native owner 在内存保留；同证券集合按规范排序后只 GET 原ID，换集合返回 Pending。确认终态后释放该内存核查责任，原 Host 记录仍保留；已确认坏行情返回错误，下一次观察可正常提交。

新进程恢复内存未知读取、通用 v6 FullTick 的长期 consumed 回收不在本模块资格内。依赖既有 Host 容量时，原 Backpressure/失败按原状态返回，服务不扩大额度、不删除记录、不换ID绕过未知。正常多次当前报价及同进程未知恢复已验；无限持续报价容量需后继契约。

## SQQ4 生命周期与降级

原服务单线程拥有后端及 Native handle，ABI返回缓冲在下次调用/销毁前有效；Python原适配立即复制。构造失败和正常关闭按 quotes→history 反向释放，任一关闭失败继续尝试另一个资源并向原服务报告失败。capabilities 分别报告两类能力；当前报价缺源时保留原历史能力，历史响应继续原 source 元数据。

## SQQ5 验收

普通发行安装→原 WT CLI/服务 owner→实际新 C++ DLL→正式 Host→实际 CPython3.6.8正式策略正文/WinSHM→计数SDK full_tick→原行情HTTP/MarketClient，报价满足库存所需字段。历史经原 Import/Helper/Reader真实读取同时通过。验证坏值后下一观察、SDK已执行而HTTP回执丢失后的同ID恢复/无额外POST、默认模式、坏输入及关闭。固定输入前后/当前一致，内外Job exit0、树零、双EOF、join/资源全关闭。SDK替身无金融写/策略文件网络违规。真实QMT、闭市时效、整套B/SRI交易和生产分别保留未验范围。

# Native retained FullTickV6

规格前缀 SQR。Native 快照 owner 持有本次消费责任，外层 HTTP 调用者读取其结果。

## SQR1 显式准入

Native配置schema=guanheng.shm-quotes.retained.v1选择新路径；原guanheng.shm-quotes.v1继续原未retained FullTickV6。新路径核生产者完整原六字段v6/profile和read_retention，不删字段、不改生产者/额度或使用新Host绕过。票据沿RR使用当前Host epoch、原GetTickCount64、原内容UUIDv5与原八字段请求，原capability SHA/完整binding保持。

## SQR2 Native消费边界

原RR3通用磁盘slot职责保持。本适配采用与AAR2同类的Native瞬时快照进程内交付：原结果身份/结构/全部报价映射完成，并由Native快照owner持有有界原result、receipt和待返回快照后，才发送原consumed。确认表达Nativeowner已取得本次观察，不表达外层HTTP调用者已收到，也不授永久存储。

完整验证确定结果不适合报价时，Nativeowner持有完整原结果及明确失败分类后，可按原确定完成规则确认消费并报告该观察失败。未知错误/不完整绑定/无法确认受理的结果继续原ID核查；不得用确定失败分支释放未知责任。

consumed回执未知时保留原result/receipt及已验证值，下一同请求集合仅原ID核查或原消费身份重确认；原结果/来源时间不刷新，不发新市场POST。网络未知/原ID404或410不推未执行、不自动换ID。跨进程原请求恢复与持久交付不在本模块资格。

## SQR3 截止、容量与来源

每次市场调用继续一个总D，prepare/容量等待/提交/原ID查询/映射/确认共享剩余时间。ticket有效期在生产者最大值内覆盖本次原请求剩余D，不延长原请求SDK截止；生产者原max_records保持，容量等待只等待已消费票据结束。未知及未消费责任原样计入容量，不能删除或扩容。源仍由正式3.6.8策略原线程/单timer调用full_tick，QMT无新增文件网络或SDK线程。

## SQR4 保持与验收

报价原API/原值/源时间/单位、原历史Reader路由、WT受管服务生命周期保持；既有Python运行依赖和生产者合同保持。普通安装同批Native的实际Cpp→Host15/Agent11→3.6.8/WinSHM→HTTP/MarketClient取得8证券/56数值和原历史，实际读取跨8容量，记录源SDK、原请求、消费确认和回收/高水位。随后必要原ID未知、consumed回执丢失恢复、legacy默认和正常关闭；独立两轴审查。SDK不授真实QMT/时效/跨日/整包交易或生产。
