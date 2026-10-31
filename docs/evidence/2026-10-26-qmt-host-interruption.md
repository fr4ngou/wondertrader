# QMT Host断连后的主动持久收尾

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：根因验证证据。日期：2026-10-26。状态：原样两场景根因已复现；后继自有Host修复、同断言2/2、101项关联回归及PD01复验通过并独审。原始失败与后继结果分别保留。

## 根因与影响

原Host I/O在send/receive异常后跳过本轮完成处理，异常入口仅冻结交易中断标记；finally关闭peer与域队列。peer把未返回的交易Future标成binding_closed，但没有后续owner把它保存成原UUID的unknown。Host继续存活并提供历史查询时，原记录可保持dispatching。外部Host.close晚调用时才领取失败Future并建立新的本地持久预算。此问题属于自有Host适配代码，与待批准的WT框架修改分开处理。

既有[QST-R19规格](../specs/qmt-shm-trading.md#qst-r19-显式-host-组合交易运行器)要求断连按原ID持久interrupt、保成功结果及首次截止。根因涉及control_trading.py、trade_runtime.py与runtime异常接缝；不新增交易账本、线程或服务。

## 原样实际反证

使用真实HostTradingRuntime.start/_run、HostTradingControlLoop、HostDomainWorker、临时SQLite Journal、两端ControlPeer及SourceTradingService/TradingControlLoop；仅已建立Session/listener的packet运输采用有界内存替身。真实原线程SDK替身进入后阻塞，不返回；在Host receive注入一次合成OSError。该案不验证认证、Win32 SHM、源进程死亡或真实券商调用。

原总测试D一次12秒，io_seconds=2，命令TTL5000ms；未外部关闭Host前，沿首次真实interrupt D观察原UUID。实际SDK进入1/返回0、原trade packet1、claim1；Host I/O和域线程已退出，中断提交0，原UUID在首次中断D之后仍dispatching，主断言失败。清理才释放SDK门并调用Host.close，之后原记录unknown/interrupted；该结果单列清理，不补授主断言成功。

| 实测事实 | 结果 |
|---|---|
| 首次本地interrupt D | 1040112.265（monotonic秒） |
| 外部close前样本 | 1040112.328，dispatching，interrupt提交0 |
| 晚close创建的持久任务D | 1040114.328 |
| 测试结果 | 1方法失败，unittest exit1；有效根因复现 |
| 资源 | 源/Host/域join，Session/listener/Journal关闭，临时目录回收；cleanup_errors为空 |

控制器实际Node句柄PID71588与其自报PID一致，子63992 exit1，外层exit2；3.657秒，Job树0、双EOF、读线程join、资源关闭，无强杀。不能把预期RED的非零改写为绿色测试。172 frozen来源post核同，运行器保原首异常及有限收尾错误，见根结果（外部历史/待归仓路径：`../../build/qmt-recovery-next-001/HOST-INTERRUPT-RED-ROOT-VERIFIED.json`）。

候选测试002修订了提交后spy追加竞争和输出后实际D检查，runner003保留原异常身份；静审见最终运行包审查（外部历史/待归仓路径：`../../build/qmt-host-interrupt-regression-independent-001/review003/REPORT.md`）。动态独立复核（外部历史/待归仓路径：`../../build/qmt-host-interrupt-regression-independent-001/dynamic001/REPORT.md`）已确认有效RED，根核11份新增原件；172源与57模块身份一致。

## 后续验收

由原I/O owner在关闭域队列前主动推进持久收尾；保已成功结果、原任务D及late claim身份，未知仅沿原ID保存。验修前本案RED→修后相同断言GREEN，并覆盖成功reply后失联、claim在途/提交失败、域背压及存储超时、读收尾失败和正常关闭。真实SHM源死亡测试另行验收，完整父死亡矩阵和生产资格继续。


## 修复实施与同断言后继（2026-10-26）

原样成功回报反例也已实际复现：真实SourceService/ControlPeer返回sdk_returned，Host已收到原成功Future但尚未take时在原_complete入口注入一次异常；外部close前原首interrupt D之后仍dispatching/202，SDK替身进入/返回各1，finish/interrupt均0。晚close才以新D保存成功。该失败保留，不能用清理结果补授通过，见成功原样根核（外部历史/待归仓路径：`../../build/qmt-host-fix-continue-001/SUCCESS-RED-ROOT-VERIFIED.json`）。

修复仅修改自有Host的control_trading.py、trade_runtime.py和runtime.py。原I/O finally撤准入后先调用内部_finalize_control，复用原八槽domain完成已知交易责任，再关闭domain/运输。成功reply优先原trade.finish，结果未知沿原ID中断；已建任务实际入域payload保原D，新收尾只用首次D；submit交付未知保原槽/owner和首错。管理close仅join和观察既有Future，不新起交易事务。只读基类hook默认空，WT/Standard/Agent/Journal/domain未改。

候选001/002静审发现关闭测试阶段错配、漏接真实owner finalizer、既建任务运输D改变及只读property赋值问题；003分别修正，保留原业务oracle。最终独立窄审（外部历史/待归仓路径：`../../build/qmt-host-interrupt-fix-independent-001/implementation003/REPORT.md`）通过，六映射及两条原样回归由根按SHA集成，见实施收据（外部历史/待归仓路径：`../../build/qmt-host-fix-continue-001/INTEGRATION.json`）。三产品SHA依次ca2ace5fb73d315f9cb5e780b7ca5c1b31c59f294c3ff18184889898891c644d、767f68a0006da4fdec6664aeba8b1ba8189e6b53c795fca07454257b3ee2e55a、33d90a00fa34aa6a3e7d28c6097fd9e22446059d5023b6398d1a1cb0882d7e44。

| 当前实测 | 结果 |
|---|---|
| 两条原runtime RED同oracle | 2/2通过，unittest0.236秒；unknown在外close0、SDKreturned0时已保存；success在外close0时sdk_returned/200、原payload SHA、finish1/interrupt0 |
| 原任务及首次D | unknown事务和success finish均由原domain执行且在首次D内；管理close没有补做交易 |
| 必要关联回归 | 44 control＋11 finalizer＋40 runtime＋1 claim-deadline＋5只读lifecycle，共101/101，无skip |
| 进程资源 | causal Node/controller73544、child39636；batch61236、child13500，均实际exit0，无forced，Job树0、双EOF、reader join及资源关闭 |

两批使用同一177源冻结闭包INPUTS bb10adafd937c11cacfcd0cbbb2c52a5ef3b09bf6621f98afd227cc69dab8d15；原unknown测试7e6c7d09099a0f021dd0280cab88914a3ac4647954035f37499005506de5b41e与success测试6bb46d64b1bf115bd481dc6d70aff0def3ed6b746dce184ea9c6cb06410907e4均逐字保持。见双场景根核（外部历史/待归仓路径：`../../build/qmt-host-fix-continue-001/CAUSAL-GREEN-ROOT-VERIFIED.json`）与101回归根核（外部历史/待归仓路径：`../../build/qmt-host-fix-continue-001/BATCH-ROOT-VERIFIED.json`）。两条runtime场景的packet载体仍为有界内存运输，源业务handoff保持未确认，实际券商调用0；真实SHM源进程故障后继、动态独审及完整恢复/父死亡资格分别登记。


## 修后动态复核与SHM回归

双场景动态独审（外部历史/待归仓路径：`../../build/qmt-host-fix-runtime-independent-001/dynamic001-causal/REPORT.md`）与101项动态独审（外部历史/待归仓路径：`../../build/qmt-host-fix-batch-dynamic-independent-001/REPORT.md`）已通过，根分别核11份与193件封包。101批实际6.264秒，原cancel提交后失败继续保原Future/首cause/dispatching/禁新cancel；九步独立资源处置完成，business close仍未确认，不能用测试清理抹去业务失败。运行器IDENTITY残留单案test标签，实际五模块suite、101唯一方法日志及module来源已交叉核实；该旧标签保留为低优先证据标注问题，不重写运行原件。

修后原PD01在同EXE/DLL下重新运行1/1，unittest6.646秒、controller7.828秒；173源闭包仅3 Host和2受影响测试改变。Node/controller67732实际exit0，child68660为venv启动器，正文Host PID20276/base image4726；Source PID10732、Native PID10608。唯一Source计划故障后，64次原UUID GET为首1条dispatching/202、随后63条unknown/200，POST仍仅1次；SDK替身进入1/返回0。Native保持Unknown/Pending1/禁新写并自然Closed/delete，Host关闭后原roSQLunknown/interrupted、原body/B/期限不变。资源及原总D均核实；根结果（外部历史/待归仓路径：`../../build/qmt-host-fix-continue-001/PD-ROOT-VERIFIED.json`）和独立动态复核（外部历史/待归仓路径：`../../build/qmt-host-fix-runtime-independent-001/dynamic002-pd/REPORT.md`）已通过，根核172份原件。该原PD01未记录首次interrupt D，immediate、自动父死亡和真实券商资格字段仍保持false；首次D内主动持久由上述两条runtime场景证明。

本轮26份保护框架SHA保持；实际券商下单/撤单0，旧QMT项目执行/修改0，生产未切。完整query/live金融交接、历史覆盖、保留业务及发行继续按整体目标完成。
