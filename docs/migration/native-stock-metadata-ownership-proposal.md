# 股票执行单元商品引用方案

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：框架行为修改方案。状态：accepted / in-progress。2026-10-30用户在根会话对call_0557ef53ceb946c090d722fa649cdc41明确回复“批准这3个框架文件，按配置选择修正版”；本模块已核原始userMessage，授权记录为APPROVAL-001（外部历史/待归仓路径：`../../build/ms-stock-reference-fix-001/APPROVAL-001.json`）。批准范围为下述三框架文件及方案必需的两处自有准入、同批隔离重编和验证；真实下撤单、生产切换及其他框架改动保持原授权边界。当前范围仅正式1.1.2使用的StockMinImpact；旧两股票算法无配置删除release提案被本文取代，旧差异原件保持。遵循[配置分流规则](../development/upstream.md#框架行为的配置分流)。

## 背景、必要性与已知范围

当前实时交易已经能沿原WT执行器成交；正常停止时，还要销毁执行单元并释放其持有的基础资料。这里的“商品对象”是证券品种和交易制度等基础资料，持仓数量、资金、成交成本继续由原有模块拥有。

WT基础资料管理器保管商品对象，getCommodityInfo把对象借给调用者。StockMinImpact初始化时把该对象缓存起来，先retain一次，表示执行单元需要长期持有。随后计算最小委托数量的辅助函数又查询同一个对象，在没有为这次临时借用retain的情况下release一次，抵消了前面的长期持有。执行单元销毁时再release，就可能提前销毁基础资料管理器仍在使用的对象。

固定原WtExeFact二进制的独立计数实验已经覆盖原工厂init和destroy：带一个QA观察引用时，实测2→2→1，配对持有应为2→3→2；该实验没有行情、线程交错或委托。原件为RESULT（外部历史/待归仓路径：`../../build/ms-stock-reference-001/RESULT.json`）。它证明了这条具体引用配对错误，框架的多策略账本和调度继续照常复用。

2026-10-30同次后继已定位最终独立安装的rt-main002关闭失败：从原异常线程CONTEXT、dump内存及原PE函数表展开到自有CtaExecutionSession::close→StandardExecutionHost::close→原WtLocalExecuter/工厂→股票执行单元析构。在原商品成员释放的间接调用处触发c0005；原对象成员与异常寄存器逐字对应，Runtime与Factory完整SHA均匹配。原COFF函数节补证确认关键函数名，容器模板的等价折叠保持歧义。另以相同原工厂、两个单元及一个借用商品独立复现：create1→initA1→initB1，期望为3；deleteA返回，deleteB在同一个释放位点失败。原件见同位点证据（外部历史/待归仓路径：`../../build/ms-retained-close-trace-002/SAME-SITE-001.json`）及最小红例（外部历史/待归仓路径：`../../build/ms-stock-close-minimal-001/RESULT-001.json`）。正式进程中商品首次释放的完整引用历史尚未捕获，此结论限定于该次失效虚调用与独立确认的引用配对缺陷，不概括所有历史异常。

实际独立运行保留了两类结果：main005完成卖200、收敛和完整正常关闭；main007在完成同样只读交接后，关闭时捕获c0000005执行访问异常，同次转储栈slot0候选为原WtExeFact.dll+0x1baff。该位置与此前商品release机器码和独立引用缺额对应；转储扫描保持候选栈范围，没有冒称完整栈展开。main006在成交后提前exit2，缺少同次异常现场，其具体根因继续unknown。各次证据见[只读交接及后继故障](../evidence/2026-10-30-execution-readonly-handoff.md)。

交易期间对象可能仍占着原内存，所以能完成成交；停止时集中释放对象，错误引用配对的影响随之出现。某一轮正常退出保留为真实通过结果，稳定两代恢复仍须验证。此项必要性来自实际对象生命周期和故障，范围限定于商品引用。

## 先核公开接缝

复用原WT-T03执行器工厂及现有executer.policy.<rule>.name配置。get_minOrderQty是类内非虚辅助函数，外部插件无法只覆盖它；在自有Context里一律retain会与原init的retain叠加。按getter调用次数变换返回所有权、停止时跳过销毁或人工长期持有对象，都改变原责任配对。复制整个股票算法会产生第二份执行实现。通用MinImpact的有效仓位语义与本现金ETF要求的总量/可卖区分不同，当前profile按原验收拒绝替代。

最小方案保留同一个股票算法类，只由原工厂选择一个初始化后固定的商品引用模式，价格、数量、买卖、资金和回报代码共用。StockVWap及其他执行单元保持原样。

## 配置分流

| 选择 | 原配置键及值 | 行为 |
|---|---|---|
| 缺省新能力 | 保持原配置的name | 无新增开关，现有配置及原算法路径保持 |
| 显式原生 | `WtExeFact.WtStockMinImpactExeUnit` | 原构造及临时release行为保持 |
| 显式适配 | `WtExeFact.WtStockMinImpactBorrowedExeUnit` | 同类执行逻辑，临时查询保留借用引用；原缓存init retain/destructor release配对 |
| 非法或不支持 | 错类型、未知名称、适配名附加多余分段，或旧工厂不支持适配名 | 自有启动准入失败，尚未初始化账户插件或发委托 |

适配是原name字段的准确值，须由配置作者明确选择。选择在工厂创建单元时固定，运行期保持。只有新工厂能创建并以getName报告适配名称；自有StandardExecutionHost在账户插件初始化前统一核全部已选policy的实际工厂能力，只做不带Context、不调用init的构造/析构检查。未知名称或旧工厂缺适配名称在同一准入边界失败。原有分段解析兼容保持，适配名要求准确两段。旧DLL不能静默忽略选择。现行独立安装清单仍逐文件核实际DLL摘要，完整候选锁定同一源码、工厂、宿主与配置。

## 准确修改范围

2026-10-30 NRT-R25后继：004五文件原源和候选身份均保持，当时框架差异尚未应用或编译。对应BUILD-BASELINE-002（外部历史/待归仓路径：`../../build/ms-stock-reference-proposal-004/BUILD-BASELINE-002.json`）将运行源基线更新为R25 INSTALLATION-001/六发行/16个B模块，保留自有实时费用能力准入；001和下文003/R24基线均保持历史。实施组合时须采用该后继源及A当时公共变更，防止从旧冻结源遗漏R25修正。

2026-10-30 NRT-R24后继：自有实时输入接线已独立更新，当前五文件候选重新生成于`build/ms-stock-reference-proposal-004`。三框架文件差异SHA仍为cf46bc5bc136446dd9d840faa3e6460eeed536205c33d36f88cd39aaac7fe976，与003逐字一致；仅自有profile准入候选重放到最新源，保留持续窗口能力。当前PROPOSAL-004（外部历史/待归仓路径：`../../build/ms-stock-reference-proposal-004/PROPOSAL-004.json`）及构建基线（外部历史/待归仓路径：`../../build/ms-stock-reference-proposal-004/BUILD-BASELINE-001.json`）绑定R24普通六发行/16个B模块。当时004尚未批准、应用或编译，独立差异审查待登记；下文003原件及独审保留其冻结输入范围。后续实施以004及当时公共源的实际组合复核为准。

固定框架来源为`08b230dd05facf6d650d949bfe51054115a2ecb1`，当前实际原工厂SHA为`8e0721f3c2d54621468a02fa6cf3a63640f7ec9218e7a2116bcfe8af5860a131`。批准前003可审阅材料在`build/ms-stock-reference-proposal-003`，沿同一三框架文件方案重新绑定最新自有生产源，保留R22/R23及独立回测迁移；002保持冻结。只生成候选副本及差异，生产源码保持原字节。原Git文件字节保存在同根fixed-git-source.zip，PROPOSAL分别登记原Git blob和LF规范化的对照文本SHA；WtExeFact.cpp原件使用CRLF，对照文本的差别仅为换行。

| 文件 | 拟议变化 |
|---|---|
| `src/WtExeFact/WtStockMinImpactExeUnit.h` | 增加显式构造重载和一个私有固定选择；适配时临时借用不release |
| `src/WtExeFact/WtStockMinImpactExeUnit.cpp` | 原无参构造选择原生；重载固定选择，getName报告实际路径 |
| `src/WtExeFact/WtExeFact.cpp` | 原工厂新增适配名称，返回同一类的显式适配实例 |
| `src/GuanhengExecution/StandardExecutionHost.cpp` | 新名字沿原min_order准入；统一核全部policy的实际工厂能力，非法/不支持在账户插件初始化前拒绝 |
| `apps/wt_runtime/guanheng_wt_runtime/execution_configured.py` | 唯一现金ETF profile准确接受两个名称，保留原数量/可卖及资金配置约束 |

前3项属于须批准的WT源码行为差异，后2项是自有装配准入。具体内容见框架差异（外部历史/待归仓路径：`../../build/ms-stock-reference-proposal-003/framework-change.diff`）、自有准入差异（外部历史/待归仓路径：`../../build/ms-stock-reference-proposal-003/own-admission-change.diff`）及逐文件SHA和未应用证明（外部历史/待归仓路径：`../../build/ms-stock-reference-proposal-003/PROPOSAL-003.json`）。没有新增持仓/资金/成交账本或线程、行情、策略调度行为。

新增私有字段改变该具体类布局，新增重载保留原无参构造符号；ExecuteUnit/IExecuterFact接口及vtable保持。取得批准后，工厂内所有直接包含该类头文件的对象同批重编，隔离重建并重新绑定运行安装，不与旧对象文件混用。其他已有冻结框架差异不随本提案进入构建；StockVWap的工作树历史差异保持独立。

## 批准后的构建选择

1. 以`build/ms-observation-refresh-001/native-002/BUILD.json`（SHA `950c101d9e7fe3010d16951756f50676b6c975e50a31626c8a1d9d531cd22a16`）和`build/ms-retained-backtest-001/INSTALLATION-004.json`（SHA `14ff0cc9c165b55bd5728633112a400660a866129dd4c6bdb24a1a0c5018d766`）为本轮准确基线，在全新E盘根装配原生23文件、完整R21/R22/R23功能及六wheel/15个B运行模块，再叠加本提案五文件。native005/R20仅为历史原件，不作为当前功能清单。准确输入见构建基线（外部历史/待归仓路径：`../../build/ms-stock-reference-proposal-003/BUILD-BASELINE-001.json`）。对照本提案三框架文件的固定Git字节，排除工作树其他框架差异。
2. 同批重编WtStockMinImpactExeUnit.cpp和WtExeFact.cpp并生成一个含双路径的WtExeFact.dll；同批重编自有StandardExecutionHost，重建相应自有静态库并重新链接GuanhengCtaRuntime/宿主。执行配置保持原name时选择原生路径，显式适配name才选择借用配对路径。
3. 在安装004的冻结运行源和六发行闭包上替换本提案的execution_configured，保留独立回测十模块和其余四个B执行模块，重建新独立WT wheel及固定安装清单；锁定框架原件/差异、全部直接编译消费者、DLL、wheel和配置SHA。公共运行组件后继变化由A保留并组合，不用本批冻结源整体覆盖当前公共目录；统一候选另跑受影响整链。历史R20/R23/NBC安装原件保持。
4. 在未安装观衡的普通新根完成下表双路径及恢复验收，安装器搬迁后复验真实CLI。原name+旧工厂继续作为原生对照；新name+旧工厂必须在账户插件初始化前失败。通过前保持开发验证资格。

## 验收ID与回退

| ID | 必要验证 | 当前状态 |
|---|---|---|
| SCMR-01 | 固定原工厂的2→2→1及两次borrowed getter计数；正式同次虚调用、两单元1→1→1及第二次析构相同位点失败 | 原红例保持；新工厂双路径及共享owner见实施证据 |
| SCMR-02 | 新工厂原名仍为2→2→1，适配名2→3→2；初始化前的能力probe无商品读取/SDK/委托 | modes001通过；原/新原名、修正版及两单元完整配对 |
| SCMR-03 | 缺省、显式原生、显式适配、非法值/附加分段、旧DLL+适配名逐一验证；原生最小委托及量价与固定上游一致 | modes001/admission002及正式适配主链通过；price-modes004原/新原名及适配名12输入量价一致 |
| SCMR-04 | 同安装唯一1.1.2卖200、后继P/资金/收敛、正常关闭并同根第二代恢复，新SDK不增加；原closed/clean和实际Job/pipe/handle闭合 | main001两代通过；main002等待两代及SHA漂移拒绝通过 |
| SCMR-05 | 零可卖、T+1、原账户资金/费用、部成未决及异常恢复继续沿原身份；故障时成功closed/clean不发布 | main002/003、五订单结果、零可卖、资金/双费用、unknown及搬迁两代已验；T+1复用同WtCore会话证据，正式跨日仍模块gap |
| SCMR-06 | 独立两轴审查、源码/对象/DLL/wheel及配置SHA、离线搬迁后实际入口、未决责任及回退材料 | 实施两轴报告及搬迁证据沿实施记录；最终报告/制品收口中 |

实施前先保存固定原制品、状态和准确配置。批准仅覆盖上述开发与隔离验证时，真实券商下撤单和生产切换继续按其明确授权。回退沿原完整制品和原name配置；先停止并核未决责任与状态兼容，保持原命令身份，恢复沿原同根准入。原生路径继续暴露已证实的引用问题，所以回退表示恢复原运行行为，稳定退出资格单独标注。

当前已按顶部批准记录实施，[实施及实际主链](../evidence/2026-10-30-stock-reference-fix.md)绑定准确新根、源码和制品。其余B主线继续推进，C只读消费、真实新周期、完整交易规则及全周期一致性仍分别列为模块缺口。

批准前独立两轴REVIEW-001（外部历史/待归仓路径：`../../build/ms-stock-reference-proposal-003/REVIEW-001.json`） SHA `6cfb8f7e9c85845bdd910bbbc0c0b81d1ee1513fed4a77282599a15b3c811d72`，确认003五候选保留当前源及显式分流；构建清单仍指旧native005的P2已通过上述R23/NBC精确基线修正关闭，当时开放P1/P2为0。历史002审查SHA `4b7bd3d802803707e238bfd5f1d38516f6e4736ae6f017a29b48c05f84db4928`保留，其首次未知name延迟拒绝问题由初始化账户插件前的实际工厂能力检查收敛。实施后独立审查继续绑定新源码及实际运行，历史提案审查不授新增运行资格。
