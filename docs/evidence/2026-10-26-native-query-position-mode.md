# 2026-10-26 查询持仓为准模式

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：实施与合成验证证据。状态：获批两文件已集成、隔离编译与两组合成回归通过，独立动态复核进行中；默认关闭，真实交易未启用。

## 根因与实现

持仓查询已经包含某笔买入时，迟到的同笔成交回报可能再次增加WT运行持仓。本次仅按用户批准原件（外部历史/待归仓路径：`../../build/qmt-archive-retry-continuation-001/TRADER-ADAPTER-USER-APPROVAL.json`）修改TraderAdapter.h/.cpp及对应测试：position_by_query默认false，显式新模式由成功完整持仓查询整批替换唯一原生持仓表；实时委托和成交保留原通知及其他处理，并请求刷新持仓，新模式不再对该表增减、冻结或解冻。普通四参initExt保持原默认选择；五参初始化显式选择模式，初始化后拒绝热切换。

持仓表访问受同一锁保护；读取返回副本，整批校验后提交，外部API、sink、日志和文件I/O位于锁外。合法空批清空，缺失证券移除；非法批保留原观察。新模式限制4096行，并校验对象、合约、方向、有限非负数量、可用数量关系及重复键；普通模式保留原接受范围。中文注释说明整批替换、锁外通知及原默认边界。

## 构建与实际结果

正式源码及新测试的身份见集成收据（外部历史/待归仓路径：`../../build/qmt-r8-approved-position-integration-001/INTEGRATION.json`）。工作树两文件还带有此前冻结CORE-006差异，当前批准没有追认它们。本次编译明确以固定上游08b230dd加本次批准diff的20个完整上下文块组合；323个上游文件中321个不变，两个组合文件另存身份，不声称原git blob。NqpAdapterHost和两探针使用同一组合头文件，未配置Standard Factory或交易DLL。

163步编译实际通过，控制器79.204秒、根实际保留句柄PID14188退出0。根核323原件、323组合件、154自有件及当前自有源，均与各自清单同SHA；见构建根核（外部历史/待归仓路径：`../../build/qmt-r8-approved-position-integration-001/BUILD-ROOT-VERIFIED.json`）。

| 运行 | 实际结果 | 范围 |
|---|---|---|
| 新持仓探针 | 168断言，14个Adapter实例，退出0 | 8时序、整批/空/非法批、T+1可卖与委托冻结、同步回调重入、初次失败、并发读取 |
| 原默认兼容探针 | 11类观察、21实例、401分发与通知步骤，退出0 | 在相同新Adapter默认模式复验原反例和控制 |

新模式在查询含120股后收到迟到20股成交，观察仍为120；原默认模式仍得到140，证明选择开关与兼容边界。新并发用两个读取线程、100次两证券整表交换，实际52538次读循环，枚举总和仅300或360。该实验验证指定持仓读取/替换窗口，未证明所有策略线程和执行器均无竞争。

两次运行控制器分别PID67180/68752，根实际保留句柄退出0，原50秒外截止内完成；各控制器45秒，探针共享30秒。两者树0、双EOF、线程join、资源关闭、无强制终止。新EXE SHA a084ba1d21a43ef81509733c822cb30e56f787f96f9d9bab509ef32e97e415c0，旧兼容EXE SHA b8ae8c4998b59edca21c1631e7c4b75721a61297eff5e0e641fd6fc1f4f56e66；运行根核（外部历史/待归仓路径：`../../build/qmt-r8-approved-position-integration-001/RUNTIME-ROOT-VERIFIED.json`）。真实券商SDK、SHM、网络及真实下撤单均0；合成orderInsert用于统计读取和重入，不能表述为全部native API调用0。

## 审查及限制

源码full001（外部历史/待归仓路径：`../../build/qmt-r8-approved-position-independent-001/full001/REPORT.md`）发现错误对象夹具被WTSArray重载展平；002以显式WTSObject指针修正并断言真实非持仓对象，delta002（外部历史/待归仓路径：`../../build/qmt-r8-approved-position-independent-001/delta002/REPORT.md`）关闭该问题，产品逻辑未随夹具修订变化。构建脚本初版EOF处理假设有末尾换行，002保留原BOM、CRLF及cpp无EOF换行；构建delta002（外部历史/待归仓路径：`../../build/qmt-r8-position-build-independent-001/delta002/REPORT.md`）通过。控制器及运行入口分别由delta003（外部历史/待归仓路径：`../../build/qmt-r8-position-build-independent-001/delta003/REPORT.md`）、delta004（外部历史/待归仓路径：`../../build/qmt-r8-position-build-independent-001/delta004/REPORT.md`）核验。

默认仍关闭。真实完整账户查询的缓存新鲜度、未登录空结果和刷新间执行窗口待实际来源核对；成功空批不能自行证明真实账户已清仓。查询与实时成交的统计可能仍40而应20，owned未成交量可能仍60而应80；full_R8_closed保持false。原订单容器释放、完整恢复/Standard接线/关闭矩阵、配置插件装载与生产资格均未由本探针证明。其余24受保护框架文件保持本轮前原样，生产未切换。


## 独立动态复核后继

dynamic005（外部历史/待归仓路径：`../../build/qmt-r8-position-build-independent-001/dynamic005/REPORT.md`）已核800份冻结闭包、两文件20块差异重建、实际163步编译及两个运行报告，无新增P1/P2；33公开原件由根逐SHA复核。根实际进程句柄事实标为根收据，与控制器PID及退出记录匹配。编译/运行结束后README两段陈旧状态已更新，冻结154件保持原样，当前153件其余源保持；区别见文档补充（外部历史/待归仓路径：`../../build/qmt-r8-position-build-independent-001/dynamic005/ADDENDUM-001.md`）及根核原件（外部历史/待归仓路径：`../../build/qmt-r8-approved-position-integration-001/DYNAMIC-INDEPENDENT-ROOT-VERIFIED.json`）。本切片独立动态复核通过，完整R8及生产资格继续保持未完成。
