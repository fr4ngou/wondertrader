# 未知委托恢复停机的写等待收敛

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B STQ-P28开发验证证据。状态：affected-main-reviewed / whole-module-pending-verification。范围：唯一共振1.1.2、原WT账本、SDK替身，以及自有Standard恢复停机。要求沿[STQ-P28](../specs/native-qmt-standard-trader.md#stq-p28-未知写任务的恢复停机accepted开发中)，前一失败沿[原最终.2记录](2026-10-31-flat-theory-availability.md)。本轮新增WT行为及真实券商调用均0，全部新增文件位于E盘。

## 根因与正确实现

原最终.2的委托已进入SDK，源端保存unknown。P21恢复停机先完成策略quiesce、关闭新写准入，再排入原订单查询。自有Standard的唯一worker仍在按原30秒委托截止轮询同一命令，恢复查询排队等待，原约8秒Native停止截止先耗尽。阶段记录实际出现ready→stop→drain→quiesce完成→关闭写准入→订单查询入队→截止异常；quiesce约7毫秒完成，订单查询没有完成。260次GET均查询同一原命令，未新增交易POST。该根因位于自有写等待与恢复停止的衔接。

最终源`build/ms-unknown-write-stop-stage-001/StandardQmtTrader.cpp` SHA `8e339919be10b5ce65bc8e21eeec56983ff5490bbd5e9cbec80f47cab06ec693`统一以已有worker_stop或submissions_closed结束写等待，关闭写准入时唤醒原条件变量，POST前继续使用原未调用判定。正常运行仍沿原绝对截止；已发送命令的原收据、unknown和身份保留。修改没有增加字段、队列、持久状态、公共ABI或金融账本。

原Native006来源与配套c050 Host/Runtime保持；仅重编普通Standard DLL，SHA `ea40eec7e847a8c16042bdf5b6dd29ed8e6d88be65f2fa57b66c51d5566e31e1`。诊断版只保存在独占build，产品没有阶段日志插桩。仓库live Standard与Host保持原字节，候选差异交集成owner合入。

## 安装后的实际未知链

| 原件 | 结果与资格 |
| --- | --- |
| `build/ms-unknown-write-stop-native-001` | 普通Native及inventorysession.2，外Job26416 exit0，25.623秒 |
| `build/ms-unknown-write-stop-moved-unknown-001` | 实际ZIP搬迁安装，外Job29100 exit0，25.461秒 |
| `build/ms-unknown-write-stop-cold-proof-001/PROOF-001.json` | 冷只读复核原Journal、原金融文件、两代准入、停止及制品，无新增业务调用 |

两案各进入SDK1次、成交0，原Journal只有一条交易命令。首代在原停机截止内完成失败关闭，原因recovery_drain；原unknown、command/body/result摘要保持，无clean。第二代使用同Host/Journal/金融根的resume_clean，完成原四查询后在CTA、策略执行前拒绝；SDK及交易POST零增量。两代组件pending/forced均false，原金融文件保持，外层Job及全部业务进程树零、EOF、读线程join、资源关闭。

这项证明未知责任可以按已知失败结果结束进程，并在后继继续阻止无clean启动。正常业务clean、解除unknown和Host/Source冷重开分别保留各自验收要求。

## 正常主链及受影响回归

普通`build/ms-unknown-write-stop-evolution-native-001`和搬迁`build/ms-unknown-write-stop-moved-evolution-002`各完成初始库存卖200、后继买200，2次SDK/2笔成交/4条Host事件、原WT费用6元与PnL=-6；同根两代正常关闭，恢复零重复提交。外Job18372/6944分别51.055/48.621秒、exit0且完整物理回收。冷证明`build/ms-unknown-write-stop-evolution-proof-001/PROOF-001.json`核查询先于执行、成交集合、周期与原金融状态。

原P26消费者因历史TraderAdapter头身份失配先拒绝复用；按Native006精确输入重新编译后，`ms-unknown-stop-p26-regressions-002`证明正常运行同ID66次GET后成功、原D耗尽保持unknown，以及全局停止保持原未决身份。原14案129断言与49案2126断言的纯状态回归在新源通过。P26全局停止和纯状态回归分别授其覆盖范围；当时尚缺的两个POST前检查点已由下述受控窗口后继补验，正式整链资格仍按实际范围登记。

## 两个prePOST恢复停止窗口

`ms-prepost-stop-build-002`复用原P28源码和14个原对象，仅在原两次`write_wait_stopped`检查前调用既有测试宏内的gate。窗口一位于原prepare及来源核验之后、创建请求之前；窗口二位于原收据、容量预留和pending插入之后、`submit_once`之前。普通发行DLL保持原字节，测试支架沿Native006原头和26项原链接输入独立构建。QA只将原测试SPI的final限制移除，以覆写委托回报计数；产品源码保持。

`ms-prepost-stop-run-004`通过公开Factory/SPI/HTTP及query_first begin/end组门运行四案。两案分别停在原pending数量0与1的位置，公开`close_submissions`成功并核submissions_closed=true后释放gate；两者均POST0、源端命令0、确认未调用的委托拒绝1、接受0、unknown pending0。原全局stop_requested保持false，故直接覆盖恢复时关闭提交的路径。相同两个gate继续放行的对照各POST1、终态记录1、接受1、拒绝0。此对照同时确认原运输与回报主路可用。

四个Native消费者均正常关闭、删除，子进程exit0/Job回收/无forced/两管道EOF及HTTP owner关闭成立；外Job31084 exit0/1.986秒、树零/EOF/reader join/资源回收完整。构建Job24448 exit0/10.406秒、构建子作业全部回收。最初build001的QA继承final/命名空间错误、run002生成语法错误及run003误用账户夹具路由的正对照失败均保留；最终004沿原P26方式路由交易请求，未据夹具失败修改产品。

窗口证明（外部历史/待归仓路径：`../../build/ms-prepost-stop-proof-004/PROOF-001.json`） SHA `8f38f3969a0dfb3f0905e1e26c04606a5726eae93ec0f3aae2f05191424ab661`绑定131项原件。本项授予QA受控交错下两个原检查点的运输动态范围；普通P28最终DLL的未知轮询/全局停止沿原独立证据复用，完整Adapter/策略恢复、根三轮、跨日及整个B继续待验。独立窗口审查正在进行，真实券商操作和新增WT修改均0。

最终后继为`ms-prepost-stop-build-005`与`ms-prepost-stop-run-007`。独立复核先指出消费端三库未进入旧131项，后继在实际构建前后核全体绝对库及Native006冻结640源，005证明保留790绑定。复核又发现QA以无虚析构的`Spi`基类holder持有派生测试SPI；最终005将实际holder精确改为`unique_ptr<PrepostSpi>`，由具体类型销毁。004生成器首次替换层级错误，回读确认未生效且未启动对应业务运行，其构建原件保持；最终直接从003复制冻结源并单行修正，证明回读确认其唯一差异。

最终构建Job63484 exit0/10.846秒，四案Job11740 exit0/2.153秒，内部与外部全部物理回收。两关闭案仍POST0/拒绝1/pending0，两放行对照仍各POST1/接受1。最终窗口证明（外部历史/待归仓路径：`../../build/ms-prepost-stop-proof-007/PROOF-001.json`） SHA `c7d3963b1d0bbae5f07dbf86a5dad00292589d7dc6d699ad69abec2818f6cd2b`固定796项原件；早期004/005见证保留当时测试支架身份，当前资格沿此最终后继。SPI简化计数覆盖回报次数，完整回报金融载荷字段沿原正式P28证据单列；本窗口范围截止于两个原检查点的受控交错。

最终独立执行审查（外部历史/待归仓路径：`../../build/ms-prepost-stop-proof-007/REVIEW-EXECUTION-001.json`） SHA `9af02e61e2e11a46974b5af14616f961f927454a2f70eb1456d45b9d638abcf9`核803绑定，开放P1/P2为0；QA析构P2与链接身份缺口均已关闭。审查准确限定两个指定窗口，原最后检查之后的其它交错、完整回报载荷及整个策略恢复分别保持未覆盖。本项完成后回到原完整三轮、正式次会话及自动首分析主线，共享Host持久层修复由A独占负责。

搬迁普通链首轮与unknown案错误地并行使用同一合成账户，原account_lease以183拒绝、SDK0。该QA编排失败及完整回收原件保留；待原案结束后顺序运行同一普通链通过，账户独占逻辑保持。

## 制品、审查与剩余

新制品`build/ms-unknown-write-stop-package-001/B-UNKNOWN-WRITE-STOP-001.zip` SHA `911889ed1f12c34816d9773eb9da43d25e250ac71893a672c5572c72c5c67f19`，58成员；Python仍为inventorysession.2，搬迁23发行/1332条摘要RECORD。全部8执行Native与独立Scan2来源沿`build/ms-unknown-write-stop-delivery-001/FULL-NATIVE-ORIGINS-001.json`登记，未重跑历史640/400源审计。新普通/搬迁测试只替换最终Standard，配套Host/Runtime及Python输入保持。

62份冻结输入交两位独立审查，清单为`build/ms-unknown-write-stop-review-001/SOURCES-001.json` SHA `0799be474507003df953b6993a1f5e8250390aa5941e3279de23d3965a596172`。协议报告SHA `03501fc8b1f5c5d090226672b5fd38b9803d9b01cd32eb894f03f476c6484c83`核658绑定；执行报告SHA `81812d6a7013aa6e15685308695b3bb34078d69a7d9d5fd6ce87088397377bb7`核338绑定。新增P1/P2均0；该次封存时两个POST前精确窗口尚缺动态验证，后继范围见上文最终007。原冻结checkpoint001有一条沿用旧unknown停止缺口的保守文字，执行审查登记P3；后继002已按新原件更正，001保持原件。

最终HANDOFF（外部历史/待归仓路径：`../../build/ms-unknown-write-stop-delivery-001/HANDOFF-001.json`） SHA `0f8c974fded0ad181f7cd60a20bef4d8c56ee10857fd4c24460cf86c6f8138b8`与检查点002（外部历史/待归仓路径：`../../build/ms-unknown-write-stop-delivery-001/INTEGRATION-CHECKPOINT-002.json`） SHA `afa19ebaca06b418b1cc168097d9d80b6c82605269abdf4c669478e28f194a2f`绑定最终源、Native、Python、制品和两报告。封存Job47692 exit0/0.862秒，62原件及副本、996报告绑定、两冷证明和包摘要均一致，物理回收完整。旧broker交接新增SUCCESSOR005、前一.2交接新增SUCCESSOR001，历史原件保持。ready_for_candidate_development=true，ready_for_root_candidate_integration=false，whole_module_qualified=false；固定候选供根后续开发组合。

完整次日原生会话/交易前解冻、自动真实时钟首个合格分析、完整Host/Source冷重开与原命令unknown解除、真实券商收费、最终撤单/多策略/异常矩阵和统一候选主链继续。SDK独立净费用/净可用资金的后继已完成，见[费用证据](2026-10-31-flat-theory-availability.md#独立sdk净费用与资金观察后继)。旧native032停止具体阶段保持unknown。真实下撤单、生产切换及新增WT行为沿对应明确授权执行。
