# 2026-11-01 未知委托核清后的WT执行连续性

类型：模块B隔离开发证据。结果：限定主链pass；整个模块继续in-progress。关联[NRT-R32](../specs/native-realtime-strategy.md#nrt-r32-原命令待核查期间的执行连续性)、[UC](../specs/qmt-unknown-cancel.md)及[C++契约](../specs/qmt-unknown-cancel-cpp.md)。本轮只使用SDK替身，真实QMT按用户要求保持关闭。

## 根因与最终行为

自有宿主原先把提交结果未知作为致命错误，提前结束策略运行；接入层也一直保留未知等待，即使后来已有原命令结果或券商终态事实。另在首次写回复后，完整request_ms被再次用作首次核查前的等待，可能阻断原八秒后继目标窗口。

最终实现只修改自有接入：query_first的纯待核查保持原查询、行情和目标队列，首次立即安排原ID只读审计，后继间隔及原请求截止保持。合法passorder返回None继续记录sdk_returned；SDK实际进入后异常的原记录继续保持unknown。Source仅消费原线程完整ORDER投影，Host仅消费原Journal已保存且重新验证的查询证明；完整token、账户、证券、方向、原数量、限价及券商订单号唯一一致并为终态，才退休相应通信等待。空结果、活动/部分成交、重复或冲突字段继续保留等待，硬故障与关闭保持独立。

Common私有重核分为审计期取得服务端独立终态资格和全部原组O→P退休后新insert前重核两个时点。原WT实际消费完整O及后继同源P后才退休原组，不使用成交量另算持仓。原UUID、原文、SDK阶段和截止保持；未知cancel继续原保护。原生账本、费用、绩效、算法及WT核心行为保持原归属。

## 固定构建与普通安装

- 独立E盘分离源码目录：`build/uc-src1`。候选构建阶段保持原默认配方，既有运行安装始终保持；候选配方只更新已审Standard源码身份，原固定WT及19个已有覆盖文件保持。源码交接同步该身份与两项Python版本，默认运行行为保持。
- 原永久构建器全新构建：`build/uc-src1/build/clean-001/RESULT.json`。外Job `build/ms-sdk-unknown-fresh-native-job-001/RUN.json`：PID69760、OS0、562.780秒；旧项目obj/lib输入0，25个安装成员，五个产品组件同批重编，树/管道/reader/资源全部关闭。
- Source/Host/Agent永久源码wheel：`build/uc-src1/build/source-001/BUILD.json`。Host为`0.1.0a22+mdphttp.3.tes.1.uc.1`，Agent为`0.1.0a12+marketdaily.4.uc.1`，Host精确依赖同代Agent。构建器额外生成的Core wheel不替换本轮已固定的Core运行依赖。
- 新venv从原固定WT角色的23个wheel中只替换上述两项，按SHA锁离线普通安装、依赖检查及独立导入通过：`build/ms-sdk-unknown-fresh-install-002/RESULT.json`。外PID29308、OS0、22.268秒。安装与运行均使用新E盘目录。
- Native组件素材ZIP及23依赖wheel素材ZIP沿`build/ms-unknown-continuity-delivery-001/ARTIFACTS-001.json`，与完整系统发行分别登记；集成者复用既有角色安装与组合入口。

## 新安装的实际主链

| 场景 | 原委托事实与实际继续 | 正常回收 |
| --- | --- | --- |
| SDK实际接受1000股后抛异常 | 原Journal仍为unknown/sdk_exception，原UUID查询和完整终态ORDER核清，WT消费O/P后实际再买200股，原1000股不重发 | `ms-sdk-unknown-fresh-main-001`，外PID1692、OS0、17.511秒 |
| 首笔POST回复真正截断 | SDK合法返回None，原记录sdk_returned，声明长度大于实际回复长度；原UUID GET核实，WT消费O/P后实际再买200股 | `ms-sdk-unknown-fresh-transport-main-001`，外PID36616、OS0、23.905秒 |

两案均使用同一全新Native安装与新普通venv，SDK替身调用为原线程的1000、200各一次；最终A800/B400、券商与WT持仓1200，额外订单0。Host、Source、服务器、代理、Native及外层Job正常关闭。运行中实际加载WT/Host/Agent，guanheng_app命名空间未加载。QA将冻结夹具中的旧App导入引用适配为独立WT模块，保留实际算法/数量/原请求预算及原业务断言，转换前后AST材料分别封存；产品代码不依赖该适配。

原request_ms8000及HTTP2000毫秒保持。快路径未单独采到长时间等待窗口，actual_unknown_wait_observed准确保留false。直接核验与源码/原件SHA沿`build/ms-unknown-continuity-final-proof-001/POSTFLIGHT-001.json`；Root另已直接核24原件、原SQLite命令阶段、WT持仓及O→P→200差额顺序，接收记录为`build/root-unknown-recovery-business-intake-001/INTERFACE-001.json`。

## 相关回归、复审及修正

155项Source/Host/原订单查询及账户投影回归通过，包含缺失、活动/部分成交、重复/字段冲突保持未知和后继硬故障保持阻写。真实Common HTTP红绿对照核到旧helper将503、原D超时和来源漂移改写为SubmissionUnknown；修正后原Status保持，意外异常锁存固定IoError。七个场景分别覆盖成功、仍未知、硬错、关闭及上述三种失败，原D和回调回收保持，SDK0。结果沿`build/ms-observation-status-baseline-test-001/RESULT.json`与`build/ms-observation-status-candidate-test-003/RESULT.json`。

同cohort实际sizeof为交易Core392、账户Impl616及两份HTTP Impl各752字节。预算原384/608/744×2统一更新为上述实测值，固定银行增加32字节；QmtHttpConfig120及交易Core392设编译期布局保护。sizeof测量只在专用QA复制源码的构造器中读取，产品BoundedSignedHttp/BoundRead源码保持；不新增运行账本。

首full复审的原件及开放P2保留：`build/ms-sdk-unknown-order-protocol-review-001/REVIEW-001.json`和`build/ms-sdk-unknown-order-execution-review-001/REVIEW-001.json`。错误分类、friend调用时点、UC/CPP说明和布局资格已据实际证据修正；最终delta及固定源码/制品绑定以本次交接的独立报告为准。Root工作树文档检查发现此前未索引的旧证据文件；相同三份当前规格在独立工作树执行`project.py check`通过，外PID65780、OS0、4.196秒，不清理其他任务的旧原件。

历史失败另行保留：SDK新主链001的业务已完成，但QA将指定注入异常计入首错；后继仅按相同异常对象和source.insert过滤指定注入，其余错误继续原捕获。003的八秒后继目标未达到，源/Host已在约0.3秒核清，但首审计等待request_ms；修正首次安排后保留原窗口通过。前期临时增量构建和既有对象树只授各自开发资格，全新构建与当前两案分别取得新资格。

## 复用边界与剩余工作

旧正式1.1.2的53笔SDK/订单/成交、原金融目录011及Root新组合的同根正常恢复继续保留其原安装身份与范围。按Root要求不重复53笔；算法、WT金融实现及正常路径未改，历史事实作为回归基线复用，当前新制品的新增资格由上述两条实际主链证明。

正式1.1.2携带活动/部分未成交委托，跨进程恢复原金融/KV/数量阶段、识别原单并由原入口取消的完整主链仍未闭合。此前三案Standard冷查询/定向取消只授该有限层，不能替代正式CTA状态恢复。本次增量可先交Root明确文件清单合入；整体模块goal继续，随后完成该实际缺口。原独占金融目录、既有安装及真实账户保持，真实交易与生产切换沿原明确授权执行。
