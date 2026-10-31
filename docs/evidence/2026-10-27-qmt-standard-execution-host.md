# 标准执行宿主主链与安装消费

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证记录。日期：2026-10-27。状态：自有C++执行宿主完成限定装配、SDK替身主链及安装头消费；正式CTA策略宿主与整体迁移继续。要求为[STQ-P14](../specs/native-qmt-standard-trader.md#stq-p14-标准执行宿主装配accepted开发中)，操作见[接入手册](../runbooks/qmt-standard-execution-host.md)。

## 问题与实现

此前原执行管理器、查询接线与线程桥能在探针装配，正式产品缺少统一拥有Adapter、Local、桥和插件关闭顺序的自有组件。新增StandardExecutionHost统一配置准入、owner推进、原表查询及生命周期，原算法及订单/持仓事实保持原职责。CMake产品库纳入Host，安装公开头。普通native装配保持，显式query_first/position_by_query/poolsize=0才选择新组件。

生命周期和账户读取由创建线程独占；生产者只交付有界值，共享桥以原子方式发布。request_stop可跨线程关目标准入，原owner close核桥无在途、detach SPI、原Standard worker关闭并join/drain，再原deleteTrader确认API置空。未确认时保留Impl及借用依赖至进程结束，不热卸载或自动重发委托。

本轮没有新增WT核心修改。工作区两份TraderAdapter SHA分别32e2efdb9ce445c23c5d8d876a32f7e6f755acd695cb6736c7ef3004322dfc31、cc3b2d79f764ab0bd1ccd35e3d0b2bcb0e010d5595801642da74a0658739645d，与此前已批准订单方案身份相同。

## 实际主链

原WtExecuterMgr→策略生产线程目标/行情→实际StandardExecutionHost→owner drain→原MinImpact/Local/Adapter→正式Standard DLL→实际Host/Win32共享内存→SDK替身。两个场景均经过四轮目标200和价格10.01，原行情对象随后改值并释放，owner仍用队列独立值执行。

| 场景 | 四轮实际新增委托 | 来源持仓 | 来源订单余量 | SDK查询 | 关闭 |
|---|---|---:|---:|---:|---|
| 查询空订单 | 1,0,0,0 | 100 | 0 | 8 | API删除、worker join/drain |
| 查询活动订单 | 1,0,0,0 | 100 | 80 | 8 | API删除、worker join/drain |

两案均验证配置拒绝发生在插件创建前、重复initialize拒绝、非owner pump/query/read/close拒绝且owner状态保留、跨线程request_stop、重复close、销毁Host后原管理器迟到目标被桥拒绝。每案原表查询订单数0/1与来源一致，队列交付8、载荷归零。真实委托/撤单0；替身每案insert1/cancel0，独立fixture按实际调用计数核对。

新构建的既有五案也通过：native空订单产生4次替身insert；query_first空/活动订单各1次；全成两轮P100→200→300、部成部撤P100→120→140各2次。原默认路径及连续下一轮主行为保持。

## 编译和安装

固定原上游加批准覆盖343份、自有固定输入255份全部摘要核对。实际工程cmake/native/qmt_standard_product使用MSVC x64/C++17及原锁定依赖，构建GuanhengStandardTrader、GuanhengBrokerContextMain、GuanhengExecutionOwnerMain、GuanhengExecutionHostMain。生成物SHA见BUILD-RESULT（外部历史/待归仓路径：`../../build/sp-006/BUILD-RESULT.json`）。

独立静态审查发现StandardExecutionHost.h包含StandardQmtTrader.h但原install遗漏，现加入安装。首次实际install暴露Windows原生反斜杠root使生成安装脚本出现Invalid character escape；已在自有CMake入口统一两个固定root为CMake路径，未改上游。失败日志保留（外部历史/待归仓路径：`../../build/sp-006/FAILED-INSTALL.log`），该次结果保持失败。

后继在全新install-002成功安装DLL、静态库、6份自有公开头和来源manifest；GuanhengInstalledHostHeaders实际仅从install-002/include取得自有头，附固定原SDK及锁定依赖编译成功。构建规则中不存在owned/src自有include；安装结果（外部历史/待归仓路径：`../../build/sp-006/INSTALL-RESULT.json`）保留实际include行及产物摘要。该结果证明公开头完整消费，完整独立应用链接/发行另验。

## 身份、审查与资源

POSTFLIGHT（外部历史/待归仓路径：`../../build/sp-006/POSTFLIGHT.json`）保存10个受控root、固定/自有输入、运行夹具、产物及源码身份；成功root实际exit0，首次install及首次文档链接检查root实际exit2，后继均修正通过。全部在各自原预算内停止，未强杀，整树归零、EOF、reader join及资源关闭核对通过。全部后台无控制台创建；未操作QMT策略、真实账户或生产实例。

自有快照沿此前候选，保留工作区9处未纳入差异（含一份当前缺失测试CMake），不以此声明整个工作区已验收。Python运行夹具明确使用本仓当前入口，三份主入口摘要与此前一致；未导入/运行旧QMT工程。

独立full静态审查complete，发现的安装头gap修正；root路径归一delta complete。审查者仅读最终规格、规则与源码，未读任务/历史/运行报告，未执行测试。实际审查身份匹配，见REVIEW（外部历史/待归仓路径：`../../build/sp-006/REVIEW.json`）。

## 范围与下一步

本次完成可复用执行宿主组件；主链时钟由固定HostStub提供，仅用于替身验收。正式CTA时钟/元数据、行情、策略状态与运行入口尚须装配，既有只读RealtimeBridge的空交易限制保持。stop与真实在途drain竞争、回调重入close、未确认关闭的原截止及进程回收、完整插件初始化失败收口尚未动态触发；这些状态保留未验。

真实常驻两代连接、查询/回报完整交接和跨进程恢复、历史全库存/尾部及在线质量协议、观衡独立发行仍未完成，整体目标active。python -B scripts/project.py check已通过（本地文档导航及技能清单完整性）；首轮手册引用不存在runtime.md已更正到实际常驻连接模块，原失败记录保持。当前无需用户决策或操作；继续推进整体运行主路径。
