# 未知提交的券商证据处置与原状态恢复

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B跨owner恢复方案。状态：proposed / implementation-not-started。范围：已在原Host Journal保存的SDK未知调用，保留原命令和本系统启用后的WT状态。新增WT核心行为、真实交易和生产切换均不在本方案实施范围内。

当前修订补齐两个设计前置：旧实例最终硬故障资格、原新成交到策略周期/KV的应用与保存前沿。原提案字节及当时反馈绑定保存在固定快照（外部历史/待归仓路径：`../../build/ms-unknown-positive-proof-cold-002/SNAPSHOTS/proposal-v1.md`）；本文维护唯一当前设计，开发与正向Native恢复验证继续待完成。

## 目标与实际缺口

当前查询能取得完整SDK token和订单关联证据，Journal、Host runtime/control、Source service/kernel及Standard仍按原合同锁存unknown；Native恢复另要求原clean证明。只清一个布尔值无法建立完整恢复。

实际反馈环（外部历史/待归仓路径：`../../build/ms-unknown-positive-proof-baseline-004/RESULT.json`）已在固定A003/已安装WT环境通过真实HMAC HTTP和WinSHM复现：SDK替身先建立100股全成订单及成交，再抛出异常；当次订单查询建立原命令的v2关联，原调用仍为unknown，新insert保持关闭。一次SDK进入、一次交易POST、八查询、全部资源回收；本例未启动Native，当前恢复oracle为false。该例用于推动恢复主链，现有防重复行为保持正确。

复用[WT-T01/T02/T09、WT-S01/S05/S06](../development/wondertrader-capabilities.md)的原查询、订单对象、加载、策略KV和账本；[ADR-0009](../architecture/adr/0009-trade-command-communication-owner.md)的唯一通信Journal、R21真实ORDER关联及[UC](../specs/qmt-unknown-cancel.md)的独立unknown/hard-fault事实继续使用。新增内容限于通信责任处置证明及自有恢复准入，不分摊策略成交、不新增金融账本、不导入启用前交易历史。

## 关键决定

1. **原调用事实保持。** 原UUID、命令字节、SDK unknown结果及摘要保持；后继券商观察不能把SDK调用阶段改为sdk_returned，也不触发原命令重新POST。
2. **区分历史未知与未处置责任。** 在同一Journal owner/事务内保存有限的处置证明，引用现有订单查询request_id、row_index及result SHA。证明解释“该未知调用的交易责任已由券商事实核清”，不替代原结果或派生资金/持仓。
3. **以正向终态证据完成首个恢复profile。** insert匹配原完整token、账户、证券、方向、数量/价格及真实broker ID；cancel同时绑定原insert及目标broker ID。需要有资格的终态订单证据；无记录、活动订单、来源/身份冲突、字段缺失或未知状态均保留阻断。仅有has_broker_proof不能替代终态判定。
4. **状态规则保持单一来源。** 现有AccountMapping的SDK状态到WT语义是依据；实现前将证明所需终态定义与该映射收敛为共用的固定定义，并核原映射逐位行为。Host不另写一套独立金融归约。
5. **复用关闭与工厂重建，并保留旧硬故障责任。** 旧实例的OR锁存保持；完成排空、退出和资源回收后，按同一Journal/账户配置重建Host、Source与Standard。当前各层hard_fault含实例内状态，新实例的初始false无法说明旧实例健康。首个profile必须取得原各owner最终排空后的明确no-hard-fault资格，绑定原代、首次截止和真实关闭结果；源端资格沿原认证通信交给Host Journal保存，QMT源端继续不写文件。缺任一旧owner证明、旧实例异常退出或硬故障仍未核清时保留阻断。Source service/kernel无需增加通用清除API，旧Runtime/control不在运行中被强制清零。
6. **Native恢复单独证明应用与保存前沿。** 由自有Native/监督者保留实际退出、最终回调健康、独立故障类别、同配置/安装及原文件身份，并证明原命令/成交身份→Native实际应用→原WT金融文件保存→对应策略周期/NSQ用户KV保存的衔接。文件摘要有效只证明文件身份，旧的完整快照仍可能漏掉后续成交。缺失、损坏、强杀、健康不明或前沿不相容时拒绝恢复。原clean模式和默认行为保持，通信处置不生成clean。
7. **正向恢复包含新成交来源续接。** 以版本化recovered-managed-origin关联原UUID、原本地受理OrderID、原上下文/运行epoch及原ORDER+DEAL查询引用；只覆盖新系统启用后产生的原命令。query继续标为query，原first_live与原提交序号保持事实。重建前先核已应用及已保存前沿并去重，沿原上下文恢复对应真实新买入周期/NSQ；缺原受理身份或上下文归属时拒绝猜测。需要补金融状态时，必须通过原WT/SPI或公开加载接缝证明恰一次应用，现有接口能力须先核实；自有层不计算替代资金/持仓账。

## 已定位的触发链与正向恢复要求

`BrokerQueryContext.cpp`中的原submit先调用gate和原Local执行器，再remember_submission；Standard.orderInsert本身只入队。当前登记基于本地受理，在正常owner后续SPI消费前完成；worker可并发开始POST，现有RAM登记不提供严格的POST前持久证明。该origin在进程重建后消失。

unknown使Standard关闭写准入，`StandardExecutionHost::pump`沿原Plugin fault使Session停止。`execution_configured._opening_cycle`要求first_live及原提交序号边界；当前查询保持query，初始化仅恢复已保存KV。若原新买入已成交而旧实例尚未保存周期，新实例会waiting_actual_cycle。ORDER终态及健康字段均无法补足这条身份与保存链。

