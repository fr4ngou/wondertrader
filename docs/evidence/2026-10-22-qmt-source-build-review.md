# QMT 来源字段与构建登记审查

类型：开发验证记录。状态：源码及构建登记独立审查通过；严格门禁受资源占用阻断，未合入、安装或发布。范围：独立候选 `E:/workspace/qmt-worktrees/native-readonly-fields`，基线 `2083e96ac7134ad808d6bfddcdfe19aaa11a64fd`。

## 实际修改与所有权

`qmt-public-fields` 在原 `qmt_agent/broker/encoding.py` 的允许字段列表保留32项可选QMT原字段，加入中文说明。缺失、null、零值及原始ID分别保留；原采集线程、OperationQueue、Journal、金融投影和权限继续各自负责。原生今昨仓、成本等字段被保留，不代表后继WT整批快照映射已经完成。

`wt-stage-forward` 将已有审查阶段修正适配到当前基线：源码准备记录真实制品漂移，严格门禁、合入及发行阶段继续要求当前制品。沿原构建owner追加6条当前源码登记，完整保留566条历史登记；没有为旧制品回写资格。32/22/40项相关回归及6个当前制品参数验证通过；字段相关175项通过、零跳过，72份Agent源码通过Python 3.6语法检查，实际3.6运行资格单列。

## 最终身份与独立复核

共同候选身份 `78cdd857135adb38af68175141ddbad9ca25ffe9124c91394d303b78b66ed5be`。构建登记SHA-256 `96f9953c809fe3273f1ae4b521e14af5cd908de6171e343d9abd7a6798bb9de8`；6条新登记均由原owner独立重算有效，旧记录与声明保持，兼容Git提交资格未扩大。

证据根为 `E:/workspace/qmt/generated-worktrees/e41e199e0d084c01`。先完成两份独立full审查，再追加登记、重新准备并完成各自delta确认；两任务实际存储状态均为 `full_testing`、`review.passed=true`、开放发现为空。

| 任务 | 最终审查包SHA-256 | 最终独立报告SHA-256 |
|---|---|---|
| qmt-public-fields | `471744a5a5299b5f2bdae1be2d0125110dd70e549566d3ecbebc96043776c0b4` | `54561d794db50d4933e2d874ffd395e53e41c17b637889d12e1b91fa30f88ef1` |
| wt-stage-forward | `fc1ec9a40b633b30d668e183bd1de747dac88f298d48f72fb343902dc472b5de` | `225da75741b19f718f559982ca0d5ab3aa1ec2c37d9b3c77fcff97ae352d7ed7` |

报告分别位于 `validation/<任务>/independent-build-delta/review.json`。主任务逐项核对源码/登记摘要、准备及报告身份并通过原 `review-result` 导入；自动严格门禁均在环境准入时返回 `native_fixture_capacity_occupied`，资源为strategy，尚未执行全量门禁批次。

## 剩余边界

原先失败后保留的隔离测试环境占用唯一名额。本次保留其数据库、容器及日志；源码审查不授予清理或生产资格。候选没有改动原运行目录，没有安装到国信QMT；实际字段返回、整批完整性、来源只读资格及WT映射沿[后继方案](../migration/native-qmt-http-snapshot-plan.md)继续验收。该记录与历史原生构建的[vendor输入复核](2026-10-22-native-history-vendor-inputs.md)分别约束各自资格。

## 后继逐查询上下文候选

独立候选`E:/workspace/qmt-worktrees/native-readonly-context`沿相同2083e96基线实现qmt.account-query.v1：显式全账户查询范围、原Core执行绑定与代际、原Queue/Journal逐请求观察；默认策略筛选和旧终态保持原语义。它尚未与上述32字段候选合并，不借用上述制品与审查资格。

