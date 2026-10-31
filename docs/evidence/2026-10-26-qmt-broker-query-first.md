# 2026-10-26 券商查询优先与原生接缝验证

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

状态：进行中。真实持仓和订单状态、剩余量采用券商查询，WT新增订单管理框架改动保持候补冻结。规范见 [QSW-R17/R18](../specs/qmt-shm-wt-binding.md#qsw-r17-真实账户持仓的券商查询权威)。

## 当前已验证

公开接口调查确认派生 Local 执行上下文及虚 SPI 可承接订单查询观察；原Runner私有构造路径、撤单私有订单表、未决提交和历史统计仍有边界。见接缝研究（外部历史/待归仓路径：`../../build/qmt-broker-query-extension-route-001/REPORT.md`）。该静态结论未授完整生产接入。

普通原生账户扫描支持v3四查询；新构建发现自有 `qmt_readonly_fixed` CMake漏列已被Core和映射调用的 `QmtHostCodec.cpp`，新增唯一实现后固定08b230原版WT与自有源码构建通过。未改WT。新普通DLL SHA256 `1b63d667f132a9b1418733af955f1eadc0b47b370601ca85512fbd04d2333f81`；实际构建（外部历史/待归仓路径：`../../build/guanheng-workspace/account-broker-build-control-005/ROOT-RESULT.json`）及固定来源（外部历史/待归仓路径：`../../build/native/account-broker-current-002/built-source.json`）。前面冷准备超时和漏链失败原件保留。

现有原生CTest两项2/2通过。随后80项构建工具测试有23个历史迁移SHA被当当前源码比较的失败及1个正常fixture遗漏当前ordinary_matrix.py的错误，原批次日志（外部历史/待归仓路径：`../../build/native/account-broker-current-002/logs/pipeline-tests.log`）保持原样；测试责任层现已修正：保留旧历史清单，当前完整选源及新增／修改模块按新快照验真；正常fixture补当前必需模块并保留旧归档兼容。新批次83项回归（外部历史/待归仓路径：`../../build/guanheng-workspace/account-broker-current-fixtures-control-001/ROOT-RESULT.json`）全部通过，原profile失败收据不回写；两测试独立审查（外部历史/待归仓路径：`../../build/qmt-account-source-fixture-review-001/REPORT.md`）未发现P1/P2，83项动态复核（外部历史/待归仓路径：`../../build/qmt-account-source-fixture-review-001/dynamic001/REPORT.md`）确认本轮结果及原D/回收。

## 查询优先接缝及后继

新自有查询上下文探针（外部历史/待归仓路径：`../../tests/integration/qmt_broker_query_context/README.md`）验证真实合成查询100/20/80经派生上下文进入原MinImpact，迟到成交后执行读取仍80；首轮固定原WT加已批准持仓两文件编译通过，实际两例52断言、各5次原unit tick读80，通过首次运行（外部历史/待归仓路径：`../../build/guanheng-workspace/broker-query-context-run-control-001/ROOT-RESULT.json`）。独审发现自有插入前retain可能在bad_alloc时遗失引用，现已改插入成功后交接并补实际入口异常回归；002源码引用修正已通过静态delta，但新增exception_ptr地址同一断言在MSVC实际失败，失败原件保留；[MSVC文档](https://learn.microsoft.com/en-us/cpp/cpp/transporting-exceptions-between-threads?view=msvc-170)明确current_exception可返回不同副本，因此003改为异常类型与稳定origin逻辑标识，其余引用/金融断言不变，003新冻结源码独立编译通过，最终两例68断言（外部历史/待归仓路径：`../../build/guanheng-workspace/broker-query-context-run-control-003/ROOT-RESULT.json`）全部通过，每例5次实际原MinImpact on_tick读取80；原订单与成交通知保留、买卖尝试0、行引用／待处理／清理错误均0。实际root74484自然exit0，创建期Job、原45秒截止、EOF、join及资源关闭通过；003静态delta（外部历史/待归仓路径：`../../build/qmt-broker-query-context-review-001/delta003/REPORT.md`）无P1/P2，最终独立动态复核（外部历史/待归仓路径：`../../build/qmt-broker-query-context-review-001/dynamic004/REPORT.md`）确认源码与二进制、两案68断言及资源边界，未发现新增P1/P2。首轮和002失败均保留，不用旧结果授最终源码资格。此探针不含真实券商、Standard/Host/SHM运输，也不授完整取消、unknown解除、统计与重连。

真实账户原生四查询尚未执行。仓库股票静态清单不覆盖10月23日已取得的4个持仓证券；计数核对保留在受保护样本覆盖摘要（外部历史/待归仓路径：`../../build/guanheng-workspace/account-broker-build-control-003/PRIOR-ACCOUNT-CONTRACT-COVERAGE.json`），没有输出证券或资金原文，不代表当前账户覆盖。已找到外部SDK真实证券详情与类型的只读接缝，见元数据研究（外部历史/待归仓路径：`../../build/qmt-real-account-native-route-001/metadata-source-003/REPORT.md`）；尚未调用。最小委托量、T+1等未提供规则保持未知。

当前QMT策略与本次Host停止，生产未切换，无真实下单或撤单。整体迁移目标保持进行中。

## 收据字段限定

更正记录（外部历史/待归仓路径：`../../build/qmt-broker-query-receipt-correction-001/CORRECTIONS.json`）保留五份原收据，明确其中controller_sha256实际指结果JSON摘要，另列控制器源码摘要及launch生成绑定。最终003已分别命名source/result；测试stdout与资源终态各有原件支持。上述更正不授完整解释器依赖或模块origin执行前后审计。

## 真实证券资料只读切片

已完成metadata探针（外部历史/待归仓路径：`../../tests/integration/qmt_metadata_read/README.md`）源码及控制器独立审查。发现SDK普通import可能执行未冻结pyc，现仅对精确清单源码采用同一bytes核SHA后编译；vendor缓存未修改。27项纯替身测试分别在开发解释器和原Python3.6.8通过，实际root68020/40880自然退出，创建期Job、EOF/join及资源关闭通过。见开发解释器结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-metadata-pure-modern-001/ROOT-RESULT.json`）、目标解释器结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-metadata-pure-py36-001/ROOT-RESULT.json`）和独立审查（外部历史/待归仓路径：`../../build/qmt-metadata-source-review-001/REPORT.md`）。

本次重新核验报价进程身份与58610监听，33项安装来源前后匹配；单次真实外部SDK连接及每证券detail/type各一次完成，4项请求的详情和类型全部为None，保留空值，未生成交易规则。实际root15428自然exit0，约1.05秒；来源20项Python源码实际加载、4模块路径、报价owner前后核、私密首双pipe、原30/45秒截止、Job树0、EOF/join和关闭通过。见安全运行收据（外部历史/待归仓路径：`../../build/qmt-metadata-controller-001/ROOT-RESULT.json`）及控制器审查（外部历史/待归仓路径：`../../build/qmt-metadata-source-review-001/CONTROLLER-REPORT.md`）。这证明本次只读请求和资源正常，不授完整金融metadata、超时故障矩阵或整个解释器闭包；原始证券正文及SDK输出保持受保护，账户/下单/撤单/历史/订阅/下载调用均0。

接续核查原生账户扫描四查询是否仅依赖券商证券身份；完整交易规则未知项保持未知。正常Standard/Host/SHM的查询优先取消纵切片候选已形成，当前仍待编译和运行，不等同真实交易验证。

## 后继配置覆盖审计

逐项源码审计（外部历史/待归仓路径：`../../build/qmt-framework-config-audit-001/REPORT.md`）确认：position_by_query业务分流明确，但锁及通知工作值由两模式共用；managed_stop只覆盖受管停止链，部分task/ticker/错误守卫共用；CORE004初始化与CORE008空计数为无新增开关的直接修正。因此前述默认开关结论仅支持对应业务分支，不能扩称全部框架差异均隔离。按QSW-R19，后继发行须逐项完成原生/适配路径选择与验收；现有开发证据保持原资格，当前不新增或改动框架源码，不以已批准范围自动豁免配置要求。

## 正常Standard/Host/WinSHM查询优先取消纵切片

新切片（外部历史/待归仓路径：`../../tests/integration/qmt_query_normal_binding/SLICE-SPEC.md`）已用固定08b230的327份源、325份原样及仅批准两文件20块position差异构建；owned229，正常StandardFactory DLL及新probe已通过003编译（外部历史/待归仓路径：`../../build/guanheng-workspace/query-normal-build-control-003/ROOT-RESULT.json`），不带冻结CORE006和故障宏目标。首次漏normal configure源、直跑缺Agent导入、N01误断取消ABI left80三份失败分别保留。已核唯一mapper把活动委托left80、取消态left0，与源raw remaining80/cancel80分开；仅测试oracle修正，产品mapper与金融源未变，原base0断言保持。003独立delta（外部历史/待归仓路径：`../../build/qmt-query-normal-oracle-review-001/REPORT.md`）无必要P1/P2。

003完整运行（外部历史/待归仓路径：`../../build/guanheng-workspace/query-normal-run-control-003/ROOT-RESULT.json`）实际root70768自然exit0/约20.07秒，两方法N01/N02均通过，0skip/failure/error。fresh172运行源前后及business模块来源核验通过；每案原seed4+恢复4+刷新P/O共10次查询，真实原insert/cancel命令各一次，经HMAC/Host/WinSHM及原源owner的SDK替身，未执行真实券商交易。R21Q由真实ORDER终态恢复原ID/tag后调用原base.cancel，保持原checkCancelLimits路径与计数；DEAL20非空保留。N01原unit tick实际读available100、query挂单0，buy/sell尝试0；两案base/query挂单0。N02在末O实际交付后抛原回调错误，原Standard9、首因、Closed/drain/join/delete/无晚SPI均通过，不在失败后继续unit。源、Host、server/proxy线程、子进程与外层Job树0、双EOF/join/资源关闭实证齐全。runner独审（外部历史/待归仓路径：`../../build/qmt-query-normal-runner-review-001/REPORT.md`）通过，动态独立复核另行登记。

限定：该测试目标100来自原上下文validOnly默认的可用100，实际总持仓120保持。目标总持仓120的一般买卖、SDK已返回但券商订单尚未出现时的防重复准入、query/live历史统计交接、重连、全故障矩阵及生产配置装配仍未完成；不得把本片通过当作完整R8/真实SDK或发布资格。下一步先调查WT既有股票执行能力和pending公开接缝，继续真实只读账户链。

只读身份生成器（外部历史/待归仓路径：`../../tests/integration/qmt_readonly_identity/SLICE-SPEC.md`）7项纯测试已通过，4份实际授权代码的受保护identity资料已生成并核SHA；技术空session/数值未知0/模式9和cash ABI命名空间仅供只读scan，未授真实证券规则、实际native加载或账户查询。独立原生loader审查（外部历史/待归仓路径：`../../build/qmt-readonly-identity-native-review-001/REPORT.md`）通过，编译/实际87check及真实四查询待验。


## 后继原生身份加载实测与独立复核

专用 loader 以固定08b230的323份原件、117份自有输入和6项固定工具构建，只编译真实WTSBaseDataMgr加载接缝；实际构建（外部历史/待归仓路径：`../../build/guanheng-workspace/readonly-identity-build-control-001/ROOT-RESULT.json`）自然exit0，EXE SHA256 `43f7d8c9fa090cd86691e2a35f98e3cc868c7a73cc104cc9ccafffae30078f10`。由已审生成器产生的4个合成身份通过原版loader运行（外部历史/待归仓路径：`../../build/guanheng-workspace/readonly-identity-native-run-control-001/ROOT-RESULT.json`）：87项实际检查全true，stdout仅固定检查JSON、stderr0，数据前后SHA一致；实际root33496自然exit0，创建期Job、原截止、树0、双EOF/join和资源关闭通过。独立动态审查（外部历史/待归仓路径：`../../build/qmt-readonly-identity-native-dynamic-review-001/REPORT.md`）重算来源、二进制、数据及87项输出后通过，无必要P1/P2。析构作用域标记只证明析构返回，完整引用平衡、真实金融metadata、实际账户四查询及交易均仍待验。

正常查询取消003的独立动态复核（外部历史/待归仓路径：`../../build/qmt-query-normal-dynamic-review-001/REPORT.md`）也已通过：核定327原版/组合、229自有、172运行来源、64实际业务模块、两案原始查询/HTTP/命令回执、二进制、原截止及回收。前述“R21Q由真实ORDER终态”准确指真实ORDER查询的成功通信终态，不表示该委托当时已撤销或成交完毕。其余一般买卖和恢复限制继续保持。

股票执行后继已只读取得固定08b230的完整20份WtExeFact原件，见来源清单（外部历史/待归仓路径：`../../build/qmt-stock-fixed-source-001/base/input.json`）及实际提取（外部历史/待归仓路径：`../../build/guanheng-workspace/stock-fixed-source-read-001/ROOT-RESULT.json`），无Git/框架修改或SDK调用。StockMinImpact当前与固定原件仅换行差异；StockVWap存在真实工作区差异，因此先前研究中基于当前StockVWap的结论只授该版本，后继仅使用固定原件重新核实。原生股票总量目标与订单未出现空窗的候选继续开发，未授动态或生产资格。


## 股票目标与订单查询空窗的实际后继

股票S1/S3已用固定08b230全20份执行工厂原件及仅批准position两文件覆盖构建，343上游组合/234自有/173运行源逐摘要核定。实际构建（外部历史/待归仓路径：`../../build/guanheng-workspace/stock-execution-build-control-002/ROOT-RESULT.json`）自然exit0/116.374秒；实际运行（外部历史/待归仓路径：`../../build/guanheng-workspace/stock-execution-run-control-001/ROOT-RESULT.json`）两案2/2，无skip，正常Standard/Host/WinSHM四查询、真实原WtExeFact工厂及原Local执行上下文通过。S1总目标120稳定无写调用；S3目标100触发原unit提前返回，后继119量化结束只作为边界反例，未授精确目标可达资格。原非空DEAL20保留；一般引用生命周期仍未取得资格。动态独审原件（外部历史/待归仓路径：`../../build/qmt-query-stock-dynamic-review-001/REPORT.md`）已核来源、实际8次查询及完整进程收束，无必要P1/P2。

订单查询空窗S4实际构建（外部历史/待归仓路径：`../../build/guanheng-workspace/order-gap-execution-build-control-001/ROOT-RESULT.json`）125.090秒/实际运行（外部历史/待归仓路径：`../../build/guanheng-workspace/order-gap-execution-run-control-001/ROOT-RESULT.json`）1/1通过，表示成功复现风险：SDK替身已返回、ORDER仍为空时，原股票unit四次tick产生4个不同原命令，每次实际100股；query U保持0，原base U达到400。未用重复POST或伪造挂单制造结果。独立动态核验（外部历史/待归仓路径：`../../build/qmt-query-order-gap-dynamic-review-001/REPORT.md`）通过。防重复准入的产品修复仍待完成，本轮未改WT核心。

## 真实只读账户扫描部分成功

本次及时启动后真实共享内存binding成功、两次新鲜tick成立。原生扫描POSITION实际返回4行；随后ORDER来源查询自身ok=false，DEAL与ACCOUNT未到达，整轮失败并回收Host/原生进程。安全结果及实际句柄保留在本机受控attempt003，原始账户与响应帧保持私密；未将来源错误伪装为空委托。根PID6576自然exit2/29.935秒，原生exit3，原Job树0、EOF/join及资源关闭成立。本次未下单/撤单，账户四查询及真实交易仍未完成。

此前首次等待失败由启动调度超过Host60秒接入期限证实，见时序诊断（外部历史/待归仓路径：`../../build/qmt-real-binding-diagnosis-001/REPORT.md`）。及时启动能连通与当前ORDER来源错误属于不同链路，不能以加长连接期限修复账户查询。用户已确认转向系统统一常驻等待与恢复，见[QSW-R20](../specs/qmt-shm-wt-binding.md#qsw-r20-常驻连接与系统统一启动)。

真实ORDER故障类别后继：只读原通信Journal固定字段投影取得`operation_interrupted`，其执行时长/排队时长缺失；POSITION原查询成功。该事实证明委托读取以通信中断终态结束，尚不能归因为券商SDK自身报错。原始消息、账户及证券值未输出；分类运行（外部历史/待归仓路径：`../../build/guanheng-workspace/account-order-error-category-control-001/build-account-order-error-category-control-001/result.json`）自然exit0，实际SDK是否进入及断连触发点继续定位。
