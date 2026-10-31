# 独立观察受管调度安装进展

类型：开发验证记录。状态：in-progress；完整观察采集、模块C及系统目标继续。规格为[OBI5–8](../specs/independent-market-observation.md)，操作入口见[观察手册](../runbooks/market-observation.md)。原件根`build/observation-scheduler-001`，本轮全部来源响应为明确合成回放，真实供应商及券商请求为0。

## 实现与责任

新增每日北京时间09:00的独立调度子端。原SQLite owner持有采集lease，在来源请求前登记原窗口尝试；完成索引、新快照和成功回执共用提交点。两日补跑、投用日期、有限退避、崩溃计数和已完成去重共用同一窗口规则。批次沿调用者原D与配置预算的较早者，内容读取/保存检查停止信号；原ManagedLocalProcess拥有最终Job回收。

App以显式父部署/SHA及子配置/SHA托管已安装`observation_service.py`，读取根与采集根在启动前核同。默认无采集Job；配置失败保留原历史读取及其他工作区。停止先收束读取消费者，再停止观察、执行及来源，保留每个后继owner的声明窗口。心跳只报告最近观察，过期/未来心跳明确显示旧值；公开进程投影另由当前owner提供。中文页面补充配置失败与启动失败说明，策略页保持名称、简介和版本目录。

B交接的`managed-reader-proposal.patch` SHA为`1360bc37ee6933090885bed694cf8864af0d13366c314b92949e797d877942a0`；应用前原公共文件SHA为`6e76765ffce1071941830a190c4a1cbe3124d03d862054fcd953a0a11fb7049f`。C已按精确片段合入，当前文件SHA为`a6d26ecc0a4d956331a3bf5ace500ab1d445f26d1978978e70e1c8f370413fd3`，规范化换行后与B候选源码相同。真实Win32读取保留32/33、仅这些共享码按首关闭D重读；权限5立即失败。两层句柄接管失败各20次及实际持锁/释放/过期回归通过。B原生访问冲突和产品恢复资格分别沿[原证据](2026-10-29-native-clean-recovery.md)继续。

## 已核实原件

- `main-001`：实际安装的正式入口已启动调度，声明批次预算240秒；验收等待约234秒后触发停止，尚未取得发布。实际终态为collection_stopped，原current保持，窗口尝试1保留，closed证明调度与监视线程正常回收；预算超时路径本轮未触发。原失败原件保留。
- `main-002`：独立诊断入口调用相同安装实现，仅在外部记录阶段时间；合计269.438秒，完整校验245.141秒，模型重算0.531秒。3次本地HTTP回放→48指标发布→实际App/生产SPA宽窄屏→完成后重启零重复请求→两代正常关闭通过。该诊断结果单独登记，完整供应商覆盖和自然09:00资格保持未验。
- `main-003`：正式入口采集中停止后保留原版本及attempt1，正常关闭通过；恢复验收脚本误将原attempt1失败回执认作attempt2失败，脚本已按当前尝试身份修正，保留失败原件。
- `main-004`：正式安装入口完整复验通过，外层原Job总耗时280.453秒。第一代3次回放后采集中停止，原current与attempt1保留；第二代沿相同窗口登记attempt2并用3次回放完整发布48指标；第三代重启新增来源请求0、current与attempt2保持。三代closed均monitor_joined=true，父owner均closed/pending=false/forced=false/error_code=null；App读池、HTTP线程/监听及外层Job整树/EOF/join全部收束。1440×1000和390×844生产SPA读出明确合成2.125，只有GET、无运行错误。snapshot为`600bf2abdcd8c0e68faeb2930d7e2550952a07e1579d76e3b71d883677e96398`，原历史根catalog摘要保持。
- `backend-004`与`pytest-004.xml`：221项通过，覆盖观察读取/事务/预算/窗口、公共Host/来源/执行/HPR及统一关闭；共享读取器变化后的旧打开函数模拟已改为当前唯一打开边界。另5项新增配置隔离/同根准入/晚期构造失败收尾用例由`backend-extra-001`通过。
- `frontend-001`：45项通过，覆盖观察Shell/API/恢复、调度文案和策略目录；TypeScript、生产构建与分块检查通过。Browser plugin unavailable，实际浏览器验证使用既有Playwright/Edge。

## 当前安装与限制

