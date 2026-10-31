# QMT订阅期同步回报的本地保留

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证记录。日期：2026-10-26。状态：新增回归实际1/1通过，独立源审及动态delta复核通过。范围为生成策略初始化的本地订阅窗口，完整首次/重连交接继续待验。

## 目标与真实路径

QMT的set_account可能在订阅函数返回前触发回报。生成入口须先发布真实Agent，再调用一次订阅，确保同步成交到达时已有SourceTradingService及事件缓冲，随后才进入timer/I/O start。新增回归（外部历史/待归仓路径：`../../tests/integration/qmt_shm_trading/test_r8_subscribe_reentrant.py`）实际调用render_trade_strategy生成完整wrapper及回调体，构造真实RestrictedTradingAgent、SourceTradingService与AccountQueryAdapter，经生成deal_callback捕获16字段合成成交。

固定替身边界为memory loader shim、monotonic时钟和base read I/O start；测试不创建线程、映射或socket，不执行账户查询、下单、撤单或真实SDK。不调用旧QMT工程。原两条模板/Agent部分测试保留，本例补全真实生成回调至事件捕获和正常排空的调用链。

## 已验行为

订阅时_agent已发布，worker/start尚未发生；set_account一次，原session/binding下sequence=1，TradeID getter只读一次。同步回报在start边界前已保留；修改源对象后原页仍为数量100。stop后尚未ACK的事件仍占资源，local_drained与trading_close_confirmed保持false；真实page/acknowledge后，原close(D)完成，retained/inflight/used_bytes均0，ACK=published=1、无gap及cleanup failure。read/order/cancel替身计数均0，首次关闭期限不延长。

源码摘要f6808255ea479eb060db0a63f4b85be736bab834fb426d175ca23631a520351d。非作者独立源审（外部历史/待归仓路径：`../../build/qmt-r8-subscribe-reentrant-independent-001/REPORT.md`）核22必要原件，P1/P2为0，执行0；根复核75前置输入及当前源，75项前置输入中的70个Python源码输入均匹配既有169项冻结运行树；此为输入集合核验，本次未记录逐模块导入追踪。测试由原unittest单方法入口运行，-I/-B与既有隐藏创建期Job/原总截止控制器保持，方法自身同一5秒单调截止。

实际1方法、0失败/错误/跳过，unittest0.016秒，完整控制器1.093秒退出0；无强杀，真实Job/tree0/双EOF/reader join及句柄关闭完整。见集成收据（外部历史/待归仓路径：`../../build/qmt-r8-subscribe-reentrant-implementation-001/TEST-INTEGRATION.json`）和实际运行（外部历史/待归仓路径：`../../build/qmt-r8-subscribe-reentrant-implementation-001/RUN-ROOT-VERIFIED.json`）。产品、框架、运行终端及生产入口保持。

## 来源形状前提与未覆盖范围

既有投影v1/v2的四项固定字段/标量/节点字符字节边界回归，以匹配当前源的同一冻结树实跑4/4通过（unittest0.020秒，控制器1.156秒），见来源前提收据（外部历史/待归仓路径：`../../build/qmt-r8-subscribe-reentrant-implementation-001/SOURCE-SCALAR-PRECONDITION-VERIFIED.json`）。它支持当前Agent固定标量字段的来源前提；C++公共DTO任意附加字段域、所有resident费用上界仍需各自验证。

本例只证明本地注册窗口的值保留、真实内存owner ACK/close；memory loader、真实I/O线程join、Host持久ACK、实际券商回调、背景缓存跨查询覆盖及WT查询/增量交接均不在范围内。R8首次/重连的联合覆盖仍待来源研究（外部历史/待归仓路径：`../../build/qmt-query-live-r8-source-followup-003/DELTA.md`）和后继真实输入验证，不能用本地sequence或时间替代。

## 独立动态复核

非作者动态复核（外部历史/待归仓路径：`../../build/qmt-r8-subscribe-reentrant-independent-001/dynamic001/REPORT.md`）核准上述1/1与4/4实际运行及原截止、创建期Job、tree0、双EOF、reader join和资源关闭。根逐项核验21份新增原件及当前文件SHA一致，报告摘要0c508c7906c404f0acafdcd9e0339e0b806a9f7c7d00e72f670625376cc30982，见根核验收据（外部历史/待归仓路径：`../../build/qmt-r8-subscribe-reentrant-implementation-001/INDEPENDENT-DYNAMIC-ROOT-VERIFIED.json`）。新增已确认P1/P2为0，原22份静态原件复用。本轮26份框架保护摘要保持。限定资格仍为本地订阅窗口及选定来源投影，完整首次/重连交接继续待验。

## 官方来源后继研究

2026-10-26官方文档增量（外部历史/待归仓路径：`../../build/qmt-query-live-r8-official-increment-001/REPORT.md`）重新区分历史分组时间标签、持仓统计字段与实际联合覆盖。当前官方说明没有给出P/O/D共同版本及已吸收成交集合；指定全局callback-cache接口读取会消费并清空缓存，不能归为被动观察。旧FAQ按2026-10-24已封原件及原日期使用，本轮没有重证其旧交易缓存段落；这也不证明行为已经改变。国信当前版本支持仍unknown，研究不扩大本地订阅测试资格。根核4项原件、3项当前本地来源及3项元数据；网页保存规范化工具返回，未声称HTML原字节，见收据（外部历史/待归仓路径：`../../build/qmt-r8-subscribe-reentrant-implementation-001/OFFICIAL-INCREMENT-ROOT-VERIFIED.json`）。
