# 原生交易查询接缝核查

类型：只读源码研究记录。状态：源码结论已核实，真实券商运行时序未实证。固定上游 `08b230dd05facf6d650d949bfe51054115a2ecb1`，QMT基线 `2083e96ac7134ad808d6bfddcdfe19aaa11a64fd`。独立研究使用固定Git版本，主任务复核原Adapter顺序及成交处理位置；没有改动源文件、运行QMT或操作账户。

## 原生职责

| 问题 | 固定原版实际行为与入口 |
|---|---|
| 是否要求四查询共同原子批次 | `src/Includes/ITraderApi.h:145–175,259–274`为独立查询/响应与push接口。`src/WtCore/TraderAdapter.cpp:1418–1434,1588–1593,1714–1719,1798–1803,1527–1533`依次推进登录→持仓→委托→成交→资金→ready，没有共同snapshot参数 |
| 原插件怎样查询 | `src/TraderXTP/TraderXTP.cpp:899–953`每次调用独立SDK request ID，收集末包于412–469、519–577；`src/TraderCTP/TraderCTP.cpp:456–548`分别排队，199–229限制一次在途及请求间隔至少一秒，966–1023独立结束各批。共享session或串行查询不代表共同观察时刻 |
| 查询和回报怎样分工 | Adapter 1537–1583更新查询持仓，1596–1712统计委托并建立匹配WT标签的活动单投影，1729–1796只统计历史成交；2134–2251的push成交实际修改持仓/未完成量并通知sink。历史成交应交onRspTrades，不能作为onPushTrade再次重放 |
| 原防重涵盖什么 | `_orderids`在1626及1940–2025保护部分首次订单统计/冻结；`checkSelfMatch`1806–1840检查成交ID对应不同订单，调用位于1784/2246且未用于提前return。它不提供任意历史成交push重放幂等，也不构成重复全量查询的通用保护 |
| 重连是否统一 | XTP 346–355重新登录，772–816已初始化时只恢复插件状态；其固定SDK头44、518–523说明未logout重登录续接断线消息，RESUME枚举注释标暂未支持。CTP 574–584、609–654、673–724在重连/登录/结算后通知成功，再触发Adapter查询链。具体SDK行为须按插件核实，不能推广为HTTP恢复保证 |
| 是否必须迁移旧策略归属 | XTP 278–291、339–341、785–800、867与CTP 365、633–648、1236–1249、1354–1356使用原WtKVCache保留entrust/order→WT标签；Adapter1685–1701才将活跃且匹配本实例的订单纳入管理。旧QMT或外部单可只读统计，管理标签为空；授WT本地管理归属时再要求可信映射 |

以上行号均指固定Git版本，避免工作树冻结差异影响结论。原SDK查询完成语义与推送续接依赖其真实实现；本次源审计没有证明券商现场重连或跨进程恢复成功。

## 自有适配的最小责任

每批结果须关联原request ID/type，区分成功、失败、未完成和完整分页终结，核验可信来源账户/环境/会话代际、交易日及该批观察范围/时间；容量、截止、取消和晚结果隔离由适配层负责。合法空持仓/委托/成交与None/错误分别处理。原Adapter在null响应后仍可能推进（1527、1588、1714、1798），故适配层在SPI之前验证单批成功，不能把不完整结果转空成功。

QMT `qmt_agent/broker/adapters.py:342–347,550–558`的account.trade_detail已绑定账户并调用原生函数；`gateway/operation_queue.py:415–425`通用envelope有request/type/成功/完成时间/data，尚未自动提供全部来源与完整性证明。可选整批来源也有边界：`NativeCapture.add:109`使用values or ()，`native_producer.py:312–326`保留原窗口和资格要求。选取整批投影不自动获得更强证明。

据此收紧尚未实施的[HTTP接线草案](../migration/native-qmt-http-snapshot-plan.md)：遵循原四查询顺序及逐批完整性，将旧整批Observation链和reconciled状态从必选前置收回到可选来源；字段、访问权限和已选入口限制照常遵守。无需为本次只读初始化新增账户数据库或对账器。

## 后继HTTP来源链补核

本段为后继只读调查，QMT源码目录为`E:/workspace/qmt-worktrees/native-readonly-fields`，HEAD仍为上述基线。Adapter、Queue、Journal及HTTP受查实现与该Git版本一致；原生字段白名单修订是单独候选，尚未安装。研究者给出逐项源码位置，主任务复核`agent_tick`绑定捕获、Queue旧结果复用及Journal结果保存位置；没有读取运行账户数据或修改源端。

