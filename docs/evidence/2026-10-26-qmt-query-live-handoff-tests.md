# QMT首次查询与回报交错测试接线

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发实施证据。日期：2026-10-26。状态：后继固定上游探针已编译，三时序实际3/3通过；X01通过表示重复计数反例被复现。生产首次/重连交接未解决。

## 实际修改

新增tests/integration/qmt_standard_trader/r8_handoff_probe.cpp与test_r8_handoff.py；测试CMake增加独立NqpR8Probe，build.py仅登记该输出，冻结器沿原目录规则纳入新文件。目标只编译一个探针TU并链接固定原版NqpAdapterHost，通过显式摘要装载正常Standard DLL，不包含产品Standard.cpp或测试版金融实现。原框架和产品源码未改。

三案由真实Agent/Host/Win32 SHM运输和原WT Adapter消费，只读SDK替身维护自身合成状态、原线程查询与真实捕获一笔外部成交；下单撤单调用0。外部备注不伪造本地owned身份，undone0，不用它授自有订单恢复资格。

| 场景 | 源真实时序 | 实验断言范围 |
| --- | --- | --- |
| X01 | position已包含买入20，四查询完成前捕获同成交 | 预计原Adapter140/源120；必须实际观察才记录重复归约反例 |
| X02 | position返回100后成交，order/deal已含，账户查询前捕获 | 持仓120的控制；不授查询与push成交统计正确 |
| X03 | 四查询Ready后才成交与捕获 | 持仓120的稳定增量控制 |

每案核源查询原行/UUID、捕获seq、ACK及native after_seq、WT真实持仓/可用/回调、SDK写0和原D关闭/实际delete。源脚本ordinal只作为独立oracle，不进入产品充当券商水位。原Adapter_stat_map未读取；完整金融统计、owned订单、真实provider排序和生产R8全部继续待验。

## 静态审查和集成

001 full发现唯一P2：先判断pump负返回值会覆盖回调中已保存的首异常；002改为先保存pump rc、先重抛原callback_failure、最后检查rc，并在getter/login/event/logout/log与各金融SPI入口统一锁存首异常，关闭/delete仍执行。原D、三时序oracle及Python不变。full58份原件、delta5份新增索引原件分别登记在full报告（外部历史/待归仓路径：`../../build/qmt-r8-handoff-tests-independent-001/REPORT.md`）及002 delta（外部历史/待归仓路径：`../../build/qmt-r8-handoff-tests-independent-001/revision002/REPORT.md`），无剩余新P1/P2。

根集成前核002封包39件、31前置当前源码及构建基线，实际四文件复制后逐份核同；最初实施收据表达式ReferenceError发生在文件已写后，未重复覆盖源码，重新逐份核对后写入实施收据（外部历史/待归仓路径：`../../build/qmt-r8-handoff-implementation-001/INTEGRATION.json`）。CPP a3b8eefeee0e4f43c3bc2c0040db48eb2deec5e352c85e274c2cfd5afca21d0f；Python a7beef1b557f3ce9af7ec5ee87bc9cf2bd34d9765487952a413cf3730305874d。

## 下一步与限制

前置构建工具第一层输出已在自有层修正，58项适用回归实际通过；范围与主批启动器身份限制见[工具证据](2026-10-26-native-bounded-build-output.md)。后继短根build/r8-001的NqpR8Probe已编译并完成下述三案。完整父死亡和全部故障范围继续分别验收。

正式算法仍缺可验证的券商查询/成交覆盖关系。本地seq、ACK、时间区间、两次查询相等和回调缓存为空均不自行生成该关系。原版21交错观察见[既有反例](2026-10-25-native-query-live-counterexamples.md)，本片三案后继实际结果见下节。全系统目标继续，不把反例测试接线当启动/重连问题已解决。

## 实际编译与三时序后继

固定08b230dd下NqpR8Probe实际161步编译通过，控制器75.437秒；178本仓/323上游快照由根逐SHA核同。新EXE SHAadc5a17036841a7167071a3b49f24356c7ceec8b7d1e42f2886c10954e075a88，运行显式复用正常TraderQMT.dll SHA61c9f81e2094dedae1c05bddbf364af1888f3a424faa779985afefb21f4d1980。未引入框架覆盖，见编译根核（外部历史/待归仓路径：`../../build/qmt-r8-handoff-implementation-001/BUILD-ROOT-VERIFIED.json`）。

171项运行源前后固定，INPUTS d72bf0f8b109e7d68ccc2b862ccb9c45c9a97c5c773b75046c946a7ace4199a7；独立runner静审（外部历史/待归仓路径：`../../build/qmt-r8-handoff-runner-independent-001/REPORT.md`）核exact closure、实际module来源、原总D、制品及控制器。一次运行三案3/3，无失败/skip，unittest8.766秒、控制器12.375秒。直接base Pythonw的根实际句柄PID20276与controller PID20276一致，exit0，Job树0、双EOF、join及资源关闭，无强杀。

