# 全市场日线准备与捕获

唯一要求见[规格](../specs/qmt-market-daily-preparation.md)。该模块位于WT侧，终端内仍使用
原HPR/v8共享内存owner。观衡消费已完成包，不控制缓存下载或WT生命周期。

库接口注入原运输，不要求Host基础角色安装分析工具链。外部CLI属于WT完整角色，依赖
原`guanheng-native-analysis-core`提供的BoundHistorySource；发行角色以精确wheel锁携带该依赖。
仅安装基础Host时使用注入运输的库接口，WT CLI资格沿实际完整角色分别验收。

`MarketDailyPreparation.run`先完成每证券原HPR，再调用`BatchAnalysisSource.capture`。
两个连接分别保留完整binding；正式组合正文摘要由部署方写入source_association，证明
两个来源由同一正式QMT策略装配。调用者拥有workflow目录的唯一写权限。

首次准备前固定HPR-BINDING与原capture/BINDING；每次未完成续接先校验当前两端。
`run(..., connection_identity=...)`可将外部调用者的实际连接配置纳入原目录身份，正式
CLI传入完整已解析配置；该配置只有原端点、key_id、秘密环境变量名与预算，秘密值不入盘。
已固定配置的目录续接须继续提供原配置。非法绝对D在任何目录或来源动作前拒绝。

正式CLI在原`BoundHistorySource`上显式选择`reuse_connections=True`。一份运输实例由一个
工作线程使用，连接归最外层`rpc_budget`所有：首次交换时连接，同一作用域内复用，退出
作用域时关闭。嵌套预算继续取原最小值；每次交换重新生成认证时间、nonce和签名，并以
该次原绝对截止限制实际发送/读取。服务端关闭连接时退役原连接，后继交换可建立新连接。
交换异常关闭连接并沿原Pending/异常返回，连接层不重放请求；原ID续核仍归RetainedReadClient。
关闭异常保留连接owner与原异常链。默认省略该显式选择及无预算作用域的调用保持单次关闭。
该接缝没有常驻连接池或新线程，连接配置字段及金融读取行为保持。

数据组织包括固定REQUEST、HPR-BINDING、preparation原slot、capture原v8批次及RESULT索引。
原slot含原请求/票据/原结果与消费确认，Host Journal拥有通信事实。PROGRESS仅表示已核
确认的函数返回数量。完成包保存原SDK观测日期与none/front引用；无行情/复权补值算法。

初次准备业务窗口，后续显式观察可从已捕获尾日重叠更新。预算到达或人工分段后继续同一
目录；网络未知沿原ID核查。换来源、换窗口或证券池需新业务观察，原未知责任仍保留。

官方[下载API](https://dict.thinktrader.net/innerApi/data_function.html)使用单证券四参数。
[多证券示例](https://dict.thinktrader.net/innerApi/code_examples.html)通过循环调用该接口；
批量get_market_data_ex用于回读。显式v3接收BJ格式；下载支持、真实缓存更新及停牌/上市
导致的日期差异分别由实际回读和消费方核实。

## 显式cache-first接缝

v2请求的mode=cache-first由同一个MarketDailyPreparation.run分派。原BatchAnalysisSource先读cache；纯值资格/缺口计划由market_daily_cache.py拥有，协议版本`t2108.ashare/2`；HPR执行复用原同一准备器，回读仍进入原capture。cache、PLAN、QUALITY均保存原件摘要。v1旧目录继续先全准备，不能用新模式替旧结果改资格。

QUALITY区分全池已核与全池合格：部分覆盖保留实际缺口、源时间和分类，completed只说明本次原责任/回读完成。源数值/身份错误直接交原失败类，不生成缓存下载特判。完整字段及范围规则唯一见MDP6。

新v2经Batch/HPR把30秒外部新请求准入余量交给原RetainedReadClient；检查在当前绑定之后、原请求plan/新槽之前，已有槽仍原ID续核。默认0保留其他消费者。固定未准入原因由操作owner记录阶段paused；真实Pending/Unknown保持责任，不作为普通预算暂停吞掉。
