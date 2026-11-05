# 辅助数据、诊断与实际费用的组合验收

类型：验证记录。时间：2026-11-06北京时间。状态：隔离主链通过，线上采用继续。承接[SDO](../specs/strategy-data-and-observability.md)、[实施方案](../migration/mainline-data-observability-20261105.md)及[原费用问题](2026-11-05-native-buy-fee-budget.md)。

## 根因与实现

三个模块已合入正式主干：辅助持续更新及历史快照、逐角色诊断及新旧报告读取、进程首错有界留存。历史补充6736条官方事实保持实际实收时间；QMT内置来源优先原则及字段核查见[研究](2026-11-05-qmt-auxiliary-api-research.md)。当前QMT证券资料的流通量缺历史统计日期，暂不能替代每日ETF份额；账户融资不能替代全市场融资。

原回测的固定20元费用预留小于实际新买入费用，出现负现金。实时和回测共用buy_fee_basis，保留原NSQ数量、信号及真实费表；回测费用估计按原C++ double运算顺序及分币四舍五入，实时考虑拆单最低费用。三项定向回归及独立delta检查通过。

组合构建逐件对比当前源码。保留Runtime13三个既有封存覆盖，其余使用已合入最终实现。遗漏既有CLI/完成归档修正及验证导入生成pyc均曾使早期候选失败；这些批次保留失败身份。当前候选补齐46模块，冻结安装的验证使用独立解释器和-I -B，保持原完整性校验。新增scripts/runtime_composition.py提供差异分类核对，发布和验证规范已同步。

## 完整业务证据

QA根为`E:/workspace/wondertrader-qa/current-day-20261105-001`。组合Runtime为`0.1.0a14+auxiliary.diagnostics.fees.3`，wheel SHA256为`bb2cc18bf7b4eb6ff23050439104495c0d31e80ef7e4c94a637fc862e9d73188`；候选安装在`E:/workspace/wondertrader-data/runtime-service-20261105-018/venv`。

- `runtime14-awp-mainline001/RESULT001.json`：固定真实QMT回放→原Native→新AWP→MarketWindowFile读回6056行，发布0→1并正常关闭；实际官方快照和持续来源合并。后续Runtime CLI/费用修改不影响该AWP代码和公式。
- `fee-smoke003/APP-VERIFIED.json`：三日原生计算→完成归档→正式App读取通过。
- `fee-replays003/APP-AND-CASH-VERIFIED.json`：原100万元、原费表、原区间两段完整原生回放及正式App配置/首尾记录读取通过，诊断可读。分别404和401条，最低现金约4921.20元，全部非负。

| 区间 | run_id | 完成归档SHA256 |
|---|---|---|
| 2025-03-05至2026-11-02 | ca52c01505d34ab680f0dbeef23807c9 | 6cc863ffb35fd9db8e6ab4e90b90bf24e672c6a16fd08923d6e39dcd9f764726 |
| 2025-03-05至2026-10-28 | 2dc1113ce5a24a0b95a8b1b70c5c81be | fbc772c3673dc9f38468b6a129ffe3e6e5dc955c3f17cc5ff3db2740ea8e6004 |

两次Native及父进程均正常exit0，无强制结束，PID已回收、管道已join。历史使用显式research-next-common-session-0925-v1假设；首次历史可知时间未知，source_qualified与execution_qualified均为false。此结果验证计算及报告完整性，不提供历史因果资格或真实交易资格。

## 线上边界与下一步

检查时原WRI40320、Native47348和独立观衡2772仍在运行；候选未替换线上。实际同账角色恢复接缝已验证允许新分析发布路径，保留金融状态，不需要新增WT框架修改。后续先部署新辅助Owner和兼容Runtime，再核真实后继收盘的字段生效、实际自然计算/目标及模拟执行、页面和新日志。历史资料在11月5日收盘后取得，不能填成此前已可用。

尚需独立观衡采用新报告读取器、全市场日线余缺核对及引用清理。当前没有需要用户决策的新增事项。
