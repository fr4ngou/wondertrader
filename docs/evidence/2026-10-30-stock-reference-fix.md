# 显式股票引用修正版的实施与隔离主链

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B开发验证。日期：2026-10-30。状态：in-progress。要求沿[SCMR方案](../migration/native-stock-metadata-ownership-proposal.md)、[CORE-011登记](../maintenance/upstream-overrides.md#core-011显式股票执行单元借用引用配对)及[模块B](../migration/module-b-delivery.md)。显式修正版的构建、业务矩阵及搬迁主链已验，最终独审及制品正在收口；完整模块B保持in-progress。后继[限定交付封存](2026-10-30-stock-reference-delivery.md)已完成两报告和ZIP核验，本文保留封包时实施过程及失败边界。

## 批准、根因与实现

用户原始回复为“批准这3个框架文件，按配置选择修正版”。本模块直接核原根会话userMessage，保存APPROVAL-001（外部历史/待归仓路径：`../../build/ms-stock-reference-fix-001/APPROVAL-001.json`）。批准限StockMinImpact.h/.cpp、WtExeFact.cpp及方案配套两处自有准入、开发与隔离验证。真实下撤单、生产切换及其他框架修改保持原边界。

根因为get_minOrderQty临时借用基础资料却release，消耗原init为缓存保留的引用；正式同次栈和原两单元红例沿方案保留。本次按既有工厂name选择：WtExeFact.WtStockMinImpactBorrowedExeUnit使用同一算法和缓存init/destructor配对，临时借用结束时保持owner引用；原名仍选原行为。Host在账户API初始化前检查实际工厂能力，唯一1.1.2桥接受精确的两种工厂名。新增金融账本、策略数量或订单分摊算法为0。

APPLIED-001（外部历史/待归仓路径：`../../build/ms-stock-reference-fix-001/APPLIED-001.json`）核五个当前文件与已审004候选的规范化内容一致，保留原换行格式；修改前字节及实际应用字节分别冻结。工作树其他框架差异保持；构建沿R23固定WT源叠加获批三文件，自有C++和WT运行源码取当前快照，保留公共通信/NAP及B的R25/R26功能。旧冻结源没有整体覆盖公共工作树。

## 实际构建与主链

原件根为`build/ms-stock-reference-fix-001`。native001在解析Ninja的E$盘符时退出，编译/链接子进程0；native002修正解析后同批编译30个对象、36次编译/归档/链接调用，全部正常回收。两个直接包含StockMinImpact头的TU和整个八单元工厂均重编，自有Host、运行体、标准Trader及依赖归档同批处理。原WtCore静态库保持d76d40f5a78bdc942e0e1489215832c02ef9a48259d209ee67699029adabf3cc。新工厂SHA为15541035b40757ce6938eb8eaf4179dcf1f699df1aa9a22961a0d85744e90853；完整源码/对象/链接及24文件后继安装身份沿native002 BUILD（外部历史/待归仓路径：`../../build/ms-stock-reference-fix-001/native-002/BUILD.json`）。

python001从当前WT运行源码构建独占开发wheel，保留A当前版本标识，六发行736条带摘要RECORD全部匹配、单链接复制，无观衡/Web包。该wheel按当前源码版本及新SHA绑定，供隔离开发；统一候选的最终版本及公共登记由A收口。

| 原件 | 实际结果 |
|---|---|
| main001 | 正式WRI、唯一1.1.2卖200后P/资金观察更新并收敛；正常停止，同根第二代恢复且SDK不增加。两代成功closed/clean及内外资源回收成立；24查询/SDK1，外层exit0 |
| main002 | 原200/可卖100保持waiting_sellable，同根两代正常；第三代追加KV空白后在CTA摘要门拒绝，恢复原件，原clean/consumed保持。16查询/SDK0；WRI启动器OS2、WT运行进程faulted，执行子进程有CTA failure/prepared，其独立OS码未归档；整个QA外层OS0 |
| main003 | 按金额费用卖200×90×0.0002=3.60；原WT费用、flag0、NAV、现金及源账户观察按原R25核算一致，正常关闭。13查询/SDK1，外层exit0 |
| modes001 | 原工厂原名与新工厂原名均2→2→1，显式修正版2→3→2；两修正版单元共享基础资料1→2→3→2→1后释放owner，无访问异常。未init能力探针无基础资料读取，SDK0 |
| admission002 | 9案含同配置有效原名的HTTP正对照，以及8个非法/旧DLL拒绝。非法项及旧DLL+修正版名在trader阶段失败、HTTP0；原名正对照确实进入HTTP后由503终止。所有状态根没有金融文件、无成功ready/closed/clean，SDK0及完整回收 |

admission001的旧DLL案仅因安装清单摘要未更新而在configuration阶段失败，未授工厂能力拒绝资格。admission002复用原write_installation_manifest登记实际旧DLL后，才在trader阶段验证能力拒绝；其余前件保留。

## 后继边界与交接

正式唯一策略使用原1.1.2；两策略订单矩阵使用原固定目标QA，范围分别登记。结果汇总为MATRIX-002（外部历史/待归仓路径：`../../build/ms-stock-reference-fix-001/MATRIX-002.json`）。

| 后继原件 | 验证结果及范围 |
|---|---|
| order-partial004、filled-late001、full-cancel001、cancel-refused001 | 部成撤余/全撤续单/撤单拒绝后原单成交/已成迟到及同成交重放，均继续到A800+B400，最终账户1200，后继实际只补买200；回报ACK、execution closed.v2 exit0及运输回收通过。单次矩阵没有clean，不授状态恢复资格 |
| order-insert-rejected004 | 原股票废单续单按10.02提交，源订单保存实际限价；独立核SDK、每次委托查询和委托回报限价一致，成交可按10.01改善，最终仍只续1000及后继200。实际资格以004原件为准 |
| order-resume001 | 成交、迟到回报及后继200后，原Host/Journal及金融根两代恢复；原clean/consumed和两代closed.v2身份/SHA匹配，SDK零增量 |
| portfolio-exit001、net001、pending002、partial002 | A退出只卖600保B400；相向净额0无SDK；未成400及成交500/未成500继续沿原订单扣减，SDK不重复。pending停止报告recovery_drain且无成功closed/clean，其余单次正常关闭 |
| zero-sellable001 | 账户1000、可卖0、策略目标400；实际SDK0、原理论目标保持、正常关闭。与main002可卖100的NSQ等待分别证明执行器及正式桥边界 |
| price-modes004 | 同样12个数量/价格输入分别运行固定原工厂、新工厂原名及适配名：买入取整、可卖截断、零可卖、未成抵扣、最优/对手价、碎股及废单后上移一跳完全一致；区分STK与ETF原商品规则。Context替身SDK0，范围为执行单元公开接口 |
| volume-fee002 | 原WT按量费用4元，P&L=-4、NAV119996、cash99996，与源账户费用/可用一致；13查询/SDK1、正常关闭。main003金额费用3.60保留 |
| unknown001 | 唯一策略卖200入口实际进入SDK替身后异常，原命令unknown/body/result SHA保持；原Host存续、同根第二代CTA拒绝，SDK及POST零增量、三金融原件保持；两代无成功closed/clean。WRI启动器OS2及外层QA OS0分列，外部资源全部回收 |
| relocated001、relocated-main001 | 全新E盘根离线复制安装同6wheel、736 RECORD及24原生文件；实际WRI CLI、site、解释器及native输入全指新根。两代24查询/SDK1，恢复零SDK增量、两代execution closed.v2 exit0及clean成立 |

T+1会话解冻、保存和新进程加载复用[R26-C4](2026-10-30-native-t1-session-recovery.md)：相同原WtCore SHA保持，本次只修改三个工厂/单元文件；正式WRI跨日日期/恢复身份及次日来源刷新仍列为模块缺口。完整400期BT/RT比较、未知责任解除和统一候选版本继续推进。新增逐策略成交分摊或金融账本为0。

## 失败原件及修正范围

order-partial001在运输QA使用纯WT解释器时缺uvicorn，未创建交易运行；后继运输QA留在外部解释器，运行模块来自独立WT安装。partial002的第二次撤原单触发通用夹具“一次撤单”断言，Source将其记unknown；股票模式现逐次记录同原单撤单，对已终态/已拒绝单返回明确false，不改金融状态。partial003的私有日历输入未形成调度；后继恢复原下一工作日合成行情。这些失败未发生所定位的商品release访问异常。

insert-rejected001错误固定续单价格10.01，原算法实际10.02，Source SDK断言抛错；002修正价格后业务通过，但源委托查询/回报还沿旧10.01，独审P2后由唯一源订单记录保存实际限价。003在初始化首个读取排队超时，查询/SDK0，trader失败且无成功ready/closed/clean；004显式选择5秒来源排队、8秒HTTP及30秒原请求总预算，执行超时仍1秒。各编号原件保留，不把前件计入完整订单事实一致资格。早期wrapper未保存完整自身快照，其资格绑定实际执行的私有QA文件、QA-SOURCES和原run.log中的子命令；后继order-resume001起逐案保存DRIVER及摘要，当前wrapper字节只授对应后继。

volume-fee001使用当日固定10:00合成行情，未形成所需首个调度、4查询/SDK0；实际运行状态stop_timeout/forced/pending，WRI启动器OS2，外层Job及运输回收完整，缺execution closed.v2/clean。002恢复原下一工作日合成行情，实际来源时间和决策截止保留。合成原生时钟与真实来源时间分别标识，未授历史首次可用或正式跨日运行资格。

price-modes001/002把ETF商品的最小数量预期套成STK，003又把原round规则当成floor；004分别按原商品和取整规则核三个实际工厂路径。pending001仍读取旧closed.json失败，原件已有recovery_drain/prepared及OS1；当前QA按父监督者的成功最终证明协议，精确读取失败prepared并核成功closed/clean缺失，pending002通过。

## 审查、安装及回退

最终两轴报告：执行/标准（外部历史/待归仓路径：`../../build/ms-stock-reference-fix-001/SCMR-REVIEW-EXECUTION-001.json`）、规格/关闭（外部历史/待归仓路径：`../../build/ms-stock-reference-fix-001/SCMR-REVIEW-PROTOCOL-001.json`）。准确源码、制品与运行绑定以新根交付收据及两报告为准，报告生成前保持审查进行中。三文件集中覆盖及实际原件应用核对见覆盖说明（外部历史/待归仓路径：`../../integrations/wondertrader_stock_reference/README.md`）与PATCH-CHECK（外部历史/待归仓路径：`../../build/ms-stock-reference-fix-001/PATCH-CHECK-001.json`）。

本轮全部新增项目运行、缓存、临时文件和制品在E盘。真实券商交易0，现有采集和QMT实例保持。原算法路径的已知引用故障仍存在，回退按原完整制品及原配置恢复行为，稳定退出资格单列；clean的安装摘要会阻断跨制品直接恢复，后继状态及未决命令不能用旧状态或空根替换。完整SCMR及模块B资格在剩余验证、独审与统一候选收口后逐项登记。
