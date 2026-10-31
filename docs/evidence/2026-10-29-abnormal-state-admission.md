# 实际异常状态的恢复拒绝与资金拒单验证

类型：开发验证。结果：partial。关联[模块B](../migration/module-b-delivery.md)的B-05/B-06、[P21](../specs/native-qmt-standard-trader.md#stq-p21-原保存加载的产品正常恢复accepted开发中)及[NRT-R16](../specs/native-realtime-strategy.md#nrt-r16-真实策略目标与账户资金拒绝的原生结果链)。异常状态恢复拒绝通过；资金拒单及频次整链尚未通过，完整模块保持in-progress。

## 固定输入及范围

本轮继续使用[当前App003开发包](2026-10-29-current-app-native-composition.md)的普通离线搬迁安装：Appa19/core a7及35发行、Runtime SHA `241cdba18271b4c9a3800efdb97a2750b30326c571554fb3cf86125a5445ffcd`。安装文件及4690个wheel有效载荷沿该安装收据核验。产品Python/原生代码和包均保持原字节；变化仅为B专用QA、规格和证据。策略核、持仓/资金/绩效、保存恢复仍由原owner处理，新增金融账本和WT核心修改0。

本轮审查时主会话仍在核实际持仓清单；后继用户已确认唯一策略为resonance-regime-v1且全部券商持仓归它，并要求运行/发行只保留最终最新正式在用规则。1.1.2激活线索与1.2.0配置分支分列，实际规则/参数仍由主会话核准。其他策略和历史版本退出后续运行/发行及验收，已完成的源码和证据封存。本轮沿既有configured共享主链收尾，没有新增算法；本批35发行及1.2.0共享验证不授新范围的最终策略/发行资格。

## 资金拒单原件：尚未取得完整资格

原件根为`build/ms-broker-cash-refusal-001`。理论本金每策略显式50000元，唯一configured核仍给A/B各700股目标；合成券商account.available=1000元、实际持仓空、废单状态57。资金不足是SDK替身明确提供的柜台事实，尚未证明委托前可用资金检查。原报单总量和频次规则按实际配置单独验收。

| 原件 | 实际结果 | 结论 |
|---|---|---|
| main-001 | 首账户查询在执行前queue_timeout；源排队TTL1000ms，SDK查询/下单均0，插件IoError；Host/来源/HTTP回收完成 | fail，未进入资金场景 |
| main-002 | 修改专用Host policy为排队5000/执行1000/总6000ms，保留原native request8000ms；首单进入后，合成废单误填remaining0/canceled0，原金融映射InvalidInput | fail，QA源字段错误 |
| main-003 | 沿既有废单源契约统一为original1400/traded0/remaining1400/canceled1400；仅order_total_limits=1仍出现第二次尝试，被一次SDK断言捕获；正常父关闭但source.first_error存在 | fail，旧proof曾标passed，最终父断言明确撤销该资格 |
| main-004 | 增加order_times_boundary=0/order_stat_timespan=3600；完成4查询及1次SDK后，原进程exit3221225477（0xC0000005），未发布closed；Host/来源/HTTP均回收 | fail，频次及资金拒单整链未完成 |

main-003第二次尝试具有另一原命令身份，进入源SDK包装后发生断言异常；原成功记录1次与尝试2次分别保留，未知结果没有记成确定失败或安全等待。main-004只记录实际退出、收据和资源状态，按用户决定继续停止WT线程调查及核心提案推进，没有原生栈/内存研究或新核心修改。

## 异常原件到恢复拒绝

`build/ms-unclean-state-001/reject-003`将main-004实际留下的2份策略JSON、2份用户KV及1份组合JSON按原字节复制到专用隔离状态根，保留实际异常原件及原Host Journal。副本缺少.cta-clean.json，显式配置resume_clean，沿同一已安装产品、标准Factory和原恢复准入运行。

原四查询完成后，恢复准入在策略初始化/首次setter前拒绝；没有ready，子closed.ok=false/error_code=cta/recovery_ready=false，父faulted且pending/forced=false。新代SDK0、原异常5文件及副本5文件摘要均不变，没有生成clean/consumed标记。原Job进程reaped、双管道EOF/reader join、Host/来源/HTTP均完整回收，driver exit0。这证明实际异常内容副本的缺证明准入拒绝；异常同根自动续跑、跨进程原命令责任恢复及完整B-06仍待验。

reject-001同样完成拒绝，旧RESULT的native_stdout_consumed标志沿成功路径误设true；后继002修正为false，原件保持。测试并未删空状态、生成干净证明或以新状态根执行原目标。

## 自有QA观察与正常兼容

compatibility的compatible-001同样在4查询/1SDK后出现原进程0xC0000005。旧QA只等待closed文件及业务查询，实际进程已退出后继续等待到55秒业务截止，最终proxy.join未获确认；Host/来源已关闭，外层driver退出及作业回收分别保留。该实例不授完整正常关闭资格。

QA在正常业务观察tick中检查原ProcessJob.poll及closed文件；进程退出即结束观察，startup及原close阶段保持各自原流程，给有限关闭预算保留时间。专用process_liveness只读取本测试实际进程状态，不改变产品或原生行为。liveness-boundary-001以main-004实际记录的退出码和缺收据条件验证及时拒绝观察，同时覆盖存活、已关闭及缺句柄；这是值边界验证，没有启动WT或账户请求，尚未单独证明修正后再次发生同类原生异常时的全部关闭时序。

独立审查发现两项QA P2：预期失败分支需要在closed后写proof，无条件存活检查会误拒绝合法窗口；后继注入调用曾出现缩进错误，可能影响正常入口。最终控制流在各预期终态分支返回后才启用正常业务存活检查，注入调用严格保持在partial分支内。partial-projection-002在原closed校验完成后显式延迟250ms才写proof，实际4查询/SDK0、原异常及失败收据保留、完整物理回收通过，验证上述窗口。

最终QA下compatible-003完整进入原configured主链：A/B各700，组合净买1400一次、8查询、后继converged；子closed正常，父/Host/来源/HTTP及Job/管道全部回收，driver exit0。reject-003在同一最终QA下再次验证缺干净证明拒绝。此前compatible-002、partial-projection-001和reject-002按各自实际源码保留；最终成功覆盖当前实际输入，没有修复、解释或提升compatible-001及main-004的失败资格。

## 交付与后继

新QA文件、各次实际运行源快照、输入/命令/原件/安装及审核由`build/ms-unclean-state-001`的MATRIX/REVIEW/DELIVERY绑定；MATRIX-001保留审查前快照，MATRIX-002和REVIEW-001冻结审查修正及全部后继运行原件。独审后用户确认唯一策略及最新在用规则范围，SCOPE-001和MATRIX-003单独绑定该文档增量，原独审保持当时范围。资金场景四次失败及源码阶段均保留。产品包沿R15封存，不另打包或发布相同运行库；新的唯一策略候选仍待实际规则及接管主链。真实下撤单0，生产切换0。

后继只接唯一共振策略的最新在用核及profile；全部持仓的归属已由用户确认，资金预算继续沿实际配置，历史交易不迁入、K线保留。当前资金拒单/频次资格、完整资金/T+1/费用、异常命令恢复、同账户跨根责任及统一候选继续。实际quote+自然分钟按A已交[真实组合](2026-10-29-qmt-real-market-cta.md)复用，真实日线实时预热沿C明确领域契约后消费，继续保留历史首次可知未知与严格回测/HEM的差别。
