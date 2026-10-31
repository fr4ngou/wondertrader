# 订单查询恢复与原结果持有

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证记录。日期：2026-10-24。状态：R21Q限定开发验证与独立静态审查完成，标准候选受影响组合已重验；生产Factory及完整实时恢复未切换。

## 实际变更

[QST-R21Q](../specs/qmt-shm-trading.md#qst-r21q-当前订单查询观察恢复)和[ADR-0010](../architecture/adr/0010-order-query-communication-proof.md)复用原通信Journal：新真实ORDER查询的完整原结果与原委托关联同事务保存。查询request/result SHA/源行/B独立于历史event session/sequence；没有新callback时也能恢复已派发原委托的身份。历史GET不刷新来源，冲突保留。Common显式AccountQuery分支与P7已接通；WT EntrustID/UserTag保持原值，未增加金融账本、用户审批或框架接口。

撤单恢复当前限定原insert已sdk_returned且正常写通道可用。原unknown仍受已有新写关闭，查询身份恢复不能自动清除unknown；该状态下的受限撤单是完整后继未完成项。查询proof也不证明订单alive、撤单成功或持仓已吸收某笔成交。

read.finish在入域前冻结持久I/O截止；排队、Journal锁、SQL、关联行及commit共享该D，不延长SDK执行TTL。背压保存原结果/原D。已take结果先由预分配持有槽保存，再做解析和入域；解析、时钟或队列异常不把真实结果覆盖成中断。提交前超时回滚；commit已发生后晚返回仍保留实际结果且不ACK，按原ID核查。

## 已执行验证

Python003结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-query-proof-python-003/RESULT.json`）：239项，失败0、错误0、跳过0，18.969秒；当前输入前后无漂移，实际源码在同目录source-snapshot。覆盖查询恢复、旧关联/codec/运行时、账户投影、通信Journal、事件、HTTP、控制、实际共享内存运输及旧BoundReadJournal。新增恢复及期限23项包含无新callback、无历史event、旧GET、错账户/证券/broker、跨日同broker不同token、重启、提交失败/晚提交、入域背压、持有槽异常和关闭不续期。

隐藏控制器（外部历史/待归仓路径：`../../build/guanheng-workspace/account-runtime-install-001/build-qmt-query-proof-python-003/result.json`）实际exit0、nonforced、tree_zero、EOF、readers_joined及resources_closed；总20.516秒，未启动可见命令窗口，真实券商SDK调用0。

C++首轮七组结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-query-canonical-native-001/ctest-identity.log`）62.03秒全部通过，包含6个query-proof真实HTTP用例及P7两种datatype的6个查询来源场景；该轮属于映射器独审修正前输入，不授后继RAII最终资格。真实Host/SHM原query与Common proof对照及最终修正将由下一轮记录。

首次Python001的失败原件保留：无proof撤单503被误改409已修，错账户样本在源adapter提前拒绝而未触发Host边界已修为有限篡改结果；另缺目标metadata导致1跳过。Python002以明确metadata/许可证补齐235项全过；其后独审发现take→slot异常窗口，再修并以003重新验239项。旧失败/旧通过各自保持原输入范围。

## 剩余范围

独立审查与最终C++组合仍待封存；完整实时SPI、query/live交接、unknown受限撤单、跨进程消费恢复、正式安装/业务入口和生产发行未完成。通信表新增列的状态回退须在正式升级手册核实；本轮仅隔离测试数据库，未升级当前运行库、旧QMT工程或终端。

## 后继：最终原生组合

Native002八组（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-query-canonical-native-002/ctest-identity.log`）全部通过，60.72秒，来源前后无漂移；逐组日志（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-query-canonical-native-002/LastTest.log`）含Common六方法、P7十六方法/原73+新6身份场景及包含真实SHM联调的七方法测试组。实际SHM场景在原ORDER查询保存后，从Common重新lookup得到AccountQuery，query_request_id和result SHA与真实Host原记录一致、原行下标0，再成功create_cancel但不额外submit；原SDK替身insert/cancel各1次的既有断言保持。无历史event的恢复由独立Host事务及Common HTTP场景分别覆盖，不把此SHM场景的已有历史event隐藏成无event。

独立full（外部历史/待归仓路径：`../../build/qmt-query-recovery-contract-review-001/NOTES.md`）及槽修正delta（外部历史/待归仓路径：`../../build/qmt-query-recovery-contract-review-001/DELTA-001.md`）保留原P2并静态闭合，新增P1/P2=0、执行0/动态unknown；最终新增append CMake目标的组合影响另封存限定delta，根的源码回核按具体版本保留。新通信表列的状态回退约束已写入[国信维护手册](../runbooks/guosen-qmt-maintenance.md#订单查询关联的状态兼容)。

组合delta002（外部历史/待归仓路径：`../../build/qmt-query-recovery-contract-review-001/DELTA-002.md`）确认新增独立append CTest对R21Q无新增影响，原61来源保持；根以第二次62来源核对（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-query-recovery-final-001/REVIEW-ROOT-CHECK-002.json`）确认最终全部匹配。第一次核对的单CMake差异及所有旧审查原件继续保留。

## 后继：固定原版标准候选重建

fixed008（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-fixed-008/result.json`）用固定08b230上游原blob及最终自有源码重新构建175步骤。runtime007的12方法/13场景通过6.862秒；随后临时驱动仍引用不存在的owned-tests路径，后三场景未启动，原退出2记录保留。根核当轮147份Python夹具仍匹配，改用同一fixed008冻结测试文件，在runtime008（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-runtime-008/result.json`）只补跑3个真实SHM场景，18.814秒全部通过。未重编译或修改产品取得补跑结果。

合计同版DLL的15方法16场景；16份实际原件回核（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-query-recovery-final-001/STANDARD-CASES.json`）确认passed/closed/deleted/drained/joined，native SDK直调0。DLL SHA c02173107189df05f2628546b3ed7d7211a4f628ee0a1668db49c5a2bf709d92。上述仍为候选限定隔离范围；完整事件、query/live、unknown受限cancel和正式Factory没有因此完成。
