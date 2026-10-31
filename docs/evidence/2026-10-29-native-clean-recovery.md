# 模块B：原保存加载的产品正常恢复

类型：隔离开发证据。状态：限定范围 development-verified，STQ-P21及完整模块B保持in-progress。日期：2026-10-29。对应[B-05/B-06](../migration/module-b-delivery.md)及[STQ-P21](../specs/native-qmt-standard-trader.md#stq-p21-原保存加载的产品正常恢复accepted开发中)。原件根为`build/ms-recovery-001`，真实券商调用0，WT核心新增修改0。

## 实现与职责

产品运行体增加显式`recovery.mode=record_clean/resume_clean`；缺省继续fresh路径。策略持仓、盈亏、信号及用户变量继续使用WT已有业务事件保存和原init加载，停止阶段没有新增save调用。配置身份去掉recovery字段后保持相同，恢复沿相同输出根及原Host/Journal。

Session在原输出根租约内核验、消费上代clean证明，再调用原engine/context初始化。停止先关闭目标桥并join生产者，原执行owner继续排空既有查询/回报和命令责任；单向关闭新insert/cancel，再取得晚于关闭屏障的完整O及其后的P。原Standard全实例责任、通信pending、错误/unknown及全账户活动单均核清后，物理close才可以记录clean。元数据只绑定配置、安装及原金融文件集合/摘要，并要求上一代成功closed收据；中途崩溃和未确认终态不授恢复。

新增`StandardQmtRecoveryV1`及两个独立C导出，原Diagnostics/Submission结构布局保持。原生运行体、Session和Standard须作为同代组件组合；公共头消费已实际编译，版本1结构64字节、next_task偏移40。该观察提供原责任计数及查询序号，没有维护账户数量或第二份金融状态。

## 固定输入与独立安装

`BUILD-010.json`绑定九份B原生生产文件及全部二进制；CtaProcess源码SHA为`d14329c98d6a53d2b489c86592122ec749e15a5cc3bfa961eff4ea55744a9960`。构建使用原P20固定composed输入及已批准核心；本轮覆盖仅位于自有执行/Trader模块。原617项输入核对中，未参与该产品编译的旧synthetic_parser源码漂移单独记录，没有借其授构建一致性。

普通venv安装22项固定依赖，Appa10、corea6、NSQa1、SDK0.14、Starlette1.10，`uv pip check`通过。App公共读取器候选仅存在于`app-source-proposal-004`及其独立wheel；仓库`managed_local_process.py`仍为C原摘要`6e76765ffce1071941830a190c4a1cbe3124d03d862054fcd953a0a11fb7049f`。候选wheel SHA为`70fd2c007b65133e044b328f6dd429fa19bb493c20748d80043d019690964f70`，候选读取器SHA为`338f1d1b9848a4f9a5b04a250fb85d08db5eae4ebb3f051663a5e2f5f76edd88`；它是待C集成的明确片段，当前App公共源码尚未合入。

测试从实际安装复制原生组件、固定Parser/Reader和Target策略DLL，使用原Factory/CTA ticker/组合/MinImpact/Adapter、真实WinSHM和SDK替身。`MATRIX-010.json`保存运行时全部相关源摘要，结束再次逐项核对；SHA为`6bbfa7b20d2f4b70d53a1fc4c5ddc4d19afff729f2f4c07654ae763806cb9742`。

## 实际业务结果

| 条件/验收 | 实际结果及原件 |
|---|---|
| P21-C1安装后同根两代 | `clean-boundaries-proposal-002`首代沿O1买1000、目标变1200后仅买200；第二代原init恢复A800/B400、用户owner A/B及组合1200，继续原调度且新增SDK为0。两代成功closed/recovery_ready、clean→consumed身份及五份原金融JSON逐项绑定 |
| P21-C2活动单 | `blocked-active-proposal-002`真实SDK替身买400后仍有活动单；停止精确报recovery_drain，clean不存在，物理退出/双EOF/join完成且无forced |
| P21-C2未知SDK结果 | `unknown-stop-proposal-001`真正进入SDK替身后抛错，原Source/Host形成unknown；停止前后同command_id/command_sha/result_sha及state保持，SDK仅一次，无重发、无clean，物理资源完整回收 |
| P21-C3拒绝与保留 | 正常两代后依次验证活动单、状态摘要变化、额外大写.JSON、配置变化、缺clean、缺成功closed、native模式；精确stage分别为trader、五项cta及configuration。六项query_first先取得四查询，native模式0查询；全部0SDK，原金融文件/clean保留，探针逐项原样恢复 |
| P21-C5缺省兼容 | `add/exit/net/pending/partial-compat-001`分别保持买1000、A退出卖600保B400、相向零委托、买400未成防重复、部成500防重复；原状态与整树/双管道/Host/源资源回收通过 |
| P21-C5真实业务配置兼容 | `configured-compat-001`通过安装Runtime/正式Python子端连接唯一corea6/NSQ，原历史输入下A/B各700、净额买1400，后继原调度converged；正常完整关闭。单次兼容通过不关闭C已报告的历史访问冲突 |
| R11恢复明确拒绝 | `python-recovery-reject-001`实际安装的PythonExecutionProcessConfig对record_clean/resume_clean均拒绝；Runtime未加载、control实例0、既有原状态字节保持。纯决策阶段尚需经原用户KV接口衔接 |

`tests/integration/qmt_cta_product/run.py`新增`--clean-resume`、`--recovery-boundaries`、`--clean-stop-blocked`及`--clean-stop-unknown`，依旧显式传安装、App包、Parser/Reader/策略及同一总截止。运输夹具仅为多代场景显式扩大有限查询进度/Journal容量，默认额度保持。

## 控制文件读取根因及修正

历史`blocked-active-001`的父进程在读取有效ready文件时得到`PermissionError`，winerror为空；当时原生错误码不可追溯。`clean-boundaries-001`原stop失败的精确原因同样保持UNKNOWN。两份失败原件保留，后继成功没有替代它们的事实。

`reader-probe-001`用实际Windows独占句柄复现：原path.open丢失共享冲突原生码，候选CreateFileW保留32；打开真实目录返回5并且仅调用一次。释放锁后成功、锁保持到首截止超时、100次读取以及两层所有权转换各20次失败的句柄差额均为0。原文件身份/链接数/长度校验保持，重试仅接纳32/33并沿原截止。

原生运行体同样保留实际Win32错误；仅stop读取的32/33在首次观察到stop的截止内重读。独立审查发现读取失败后catch重设关闭D的缺口，BUILD-010已使首D存于外层，读取成功再核D，解码标记独立且后续只收紧D。

实际产品`stop_reader.py`将stop发布后保留仅允许删除的写句柄150ms，并用同类原生读取探针确认32。冻结008运行体`lock-old-003`精确stop_read失败；010运行体`lock-release-002`正常关闭；`lock-malformed-001`在锁释放后精确stop_parse失败。三案均完整物理回收。原生持锁贯穿首次截止的运行案仍待验；Python截止实验不替代该原生异常路径。

给C的唯一公共片段为`managed-reader-proposal.patch`，SHA `1360bc37ee6933090885bed694cf8864af0d13366c314b92949e797d877942a0`：共享读取helper保留原生错误码，已有stop及最终closed读取沿同一关闭D处理32/33。合入时保持C当前App其他文件与版本，再验证当前公共读取器消费者。候选和开发ZIP不授生产启用。

## 独立审查与剩余范围

`REVIEW-010.json`由独立review_execution写入，SHA `83387b8ddd5b94bb049515ec39930674203caf39bd2f56224897b30bd0ba6244`，绑定生产/测试摘要、矩阵输入、实际DLL、clean/consumed/closed及SDK原件。已关闭模式准入、扩展名集合、首次失败阶段保留、首关闭D及证明索引等发现，当前无新增P级源码问题；完整P21及模块B均明确false。

继续项包括：安装漂移专项拒绝、恢复模式下生产者pending/回调失败/父截止/根及账户争用、原生持锁贯穿首D、R11纯决策状态恢复、异常退出及跨根未知责任恢复。完整订单/撤单结果矩阵、真实资金/T+1/非零费用、全部保留算法和真实来源M1/统一App安装继续分别验收。历史原生访问冲突仍为运行资格缺口，见[App原件](2026-10-29-configured-app-entry.md)。

## 开发制品与搬迁主链

`DELIVERY-010.json`摘要`1afb654a69b270619e51989c96d9be830c15e1f4300c6eadf59b95044193a689`；`GuanhengExecution-clean-recovery-dev-010.zip`摘要`7c43e8b15c59ee1583a91e1a8e7ebd8df7a04d869491ecf57e2b886fa6122378`，86项成员全部校验。归档含同代原生安装/公共头、隔离App wheel、C读取器patch、固定源码及有限结果，不包含原HTTP/fixture正文。公共App仍须C合入，开发候选保持完整模块/P21完成标记false。

原归档实际解到`relocated-010`，与同一wheel源码及其余元数据逐项相符的普通安装组合，再跑正式产品exe→原ticker→组合→Adapter/WinSHM，A600+B400实际SDK替身买1000。`relocated-main-001`记录树/双管道/Host/source完整回收；归档全部文件运行前后保持。安装公共头消费原件为`HEADERS-010.json`。文档后继与搬迁收据在归档外单独绑定，原ZIP及DELIVERY保持冻结。

交付delta更正：首份PACKAGE-POSTFLIGHT-010的wheel_members_equal_installed字段范围过宽。后继`PACKAGE-POSTFLIGHT-010-002.json`完整核65项wheel文件，64项源码/其余元数据相同，RECORD由pip正常重写；明确排除RECORD的字节等同判断，并分别绑定归档与安装RECORD摘要。复用同一源码/安装/归档的搬迁主链原件，重新核全部成员及搬迁文件；该更正保持运行结果，原收据保留历史身份。

## 原生访问冲突定位后继

本轮只读消费C的`build/configured-app-001/NATIVE-FAULT.json`，核同一原Runtime SHA `73d3f64519f71360b12b3ec3cc8e0c856ae67d3caf9ddbda97d7183d6a4b3c04`。在`build/ms-runtime-fault-001`用原对象/库另行链接MAP，原目录和DLL保持；故障函数所在RVA9cc60..9cda0的完整320字节与原DLL一致，函数摘要`5049586113ad7785e48d9973cd5a530689ef4fa1374074dcf0f586dd51efd9e8`。全.text另有321字节差异，报告没有授整个重新链接DLL等同原件。

两次故障RVA9ccc0/9cce5分别落在该WtEngine.cpp任务闭包的仓位对象锁访问及volume读取；反汇编对应原on_tick提交的组合浮盈任务。`RESULT.json`摘要`657a4bf4053995745c840c8544624bcdbebce7890c173085ef2b660b4db7c66f`。函数级范围已缩小，实际异常寄存器/对象及同次原生栈仍缺，具体根因保持unknown。继续先捕获原调用链的异常事实，不据此新增行情冻结或修改核心。
