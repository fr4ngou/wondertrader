# 2026-10-30 八ETF逐日原生前复权窗口

类型：验证记录。结果：开发主路径、边界与隔离安装通过；独立审查记录见最终交付。关联 [QNA4/QNA5](../specs/qmt-native-adjustment.md#qna4-逐日原生回放窗口)。

## 输入与实现

原 accepted QNA 的 main006 NativeRead、八证券真实因子与日线保持：8,870条 raw 日线、59个因子事件、八证券共同401日（2025-03-05至2026-10-28）。原 DLL SHA `12591cf9d1073449615a6146ce2e5037ae07494002b6bffa77916844980bb838`，全量原件身份在 `build/qmt-native-replay-001/main002/catalog/MANIFEST.json`，SHA `328978f0eee0d0ad1b65cab7ee5fd6073158efecab6af3d63ae580260325f6bf`。

新增自有 `qmt_native_replay.py` 与薄 `WtReplayProbe`，复用同 DLL 的公开 `IRdmDtReader.readKlineSliceByCount`。原 IDataReader 纯历史分支按库存尾部取 count，历史 etime 未裁切库存；本任务改用原随机 Reader 的时间定位接口。13个连续组按八证券累计因子 JSON 完全相同划分，逐日 basis/factor revision 各自重推，OHLC 只取原 Reader 返回。原 QNA 最新接口与 WT 框架源码保持。

`BUILD-BOM.json` 绑定薄探针源码/二进制、CMake/ninja/cache/log与正常构建 Job，并重核既有224原 snapshot 头及12链接库；其中包含 IRdmDtReader 和 WTSBarStruct。工具SHA为编译后核实，完整外部 SDK 头的编译前清单未声明。实际RR112安装版本为1.1.2，领域依赖路径与SHA随主链结果和提前交接固定。

## 实际验证

| 原件 | 观察 | 结论 |
|---|---|---|
| `main002/RESULT.json`、`WINDOWS.json` | 401逐日窗口、644,808对 raw/analysis bars；每个日期截止、末日原价、量额和独立factor revision保持 | 原生逐基准主链通过 |
| `main002/INDEPENDENT.json` | 2025-03-05、03-18、03-19、06-17、2026-07-16、10-28六次独立原Reader，对组内裁切raw/front逐字段精确一致 | 首末、事件前后与同组中间日期通过 |
| `main002/RESULT.json` | 全部401窗实际构造安装版 AnalysisWindow/AnalysisBar、FrozenHistory、CurrentHistoryView；搬迁后全部窗口摘要一致 | 实际领域接口通过 |
| `control-main002/result.json` | 153.359秒exit0；隐藏创建期Job，未强杀，tree0/双EOF/join/句柄关闭 | 进程正常回收 |
| `boundaries002/RESULT.json` | 错摘要、越界/非交易日期、返回容器独立、改读回、错误逐日revision、未来因子组、改分析价九项 | 边界通过，原包保持 |
| `installed002/RESULT.json` | ZIP全新解压，`-I`解释器从包内lib导入，401窗摘要一致，0来源/0原生进程 | 独立安装消费通过 |
| `control-package002/result.json` | 39.125秒exit0；未强杀，tree0/双EOF/join/句柄关闭 | 打包验收正常退出 |

ZIP为 `build/qmt-native-replay-001/qmt-native-replay-002.zip`，6,475,854字节，SHA `d41ef210de2b0b60498ff08cffd35051a7198311a93c8abf619ed1f680612f92`。提前交接 `MAINPATH-HANDOFF-001.json` 单列开发主路径资格，供根交B并行消费；最终资格沿独立审查及最终交付收据。

## 保留失败与范围

main001 使用旧 IDataReader 接口，发现历史 etime 未截断并按 raw 日期约束拒绝，9.766秒正常关闭；该原件保持。package001 的未来因子组测试同时更改组末日，先触发 raw 日期校验而原因码断言不符；仅更改测试注入为保持日期分区、替换未来因子文件，package002通过，原失败及旧源码清单保留。两者均无现场、Writer或交易副作用。

窗口属于 current-visible-reconstruction，known_at/received_at 为实际重建时间，历史首次可见和修订历史均 unknown；market_available_at为空，amount为unknown/unused。前100日预热、辅助事实、实际策略BT/RT结果与历史因果资格由对应原owner核实，本模块不伪造。未操作QMT、账户、活动采集或观衡实例，未下单、撤单、生产切换或修改WT核心。完整系统仍由根集成验收。
