# Native策略归属事实接缝

类型：接口规格。状态：implemented / isolated-validated；正式整体装配与采用待所属发布验证。范围：[OLS](original-live-strategy.md)的同账户双ctx归属关联；份额/现金分配由单一ASA模块负责，Native接缝不计算分配、不增加持仓/命令数据库、不发独立订单。旧单策略默认不注册回调，沿原行为。

## NAH-1 注册与生命周期

提供独立可选C ABI1事件回调，原MS/CTA/Standard DTO及ABI保持。`gh_cta_attribution_configure`在原run前同配置线程注册一次；原run冻结并向同次实际加载的ManagedFactory和Standard插件传递。显式启用后所需可选导出缺失即启动拒绝，不静默关闭；调用方保留callback/user直到原策略、执行owner和worker均回收或进程退出。禁止运行中替换、解除或热切回调。独立策略DLL与Standard插件有对应注册/能力入口，供同一次装配及隔离验证。

事件头包含size/version、kind、线程角色、原epoch、原剩余期限、UTF8字节数和仅本次回调有效的JSON指针，pack8。JSON由Native完整复制证券、字符串与向量后生成；Python必须在回调返回前复制字节。每事件最多2MiB，完整目标沿原最大4096项资源合同；超限失败且不截断。上限属于接口资源，不作为交易次数/总资金配额。

回调签名为`int32 callback(const EventV1*, ReplyV1*, void*)`。ReplyV1含size/version、decision/reserved、authorized_quantity；初值decision=-1、quantity=0，接收方须明确答复，异常未答复保持关闭。通知要求C返回0、decision=0且quantity=0。authorize在原group begin/base buy或sell之前，decision=0须给0<quantity<=原请求（BUY百份，SELL正整数）；decision=1且quantity=0表示暂缓，不创建group或派发；负返回/非法回复为协议失败。无callback保持原数量与原路径。实际缩量后原WT继续按真实OrderIDs、持仓/undone与原剩余目标推进，不把请求量写成已成交量。

7/8/9已有原绝对截止：JSON编码完成、真正回调前重算同一原D的剩余毫秒，余量<=0（含不足1ms）直接Timeout且不进入回调；原callback返回后和source循环收尾仍核同一until。该阶段不把0当成无独立D，不从本地预算重开。prepared截止失败保留原UUID/receipt、NotSent及写围栏，Source已经交付的WT事实继续沿原来源恢复。

原ctx事件仅在原线程/epoch内发生；worker事件只含不可变原身份和真实拟报参数，不调用ctx或策略KV。回调不重入Native控制/下单接口，不跨ABI抛异常；ASA持久事务归调用方，同一次原截止不因回调刷新。关闭继续原owner顺序：停止策略生产→交接停止→原提交/查询责任收口→worker join→释放API/DLL/callback。

## NAH-2 事件与顺序

