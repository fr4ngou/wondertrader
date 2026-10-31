# 统一行情安装候选接入自然归档查询

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：组件后继安装与集成证据。日期：2026-10-29。规格为[MRC-R5](../specs/market-runtime-candidate.md#mrc-r5-采集归档查询后继)。状态：装配、搬迁、组合主链、普通完整App接口及独立两轴审查通过；整体系统交付与生产资格继续。

## 根因与改动

原统一候选固定history=RS14-package005，已经独立交付的CNH-package002无法由原装配器选择。自有打包工具集中登记已批准组件清单SHA与版本的唯一映射，显式输入哪个已登记原件就装配对应版本；旧RS14候选继续验证，未知原件及版本错配拒绝。manifest/schema/消费字段和默认关闭保持，其他五组件不变。没有修改WT框架、运行算法或App生命周期。

CNH最终组件原清单SHA为225791a042473d5aa669bf8f56aa09a3ed2d3e06cb3d8864db4270e102167903，161文件。原组件已通过[CNH实现及普通App链](2026-10-29-collected-native-history.md)，本次重点核统一新安装路径及与其他原组件组合。

## 新候选与身份

运行目录build/market-runtime-collected-001，candidate-001及relocated-001，总1162成员。总manifest SHA为077b06199177ada3e014745bf777317af2d5d3d24879092044e945f7ceb0d21a；ZIP SHA为f484cbce499d87081107947ebe0871ba2cb18ff9e3a97e34e58c9e9d9175c6e3。原脚本create→完整ZIP核验→extract新目录→resolve实际路径全部完成；ASSEMBLY（外部历史/待归仓路径：`../../build/market-runtime-collected-001/ASSEMBLY.json`）同时核新组件原161文件、其他五组件与旧005逐字节相同，以及旧005原manifest继续有效。外层305正常exit0/树0/EOF/join/句柄回收。

## 实际组合主链

main002/RESULT（外部历史/待归仓路径：`../../build/market-runtime-collected-001/main002/RESULT.json`）沿同一relocated-001完成四链：普通SDK0.15安装→原历史服务1m/d1；NMR原Reader/闭合通知/切片持有/stop与默认HTTP；显式v6 Parser→正式HPR Host→真实Windows SHM→国信3.6.8完整内存正文SDK替身；原采集service→正式SHM/SDK替身→005原Writer→原Helper回读和App采集owner关闭。组件运行后重新verify，载荷保持；外层309正常exit0、未强杀、树0/EOF/join/句柄回收。真实QMT业务请求、下载、账户与交易均为零。

app006/RESULT（外部历史/待归仓路径：`../../build/collected-native-history-001/app006/RESULT.json`）通过原collected_app复用入口让普通35发行a19/最终SDK216从新统一候选的components/history启动服务，使用实际335分钟store+一个9ETF日线store与今天137自然归档。三证券各240根，并各读旧尾1+今日240根；SDK六字段/App时间OHLCV/分段1+240精确，重复一致、原文件保持，App及所有owner正常关闭。外层307通过；图表HTTP和静态入口与浏览器绘制分别记，后者由C继续整合。

## 验证范围与失败原件

main001在NMR现场测试失败并保留：原测试在下午收盘归档后仍按上午120根/11:30截止读137，现场已为240根DSB，原Reader明确拒绝不匹配cutoff。新候选未修改Reader算法。后继QA显式minute_scope=snapshot，只读取原212上午冻结副本并验证新安装路径，collector_phase=not_observed且不读取旧LIVE.json冒充当前连接；原snapshot-and-live默认路径及原白天实采资格保持。完整下午真实分钟/当天采集沿原证据，当前回放不授新现场资格。

profile001回归（外部历史/待归仓路径：`../../build/market-runtime-collected-001/profile001/RESULT.json`）实际验证新/旧候选、两种已登记版本与原清单错配、未知版本、内部包络摘要一致但来源未登记，以及create未知原件时不产生输出；其他五记录、schema及defaults相等。原路径/ZIP/容量边界代码保持，前次有效证据只复用其不受改动范围。

独立两轴审查（外部历史/待归仓路径：`../../build/market-runtime-collected-001/REVIEW-INDEPENDENT.md`）最终Spec实现/制品与Standards均complete、问题0；独立新create/ZIP/搬迁/17入口resolve及五组件全字节保持和身份错配拒绝通过。其110秒首轮超时保留，随后独占输出续验66.094秒完成；独审没有执行App/Host四组合业务运行，该范围仍按本次作者实际运行原件证明。系统整体M3、当前App实际页面、跨机器Python锚点、长期运行/次日采集、源单位和原厂分钟一致性、真实写与发布仍待所属链验收。
