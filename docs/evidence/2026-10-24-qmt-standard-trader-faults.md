# 标准 TraderQMT 丢回复与未知结果验证

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。日期：2026-10-24。范围：[STQ-P9](../specs/native-qmt-standard-trader.md#stq-p9-标准插件接线与实施状态)标准候选的丢提交回复、SDK进入后未知及原回归。上述隔离场景通过；完整关闭故障、实时回报、恢复、正式入口与发行仍未完成，整体目标active。

## 实现与根因保护

本轮只增加标准原生探针（外部历史/待归仓路径：`../../tests/integration/qmt_standard_trader/standard_probe.cpp`）和真实共享内存测试（外部历史/待归仓路径：`../../tests/integration/qmt_standard_trader/test_standard_shm_trader.py`）中的异常场景。固定构建的全部src/*.cpp和src/*.h与前一fixed005输入相同，未新增产品修改或WT框架修改；原[正向记录](2026-10-24-qmt-standard-trader.md)保留。

交易请求已经到达源端后，网络回复丢失和SDK异常都无法证明委托未执行。测试核插件沿原通信UUID查询、至多一次POST、保留未知，并把账户读取与后继写入准入分别验证。WT原EntrustID/UserTag沿原样使用，内部UUID自动产生。

## 实际构建与运行

fixed006（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-fixed-006/result.json`）从固定上游08b230dd05facf6d650d949bfe51054115a2ecb1原Git blob及本轮冻结自有源码编译；没有使用当前工作树冻结的框架差异。runtime004（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-runtime-004/result.json`）共13方法14场景通过：原标准接口10方法11场景耗时3.361秒，真实Host/HMAC/Win32 SHM的3场景耗时19.375秒。

| 场景 | 实际结果 |
|---|---|
| 原正向insert→owned查询→cancel | SDK替身insert/cancel各1次；原WT身份及broker.1恢复，源ACK到3；WT实时事件消费仍为0 |
| 首次下单回复丢失 | 原Proxy读取Host完整2xx后在发送任何回复头之前断开一次；SDK替身insert/cancel各1，写POST恰2条且每原UUID一次，随后仅GET各自原UUID，正常查询与撤单完成 |
| SDK进入后抛异常 | SDK替身insert恰1、写POST恰1、原UUID GET64次有界结束；Host原记录unknown/sdk_entered/sdk_exception保留，插件pending=1，无成功或拒单委托回调，SubmissionUnknown错误回报1次，后继新写返回-2 |
| 未知后的账户读取 | 真account2.0/batch.v2/Core/P8链查询一次，余额137.25、可用19.5；原pending及UUID保持 |
| 未知后的关闭 | 原生API真实drain/join/delete；源沿首次close D关闭线程与I/O，同时handoff=false、source_unknown与原通信记录保持；Host正常关闭。资源关闭没有被记成交易结果已确认 |

全部真实券商SDK调用0。原标准Adapter单槽登录/四查询、线程/回调/超时、detach/stop、容量边界和已知拒单等原11场景保持并重跑通过。

## 原件、来源与独审

根逐项复核（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-fault-final-001/CASES.json`）检查14份实际native-result/fixture：子树正常回收、创建前Job归属、无强制退出/HTTP或清理错误；真实共享内存场景的源线程、Host、HTTP服务和资源分别检查。外层控制器tree0、双管道EOF、reader join和资源关闭均通过。所有旧fixture源码前后无漂移。

本轮DLL SHA256：d58a46a092abf1c2a1629e0cbb04bcb04b5bf92ebad75376074518d3cc673e96；探针：f33ea9736cde6276f20c0c16ac1edfd00cc3c232e67d65ac82ecfd4583bf7bc0。新测试的独立静态delta（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-fault-review-001/NOTES.md`）无未解决P1/P2；31来源根核（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-fault-final-001/REVIEW-ROOT-CHECK.json`）一致。Reviewer执行0，根实际运行分别提供对应证据。

## 剩余范围

关闭超时/晚HTTP回调/父死亡与容量交错的Standard完整矩阵仍待补。事件到onPushOrder/onPushTrade、查询/实时交接、同实例重连和跨进程未知恢复没有被本轮证明。pending=1在本地release前后保留，不宣称删除进程内对象后仍拥有同一内存收据；Host保留原通信事实，完整重启恢复另验。

生产Factory仍为旧ManagedTrader；正式切换、独立安装与搬迁、真实SDK非空字段、保留策略/观衡用户入口和最终发行继续。旧QMT工程仅静态参考，终端HTTP未使用，真实终端/账户/权限及生产实例未切换。当前没有新增需用户先解决的外部阻塞。
