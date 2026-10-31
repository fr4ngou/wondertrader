# QMT配置资源异常通道修正

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。日期：2026-10-25。状态：自有资源异常通道已实现，核心回归及10263个single故障点通过并独审；24个persistent代表点通过并独审。Standard补查接线及整体迁移仍未完成。

## 根因与正确实现

原DEAL begin-exception首批故障实际在point3发生：一次bad_alloc被纯profile校验转换为Backpressure，并再次分配诊断。直接身份入口保留该Status；Shm mapper和部分交易调用者还会通过.ok()/bool将其折叠为输入错误。实际48字节观察是仍活着的Status.reason，未认定泄漏。

纯profile校验现在原样传播bad_alloc，失败保持调用者descriptor原值；Identity的Query/Event/EventQuery在业务try内精确形成IoError/空reason。结构、绑定和显式容量Status保持，初始resolve holder尚未建立前的传播、旧非法句柄前置和双空边界继续保留。原委托receipt、未知结果、线程归属和绝对截止保持。修改限四个自有文件及[accepted资源契约](../specs/native-qmt-standard-events.md)，WT保护文件没有新增变化。

## 当前输入与范围

根实施清单（外部历史/待归仓路径：`../../build/qmt-profile-resource-channel-implementation-001/MANIFEST.json`）保存前后源码摘要。Common/Identity静态full审查的34份原件（外部历史/待归仓路径：`../../build/qmt-profile-resource-channel-independent-full-001/REPORT.md`）已由根重核。正式事件探针为004测试TU与资源修正产品组合，EXE SHA 7a1fa4e7999caaaa1664acaec8ad7fded2689d426b65474aafcc787f211f704c，167份Python运行源清单SHA 2ec4c467b42f4eb8b89767bb2b58e9b61aa1f729615b2335cef0cc8689ef4afd。

首批13目标和正式探针的资格分别绑定实际快照。正式探针168项编译链接完成；构建回执及首个核验入口错误保留，后继完整162自有/323原上游、cache、实际源码和同树no-work核验通过。工具原件说明（外部历史/待归仓路径：`../../build/qmt-profile-resource-channel-implementation-001/TOOL-ATTEMPTS.md`）记录这些失败，旧结果未覆盖。

## 核心实际验证

| 验证 | 实际结果 |
|---|---|
| 纯profile直接校验 | 实测N196，single196与persistent196全覆盖；每点精确bad_alloc、attempts=point、injection1、out/input不变、live0；12项结构/账户/容量负向保持 |
| 选行及Shm准入 | 五组3360断言，四路1592分配故障，翻译为runtime_error计数0；原金融值、数组、下标、引用和释放检查保持 |
| 旧链兼容 | Common19、Standard31、Retry9共59方法全部通过，0失败/错误/跳过 |
| 双来源新功能 | 38方法、77不同原生输入全部通过，逐案child/source及首错/cleanup事实正常 |
| 原失败八点 | 同输入1..8全部通过，含point3；当案重新测N1299 |

核心收据（外部历史/待归仓路径：`../../build/qmt-profile-resource-channel-implementation-001/CORE-QUALIFICATION.json`）关联十个通过的受控运行。它们均在原截止内正常退出，无强杀/控制台，创建期Job、tree0、双EOF、读线程join及资源关闭成立。独立核心动态复核（外部历史/待归仓路径：`../../build/qmt-profile-resource-independent-dynamic-001/REPORT.md`）与正式探针追加复核（外部历史/待归仓路径：`../../build/qmt-profile-resource-independent-dynamic-001/revision002/REPORT.md`）分别保其实际输入和范围。

## 全点与后继

正式新制品重新测得ORDER begin1889/resolve1941/finish0/begin-exception1331，DEAL begin1861/resolve1942/finish0/begin-exception1299，共10263点。finish0如实记录。根按新计划（外部历史/待归仓路径：`../../build/qmt-profile-resource-channel-implementation-001/ALLOCATION-SWEEP-PLAN.json`）和执行分片（外部历史/待归仓路径：`../../build/qmt-profile-resource-channel-implementation-001/ALLOCATION-SWEEP-SCHEDULE.json`）逐点执行：复用已通过八点，余下21批每批最多64片、每片最多8点，失败即停；最终须跨批核无缺口和重复后才授有限全集。当前进行中。

这些测试覆盖预热后的实际global C++ new路径；冷池增长、物理allocator/系统/CNG内存失败、Standard C、首次/重连交接和真实SDK仍未取得完整资格。真实SDK调用0，生产入口未切换。C的实际类型尺寸、HTTP和查询长度边界已有后继研究，普通mapper检查前峰值及并存银行继续收敛。整体目标保持进行中。

## 全点及持续故障代表场景后继

正式资源修正制品的21批已全部正常退出。根以原计划、原八点和每片fixture/input/result逐项核对，1286片、10263个不同single点精确覆盖六条非零route的1..N，无重复或缺口；两条finish的N=0保持。每点attempts等于point、injection=1、live=0、引用恢复且排空，resolve前两点的holder传播边界单独核实。根读取3946份原件，控制器原D/创建期Job/tree0/双EOF/join/资源关闭均成立，见全点收据（外部历史/待归仓路径：`../../build/qmt-profile-resource-channel-implementation-001/SINGLE-ALLOCATION-QUALIFICATION.json`）。独立全点复核正在封存最终报告。

另用同一制品对六条非零route各选1、2、3、N，共24个persistent代表点，全部通过并正常回收；根核76份原件，见代表点收据（外部历史/待归仓路径：`../../build/qmt-profile-resource-channel-implementation-001/PERSISTENT-ALLOCATION-QUALIFICATION.json`）。这24点属于抽样，完整persistent全集、冷池增长与系统/物理allocator失败保持未验。此前直接profile校验196个persistent全点的资格只覆盖纯profile入口。

核心独审原件根核（外部历史/待归仓路径：`../../build/qmt-profile-resource-channel-implementation-001/INDEPENDENT-DYNAMIC-CORE-ROOT-VERIFIED.json`）逐份重读1500+432份raw与实际来源及兼容工具13份清单。源端SDK调用0、生产未切换；Standard实际缺字段补查接线及R8首次/重连仍未完成。C合同继续用真实对象所有权和逐阶段峰值收敛，不把这轮10263点通过扩大成整链完成。

## 最终独审与根原件复核

single独立delta（外部历史/待归仓路径：`../../build/qmt-profile-resource-independent-dynamic-001/revision003/REPORT.md`）逐核1286片与10263点，根重新读取4636份raw及实际来源全部同SHA，见根收据（外部历史/待归仓路径：`../../build/qmt-profile-resource-channel-implementation-001/INDEPENDENT-SINGLE-ROOT-VERIFIED.json`）。persistent独立delta（外部历史/待归仓路径：`../../build/qmt-profile-resource-independent-dynamic-001/revision004/REPORT.md`）逐核24个代表点与真实收尾，根重核453份raw及来源同SHA，见根收据（外部历史/待归仓路径：`../../build/qmt-profile-resource-channel-implementation-001/INDEPENDENT-PERSISTENT-ROOT-VERIFIED.json`）。两份独审均无新增问题，资格保持上述有限输入及抽样边界。