因此，本方案的正向验收必须实际完成成交后异常的新买入用例及原周期恢复。仅接收旧金融/KV恰好完整的受控失败profile、或只验证缺证拒绝，均不足以完成UDR-C3。当前反馈例没有启动Native，正向Native失败恢复证据仍缺；本节记录所需开发能力。

## 数据与接口边界

| 内容 | 所有者与约束 |
|---|---|
| 原unknown记录及已存在ORDER查询 | 原Host Journal；原文及原阶段保持 |
| 责任处置证明 | 同一Journal事务；每原命令有限一项有效证明，保存来源引用、策略定义版本及摘要，不保存第二份金融数量或策略分配 |
| 终态语义 | 现有SDK账户映射边界；当前模式只接有定义的终态，状态48及活动/未知状态不作为恢复证明 |
| 处置发布 | Host自行核保存的查询和原关联；客户端只引用原命令/查询身份，不提交“已确认”“已终态”等人工布尔资格 |
| 新旧状态协议 | 显式版本/能力选择，保留历史unknown和当前未处置责任；旧消费者拒绝不理解的新模式，默认v2行为保持 |
| 来源与认证换代 | 原派发B、观察B、当前B分别保存；终态事实和当前连接就绪分别核实，不改写旧观察来源 |
| 旧owner最终安全资格 | 原Host/Source/Standard各自最终排空后提供，认证源端结果交原Journal保存；与重建实例的初始健康区分 |
| 原受理与恢复来源身份 | 原本地OrderID/上下文/运行epoch由原受理链提供；Journal关联原命令及查询证据，Native保存消费前沿引用，不新增金融分摊账 |
| Native失败停止材料 | 自有运行体和监督者；包含实际应用/金融保存/策略KV前沿，与成功closed/clean区分 |
| 策略状态/周期 | 原WT文件、原用户KV及原唯一核；新系统基准和记录保持，不以重新起步消除旧责任 |

证明的容量须纳入原max_trade_bytes和原命令上限，所有I/O沿同一原截止；容量不足保留原记录和围栏。显式模式的新增表/字段、回退拒绝、Host/Common/Native能力协商及所需预算在实施契约中冻结后再接生产者和消费者。

Native受控失败材料须能区分unknown与硬故障并确认最终回调健康；现有V1聚合unsafe和失败prepared尚不足以单独授此资格。新增可选诊断能力或版本须保持旧ABI路径。恢复来源只续接原受理身份和本系统新成交，原金融/策略应用前沿缺失、部分副作用不可判别或成交上下文存在歧义时保持拒绝。首个正向用例采用用户已确认的唯一1.1.2上下文；多个上下文仍须各有原生身份依据，账户净额不能推定策略成交分配。

## 实施顺序

1. 沿现有正向反馈环固定命令、查询、原结果与实际关闭事实，补齐完整的证据校验输入。
2. 冻结Host处置记录/版本/预算和终态定义，先完成同Journal的正向证明、缺证保持及原记录不变主路径；普通读和默认旧模式保持。
3. 冻结原各owner最终安全资格和本地受理身份的生产/保存合同；通过原工厂实际关闭/重建Host与Source，新实例核原资格及有效阻断，原SDK POST零增量。
4. 冻结自有Native失败材料、应用/保存前沿及recovered-managed-origin能力，接同配置/安装/金融根与原KV；实际跑通成交后异常的新买入、原周期续接和下一次正式1.1.2计算，再集中补坏例。
5. 同批普通和搬迁安装、独立审查及精确交接；原包、失败原件和默认路径保持。真实写及生产切换另按明确授权执行。

## 验证标准

| ID | 可观察结果 |
|---|---|
| UDR-C1 | SDK先产生成交效果再抛错，查询精确关联原终态订单；原UUID/body/result保持，处置证明指向真实原查询；缺证和活动订单保持阻断 |
| UDR-C2 | 原实例最终排空及各owner无硬故障资格有据可核，同Journal/账户的新Host/Source/Standard恢复有效准入；历史unknown仍可读、无原POST/SDK重复；原硬故障或缺旧owner资格保持阻断 |
| UDR-C3 | 正式唯一1.1.2实际新买入先成交再异常，原UUID/受理OrderID/ORDER+DEAL证据续接原周期及应用/金融/NSQ-KV保存前沿；恢复原基准并完成后继计算，恢复额外SDK0，后继新决策仅产生真实差额 |
| UDR-C4 | 错token/账户/证券/方向/数量/来源、状态回退、缺/多字段、预算及截止失败不改原责任；中断发布/关闭/重建可按原身份核查 |
| UDR-C5 | 无失败停止材料、健康不明、强杀、坏/缺金融状态或旧协议不授恢复，不重置本系统记录，不补造clean |
| UDR-C6 | 普通/搬迁最终角色和实际Native主链、制品/源码SHA、完整资源回收与独立审查分别成立；整个B资格继续按总方案逐项判断 |
| UDR-C7 | query/live来源及原序号保持真实；旧本地origin丢失、上下文歧义、漏消费或漏保存、重复证明和部分应用窗口均不产生重复记账/周期，不以重置库存或推定归属通过 |

该方案尚未修改生产源或解除任何实际围栏。A负责Journal/Host及来源装配合同，B负责Standard/Common消费与Native恢复，C按最终版本只读呈现；原跨owner接口（外部历史/待归仓路径：`../../build/ms-unknown-recovery-owner-interface-001/INTERFACE-001.json`）保留定位证据。
