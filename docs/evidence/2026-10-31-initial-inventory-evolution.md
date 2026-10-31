# 当前库存启用后差额、新成交周期及会话日后继

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B开发验证证据。状态：限定切片已独立审查，完整运行资格pending-verification；完整B保持active。所有来源为明确SDK替身，真实账户操作0，新增WT框架修改0，新写入全部位于E盘。

## 根因与实现

周六首次自动库存原链在CTA初始化拒绝，SDK0，外Job75556 exit1且树0/EOF/join/资源关闭全部通过。原件为`build/ms-inventory-evolution-native-001`。其准备事实使用自然日期20261031；原P23分支要求与ExecutionEnvironment同次观察的原生交易日相等。原版Environment与原WT日历的独立探针在同一现场返回20261102，另核周五20261030→20261030、周日20261101→20261102。该证据结合分支源码及修正后整链成功支持日期所有权根因；旧现场直接错误边界为CTA，未记录其内部失败指令。探针构建/执行Job46604 exit0/6.445秒，证明位于`build/ms-inventory-session-date-002/DATE-PROOF.json`。

修改限自有三源：initial_inventory_execution.py移除自动装配的日历推定；initial_inventory.py支持无trading_date的facts.v2并生成cta-takeover.v2；CtaProcess.cpp沿原ExecutionEnvironment同次观察取WT会话日，初始原生账本及载入收据保存该日期。旧v1显式日期仍严格核同一次观察。券商日期known/unknown、有效事实/标价、原WT日历/金融格式及正常恢复语义保持。对应NRT-R30-C1/C2/C3，具体合同沿[唯一规格](../specs/native-realtime-strategy.md#nrt-r30-当前持仓初始库存与新的运行基准)和[初始库存方案](../migration/retained-strategy-takeover-proposal.md)。

新CtaProcess源码SHA `c05005ac263a57d87fda832f6b1db244f91516e2950f924a755e80cfbfb102e8`；固定Native006原库加最终Standard cdc500候选，只重编自有Runtime及同批链接Host，26成员中Host/Runtime DLL变化，原import lib字节一致。编译/链接各exit0并完整回收；构建控制器因过严要求import lib也必须变化而exit1，该历史保留。`build/ms-inventory-session-native-build-001/POSTBUILD-001.json`另行冷核原链接输入、源码、实际产物及全部物理回收，SHA `0021ac181f0062a90a4fdcd9a3367a0bba229205b02bef78e468e8f4f06a634f`。最终包不依赖该私有控制器的失败断言。

## 实际主链

普通23发行版本0.1.0a12+inventorysession.1，1355条摘要RECORD。`ms-inventory-evolution-native-002`使用实际原Factory/CTA/NSQ/执行器/Adapter/WinSHM、安装Host/Agent及唯一1.1.2：当前200份510050、可卖200，初始年龄0/无旧峰值/旧退出；原模型先卖200，再买新目标200。2次SDK替身调用、2笔实际映射、4条Host事件及源/Host/策略成交ID集合精确相等，新仓周期为native-open并使用本次live成交来源。两代正常停止，原目标/数量/周期/NAV/资金/PnL保持，恢复新增SDK0。外Job76796 exit0/52.664秒。

独立56成员ZIP SHA `cdbd50fe7873625cf0b8282427d18c0452b7785fd4a9abcea952d5cf36d5b235`，23发行完整require-hashes离线搬迁安装1332条摘要RECORD。搬迁`ms-inventory-evolution-native-moved-001`通过同一完整链，Job31512 exit0/48.091秒；两案均91个实际guanheng模块来自各自安装site，运行后RECORD、ZIP及26原生组件0漂移。材料位于`build/ms-inventory-session-package-001`。

原WT账本手续费为6元：卖200×0.02、买200×0.01，固定价格下原realized/dynamic profit为0，原PnL从0到-6、NAV从120000到119994，恢复保持。SDK替身available按成交毛额变化，故券商净手续费和净available不在本次费用资格内。冷只读证明`build/ms-inventory-evolution-proof-001/PROOF-001.json`重新核实际回报集合、手续费配置、原金融文件和关闭身份，新增查询/SDK0。

## 可卖等待与回归

`ms-inventory-scheduled-sellable-native-001`实际调度、再次计算和同根恢复均为waiting_sellable，总量200/可卖100，冻结100，SDK0；Job44036 exit0/42.335秒，两代原closed.v2及clean.v2、KV/数量状态/原金融文件与物理清理通过。独立冷核沿原sellable_recovery_proof执行，结果位于该目录SELLABLE-PROOF-001.json；下一会话释放尚未验收。

安装合同回归保留旧函数拒绝v2的红例，并核新v2日期所有权/数量/可卖、旧v1保留显式日期、v2拒外部日期、v1缺日拒绝、未知schema拒绝及空库存原fresh路径。最终两个有限Job44624/31800 exit0、完整回收；初次测试读错异常属性的工具失败原件保留，修正测试使用原CtaBridgeError字符串原因码。

## 交接与缺口

固定集成检查点（外部历史/待归仓路径：`../../build/ms-inventory-session-delivery-001/INTEGRATION-CHECKPOINT-001.json`） SHA `3a6b77132b3d9f3a68586bf8f326fbaa039d37d5434da4291f28a2d18d56e030`绑定三源、普通/搬迁安装、Native链接依赖、制品及实际主链。旧broker固定交付保持原件，其目录新INTEGRATION-SUCCESSOR-002明确指向该后继；根组合按同一Reader/Common/WT ABI cohort纳入配套Python及Native消费端。新增接口尚待最终独立审查及根统一候选验收。

首根合格分析收盘的原生日线发布/日内与盘后组合、下一交易日可卖释放和跨日来源、真实休市有效标价/券商日期、完整订单撤单/多策略受影响组合及整体B继续待验。原032停止具体阶段unknown与旧预算oracle保留。真实交易、生产发布均未授权或执行。


## 最终独立审查与交接

源码full采用57冻结输入：协议297绑定，报告SHA `65576cc8d4a19c0a9c85eb5e03f6e69f02b79eae4dd95329a42eb3b5a7bafa98`；执行194绑定，SHA `2a9b23c0cd4774d41f15797296f26a38d711981f66d5ea1e1b92116995f20074`。包与搬迁delta采用31冻结输入：协议411绑定，SHA `22d55305a0ff6a538ef3cf6196e2a315f6ebbc56bd464be64f5d22101990dd9c`；执行262绑定，SHA `10345418c7fe5d017a366d31b04b9ea6db008aefaf2d910e2fd63a136f204dbe`。四报告新增开放P1/P2均0；交接前逐一复核1164绑定及两份冻结清单原件/副本，均无漂移。报告与冻结原件适用其原身份，本段为审查完成后的追加记录。

普通1355与搬迁1332的RECORD条目数差为23个direct_url.json；共有安装生成项中23个uv_cache.json、6个exe launcher摘要分别绑定各安装根。产品共同.py/.pyd/DLL保持各自声明身份；本次资格依据每一安装自身RECORD、实际91模块来源及完整主链，不称两安装所有文件逐字相同。实际main控制器于运行前封存，包生成控制器的时序按报告单列。

最终HANDOFF（外部历史/待归仓路径：`../../build/ms-inventory-session-delivery-001/HANDOFF-001.json`） SHA `e082d8b679db059cbaf074ffe733b26890ff980a882f687c0e2ee416e9fee92f`固定源、制品、普通/搬迁原件与四报告，状态ready_for_root_candidate_integration=true、whole_module_qualified=false。根按其匹配ABI cohort组合三源与新wheel/Native，真实交易和生产切换继续另按授权。旧broker目录INTEGRATION-SUCCESSOR-003链接本最终后继，旧检查点/交接保持原件。

先前公共文档检查曾报告另一个模块新文档observer-natural09未索引，原观察单独保留；owner后继索引后检查通过。本模块证据由module-b-delivery入口可达。完整B仍active，前述首合格日线/下一交易日释放/实源及统一验收缺口保持。

## 受管次会话日历模型后继

`build/ms-managed-next-session-run-002`沿实际安装的WRI、执行工厂及原ticker完成同一金融根的两代运行。隔离构建仅在自有`CtaExecutionSession::start`调用原`engine.run()`之前，选择公开`set_date_time`设置原生启动日；第一代20261102，第二代20261103。原ticker继续自行计算交易日并调用`on_init/on_session_begin`，原WT及账本格式保持。ExecutionEnvironment、来源新鲜度和真实系统时钟保持原值；本模型单独控制CTA原生日期。

第一代原生持仓200、可卖100；恢复后的原ticker将原生可卖释放到200，券商观察仍为100时策略保持`waiting_sellable`且SDK0。随后替身来源可卖变为200，由已有5000ms刷新配置沿原Source/Parser完整查询确认，再实际卖200。SDK1、映射成交1、Host事件2，WT本次费用4、盈亏-4。原周期状态恢复后接续，卖清证券周期退出；两个Native `closed.v2`及两个WRI运行根均正常关闭，无pending/forced，外Job52188 exit0、64.701秒，树/EOF/join/资源关闭全部通过。

首个`run-001`未选择已有观察刷新配置：原生100→200已观察，券商P仍为100，14查询、SDK0，最终WRI exit2且缺第二代正常关闭，物理回收完成。该失败原件保留；具体晚关闭阶段尚未核实。后继选择原刷新配置并通过完整来源刷新、卖出及正常关闭，不把前次进程失败归因于WT。

固定证明（外部历史/待归仓路径：`../../build/ms-managed-next-session-proof-002/PROOF-001.json`） SHA `df195d7afe886540467b4725b5f00d84acae146b5597ac4ddff916013d6382b9`绑定998输入。执行独立审查（外部历史/待归仓路径：`../../build/ms-managed-next-session-proof-002/REVIEW-EXECUTION-001.json`） SHA `20f62680c99e468bbb639701540c41d631120149ca32d8e07693a14a2afdd2e0`核1010绑定，新增开放P1/P2为0。

审查发现旧QA结果仍按初始`blocked_sellable`标志写`sold_sh50=0`。实际来源deal、原canonical成交身份和Native映射一致确认卖200；原RESULT保留，只读更正（外部历史/待归仓路径：`../../build/ms-managed-next-session-proof-002/SUMMARY-CORRECTION-001.json`） SHA `4ccffc562760f5b82dd359cbd7df6c3d242f5ab4b52540093eb3ea9998753d41`核7绑定，QA通用摘要现改为汇总并去重来源已报告成交。该摘要不推断未知委托是否执行。补充控制器依赖（外部历史/待归仓路径：`../../build/ms-managed-next-session-proof-002/CONTROLLER-DEPENDENCY-001.json`） SHA `3a661710f826b1143c205002b5429818e6b48fb31def6e5bcd09299bb105d3ce`仅记录事后当前SHA；base controller的运行前冻结身份仍有限，实际生成QA/配置/native/运输沿原证明。

本次授受管日历模型下的原ticker解冻、券商补查先于卖出和正常两代资格。自然跨夜、默认系统时钟下所有日期owner一致、首根自动新日分析、完整三轮和整个模块仍为gap。诊断用成对Runtime/Host保持隔离，原P28产品包未替换；当前优先沿根full003原现场定位实际目标未达的执行推进耗时。