Appa14第二份冻结wheel SHA为`40ffbf8fb19a559e89a55e2aa9dfe266d359b245b47be804f8308d4bed0cc8b5`，普通venv的30发行依赖检查与4678条带摘要RECORD完整核验通过。wheel85成员中84份非RECORD文件与实际安装逐字节相同；安装RECORD按安装器重写后的声明单独核验。83份App构建输入与当前源码保持相同，最终263份App/前端/相关测试与规范输入由`SOURCE-SHA256.json`绑定，SHA为`2a7c7fdb9cebdab042ae1b4751cd35e2078c5ad7db4a9ec8ef993b97cd922b1b`。

`INSTALLATION-002.json` SHA为`5fea7ef073c683a36e3c30e2a66132b32e48b1ac54e4a0613b8efe1c1e449bf4`，18文件SPA ZIP为`276fefa2eafafd442fd570b8ccbae6f505a6cbb79e5015db760bab6c0f85872b`。34份有限运行原件及6份QA入口分别冻结，`EVIDENCE-SHA256.json` SHA为`59e36108c5a00eadc0fea566e4e5f579d7d119b708095ae5f7240d519714a330`。诊断入口保持独立原件，正式main-004使用已安装原入口。以下独审结论限制当前候选资格。

## 独立full与修正续接

`SPEC-REVIEW.md`结论gap，三项P2：相对读取根与采集根准入不一致；未来1–60秒心跳仍running；source_table_parents未进入完整引用验证闭包。`STANDARDS-REVIEW.md`结论gap，两项P2：发布事务没有消费原批次D/取消；同根多个调度实例会覆盖单行心跳。两名审查者各自核263/34/6零漂移、30发行4678 RECORD及正常三代主链；正常工程事实保留，切片整体保持gap。

全部263原输入已在`build/observation-scheduler-002/review-base-001`复制并逐SHA核验，原wheel、SPA、清单及报告保持。当前源码随后进入delta，原40ff候选不代表后继修正。

外部隔离探针`LATE-PUBLISH-PROBE-001.json`实际复现：调用前约40ms截止，另一个写事务短持锁后，旧发布调用约281ms返回并改变current与窗口完成。未来30秒心跳仍running也实际复现。`RELATIVE-ROOT-PROBE-001.json`在进程工厂观察边界复现：读取owner缺失、绝对子根仍通过准入且调用start；探针实际创建子进程0，App线程全部关闭。

delta先增加根条件回归，原实现出现10项目标失败；同轮另有一个全局句柄总数下降造成的测试误判。后继已统一使用读取owner的local_root准入，拒绝相对根并隔离错误；未来/过期心跳统一降级；为源表父引用声明结构/身份，并加入采用与恢复的完整SHA闭包。句柄测试逐个核实际新句柄均已失效，同时要求总数不增长。`delta-green`实际100项通过，43.59秒；新结构亦严格核过main-004实际48指标快照。002根`DELTA-IDENTITY-001.json`绑定七项源码/测试变化、原263基线及红/绿原件。当前尚未重打安装候选或授delta审查通过。

下一段先将原D/取消传至发布的准备、锁等待、CAS与提交准入，验证锁等待跨D时current/回执/完成索引均保持；再确定root调度状态唯一发布资格，验证同根双实例及停止/崩溃释放。修正后重新构建安装、跑受影响主链并由两名原审查者确认delta闭包。完整21来源等后继范围保持。

后继继续21来源逐一解析/真实公开来源、非HTTP供应商及股票新增输入的预算边界、A八指数完整旧日期/单位覆盖、自然09:00、全来源失败/部分失败/崩溃恢复矩阵、当前切片双轴独审和最终发行组合。完整观察采集尚未完成。M1原生稳定性、全部策略、统一升级回退及中文全链运维仍属完整模块目标；无真实下撤单、QMT界面操作、生产切换或新增WT核心行为。

## a15原D与唯一调度修正后继

原D/取消已传至发布准备、SQLite有限等待、事务及提交准入；提交前停止保持current/成功回执/完成索引，网络前attempt保留。COMMIT后确认超期返回publication_unknown，由原候选SHA/窗口恢复核查，保持已提交事实且不追加虚假失败回执。存续期scheduler.sqlite3租约先于ready/心跳，短采集lease保持独立；只有有效线程/租约能够写根心跳。App的process故障与数据根scheduler事实分别展示。规格、ADR0015及操作手册已同步。

`build/observation-scheduler-002`保留原full基线及后继原件。`delta-boundaries-red`在原实现出现6项失败；`delta-boundaries-green`实际106项通过，48.83秒。后继增加租约释放后/跨线程写入拒绝及两类lease可组合检查，完整组合`backend-001`243项通过，59.31秒；`frontend-001`46项、TypeScript、生产构建与分块检查通过。

