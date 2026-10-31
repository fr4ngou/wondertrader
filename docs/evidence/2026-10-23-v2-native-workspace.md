# V2原生回测与独立工作区接线

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

日期：2026-10-23。类型：开发及部分审查证据。范围：[NVB](../specs/native-v2-backtest-session.md)、[NBW](../specs/native-backtest-workspace.md)。当前状态：报告F1/F2离线独立delta均关闭；首次后端full仍partial。前端摘要一致性F1修正后的独立delta complete、新增gap 0；新页面包的五个真实业务HTTP/原DLL/浏览器合成场景通过。真实来源、RT与生产另验。下方保留各轮历史记录。

## 复用与应用变化

V2沿既有StrategyBacktestSession、NSQ、受管StrategyHost/runner及原CtaMocker回放；NVT/SST/NFA分别拥有算法、信号和分配计算。原始权重超过1时保留原值并阻止新增setter，不归一化。WT拥有回测持仓/资金与撮合，页面使用原生观察，不增加资本账本或逐单人工审批。

NBW用唯一project_session_record消费轻量header与当日观察，不先重建全部历史再删除字段。configured响应保持原字段，V2详情明确report_schema。前端按两组独立事实显示信号权重与执行证券原生数量，不猜测两组证券的对应关系。

应用a3显式依赖NVT a1、SST a2、NFA a3，继续core a5、NSQ a1及SDK 0.12；resolver生成新锁，其他锁定发行版本保持。原a2和各轮原件保留。

## 首次独审与报告一致性

初始后端最终入口SHA `300942bdb0226ddb6fb79ffbe80e7a620cbc925c8f76983cc13051382c8ce52f`；根核1500份原件、82输入、43 ZIP成员相符，见身份收据（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-workspace-001/backend-input-integrity.json`）。

自动安全检查中止了子Agent完整审查，提示可能存在网络安全风险，未给出具体触发位置。随后仅离线封存，未继续动态任务。部分报告（外部历史/待归仓路径：`../../build/guanheng-workspace/strategy-v2-native-review-001/PARTIAL-REVIEW.md`） SHA `a3136f16c69b36356920017cd97441cd17d6958e0ca63934ad4767342b048fc0`，根核1308份原件相符。独审20项V2软件测试通过；额外configured测试因审查副本路径错误仅1项通过、95项失败，不能据此判产品失败或兼容通过；原生矩阵未由该审查执行。

独审F1确认公开准入接受共享行/摘要不一致的报告，而完整重建失败。根任务修正在Session抽取同一_v2_prefix_result，准入阶段即核各完整前缀摘要与组合容量，重建复用；轻量投影继承准入结论。新增22项反例/正向中，原实现18失败、4通过；修正与26项NBW组合48通过。修正只涉及观衡自有源码，WT框架保持。

当前离线delta已确认原F1拒绝行为，另发现F2（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-report-review-002/NVB-F2.md`）：canonical编码捕获KernelValidationError时误将调用方check抛出的同类受控错误改成SessionError。源码/安装保持该轮冻结，待delta完整封存后统一修正；不授最终报告资格。该发现属于异常所有权，未声称报告损坏可通过或WT并发存在缺陷。

## a3独立安装及回归

新noneditable运行目录为`v2-workspace-001/install-8cf200c748f34a4781ddbefc7a4e5c3b`，Python3.14.6；app wheel SHA `de1ccaf826f91b780549a80735fb43f7e5f405b02c3b67f41488c6f8cb5921ba`。全部生产依赖逐wheel SHA安装，pip check通过，configured/V2分别绑定完整site与原DLL/probe/basefiles。

同一安装164项软件回归通过，覆盖22完整性、20 V2、96 configured及26 NBW；每个计算/应用模块的实际导入路径均核在该site。测试依赖放外部独占目录，没有修改运行site。日志见安装回归（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-workspace-001/tests-f8f801d9b08e4c168bec00b4e1291337/receipt.json`）。早期根开发环境缺V2发行元数据、测试依赖少py shim及构建/锁准备失败均保留，不混入成功条数。

同版安装完成8个原DLL场景：小目标、信号/执行不同证券、原始超额、未知费用、T+1、configured、坏来源拒绝及schema错配拒绝。6个正常模型回放与2个预期拒绝通过，受管外Job均自然退出、管道结束；实际Host完成结果核原生输出/完整前缀与精确资金。输入、执行与断言脚本沿冻结案例，仅重新绑定当前安装；合成行情/模型资金均明确。见实际矩阵（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-workspace-001/native-0fccaf77b94d4c53bff629a62a23cc7c/result.json`），SHA `d5f232ecae592de7794101025d2ad33122ce64c662b036bf132ed7ed5824782b`。

