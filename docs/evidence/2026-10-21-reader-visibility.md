# 原生历史缓存与公开 reader 插件对照

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：隔离设计验证。日期：2026-10-21。状态：reader 边界通过；完整运行策略与生产数据契约待验。

## 输入与方法

官方源码基线 `08b230dd05facf6d650d949bfe51054115a2ecb1`；使用[原生设计复核](2026-10-21-wondertrader-design-audit.md)中从原样源文件编译的 WtDataStorage/WtDtHelper DLL。结果内绑定两个 DLL、原头文件、原 reader 和 helper 源码、测试驱动及自有实验插件 SHA。没有修改 WT 框架。

外部独立进程用原 `store_bars` 写临时 DSB，用原 `read_dsb_bars` 完整回读后替换目标文件。reader 宿主保持原实例，分别测试普通文件、raw loader、final loader 的初始有数据/初始缺文件六种场景。每场景八个快照，共48个断言快照；另有自有 IDataReader 插件的6个快照正对照。

命令：`D:/workspace/qmt/.venv/Scripts/python.exe -B build/native/reader-visibility-audit/run_audit.py`。本次结果目录 `build/native/reader-visibility-audit/run-1e8749be`。源码参考快照由 `capture_sources.py` 从固定提交提取；所有证券及量价为合成输入。

## 实际结果

| 边界 | 观察 |
|---|---|
| 原 reader 初始2根，文件追加第3根 | 同一实例继续返回2根，新实例返回3根 |
| 原 reader 首次缺文件，之后发布 | 同一实例继续为空，新实例读到数据 |
| etime=0、onMinuteEnd、再次init | 均未刷新原历史缓存；loader调用次数未增长 |
| 原文件条数不变、首条close从10.25修订20.25 | 原实例仍10.25，新实例20.25 |
| 自有 IDataReader 原型保持同一对象 | 缺文件→2根→3根→修订20.25均可见 |
| 原型旧slice仍由调用者持有 | 新读看到20.25，旧slice继续保持10.25；截止时间及count范围断言通过 |

原型通过公开 factory 加载，以拥有独立数组的 WTSKlineSlice 子类维持数据生命期；原 helper 是唯一 DSB 解码器。最终原型无数据返回 nullptr，符合 CTA 消费者对非空 slice 含末条数据的前提。

## 结论及限制

原 reader 历史缓存按现有设计首次装载，实时 onMinuteEnd 读取实时映射；更新 DSB 没有公开的历史失效通知。这个结果用于明确适配责任。自有 reader 插件可以提供同实例重读，已得到运行正对照。

原型限合成证券与基础1m，不包含正式来源/资格/覆盖/预算准入和实时分钟事件，也未装载进完整 WtRunner 策略。原生 WtRunner 默认不强制二级缓存、基础1m逐次转发reader；WtPorter 强制二级缓存，单独替换 reader 仍不能保证策略重复读取可见。以上宿主区别已核对原源码，完整调用链另验。

长期职责和公开接口边界见[历史读取模块说明](../modules/wondertrader-history-visibility.md)。本结果支持继续自有插件方案，尚未产生新的框架修改申请。

附件：全部结果及摘要（外部历史/待归仓路径：`reader-visibility-2026-10-21/results.json`）、原源码引用摘要（外部历史/待归仓路径：`reader-visibility-2026-10-21/source-reference.json`）、原样reader驱动（外部历史/待归仓路径：`reader-visibility-2026-10-21/reader_probe.cpp`）、自有实验插件（外部历史/待归仓路径：`reader-visibility-2026-10-21/snapshot_reader.cpp`）、隔离执行器（外部历史/待归仓路径：`reader-visibility-2026-10-21/run_audit.py`）。附件源码用于复现本实验，不加入发布模块清单。