首次full发现接收端DTO跨字段校验缺口AQ-DTO-001，修正在原DTO所有者完成；新增36项，当前206项定向通过，73文件Python3.6语法通过。独立delta确认查询R1–R6、准备阶段R1–R3全部完整，发现关闭。两报告SHA-256分别为`cd25e0bd764b6c2916020565eb99104d47d04ff1440d91a9404d3a2151e0e0b2`和`0688d19fcec04db5b02f894cbfa31395cb1d05a93f892b2c4ba8cc5da2930dd2`，位于该工作树受管generated根`293d2754d5ebe565/workflow/validation/<任务>/independent-dto-delta/review.json`。查询任务为qmt-query-context，准备阶段任务为wt-stage-forward-context；复审绑定候选`02f3009e6d85170e4d1f4d49dbe07070f6b0e70f3a2c0eca009f88ab1173a20f`。

主任务实际核对文件摘要并沿原review-result登记；严格门禁拒绝六份旧策略制品source_changed，尚未执行后续门禁批次。下一步先核定两候选最终组合，沿原strategytool和原追加登记owner生成已审源码的新制品，再绑定实际输入复审与严格门禁。没有变更国信QMT运行、交易、数据库或原保留测试资源。

## 字段与上下文实际组合

后继在context候选仅精确承接encoding、原字段测试、唯一规格与ADR四文件，主任务核对来源/目标SHA均一致；原Core、Queue、DTO及治理源码保持此前修正。新增四类原生对象的真实HMAC HTTP→原tick→原SQLite Journal→GET→Bridge及新Core重开旧终态测试，原缺字段源实测4失败；承接后220项通过（原206、字段10、组合4），73文件3.6语法及变化文件Ruff通过。SQLite沿原Journal的隔离tmp_path，无外部数据库或新账户账本。

回执为当前generated根`workflow/validation/qmt-query-context/combined-fields-001`；绿回执SHA-256为`ec65d525a2f0ce3f4d6acf51a541404a501502f1fa2db748ac10c1a9fb737466`，实际测试日志为`710812b5889ca53f6ec2e15abf9d8df18fbb64bb9a3ebdb846415fcc5e50f5a4`，source-freeze为`25b98376fc0cd71e7b21884f41d8f3d9657a496c825a4180e3a8a5390071502a`。主任务实际回读日志SHA及220项通过结果。当前组合正式准备/独立delta继续，原两候选报告各自保持原身份，尚未构建最终组合制品或安装。

## 后继受限终态修正与源码登记

组合独立delta发现AQ-RESTRICTED-RESULT-001：原受限结果默认项缺observation，Host DTO补null后重新计算，可能改变摘要及容量边界；错误回退还可能保留已complete的观察。修正在原`broker/results.py`统一默认项与失败清理，保留旧持久终态原字节/SHA；没有修改HTTP/DTO/Core/Queue金融语义。原IPC与领域回归合计314通过，73文件Agent3.6语法及变化两文件Ruff通过。新增容量精确边界、超一字节、实际Host摘要一致、NaN/非法代理字符失败及旧终态重开等负向已运行。

正式准备与独立delta绑定候选`b0fa7b73a364c13db41525dff98c33341f6b06ebfa7f5794444b705db7011db7`，查询R1–R6及治理R1–R3全部complete，开放发现0。报告位于当前generated根`workflow/validation/<任务>/independent-restricted-delta/review.json`，查询报告SHA `342e92df74d6bb2e8b135e65dd516dca93a1aa8ebe1515c8cbc90dfc215982ff`，治理报告SHA `aaf3e5a00cb31ba3ddeed87a869f4612e49cffcaf62c972a60464eeaa6e9f348`。主任务实际回读核验并以原review-result导入；该轮严格门禁仍准确拒绝六项旧制品source_changed。

随后只在候选分支有限提交61个明确源码/规格及实际引用的任务事实，提交为`34777db5eab144d6fe8a2f259b9f2c0de167435a`，父2083e96。沿原strategytool artifact-build，以该实际Git提交及三个显式依赖operation_queue.py/capabilities.py/操作目录JSON登记`20261022-qmt-account-query-context-v1`。566条原记录保持，追加6条至572，六active指针更新；原owner重算当前与Git摘要全部一致且有效，重复原CLI为changed=false、字节保持。manifest SHA `cf004132c896a32861172c2892d856634c6ef1b55fd6c068999c73e50cb85edd`。这里的开发制品是原候选清单登记，尚未生成运行安装包或授生产资格。

