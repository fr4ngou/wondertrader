# 首账户查询到原生执行单元的资金接线

类型：模块B开发验证。状态：partial。规格：[STQ-P22](../specs/native-qmt-standard-trader.md#stq-p22-首账户查询与延后创建的股票执行单元accepted开发中)。WT框架多线程调查继续停止；本轮只核自有数据流、构建及业务结果，没有线程/栈/内存研究或WT核心修改。

## 根因与实现

自有宿主先完成账户四查询，首次策略目标随后创建原执行单元。原Local账户回调只通知当时已有单元，晚创建单元首笔缺少先前资金回调。固定旧库baseline-low-002实际available=1000元、价10.01、目标1000份，SDK替身仍收到1000份，原生断言失败；源/proxy无错误且完整关闭。

自有BrokerQueryAdapter复制最近完整查询的CNY原回调值，仍交原base推进；Local在目标/增量可能创建单元后重放该观察。原股票算法继续按可用资金及整手计算数量。query_first买入在创建提交组前核原资金观察已知、正数及名义金额；不足返回空OrderIDs/BlockedFunds=9，原委托及未知责任继续由插件持有。native旁路与卖出保持。

观察只由完整查询更新，空/缺CNY或断线转unknown，没有按委托、成交或策略权重扣减/分配资金。独审发现的有限负available观察误拒已删除，非正数只影响新买入。行情、账户和交易记录查看没有新增门槛；本项没有金融账本，也没有跨证券资金预留或完整费用资格。

## 固定输入与结果

根为`build/ms-funds-host-001`，全部账户/价格/SDK明确合成；原WinSHM、Host、插件、Adapter及执行算法实际运行。生产变化仅BrokerQueryContext.h/.cpp及自有StandardSubmission.h末尾枚举。原WT对象、TraderQMTStandard DLL及执行算法DLL保持。

| 原件 | 实际结果 | 范围 |
|---|---|---|
| adapted-low-001 | 中间Local观察实现：1000元首笔0，2500元后原股票算法买200；5查询、完整exit0 | 仅当时中间源码，最终观察owner已收敛到Adapter |
| generic-refresh-003 | 最终adapted-004库：1000元首笔0，20000元后原通用算法仅买1000；5查询、完整exit0 | 最终名义资金等待/恢复与通用兼容 |
| negative-001 | 同一最终库：available=-1仍Ready、首笔0；20000元后仅买1000；5查询、完整exit0 | 负观察保留，买入独立等待 |
| unknown-004 | 同一最终库：空资金来源沿原mapper失败；源查询4/成功SPI3、SDK0，明确失败、完整exit0 | 预期失败与回收；没有同实例Ready后恢复资格 |
| native-add-001 | 保留exe入口：原Factory/CTA/组合A600+B400净买1000一次；4查询、完整关闭 | 安装exe主链；没有Python公开CtaRuntime直接入口观察 |
| native-dll-001 | 安装公开CtaRuntime直接进入最终f3049cd1…DLL：原Factory/CTA/组合A600+B400净买1000一次；4查询、完整exit0 | 最终运行DLL共享主链；不授1.1.2规则或股票完整退出资格 |

最终成功实例均有driver及原生exit0、Job回收、双EOF/reader join、Host/源/HTTP/proxy关闭且源/proxy无错误。SDK返回后尚无券商订单观察的责任继续保留；未伪造成交或生成干净恢复证明。

## 保留失败与修正

low-002、zero-001、positive-001、sellable-zero-001、sellable-200-001业务report符合预期，进程随后0xC0000005，全部保持失败；分别观察到等待后200、首笔200、卖200或零提交。只记录退出与资源事实，未归因于WT或推进核心方案。

baseline-low-001初版QA的tick.code错误，002修正后才形成有效根因验证。unknown-001/002误按空源可Ready，旧QA只查pump非负而等到D；实际mapper要求资金恰一行，失败发生在onRspAccount前，之前将其归于nullable条件的解释撤回。unknown-003及时观察故障但QA误预期InvalidInput2，固定插件owner分类实际IoError10；005仅改QA后unknown-004验证。自有回调保留原SPI空指针语义，不能据此宣称修复了该源失败。

generic-refresh-001在并行QA源快照写入时被摘要检查拒绝，未启动native；后继顺序运行002及最终生产004的003各自保留。全部失败、源码阶段及限定资格随MATRIX/REVIEW/DELIVERY绑定。

## 同批运行体与后继

runtime-004/BUILD.json记录重编BrokerQueryContext、StandardExecutionHost及CtaProcess，重链接运行DLL与安装头消费。DLL SHA `f3049cd1be1b49b187539735184a28882d7256e6e52cddb68e00e8629360f6c3`，相较install-003仅变运行DLL、Broker静态库及两份公共头。未制作发行ZIP或生产切换。后继审查勘误：native-add的runtime_entry=false记录Python直接调用分支；原main→gh_cta_run及Ninja导入库接线表明，不能据该字段断言exe未调用DLL，更早“静态exe”的说法依据不足。旧报告原件保留，CORRECTION-002.json登记。独立native-dll-001沿普通安装公开Python API直接装载最终DLL，RESULT三个DLL/entry/load字段均true；callback-api-proof核两策略create/destroy=2、setters=2、active/failure=0，POSTFLIGHT核完整关闭。该案使用普通合成目标，不启用行情交错实验。

后继按[RR112](../specs/retained-resonance.md)接C唯一1.1.2核、A同基准前复权来源及[持仓接管初值](../migration/retained-strategy-takeover-proposal.md)，继续实时/回测和恢复。股票完整退出、跨证券资金/费用、异常原命令/跨根责任及统一安装继续。真实下撤单与生产变更均0，完整模块active。
