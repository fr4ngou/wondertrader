# 唯一1.1.2实时桥与实际关闭边界

类型：验证记录。结果：partial，当前股票完整关闭候选失败。关联NRT-R18、STQ-P24及B-04/05/06/07；模块B整体in-progress。环境为独占Windows隔离安装，原行情/历史Reader、CTA、执行工厂及真实算法，行情/日线/基础资料/券商数据均明确合成，真实券商调用0。

## 输入身份

| 输入 | 固定身份 |
|---|---|
| Python安装 | `build/ms-retained-cta-001/INSTALLATION-004.json`，SHA256 `bd04d831add688ba37d9ea62f1b224e82dd37c6008ea1d5c5179906ae10150c4`；29发行、4729条RECORD核对及pip check通过 |
| 自有原生构建 | `build/ms-retained-runtime-001/native-004/BUILD.json`，SHA256 `43de4701656c404ac416b29bd92401cf4cae1fe95759c51a3a57639c1b3f389c` |
| 当前Runtime | SHA256 `a902bcc989f9881e7eb9309beac176dfb0d38ef6e71415691859f89ea281283d` |
| 固定原执行工厂 | `WtExeFact.dll` SHA256 `8e0721f3c2d54621468a02fa6cf3a63640f7ec9218e7a2116bcfe8af5860a131`，本轮框架源码修改0 |
| Python薄桥 | execution_process `e7db10706913fb1dd7136c0f8ac0cf5d25761ef2aa6677e2cc343d8e0d71f3c2`；execution_strategy `f1d62a7c5523f85728bb1065d422f9052bd75b8ace5c6ca8e7f988405c379daf`；execution_configured `ccd20b2188e9cecabba46bf721cd31d32dff34e7f1f40bda07eaa20bbfed103a` |
| 自有关闭实现 | Standard.cpp `f5cfcfcb58daafbeb7771c62737a4f341dd90157592dd1a36f51032a3d99ebf9`；Standard.h `4718d2334cb2acbb0876df6e62dd0ae8bd3feb79dd36861e3d80b19d0e1ae8fe`；Session.cpp `16994177cb490e0dc74364d60a2394bcbc2aa4981d6a4a5f5889e13f38c393cc` |

Python安装消费C冻结Appa23的DELIVERY-003和唯一v1核，B只覆盖已分配的三个execution文件，保留C原共享`evaluate_retained`/`advance_retained`。未在此覆盖后重新授予整个App/HTTP/SPA资格。当前五包profile沿唯一1.1.2选择；旧configured/V2路径保留各自历史身份。

## 实现与实际业务链

R18沿原Broker观察读取实际数量/可卖；实际周期只保存已核周期来源等非金融元数据，数量、成本和绩效继续由WT及券商事实所有者维护。完整八目标、同一原上下文价格/日线、策略独立预算、原NSQ和原用户KV接入C唯一核。部分减仓保持实际周期起点，平仓移除周期，无法证明新开仓周期时等待。首次接管包的有效期只约束record_clean首次准入；resume_clean核同配置、原状态和新查询，不要求改写首代包。

现金ETF准入选择原StockMinImpact、scale=1、无分组/清仓覆盖、min_order=100及关闭未管理单自动撤销。原generic执行器默认getPosition读取可卖量，会把部分冻结场景的可卖100当总持仓参与目标差计算；该选型负例保留，当前profile在加载Runtime前拒绝。此限制只定义该实时profile。

P24修正自有宿主的完整关闭边界：停止新命令、等待inflight及插件join/drain、销毁Local/执行单元和Adapter，再释放其借用的上下文/行情依赖，随后生成clean。关闭异常不授予成功收据和干净恢复资格。该修正没有改变WT原交易算法、调度或保存内容。

## 运行与观察

原件根为`build/ms-retained-cta-001`，逐次输入摘要位于各案`*-input.json`，现场和关闭事实在各案POSTFLIGHT。驱动经`scripts/native.py::run`使用隐藏独占Job和单一截止；所有下述进程均已终态回收。

