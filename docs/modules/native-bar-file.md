# 原生历史文件适配边界

类型：模块说明。所有者：自有历史接入层。状态：限定Windows本地固定NTFS历史开发链已验证并通过[独立复核](../evidence/2026-10-22-native-history-public-abi.md)，NHA-F001已关闭；尚未发布。行为要求见[NHA规格](../specs/native-history-public-abi.md)，原实验输入边界见[vendor复核](../evidence/2026-10-22-native-history-vendor-inputs.md)。

## 职责与原生复用

该模块负责原生历史文件进入解码器前的类型、容量和不可变输入准入，以及原store输出的实际回读判定。完整DSB解码继续交给原 `WtDtHelper::read_dsb_bars`；历史索引和派生周期继续交给原IRdm/DataFactory。模块不保存另一套行情事实，不建立数据库、完整解码器或聚合器。

原Helper按帧声明大小分配解压结果，公开读取ABI没有容量参数；原store返回bool不足以单独证明文件已经完整写出。容量、并发文件身份和发布判定由接入层统一承担。原实现及边界依据见[WT数据能力](wondertrader-data-capabilities.md)和[原生存储](wondertrader-storage.md)。

## 入口与调用链

| 接口 | 调用链与所有权 |
|---|---|
| `src/GuanhengData/NativeBarFile.h/.cpp` | History的merge、回读、冻结、恢复及无IRdm读取，共用预检与原Helper解码入口 |
| `NativeFileLease` | 根路径转卷GUID，逐层固定物理祖先及最终文件，拒绝reparse与并行写删；租约覆盖按路径原生读取全过程 |
| `read_native_bar_bytes` | 预检已取得字节，创建全新私有快照并保持保护句柄，调用原Helper同步回调，复制后返回自有数组 |
| `NativeBarOutput` | 原store写全新临时身份，取得持续保护句柄，完整回读核对；经同一句柄替换后交回History原DSB/sidecar发布协议 |
| `src/GuanhengNativeBarFile/Exports.cpp` | 自有DLL导出版本、结构布局及同步读取ABI；与原Helper分开命名、加载及登记 |
| `integrations/guanheng/native_history.py` | 核自有制品摘要、ABI版本/布局及来源元数据，显式声明1m/5m/1d类型，再调用自有读取入口 |

原Helper导出保持原样。C++受管Store及IRdm路径继续使用m1；Python既有显式1m/5m/1d入口保留，文件类型必须与请求一致。支持存量文件格式不自动取得相应真实来源、完整性或复权资格。

## 容量、身份与生命周期

调用方明确提供条数及压缩文件字节预算。自有边界校验V2头、块类型、实际压缩长度、单帧、已知非零解压长度、Bar整除和条数；原生解压体与回调结果副本分别受条数预算约束。此预算约束相应分配对象，不能解释为进程RSS硬上限。

实际读取必须消费刚通过校验的相同字节。私有快照使用独占新身份，Windows保护句柄拒绝写入、删除和替换；路径前后摘要不能代替租约。回调指针只在同步回调期间有效，线程局部收集状态在异常出口恢复；声明数量、实际数量、终态与返回值必须一致。C ABI捕获异常并返回失败，错误日志回调也受异常边界保护。

完整路径保护包括各级祖先目录和reparse连接，原生按路径重开持续指向受检文件。仅终项文件拒写/拒删不足以覆盖祖先junction变化。Windows本地固定NTFS物理目录建立逐层租约并拒绝已有reparse，根路径实际交接为卷GUID；临时材料清理由本次新建文件句柄承担。实际原Helper/IRdm、同父发布及失败析构已验；盘符重映射、OOM和断电故障未注入，不扩大相应资格。

输出每次使用全新身份，旧pending文件不参与本次成功判定。原store调用后，输出存在、全量回读一致及内容摘要共同建立发布资格；发布期间持续持有保护句柄，并由该句柄执行自身替换。DSB与sidecar仍沿History原单写者、上一版保留和摘要不匹配关闭读取的恢复机制处理，两文件发布没有新增原子事务声明。

句柄、新建临时文件和收集数组分别由同步调用或输出对象拥有并释放，只清理本次创建身份。宿主在调用结束前保留依赖对象和DLL；本模块没有取得并发热卸载资格。文件保护限定Windows本地固定NTFS物理路径，输出发布限定同一父目录；其他平台在相同不变量验证前明确返回不可用。

## 失败、恢复与验证

源句柄共享冲突作为Backpressure交回原队列，保留待发布工作，后续重试。头/类型/帧/摘要错误、回调不完整和写入回读不一致均失败关闭，原已发布数据继续保留；缺失来源或单位资格沿原调用方处理，禁止通过格式正确推导来源正确。

构建及根因测试入口为 `tests/integration/native_history_public_abi/build.py` 和同目录probe；新profile从固定Git对象构建历史依赖，只叠加批准的NRC空count修正，Windows头顺序在构建侧处理。验收须绑定真实编译输入、原Helper无limited导出、自有ABI身份、文件写删/替换窗口、原写入失败、空Reader及现有历史查询/分片消费者。正在运行的构建及尚未完成的测试不形成通过证据；最终结果另入证据索引。

## 源值历史读取接口

[源值历史合同](../specs/qmt-source-history.md)复用同一原 Helper/DSB 和独立文件 ABI。Python `NativeHistory.read_source_store(root, exchange, code, *, expected_import_sha256=None)` 返回 `HistoryResult`，包含独立 `SourceHistoryBar` 与 `SourceHistoryMetadata`；量额与时间标签原值保留，单位、区间、来源和内容身份随结果提供。读取默认绑定本根成功 `qmt-import.json` 的 DSB 与 sidecar 字节，前后核身份；调用方可用独立摘要进一步固定整套制品。

源值 sidecar format=2 与原 canonical format=1 分流：`read_store` 拒绝源值，source 入口拒绝 canonical，底层文件读取与有限性校验保持共同实现。未知单位或区间按显式 unknown 返回，coverage=unknown，不构造交易日历缺失表。原 WT CTA 不自动读取此 sidecar；自有策略启动和指标消费仍需按实际要求接元数据。实际资格见[源值回归证据](../evidence/2026-10-27-qmt-real-account-budget.md)。