| 事件 | 原接缝与字段 | 确认范围 |
|---|---|---|
| strategy_targets | Managed同epoch，完整预验后、首个原setter前；strategy_id/ctx_id/owner_token/epoch/交易时钟及完整symbol/quantity向量 | 策略意图，不是成交；setter部分失败沿原锁存 |
| merged_targets | 原Local::set_position收到WT同轮已合并完整向量；execution_id/完整targets | 原合并commit，Native不再次汇总策略目标 |
| target_delta | 原Local::on_position_changed的真实增量及execution_id/symbol | 即时增量，不能冒充同轮完整commit |
| authorize | 原Local buy/sell内、原group begin前；execution_id/instance_id/symbol/side/requested_quantity/规范limit_price_cny及原account_known/available观察 | ASA唯一算法返回实际允许量或暂缓；只裁剪原请求，不生成新目标 |
| submission_group | 原QueryFirst.begin成功后、delegate前；instance_id/native_generation/group_id/symbol/side/原实际qty/规范限价字符串 | 原组身份；Root需加本Runtime/control前缀，裸group号可重用 |
| wt_child | 原WT entrust已形成、enqueue前；原group、entrust_id/user_tag/实际qty/规范限价 | 原WT委托标识，尚无prepared UUID，不能宣称已绑定金融命令 |
| prepared_child | worker create_insert得到原receipt后、真实submit_once前；同group/WT身份、原command_id、正文SHA、真实qty/限价、原剩余期限 | ASA确认持久关联且首次准许后才可派发；绑定失败禁止此dispatch，原UUID与原结果责任保留 |
| source_fill | 原完整QMT身份映射和WT SPI交付后的原实际trade/order/user_tag、symbol/side/整数增量qty/price/amount/date及明确source_kind/source_sha256 | 实际源成交；费用缺证明为null，可卖日由合格日历消费者提供，不推算T+1日期 |
| source_order | 原完整query或event身份映射后，保留order状态/原累计成交/未成交/源SHA和WT关联 | 原订单观察；cancel命令返回不代表插入单终态，缺成交时由ASA保持待补 |
| group_end | 原QueryFirst.end返回后，原group/实际quantity/accepted_children/decision/outcome | 原delegate退出，不能由此宣称所有child金融终态 |
| original_insert_result | 原pump核完成值generation/ticket后；同group、WT/command身份、command_sha256、原phase/status/source结果摘要 | NotSent/DefinitelyNotCalled且原insert_failure_confirmed才给dispatch_not_entered与filled_quantity=0；SdkReturned只确认命令返回，不释放券商订单责任 |

原QueryFirst group覆盖一次Local buy/sell delegate，delegate内部多个WT child共用该原group；股票撤后重算再次进入buy/sell会产生原生后继group。Native不另造金融group以规避未知/次数责任。同plan可由ASA明确承接原后继组。

group/child/prepared的价格使用既有Standard price_text同一正文和品种tick，字符串以原价CNY/份表达；仅消除原有档位浮点噪声，原离档值保持。所有数量保存原整数份，不在hook取整；合法SELL碎份沿原通道。Native不把CTA条件阈值当作真实委托价格，也不增加全账户D限价。

源成交/订单事件从既有已验证映射提取有限白名单。原全账户QUERY默认不生成单行canonical记录；其source_kind=`query-result`、source_sha256为原完整result_sha，并附原request_id/output_index/lookup_sha。EVENT/selected-row的source_kind=`derived-facts`、source_sha256沿原mapper的derived_facts_SHA，并附原sequence/derived_page_sha256/derived_event_sha256。canonical key含账户字段，回调只给canonical_key_sha256，不复制key正文。源成交trade_id沿原WT mapper稳定nqh1派生ID，保持原金融去重决定。源price/amount保存有限double的完整往返十进制文本，保留原合法零值，不重新按tick修改源事实。重启查询未必在本进程Identity中有command UUID；保留已验证WT user_tag/entrust/broker身份，由ASA持久prepared索引查回，缺关联保持未知，不按revision猜归属。费用与账户字段不伪造，也不复制凭据或整段私有lookup正文。

全账户 QUERY 的订单和成交按原回报顺序分批交给归属回调，kind 12 的正文包含原 kind 8 或 9 与逐行原 JSON 字节。每批在原查询截止内使用一次同步收件事务，单行身份及原证明摘要不变。已关联行再按原顺序和规则投影。实时 EVENT 继续使用原逐行入口。诊断记录原查询类型、回调阶段、剩余预算及首个失败原因。

## NAH-3 失败、恢复与默认兼容

原group已建立后的准入拒绝、prepared关联失败、回调异常和超时分别保留原阶段。prepared失败既不能进入真实submit，也不能把原UUID换成新UUID重试；原pending保留完整receipt及原UUID，next_due不进入自动审计删除路径，原写围栏关闭。原owner的kind11继续给出本地NotSent事实，source_sha256=null，不能伪称收到Source回执；回收/恢复沿原Standard责任及ASA原关联核查。外部结果已经发生后，归属回调失败不重复交付WT或重发命令，保留源身份并关闭后继派发，恢复时按原事实幂等续接。

