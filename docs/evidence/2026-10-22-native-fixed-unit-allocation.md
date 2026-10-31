# V2固定单位纯分配器验收

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

日期：2026-10-22。范围：[NFA规格](../specs/native-fixed-unit-allocation.md)的固定信号轨迹→V2目标纯计算；源码版本`guanheng-strategy-variants==0.1.0a2`。结论：该纯计算切片独立full及时间修正delta完成；完整V2、实时、数量执行、真实来源及生产分别待验。

## 发现与实现

首轮独立full发现两项P2：Python时间解析会将`+00:60`等非法偏移归并；固定UTC+8会错判1900上海地方时及1991夏令时收盘。修正在本模块输入准入与时间策略层，先校验偏移小时/分钟范围，上海收盘使用固定IANA2026c的包内TZif。分配算法保持原实现。

包内包含393字节`Asia_Shanghai.tzif`、tzdata版权及Apache许可证。数据SHA为`bf8b7ed82fe6e63e6d98f8cea934eeac901cd16aba85eb5755ce3f8b4289ea8a`；初始化核验后加载，缺失或损坏明确失败。计算不探测宿主时区数据库、不下载数据、不依赖第三方Python运行包。结果记录时间策略与数据身份，纳入原输出字节预算。

## 独立证据

首轮full（外部历史/待归仓路径：`../../build/guanheng-workspace/reviews/native-fixed-unit-allocation-full-001.md`）报告SHA为`6c27224ad9089b1091bd9b939c07d1ac6f091cb14d7cfae4e25413eea4d2ff2a`；时间修正delta（外部历史/待归仓路径：`../../build/guanheng-workspace/reviews/native-fixed-unit-allocation-delta-002.md`）SHA为`c4335060f1d48892383eb5f63768ff294f9b7649aa263596f7170f75c2be24b9`，结论complete、原两项关闭、新增开放0。

delta从独立新安装复验72条原时间语法、30条原上海时间、30条微秒因果及12条偏移边界观察；清空宿主TZPATH、无tzdata模块、禁网络时正常导入，5类缺失/损坏资源副本明确失败。原安装前后保持。独立AST核对确认分配数学未变，另重放160个数学oracle、320前缀、50拒绝场景、21公开边缘及8项容量场景。

开发正式wheel SHA为`ba538b5ae447e2b05a7e0130cb3f473c246f56a0b3f66204fbc8f2f5bf31c45f`，C:/Python314非editable隔离安装；开发134项回归通过。独审另建新安装，32768条JSON例约2.635秒、8×4096条约2.411秒，在当前机器默认5秒预算下返回；收紧期限按领域超时拒绝。该观察不承诺任意机器或输入硬实时成功。

根任务回核记录（外部历史/待归仓路径：`../../build/guanheng-workspace/strategy-native-root-003/nfa-time-and-guosen-docs-verification.json`）确认delta990项原件、当前12项源码/规格与冻结输入一致；清单SHA为`e8ef48ef30d9d1aa731c0b83f618a233bb2a6c3fe7d40ce36a1b29b84f24aca3`。摘要核对证明身份，行为结论依据上述实际独立场景。

## 资格边界

输入仍为显式冻结信号轨迹；共享信号生产、真实数据覆盖、V2各旧调用入口差异、风险/数量映射及WT实际执行另有接线与验收。没有新增WonderTrader框架修改、资金账本、人工审批流程、终端操作或真实委托。
