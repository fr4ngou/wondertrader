# 2026-10-27 QMT本地分钟缓存直接转换

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：外部脚本直接读DAT→原QMI/Importer/Helper→WT DSB→原生Reader主路径已通过。实时与在线查询继续保留共享内存；首次大批历史优先离线导入。

## 实际结果

- 缓存目录：D:/software/guoxin/datadir/SH/60、SZ/60；库存（外部历史/待归仓路径：`../../build/qmt-local-dat-001/INVENTORY.json`）共5342份、88667127984字节，约82.58GiB。长度推算约13.85亿记录，其中两份为空；该清点不证明全部内容有效或全市场覆盖。
- 000001.SZ的287966根、510300.SH的13980根，合计301946根，直接DAT解码与[已验QMT来源链](2026-10-27-qmt-bulk-real-full.md)的时间及OHLC/volume/amount六字段逐行精确相等，比较约2.70秒。
- 新产品CLI实际convert完成：约4.82秒，两个证券进入同一WT store。
- 原生NativeHistory.read_source_store再读取两证券，与此前来源CSV逐行核对，全部一致；约5.08秒。两个DSB的SHA也与前序SHM来源产物分别完全一致。
- 具体命令/句柄/结果（外部历史/待归仓路径：`../../build/qmt-local-dat-001/REAL-MAIN.json`）、转换收据（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-local-dat-real-002/convert.json`）、原生存储（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-local-dat-real-002/store`）。

以上是本机两样本的观测耗时，不授全市场固定速度保证。原文件SHA在转换后仍相同；源文件没有被改写。布局支持8字节feffffffffffff7f头与64字节记录，本轮全部字段均与真实接口逐行核实；未知布局拒绝。

## 实现与执行边界

新增产品模块（外部历史/待归仓路径：`../../integrations/guanheng/qmt_local_dat.py`），最终SHA256 5dd16d227f909a7299a9f731f57629b6dc05b91ba22b51838f01489647a680d1，提供scan_cache/export_cache/convert_cache及export/convert CLI。调用原Importer与受管WtDtHelper，不修改WT框架、不依赖wtpy或旧QMT工程；本轮没有启动策略、Host、SDK或网络。根验证进程的导入边界明确拒绝xtquant及SHM源包。原生Helper/Reader沿原已验DLL身份复用。

首次主路径失败为Windows跨API ctime语义不同：Path.lstat返回创建时间，os.fstat返回更改时间。随后同对象比较dev/ino/size/mtime及存在的birthtime，各接口内部仍完整检查ctime前后稳定性；非空和空文件共用该规则。首失败目录保留，最终002重新执行通过。所有本轮成功受控进程均正常exit0，无可见控制台或强制结束，Job树/双EOF/读线程join/资源关闭分别已核。

来源量额单位和分钟边界保持source/unknown，离线批次身份明确local-dat，不冒充在线认证。首末标签、精确覆盖限制与此前来源一致；不因转换成功填造缺失分钟或提升生产资格。完整库存转换、多证券日常接入、策略/观衡消费、恢复与独立发行继续；边界、bad case与代码review按主路径优先顺序后置。

操作见[本地DAT手册](../runbooks/qmt-local-dat.md)，要求见[QMI-DAT](../specs/qmt-minute-import.md#qmi-dat已下载本地缓存的离线入口)。


## 后继：17只股票批量转换

首次20只整批在600000.SH原始记录的OHLC关系校验处停止，原partial保留。只读逐记录检查20只，600000.SH、600015.SH、000007.SZ分别存在开盘价低于最低价的来源记录；这只能证明当前字段解释与导入规则存在差异，不能据此断言来源损坏。记录见BATCH-INSPECTION（外部历史/待归仓路径：`../../build/qmt-local-dat-001/BATCH-INSPECTION.json`）。本轮未改价格、未跳过证券内记录；三只未纳入后继成功批次，来源含义待核。

其余17只显式清单实际进入同一个QMI/Store，共4860337根，convert进程正常退出0，约69.84秒。导入收据SHA为 `9a32f38ff13a75741d4a51cf4d4263dc04efb31539b82ba1a9c7f7bb59e50ded`；QMI SHA为 `30a6cd3fd49e9339da5428d7241b3cbf4863c0466451b98f1965590905248853`。条数与证券清单见批次主记录（外部历史/待归仓路径：`../../build/qmt-local-dat-001/BATCH-MAIN.json`）。这17只均从2021-11-01起，实际缓存尾部至2026-10-21，部分证券尾部在日内；没有补造后续分钟或宣称下载目录完整。原生逐行回读仍在本次独立步骤执行，结论完成后追加。

该结果支持离线分批转换方案，不代表全库存已完成；全缓存约13.85亿条的时间不能由单批速度直接保证。原缓存只读、无新SDK调用、无真实委托或撤单。

后继回读已完成：BATCH-NATIVE-READ（外部历史/待归仓路径：`../../build/qmt-local-dat-001/BATCH-NATIVE-READ.json`）记录17只、4860337根，原生 source Reader 与本批原值 CSV 的时间及六字段逐行全部一致。进程正常退出0，约73秒，整树归零、输出EOF、读取线程join及资源关闭均确认，无强杀。批次主记录（外部历史/待归仓路径：`../../build/qmt-local-dat-001/BATCH-MAIN.json`）已追加原件与收尾。该结果验证本批DAT→CSV/QMI→原Helper/DSB→原生Reader整链；来源字段解释仍以前述两证券SDK对照和待核差异范围为限。


后继[完整库存范围清点](2026-10-27-qmt-local-dat-inventory.md)已完成5342文件首末抽样：5284份尾部为10-21，完整转换和后续补齐仍未完成。三条已知价格关系差异均在09:31，仅形成来源口径核实方向，尚未修正或放宽校验。新inspect入口与本页此前export/convert源码身份分别登记。