受影响原静态构建回归为45通过/1失败，定位`docs/contracts/qmt-gateway-operations.json`受管源依赖没有进入原Dockerfile COPY路径；真实打包与路径覆盖检查在自有QMT候选修复。该失败及新manifest保持，尚未继续后继准备/审查/严格门禁或提交manifest。材料在当前generated根`workflow/validation/qmt-query-context/artifact-build-001`；不改变运行QMT、数据库、保留失败资源或其他工作树。后续证据按新包装及manifest输入取得，以上已审源码结果保留原身份。

包装后继：原Dockerfile存在`/app/qmt_agent`及`/app/src/qmt_agent`两个源码落点，实际capabilities.py按自身路径寻找契约。新增两条精确COPY，将同一JSON放在两处对应docs/contracts目录；原loader、能力/制品owner及门槛保持。原静态路径检查改成实际文件/父目录和目标相对路径，增加6个用例；其中两个实际隔离加载原capabilities模块，验证源目录原字节/新query_contract、源优先、错放时原生成fallback、fallback也缺失时报错。新增红态为49通过/3失败，修正52通过/0失败，native requirements为空；没有运行Docker构建或实际镜像安装。

后继材料为`workflow/validation/qmt-query-context/artifact-packaging-001`，green回执SHA `35dbda3fd2443f8bc93473d1c4485de5c301d675fdd78028bedd247e7c72dc26`，实际日志SHA `08ddecc21eb85f4881e4b80d058bfb40a84b44335b1d6bfb45fd568deeed4b90`；原45/1和新49/3失败历史均保留。根任务回读red/green/style实际日志并核SHA，52通过及49/3失败相符，结果见同目录root-verification.json。新输入正式准备继续，风险decision.mode=full要求独立审查；本任务已有正式审查，原expected_review_kind规定后继报告为delta_confirmation。按当前最终包检查新增包装/登记及受影响链，逐要求确认结论，保留先前报告的输入身份；不重建任务或删历史来改变形态。根任务另核实际61文件Git提交范围及六登记，沿原owner独立重算当前/Git摘要相同；`artifact-build-001/root-verification.json`记录566旧行保持、六项有效。包装与manifest均未继续提交或部署。

包装输入的正式准备已完成，候选`d38813dd54c2bc1a08b413a81eb873e875fbafabc953e0504a450479ff221736`，查询包`f38094667805322e8dbcb4035d785805acc97be1eedf4d7fdb6f2394fc4fb410`、治理包`09d0c69f7dfe877e9c8d468f988752c8681ff48f9d6dc9a099be70263fa1e4c6`。查询7组检查全部成功，314/73语法/原Ruff按原工具复用，新增带coverage的52项实际执行；六制品预检均有效。治理3组按原工具复用。根任务回读两包SHA、新包装三文件原始SHA及全部10组实际日志，身份/返回码相符，见artifact-packaging-001/formal-root-verification.json。spec身份由原owner的多文档摘录计算，和单文件原始SHA分别核验。

该候选独立查询报告SHA `f09400214179eeb06f822cd97f381aba0557bbe1c3ee544ca20c3afacfc6c422`提出PF-AQ-32-COMPOSITION：完整HTTP/tick/Journal/GET/Bridge组合样本只包含32个新增字段中的16个，其余在较低层验证；R3/R6为gap。该项属于具体功能验收证据缺口，尚未发现实现丢字段。主任务沿原review-result实际导入，查询任务回到development；在原参数化样本补齐缺16字段和独立契约集合守卫，生产源码/规格/manifest保持。

