# Host空闲领取与完整功能观察后继

类型：模块B隔离开发证据。状态：in-progress。适用[模块B完整目标](../migration/module-b-delivery.md)、[HIR-R1–R5候选](../migration/host-idle-read-claim-proposal.md)及[NRT-R31-C5](../specs/native-realtime-strategy.md#nrt-r31-实时执行阶段按券商实际数量确认)。本轮真实账户、下撤单、生产切换和新增WT行为均为0；全部新文件在E盘。当前库存作为首次起点，旧开仓历史和旧交易流水继续退出输入，新系统产生的状态沿正常恢复接续。

## 普通019终态

原full019与外Job73329已经终态，Source和原Native正常关闭，输入前后相同，根进程/子树/管道EOF/读取线程join/资源关闭全部取得。普通P29 DLL为9b43b80c89db9449ce311cd84cd399c79bb54f97e708988686dc66bc14c3ef42；原100毫秒来源回调、6982证券、65秒晚到、70秒目标及主场景400秒保持。41笔SDK替身订单全成，实际39100/目标50400，差11300；首轮70秒断言失败，完整三轮与恢复未取得。

FULL019-COLD-001（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/FULL019-COLD-001.json`） SHA f4f0b5879a742b44f2ce9b4782585f50ca2f4dd26f4ea063296c17ca119e8d18，25绑定。独立冷核（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/REVIEW-UNTRACED-019-001.json`） SHA 5c6549b41113e56c3bea9a07f714df9a5f036bfb24ff63cbb619e8a711c7a037，43绑定；仅授普通候选身份、实际部分结果与关闭范围。该轮没有请求时序包装，不从它推导单请求阶段耗时。

## HIR007实现与受控回归

候选位于build/ms-source-roundtrip-proposal-007，生产源码保持。PROPOSAL-001（外部历史/待归仓路径：`../../build/ms-source-roundtrip-proposal-007/PROPOSAL-001.json`） SHA 384acf336d2e2c79a76254c927d021ea671002df4bb5055a55e4f18ca231e331；METHODS-001（外部历史/待归仓路径：`../../build/ms-source-roundtrip-proposal-007/METHODS-001.json`） SHA 3ea28299d6799ca24b99d6f3f1f78b66951c0b4526c64e4bdae9210e87b4f540。新增ControlPeer.is_idle只读检查原阶段/准备帧/保留调用；Host._prepare_send仅在无任何通信责任时等待原claim，并继续原虚方法_admit，有责任或shutdown即发送，等待与发送共享同一首D。

`.tmp/ms-host-idle-claim-regression-001.py`使用实际Host.run/_admit/_progress_domain/_complete及实际ControlPeer，确定时钟、Future和内存Session覆盖28案。candidate全部通过；撤回005有9项门槛失败，包含已有短D调用/ACK/在途/新就绪调用与shutdown/原D。原版7项红属于新增空闲同轮能力的对照，分别保留其范围；11项peer状态案在三种模式均安装候选is_idle接口，不作为该接口的原版对照。SDK/真实运输/Journal为0。

三份REGRESSION-{ORIGINAL,WITHDRAWN,CANDIDATE}-001及ms-host-idle-claim-{original,withdrawn,candidate}-job-001/RUN.json保存原结果。外根58400/42748为预期断言exit1，75588为exit0；全部物理清理通过。发送故障保持原batch责任，关闭错误和域失败继续向原owner传播。

## 正式A003上的交易、只读和bulk兼容

正式来源端INTERFACE-001（外部历史/待归仓路径：`../../build/root-qmt-source-cohort-003/INTERFACE-001.json`） SHA fcc7e72e526c27c9399ea3d2cc04f25f02797254782cb344e225e9b0182d97db，Agent12+marketdaily.4 / Host20+sourcecohort.3，已经正式包含既有Source两文件修正。其control.py/control_peer.py与007原件逐字相同；control_trading继续原实现。

`.tmp/ms-idle-claim-trading-matrix-001.py`在该普通安装运行原test_host_trade_control完整44向量。原版和候选均44通过、0skip，真实SQLite、ControlPeer、SourceTradingService及SDK替身。候选Harness.cycle调用原候选_prepare_send；原Runtime夹具仅显式补connection_continuity=None并要求observe_source的continuity=None。TRADING-{ORIGINAL,CANDIDATE}-001绑定执行入口和安装源码，外Job35408/66228 exit0，43.368/43.495秒且完整清理。矩阵没有将helper返回的发送D交给真实Session，不能授真实I/O D资格。

`.tmp/ms-idle-claim-read-bulk-004.py`在同一正式安装运行默认read和两个原BulkHostChainTests，原版与候选各3通过、0skip。默认read实际Host.run→原domain→SQLite→AgentControlLoop派发/完成，核终态保存后ACK、只派发一次及原future退休。bulk核原页/CSV/manifest摘要、空源与最终保存后ACK；候选只把原prepare换成实际helper，fixture显式具备正式runtime已有的shutdown_started=false。READ-BULK-{ORIGINAL,CANDIDATE}-004及外Job39228/34708保存；exit0、6.016/5.992秒、完整清理。Session仍为内存传帧，默认发送仅检查调用时now<D，bulk不消费返回D；真实socket/SHM和Source原线程/tick不在这些夹具范围。

001误传legacy full-tick不接受的operation_profiles；002非规范+00:00时间戳触发JournalConflict，临时目录清理错误覆盖了首因；003将E盘临时原件保留后显露原JournalConflict；004只将测试时间戳规范为Z，业务断言和产品验证保持。原失败、输出和清理收据保留。

静态独审（外部历史/待归仓路径：`../../build/ms-source-roundtrip-proposal-007/REVIEW-IDLE-STATIC-001.json`） SHA f271b47ff82672b28b111444d260dfca8150182d216fabbbced7b8ed6587be05，99绑定；动态独审（外部历史/待归仓路径：`../../build/ms-source-roundtrip-proposal-007/REVIEW-IDLE-DYNAMIC-001.json`） SHA 036beca7dc94dc72f32bb700d16b76644a874ceca60be19f60a4d53bf915722f，160绑定。上述范围无新增确定P1/P2，完整业务收益继续单列。

## HIR007普通完整运行022

full022以正式A003、普通P29 DLL及隔离Host007三个方法运行，Source直接使用正式安装，未再替换其方法。原100毫秒/6982/65秒晚到/70目标/main400秒保持。35笔SDK替身订单全成，实际33100/目标50400，差17300；main.py174→continuous_rounds.py66首轮70秒断言失败。原Native closed.v2为ok/recovery_ready/exit0/resources_closed，Sourcepassed、输入完全相同，外Job31160 exit1及全部子进程/EOF/join/资源回收通过。

FULL022-COLD-001（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/FULL022-COLD-001.json`） SHA dbee0165dde9dfa208bdf03e8e3c5b574db71595de1e2488645c44a5b989b31b，27绑定；实际wrapper/QA-DELTA、Formal A接口及007方法绑定。旧CONTROLLER-SELECTION-022原本没有生成，冷核去掉该不存在的引用，使用实际QA-DELTA和运行原件。末次发布映射与停止后的全部实际成交之间仍有观察边界，未据最后部分投影认定最终映射完备。

007未取得完整性能收益，继续保留隔离候选，当前完整功能主链使用正式A003原Host。019与022的来源配套不同，两个实际数量不构成严格性能因果对照。新功能场景不把007带入正式依赖。

022准备时job020误传不存在CLI选项；job021引用wt_entry而实际文件为wt_cli；job022错误假定该QA有main guard，均在业务前退出且完整清理。后继按实际AST入口接入wrapper，唯一job023/full022完整运行。相关失败不计为产品执行结果。

## 新完整功能观察R31-C5

原规格要求完整买卖、数量确认、停止和恢复；70秒来自原continuous_rounds的QA等待窗口。已在NRT-R31-C5明确新观察：单轮240秒、主场景1200秒、外层1500秒。原70秒结果及性能缺口保持。单请求/队列/SDK/计算/来源新鲜度/未知责任/关闭截止保持；目标、分单、100毫秒回调、6982证券和65秒晚到、原业务断言保持。新功能观察使用正式A003原Host/Source及普通P29 DLL。

`.tmp/ms-functional-full-023-generator.py`生成`.tmp/ms-functional-full-023.py`，full023控制器原生成SHA为7ee471e82dd57ee1db323d8108e469b1ddd5b2336fd59f531f79d06ffecc77f8，原现场未另冻控制器。后继93af8bbc7c26070910a37fd23a41a557dc48fe1672f9829f2d0e552aa1bd5381实际用于full024并保存于该次CONTROLLER-USED.py；误放入full023的同字节副本已改名CONTROLLER-SUCCESSOR-REFERENCE.py。full023/CONTROLLER-RECONSTRUCTED.py从该后继逆向去掉唯一QA断言替换并按原CRLF编码，SHA精确重建为上述7ee；CONTROLLER-PROVENANCE.json明确其事后重建性质，历史失败和实际QA快照分别保持。后继最终SHA d7480d5acebef43d119174290143d727a1a53f197486d621519bcfeeb539d155。QA调整限定continuous_rounds的actual_deadline与observed70→240、恢复account_match70→240、主D1200及run_control的总体观察参数/一致性断言，外Native包装MAIN-CONTROL为1225秒。产品配置不由这些调整改写。

full023/job024在check-only的args.seconds==600预算一致性断言退出，业务尚未启动；修正其QA断言为1200并保留失败原件。此前job023因生成器文件尚未成立退出，均完整回收。full024/ms-functional-full-job-025已终态：41SDK/39100对50400，仍在continuous_rounds.py66断言失败；原actual_deadline=time.monotonic()+70还有独立QA手动总窗口，首版只改until未同步该赋值。这轮未实际取得240秒功能观察，不能以其结果认定240秒不够或新产品故障。Native正常、Sourcepassed、输入保持及全部回收。FULL024-COLD-001（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/FULL024-COLD-001.json`） SHA 3abc7d218887cc40ee56803b18b1829fb91529f1d3476a3738982a1efcb999d3，25绑定。后继以AST精确选择actual_deadline赋值的右侧70改为240，保留原位置到位断言和全部产品截止。full025/ms-functional-full-job-026已经终态：首轮53笔SDK替身全成，逐证券目标与实际完全相同、均50400份，原Native最终converged、映射53/submission_revision53；QA仍在原位置到位断言失败。Sourcepassed、Native正常、输入精确及外根57224/全部子树/EOF/join/资源回收通过。后继继续定位QA冻结首次发布的判定链，完整三轮及恢复尚未取得。独立审查按当前脚本和该新case进行，不据启动或受控回归授完整B或统一候选资格。

默认read/bulk独审（外部历史/待归仓路径：`../../build/ms-source-roundtrip-proposal-007/REVIEW-IDLE-READ-BULK-001.json`） SHA aea4852398c86c980e2c279a1a915cf6d2ea773b6e7252f7122ada613c333f34，192绑定/0漂移，三条内部链限定资格和实际运输边界分别保持。文档检查ms-host-idle-document-check-job-001实际exit0、18088完整回收，只授导航及技能清单完整性；本段为其后新增文档，最终检查后继另记。

## 首轮实际到位与QA发布身份根因

FULL025-COLD-001（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/FULL025-COLD-001.json`） SHA 35e75a4edadc37f02c2870f195e6c8fccf20e6afc35dc019d2e22f539dd912a1，25绑定，确认53SDK/实际50400/目标50400/差0，全部委托成交，原策略最终converged及53条映射/修订53。该轮确实执行240秒观察，完整主链仍失败。原报告的final_mapping_after_quiesce_unknown为保守边界；其同一报告已分别记录最后发布映射53和SDK53，不据此推导未覆盖时段的普遍映射保证。

直接链路：原QA仅当decision.market_window.publication_sha256等于首份success摘要时更新chosen。持续发布者runtime325–352按每次来源接收时间更新analysis.known_at/current_view.received_at，合法后继发布有新的SHA，每轮另存PUBLICATION.json。025共7份原发布收据，末次原生窗口恰与其中一份匹配；首份决策仍为selling，后继真实converged的发布SHA不同。旧QA因此持续使用早期chosen，即使原数量、成交与修订已经到位仍判失败。生产发布者和策略状态保持原行为。

新增隔离QA helper `.tmp/ms-functional-publication-match-001.py`按decision精确SHA查原PUBLICATION，核同根work、原CANDIDATE/RESULT/NATIVE摘要及capture；按生产者原两处时间赋值与qna.canonical重建发布SHA，再核expected phase的basis和原价末行。缺收据保持待确认，证据冲突使QA失败。只替换原两处decision筛选式，原策略收敛、逐证券数量、修订/成交全量、资金与账户投影断言保持。没有新增产品账本或修改发布者。

原件回归001（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/PUBLICATION-MATCH-REGRESSION-001.json`）在停止后的025实物完成8案：旧首份门拒绝真实后继收敛、精确同phase通过、两错phase/无收据拒绝、两种摘要破坏失败、原53/50400完整业务谓词保持。SDK新增0，Job58308 exit0/0.898秒且完整回收。

独审发现helper001容量检查发生在read_bytes/list分配之后，P2在后继`.tmp/ms-functional-publication-match-002.py`修正：打开后fstat先核尺寸，再read(limit+1)并复核实际长度；PUBLICATION逐项计数，最多检查4096份。当前026在途副本仍为001，保持输入原件，实际模型范围与最终通用有界实现分开登记。002同实物8案（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/PUBLICATION-MATCH-REGRESSION-002.json`）通过，Job65672 exit0/完整回收；容量旧红（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/PUBLICATION-BUDGET-OLD-001.json`）精确触发读取后检查及先生成5000项，新绿（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/PUBLICATION-BUDGET-NEW-001.json`）保持超限读取0、最多生成4097/解析4096。Jobs66872预期exit1及44440 exit0均完整回收，没有实际巨大分配或SDK调用。

预算静态独审（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/REVIEW-FUNCTIONAL-OBSERVATION-001.json`） SHA e33193adf2e137c485853ba26458eb9f6b49b61479f1216f2810a106a98264d8，104绑定，确认修正后的actual_deadline及until均240、恢复240，反向AST与原三QA文件一致，产品D保持。该报告授预算选择范围；发布匹配器及后继容量修正由新独审另封，不覆盖原报告。

当时普通full026/ms-functional-full-job-027已经启动，exec83939为该时点唯一业务句柄；控制器`.tmp/ms-functional-full-026.py` SHA 52a43bc790f2099cb3995304ddddb7a2a8bed6430d03542ccf0345d3ef57b982，正式A003原Host/Source、普通P29 DLL、完整R31-C5观察和QA精确收据匹配。其后终态及后继见下文。整个B、70秒性能及统一候选完整资格均未授予。真实QMT现场由A独占，本轮没有操作现场或真实交易。

## 账户发布读取复用原大帧入口

full026/job027已终态，首轮53SDK/50400逐证券到位，BROKER-LAST-001存在；随后QA使用普通status的64KiB读取器读取238909字节账户发布文件，产生CollectionStatusError(capacity)。原产品App已具备`account_publication.read_publication`，沿同句柄及20MiB+64KiB合同读取，无需新增产品读取器。原件回归（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/ACCOUNT-PUBLICATION-READ-REGRESSION-001.json`）确认旧容量触发、原NAP全文精确及原schema4投影完整，Job51656 exit0并完整回收。FULL026冷核（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/FULL026-COLD-001.json`） SHA 7767bc916e2137822f21f900a2e390f491da255d1fc7b451c93f6a77bd1da326，28绑定；Source/Native正常，全部物理回收。三轮和重启仍未通过。

028 QA使用helper002精确发布匹配，并以原安装App子进程调用NAP读取。独审在后继030补齐最早phase D向Child传递，以及snapshot读取/解码后同D检查。原Child真实受控sleep回归：旧监督工作到13.068秒越过phase12秒；新监督保留原10秒清理预留，2.020秒进入关闭并在phase内完整回收。此受控测试刻意触发强制停止，两个Child exit1为预期，外Job66988 exit0及物理字段全通过。独审001（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/REVIEW-ACCOUNT-PUBLICATION-QA-001.json`） SHA 6b0217102f3841bf3b4eb9ef689043dcd6f8071c8b278eea2aba1cc5c29db30d，65绑定，保留CLI将可重试pending变硬失败的开放QA P2。

后继`.tmp/ms-read-account-publication-002.py`在原reader调用层恢复FileNotFound、CollectionStatusPending及WinError32/33沿同D重读，其余错误立即传播。有限回归（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/ACCOUNT-PUBLICATION-PENDING-REGRESSION-001.json`）8案通过，包括持续pending到原D、协议错误首调用失败及原026完整NAP实物；Job37364 exit0、0.674秒及完整回收。031/032使用该后继，028原输入保持。本项只修QA，SDK新增0、产品编辑0。

## 完整首轮通过与短夹具寿命冲突

full028/job028/exec58916已终态：首轮53笔SDK替身委托全部成交，逐证券目标=实际、总量50400，原Native converged且53映射/修订53；CONTINUOUS-ROUND-0、BROKER-LAST-001及完整账户PUBLICATION/PROJECTED/HTTP均已保存并通过原断言。该范围首次完成完整首轮及读取核对。第二轮在continuous_rounds42→main.until64产生TimeoutError，三轮及重启失败保留。

同次QA prepare_execution仍赋原短场景run_ms300000。原CtaProcess480按配置设置run_until，到期沿正常关闭准备退出；ready至close-prepared实测302.004秒，准备凭据ok/recovery_ready=true；0.374秒后owner记录unexpected_exit，未生成监督closed.v2。WT外层exit2、forced=false；外Job39032 exit1，所有业务子树/EOF/join/资源均回收。同期AWP保留source_pending，最后5份发布及analysis/hpr保留表均有terminal事实；该观察不单独证明来源缺陷，也不用于归因WT。

FULL028冷核（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/FULL028-COLD-001.json`） SHA d9487ea4c7aafe8960e9ffe38a530eeb8539fc22bb074caafdb310bb466440b8，28绑定；实际控制器72666f70…另存CONTROLLER-USED.py，输入精确、Source正常，正式A003原Host/Source与普通P29 DLL保持。首轮通过、物理回收与完整监督关闭分别登记，整体模块资格仍false。

后继控制器032 SHA b31bfd6123909503a1264ccb415e82bb9f86b72d8bf9f9a9abacce8749547043，在031原NAP/pending/父监督D基础上，仅将QA prepare_execution的唯一run_ms赋值300000→1200000；原启动/单请求/SDK/队列/计算/来源新鲜度/停止截止保持，生成的配置及摘要沿原准备链重建。后继完整三轮、同根恢复、费用和最终组合资格继续实跑验收，当前结论仅覆盖上述已取原件。

032首包装误用不存在的Python路径，pid=null且业务未创建；job033使用实际C:/Python314/python.exe后，032控制器在业务前因TypeError退出，steps/processes为空。准备专用回归PREPARE-TRACE-033将异常定位到控制器187的`load(original/name)`：030插入的顶层AST变换把原Path变量original覆盖成AST节点。034仅将该变换放进独立函数局部作用域，原Path及业务准备流程保持。PID45244和准备回归20772均exit1/完整回收；这些失败属于QA业务前范围。

QA读取delta独审002（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/REVIEW-ACCOUNT-PUBLICATION-QA-002.json`） SHA ab4a828e3fcd7614654278c8c9f9c0a740e607644165517520ab3ab780c01838，47绑定，原pending P2已按原C循环AST和有限回归关闭，当前增量开放P1/P2为0。QA寿命/作用域独审（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/REVIEW-QA-LIFETIME-001.json`） SHA 5724e9b4baa4d5798cfe53a58d100dfd41a286a35b481bb5cb1c6dd1d689f68c，49绑定/0漂移，授最终034静态限定资格；完整业务另验。

当时唯一完整业务full034/ms-functional-full-job-034/exec69940，控制器`.tmp/ms-functional-full-034.py` SHA 7ac52c6b0377eecd929cb6e186af37820956ed5841b821933e573265c7934055；角色预检通过，首轮SDK53/50400已到位。现已取得下方终态，保留历史时点，不据观察超时重启业务。

## 最终正式订单与多策略矩阵的配套准备

最终矩阵尚未运行。已将原订单O1–O5、组合add/exit/net/pending/partial和unknown入口的QA定义冻结到新目录，并将原测试入口的执行进程导入与包路径断言切到实际安装的WT运行侧；原业务判定保持。显式预导入正式A003 Host/Agent和root-continuous006 WT/App，原正式API/Factory/CTA/WinSHM继续由实际产品承担。原泛化合成目标策略与保留算法主链分别记录。

测试插件FIXTURES（外部历史/待归仓路径：`../../build/ms-final-matrix-fixtures-003/FIXTURES.json`）绑定174输入：三个测试DLL重新用Native006固定头及绝对原库编译；原GuanhengCtaExecution.lib摘要72ad22c2…、CtaExecutionSession.h摘要85ab9348…保持。首次脚本语法错误在编译前退出；后两次分别缺原相对Includes及FasterLibs目录，原件保存且全部回收。最终复制固定Includes/Share/FasterLibs头闭包，三DLL编译成功，外Job10332 exit0/14.663秒，三编译子树及外Job全部回收。产品和WT源码编辑0、SDK0。

最终准备收据（外部历史/待归仓路径：`../../build/ms-final-native-matrix-preparation-003/PREPARED.json`） SHA f5691b6af1f4bd1b74b8cea2041d891dfdf51b994be3c3025dec4445f65c8b5d，801绑定，包含原测试源码、冻结QA、实际角色源码、P29 Native及测试DLL。准备首版错误假定存在guanheng_common包，在任何业务前停止；后继按正式Host实际两个包固定，没有新增兼容包。仅导入预检（外部历史/待归仓路径：`../../build/ms-final-native-matrix-preparation-003/IMPORT-CHECK-001.json`）确认四角色及四测试模块均来自指定安装/冻结目录，未构造owner、SDK0；外Job40680 exit0/1.527秒且完整回收。最终独立审查与11入口实际矩阵仍待执行，准备和导入结果不授订单/组合业务资格。

本次文档检查job004在45秒观察内未完成，超时回收原件保留；同一命令后继job005使用有限180秒外窗，实际1.159秒通过，PID52624 exit0及完整回收。检查只授文档导航及技能清单完整性，本段后续文档仍需最终检查。

## 完整三轮通过、原生正常关闭与系统停止缺口

full034/job034/exec69940已经终态，外PID61932 exit1且全部回收。原同CTA实例完成三轮原生d1更新，三个不同core输入和发布摘要、新共同闭合日及同日修订均通过原判定；各轮实际/目标50400，53笔SDK替身委托全成，完整账户投影/HTTP相等。策略HTTP和800点报告HTTP通过，App停止后另有新scan发布且原组件PID保持。

执行组件已生成ok/recovery_ready/exit0/resources_closed的closed.v2，原`.cta-clean.json`存在。根系统停止时，analysis_window仍stopping/pending=true/closed=false，根首错为component_close_analysis_window；collection随后stop_timeout/forced=true。WT外层exit2、forced=false，Source正常且所有子树、EOF、reader join和资源均回收。原main在247的stop_wt退出码断言失败，SAME-ROOT-RECOVERY未开始；根closed证明缺失。三轮及Native单组件关闭通过，系统完整停止/恢复继续失败，两个范围分别保留。

FULL034-COLD-001（外部历史/待归仓路径：`../../build/ms-query-coalescing-full-001/FULL034-COLD-001.json`） SHA 22eed0fe064b89e4a4dfd31ccd39d576ca4e442784337ac60e0c79067780ea0a，40绑定；关闭owner接口（外部历史/待归仓路径：`../../build/ms-functional-close-owner-interface-001/INTERFACE-001.json`） SHA 26ae9f6bb42b457e913ce50b93e1c748ebb7d9d3017b41a9e6de911cc47f7320，提供原系统/分析/采集侧后继使用。没有据根关闭失败归因WT，没有改其多线程行为。安装工具三项不在该次INPUTS-BEFORE内，主会话其独立候选开发不与该冻结输入冲突。

另外静态发现原main最后停止态账户检查仍有一处通用read_status读取NAP；该轮未到此处。035控制器 SHA aeca998c67aa619cd75664c6fc5b97fa09ac77fbe4946ff26e6fc032baaa132b只将其改用现有read_account_document，保留尾段所有原断言，尚未跑业务。此未触发QA遗漏与本轮实际系统停止失败分别登记，不能用有限尾段读取替代缺失的系统恢复验收。

最终矩阵准备首O1因runpy未把冻结run所在目录加入sys.path，业务前ModuleNotFoundError@run227；PID35256 exit1及完整回收，SDK未启动。后继PREPARED004（外部历史/待归仓路径：`../../build/ms-final-native-matrix-preparation-004/PREPARED.json`） SHA bbe76ca97882d217dc79050cc623fe3cb2f7199e0c8e40ef43dd4efdd072614e只补原脚本入口的目录搜索语义。O1已实际通过：终态迟到/重复成交后继续目标、原Factory/CTA/WinSHM及正式A003/WT/P29，外PID53288 exit0/10.226秒并完整回收。其余4订单、5组合及unknown由唯一ms-final-native-matrix-job-001/exec38213顺序运行，业务终态与独审后继另封。原准备层独审（外部历史/待归仓路径：`../../build/ms-final-native-matrix-preparation-003/REVIEW-EXECUTION-001.json`） SHA73c77ba6ac18e0b5f7edbf70f337c41383ea18caf46203dad5e5daad1abd484b绑定003限定静态范围，004目录搜索delta及实际动态身份另验。

## 最终正式矩阵、恢复和独立候选

上段38213已终态。正式P29/A003的五订单、五组合及unknown共11入口全部完成；矩阵冷核（外部历史/待归仓路径：`../../build/ms-final-native-matrix-preparation-004/MATRIX-COLD-001.json`） SHA 1f3c6d80c287a1f12d7533917190cf766fa96c848b8376d9f5ca18ce23d21fdf，945绑定。合计121次查询、18次下单及3次撤单尝试，均为SDK替身。O1–O5最终A800/B400、券商1200，迟到/重复成交保持去重；组合包含买1000、A退出卖600保留B400、反向目标零净额、在途400以及部分成交500。未知提交保留原命令身份、禁止重复POST，故障关闭与物理回收分别成立。剩余10入口外层74888 exit0/73.861秒，所有子树完整回收。

实际执行独审（外部历史/待归仓路径：`../../build/ms-final-native-matrix-preparation-004/REVIEW-EXECUTION-001.json`） SHA 99aa81ecd4590d44543a5431e86c0a53fe852c5d1a3eadbb4a9cb03d779fbce9，直接115绑定并复核801准备输入及945冷核输入，新增开放P1/P2为0。资格覆盖原泛化目标策略和实际安装的执行/通信链；保留1.1.2算法完整系统、自然跨夜、真实券商及整个B分别验收。

普通安装的恢复冷核（外部历史/待归仓路径：`../../build/ms-final-native-recovery-002/RECOVERY-COLD-001.json`） SHA e0a9793f49b56786eaf5728cbaf6b738c74693bcce8b601757f56c44f4097fe6，831绑定。两代Native34408/53812均正常closed.v2，第二代恢复A800/B400和原KV，新增SDK0。七项拒绝覆盖活动委托、状态摘要、额外状态文件、配置绑定、缺clean、缺closed及不支持的原生模式，各按原阶段拒绝并保留金融状态。QA只将失败实例的收据读取切到实际close-prepared.v1；原成功closed.v2语义保持。外层72316 exit0/17.207秒及完整回收。恢复独审（外部历史/待归仓路径：`../../build/ms-final-native-recovery-002/REVIEW-PROTOCOL-001.json`） SHA 0426deb225c04aa23e60d072d97483209c36fcc23c2af26046686cfaab5b86ed，直接38绑定并核831/801闭包，开放P1/P2为0；失败准入实例缺独立OS退出码时保留unknown，不由prepared推造成功退出。

未知提交后的冷重开（外部历史/待归仓路径：`../../build/ms-final-unknown-transport-001/reopened/RESULT.json`）完成四项当前账户查询，新增SDK0/POST0，Host持久unknown=true、新Source本地unknown=false，仍禁止新下单，原Journal和金融文件保持。新Host与Source共用实际fixture进程73852；43000是外层受管QA启动器。原OWNER-IDENTITY中old_source_fixture_pid=23064来自旧启动器收据，旧实际fixture PID缺独立证据，角色口径以后继审查更正，原收据保持。此项验证只读重开和保留未知责任，未知结果处理及Native/WRI重启另验。

独立候选包（外部历史/待归仓路径：`../../build/ms-final-p29-package-001/PACKAGE-001.json`）为61成员ZIP，SHA 461ca94f5b515e28e0e3d657693405efb41e368f38fe110796b6bf2295aba163；552个Python源码/扩展与实际WT安装逐字节一致，23-wheel依赖保持其原WT角色，外部正式Host/A003独立安装。新目录离线安装（外部历史/待归仓路径：`../../build/ms-final-p29-portable-003/INSTALLATION.json`）成功，23个发行包、1332条RECORD/1309项摘要。候选包内容冻结，整体交付资格false。

离线安装后的实际两代运行出现新的关闭失败：外层RUN（外部历史/待归仓路径：`../../build/ms-final-p29-portable-recovery-job-001/RUN.json`）为43980 exit1，物理回收完整。首代Native13436正常closed.v2；第二65920已恢复A800/B400和原KV并执行schedule，close-prepared.v1为closed=true/ok=false/recovery_state/recovery_ready=false，没有成功closed或新clean；七项拒绝尚未进入。旧consumed及失败金融根保持。自有CtaProcess关闭钩子检查执行责任、宿主状态、健康、状态文件身份和证明发布，异常在Session.close锁存为Close；现有收据缺少具体失败检查。当前定位范围为自有钩子诊断，WT原线程方式保持。本次失败保留普通安装已验范围，同时使搬迁恢复及整个B继续pending-verification。

包后续资格收据（外部历史/待归仓路径：`../../build/ms-final-p29-post-install-qualification-001/QUALIFICATION.json`） SHA 8620be882491b6bd1f06e764eefdcb6676705fe6b944e89d04beed97d4bba14d固定19个实际输入/失败原件，明确portable_recovery_qualified=false及ready_for_unified_candidate=false；原ZIP保持冻结，后续诊断运行使用单独目录和仅自有钩子枚举的诊断Runtime。

### 搬迁关闭失败的有限复现后继

自有钩子的诊断Runtime只记录recovery/host/health/state_identity/publish五种固定阶段及原返回码，链接原Native006库，WT改动0，原共享源码及失败状态均保持。首次准备错误核成较早Native006的CtaProcess身份，业务前退出；第二次按实际C050来源编译成功，随后发现源安装根没有QA运行时才生成的execution-install.json，准备在复制后退出。后继003直接复用已成功的编译产物，QA继续按原入口生成安装清单。两个准备失败的原件和回收证明保留。

诊断运行003的一轮、复现004的三轮均通过两代恢复及七拒绝；复现005进一步缩到两代恢复，八轮全部通过，外层73124 exit0/83.739秒及八个子树完整回收。004最初的关闭后缓冲读取晚于监督器清空，005调整为原pipe reader完成后、原资源回收前仅提取固定诊断前缀，原reader/关闭判定保持。上述12轮都未重现关闭失败，不能由空诊断反推失败原因。

随后直接用未修改的原候选Runtime和同一离线安装环境运行portable002（外部历史/待归仓路径：`../../build/ms-final-p29-portable-recovery-job-002/RUN.json`），外层9756 exit0/17.182秒及完整回收；两代恢复（外部历史/待归仓路径：`../../build/ms-final-p29-portable-recovery-002/run/CLEAN-RECOVERY.json`）和七项拒绝（外部历史/待归仓路径：`../../build/ms-final-p29-portable-recovery-002/run/RECOVERY-BOUNDARIES.json`）均通过。此结果证明原候选在搬迁安装下存在通过运行，同时保留001的实际失败；具体失败检查与根因仍unknown，整体资格继续待验证，诊断Runtime不进入发行包。

冷unknown运输独审（外部历史/待归仓路径：`../../build/ms-final-unknown-transport-001/REVIEW-EXECUTION-001.json`） SHA 89f4574ed034c6862eb6b948043febdd5ef7a06abc880ecc45d96ac0de0d8998固定37项绑定，开放P1/P2为0；四查询、SDK0/POST0、原unknown/金融文件及PID角色更正均按原件核实，Native/WRI恢复和未知解除继续gap。后继文档检查job007实际0.915秒通过，PID76520 exit0/完整回收；本段追加后的最终文档检查另记。

## P30 停止事件读取的分类根因与普通候选

已确认自有Standard的两条停止退休路径对同一结果采用不同规则：ControlStoppedBeforeStage在普通退休保持正常，worker已join的最终退休却把其Unavailable状态记入first_error；后继recovery.unsafe因此成为true。此差异发生在自有接入层，原WT行情/策略/保存流程保持。portable001没有具体关闭检查的同次记录，故其准确原因继续unknown；本节确定的是可复现的自有分类缺陷及其受控修复。

原实现红例（外部历史/待归仓路径：`../../build/ms-stopped-event-retirement-red-001/RESULT.json`）使用固定P29真实实现及原event_stopped构造，六项只有最终退休的controlled_stop失败：error=1/unsafe=true；普通停止、正常成功及真实Failure各保持原语义。候选绿例（外部历史/待归仓路径：`../../build/ms-stopped-event-retirement-green-001/RESULT.json`）六项全通过。两者都调用公开release并核payload、队列、任务及可删除状态；范围为合法完成值状态验证，HTTP/SDK/WT运行0。外层51040与37856均exit0、完整回收；原红例内部164 exit1为预期反馈。

真实worker红绿（外部历史/待归仓路径：`../../build/ms-stopped-event-worker-regression-001/RESULT.json`）进一步经原Factory对象、真实Standard::work、原控制停止结果和既有kind2发布门，将完成值保留到最终release/join退休。原实现error1/unsafe=true；候选error0/unsafe=false，已有unknown时仍unsafe=true，两案Factory实际删除且资源完整。原worker负责构造结果，测试没有以自造Completion替代该链；客户端构造和控制停止发生在实际HTTP之前，HTTP/SDK0。外层33204 exit0/11.379秒及各子树完整回收。

候选源码SHA 818fa8e433fa98f022f07bb8cd85908e9ee1fb69ebfbdcd3dc341bb904c11bcf，以同一个retain_stopped_event_failure分类函数供两条原退休路径调用，保留真实Failure及原首因。原live源码保持；普通构建（外部历史/待归仓路径：`../../build/ms-stopped-event-production-build-001/BUILD.json`）只替换TraderQMTStandard.dll，SHA 694dc60ba46c0100b541c7242447cb7b77f401b14d06073c80b7d62beae74ce0。其余Native成员及原WT库完全保持，普通编译不带事件测试门，诊断Runtime排除。

P30正式矩阵冷核（外部历史/待归仓路径：`../../build/ms-p30-native-matrix-001/MATRIX-COLD-001.json`） SHA 6b589a0179332272e2f56ca42fe21cb58f6da33b1dc3f261eb619d4e21e27571，974绑定；五订单/五组合/unknown全部重新运行，121查询/18下单/3撤单尝试均为SDK替身，原身份、目标、迟到去重、价格及关闭判定全通过。外47736 exit0/87.353秒、11个子树完整回收。

P30两代及拒绝冷核（外部历史/待归仓路径：`../../build/ms-p30-native-recovery-002/RECOVERY-COLD-001.json`） SHA d63c68b9843e06b3aba5686164e2c9b584d1e38e76a495d575ffa755d05a9c5e，853绑定；正常同根两代恢复原A/B及KV，SDK零增量，七项拒绝保持原状态。外48924 exit0/31.492秒、完整回收。首次001仅因QA从新manifest根寻找仍位于原run旁的helper而在业务前FileNotFound；002按manifest中的实际run路径定位同一helper，原断言和产品保持，失败原件55144 exit1/完整回收另存。

P30候选ZIP（外部历史/待归仓路径：`../../build/ms-final-p30-package-001/PACKAGE-001.json`）为65成员，SHA 20475221128918a662a2450ec2ae25a2156d5ed9776d246cc080b219cb380bcf。23个WT wheel与原P29保持，附原P29来源、P30源码差异及两份回归探针；仅普通Standard DLL更新，实际包内排除了测试门和关闭诊断前缀。候选声明搬迁P30恢复待验证及整体资格false，后继普通安装使用新完成的固定CPython锚点。P29旧包和根组装固定入口（外部历史/待归仓路径：`../../build/ms-final-p29-root-handoff-001/HANDOFF-001.json`）保留其历史资格，P30最终交接另封。

### P30 固定解释器搬迁与原账户互斥

全新离线安装（外部历史/待归仓路径：`../../build/ms-final-p30-portable-001/INSTALLATION.json`）已完成，23发行包、1332条RECORD/1309摘要；基于E盘固定CPython锚点的3320文件在安装前后全部一致，pip及venv均使用该锚点，未使用可变C盘基础解释器作为本次WT角色工具。外68180 exit0/41.747秒及全部子树完整回收，23个wheel和65成员包的原字节保持。

首次搬迁启动在account_lease拒绝：Native51568、外59164 exit1，查询0/SDK0，完整回收。只读核实Root整体停止测试的实际Python5512已载入自己的执行Runtime，且两端account/environment/profile三项完全相同；原值未输出，原Root实例保持运行。互斥拒绝原件（外部历史/待归仓路径：`../../build/ms-p30-portable-owner-busy-proof-001/REFUSAL-001.json`） SHA 798619302cf02b8a1e8ba08d68241b7c746c316cd473930604b22ed543eb642e保留该事实。实际确认5512已经退出后，才以原账户身份和新目录执行后继；没有改账户键规避保护。

搬迁后继002（外部历史/待归仓路径：`../../build/ms-final-p30-portable-recovery-job-002/RUN.json`）实际通过，外39276 exit0/23.528秒及完整回收。Native57392/35176均closed.v2、ok/recovery_ready/exit0/resources_closed，恢复原A800/B400及KV、额外SDK0，七项拒绝保持原金融文件和证明。搬迁冷核（外部历史/待归仓路径：`../../build/ms-final-p30-portable-recovery-002/RECOVERY-COLD-001.json`）再次核包、26个实际Native成员、实际WT模块来源、普通收据和固定锚点3320文件，全部一致。此为P30固定解释器安装的限定执行恢复资格，正式1.1.2全组件WRI重启、未知解除及整个B仍待。

最终P30独立delta审查（外部历史/待归仓路径：`../../build/ms-stopped-event-retirement-stage-001/REVIEW-EXECUTION-001.json`） SHA f088e406bc1503f1c89ecd70ae4053d742f527d9bf08d3f0be19fd012f929a7f固定108项直接绑定，开放P1/P2为0。源码分类、票据/收费及join顺序保持、局部红绿、普通11矩阵、普通/搬迁两代及七拒绝均已核实。旧P29 portable001同次原因保持unknown；搬迁完整11矩阵、正式WRI及整个B分别列gap。账户占用者5512的角色来源按人工只读观察结合机器account_lease/0查询/0SDK证据描述，未将其称为内核mutex owner自动证明。

安装后限定资格（外部历史/待归仓路径：`../../build/ms-final-p30-qualification-001/QUALIFICATION.json`） SHA 318fb7e7eb60baa7fc8c7e56a751fa06caa8f8b42f757774cb75afd5c642fa9e绑定23项直接输入，重核974/853/884三份冷闭包及全部成功Job，保留整体资格false。P30根组装交接（外部历史/待归仓路径：`../../build/ms-final-p30-root-handoff-001/HANDOFF-001.json`） SHA 601f49059fcd66a3c3cc2d977c3e940c8a12d8a11fe52cf7c882e4ef6c5fd151提供精确WT角色6a4a9b72…、P30 Native描述、65成员ZIP和独审/资格引用；外53104 exit0/0.486秒、完整回收，业务启动0。共享live Standard仍e97d0af4…，源码818fa8e4…保存在固定候选及包内，未改他人进行中的输入或发布。搬迁11矩阵等待同模拟账户的系统停止验证实例实际退出后进行，原账户身份及预算保持。

## P30 搬迁完整矩阵及资格收口

实际确认Root同账户PID40412退出且当时没有其他加载执行Runtime的Python进程后，在全新矩阵根启动搬迁完整11入口。其PREPARED（外部历史/待归仓路径：`../../build/ms-p30-portable-matrix-001/PREPARED.json`） SHA 9e93e9aabc64e32a2ff8b5e80e4b5af138ad152b137e0871c09e31b570843ef8固定1415项，原ENTRY字节复用，manifest只选择已验固定锚点WT/Native并增加实际源码/扩展绑定，业务断言和原D保持。

全部五订单、五组合及unknown通过。实际124次查询、18次insert及3次cancel尝试；O1为15查询、O2为24，分别比普通14/22多1/2，其余相同，SDK数量、原价格/回调、迟到重复去重、终态后仅补200及五组合结果均保持。增加的查询记录按原件保留，未将普通121查询拷作搬迁结果。unknown仍只POST一次、保留原责任且无clean，原Host/Source和金融文件保持。外层（外部历史/待归仓路径：`../../build/ms-p30-portable-matrix-job-001/RUN.json`）12284 exit0/125.628秒，11个子树及外层完整回收。

搬迁矩阵冷核（外部历史/待归仓路径：`../../build/ms-p30-portable-matrix-001/MATRIX-COLD-001.json`） SHA 3956d637fcc083b110c8536eed94ddf68de91d8e5c4898072caf4a6630f35df2，1558绑定；限定动态delta独审（外部历史/待归仓路径：`../../build/ms-p30-portable-matrix-001/REVIEW-EXECUTION-001.json`） SHA 33913818edd3131978c86fbb94b3c950fe83446572e540d483877f42211d6a25固定112项直接输入并复核1415/1558闭包，开放P1/P2为0，关闭搬迁11动态gap。源码/普通/两代/七拒绝沿原108绑定审查reuse，旧P29单次原因、正式WRI、未知解除及自然跨夜分别保持其缺口。

资格v3（外部历史/待归仓路径：`../../build/ms-final-p30-qualification-003/QUALIFICATION.json`） SHA a29035efeef39db8ec335b3ca4fb943c1fc4f44168e9b4c0d157dce4557d86da和后继组装002（外部历史/待归仓路径：`../../build/ms-final-p30-root-handoff-002/HANDOFF-001.json`） SHA f54b7ebed8f6ec38645f426779f50afd85715ea67920da295354eb7b50293b0c已封，后者外460 exit0/0.397秒、完整回收，无业务启动。原65成员包、角色wheel和26 Native字节保持；该交接准备整套测试，完整模块/生产资格继续false。

另按B-06核清未知恢复的跨owner接口（外部历史/待归仓路径：`../../build/ms-unknown-recovery-owner-interface-001/INTERFACE-001.json`） SHA 21d54d828014ab4099c668a846f865c74e94b7c1b2a3741f9c17127f7d79ce5d。实际A003的五个公共模块在Journal/runtime/control/Source service/kernel各自持有未知阻断，所选方法与当前live AST语义全部一致，另绑定Standard及CtaProcess恢复位置。现有关联proof只说明订单归属；当前协议明确没有一般解除路径，Native缺clean准入仍独立存在。接口登记原Journal/UUID/结果保留、正向券商证据、按操作处置和Native状态恢复所需合同，实施尚未开始；生产源、金融根和未知责任均保持。

## 未知调用取得正向券商证明的实际反馈

固定反馈用例（外部历史/待归仓路径：`../../build/ms-unknown-positive-proof-baseline-004/RESULT.json`）在已安装P30 WT与正式A003 Host/Agent中，通过真实HMAC HTTP及WinSHM执行一次SDK替身下单。替身先生成100股全成订单、成交及账户效果，再抛出异常；之后沿原四查询取得订单，原完整token建立v2订单关联且含query_observation。原UUID、命令及unknown结果保持，Host的新insert准入仍关闭，Source的unknown围栏保持。实际1次SDK进入、1次交易POST、8次账户查询；本例没有启动Native，真实下撤单为0。

原Job（外部历史/待归仓路径：`../../build/ms-unknown-positive-proof-baseline-job-004/RUN.json`）69248 exit0、4.681秒，Host、Source、HTTP server、proxy及外层树全部关闭，first_error和proxy_first_error为空。三次早期准备失败分别为预算单位和绝对截止使用错误，均发生在SDK进入前；原件保持，没有修改产品预算或协议。

冷核（外部历史/待归仓路径：`../../build/ms-unknown-positive-proof-cold-001/COLD-001.json`） SHA 216380562715bc99f55c6ddedeca945c8d73cd8ccdaa82b90a0d4b01fd155dfa，1423项绑定，复核原1415项安装/来源闭包、用例、实际结果、关闭及方案身份；外45184 exit0、0.551秒、完整回收。该例证明现有防重复和正向订单关联行为，同时把有终态证据后的责任处置及原状态恢复记录为尚缺能力，desired_recovery_oracle_passed=false。

[恢复方案](../migration/unknown-broker-evidence-recovery-proposal.md)当前为proposed / implementation-not-started：复用原通信Journal保存有限处置证明，原unknown事实保持，完成真实关闭后由原工厂重建；Native恢复单独要求有效的实际失败关闭材料和原文件身份。没有新增金融账本、人工清零入口、WT核心行为或生产准入变化。

## Root关闭修复接收与完整组合准备

集成接收（外部历史/待归仓路径：`../../build/ms-root-close-integration-intake-002/INTAKE-001.json`）核准Root的WT0.1.0a12+integrated.1与AWP0.1.0a12+closestop.2用于后继准备。WT36个模块中33个逐字节保持，另外三个仅包版本、runtime组件顺序/类型及trade_host的分析身份/输入校验变化，执行逻辑保持。AWP接口90项绑定全部匹配；完整23发行安装的15项分析验证、基础2发行安装的19项WRI验证分别通过。早期34项组合中的一次失败保持原记录，后继结果按各自声明范围使用。外63712 exit0、0.440秒、完整回收，业务启动0。

Root的main004已证明53笔SDK替身成交、50400及九组件正常关闭；main005保留retirement_unconfirmed/page/TimeoutError，交易运行域仍有1个作业、generation=1及runtime_present=true。该观察属于自有读取代退休与关闭责任，具体超时位置继续按同次证据定位；整套停止恢复资格保持待验。

B后继纯QA控制器把实际WT角色换成Root固定普通安装并选择P30 Standard694dc60b…，A003通信Host和原App角色保持。full036与full037均在verify_wiring的旧包版本断言处准备失败，尚未进入MAIN，全部树/pipe/readers/资源回收。后继038保留原业务断言及产品截止，精确核新WT/AWP版本；这些准备结果只授接线范围，完整三轮、系统停止及同根恢复由实际运行另验。新增输出均在E盘，原金融目录、账户身份和其他会话实例保持。

后继038在输入冻结发现旧App基础解释器与原receipt摘要不同，校验保持拒绝。固定角色接收（外部历史/待归仓路径：`../../build/ms-functional-unchanged-role-intake-001/INTAKE-001.json`）核Root已交接的E锚点App30 wheel及完整Host15 wheel与原角色完全相同，原2729/443个Python源码与扩展全部逐字节保持；各环境额外两个文件为uv虚拟环境工具。5509项当前绑定一致，外51044 exit0、1.351秒、完整回收。四个通信Host继续使用A003，App和历史/采集工作环境改选这些固定角色。

039及040的准备失败为QA解释Root紧凑receipt相对路径时根目录取错，原件和完整回收保留。最终041统一以receipt自身目录为owner根，对相对入口及files执行containment和全部SHA校验，保留原基础解释器/DLL核对。其准备Job（外部历史/待归仓路径：`../../build/ms-functional-integrated-prepare-job-006/RUN.json`）38044 exit0、35.154秒、全部11阶段通过；四通信Host的实际配置准入全通过，新增Source查询0、SDK0。控制器SHA 71e9d62c1806bbb5d0b1b270b78ac60008767647adb2e6fa59bfcc2371447dc7，产品及业务断言保持。

实际确认当时全部Python/CTA进程没有加载执行Runtime且模块读取无失败后，用同一041字节启动full042，外层`build/ms-functional-integrated-full-job-001`。本段登记启动事实；三轮正式算法、系统停止和同根恢复以终态收据另核，未授整套通过资格。

### full042三轮与九组件正常关闭

full042已终态。冷封存（外部历史/待归仓路径：`../../build/ms-functional-full042-cold-001/COLD-001.json`） SHA 865ea4d6e4eb6d9f9dff85b958e68ce1635c922c684bf6bcddd0a4f4cd70de9d绑定43961项，原26944项业务输入运行前后完全一致。三轮正式1.1.2均converged，sequence12/13/14，同一轮累计53笔SDK替身委托和53笔成交、最终50400股；后两轮保持53，没有重复买入。

第一代策略HTTP结果已生成，后继报告HTTP核对期间出现AssertionError。原QA只保存异常类型，报告HTTP产物尚未生成，准确失败断言与原因继续unknown。App停止后的WT继续发布和同根恢复尚未进入。原整体passed=false、外21328 exit1保留。

本次finally实际完成整个WT正常关闭：Root实际PID75900的closed声明components_closed=true/error_code=null，WT外部启动PID11860 exit0；Native实际66776 closed.v2的ok/recovery_ready/resources_closed均true。14份子控制全部exit0、forced=false、树/reader/资源回收成立，Source亦正常退出，没有failure.json。Root的main005退休超时仍保留历史，本次按本次原件授九组件停止资格。冷封存外23616 exit0、66.341秒，完整回收；完整WRI恢复与整体资格继续待验。

只读报告后继诊断（外部历史/待归仓路径：`../../build/ms-full042-report-read-diagnostic-001/RESULT.json`）在同一已安装App及本次原报告fixture上，沿原BacktestArchive和原5秒截止读取：index两项0.015秒，comparison2.485秒且与准备fixture完全一致；外26664 exit0、3.402秒、完整回收。无App服务器、Source、Native或SDK。此为离线后继成功，原HTTP断言位置与原因保持unknown。

041准备独审（外部历史/待归仓路径：`../../build/ms-functional-integrated-qa-review-001/REVIEW-001.json`） SHA 269869dfb752dc30c0f3a4662f47ce782aaf5c72b1c77d9900276f80a51a084a直接绑定50份文件，新增开放P1/P2为0，核12个准备子进程及实际角色/冻结输入。当前控制器、生成器与两份接收收据另由审查直接绑定，未把它们称为26944业务map的一部分。后继044纯QA诊断独审（外部历史/待归仓路径：`../../build/ms-functional-integrated-qa-review-001/REVIEW-002.json`） SHA 9869b49edc330f672e45137d4e2e1baca0dbf4761ebf417d28d26d5130077b97核12份输入、无新增P1/P2；新增HTTP状态/长度/耗时及异常固定frames，原断言和截止保持，动态时序影响待验。

后继046在实际QA静态转换编译通过后，将原策略/报告HTTP五项断言整体移至原同根恢复及恢复后的账户HTTP之后、原App停止之前；所有断言和最终失败语义保持。这样先取得独立WT账户恢复事实，报告依旧单独判定。JSONL使用真实换行，原异常记录保留文件/行/函数且不包含错误正文、请求参数或响应数据。046控制器SHA 3e1c7c81a0a8cc40d6a025bee10979a576076487121af0725c7410370bb1aef0；静态失败043及045均未启动业务，原件保持。确认没有其他Native运行体后在全新full046启动，外build/ms-functional-integrated-full-job-002；本段只登记运行中状态，整套资格以终态另核。

### full046恢复入口与QA凭据字段修正

full046三轮sequence16/17/18均converged，SDK/订单/成交保持53、最终50400。App正常停止后WT取得新的账户发布，原Source进程继续保留；首代整套正常关闭，第二代WT入口已返回ready。随后QA在main.py:448读取first_closed的components字段发生KeyError。实际closed凭据只有components_closed；组件列表属于ready/status合同。原生恢复后的计算尚未进入。

本次冷封存（外部历史/待归仓路径：`../../build/ms-functional-full046-cold-001/COLD-001.json`） SHA a7516faa02ed71ebe1d029d7781042f1b624e82d5a7a708445a042481361c74e固定44554项，运行前后输入一致。首代Native49524的closed.v2 ok/recovery_ready/resources_closed均true，两代WT均全部组件关闭、error_code为空；19份子控制全部exit0、无forced，Source和所有资源回收。原主Job43000 exit1保留；冷核外70540 exit0、68.914秒、完整回收。

实际凭据红绿回归（外部历史/待归仓路径：`../../build/ms-functional-ready-contract-regression-001/RESULT.json`）使用该次两代真实status及首代closed：原字段读取确实KeyError，改用两代组件集合核对则9项完全一致，关闭证明保持；无Source/SDK/Native启动，外25932 exit0、0.250秒、完整回收。两份最终status的ready均已为false，代表关闭后的状态；本回归授字段及成员合同，运行中ready事实沿原main已执行分支和原ready凭据核实。

047只把该单个Subscript的first_closed改为首次已验证的state快照，保留first_closed.components_closed、resumed.ready及所有其他原断言；已核state在main中仅赋值一次。移动顺序delta独审003（外部历史/待归仓路径：`../../build/ms-functional-integrated-qa-review-001/REVIEW-003.json`） SHA f3a53b217b245a99eb626f396eb3a3d81dcf2063f6755fbed0477a8b5514beff核13份文件、12条移动语句和五断言；字段修正delta独审004（外部历史/待归仓路径：`../../build/ms-functional-integrated-qa-review-001/REVIEW-004.json`） SHA ebff98b31765227511e6204dbb45164e4738d9be02d25950d760b5c64d97e188核13份文件及6项回归输入，新增开放P1/P2均0。诊断流最终使用LF，只授最终正确状态，不将其描述为已有原触发红绿。

047控制器SHA e716124f622c7787672aeb47e029bed0de186725560ad71a02dfb304bf820b70，实际转换编译通过。没有其他Native运行体时在新full047启动，外build/ms-functional-integrated-full-job-003；首次金融目录、新系统基准、真实策略和产品截止保持原合同。本段登记运行中状态，恢复后原生计算、零重复提交及报告HTTP继续由该实际Job验收。

### 未知恢复设计独审与后继修订

原反馈冷封存001曾绑定可修订提案正文。后继冷封存002（外部历史/待归仓路径：`../../build/ms-unknown-positive-proof-cold-002/COLD-002.json`） SHA 88b0c02196f83bc9993fd322b6845e9bae5139207408c4cdf3c5aadc07dcd9cb保持实际SDK反馈及安装身份，将当时提案逐字冻结后绑定；1425项当前闭包通过，原001作为当时历史保留。外37856 exit0、0.857秒、完整回收，没有重跑交易。

原设计独审（外部历史/待归仓路径：`../../build/ms-unknown-recovery-design-review-001/REVIEW-001.json`） SHA 888f70e4f3295ad7bd9870fd0f11c6c8e0ef3b16ca0130de14a620a120385204核41份直接输入，发现两个P2：重建实例会丢失未持久的旧硬故障状态；ORDER终态无法补齐原新成交到Native金融/策略周期KV的应用与保存前沿。原本地ID基于enqueue受理后登记，SDK成功并非前提，worker仍可并发开始POST。unknown引起原Host Plugin fault并停止Session，最后一次策略schedule及周期保存没有保证。

唯一[当前提案](../migration/unknown-broker-evidence-recovery-proposal.md)已补旧各owner最终排空安全资格、recovered-managed-origin及原应用/金融保存/周期NSQ-KV前沿，并明确要求真实新买入成交后异常的正向恢复实例。query继续是query，原first_live/提交序号保持事实。设计delta独审（外部历史/待归仓路径：`../../build/ms-unknown-recovery-design-review-001/REVIEW-002.json`） SHA 066866d3e7df23d3e95b53310cb50cb563c472c9a87654051331c89862718142核40份既有直接输入及1425冷绑定，设计要求层P1/P2为0；原v1与新v2快照均固定。具体版本/schema/最早截止、受控非0退出与非受控退出、unknown派生Plugin fault和独立硬故障仍须实施合同分别冻结。产品实现0，正向Native未知恢复实例0，业务恢复及整体模块资格继续gap。

### 原金融目录恢复后继与来源会话容量

full047已终态，原Source给出analysis_refresh_failed，WRI在analysis_window运行失败后退出；该次准确内部异常未保留，根因继续unknown。外32712 exit1，物理回收完成。后继遵照主线分工直接复用full046已完成53笔的原金融目录，不重跑首次建仓。历史行情保留；迁入前旧成交和旧开仓历史仍退出输入要求。

第一次续接使用原正式resume_clean配置、原金融目录和原生49524正常关闭证明。Native实际加载并消费49524，随后以新PID10968正常关闭，closed.v2的ok/recovery_ready/resources_closed均true、exit_code=0。QA仍等待第一代SOURCE-STARTED标记，未送入恢复后的计算；其TimeoutError和外64168 exit1保留。该次新Source重新载入已有券商模型，53委托/53成交、50400份及资金与前代一致，新增SDK0；Source物理进程有变化，不能表述为原Source进程持续存活。

第二次续接只移除首次标记等待，并将前代PID与证明绑定到真实10968；保留execution_ready和当前券商核对。交易Host55184实际在事件page阶段runtime_fault，原快照把具体异常归为other；WRI报告component_runtime_trade_host，execution尚未就绪。外67740 exit1且全部物理回收，10968证明保持原SHA且未消费，金融文件逐项保持。输入26999项中，原SOURCE-CONTROL.json和WT-CONTROL.json发生变化，原RESULT.inputs_before_after_exact=false照实保留；其余26997项保持，后续须按实际控制记录所有权修正QA输入分类，不追认该次整体通过。

隔离复现（外部历史/待归仓路径：`../../build/ms-existing-financial-stream-capacity-002/RESULT.json`）使用同一A003普通Host安装、正式材料核验/构造工厂和原通信Journal的SQLite副本；原库与全部原金融文件保持。配置max_streams=2、已保存两会话流（前沿106和0）及106事件；相同已存在空会话的页写入成功，第三个新Source会话的空页经真实events.ingest抛JournalFull，事务回滚后仍为两流/106事件。当前继续重启新Source必然触及这一容量；历史failure没有保存异常类，不能追认其other字段就是JournalFull。复现未启动Runtime运输、SDK0，runtime.close完整，外21460 exit0、1.888秒、资源全部回收。复现001在完成页验证后漏传close截止而TypeError，原失败保留，002使用原API显式截止完成关闭。

检查点（外部历史/待归仓路径：`../../build/ms-existing-financial-resume-checkpoint-001/CHECKPOINT-001.json`） SHA c02e774274664021f4dfc0db4276d86c56853e302e58dc7c14ecdbda50456c00绑定53项，附当前18份金融文件的证据副本；运行始终使用原目录，副本仅供核验。检查点外76300 exit0、0.425秒及完整物理回收。最新真实clean为10968，SHA a9dc595d70698a3625242888d7af35fe55620a7ac59c2eca9dcb81f9f67dc210，49524属于已消费历史。原库预算和身份、原事件、账户键和金融基准均保持。先核同Journal的受支持续接方式；完成后沿10968继续恢复后的真实策略计算和正常关闭。完整WRI恢复、报告HTTP、未知正向Native、活动单冷恢复和自然跨夜分别待验，整体B资格false。

活动单能力复核（外部历史/待归仓路径：`../../build/ms-active-order-restart-capability-001/REVIEW-001.json`） SHA 5f958b399755e02e251fe48c39e8fd03ad0e9c8d94392970d8d63a76ad11a8a8绑定63项：当前产品主动要求active_orders=0；原O1–O5及部成/等待为同进程资格，不能授跨Native恢复。原WT订单同步、未成量及同向等待可复用，原上下文责任、订单终态到后继持仓查询屏障及金融/KV前沿仍需统一衔接。四份旧cold各有两项live测试别名后继变化，对应冻结原件仍匹配，Native和业务制品未漂移；历史输入有效性按该范围解释。

独立容量审查（外部历史/待归仓路径：`../../build/ms-existing-financial-stream-capacity-review-001/REVIEW-001.json`） SHA c562976589b295d649a8e05a3ca18fe22bed8a0ecbaceaecb8a96a5518049ba2绑定21项，确认现有previous_read_profile只兼容read_retention引入，continuity只续同一stream的认证链，均不提供原库扩容。当前保留事实的第三会话接纳缺口为开放P2；新增审查引入P1/P2均0。原报告误将“总第3会话”写成“三个新Source向量”，后继delta明确勘误，001原件保持。实际002为一个已有空会话成功页和一个新会话JournalFull；没有补跑额外业务。

QA输入归属回归（外部历史/待归仓路径：`../../build/ms-existing-financial-input-scope-002/RESULT.json`） SHA dbe23faf2aeaec2374165a3ff83e78a96682c9ef3af2e04348b1572bef00fad6使用005实际26999项before/after，旧整体比较为false；仅将本次out/private下两个精确进程关闭收据分出，26997项业务输入比较为true，两个收据的前后SHA分别保存。其他目录的同名SOURCE-CONTROL仍保持不可变，实际exe修改仍判失败，缺控制路径拒绝。原005 RESULT保持原false。初版001把两个路径误定位旧full046根而在纯回归ValueError；原件保留，002改为当前out根。外41920 exit0、0.494秒及完整物理回收；新staged main仅编译和静态审查，未启动Source/Native/SDK，不能授完整恢复。

delta独审002（外部历史/待归仓路径：`../../build/ms-existing-financial-stream-capacity-review-001/REVIEW-002.json`） SHA 7abd07b91fbeaf71cf85af59870c65a5b36d98dfe0d32e543716eba7bc133c88绑定12项，核输入分类的精确路径、其余原断言、完整正常/失败判定及前述重现次数勘误，新增开放P1/P2为0。原容量P2和完整恢复gap保持。

后继[显式容量扩展方案](../migration/trade-event-storage-expansion-proposal.md)冻结TES-C1–C6的预期行为，状态proposed / implementation-not-started：原owner租约、原事务、只增加声明容量身份、其余原事实不变，先在副本验证维护及新Source接纳，再接原目录最新证明恢复。原库、原配对、WT及真实交易变更均0。此文档是后继实施设计，尚未授维护入口或容量扩展资格。

## 容量实施与原目录恢复后继

本段接续前述未实施检查点。自有通信层已提供`guanheng_qmt_shm.trade_event_maintenance`公开入口，沿原Journal租约与原事务扩大声明的事件容量。SDK副本main005通过原工厂、原106事件及第三会话接纳；boundaries002的14案覆盖错误身份、缩容、原租约争用、未派发命令、原截止、事务前失败、提交晚返回及后继物理清理。公开CLI和SDK副本生成器QA003通过，成功0、重复旧身份/非法预算/提交晚返回2，未知提交结果保留新身份并单独确认资源关闭。core REVIEW-002、CLI/生成器REVIEW-003及close-review REVIEW-003的开放P1/P2为0，各结论沿各自准确输入。

最终容量接口004（外部历史/待归仓路径：`../../build/ms-event-storage-expansion-shared-002/INTERFACE-004.json`） SHA `080d2b62278017a5388be45949cf7576b3b3410439b2d2f3915bb91d13b7636e`关联上述报告和Root后继。Root普通安装候选Host为`0.1.0a22+mdphttp.3.tes.1`；共享接缝及版本集成已由Root沿永久源码完成，三wheel与已安装候选逐字相同，Agent/Core保持Source.3。原接口003的CLI-tail-review-pending已由本后继关闭，旧原件保持。公开SDK副本准备入口为`tests/integration/qmt_trade_host_product/prepare_event_storage_fixture.py`，只为维护QA生成独立材料，运行时使用当前安装正常配对，不共享实际运输。

原SDK库实际维护（外部历史/待归仓路径：`../../build/ms-original-event-capacity-expansion-001/RESULT.json`） SHA `db5f4aeb6b515357ee11ae1a8e7c44372ab88576b9791e5a621c5e8b1474f688`确认max_streams从2到16；只有一条容量身份记录变化，53命令、106事件、两条旧流和全部其他SQLite行精确保持。外39968 exit0、2.897秒、完整物理回收，维护期间SDK/Native均0，原18份金融文件和当时10968证明保持。该数值为显式SDK候选容量，正式环境预算沿其配置另定。随后Source实际查询及新流追加属于正常运行，维护时的Journal整文件SHA为历史身份。

resume005沿原金融目录实际消费10968并由Native35256正常关闭，SDK0、原53委托/53成交/50400份和四项券商模型字段保持。恢复回调消费旧窗口后为waiting_market_input/market_window_stale，后继AWP已发布新窗口，QA未再次送触发行情；该次collection stop_timeout与其他正常组件、原生正常关闭分别记录。独立freshness REVIEW-001绑定26份文件，确认实际发布/消费路径一致、源窗口超600秒以及QA把精确活动WINDOW归入不可变输入的两项缺口。后继按实际生产者配置精确分出一个活动窗口，其他不可变输入继续核同；不改时间戳，不放宽原600秒新鲜度或60秒验证预算。

resume008检查点（外部历史/待归仓路径：`../../build/ms-existing-financial-resume-checkpoint-002/CHECKPOINT-001.json`） SHA `b1387418108e694eae38f97198c004d28afae41a4441b7bcf79b53306186fcb1`绑定16份原件。该次取得本代合格新窗口，随后QA main405在第一笔bar之前读取尚未生成的策略观察文件而FileNotFoundError；恢复计算尚未触发。ROOT72212九组件正常关闭、error为空；Native30456正常关闭/recovery_ready，新增SDK0，53委托/53成交/50400份及四项券商模型字段保持，全部不可变输入一致。外42672 exit1、树零/EOF/join/资源关闭。该次失败属于QA观察顺序，现有证据未指向WT线程。

resume009将观察读取移到发bar之后，等待文件存在，并以同一观察内的整数restored_sequence核sequence推进；原fresh发布身份、600秒、共用60秒和converged/core_result/当前持仓断言保持。实际运行在到达该QA之前因execution_start退出：Native19428的failure阶段trader、plugin_error=10（IoError）、host_fault=3（Plugin），session_fault/native_error均0。该次自有交易接入的内部IoError原因待定位，不能归因WT，也未证明新QA动态通过。SOURCE正常关闭、SDK0，原18金融文件及30456证明逐项保持，30456未消费；原RESULT的new_clean_pid=30456引用已有证明，不能解释为本次产生新关闭。ROOT最终正常关闭收据缺失；外63824 exit1且物理资源全部回收。当前无B业务运行，不重复启动或重放原53笔。

首次启用规则保持用户决定：旧开仓历史和旧交易流水不迁入，当前券商库存作为新运行基准。上述53笔属于本系统自己的SDK替身运行，重启应接续。真实下撤单、生产及新增WT行为均0。P30永久固定源码全量干净构建、上述实际启动错误、恢复后正式计算、未知正向Native、活动单冷恢复、自然跨夜、报告HTTP及整体B分别为待办；先前重用旧obj/lib的P30构建保留限定资格。

resume009终态检查点（外部历史/待归仓路径：`../../build/ms-existing-financial-resume-checkpoint-003/CHECKPOINT-001.json`） SHA `f960828296192b8266130d73914bcf3750ee2c3163ea13353b45f0297ecbcbc7`绑定9份原件，并在该次所有进程终态后重新核原18文件及30456证明精确保持。QA顺序delta独审（外部历史/待归仓路径：`../../build/ms-existing-financial-resume-qa-order-review-001/REVIEW-001.json`） SHA `d95f66e5759c12ec1b6656fa519600b7e0c29a445de1ea641483213c5dc4cea2`直接绑定24项：008预读P2已在009源码修正，11项纯内存条件验证通过，其余45条assert、鲜窗函数及关闭逻辑保持，新增开放P1/P2为0。009的实际Trader启动失败与新QA未获动态验证分别保留；下一步定位该实际自有错误，再从真实30456证明续接。

## NRT-R7 永久源码干净构建与实际链接来源

G3核证发现旧P30候选复用14份对象及旧静态库，永久Standard源码仍停留在较早版本。该候选的业务证据保留原范围，永久源码全量重建资格待补。自有Standard在原e97d0af…摘要核对后采用既有独立验收的818fa8e…准确字节；永久WT工作树保持原状。专用[永久构建入口](../runbooks/standard-execution-build.md)从固定Git08b230、16文件既有受管/查询覆盖及原3文件SCMR覆盖生成输入，19结果逐一等于已验Native006规范化内容。原相对Includes通过同一批准WT快照镜像满足，自有与上游来源分开登记。

完整编译首次阻断于自有账户结果ABI校验：公共QmtBoundResult新增snapshot_consumption_ready，使其从344到352字节，QmtAccountResult从376到384，原QmtBoundReceipt136保持。实际同MSVC探针31356 exit0、5.16秒、完整回收，结果在`build/ms-permanent-execution-layout-probe-001`。B只更新StandardEventBudget.h的旧376断言与原因注释；银行正文原本按sizeof计量。后继完整编译已通过该点，Common和WT源码保持。

公开入口的工具链探测、固定Git、依赖解压与复核分别由父入口的native.run Job在原剩余D内拥有；编译安装继续沿同D。构建环境限定VC/SDK字段和搜索根。真实受控探测20秒睡眠在原6秒操作预算内被终止，实际phase PID69812的树零/EOF/join/资源关闭全部通过，无工具链收据、后继Git或依赖阶段；`ms-execution-phase-deadline-qa-002`的外47496 exit0、8.307秒，内部5.076秒。001的判定误期待TimeoutError，实际是原API的TimeoutExpired，失败原件及真实完整回收保留；002只修正测试的错误类型判断。更早1秒样本仅证明准备阶段过D后停止，其未启动phase，不作探测回收证据。

实际MSVC DEFAULTLIB红绿使用真实外部静态库及对象pragma：旧显式rsp审计会误接纳该隐式库，最终永久审计联合显式rsp与实际库搜索路径拒绝它，正常新对象和VC/SDK默认库通过。`ms-execution-link-input-qa-003`外41636 exit0、5.801秒、完整回收；原错误UTF8解码UTF16的001保留，002为原型、003实际调用永久实现。生成的Ninja命令继续保留，完整来源结论沿实际链接证据。

007完成223步编译链接和五实际rsp后，最终审计因实际库搜索轨迹缺失而拒绝，外28416 exit1、完整回收。CMake的vs_link包装在成功时默认隐藏链接器输出；本机同包装对照`ms-cmake-link-trace-qa-002`两次链接均成功，仅显式VERBOSE环境时保留库搜索输出，外66240 exit0、3.678秒、完整回收。001的大写/OUT未被包装识别，其失败原件保留；002按实际生成命令使用小写/out。永久入口已明确VERBOSE=1，完整008按全新目录重建中，当前不从007的编译成功授完整G3或安装资格。

首full审查001 SHA `5aa1c59208d9456bd14d7a1a40a2e180fd21752b29da86702060f01092e0e69c`、delta002 SHA `13460a8f41dca372cc438e35283838b4053cdf001847f806681dde326e0142d5`各绑定58项。总D实现P2已关闭；实际完整五目标来源闭包与安装仍待008终态及后继审查。以上仅执行组件构建和工具验证，SDK/业务Runtime/真实交易均0；完整B目标及原金融目录恢复继续。

HTTP后继接收（外部历史/待归仓路径：`../../build/ms-existing-financial-resume-checkpoint-003/HTTP-BOUNDARY-001.json`）核Root/A已安装TES Host的四项正式签名HTTP→WinSHM→SDK隔离查询与正常关闭，原金融目录访问0。原009的19428失败原因摘要精确匹配公开常量qmt_http_remote_failure，具体endpoint/status/error_code仍缺；其Native失败文件早于手动Source停止命令文件8.183秒，文件发布顺序与精确网络时序分别标识。原008预bar缺文件与009启动失败继续分别记录；A新隔离通过和后继收尾503不替代原009具体失败请求的证据。接收过程未新增查询或SDK调用。

## 永久构建与原目录恢复的最终结果

clean009已经从永久自有源码、固定Git及19份既有批准覆盖，在独占新目录完成编译、链接、安装和前后复核。实际五份linker显式收据与库搜索轨迹重建65个输入，其中42项目文件均位于本次cmake、23系统库位于声明VC/SDK根；25份安装文件精确核同。350个上游、471个组合owned及350份同源镜像精确，121永久自有输入保持。原obj/lib输入0。外25464 exit0、445.007秒及树零/EOF/join/资源关闭全部通过，SDK/业务Runtime0。008已完成相同编译和安装，最后因Windows反斜杠路径键未归一化而误拒；009仅将输出键改为POSIX后完整重跑，008原exit1及有限冷证（外部历史/待归仓路径：`../../build/ms-permanent-execution-cold-audit-001/AUDIT-001.json`）保持。

源码delta003（外部历史/待归仓路径：`../../build/ms-permanent-execution-source-review-001/REVIEW-003.json`） SHA `f382efb59a221e527ebdf461f5ff2df4c03fb460d56154313a34d7abac5e644c`绑定150项；执行独审001（外部历史/待归仓路径：`../../build/ms-final-main-recovery-execution-review-001/REVIEW-001.json`） SHA `50ffe7348da305a9be885afb5a6648509ef116b06121d0dc88145caf07725532`绑定155项，新增开放P1/P2均0。二者分别核实际来源/预算及构建安装/原目录业务，均明确区分新G3 Native与原安装的金融恢复资格。Root已接收候选接口（外部历史/待归仓路径：`../../build/ms-permanent-execution-root-handoff-001/INTERFACE-001.json`） SHA `12f2b88b9403c3c5fdee22db30cc239e6cbd16e021b8de8fd32c036961049945`，以该五组件、39份原WT Python源码及仅两处integrated.2版本元数据组合新005；新SDK业务由Root独立运行，组合和业务结论沿Root原件，B不重复运行或提前授信。

原金融resume010实际已经发布fresh core结果，sequence20/restored19、converged及execution_position_qualified=true；验证脚本仍要求兼容broker_position_qualified=true，因其按NRT-R31刻意保持false而超时。源码正文明确NSQ消费经核实的券商完整P，原理论观察只承担财务basis和pending；010有限业务证明（外部历史/待归仓路径：`../../build/ms-existing-financial-resume-checkpoint-004/BUSINESS-PROOF-001.json`） SHA `242ae185f9fc8ff579cabac8f7d5e4fb4bf4ed82a0ae1d4cfafe38efffcd5bd2`保留其实际计算与原RESULT失败，采集stop_timeout及具体内部阶段缺证分别登记。

011只按既有R31修正上述QA字段，并新增八项真实执行观察断言：完整P/资金已知、broker-derived来源、verified、逐证券actual与SDK完全一致、总量一致及三份观察身份相同。原60秒总验证、90秒原生ready及600秒窗口有效期保持；先等本代合法新窗口，再发下一根行情，观察文件在实际回调后读取。额外HTTP观察仅为单独签名trade-status GET，保存阶段/状态和固定错误码，不拦截Native请求、不触发SDK查询或重试。Startup503对应绑定缺席，主线继续原来源等待；不能把这条观察当作Native请求失败。

原目录成功收据（外部历史/待归仓路径：`../../build/ms-existing-financial-resume-checkpoint-005/SUCCESS-001.json`） SHA `5719f25ecdd1de4c36e2fe56ff9dda43d8c07ade63cae996ae323c5a2cdd9aac`确认正式1.1.2恢复计算sequence21/restored20、converged，八维执行实际量与当前SDK源50400完全一致，53订单/53成交及资金/持仓四模型字段保持，新增SDK0。所有不可变输入精确，活动窗口按唯一生产者路径另列。Root74988九组件正常关闭，error为空且无pending/forced；Native63680 closed.v2的ok/recovery_ready/resources_closed均true、exit0，原60400证明按原字节消费。外42800 exit0、83.708秒、全部物理回收。18份当前金融文件的副本仅用于验证，运行始终使用full046原金融目录，未重建初值或重放53笔。

该金融恢复使用原clean精确绑定的P30安装；CtaProcess同时核配置及安装摘要，新G3 DLL未替换这份安装、未改写关闭证明。本收据授同版原目录恢复和正常关闭资格，新Native普通业务/版本迁移、未知正向Native、活动单冷恢复、自然跨夜、完整报告/整套候选与整个B仍沿各自缺口继续。009具体HTTP响应和010关闭故障的缺证仍保留，011成功不反推旧故障根因。首次启用保持当前库存新起点，旧交易/开仓历史不迁入，新运行记录继续保存；真实下撤单、生产及新增WT行为均0。

## 原身份冷重开查询与定向撤单

类型：模块B有限恢复主链后继。范围为原命令身份下的未知提交、活动订单查询及必要SDK替身撤单。采用Root005 installed002中的WT integrated.2、Host TES及原G3 Standard DLL；新增内容只有两个验收入口：Python两代夹具（外部历史/待归仓路径：`../../tests/integration/qmt_standard_trader/cold_order_recovery.py`）和原生插件探针（外部历史/待归仓路径：`../../tests/integration/qmt_standard_trader/cold_order_probe.cpp`）。生产代码、数据库结构、准入规则及WT行为修改均0，原53笔金融目录保持原件。

两代Python进程先后运行，各自拥有真实Host、Source、HMAC HTTP和WinSHM。首次SDK替身实际创建订单后才抛错或返回；第一代真实关闭后，第二代使用同一路径Journal和同一profile，来源session改变。新原生探针从当前ORDER查询取回原EntrustID/UserTag及broker ID，沿安装DLL的ITraderApi.orderAction提交一次撤单，再先查终态ORDER、后查P。测试券商模型保存于QA输入；原Journal调用阶段、body和result SHA在两代间逐一核对。

| 验收ID | 实际场景与结果 |
|---|---|
| B-06 / UC-R1/R7 | 未知未成交（外部历史/待归仓路径：`../../build/ms-cold-order-unknown-unfilled-002/reopen/RESULT.json`）：第一代SDK insert一次后抛错，第二代原调用仍unknown、原body/result保持；真实订单查询恢复原身份，SDK cancel一次，终态后P为0，新insert为0，Host围栏继续关闭新买单 |
| B-02/B-06 / UC-R1/R7 | 未知部分成交（外部历史/待归仓路径：`../../build/ms-cold-order-matrix-002/unknown-partial/reopen/RESULT.json`）：原100股已成40、活动60；第二代查询原身份并只撤余量，原生两次O/一次后继P，已成40及可卖0保持，SDK新insert为0/cancel为1，原unknown与围栏保持 |
| B-02 / 原生查询撤单 | 正常受理活动单（外部历史/待归仓路径：`../../build/ms-cold-order-matrix-002/accepted-active/reopen/RESULT.json`）：第一代原记录sdk_returned、订单未成；第二代真实查询取回原身份，cancel一次、终态后P为0，旧调用及来源事实保持，正常新单准入保持原规则 |

未成交两代外Job分别72724 exit0/14.335秒、40992 exit0/8.078秒，原生24456正常关闭并删除实例。最终另两场景串行矩阵（外部历史/待归仓路径：`../../build/ms-cold-order-matrix-002/RESULT.json`）外60596 exit0/44.501秒，四个实际子Job均exit0、树零、EOF、reader join和资源关闭；两代Host/Source/server/proxy均正常关闭。所有SDK调用均由原来源owner线程执行。原生测试前端build004（外部历史/待归仓路径：`../../build/ms-cold-order-build-004/RESULT.json`）只链接G3既有同批库，产品DLL保持；外55392 exit0/5.743秒，完整回收。

失败原件分别保留：unfilled001把Windows大小写等价的native.json/NATIVE.json误当不同路径，业务后写报告exit4；unfilled002改为明确不同文件名后完整通过。partial矩阵001在一次后继请求得到运输超时，原生错误1、关闭未确认，外层最终物理回收；缺少同次请求关联，具体超时阶段继续unknown。矩阵002增加QA固定错误和请求阶段记录、沿同一产品代码重跑通过；这次通过不证明旧超时根因已修复。产品未增加重试、延长D或改写旧结果。

资格边界：上述原生实例是Standard插件的独立消费者，没有运行正式1.1.2 CTA周期或恢复旧金融目录。已确认原身份查询及必要撤单的冷重开，整策略在活动单尚存时自动接续、未知解除后自动重开买单、成交前沿到旧WT/周期状态的异常恢复仍未取得资格。[UDR提案](../migration/unknown-broker-evidence-recovery-proposal.md)继续proposed/未实施，按当前有限收口范围不新增架构、数据库或准入机制。原011同版正常恢复保持通过。两项限定独立审查及最终交接沿后继收据登记，完整B与统一系统资格分别判断。

独立审查定位QA原D晚返回P2：旧progress仅在pump前检查，返回后条件已满足时可能继续后继动作；Python HTTP线程启动前也缺同一工作D检查。原字节保存在`build/ms-finite-recovery-closeout-001/QA-v1-*`及EVIDENCE-v1.md。最终QA统一在操作前、pump/wait/HTTP返回后核同一原D，HTTP原2秒timeout按剩余时间收窄；原生撤单对象采用RAII覆盖超时退出。没有调整产品准入、重试或任何截止值。

修后最终matrix003（外部历史/待归仓路径：`../../build/ms-cold-order-matrix-003/RESULT.json`）将原三场景按同一代码完整串行重跑：六个实际Python子Job均exit0和全物理回收，三个原生实例均passed/closed/deleted、两次订单查询/一次后继持仓查询和一次cancel，恢复额外insert均0；两unknown仍保原事实及禁入，40股/可卖0保持。外69664 exit0、97.206秒、树零/EOF/join/资源关闭全部通过；六阶段进程身份和回收事实保留于PROCESSES，原截止定义及调用保留于冻结QA源码和运行命令，单阶段耗时未单独采集。最终测试前端build005（外部历史/待归仓路径：`../../build/ms-cold-order-build-005/RESULT.json`）外63188 exit0、6.831秒/全回收，产品DLL保持同一Root005/G3摘要。最终源码、安装消费者、原SQLite行及两份审查沿精确交接绑定；001/002及各失败原件保持原资格。
