# QMT原生复权资料实机采集

类型：运行证据。日期：2026-10-29。状态：八证券原生事件与同基准WT分析窗口已核验并完成模块交付；完整策略接线继续。依据[行情数据合同](../modules/market-data-contracts.md)与[模块A](../migration/module-a-delivery.md)。

## 已取得的真实资料

沿原QMT_METRIC_GATEWAY及其内存正文，通过Windows命名共享内存连接外部Host。源文件SHA256为0dfc91e9fbef8347327c646f138139e50e04f4eccbae66a1cf00bf086f39622a；本轮保持GH_WT_MEMORY_VERIFY及跨夜采集运行。全部调用限行情读取，下单、撤单均0。旧QMT工作树只读，原完整SDK只作为本次诊断依赖。

工作根build/qmt-native-adjustment-001。native-capture006的8项market.divid_factors均返回ok，共59条事件：510300为14条、515080为18条、588000/589000/159780各为空、510050为18条、512100为3条、510500为6条。FACTOR-INPUTS.json逐项绑定原回包文件SHA、requested_at与received_at。空响应保留原值，尚未据此合成全1因子。

外层qmt-native-analysis-control-360实际51.421秒exit0，forced=false、tree_zero/readers_joined/resources_closed及双EOF均通过。HTTP/IPC线程均join；停止传输后的runtime_failure=OSError作为关闭诊断保留。该结果证明8项原生读取完成，账户完整同步和持续连接资格另验。

native-capture005另取得510300原始日线401条与14条原生事件；前复权请求GatewayTimeoutError。market_data_ex的既有DataFrame转换保留行值但丢失日期索引，该回包尚不能单独作为已绑定日期的分析输入。外层359正常exit2、无强制且完整回收。

## 阻断与调用边界

原脚本先等BrokerClient.health达到旧系统账户同步ready，再发市场读取；实机已注册agent_tick并收到心跳，账户观察投影随后observation_rejected/journal_unavailable，导致0项市场请求。后继采集按实际SHM连接与策略心跳开始市场读取，各次使用新的隔离诊断journal，原记录完整保留；没有删除原状态或修改WT框架。原共享内存源端的账户观察错误仍待定位，不能声称已修复。

原单次回包上限262144字节。8证券全字段日线Panel明确返回result_too_large，未授成功；后继按容量分组并使用保留日期轴的market.market_data。原客户端支持timeout_seconds最大30秒，45秒配置在任何业务请求前被拒绝；后继已使用其支持范围。每项原生执行预算保持原配置，不提高交易权限。

## 后续验收

取得实际带日期的前复权价格，与既有原始日线按证券/日期配对，验证同一基准、单位、除息事件与倍率，再形成RR112 AnalysisWindow。当前资料统一声明current-visible-reconstruction和实际接收时间；历史首次可见时间及修订历史unknown。严格历史时点回测资格继续独立验收。

临时查询完成后仅停止QMT_METRIC_GATEWAY，核编辑器关闭并恢复逐字原备份；其他策略、原Host和跨夜Writer保持。原生框架新增修改0，无生产切换。原证据及失败记录继续保留。

## 本轮收口

分组前复权读取native-capture009首项返回operation_interrupted，Host runtime_failure=TimeoutError；外层363实际17.938秒exit2，forced=false且资源完整回收。该现象尚未定位到具体传输/转换阶段，现有Host io_seconds=2只是已核配置，不能据此认定根因。358–363外层均已终态关闭，360仅授8项因子读取成功。临时源已在UI停止且编辑器关闭，逐字恢复原备份d9c51b8150fbd9f511e1cfab9b24b532991276c6b5f6056e185a730fc2741824，RESTORED-009绑定；GH源99a8…372e保持。跨夜App18812/Writer50208通过系统进程再次确认存活。

本轮修改为开发诊断、资料与状态记录，独立审查范围none；既有原生候选资格沿原审查，本轮不改变产品DLL或WT源码。后继仍需真实带日期价格/原生因子配对及策略完整消费验收。

## 后继：真实前复权参考与全部因子倍率已交叉通过

2026-10-29 20:14取得native-capture010：两证券510300/512100在2026-01-15/16/19/20/21共10个股票日的none及front_ratio OHLC，包含1月19日除息前后。20:17的native-capture011取得正式八证券2025-03-05/06共16个股票日的同类参考；均保留真实日期键，两项原调用各自ok。原生事件按上海日累乘/换基准后与104个实际参考价格全部吻合，最大绝对差8.881784197001252e-16；3个空表证券原价与前复权价完全一致。独立可重跑入口build/qmt-native-adjustment-001/verify_factor_reference.py生成FACTOR-CROSS-CHECK-V2.json，exit0。该参考核实累计方向、事件日生效和本次八证券的空表恒等，完整WT分析窗口另由模块主链验收。

364/365实际40.734/23.109秒exit0，无强制、树0及资源完整回收。两次继续使用同一已验只读pair，磁盘策略正文为生成原件22877d…1f6；调用前后权限保持，未新增下撤单能力。当前临时源已在UI停止、编辑器关闭，RESTORED-011核原正文d9c5…1824恢复，跨夜GH来源保持。

大范围失败与小范围成功已区分；具体大回包耗时仍未定位，不能把现有2秒io配置直接当已证根因。主线现采用已核真实因子和WT原生Reader完成复权，旧完整SDK大回包继续保留失败资格，不作为产品回退。


## 原生模块最终交付与根集成

固定交付为build/qmt-native-adjustment-module-001/DELIVERY.json，SHA256 `d2b08e4cd7e61eb9312af3647a1d39cfd27257fd3169566fd2977a2754c907ac`。root对22项交付原件及8项源码/文档逐项核SHA，全部匹配；ROOT-INTEGRATION-001.json登记根核对，原sealed资料保持。独立full审查的Standards、Spec及QNA1–3均complete，剩余发现0；main006、边界、搬迁及ZIP安装的外层均正常exit0，forced=false、树0、EOF/join/句柄回收成立。

WT原Reader共读8870根raw/front；8证券共同区间2025-03-05至2026-10-28，共401日3208根AnalysisBar，基准日2026-10-28。普通安装正式1.1.2的AnalysisWindow、FrozenHistory及CurrentHistoryView构造成功。最终main006/ANALYSIS-WINDOW.json SHA256 `a38386d74bda91da91cc9669ffde734cb69ba50f4d06427fe27038e0ff857859`已交模块C接正式回测和页面。

倍率转换位于自有适配模块，价格计算使用原WT Reader；WT框架新增修改0。本模块只授当前可见同基准价格分析。历史首次可见与修订历史unknown，辅助策略事实、完整策略结果、账户/交易和生产资格继续各自验收。根集成本轮新增真实QMT请求0，原常驻采集保持。
