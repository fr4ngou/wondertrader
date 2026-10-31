# 原交易通信库的显式容量扩展

类型：模块B恢复能力设计。状态：accepted / implementation-in-progress。适用范围：已停止交易Host的原通信Journal；不改变WT框架、策略账本或绩效。集成者已确认由B实施自有通信能力，永久Host源保留当前Host22+mdphttp.3的后继，发行接线由集成owner完成。

## 目标与必要性

当前full046原金融目录已恢复加载并由Native10968正常关闭。后继需重建测试Source，原通信库已保留两个来源会话；其max_streams=2进入持久身份，第三会话的空页也触发JournalFull。现有构造接口要求身份精确一致，无法直接提高配置上限。[实际复现与检查点](../evidence/2026-10-31-host-idle-functional-observation.md#原金融目录恢复后继与来源会话容量)说明当前阻断和证据边界。

目标是在保留同一Journal全部原命令、查询、事件、来源和确认前沿的条件下，显式增加其来源会话容量，再从最新真实金融状态继续。单独提高新库默认值无法解决已存在的原库。

原生能力WT-S05/S06和WT-T02/T10继续负责策略状态、账本、执行及通道事实，见[能力目录](../development/wondertrader-capabilities.md)。当前缺口属于自有Host的通信存储配置：[QST-R18](../specs/qmt-shm-trading.md#qst-r18-同一通信-owner-的回报保存与源确认)和[ADR-0009](../architecture/adr/0009-trade-command-communication-owner.md)的单一owner、SQLite事务及文件租约继续复用。本文不新增金融账本。

## 实施合同

| ID | 可观察要求 |
|---|---|
| TES-C1 | 输入为原Journal路径、原持久事件身份SHA及显式新容量。账户、路由、交易绑定、profile、全部金融事实和原金融目录保持；先核原身份再执行。 |
| TES-C2 | 首个能力只允许增加max_streams和所需max_bytes；max_events、max_page_bytes保持。全部数值复用现有validate_trade_event_storage校验。缺省构造继续严格比较身份，不静默扩容。 |
| TES-C3 | 维护owner先取得原Journal的进程独占文件租约；活动Host持有租约时明确拒绝。维护期间没有运输、域worker、SDK或WT运行。复用原表/字段/身份/原文验证器，验证阶段保留全部原命令阶段。普通启动时的命令恢复不得作为维护的隐式副作用。 |
| TES-C4 | 旧身份比较和新身份写入在原同一SQLite事务内完成，写集合只包含trade_event_identity的容量身份。全部其他行、原文、关联及前沿保持。提交后以有界结果记录原/新身份SHA和事实保持核验；结果记录不承担金融事实所有权。 |
| TES-C5 | 全程沿同一绝对截止。提交结果未知时，只核查原库当前身份及原事实；读到旧身份表示未生效，读到精确新身份表示已生效，其他状态保持失败。保留失败原件，不回写旧数据库快照，不删除Journal或事件，不复用旧Source session伪装新来源。 |
| TES-C6 | 扩展后的库用新显式配置重开；旧容量配置继续身份拒绝。实际新Source获得独立会话后沿原认证/事件页及四查询推进。Native沿最新有效clean和原金融目录恢复，产生新的策略计算及真实正常关闭证明；零旧委托重发。 |

此合同保留有界存储和满额拒绝。容量值由实际候选的运行预算声明，后续满额仍需显式维护。新增能力只用于已停止owner的维护，在线热改容量退出首个实现范围。

## 维护接口与容量声明

交易专用模块trade_event_maintenance提供expand_product_event_storage(directory, *, expected_identity_sha256, event_storage, deadline, installed_agent=None, failed_owners=None)。directory沿原产品配对核验，函数只打开其原Journal；deadline为调用者首次固定的绝对monotonic秒，failed_owners复用构造/关闭未确认时的原单槽owner责任。结果版本qmt.trade-event-storage-expansion.v1，携带原/新事件身份SHA、原/新容量、其余各表行数/内容摘要、schema摘要及真实关闭事实；无原事件、账户或凭据正文。

维护实例继承原HostTradingJournal或RetainedTradingJournal，共用其文件租约、事务和全部验证。构造期事务在提交前核total_changes与schema；任何原命令恢复、旧表补列或原关联补写均回滚并拒绝本次维护。此入口适用于已完整初始化且本次验证无需变更事实的库；需先恢复原命令阶段的库继续由原恢复owner处理。维护阶段唯一允许的写入是同一原事务内以原身份比较后替换事件容量身份，其他表与schema前后摘要必须相同。

测试原两会话预算与正式声明分开登记。本轮SDK模型候选显式声明max_streams=16，覆盖已保留2会话和本轮最多8次来源重建，max_events/max_page_bytes/max_bytes保持原值并重新通过统一校验。正式运行仍消费部署方明确声明的容量，不从此测试值推定生产预算，也不静默把原2会话扩大。

公开离线入口为python -I -B -m guanheng_qmt_shm.trade_event_maintenance，显式参数为--directory、--installed-agent、--expected-identity-sha256、--max-streams、--max-events、--max-bytes、--max-page-bytes、--timeout-seconds、--cleanup-seconds。两个预算均须在0.001..300秒内；操作截止在解析完显式参数后首次固定，后继清理只调用同一owner.close，不继续事务。无参数或--help只显示用法。

CLI输出qmt.trade-event-maintenance-cli.v1；正常及时完成返回0、ok/outcome_confirmed为true并携带原API收据。失败返回2、outcome_confirmed=false、maintenance_not_confirmed和物理owner是否关闭；不输出异常正文、账户、凭据或原事件。提交后超时可已经写入新身份，退出2不代表未生效；先核原/新身份再决定后续，重复原调用继续经过严格身份校验，不盲重写。容量扩展不改配对材料，集成者沿原配对工厂生成新容量材料。

## 实施与验收

1. 复用已冻结失败及原安装副本反馈环，先验证原容量拒绝、原空会话可用、全部106事件和原金融文件保持；该步骤已有证据。
2. 在交易专用Host模块实现单一维护接缝，先冻结输入/输出版本与原租约/验证/事务调用关系；共享文件由其owner合入。原live材料及原金融目录在隔离验证期间保持。
3. 用原Journal副本完成真实维护、旧配置拒绝、新配置重开、新Source空页和原四查询；核其余所有表逐行/原文不变，SDK0。覆盖持租约拒绝、错身份、非法缩容和提交前后失败。
4. 以最终源码SHA进行独立full审查，固定普通安装及维护入口。集成者核同配对材料和角色身份后再安排原SDK模型目录维护与恢复；不为本项修改WT核心或执行真实下撤单。
5. 从原金融目录最新正常证明继续，验证持仓/资金/订单一致、策略实际计算、零旧委托重发及完整正常关闭。原同次page/other异常缺少具体异常栈的边界继续保留，不以新通过覆盖旧失败。

维护后的回退使用理解新容量的冻结制品及同份新配置。已接纳新会话后继续保留全部事实，旧容量配置的拒绝行为构成明确回退限制；恢复旧数据库快照会丢失后继事实，退出回退方案。