每条回调只确认关联/准入，不确认券商接单或成交。Native不重建分配FIFO、资金账本或执行器，不以返回后的submission_revision充当前置关联。所有默认未注册路径、旧ABI1八标的、可选V2九标的、只读绑定和独立Realtime继续原语义。

## NAH-4 验证

主路径实际Native DLL/原SDK替身：双ctx完整意图→WT合并commit→原group→原WT child→prepared UUID/SHA持久回调→原SDK submit，严格核prepared回调先于真实SDK调用，拒绝时SDK调用0。原fill/terminal沿同一UUID/WT标识回查，保持原增量/累计含义和来源摘要。

隔离实际验证分为两条：Managed真实Factory/CtaStraContext的双ctx八/九完整意图与17次setter；StandardHost/原股票单元/WinSHM原Host/SDK替身的200→100裁剪、原group/child/prepared前置确认、Source查询和实时20成交/80余量。两条分别证明本Native模块接缝；完整Runtime→ASA协调器→双ctx金融装配及正式采用由所属整体回归补齐，不将两条分层验证表述为已完成真实账户执行。

随后验证绑定拒绝（SDK零调用、原UUID/pending保留）、授权暂缓/非法数量（零group/child/SDK）、默认无回调原200份路径、错误线程/epoch、显式回复/布局/超界/完整复制与物理关闭。跨重启ASA分配、异序/晚成交、原取消未知、完整恢复和真实账户授权由ASA/原Host所属回归及整体装配继续核验；Native回调不增加第二份恢复账。TEMP/TMP/构建/日志/SQLite和pytest输出全部显式E/D；真实账户启停与金融采用另验。


## NAH-5 固定ABI与JSON键

公共纯C头为`src/GuanhengCommon/AccountAttributionProtocol.h`；内部Hooks序列化不作为SDK依赖。EventV1=48B、ReplyV1=24B。Runtime导出`gh_cta_attribution_abi_version()`=1、`gh_cta_attribution_layout(1/2)`=48/24（未知0）、`gh_cta_attribution_configure(callback,user)`；Managed导出`gh_ms_attribution_abi_version/configure`，Standard导出`standardQmtAttributionVersion/configureStandardQmtAttribution`。注册在配置线程执行，创建/run后冻结；错线程freeze明确失败，多个ctx共享同一Managed实际DLL的一次注册。

kind数值固定：1 targets、2 merged、3 delta、4 authorize、5 group、6 child、7 prepared、8 fill、9 order、10 group_end、11 original_insert_result。kind11的phase按原QmtTradePhase固定投影0 NotSent、1 Queued、2 Dispatching、3 DefinitelyNotCalled、4 SdkReturned、5 Unknown，并附phase_name；command_id/command_sha256/source_sha256缺证据时为null。source_kind分别为native-insert-result或source-command-result。dispatch_not_entered只有原明确未进入/未调用时true，filled_quantity对应0；其它情况填null，不把未知填0。attribution_binding_failed仅表示本地关联回调失败，与券商事实分开。

原8标的ABI1/GhMsConfig、V2/GhMsConfigV2、Realtime和原Standard诊断结构均保持布局；新增能力通过独立导出选择。Group/child/prepared分别按原Runtime/control + instance_id + native_generation + group_id和完整entrust_id/user_tag关联，裸整数不能作持久唯一键。Source返回的command_id=null可沿持久WT关联回查，不能生成新金融UUID。


## NAH-6 WT child已登记但入口拒绝

显式归属时，在kind6前保存原OrderValue/group的纯值副本。kind6确认后原enqueue若明确返回rc<0，沿原WT身份发kind11：NotSent、dispatch_not_entered=true、filled_quantity=0、原enqueue_return_code完整负值，command_id/command_sha256/source_sha256均null；没有worker/SDK调用或新UUID。原负返回与group_end accepted_children继续原路径，ASA据本地未入队证明结算该child。无归属路径不增加此复制；异常且结果未知继续原hardfault，不伪造已知未调用。