| 案例 | Ready持仓 | 消费成交后WT持仓 | 来源真实最终持仓 | 实测解释 |
|---|---:|---:|---:|---|
| X01 | 120 | 140 | 120 | 重复归约反例复现 |
| X02 | 100 | 120 | 120 | 查询间成交的持仓控制匹配 |
| X03 | 100 | 120 | 120 | Ready后增量控制匹配 |

每案5次原查询，原生insert/cancel均0；真实Agent/Host/WinSHM、原Adapter和正常插件参与，券商SDK全部替身。每案native closed/deleted/drained/joined为true，最终payload0/pending0。查询UUID/terminal原件、实际事件seq/ACK与after_seq由既有断言核查；根运行收据（外部历史/待归仓路径：`../../build/qmt-r8-handoff-implementation-001/RUNTIME-ROOT-VERIFIED.json`）保留每案原件摘要。所有summary/provenance/native结果的R8_qualified与production_qualified仍为false。

该结果证明指定接入时序下运行持仓重复应用的条件；源实际仍120，并无第二次真实买入。X02/X03不授完整统计、自有订单恢复或真实券商更新顺序资格。下一步沿[绝对持仓研究](../migration/qmt-account-snapshot-research.md)冻结最小必要框架提案并核来源新鲜度，新增框架修改继续按用户批准执行。

独立动态窄复核（外部历史/待归仓路径：`../../build/qmt-r8-handoff-runner-independent-001/dynamic001/REPORT.md`）已通过：15个查询UUID、216份响应SHA、8个事件页、ACK及三时序匹配；171源与64个实际业务module前后核同。根已核该报告19份公开副本及3份仅摘要登记的合成fixture来源；实际进程句柄事实来自根保留的Node对象与收据，审查者没有重复执行。该复核保持上述恢复与生产资格false。


## 自有委托恢复交错后继（2026-10-26）

新增X04/X05显式场景，默认X01–03保持。两案先由原Adapter.buy创建真实localid/tag/EntrustID，经正常DLL、Host和Win32共享内存进入一次原线程SDK替身；真实返回后Pending正常退役至0，原实例Closed/delete，再以同一Host/Agent/source重建插件。恢复ORDER查询的成功保存事务生成R21Q关系，不预填身份或证明。该返回仅证明SDK调用返回，不证明券商已受理。

固定原版上游08b230dd编译NqpR8Probe通过，71.266秒；根核178自有/323上游来源，新EXE为e5b33497c50ae0e855a39130137a116335d3e6886ad785ef58f7a3309af58254，正常DLL仍61c9f81e2094dedae1c05bddbf364af1888f3a424faa779985afefb21f4d1980。见编译原件（外部历史/待归仓路径：`../../build/qmt-recovery-next-001/BUILD-ROOT-VERIFIED.json`）。

首轮前三案通过，X04在第七个读取POST遭503 queue_full，X05未运行。原测试读Journal上限200000字节，六条保留记录已预留198547，第七条累计231636；产品按配置拒绝正确，未到金融窗口。后继只在测试构造期按真实validator的十槽上界配置381440，默认共享配置不变，TTL、金融断言及截止不变；失败原件与独审遗漏更正保留。见首轮失败（外部历史/待归仓路径：`../../build/qmt-recovery-next-001/RUNTIME-001-FAILED.json`）及容量修订审查（外部历史/待归仓路径：`../../build/qmt-r8-owned-order-independent-001/capacity002/REPORT.md`）。

修订后显式五案5/5，unittest16.202秒、外层17.750秒；实际Node句柄PID56000与控制器一致、exit0，Job树0、双EOF、join、资源关闭，无强杀。171运行源前后SHA及实际module来源核同，两个owned案各九次账户读取、一次原线程insert替身、撤单0；所有实例正常Closed/delete，最终payload0/Pending0。见根运行结果（外部历史/待归仓路径：`../../build/qmt-recovery-next-001/RUNTIME-002-ROOT-VERIFIED.json`）。

| 场景 | Ready总持仓／未成交数量 | 消费实时成交后 | 正确最终未成交数量 | 实测解释 |
|---|---|---|---:|---|
| X04：P后成交，恢复O/D已含此成交 | 100／80 | 120／60 | 80 | 同一笔成交对已含成交的未成交数量再扣20，反例复现 |
| X05：恢复O/D后成交 | 100／100 | 120／80 | 80 | 增量控制符合预期 |

原X01仍120→140而来源120，X02/X03仍100→120。五案通过表示反例及控制符合期待，完整R8恢复、成交统计去重和生产资格均保持false；本次未修改WT框架或产品，没有真实券商下单/撤单。新动态独立复核（外部历史/待归仓路径：`../../build/qmt-r8-owned-order-independent-001/dynamic002/REPORT.md`）已通过，根核44份新增原件；33查询终态、494响应、15事件页及64模块身份一致。金融问题仍需修复。
