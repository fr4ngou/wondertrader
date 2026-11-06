# 旧工作树清理与撤单适配独立分支

类型：工作区清理记录。状态：本批清理及新树创建完成；撤单同步开发继续。

## 实际目录与清理范围

用户截图中的对应目录实际位于E:/workspace。wondertrader-data为业务运行数据，build/dependencies/qa/deliveries分别保存构建、依赖、验收和交付原件，不能将这些名称一并解释为Git工作树。本批只删除两个明确退役、无实际未提交成果的注册工作树。

| 删除目录（wondertrader-worktrees下） | 保留分支 | 逻辑字节 |
|---|---|---:|
| observer-sdk017-20261104 | codex/observer-sdk017-20261104 | 751710457 |
| unified-daily-formal-20261104 | codex/unified-daily-formal-20261104 | 42015441 |

两树唯一Git修改提示updatelog.md的工作字节、HEAD及index完全相同；第一树另有可重建pytest缓存，第二树无忽略材料。删除前核50份当前服务/descriptor/Native及观衡配置无候选引用，当前进程命令行无候选路径，两目录及其后代无reparse条目。解析绝对路径后使用Git worktree remove定向删除，保留原HEAD与分支并回读一致。

回收合计793725898字节，约756.96MiB。其余树包含真实未提交修改、未跟踪文件、构建或验收引用，保留；未删除运行数据、Git分支、公共依赖或归档根。清理后当前登记14树，含本次新树。

## 新工作树与后检

新目录E:/workspace/wondertrader-worktrees/qmt-cancel-reconciliation-20261106，分支codex/qmt-cancel-reconciliation-20261106，基线93ab509。仅把本次撤单同步方案及索引条目移入新树，主目录的current-history-decision修改保持原样。自有插件修改和后续验证都在新树进行，WT框架未改。

清理后金融WT10644、历史51044、证券66764、分钟19908及报价22688保持就绪；日线服务由另一个已授权发布采用70156，本次清理未启动或停止该服务。独立业务状态及后续身份以正式部署记录为准。

原件位于受控QA的worktree-audit-20261106-002：SMALL-CANDIDATES记录原始字节比较，ACTIVE-REFERENCES记录50份当前配置范围，REMOVED及RESULT记录执行、保留分支、回收和运行后检。首次无界忽略文件枚举及替代枚举因耗时停止，只终止本次诊断进程，未用其不完整结果授删除资格。

需要恢复旧工作目录时，可从原保留分支重新git worktree add；资金、持仓和委托没有本批恢复动作。撤单同步的开发和剩余资格见[专项方案](../migration/qmt-cancel-reconciliation-proposal.md)。
