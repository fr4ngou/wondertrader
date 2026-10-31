# 原CTA与原Porter的400期历史对照

类型：模块B开发证据。状态：本历史模型限定验收完成，整个模块B仍in-progress。要求沿[NRT-R28-C5](../specs/native-realtime-strategy.md#nrt-r28-逐日基准的原生回放与完整比较)及[模块B](../migration/module-b-delivery.md)。原件根为`build/ms-native-parity-001`，本轮新增运行、构建、临时及缓存文件全部位于E盘。

## 实现与事实所有者

自有测试宿主复用固定原WtCtaEngine、CtaStraContext、ManagedStrategyBridge和普通安装中的正式RetainedStrategy、唯一1.1.2及NSQ。测试只调用原日期/session/tick/bar/schedule公开接口，未启动实际ticker、Source、SDK或WinSHM；WT框架和生产运行代码新增修改为0。金融持仓、费用和损益保持原WT计算，本测试没有新增金融账本。

输入为原A逐日ReplayCatalog及401窗SHA。测试发布替身把当期A原价前缀交原Helper生成DSB并完整回读，原因子/分组输出/元数据保持原字节，原RealtimeReader经已有publication入口切换和清理。替身发布与收据采用专用model schema，不授真实AWP资格。A的known_at/received_at保持，历史时间使用原RetainedHistoricalModel。

原CTA模型在下一原交易日09:31使用上一闭合窗计算，原价开盘成交；后继原价按原HisDataReplayer的开/高/低/收路径推进账本，15:00完成原session_end，下一轮才把该闭合窗交算法。末期缺后继原价时显式保留末日价格。原d1 Mocker成交时间标签为15:00，CTA为09:31，成交来源字段复制各自原生成交CSV。INIT归档只含当前已闭合单分钟，后续分钟按原事件入口逐期推进。

## 已有实测

`native-009`测试DLL SHA为`9a4f222941d80afc9f0d846cd542290b79354830d280e439a61c023eb5cea068`，绑定709份冻结源和13项链接输入。固定WtCore.lib SHA保持`d76d40f5a78bdc942e0e1489215832c02ef9a48259d209ee67699029adabf3cc`；configure/build均exit0、进程树0、EOF、reader join及资源关闭。

`smoke-005`原安装实际110期：98预热、12正式算法计算，原上下文正常销毁，Reader缓存消失。初版`main-001`实际400期/302计算/65笔原生模型成交；旧来源价格及比较器审查问题保留，未据此授完整一致结论。

修正版`main-002`已完成400期、302正式算法计算、65笔原模型成交及400次原日结；原setter累计248，created=destroyed=1、active=failure=0，Reader缓存消失。外层Job根PID49388 exit0，root reaped/tree0/EOF/readers joined/resources closed均成立；实际加载DLL的底层解释器PID未独立采样，不能用该Job根代替。

`reconstruct-001`使用原Porter保存观察重建前120期纯核输入，22份正式结果的input_sha256及full_result_sha256均与原报告相符，进程正常关闭。完整302份重建及最终比较见下节。

`proof-negative-001`在同目录保留实际400期报告，显式把完成证明的result_sha256换为其他值，再提供该证明自身的正确SHA。比较器在原件交叉身份处拒绝；未产生比较成功文件，进程exit1为预期拒绝，物理回收完整。此案覆盖首轮审查指出的“分别有SHA仍可混配”缺口。

## 失败、审查与范围

早期构建错误为测试代码使用错误的原头文件/重载；Windows系统库名被当作绝对文件路径的脚本错误已修正。原件逐代保留。smoke001使用已拆分SDK的旧导入路径而退出。smoke002–004把未来分钟归档暴露给历史时点，Reader在原m1读取处拒绝；后继按期提供闭合输入，不修改WT或放宽Reader截止。

首轮独立审查分别保存`REVIEW-PROTOCOL-001.json`及`REVIEW-EXECUTION-001.json`，共确认比较语义/终态遗漏、完成证明交叉身份以及测试成交来源使用后继mark价的问题。原报告冻结。后继独审又指出可卖差异仅凭数值形态归因T+1并自动豁免的比较器缺口；本次实际差异计数为0，最终实现仍删除该豁免。`sellable-regression-001`对冻结旧gate与最终gate运行相同五个受控值，旧T+1标签差异未解释数0、最终1，其余差异全部计入，进程正常回收。

## 最终完整比较与交付

最终`main-003`保留相同native009和普通安装，补齐原回测OHLC标价路径；实际400期、98预热、302完整算法计算、65笔原生模型成交、400次原session_end，setter248。Job根PID18328 exit0，全部物理回收成立；created=destroyed=1、active=failure=0，Reader缓存消失。原模型两端全部最终金融明细（成本、数量、浮盈、最大/最小价格和最大盈亏）相符。旧main002因缺少high/low标价产生的路径差异及compare001的false结果保持。

最终`compare-003`核400期原窗口SHA/因子身份、302份完整BT输入与完整结果SHA、原RT全部NSQ重放、计算前及日结后原数量/可卖/资金、逐证券65笔完整成交顺序、400行原funds.csv及最终原生金融文件。differences为空、unexplained为0，限定声明模型与归一规则的semantic_parity_proven=true。COMPARISON SHA为`a39d88083c59b38e58b17ab3119d1aa2feece759f61a3bc72546bd425f399a11`；Job根PID31856 exit0、root reaped/tree0/EOF/readers joined/resources closed均成立。父完成证明经原StrategyHost结果验证交叉绑定run/request/install/result/report，末期原目标无新增提交，保留末价模型没有未核新成交。

差异按原值保存：50期NSQ目标日期来自同一C target_for_result在下一会话截止下的fallback；4期共12个state basis金额字段最大差5e-12元，计算前55个和日结后55个资金字段最大差1e-11元，均在事先声明的1e-8元比较容差内。不同标的成交日志写序按逐证券完整顺序核实，15:00/09:31标签、tag/计数器、空仓与空条件记录分别保留。可卖差异全部阻断，没有T+1自动豁免；金额相符的结论沿明确容差，不代表逐位相同。

`SOURCES-003.json`冻结四份最终源，SHA为`aae318dfb53de647110a45bf3b0a380d7cdc75cf0ba4ba41f31624ec8817dbd7`。`WITNESS-001.json`绑定5255份实际模型文件/53,228,167字节、709构建源/13链接输入及七发行760条安装RECORD，均无漂移；SHA为`6390abdaf28ece14dfa5c068d3f25e140a1dfbdf2d27061ed96acefa0879c0a7`。最终独立增量报告、验证制品与交接摘要沿本根HANDOFF/DELIVERY/POSTFLIGHT登记。

本记录授原CTA历史模型的同核/目标/执行/原生财务对照资格。实际AWP/ticker/WinSHM、正式WRI统一候选、真实来源、存量持仓接管、真实跨日、C普通App/HTTP/页面及整个模块B继续验收。本轮未执行真实查询、下撤单或生产切换。

## 根集成接收

根在 `build/root-rtbt-400-intake-001/ROOT-ACCEPTANCE-001.json` 接收本历史模型基准：15份封存源/比较/运行/审查收据及完整ZIP摘要核同，5,339个归档成员的字节数和SHA逐项一致，三份测试源码与当前工作树保持。整个规格文件已因后续初始库存等需求更新，归档中的原NRT-R28章节与当前章节仍逐字一致；归档规格原SHA保持0aad48…，不以相邻新需求回写旧运行结论。

原COMPARISON的400期、302次正式计算、65笔模型成交、248次setter及0未解释差异已核，原生运行正常关闭及物理回收成立，复用两份已绑定的独立审查。该接收只授已声明历史时钟、成交及金额容差下的模型对照，未重新运行实际QMT、ticker或WinSHM。当前库存接入按用户新决定仅接当前持仓，旧开仓历史重建要求已取消；新运行及最终观衡资格继续独立验收。
