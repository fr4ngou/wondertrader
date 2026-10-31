# 存量持仓接管与原状态两代恢复

类型：模块B开发证据。状态：partial。要求：[STQ-P23](../specs/native-qmt-standard-trader.md#stq-p23-唯一策略首次存量持仓接管accepted开发中)、[RR112](../specs/retained-resonance.md)。原件位于`build/ms-retained-takeover-002`。账户、开仓时间、价格及目标均明确合成；真实账户、配置和生产保持。

## 正确接线

自有Session取得原输出根租约、核fresh金融目录为空并完成原admit后，执行一次prepare。自有产品入口核接管输入身份、有效期、同次原环境交易日/本地分钟及原券商表全部非零数量/可卖；原恢复观察须无活动/未知责任。代码沿ExecutionEnvironment既有准入再调用原CodeHelper。零量条目忽略，额外有仓证券拒绝。

输入转换成原stradata、portfolio和userdata格式，随后沿原WT load_data/load_datas/load_userdata读取。首次显式takeover-mark以接管价起算绩效，原累计损益/费用为0；实际周期时间和原用户变量同时加载。元数据保留输入身份与初值，后续持仓/绩效仍由WT维护。prepare失败保留原件；resume_clean消费原关闭证明并跳过prepare，首次接管记录保持。

生产变更只在自有CtaExecutionSession.h/.cpp、StandardExecutionHost.h/.cpp及CtaProcess.cpp。positions()同owner复制原Adapter枚举值；没有新增金融归约、持仓/成本账或历史成交导入。WT框架调查保持停止，本轮未改上游核心。

## 实际结果

当前native-003为修正候选。native-002同批编译Session/Host/Runtime/main和安装头，003复用同身份库、重编Runtime并重链exe；BUILD记录完整冻结源及实际链接输入。

| 原件 | 结果 | 资格 |
|---|---|---|
| hold-resume-002 | 首次读回1000/valid1000、202610201000及原用户KV；同根两代12查询、SDK0、两代clean/自然关闭；接管记录原SHA不变 | 最终原加载及正常恢复主链 |
| reduce-002 | 同候选1000→目标800，仅卖200；后继券商替身查询800、7查询及正常关闭 | 合成目标差额执行 |
| extra-zero-001 | 额外零仓证券存在，保持1000、SDK0、6查询和完整关闭 | 零仓集合边界 |
| invalid-code/old-date/future-opening/extra-held/mismatch/expired/missing-cycle/sellable-mismatch/existing-state各001 | 各4查询、SDK0、明确拒绝及正常物理回收；原金融目录未写，已有preserve.json原字节保持 | 指定拒绝边界 |

公开安装CtaRuntime及ManagedStrategy原Factory实际执行；新exe另验原A600+B400通用主链兼容。独立审查的符号容量和日期两项P2已在自有边界修正，原触发条件纳入上述拒绝。最终MATRIX/REVIEW/DELIVERY分别绑定结果及范围。

## 保留失败与限制

native-001初版构建driver误用exe Ninja键分隔，Runtime已编译后driver停止；后继只补exe/头及收据。hold-001在启动前缺QA parsers目录；hold-002继承的GapFixture只接受初始化四查询加O，关闭所需P被QA拒绝；两者均保留失败。hold-003/reduce-001是修正前生产源码的早期运行观察。最终hold-resume-001沿新增日期校验拒绝QA误用的下一行情日；002改为当次账户环境日后才取得最终两代结果。该过程没有更改WT日期/调度逻辑。

当前仅验证单证券合成目标与现有加载/执行链，尚未消费C唯一1.1.2数学核，也未授真实前复权、当前实际周期、实际预算/起算价或完整股票/T+1资格。多证券接管、未知责任和准备中途文件写失败仍需完整验收。A通知新实源limits.v2需新Parser，旧包不重复实源。下一主线继续C纯核、当前周期/退出状态与原生数量及真实历史/回测接线，完整模块active。
