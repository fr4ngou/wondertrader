# 批量日线来源的完整股票池 SDK 验收

类型：验证记录。唯一规格：[QAB](../specs/qmt-analysis-batch-source.md)。制品入口：`build/root-qas-market-batch-001/INTERFACE-001.json`，SHA `a3b1bf85e9bcdc76d35ae8259d24542fe485b30b6a66ba23f2b0cd49c94c74d9`。此记录对应隔离 SDK 与实机准备资格。

## 完整主链

普通安装 Host `0.1.0a16+dailybatch.3` / Agent `0.1.0a12+dailybatch.3`，沿原 WT qmt_read owner、真实 WinSHM、CPython 3.6.8 正式完整正文和单策略线程 SDK 替身读取固定5576股票池。沪2317、深2905、北354，每证券 none/front_ratio 各88个合成源日期，508实际SDK批次；一个原slot对应一个实际列表SDK调用。

`sdk005/RESULT.json` 主路径883.938秒，外层 `control-main002/RESULT.json` 884.5秒 exit0。1306输入前后相同，WT和Source内外所有Job均正常退出、tree0、双EOF、join、资源关闭。SDK登记唯一100毫秒timer、实际SDK仅原策略线程、运输线程0、禁止入口尝试0、下载/账户/下撤单0。替身外部驱动轮询5毫秒；本记录保留这项事实，不授实际终端100毫秒吞吐性能。

`sdk005/AUDIT-002.json` 冷核981376条原日线、5888256个float64逐位一致；508批次原请求/结果/来源binding和SDK区间/Native完成/收到时间全部关联。原容量64，观察高水位21，508个原ID均consumed，期满后retained0；关闭Journal的read_operations/read_retention均0，immutable读取和文件SHA保持。

## 消费、安装及恢复

公开消费包 `sdk005-capture.zip` SHA `66d6422905085a96d73bf5336634e7710ae80ea2268046796347ebc5118e8509`，18777929字节、513成员。保留原股票池、508批次slot、证券引用和SDK时点，无凭据或策略正文。复权/闭合资格为false，因子未请求。

原ATI完成新Host角色的源码构建、普通离线安装、pip check、RECORD及可供stage_artifacts消费的制品。`ordinary-host001/installation.json` SHA `fba9c53b575abb7e841d5d2a36d73aebb522ededfc202b88a083bc95c0e6a5b8`；两wheel与完整SDK使用者逐字相同。新23发行普通SDK环境保留其余21wheel。

10项新形状/分片及原v7真实共享内存SDK回归通过。`retained-checks002/RESULT.json` 验证已consumed原slot无运输续读、未知原ID只lookup不重交market POST、同capture换epoch在新提交前拒绝且旧结果保持；这三项是关闭后纯消费方夹具，没有实际Host/SDK请求。

## 原失败及范围

首轮 `sdk002/control-main001` 沿旧小范围QA整轮600秒，在525秒业务截止保留Pending；原320slot中319成功/consumed，最后原ID继续未确认。WT/Source正常关闭，1306输入保持。后继为显式新观察与新固定产品，不把成功结果转授旧ID完成或修复未知责任。`FIRST-RUN-BOUNDARY-001.json` 保留其事实。恢复夹具首轮错误使用带连字符UUID模拟32位nonce而被原协议拒绝；后继仅修夹具为合法nonce并通过，原失败保留。

`real005` 三证券/两批次的小切片已准备和check-only，0owner/0SDK/0Journal，根操作说明及ROOT-READY固定。真实QMT、BJ实际缓存/更新、全市场真实来源、闭合与复权资格、同正文v7+v8组合、生产和交易均另验。本模块不改变WT框架或金融协议。

七个永久源码目标按原SHA检查、保留回滚副本后合入，见 `PERMANENT-MERGE-001.json`；公共发行metadata由后继组合统一处理，旧冻结包/配对保持原件。没有Git提交或发布。
