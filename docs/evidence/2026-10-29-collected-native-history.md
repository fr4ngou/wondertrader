# WT采集归档进入统一历史与完整观衡

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：功能验收证据。日期：2026-10-29。规格为[CNH](../specs/collected-native-history.md)，模块见[原生采集归档历史查询](../modules/collected-native-history.md)。状态：实现、独立审查、普通组件安装及完整App接口主链通过；整体发行、实际页面绘制与生产资格分别待验。

## 根因与实现

原Writer能够把采集分钟归档为DSB，原来源查询只登记QMI成功导入收据，新采集文件没有进入同一个查询入口。自有source-collected适配器补齐这一接缝：显式绑定原storage、数据集身份、证券清单和价量额单位，按请求读取原归档，经原NativeHistory/文件ABI/Helper及原select_sources，与旧历史合并。盘中DMB与分钟订阅继续使用原NMR；WT框架、分钟算法、Writer及默认路径保持原身份。

动态Writer目录以普通只读句柄捕获有界内容，复制前后及原Reader解码后核原文件SHA/大小。原冻结路径租约作用于短期私有副本，形成中或内容变化返回Unavailable。日线沿原base，不由分钟推造。未知单位、覆盖与历史缺口保留；不同来源不按时间范围偷偷补零或覆盖。

## 最终输入与制品

- 六份生产文件及两项原有测试适配的摘要见DELIVERY（外部历史/待归仓路径：`../../build/collected-native-history-001/DELIVERY.json`）。最终collected_history.py SHA为3dbaf586cb9344fa38f22338b513398e511258ab3ecf4f73a33c0b6f01c5aae3。
- 沿原scripts/source_market.py repackage生成package-002（外部历史/待归仓路径：`../../build/collected-native-history-001/package-002/BUILT.json`）：161文件、native_rebuilt=false；ZIP SHA为73033b952ec297105f4f01dee5505b2521aa91dea3228ac52cc22fb3dab10db0。原Reader SHA e79377207608b802f0bc818bbe11a7db3515392fd778cf08bb87fb8ef7316466，原Helper SHA 8209ed4eb5a28aa1daa40ffd13c22c09d0f382a2b8d151f81bdb5ebbf8e80c4a。
- 完整App来自原普通35发行安装环境，a19 wheel SHA adefd23aeab21a90171bb3bc5283bbbac13d9715bb0134e5da084898ec1f736c；最终SDK0.15 SHA 34579862be4dc777bf2f10cceff64d0df2a242a7ee78f368c06e9a4c744287ab。4690个非RECORD wheel成员逐字节核验，来源组件161文件逐项核摘要，原App/组件无现场源码覆盖。

## 主路径结果

| 运行 | 实际调用链及结果 |
|---|---|
| main004与独立回放 | 真实上午/下午副本经原Helper写自有DSB；同一服务缺档3根→第一次归档120根→追加122根；重复一致，provenance保留3+119，正常关闭。 |
| archive001及独立自然归档复验 | 读取137原15:05自然归档；SSE.510300、SSE.600000、SZSE.000001各240根，09:31..15:00，原Helper与SDK/HTTP标签和六字段逐项相同。 |
| app003 / 控制300 | 最终161文件组件由普通App a19的原SourceMarketProcess托管；三个证券各240根进入SDK及App图表HTTP接口，重复读取一致。样本base明确为回放fixture，不据此证明真实旧库合并。 |
| app005 / 控制302 | 实际整库配置（外部历史/待归仓路径：`../../build/collected-native-history-001/FULL-SOURCE.json`）登记335个分钟store与一个真实9ETF日线store，collection沿原6982证券清单；同一普通App读取三证券当天240根，并各查询241根：一根旧库尾记录+今天240根。旧记录分别为510300的10月28日15:00、600000和000001的10月27日15:00，均经原Helper独立核尾值。SDK六字段、App时间/OHLCV及分段1+240来源均精确，完整页面静态资源入口200。 |

最终安装主链app005/RESULT（外部历史/待归仓路径：`../../build/collected-native-history-001/app005/RESULT.json`）与外层302（外部历史/待归仓路径：`../../build/guanheng-workspace/collected-history-full-app-302/build-collected-history-full-app-302/result.json`）均通过：exit0、未强杀、树0、EOF、reader/monitor join及句柄回收；App shutdown_complete、读线程0、原始行情文件摘要保持。来源服务只读本地原DSB，无QMT业务查询、下载、账户、真实下单或撤单。本轮没有操作QMT界面、策略、原采集实例或生产配置。

三样本实际逐值验证不扩大为6982证券全部连续或与QMT原厂分钟完全一致。旧库股票缺10月28日的现状继续保留，241根结果不声称连续两日完整；自动补齐与长期采集沿其原模块继续验收。

## 回归、审查与失败原件

69项受影响回归（外部历史/待归仓路径：`../../build/collected-native-history-001/REGRESSION-003.json`）通过。独立Spec/Standards审查（外部历史/待归仓路径：`../../build/collected-native-history-001/REVIEW-INDEPENDENT.md`）最终complete，读取期间原DSB修订的P2已在唯一读取逻辑补后验并由独立反例关闭；审查未授普通安装资格，后继安装由本轮实际结果单独证明。

app001误用了QA状态字段，app002误把单来源响应要求为多段provenance，均在资源关闭后退出，失败原件保持。app004把全市场清单错误当作三样本期望，并在最终汇总访问未启动App的state；后继QA明确三样本、保留完整市场注册，失败清理汇总使用实际已创建资源，app005通过。以上修改仅在验收工具，产品源码保持独审最终身份。package-001为前一版冻结组件，正式后继只消费package-002。

## 剩余范围

完整App接口与静态入口已验，浏览器实际绘制和最终统一发行需消费该稳定组件另验。全市场单位/原厂分钟对照、五份归档相较收盘前副本新增15:00零量尾条的生成时点、旧库日期缺口、长期自动启动和次日采集分别保留。完整实盘策略/资金/成交链继续开发，真实交易与生产发布未启用。