Appa15第三份候选已从83项冻结输入构建并安装到普通采集venv，30发行依赖及4678条RECORD完整核验通过。wheel SHA为`ec73acaf6ce31e04812dabda385939e2f45e6b4e8463304bc26e4bce12fbff44`；它与原a14身份分别保留。正式`main-001`三代主链在同一安装通过，原Job总耗时320.062秒：采集中停止保持原current/attempt1，同窗口attempt2通过全部历史/引用/股票分区验证并发布48指标，第三代重启新增来源请求0，三代正常关闭。生产SPA在1440×1000与390×844读出合成2.125，GET以外请求0、运行错误0；快照为`f5efa5076b61dd4b6b10230bf2771b94082d24bc3c1e1fa1bcd034a0a7c28866`。

`collision-003`已使用该安装原App/原子端/生产SPA验证真实同根两App：第二实例的failure.json为scheduler_already_running，HTTP及实际390px页面保持根调度running、本实例faulted。仅终止本QA持Job成员句柄的实际子端后，新App同根取得租约并ready；新实例正常停止。两故障App的shutdown_complete=false与最终pending=false、读池0、HTTP线程join/端口关闭分别记录；新App shutdown_complete=true。来源请求0，原current及回执保持，外层原Job整树/EOF/join收束。`collision-001`是验收脚本把pending等同仍在运行的误判，原失败日志保留；按ThreadOwner真实join语义修正后复验。

`INSTALLATION-003.json` SHA为`aef3e851cbd51f496cd208b27456c9f3273c14620ac6dd91bca8dcc3e8bf88d8`；18文件SPA ZIP SHA为`041185ff59d492fb9b7d57db76af2ea74e319882daa1d4c95b4eebf4d533a6e1`。本次266源码、53原件和10 QA分别固定，`DELTA-IDENTITY-002.json` SHA为`01ca98237896fd5ddf77ab4458a6d55f1286f25dbe25eb59d77979a6172a0ffb`，记录原263基线的19项变化。

两位原审查者已交后继结论，均complete（本次受影响风险闭包）。原三项规格P2及两项规范P2全部闭合；新增持久/未知恢复/唯一调度执行受影响闭包full，原条件逐项delta，244未变输入按身份reuse。`SPEC-DELTA-REVIEW.md` SHA为`5ed88c79f503dc6d1de91514075d80ef8c148dd9d335f6dc6d03ded0263fe480`，`STANDARDS-DELTA-REVIEW.md`为`e16cf994d15a0d06dc0e6427c39cf40c8edb0e80bea47aedced860d2d8e83a99`。两人独立核266/53/10零漂移、30发行4678 RECORD及实际主链/双App原件；没有运行额外进程或来源。

后继原件`DELIVERY.json` SHA为`0b35a79fc6987a6253cfd7f7a6918c2088fb5c43e7517c7a1826bbe3ce906b12`，末次检查源码、QA、运行原件、报告与实际安装均匹配。只关闭本工程切片，full_module_complete=false、goal_status=active；真实供应商、自然09:00、全部保留范围及生产资格继续。实装CLI磁盘提交异常/晚确认注入仍unknown，当前晚提交结果只授真实SQLite事务边界及消费者静态符合性。下一段按本根NEXT-SOURCE-BUDGET-PLAN.md处理非HTTP/股票新增输入，再补21来源和A八指数；完整M1/全策略/统一发行保持。

## 独立App程序升降级兼容

另建`build/observation-upgrade-001/runtime`普通venv，按固定hash requirements与SDK/纯包摘要安装30发行，不修改正在独审的a15安装。`validate.py prepare/exercise/identity`均沿原native.run隐藏Job与有限总D。演练在42.14秒内完成a14→a15→a14三代；各代实际安装wheel非RECORD成员与固定原件逐字节相同，通过真实HTTP读取同一48指标catalog、10-27合成2.125及生产SPA资源，snapshot均为f5efa507…c28866，查询行逐值相同。

数据目录在程序目录之外；三代目录数据库SHA、全部对象路径集合及原主链数据根catalog保持。各代正常关闭、App两个读池0、HTTP线程join/端口关闭，自动采集未配置，来源及交易请求0，外层Job整树/EOF/join通过。`IDENTITY.json` SHA为`642e86699425c6c51ba3a10f6451d684f05bfdc2f922f3519f84c423b7d13b3e`，绑定5 QA及21原件。

本项只授程序/观察目录兼容；三代未逐代重复全对象字节校验，未重复浏览器交互，SPA沿本次固定a15资源。统一安装器、原子切换、运行服务升级/回退及A/B组合仍待验；原a14已知审查缺口的生产资格保持原边界。
