# 同账户多策略统一执行装配

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证记录。日期：2026-10-28。结果：限定开发链pass；完整生产接线pending-verification。要求：[STQ-P17](../specs/native-qmt-standard-trader.md#stq-p17-同账户多策略固定集合accepted开发中)。评估及边界：[专项方案](../migration/multi-strategy-account-ownership.md)。

## 根因与正确实现

自有CtaExecutionSession原先只装配一个策略。每策略独立执行器会把自身目标与同一券商总仓比较，产生争抢。新增固定集合复用同一原WtCtaEngine、逐策略CtaStraContext及唯一执行桥/交易owner；原WtExecuterMgr继续按标的求和。券商完整持仓/订单查询及Standard未知命令责任保持，无新金融账本及WT核心行为修改。

集合逐项接管策略、工厂及独立参数，1..64项，Windows文件身份无冲突。先完成全部策略init，再核冻结ID及创建原上下文。关闭在停止原生产者后逐项factory删除，每项最多尝试一次；pending保留整个依赖树。原单策略入口继续可用。

## 输入与方法

构建使用sp-008原已批准快照（外部历史/待归仓路径：`../../build/sp-008/APPROVED-SOURCE-AUDIT.json`），固定上游08b230dd05facf6d650d949bfe51054115a2ecb1加既有批准查询/NCS覆盖。609份输入逐文件校验，新差异仅5份自有源码/测试，见最终根核（外部历史/待归仓路径：`../../build/ms-account-001/POSTFLIGHT.json`）。编译器MSVC x64 14.51.36231，C++17，Release，CMake/Ninja沿既有工具链，依赖复用原锁定build/native/deps。

最终构建（外部历史/待归仓路径：`../../build/ms-account-001/BUILD-final.json`）绑定Session.h/.cpp、原生驱动及Python夹具摘要和二进制；输入清单（外部历史/待归仓路径：`../../build/ms-account-001/composed/input.json`）绑定全部源码。原生源码通过自有CMake工程编译，核心与算法取同一固定来源。未提交共享checkout只按本切片文件取身份，其他改动保持原状。

验证入口为tests/integration/qmt_cta_execution/run.py，显式exe/dll/factory/parser/reader/output与deadline-uptime-ms；--portfolio选择add/exit/net/pending，--session-case选择六项生命周期场景，--configuration-case risk-object核既有配置拒绝。实际原ticker闭合分钟驱动策略，未手调schedule。测试以创建期Job、有界隐藏driver及同次进程树回收执行；每案真实Host/Win32 SHM连接明确SDK替身，来源/Reader/行情均为合成输入。

合成资金余额及可用资金30000元，足额覆盖1000股×10.01元主路径；原单策略夹具保持既有数据。行情日期为显式注入的2026-10-29，SDK/执行模拟日为2026-10-22；该时钟组合只证明组件业务流转，不授真实交易日/T+1资格。

## 业务与边界结果

最终矩阵（外部历史/待归仓路径：`../../build/ms-account-001/FINAL.json`）和逐案根核（外部历史/待归仓路径：`../../build/ms-account-001/POSTFLIGHT.json`）保存12案结果；最终运行目录为final-*-002，早期001保留为开发过程原件。

| 场景 | 实际观察 |
|---|---|
| A600+B400，实际仓0 | 两策略原初始化/调度各1轮，共一个SDK替身买1000股请求 |
| 实际仓1000，A600→0，B400保持 | 共一个卖600股请求；两策略原JSON分别保留0/400目标 |
| A600→800、B400→200 | 实际仓1000，SDK替身提交0，原JSON分别800/200 |
| 实际仓600，总目标1000 | 买400后完整ORDER查询返回未成400；新tick及相同总目标未产生重复提交 |
| 原单策略 | 目标200/实际100，保持一次买100请求、8查询与完整关闭 |
| 原策略init失败、init改ID | 均按Initialize拒绝，全部2策略删除、0委托，完整关闭 |
| 对多策略调用旧参数入口、已有状态根 | 按Configuration在行情插件加载前拒绝，原已有文件保留，2策略删除 |
| 第二策略delete false或throw | 第一策略只删除一次，第二策略只尝试一次；再次close为pending，停止新执行并保留依赖至专属测试进程退出 |
| 原riskmon错误类型 | Ready账户下按Configuration拒绝，0委托、原单策略/API删除 |

每案还执行12项构造/占用准入检查：空/超限集合、空指针/工厂、重复指针、大小写冲突、参数错误类型、非法/设备名/尾点以及第二Session。构造拒绝后调用方仍能按原factory删除；独立参数通过各策略600/400等不等目标及原JSON回读验证。

四个组合与原单策略均确认Parser在途0、Reader/策略删除及API脱离；删除失败两案明确保持closed=false，进程退出后外层确认整树回收及EOF。12案子进程均exit0、无forced，所有Host/Agent/代理/服务器资源确认关闭。实际券商调用0，无真实撤单或生产切换。

## 审查与安装

独立full/delta审查（外部历史/待归仓路径：`../../build/ms-account-001/REVIEW.json`）发现并关闭F1：策略init可改写名称绕过构造校验。修正为冻结ID及全部init后的统一复核，最终delta确认全部P17要求影响范围，无新增静态问题；改名拒绝实际案通过。静态审查与上文运行证据分别成立。

实际安装（外部历史/待归仓路径：`../../build/ms-account-001/INSTALL.json`）生成原可选产品库及公共头；安装后的CtaExecutionSession.h与当前源码逐字节一致，仅以安装自有头及原WT SDK编译消费端，并静态核多策略构造可用。该安装仍须匹配原WT SDK/ABI，不构成完整独立发行包。project.py check通过仅证明文档导航及技能清单完整性。

## 剩余风险与下一动作

本切片确认固定集合统一汇总及显式拒绝/保留边界。策略原JSON仍采用WT文件格式；当前已有根拒绝保护不等于跨进程恢复完成。下一步是生产宿主的同账户唯一装配、原JSON/执行目标及未决命令交接恢复、实际业务预算/可用资金/T+1约束与真实连续来源验真。

同标的手工持仓会被账户总目标影响；外部订单未进入当前本通道执行订单表，原MinImpact就绪时会尝试取消未监控挂单。混用需明确人工归属及取消策略，再提出必要适配；需要新增框架行为时沿现有批准规则办理。未以本次SDK替身证明共享资金不足拒绝、跨进程锁、真实成交分派或实际账户变为目标数量。整体迁移继续active，行情来源时延继续由原迁移对话负责。