| 场景 | 实际结果 | 范围 |
|---|---|---|
| main-003/004 | 唯一1.1.2首代卖SH50 200，后继收敛；两代24查询、SDK替身1次、自然exit0 | generic旧profile；Python002/003及native002，不能替代当前股票候选 |
| sellable-001 | generic将可卖量参与总持仓差额，进入意外SDK调用，夹具明确失败 | 旧QA在断言后才记SDK列表，空数组不证明SDK0；现已提前记每次调用 |
| sellable-003 | SH50总200/可卖100，waiting_sellable，SDK0；两代12查询、自然exit0 | Python003/native002；同一冻结可卖量跨重启，未验证次日解冻 |
| stock-main-003 | 股票卖200/收敛后关闭异常；debug捕获c0005，原失败现场保留 | 旧候选在最终析构前曾输出成功收据，暴露自有关闭边界错误 |
| p24-unclean-001 | 实际13查询、卖200一次、自然exit0，产生clean | 驱动原先预期关闭失败，其断言失败；实际结果是成功，不能充作异常负例 |
| stock-main-004 | Python004/native003，24查询、卖200一次、同根两代、自然exit0、两代clean | 旧Session顺序的一次完整成功；当前故障仍可再现 |
| stock-main-005 | Python004/native004，13查询、卖200一次并收敛；关闭c0005/exit2，无clean、无closed | 当前股票完整关闭失败；外部debug附加/退出/回收成功 |
| sellable-004 | Python004/native004，6查询、SDK0，关闭exit2，无clean/closed | 未附异常调试器，具体原因unknown |
| p24-unclean-003 | 复制stock005实际5份金融文件，resume_clean在Ready前拒绝；4查询、SDK0、失败closed；原件及副本共10项SHA不变 | 当前P24缺clean准入负例；没有恢复交易资格 |

当前最后三案Host关闭、Host资源关闭、Source资源关闭、Source关闭确认、HTTP server join、proxy join六项均为true，forced/pending均为false。外层测试失败与原生退出原因分别保存。`p24-unclean-002`因临时驱动多传一个CLI参数在解析阶段退出2，未进入原生链；修正驱动的003才是上述有效负例。

股票组件的独立引用计数原件在`build/ms-stock-reference-001/RESULT.json`。加载相同原工厂，在仅用于观察的额外引用下，计数2→init后2→销毁后1，正常配对应为2→3→2。原辅助函数对借用资料release一次，缓存初始化又retain，析构再release，少留一个引用。stock005的私有dump栈顶候选为`WtExeFact+0x1baff`，固定指令是商品资料release；寄存器显示执行堆地址失败。候选栈与独立计数实验相互对应，未把栈扫描当成完整栈展开，也未推断所有WT运行版本均有相同影响。

运行中`0xab620`的首次自然异常、两次受控条目搬移实验及HTTP夹具容量故障见[单一故障记录](../incidents/2026-10-29-retained-cta-access-violation.md)，与本段关闭现场分开。QA页预算已收敛到既有请求/字节上限；二代增加实际后继闭合分钟。没有冻结行情或新增串行事件调度。

## 审查、验收和限制

独立审查完成R18/P24 full及最终Session顺序、实际异常副本的delta，当前无新增P1/P2。审查逐案核对实际安装身份，明确当前股票候选仍失败；未运行程序或修改开发文件。最终冻结清单在同根`R18-P24-DELIVERY-001.json`，报告绑定该清单。

| 要求 | 当前结论 |
|---|---|
| R18-C1 | 真实算法/原CTA/完整八目标/卖出和后继收敛已运行；最终候选完整退出及两代仍gap |
| R18-C2 | 完整相同输入BT/RT比较仍gap；旧values替身只证明各自固定源码的值与周期状态 |
| R18-C3 | 真实新开仓周期来源、动态真实分析窗口、真实预算/接管输入仍gap；等待状态已实现 |
| R18-C4 | 自有安装与发行身份已核；开发清单及独立审查单列，当前失败候选无稳定运行资格 |
| P24-C1 | 当前股票异常前无clean/无成功closed、物理回收已验；正常完整退出仍gap |
| P24-C2 | 实际异常金融副本缺clean拒绝、零SDK、源/副本不变已验 |
| P24-C3 | 旧native003有两代正例；native004正常/重复close及兼容资格仍gap |

编译及安装头消费通过，当前语法/文档检查的最终退出码记录在冻结清单。原框架文件保持原状；[既有商品引用提案](../migration/native-stock-metadata-ownership-proposal.md)仍待审批，当前只补现场依据。运行中故障首次同次根因与股票关闭修复保持开放，模块B及生产均未完成。
