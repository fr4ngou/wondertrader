# 合法读取等待的提交组准入根因修正

类型：自有执行模块验证。日期：2026-11-06。范围：NRT-R32/R33与原Standard→QueryFirstSubmission→OwnerExecCommand主链。当前源码主链及根因回放通过；正式完整构建、恢复和真实运行分别登记。

## 原条件与根因

真实控制代1fc40dc8-8f1a-4e78-a5f1-d82d8c0b614a在10:59:42退出，原failure记录Host Queue(4)、Session Execution(4)、plugin SubmissionUnknown(9)、空reason摘要；原read-status保存waiting=true、writes_blocked=true。最后业务日志为Order placing failed:-2。原failure缺桥细节，历史queuefault数值无法从该文件直接回读。

实际原Standard方法回放已精确产生Destination(6)：read_waiting时inspect/begin未检查该状态，放行提交组；orderInsert→enqueue复用permits时拒绝相同状态并返回-2，submission.failed置位；end_submission据此锁存SubmissionUnknown并清空reason，QueryFirstSubmission抛SubmissionEndFailure，Owner桥转Destination，Host再转Queue。原真实日志、只读等待和错误类别与这条因果链吻合。Root另核原通信记录全部SDK已返回且本次失败没有新增Host命令；通信处置与实际成交仍由Root原身份核查，不能由plugin_error9推定真实SDK未知。

## 统一实现

仅自有StandardQmtTrader.cpp的提交组inspect/begin改为复用原permits(Insert)写许可，保留writes_blocked及原未决子责任检查。read_waiting先返回BlockedAwait，既不创建组，也不进入原insert。原permits、委托/收口、Owner桥故障分类和WT框架均保持。真实unknown继续按原UUID/收据保护，修正不把未知强设成功。

## 实际回放

`tests/integration/qmt_broker_context/run_read_wait_submission.py`链接ef5已核同源码Common/映射对象及WTSTools/WTSUtils，当前Standard及Owner桥独立重新编译。每个复用对象对应.cpp及全部自有依赖头与原构建快照逐项同SHA；owned/upstream完整冻结快照在编译前后核验，编译include不含当前ROOT，结果仅记录实际stage字节；RESULT.json保存对象、库、源码和命令身份。既有GH_QMT_STANDARD_AUDIT_TESTING friend仅供测试TU设置冻结状态，生产代码无新测试字段/导出；原API、QueryFirstSubmission、原组收口及Owner drain实际执行。无worker、网络、Host、Source SDK或金融文件写入。

- 红：`build/read-wait-red-003/RESULT.json`，固定ef5原Standard源码，insert_result=-2、queue_fault=6、awaiting由1降0、plugin_error=9，delegate恰1次。
- 绿：`build/read-wait-green-004/RESULT.json`，当前Standard，queue_fault=0、awaiting保持1、plugin_error=0，等待期delegate/insert均0。
- 原observation_refresh_applied完成后继P阶段后，下一目标恰创建1个子身份；重复同目标不创建第二个身份。
- 真实unknown形态的原entrust/group777/UUID/原收据及unknown_fenced全部保留，SDK委派0。
- 独立容量、过期和Destination异常仍分别锁存原Capacity/Expired/Destination；默认native门的直接委派保持。

独立full源码审查确认产品修复符合R32，发现复用对象头文件身份及inspect动态覆盖缺口；测试已改为只使用完整已核冻结include闭包，37个自有依赖头逐件匹配，26个复用对象/库逐件记录SHA，摘要取实际stage。probe另直接调用inspect_submission验证BlockedAwait。随后delta复核standards/spec均complete，剩余可行动项0；Reviewer未独立运行C++，实际运行结果由上述红绿RESULT证明。

复现命令：anchor Python执行该driver，提供`--build <ef5固定构建>`和全新`--work`；红例追加`--baseline`。测试入口保留来源和实际二进制身份，完整Native制品由Root沿execution_product.py统一构建。

## 限制与后续

本回放直接验证原Standard/提交门/Owner桥，不启动真实Source，也未重新部署。Root负责CtaProcess追加数值白名单execution_queue和plugin_state诊断、原通信身份与实际成交核查以及正式同账恢复。完整构建须采用更新的owned_standard_source_sha256；既有金融账、NSQ目标、资本基准、未知命令和来源收据保持。发现原独立硬故障时仍按原错误退出，修正只收敛合法只读等待的准入不一致。