## 实际限制及下一验收

独立full缺失和新F2仍须关闭；通过条数、编译及作者原生矩阵不能代替完整独审。前端类型/API/组件与独立复制树构建已取得开发结果，浏览器及正式业务HTTP→原DLL→页面组合仍待本轮完整证据。旧console/dist及既有发布保持。

真实QMT/ETF覆盖、行情单位、实时CTA及生产交易资格分别验收；本轮没有接入真实账户、发送或撤销委托、恢复旧终端HTTP、重启终端或修改WT框架。

## 后继：控制异常所有权统一修正

完整离线delta（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-report-review-002/DELTA-REVIEW.md`）已封存，结论F1关闭、F2/P2 open；164回归通过，自主57项55通过、2项同根因失败。原首次full仍partial，该delta未启动Host、原DLL、SDK或网络监听。

封存后根任务在报告公开入口统一隔离check控制异常：内部专用BaseException信号越过业务与codec转换，公开出口恢复原异常对象、原因码及原有traceback；数据错误继续由原准入层分类。没有逐异常特判。新增72组合覆盖6类异常、4入口及入口/解压/编码3阶段；原实现11失败、83通过，修正后94完整性及26 NBW共120通过。

新noneditable安装为`v2-workspace-001/install-0e899c6c789140a0a07387a8ef7062c1`，仍为未发布app a3、由新wheel/manifest SHA区分候选。其236项安装软件回归（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-workspace-001/tests-ad3288861c714fbe8a0d9cdc63685a92/receipt.json`）通过，原8个合成原DLL场景（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-workspace-001/native-8cd08c20f2b7444c9d398c2b4a6b4c27/result.json`）同版重验通过；旧安装及两轮红灯保留。新独立delta入口（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-workspace-001/report-fix-final-002/review-inputs.json`） SHA `de058de97670397ca79d3fe4bc2b3da59e43b9433afe333a9346d1341e23d36e`，25输入冻结，后继独审待验。不得据开发通过预先关闭F2或首次full。

## 后继：报告独立delta关闭

离线delta003（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-report-review-003/DELTA-REVIEW.md`）已完成，F1/F2关闭、新增gap 0；236项冻结回归与220项自主测试通过，覆盖异常对象/原因码/源traceback、嵌套check、取消后恢复及有效报告。报告SHA `bd2f926b33bc53d2ef1e21a890cdb417725d9c95a1038ed2e684a104e80192c6`。根任务回核（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-workspace-001/closed-report-review-integrity.json`）前两轮138与133份原件及当前25输入相符。该审查没有执行原生、Host、SDK或业务HTTP，原首次full的动态矩阵缺项继续保留。

## 后继：前端一致性修正与真实业务调用链

前端首次full（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-workspace-ui-review-001/REVIEW.md`）完成全部适用矩阵，发现NBW-UI-F1/P2：类型正确但重复事实矛盾的摘要仍可通过公开fetch入口，实际Edge可同时显示八项零权重与112.5%总权重。根任务修改前回核420份审查原件、52份作者原件及当前8源码，原件保持。

自有`backtestV2.ts`在唯一消费边界校验重复末特征、权重明细/浮点总和/原精确分数、事件日期与当日事件标志。对象键顺序保持语义无关；八个非负数有限累加允许相对舍入误差，零总和仍严格为零；精确分数的准入与浮点诊断分别核实，页面不重新分配或归一化。原始回归47项中8项失败，修正后原五文件与新增共69项通过；类型、Vite及分块门禁通过。新冻结入口（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-workspace-ui-002/final-001/review-inputs.json`） SHA `733693c3e4c1220a8e44e8baf6ad5031b1ddae2c8996d724c2e6b424b1c67390`，148源码、7个新dist文件；原console/dist及UI001包保持，独立delta封存中。

当前app a3安装配合新UI002包，经实际原WtBtPorter、业务HTTP及Edge完成roles、overweight、configured、bad-source、unconfigured五场景。全程没有route替身；每个配置场景仅启动一次，未配置零POST。完成模型均非forced、exit0且进程/管道回收；坏来源明确incomplete且无报告，失败路径回收不冒充完成。旧策略预热为空时不展示虚构持仓，后续可显示模型持仓；超额三日零新增提交并保留原生已持仓。

