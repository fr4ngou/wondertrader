# 国信 QMT 运行环境、接口与更新资料核查

类型：外部资料核查证据。适用范围：国信 iQuant／QMT 内置策略的开发、运维及后续运行环境升级。

状态：2026-10-28 官方网页检索完成；客户端升级、解释器切换和新版兼容性尚未实施。本记录只采用国信证券和迅投发布的直接资料。官方知识库属于通用产品说明，国信发行包及账户实际开放能力须另行核实。

## 结论与适用边界

- 国信官方软件下载元数据目前列出 **iQuant V3.13，2026-09-16 更新**，更新内容为沪深北业务规则适配和已知问题修复。该公告没有列出 Python 解释器升级、行情 API 替换或文件／网络权限变化，现有使用方法尚无据此强制重写的依据。[国信下载页](https://weixin.guosen.com.cn/gs/software/detail.html?id=43)、[同页官方数据接口](https://weixin.guosen.com.cn/xcgswz-web/software/list/1.0?id=43)
- 迅投内置 Python 快速开始仍标为 **3.6**。本次未找到国信官方公开材料，证明国信内置环境已经提供 3.6／3.12 选择或公布对应切换流程。外部 XtQuant 的 Python 支持范围应单独登记。[内置快速开始](https://dict.thinktrader.net/innerApi/start_now.html)、[外部 XtQuant 快速开始](https://dict.thinktrader.net/nativeApi/start_now.html)
- 官方线程说明存在口径差异。使用须知限制内置多线程／多进程；系统函数的 `stop` 说明又涉及策略自建线程收尾。当前不能把后台线程可创建，等同于券商 API 可跨线程安全调用。详细边界见下文。[使用须知](https://dict.thinktrader.net/innerApi/user_attention.html)、[系统函数](https://dict.thinktrader.net/innerApi/system_function.html)

## 官方来源与日期登记

所有来源检索日期均为 **2026-10-28**。未展示发布日期的页面，以下明确登记为“未展示”，不使用搜索引擎抓取时间代替发布日期。

| 编号 | 直接来源 | 页面日期／版本 | 可支持的事实 |
| --- | --- | --- | --- |
| G1 | [国信 iQuant 下载详情](https://weixin.guosen.com.cn/gs/software/detail.html?id=43) | V3.13；更新日期 2026-09-16 | 国信发行版版本与更新摘要 |
| G2 | [G1 页面使用的官方数据接口](https://weixin.guosen.com.cn/xcgswz-web/software/list/1.0?id=43) | `softUpdateDate=2026-09-16 17:28:40` | G1 动态正文的直接复核 |
| G3 | [国信 iQuant Python API 使用手册 PDF](https://www3.guosen.com.cn/guosen/newxwfiles/20190902/1567416998056.pdf) | V1.0；完成日期 2019-08-07 | 国信历史环境与 API 依据，不能代表当前发行版 |
| X1 | [迅投内置 Python 快速开始](https://dict.thinktrader.net/innerApi/start_now.html) | 发布日期／客户端版本未展示 | 内置 3.6、逐 K 线／订阅／定时运行三种机制 |
| X2 | [使用须知](https://dict.thinktrader.net/innerApi/user_attention.html) | 发布日期／客户端版本未展示 | ContextInfo 状态回滚、线程进程与阻塞限制 |
| X3 | [系统函数](https://dict.thinktrader.net/innerApi/system_function.html) | 发布日期／客户端版本未展示 | 生命周期、定时器、停止回调 |
| X4 | [行情函数](https://dict.thinktrader.net/innerApi/data_function.html) | 发布日期／客户端版本未展示 | 内置行情 API、订阅、历史与元数据 |
| X5 | [交易函数](https://dict.thinktrader.net/innerApi/trading_function.html) | 发布日期／客户端版本未展示 | 委托、撤单、资金／订单／成交／持仓查询 |
| X6 | [成交回报实时主推函数](https://dict.thinktrader.net/innerApi/callback_function.html) | 发布日期／客户端版本未展示 | 账户、订单、成交、持仓等回调 |
| X7 | [外部 XtQuant 快速开始](https://dict.thinktrader.net/nativeApi/start_now.html) | 发布日期未展示；概述列 64 位 3.6—3.12 | 外部 Python 依赖环境与 MiniQMT 关系 |
| X8 | [XtQuant 版本下载与变更记录](https://dict.thinktrader.net/nativeApi/download_xtquant.html) | 2024-06-17／2025-05-16／2025-12-19 等独立条目 | 外部 SDK 的 3.12、3.13 支持和版本范围 |

G1 为动态网页，普通正文读取可能只返回“基本介绍／更新”标题。本次沿页面公开脚本 `gs/software/js/detail.js` 找到 G2，并实际读取 HTTP 200 JSON；G2 的 `data[0].newFeature`、`swIPhoneInfo` 和 `softUpdateDate` 相互一致。未下载该接口列出的安装包。

## 国信最近一次可核实的更新

G2 实际返回产品名“国信 iQuant 策略交易平台”、产品版本 V3.13、软件大小 422M、更新日期 2026-09-16，以及 MD5 `6B70F42D195A154F6FB80D4341770A44`。公告范围为沪深北业务规则适配与问题修复。该结果表示这次公开检索找到的版本，不能证明不存在其他定向或客户端内更新。[国信官方元数据](https://weixin.guosen.com.cn/xcgswz-web/software/list/1.0?id=43)

本机运行版本应同时记录客户端显示版本、主程序 PE 版本和实际已加载解释器。本次网页调查未取得“产品 V3.13”与某个 `XtItClient.exe` PE 构建号的官方对应表，因此应由本机证据完成版本映射。

本次未找到国信直接公告，说明在某一具体日期统一禁止策略读本地文件、建立网络连接，或说明这些权限与 Python 3.12 的对应关系。受限调用继续按当前运行约束处理；不要从旧文档中能够调用 `to_csv`、导入库的示例，推断当前国信账户拥有文件／网络权限。

## Python 版本：区分内置解释器和外部 SDK

| 环境 | 官方可核实说明 | 当前解释 |
| --- | --- | --- |
| 国信历史内置环境 | G3 2019 年手册的第三方库章节要求对应 Python 3.6；封面为 V1.0 | 可追溯旧环境，不能作为 2026 年新发行包的完整版本清单 |
| 迅投通用内置环境 | X1 概述仍写 3.6 | 本次没有找到官方内置 3.12 选择手册，实际以国信发行包与运行解释器为准 |
| 外部 XtQuant 概述 | X7 列 64 位 Python 3.6、3.7、3.8、3.9、3.10、3.11、3.12 | 适用于外部 Python 库与 MiniQMT 交互 |
| 外部 XtQuant 版本记录 | X8 的 2024-06-17 条目新增 3.12；2025-05-16 `xtquant_250516` 条目新增 3.13 | 概述与发行说明有更新差；应按所用 SDK 发行包确认，不能套用到内置策略 |

来源：[G3 国信历史手册](https://www3.guosen.com.cn/guosen/newxwfiles/20190902/1567416998056.pdf)、[X1 内置环境](https://dict.thinktrader.net/innerApi/start_now.html)、[X7 外部环境](https://dict.thinktrader.net/nativeApi/start_now.html)、[X8 SDK 发行记录](https://dict.thinktrader.net/nativeApi/download_xtquant.html)。

运行环境留档时分别记录：`sys.version`／`sys.version_info`、位数、客户端版本、实际解释器 DLL 版本、相关 SDK 包版本和探测日期。启动器 `pythonw.exe` 的文件版本只能说明该启动器自身。终端外执行一个 Python 程序，也只能证明该程序的解释器；最终内置版本应由内置只读回调确认。本段为证据采集建议。

## 内置 API 持续查阅入口

以下是开发常用接口导航，不代表当前账户全部接口已验收，也不是对官方完整参数文档的复制。`ContextInfo.xxx` 为上下文方法；没有前缀的交易／生命周期函数按官方示例在策略全局使用。内置方法与 `xtquant.xtdata`、`xtquant.xttrader` 的外部接口分开维护。

| 职责 | 官方接口入口 | 使用边界 |
| --- | --- | --- |
| 生命周期 | `init`、`after_init`、`handlebar`、`stop` | 系统调用；`after_init` 适合初始化完成后的操作，部分接口在 `init` 尚不可用 |
| K 线位置 | `ContextInfo.is_last_bar`、`is_new_bar` | 判定主图事件位置，避免历史遍历时重复执行实时工作 |
| 定时器 | `ContextInfo.run_time`、`schedule_run`、`cancel_schedule_run` | 文档包含新旧接口；新接口增加分组／取消能力，本机支持仍须核验 |

以上接口与上下文状态说明见 [X3 系统函数](https://dict.thinktrader.net/innerApi/system_function.html)。

| 行情与参考数据 | 接口 |
| --- | --- |
| 最新快照 | `ContextInfo.get_full_tick` |
| 实时全推 | `ContextInfo.subscribe_whole_quote` |
| 单品种／周期订阅 | `ContextInfo.subscribe_quote` |
| 取消订阅 | `ContextInfo.unsubscribe_quote` |
| 历史／实时 K 线 | `ContextInfo.get_market_data_ex` |
| 下载历史 | 全局 `download_history_data` |
| 清单、基础资料、日历 | `ContextInfo.get_stock_list_in_sector`、`get_instrument_detail`、`get_trading_dates` |
| 复权与财务 | `ContextInfo.get_divid_factors`、`get_financial_data`、`get_raw_financial_data` |
| ETF 参考资料 | 全局 `get_etf_info`、`get_etf_iopv` |

`get_full_tick` 返回当前最新分笔快照，不能请求历史分笔。全推订阅支持市场或品种列表，只增量推送变化的品种；订阅号交给 `unsubscribe_quote`。`get_market_data_ex` 支持 `1m` 等周期、显式复权及填充参数，`subscribe=False` 只读取现有本地数据；官方不推荐在 `init` 使用它获取在线数据。原 `get_local_data`、`get_history_data`、`get_market_data` 在当前目录标为不推荐。[X4 行情函数](https://dict.thinktrader.net/innerApi/data_function.html)

| 交易职责 | 接口 |
| --- | --- |
| 发送委托 | 全局 `passorder`；算法接口 `algo_passorder`、`smart_algo_passorder` |
| 撤单 | 全局 `cancel`；算法任务 `cancel_task` |
| 账户、资金、委托、成交、持仓 | 全局 `get_trade_detail_data`，按官方类别参数选择 |
| 历史明细、指定委托 | `get_history_trade_detail_data`、`get_value_by_order_id` |
| 信用账户等扩展 | `query_credit_account`、`query_credit_opvolume` 等 |

`passorder` 的快速交易参数会影响委托触发时机；查询接口类别和回调对象须按当前文档映射。以上是接口存在性的官方依据，实际交易权限、柜台支持和可用字段应独立验证。[X5 交易函数](https://dict.thinktrader.net/innerApi/trading_function.html)

账户、委托、成交、持仓变化分别查阅 `account_callback`、`order_callback`、`deal_callback`、`position_callback`，以及官方回调页面列出的错误和任务回报。相关回调页面要求实盘运行模式，并先通过 `ContextInfo.set_account` 订阅账户。资金和订单的查询快照与异步回报须明确时点与身份；回调名称存在不等于实时数据已同步完成。[X6 实时主推函数](https://dict.thinktrader.net/innerApi/callback_function.html)

## 性能与线程／进程：官方事实和实现建议

官方使用须知明确限制内置 Python 的多线程／多进程，并称各策略共用执行线程，阻塞写法会影响其他策略。该页也提醒 `ContextInfo` 自定义状态可能随 K 线回滚，建议把持续状态放在自建全局对象。[X2 使用须知](https://dict.thinktrader.net/innerApi/user_attention.html)

系统函数的 `stop` 文档则提到策略中已经创建线程时可在此收尾，并说明停止回调时交易连接已断开，应避免在停止回调发委托或撤单。两页没有给出能够消除口径差异的客户端版本范围或线程安全 API 白名单。[X3 系统函数](https://dict.thinktrader.net/innerApi/system_function.html)

据此采用以下**工程建议**，并以本机调用链证据验证：

1. 把官方 SDK 查询、订阅／反订阅及交易调用保留在已确认可用的策略回调线程；后台线程接收纯值，不持有 `ContextInfo` 去跨线程调用。
2. 行情回调仅筛选目标证券、提取必要字段并交出有界批次，减少逐条打印、反复构造大表和全市场轮询。全推属于事件驱动，原生采集和分钟聚合交由外部 C++ DataKit。
3. 将压缩、持久化、历史转换和较重计算交给系统管理的外部进程。QMT 内部创建 `multiprocessing` 子进程的支持证据本次未取得；不能直接当作加速方案部署。
4. 内置纯内存通信线程的可创建性、调度延迟、退出过程和对其他策略的影响属于本机版本验证项。为此增加线程数量之前，先记录 SDK 耗时、回调耗时、待发送量、外部消费速度，识别实际瓶颈。

外部 XtQuant 的“本地 Python 回测支持多线程”出现在其 2024-03-29 版本记录中，该说明限定外部 SDK 场景。[X8 版本记录](https://dict.thinktrader.net/nativeApi/download_xtquant.html)

## 升级与维护时保留的检查表

- 保存客户端、解释器和 SDK 的独立版本证据，并把官方发行说明与实际安装包对应起来；公开版本号未能映射时登记为待核实。
- 核对已用 API 的函数名、参数、返回字段、单位、回调和停止行为。新增函数只在已验证的客户端能力下使用。
- 对受限账户继续保持 QMT 运行阶段的文件／网络约束。库更新、依赖打包和配置生成在外部完成，不能沿旧示例自行恢复受限访问。
- 首先验证只读快照、订阅、取消订阅与退出，再验证历史和账户查询。涉及真实交易的验证按账户授权单独执行。

上述是后续维护建议。本次没有安装更新、切换 Python、修改策略或改变权限。国信内置 Python 可选版本清单、2026 年文件／网络权限变更公告和 SDK 跨线程安全契约，仍缺少可直接引用的官方材料。
