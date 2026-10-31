# 持续分析窗口的近期日线缓存准备

类型：验证证据。范围：[AWP5](../specs/qmt-analysis-window-producer.md#awp5-可选日线缓存准备)。状态：普通安装 SDK 模块完成，独立审查/最终系统组合及真实来源继续。

原 v7 读取仅观察终端缓存。显式 history_preparation 将原 HPR v6 缓存副作用放在同 capture 的 CLOSURE 与 v7读取之间，复用原 BoundHistorySource binding/plan/observe、原 uptime 截止及原请求/结果留证。未知只 GET 原 UUID；准备返回保留 call_returned/coverage unknown，实际 basis 和实收时间仍来自原 v7 回读。源码修改限 AWP，Host/Agent/WT框架和复权算法保持。

首次仅补闭合日；后继从最后准备尾日含首尾推进，同日按显式间隔合并或刷新。日期按来源1d日历额度拆片，原单段观察结束后沿同一总截止继续 GET，耗尽截止保留原请求。准备配置进入完整配置身份，省略时原a5配置身份和零补齐行为保持。历史暖机继续使用已有缓存，任务/Journal容量沿原HPR边界管理。

`build/root-analysis-history-preparation-001/final001` 使用正式普通 AWP a7/WT a11/Host a12/Agent a9/core a2 的 WT工厂五组件，以及正式配对生成的单100ms 3.6.8/WinSHM正文。隔离 SDK 的 download 真正更新与原daily读取共享的内存缓存；24次准备/96次分析SDK调用，经3次原 Import/Reader/QNA/R24：basis 2026-10-28→29→29，8870→8878→8878原始日线，3208→3216→3216分析行。准备窗口28..28、28..29、29..29，三次发布身份不同，同日修订由原SDK值进入原算法。业务段155.814秒，1386安装/QA输入前后同，全部创建期与Native子树正常闭合。

冷库 immutable 审计逐一核120个原请求正文/结果/绑定与捕获记录相同，120个唯一终态成功对照120次源执行，原库SHA保持。来源正文的禁入口尝试/运输线程/真实下撤单均为零，原策略线程执行，全部连接正常关闭。观察日时钟仅在隔离夹具中按三个已闭合日状态驱动；正式工厂、HPR/v7入口及金融算法保持。

最终普通角色23发行，仅替换AWP a7/core a2，其余21wheel保持原字节；1167个旧成员相等，AWP6模块匹配冻结源，原ATI生成1376成员收据、pip check及stage_artifacts通过。core a2仅添加既有Replay API与SDK薄重导出，其401日资格沿根专属证据；本模块不重授回测资格。21项相关回归包含HPR失回执/未知/截止/同日合并/跨日及1日额度拆片，实际从新安装导入通过。

a6/corea1三轮先行主链main005保持。main001为SDK小范围QST准备额度不匹配，main002为QA Host解释器路径未重绑，main003/004为QA设置一小时刷新且首次来源晚到，均保留失败与关闭原件；后继修正QA后完成全链。main003与004还存在不同Host组合，具体影响未单独授因果结论。

本证据实际来源为隔离SDK。真实QMT、长期HPR任务保留/容量后继、整包启用与生产资格分别由根统一验收。

## 等值刷新配置的重启修正

独立审查在 a7 发现：`history_preparation.refresh_interval_seconds` 的整数1与浮点1.0具有相同运行含义，原权威配置却保留输入类型，生成不同摘要并阻止同根重启。后继 a8 从已校验的 preparation 对象取得规范化浮点间隔后参与原配置身份，省略配置的原路径保持。

`build/root-analysis-history-preparation-002` 保存原 a7 第二代冲突红例与 a8 同根 `1→1.0→1` 三代绿例；原 Pending 的请求文件和身份保持，真正间隔2仍在调用来源前拒绝。普通安装只替换 AWP wheel，其余22份 wheel 保持，23项适用回归通过；a7 未变的三轮 SDK、原生计算及关闭证据按实际文件身份复用。

必要独立 delta 审查为同根 `review/REVIEW-001.json`，SHA-256 `6b53d190fef344e17e8d7fdf909a6ac8941130d0a431cdeebcf46651de699ec8`，原P2关闭，开放发现0。它核当前1465份固定材料、原安装输入及459份主链复用文件；结论限归一修正和普通安装。原 a7 整数权威记录保持，不自动迁移既有目录；新启用按新候选目录与原发布流程执行。长期容量和实际QMT资格仍单列。