调用链封存（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-workspace-http-002/SEAL.json`）包含184份原件，manifest SHA `c0980ddf0878e64ba9f2a7de7fc8898e82954d930d608bcc960cadab200d2c07`。独占测试harness执行前保存源码及摘要，实际子进程执行该快照，临时文件位于E盘。安装中的原报告owner再次核对（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-workspace-http-002/audit.json`）全部13日HTTP投影与原生报告逐字段相同，36个原生输出文件摘要匹配；五组后台/浏览器均退出，应用关闭确认。已查看正常桌面、超额窄屏、坏输入桌面及未配置窄屏截图，中文核心数据与状态可见，无整页横向溢出。合成来源与模型资金的资格标签保持明确；完整后端独审、真实来源、RT和生产仍有独立验收工作。

## 后继：前端独立delta关闭

前端delta002（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-workspace-ui-review-002/REVIEW.md`）已正式complete，NBW-UI-F1/P2关闭、新增gap 0。报告SHA `5dbaff2f064379201d64d198b41290e9832c1af6e32f64005906874e35ea0374`，461份独审原件的manifest SHA `fbc1abe850106b886121ed52fac6367b9a143625f827dac1a2ac25044827c84c`。公开69项、独立39项及原独立边界38项全部通过，实际Edge20场景覆盖四种矛盾拒绝/恢复及精确分数高于/等于/低于1而浮点诊断显示100%的边界；类型、构建、分块及独立7/7 dist一致性通过。

根任务最终核对（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-workspace-ui-002/closure-integrity.json`）461份独审、13份候选、184份实际业务链原件及当前148源码/7 dist全部相符；相对原候选仅`backtestV2.ts`与其测试改变。前端审查仅使用内存HTTP替身与冻结静态包，真实业务链由上述独立原件证明；原后端首次full的缺项、真实数据、实时执行及发布资格继续保留。

## 后继：Session预算及完整回调期限

后端离线补核（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-backend-offline-review-001/REVIEW.md`）完成其限定矩阵：210项通过、6项失败，归为NVB-OFF-F1预算对象别名/入口重验和NVB-OFF-F2历史前缀耗时漏计两项P2。8原生场景的24记录/19个V2完整前缀及5个HTTP场景13日详情的既有原件复核相符，未重新执行这些动态场景；原首次动态full仍partial。根任务逐项重算607份封存原件，全部匹配，记录见完整性核对（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-session-boundaries-001/review-integrity.json`）。

在自有`strategy_session.py`修正两个责任边界：公开入口完整重建SessionLimits并复验既定硬限，缺字段按SessionError拒绝，内部持独占预算；V2回调入口建立一次截止，贯穿原生读取、逐行核对、子集、既有evaluate、capture、advance、报告及setter前检查。现有容量常量、计算规则、wire、Host/Runner/Job/Porter与WT框架保持同一实现。源码SHA `bc8bba08b5bb5aa96b0b28c90f44c15e8ce23d642365e96c168027149d45a3bf`。

新增六项根因回归，原始实现四项失败；补齐缺字段场景后保留第二份一红五绿记录；最终六项全部通过。新noneditable独立安装`v2-session-boundaries-001/install-b5df5cd7841140e59c2b2d81fdbf79f5`的242项软件回归（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-session-boundaries-001/tests-398b1b6bfa7c4a8eb1b820e614266035/receipt.json`）通过，app wheel SHA `266b675578548d1e0dfcc72711be2c50cce8f59899119b883819cc867aec33fa`。原安装及两轮红灯均保留。

本轮独立delta入口（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-session-boundaries-001/final-001/review-inputs.json`）绑定42项最终输入，SHA `e98057d6ee0013bd3e23de0ee0098e6adbdd37cb2e4386911e4b8b5badcb10e2`。产品保持冻结，独立软件/安装delta与新安装原生调用链仍在验收；该段开发结果尚不关闭两项P2，也不扩授真实来源、RT、交易或生产资格。

新安装的八场景原DLL矩阵（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-session-boundaries-001/native-6ee1e2b52fba4be0a0424975320d6e9d/result.json`）已实际通过：六个正常模型回放与两个预期incomplete拒绝，全部外层Job自然exit0、管道结束；正常Host完成条件按其原结果检查。完整前缀、精确NAV/现金、signal/execution、超额零新增提交、未知费用、T+1与configured均沿原断言重验。顶层与嵌套命令显式无控制台，原动态独审中止路径未重试；本项是作者对新安装的回归证据。五个新安装业务HTTP/无界面Edge场景继续验收，旧UI静态身份保持。

上述安装随后完成五个实际业务场景（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-workspace-http-003/SEAL.json`），207份原件，manifest SHA `554d45821df76970916d2e4605ab6686c2de850a489e3a508b6be5291327826d`；安装中的报告owner再次核13日DTO及36原生输出相符，查看了roles桌面、超额窄屏、坏来源桌面与未配置窄屏。第一次harness自动msedge路径误选不存在的用户目录，明确绑定现有系统Edge后通过，无浏览器安装；失败原件及服务自然关闭证据保留。

