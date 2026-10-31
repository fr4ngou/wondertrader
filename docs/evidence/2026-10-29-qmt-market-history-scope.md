# 来源支持范围补齐与统一安装后继

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发与集成证据。日期：2026-10-29。状态：来源范围实现、独立安装、搬迁组合、独立审查及真实QMT清单外ETF缺数补齐到完整App接口主链通过；全市场持续覆盖和整个系统交付继续。规格：[HPR2](../specs/qmt-history-preparation.md#hpr2-固定输入与预算)、[RS15](../specs/qmt-source-history.md#rs15-来源支持范围与补齐配置)、[MRC-R6](../specs/market-runtime-candidate.md#mrc-r6-来源市场范围补齐后继)。

## 根因与实现

原Agent的limits.v1和SourcePreparingMarket的preparation.symbols分别校验逐只证券清单，早期测试范围成为正式补齐门槛。新limits.v2省去symbols，沪深代码经原格式校验进入原QMT下载调用；外部正式source-preparing配置省略symbols。旧limits.v1和含symbols的配置维持原行为及收据身份，新descriptor继续进入原profile/配对摘要。原profile.v6、policy、请求/结果、任务去重、原线程、SHM及Importer/Reader保持。

生产逻辑仅修改Agent的history_preparation.py与外部source_history_preparation.py。装配工具market_runtime.py增加两条原清单SHA映射，原默认、schema和其他四组件保持。新增WT核心修改为0。原生Reader/Helper等二进制与旧CNH安装逐字节相同；新版历史安装161个成员只变化上述两份Python文件。

## 已执行主链

| 运行 | 结果与范围 |
|---|---|
| protocol002 / 控制319 | 旧v1的510300.SH与新v2清单外510010.SH分别经过签名HTTP、真实Windows命名SHM、原策略线程下载替身、1m/1d调用和原历史回读；重复下载为0、两代重连/原结果保持、正常关闭。沪深股票及ETF参数和旧v1范围兼容另有回归。286项unittest通过。 |
| 客户端控制318 | 省略symbols的配置让沪深ETF/股票查询实际进入原补齐窗口；旧含symbols配置保持原范围。 |
| 独立安装控制320/321 | 新HPR普通wheel离线安装与来源历史包生成完成。历史包仅两Python文件变化，未重编WT；HPR普通安装带当前App共享读取器，由后继组合实际核验。 |
| installed-main001 / 控制322 | 新安装Host/Agent及来源服务→实际3.6.8完整内存正文→原SHM→下载替身→原Helper/Reader→SDK，缺档5根、重连后6根、重复及服务重启原UUID/原值保持。两代正文文件/网络拦截计数0，全部owner及外层资源关闭。 |
| unified/candidate-001与relocated-001 / 控制325/327 | 1162成员统一包create、ZIP摘要核验和新根extract完成；manifest为2f417ae0f96ee2ef01dad0326e0c22cffa8eb7a62989f851d4a1cd4a8ae2f65e，ZIP为ab52842b4766462abd090a043220c2430cc6057908ab3bc78e521a227ce561cf。 |
| unified/combined-main001 / 控制329 | 搬迁根四条原组合链：普通SDK历史1m/d1、原NMR快照、v6 Parser/HPR/真实SHM/3.6正文、原采集Writer/Helper/owner关闭，均通过。快照沿原上午冻结样本，不代表新现场实采。 |
| unified/scope-main001 / 控制330 | 搬迁根新Host和历史组件再跑省略逐只证券配置的完整5→6根补齐、重连、重复/服务重启及原值读回，全部资源关闭。 |

新HPR原安装清单SHA为819ae7497b765f4005afc230f3d6bc46d5c58c70d47fcb615173d4c62af45ba1；新历史原安装清单SHA为199c3eb662d135b6866a5bc21b19d98393fdeb8cf720194e98597042af24542e。目录及生产摘要见开发记录（外部历史/待归仓路径：`../../build/qmt-market-history-scope-001/DEVELOPMENT.json`）。上述替身下载均非真实券商下载。

## 本次真实来源观察

沿既有GH_WT_MEMORY_VERIFY正文及配对做有限真实来源联调，没有切换QMT正文。build/qmt-collected-demand-real-001/run003先读取588000.SH在2021-11-01 14:51..14:55得到0根，原market.history_prepare实际调用1次并返回call_returned，后读仍0根，本轮以未发布失败收尾。保留原UUID9bb6194c-4b2a-4e8d-a3f6-e494ef88b5ff；DAT摘要保持，终态不能解释为已有数据。下载未重发。

后继real-readback002仅回读：2021同窗仍0根，2026-08-24同窗取得5根，证明同连接和读取链可用；新增下载0。run004按2026-10-28近期窗口，在源缓存首次读取即取得5根，经原Importer/Reader、SDK和普通完整App图表接口逐字段一致；重复与App读取新增来源操作0。该轮新增真实读取1次、下载0，证明既有缓存导入及完整App链，不宣称缺档下载成功。

真实各轮原QMT正文SHA保持，账户/真实下单/撤单和生产切换均0；App、Host、来源服务、读线程、端口和外层Job均正常回收。2021目标窗口仍缺实际数据，具体供应商范围或下载行为需要继续核实。以上为旧正文阶段记录；新limits.v2实机后继如下，全市场连续覆盖仍待长期验证。

## 同一QMT条目的新版真实补齐后继

先用新统一候选中的HPR产品配对工具生成并verify完整正文，保存原GH_WT_MEMORY_VERIFY.py逐字备份。原文SHA为6be3b6e5d9b41fc6861b40972192e31d7aae72bc73933ca65bddad7ed0a9b89b，新正文SHA为99a8d6fef78847dcc018a61a8dcd7c484ecbf5171654558f7944149265be372e。通过computer-use仅停止并启动同一原条目；其他策略运行现状保持，没有新建策略、改交易权限、下单或撤单。新源配对及原文备份在本地私有目录，未入公共安装包。

真实run005结果（外部历史/待归仓路径：`../../build/qmt-collected-demand-real-001/run005/RESULT.json`）及控制334实际通过。普通App使用新统一候选history和HPR，正式配置省略symbols；read-binding成功认证原profile.v6及limits.v2，preparation_symbols=null。查询原9只清单以外的510010.SH在2026-10-28 14:51..14:55：来源前读0根，market.history_prepare调用1次，后读5根。原准备ID为e9dd6195-d5ca-4177-be3b-69c6f0b4d0c5，终态ok/call_returned；源DAT由不存在变为存在，SHA为bf79b47c86372e03819b395165e06a9da4dcb9e7f0389df4a16cbe7ceb855c24。

这5根经过原Importer/Helper/Reader发布，SDK与完整App图表HTTP时间/OHLCV逐项相同；SDK重复及App消费无新增来源操作。该轮真实操作精确为历史前后读取2次、下载函数1次。App shutdown_complete、读线程0、来源服务/Host全部closed，外层进程树、管道、reader/monitor及Job句柄正常回收、无强杀。新正文在运行前后SHA保持，账户/真实委托/撤单及生产服务切换均0。

QMT原条目当前已更新为新版候选并运行；本次App/Host实例按验收结束正常关闭，后续由统一App使用新descriptor重新管理。全市场新源路径已按沪深格式开放；本次实机样本只证明一只ETF的实际0→5根补齐，沪深股票链由独立安装替身另验。2021旧缺口、长期采集/恢复、全市场连续覆盖与整体系统M3/M4继续。

## 原失败及后继

protocol001误用无pytest的产品Host环境执行额外开发回归，三模块导入失败；286项实际主测试及两条主链并无对应失败，protocol002改用已有开发环境，完整通过。原外层和原TESTS保留。real-readback001的QA没有等待202异步结果即结束；后继同一下载事实下仅做缓存读取，修正工具等待原ID结果，未增加下载。此前真实run001/002的错误选样/QA导入失败沿原目录保留。

独立full审查的Standards/Spec均complete，待修源码问题0；报告绑定三份生产源码和新安装原件，独立执行清单外ETF、沪深股票、5→6根/原UUID恢复与统一候选链。四个重建console launcher的完整PE等价性保留unknown，实际产品主链使用原SHA保持的python/pythonw模块入口。真实QMT续验由本轮root另证，原独审时点的真实来源unknown保留。后续继续2021旧源缺口、长期持续采集及整个系统M3/M4；只读页面收敛由模块C继续，真实交易和生产发布沿原授权。
