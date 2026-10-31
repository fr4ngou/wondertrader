# 券商订单同步到WT原表及执行线程主路径

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发隔离证据。日期：2026-10-27。状态：限定主路径通过，完整迁移、恢复与发布继续。对应[STQ-P12/P13](../specs/native-qmt-standard-trader.md)、[已批准两文件方案](../migration/native-order-query-sync-proposal.md)。

## 根因与实现

此前自有BrokerQueryContext后续ORDER查询只替换独立rows_投影，查询可见订单与原TraderAdapter._orders分离；[旧缺口证据](2026-10-27-qmt-native-order-cache-gap.md)已实际复现查询1笔、原表0笔及原cancel返回false。用户明确批准仅修改TraderAdapter.h/.cpp后，完整ORDER查询在query_first下更新原订单表、原未成交量与订单统计。自有独立订单数组及其数量求和已移除。缺省/native保留原路径，原cancel/doCancel正文逐字相同；配置在初始化冻结并依赖position_by_query。

订单统计按完整查询刷新，成交统计和原频率缓存继续原职责。查询余量不再由迟到成交通知递减；回报继续原通知，并安排账户、订单和持仓查询。WT原通道身份关联沿既有EntrustID/UserTag/OrderID，外部单不伪造localid。未知命令责任留原Standard，空查询不能解读为确定未提交。

自有OwnerExecCommand通过原IExecCommand/WtExecuterMgr接缝交接目标与行情，生产线程复制纯值，owner按FIFO调用原Local/原MinImpact。目标执行器stub由owner显式配置，桥自身的引擎_stub不透传。组件不创建线程、不保存跨线程WT对象，不复制原算法。

## 构建身份与范围

编译使用固定上游08b230dd05facf6d650d949bfe51054115a2ecb1，叠加此前批准的查询持仓两文件及本次批准订单模式，组成见sg-003（外部历史/待归仓路径：`../../build/sg-003/COMPOSITION.json`）。343份固定源码与251份自有冻结输入逐项SHA核对。工作区其他冻结核心差异未编入。当前工作区另有9份自有文件与该输入不同，详见POSTFLIGHT.source_mismatches；本证据仅授予明确组成，不宣称完整工作区发布合格。运行Python夹具采用当前入口并记录SHA，实际GapFixture正文与冻结输入相同。

固定组成TraderAdapter.h SHA：52279d3ae1d1a3f012b389867c224d55c071dc8f40bf27d71ac83ccb018acc4a。
固定组成TraderAdapter.cpp SHA：77ac3b76b31a1d394cd1baba695362ee8e994eb866903dff09fcfd3665f9baa6。

最终制品：

| 制品 | SHA256 |
|---|---|
| TraderQMTStandard.dll | 3115b7cd8d414db2dd0b1f1e56ba3fdffe1030f2f11bd8050e9bfe0b6825c34c |
| GuanhengBrokerContextMain.exe | 908dca61b7873672e9fb21878e8649db0ac0380f221e8b005619d00d630a8616 |
| GuanhengExecutionOwnerMain.exe | 3397fc185e05e9a587808a43e2468c166e8961dc3bb65f9368411a0918c14b02 |
| 原WtExeFact.dll验证制品 | 12fb82ff9504d2d9c30db1477ae3abc60887578f1bc3bb4307e8c3f523f67d60 |

原WtExeFact八份源文件保持固定上游，CMake仅在验证目标编译并装载该原工厂。Owner桥及Standard可选产品入口已接自有CMake；验证程序不作为正式策略宿主发布。

## 实际结果

主链为正式Standard DLL→原TraderAdapter/Local→真实Host及Windows命名共享内存→独立SDK替身。所有账户和价格均为合成，真实券商调用为0。

| 验收 | 结果 |
|---|---|
| 默认算法行为的显式native对照 | 4轮空ORDER，实际SDK替身提交4次，P=100、U=0 |
| query_first空ORDER | 4轮仅提交1次，未知原身份保留，P=100、U=0 |
| query_first活动订单 | 4轮仅提交1次，完整查询余量80、原订单表1笔，P=100 |
| 全成后下一组 | 两次实际提交，后继券商P依次200、300 |
| 部成部撤后下一组 | 两次实际提交，后继券商P依次120、140 |
| 原执行管理器→跨线程桥→原MinImpact→Standard，空ORDER | 四轮目标和行情共8项交付，实际提交1次，P=100、U=0 |
| 同一原算法链，活动ORDER | 四轮8项交付，实际提交1次，P=100、U=80 |
| 原表同步、重复查询统计、迟到成交及原cancel | 四轮查询同一单，原表1笔；原订单总数门槛2仍允许；交付20股迟到成交后U仍80、P仍100；后继A/O/P查询共11次；原cancel返回true，SDK替身收到broker.1的撤单恰好1次 |
| 执行桥组件 | 生产线程与owner不同；原行情对象销毁后再交付，3项FIFO调用及owner元数据解析正确，正常关闭 |

八条正式运输场景和一条组件场景全部通过。原表撤单证明的是SDK替身入口已调用；实际柜台受理、最终撤销和取消终态后下一组的组合尚未验收。全成/部成部撤的后继P是另外两条明确合成场景，不能与撤单场景拼接为已经验证的完整闭环。

命令入口：[自有CMake](../../cmake/native/qmt_standard_product/CMakeLists.txt)、[主链runner](../../tests/integration/qmt_broker_context/run.py)、[原生探针](../../tests/integration/qmt_broker_context/main_probe.cpp)、[桥组件探针](../../tests/integration/qmt_broker_context/owner_bridge_probe.cpp)。参数为显式exe/dll/output/总截止；--execution-owner需要固定原工厂，--verify-order-cache只选择专用SDK替身撤单与迟到成交场景。普通GapFixture继续拒绝撤单。

## 原始记录与资源

POSTFLIGHT（外部历史/待归仓路径：`../../build/sp-005/POSTFLIGHT.json`）包含冻结输入、各终端根进程、结果与制品SHA。最终构建根38556退出0；最终五案根66924退出0；原算法两案根72260退出0；迟到成交/原撤单根70848退出0；组件根56188退出0。均在原总预算内完成，整树归零、EOF、reader join和资源关闭已确认，无强制回收。所有进程无可见控制台。本轮未启停QMT策略或操作真实账户。

各结果：五条正向链（外部历史/待归仓路径：`../../build/sp-005/basic-main-002/RESULT.json`）、两条原算法链（外部历史/待归仓路径：`../../build/sp-005/owner-main-001/RESULT.json`）、原表/迟到成交/撤单（外部历史/待归仓路径：`../../build/sp-005/cache-main-003/RESULT.json`）、组件（外部历史/待归仓路径：`../../build/sp-005/owner-component-001.json`）。

## 剩余范围与风险

完整CTA宿主的时钟、元数据、生命周期及正式执行装配继续；取消后终态至下一组的组合、完整查询/回报恢复、并发/容量异常与独立审查按主路径后顺序完成。原框架对象布局已变化，所有消费者必须使用本组成重编，禁止混用旧库。O/P仍是分别查询，不能承诺券商跨查询事务。该证据不授予生产发布或真实下撤单。

历史全库存导入、缓存尾部补齐、3只09:31原始OHLC差异核实与观衡独立发行保持原待办。历史交易记录不作为迁移前提。

文档导航检查：scripts/project.py check通过（根72248，exit0，资源已关闭）；该检查范围为本地链接/索引及技能清单，应用构建和运行资格按上文独立结果。
