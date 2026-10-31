# 国信 QMT 内置 Python 开发与性能手册

类型：长期运行手册。适用范围：国信终端内置策略及终端外行情/交易接入。版本事实保存在独立安装和官方资料记录；本手册维护核对方法与稳定使用边界。

## 环境与可选版本

| 环境 | 版本依据 | 使用方式 |
| --- | --- | --- |
| QMT内置策略 | 国信发行包、实际加载DLL及内置回调sys.version | 按该解释器语法/位数和受限运行规则开发 |
| 安装内配套pythonw | 该独立进程的sys.version | 可做离线兼容检查，结果与内置回调实测分别记录 |
| 外部XtQuant | 具体SDK发行记录和对应wheel/pyd | 属于终端外接口，不作为内置解释器选择清单 |
| 系统外部Host/工具 | 本仓制品声明和受管解释器 | 独立管理依赖，可承担并行纯数据工作 |

当前已核实安装见[本机证据](../evidence/2026-10-28-qmt-installed-runtime.md)：随安装手册和配套解释器为CPython3.6.8/64位。本次没有取得国信内置解释器多版本选择的官方清单。官方外部XtQuant已有3.12/3.13发行说明，不能据此切换内置解释器；新版本选择先补国信对应发行证据和兼容验证。

客户端产品版本、PE文件版本、pythonw启动器PE版本和运行时sys.version分别留档。Python库路径/库下载配置第三方库位置，不能据此认定可更换解释器。库文件存在也不能证明受限策略可以通过普通文件import加载它。升级前后在同一已授权只读入口的init里输出sys.version/sys.version_info及位数证据即可，不必为每次核对新建业务策略；不输出账户或私有配对正文。

## 函数与状态

[API查阅索引](../modules/qmt-native-api-index.md)保存本机手册函数/属性及页码，[官方资料记录](../evidence/2026-10-28-guosen-qmt-official-runtime.md)链接新版系统、行情、交易及回报目录。区分ContextInfo方法、策略全局函数和外部xtquant函数；使用对应版本的拼写、参数及返回字段。

init负责一次初始化，after_init在初始化完成后调用，handlebar由主图历史/实时数据驱动，stop负责请求本策略清理。部分函数不支持在init读取在线数据，按官方具体说明选择阶段。持续队列、连接和计数放自建全局对象；ContextInfo自定义状态有随bar回滚的语义，不能承担持久队列所有权。

快照get_full_tick、全推subscribe_whole_quote、周期历史get_market_data_ex职责不同。全推订阅号由原入口保存并用于unsubscribe_quote；单次快照成功不代表完整分钟。历史显式选择周期、日期、复权、fill_data、subscribe；读取已下载缓存不等于已触发补充下载。

策略分析窗口的日线使用get_market_data_ex的time/OHLC/volume/amount原字段，period=1d；显式none和front_ratio分别保留原始及前复权参考，fill_data=False、subscribe=False。get_divid_factors返回按时间戳索引的七列原事件，空映射保持原值。当前接入合同及主线程/内存入口见[QAS](../specs/qmt-analysis-source.md)，累计因子及价格计算继续归[原生复权模块](../modules/qmt-native-adjustment.md)。