同候选治理独立报告SHA `bd38cadb6e91b4a55bf0f85350c08f8bb9980d0527841341e41ffac45b3823f0`确认R1–R3 complete，仅覆盖治理及静态包装相容性。实际导入后原自动严格门禁6项通过，stage为ready_for_integration；量化changed-code coverage有缺失文件，保持unknown，未拿该数字替代行为验证。该gate只绑定d388，后继测试输入需要原机制重新准备/复审；整个组合尚未整合。两个独立报告均在各任务independent-packaging-delta目录，原失败/报告历史保留，真实运行和生产资格继续未授予。

## 32字段全链补测与当前复审

唯一测试文件`tests/gateway_agent/test_account_query_context.py`在原四类HTTP样本补齐16个字段，加入独立规格集合守卫；现有32项全部沿签名POST、原tick、Journal、GET、Bridge、重复ID及新Core重读旧终态验证原值、观察和摘要。生产源码、规格及制品登记保持。原策略测试owner实际315项通过；正式008准备重新执行315及52项，主任务逐项回读11份当前日志、包摘要和测试源码，见`build/native/qmt-http-bootstrap/source-boundary-001/qmt-final.json`。未重复执行有效测试。

007准备曾因本任务遗留的跨输入复用声明引用旧314日志，该记录保留并明确不授当前315资格。已撤回失效声明，008/004由原owner重备，实际正式315日志SHA为`45e47e52f752a175aab138f75b65168b6b1e47bf72c6415767280a4cb4560c6c`，输入与环境均匹配。原工具没有遗漏测试输入，未修改全局规则或重写旧日志。

当前candidate为`1d62fa823effcbcd7b583da2834735ee53a0cb1fbd5ec0aaf45a6c7ace211859`；查询包SHA `52680647ccef3eabe3c3380b2aeca9e9e1542f863742a36709e303fe577b80a4`，治理包SHA `caac758e6a5267b5efba71a82947ea64cf3a1ec7fe5e5ec499b5cd49ceb7fcc6`。两份当前delta已送独立审查，PF-AQ-32-COMPOSITION等待独立关闭；后继严格门禁、整合、安装与发布分别待完成。旧d388门禁结论保持其原输入范围。

后继当前输入复审已通过：查询R1–R6 complete且PF-AQ-32-COMPOSITION关闭，报告SHA `d083c47f909b23433bc8d98be18ccf5a4e938f1e5b1678a80cf8a8b3fc201c80`；治理R1–R3 complete，报告SHA `21dab772ad5892316daf6ab8d1630dd2e8249574ee2c65e7655caf223ad2f575`。报告分别位于当前generated根的`workflow/validation/<任务>/independent-composition-delta/review.json`。主任务核报告/候选/包身份后依次原review-result导入；自动严格门禁分别7/7、6/6通过，两任务stage实际为ready_for_integration、开放发现为空。相关批次沿原准入执行，保留的失败数据库资源保持；量化coverage存在缺失/无适用行等情况，不作为完整功能证明。尚未整合、安装、部署或改变运行终端。


## 本地主干整合

2026-10-22：现场复核 qmt-query-context 与 wt-stage-forward-context 均 ready_for_integration 后，按明确18文件清单封存候选提交 `10436d6d10cb7e5a588c39f9e3cd910d9d5805e6`，沿原 dev-workflow integrate 将完整已审树整合到本地 master `dc854b60d3ed061a6e420cedba6a97f11ab27e36`。原主干 parent `2083e96ac7134ad808d6bfddcdfe19aaa11a64fd`；实际 tree `f61d73c2e673c1a46722376904bb47632eaf9cd1` 与候选及集成回执一致，主干工作区干净。源端固定编译输入34777仍保持其原 Git 对象身份。

原工具回执 `@generated/workflow/integration/qmt-query-context/9f321522ff5040128ca5d4eecbcbc07f.json`；根任务复核 `build/native/qmt-http-bootstrap/source-boundary-001/integration-verified.json`。本项为本地代码整合，运行终端未安装、未重启，生产未部署，账户及交易事实未改变。纯观衡图表候选正在语义合并该当前基线，并重新取得其正式送审资格。