独立Session边界delta001（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-session-boundaries-review-001/DELTA-REVIEW.md`）结论F1关闭、F2剩余一项P2：采集首字段超时后继续读取其余字段，最终才拒绝；五条反例均零提交/零记录。310项通过、8项Windows TestClient内部socketpair因审查禁网络边界未执行；原动态full保持partial。根任务逐项核263份封存原件无差异。

后继仅在`_capture`复用同一check，封闭包装各个原生getter前后检查；configured默认不增加期限。新增五个触发子例含末次枚举，七项边界回归通过。最终源码SHA `4d964d04f59540259491e6220a761ae1f35119cd35c85937981bccbc53c40dd4`，新noneditable安装`v2-session-boundaries-002/install-c6137f403a0b45e0ab26eb7e5496593e`的243项软件和八个原DLL场景（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-session-boundaries-002/native-5d05d85ee0054fe4a291b15259910554/result.json`）通过。最终42输入（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-session-boundaries-002/final-001/review-inputs.json`） SHA `d3e52f60982fc448194fe319d4a9e22dcb477e027e8f2149658379e7d27b633b`，独立后继delta及同版实际HTTP继续验收。前一安装业务绿灯保持其原身份，不用于预先关闭此剩余P2。

## 后继：Session两项缺口关闭及最终业务链

独立delta002（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-session-boundaries-review-002/DELTA-REVIEW.md`）已complete，NVB-OFF-F1/F2均关闭，新增gap 0。321项纯软件通过，覆盖五getter到期后的零新读取/提交/记录及序号不发布；真实0.5秒预算、首枚举睡0.55秒的反例现在仅一次getter、约0.56038秒即拒绝。8个TestClient内部socketpair用例仍按该独审禁网络边界未执行，原动态full的整体状态继续保留，不将它们计入321项。

根任务逐项回核（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-session-boundaries-002/closure-integrity.json`）231份独审原件与当前42输入全部匹配；报告SHA `c6f014f85b8bc4249e1c5b7cb656eabad79300e4a93a7df37a213e074bfedc43`，manifest SHA `dbf69b98c35e052824f05776dce2e52e8b90a5ffcf9eb281f46f10a4b5ac8839`。

最终同一安装完成五场景实际业务HTTP/无界面Edge整链（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-workspace-http-004/SEAL.json`），185份原件，manifest SHA `2da0a34c5497d37aed6046a82537a7ed9b7813a886ef355f6ea8e16ff39562d5`。未拦截路由或伪造响应；roles、原始超额、configured、坏来源和未配置均通过，所有服务/浏览器自然退出并确认回收。安装中的原报告owner重新核13日DTO与36个原生输出相符；五场景DOM/视口断言通过，实际查看本轮超额窄屏，其他冻结UI源沿已验身份复用。合成来源、模型资金和未发布资格标识保持，真实来源、RT及整体动态独审的精确未覆盖项继续分别收敛。

## 后继：冻结回测配置的逐要求证据收敛

独立组合核对报告（外部历史/待归仓路径：`../../build/guanheng-workspace/v2-native-evidence-audit-001/RECONCILIATION.md`）及34条要求矩阵已封存。针对固定合成行情、模型资金、独立安装原生BT的开发范围，NSH/NVB要求均有匹配输入的组合证据，新增gap及功能缺证为0。依据为已核独立Win32生命周期/Porter原件、当前Session独立321软件回归、当前8场景原DLL及5场景实际HTTP/浏览器原件；本轮没有新增进程或测试执行。

当前软件仍准确记321 passed、8 deselected。8项具体业务断言经方法、routes/settings、Workspace相关方法、app初始化区间及312个框架依赖文件对应到既有独立实际TCP/配置重放证据；新report投影由当前321及13日DTO/36原输出覆盖。原始动态full中止与partial保持原样，本轮没有把它改成一次成功执行，也没有将复用的8项计为本轮通过。冻结范围内无必要的额外重跑，产品/资格域变化时再按影响确定。

审查入口SHA `e94b6b9a377e0d4cabeaf2d1272379e307777a49f1ec4cbacd1c5d1870ac0154`，报告SHA `69fc59cf41c763df862f4f31b2bbc007e8be2800d33e246759823b425084063c`，30原件manifest SHA `596b56b48160a5f6b1100a71d9dfa4aa466cda0b0f0f6c9570718634e72e4122`。根任务重新核对30份审查文件及180份外部原件，差异0，收据见`build/guanheng-workspace/background-window-fix-002/v2-evidence-integrity.json`。真实QMT/SDK、来源单位/覆盖、真实账户、实时执行及生产资格继续分别待验。
