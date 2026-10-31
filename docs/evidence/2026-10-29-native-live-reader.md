# DataKit 当天分钟的原生读取与闭合回调

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：运行证据。日期：2026-10-29。状态：所列读取与回放范围通过，完整策略持续消费待验。

## 能力与实现

对应 WT-D03/WT-S01 的数据读取与分钟通知能力，实际接口为 `IDataReader::readKlineSlice/onMinuteEnd` 和 `IRdmDtReader::readKlineSliceByCount/readKlineSliceByRange`。策略数据管理器 `WtDtMgr::get_kline_slice` 的直接读取分支调用前者；随机查询使用后者。

沿原 `createDataReader/deleteDataReader` 与 `createRdmDtReader/deleteRdmDtReader` 工厂装配，加载采集实例的真实 sessions、commodities、contracts。配置 `path` 指向原 DataKit 存储根，原 Reader 读取 `rt/min1/{exchange}/{code}.dmb`。框架代码本轮零改动；历史专用 NativeHistoryReader 的禁止实时目录约束保持，未创建导入元数据或伪装来源身份。

验证源码：probe.cpp（外部历史/待归仓路径：`../../tests/integration/native_live_reader/probe.cpp`）。源码只创建读取者，借用切片逐块检查条数并复制，切片先释放，Reader 在基础资料/回调接收者之前释放，DLL保持加载至进程退出。

## 输入与执行

- 固定原生基线：`08b230dd05facf6d650d949bfe51054115a2ecb1`，复用 `build/native/history-public-abi/repair-001/build-002`；已有覆盖仅为已批准 NRC 空历史 count 清零。
- `WtDataStorage.dll` SHA256：`12591cf9d1073449615a6146ce2e5037ae07494002b6bffa77916844980bb838`。
- Helper：原采集安装005的 `WtDtHelper.dll`，SHA256 `50a106a44d7dcaa1c60c0c4f1b766dce69bf1738c86f914d13a240f963986c0f`。
- 稳定副本来自已完成的上午212清点；实际根为持续运行的137采集存储。510300/600000/000001，各120根、09:31—11:30，日为2026-10-29。
- 最终验证根：`build/qmt-native-live-reader-233`；外层：`build/guanheng-workspace/qmt-native-live-reader-main-234`。`INPUTS.json`、`RESULT.json`、`snapshot.json`、`actual.json`及构建/运行日志保存实际身份和结果。229/231保留此前仅读取阶段的成功原件。

最终234耗时16.516秒、退出0；子树归零、两输出EOF、读取线程join及资源关闭均通过，无强制终止。现有137/140采集持续运行，真实委托0、真实撤单0。

## 结果

稳定副本和实际采集根的六组证券读取全部通过：策略读取、随机按数量读取、随机按范围读取的120条时间标签及OHLC/量/额，与原Helper结果逐值一致。

在新建的原策略Reader中分别预热09:31第一根，再调用原 `onMinuteEnd(20261029,1130)`，每证券收到后续119根，六字段及标签逐值一致。再次通知相同分钟新增事件0，全部更新通知一次。这里使用实际上午文件回放分钟推进，未将其表述为下午自然时钟或完整CTA运行。

入口检查的228因输出容量限制终结；230包装入口缺少脚本搜索路径终结；232补齐包装器搜索路径后正常退出0。失败记录保留，均未触及QMT和采集进程。

## 范围与下一步

原生公开Reader能够消费已有实时DMB，形成中分钟的策略消费应服从原时钟/分钟结束通知和明确截止。当前结果证明上述固定截止前的数据读取与回调；下午自然调度、源重连、多日衔接、全市场完整性、图表来源投影及完整策略仍分别验收。

策略宿主继续沿原Reader接线。现有独立历史源接口仍只处理其已登记历史根和日期准入，本证据不扩大它的当天共享内存补数能力。数据单位与源资格沿原数据合同，本次比较不提升其单位结论。

## 显式受管分钟Reader候选交付

NMR build-005/candidate-002已将原WtDataReader接入自有GuanhengRealtimeReader组合器，显式minute_native启用，默认HTTP与d1保持。生产仅修改自有Factory.cpp，原分钟算法与WtDataReader源字节保持；最终规格见[受管原生分钟读取](../specs/native-minute-reader.md)。

安装及ZIP搬迁后的main-005/main-006，沿上午三证券稳定副本和活动137只读根各120根与原Helper逐值一致，09:31预热后各119次闭合通知、重复新增0。原WtCtaEngine/WtDtMgr以require_stop=true加载安装DLL，真实stop/release及Reader删除后持有副本读取通过；默认HTTP/d1、22组预算/回调/路径边界通过。独立两轴full/delta完成，自有路径容量P2已修复。

最终DLL SHA256为f5f7efecf0648c425d4c7d85f217ea670be372c95465f07081564b5db30da122；ZIP SHA256为1d6cf4366371a6bff3fc341a2f42cbc32afefb3f78c44912809f7405507ce94a。build/native-minute-reader-001的HANDOFF/DELIVERY/FINAL_INPUTS保存全部身份与原件；根ROOT-ACCEPTANCE核11份源码/33原件/371安装成员摘要一致。原模块文档检查因其他未索引文件失败的原件保留；根260/261已补共享索引并通过本地文档检查，仅授静态范围。

该候选具备所列受管Reader安装接缝，完整B CtaExecutionSession、下午自然ticker、跨日和真实策略消费继续。当前没有切换正在运行的采集或生产组件。