| 项目 | 源码事实与具体边界 |
|---|---|
| 请求关联 | `gateway/core.py:728–746`检查path/body操作一致和参数对象；`operation_queue.py:255–274`以operation_id+arguments生成请求摘要并检查ID冲突。四查询共用account.trade_detail，datatype仍在原请求arguments中，消费者须保留本次描述 |
| 账户 | `broker/adapters.py:342–347,550–558`注入bindings.account_id，客户端参数不能覆盖账户；原生行账户字段可缺失且空数组无行，不能代替执行批次身份 |
| 环境与代际 | `core.py:304–322,868–875`可重配环境且health公开agent/session/generation/environment。`bind_context:287–302`推进generation；同ContextInfo在`agent_tick:355–363`重新创建bindings时可换account_id而未推进generation。因此generation与前后health不能单独证明账户绑定 |
| 执行点 | `core.py:368–392`在锁内捕获bindings/generation，再由闭包沿原策略线程调用Adapter；`queue.py:372–373`执行前拒绝过期代际。执行身份应对应实际捕获的bindings和配置上下文，不能事后从最新health回填 |
| 旧终态 | `operation_queue.py:268–293`可按原ID直接返回持久终态，原请求身份没有账户/会话/generation。旧结果继续结清原请求，不能把本次准入generation写成旧执行generation |
| 空、None与异常 | `broker/adapters.py:182–183`原样返回；`encoding.py:133–134,171–174`分别保留None与空列表，形成ok=true/data:null和ok=true/data:[]；`queue.py:427–435,588–598`将异常变为ok=false及error。`http.py:159–171,186–194`保持这一区别，202只表示等待未终结 |
| 完整性 | `encoding.py:128–174,194–205`超深/超容量/循环/不支持对象报错，逐项转换不静默截断；仍缺券商get_trade_detail_data的完整返回范围、None含义及隐式限制证据。序列化成功不能自行声明券商完整 |
| 时间/交易日 | `queue.py:399–420`记录执行开始并在原调用返回后生成completed_at；`journal.py:484–509`保存开始/完成。可公开服务器执行区间，不能称券商原子时刻；交易日/查询范围缺少来源时明确不可用，不能由HTTP完成日期补造 |
| 原持久所有者 | `journal.py:468–515`已有request payload和result JSON，517–548在重启后终结未完成请求，550–575按原ID读取。新增逐批来源元数据可沿已有结果JSON保存，无需新数据库或第二请求账本 |

原结果摘要的覆盖还有明确边界：Journal在493–497计算持久result SHA；Queue随后追加result_persistence_ms/result_sha256，Ticket在101–113追加response_wakeup_ms，HTTP还追加返回计时。接收端须使用原owner定义的稳定投影核验，整个最终响应JSON不等同于原摘要输入。

现有QmtHttpClient只允许两个market操作（61–62、180–193），528–563在本次预算内只认领原ID；它在568把远端错误归一、570–574只保留data。HTTP非200/202还可能在319提前返回错误。后继应在原响应容量约束下保留完整envelope、结构化错误及传输观察，复用签名/截止/认领/drain。来源身份、范围和完整性在原源端执行/结果所有者补齐，插件仍只负责单批验证与原SPI映射。具体分层见[HTTP草案的复用接缝](../migration/native-qmt-http-snapshot-plan.md)。

该结论支持最小接线设计；真实券商字段、None/完整范围语义、当前安装身份及运行效果仍待实证。

### 原生查询的策略筛选范围

主任务另核`broker/adapters.py:550–558`：当前account.trade_detail使用四参数调用，第四项固定为`"qmt"`。迅投[内置Python交易函数文档](https://dict.thinktrader.net/innerApi/trading_function.html)及[现行知识库](https://knowledge.thinktrader.net/docs/python/trading_function.html)在2026-10-22检索时均说明：strategyName对ORDER/DEAL有效，可筛选相应策略的委托/成交；三参数形式不按策略筛选。官方声明返回list，未在该接口说明中定义None成功语义。XtQuant的其他查询接口属于不同调用契约，不能代替此处证据。

据当前代码与官方参数定义推论，该公开入口的ORDER/DEAL应登记为strategy-filtered(qmt)查询，不能作为账户全量完成证明。POSITION/ACCOUNT不受这个参数的筛选定义影响，但仍需核各自来源身份与字段。后继需要账户全量时，应沿源owner提供明确的三参数、不筛选策略的只读范围，同时保留原消费者依赖的策略筛选语义。不得悄悄改变现有默认范围；原请求、返回范围与完整性声明需一致，fixture须含qmt、其他策略和外部记录以验证覆盖。此处没有执行真实查询，也没有证明当前券商返回内容或生产筛选效果。

原项目已存在三参数采集：`qmt_agent/qmt_strategy.py:176–180,209–222`以及`broker/native_producer.py:311–313`按绑定账号/类型调用原函数，不传策略名。这证明原项目已有相应调用方式，可作为源端语义复用依据；不要求新只读接口接入整个旧快照/对账发布链，也不将这些源码路径等同于当前公开HTTP操作的运行证据。

## 后继验证边界

只读查询成功不授持续回报或真实交易资格。真实接线继续证明查询与实时流交接、重复/缺口/乱序、断线与进程恢复、可信订单归属及发送/撤单权限和风险条件。先核已有WT/SDK能力，再按具体缺口补适配；本次没有形成新增框架修改的必要性结论。
