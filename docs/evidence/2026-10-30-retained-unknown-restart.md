# 唯一策略未知提交后的原身份与同根拒绝

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B隔离验证证据。日期：2026-10-30。状态：Host存续的Native重启拒绝已验证；Host/Source整体重启、未知责任解除、稳定关闭及完整模块继续。要求：[NRT-R27](../specs/native-realtime-strategy.md#nrt-r27-未知提交后的原身份与同根重启拒绝)、[B-06](../migration/module-b-delivery.md)及STQ-P21。全部新增运行、临时文件、缓存及制品在E盘。

## 原生复用与实际主链

本轮产品与WT源码修改0。正式普通WT 0.1.0a3六发行沿A的`build/wt-account-publication-composition-001/installation001`，730条hashed RECORD逐项核对；原生沿R23 native002，12份生产源及各案23项安装文件保持原BUILD摘要。Runtime SHA `68d7c415837556ff7c3e2d180250dfb1e98c4d3051a0fd4133a9e4f5a3f1d86f`，股票工厂SHA `8e0721f3c2d54621468a02fa6cf3a63640f7ec9218e7a2116bcfe8af5860a131`。当前行情、历史、账户和SDK明确为合成替身。

实际入口为安装WRI CLI→原唯一1.1.2/Factory/CTA/NSQ→原股票执行器/Adapter→WinSHM→SDK替身。首代已有510050及510300各200股，唯一核产生510050退出目标，源SDK卖200股入口实际进入一次后抛出明确合成异常；没有制造成交回报或改变券商持仓。原Source和Host/Journal将同一命令记为unknown，保留command_id、命令原文摘要、command_sha256及result_sha256。

首代停止在recovery_drain失败，clean未发布。第二代保留同一Host、Journal、账户配置及金融目录，仅将原recovery.mode改为resume_clean，通过正式WRI再次启动。新Standard实例先完成四查询；原clean缺失在CTA准入拒绝，未进入策略运行。原命令仍为unknown，SDK和POST均没有增加，原金融文件逐项摘要保持。Host和Source的未知围栏继续存在。新Standard内存中的责任计数不能代替Host保留的旧责任；本次以原Journal和原生拒绝分别取证。

## 原件、失败与资格

根为`build/ms-unknown-restart-001`。FROZEN-SOURCES-001（外部历史/待归仓路径：`../../build/ms-unknown-restart-001/FROZEN-SOURCES-001.json`）绑定每案实际12份QA原字节副本、12份未改生产源、三份177项运输快照及普通安装。三案合计27次SDK替身只读查询、3次合成SDK入口、真实下撤单0。

| 原件 | 实际结果 |
|---|---|
| main001 / RUN001 | 原unknown及第二代拒绝均已发生；QA预期在trader阶段拒绝，实际原实现为cta，因此整体失败保留。首代关闭捕获c0005，物理回收完整 |
| main002 / RUN002 | 同根原身份保持及拒绝断言通过，9查询/SDK1；旧通用RESULT误把未知卖出写成sold_sh50=200，该字段资格撤回，原RESULT保持。专用UNKNOWN-RESTART证明的SDK1/原命令/原持仓200及拒绝事实有效 |
| main003 / RUN003 | 最终QA整链通过，9查询/SDK1，sold_sh50=null，原券商两证券仍各200；第二代新增SDK0/POST0，原三份金融JSON保持、无clean，两代均按预期运行失败并完整物理回收 |

最终UNKNOWN-RESTART-001（外部历史/待归仓路径：`../../build/ms-unknown-restart-001/main-003/UNKNOWN-RESTART-001.json`）明确只授“未知责任保持及重启拒绝”资格，未知命令未解除。首代执行PID37004、第二代执行PID4872；对应WRI启动器PID52296/45024的OS退出码均为2。外层QA PID24304实际exit0，表示预期失败合同验证完成；WT Python自身独立OS退出码没有另行归档，启动器退出码保持其本来角色。

三案的Source/Host/Reader/HTTP代理与每层Job、stdout/stderr EOF、reader join及句柄回收均完整。main001/003记录了0xc0000005，main002没有该异常；0xe06d7363为捕获到的C++异常事件，业务失败阶段按原failure.json分别记录。两次新AV保留现场，本轮未另行推断其首次释放历史或声称已修复。既有[股票引用最小提案](../migration/native-stock-metadata-ownership-proposal.md)保持未批准、未应用、未编译。

## 实现边界与继续项

QA只增加显式unknown-restart场景、同根第二代验证和失败目录的明确stage参数，原可卖摘要拒绝默认仍为cta。未知场景复用原unknown_stop异常类型及调用追踪，源端未知处理沿原实现。历史R26包及物理冻结源保持；本轮QA后继按自己的摘要与审查核验，不追授旧报告给新源码。

原Host/Journal保留期间，重启原生执行进程的保守边界已有实际证据。完整B-06仍要求Host/Source整体重启后的原身份核查、异常后的继续处理与准确准入；本轮没有重建空状态、清理unknown或换命令身份重发。稳定关闭、跨日T+1、全周期BT/RT与统一候选继续。独立审查、归档成员及最终SHA沿本根后继交付收据登记。
