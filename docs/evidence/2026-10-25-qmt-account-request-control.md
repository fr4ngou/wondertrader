# 账户读取按次请求停止

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。日期：2026-10-25。状态：R5a基础切片32场景及冻结输入的Common19/Standard31/Retry9兼容回归通过；完整R5补查未完成。正式要求见[SEV-R5a](../specs/native-qmt-standard-events.md)。

## 实现与边界

缺字段补查需要在事件detach后停止后继HTTP，同时保留普通账户查询。原账户client只有实例control，复用它会让事件control失去逐跳作用，改实例control则会污染普通查询。本片在同一QmtHostAccountClient/QmtBoundReadCore实现增加显式兼容重载，按次借用control与原control做OR；每个binding/verify/POST/原UUID GET/末验证/发布阶段沿原D检查，不新增client或线程。typed outcome/stage区分真正失败与进入后继阶段前的正常停止，不靠reason字符串分类。已准入HTTP的真实失败先保留，stop不把它改成成功。旧入口及receipt/Host协议保持。

旧resume预读binding失败后仍GET原终态属于原审计恢复意图；新显式按次入口对该失败保真实Failure并停止新跳。两种入口复用同一follow/validator，兼容差异由正式R5a说明并真实对照验证。P8、Standard补查装配、mapper、Host/Agent及WT本片未改。

## 实际执行

| 验证 | 结果 | 原件 |
|---|---|---|
| 固定原版+自有Common探针 | NqpAccountControlProbe单选，165/165编译步骤，DLL SHA19251b2533090aa10fcb5b3a2ad895c67468d0fbd236bafd484c298f96d3b098 | 构建（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-request-control-fixed-001/result.json`） |
| 真实C++/loopback/HMAC读取 | 9方法、31原生场景+1实际listener构造失败反例；失败0、错误0、跳过0，SDK0 | 结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-request-control-runtime-001/result.json`）、收集（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-request-control-runtime-001/COLLECTED.json`）、日志（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-request-control-runtime-001/tests.log`） |
| 冻结运行身份 | 166文件；驱动运行后核SHA，并严格核31/1场景计数，DLL前后SHA一致 | 输入（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-request-control-runtime-sources-001/INPUTS.json`）、驱动（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-request-control-runtime-001/run.py`） |
| 独立full/delta | 原两测试P2静态关闭，当前开放P1/P2=0，审查执行0 | full（外部历史/待归仓路径：`../../build/qmt-account-request-control-independent-review-001/FULL-REVIEW.md`）、测试/接线delta（外部历史/待归仓路径：`../../build/qmt-account-request-control-independent-review-001/revision002-tests-wiring/REPORT.md`） |

原生场景核binding前、prepare/create/submit、POST结果、原ID GET与末发布各停止门，503/坏正文/合法业务失败与stop并发仍保真实错误，原业务D耗尽，旧resume审计及新入口失败、显式成功清旧typed值。同一client在请求control停止后继续普通查询，不借重prepare清状态。observer仅测试DLL暴露真实原子停止值，注册/停止/注销同锁；case退役指针后HTTP owner按原D join，DLL保持引用至进程收口。

新增资源反例在真实listener已SO_ACCEPTCONN=1、线程启动前注入callback构造MemoryError；保原异常对象，确认socket fileno=-1、再次getsockopt报OSError、没有请求或stop调用。

## 审查修正与剩余

原测试使用不在正式源错误集中的synthetic_failure，被validator正确判invalid而非预期业务终态；最终改为合法qmt_call_failed，产品allowlist和失败优先断言保持。原listener取得后至callback构造存在finally空窗；已把取得后的所有步骤纳入contextmanager并补真实反例。原001和独审初版保留，最终Python SHA35ad36745460fee736df3fce8b6924ece68b57b5c0021435cb5b07418eb23c54，四产品及C++ probe保持原full身份。

本片尚未交付缺字段精准匹配、真实查询整行/双provenance/P8/单项SPI，也未解决生产首次/重连R8。下一步完成旧Common/Standard当前二进制回归，继续唯一mapper的typed部分事实准入；没有第二持仓资金账本、生产Factory切换或真实SDK调用。

