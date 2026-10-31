# 认证续接后新增回报与未知命令的整套恢复

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B验证证据。状态：STQ-P25-C3的诊断副本主链通过，独立审查和正式安装资格分别登记。依据：[原事件续接规格](../specs/native-qmt-standard-trader.md#stq-p25-整套重启后的事件认证续接proposed隔离验证中)、[原故障修复](2026-10-30-native-event-auth-recovery.md)。新增文件、运行、缓存及临时目录全部位于E盘。

## 输入与实现身份

复用原已审Common/Host续接候选、SCMR批准制品、唯一正式策略`resonance-regime-v1@1.1.2`、原七组件QA及同一Source业务service。两个验证根分别为`build/ms-seven-suffix-001`、`build/ms-seven-unknown-001`；原QA、原安装及上一轮封存原件保持。

本轮生产实现改动为0。首版独占DLL在原`advance_event`成功后同步写文件，独审指出该观察可能延长原事件锁持有。后继observer003（外部历史/待归仓路径：`../../build/ms-seven-suffix-001/native-observation-003/BUILD.json`）移除Native文件IO，改为三个固定宽度的进程内整数，原成功advance后最后发布handled；QA只读取得自有Native的12字节并存证。该观察限定本次序号3/4，无通用64位游标或多字段原子快照资格，全部诊断观察均未进入公共发行。原Common与Host的[公共合入](2026-10-30-event-continuity-public-integration.md)由A负责，其后续普通wheel/Native安装、搬迁与统一主链继续沿原交接推进。

所有Native/业务子进程从原`scripts/native.py::run`有限Job进入，保留原生产请求、交易和关闭截止；外层QA为420秒、Job为430秒。私有QA、运行日志、SDK原件及通信SQLite留在受控验证目录；本文及交接只输出枚举、计数、文件摘要和限定验证结果。

## 新认证连接的事件后缀

RUN-005（外部历史/待归仓路径：`../../build/ms-seven-suffix-001/RUN-005.json`）及业务复核（外部历史/待归仓路径：`../../build/ms-seven-suffix-001/BUSINESS-WITNESS-001.json`）完成约203.830秒的整条调用链：首代七组件运行、唯一策略卖出200份、账户发布、观衡关闭期间WT继续、整个WT正常停止、同Source/Journal/金融根恢复、第二代认证后由原策略线程再次上报同一委托和成交、后继策略计算、第二代完整关闭及最终只读观衡重开。

新增回报分配运输序号3/4，原序号1/2保持。关闭后以SQLite `mode=ro&immutable=1`复核，读前后SHA相同：两组事件除sequence外的整个原始正文相同；序号1/2按原连接区间证明，序号3/4按第二认证连接证明；创世binding保持，两代当前binding不同。最终durable、ACK intended、source ACK、published均为4。

独占观察确认第二代Native PID62900实际消费`3/4`、`4/4`。验证按当前实际PID过滤此前运行的观察行，再推进原行情Reader至下一分钟：原策略序号达到4，原券商观察和原生持仓观察均为200份；SDK调用、源委托及源成交记录仍各1。没有使用Host已ACK来替代Native消费证据，也没有新增成交分摊账本。

24条保留交易查询均terminal/ok，P9/O9/D2/A4。两代WT、三次观衡和Source全部exit0；14份成功关闭收据包含两份execution.closed.v2及两份WRI关闭证明。原安装3885文件和全部冻结输入摘要保持，外层73628退出0，树归零、管道EOF、reader join及句柄回收齐全。真实QMT与浏览器操作分别保留原资格边界。

`RUN-004`先通过同一后缀消费及正常关闭。005补充当前Native PID绑定与消费后的正式策略计算、券商/原生数量观察。此前001准备期缩进错误，002/003在启动状态暂不可读时退出，均保留失败。004起对初始状态调用原有有界读取等待，产品状态发布和截止保持。

## 内存观察后的完整后继

RUN-009（外部历史/待归仓路径：`../../build/ms-seven-suffix-001/RUN-009.json`）及最终业务复核（外部历史/待归仓路径：`../../build/ms-seven-suffix-001/BUSINESS-WITNESS-002.json`）使用observer003完成同一整条七组件两代、三次观衡和后继数量观察，约105.863秒。QA按实际模块完整路径解析导出，只读读取当前Native PID55652的`handled=4/read=4`；原连续advance约束使该值涵盖此前序号3。后继策略序号4，券商/原生数量均200，SDK/order/deal各1，24条成功查询及四前沿4保持。14份成功关闭、两个WT启动器及三次观衡/Source启动器OS0、外层58636 OS0和完整树/EOF/join/句柄回收成立。

原生事件锁内仅有定长整数写入及最后的InterlockedExchange，文件IO、等待及分配触发链已移除。PE导出和只读自进程的短反馈（外部历史/待归仓路径：`../../build/ms-seven-suffix-001/memory-check-001/RESULT.json`）只证明观察API，实际Native消费结论来自009的原件。QA健康观察线程也已join；它只读取既有`/health`，不启动账户查询或SDK调用。

006在account_lease被另一个并发场景的同账户租约拒绝，原保护和失败原件保持。007首代Native已正常关闭，独立账户只读Host报告`runtime_failed`，使整个WRI关闭失败；单独复核（外部历史/待归仓路径：`../../build/ms-seven-suffix-001/READ-HOST-CLOSE-WITNESS-001.json`）确认Native24688的closed.v2为ok/exit0，账户Host49280为incomplete/runtime_closed=false，WRI56960为faulted。只读Journal保留29条成功和1条queued请求，全部物理资源已回收；Host内部原因仍缺直接证据，交公共生命周期owner继续定位，未归因为WT线程问题。该次没有进入第二代，整体失败保持。

008在另一次直接读取状态快照时收到CollectionStatusPending，业务SDK0，随后正常关闭。009将本地QA的current读取统一收敛到既有有界等待，所有调用共用同一逻辑；产品状态发布和各产品截止保持。009的健康读取在正常关闭窗口观察到可用→503/断连，007的Host内部异常仍缺直接证据。原失败独立保留，成功重跑不消除该缺口。

## SDK已进入后的未知结果

RUN-004（外部历史/待归仓路径：`../../build/ms-seven-unknown-001/RUN-004.json`）及业务复核（外部历史/待归仓路径：`../../build/ms-seven-unknown-001/BUSINESS-WITNESS-001.json`）完成约49.616秒的预期失败恢复链。首代完整七组件运行唯一1.1.2，SDK替身实际进入后先记录调用、随后抛错；源端没有制造委托、成交或持仓变化。原Source/Host将同一命令持久化为unknown，sdk_entered=true、error_code=sdk_exception。

首代停止在recovery_drain报告失败，保留原责任且不产生最终clean。整个WT及Host退出后，用同一通信Journal、原生金融根和resume_clean配置启动第二代。原Source业务service继续存在；第二代完成四查询，随后在CTA的干净恢复准入处拒绝。命令ID、原命令正文SHA及原结果SHA在前后完全相等；Journal仅有该一条unknown，SDK仍为1，原三份策略/用户KV/组合文件摘要保持，最终clean仍缺失。

交易通道保留9条成功查询，P2/O3/D2/A2，其中重启新增4条。两代Native的失败阶段分别为recovery_drain及cta；两代WRI启动器OS码均为2，Source启动器exit0，外层48756 exit0。实际WRI应用PID69812/55340报告faulted，Native及WRI应用各自的独立OS退出码未另采集。外层及全部子树归零、EOF、join和句柄回收成立。WRI的components_closed=false及业务排空未确认原样保留，成功关闭证明为0；物理资源回收与未知业务责任分别记录。

001/002已到达两代预期拒绝，QA分别取错Native收据目录和查询通道，整轮判失败；003与另一场景并行，被原同账户执行租约在启动阶段拒绝。004在前案全部退出后串行运行。所有失败原件保留，未改变执行租约、未知判断或恢复准入。

## 资格与后续

本证据支持同Source业务service、整套WT/Host换代时的事件后缀消费和unknown保留/拒绝，运行使用明确诊断source overlay。Source进程自身冷重开、unknown核查解除、正式同批发行/搬迁、完整400期RT/BT、正式跨日及统一候选主链继续分别验收。券商事实、WT策略账本和绩效保持各自原所有者，真实下撤单与生产切换沿原明确授权边界。

独立审查与最终文件SHA由两验证根的交接收据绑定，模块整体保持in-progress。