历史缺口使用对应安装版本支持的内置全局download_history_data，参数为单证券、基础周期及显式起止时间，按系统任务额度串行交给原策略线程。它与终端外xtquant.xtdata.download_history_data属于不同调用入口；某一路返回正常，不能替另一条路径授资格。官方[内置行情函数](https://dict.thinktrader.net/innerApi/data_function.html)注明返回None，因此以随后get_market_data_ex(subscribe=False, fill_data=False)的实际日期/条数及来源数据核对完成。原生调用可能超过Python预算，调用结果未知时先回读核查；保持原历史根，新的导入/修订写入新根后再切换配置。安装验证见[单位与补齐证据](../evidence/2026-10-28-qmt-daily-units-backfill.md)。

## 文件、网络及准备阶段

受限内置策略运行时保持当前无外部文件/网络访问的约束。源码依赖和配对参数在终端外准备，沿已验证的内存正文加载；Windows命名共享内存由系统内存支撑。平台自身加载策略/SDK缓存与策略主动读取普通文件分别说明。旧官方示例中的to_csv或磁盘导入不能作为当前权限依据。

外部Host及DataKit由系统管理，分别拥有外部文件/网络/原生文件职责。原来HTTP验证入口的存在不表示QMT内部可建网络；真实用法按当前共享内存入口和来源profile核对。

## 多线程与多进程

迅投[内置Python使用须知](https://dict.thinktrader.net/innerApi/user_attention.html#关于线程和进程)明确给出内置策略的线程/进程限制，并说明策略回调共用执行线程。面向该模式的源端设计应把等待、并行和较重工作放到终端外，原策略回调每次只推进有限的现成工作。

[stop说明](https://dict.thinktrader.net/innerApi/system_function.html)中的线程清理要求用于资源收回，不能作为后台Python线程持续获得调度的支持承诺。配套pythonw里的独立进程测试、线程能创建和一次连接成功，各自保留实际证明范围；内置回调环境的持续推进和停止需要在QMT进程内验证。

| 工作 | 执行位置 | 调度边界 |
| --- | --- | --- |
| 查询、订阅/退订、账户、下单/撤单SDK | 已验证的原策略回调线程及对应ContextInfo | SDK在原回调调用，工作量有界；原生调用及结果未知沿各业务契约处理 |
| 原SDK行情回调 | SDK实际回调线程 | 只复制必要纯值并更新有界内存，及时返回 |
| 受限内置模式的SHM运输 | 原策略timer/回调驱动的非阻塞推进 | 每次只读写已就绪的有限帧和字节，跨回调保存状态；业务截止、MAC、序列和ACK沿原协议；具体实现/安装/真实资格由来源模块登记 |
| 线程式源运输兼容模式 | 原显式运行配置及唯一I/O owner | 保留旧配置语义和已验证范围，持续调度的资格按平台及实际环境单列 |
| 外部Host、历史转换和较重计算 | 终端外受管进程 | 可按纯值输入并行；统一预算、汇合、背压和正常关闭 |
| 分钟聚合和原生存储 | 终端外DataKit原生组件 | 沿原Writer/session并发模型，保持同一数据根唯一写者 |

新的源运行模式应在配对版本及摘要中显式绑定；旧版本继续原语义，较新的实现通过配置选择。回调驱动的设计保持原timer，按消息状态继续原操作；通信断开或结果未知时保留原请求身份。

官方[run_time说明](https://dict.thinktrader.net/innerApi/system_function.html#contextinfo-run-time-设置定时器)支持 `nMilliSecond`、`nSecond` 和 `Day` 周期，并注明回测无效、定时器随策略停止；部分周期在首次执行前先等待一个周期。运输推进频率属于来源运行模式及配对身份，使用已有同一个timer。缩短运输推进间隔时，继续保持业务、连接及单次IO的原绝对截止。官方支持的周期单位与本机发行版本的实际回调节拍分别核验；主图K线周期也不代表通信timer的执行频率。

标准CPython的GIL和Windows进程spawn是语言层事实；QMT内置解释器的具体调度机制需要对应现场证据。一次收包超时不足以判断其GIL或锁竞争原因。相关语言参考见[Python3.6 threading](https://docs.python.org/3.6/library/threading.html)、[multiprocessing](https://docs.python.org/3.6/library/multiprocessing.html)。终端外进程池只处理纯值，不共享或重新构造内置ContextInfo来调用券商API。

## 性能优化顺序

先完成正常全市场链，再围绕实际慢段优化。记录同一输入的证券/回调/批次数量、时间范围、CPU/RSS和队列变化，并拆分以下阶段：

| 阶段 | 需测内容 | 根据测量选择的优化 |
| --- | --- | --- |
| SDK及回调 | 订阅返回、首回调延迟、接收行数、筛选/复制耗时和锁占用 | 全推代替重复全市场快照轮询，先筛证券后提字段，缩短回调工作 |
| 源端运输 | 排队时长、批次序列化/HMAC耗时、帧字节、发送/等待耗时 | 合理批次，减少重复全表编码；保持身份校验及顺序 |
| Host消费 | 接收/校验/映射耗时、背压及原生调用耗时 | 缓存已固定清单的派生数据，避免反复排序/摘要；变化需同契约回归 |
| Writer | 原生接受、文件创建、分钟实际生成和归档耗时 | 原生配置和时段核对，按原组件接缝调整容量，单根写者保持 |
| 关闭 | 源端退订/IO退出、接收线程join、原生release各阶段 | 原生产者先停止，再释放依赖；未知关闭保留证据 |

这是后续测量与优化方法，不表示上述慢段已被证实或修改。已有线程式报价流的成功证据保留其当时版本、输入和时段范围。源端运行方式按内置环境约束选择，较重工作放到外部受管worker。观察总耗时包含启动、等待和停止，不能用收到行数除以总观察秒数作为稳定吞吐；“仅收到3000条”也不能单独认定QMT Python CPU慢。不得通过跳过认证、放大原截止或丢报价把失败改成成功。

## 更新公告与升级复核

官方入口为[国信下载页](https://weixin.guosen.com.cn/gs/software/detail.html?id=43)和[迅投内置文档](https://dict.thinktrader.net/innerApi/start_now.html)。每次记录页面版本、发布日期、检索日期、适用产品和直接来源；动态页正文不足时核其公开数据接口，原件摘要留在对应证据。产品版本与本机PE无映射时保持待核，不能自行判定已升级或落后。

先核已用API的函数名、参数、返回结构、调用阶段、线程、权限及停止行为，再决定适配范围。新函数存在不要求立即替换已验证接口；公告只写规则/缺陷改进时，不推断Python或权限变化。终端更新按[维护升级回滚](guosen-qmt-maintenance.md)，运行步骤按[日常操作](guosen-qmt-operations.md)。