## 后继：冻结R5a输入的兼容回归与当前mapper边界

同一冻结R5a源码补编八个兼容目标，构建原件（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-request-control-compat-append-001/result.json`）SHA为`b64483013c76823d27621c347ad572fa1caee920ea82f1462adaebba37c7c22b`；三批共同绑定INPUTS（外部历史/待归仓路径：`../../build/qmt-account-request-control-compat-001/INPUTS.json`）SHA `69eb632020b2d07a3944c53b378be553462d41326d8a33f0d8b9a605126e71fa`。各结果重新核该构建收据及实际八制品SHA。

| 冻结输入回归 | 实际结果 | 实际退出与回收 |
|---|---|---|
| Common旧客户端 | 19/19（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-request-control-common-001/result.json`），失败/错误/跳过均0 | controller（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-request-control-common-controller-001/build-qmt-account-request-control-common-controller-001/result.json`），exit0，19.843秒 |
| Standard公开链 | 31/31（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-request-control-standard-001/result.json`），失败/错误/跳过均0 | controller（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-request-control-standard-controller-001/build-qmt-account-request-control-standard-controller-001/result.json`），exit0，38.484秒 |
| 读取重试 | 9/9（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-request-control-retry-001/result.json`），失败/错误/跳过均0 | controller（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-request-control-retry-controller-001/build-qmt-account-request-control-retry-controller-001/result.json`），exit0，53.875秒 |

构建controller与上述三批均forced=false、创建期Job归属成立、tree0、双EOF、读线程join、resources_closed=true。原32场景也已核9个真实收集方法及运行日志（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-request-control-runtime-001/tests.log`）全部成功；驱动严格核31个native场景加1个真实listener构造失败反例，外层（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-request-control-runtime-001/build-qmt-account-request-control-runtime-001/result.json`）exit0/完整回收，耗时7.468秒。

兼容回归的owned输入（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-request-control-fixed-001/owned/input.json`）中AccountMapping.h为`362728431969fe0c24bd881f3eaedd3c169a65f28c154be378edf19400319e8c`、AccountMapping.cpp为`07063c9b21c6e2c05398a33ecc3a587a410a8c989620b1dc140bfdadff520149`。当前R5b的两文件已分别变为`02aaf868f5a8bb04868935a1e3490c1188c8d825ae1fafecc98c313eeb6f70aa`、`2928757bb168749a00fd97967ff8e261955ff23d6e6e5de1e79950c987814ff4`；19/31/9保留冻结R5a输入资格，当前R5b的整链兼容需要按新输入另验。

收尾时R5b已完成full（外部历史/待归仓路径：`../../build/qmt-account-row-inspection-independent-review-001/FULL-REVIEW.md`）及接线delta（外部历史/待归仓路径：`../../build/qmt-account-row-inspection-independent-review-001/WIRING-DELTA-001/DELTA-REVIEW.md`）静审，独立NqpAccountInspectionProbe单选编译（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-row-inspection-fixed-001/result.json`）通过，EXE SHA `dbdfc94c40e33d31452b483ab5daf7bc8f797cd57f3f1cbf15e22e25c22b2f34`。实际stdout（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-row-inspection-runtime-controller-001/build-qmt-account-row-inspection-runtime-001/stdout.txt`）报告128币种/金融、115规范、31事件及142次inspection调用全部完成，运行controller（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-row-inspection-runtime-controller-001/build-qmt-account-row-inspection-runtime-001/result.json`）exit0、0.312秒、tree0/EOF/join/resources关闭。该独立纯合成探针覆盖其已定义范围；完整R5匹配/补查、P8/Standard接续及生产R8继续，整体目标active。

后继以当前156份自有源（含R5b新mapper）重新编译并实际完成Common19/Standard31/Retry9，范围与旧冻结结果分别保留。见[后继原件](2026-10-25-qmt-event-row-match.md)；完整缺字段接续及R8仍待验。
